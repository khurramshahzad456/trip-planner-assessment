"""Fuel interval tracking and (optional) real fuel-station lookup."""

from __future__ import annotations

import logging
import math
from concurrent.futures import ThreadPoolExecutor, as_completed
from concurrent.futures import TimeoutError as FuturesTimeout

import requests
from django.conf import settings
from django.core.cache import cache

from .cache_utils import make_key
from .geo import LatLng, haversine_miles

logger = logging.getLogger(__name__)

# Below this many miles of range the planner treats fuel as due now.
FUEL_EPSILON_MILES = 1e-6


class FuelTracker:
    """Tracks miles driven since the last fuel stop."""

    def __init__(self, interval_miles: float):
        self.interval_miles = interval_miles
        self.miles_since_fuel = 0.0  # assumption: the trip starts with a full tank

    def miles_until_fuel(self) -> float:
        return max(0.0, self.interval_miles - self.miles_since_fuel)

    def minutes_until_fuel(self, speed_mph: float) -> int:
        """Whole driving minutes possible before the interval would be exceeded."""
        return math.floor(round(self.miles_until_fuel() / speed_mph * 60, 6))

    def is_due(self, speed_mph: float) -> bool:
        return self.miles_until_fuel() <= FUEL_EPSILON_MILES or self.minutes_until_fuel(speed_mph) <= 0

    def add_miles(self, miles: float) -> None:
        self.miles_since_fuel += miles

    def refuel(self) -> None:
        self.miles_since_fuel = 0.0


def _overpass_query(points: list[LatLng], radius_m: int) -> str:
    clauses = "".join(
        f'node["amenity"="fuel"](around:{radius_m},{p.lat:.5f},{p.lng:.5f});'
        f'way["amenity"="fuel"](around:{radius_m},{p.lat:.5f},{p.lng:.5f});'
        for p in points
    )
    return f"[out:json][timeout:20];({clauses});out center tags 300;"


def _station_from_element(element: dict) -> dict | None:
    lat = element.get("lat") or element.get("center", {}).get("lat")
    lng = element.get("lon") or element.get("center", {}).get("lon")
    if lat is None or lng is None:
        return None
    tags = element.get("tags", {})
    name = tags.get("name") or tags.get("brand") or "Fuel station"
    return {
        "name": name,
        "brand": tags.get("brand"),
        "truck_friendly": tags.get("hgv") in {"yes", "designated"} or "truck" in name.lower(),
        "lat": float(lat),
        "lng": float(lng),
    }


def _query_overpass(query: str, config: dict, deadline_seconds: float = 9.0) -> list[dict] | None:
    """Race the configured Overpass mirrors; the first successful answer wins."""
    urls = config["OVERPASS_URLS"]

    def fetch(url: str) -> list[dict]:
        response = requests.post(
            url,
            data={"data": query},
            headers={"User-Agent": config["HTTP_USER_AGENT"]},
            timeout=deadline_seconds,
        )
        response.raise_for_status()
        return response.json().get("elements", [])

    pool = ThreadPoolExecutor(max_workers=len(urls))
    futures = [pool.submit(fetch, url) for url in urls]
    try:
        for future in as_completed(futures, timeout=deadline_seconds + 1):
            try:
                return future.result()
            except (requests.RequestException, ValueError) as exc:
                logger.info("Overpass mirror failed: %s", exc)
    except FuturesTimeout:
        logger.info("Overpass lookup timed out")
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
    logger.warning("Fuel station lookup unavailable; using planned route positions only.")
    return None


def find_nearby_fuel_stations(points: list[LatLng], radius_m: int = 8000) -> list[dict | None]:
    """Find the nearest real fuel station (OpenStreetMap) to each planned fuel point.

    Best effort only: returns ``None`` entries when nothing is found or the
    Overpass API is unavailable. The schedule itself never depends on this.
    """
    config = settings.TRIP_PLANNER
    if not points or not config["ENABLE_FUEL_STATION_LOOKUP"]:
        return [None] * len(points)

    key = make_key("fuel", *(f"{p.lat:.3f},{p.lng:.3f}" for p in points))
    cached = cache.get(key)
    if cached is not None:
        return cached

    elements = _query_overpass(_overpass_query(points, radius_m), config)
    if elements is None:
        return [None] * len(points)

    stations = [s for s in (_station_from_element(e) for e in elements) if s]
    results: list[dict | None] = []
    for point in points:
        best = None
        for station in stations:
            distance = haversine_miles(point, LatLng(station["lat"], station["lng"]))
            # Prefer truck-friendly stations unless a regular one is much closer.
            score = distance - (1.5 if station["truck_friendly"] else 0)
            if distance * 1609.34 <= radius_m and (best is None or score < best[0]):
                best = (score, {**station, "distance_miles": round(distance, 1)})
        results.append(best[1] if best else None)

    cache.set(key, results, 60 * 60 * 24)
    return results
