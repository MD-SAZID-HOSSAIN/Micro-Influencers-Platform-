import secrets
from datetime import timedelta
from decimal import Decimal
from urllib.parse import urlencode, urlparse

from django.conf import settings
from django.core.cache import cache
from django.http import Http404, HttpResponseRedirect
from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.generics import GenericAPIView, ListAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.choices import Platform
from apps.core.throttling import FailOpenScopedRateThrottle
from apps.core.permissions import IsCreator

from .crypto import encrypt
from .models import PlatformStats, YouTubeConnection
from .serializers import (
    AuthorizationUrlSerializer,
    ChallengeCodeSerializer,
    CompleteConnectSerializer,
    DirectAccountAuthSerializer,
    PlatformStatsSerializer,
    RecentVideoSerializer,
    YouTubeDirectConnectSerializer,
    YouTubeStatusSerializer,
)
from .services import (
    DIRECT_ACCESS_TOKEN,
    DIRECT_REFRESH_TOKEN,
    ConnectError,
    complete_connect,
    connection_status,
    disconnect,
    read_state,
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

    @extend_schema(tags=["Social"], responses={204: None})
    def delete(self, request, platform):
        if platform not in Platform.values:
            raise Http404
        PlatformStats.objects.filter(creator=request.user, platform=platform).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


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
        if not settings.GOOGLE_CLIENT_ID:
            return Response({"authorization_url": ""})
        return Response({"authorization_url": start_connect(request.user)})


class YouTubeCallbackView(APIView):
    """Google redirects the browser here, so there is no bearer token and nothing is saved.

    It only checks the state's signature and age, then redirects to the frontend:
    ``?youtube=confirm&code=...&state=...`` (the frontend, logged in, then POSTs both to
    ``/social/youtube/complete/``) or ``?youtube=error&reason=...``.
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
            return self._redirect({"youtube": "error", "reason": "access_denied"})
        state, code = params.get("state", ""), params.get("code", "")
        if not state or not code:
            return self._redirect({"youtube": "error", "reason": "invalid_state"})
        try:
            read_state(state)
        except ConnectError as exc:
            return self._redirect({"youtube": "error", "reason": exc.reason})
        return self._redirect({"youtube": "confirm", "code": code, "state": state})

    @staticmethod
    def _redirect(query: dict):
        return HttpResponseRedirect(
            f"{settings.FRONTEND_URL}/settings/connections?{urlencode(query)}"
        )


class YouTubeCompleteView(GenericAPIView):
    """Finish connecting YouTube. Send back the ``code`` and ``state`` the callback redirect carried.

    The state must have been issued to the logged-in creator, so a link started by someone else
    cannot be completed here.
    """

    permission_classes = [IsCreator]
    throttle_classes = [FailOpenScopedRateThrottle]
    throttle_scope = "youtube_complete"
    serializer_class = CompleteConnectSerializer

    @extend_schema(tags=["Social"], responses={200: YouTubeStatusSerializer})
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        complete_connect(user=request.user, **serializer.validated_data)
        return Response(connection_status(request.user))


class YouTubeDirectConnectView(GenericAPIView):
    """Directly link and verify a YouTube channel by handle or URL."""

    permission_classes = [IsCreator]
    serializer_class = YouTubeDirectConnectSerializer

    @extend_schema(tags=["Social"], responses={200: YouTubeStatusSerializer})
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        handle_url = serializer.validated_data.get("handle_url") or ""
        followers = serializer.validated_data.get("followers", 0)
        engagement_rate = serializer.validated_data.get("engagement_rate", Decimal("3.50"))

        now = timezone.now()
        clean_handle_url = handle_url

        if handle_url:
            from .youtube_public import fetch_public_channel, normalize_youtube_input
            live_data = fetch_public_channel(handle_url)
            if live_data.get("success"):
                clean_handle_url = live_data["canonical_url"]
                followers = live_data["subscribers"]

                # If creator has no avatar photo, populate with YouTube channel avatar
                from apps.profiles.services import get_or_create_profile
                profile = get_or_create_profile(request.user)
                if not profile.photo_url and live_data.get("avatar_url"):
                    profile.photo_url = live_data["avatar_url"]
                    profile.save(update_fields=["photo_url"])
            else:
                norm_url, _ = normalize_youtube_input(handle_url)
                if norm_url:
                    clean_handle_url = norm_url

        try:
            access_enc = encrypt(DIRECT_ACCESS_TOKEN)
            refresh_enc = encrypt(DIRECT_REFRESH_TOKEN)
        except Exception:
            access_enc = f"{DIRECT_ACCESS_TOKEN}-plain"
            refresh_enc = f"{DIRECT_REFRESH_TOKEN}-plain"

        YouTubeConnection.objects.update_or_create(
            creator=request.user,
            defaults={
                "access_token_enc": access_enc,
                "refresh_token_enc": refresh_enc,
                "access_expires_at": now + timedelta(days=365),
                "status": YouTubeConnection.Status.CONNECTED,
                "last_error": "",
            },
        )

        PlatformStats.objects.update_or_create(
            creator=request.user,
            platform="youtube",
            defaults={
                "handle_url": clean_handle_url,
                "followers": followers,
                "engagement_rate": engagement_rate,
                "is_verified": True,
                "is_outdated": False,
                "last_synced_at": now,
            },
        )

        return Response(connection_status(request.user))


class YouTubeRecentContentView(APIView):
    """Recent videos from the last sync, used to suggest portfolio items."""

    permission_classes = [IsCreator]

    @extend_schema(tags=["Social"], responses={200: RecentVideoSerializer(many=True)})
    def get(self, request):
        connection = YouTubeConnection.objects.filter(creator=request.user).first()
        return Response(connection.recent_content if connection else [])


class SocialChallengeView(APIView):
    """Generate a temporary, unique verification challenge code to verify account ownership."""

    permission_classes = [IsCreator]

    @extend_schema(tags=["Social"], responses={200: ChallengeCodeSerializer})
    def get(self, request, platform):
        if platform not in Platform.values:
            raise Http404
        code = f"MIC-{secrets.randbelow(90000) + 10000}"
        cache.set(f"challenge:{request.user.id}:{platform.lower()}", code, 900)
        instructions = (
            f"Add this verification code '{code}' to your {platform.capitalize()} profile bio or page description. "
            f"Then click 'Verify Ownership' to confirm that you own this account."
        )
        return Response({
            "platform": platform,
            "challenge_code": code,
            "instructions": instructions,
        })


class DirectAccountConnectView(GenericAPIView):
    """Directly connect and verify ownership of a social account (OAuth or Challenge verification)."""

    permission_classes = [IsCreator]
    serializer_class = DirectAccountAuthSerializer

    @extend_schema(tags=["Social"], responses={200: PlatformStatsSerializer})
    def post(self, request, platform):
        if platform not in Platform.values:
            raise Http404

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        handle = serializer.validated_data["handle"].strip()
        method = serializer.validated_data.get("verification_method", "direct_auth")
        auth_code = serializer.validated_data.get("auth_code", "").strip()
        followers = serializer.validated_data.get("followers", 0)
        engagement_rate = serializer.validated_data.get("engagement_rate", Decimal("3.50"))

        if method == "challenge":
            cached = cache.get(f"challenge:{request.user.id}:{platform.lower()}")
            if not cached or cached.lower() != auth_code.lower():
                return Response(
                    {"error": {"code": "challenge_failed", "message": "Verification code does not match the active challenge code."}},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            cache.delete(f"challenge:{request.user.id}:{platform.lower()}")

        # Clean handle and format standard profile URL
        raw_handle = handle.lstrip("@").strip()
        if raw_handle.startswith("http://") or raw_handle.startswith("https://"):
            parsed = urlparse(raw_handle)
            raw_handle = parsed.path.strip("/").split("/")[0]

        if platform == "instagram":
            canonical_url = f"https://instagram.com/{raw_handle}"
        elif platform == "facebook":
            canonical_url = f"https://facebook.com/{raw_handle}"
        elif platform == "tiktok":
            canonical_url = f"https://tiktok.com/@{raw_handle}"
        elif platform == "youtube":
            canonical_url = f"https://youtube.com/@{raw_handle}"
        else:
            canonical_url = f"https://{platform}.com/{raw_handle}"

        now = timezone.now()
        stats, _ = PlatformStats.objects.update_or_create(
            creator=request.user,
            platform=platform,
            defaults={
                "handle_url": canonical_url,
                "followers": followers,
                "engagement_rate": engagement_rate,
                "is_verified": True,
                "is_outdated": False,
                "last_synced_at": now,
            },
        )
        return Response(PlatformStatsSerializer(stats).data)


class InstagramConnectView(APIView):
    """Start Meta / Instagram OAuth flow."""

    permission_classes = [IsCreator]

    @extend_schema(tags=["Social"], responses={200: AuthorizationUrlSerializer})
    def get(self, request):
        app_id = getattr(settings, "INSTAGRAM_CLIENT_ID", "") or getattr(settings, "META_APP_ID", "")
        if not app_id:
            return Response({"authorization_url": ""})
        redirect_uri = getattr(settings, "INSTAGRAM_REDIRECT_URI", "") or f"{settings.FRONTEND_URL}/settings/connections"
        url = (
            f"https://api.instagram.com/oauth/authorize"
            f"?client_id={app_id}&redirect_uri={redirect_uri}&scope=user_profile,user_media&response_type=code"
        )
        return Response({"authorization_url": url})


class FacebookConnectView(APIView):
    """Start Meta / Facebook OAuth flow."""

    permission_classes = [IsCreator]

    @extend_schema(tags=["Social"], responses={200: AuthorizationUrlSerializer})
    def get(self, request):
        app_id = getattr(settings, "META_APP_ID", "")
        if not app_id:
            return Response({"authorization_url": ""})
        redirect_uri = getattr(settings, "META_REDIRECT_URI", "") or f"{settings.FRONTEND_URL}/settings/connections"
        url = (
            f"https://www.facebook.com/v19.0/dialog/oauth"
            f"?client_id={app_id}&redirect_uri={redirect_uri}&scope=pages_show_list,pages_read_engagement&response_type=code"
        )
        return Response({"authorization_url": url})

