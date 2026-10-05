"""Small geometry helpers: distances, polyline interpolation and simplification."""

from __future__ import annotations

import bisect
import math
from dataclasses import dataclass

EARTH_RADIUS_MILES = 3958.7613
METERS_PER_MILE = 1609.344


@dataclass(frozen=True)
class LatLng:
    lat: float
    lng: float

    def as_list(self) -> list[float]:
        return [round(self.lat, 6), round(self.lng, 6)]


def haversine_miles(a: LatLng, b: LatLng) -> float:
    lat1, lat2 = math.radians(a.lat), math.radians(b.lat)
    dlat = lat2 - lat1
    dlng = math.radians(b.lng - a.lng)
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
    return 2 * EARTH_RADIUS_MILES * math.asin(min(1.0, math.sqrt(h)))


class PolylineLocator:
    """Finds the coordinate a given distance along a route polyline.

    The provider's reported distance is treated as authoritative; the
    polyline's own length is only used to find the matching fraction.
    """

    def __init__(self, points: list[LatLng], reported_miles: float):
        if not points:
            raise ValueError("A polyline needs at least one point.")
        self.points = points
        self.reported_miles = reported_miles
        self.cumulative = [0.0]
        for prev, cur in zip(points, points[1:]):
            self.cumulative.append(self.cumulative[-1] + haversine_miles(prev, cur))

    def point_at(self, miles: float) -> LatLng:
        total = self.cumulative[-1]
        if total == 0 or self.reported_miles <= 0:
            return self.points[0]
        fraction = min(1.0, max(0.0, miles / self.reported_miles))
        target = fraction * total
        index = bisect.bisect_left(self.cumulative, target)
        if index <= 0:
            return self.points[0]
        if index >= len(self.points):
            return self.points[-1]
        seg_start, seg_end = self.cumulative[index - 1], self.cumulative[index]
        ratio = 0.0 if seg_end == seg_start else (target - seg_start) / (seg_end - seg_start)
        a, b = self.points[index - 1], self.points[index]
        return LatLng(a.lat + (b.lat - a.lat) * ratio, a.lng + (b.lng - a.lng) * ratio)


def _perpendicular_distance(p: LatLng, a: LatLng, b: LatLng) -> float:
    if a == b:
        return math.hypot(p.lat - a.lat, p.lng - a.lng)
    dx, dy = b.lng - a.lng, b.lat - a.lat
    t = ((p.lng - a.lng) * dx + (p.lat - a.lat) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    return math.hypot(p.lng - (a.lng + t * dx), p.lat - (a.lat + t * dy))


def simplify(points: list[LatLng], tolerance: float = 0.0006) -> list[LatLng]:
    """Iterative Ramer–Douglas–Peucker simplification (tolerance in degrees)."""
    if len(points) < 3:
        return list(points)
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        start, end = stack.pop()
        max_dist, index = 0.0, None
        for i in range(start + 1, end):
            dist = _perpendicular_distance(points[i], points[start], points[end])
            if dist > max_dist:
                max_dist, index = dist, i
        if index is not None and max_dist > tolerance:
            keep[index] = True
            stack.append((start, index))
            stack.append((index, end))
    return [p for p, k in zip(points, keep) if k]
