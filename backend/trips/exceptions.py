"""Uniform, user-safe API errors: ``{"error": {"code", "message", "fields"}}``."""

import logging

from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import exception_handler

from .services.exceptions import TripPlanningError

logger = logging.getLogger(__name__)

GENERIC_MESSAGE = "Something went wrong while planning the trip. Please try again."


def _flatten(detail, prefix: str = "") -> dict[str, str]:
    if isinstance(detail, dict):
        flat: dict[str, str] = {}
        for key, value in detail.items():
            flat.update(_flatten(value, f"{prefix}{key}."))
        return flat
    key = prefix.rstrip(".") or "non_field_errors"
    if isinstance(detail, list):
        if detail and isinstance(detail[0], dict):
            return _flatten(detail[0], prefix)
        return {key: str(detail[0]) if detail else ""}
    return {key: str(detail)}


def api_exception_handler(exc, context):
    if isinstance(exc, TripPlanningError):
        fields = {exc.field: exc.message} if exc.field else {}
        return Response({"error": {"code": exc.code, "message": exc.message, "fields": fields}}, status=exc.status_code)

    response = exception_handler(exc, context)
    if response is None:
        logger.exception("Unhandled API error", exc_info=exc)
        return Response(
            {"error": {"code": "server_error", "message": GENERIC_MESSAGE, "fields": {}}},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    if isinstance(exc, ValidationError):
        fields = _flatten(exc.detail)
        message = fields.get("non_field_errors") or next(iter(fields.values()), "Please check the form and try again.")
        response.data = {"error": {"code": "validation_error", "message": message, "fields": fields}}
    else:
        detail = response.data.get("detail", GENERIC_MESSAGE) if isinstance(response.data, dict) else GENERIC_MESSAGE
        response.data = {"error": {"code": getattr(exc, "default_code", "error"), "message": str(detail), "fields": {}}}
    return response
