from math import atan2, cos, radians, sin, sqrt
from backend.utils.text import clean_text, normalize_lookup_key

DEFAULT_COORDS = (-6.7924, 39.2083)

AREA_COORDS: dict[str, tuple[float, float]] = {
    "dar es salaam": (-6.7924, 39.2083),
    "masaki": (-6.7466, 39.2899),
    "msasani": (-6.7480, 39.2860),
    "kariakoo": (-6.8163, 39.2797),
    "ilala": (-6.8235, 39.2695),
    "kinondoni": (-6.7761, 39.2496),
    "mikocheni": (-6.7471, 39.2598),
    "posta": (-6.8158, 39.2878),
    "ubungo": (-6.7833, 39.2078),
    "temeke": (-6.8697, 39.2665),
}


def coords_for_location(*parts: str | None) -> tuple[float, float]:
    candidates = [normalize_lookup_key(part) for part in parts if clean_text(part)]
    for candidate in candidates:
        for key, coords in AREA_COORDS.items():
            if key in candidate:
                return coords
    return DEFAULT_COORDS


def haversine_km(start: tuple[float, float], end: tuple[float, float]) -> float:
    lat1, lon1 = start
    lat2, lon2 = end
    radius = 6371.0
    d_lat = radians(lat2 - lat1)
    d_lon = radians(lon2 - lon1)
    a = sin(d_lat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(d_lon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return radius * c


def interpolate_coords(
    start: tuple[float, float],
    end: tuple[float, float],
    ratio: float,
) -> tuple[float, float]:
    safe_ratio = max(0.0, min(1.0, float(ratio)))
    return (
        round(start[0] + ((end[0] - start[0]) * safe_ratio), 6),
        round(start[1] + ((end[1] - start[1]) * safe_ratio), 6),
    )
