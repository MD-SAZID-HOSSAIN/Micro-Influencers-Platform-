from django.db import connection
from django.http import JsonResponse
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView


class HealthView(APIView):
    """Liveness/readiness probe: confirms the app can reach its database."""

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(tags=["Health"], responses={200: dict})
    def get(self, request):
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        return Response({"status": "ok", "database": "ok"})


def _error(code: str, message: str, status: int) -> JsonResponse:
    return JsonResponse({"error": {"code": code, "message": message, "details": None}}, status=status)


def not_found(request, exception=None):
    """Unmatched URLs, in the standard error envelope instead of Django's HTML page."""
    return _error("not_found", "Not found.", 404)


def server_error(request):
    """Unhandled exceptions: a generic message, never a traceback or internals."""
    return _error("server_error", "Something went wrong.", 500)
