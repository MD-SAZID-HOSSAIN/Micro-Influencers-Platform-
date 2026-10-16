import logging
import secrets
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core import signing
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound

from apps.accounts.models import User
from apps.core.exceptions import Conflict, DomainError, ServiceUnavailable
from apps.core.queueing import enqueue
from apps.core.throttling import CACHE_ERRORS
from apps.notifications.models import Kind
from apps.notifications.services import notify

from .crypto import decrypt, encrypt
from .models import PlatformStats, YouTubeConnection
from .youtube_client import (
    ChannelNotFound,
    ChannelSnapshot,
    TokenRevoked,
    YouTubeClient,
    YouTubeError,
)

logger = logging.getLogger(__name__)

ACCESS_TOKEN_MARGIN = timedelta(seconds=60)
OAUTH_STATE_SALT = "youtube-oauth"
OAUTH_STATE_MAX_AGE = 600
OAUTH_NONCE_KEY = "youtube-oauth-nonce:{}"


class StatsVerified(Conflict):
    default_code = "stats_verified"
    default_detail = "These stats come from a connected account and cannot be edited manually."


def set_manual_stats(
    *,
    creator: User,
    platform: str,
    followers: int,
    engagement_rate: Decimal,
    handle_url: str | None = None,
) -> PlatformStats:
    """Create or update Unverified stats entered by hand; refuses to overwrite Verified ones."""
    existing = PlatformStats.objects.filter(creator=creator, platform=platform).first()
    if existing is not None and existing.is_verified and platform == "youtube":
        raise StatsVerified()
    stats, _ = PlatformStats.objects.update_or_create(
        creator=creator,
        platform=platform,
        defaults={
            "followers": followers,
            "engagement_rate": engagement_rate,
            "handle_url": handle_url,
            "is_verified": False,
            "is_outdated": False,
            "last_synced_at": timezone.now(),
        },
    )
    return stats


class RefreshCooldown(DomainError):
    status_code = 429
    default_code = "refresh_cooldown"
    default_detail = "You refreshed recently. Please try again in a few minutes."


class ReconnectRequired(Conflict):
    default_code = "reconnect_required"
    default_detail = "Your YouTube connection has expired. Please reconnect your account."


def get_youtube_client() -> YouTubeClient:
    return YouTubeClient()


def _usable_access_token(connection: YouTubeConnection, client) -> str:
    """Return a valid access token, refreshing (and storing the result) when it is close to expiry."""
    if connection.access_expires_at > timezone.now() + ACCESS_TOKEN_MARGIN:
        return decrypt(connection.access_token_enc)
    tokens = client.refresh_access_token(decrypt(connection.refresh_token_enc))
    connection.access_token_enc = encrypt(tokens.access_token)
    connection.access_expires_at = timezone.now() + timedelta(seconds=tokens.expires_in)
    fields = ["access_token_enc", "access_expires_at"]
    if tokens.refresh_token:
        connection.refresh_token_enc = encrypt(tokens.refresh_token)
        fields.append("refresh_token_enc")
    connection.save(update_fields=fields)
    return tokens.access_token


def apply_snapshot(connection: YouTubeConnection, snapshot: ChannelSnapshot) -> PlatformStats:
    """Store a fresh channel snapshot as the creator's Verified YouTube stats."""
    stats, _ = PlatformStats.objects.update_or_create(
        creator_id=connection.creator_id,
        platform="youtube",
        defaults={
            "handle_url": snapshot.handle_url,
            "followers": snapshot.subscribers,
            "engagement_rate": snapshot.engagement_rate,
            "is_verified": True,
            "is_outdated": False,
            "last_synced_at": timezone.now(),
        },
    )
    connection.recent_content = snapshot.recent_content
    connection.last_error = ""
    connection.save(update_fields=["recent_content", "last_error"])
    return stats


def _mark_needs_reconnect(connection: YouTubeConnection) -> None:
    """Flag a dead connection once: keep the last stats (outdated) and tell the creator."""
    with transaction.atomic():
        locked = YouTubeConnection.objects.select_for_update().filter(pk=connection.pk).first()
        if locked is None or locked.status == YouTubeConnection.Status.NEEDS_RECONNECT:
            return
        locked.status = YouTubeConnection.Status.NEEDS_RECONNECT
        locked.last_error = "token_revoked"
        locked.save(update_fields=["status", "last_error"])
        PlatformStats.objects.filter(creator_id=locked.creator_id, platform="youtube").update(
            is_outdated=True
        )
        notify(
            locked.creator,
            Kind.ACCOUNT_RECONNECT,
            "Your YouTube connection has expired. Please reconnect to keep your stats up to date.",
            platform="youtube",
        )


def sync_connection(connection: YouTubeConnection) -> None:
    """Pull fresh stats for one connection.

    A revoked or expired grant flags the connection for reconnecting (once) and keeps the
    last known stats. Transient errors propagate so the Celery task can retry them.
    """
    if connection.status != YouTubeConnection.Status.CONNECTED:
        return
    client = get_youtube_client()
    try:
        access_token = _usable_access_token(connection, client)
        snapshot = client.fetch_channel(access_token)
    except TokenRevoked:
        _mark_needs_reconnect(connection)
        return
    except ChannelNotFound:
        PlatformStats.objects.filter(creator_id=connection.creator_id, platform="youtube").update(
            is_outdated=True
        )
        connection.last_error = "no_channel"
        connection.save(update_fields=["last_error"])
        return
    apply_snapshot(connection, snapshot)


def request_manual_refresh(user: User) -> None:
    """Schedule an immediate background sync, at most once per cooldown period."""
    from . import tasks

    with transaction.atomic():
        connection = YouTubeConnection.objects.select_for_update().filter(creator=user).first()
        if connection is None:
            raise NotFound("No YouTube account is connected.")
        if connection.status != YouTubeConnection.Status.CONNECTED:
            raise ReconnectRequired()
        now = timezone.now()
        cooldown = timedelta(seconds=settings.YOUTUBE_REFRESH_COOLDOWN_SECONDS)
        last = connection.last_manual_refresh_at
        if last is not None and now - last < cooldown:
            raise RefreshCooldown()
        connection.last_manual_refresh_at = now
        connection.save(update_fields=["last_manual_refresh_at"])
        connection_id = connection.id
        transaction.on_commit(lambda: enqueue(tasks.sync_connection_task, connection_id))


_CONNECT_MESSAGES = {
    "invalid_state": "This connection request is invalid, expired or belongs to someone else. Please start again.",
    "exchange_failed": "Google did not accept the sign-in. Please try connecting again.",
    "no_refresh_token": (
        "Google did not allow us to keep the connection. Please connect again and accept every requested permission."
    ),
}


class ConnectError(DomainError):
    """The YouTube connection could not be completed. ``reason`` doubles as the API error code."""

    status_code = 400

    def __init__(self, reason: str):
        super().__init__(detail=_CONNECT_MESSAGES.get(reason, "The connection could not be completed."), code=reason)
        self.reason = reason


def start_connect(user: User) -> str:
    """Return the Google consent URL carrying a signed, single-use ``state`` (CSRF defence)."""
    nonce = secrets.token_urlsafe(16)
    try:
        cache.set(OAUTH_NONCE_KEY.format(nonce), True, OAUTH_STATE_MAX_AGE)
    except CACHE_ERRORS:
        # The one-time nonce lives in the shared cache; without it the flow cannot be made safe.
        raise ServiceUnavailable()
    state = signing.dumps({"uid": user.id, "nonce": nonce}, salt=OAUTH_STATE_SALT)
    return get_youtube_client().build_auth_url(state)


def read_state(state: str) -> dict:
    """Check a ``state`` value's signature and age. Touches neither the database nor the cache."""
    try:
        payload = signing.loads(state, salt=OAUTH_STATE_SALT, max_age=OAUTH_STATE_MAX_AGE)
        payload["nonce"], payload["uid"]  # both must be present
    except (signing.BadSignature, KeyError, TypeError):
        raise ConnectError("invalid_state")
    return payload


def complete_connect(*, user: User, state: str, code: str) -> YouTubeConnection:
    """Finish the OAuth flow for the logged-in creator: store encrypted tokens, queue the first sync.

    The ``state`` must have been issued to THIS creator. Google's redirect carries no login, so
    without this check one creator could send another person their own connect link, and the
    person's channel would end up shown as Verified on the first creator's profile.
    """
    from . import tasks

    payload = read_state(state)
    if payload["uid"] != user.id:
        raise ConnectError("invalid_state")  # checked before the nonce is claimed: a wrong person cannot burn it
    # cache.delete is the atomic "claim": only the first completion finds the nonce.
    try:
        claimed = cache.delete(OAUTH_NONCE_KEY.format(payload["nonce"]))
    except CACHE_ERRORS:
        raise ServiceUnavailable()  # nothing was used up: Google's code is untouched, so the user can retry
    if not claimed:
        raise ConnectError("invalid_state")

    try:
        tokens = get_youtube_client().exchange_code(code)
    except YouTubeError:
        raise ConnectError("exchange_failed")

    existing = YouTubeConnection.objects.filter(creator=user).first()
    if tokens.refresh_token:
        refresh_token = tokens.refresh_token
    elif existing is not None:
        refresh_token = decrypt(existing.refresh_token_enc)
    else:
        raise ConnectError("no_refresh_token")

    connection, _ = YouTubeConnection.objects.update_or_create(
        creator=user,
        defaults={
            "access_token_enc": encrypt(tokens.access_token),
            "refresh_token_enc": encrypt(refresh_token),
            "access_expires_at": timezone.now() + timedelta(seconds=tokens.expires_in),
            "status": YouTubeConnection.Status.CONNECTED,
            "last_error": "",
        },
    )
    # The link is already saved. If the queue is down, the first sync simply waits for the next daily run.
    transaction.on_commit(lambda: enqueue(tasks.sync_connection_task, connection.id))
    return connection


def disconnect(user: User) -> None:
    """Delete the stored tokens; the last stats stay but are no longer Verified."""
    with transaction.atomic():
        YouTubeConnection.objects.filter(creator=user).delete()
        PlatformStats.objects.filter(creator=user, platform="youtube").update(is_verified=False)


def connection_status(user: User) -> dict:
    connection = YouTubeConnection.objects.filter(creator=user).first()
    stats = PlatformStats.objects.filter(creator=user, platform="youtube").first()
    return {
        "connected": connection is not None,
        "status": connection.status if connection else None,
        "needs_reconnect": bool(
            connection and connection.status == YouTubeConnection.Status.NEEDS_RECONNECT
        ),
        "connected_at": connection.connected_at if connection else None,
        "last_synced_at": stats.last_synced_at if stats else None,
        "is_outdated": bool(stats and stats.is_outdated),
        "last_error": (connection.last_error or None) if connection else None,
    }
