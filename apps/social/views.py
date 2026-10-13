from urllib.parse import urlencode

from django.conf import settings
from django.http import Http404, HttpResponseRedirect
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.choices import Platform
from apps.core.permissions import IsCreator

from .models import PlatformStats, YouTubeConnection
from .serializers import (
    AuthorizationUrlSerializer,
    PlatformStatsSerializer,
    RecentVideoSerializer,
    YouTubeStatusSerializer,
)
from .services import (
    ConnectError,
    complete_connect,
    connection_status,
    disconnect,
    request_manual_refresh,
    set_manual_stats,
    start_connect,
)


@extend_schema(tags=["Social"])
class MyStatsListView(ListAPIView):
    permission_classes = [IsCreator]
    serializer_class = PlatformStatsSerializer
    pagination_class = None

    def get_queryset(self):
        return PlatformStats.objects.filter(creator=self.request.user)


class ManualStatsView(APIView):
    """Enter Unverified stats by hand for a platform (the fallback to account connection)."""

    permission_classes = [IsCreator]

    @extend_schema(
        tags=["Social"], request=PlatformStatsSerializer, responses={200: PlatformStatsSerializer}
    )
    def put(self, request, platform):
        if platform not in Platform.values:
            raise Http404
        serializer = PlatformStatsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        stats = set_manual_stats(creator=request.user, platform=platform, **serializer.validated_data)
        return Response(PlatformStatsSerializer(stats).data)


class YouTubeRefreshView(APIView):
    """Ask for an immediate stats refresh (rate limited by a cooldown)."""

    permission_classes = [IsCreator]

    @extend_schema(tags=["Social"], request=None, responses={202: None})
    def post(self, request):
        request_manual_refresh(request.user)
        return Response({"detail": "Refresh scheduled."}, status=status.HTTP_202_ACCEPTED)


class YouTubeConnectionView(APIView):
    """GET the connection state; DELETE to disconnect (tokens are deleted)."""

    permission_classes = [IsCreator]

    @extend_schema(tags=["Social"], responses={200: YouTubeStatusSerializer})
    def get(self, request):
        return Response(connection_status(request.user))

    @extend_schema(tags=["Social"], responses={204: None})
    def delete(self, request):
        disconnect(request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


class YouTubeConnectView(APIView):
    """Start the OAuth flow: returns the Google consent URL to send the creator to."""

    permission_classes = [IsCreator]

    @extend_schema(tags=["Social"], responses={200: AuthorizationUrlSerializer})
    def get(self, request):
        return Response({"authorization_url": start_connect(request.user)})


class YouTubeCallbackView(APIView):
    """Google redirects the browser here, so there is no bearer token.

    The signed ``state`` identifies the creator. The response is always a redirect back to
    the frontend: ``?youtube=success`` or ``?youtube=error&reason=...``.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        tags=["Social"],
        responses={302: OpenApiResponse(description="Redirect to the frontend connections page")},
    )
    def get(self, request):
        params = request.query_params
        if params.get("error"):
            return self._redirect(error="access_denied")
        try:
            complete_connect(state=params.get("state", ""), code=params.get("code", ""))
        except ConnectError as exc:
            return self._redirect(error=exc.reason)
        return self._redirect()

    @staticmethod
    def _redirect(error: str | None = None):
        query = {"youtube": "error", "reason": error} if error else {"youtube": "success"}
        return HttpResponseRedirect(
            f"{settings.FRONTEND_URL}/settings/connections?{urlencode(query)}"
        )


class YouTubeRecentContentView(APIView):
    """Recent videos from the last sync, used to suggest portfolio items."""

    permission_classes = [IsCreator]

    @extend_schema(tags=["Social"], responses={200: RecentVideoSerializer(many=True)})
    def get(self, request):
        connection = YouTubeConnection.objects.filter(creator=request.user).first()
        return Response(connection.recent_content if connection else [])
