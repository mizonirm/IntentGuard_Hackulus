"""
Cross-file GPS location clustering using DBSCAN with Haversine distance.
Identifies groups of files that share physical proximity (e.g. within 250m)
even if individual files appear benign in isolation.
"""

from typing import Any, Dict, List
import math
import numpy as np
from sklearn.cluster import DBSCAN

# Pre‑filter radius (meters) used for the cheap DBSCAN pass.
# This is a loose net to find roughly nearby points; the final decision
# is based on address matching.
PRE_FILTER_RADIUS_METERS: float = 1000.0

# Mean Earth radius in meters
EARTH_RADIUS_METERS: float = 6371000.0

# Import the reverse geocoder helper
from .geocoder import reverse_geocode

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return great‑circle distance between two lat/lon points in meters."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_METERS * math.asin(math.sqrt(a))

def addresses_match(addr1: Dict[str, Any], addr2: Dict[str, Any]) -> bool:
    """
    Simple explainable rule to decide whether two reverse‑geocoded addresses refer to the same location.

    A match is declared when either:
    * Both have a non‑null ``building`` field and the values are equal (case‑insensitive).
    * Both have the same ``road`` *and* the same ``suburb`` (case‑insensitive).

    Returns False if either address is None or lacking the required fields.
    """
    if not addr1 or not addr2:
        return False

    b1 = addr1.get("building")
    b2 = addr2.get("building")
    if b1 and b2 and b1.strip().lower() == b2.strip().lower():
        return True

    road1 = addr1.get("road")
    road2 = addr2.get("road")
    suburb1 = addr1.get("suburb")
    suburb2 = addr2.get("suburb")
    if road1 and road2 and suburb1 and suburb2:
        if (road1.strip().lower() == road2.strip().lower() and
                suburb1.strip().lower() == suburb2.strip().lower()):
            return True

    return False

def find_location_clusters(gps_points: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Cluster GPS points using a cheap DBSCAN pre‑filter and then refine clusters
    with address matching via the reverse‑geocoder.

    Returns a list of cluster dictionaries. Each dictionary contains:
        - cluster_id: int
        - files: list of filenames belonging to the cluster
        - center_lat, center_lon: centroid of the retained points
        - radius_meters: PRE_FILTER_RADIUS_METERS (the pre‑filter radius)
        - matched_address: a representative address string that justified the match
    """
    # 1. Filter out entries with missing or invalid GPS coordinates
    valid_points = []
    for item in gps_points:
        lat = item.get("lat")
        lon = item.get("lon")
        if lat is not None and lon is not None:
            try:
                valid_points.append(
                    {
                        "filename": str(item.get("filename", "unknown")),
                        "lat": float(lat),
                        "lon": float(lon),
                    }
                )
            except (ValueError, TypeError):
                continue

    if len(valid_points) < 2:
        return []

    # 2. DBSCAN pre‑filter (coordinates in radians for haversine metric)
    coords_rad = np.radians([[p["lat"], p["lon"]] for p in valid_points])
    eps = PRE_FILTER_RADIUS_METERS / EARTH_RADIUS_METERS
    db = DBSCAN(eps=eps, min_samples=2, metric="haversine")
    labels = db.fit_predict(coords_rad)

    # 3. Group by cluster id (ignore noise label -1)
    clusters_dict: Dict[int, List[Dict[str, Any]]] = {}
    for idx, cid in enumerate(labels):
        if cid != -1:
            clusters_dict.setdefault(cid, []).append(valid_points[idx])

    results: List[Dict[str, Any]] = []
    next_cluster_id = 0
    for _, points in sorted(clusters_dict.items()):
        # Resolve addresses for each point (cached internally)
        point_infos = []
        for pt in points:
            addr = reverse_geocode(pt["lat"], pt["lon"])  # type: ignore[arg-type]
            point_infos.append({"point": pt, "addr": addr})

        retained: List[Dict[str, Any]] = []
        representative_addr: str | None = None
        for i, info_i in enumerate(point_infos):
            matched = False
            for j, info_j in enumerate(point_infos):
                if i == j:
                    continue
                dist = haversine_distance(
                    info_i["point"]["lat"], info_i["point"]["lon"],
                    info_j["point"]["lat"], info_j["point"]["lon"]
                )
                # 1. Direct physical proximity check (within 250m)
                if dist <= 250.0:
                    matched = True
                    if not representative_addr:
                        if info_i["addr"] and info_i["addr"].get("display_name"):
                            representative_addr = info_i["addr"].get("display_name")
                        elif info_j["addr"] and info_j["addr"].get("display_name"):
                            representative_addr = info_j["addr"].get("display_name")
                    break
                # 2. Extended address-based matching for points between 250m and 1000m
                elif addresses_match(info_i["addr"], info_j["addr"]):
                    matched = True
                    if not representative_addr and info_i["addr"]:
                        representative_addr = info_i["addr"].get("display_name")
                    break
            if matched:
                retained.append(info_i["point"])

        if len(retained) < 2:
            continue

        filenames = [p["filename"] for p in retained]
        center_lat = round(float(np.mean([p["lat"] for p in retained])), 6)
        center_lon = round(float(np.mean([p["lon"] for p in retained])), 6)
        results.append(
            {
                "cluster_id": next_cluster_id,
                "files": filenames,
                "center_lat": center_lat,
                "center_lon": center_lon,
                "radius_meters": PRE_FILTER_RADIUS_METERS,
                "matched_address": representative_addr or "",
            }
        )
        next_cluster_id += 1

    return results

