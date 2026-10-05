"""API tests with geocoding and routing replaced by deterministic fakes."""

from unittest import mock

from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from trips.models import Trip
from trips.services.exceptions import GeocodingError, RoutingError
from trips.services.geo import LatLng
from trips.services.geocoding_service import GeocodedLocation
from trips.services.routing_service import RouteLeg

PLACES = {
    "dallas, tx": GeocodedLocation("Dallas, TX", "Dallas, TX", "Dallas, Texas, USA", 32.7767, -96.7970),
    "fort worth, tx": GeocodedLocation("Fort Worth, TX", "Fort Worth, TX", "Fort Worth, Texas, USA", 32.7555, -97.3308),
    "houston, tx": GeocodedLocation("Houston, TX", "Houston, TX", "Houston, Texas, USA", 29.7604, -95.3698),
    "chicago, il": GeocodedLocation("Chicago, IL", "Chicago, IL", "Chicago, Illinois, USA", 41.8781, -87.6298),
}


def fake_geocode(query: str) -> GeocodedLocation:
    try:
        return PLACES[query.lower()]
    except KeyError:
        raise GeocodingError(f'We could not find "{query}".') from None


class FakeProvider:
    """Straight-line 'routes' at 1.2x crow-flies distance and 55 mph."""

    name = "Fake router"

    def route(self, start: LatLng, end: LatLng) -> RouteLeg:
        from trips.services.geo import haversine_miles

        miles = haversine_miles(start, end) * 1.2
        mid = LatLng((start.lat + end.lat) / 2, (start.lng + end.lng) / 2)
        return RouteLeg(miles * 1609.344, miles / 55 * 3600, [start, mid, end])


class FailingProvider(FakeProvider):
    name = "Failing router"

    def route(self, start, end):
        raise RoutingError("Unable to calculate this route. Please verify your locations and try again.")


def payload(**overrides):
    body = {
        "current_location": "Dallas, TX",
        "pickup_location": "Fort Worth, TX",
        "dropoff_location": "Houston, TX",
        "current_cycle_used": 20,
        "start_time": "2026-10-05T08:00",
    }
    body.update(overrides)
    return body


@mock.patch("trips.services.trip_planner.geocode", side_effect=fake_geocode)
@mock.patch("trips.services.trip_planner.get_routing_provider", return_value=FakeProvider())
class TripPlanApiTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()

    def post(self, **overrides):
        return self.client.post("/api/trips/plan/", payload(**overrides), format="json")

    def test_plan_returns_complete_payload(self, *_):
        response = self.post()
        self.assertEqual(response.status_code, 201)
        data = response.json()
        for key in ("trip_summary", "route", "events", "daily_logs", "stops", "hos_summary", "assumptions", "id"):
            self.assertIn(key, data)
        self.assertEqual(data["trip_summary"]["log_days"], 1)
        self.assertEqual(data["trip_summary"]["pickup_duration_hours"], 1.0)
        self.assertTrue(data["hos_summary"]["all_checks_passed"])
        self.assertEqual(data["hos_summary"]["cycle_remaining_hours"], 50)
        self.assertTrue(Trip.objects.filter(pk=data["id"]).exists())

    def test_map_stops_and_logs_reference_schedule_events(self, *_):
        data = self.post(dropoff_location="Chicago, IL").json()
        event_ids = {e["id"] for e in data["events"]}
        stop_event_ids = {s["event_id"] for s in data["stops"] if s["event_id"]}
        self.assertTrue(stop_event_ids <= event_ids)
        logged = {seg["event_id"] for log in data["daily_logs"] for seg in log["segments"] if seg["event_id"]}
        self.assertEqual(logged, event_ids)
        self.assertGreater(len(data["daily_logs"]), 1)

    def test_saved_trip_can_be_retrieved(self, *_):
        trip_id = self.post().json()["id"]
        response = self.client.get(f"/api/trips/{trip_id}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], trip_id)
        self.assertEqual(len(self.client.get("/api/trips/").json()), 1)

    def test_autocomplete_coordinates_skip_geocoding(self, _provider, geocode_mock):
        coords = {"lat": 32.78, "lng": -96.8, "label": "Dallas, TX"}
        response = self.post(current_location_coords=coords)
        self.assertEqual(response.status_code, 201)
        queried = [call.args[0] for call in geocode_mock.call_args_list]
        self.assertNotIn("Dallas, TX", queried)

    def test_missing_location_is_rejected(self, *_):
        response = self.post(pickup_location="  ")
        self.assertEqual(response.status_code, 400)
        error = response.json()["error"]
        self.assertEqual(error["fields"]["pickup_location"], "Please enter a pickup location.")

    def test_cycle_hours_must_be_between_0_and_70(self, *_):
        for value in (-1, 70.01, 120):
            with self.subTest(value=value):
                response = self.post(current_cycle_used=value)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json()["error"]["message"], "Current cycle used must be between 0 and 70 hours.")

    def test_cycle_hours_must_be_numeric(self, *_):
        response = self.post(current_cycle_used="lots")
        self.assertEqual(response.status_code, 400)

    def test_exactly_seventy_hours_is_reported_clearly(self, *_):
        data = self.post(current_cycle_used=70).json()
        self.assertEqual(data["hos_summary"]["status"], "NO_HOURS_AVAILABLE")
        self.assertEqual(data["hos_summary"]["cycle_remaining_hours"], 0)
        self.assertEqual(data["events"][0]["trigger"], "CYCLE")

    def test_cycle_message_matches_whether_recovery_time_was_added(self, *_):
        # Starting late, older hours recap at midnight while driving: no wait is needed.
        night = self.post(current_cycle_used=65, start_time="2026-10-05T20:00").json()["hos_summary"]
        self.assertEqual(night["status"], "RECOVERY_REQUIRED")
        self.assertEqual(night["cycle_recoveries"], [])
        self.assertIn("no extra off-duty time", night["message"])
        # Starting in the morning, the 5 remaining hours run out before midnight.
        morning = self.post(current_cycle_used=65).json()["hos_summary"]
        self.assertTrue(morning["cycle_recoveries"])
        self.assertIn("adds off-duty time", morning["message"])

    def test_same_pickup_and_dropoff_rejected(self, *_):
        response = self.post(dropoff_location="Fort Worth, TX")
        self.assertEqual(response.status_code, 400)
        self.assertIn("dropoff_location", response.json()["error"]["fields"])

    def test_unknown_location_returns_field_error(self, *_):
        response = self.post(dropoff_location="Atlantis")
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["code"], "geocoding_failed")
        self.assertIn("dropoff_location", response.json()["error"]["fields"])

    def test_routing_failure_returns_friendly_error(self, provider_mock, _):
        provider_mock.return_value = FailingProvider()
        response = self.post()
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["message"], "Unable to calculate this route. Please verify your locations and try again.")

    def test_unexpected_errors_do_not_leak_details(self, provider_mock, _):
        provider_mock.side_effect = RuntimeError("database password is hunter2")
        with self.assertLogs("trips.exceptions", level="ERROR"):
            response = self.post()
        self.assertEqual(response.status_code, 500)
        self.assertNotIn("hunter2", response.content.decode())


class MiscEndpointTests(TestCase):
    def test_health(self):
        self.assertEqual(self.client.get("/api/health/").json(), {"status": "ok"})

    def test_assumptions_are_exposed(self):
        data = self.client.get("/api/hos/assumptions/").json()
        self.assertEqual(data["rules"]["cycle_limit_minutes"], 70 * 60)
        self.assertTrue(data["statements"])

    def test_autocomplete_ignores_short_queries(self):
        self.assertEqual(self.client.get("/api/geocode/autocomplete/?q=da").json(), {"results": []})
