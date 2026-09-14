"""
Metadata stripping functions for IntentGuard.

Each cleaner accepts an input_path and output_path (strings), writes the
sanitised file to output_path, and returns nothing.  All functions are
intentionally minimal — strip the metadata, save, done.
"""

import shutil
from pathlib import Path


# ---------------------------------------------------------------------------
# Image cleaner  (JPEG / PNG / TIFF)
# ---------------------------------------------------------------------------

def clean_image(input_path: str, output_path: str) -> None:
    """
    Strip ALL EXIF data from an image (GPS, device, timestamps, software).

    Strategy: PIL re-save without the 'exif' kwarg drops the EXIF blob
    entirely, which works for JPEG, PNG, and TIFF without any extra library.
    piexif is not used here because PIL's approach is simpler and more
    portable across image modes (e.g. RGBA PNGs).
    """
    from PIL import Image

    suffix = Path(input_path).suffix.lower()

    with Image.open(input_path) as img:
        # Convert RGBA → RGB for JPEG (JPEG doesn't support alpha)
        if suffix in (".jpg", ".jpeg") and img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        # Save without exif; for JPEG pass 'exif=b""' explicitly to be safe
        save_kwargs: dict = {}
        if suffix in (".jpg", ".jpeg"):
            save_kwargs["exif"] = b""

        img.save(output_path, **save_kwargs)


# ---------------------------------------------------------------------------
# DOCX cleaner
# ---------------------------------------------------------------------------

def clean_docx(input_path: str, output_path: str) -> None:
    """
    Clear all core_properties from a .docx file:
    author, last_modified_by, comments, description, keywords, subject, title.
    Also resets revision to 1 (lowest valid value).
    """
    from docx import Document

    doc = Document(input_path)
    props = doc.core_properties

    # Clear text fields
    props.author = ""
    props.last_modified_by = ""
    props.comments = ""
    props.description = ""
    props.keywords = ""
    props.subject = ""
    props.title = ""

    # Reset revision counter — python-docx exposes it as an int
    try:
        props.revision = 1
    except (AttributeError, TypeError):
        pass  # read-only on some python-docx builds; skip silently

    doc.save(output_path)


# ---------------------------------------------------------------------------
# XLSX cleaner
# ---------------------------------------------------------------------------

def clean_xlsx(input_path: str, output_path: str) -> None:
    """
    Clear workbook properties (creator, lastModifiedBy, description,
    subject, title, keywords) from an .xlsx/.xlsm workbook and remove any
    hidden worksheets (hidden content itself is the risk — not just its
    visibility).
    """
    import openpyxl

    wb = openpyxl.load_workbook(input_path, keep_vba=True)
    props = wb.properties

    # Clear identity / descriptive fields
    props.creator = ""
    props.lastModifiedBy = ""
    props.description = ""
    props.subject = ""
    props.title = ""
    props.keywords = ""

    # Remove hidden sheets — a hidden sheet can contain formulas, data,
    # or personal notes that are invisible in a normal spreadsheet view.
    hidden = [
        ws.title
        for ws in wb.worksheets
        if ws.sheet_state in ("hidden", "veryHidden")
    ]
    for sheet_name in hidden:
        del wb[sheet_name]

    wb.save(output_path)


# ---------------------------------------------------------------------------
# PDF cleaner
# ---------------------------------------------------------------------------

def clean_pdf(input_path: str, output_path: str) -> None:
    """
    Strip /Info dictionary and XMP metadata stream from a PDF.

    pikepdf gives direct access to both the document information dictionary
    and the XMP metadata packet — clearing both is necessary because many
    PDF generators write the same data to both locations.
    """
    import pikepdf

    with pikepdf.open(input_path) as pdf:
        # Clear the /Info dictionary (author, producer, creator, dates, …)
        if "/Info" in pdf.trailer:
            # Remove each key individually so pikepdf doesn't keep a stub
            info_obj = pdf.trailer["/Info"]
            for key in list(info_obj.keys()):
                del info_obj[key]

        # Clear XMP metadata stream
        try:
            with pdf.open_metadata(set_pikepdf_as_editor=False) as meta:
                # Iterate over all keys and remove them
                keys = list(meta.keys())
                for k in keys:
                    try:
                        del meta[k]
                    except Exception:
                        pass
        except Exception:
            # open_metadata can fail on malformed or encrypted PDFs; skip
            pass

        pdf.save(output_path)
