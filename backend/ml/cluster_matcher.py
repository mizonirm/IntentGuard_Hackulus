"""
Cross-file GPS location clustering using DBSCAN with Haversine distance.
Identifies groups of files that share physical proximity (e.g. within 250m)
even if individual files appear benign in isolation.
"""

from typing import Any, Dict, List
import numpy as np
from sklearn.cluster import DBSCAN

# Distance threshold in meters: files closer than this distance are considered to share the same physical location.
# This threshold is adjustable based on threat model (e.g. 100m for exact home/office, 250m for neighborhood block, 500m for campus).
CLUSTER_RADIUS_METERS: float = 250.0

# Mean Earth radius in meters
EARTH_RADIUS_METERS: float = 6371000.0


def find_location_clusters(gps_points: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Cluster a list of GPS points using DBSCAN with Haversine distance metric.

    Parameters:
        gps_points: list of dicts, e.g. [{"filename": "img1.jpg", "lat": 37.7749, "lon": -122.4194}, ...]

    Returns:
        List of clusters:
        [
            {
                "cluster_id": 0,
                "files": ["img1.jpg", "img2.jpg"],
                "center_lat": 37.7749,
                "center_lon": -122.4194,
                "radius_meters": 250.0,
            },
            ...
        ]
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

    # Need at least 2 points to form a cluster with min_samples=2
    if len(valid_points) < 2:
        return []

    # 2. Convert lat/lon to radians for scikit-learn DBSCAN haversine metric
    # scikit-learn's haversine metric expects coordinates in [latitude, longitude] in radians
    coords_rad = np.radians([[p["lat"], p["lon"]] for p in valid_points])

    # Convert radius in meters to radian angular distance
    eps = CLUSTER_RADIUS_METERS / EARTH_RADIUS_METERS

    # 3. Fit DBSCAN
    db = DBSCAN(eps=eps, min_samples=2, metric="haversine")
    labels = db.fit_predict(coords_rad)

    # 4. Group by cluster id (ignoring noise label -1)
    clusters_dict: Dict[int, List[Dict[str, Any]]] = {}
    for idx, cluster_id in enumerate(labels):
        if cluster_id != -1:
            clusters_dict.setdefault(cluster_id, []).append(valid_points[idx])

    # 5. Format results
    results = []
    for cluster_id, points in sorted(clusters_dict.items()):
        filenames = [p["filename"] for p in points]
        center_lat = round(float(np.mean([p["lat"] for p in points])), 6)
        center_lon = round(float(np.mean([p["lon"] for p in points])), 6)
        results.append(
            {
                "cluster_id": int(cluster_id),
                "files": filenames,
                "center_lat": center_lat,
                "center_lon": center_lon,
                "radius_meters": CLUSTER_RADIUS_METERS,
            }
        )

    return results
