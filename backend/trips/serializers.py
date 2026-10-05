from datetime import datetime, time

from django.utils import timezone
from rest_framework import serializers

from .models import Trip

MAX_CYCLE_HOURS = 70


def _required_text(message: str, max_length: int = 255) -> serializers.CharField:
    return serializers.CharField(
        max_length=max_length,
        trim_whitespace=True,
        error_messages={"blank": message, "required": message, "null": message},
    )


class CoordinateSerializer(serializers.Serializer):
    lat = serializers.FloatField(min_value=-90, max_value=90)
    lng = serializers.FloatField(min_value=-180, max_value=180)
    label = serializers.CharField(max_length=255, required=False, allow_blank=True)
    display_name = serializers.CharField(max_length=500, required=False, allow_blank=True)


class TripPlanRequestSerializer(serializers.Serializer):
    current_location = _required_text("Please enter your current location.")
    pickup_location = _required_text("Please enter a pickup location.")
    dropoff_location = _required_text("Please enter a dropoff location.")
    current_cycle_used = serializers.FloatField(
        error_messages={
            "required": "Please enter current cycle used (hours).",
            "null": "Please enter current cycle used (hours).",
            "invalid": "Current cycle used must be a number of hours.",
        }
    )
    start_time = serializers.DateTimeField(required=False, input_formats=["iso-8601"])
    current_location_coords = CoordinateSerializer(required=False, allow_null=True)
    pickup_location_coords = CoordinateSerializer(required=False, allow_null=True)
    dropoff_location_coords = CoordinateSerializer(required=False, allow_null=True)
    driver_name = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    carrier_name = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    truck_number = serializers.CharField(max_length=50, required=False, allow_blank=True, default="")

    def validate_current_cycle_used(self, value: float) -> float:
        if not 0 <= value <= MAX_CYCLE_HOURS:
            raise serializers.ValidationError("Current cycle used must be between 0 and 70 hours.")
        return round(value, 2)

    def validate_start_time(self, value: datetime) -> datetime:
        # Times are the driver's home-terminal clock: drop any offset, seconds and tzinfo.
        return value.replace(tzinfo=None, second=0, microsecond=0)

    def validate(self, attrs: dict) -> dict:
        if not attrs.get("start_time"):
            attrs["start_time"] = datetime.combine(timezone.localdate(), time(8, 0))
        if attrs["pickup_location"].lower() == attrs["dropoff_location"].lower():
            raise serializers.ValidationError({"dropoff_location": "Pickup and dropoff must be different locations."})
        return attrs


class TripListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Trip
        fields = [
            "id",
            "created_at",
            "current_location",
            "pickup_location",
            "dropoff_location",
            "current_cycle_used",
            "start_time",
            "total_distance_miles",
            "total_duration_hours",
            "log_days",
        ]
