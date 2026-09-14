"""
Image metadata extractor using exifread.
Extracts EXIF tags, GPS coordinates, device information, and software history.
"""

from typing import Any, Dict, Optional
import exifread


def _ratio_to_float(val: Any) -> float:
    """Safely convert exifread ratio or numeric value to float."""
    if hasattr(val, "num") and hasattr(val, "den"):
        return float(val.num) / float(val.den) if val.den != 0 else 0.0
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0


def _convert_dms_to_decimal(coords: Any, ref: Optional[str]) -> Optional[float]:
    """Convert degrees, minutes, seconds tuple/list to decimal degrees."""
    if not coords or len(coords) < 3:
        return None
    try:
        degrees = _ratio_to_float(coords[0])
        minutes = _ratio_to_float(coords[1])
        seconds = _ratio_to_float(coords[2])
        decimal = degrees + (minutes / 60.0) + (seconds / 3600.0)
        if ref and str(ref).upper() in ("S", "W"):
            decimal = -decimal
        return round(decimal, 6)
    except Exception:
        return None


def extract_image_metadata(file_path: str) -> Dict[str, Any]:
    """
    Extract EXIF metadata from an image file using exifread.

    Returns:
        Dict with keys:
            - gps: {"lat": float, "lon": float} or None
            - device: str or None
            - datetime: str or None
            - software: str or None
    """
    with open(file_path, "rb") as f:
        tags = exifread.process_file(f, details=False)

    # 1. GPS Extraction
    lat_val = tags.get("GPS GPSLatitude")
    lat_ref = tags.get("GPS GPSLatitudeRef")
    lon_val = tags.get("GPS GPSLongitude")
    lon_ref = tags.get("GPS GPSLongitudeRef")

    lat = _convert_dms_to_decimal(lat_val.values if lat_val else None, lat_ref.printable if lat_ref else None)
    lon = _convert_dms_to_decimal(lon_val.values if lon_val else None, lon_ref.printable if lon_ref else None)

    gps = {"lat": lat, "lon": lon} if (lat is not None and lon is not None) else None

    # 2. Camera Device (Make / Model)
    make = str(tags.get("Image Make", "")).strip()
    model = str(tags.get("Image Model", "")).strip()

    if make and model:
        device = f"{make} {model}" if make not in model else model
    elif make or model:
        device = make or model
    else:
        device = None

    # 3. Datetime Original
    dt = (
        tags.get("EXIF DateTimeOriginal")
        or tags.get("Image DateTime")
        or tags.get("EXIF DateTimeDigitized")
    )
    dt_str = str(dt).strip() if dt else None

    # 4. Software Tag
    software = tags.get("Image Software")
    software_str = str(software).strip() if software else None

    return {
        "gps": gps,
        "device": device,
        "datetime": dt_str,
        "software": software_str,
    }
