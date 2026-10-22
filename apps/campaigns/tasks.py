import logging

from celery import shared_task
from django.utils import timezone

from . import services
from .models import Campaign

logger = logging.getLogger(__name__)


@shared_task
def close_expired_campaigns() -> int:
    """Close every Published campaign whose application deadline has passed.

    Returns how many were closed. Each closure notifies the brand exactly once, because
    only Published campaigns are picked up and closing is a locked, one-way transition.
    One campaign that cannot be closed is logged and skipped, so it never stops the others.
    """
    ids = list(
        Campaign.objects.filter(
            status=Campaign.Status.PUBLISHED, deadline__lte=timezone.now()
        ).values_list("id", flat=True)
    )
    closed = 0
    for campaign in Campaign.objects.filter(pk__in=ids):
        try:
            services.close_campaign(campaign, auto=True)
        except Exception:
            logger.exception("Could not close expired campaign %s; the others are still processed", campaign.pk)
        else:
            closed += 1
    return closed
