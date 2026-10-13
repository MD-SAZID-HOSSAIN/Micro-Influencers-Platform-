from celery import shared_task

from .deliverable_stats import refresh_deliverable_stats


@shared_task
def sync_deliverable_stats() -> int:
    """Daily job: refresh view/like/comment counts of delivered YouTube videos."""
    return refresh_deliverable_stats()
