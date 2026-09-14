print('Geocoder script start')
import threading
import time
from typing import Optional, Dict

import requests

# Module level cache for rounded coordinates (lat, lon) -> result dict
_cache: Dict[tuple, Optional[Dict]] = {}

# Timestamp of the last successful API call (epoch seconds). Initialized to 0.
_last_call_time = 0.0
# Lock to protect shared state in multithreaded scenarios
_lock = threading.Lock()

_USER_AGENT = "IntentGuard-Hackathon-Prototype/1.0"


def _rate_limit():
    """Enforce at least 1 second between API calls.
    This function should be called while holding the module lock.
    """
    global _last_call_time
    now = time.time()
    elapsed = now - _last_call_time
    if elapsed < 1.0:
        time.sleep(1.0 - elapsed)
    _last_call_time = time.time()


def reverse_geocode(lat: float, lon: float) -> Optional[Dict]:
    """Return a simplified address dictionary for the given latitude/longitude.

    The function uses OpenStreetMap's Nominatim reverse geocoding endpoint with a
    custom ``User-Agent`` header as required by the usage policy. Results are
    cached for coordinates rounded to 5 decimal places (~1 m precision) and the
    API is rate‑limited to one request per second.

    Parameters
    ----------
    lat: float
        Latitude in decimal degrees.
    lon: float
        Longitude in decimal degrees.

    Returns
    -------
    dict or None
        Simplified address dictionary or ``None`` if the request fails.
    """
    # Round coordinates for caching (5 decimal places ≈ 1 m)
    key = (round(lat, 5), round(lon, 5))

    with _lock:
        if key in _cache:
            return _cache[key]

        # Rate limiting before making the request (cache miss)
        _rate_limit()

        url = (
            f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}&zoom=18&addressdetails=1"
        )
        headers = {"User-Agent": _USER_AGENT}
        try:
            response = requests.get(url, headers=headers, timeout=5)
            response.raise_for_status()
            data = response.json()
        except Exception:
            # Store None in cache to avoid repeated failing calls for same coords
            _cache[key] = None
            return None

        address = data.get("address", {})
        result = {
            "display_name": data.get("display_name"),
            "building": address.get("building") or address.get("amenity"),
            "road": address.get("road"),
            "suburb": address.get("suburb") or address.get("neighbourhood"),
            "city": address.get("city") or address.get("town"),
            "raw_lat": lat,
            "raw_lon": lon,
        }
        _cache[key] = result
        return result



if __name__ == "__main__":
    try:
        # Simple sanity check – prints the resolved address for Chennai, India.
        sample = reverse_geocode(13.0827, 80.2707)
        if sample:
            print(sample)
        else:
            print('No address returned (network issue or invalid coordinates)')
        print("Script executed")
    except Exception as e:
        import traceback, sys
        traceback.print_exc()
        sys.exit(1)

