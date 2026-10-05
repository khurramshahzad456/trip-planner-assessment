"""Tests for midnight splitting and daily ELD log generation."""

from datetime import datetime

from django.test import SimpleTestCase

from trips.services.hos_rules import DutyStatus
from trips.services.log_generator import TimelineItem, build_daily_logs, split_by_day

from .helpers import schedule


def to_items(result) -> list[TimelineItem]:
    return [
        TimelineItem(
            id=f"evt-{i + 1}",
            type=e.type.value,
            duty_status=e.duty_status,
            start=e.start,
            end=e.end,
            distance_miles=e.distance_miles,
            start_label=f"Mile {e.start_mile:.0f}",
            end_label=f"Mile {e.end_mile:.0f}",
        )
        for i, e in enumerate(result.events)
    ]


def logs_for(result, cycle_used=0):
    return build_daily_logs(to_items(result), result.clock.cycle, "Origin", "Destination")


class MidnightSplitTests(SimpleTestCase):
    def test_event_crossing_midnight_is_split_into_two_days(self):
        item = TimelineItem("evt-1", "DRIVING", DutyStatus.DRIVING, datetime(2026, 10, 5, 22), datetime(2026, 10, 6, 3), 250, "A", "B")
        days = split_by_day([item])
        self.assertEqual(len(days), 2)
        first, second = days.values()
        self.assertEqual([round(s.hours, 2) for s in first if s.item], [2.0])
        self.assertEqual([round(s.hours, 2) for s in second if s.item], [3.0])
        self.assertAlmostEqual(sum(s.miles for d in days.values() for s in d), 250)

    def test_driving_miles_are_prorated_across_midnight(self):
        item = TimelineItem("evt-1", "DRIVING", DutyStatus.DRIVING, datetime(2026, 10, 5, 23), datetime(2026, 10, 6, 1), 100, "A", "B")
        first, second = split_by_day([item]).values()
        self.assertAlmostEqual(sum(s.miles for s in first), 50)
        self.assertAlmostEqual(sum(s.miles for s in second), 50)

    def test_trip_ending_exactly_at_midnight_creates_no_empty_day(self):
        item = TimelineItem("evt-1", "PICKUP", DutyStatus.ON_DUTY, datetime(2026, 10, 5, 23), datetime(2026, 10, 6, 0), 0, "A", "A")
        self.assertEqual(len(split_by_day([item])), 1)


class DailyLogTests(SimpleTestCase):
    def test_every_log_accounts_for_exactly_24_hours(self):
        for log in logs_for(schedule(400, 2200, cycle_used=30)):
            with self.subTest(day=log["day_number"]):
                self.assertAlmostEqual(sum(log["totals"].values()), 24, places=2)
                self.assertEqual(log["segments"][0]["start_hour"], 0)
                self.assertEqual(log["segments"][-1]["end_hour"], 24)
                for a, b in zip(log["segments"], log["segments"][1:]):
                    self.assertEqual(a["end_hour"], b["start_hour"])

    def test_multi_day_trip_produces_one_log_per_calendar_day(self):
        result = schedule(372, 1765)
        logs = logs_for(result)
        expected_days = (result.events[-1].end.date() - result.events[0].start.date()).days + 1
        self.assertEqual(len(logs), expected_days)
        self.assertGreaterEqual(len(logs), 3)
        self.assertEqual([log["day_number"] for log in logs], list(range(1, len(logs) + 1)))

    def test_log_totals_match_the_schedule(self):
        result = schedule(300, 1500)
        logs = logs_for(result)
        driving = sum(e.duration_minutes for e in result.events if e.duty_status == DutyStatus.DRIVING) / 60
        on_duty = sum(e.duration_minutes for e in result.events if e.duty_status == DutyStatus.ON_DUTY) / 60
        self.assertAlmostEqual(sum(log["totals"]["driving"] for log in logs), driving, places=1)
        self.assertAlmostEqual(sum(log["totals"]["on_duty"] for log in logs), on_duty, places=1)
        self.assertAlmostEqual(logs[-1]["cumulative_miles"], 1800, places=0)

    def test_time_before_and_after_trip_is_off_duty(self):
        logs = logs_for(schedule(32, 263))
        self.assertEqual(len(logs), 1)
        segments = logs[0]["segments"]
        self.assertEqual(segments[0]["status"], "OFF_DUTY")
        self.assertEqual(segments[0]["end_hour"], 8)
        self.assertEqual(segments[-1]["status"], "OFF_DUTY")

    def test_cycle_recap_reported_per_day(self):
        logs = logs_for(schedule(32, 263, cycle_used=45))
        cycle = logs[0]["cycle"]
        self.assertAlmostEqual(cycle["used_hours"] + cycle["remaining_hours"], 70)
        self.assertGreater(cycle["used_hours"], 45)

    def test_remarks_record_each_duty_status_change(self):
        log = logs_for(schedule(32, 263))[0]
        activities = [r["activity"] for r in log["remarks"]]
        self.assertEqual(activities, ["Off duty", "Driving", "Pickup", "Driving", "Dropoff", "Off duty"])
        self.assertEqual(log["remarks"][0]["location"], "Origin")
        self.assertEqual(log["remarks"][-1]["location"], "Destination")

    def test_continued_events_are_marked_on_the_next_day(self):
        logs = logs_for(schedule(0, 700, start=datetime(2026, 10, 5, 18)))
        self.assertTrue(any("(continued)" in r["activity"] for r in logs[1]["remarks"]))
