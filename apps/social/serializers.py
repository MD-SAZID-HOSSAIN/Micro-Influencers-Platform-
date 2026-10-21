from rest_framework import serializers

from apps.core.fields import OptionalUrlField

from .models import BrandSocialAccount, PlatformStats, YouTubeConnection


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
    followers = serializers.IntegerField(allow_null=True, help_text="Subscribers at the last sync, if any.")
    minimum_followers = serializers.IntegerField(help_text="Subscribers needed to be Verified and apply.")
    below_minimum = serializers.BooleanField(
        help_text="True when a channel is connected but has fewer subscribers than the minimum."
    )


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
            "review_status",
            "review_note",
            "is_outdated",
            "last_synced_at",
        ]
        read_only_fields = ["platform", "is_verified", "review_status", "review_note", "is_outdated", "last_synced_at"]


class PublicPlatformStatsSerializer(PlatformStatsSerializer):
    """What brands see: no review details."""

    class Meta(PlatformStatsSerializer.Meta):
        fields = [f for f in PlatformStatsSerializer.Meta.fields if f not in ("review_status", "review_note")]
        read_only_fields = fields


class CompleteConnectSerializer(serializers.Serializer):
    """What the frontend received from the callback redirect: pass both back unchanged."""

    state = serializers.CharField(max_length=2048)
    code = serializers.CharField(max_length=2048)


class BrandSocialAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = BrandSocialAccount
        fields = ["platform", "handle_url", "is_verified", "review_status", "review_note", "connected_at"]
        read_only_fields = fields


class BrandSocialLinkSerializer(serializers.Serializer):
    """The link a brand types for Instagram, TikTok or Facebook."""

    handle_url = serializers.CharField(max_length=500)
