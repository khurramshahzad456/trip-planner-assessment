"""Unit tests for the HOS clock and the 70-hour / 8-day cycle ledger."""

from datetime import datetime, timedelta

from django.test import SimpleTestCase

from trips.services.hos_engine import HOSClock
from trips.services.hos_rules import HOSRules

from .helpers import START


class ElevenHourLimitTests(SimpleTestCase):
    def test_driving_available_never_exceeds_eleven_hours(self):
        clock = HOSClock(START, 0)
        self.assertEqual(clock.shift_driving_remaining(), 11 * 60)
        clock.drive(7 * 60)
        clock.off_duty(30)
        clock.drive(4 * 60)
        self.assertEqual(clock.shift_driving_remaining(), 0)
        self.assertEqual(clock.driving_available(), 0)
        self.assertEqual(clock.needs_shift_reset(), "11_HOUR")

    def test_ten_hour_reset_restores_driving_time(self):
        clock = HOSClock(START, 0)
        clock.drive(11 * 60)
        clock.off_duty(10 * 60)
        self.assertIsNone(clock.needs_shift_reset())
        self.assertEqual(clock.shift_driving_remaining(), 11 * 60)
        self.assertEqual(clock.window_remaining(), 14 * 60)

    def test_off_duty_shorter_than_ten_hours_does_not_reset(self):
        clock = HOSClock(START, 0)
        clock.drive(11 * 60)
        clock.off_duty(9 * 60 + 59)
        self.assertEqual(clock.needs_shift_reset(), "11_HOUR")


class FourteenHourWindowTests(SimpleTestCase):
    def test_window_starts_at_first_on_duty_and_counts_off_duty_time(self):
        clock = HOSClock(START, 0)
        clock.on_duty(60)
        clock.off_duty(5 * 60)  # breaks do not pause the 14-hour clock
        self.assertEqual(clock.window_remaining(), 8 * 60)

    def test_window_limits_driving_even_with_driving_hours_left(self):
        clock = HOSClock(START, 0)
        clock.drive(3 * 60)
        clock.off_duty(9 * 60)
        self.assertEqual(clock.shift_driving_remaining(), 8 * 60)
        self.assertEqual(clock.driving_available(), 2 * 60)
        clock.drive(2 * 60)
        self.assertEqual(clock.needs_shift_reset(), "14_HOUR")

    def test_window_does_not_start_before_first_duty(self):
        clock = HOSClock(START, 0)
        clock.off_duty(3 * 60)
        self.assertEqual(clock.window_remaining(), 14 * 60)


class BreakRuleTests(SimpleTestCase):
    def test_break_required_after_eight_hours_of_driving(self):
        clock = HOSClock(START, 0)
        clock.drive(8 * 60)
        self.assertEqual(clock.break_remaining(), 0)
        self.assertEqual(clock.driving_available(), 0)

    def test_thirty_minute_off_duty_satisfies_break(self):
        clock = HOSClock(START, 0)
        clock.drive(8 * 60)
        clock.off_duty(30)
        self.assertEqual(clock.break_remaining(), 8 * 60)

    def test_short_stop_does_not_satisfy_break(self):
        clock = HOSClock(START, 0)
        clock.drive(5 * 60)
        clock.off_duty(29)
        self.assertEqual(clock.break_remaining(), 3 * 60)

    def test_on_duty_stop_of_thirty_minutes_counts_as_break(self):
        clock = HOSClock(START, 0)
        clock.drive(6 * 60)
        clock.on_duty(30)  # e.g. fueling
        self.assertEqual(clock.break_remaining(), 8 * 60)

    def test_on_duty_break_can_be_disabled(self):
        clock = HOSClock(START, 0, HOSRules(on_duty_counts_as_break=False))
        clock.drive(6 * 60)
        clock.on_duty(60)
        self.assertEqual(clock.break_remaining(), 2 * 60)


class CycleTests(SimpleTestCase):
    def test_remaining_cycle_is_seventy_minus_used(self):
        self.assertEqual(HOSClock(START, 45).cycle_available(), 25 * 60)
        self.assertEqual(HOSClock(START, 65).cycle_available(), 5 * 60)
        self.assertEqual(HOSClock(START, 70).cycle_available(), 0)

    def test_on_duty_and_driving_consume_cycle(self):
        clock = HOSClock(START, 60)
        clock.drive(4 * 60)
        clock.on_duty(60)
        self.assertEqual(clock.cycle_available(), 5 * 60)

    def test_cycle_limits_available_driving(self):
        clock = HOSClock(START, 65)
        self.assertEqual(clock.driving_available(), 5 * 60)

    def test_prior_hours_drop_out_of_the_eight_day_window(self):
        clock = HOSClock(START, 70)  # 10 h/day over the previous 7 days
        tomorrow = datetime.combine(START.date() + timedelta(days=1), datetime.min.time())
        self.assertEqual(clock.cycle_available(START), 0)
        self.assertEqual(clock.cycle_available(tomorrow), 10 * 60)

    def test_recap_is_chosen_when_sooner_than_restart(self):
        clock = HOSClock(START, 70)
        minutes, kind = clock.plan_cycle_recovery(60)
        self.assertEqual(kind, "recap")
        self.assertEqual(START + timedelta(minutes=minutes), datetime(2026, 10, 6, 0, 0))

    def test_thirty_four_hour_restart_resets_cycle(self):
        clock = HOSClock(START, 70)
        clock.off_duty(34 * 60)
        self.assertEqual(clock.cycle_available(), 70 * 60)
