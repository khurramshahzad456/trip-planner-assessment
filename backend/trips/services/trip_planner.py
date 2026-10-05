"""Orchestrates a full trip plan.

    locations → geocoding → routing → HOS schedule → stop enrichment → daily logs

The returned payload is the single source of truth that the map, timeline and
ELD log sheets on the frontend all render from.
"""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime

from .compliance import audit_schedule
from .exceptions import TripPlanningError
from .fuel_planner import find_nearby_fuel_stations
from .geo import LatLng, PolylineLocator, simplify
from .geocoding_service import GeocodedLocation, geocode, reverse_labels
from .hos_rules import DEFAULT_RULES, DEFAULT_SPEEDS, DutyStatus, EventType, HOSRules, SpeedAssumptions, describe_assumptions
from .log_generator import TimelineItem, build_daily_logs
from .routing_service import RouteLeg, RoutingProvider, calculate_leg, get_routing_provider
from .trip_scheduler import LegPlan, ScheduledEvent, plan_schedule

LOCATION_FIELDS = ("current_location", "pickup_location", "dropoff_location")


@dataclass
class TripRequest:
    current_location: str
    pickup_location: str
    dropoff_location: str
    current_cycle_used: float
    start_time: datetime
    coordinates: dict[str, dict] = field(default_factory=dict)  # optional pre-resolved autocomplete picks
    driver_name: str = ""
    carrier_name: str = ""
    truck_number: str = ""


@dataclass
class PlanningContext:
    request: TripRequest
    locations: dict[str, GeocodedLocation]
    legs: list[RouteLeg]
    events: list[ScheduledEvent]


# ---- step 1: locations --------------------------------------------------------
def resolve_locations(request: TripRequest, geocoder: Callable[[str], GeocodedLocation] | None = None) -> dict[str, GeocodedLocation]:
    geocoder = geocoder or geocode
    resolved: dict[str, GeocodedLocation] = {}
    for field_name in LOCATION_FIELDS:
        text = getattr(request, field_name).strip()
        coords = request.coordinates.get(field_name)
        if coords:
            resolved[field_name] = GeocodedLocation(
                query=text,
                label=coords.get("label") or text,
                display_name=coords.get("display_name") or text,
                lat=float(coords["lat"]),
                lng=float(coords["lng"]),
            )
            continue
        try:
            resolved[field_name] = geocoder(text)
        except TripPlanningError as exc:
            exc.field = field_name
            raise
    pickup, dropoff = resolved["pickup_location"], resolved["dropoff_location"]
    if abs(pickup.lat - dropoff.lat) < 1e-4 and abs(pickup.lng - dropoff.lng) < 1e-4:
        raise TripPlanningError("Pickup and dropoff resolve to the same place. Please enter different locations.", field="dropoff_location")
    return resolved


# ---- step 2: route ------------------------------------------------------------------
def calculate_route(locations: dict[str, GeocodedLocation], provider: RoutingProvider) -> list[RouteLeg]:
    return [
        calculate_leg(provider, locations["current_location"].point, locations["pickup_location"].point),
        calculate_leg(provider, locations["pickup_location"].point, locations["dropoff_location"].point),
    ]


# ---- step 4: enrich events with coordinates and labels -------------------------------
class EventLocator:
    def __init__(self, legs: list[RouteLeg]):
        self.legs = legs
        self.offsets = [0.0, legs[0].distance_miles]
        self.locators = [PolylineLocator(leg.geometry, leg.distance_miles) for leg in legs]

    def point(self, leg_index: int, global_mile: float) -> LatLng:
        return self.locators[leg_index].point_at(global_mile - self.offsets[leg_index])


def _stop_point(event: ScheduledEvent, locator: EventLocator, locations: dict[str, GeocodedLocation]) -> LatLng:
    if event.type == EventType.PICKUP:
        return locations["pickup_location"].point
    if event.type == EventType.DROPOFF:
        return locations["dropoff_location"].point
    return locator.point(event.leg_index, event.start_mile)


def _fallback_label(event: ScheduledEvent) -> str:
    return f"Route mile {event.start_mile:,.0f}"


def build_event_payload(context: PlanningContext) -> list[dict]:
    locations = context.locations
    locator = EventLocator(context.legs)
    events = context.events

    stop_indexes = [i for i, e in enumerate(events) if e.duty_status != DutyStatus.DRIVING]
    stop_points = {i: _stop_point(events[i], locator, locations) for i in stop_indexes}
    needs_label = [
        i for i in stop_indexes
        if events[i].type not in (EventType.PICKUP, EventType.DROPOFF) and events[i].start_mile > 0.01
    ]
    fuel_indexes = [i for i in stop_indexes if events[i].type == EventType.FUEL]

    with ThreadPoolExecutor(max_workers=2) as pool:
        labels_future = pool.submit(reverse_labels, [stop_points[i] for i in needs_label])
        stations_future = pool.submit(find_nearby_fuel_stations, [stop_points[i] for i in fuel_indexes])
        reverse = dict(zip(needs_label, labels_future.result()))
        stations = dict(zip(fuel_indexes, stations_future.result()))

    def stop_label(i: int) -> str:
        event = events[i]
        if event.type == EventType.PICKUP:
            return locations["pickup_location"].label
        if event.type == EventType.DROPOFF:
            return locations["dropoff_location"].label
        if event.start_mile <= 0.01:
            return locations["current_location"].label if event.leg_index == 0 else locations["pickup_location"].label
        found = reverse.get(i)
        return f"near {found}" if found else _fallback_label(event)

    labels = {i: stop_label(i) for i in stop_indexes}
    payload = []
    for index, event in enumerate(events):
        item = {
            "id": f"evt-{index + 1}",
            "type": event.type.value,
            "duty_status": event.duty_status.value,
            "start": event.start.isoformat(timespec="minutes"),
            "end": event.end.isoformat(timespec="minutes"),
            "duration_hours": round(event.duration_minutes / 60, 4),
            "start_mile": round(event.start_mile, 1),
            "end_mile": round(event.end_mile, 1),
            "distance_miles": round(event.distance_miles, 1),
            "leg_index": event.leg_index,
            "reason": event.reason,
        }
        if event.duty_status == DutyStatus.DRIVING:
            prev_label = next((labels[j] for j in range(index - 1, -1, -1) if j in labels), None)
            next_label = next((labels[j] for j in range(index + 1, len(events)) if j in labels), None)
            start_label = prev_label or locations["current_location"].label
            item.update(
                {
                    "start_location": {**locator.point(event.leg_index, event.start_mile).__dict__, "label": start_label},
                    "end_location": {**locator.point(event.leg_index, event.end_mile).__dict__, "label": next_label or locations["dropoff_location"].label},
                    "average_speed_mph": round(event.details.get("speed_mph", 0), 1),
                }
            )
        else:
            point = stop_points[index]
            item["location"] = {"lat": point.lat, "lng": point.lng, "label": labels[index]}
            if event.details.get("trigger"):
                item["trigger"] = event.details["trigger"]
            if event.details.get("recovery"):
                item["recovery"] = event.details["recovery"]
            if index in stations and stations[index]:
                item["fuel_station"] = stations[index]
        payload.append(item)
    return payload


# ---- step 5: logs, stops and summaries ----------------------------------------------------
def _timeline_items(events: list[dict]) -> list[TimelineItem]:
    items = []
    for e in events:
        if e["duty_status"] == DutyStatus.DRIVING.value:
            start_label, end_label = e["start_location"]["label"], e["end_location"]["label"]
        else:
            start_label = end_label = e["location"]["label"]
        items.append(
            TimelineItem(
                id=e["id"],
                type=e["type"],
                duty_status=DutyStatus(e["duty_status"]),
                start=datetime.fromisoformat(e["start"]),
                end=datetime.fromisoformat(e["end"]),
                distance_miles=e["distance_miles"],
                start_label=start_label,
                end_label=end_label,
                reason=e["reason"],
            )
        )
    return items


def _build_stops(events: list[dict], locations: dict[str, GeocodedLocation], trip_start: str) -> list[dict]:
    current = locations["current_location"]
    stops = [
        {
            "id": "stop-origin",
            "type": "CURRENT",
            "label": current.label,
            "lat": current.lat,
            "lng": current.lng,
            "arrival": None,
            "departure": trip_start,
            "duration_hours": 0,
            "reason": "Trip starts here.",
            "event_id": None,
            "mile": 0,
        }
    ]
    for e in events:
        if e["duty_status"] == DutyStatus.DRIVING.value:
            continue
        stops.append(
            {
                "id": f"stop-{e['id']}",
                "type": e["type"],
                "label": e["location"]["label"],
                "lat": e["location"]["lat"],
                "lng": e["location"]["lng"],
                "arrival": e["start"],
                "departure": e["end"],
                "duration_hours": e["duration_hours"],
                "reason": e["reason"],
                "event_id": e["id"],
                "mile": e["start_mile"],
                "fuel_station": e.get("fuel_station"),
            }
        )
    return stops


def _route_payload(legs: list[RouteLeg], locations: dict[str, GeocodedLocation], provider_name: str, speeds: list[float]) -> dict:
    names = [("current_location", "pickup_location"), ("pickup_location", "dropoff_location")]
    leg_payload = []
    all_points: list[LatLng] = []
    for leg, (origin, destination), speed in zip(legs, names, speeds):
        simplified = simplify(leg.geometry)
        all_points.extend(simplified)
        leg_payload.append(
            {
                "from": locations[origin].label,
                "to": locations[destination].label,
                "distance_miles": round(leg.distance_miles, 1),
                "provider_duration_hours": round(leg.duration_hours, 2),
                "planned_driving_hours": round(leg.distance_miles / speed, 2) if leg.distance_miles else 0,
                "average_speed_mph": round(speed, 1),
                "geometry": [p.as_list() for p in simplified],
            }
        )
    lats = [p.lat for p in all_points] or [locations["current_location"].lat]
    lngs = [p.lng for p in all_points] or [locations["current_location"].lng]
    return {
        "provider": provider_name,
        "total_distance_miles": round(sum(leg.distance_miles for leg in legs), 1),
        "provider_duration_hours": round(sum(leg.duration_hours for leg in legs), 2),
        "legs": leg_payload,
        "bounds": [[min(lats), min(lngs)], [max(lats), max(lngs)]],
    }


def _hours(events: list[dict], *types: str) -> float:
    return round(sum(e["duration_hours"] for e in events if e["type"] in types), 2)


def _count(events: list[dict], *types: str) -> int:
    return sum(1 for e in events if e["type"] in types)


def plan_trip(
    request: TripRequest,
    rules: HOSRules = DEFAULT_RULES,
    speeds: SpeedAssumptions = DEFAULT_SPEEDS,
    geocoder: Callable[[str], GeocodedLocation] | None = None,
    provider: RoutingProvider | None = None,
) -> dict:
    provider = provider or get_routing_provider()
    locations = resolve_locations(request, geocoder)
    legs = calculate_route(locations, provider)

    result = plan_schedule(
        request.start_time,
        request.current_cycle_used,
        LegPlan(legs[0].distance_miles, legs[0].duration_hours, "to_pickup"),
        LegPlan(legs[1].distance_miles, legs[1].duration_hours, "to_dropoff"),
        rules,
        speeds,
    )
    context = PlanningContext(request, locations, legs, result.events)
    events = build_event_payload(context)
    daily_logs = build_daily_logs(
        _timeline_items(events),
        result.clock.cycle,
        trip_start_label=locations["current_location"].label,
        trip_end_label=locations["dropoff_location"].label,
    )
    checks = audit_schedule(result.events, request.start_time, request.current_cycle_used, rules)

    trip_start = result.events[0].start if result.events else request.start_time
    trip_end = result.events[-1].end if result.events else request.start_time
    cycle_limit = rules.cycle_limit_minutes / 60
    cycle_used = float(request.current_cycle_used)
    cycle_remaining = round(cycle_limit - cycle_used, 2)
    driving_hours = _hours(events, EventType.DRIVING.value)
    required_on_duty = round(driving_hours + _hours(events, "PICKUP", "DROPOFF", "FUEL"), 2)
    recoveries = [e for e in events if e.get("trigger") == "CYCLE"]
    used_at_end = round(result.clock.cycle_used_minutes(trip_end) / 60, 2)

    if cycle_remaining <= 0:
        cycle_status = "NO_HOURS_AVAILABLE"
        cycle_message = (
            f"No cycle hours remain ({cycle_used:g} of {cycle_limit:g} used). The driver cannot drive until "
            "hours recap or a 34-hour restart is taken — the schedule below includes that wait."
        )
    elif required_on_duty <= cycle_remaining + 1e-6:
        cycle_status = "FITS"
        cycle_message = f"Trip needs {required_on_duty:g} on-duty hours; {cycle_remaining:g} are available in the current cycle."
    else:
        cycle_status = "RECOVERY_REQUIRED"
        recovery_note = (
            "The schedule adds off-duty time for cycle hours to recap or a 34-hour restart."
            if recoveries
            else "Older hours drop out of the 8-day window during the trip, so no extra off-duty time is needed."
        )
        cycle_message = f"Trip needs {required_on_duty:g} on-duty hours but only {cycle_remaining:g} remain. {recovery_note}"

    trip_summary = {
        "current_location": locations["current_location"].label,
        "pickup_location": locations["pickup_location"].label,
        "dropoff_location": locations["dropoff_location"].label,
        "total_distance_miles": round(sum(leg.distance_miles for leg in legs), 1),
        "driving_hours": driving_hours,
        "on_duty_hours": required_on_duty,
        "trip_start": trip_start.isoformat(timespec="minutes"),
        "trip_end": trip_end.isoformat(timespec="minutes"),
        "total_duration_hours": round((trip_end - trip_start).total_seconds() / 3600, 2),
        "log_days": len(daily_logs),
        "driving_days": sum(1 for log in daily_logs if log["totals"]["driving"] > 0),
        "fuel_stops": _count(events, "FUEL"),
        "rest_periods": _count(events, "REST", "RESTART"),
        "breaks": _count(events, "BREAK"),
        "pickup_duration_hours": _hours(events, "PICKUP"),
        "dropoff_duration_hours": _hours(events, "DROPOFF"),
        "driver_name": request.driver_name,
        "carrier_name": request.carrier_name,
        "truck_number": request.truck_number,
    }
    hos_summary = {
        "cycle_limit_hours": cycle_limit,
        "cycle_used_hours": cycle_used,
        "cycle_remaining_hours": max(0.0, cycle_remaining),
        "required_on_duty_hours": required_on_duty,
        "fits_within_cycle": cycle_status == "FITS",
        "status": cycle_status,
        "message": cycle_message,
        "cycle_used_at_arrival_hours": used_at_end,
        "cycle_remaining_at_arrival_hours": round(max(0.0, cycle_limit - used_at_end), 2),
        "cycle_recoveries": [
            {"event_id": e["id"], "kind": e.get("recovery"), "start": e["start"], "end": e["end"], "duration_hours": e["duration_hours"]}
            for e in recoveries
        ],
        "warnings": result.warnings,
        "compliance_checks": checks,
        "all_checks_passed": all(c["passed"] for c in checks),
    }
    return {
        "inputs": {
            "current_location": request.current_location,
            "pickup_location": request.pickup_location,
            "dropoff_location": request.dropoff_location,
            "current_cycle_used": cycle_used,
            "start_time": request.start_time.isoformat(timespec="minutes"),
            "driver_name": request.driver_name,
            "carrier_name": request.carrier_name,
            "truck_number": request.truck_number,
        },
        "locations": {key: loc.to_dict() for key, loc in locations.items()},
        "route": _route_payload(legs, locations, provider.name, result.leg_speeds_mph),
        "events": events,
        "stops": _build_stops(events, locations, trip_start.isoformat(timespec="minutes")),
        "daily_logs": daily_logs,
        "trip_summary": trip_summary,
        "hos_summary": hos_summary,
        "assumptions": describe_assumptions(rules, speeds),
    }
