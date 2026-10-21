"""Who may publish, accept and apply: brands need a verified email AND a connected platform, creators a verified YouTube channel.

Everything else (logging in, browsing, editing a profile, saving drafts, shortlisting) stays open to
unverified accounts. The checks live here so the services and the API reply with the same error codes.
"""
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
        "Connect at least one social account (YouTube, Instagram, TikTok or Facebook) "
        "before publishing campaigns or accepting proposals."
    )


class CreatorYouTubeRequired(DomainError):
    status_code = 403
    default_code = "creator_youtube_required"
    default_detail = "Connect your YouTube channel before applying to campaigns."


def creator_is_verified(creator: User) -> bool:
    """A creator is verified only while a YouTube channel is connected (Verified stats)."""
    from apps.social.models import PlatformStats

    return PlatformStats.objects.filter(creator=creator, platform="youtube", is_verified=True).exists()


def brand_has_platform(brand: User) -> bool:
    """A brand has a connected platform when at least one of YouTube, Instagram, TikTok or Facebook is linked."""
    from apps.social.models import BrandSocialAccount

    return BrandSocialAccount.objects.filter(brand=brand).exists()


def require_verified_brand(brand: User) -> None:
    """The email is checked first, then the platform, so the brand is told what to do in order."""
    if not brand.email_verified:
        raise BrandEmailNotVerified()
    if not brand_has_platform(brand):
        raise BrandPlatformRequired()


def require_verified_creator(creator: User) -> None:
    if not creator_is_verified(creator):
        raise CreatorYouTubeRequired()
