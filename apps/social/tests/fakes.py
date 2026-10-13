"""Test doubles for the YouTube integration."""
from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

from apps.social.crypto import encrypt
from apps.social.models import PlatformStats, YouTubeConnection
from apps.social.youtube_client import ChannelSnapshot, TokenSet


def snapshot(*, subscribers=10000, engagement="4.20", handle="@amina") -> ChannelSnapshot:
    return ChannelSnapshot(
        handle_url=f"https://www.youtube.com/{handle}",
        subscribers=subscribers,
        engagement_rate=Decimal(engagement),
        recent_content=[
            {
                "video_id": "v1",
                "title": "My first video",
                "url": "https://www.youtube.com/watch?v=v1",
                "published_at": "2026-10-01T10:00:00Z",
            }
        ],
    )


class FakeYouTubeClient:
    """Scriptable stand-in for YouTubeClient.

    ``fetch_results`` maps an access token to the ChannelSnapshot to return, or to an
    exception instance to raise; unlisted tokens get ``default_snapshot``.
    """

    def __init__(self):
        self.default_snapshot = snapshot()
        self.fetch_results: dict[str, object] = {}
        self.refresh_result: object = TokenSet("refreshed-at", None, 3600)
        self.exchange_result: object = TokenSet("exchanged-at", "exchanged-rt", 3600)
        self.fetch_calls: list[str] = []
        self.refresh_calls: list[str] = []
        self.exchange_calls: list[str] = []

    def build_auth_url(self, state):
        return f"https://accounts.google.com/o/oauth2/v2/auth?state={state}"

    def exchange_code(self, code):
        self.exchange_calls.append(code)
        return self._result(self.exchange_result)

    def refresh_access_token(self, refresh_token):
        self.refresh_calls.append(refresh_token)
        return self._result(self.refresh_result)

    def fetch_channel(self, access_token):
        self.fetch_calls.append(access_token)
        return self._result(self.fetch_results.get(access_token, self.default_snapshot))

    @staticmethod
    def _result(value):
        if isinstance(value, Exception):
            raise value
        return value


def make_connection(
    creator,
    *,
    access="at-1",
    refresh="rt-1",
    expires_in=3600,
    status=YouTubeConnection.Status.CONNECTED,
    with_stats=True,
    followers=100,
) -> YouTubeConnection:
    """A connected creator, as left behind by a previous sync."""
    if with_stats:
        PlatformStats.objects.create(
            creator=creator,
            platform="youtube",
            followers=followers,
            engagement_rate="1.00",
            is_verified=True,
            last_synced_at=timezone.now() - timedelta(days=1),
        )
    return YouTubeConnection.objects.create(
        creator=creator,
        access_token_enc=encrypt(access),
        refresh_token_enc=encrypt(refresh),
        access_expires_at=timezone.now() + timedelta(seconds=expires_in),
        status=status,
    )
