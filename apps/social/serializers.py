from rest_framework import serializers

from apps.core.fields import OptionalUrlField

from .models import PlatformStats


class PlatformStatsSerializer(serializers.ModelSerializer):
    handle_url = OptionalUrlField()
    followers = serializers.IntegerField(min_value=0, max_value=2_000_000_000)
    engagement_rate = serializers.DecimalField(max_digits=5, decimal_places=2, min_value=0, max_value=100)

    class Meta:
        model = PlatformStats
        fields = [
            "platform",
            "handle_url",
            "followers",
            "engagement_rate",
            "is_verified",
            "is_outdated",
            "last_synced_at",
        ]
        read_only_fields = ["platform", "is_verified", "is_outdated", "last_synced_at"]
