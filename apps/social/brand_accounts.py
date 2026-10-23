"""A brand's connected social accounts.

A brand is fully verified once its email is confirmed AND an admin has approved at least one of its Instagram, TikTok
or Facebook links. YouTube does not verify a brand.

The link is typed by the brand. We check it points at that platform, but nothing proves the brand owns the page (that
would need Meta or TikTok approval), so an admin opens it and approves or rejects it. Until then it is "pending" and
does not count.
"""
from apps.accounts.models import User
from apps.core.exceptions import DomainError

from .links import clean_profile_link
from .models import BrandSocialAccount


class YouTubeNotForBrands(DomainError):
    status_code = 400
    default_code = "youtube_not_for_brands"
    default_detail = "YouTube does not verify a brand. Add your official Instagram, TikTok or Facebook link instead."


def connect_typed_platform(*, brand: User, platform: str, handle_url: str) -> BrandSocialAccount:
    """Save (or replace) the link a brand typed for Instagram, TikTok or Facebook. It waits for an admin."""
    if platform == "youtube":
        raise YouTubeNotForBrands()
    link = clean_profile_link(platform, handle_url)
    account, _ = BrandSocialAccount.objects.update_or_create(
        brand=brand,
        platform=platform,
        defaults={
            "handle_url": link,
            "is_verified": False,
            "review_status": BrandSocialAccount.Review.PENDING,
            "review_note": "",
        },
    )
    return account


def remove_platform(*, brand: User, platform: str) -> None:
    """Disconnect a platform. Removing the last approved one means the brand is no longer fully verified."""
    BrandSocialAccount.objects.filter(brand=brand, platform=platform).delete()
