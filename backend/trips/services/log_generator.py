"""Turns the scheduler's event timeline into one ELD daily log per calendar day.

Events are split at midnight; any time before the trip starts or after it
ends is filled as off duty, so every daily log accounts for exactly 24 hours.
The frontend draws its graph directly from the ``segments`` produced here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from .hos_engine import CycleLedger, minutes_between, start_of_day
from .hos_rules import DutyStatus

STATUS_KEYS = {
    DutyStatus.OFF_DUTY: "off_duty",
    DutyStatus.SLEEPER_BERTH: "sleeper_berth",
    DutyStatus.DRIVING: "driving",
    DutyStatus.ON_DUTY: "on_duty",
}


@dataclass(frozen=True)
class TimelineItem:
    """Minimal view of an event that the log generator needs."""

    id: str
    type: str
    duty_status: DutyStatus
    start: datetime
    end: datetime
    distance_miles: float
    start_label: str
    end_label: str
    reason: str = ""


@dataclass(frozen=True)
class DaySlice:
    item: TimelineItem | None  # None = off-duty filler outside the trip
    start: datetime
    end: datetime

    @property
    def status(self) -> DutyStatus:
        return self.item.duty_status if self.item else DutyStatus.OFF_DUTY

    @property
    def hours(self) -> float:
        return minutes_between(self.start, self.end) / 60

    @property
    def miles(self) -> float:
        if not self.item or self.item.duty_status != DutyStatus.DRIVING:
            return 0.0
        total = minutes_between(self.item.start, self.item.end)
        return self.item.distance_miles * (minutes_between(self.start, self.end) / total) if total else 0.0


def split_by_day(items: list[TimelineItem]) -> dict[date, list[DaySlice]]:
    """Split events at midnight and pad each day to a full 24 hours of slices."""
    if not items:
        return {}
    first_day = items[0].start.date()
    trip_end = items[-1].end
    last_day = (trip_end - timedelta(microseconds=1)).date() if trip_end > items[0].start else first_day

    days: dict[date, list[DaySlice]] = {}
    day = first_day
    while day <= last_day:
        day_start = start_of_day(day)
        day_end = day_start + timedelta(days=1)
        slices: list[DaySlice] = []
        cursor = day_start
        for item in items:
            start, end = max(item.start, day_start), min(item.end, day_end)
            if end <= start:
                continue
            if start > cursor:
                slices.append(DaySlice(None, cursor, start))
            slices.append(DaySlice(item, start, end))
            cursor = end
        if cursor < day_end:
            slices.append(DaySlice(None, cursor, day_end))
        days[day] = slices
        day += timedelta(days=1)
    return days


def _hour_of_day(moment: datetime, day_start: datetime) -> float:
    return round(minutes_between(day_start, moment) / 60, 4)


def _label(item: TimelineItem | None) -> str:
    if item is None:
        return "Off duty"
    return {
        "DRIVING": "Driving",
        "PICKUP": "Pickup",
        "DROPOFF": "Dropoff",
        "FUEL": "Fuel stop",
        "BREAK": "30-min break",
        "REST": "10-hr rest",
        "RESTART": "34-hr restart",
    }.get(item.type, item.type.title())


def _location_at_day_end(trip_slices: list[DaySlice], day_end: datetime) -> str:
    last = trip_slices[-1].item
    if last.end <= day_end or last.duty_status != DutyStatus.DRIVING:
        return last.end_label if last.end <= day_end else last.start_label
    return f"En route from {last.start_label}"


def _remarks(slices: list[DaySlice], day_start: datetime, start_label: str, end_label: str) -> list[dict]:
    """Duty-status change remarks: time, location and activity, like a paper log."""
    remarks = []
    previous_key = None
    for index, s in enumerate(slices):
        key = (s.status, s.item.id if s.item else None)
        if key == previous_key:
            continue
        previous_key = key
        if s.item is None:
            location = start_label if index == 0 else end_label
        else:
            location = s.item.start_label
        continued = s.item is not None and s.item.start < s.start
        if continued and s.status == DutyStatus.DRIVING:
            location = f"En route from {s.item.start_label}"
        remarks.append(
            {
                "time": s.start.strftime("%H:%M"),
                "hour": _hour_of_day(s.start, day_start),
                "status": s.status.value,
                "activity": _label(s.item) + (" (continued)" if continued else ""),
                "location": location,
                "event_id": s.item.id if s.item else None,
            }
        )
    return remarks


def build_daily_logs(
    items: list[TimelineItem],
    ledger: CycleLedger,
    trip_start_label: str,
    trip_end_label: str,
) -> list[dict]:
    rules = ledger.rules
    cycle_limit_hours = rules.cycle_limit_minutes / 60
    days = split_by_day(items)
    logs: list[dict] = []
    cumulative_miles = 0.0
    previous_end: str | None = None
    for day_number, (day, slices) in enumerate(days.items(), start=1):
        day_start = start_of_day(day)
        day_end = day_start + timedelta(days=1)

        totals = {key: 0.0 for key in STATUS_KEYS.values()}
        for s in slices:
            totals[STATUS_KEYS[s.status]] += s.hours
        miles = sum(s.miles for s in slices)
        cumulative_miles += miles

        trip_slices = [s for s in slices if s.item]
        start_location = previous_end or trip_start_label
        end_location = _location_at_day_end(trip_slices, day_end) if trip_slices else start_location
        if day_number == len(days) and trip_slices and trip_slices[-1].item.end <= day_end:
            end_location = trip_end_label
        previous_end = end_location

        # 70-hour / 8-day recap, evaluated at the end of the day.
        end_moment = day_end - timedelta(microseconds=1)
        used_8 = ledger.used_minutes(end_moment) / 60
        used_7 = ledger.used_minutes(end_moment, days=rules.cycle_days - 1) / 60

        logs.append(
            {
                "date": day.isoformat(),
                "day_number": day_number,
                "segments": [
                    {
                        "status": s.status.value,
                        "start_hour": _hour_of_day(s.start, day_start),
                        "end_hour": _hour_of_day(s.end, day_start),
                        "start": s.start.isoformat(timespec="minutes"),
                        "end": s.end.isoformat(timespec="minutes"),
                        "event_id": s.item.id if s.item else None,
                        "event_type": s.item.type if s.item else "OFF_DUTY",
                        "label": _label(s.item),
                    }
                    for s in slices
                ],
                "totals": {key: round(value, 2) for key, value in totals.items()},
                "total_on_duty_hours": round(totals["driving"] + totals["on_duty"], 2),
                "miles": round(miles, 1),
                "cumulative_miles": round(cumulative_miles, 1),
                "start_location": start_location,
                "end_location": end_location,
                "remarks": _remarks(slices, day_start, start_location, end_location),
                "event_ids": sorted({s.item.id for s in trip_slices}, key=lambda i: int(i.split("-")[1])),
                "cycle": {
                    "limit_hours": cycle_limit_hours,
                    "used_hours": round(used_8, 2),
                    "remaining_hours": round(max(0.0, cycle_limit_hours - used_8), 2),
                    "available_tomorrow_hours": round(max(0.0, cycle_limit_hours - used_7), 2),
                },
            }
        )
    return logs
