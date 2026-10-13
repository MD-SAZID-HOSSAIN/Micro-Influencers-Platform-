"""Thin client for Google OAuth and the YouTube Data API (read-only)."""
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from urllib.parse import urlencode

import requests
from django.conf import settings

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
API_URL = "https://www.googleapis.com/youtube/v3"
SCOPE = "https://www.googleapis.com/auth/youtube.readonly"
TIMEOUT_SECONDS = 10
RECENT_VIDEOS = 10

_QUOTA_REASONS = {"quotaExceeded", "rateLimitExceeded", "dailyLimitExceeded", "userRateLimitExceeded"}
_PERMISSION_REASONS = {"insufficientPermissions", "forbidden"}


class YouTubeError(Exception):
    """Base class for every failure talking to Google."""


class TokenRevoked(YouTubeError):
    """The grant or access token is no longer valid; the creator must reconnect."""


class TransientApiError(YouTubeError):
    """Timeouts, 5xx, rate limits: safe to retry later."""


class QuotaExceeded(TransientApiError):
    """The YouTube API daily quota or rate limit was hit."""


class ChannelNotFound(YouTubeError):
    """The Google account has no YouTube channel."""


@dataclass(frozen=True)
class TokenSet:
    access_token: str
    refresh_token: str | None
    expires_in: int


@dataclass(frozen=True)
class ChannelSnapshot:
    handle_url: str
    subscribers: int
    engagement_rate: Decimal
    recent_content: list[dict] = field(default_factory=list)


def _error_reasons(response: requests.Response) -> set[str]:
    try:
        errors = response.json().get("error", {})
    except ValueError:
        return set()
    if isinstance(errors, str):
        return {errors}
    return {e.get("reason", "") for e in errors.get("errors", [])} | {errors.get("status", "")}


class YouTubeClient:
    def build_auth_url(self, state: str) -> str:
        params = {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "redirect_uri": settings.GOOGLE_REDIRECT_URI,
            "response_type": "code",
            "scope": SCOPE,
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
        }
        return f"{AUTH_URL}?{urlencode(params)}"

    def exchange_code(self, code: str) -> TokenSet:
        return self._token_request(
            {
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": settings.GOOGLE_REDIRECT_URI,
            }
        )

    def refresh_access_token(self, refresh_token: str) -> TokenSet:
        return self._token_request(
            {"refresh_token": refresh_token, "grant_type": "refresh_token"}
        )

    def fetch_channel(self, access_token: str) -> ChannelSnapshot:
        channels = self._api_get(
            "channels",
            access_token,
            part="snippet,statistics,contentDetails",
            mine="true",
        ).get("items", [])
        if not channels:
            raise ChannelNotFound()
        channel = channels[0]

        custom_url = channel.get("snippet", {}).get("customUrl")
        if custom_url:
            handle_url = f"https://www.youtube.com/{custom_url}"
        else:
            handle_url = f"https://www.youtube.com/channel/{channel['id']}"
        subscribers = int(channel.get("statistics", {}).get("subscriberCount", 0))

        uploads = channel.get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads")
        video_ids = self._recent_video_ids(access_token, uploads) if uploads else []
        if not video_ids:
            return ChannelSnapshot(handle_url, subscribers, Decimal("0.00"), [])

        videos = self._api_get(
            "videos", access_token, part="snippet,statistics", id=",".join(video_ids)
        ).get("items", [])
        return ChannelSnapshot(
            handle_url=handle_url,
            subscribers=subscribers,
            engagement_rate=self._engagement_rate(videos),
            recent_content=[
                {
                    "video_id": v["id"],
                    "title": v.get("snippet", {}).get("title", ""),
                    "url": f"https://www.youtube.com/watch?v={v['id']}",
                    "published_at": v.get("snippet", {}).get("publishedAt", ""),
                }
                for v in videos
            ],
        )

    # -- internals ----------------------------------------------------------------------

    def _recent_video_ids(self, access_token: str, playlist_id: str) -> list[str]:
        items = self._api_get(
            "playlistItems",
            access_token,
            part="contentDetails",
            playlistId=playlist_id,
            maxResults=RECENT_VIDEOS,
        ).get("items", [])
        return [i["contentDetails"]["videoId"] for i in items]

    @staticmethod
    def _engagement_rate(videos: list[dict]) -> Decimal:
        views = interactions = 0
        for video in videos:
            stats = video.get("statistics", {})
            views += int(stats.get("viewCount", 0))
            interactions += int(stats.get("likeCount", 0)) + int(stats.get("commentCount", 0))
        if views == 0:
            return Decimal("0.00")
        rate = Decimal(interactions) / Decimal(views) * 100
        return rate.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def _token_request(self, form: dict) -> TokenSet:
        form = {
            **form,
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
        }
        response = self._send("POST", TOKEN_URL, data=form)
        self._raise_for_status(response)
        body = response.json()
        return TokenSet(
            access_token=body["access_token"],
            refresh_token=body.get("refresh_token"),
            expires_in=int(body.get("expires_in", 3600)),
        )

    def _api_get(self, resource: str, access_token: str, **params) -> dict:
        response = self._send(
            "GET",
            f"{API_URL}/{resource}",
            params=params,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        self._raise_for_status(response)
        return response.json()

    @staticmethod
    def _send(method: str, url: str, **kwargs) -> requests.Response:
        try:
            return requests.request(method, url, timeout=TIMEOUT_SECONDS, **kwargs)
        except (requests.Timeout, requests.ConnectionError) as exc:
            raise TransientApiError(str(exc)) from exc

    @staticmethod
    def _raise_for_status(response: requests.Response) -> None:
        status = response.status_code
        if status < 400:
            return
        reasons = _error_reasons(response)
        if status == 401 or "invalid_grant" in reasons:
            raise TokenRevoked(f"HTTP {status}")
        if status == 403 and reasons & _QUOTA_REASONS:
            raise QuotaExceeded(f"HTTP {status}")
        if status == 403 and reasons & _PERMISSION_REASONS:
            raise TokenRevoked(f"HTTP {status}")
        if status == 429 or status >= 500:
            raise TransientApiError(f"HTTP {status}")
        raise YouTubeError(f"HTTP {status}")
