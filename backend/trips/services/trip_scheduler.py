"""Builds an HOS-compliant, chronological list of trip events.

The scheduler is a discrete simulation: it advances through the trip's tasks
(drive to pickup, pickup, drive to dropoff, dropoff) and, before every chunk
of driving, asks the ``HOSClock`` and ``FuelTracker`` what is allowed. Each
driving chunk ends at whichever limit binds first, and the matching stop
(break, fuel, 10-hour rest, cycle recovery) is inserted.

Input is pure data (leg distances and durations), so it is fully testable
without any network access.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime

from .fuel_planner import FuelTracker
from .hos_engine import HOSClock
from .hos_rules import DEFAULT_RULES, DEFAULT_SPEEDS, DutyStatus, EventType, HOSRules, SpeedAssumptions

MILES_EPSILON = 1e-6


class ScheduleError(Exception):
    """Raised when a schedule cannot be produced (e.g. invalid input)."""


@dataclass(frozen=True)
class LegPlan:
    """One routed leg of the trip, e.g. current location → pickup."""

    distance_miles: float
    provider_duration_hours: float
    name: str = ""

    def average_speed_mph(self, speeds: SpeedAssumptions = DEFAULT_SPEEDS) -> float:
        if self.distance_miles <= 0:
            return speeds.max_average_speed_mph
        hours = self.provider_duration_hours * speeds.route_duration_factor
        speed = self.distance_miles / hours if hours > 0 else speeds.max_average_speed_mph
        return min(speeds.max_average_speed_mph, max(speeds.min_average_speed_mph, speed))


@dataclass
class ScheduledEvent:
    type: EventType
    duty_status: DutyStatus
    start: datetime
    end: datetime
    start_mile: float
    end_mile: float
    leg_index: int
    reason: str = ""
    details: dict = field(default_factory=dict)

    @property
    def duration_minutes(self) -> float:
        return (self.end - self.start).total_seconds() / 60

    @property
    def distance_miles(self) -> float:
        return self.end_mile - self.start_mile


@dataclass
class ScheduleResult:
    events: list[ScheduledEvent]
    clock: HOSClock
    warnings: list[str]
    leg_speeds_mph: list[float]
    recovery_decisions: list[str] = field(default_factory=list)

    @property
    def end_time(self) -> datetime:
        return self.events[-1].end


REASONS = {
    "11_HOUR": "11-hour driving limit reached — 10 consecutive hours off duty required.",
    "14_HOUR": "14-hour duty window reached — 10 consecutive hours off duty required.",
    "14_HOUR_TASK": "Not enough time left in the 14-hour window for the next on-duty task.",
    "BREAK": "30-minute break required before exceeding 8 hours of cumulative driving.",
    "FUEL": "Planned fuel stop to stay within the 1,000-mile fueling interval.",
    "PICKUP": "Loading at the shipper (1 hour, on duty not driving).",
    "DROPOFF": "Unloading at the receiver (1 hour, on duty not driving).",
    "rest": "70-hour cycle exhausted — 10-hour rest recaps enough cycle hours.",
    "recap": "70-hour cycle exhausted — off duty until hours from 8 days ago drop off (recap).",
    "restart": "70-hour cycle exhausted — 34-hour restart resets the cycle to zero.",
}


class TripScheduler:
    def __init__(
        self,
        start_time: datetime,
        cycle_used_hours: float,
        rules: HOSRules = DEFAULT_RULES,
        speeds: SpeedAssumptions = DEFAULT_SPEEDS,
        recovery_plan: list[str] | None = None,
    ):
        if not 0 <= cycle_used_hours <= rules.cycle_limit_minutes / 60:
            raise ScheduleError("Current cycle used must be between 0 and 70 hours.")
        self.rules = rules
        self.speeds = speeds
        self.clock = HOSClock(start_time, cycle_used_hours, rules)
        self.fuel = FuelTracker(rules.fuel_interval_miles)
        self.events: list[ScheduledEvent] = []
        self.mile = 0.0
        self.leg_index = 0
        self.warnings: list[str] = []
        # Forced choices for successive cycle recoveries ("auto" or "restart"); see plan_schedule().
        self.recovery_plan = recovery_plan or []
        self.recovery_decisions: list[str] = []

    # ---- public API ------------------------------------------------------
    def schedule(self, to_pickup: LegPlan, to_dropoff: LegPlan) -> ScheduleResult:
        speeds = [to_pickup.average_speed_mph(self.speeds), to_dropoff.average_speed_mph(self.speeds)]

        self.leg_index = 0
        self._drive_leg(to_pickup, speeds[0])
        self._on_duty_task(EventType.PICKUP, self.rules.pickup_minutes, REASONS["PICKUP"])

        self.leg_index = 1
        self._drive_leg(to_dropoff, speeds[1])
        self._on_duty_task(EventType.DROPOFF, self.rules.dropoff_minutes, REASONS["DROPOFF"])

        return ScheduleResult(self.events, self.clock, self.warnings, speeds, self.recovery_decisions)

    # ---- driving -----------------------------------------------------------
    def _drive_leg(self, leg: LegPlan, speed_mph: float) -> None:
        remaining = leg.distance_miles
        while remaining > MILES_EPSILON:
            needed_minutes = max(1, math.ceil(round(remaining / speed_mph * 60, 6)))
            self._prepare_to_drive(needed_minutes, speed_mph)

            chunk = min(
                self.clock.driving_available(),
                self.fuel.minutes_until_fuel(speed_mph),
                needed_minutes,
            )
            if chunk <= 0:  # defensive: _prepare_to_drive guarantees progress
                raise ScheduleError("Scheduler could not make progress; check HOS rule configuration.")

            miles = remaining if chunk == needed_minutes else min(remaining, chunk * speed_mph / 60)
            start, end = self.clock.drive(chunk)
            self._append(EventType.DRIVING, DutyStatus.DRIVING, start, end, miles, details={"speed_mph": speed_mph})
            self.fuel.add_miles(miles)
            remaining -= miles

    def _prepare_to_drive(self, needed_minutes: int, speed_mph: float) -> None:
        """Insert stops until at least one minute of legal driving is available."""
        for _ in range(20):  # each pass resolves one blocking constraint
            if self.clock.cycle_available() <= 0:
                self._recover_cycle(min(needed_minutes, self.rules.min_recap_minutes))
            elif reset_reason := self.clock.needs_shift_reset():
                self._rest(REASONS[reset_reason], trigger=reset_reason)
            elif self.fuel.is_due(speed_mph):
                self._on_duty_task(EventType.FUEL, self.rules.fuel_minutes, REASONS["FUEL"])
                self.fuel.refuel()
            elif self.clock.break_remaining() <= 0:
                start, end = self.clock.off_duty(self.rules.break_minutes)
                self._append(EventType.BREAK, DutyStatus.OFF_DUTY, start, end, reason=REASONS["BREAK"])
            else:
                return
        raise ScheduleError("Scheduler exceeded its safety limit while resolving HOS constraints.")

    # ---- stops ---------------------------------------------------------------
    def _on_duty_task(self, event_type: EventType, minutes: int, reason: str) -> None:
        if self.rules.keep_on_duty_within_limits:
            for _ in range(5):
                if self.clock.cycle_available() < minutes:
                    self._recover_cycle(minutes)
                elif self.clock.window_remaining() < minutes:
                    self._rest(REASONS["14_HOUR_TASK"], trigger="14_HOUR")
                else:
                    break
        start, end = self.clock.on_duty(minutes)
        self._append(event_type, DutyStatus.ON_DUTY, start, end, reason=reason)

    def _rest(self, reason: str, trigger: str) -> None:
        start, end = self.clock.off_duty(self.rules.off_duty_reset_minutes)
        self._append(EventType.REST, self.rules.rest_duty_status, start, end, reason=reason, details={"trigger": trigger})

    def _recover_cycle(self, needed_minutes: int) -> None:
        index = len(self.recovery_decisions)
        forced = self.recovery_plan[index] if index < len(self.recovery_plan) else "auto"
        if forced == "restart":
            minutes, kind = self.rules.restart_minutes, "restart"
        else:
            minutes, kind = self.clock.plan_cycle_recovery(needed_minutes)
        self.recovery_decisions.append(forced)
        start, end = self.clock.off_duty(minutes)
        if kind == "restart":
            event_type, status = EventType.RESTART, DutyStatus.OFF_DUTY
        else:
            event_type, status = EventType.REST, self.rules.rest_duty_status
        self._append(event_type, status, start, end, reason=REASONS[kind], details={"trigger": "CYCLE", "recovery": kind})
        message = {
            "restart": "The 70-hour cycle runs out during this trip, so a 34-hour restart is scheduled.",
            "recap": "The 70-hour cycle runs out during this trip; the driver waits off duty until hours recap.",
            "rest": "Cycle hours run out during this trip; they recap during a 10-hour rest.",
        }[kind]
        if message not in self.warnings:
            self.warnings.append(message)

    # ---- bookkeeping -------------------------------------------------------------
    def _append(
        self,
        event_type: EventType,
        status: DutyStatus,
        start: datetime,
        end: datetime,
        miles: float = 0.0,
        reason: str = "",
        details: dict | None = None,
    ) -> None:
        self.events.append(
            ScheduledEvent(
                type=event_type,
                duty_status=status,
                start=start,
                end=end,
                start_mile=self.mile,
                end_mile=self.mile + miles,
                leg_index=self.leg_index,
                reason=reason,
                details=details or {},
            )
        )
        self.mile += miles


def plan_schedule(
    start_time: datetime,
    cycle_used_hours: float,
    to_pickup: LegPlan,
    to_dropoff: LegPlan,
    rules: HOSRules = DEFAULT_RULES,
    speeds: SpeedAssumptions = DEFAULT_SPEEDS,
    max_branching_depth: int = 6,
) -> ScheduleResult:
    """Pick the cycle-recovery strategy that delivers the load soonest.

    Whenever the 70-hour cycle runs out the driver can either wait for hours to
    recap (often sooner) or take a 34-hour restart (often better for long
    trips). Each simulation is cheap, so every combination of choices up to
    ``max_branching_depth`` recoveries is evaluated and the earliest arrival wins.
    """

    def run(plan: list[str]) -> ScheduleResult:
        scheduler = TripScheduler(start_time, cycle_used_hours, rules, speeds, recovery_plan=plan)
        return scheduler.schedule(to_pickup, to_dropoff)

    best = run([])
    pending = [([], best)]
    while pending:
        prefix, result = pending.pop()
        decisions = result.recovery_decisions
        for i in range(len(prefix), min(len(decisions), max_branching_depth)):
            if decisions[i] == "restart":
                continue
            candidate_plan = decisions[:i] + ["restart"]
            candidate = run(candidate_plan)
            if (candidate.end_time, len(candidate.events)) < (best.end_time, len(best.events)):
                best = candidate
            pending.append((candidate_plan, candidate))
    return best
