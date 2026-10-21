"""Thin client for Google OAuth and the YouTube Data API (read-only)."""
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from urllib.parse import urlencode

import re
from urllib.parse import parse_qs, urlparse

import requests
from django.conf import settings

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
REVOKE_URL = "https://oauth2.googleapis.com/revoke"
API_URL = "https://www.googleapis.com/youtube/v3"
SCOPE = "https://www.googleapis.com/auth/youtube.readonly"
TIMEOUT_SECONDS = 10
RECENT_VIDEOS = 10
# engagement_rate is stored as a DecimalField(max_digits=5, decimal_places=2).
MAX_ENGAGEMENT_RATE = Decimal("999.99")

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


class SubscribersHidden(YouTubeError):
    """The channel hides its subscriber count, so its reach cannot be verified."""


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


@dataclass(frozen=True)
class VideoStats:
    """Public counters for one video. ``None`` means the owner hides that counter."""

    views: int | None
    likes: int | None
    comments: int | None


_VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
_PATH_ID = re.compile(r"^/(?:shorts|embed|live|v)/([^/?#]+)")


def youtube_video_id(url: str) -> str | None:
    """The video id in a YouTube link (watch, youtu.be, shorts, embed, live), or None."""
    try:
        parsed = urlparse(url or "")
    except ValueError:
        return None
    host = (parsed.hostname or "").lower()
    for prefix in ("www.", "m."):
        host = host.removeprefix(prefix)
    if host == "youtu.be":
        candidate = parsed.path.lstrip("/").split("/")[0]
    elif host in ("youtube.com", "music.youtube.com"):
        if parsed.path == "/watch":
            candidate = parse_qs(parsed.query).get("v", [""])[0]
        else:
            match = _PATH_ID.match(parsed.path)
            candidate = match.group(1) if match else ""
    else:
        return None
    return candidate if _VIDEO_ID.match(candidate) else None


def _count(value) -> int | None:
    return int(value) if value is not None else None


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

    def revoke_token(self, token: str) -> None:
        """Tell Google to forget a grant, so the app disappears from the creator's Google permissions.

        A token Google already considers invalid (revoked earlier, or expired) counts as done.
        """
        response = self._send("POST", REVOKE_URL, data={"token": token})
        if response.status_code == 400 and "invalid_token" in _error_reasons(response):
            return
        self._raise_for_status(response)

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
        if channel.get("statistics", {}).get("hiddenSubscriberCount") is True:
            # Google reports no usable number; storing 0 would show a "Verified" creator with no audience.
            raise SubscribersHidden()

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

    def fetch_channel_link(self, access_token: str) -> str:
        """The link to the signed-in account's channel, and nothing else (used to prove a brand owns one).

        Unlike ``fetch_channel`` it ignores subscriber counts and videos, so a channel that hides its audience
        still works.
        """
        channels = self._api_get("channels", access_token, part="snippet", mine="true").get("items", [])
        if not channels:
            raise ChannelNotFound()
        channel = channels[0]
        custom_url = channel.get("snippet", {}).get("customUrl")
        if custom_url:
            return f"https://www.youtube.com/{custom_url}"
        return f"https://www.youtube.com/channel/{channel['id']}"

    def fetch_video_stats(self, video_ids: list[str], api_key: str) -> dict[str, VideoStats]:
        """Public statistics for up to 50 videos, using the server's API key (no creator login needed).

        Videos Google does not return (deleted, private) are simply absent from the result.
        """
        if not video_ids:
            return {}
        response = self._send(
            "GET",
            f"{API_URL}/videos",
            params={"part": "statistics", "id": ",".join(video_ids), "key": api_key},
        )
        self._raise_for_status(response)
        found = {}
        for item in response.json().get("items", []):
            stats = item.get("statistics", {})
            found[item["id"]] = VideoStats(
                views=_count(stats.get("viewCount")),
                likes=_count(stats.get("likeCount")),
                comments=_count(stats.get("commentCount")),
            )
        return found

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
        # Likes and comments can briefly outnumber views (new videos, delayed view counts). Without a
        # cap, a rate of 1000% or more does not fit the database column and the whole sync fails.
        return min(rate.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), MAX_ENGAGEMENT_RATE)

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
            # Never pass the library's own message on: it contains the full request URL, and for
            # the video-statistics call that URL carries the server's API key. `from None` also drops
            # the chained original, which would otherwise print the same URL in a traceback.
            raise TransientApiError(f"{type(exc).__name__} while calling Google") from None

    @staticmethod
    def _raise_for_status(response: requests.Response) -> None:
        status = response.status_code
        if status < 400:
            return
        reasons = _error_reasons(response)
        # Google's own reason codes (invalid_grant, quotaExceeded, ...) make a log line useful. They
        # are short fixed words, so unlike the request URL they never contain a key or token.
        why = f"HTTP {status}" + (f" ({', '.join(sorted(r for r in reasons if r))})" if reasons - {""} else "")
        if status == 401 or "invalid_grant" in reasons:
            raise TokenRevoked(why)
        if status == 403 and reasons & _QUOTA_REASONS:
            raise QuotaExceeded(why)
        if status == 403 and reasons & _PERMISSION_REASONS:
            raise TokenRevoked(why)
        if status == 429 or status >= 500:
            raise TransientApiError(why)
        raise YouTubeError(why)
