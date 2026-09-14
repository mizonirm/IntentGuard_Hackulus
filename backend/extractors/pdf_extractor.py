"""
PDF metadata extractor using pikepdf.
Extracts document information dictionary (/Info) such as Author, Producer, CreationDate,
ModDate, Creator, Title, and XMP metadata if present.
"""

from typing import Any, Dict
import pikepdf


def extract_pdf_metadata(file_path: str) -> Dict[str, Any]:
    """
    Extract metadata from a PDF file using pikepdf.

    Returns:
        Dict with keys:
            - author: str or None
            - producer: str or None
            - creator: str or None
            - title: str or None
            - creation_date: str or None
            - mod_date: str or None
            - xmp: dict or None
    """
    with pikepdf.open(file_path) as pdf:
        docinfo = getattr(pdf, "docinfo", None)

        def _get_info(key: str):
            if not docinfo:
                return None
            try:
                val = docinfo.get(key)
                if val is not None:
                    s = str(val).strip()
                    return s if s else None
            except Exception:
                pass
            return None

        author = _get_info("/Author")
        producer = _get_info("/Producer")
        creator = _get_info("/Creator")
        title = _get_info("/Title")
        creation_date = _get_info("/CreationDate")
        mod_date = _get_info("/ModDate")

        # Extract XMP metadata if present
        xmp_data = {}
        try:
            xmp = pdf.open_metadata()
            for k, v in xmp.items():
                xmp_data[str(k)] = str(v)
        except Exception:
            xmp_data = {}

        return {
            "author": author,
            "producer": producer,
            "creator": creator,
            "title": title,
            "creation_date": creation_date,
            "mod_date": mod_date,
            "xmp": xmp_data if xmp_data else None,
        }
