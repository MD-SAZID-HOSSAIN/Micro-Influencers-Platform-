"""The link a person types for Instagram, TikTok or Facebook: shared by brands and creators."""
from urllib.parse import urlparse

from rest_framework.exceptions import ValidationError

# The websites a typed link may point at, per platform.
TYPED_PLATFORM_HOSTS = {
    "instagram": ("instagram.com",),
    "tiktok": ("tiktok.com",),
    "facebook": ("facebook.com", "fb.com"),
}
PLATFORM_LABELS = {"instagram": "Instagram", "tiktok": "TikTok", "facebook": "Facebook"}
PLATFORM_EXAMPLES = {
    "instagram": "https://instagram.com/yourname",
    "tiktok": "https://www.tiktok.com/@yourname",
    "facebook": "https://facebook.com/yourpage",
}


def _is_on_host(hostname: str, hosts: tuple[str, ...]) -> bool:
    return any(hostname == host or hostname.endswith("." + host) for host in hosts)


def clean_profile_link(platform: str, handle_url: str | None) -> str:
    """Return the trimmed link, or raise a ``handle_url`` error if it is not a page on that platform's website."""
    link = (handle_url or "").strip()
    parsed = urlparse(link)
    on_platform = (
        parsed.scheme in ("http", "https")
        and parsed.hostname is not None
        and _is_on_host(parsed.hostname.lower(), TYPED_PLATFORM_HOSTS[platform])
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
    return link
