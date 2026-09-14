"""
Image metadata extractor using exifread.
Extracts EXIF tags, GPS coordinates, device information, and software history.
"""

import base64
import io
from typing import Any, Dict, Optional
import exifread
import piexif
from PIL import Image
import numpy as np


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


def _check_thumbnail_mismatch(file_path: str) -> Optional[Dict[str, str]]:
    """
    Extract embedded EXIF thumbnail using piexif and compare with main image.
    Returns a dict with mismatch description and base64 data URL if pixel difference exceeds 15%.
    """
    try:
        exif_dict = piexif.load(file_path)
        thumb_bytes = exif_dict.get("thumbnail")
        if not thumb_bytes:
            return None

        # Load main image and thumbnail
        with Image.open(file_path) as main_img:
            main_rgb = main_img.convert("RGB").resize((64, 64))

        with Image.open(io.BytesIO(thumb_bytes)) as thumb_img:
            thumb_rgb = thumb_img.convert("RGB").resize((64, 64))

        # Calculate mean pixel difference percentage
        arr1 = np.array(main_rgb, dtype=np.float32)
        arr2 = np.array(thumb_rgb, dtype=np.float32)
        diff_pct = float(np.mean(np.abs(arr1 - arr2)) / 255.0 * 100.0)

        if diff_pct > 15.0:
            b64_str = base64.b64encode(thumb_bytes).decode("ascii")
            return {
                "message": f"Embedded thumbnail mismatch detected ({diff_pct:.1f}% difference). Original un-cropped image may linger in EXIF metadata.",
                "thumbnail_b64": f"data:image/jpeg;base64,{b64_str}",
            }
    except Exception:
        pass
    return None


def extract_image_metadata(file_path: str) -> Dict[str, Any]:
    """
    Extract EXIF metadata from an image file using exifread & piexif.

    Returns:
        Dict with keys:
            - gps: {"lat": float, "lon": float} or None
            - device: str or None
            - datetime: str or None
            - software: str or None
            - thumbnail_mismatch: str or None
            - thumbnail_b64: str or None
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

    # 5. EXIF Thumbnail Mismatch Analysis
    thumb_info = _check_thumbnail_mismatch(file_path)
    thumbnail_mismatch = thumb_info["message"] if thumb_info else None
    thumbnail_b64 = thumb_info["thumbnail_b64"] if thumb_info else None

    return {
        "gps": gps,
        "device": device,
        "datetime": dt_str,
        "software": software_str,
        "thumbnail_mismatch": thumbnail_mismatch,
        "thumbnail_b64": thumbnail_b64,
    }

