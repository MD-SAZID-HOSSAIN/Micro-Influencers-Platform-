from decimal import Decimal

from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.core.choices import Niche, Platform
from apps.core.fields import SafeCharField

from .eligibility import is_eligible
from .models import MAX_CREATORS_NEEDED, Campaign


class CampaignSerializer(serializers.ModelSerializer):
    """A campaign as its owning brand sees and edits it."""

    title = SafeCharField(max_length=200)
    description = SafeCharField(max_length=5000)
    deliverables = SafeCharField(max_length=2000)
    niche = serializers.ChoiceField(choices=Niche.choices)
    platform = serializers.ChoiceField(choices=Platform.choices)
    budget = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal("0.01"))
    creators_needed = serializers.IntegerField(
        min_value=1, max_value=MAX_CREATORS_NEEDED, default=1
    )
    min_followers = serializers.IntegerField(min_value=0, allow_null=True, required=False)

    class Meta:
        model = Campaign
        fields = [
            "id",
            "title",
            "description",
            "niche",
            "platform",
            "budget",
            "deadline",
            "deliverables",
            "creators_needed",
            "min_followers",
            "status",
            "published_at",
            "closed_at",
            "created_at",
        ]
        read_only_fields = ["id", "status", "published_at", "closed_at", "created_at"]

    def validate_deadline(self, value):
        if value <= timezone.now():
            raise serializers.ValidationError("The application deadline must be in the future.")
        return value


class BrandSummarySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    logo_url = serializers.CharField(allow_null=True)


def brand_summary(user) -> dict:
    """Public identity of a brand: company name (or the account holder until it is set) and logo."""
    try:
        profile = user.brand_profile
    except ObjectDoesNotExist:
        return {"id": user.id, "name": user.full_name, "logo_url": None}
    return {"id": user.id, "name": profile.display_name, "logo_url": profile.logo_url}


class CampaignCardSerializer(serializers.ModelSerializer):
    """A campaign as a creator sees it in the directory.

    Needs ``followers_by_platform`` (the requesting creator's follower counts) in the
    serializer context to compute ``eligible``.
    """

    brand = serializers.SerializerMethodField()
    eligible = serializers.SerializerMethodField()

    class Meta:
        model = Campaign
        fields = [
            "id",
            "title",
            "brand",
            "niche",
            "budget",
            "platform",
            "deadline",
            "creators_needed",
            "eligible",
        ]
        read_only_fields = fields

    @extend_schema_field(BrandSummarySerializer)
    def get_brand(self, campaign) -> dict:
        return brand_summary(campaign.brand)

    def get_eligible(self, campaign) -> bool:
        return is_eligible(campaign, self.context.get("followers_by_platform", {}))


class CampaignDetailSerializer(CampaignCardSerializer):
    class Meta(CampaignCardSerializer.Meta):
        fields = CampaignCardSerializer.Meta.fields + [
            "description",
            "deliverables",
            "min_followers",
            "status",
        ]
        read_only_fields = fields


class BrandCampaignListFilterSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Campaign.Status.choices, required=False)
