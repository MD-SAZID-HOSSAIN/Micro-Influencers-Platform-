from celery import shared_task
from django.utils import timezone

from . import services
from .models import Campaign


@shared_task
def close_expired_campaigns() -> int:
    """Close every Published campaign whose application deadline has passed.

    Returns how many were processed. Each closure notifies the brand exactly once, because
    only Published campaigns are picked up and closing is a locked, one-way transition.
    """
    ids = list(
        Campaign.objects.filter(
            status=Campaign.Status.PUBLISHED, deadline__lte=timezone.now()
        ).values_list("id", flat=True)
    )
    for campaign in Campaign.objects.filter(pk__in=ids):
        services.close_campaign(campaign, auto=True)
    return len(ids)
