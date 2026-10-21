from django.conf import settings
from django.db import migrations

PLACEHOLDER = "direct-token"  # what the removed direct-connect endpoints stored instead of a real Google token


def _is_placeholder(stored: str) -> bool:
    if (stored or "").startswith(PLACEHOLDER):  # plain fallback used when no encryption key was configured
        return True
    try:
        from apps.social.crypto import decrypt

        return decrypt(stored) == PLACEHOLDER
    except Exception:  # noqa: BLE001 - a real token that cannot be read is not a placeholder
        return False


def unverify_unproven_stats(apps, schema_editor):
    """Verified now means: proven by Google sign-in AND at least MIN_CREATOR_FOLLOWERS subscribers.

    1. Only YouTube can be proven, so a Verified flag on Instagram, TikTok or Facebook came from the removed
       direct-connect endpoints and is taken away.
    2. A YouTube channel linked by handle (placeholder tokens, never a Google sign-in) is unverified and unlinked.
    3. A Verified channel below the minimum is unverified. It stays connected and becomes Verified again if it grows.

    Numbers are never changed, and stats without any connection (the demo data) are left alone.
    """
    PlatformStats = apps.get_model("social", "PlatformStats")
    YouTubeConnection = apps.get_model("social", "YouTubeConnection")

    PlatformStats.objects.exclude(platform="youtube").filter(is_verified=True).update(is_verified=False)

    unproven = [c.creator_id for c in YouTubeConnection.objects.all() if _is_placeholder(c.access_token_enc)]
    if unproven:
        PlatformStats.objects.filter(platform="youtube", creator_id__in=unproven).update(is_verified=False)
        YouTubeConnection.objects.filter(creator_id__in=unproven).delete()

    PlatformStats.objects.filter(
        platform="youtube", is_verified=True, followers__lt=settings.MIN_CREATOR_FOLLOWERS
    ).update(is_verified=False)


class Migration(migrations.Migration):
    dependencies = [("social", "0003_brandsocialaccount")]

    operations = [migrations.RunPython(unverify_unproven_stats, migrations.RunPython.noop)]
