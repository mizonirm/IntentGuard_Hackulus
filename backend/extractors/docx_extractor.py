"""
DOCX metadata extractor using python-docx.
Extracts core properties (author, last modified by, revisions, creation time, comments)
and inspects for tracked changes / hidden revisions.
"""

from typing import Any, Dict, List, Set
import xml.etree.ElementTree as ET
import zipfile
from docx import Document

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
TRACKED_TAGS: Set[str] = {
    f"{{{W_NS}}}ins",
    f"{{{W_NS}}}del",
    f"{{{W_NS}}}pPrChange",
    f"{{{W_NS}}}rPrChange",
    f"{{{W_NS}}}comment",
}


def _extract_docx_xml_tracked_changes(file_path: str) -> Dict[str, Any]:
    """
    Open the .docx as a zip archive and parse word/document.xml & word/comments.xml
    to find tracked changes (<w:ins>, <w:del>, <w:pPrChange>, <w:rPrChange>, <w:comment>).

    Extracts ONLY count, unique author names, and date ranges — NO text content is extracted or exposed.
    """
    authors: Set[str] = set()
    dates: List[str] = []
    total_changes = 0

    try:
        with zipfile.ZipFile(file_path, "r") as z:
            xml_files = [
                name
                for name in z.namelist()
                if name in ("word/document.xml", "word/comments.xml")
            ]
            for xml_name in xml_files:
                with z.open(xml_name) as f:
                    tree = ET.parse(f)
                    root = tree.getroot()
                    for elem in root.iter():
                        if elem.tag in TRACKED_TAGS:
                            total_changes += 1
                            author = elem.attrib.get(f"{{{W_NS}}}author") or elem.attrib.get("author")
                            date_str = elem.attrib.get(f"{{{W_NS}}}date") or elem.attrib.get("date")

                            if author and str(author).strip():
                                authors.add(str(author).strip())
                            if date_str and str(date_str).strip():
                                dates.append(str(date_str).strip())
    except Exception:
        pass

    authors_list = sorted(list(authors))
    date_range = None
    if dates:
        dates_sorted = sorted(dates)
        earliest = dates_sorted[0][:10] if len(dates_sorted[0]) >= 10 else dates_sorted[0]
        latest = dates_sorted[-1][:10] if len(dates_sorted[-1]) >= 10 else dates_sorted[-1]
        date_range = f"{earliest} to {latest}" if earliest != latest else earliest

    has_tracked_changes = total_changes > 0

    summary = None
    if has_tracked_changes:
        author_str = f" by {', '.join(authors_list)}" if authors_list else ""
        date_str = f" ({date_range})" if date_range else ""
        summary = f"{total_changes} tracked change(s)/comment(s){author_str}{date_str}"

    return {
        "has_tracked_changes": has_tracked_changes,
        "total_tracked_changes": total_changes if has_tracked_changes else 0,
        "tracked_change_authors": authors_list if has_tracked_changes else [],
        "tracked_change_date_range": date_range if has_tracked_changes else None,
        "tracked_changes_summary": summary,
    }


def extract_docx_metadata(file_path: str) -> Dict[str, Any]:
    """
    Extract metadata from a Word document (.docx).

    Returns:
        Dict with keys:
            - author: str or None
            - last_modified_by: str or None
            - created: ISO datetime str or None
            - modified: ISO datetime str or None
            - revision: str or None
            - comments: str or None
            - has_tracked_changes: bool
            - total_tracked_changes: int
            - tracked_change_authors: list of str
            - tracked_change_date_range: str or None
            - tracked_changes_summary: str or None
    """
    doc = Document(file_path)
    props = doc.core_properties

    xml_info = _extract_docx_xml_tracked_changes(file_path)

    return {
        "author": props.author or None,
        "last_modified_by": props.last_modified_by or None,
        "created": props.created.isoformat() if props.created else None,
        "modified": props.modified.isoformat() if props.modified else None,
        "revision": str(props.revision) if props.revision is not None else None,
        "comments": props.comments or None,
        "has_tracked_changes": xml_info["has_tracked_changes"],
        "total_tracked_changes": xml_info["total_tracked_changes"],
        "tracked_change_authors": xml_info["tracked_change_authors"],
        "tracked_change_date_range": xml_info["tracked_change_date_range"],
        "tracked_changes_summary": xml_info["tracked_changes_summary"],
    }

