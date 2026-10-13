from decimal import Decimal

from django.utils import timezone

from apps.accounts.models import User
from apps.core.exceptions import Conflict

from .models import PlatformStats


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
