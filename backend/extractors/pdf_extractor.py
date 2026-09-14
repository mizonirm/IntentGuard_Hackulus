"""
PDF metadata extractor using pikepdf.
Extracts document information dictionary (/Info) such as Author, Producer, CreationDate,
ModDate, Creator, Title, and XMP metadata if present.
"""

from typing import Any, Dict, List
import pdfplumber
import pikepdf


def _detect_pdf_fake_redactions(file_path: str) -> Dict[str, Any]:
    """
    Detect text runs covered by filled vector rectangles or paths using pdfplumber.
    Does NOT extract or expose the actual hidden text content.
    """
    fake_redactions: List[Dict[str, Any]] = []
    total_fake_redactions = 0

    try:
        with pdfplumber.open(file_path) as pdf:
            for page_idx, page in enumerate(pdf.pages, start=1):
                rectangles: List[tuple] = []

                # Extract filled vector rectangles
                for rect in page.rects:
                    if rect.get("fill"):
                        x0 = float(rect.get("x0", 0))
                        top = float(rect.get("top", 0))
                        x1 = float(rect.get("x1", 0))
                        bottom = float(rect.get("bottom", 0))
                        w = abs(x1 - x0)
                        h = abs(bottom - top)
                        if w > 3 and h > 3:
                            rectangles.append((x0, top, x1, bottom))

                # Extract filled vector curves/paths
                for curve in page.curves:
                    if curve.get("fill"):
                        x0 = float(curve.get("x0", 0))
                        top = float(curve.get("top", 0))
                        x1 = float(curve.get("x1", 0))
                        bottom = float(curve.get("bottom", 0))
                        w = abs(x1 - x0)
                        h = abs(bottom - top)
                        if w > 3 and h > 3:
                            rectangles.append((x0, top, x1, bottom))

                if not rectangles:
                    continue

                words = page.extract_words()
                page_fake_count = 0
                page_bboxes: List[List[float]] = []

                for word in words:
                    word_text = str(word.get("text", "")).strip().upper()
                    # Skip literal redaction placeholders (e.g. "[REDACTED]")
                    if "REDACTED" in word_text:
                        continue

                    wx0 = float(word.get("x0", 0))
                    wtop = float(word.get("top", 0))
                    wx1 = float(word.get("x1", 0))
                    wbottom = float(word.get("bottom", 0))
                    w_area = (wx1 - wx0) * (wbottom - wtop)
                    if w_area <= 0:
                        continue

                    # Check overlap with filled shapes
                    for rx0, rtop, rx1, rbottom in rectangles:
                        ox0 = max(wx0, rx0)
                        otop = max(wtop, rtop)
                        ox1 = min(wx1, rx1)
                        obottom = min(wbottom, rbottom)

                        if ox1 > ox0 and obottom > otop:
                            overlap_area = (ox1 - ox0) * (obottom - otop)
                            if (overlap_area / w_area) > 0.5:
                                page_fake_count += 1
                                page_bboxes.append([round(wx0, 1), round(wtop, 1), round(wx1, 1), round(wbottom, 1)])
                                break

                if page_fake_count > 0:
                    total_fake_redactions += page_fake_count
                    fake_redactions.append({
                        "page": page_idx,
                        "count": page_fake_count,
                        "bboxes": page_bboxes,
                    })

    except Exception:
        pass

    has_fake = total_fake_redactions > 0
    summary = None
    if has_fake:
        pages_affected = sorted(list({item["page"] for item in fake_redactions}))
        pages_str = ", ".join(str(p) for p in pages_affected)
        summary = (
            f"{total_fake_redactions} instance(s) of text hidden beneath opaque overlays found across {len(pages_affected)} page(s) (Page {pages_str}) — "
            f"this content is fully recoverable via copy-paste despite appearing redacted."
        )

    return {
        "has_fake_redactions": has_fake,
        "total_fake_redactions": total_fake_redactions if has_fake else 0,
        "fake_redaction_details": fake_redactions if has_fake else [],
        "fake_redaction_summary": summary,
    }


def extract_pdf_metadata(file_path: str) -> Dict[str, Any]:
    """
    Extract metadata from a PDF file using pikepdf and pdfplumber.

    Returns:
        Dict with keys:
            - author: str or None
            - producer: str or None
            - creator: str or None
            - title: str or None
            - creation_date: str or None
            - mod_date: str or None
            - xmp: dict or None
            - has_fake_redactions: bool
            - total_fake_redactions: int
            - fake_redaction_details: list of dicts
            - fake_redaction_summary: str or None
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

        # Detect fake redactions (text underneath solid vector overlays)
        redaction_info = _detect_pdf_fake_redactions(file_path)

        return {
            "author": author,
            "producer": producer,
            "creator": creator,
            "title": title,
            "creation_date": creation_date,
            "mod_date": mod_date,
            "xmp": xmp_data if xmp_data else None,
            "has_fake_redactions": redaction_info["has_fake_redactions"],
            "total_fake_redactions": redaction_info["total_fake_redactions"],
            "fake_redaction_details": redaction_info["fake_redaction_details"],
            "fake_redaction_summary": redaction_info["fake_redaction_summary"],
        }
