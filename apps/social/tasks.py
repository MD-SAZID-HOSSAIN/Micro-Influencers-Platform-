import logging

from celery import shared_task
from django.conf import settings

from . import services
from .crypto import decrypt
from .models import YouTubeConnection
from .youtube_client import TransientApiError


@shared_task(
    autoretry_for=(TransientApiError,),
    retry_backoff=True,
    retry_backoff_max=3600,
    retry_jitter=True,
    max_retries=5,
)
def sync_connection_task(connection_id: int) -> None:
    """Sync one creator's YouTube stats; transient Google errors are retried with backoff."""
    connection = YouTubeConnection.objects.filter(pk=connection_id).first()
    if connection is None:  # disconnected between scheduling and running
        return
    services.sync_connection(connection)


logger = logging.getLogger(__name__)


@shared_task
def revoke_token_task(encrypted_token: str, user_id: int) -> None:
    """Give a Google grant back at Google, away from the request that asked for it. Never raises."""
    try:
        token = decrypt(encrypted_token)
    except Exception:  # noqa: BLE001 - an unreadable token cannot be revoked; there is nothing to retry
        logger.warning("A queued YouTube revoke for user %s had an unreadable token and was dropped", user_id)
        return
    services.revoke_token_quietly(token, user_id)


@shared_task
def sync_all_youtube() -> int:
    """Daily job: queue one sync per healthy connection, so one failure cannot stop the rest.

    The syncs are started evenly over ``YOUTUBE_SYNC_SPREAD_SECONDS`` instead of all at once, so
    thousands of creators do not hit Google in the same few seconds (which would trigger rate limits
    and make every retry land together too).
    """
    ids = list(
        YouTubeConnection.objects.filter(status=YouTubeConnection.Status.CONNECTED)
        .order_by("id")
        .values_list("id", flat=True)
    )
    spread = settings.YOUTUBE_SYNC_SPREAD_SECONDS
    for index, connection_id in enumerate(ids):
        sync_connection_task.apply_async(args=[connection_id], countdown=index * spread // len(ids))
    return len(ids)
