"""
XLSX metadata extractor using openpyxl.
Extracts document properties (creator, last_modified_by, created, modified),
identifies hidden sheets, and checks for external links / workbook references.
"""

import re
from typing import Any, Dict, List, Set
import xml.etree.ElementTree as ET
import zipfile
import openpyxl
from openpyxl.utils import get_column_letter

EXT_REF_PATTERN = re.compile(r"\[([^\]]+\.(?:xlsx|xlsm|xlsb|xls))\]", re.IGNORECASE)


def _extract_xlsx_zip_external_links(file_path: str) -> List[str]:
    """
    Open the .xlsx zip archive and parse xl/externalLinks/ to extract
    referenced external workbook paths/filenames.
    """
    ext_refs: Set[str] = set()
    try:
        with zipfile.ZipFile(file_path, "r") as z:
            for name in z.namelist():
                if "xl/externalLinks/_rels/" in name and name.endswith(".rels"):
                    with z.open(name) as f:
                        tree = ET.parse(f)
                        root = tree.getroot()
                        for elem in root.iter():
                            target = elem.attrib.get("Target")
                            if target and any(ext in target.lower() for ext in (".xlsx", ".xlsm", ".xlsb", ".xls")):
                                ext_refs.add(target)
                elif "xl/externalLinks/externalLink" in name and name.endswith(".xml"):
                    with z.open(name) as f:
                        tree = ET.parse(f)
                        root = tree.getroot()
                        for elem in root.iter():
                            for _, v in elem.attrib.items():
                                if any(ext in str(v).lower() for ext in (".xlsx", ".xlsm", ".xlsb", ".xls")):
                                    ext_refs.add(str(v))
    except Exception:
        pass
    return sorted(list(ext_refs))


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
            - hidden_rows_cols: list of dicts per sheet or None
            - external_references: list of deduplicated external file links or None
    """
    wb = openpyxl.load_workbook(file_path, read_only=False, data_only=False)
    props = wb.properties

    # 1. Hidden sheets
    hidden_sheets = [
        sheet.title
        for sheet in wb.worksheets
        if sheet.sheet_state in ("hidden", "veryHidden")
    ]

    # 2. Hidden rows & columns per sheet (metadata only — cell values are NOT extracted)
    hidden_rows_cols: List[Dict[str, Any]] = []
    for ws in wb.worksheets:
        hidden_rows = [
            row_idx
            for row_idx, rd in ws.row_dimensions.items()
            if rd.hidden
        ]
        hidden_cols = []
        for col_key, cd in ws.column_dimensions.items():
            if cd.hidden:
                col_letter = get_column_letter(col_key) if isinstance(col_key, int) else str(col_key)
                hidden_cols.append(col_letter)

        if hidden_rows or hidden_cols:
            hidden_rows_cols.append(
                {
                    "sheet": ws.title,
                    "hidden_rows": sorted(hidden_rows),
                    "hidden_columns": sorted(hidden_cols),
                }
            )

    # 3. External workbook references (zipfile inspection + formula regex cross-check)
    ext_refs_set: Set[str] = set(_extract_xlsx_zip_external_links(file_path))

    # Scan cell formulas for external file references like '[Financial_Model_2025.xlsx]'
    for ws in wb.worksheets:
        for row in ws.iter_rows(values_only=False):
            for cell in row:
                val = str(cell.value or "")
                if val.startswith("=") and "[" in val:
                    matches = EXT_REF_PATTERN.findall(val)
                    for m in matches:
                        ext_refs_set.add(m)

    wb.close()

    external_references = sorted(list(ext_refs_set))

    return {
        "creator": props.creator or None,
        "last_modified_by": props.lastModifiedBy or None,
        "created": props.created.isoformat() if props.created else None,
        "modified": props.modified.isoformat() if props.modified else None,
        "hidden_sheets": hidden_sheets if hidden_sheets else None,
        "hidden_rows_cols": hidden_rows_cols if hidden_rows_cols else None,
        "external_references": external_references if external_references else None,
    }
