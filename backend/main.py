import os
import sys
import tempfile
from pathlib import Path
from typing import List
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

# Ensure backend directory is on sys.path for extractor imports
BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from extractors.image_extractor import extract_image_metadata
from extractors.docx_extractor import extract_docx_metadata
from extractors.xlsx_extractor import extract_xlsx_metadata
from extractors.pdf_extractor import extract_pdf_metadata
from extractors.normalizer import normalize
from ml.risk_scorer import score_risk
from ml.cluster_matcher import find_location_clusters, CLUSTER_RADIUS_METERS
from cleaner.clean_file import clean_image, clean_docx, clean_xlsx, clean_pdf

app = FastAPI(
    title="IntentGuard API",
    description="Scan files for hidden metadata, score risk, and clean them.",
    version="0.1.0"
)

# CORS enabled for local frontend testing
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = BACKEND_DIR.parent / "frontend"

EXTENSION_MAP = {
    ".jpg": "image",
    ".jpeg": "image",
    ".png": "image",
    ".tif": "image",
    ".tiff": "image",
    ".docx": "docx",
    ".xlsx": "xlsx",
    ".xlsm": "xlsx",
    ".pdf": "pdf",
}


@app.get("/health")
def health_check():
    """Placeholder health check endpoint."""
    return {"status": "ok"}


@app.get("/")
def read_root():
    """Serve the frontend index.html if accessed directly from the backend root."""
    index_file = FRONTEND_DIR / "index.html"
    if index_file.is_file():
        return FileResponse(index_file)
    return {"message": "IntentGuard API is running. Check /health for status."}


@app.post("/scan")
async def scan_file(
    file: UploadFile = File(...),
    context: str = Form("public"),
):
    """
    Scan an uploaded file for metadata, normalize the fields,
    tag each with a risk category, and calculate overall ML risk.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename in upload.")

    suffix = Path(file.filename).suffix.lower()
    file_type = EXTENSION_MAP.get(suffix)

    if not file_type:
        supported_types = ", ".join(sorted(EXTENSION_MAP.keys()))
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format '{suffix}'. Supported formats: {supported_types}",
        )

    # Save to a temporary file for extractor processing
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp_path = tmp.name
            contents = await file.read()
            tmp.write(contents)

        # Route to appropriate extractor
        if file_type == "image":
            raw_metadata = extract_image_metadata(tmp_path)
        elif file_type == "docx":
            raw_metadata = extract_docx_metadata(tmp_path)
        elif file_type == "xlsx":
            raw_metadata = extract_xlsx_metadata(tmp_path)
        elif file_type == "pdf":
            raw_metadata = extract_pdf_metadata(tmp_path)
        else:
            raise HTTPException(status_code=400, detail="Unhandled file type.")

        # Normalize metadata fields
        normalized = normalize(raw_metadata, file_type)

        # Predict overall risk using ML model with rule-based fallback
        overall_risk = score_risk(normalized, context=context)

        return {
            "filename": file.filename,
            "file_type": file_type,
            "context": context,
            "raw_metadata": raw_metadata,
            "metadata": normalized,
            "overall_risk": overall_risk,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to extract metadata from '{file.filename}': {str(e)}",
        )
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass


@app.post("/cross-check")
async def cross_check_locations(files: List[UploadFile] = File(...)):
    """
    Cross-check multiple uploaded files for shared physical location patterns
    using DBSCAN with Haversine distance.
    """
    gps_points = []

    for file in files:
        if not file.filename:
            continue
        suffix = Path(file.filename).suffix.lower()
        if suffix in (".jpg", ".jpeg", ".png", ".tif", ".tiff"):
            tmp_path = None
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                    tmp_path = tmp.name
                    contents = await file.read()
                    tmp.write(contents)

                meta = extract_image_metadata(tmp_path)
                gps = meta.get("gps")
                if gps and gps.get("lat") is not None and gps.get("lon") is not None:
                    gps_points.append(
                        {
                            "filename": file.filename,
                            "lat": gps["lat"],
                            "lon": gps["lon"],
                        }
                    )
            except Exception:
                # Silently skip files that cannot be processed for GPS
                pass
            finally:
                if tmp_path and os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except OSError:
                        pass

    clusters = find_location_clusters(gps_points)
    clusters_found = len(clusters)

    if clusters_found > 0:
        total_clustered = sum(len(c["files"]) for c in clusters)
        message = (
            f"{total_clustered} files share a location within {int(CLUSTER_RADIUS_METERS)}m "
            "— this may reveal an address or routine location even though neither file alone looked risky."
        )
    else:
        message = "No shared locations detected across uploaded files."

    return {
        "clusters_found": clusters_found,
        "clusters": clusters,
        "message": message,
    }


@app.post("/clean")
async def clean_file_endpoint(
    file: UploadFile = File(...),
):
    """
    Strip all metadata from the uploaded file and return the cleaned copy
    as a file download.  Supports the same formats as /scan.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename in upload.")

    suffix = Path(file.filename).suffix.lower()
    file_type = EXTENSION_MAP.get(suffix)

    if not file_type:
        supported_types = ", ".join(sorted(EXTENSION_MAP.keys()))
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format '{suffix}'. Supported formats: {supported_types}",
        )

    tmp_input = None
    tmp_output = None
    try:
        # Write uploaded bytes to a temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as f_in:
            tmp_input = f_in.name
            f_in.write(await file.read())

        # Prepare a separate temp file for the cleaned output
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as f_out:
            tmp_output = f_out.name

        # Dispatch to the appropriate cleaner
        if file_type == "image":
            clean_image(tmp_input, tmp_output)
        elif file_type == "docx":
            clean_docx(tmp_input, tmp_output)
        elif file_type == "xlsx":
            clean_xlsx(tmp_input, tmp_output)
        elif file_type == "pdf":
            clean_pdf(tmp_input, tmp_output)
        else:
            raise HTTPException(status_code=400, detail="Unhandled file type.")

        cleaned_name = f"cleaned_{file.filename}"
        return FileResponse(
            path=tmp_output,
            media_type="application/octet-stream",
            filename=cleaned_name,
            # FileResponse streams the file; we clean up the input temp now,
            # but output temp must survive until the response body is sent.
        )

    except HTTPException:
        # Clean up both temp files on error
        for p in (tmp_input, tmp_output):
            if p and os.path.exists(p):
                try:
                    os.remove(p)
                except OSError:
                    pass
        raise
    except Exception as e:
        for p in (tmp_input, tmp_output):
            if p and os.path.exists(p):
                try:
                    os.remove(p)
                except OSError:
                    pass
        raise HTTPException(
            status_code=500,
            detail=f"Failed to clean '{file.filename}': {str(e)}",
        )
    finally:
        # Always remove the input temp file
        if tmp_input and os.path.exists(tmp_input):
            try:
                os.remove(tmp_input)
            except OSError:
                pass
        # Note: tmp_output is managed by FileResponse; do NOT delete it here.

