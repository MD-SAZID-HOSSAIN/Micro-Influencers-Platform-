from django.conf import settings
from django.db import models

from apps.core.choices import Platform


class PlatformStats(models.Model):
    """A creator's audience numbers on one platform: Verified (API) or Unverified (manual)."""

    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="platform_stats"
    )
    platform = models.CharField(max_length=20, choices=Platform.choices)
    handle_url = models.URLField(max_length=500, null=True, blank=True)
    followers = models.PositiveIntegerField()
    engagement_rate = models.DecimalField(max_digits=5, decimal_places=2)
    is_verified = models.BooleanField(default=False)
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

    def __str__(self):
        return f"PlatformStats({self.creator_id}, {self.platform})"
