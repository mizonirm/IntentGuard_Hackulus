"""
XLSX metadata extractor using openpyxl.
Extracts document properties (creator, last_modified_by, created, modified),
identifies hidden sheets, and checks for external links / workbook references.
"""

from typing import Any, Dict
import openpyxl


def extract_xlsx_metadata(file_path: str) -> Dict[str, Any]:
    """
    Extract metadata from an Excel workbook (.xlsx).

    Returns:
        Dict with keys:
            - creator: str or None
            - last_modified_by: str or None
            - created: ISO datetime str or None
            - modified: ISO datetime str or None
            - hidden_sheets: list of sheet names or None
            - external_links: list of external link references or None
    """
    wb = openpyxl.load_workbook(file_path, read_only=False, data_only=True)
    props = wb.properties

    # 1. Hidden sheets
    hidden_sheets = [
        sheet.title
        for sheet in wb.worksheets
        if sheet.sheet_state in ("hidden", "veryHidden")
    ]

    # 2. External links and references
    external_links = []
    # Check openpyxl external links table
    ext_links = getattr(wb, "_external_links", None) or getattr(wb, "external_links", None)
    if ext_links:
        for link in ext_links:
            target = getattr(link, "target", None) or getattr(link, "Target", None)
            if target:
                external_links.append(str(target))
            elif hasattr(link, "file_link"):
                external_links.append(str(link.file_link))
            else:
                external_links.append(str(link))

    # Check defined names for external file/network references
    if hasattr(wb, "defined_names") and wb.defined_names:
        name_list = []
        if hasattr(wb.defined_names, "values"):
            try:
                name_list = list(wb.defined_names.values())
            except Exception:
                name_list = []
        elif hasattr(wb.defined_names, "definedName"):
            name_list = getattr(wb.defined_names, "definedName", [])

        for name in name_list:
            val = getattr(name, "value", "") or getattr(name, "attr_text", "")
            if val and ("[" in val or "http://" in val or "https://" in val or "\\\\" in val):
                name_title = getattr(name, "name", "ExternalRef")
                external_links.append(f"{name_title}: {val}")

    wb.close()

    return {
        "creator": props.creator or None,
        "last_modified_by": props.lastModifiedBy or None,
        "created": props.created.isoformat() if props.created else None,
        "modified": props.modified.isoformat() if props.modified else None,
        "hidden_sheets": hidden_sheets if hidden_sheets else None,
        "external_links": external_links if external_links else None,
    }
