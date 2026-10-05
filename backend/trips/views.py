import logging

from django.db import DatabaseError
from rest_framework import status
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Trip
from .serializers import TripListSerializer, TripPlanRequestSerializer
from .services.exceptions import TripPlanningError
from .services.geocoding_service import autocomplete
from .services.hos_rules import describe_assumptions
from .services.trip_planner import LOCATION_FIELDS, TripRequest, plan_trip

logger = logging.getLogger(__name__)


class HealthView(APIView):
    def get(self, request):
        return Response({"status": "ok"})


class AssumptionsView(APIView):
    def get(self, request):
        return Response(describe_assumptions())


class AutocompleteView(APIView):
    throttle_scope = "autocomplete"

    def get(self, request):
        query = request.query_params.get("q", "").strip()
        if len(query) < 3:
            return Response({"results": []})
        try:
            return Response({"results": autocomplete(query[:120])})
        except TripPlanningError:
            # Suggestions are a convenience; the form still works without them.
            return Response({"results": [], "unavailable": True})


class TripPlanView(APIView):
    """POST /api/trips/plan/ — geocode, route and build an HOS-compliant schedule."""

    throttle_scope = "trip_plan"

    def post(self, request):
        serializer = TripPlanRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        trip_request = TripRequest(
            current_location=data["current_location"],
            pickup_location=data["pickup_location"],
            dropoff_location=data["dropoff_location"],
            current_cycle_used=data["current_cycle_used"],
            start_time=data["start_time"],
            coordinates={f: data[f"{f}_coords"] for f in LOCATION_FIELDS if data.get(f"{f}_coords")},
            driver_name=data.get("driver_name", ""),
            carrier_name=data.get("carrier_name", ""),
            truck_number=data.get("truck_number", ""),
        )
        plan = plan_trip(trip_request)
        plan["id"] = self._persist(trip_request, plan)
        return Response(plan, status=status.HTTP_201_CREATED)

    @staticmethod
    def _persist(trip_request: TripRequest, plan: dict) -> str | None:
        try:
            trip = Trip.objects.create(
                current_location=trip_request.current_location,
                pickup_location=trip_request.pickup_location,
                dropoff_location=trip_request.dropoff_location,
                current_cycle_used=trip_request.current_cycle_used,
                start_time=trip_request.start_time.isoformat(timespec="minutes"),
                total_distance_miles=plan["trip_summary"]["total_distance_miles"],
                total_duration_hours=plan["trip_summary"]["total_duration_hours"],
                log_days=plan["trip_summary"]["log_days"],
                plan=plan,
            )
        except DatabaseError:
            # Saving only powers shareable links; never fail a computed plan because of it.
            logger.exception("Could not persist trip plan")
            return None
        return str(trip.id)


class TripDetailView(RetrieveAPIView):
    """GET /api/trips/<id>/ — re-open a previously planned trip."""

    queryset = Trip.objects.all()

    def retrieve(self, request, *args, **kwargs):
        trip = self.get_object()
        return Response({**trip.plan, "id": str(trip.id)})


class TripListView(ListAPIView):
    """GET /api/trips/ — the ten most recent plans."""

    serializer_class = TripListSerializer
    pagination_class = None

    def get_queryset(self):
        return Trip.objects.all()[:10]
