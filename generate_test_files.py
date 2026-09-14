"""
IntentGuard - Test File Generator
Generates sample_files/ with realistic-but-fake embedded metadata so the
extraction engine (Phase 1) has something real to extract and score.

Usage:
    pip install piexif python-docx openpyxl pikepdf Pillow
    python generate_test_files.py

Creates:
    sample_files/test_photo.jpg   - JPG with fake GPS + camera EXIF
    sample_files/test_doc.docx    - DOCX with fake author/revision metadata
    sample_files/test_sheet.xlsx  - XLSX with a hidden sheet + creator info
    sample_files/test_file.pdf    - PDF with fake author/producer metadata
    sample_files/test_photo_2.jpg - second JPG with GPS NEAR photo 1
                                     (for testing the K-Means cross-file
                                     location-clustering feature in Phase 3)
"""

import os

OUT_DIR = "sample_files"
os.makedirs(OUT_DIR, exist_ok=True)


def deg_to_dms_rational(deg_float):
    """Convert decimal degrees to EXIF's degrees/minutes/seconds rational format."""
    deg = int(deg_float)
    min_float = (deg_float - deg) * 60
    minute = int(min_float)
    sec_float = (min_float - minute) * 60
    sec = int(sec_float * 100)
    return [(deg, 1), (minute, 1), (sec, 100)]


def make_photo(filename, lat, lon, make="Apple", model="iPhone 13",
               software="17.4.1", datetime_str="2025:03:12 14:22:31"):
    """Create a small JPG with fake GPS + camera EXIF using piexif + Pillow."""
    import piexif
    from PIL import Image

    img = Image.new("RGB", (640, 480), color=(120, 160, 200))
    path = os.path.join(OUT_DIR, filename)
    img.save(path, "jpeg")

    lat_ref = "N" if lat >= 0 else "S"
    lon_ref = "E" if lon >= 0 else "W"

    gps_ifd = {
        piexif.GPSIFD.GPSLatitudeRef: lat_ref,
        piexif.GPSIFD.GPSLatitude: deg_to_dms_rational(abs(lat)),
        piexif.GPSIFD.GPSLongitudeRef: lon_ref,
        piexif.GPSIFD.GPSLongitude: deg_to_dms_rational(abs(lon)),
    }
    zeroth_ifd = {
        piexif.ImageIFD.Make: make,
        piexif.ImageIFD.Model: model,
        piexif.ImageIFD.Software: software,
    }
    exif_ifd = {
        piexif.ExifIFD.DateTimeOriginal: datetime_str,
    }

    exif_dict = {"0th": zeroth_ifd, "Exif": exif_ifd, "GPS": gps_ifd, "1st": {}, "thumbnail": None}
    exif_bytes = piexif.dump(exif_dict)
    piexif.insert(exif_bytes, path)
    print(f"[ok] {path}  (GPS: {lat}, {lon})")


def make_docx(filename, author="Priya Shalini", last_modified_by="Bahutharivu M A",
              revision=7, comment_text="Remove the client's phone number before sending."):
    """Create a DOCX with fake author/revision metadata and a comment."""
    from docx import Document
    import datetime

    doc = Document()
    doc.add_heading("Project Proposal - Confidential Draft", level=1)
    doc.add_paragraph(
        "This document outlines the scope, timeline, and budget for the "
        "upcoming client engagement. Please review before the Friday call."
    )
    doc.add_paragraph("Contact: priya.shalini@example.com | +91 98765 43210")

    path = os.path.join(OUT_DIR, filename)
    doc.save(path)

    # python-docx exposes core_properties for direct metadata editing
    doc2 = Document(path)
    cp = doc2.core_properties
    cp.author = author
    cp.last_modified_by = last_modified_by
    cp.revision = revision
    cp.comments = comment_text
    cp.created = datetime.datetime(2025, 2, 1, 9, 15)
    cp.modified = datetime.datetime(2025, 3, 10, 18, 42)
    doc2.save(path)
    print(f"[ok] {path}  (author={author}, last_modified_by={last_modified_by})")


def make_xlsx(filename, creator="R.M. Mizoni", last_modified_by="Bahutharivu M A"):
    """Create an XLSX with visible + hidden sheet, plus creator metadata."""
    from openpyxl import Workbook
    import datetime

    wb = Workbook()
    ws1 = wb.active
    ws1.title = "Summary"
    ws1["A1"] = "Region"
    ws1["B1"] = "Revenue"
    ws1["A2"] = "South"
    ws1["B2"] = 452000

    ws2 = wb.create_sheet("Internal_Notes")
    ws2["A1"] = "Client salary band: confidential"
    ws2["A2"] = "Internal margin: 34%"
    ws2.sheet_state = "hidden"  # <-- this is the "hidden sheet" risk signal

    wb.properties.creator = creator
    wb.properties.lastModifiedBy = last_modified_by
    wb.properties.created = datetime.datetime(2025, 1, 20, 11, 0)
    wb.properties.modified = datetime.datetime(2025, 3, 5, 16, 30)

    path = os.path.join(OUT_DIR, filename)
    wb.save(path)
    print(f"[ok] {path}  (hidden sheet: Internal_Notes, creator={creator})")


def make_pdf(filename, author="Bahutharivu M A", producer="Microsoft Word",
             title="Client Contract Draft"):
    """Create a minimal PDF and set fake /Info metadata using pikepdf."""
    import pikepdf

    pdf = pikepdf.new()
    pdf.add_blank_page(page_size=(612, 792))  # letter size

    with pdf.open_metadata() as meta:
        meta["dc:title"] = title
        meta["dc:creator"] = [author]

    pdf.docinfo["/Author"] = author
    pdf.docinfo["/Producer"] = producer
    pdf.docinfo["/CreationDate"] = "D:20250228120000"
    pdf.docinfo["/ModDate"] = "D:20250310090000"

    path = os.path.join(OUT_DIR, filename)
    pdf.save(path)
    print(f"[ok] {path}  (author={author}, producer={producer})")


if __name__ == "__main__":
    # Two photos with GPS coords ~80m apart -> same real-world location.
    # Use these to demo the Phase 3 K-Means cross-file location clustering:
    # uploading both "safe-looking" photos together should flag that they
    # share a location even though neither one alone looks risky.
    make_photo("test_photo.jpg", lat=13.0827, lon=80.2707)      # Chennai pt A
    make_photo("test_photo_2.jpg", lat=13.0834, lon=80.2715)    # Chennai pt B (~100m away)
    make_photo("test_photo_far.jpg", lat=28.6139, lon=77.2090)  # Delhi - ~1,760 km from Chennai
    
    make_docx("test_doc.docx")
    make_xlsx("test_sheet.xlsx")
    make_pdf("test_file.pdf")

    print("\nDone. Files are in ./sample_files/")
    print("Use these to test Phase 1 (/scan on each file type)")
    print("and later Phase 3 (upload test_photo.jpg + test_photo_2.jpg together")
    print("to test cross-file GPS clustering).")
