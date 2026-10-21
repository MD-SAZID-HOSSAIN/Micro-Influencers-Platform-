"""Who may publish, accept and apply.

- A brand needs a confirmed email AND one verified platform: a YouTube channel proven by Google sign-in, or an
  Instagram, TikTok or Facebook link that an admin approved.
- A creator needs a confirmed email AND a YouTube channel proven by Google sign-in with enough subscribers.

Everything else (logging in, browsing, editing a profile, saving drafts, shortlisting) stays open to
unverified accounts. The checks live here so the services and the API reply with the same error codes.
"""
from django.conf import settings

from apps.core.exceptions import DomainError

from .models import User


class BrandEmailNotVerified(DomainError):
    status_code = 403
    default_code = "brand_email_unverified"
    default_detail = "Verify your email address before publishing campaigns or accepting proposals."


class BrandPlatformRequired(DomainError):
    status_code = 403
    default_code = "brand_platform_required"
    default_detail = (
        "Connect YouTube, or add your Instagram, TikTok or Facebook link and wait for an admin to approve it, "
        "before publishing campaigns or accepting proposals."
    )


class CreatorEmailNotVerified(DomainError):
    status_code = 403
    default_code = "creator_email_unverified"
    default_detail = "Verify your email address before applying to campaigns."


class CreatorYouTubeRequired(DomainError):
    status_code = 403
    default_code = "creator_youtube_required"
    default_detail = "Connect your YouTube channel before applying to campaigns."


class CreatorFollowersTooLow(DomainError):
    """A connected channel with fewer subscribers than MIN_CREATOR_FOLLOWERS. The message gives both numbers."""

    status_code = 403
    default_code = "creator_followers_too_low"

    def __init__(self, followers: int, minimum: int):
        super().__init__(
            detail=(
                f"Your YouTube channel has {followers:,} subscribers. "
                f"You need at least {minimum:,} to be Verified and apply to campaigns."
            )
        )


def creator_is_verified(creator: User) -> bool:
    """Verified: a confirmed email AND YouTube stats proven by Google sign-in with at least MIN_CREATOR_FOLLOWERS subscribers."""
    from apps.social.models import PlatformStats

    return creator.email_verified and PlatformStats.objects.filter(
        creator=creator,
        platform="youtube",
        is_verified=True,
        followers__gte=settings.MIN_CREATOR_FOLLOWERS,
    ).exists()


def brand_has_platform(brand: User) -> bool:
    """A brand has a verified platform: YouTube proven by Google, or a typed link an admin approved."""
    from apps.social.models import BrandSocialAccount

    return BrandSocialAccount.objects.filter(brand=brand, is_verified=True).exists()


def brand_platform_status(brand: User) -> str:
    """"verified", "pending" (a typed link is waiting for an admin) or "none" (nothing, or only rejected links)."""
    from apps.social.models import BrandSocialAccount

    rows = list(BrandSocialAccount.objects.filter(brand=brand).values_list("is_verified", "review_status"))
    if any(verified for verified, _ in rows):
        return "verified"
    if any(status == "pending" for _, status in rows):
        return "pending"
    return "none"


def require_verified_brand(brand: User) -> None:
    """The email is checked first, then the platform, so the brand is told what to do in order."""
    if not brand.email_verified:
        raise BrandEmailNotVerified()
    if not brand_has_platform(brand):
        raise BrandPlatformRequired()


def require_verified_creator(creator: User) -> None:
    """Allow a Verified creator. Otherwise say why: no YouTube, or a channel that is connected but too small.

    The count is checked here as well as when stats are stored, so raising the minimum takes effect at once and
    not only at the next sync.
    """
    if not creator.email_verified:
        raise CreatorEmailNotVerified()  # the email is checked first, so the creator is told what to do in order
    if creator_is_verified(creator):
        return
    from apps.social.models import PlatformStats, YouTubeConnection

    minimum = settings.MIN_CREATOR_FOLLOWERS
    stats = PlatformStats.objects.filter(creator=creator, platform="youtube").first()
    # A channel counts as connected when Google sign-in proved it (a connection, or Verified stats).
    proven = stats is not None and (stats.is_verified or YouTubeConnection.objects.filter(creator=creator).exists())
    if proven and stats.followers < minimum:
        raise CreatorFollowersTooLow(stats.followers, minimum)
    raise CreatorYouTubeRequired()
