from celery import shared_task

from . import services
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


@shared_task
def sync_all_youtube() -> int:
    """Daily job: queue one sync per healthy connection, so one failure cannot stop the rest."""
    ids = list(
        YouTubeConnection.objects.filter(status=YouTubeConnection.Status.CONNECTED).values_list(
            "id", flat=True
        )
    )
    for connection_id in ids:
        sync_connection_task.delay(connection_id)
    return len(ids)
