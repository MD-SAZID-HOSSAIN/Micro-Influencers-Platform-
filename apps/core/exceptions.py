from rest_framework.exceptions import APIException, ValidationError
from rest_framework.views import exception_handler as drf_exception_handler


class DomainError(APIException):
    """Base class for business-rule failures raised from services."""

    status_code = 400
    default_code = "domain_error"
    default_detail = "The request could not be completed."


class Conflict(DomainError):
    status_code = 409
    default_code = "conflict"
    default_detail = "The request conflicts with the current state."


def api_exception_handler(exc, context):
    """Render every API error as {"error": {"code", "message", "details"}}."""
    response = drf_exception_handler(exc, context)
    if response is None:
        return None

    if isinstance(exc, ValidationError):
        code, message, details = "validation_error", "Invalid input.", response.data
    else:
        detail = response.data.get("detail") if isinstance(response.data, dict) else None
        code = getattr(detail, "code", None) or "error"
        message = str(detail) if detail is not None else "An error occurred."
        details = None

    response.data = {"error": {"code": code, "message": message, "details": details}}
    return response


class ServiceUnavailable(DomainError):
    """A dependency (such as the shared cache) is down; the caller can simply try again shortly."""

    status_code = 503
    default_code = "temporarily_unavailable"
    default_detail = "This feature is temporarily unavailable. Please try again in a moment."
