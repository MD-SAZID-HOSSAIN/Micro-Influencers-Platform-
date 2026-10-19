from rest_framework import serializers

from apps.core.choices import Niche, Platform
from apps.core.fields import OptionalUrlField, SafeCharField
from apps.core.validators import validate_safe_url
from apps.social.serializers import PlatformStatsSerializer

from .images import discard_upload
from .models import BrandProfile, CreatorProfile, PortfolioItem
from .services import completion_percent


def _rate():
    return serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=0, allow_null=True, required=False
    )


class CreatorProfileSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source="user_id", read_only=True)
    username = serializers.CharField(source="user.username", read_only=True)
    full_name = SafeCharField(source="user.full_name", max_length=150)
    photo_url = OptionalUrlField()
    bio = SafeCharField(max_length=1000, allow_blank=True, required=False)
    niche = serializers.ChoiceField(choices=Niche.choices, allow_null=True, required=False)
    primary_platform = serializers.ChoiceField(
        choices=Platform.choices, allow_null=True, required=False
    )
    city = SafeCharField(max_length=100, allow_blank=True, required=False)
    country = SafeCharField(max_length=100, allow_blank=True, required=False)
    rate_post = _rate()
    rate_story = _rate()
    rate_video = _rate()
    rating_avg = serializers.DecimalField(max_digits=3, decimal_places=2, allow_null=True, read_only=True)
    rating_count = serializers.IntegerField(read_only=True)
    completion_percent = serializers.SerializerMethodField()
    stats = PlatformStatsSerializer(source="user.platform_stats", many=True, read_only=True)

    class Meta:
        model = CreatorProfile
        fields = [
            "id",
            "username",
            "full_name",
            "photo_url",
            "bio",
            "niche",
            "primary_platform",
            "city",
            "country",
            "rate_post",
            "rate_story",
            "rate_video",
            "rating_avg",
            "rating_count",
            "completion_percent",
            "stats",
        ]

    def get_completion_percent(self, profile) -> int:
        return completion_percent(profile)

    def update(self, instance, validated_data):
        user_data = validated_data.pop("user", {})
        if "full_name" in user_data:
            instance.user.full_name = user_data["full_name"]
            instance.user.save(update_fields=["full_name"])
        if "photo_url" in validated_data:
            discard_upload(instance)  # a link set by hand replaces an uploaded photo
        return super().update(instance, validated_data)


class BrandProfileSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source="user_id", read_only=True)
    display_name = serializers.CharField(read_only=True)
    company_name = SafeCharField(max_length=150, allow_blank=True, required=False)
    industry = SafeCharField(max_length=100, allow_blank=True, required=False)
    website = OptionalUrlField()
    logo_url = OptionalUrlField()
    about = SafeCharField(max_length=2000, allow_blank=True, required=False)

    class Meta:
        model = BrandProfile
        fields = [
            "id",
            "display_name",
            "company_name",
            "industry",
            "website",
            "logo_url",
            "about",
        ]

    def update(self, instance, validated_data):
        if "logo_url" in validated_data:
            discard_upload(instance)  # a link set by hand replaces an uploaded logo
        return super().update(instance, validated_data)


class CreatorCardSerializer(serializers.Serializer):
    """A directory result. Expects a profile annotated by ``annotate_primary_stats``."""

    id = serializers.IntegerField(source="user_id")
    name = serializers.CharField(source="user.full_name")
    photo_url = serializers.CharField(allow_null=True)
    niche = serializers.ChoiceField(choices=Niche.choices, allow_null=True)
    primary_platform = serializers.ChoiceField(choices=Platform.choices, allow_null=True)
    followers = serializers.IntegerField(source="primary_followers", allow_null=True)
    engagement_rate = serializers.DecimalField(
        source="primary_engagement", max_digits=5, decimal_places=2, allow_null=True
    )
    is_verified = serializers.BooleanField(source="primary_verified")
    rating_avg = serializers.DecimalField(max_digits=3, decimal_places=2, allow_null=True)
    rating_count = serializers.IntegerField()


class PortfolioItemSerializer(serializers.ModelSerializer):
    url = serializers.CharField(max_length=500, validators=[validate_safe_url])
    caption = SafeCharField(max_length=200, allow_blank=True, required=False)
    source = serializers.ChoiceField(choices=PortfolioItem.Source.choices, required=False)

    class Meta:
        model = PortfolioItem
        fields = ["id", "url", "caption", "source", "created_at"]
        read_only_fields = ["id", "created_at"]


class CreatorDetailSerializer(serializers.ModelSerializer):
    """The brand-facing view of a creator. Private account data (email, phone) is excluded."""

    id = serializers.IntegerField(source="user_id", read_only=True)
    username = serializers.CharField(source="user.username", read_only=True)
    full_name = serializers.CharField(source="user.full_name", read_only=True)
    stats = PlatformStatsSerializer(source="user.platform_stats", many=True, read_only=True)
    portfolio = PortfolioItemSerializer(source="user.portfolio_items", many=True, read_only=True)
    rating_avg = serializers.DecimalField(max_digits=3, decimal_places=2, allow_null=True, read_only=True)
    rating_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = CreatorProfile
        fields = [
            "id",
            "username",
            "full_name",
            "photo_url",
            "bio",
            "niche",
            "primary_platform",
            "city",
            "country",
            "rate_post",
            "rate_story",
            "rate_video",
            "stats",
            "portfolio",
            "rating_avg",
            "rating_count",
        ]
        read_only_fields = fields
