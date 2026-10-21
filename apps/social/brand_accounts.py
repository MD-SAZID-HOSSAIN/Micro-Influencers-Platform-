"""A brand's connected social accounts.

A brand is fully verified once its email is confirmed AND it has connected at least one platform. Any of YouTube,
Instagram, TikTok or Facebook counts:

- **YouTube** is connected with Google sign-in, the only real proof of ownership available. We read the channel link
  once and give the Google access back straight away, because a brand needs no ongoing sync.
- **Instagram, TikTok, Facebook** are a link the brand types. We check the link points at that platform, but nothing
  proves the brand owns the page (that would need Meta or TikTok approval), so an admin opens it and approves or rejects
  it. Until then it is "pending" and does not count.
"""
import logging

from apps.accounts.models import User
from apps.core.exceptions import DomainError

from . import services
from .links import clean_profile_link
from .models import BrandSocialAccount
from .youtube_client import ChannelNotFound, YouTubeError

logger = logging.getLogger(__name__)


class GoogleSignInRequired(DomainError):
    status_code = 400
    default_code = "google_signin_required"
    default_detail = "YouTube is connected with Google sign-in. Use the Connect YouTube button instead of typing a link."


def connect_typed_platform(*, brand: User, platform: str, handle_url: str) -> BrandSocialAccount:
    """Save (or replace) the link a brand typed for Instagram, TikTok or Facebook. It waits for an admin."""
    if platform == "youtube":
        raise GoogleSignInRequired()
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


def complete_brand_youtube(*, brand: User, state: str, code: str) -> BrandSocialAccount:
    """Finish the Google sign-in for a brand: remember the channel link as Verified, then give the access back.

    The ``state`` must have been issued to THIS brand (the same check creators use).
    """
    services.claim_state(brand, state)
    client = services.get_youtube_client()
    tokens = None
    try:
        tokens = client.exchange_code(code)
        link = client.fetch_channel_link(tokens.access_token)
    except ChannelNotFound:
        raise services.ConnectError("no_channel")
    except YouTubeError as exc:
        logger.warning("YouTube sign-in could not be completed for brand %s: %s", brand.id, exc)
        raise services.ConnectError("exchange_failed")
    finally:
        if tokens is not None:  # a brand needs no ongoing access, so none is kept: give it back in the background
            services.schedule_token_revoke(tokens.refresh_token or tokens.access_token, brand.id)
    account, _ = BrandSocialAccount.objects.update_or_create(
        brand=brand,
        platform="youtube",
        defaults={"handle_url": link, "is_verified": True, "review_status": BrandSocialAccount.Review.APPROVED, "review_note": ""},
    )
    return account


def remove_platform(*, brand: User, platform: str) -> None:
    """Disconnect a platform. Removing the last one means the brand is no longer fully verified."""
    BrandSocialAccount.objects.filter(brand=brand, platform=platform).delete()
