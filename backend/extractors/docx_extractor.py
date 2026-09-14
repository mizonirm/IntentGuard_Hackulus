"""
DOCX metadata extractor using python-docx.
Extracts core properties (author, last modified by, revisions, creation time, comments)
and inspects for tracked changes / hidden revisions.
"""

from typing import Any, Dict
from docx import Document


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
            - has_tracked_changes: bool (detects <w:ins> and <w:del> tags; note: deep comment body inspection omitted for simplicity)
    """
    doc = Document(file_path)
    props = doc.core_properties

    # Check for tracked changes in the document body XML
    has_tracked_changes = False
    try:
        # Tracked insertions (<w:ins>) and deletions (<w:del>)
        ins_nodes = doc.element.xpath(".//w:ins")
        del_nodes = doc.element.xpath(".//w:del")
        if ins_nodes or del_nodes:
            has_tracked_changes = True
    except Exception:
        # Note limitation: Fallback if custom/non-standard namespace schema is used
        has_tracked_changes = False

    return {
        "author": props.author or None,
        "last_modified_by": props.last_modified_by or None,
        "created": props.created.isoformat() if props.created else None,
        "modified": props.modified.isoformat() if props.modified else None,
        "revision": str(props.revision) if props.revision is not None else None,
        "comments": props.comments or None,
        "has_tracked_changes": has_tracked_changes,
    }
