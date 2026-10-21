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


class CompleteConnectSerializer(serializers.Serializer):
    """What the frontend received from the callback redirect: pass both back unchanged."""

    state = serializers.CharField(max_length=2048)
    code = serializers.CharField(max_length=2048)


class YouTubeDirectConnectSerializer(serializers.Serializer):
    handle_url = serializers.CharField(max_length=500, required=False, allow_blank=True)
    followers = serializers.IntegerField(min_value=0, max_value=2_000_000_000, required=False, default=0)
    engagement_rate = serializers.DecimalField(
        max_digits=5, decimal_places=2, min_value=0, max_value=100, required=False, default=3.50
    )


class ChallengeCodeSerializer(serializers.Serializer):
    platform = serializers.CharField()
    challenge_code = serializers.CharField()
    instructions = serializers.CharField()


class DirectAccountAuthSerializer(serializers.Serializer):
    handle = serializers.CharField(max_length=200)
    verification_method = serializers.ChoiceField(
        choices=["oauth", "direct_auth", "challenge"], default="direct_auth"
    )
    auth_code = serializers.CharField(max_length=2048, required=False, allow_blank=True, default="")
    followers = serializers.IntegerField(min_value=0, max_value=2_000_000_000, required=False, default=0)
    engagement_rate = serializers.DecimalField(
        max_digits=5, decimal_places=2, min_value=0, max_value=100, required=False, default=3.50
    )



class BrandSocialAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = BrandSocialAccount
        fields = ["platform", "handle_url", "is_verified", "connected_at"]
        read_only_fields = fields


class BrandSocialLinkSerializer(serializers.Serializer):
    """The link a brand types for Instagram, TikTok or Facebook."""

    handle_url = serializers.CharField(max_length=500)
