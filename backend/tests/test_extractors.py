"""
Comprehensive tests for IntentGuard extractors, normalizer, and the POST /scan endpoint.
"""

import datetime
import os
import tempfile
from pathlib import Path
from PIL import Image
import docx
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
import openpyxl
from openpyxl.workbook.defined_name import DefinedName
import pikepdf
from starlette.testclient import TestClient

from backend.extractors.image_extractor import extract_image_metadata
from backend.extractors.docx_extractor import extract_docx_metadata
from backend.extractors.xlsx_extractor import extract_xlsx_metadata
from backend.extractors.pdf_extractor import extract_pdf_metadata
from backend.extractors.normalizer import normalize
from backend.ml.risk_scorer import score_risk
from backend.ml.cluster_matcher import find_location_clusters
from backend.main import app


def create_test_image(path: str):
    """Create a temporary JPEG with EXIF tags (GPS, make/model, date, software)."""
    img = Image.new("RGB", (30, 30), color="red")
    exif = img.getexif()

    # Device & Software
    exif[0x010F] = "Canon"
    exif[0x0110] = "EOS R5"
    exif[0x0131] = "Adobe Photoshop"

    # Datetime in EXIF IFD
    exif_ifd = exif.get_ifd(0x8769)
    exif_ifd[0x9003] = "2023:08:15 10:30:00"

    # GPS IFD
    gps_ifd = exif.get_ifd(0x8825)
    gps_ifd[1] = "N"
    gps_ifd[2] = (37.0, 46.0, 29.64)  # ~ 37.7749 deg
    gps_ifd[3] = "W"
    gps_ifd[4] = (122.0, 25.0, 9.96)  # ~ -122.419433 deg

    img.save(path, exif=exif)


def create_test_docx(path: str):
    """Create a temporary DOCX with core properties and tracked changes."""
    doc = docx.Document()
    doc.add_heading("Confidential Proposal", 0)
    doc.add_paragraph("This is internal draft content.")

    props = doc.core_properties
    props.author = "Jane Doe"
    props.last_modified_by = "John Smith"
    props.revision = 3
    props.comments = "Reviewed by legal"

    # Add a tracked insertion element (<w:ins>) to simulate tracked changes
    p = doc.paragraphs[0]._element
    ins = OxmlElement("w:ins")
    ins.set(qn("w:id"), "1")
    ins.set(qn("w:author"), "Jane Doe")
    p.append(ins)

    doc.save(path)


def create_test_xlsx(path: str):
    """Create a temporary XLSX with properties, hidden sheet, and external reference."""
    wb = openpyxl.Workbook()
    ws1 = wb.active
    ws1.title = "VisibleData"
    ws1["A1"] = "Public metrics"

    ws2 = wb.create_sheet(title="HiddenSalaries")
    ws2["A1"] = "Confidential Salary List"
    ws2.sheet_state = "hidden"

    wb.properties.creator = "FinanceDept"
    wb.properties.lastModifiedBy = "AuditorCorp"

    # External reference in defined names
    wb.defined_names.add(
        DefinedName("ExtReport", attr_text="[RemoteServer.xlsx]Sheet1!$A$1")
    )

    wb.save(path)


def create_test_pdf(path: str):
    """Create a temporary PDF with docinfo and XMP."""
    pdf = pikepdf.Pdf.new()
    pdf.add_blank_page()
    pdf.docinfo["/Author"] = "Internal Team"
    pdf.docinfo["/Producer"] = "IntentGuard PDF Writer"
    pdf.docinfo["/Title"] = "Security Analysis"
    pdf.docinfo["/CreationDate"] = "D:20230501120000Z"
    pdf.save(path)


def test_image_extractor():
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
        tmp_path = f.name
    try:
        create_test_image(tmp_path)
        meta = extract_image_metadata(tmp_path)

        assert meta["gps"] is not None
        assert abs(meta["gps"]["lat"] - 37.7749) < 0.001
        assert abs(meta["gps"]["lon"] - (-122.419433)) < 0.001
        assert "Canon" in meta["device"]
        assert meta["datetime"] == "2023:08:15 10:30:00"
        assert meta["software"] == "Adobe Photoshop"

        records = normalize(meta, "image")
        categories = {r["raw_key"]: r["category"] for r in records}
        assert categories["gps"] == "high"
        assert categories["device"] == "medium"
        assert categories["datetime"] == "medium"
        assert categories["software"] == "medium"
        print("[PASS] test_image_extractor & normalizer")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_docx_extractor():
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        tmp_path = f.name
    try:
        create_test_docx(tmp_path)
        meta = extract_docx_metadata(tmp_path)

        assert meta["author"] == "Jane Doe"
        assert meta["last_modified_by"] == "John Smith"
        assert meta["revision"] == "3"
        assert meta["comments"] == "Reviewed by legal"
        assert meta["has_tracked_changes"] is True

        records = normalize(meta, "docx")
        categories = {r["raw_key"]: r["category"] for r in records}
        assert categories["author"] == "high"
        assert categories["last_modified_by"] == "high"
        assert categories["has_tracked_changes"] == "high"
        assert categories["revision"] == "safe"
        assert categories["comments"] == "safe"
        print("[PASS] test_docx_extractor & normalizer")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_xlsx_extractor():
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
        tmp_path = f.name
    try:
        create_test_xlsx(tmp_path)
        meta = extract_xlsx_metadata(tmp_path)

        assert meta["creator"] == "FinanceDept"
        assert meta["last_modified_by"] == "AuditorCorp"
        assert "HiddenSalaries" in meta["hidden_sheets"]
        assert any("RemoteServer.xlsx" in link for link in (meta["external_links"] or []))

        records = normalize(meta, "xlsx")
        categories = {r["raw_key"]: r["category"] for r in records}
        assert categories["creator"] == "high"
        assert categories["last_modified_by"] == "high"
        assert categories["hidden_sheets"] == "high"
        assert categories["external_links"] == "medium"
        print("[PASS] test_xlsx_extractor & normalizer")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_pdf_extractor():
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        tmp_path = f.name
    try:
        create_test_pdf(tmp_path)
        meta = extract_pdf_metadata(tmp_path)

        assert meta["author"] == "Internal Team"
        assert meta["producer"] == "IntentGuard PDF Writer"
        assert meta["title"] == "Security Analysis"
        assert meta["creation_date"] == "D:20230501120000Z"

        records = normalize(meta, "pdf")
        categories = {r["raw_key"]: r["category"] for r in records}
        assert categories["author"] == "high"
        assert categories["producer"] == "medium"
        assert categories["creation_date"] == "medium"
        assert categories["title"] == "safe"
        print("[PASS] test_pdf_extractor & normalizer")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_scan_api_endpoint():
    client = TestClient(app)

    # 1. Health check
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}

    # 2. Test Image scan
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
        img_path = f.name
    create_test_image(img_path)
    try:
        with open(img_path, "rb") as f:
            res = client.post("/scan", files={"file": ("sample.jpg", f, "image/jpeg")})
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["filename"] == "sample.jpg"
        assert data["file_type"] == "image"
        assert len(data["metadata"]) >= 4
        print("[PASS] API /scan with JPEG")
    finally:
        if os.path.exists(img_path):
            os.remove(img_path)

    # 3. Test DOCX scan
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        docx_path = f.name
    create_test_docx(docx_path)
    try:
        with open(docx_path, "rb") as f:
            res = client.post(
                "/scan",
                files={
                    "file": (
                        "sample.docx",
                        f,
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    )
                },
            )
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["filename"] == "sample.docx"
        assert data["file_type"] == "docx"
        print("[PASS] API /scan with DOCX")
    finally:
        if os.path.exists(docx_path):
            os.remove(docx_path)

    # 4. Test XLSX scan
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
        xlsx_path = f.name
    create_test_xlsx(xlsx_path)
    try:
        with open(xlsx_path, "rb") as f:
            res = client.post(
                "/scan",
                files={
                    "file": (
                        "sample.xlsx",
                        f,
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )
                },
            )
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["filename"] == "sample.xlsx"
        assert data["file_type"] == "xlsx"
        print("[PASS] API /scan with XLSX")
    finally:
        if os.path.exists(xlsx_path):
            os.remove(xlsx_path)

    # 5. Test PDF scan
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        pdf_path = f.name
    create_test_pdf(pdf_path)
    try:
        with open(pdf_path, "rb") as f:
            res = client.post("/scan", files={"file": ("sample.pdf", f, "application/pdf")})
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["filename"] == "sample.pdf"
        assert data["file_type"] == "pdf"
        assert "overall_risk" in data
        assert data["overall_risk"]["risk_level"] in ("high", "medium", "safe")
        print("[PASS] API /scan with PDF")
    finally:
        if os.path.exists(pdf_path):
            os.remove(pdf_path)

    # 6. Test Unsupported file type (e.g. .exe or .txt)
    res = client.post("/scan", files={"file": ("malicious.exe", b"fake", "application/octet-stream")})
    assert res.status_code == 400
    assert "Unsupported file format" in res.json()["detail"]
    print("[PASS] API /scan rejects unsupported format")

    # 7. Test context parameter (anonymous vs public)
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        docx_path = f.name
    create_test_docx(docx_path)
    try:
        with open(docx_path, "rb") as f:
            res_pub = client.post(
                "/scan",
                data={"context": "public"},
                files={"file": ("sample_pub.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
            )
        assert res_pub.status_code == 200
        assert res_pub.json()["overall_risk"]["risk_level"] == "high"
        print("[PASS] API /scan with context=public")
    finally:
        if os.path.exists(docx_path):
            os.remove(docx_path)


def test_ml_risk_scorer():
    # 1. High risk with GPS
    r_gps = score_risk([{"raw_key": "gps", "category": "high"}], context="public")
    assert r_gps["risk_level"] == "high"
    assert r_gps["source"] in ("ml", "rule-based")
    assert r_gps["confidence"] > 0.5

    # 2. Author in public vs anonymous
    r_author_pub = score_risk([{"raw_key": "author", "category": "high"}], context="public")
    assert r_author_pub["risk_level"] == "high"

    r_author_anon = score_risk([{"raw_key": "author", "category": "high"}], context="anonymous")
    assert r_author_anon["risk_level"] in ("safe", "medium")

    # 3. Clean file
    r_clean = score_risk([], context="public")
    assert r_clean["risk_level"] == "safe"
    print("[PASS] test_ml_risk_scorer")


def test_cluster_matcher():
    pts = [
        {"filename": "home1.jpg", "lat": 37.774900, "lon": -122.419400},
        {"filename": "home2.jpg", "lat": 37.775050, "lon": -122.419450},  # ~20m away from home1
        {"filename": "vacation.jpg", "lat": 34.052200, "lon": -118.243700},  # Los Angeles (~550km away)
        {"filename": "nodata.jpg", "lat": None, "lon": None},
    ]
    clusters = find_location_clusters(pts)
    assert len(clusters) == 1
    assert "home1.jpg" in clusters[0]["files"]
    assert "home2.jpg" in clusters[0]["files"]
    assert "vacation.jpg" not in clusters[0]["files"]
    assert clusters[0]["radius_meters"] == 250.0
    print("[PASS] test_cluster_matcher")


def test_cross_check_endpoint():
    client = TestClient(app)

    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f1, \
         tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f2, \
         tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f3:
        p1, p2, p3 = f1.name, f2.name, f3.name

    try:
        # Create 2 images ~20m apart with GPS
        img1 = Image.new("RGB", (10, 10))
        ex1 = img1.getexif()
        gps1 = ex1.get_ifd(0x8825)
        gps1[1] = "N"
        gps1[2] = (37.77490, 0, 0)
        gps1[3] = "W"
        gps1[4] = (122.41940, 0, 0)
        img1.save(p1, exif=ex1)

        img2 = Image.new("RGB", (10, 10))
        ex2 = img2.getexif()
        gps2 = ex2.get_ifd(0x8825)
        gps2[1] = "N"
        gps2[2] = (37.77500, 0, 0)
        gps2[3] = "W"
        gps2[4] = (122.41945, 0, 0)
        img2.save(p2, exif=ex2)

        # 3rd image with no GPS
        img3 = Image.new("RGB", (10, 10))
        img3.save(p3)

        with open(p1, "rb") as f_a, open(p2, "rb") as f_b, open(p3, "rb") as f_c:
            res = client.post(
                "/cross-check",
                files=[
                    ("files", ("photo1.jpg", f_a, "image/jpeg")),
                    ("files", ("photo2.jpg", f_b, "image/jpeg")),
                    ("files", ("photo3.jpg", f_c, "image/jpeg")),
                ],
            )
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["clusters_found"] == 1
        assert "photo1.jpg" in data["clusters"][0]["files"]
        assert "photo2.jpg" in data["clusters"][0]["files"]
        assert "250m" in data["message"]
        print("[PASS] API /cross-check with 3 files")
    finally:
        for p in (p1, p2, p3):
            if os.path.exists(p):
                os.remove(p)


if __name__ == "__main__":
    print("--- Running IntentGuard Extraction & API Tests ---")
    test_image_extractor()
    test_docx_extractor()
    test_xlsx_extractor()
    test_pdf_extractor()
    test_ml_risk_scorer()
    test_cluster_matcher()
    test_scan_api_endpoint()
    test_cross_check_endpoint()
    print("--- All Tests Passed Successfully! ---")
