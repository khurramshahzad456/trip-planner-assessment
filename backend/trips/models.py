import uuid

from django.db import models


class Trip(models.Model):
    """A planned trip. The full plan is stored as JSON so it can be re-opened by link."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    current_location = models.CharField(max_length=255)
    pickup_location = models.CharField(max_length=255)
    dropoff_location = models.CharField(max_length=255)
    current_cycle_used = models.DecimalField(max_digits=4, decimal_places=2)
    # Home-terminal wall-clock time, kept as text so no timezone conversion is applied.
    start_time = models.CharField(max_length=16)

    total_distance_miles = models.FloatField()
    total_duration_hours = models.FloatField()
    log_days = models.PositiveIntegerField()

    plan = models.JSONField()

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.current_location} → {self.pickup_location} → {self.dropoff_location}"
