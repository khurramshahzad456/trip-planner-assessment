"""Hours-of-Service state machine.

``HOSClock`` tracks everything the regulations care about while the trip
scheduler advances time: the 14-hour window, 11-hour driving limit, 8-hour
break requirement and the rolling 70-hour / 8-day cycle. It knows nothing
about routes or miles, which keeps it easy to test in isolation.
"""

from __future__ import annotations

import math
from datetime import date, datetime, time, timedelta

from .hos_rules import DEFAULT_RULES, DutyStatus, HOSRules

ON_DUTY_STATUSES = {DutyStatus.DRIVING, DutyStatus.ON_DUTY}


def minutes_between(start: datetime, end: datetime) -> float:
    return (end - start).total_seconds() / 60


def start_of_day(day: date) -> datetime:
    return datetime.combine(day, time.min)


class CycleLedger:
    """Rolling record of on-duty time used for the 70-hour / 8-day calculation."""

    def __init__(self, rules: HOSRules, trip_start: datetime, prior_cycle_minutes: float):
        self.rules = rules
        self.intervals: list[tuple[datetime, datetime]] = []
        self.restarts: list[datetime] = []
        self._seed_prior_history(trip_start, prior_cycle_minutes)

    def _seed_prior_history(self, trip_start: datetime, prior_minutes: float) -> None:
        # The driver only tells us the total used in the current cycle, so it is
        # spread evenly over the previous (cycle_days - 1) days. Those hours then
        # drop out of the window one day at a time, exactly like a real recap.
        prior_days = self.rules.cycle_days - 1
        if prior_minutes <= 0 or prior_days <= 0:
            return
        per_day = prior_minutes / prior_days
        for offset in range(prior_days, 0, -1):
            day_start = start_of_day(trip_start.date() - timedelta(days=offset))
            self.intervals.append((day_start, day_start + timedelta(minutes=per_day)))

    def record(self, start: datetime, end: datetime) -> None:
        if end > start:
            self.intervals.append((start, end))

    def record_restart(self, at: datetime) -> None:
        self.restarts.append(at)

    def used_minutes(self, at: datetime, days: int | None = None) -> float:
        """On-duty minutes in the ``days``-day window ending at ``at`` (default: full cycle).

        A 34-hour restart that ended at or before ``at`` discards everything before it.
        """
        days = days or self.rules.cycle_days
        lower = start_of_day(at.date() - timedelta(days=days - 1))
        past_restarts = [r for r in self.restarts if r <= at]
        if past_restarts:
            lower = max(lower, max(past_restarts))
        total = 0.0
        for start, end in self.intervals:
            overlap_start = max(start, lower)
            overlap_end = min(end, at)
            if overlap_end > overlap_start:
                total += minutes_between(overlap_start, overlap_end)
        return total

    def available_minutes(self, at: datetime) -> int:
        remaining = self.rules.cycle_limit_minutes - self.used_minutes(at)
        # Round tiny float noise before flooring so 600.0000001 does not become 600.
        return max(0, math.floor(round(remaining, 6)))


class HOSClock:
    """Tracks the driver's HOS counters as the scheduler advances time."""

    def __init__(self, start: datetime, cycle_used_hours: float, rules: HOSRules = DEFAULT_RULES):
        self.rules = rules
        self.now = start
        self.shift_start: datetime | None = None
        self.shift_driving_minutes = 0
        self.driving_since_break_minutes = 0
        self.cycle = CycleLedger(rules, start, cycle_used_hours * 60)

    # ---- queries -------------------------------------------------------
    def window_remaining(self) -> int:
        if self.shift_start is None:
            return self.rules.duty_window_minutes
        elapsed = minutes_between(self.shift_start, self.now)
        return max(0, self.rules.duty_window_minutes - math.ceil(round(elapsed, 6)))

    def shift_driving_remaining(self) -> int:
        return max(0, self.rules.max_driving_minutes - self.shift_driving_minutes)

    def break_remaining(self) -> int:
        return max(0, self.rules.break_after_driving_minutes - self.driving_since_break_minutes)

    def cycle_available(self, at: datetime | None = None) -> int:
        return self.cycle.available_minutes(at or self.now)

    def cycle_used_minutes(self, at: datetime | None = None) -> float:
        return self.cycle.used_minutes(at or self.now)

    def driving_available(self) -> int:
        """Minutes the driver may drive right now before any HOS limit is hit."""
        return min(
            self.shift_driving_remaining(),
            self.window_remaining(),
            self.break_remaining(),
            self.cycle_available(),
        )

    def needs_shift_reset(self) -> str | None:
        """Return the limit that forces a 10-hour reset, if any."""
        if self.shift_driving_remaining() <= 0:
            return "11_HOUR"
        if self.window_remaining() <= 0:
            return "14_HOUR"
        return None

    # ---- mutations -----------------------------------------------------
    def drive(self, minutes: int) -> tuple[datetime, datetime]:
        start = self.now
        self._begin_shift_if_needed()
        self.now = start + timedelta(minutes=minutes)
        self.shift_driving_minutes += minutes
        self.driving_since_break_minutes += minutes
        self.cycle.record(start, self.now)
        return start, self.now

    def on_duty(self, minutes: int) -> tuple[datetime, datetime]:
        start = self.now
        self._begin_shift_if_needed()
        self.now = start + timedelta(minutes=minutes)
        self.cycle.record(start, self.now)
        if self.rules.on_duty_counts_as_break and minutes >= self.rules.break_minutes:
            self.driving_since_break_minutes = 0
        return start, self.now

    def off_duty(self, minutes: int) -> tuple[datetime, datetime]:
        start = self.now
        self.now = start + timedelta(minutes=minutes)
        if minutes >= self.rules.break_minutes:
            self.driving_since_break_minutes = 0
        if minutes >= self.rules.off_duty_reset_minutes:
            self.shift_start = None
            self.shift_driving_minutes = 0
        if minutes >= self.rules.restart_minutes:
            self.cycle.record_restart(self.now)
        return start, self.now

    def _begin_shift_if_needed(self) -> None:
        if self.shift_start is None:
            self.shift_start = self.now

    # ---- planning helpers ------------------------------------------------
    def plan_cycle_recovery(self, needed_minutes: int) -> tuple[int, str]:
        """Choose the shortest off-duty period that makes ``needed_minutes`` available.

        Returns ``(minutes_off, kind)`` where kind is ``"rest"`` (a normal
        10-hour reset already recaps enough), ``"recap"`` (wait until older
        days drop out of the 8-day window) or ``"restart"`` (34-hour restart).
        """
        rules = self.rules
        needed = max(1, min(needed_minutes, rules.cycle_limit_minutes))
        earliest = self.now + timedelta(minutes=rules.off_duty_reset_minutes)
        if self.cycle_available(earliest) >= needed:
            return rules.off_duty_reset_minutes, "rest"

        restart_end = self.now + timedelta(minutes=rules.restart_minutes)
        midnight = start_of_day(self.now.date() + timedelta(days=1))
        while midnight < restart_end:
            candidate = max(midnight, earliest)
            if self.cycle_available(candidate) >= needed:
                return math.ceil(minutes_between(self.now, candidate)), "recap"
            midnight += timedelta(days=1)
        return rules.restart_minutes, "restart"
