from rest_framework import serializers

from apps.core.choices import Niche, Platform
from apps.core.fields import OptionalUrlField, SafeCharField
from apps.social.serializers import PlatformStatsSerializer

from .models import BrandProfile, CreatorProfile
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
