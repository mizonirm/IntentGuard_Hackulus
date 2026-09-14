"""
Common metadata normalizer for IntentGuard.
Converts raw extractor outputs into a standardized list of metadata records
tagged with risk categories (high, medium, safe).
"""

from typing import Any, Dict, List


FIELD_NAMES = {
    "gps": "GPS Location",
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
    "external_links": "External Links",
    "producer": "PDF Producer",
    "title": "Document Title",
    "creation_date": "Creation Date",
    "mod_date": "Modification Date",
}


def _classify_category(raw_key: str) -> str:
    """
    Classify a metadata field into high, medium, or safe:
      - GPS, author, creator, identity, tracked changes, hidden content -> high
      - Timestamps, software, device, producer, external references -> medium
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
        )
    ):
        return "medium"

    return "safe"


def normalize(raw_metadata: Dict[str, Any], file_type: str) -> List[Dict[str, str]]:
    """
    Convert extractor raw dictionary output into a standardized list of metadata records:
      [
        {
          "field": "GPS Location",
          "value": "...",
          "category": "high|medium|safe",
          "raw_key": "..."
        },
        ...
      ]
    """
    records: List[Dict[str, str]] = []

    for raw_key, val in raw_metadata.items():
        if val is None or val == "" or val == [] or val is False:
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
                records.append(
                    {
                        "field": FIELD_NAMES.get("has_tracked_changes", "Tracked Changes"),
                        "value": "Hidden / tracked revisions detected",
                        "category": "high",
                        "raw_key": "has_tracked_changes",
                    }
                )
            continue

        # 3. Hidden Sheets / Lists
        if isinstance(val, list):
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
