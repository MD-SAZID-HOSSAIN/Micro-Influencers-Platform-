from rest_framework import serializers

from apps.core.fields import OptionalUrlField

from .models import PlatformStats, YouTubeConnection


class YouTubeConnectionSerializer(serializers.ModelSerializer):
    """Connection state only: token fields are deliberately never listed."""

    class Meta:
        model = YouTubeConnection
        fields = ["status", "connected_at"]
        read_only_fields = fields


class YouTubeStatusSerializer(serializers.Serializer):
    connected = serializers.BooleanField()
    status = serializers.ChoiceField(choices=YouTubeConnection.Status.choices, allow_null=True)
    needs_reconnect = serializers.BooleanField()
    connected_at = serializers.DateTimeField(allow_null=True)
    last_synced_at = serializers.DateTimeField(allow_null=True)
    is_outdated = serializers.BooleanField()
    last_error = serializers.CharField(allow_null=True)


class AuthorizationUrlSerializer(serializers.Serializer):
    authorization_url = serializers.URLField()


class RecentVideoSerializer(serializers.Serializer):
    video_id = serializers.CharField()
    title = serializers.CharField()
    url = serializers.URLField()
    published_at = serializers.CharField()


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
