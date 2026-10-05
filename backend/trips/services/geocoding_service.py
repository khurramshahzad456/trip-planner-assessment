"""Geocoding, autocomplete and reverse geocoding using free OpenStreetMap services.

* Nominatim is the primary forward geocoder (max 1 request/second per its policy).
* Photon (Komoot) is the fallback geocoder and powers type-ahead autocomplete,
  which Nominatim's usage policy does not allow.
* Stops along the route are labelled ("near Pecos, TX") by racing Photon and
  Nominatim reverse lookups against a deadline; labels are cosmetic, so a
  slow provider never blocks a trip plan.
"""

from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass

import requests
from django.conf import settings
from django.core.cache import cache

from .cache_utils import make_key
from .exceptions import GeocodingError
from .geo import LatLng

logger = logging.getLogger(__name__)

US_STATE_CODES = {
    "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR", "California": "CA",
    "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE", "District of Columbia": "DC",
    "Florida": "FL", "Georgia": "GA", "Hawaii": "HI", "Idaho": "ID", "Illinois": "IL",
    "Indiana": "IN", "Iowa": "IA", "Kansas": "KS", "Kentucky": "KY", "Louisiana": "LA",
    "Maine": "ME", "Maryland": "MD", "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN",
    "Mississippi": "MS", "Missouri": "MO", "Montana": "MT", "Nebraska": "NE", "Nevada": "NV",
    "New Hampshire": "NH", "New Jersey": "NJ", "New Mexico": "NM", "New York": "NY",
    "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK", "Oregon": "OR",
    "Pennsylvania": "PA", "Rhode Island": "RI", "South Carolina": "SC", "South Dakota": "SD",
    "Tennessee": "TN", "Texas": "TX", "Utah": "UT", "Vermont": "VT", "Virginia": "VA",
    "Washington": "WA", "West Virginia": "WV", "Wisconsin": "WI", "Wyoming": "WY",
}
PLACE_TYPES = {"city", "town", "village", "hamlet", "district", "county", "state", "locality"}
PROVIDER_ERRORS = (requests.RequestException, ValueError, KeyError, TypeError)


@dataclass(frozen=True)
class GeocodedLocation:
    query: str
    label: str  # short, e.g. "Phoenix, AZ"
    display_name: str  # full provider name
    lat: float
    lng: float

    @property
    def point(self) -> LatLng:
        return LatLng(self.lat, self.lng)

    def to_dict(self) -> dict:
        return asdict(self)


def _config() -> dict:
    return settings.TRIP_PLANNER


def _get(url: str, params: dict, timeout: float | None = None) -> requests.Response:
    response = requests.get(
        url,
        params=params,
        headers={"User-Agent": _config()["HTTP_USER_AGENT"], "Accept-Language": "en"},
        timeout=timeout or _config()["REQUEST_TIMEOUT_SECONDS"],
    )
    response.raise_for_status()
    return response


def _country_codes() -> set[str]:
    return {c.strip().upper() for c in _config()["GEOCODING_COUNTRY_CODES"].split(",") if c.strip()}


def _state_code(state: str | None) -> str | None:
    return US_STATE_CODES.get(state or "", state)


def _join(*parts: str | None) -> str:
    return ", ".join(p for p in parts if p)


def _locality(props: dict) -> str | None:
    for key in ("city", "town", "village", "hamlet"):
        if props.get(key):
            return props[key]
    if props.get("county"):
        county = props["county"]
        return county if county.lower().endswith(("county", "parish", "borough")) else f"{county} County"
    return None


# ---- Nominatim (rate limited) -----------------------------------------------------
_nominatim_lock = threading.Lock()
_nominatim_last_call = 0.0


def _nominatim(path: str, params: dict) -> object:
    global _nominatim_last_call
    with _nominatim_lock:
        wait = 1.0 - (time.monotonic() - _nominatim_last_call)
        if wait > 0:
            time.sleep(wait)
        try:
            return _get(f"{_config()['NOMINATIM_BASE_URL']}/{path}", {**params, "format": "jsonv2", "addressdetails": 1}).json()
        finally:
            _nominatim_last_call = time.monotonic()


def _nominatim_state(address: dict) -> str | None:
    iso = address.get("ISO3166-2-lvl4", "")
    return iso.split("-")[-1] if iso.startswith("US-") else _state_code(address.get("state"))


def _nominatim_search(query: str) -> GeocodedLocation | None:
    params = {"q": query, "limit": 1}
    if _config()["GEOCODING_COUNTRY_CODES"]:
        params["countrycodes"] = _config()["GEOCODING_COUNTRY_CODES"]
    results = _nominatim("search", params)
    if not results:
        return None
    best = results[0]
    address = best.get("address", {})
    locality = _locality(address)
    name = best.get("name")
    if best.get("addresstype") in PLACE_TYPES:
        head = None
        locality = name or locality
    else:
        head = name or _join(address.get("house_number"), address.get("road")).replace(", ", " ")
    label = _join(head, locality, _nominatim_state(address))
    return GeocodedLocation(query, label or best["display_name"], best.get("display_name", query), float(best["lat"]), float(best["lon"]))


# ---- Photon ------------------------------------------------------------------------------
def _photon_feature_to_location(feature: dict, query: str) -> GeocodedLocation:
    props = feature.get("properties", {})
    lng, lat = feature["geometry"]["coordinates"]
    name = props.get("name")
    street = " ".join(p for p in (props.get("housenumber"), props.get("street")) if p)
    if props.get("type") in PLACE_TYPES:
        head, locality = None, name or _locality(props)
    else:
        head, locality = name or street, _locality(props)
    label = _join(head, locality, _state_code(props.get("state")))
    if props.get("type") == "postcode" or (not name and props.get("postcode")):
        label = _join(props.get("postcode"), label)
    display = _join(name, street, props.get("city"), props.get("state"), props.get("postcode"), props.get("country"))
    return GeocodedLocation(query, label or query, display or label or query, float(lat), float(lng))


def _photon_features(query: str, limit: int) -> list[dict]:
    features = _get(f"{_config()['PHOTON_BASE_URL']}/api/", {"q": query, "limit": limit, "lang": "en"}).json().get("features", [])
    allowed = _country_codes()
    if allowed:
        features = [f for f in features if f.get("properties", {}).get("countrycode", "").upper() in allowed]
    return features


# ---- public API -----------------------------------------------------------------------------
def geocode(query: str) -> GeocodedLocation:
    """Resolve free text (address, city, state, ZIP...) to a coordinate."""
    query = " ".join(query.split())
    key = make_key("geocode", query, _config()["GEOCODING_COUNTRY_CODES"])
    if cached := cache.get(key):
        return GeocodedLocation(**cached)

    location = None
    try:
        location = _nominatim_search(query)
    except PROVIDER_ERRORS as exc:
        logger.warning("Nominatim failed for %r, falling back to Photon: %s", query, exc)
    if location is None:
        try:
            features = _photon_features(query, limit=5)
        except PROVIDER_ERRORS as exc:
            logger.warning("Photon geocoding failed for %r: %s", query, exc)
            raise GeocodingError("Geocoding services are unavailable right now. Please try again shortly.") from exc
        if features:
            location = _photon_feature_to_location(features[0], query)
    if location is None:
        raise GeocodingError(f'We could not find "{query}". Try adding a city and state, or a ZIP code.')
    cache.set(key, location.to_dict())
    return location


def autocomplete(query: str, limit: int = 6) -> list[dict]:
    query = " ".join(query.split())
    key = make_key("autocomplete", query, limit)
    if (cached := cache.get(key)) is not None:
        return cached
    try:
        features = _photon_features(query, limit=limit * 2)
    except PROVIDER_ERRORS as exc:
        logger.warning("Autocomplete failed for %r: %s", query, exc)
        raise GeocodingError("Address suggestions are temporarily unavailable.") from exc
    seen, suggestions = set(), []
    for feature in features:
        location = _photon_feature_to_location(feature, query)
        if location.display_name in seen:
            continue
        seen.add(location.display_name)
        suggestions.append(location.to_dict())
        if len(suggestions) >= limit:
            break
    cache.set(key, suggestions, 60 * 60 * 6)
    return suggestions


# ---- reverse geocoding for stop labels -----------------------------------------------------------
def _reverse_key(point: LatLng) -> str:
    return make_key("reverse", f"{point.lat:.2f}", f"{point.lng:.2f}")


def _photon_reverse(point: LatLng) -> str | None:
    response = _get(f"{_config()['PHOTON_BASE_URL']}/reverse", {"lat": f"{point.lat:.5f}", "lon": f"{point.lng:.5f}", "lang": "en", "limit": 1})
    features = response.json().get("features", [])
    if not features:
        return None
    props = features[0].get("properties", {})
    locality = _locality(props)
    return _join(locality, _state_code(props.get("state"))) if locality else None


def _nominatim_reverse(point: LatLng) -> str | None:
    result = _nominatim("reverse", {"lat": f"{point.lat:.5f}", "lon": f"{point.lng:.5f}", "zoom": 10})
    address = result.get("address", {}) if isinstance(result, dict) else {}
    locality = _locality(address)
    return _join(locality, _nominatim_state(address)) if locality else None


def reverse_labels(points: list[LatLng], deadline_seconds: float = 9.0) -> list[str | None]:
    """Label points concurrently; anything not resolved before the deadline is ``None``."""
    if not points or not _config()["ENABLE_REVERSE_GEOCODING"]:
        return [None] * len(points)

    results: list[str | None] = [cache.get(_reverse_key(p)) for p in points]
    if all(results):
        return results
    lock = threading.Lock()
    finished = threading.Event()
    attempts_left = [0 if label else 2 for label in results]  # one per provider

    def settle(index: int, label: str | None) -> None:
        if label:
            cache.set(_reverse_key(points[index]), label)
        with lock:
            if label and results[index] is None:
                results[index] = label
            attempts_left[index] -= 1
            if all(r is not None or a <= 0 for r, a in zip(results, attempts_left)):
                finished.set()

    def safe(provider, index: int) -> None:
        label = None
        try:
            if results[index] is None and not finished.is_set():
                label = provider(points[index])
        except PROVIDER_ERRORS as exc:
            logger.info("Reverse geocoding via %s failed: %s", provider.__name__, exc)
        finally:
            settle(index, label)

    def nominatim_worker() -> None:
        for index in range(len(points)):
            if attempts_left[index] > 0:
                safe(_nominatim_reverse, index)

    pool = ThreadPoolExecutor(max_workers=8)
    for index in range(len(points)):
        if results[index] is None:
            pool.submit(safe, _photon_reverse, index)
    threading.Thread(target=nominatim_worker, daemon=True).start()
    finished.wait(deadline_seconds)
    finished.set()  # stop any remaining background lookups
    pool.shutdown(wait=False, cancel_futures=True)
    with lock:
        return list(results)
