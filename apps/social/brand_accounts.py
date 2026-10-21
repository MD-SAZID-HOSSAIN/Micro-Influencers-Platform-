"""A brand's connected social accounts.

A brand is fully verified once its email is confirmed AND it has connected at least one platform. Any of YouTube,
Instagram, TikTok or Facebook counts:

- **YouTube** is connected with Google sign-in, the only real proof of ownership available. We read the channel link
  once and give the Google access back straight away, because a brand needs no ongoing sync.
- **Instagram, TikTok, Facebook** are a link the brand types. We check the link points at that platform, but nothing
  proves the brand owns the page (that would need Meta or TikTok approval), so it is stored as "added", not Verified.
"""
import logging
from urllib.parse import urlparse

from rest_framework.exceptions import ValidationError

from apps.accounts.models import User
from apps.core.exceptions import DomainError

from . import services
from .models import BrandSocialAccount
from .youtube_client import ChannelNotFound, YouTubeError

logger = logging.getLogger(__name__)

# The websites a typed link may point at, per platform.
TYPED_PLATFORM_HOSTS = {
    "instagram": ("instagram.com",),
    "tiktok": ("tiktok.com",),
    "facebook": ("facebook.com", "fb.com"),
}
PLATFORM_LABELS = {"instagram": "Instagram", "tiktok": "TikTok", "facebook": "Facebook"}
PLATFORM_EXAMPLES = {
    "instagram": "https://instagram.com/yourbrand",
    "tiktok": "https://www.tiktok.com/@yourbrand",
    "facebook": "https://facebook.com/yourbrand",
}


class GoogleSignInRequired(DomainError):
    status_code = 400
    default_code = "google_signin_required"
    default_detail = "YouTube is connected with Google sign-in. Use the Connect YouTube button instead of typing a link."


def _is_on_host(hostname: str, hosts: tuple[str, ...]) -> bool:
    return any(hostname == host or hostname.endswith("." + host) for host in hosts)


def connect_typed_platform(*, brand: User, platform: str, handle_url: str) -> BrandSocialAccount:
    """Save (or replace) the link a brand typed for Instagram, TikTok or Facebook. Never marked Verified."""
    if platform == "youtube":
        raise GoogleSignInRequired()
    hosts = TYPED_PLATFORM_HOSTS[platform]
    link = (handle_url or "").strip()
    parsed = urlparse(link)
    on_platform = (
        parsed.scheme in ("http", "https")
        and parsed.hostname is not None
        and _is_on_host(parsed.hostname.lower(), hosts)
        and parsed.path.strip("/") != ""
    )
    if not on_platform:
        raise ValidationError(
            {
                "handle_url": [
                    f"Enter the link to your {PLATFORM_LABELS[platform]} page, "
                    f"for example {PLATFORM_EXAMPLES[platform]}."
                ]
            }
        )
    account, _ = BrandSocialAccount.objects.update_or_create(
        brand=brand, platform=platform, defaults={"handle_url": link, "is_verified": False}
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
        brand=brand, platform="youtube", defaults={"handle_url": link, "is_verified": True}
    )
    return account


def remove_platform(*, brand: User, platform: str) -> None:
    """Disconnect a platform. Removing the last one means the brand is no longer fully verified."""
    BrandSocialAccount.objects.filter(brand=brand, platform=platform).delete()
