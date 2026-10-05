"""Driving-route calculation behind a small provider abstraction.

``OSRMRoutingProvider`` works with no API key (public OSRM demo server or a
self-hosted instance). ``OpenRouteServiceProvider`` uses the heavy-goods
vehicle profile when ``ROUTING_API_KEY`` is configured. Additional providers
only need to implement ``route(start, end) -> RouteLeg``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol

import requests
from django.conf import settings
from django.core.cache import cache

from .exceptions import ProviderUnavailableError, RoutingError
from .cache_utils import make_key
from .geo import METERS_PER_MILE, LatLng, simplify

logger = logging.getLogger(__name__)

ROUTE_NOT_FOUND = "Unable to calculate this route. Please verify your locations and try again."


@dataclass(frozen=True)
class RouteLeg:
    distance_meters: float
    duration_seconds: float
    geometry: list[LatLng]

    @property
    def distance_miles(self) -> float:
        return self.distance_meters / METERS_PER_MILE

    @property
    def duration_hours(self) -> float:
        return self.duration_seconds / 3600


class RoutingProvider(Protocol):
    name: str

    def route(self, start: LatLng, end: LatLng) -> RouteLeg: ...


def _same_point(start: LatLng, end: LatLng) -> bool:
    return abs(start.lat - end.lat) < 1e-5 and abs(start.lng - end.lng) < 1e-5


class OSRMRoutingProvider:
    name = "OSRM (OpenStreetMap)"

    def __init__(self, base_url: str, timeout: float, user_agent: str):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.user_agent = user_agent

    def route(self, start: LatLng, end: LatLng) -> RouteLeg:
        if _same_point(start, end):
            return RouteLeg(0.0, 0.0, [start])
        coords = f"{start.lng:.6f},{start.lat:.6f};{end.lng:.6f},{end.lat:.6f}"
        try:
            response = requests.get(
                f"{self.base_url}/route/v1/driving/{coords}",
                params={"overview": "full", "geometries": "geojson", "alternatives": "false", "steps": "false"},
                headers={"User-Agent": self.user_agent},
                timeout=self.timeout,
            )
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            logger.warning("OSRM request failed: %s", exc)
            raise ProviderUnavailableError("The routing service is unavailable right now. Please try again shortly.") from exc

        if payload.get("code") != "Ok" or not payload.get("routes"):
            logger.info("OSRM returned %s: %s", payload.get("code"), payload.get("message"))
            raise RoutingError(ROUTE_NOT_FOUND)
        route = payload["routes"][0]
        geometry = [LatLng(lat, lng) for lng, lat in route["geometry"]["coordinates"]]
        return RouteLeg(float(route["distance"]), float(route["duration"]), geometry)


class OpenRouteServiceProvider:
    name = "OpenRouteService (HGV profile)"

    def __init__(self, base_url: str, api_key: str, timeout: float):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def route(self, start: LatLng, end: LatLng) -> RouteLeg:
        if _same_point(start, end):
            return RouteLeg(0.0, 0.0, [start])
        try:
            response = requests.post(
                f"{self.base_url}/v2/directions/driving-hgv/geojson",
                json={"coordinates": [[start.lng, start.lat], [end.lng, end.lat]]},
                headers={"Authorization": self.api_key, "Content-Type": "application/json"},
                timeout=self.timeout,
            )
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            logger.warning("OpenRouteService request failed: %s", exc)
            raise ProviderUnavailableError("The routing service is unavailable right now. Please try again shortly.") from exc
        features = payload.get("features") or []
        if response.status_code != 200 or not features:
            logger.info("OpenRouteService error %s: %s", response.status_code, payload.get("error"))
            raise RoutingError(ROUTE_NOT_FOUND)
        feature = features[0]
        summary = feature["properties"]["summary"]
        geometry = [LatLng(lat, lng) for lng, lat in feature["geometry"]["coordinates"]]
        return RouteLeg(float(summary.get("distance", 0)), float(summary.get("duration", 0)), geometry)


def get_routing_provider() -> RoutingProvider:
    config = settings.TRIP_PLANNER
    if config["ROUTING_PROVIDER"] == "openrouteservice":
        if not config["ROUTING_API_KEY"]:
            raise ProviderUnavailableError("Routing is misconfigured: ROUTING_API_KEY is required for OpenRouteService.")
        return OpenRouteServiceProvider(
            config["OPENROUTESERVICE_BASE_URL"], config["ROUTING_API_KEY"], config["REQUEST_TIMEOUT_SECONDS"]
        )
    return OSRMRoutingProvider(config["OSRM_BASE_URL"], config["REQUEST_TIMEOUT_SECONDS"] + 10, config["HTTP_USER_AGENT"])


def calculate_leg(provider: RoutingProvider, start: LatLng, end: LatLng) -> RouteLeg:
    key = make_key("route", provider.name, f"{start.lat:.5f},{start.lng:.5f}", f"{end.lat:.5f},{end.lng:.5f}")
    if cached := cache.get(key):
        return cached
    leg = provider.route(start, end)
    # ~20 m tolerance keeps stop positioning accurate while shrinking very long routes.
    leg = RouteLeg(leg.distance_meters, leg.duration_seconds, simplify(leg.geometry, tolerance=0.0002))
    cache.set(key, leg, 60 * 60 * 12)
    return leg
