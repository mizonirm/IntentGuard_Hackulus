"""
Metadata stripping functions for IntentGuard.

Each cleaner accepts an input_path and output_path (strings), writes the
sanitised file to output_path, and returns nothing.  All functions are
intentionally minimal — strip the metadata, save, done.
"""

import re
import shutil
from pathlib import Path


# ---------------------------------------------------------------------------
# Image cleaner  (JPEG / PNG / TIFF)
# ---------------------------------------------------------------------------

from typing import List, Optional

# ---------------------------------------------------------------------------
# Image cleaner  (JPEG / PNG / TIFF)
# ---------------------------------------------------------------------------

def clean_image(input_path: str, output_path: str, remove_keys: Optional[List[str]] = None) -> None:
    """
    Strip EXIF data from an image.
    If remove_keys is None or empty, strip ALL EXIF data.
    If remove_keys is provided, selectively strip matching EXIF tags using piexif.
    """
    from PIL import Image

    suffix = Path(input_path).suffix.lower()

    # If no specific keys provided or requested full strip, use PIL's save without exif
    if not remove_keys:
        with Image.open(input_path) as img:
            if suffix in (".jpg", ".jpeg") and img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            save_kwargs: dict = {}
            if suffix in (".jpg", ".jpeg"):
                save_kwargs["exif"] = b""
            img.save(output_path, **save_kwargs)
        return

    keys_set = set(k.lower() for k in remove_keys)

    # Selective cleaning for JPEGs via piexif
    if suffix in (".jpg", ".jpeg"):
        try:
            import piexif
            exif_dict = piexif.load(input_path)

            # GPS
            if "gps" in keys_set:
                exif_dict["GPS"] = {}

            # Thumbnail
            if "thumbnail" in keys_set:
                exif_dict["thumbnail"] = None
                if "1st" in exif_dict:
                    exif_dict["1st"] = {}

            # Device / Camera / Make / Model
            if any(k in keys_set for k in ("device", "camera", "make", "model")):
                for tag in (piexif.ImageIFD.Make, piexif.ImageIFD.Model):
                    exif_dict.get("0th", {}).pop(tag, None)
                for tag in (
                    piexif.ExifIFD.BodySerialNumber,
                    piexif.ExifIFD.LensModel,
                    piexif.ExifIFD.LensMake,
                    piexif.ExifIFD.LensSerialNumber,
                    piexif.ExifIFD.DeviceSettingDescription,
                ):
                    exif_dict.get("Exif", {}).pop(tag, None)

            # Datetime / Timestamps
            if any(k in keys_set for k in ("datetime", "timestamp", "date")):
                exif_dict.get("0th", {}).pop(piexif.ImageIFD.DateTime, None)
                for tag in (
                    piexif.ExifIFD.DateTimeOriginal,
                    piexif.ExifIFD.DateTimeDigitized,
                    piexif.ExifIFD.SubSecTime,
                    piexif.ExifIFD.SubSecTimeOriginal,
                    piexif.ExifIFD.SubSecTimeDigitized,
                ):
                    exif_dict.get("Exif", {}).pop(tag, None)

            # Software
            if "software" in keys_set:
                exif_dict.get("0th", {}).pop(piexif.ImageIFD.Software, None)
                exif_dict.get("0th", {}).pop(piexif.ImageIFD.ProcessingSoftware, None)

            # Author / Artist / Copyright
            if any(k in keys_set for k in ("author", "artist", "copyright")):
                exif_dict.get("0th", {}).pop(piexif.ImageIFD.Artist, None)
                exif_dict.get("0th", {}).pop(piexif.ImageIFD.Copyright, None)

            exif_bytes = piexif.dump(exif_dict)
            with Image.open(input_path) as img:
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")
                img.save(output_path, exif=exif_bytes)
            return
        except Exception:
            # Fallback to full EXIF strip if piexif modification fails
            pass

    # Fallback or PNG/TIFF: full EXIF strip
    with Image.open(input_path) as img:
        if suffix in (".jpg", ".jpeg") and img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        save_kwargs: dict = {}
        if suffix in (".jpg", ".jpeg"):
            save_kwargs["exif"] = b""
        img.save(output_path, **save_kwargs)


# ---------------------------------------------------------------------------
# DOCX cleaner
# ---------------------------------------------------------------------------

def clean_docx(input_path: str, output_path: str, remove_keys: Optional[List[str]] = None) -> None:
    """
    Clear core_properties from a .docx file.
    If remove_keys is None or empty, clear all core properties.
    Otherwise selectively clear matching fields.
    """
    from docx import Document

    doc = Document(input_path)
    props = doc.core_properties

    if not remove_keys:
        # Clear all text fields
        props.author = ""
        props.last_modified_by = ""
        props.comments = ""
        props.description = ""
        props.keywords = ""
        props.subject = ""
        props.title = ""
        try:
            props.revision = 1
        except (AttributeError, TypeError):
            pass
    else:
        keys_set = set(k.lower() for k in remove_keys)
        if "author" in keys_set:
            props.author = ""
        if "last_modified_by" in keys_set:
            props.last_modified_by = ""
        if "comments" in keys_set:
            props.comments = ""
        if "description" in keys_set:
            props.description = ""
        if "keywords" in keys_set:
            props.keywords = ""
        if "subject" in keys_set:
            props.subject = ""
        if "title" in keys_set:
            props.title = ""
        if "revision" in keys_set:
            try:
                props.revision = 1
            except (AttributeError, TypeError):
                pass

    doc.save(output_path)


# ---------------------------------------------------------------------------
# XLSX cleaner
# ---------------------------------------------------------------------------

def clean_xlsx(input_path: str, output_path: str, remove_keys: Optional[List[str]] = None) -> None:
    """
    Clear workbook properties, hidden sheets, hidden rows/columns, and external
    formulas based on remove_keys. If remove_keys is None or empty, clean all.
    """
    import openpyxl

    keys_set = set(k.lower() for k in remove_keys) if remove_keys else None

    # Load data_only copy to retrieve cached calculated values for external formulas
    try:
        wb_data = openpyxl.load_workbook(input_path, data_only=True)
    except Exception:
        wb_data = None

    wb = openpyxl.load_workbook(input_path, keep_vba=True)
    props = wb.properties

    # Identity / descriptive fields
    if not keys_set or "creator" in keys_set or "author" in keys_set:
        props.creator = ""
    if not keys_set or "last_modified_by" in keys_set or "lastmodifiedby" in keys_set:
        props.lastModifiedBy = ""
    if not keys_set or "description" in keys_set:
        props.description = ""
    if not keys_set or "subject" in keys_set:
        props.subject = ""
    if not keys_set or "title" in keys_set:
        props.title = ""
    if not keys_set or "keywords" in keys_set:
        props.keywords = ""

    # Hidden sheets
    if not keys_set or "hidden_sheets" in keys_set:
        hidden = [
            ws.title
            for ws in wb.worksheets
            if ws.sheet_state in ("hidden", "veryHidden")
        ]
        for sheet_name in hidden:
            del wb[sheet_name]

    # Unhide hidden rows & columns
    clean_rows_cols = not keys_set or any(
        k in keys_set for k in ("hidden_rows_cols", "hidden_rows", "hidden_columns")
    )
    clean_ext_refs = not keys_set or any(
        k in keys_set for k in ("external_references", "external_links")
    )

    for ws in wb.worksheets:
        if clean_rows_cols:
            for rd in ws.row_dimensions.values():
                rd.hidden = False
            for cd in ws.column_dimensions.values():
                cd.hidden = False

        if clean_ext_refs:
            for row in ws.iter_rows(values_only=False):
                for cell in row:
                    val = str(cell.value or "")
                    if val.startswith("=") and "[" in val:
                        cached_val = None
                        if wb_data and ws.title in wb_data.sheetnames:
                            try:
                                cached_val = wb_data[ws.title][cell.coordinate].value
                            except Exception:
                                cached_val = None

                        if cached_val is not None and not str(cached_val).startswith("="):
                            cell.value = cached_val
                        else:
                            cell.value = re.sub(r"\[[^\]]+\.(?:xlsx|xlsm|xlsb|xls)\]", "", val)

    if clean_ext_refs and hasattr(wb, "_external_links"):
        try:
            wb._external_links = []
        except Exception:
            pass

    if wb_data:
        wb_data.close()

    wb.save(output_path)


# ---------------------------------------------------------------------------
# PDF cleaner
# ---------------------------------------------------------------------------

def clean_pdf(input_path: str, output_path: str, remove_keys: Optional[List[str]] = None) -> None:
    """
    Strip /Info dictionary and XMP metadata stream from a PDF based on remove_keys.
    If remove_keys is None or empty, clean all PDF metadata.
    """
    import pikepdf

    keys_set = set(k.lower() for k in remove_keys) if remove_keys else None

    key_map = {
        "author": "/Author",
        "producer": "/Producer",
        "creator": "/Creator",
        "title": "/Title",
        "creation_date": "/CreationDate",
        "datetime": "/CreationDate",
        "date": "/CreationDate",
        "mod_date": "/ModDate",
        "keywords": "/Keywords",
        "subject": "/Subject",
    }

    with pikepdf.open(input_path) as pdf:
        if "/Info" in pdf.trailer:
            info_obj = pdf.trailer["/Info"]
            if not keys_set:
                for key in list(info_obj.keys()):
                    del info_obj[key]
            else:
                for req_key in keys_set:
                    pdf_key = key_map.get(req_key)
                    if pdf_key and pdf_key in info_obj:
                        del info_obj[pdf_key]

        # XMP Metadata stream
        if not keys_set or "xmp" in keys_set:
            try:
                with pdf.open_metadata(set_pikepdf_as_editor=False) as meta:
                    keys = list(meta.keys())
                    for k in keys:
                        try:
                            del meta[k]
                        except Exception:
                            pass
            except Exception:
                pass

        pdf.save(output_path)

