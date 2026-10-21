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
        self.channel_link_result: object = "https://www.youtube.com/@brandchannel"  # used by brand sign-in
        self.fetch_results: dict[str, object] = {}
        self.refresh_result: object = TokenSet("refreshed-at", None, 3600)
        self.exchange_result: object = TokenSet("exchanged-at", "exchanged-rt", 3600)
        self.fetch_calls: list[str] = []
        self.refresh_calls: list[str] = []
        self.exchange_calls: list[str] = []
        self.revoked: list[str] = []
        self.revoke_error: Exception | None = None
        # video statistics (FR-23 content performance): id -> VideoStats, or an exception per batch
        self.video_results: dict[str, object] = {}
        self.video_batch_errors: list[Exception | None] = []  # consumed one per call, in order
        self.video_calls: list[tuple[list[str], str]] = []

    def build_auth_url(self, state):
        return f"https://accounts.google.com/o/oauth2/v2/auth?state={state}"

    def exchange_code(self, code):
        self.exchange_calls.append(code)
        return self._result(self.exchange_result)

    def refresh_access_token(self, refresh_token):
        self.refresh_calls.append(refresh_token)
        return self._result(self.refresh_result)

    def revoke_token(self, token):
        if self.revoke_error is not None:
            raise self.revoke_error
        self.revoked.append(token)

    def fetch_channel(self, access_token):
        self.fetch_calls.append(access_token)
        return self._result(self.fetch_results.get(access_token, self.default_snapshot))

    def fetch_channel_link(self, access_token):
        return self._result(self.channel_link_result)

    def fetch_video_stats(self, video_ids, api_key):
        self.video_calls.append((list(video_ids), api_key))
        if self.video_batch_errors:
            error = self.video_batch_errors.pop(0)
            if error is not None:
                raise error
        return {vid: self.video_results[vid] for vid in video_ids if vid in self.video_results}

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
