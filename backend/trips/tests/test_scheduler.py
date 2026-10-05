"""Behavioural tests for the trip scheduler (no network access)."""

from datetime import datetime, timedelta

from django.test import SimpleTestCase

from trips.services.compliance import audit_schedule
from trips.services.hos_rules import DutyStatus, EventType, HOSRules
from trips.services.trip_scheduler import ScheduleError, TripScheduler

from .helpers import START, driving_blocks_between_resets, leg, of_type, schedule


class ShortTripTests(SimpleTestCase):
    def test_dallas_fort_worth_houston_is_a_simple_one_day_schedule(self):
        result = schedule(32, 263)
        types = [e.type for e in result.events]
        self.assertEqual(types, [EventType.DRIVING, EventType.PICKUP, EventType.DRIVING, EventType.DROPOFF])
        self.assertEqual(result.events[0].start.date(), result.events[-1].end.date())
        self.assertEqual(result.warnings, [])

    def test_current_location_equal_to_pickup_skips_first_leg(self):
        result = schedule(0, 100)
        self.assertEqual(result.events[0].type, EventType.PICKUP)


class PickupDropoffTests(SimpleTestCase):
    def test_pickup_and_dropoff_take_exactly_one_hour_on_duty(self):
        result = schedule(300, 1200)
        (pickup,) = of_type(result, EventType.PICKUP)
        (dropoff,) = of_type(result, EventType.DROPOFF)
        for event in (pickup, dropoff):
            self.assertEqual(event.duration_minutes, 60)
            self.assertEqual(event.duty_status, DutyStatus.ON_DUTY)
        self.assertAlmostEqual(pickup.start_mile, 300, places=6)
        self.assertAlmostEqual(dropoff.start_mile, 1500, places=6)
        self.assertIs(result.events[-1], dropoff)


class BreakTests(SimpleTestCase):
    def test_break_inserted_before_eight_hours_of_driving(self):
        result = schedule(0, 450)  # 9 hours of continuous driving at 50 mph
        breaks = of_type(result, EventType.BREAK)
        self.assertEqual(len(breaks), 1)
        driving_before = sum(e.duration_minutes for e in result.events if e.end <= breaks[0].start and e.type == EventType.DRIVING)
        self.assertEqual(driving_before, 8 * 60)
        self.assertEqual(breaks[0].duration_minutes, 30)
        self.assertEqual(breaks[0].duty_status, DutyStatus.OFF_DUTY)

    def test_pickup_resets_break_clock(self):
        result = schedule(300, 300)  # 6h + pickup + 6h: pickup counts as the break
        self.assertEqual(of_type(result, EventType.BREAK), [])

    def test_no_driving_stretch_exceeds_eight_hours(self):
        result = schedule(200, 2400)
        since_break = 0.0
        for event in result.events:
            if event.type == EventType.DRIVING:
                since_break += event.duration_minutes
                self.assertLessEqual(since_break, 8 * 60)
            elif event.duration_minutes >= 30:
                since_break = 0.0


class ElevenAndFourteenHourTests(SimpleTestCase):
    def test_eleven_hour_limit_forces_ten_hour_rest(self):
        result = schedule(0, 700)  # 14h of driving
        rests = of_type(result, EventType.REST)
        self.assertEqual(len(rests), 1)
        self.assertEqual(rests[0].duration_minutes, 600)
        self.assertEqual(rests[0].details["trigger"], "11_HOUR")
        self.assertTrue(all(block <= 11 * 60 for block in driving_blocks_between_resets(result)))

    def test_fourteen_hour_window_forces_rest_before_dropoff(self):
        # 5h drive + 4h (slow) pickup + 4.5h drive = 13.5h: a 1h dropoff would end past 14h.
        rules = HOSRules(pickup_minutes=4 * 60)
        result = TripScheduler(START, 0, rules).schedule(leg(250), leg(225))
        types = [e.type for e in result.events]
        self.assertEqual(types[-2:], [EventType.REST, EventType.DROPOFF])
        self.assertEqual(result.events[-2].details["trigger"], "14_HOUR")

    def test_fourteen_hour_window_ends_driving_with_hours_left(self):
        # 5h drive + 5h pickup leaves 4h of window but 6h of driving: rest after 4h.
        rules = HOSRules(pickup_minutes=5 * 60)
        result = TripScheduler(START, 0, rules).schedule(leg(250), leg(400))
        first_rest = of_type(result, EventType.REST)[0]
        self.assertEqual(first_rest.details["trigger"], "14_HOUR")
        self.assertEqual(first_rest.start, START + timedelta(hours=14))

    def test_driving_never_occurs_outside_the_fourteen_hour_window(self):
        checks = {c["rule"]: c for c in audit_schedule(schedule(150, 1900).events, START, 0)}
        self.assertTrue(checks["14_HOUR"]["passed"])
        self.assertLessEqual(checks["14_HOUR"]["observed"], 14)


class FuelTests(SimpleTestCase):
    def test_fuel_stop_before_every_thousand_miles(self):
        result = schedule(250, 2600)
        fuel_stops = of_type(result, EventType.FUEL)
        self.assertEqual(len(fuel_stops), 2)
        last_fuel_mile = 0.0
        for event in result.events:
            if event.type == EventType.DRIVING:
                self.assertLessEqual(event.end_mile - last_fuel_mile, 1000 + 1e-6)
            if event.type == EventType.FUEL:
                last_fuel_mile = event.start_mile
                self.assertEqual(event.duty_status, DutyStatus.ON_DUTY)
                self.assertEqual(event.duration_minutes, 30)

    def test_no_fuel_stop_for_trips_under_the_interval(self):
        self.assertEqual(of_type(schedule(100, 850), EventType.FUEL), [])


class CycleTests(SimpleTestCase):
    def test_high_cycle_usage_allows_only_remaining_hours_before_recovery(self):
        result = schedule(372, 1065, cycle_used=65)
        first_recovery = next(e for e in result.events if e.details.get("trigger") == "CYCLE")
        on_duty_before = sum(e.duration_minutes for e in result.events if e.end <= first_recovery.start and e.duty_status in (DutyStatus.DRIVING, DutyStatus.ON_DUTY))
        self.assertLessEqual(on_duty_before, 5 * 60)
        self.assertTrue(result.warnings)

    def test_exactly_seventy_hours_means_no_driving_until_recovery(self):
        result = schedule(32, 263, cycle_used=70)
        first = result.events[0]
        self.assertIn(first.type, (EventType.REST, EventType.RESTART))
        self.assertEqual(first.details["trigger"], "CYCLE")
        self.assertGreater(first.end, START)

    def test_long_trip_with_high_cycle_stays_within_seventy_hours(self):
        for cycle in (0, 30, 55, 65, 69.5, 70):
            with self.subTest(cycle=cycle):
                result = schedule(400, 2400, cycle_used=cycle)
                checks = {c["rule"]: c for c in audit_schedule(result.events, START, cycle)}
                self.assertTrue(checks["CYCLE"]["passed"], checks["CYCLE"])

    def test_restart_chosen_when_it_delivers_sooner(self):
        result = schedule(372, 1800, cycle_used=65)
        self.assertIn(EventType.RESTART, [e.type for e in result.events])
        restart = of_type(result, EventType.RESTART)[0]
        self.assertEqual(restart.duration_minutes, 34 * 60)

    def test_invalid_cycle_hours_rejected(self):
        for value in (-1, 70.5, 100):
            with self.subTest(value=value):
                with self.assertRaises(ScheduleError):
                    TripScheduler(START, value)


class TimelineIntegrityTests(SimpleTestCase):
    def test_events_are_contiguous_chronological_and_cover_the_distance(self):
        for miles, cycle, hour in [(30, 0, 8), (600, 20, 22), (1800, 50, 3), (3100, 68, 15)]:
            with self.subTest(miles=miles, cycle=cycle):
                start = START.replace(hour=hour)
                result = schedule(miles * 0.2, miles * 0.8, cycle_used=cycle, start=start)
                self.assertEqual(result.events[0].start, start)
                for previous, current in zip(result.events, result.events[1:]):
                    self.assertEqual(previous.end, current.start)
                    self.assertLess(current.start, current.end)
                driven = sum(e.distance_miles for e in result.events)
                self.assertAlmostEqual(driven, miles, places=6)

    def test_every_generated_schedule_passes_the_independent_audit(self):
        for miles in (50, 480, 700, 1100, 2100, 3000):
            for cycle in (0, 40, 62, 70):
                for mph in (45, 60):
                    with self.subTest(miles=miles, cycle=cycle, mph=mph):
                        result = schedule(miles * 0.3, miles * 0.7, cycle_used=cycle, mph=mph)
                        failed = [c for c in audit_schedule(result.events, START, cycle) if not c["passed"]]
                        self.assertEqual(failed, [])

    def test_speed_is_capped_for_unrealistic_provider_durations(self):
        self.assertEqual(leg(650, mph=90).average_speed_mph(), 65.0)

    def test_midnight_start_is_supported(self):
        result = schedule(100, 100, start=datetime(2026, 10, 5, 23, 30))
        self.assertGreater(result.events[-1].end, datetime(2026, 10, 6))
        self.assertEqual(result.events[-1].end - result.events[0].start, timedelta(hours=6))
