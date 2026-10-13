import logging
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound

from apps.accounts.models import User
from apps.core.exceptions import Conflict, DomainError
from apps.notifications.models import Kind
from apps.notifications.services import notify

from .crypto import decrypt, encrypt
from .models import PlatformStats, YouTubeConnection
from .youtube_client import ChannelNotFound, ChannelSnapshot, TokenRevoked, YouTubeClient

logger = logging.getLogger(__name__)

ACCESS_TOKEN_MARGIN = timedelta(seconds=60)


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
    if existing is not None and existing.is_verified:
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
        transaction.on_commit(lambda: tasks.sync_connection_task.delay(connection_id))
