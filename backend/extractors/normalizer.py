"""
Common metadata normalizer for IntentGuard.
Converts raw extractor outputs into a standardized list of metadata records
tagged with risk categories (high, medium, safe).
"""

from typing import Any, Dict, List


FIELD_NAMES = {
    "gps": "GPS Location",
    "thumbnail_mismatch": "EXIF Thumbnail Mismatch",
    "device": "Camera Device",
    "datetime": "Capture Timestamp",
    "software": "Software",
    "author": "Author",
    "last_modified_by": "Last Modified By",
    "created": "Creation Timestamp",
    "modified": "Modification Timestamp",
    "revision": "Revision Number",
    "comments": "Comments",
    "has_tracked_changes": "Tracked Changes",
    "creator": "Creator",
    "hidden_sheets": "Hidden Sheets",
    "hidden_rows_cols": "Hidden Rows/Columns",
    "external_links": "External Links",
    "external_references": "External File References",
    "has_fake_redactions": "Unsanitized Fake Redactions",
    "producer": "PDF Producer",
    "title": "Document Title",
    "creation_date": "Creation Date",
    "mod_date": "Modification Date",
}


def _classify_category(raw_key: str) -> str:
    """
    Classify a metadata field into high, medium, or safe:
      - GPS, author, creator, identity, tracked changes, hidden content, thumbnail mismatch, external references, fake redactions -> high
      - Timestamps, software, device, producer, hidden rows/columns -> medium
      - Everything else (title, comments, revision number, etc.) -> safe
    """
    key_lower = raw_key.lower()

    if any(
        term in key_lower
        for term in (
            "gps",
            "lat",
            "lon",
            "author",
            "last_modified_by",
            "creator",
            "identity",
            "tracked_change",
            "hidden_sheet",
            "thumbnail",
            "mismatch",
            "external_reference",
            "fake_redaction",
            "redaction",
        )
    ):
        return "high"
    elif any(
        term in key_lower
        for term in (
            "date",
            "time",
            "created",
            "modified",
            "software",
            "device",
            "producer",
            "link",
            "ref",
            "hidden_rows_cols",
        )
    ):
        return "medium"

    return "safe"


def normalize(raw_metadata: Dict[str, Any], file_type: str) -> List[Dict[str, str]]:
    """
    Convert extractor raw dictionary output into a standardized list of metadata records.
    """
    records: List[Dict[str, str]] = []

    for raw_key, val in raw_metadata.items():
        if val is None or val == "" or val == [] or val is False:
            continue
        if raw_key in (
            "thumbnail_b64",
            "total_tracked_changes",
            "tracked_change_authors",
            "tracked_change_date_range",
            "tracked_changes_summary",
            "total_fake_redactions",
            "fake_redaction_details",
            "fake_redaction_summary",
        ):
            continue

        # 1. GPS Special Formatting
        if raw_key == "gps" and isinstance(val, dict):
            lat = val.get("lat")
            lon = val.get("lon")
            if lat is not None and lon is not None:
                records.append(
                    {
                        "field": FIELD_NAMES.get("gps", "GPS Location"),
                        "value": f"Lat: {lat}, Lon: {lon}",
                        "category": "high",
                        "raw_key": "gps",
                    }
                )
            continue

        # 2. Tracked Changes Boolean
        if raw_key == "has_tracked_changes":
            if val is True:
                summary_val = raw_metadata.get("tracked_changes_summary") or "Hidden / tracked revisions detected"
                records.append(
                    {
                        "field": FIELD_NAMES.get("has_tracked_changes", "Tracked Changes"),
                        "value": summary_val,
                        "category": "high",
                        "raw_key": "has_tracked_changes",
                    }
                )
            continue

        # 3. Fake Redactions Boolean
        if raw_key == "has_fake_redactions":
            if val is True:
                summary_val = raw_metadata.get("fake_redaction_summary") or "Text hidden beneath opaque overlays detected"
                records.append(
                    {
                        "field": FIELD_NAMES.get("has_fake_redactions", "Unsanitized Fake Redactions"),
                        "value": summary_val,
                        "category": "high",
                        "raw_key": "has_fake_redactions",
                    }
                )
            continue

        # 3. Hidden Sheets / Lists / Hidden Rows & Cols
        if isinstance(val, list):
            if raw_key == "hidden_rows_cols":
                parts = []
                for item in val:
                    if isinstance(item, dict):
                        sheet_name = item.get("sheet", "Unknown Sheet")
                        r_list = item.get("hidden_rows", [])
                        c_list = item.get("hidden_columns", [])
                        desc_parts = []
                        if r_list:
                            desc_parts.append(f"{len(r_list)} hidden row(s) {r_list}")
                        if c_list:
                            desc_parts.append(f"{len(c_list)} hidden col(s) {c_list}")
                        parts.append(f"Sheet '{sheet_name}': {', '.join(desc_parts)}")
                    else:
                        parts.append(str(item))
                formatted_val = "; ".join(parts)
            else:
                formatted_val = ", ".join(str(item) for item in val)

            field_name = FIELD_NAMES.get(raw_key, raw_key.replace("_", " ").title())
            records.append(
                {
                    "field": field_name,
                    "value": formatted_val,
                    "category": _classify_category(raw_key),
                    "raw_key": raw_key,
                }
            )
            continue

        # 4. Nested XMP dictionary
        if raw_key == "xmp" and isinstance(val, dict):
            for xmp_k, xmp_v in val.items():
                if xmp_v:
                    records.append(
                        {
                            "field": f"XMP: {xmp_k}",
                            "value": str(xmp_v),
                            "category": _classify_category(xmp_k),
                            "raw_key": f"xmp.{xmp_k}",
                        }
                    )
            continue

        # 5. Generic scalar fields
        field_name = FIELD_NAMES.get(raw_key, raw_key.replace("_", " ").title())
        records.append(
            {
                "field": field_name,
                "value": str(val),
                "category": _classify_category(raw_key),
                "raw_key": raw_key,
            }
        )

    return records
