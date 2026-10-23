"""Content performance (FR-23, second half): views, likes and comments per deliverable.

Google is only ever called by the daily background sync. The brand's report reads the saved
snapshot, so opening it never waits on (or fails because of) a third-party API.
"""
import logging
from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.db.models import F
from django.utils import timezone

from apps.campaigns.models import Campaign
from apps.core.choices import Platform
from apps.social import services as social_services
from apps.social.youtube_client import YouTubeError, youtube_video_id

from .models import Deliverable, Proposal

logger = logging.getLogger(__name__)

BATCH_SIZE = 50  # the most video ids YouTube's API accepts in one call
NOT_AVAILABLE = "not_available"


def refresh_deliverable_stats() -> int:
    """Fetch current statistics for every YouTube deliverable of an accepted proposal.

    A video's numbers are stored only when the video belongs to the channel the creator connected. Anyone else's
    video (or a creator whose channel is not known yet) gets no numbers, and any stored earlier are cleared.

    Returns how many deliverables were updated. A failed batch keeps its previous numbers and the
    other batches still run; the next daily run tries again. With no ``YOUTUBE_API_KEY`` it does nothing.
    """
    api_key = settings.YOUTUBE_API_KEY
    if not api_key:
        return 0

    by_video: dict[str, list[Deliverable]] = defaultdict(list)
    for deliverable in (
        Deliverable.objects.filter(platform=Platform.YOUTUBE, proposal__status=Proposal.Status.ACCEPTED)
        .annotate(owner_channel=F("proposal__creator__youtube_connection__channel_id"))
        .only("id", "post_url", "views_count", "likes_count", "comments_count", "stats_synced_at")
    ):
        if video_id := youtube_video_id(deliverable.post_url):
            by_video[video_id].append(deliverable)

    client = social_services.get_youtube_client()
    video_ids = list(by_video)
    changed: list[Deliverable] = []
    now = timezone.now()
    for start in range(0, len(video_ids), BATCH_SIZE):
        batch = video_ids[start : start + BATCH_SIZE]
        try:
            stats = client.fetch_video_stats(batch, api_key)
        except YouTubeError as exc:
            logger.warning("Could not fetch statistics for %d videos: %s", len(batch), exc)
            continue
        for video_id, video in stats.items():
            for deliverable in by_video[video_id]:
                if not video.channel_id or video.channel_id != (deliverable.owner_channel or ""):
                    # Not the creator's own video: show nothing rather than someone else's numbers.
                    if deliverable.stats_synced_at is not None:
                        deliverable.views_count = deliverable.likes_count = deliverable.comments_count = None
                        deliverable.stats_synced_at = None
                        changed.append(deliverable)
                    continue
                deliverable.views_count = video.views
                deliverable.likes_count = video.likes
                deliverable.comments_count = video.comments
                deliverable.stats_synced_at = now
                changed.append(deliverable)

    Deliverable.objects.bulk_update(
        changed, ["views_count", "likes_count", "comments_count", "stats_synced_at"]
    )
    return len(changed)


def _engagement_rate(deliverable: Deliverable):
    """(likes + comments) / views as a percentage; unavailable unless all three numbers are known."""
    views, likes, comments = deliverable.views_count, deliverable.likes_count, deliverable.comments_count
    if not views or likes is None or comments is None:
        return NOT_AVAILABLE
    rate = Decimal(likes + comments) / Decimal(views) * 100
    return rate.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def content_performance(campaign: Campaign) -> list[dict]:
    """One row per deliverable of the campaign's accepted creators, from the saved snapshot."""
    deliverables = (
        Deliverable.objects.filter(proposal__campaign=campaign, proposal__status=Proposal.Status.ACCEPTED)
        .select_related("proposal__creator")
        .order_by("proposal__created_at", "proposal_id", "created_at", "id")
    )
    rows = []
    for deliverable in deliverables:
        synced = deliverable.platform == Platform.YOUTUBE and deliverable.stats_synced_at is not None

        def number(value):
            return value if synced and value is not None else NOT_AVAILABLE

        creator = deliverable.proposal.creator
        rows.append(
            {
                "deliverable_id": deliverable.id,
                "proposal_id": deliverable.proposal_id,
                "creator": {"id": creator.id, "name": creator.full_name},
                "platform": deliverable.platform,
                "post_url": deliverable.post_url,
                "views": number(deliverable.views_count),
                "likes": number(deliverable.likes_count),
                "comments": number(deliverable.comments_count),
                "engagement_rate": _engagement_rate(deliverable) if synced else NOT_AVAILABLE,
                "synced_at": deliverable.stats_synced_at if synced else None,
            }
        )
    return rows
