"""Centralised Hours-of-Service rules and planning assumptions.

Every number the scheduler relies on lives here so that the interpretation of
the rules can be changed in one place. Durations are integer minutes so the
simulation never accumulates floating point drift.

This is an assessment/demo implementation of the U.S. property-carrying HOS
rules (49 CFR Part 395) under the assumptions given in the brief. It is not
legal advice.
"""

from dataclasses import asdict, dataclass
from enum import Enum


class DutyStatus(str, Enum):
    OFF_DUTY = "OFF_DUTY"
    SLEEPER_BERTH = "SLEEPER_BERTH"
    DRIVING = "DRIVING"
    ON_DUTY = "ON_DUTY"


class EventType(str, Enum):
    DRIVING = "DRIVING"
    PICKUP = "PICKUP"
    DROPOFF = "DROPOFF"
    FUEL = "FUEL"
    BREAK = "BREAK"
    REST = "REST"
    RESTART = "RESTART"


@dataclass(frozen=True)
class HOSRules:
    # Driving / duty limits
    max_driving_minutes: int = 11 * 60
    duty_window_minutes: int = 14 * 60
    break_after_driving_minutes: int = 8 * 60
    break_minutes: int = 30
    off_duty_reset_minutes: int = 10 * 60

    # 70-hour / 8-day cycle
    cycle_limit_minutes: int = 70 * 60
    cycle_days: int = 8
    restart_minutes: int = 34 * 60
    # Do not end a cycle wait unless at least this much driving time has recapped.
    min_recap_minutes: int = 60

    # Trip activities (assessment assumptions)
    pickup_minutes: int = 60
    dropoff_minutes: int = 60
    fuel_minutes: int = 30
    fuel_interval_miles: float = 1000.0

    # Interpretation choices
    rest_duty_status: DutyStatus = DutyStatus.SLEEPER_BERTH
    # Since 2020 a 30-minute on-duty (not driving) period also satisfies the break.
    on_duty_counts_as_break: bool = True
    # Conservative planning: never schedule on-duty work outside the 14-hour
    # window or beyond the 70-hour cycle, even where the regulation would allow it.
    keep_on_duty_within_limits: bool = True


@dataclass(frozen=True)
class SpeedAssumptions:
    """How provider travel times are converted into truck driving time."""

    # Multiplier applied to the routing provider's duration (1.0 = use as-is).
    route_duration_factor: float = 1.0
    # Trucks rarely average more than this over a leg, so faster legs are capped.
    max_average_speed_mph: float = 65.0
    # Guard against degenerate provider responses.
    min_average_speed_mph: float = 10.0


DEFAULT_RULES = HOSRules()
DEFAULT_SPEEDS = SpeedAssumptions()


def describe_assumptions(rules: HOSRules = DEFAULT_RULES, speeds: SpeedAssumptions = DEFAULT_SPEEDS) -> dict:
    """Human-readable view of the active rules, shown in the UI and API."""
    raw = asdict(rules)
    raw["rest_duty_status"] = rules.rest_duty_status.value
    return {
        "driver_type": "Property-carrying driver",
        "cycle": f"{rules.cycle_limit_minutes // 60} hours / {rules.cycle_days} days",
        "adverse_driving_conditions": False,
        "rules": raw,
        "speeds": asdict(speeds),
        "statements": [
            "Property-carrying driver on the 70-hour / 8-day cycle.",
            "No adverse driving conditions or other exceptions are used.",
            f"Up to {rules.max_driving_minutes // 60} hours of driving within a "
            f"{rules.duty_window_minutes // 60}-hour duty window after "
            f"{rules.off_duty_reset_minutes // 60} consecutive hours off duty.",
            f"A {rules.break_minutes}-minute break is taken before "
            f"{rules.break_after_driving_minutes // 60} cumulative hours of driving.",
            f"Fuel stop ({rules.fuel_minutes} min, on duty) at least every "
            f"{rules.fuel_interval_miles:,.0f} miles; the truck starts with a full tank.",
            f"Pickup and dropoff take {rules.pickup_minutes // 60} hour each (on duty, not driving).",
            "Overnight 10-hour rests are logged in the sleeper berth.",
            "When cycle hours run out the driver waits for hours to recap or takes a "
            f"{rules.restart_minutes // 60}-hour restart, whichever is sooner.",
            "Hours already used in the cycle are assumed to be spread evenly over the previous 7 days.",
            "The driver starts the trip rested (after 10+ hours off duty).",
            "Driving time comes from the routing provider, with leg averages capped at "
            f"{speeds.max_average_speed_mph:.0f} mph.",
            "All times are the driver's home-terminal time.",
        ],
    }
