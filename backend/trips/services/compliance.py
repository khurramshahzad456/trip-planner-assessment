"""Independent post-hoc audit of a generated schedule.

The scheduler is constructive; this module re-checks its output against each
rule from scratch so bugs in one are caught by the other. Results are shown in
the UI and used heavily by the test-suite.
"""

from __future__ import annotations

from datetime import datetime

from .hos_engine import CycleLedger
from .hos_rules import DEFAULT_RULES, DutyStatus, EventType, HOSRules
from .trip_scheduler import ScheduledEvent

EPS = 1e-6


def _minutes(start: datetime, end: datetime) -> float:
    return (end - start).total_seconds() / 60


def audit_schedule(
    events: list[ScheduledEvent],
    trip_start: datetime,
    cycle_used_hours: float,
    rules: HOSRules = DEFAULT_RULES,
) -> list[dict]:
    checks: dict[str, dict] = {
        "11_HOUR": {"label": "11-hour driving limit", "max": 0.0, "limit": rules.max_driving_minutes},
        "14_HOUR": {"label": "14-hour duty window", "max": 0.0, "limit": rules.duty_window_minutes},
        "BREAK": {"label": "30-minute break after 8 hours driving", "max": 0.0, "limit": rules.break_after_driving_minutes},
        "CYCLE": {"label": "70-hour / 8-day cycle", "max": 0.0, "limit": rules.cycle_limit_minutes},
        "FUEL": {"label": "Fuel at least every 1,000 miles", "max": 0.0, "limit": rules.fuel_interval_miles},
    }

    shift_driving = 0.0
    shift_start: datetime | None = None
    since_break = 0.0
    off_run = 0.0
    fuel_miles = 0.0
    ledger = CycleLedger(rules, trip_start, cycle_used_hours * 60)
    restart_pending = False
    pickup_ok = dropoff_ok = True

    for event in events:
        minutes = _minutes(event.start, event.end)
        on_duty = event.duty_status in (DutyStatus.DRIVING, DutyStatus.ON_DUTY)

        if not on_duty:
            off_run += minutes
            if off_run >= rules.off_duty_reset_minutes:
                shift_driving, shift_start = 0.0, None
            if off_run >= rules.break_minutes:
                since_break = 0.0
            if off_run >= rules.restart_minutes and not restart_pending:
                ledger.record_restart(event.end)
                restart_pending = True
            continue

        off_run = 0.0
        restart_pending = False
        if shift_start is None:
            shift_start = event.start
        ledger.record(event.start, event.end)

        if event.duty_status == DutyStatus.DRIVING:
            shift_driving += minutes
            since_break += minutes
            fuel_miles += event.distance_miles
            checks["11_HOUR"]["max"] = max(checks["11_HOUR"]["max"], shift_driving)
            checks["BREAK"]["max"] = max(checks["BREAK"]["max"], since_break)
            checks["FUEL"]["max"] = max(checks["FUEL"]["max"], fuel_miles)
        elif rules.on_duty_counts_as_break and minutes >= rules.break_minutes:
            since_break = 0.0

        if event.duty_status == DutyStatus.DRIVING or rules.keep_on_duty_within_limits:
            checks["14_HOUR"]["max"] = max(checks["14_HOUR"]["max"], _minutes(shift_start, event.end))
        checks["CYCLE"]["max"] = max(checks["CYCLE"]["max"], ledger.used_minutes(event.end))

        if event.type == EventType.FUEL:
            fuel_miles = 0.0
        if event.type == EventType.PICKUP and abs(minutes - rules.pickup_minutes) > EPS:
            pickup_ok = False
        if event.type == EventType.DROPOFF and abs(minutes - rules.dropoff_minutes) > EPS:
            dropoff_ok = False

    results = []
    for key, check in checks.items():
        is_miles = key == "FUEL"
        results.append(
            {
                "rule": key,
                "label": check["label"],
                "passed": check["max"] <= check["limit"] + EPS,
                "observed": round(check["max"], 1) if is_miles else round(check["max"] / 60, 2),
                "limit": check["limit"] if is_miles else check["limit"] / 60,
                "unit": "miles" if is_miles else "hours",
            }
        )
    results.append({"rule": "PICKUP", "label": "Pickup takes 1 hour", "passed": pickup_ok, "observed": None, "limit": rules.pickup_minutes / 60, "unit": "hours"})
    results.append({"rule": "DROPOFF", "label": "Dropoff takes 1 hour", "passed": dropoff_ok, "observed": None, "limit": rules.dropoff_minutes / 60, "unit": "hours"})
    return results
