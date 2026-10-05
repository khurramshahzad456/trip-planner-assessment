from datetime import datetime

from trips.services.hos_rules import DEFAULT_RULES, DutyStatus, EventType
from trips.services.trip_scheduler import LegPlan, ScheduleResult, plan_schedule

START = datetime(2026, 10, 5, 8, 0)  # a Monday, 08:00 home-terminal time


def leg(miles: float, mph: float = 50.0) -> LegPlan:
    """A leg whose provider duration implies the given average speed."""
    return LegPlan(distance_miles=miles, provider_duration_hours=miles / mph if miles else 0.0)


def schedule(to_pickup: float, to_dropoff: float, cycle_used: float = 0.0, start: datetime = START, mph: float = 50.0) -> ScheduleResult:
    return plan_schedule(start, cycle_used, leg(to_pickup, mph), leg(to_dropoff, mph))


def of_type(result: ScheduleResult, event_type: EventType):
    return [e for e in result.events if e.type == event_type]


def driving_blocks_between_resets(result: ScheduleResult, rules=DEFAULT_RULES) -> list[float]:
    """Total driving minutes in each shift (shifts separated by >=10h off duty)."""
    shifts, current, off_run = [], 0.0, 0.0
    for event in result.events:
        if event.duty_status in (DutyStatus.OFF_DUTY, DutyStatus.SLEEPER_BERTH):
            off_run += event.duration_minutes
            if off_run >= rules.off_duty_reset_minutes and current:
                shifts.append(current)
                current = 0.0
            continue
        off_run = 0.0
        if event.duty_status == DutyStatus.DRIVING:
            current += event.duration_minutes
    if current:
        shifts.append(current)
    return shifts
