from typing import Callable

from django.db import transaction

from apps.accounts.models import Role, User
from apps.core.exceptions import Conflict
from apps.social.models import PlatformStats

from .models import BrandProfile, CreatorProfile, PortfolioItem

# The completion indicator is fixed at 8 equally weighted items.
COMPLETION_ITEMS = 8
PORTFOLIO_MAX_ITEMS = 10

COMPLETION_CHECKS: dict[str, Callable[[CreatorProfile], bool]] = {
    "photo": lambda p: bool(p.photo_url),
    "bio": lambda p: bool(p.bio),
    "niche": lambda p: bool(p.niche),
    "primary_platform": lambda p: bool(p.primary_platform),
    "location": lambda p: bool(p.city and p.country),
    "rate": lambda p: any(r is not None for r in (p.rate_post, p.rate_story, p.rate_video)),
    "primary_platform_stats": lambda p: bool(p.primary_platform)
    and PlatformStats.objects.filter(creator_id=p.user_id, platform=p.primary_platform).exists(),
    "portfolio": lambda p: PortfolioItem.objects.filter(creator_id=p.user_id).exists(),
}


def completion_percent(profile: CreatorProfile) -> int:
    """Share of the 8 profile items that are filled in, as an integer rounded half-up."""
    done = sum(1 for check in COMPLETION_CHECKS.values() if check(profile))
    return (100 * done + COMPLETION_ITEMS // 2) // COMPLETION_ITEMS


def get_or_create_profile(user: User) -> CreatorProfile | BrandProfile:
    """Return the user's profile row, creating it if the account predates the signal."""
    if user.role == Role.CREATOR:
        return CreatorProfile.objects.select_related("user").get_or_create(user=user)[0]
    if user.role == Role.BRAND:
        return BrandProfile.objects.select_related("user").get_or_create(user=user)[0]
    raise ValueError(f"Role {user.role!r} has no profile.")


class PortfolioFull(Conflict):
    default_code = "portfolio_full"
    default_detail = f"A portfolio can hold at most {PORTFOLIO_MAX_ITEMS} items. Remove one first."


def add_portfolio_item(
    *, creator: User, url: str, caption: str = "", source: str = PortfolioItem.Source.MANUAL
) -> PortfolioItem:
    """Add a portfolio link, enforcing the 10-item cap even under concurrent requests."""
    with transaction.atomic():
        # Lock the creator's profile row so concurrent adds are counted one at a time.
        get_or_create_profile(creator)
        CreatorProfile.objects.select_for_update().get(user=creator)
        if PortfolioItem.objects.filter(creator=creator).count() >= PORTFOLIO_MAX_ITEMS:
            raise PortfolioFull()
        return PortfolioItem.objects.create(creator=creator, url=url, caption=caption, source=source)
