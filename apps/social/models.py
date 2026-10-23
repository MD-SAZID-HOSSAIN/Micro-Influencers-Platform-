from django.conf import settings
from django.db import models

from apps.core.choices import Platform


class PlatformStats(models.Model):
    """A creator's audience numbers on one platform.

    YouTube is Verified by Google sign-in. Instagram, TikTok and Facebook are typed by the creator, wait for an
    admin (``review_status`` "pending") and are Verified only once the admin approves them. Until then they are
    visible only to the creator, never on the public profile.
    """

    class Review(models.TextChoices):
        PENDING = "pending", "Waiting for an admin"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="platform_stats"
    )
    platform = models.CharField(max_length=20, choices=Platform.choices)
    handle_url = models.URLField(max_length=500, null=True, blank=True)
    followers = models.PositiveIntegerField()
    engagement_rate = models.DecimalField(max_digits=5, decimal_places=2)
    is_verified = models.BooleanField(default=False)
    review_status = models.CharField(max_length=10, choices=Review.choices, default=Review.APPROVED)
    review_note = models.CharField(max_length=500, blank=True, default="")
    is_outdated = models.BooleanField(default=False)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["creator", "platform"], name="uniq_stats_per_creator_platform"
            )
        ]
        ordering = ["platform"]

    @property
    def is_public(self) -> bool:
        """YouTube numbers are always shown (with their own Verified tag). The others only once an admin approved them."""
        return self.platform == "youtube" or self.is_verified

    def __str__(self):
        return f"PlatformStats({self.creator_id}, {self.platform})"


class YouTubeConnection(models.Model):
    """OAuth link to a creator's YouTube channel. Tokens are stored encrypted, never exposed."""

    class Status(models.TextChoices):
        CONNECTED = "connected", "Connected"
        NEEDS_RECONNECT = "needs_reconnect", "Needs reconnect"

    creator = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="youtube_connection"
    )
    access_token_enc = models.TextField()
    refresh_token_enc = models.TextField()
    access_expires_at = models.DateTimeField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.CONNECTED)
    recent_content = models.JSONField(default=list, blank=True)
    last_manual_refresh_at = models.DateTimeField(null=True, blank=True)
    last_error = models.CharField(max_length=100, blank=True, default="")
    connected_at = models.DateTimeField(auto_now_add=True)
    # Google's id for the channel. One channel can be connected to one account only; blank until a legacy
    # connection has synced once.
    channel_id = models.CharField(max_length=64, blank=True, default="")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["channel_id"],
                condition=~models.Q(channel_id=""),
                name="uniq_youtube_channel",
            )
        ]

    def __str__(self):
        return f"YouTubeConnection({self.creator_id}, {self.status})"


class BrandSocialAccount(models.Model):
    """A social account a brand has connected. One verified platform completes a brand's verification.

    ``is_verified`` is True when ownership was proven with Google sign-in (YouTube), or when an admin approved the
    Instagram, TikTok or Facebook link the brand typed. A typed link waits as ``review_status = "pending"`` and does
    not count until then.
    """

    Review = PlatformStats.Review

    brand = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="social_accounts"
    )
    platform = models.CharField(max_length=20, choices=Platform.choices)
    handle_url = models.URLField(max_length=500)
    is_verified = models.BooleanField(default=False)
    review_status = models.CharField(max_length=10, choices=PlatformStats.Review.choices, default=PlatformStats.Review.APPROVED)
    review_note = models.CharField(max_length=500, blank=True, default="")
    connected_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["brand", "platform"], name="uniq_brand_social_per_platform")
        ]
        ordering = ["platform"]

    def __str__(self):
        return f"BrandSocialAccount({self.brand_id}, {self.platform})"
