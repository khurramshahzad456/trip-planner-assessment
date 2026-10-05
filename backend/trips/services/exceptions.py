"""Domain errors raised by the planning services and mapped to API responses."""


class TripPlanningError(Exception):
    """Base class for errors that are safe to show to the user."""

    status_code = 422
    code = "trip_planning_error"

    def __init__(self, message: str, field: str | None = None):
        super().__init__(message)
        self.message = message
        self.field = field


class GeocodingError(TripPlanningError):
    code = "geocoding_failed"


class RoutingError(TripPlanningError):
    code = "routing_failed"


class ProviderUnavailableError(TripPlanningError):
    status_code = 503
    code = "provider_unavailable"
