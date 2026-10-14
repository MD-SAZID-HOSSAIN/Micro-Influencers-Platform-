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
    """Full details plus the viewing creator's apply state (needs ``request`` in the context)."""

    accepted_count = serializers.SerializerMethodField()
    all_creators_selected = serializers.SerializerMethodField()
    can_apply = serializers.SerializerMethodField()
    apply_blocked_reason = serializers.SerializerMethodField()

    class Meta(CampaignCardSerializer.Meta):
        fields = CampaignCardSerializer.Meta.fields + [
            "description",
            "deliverables",
            "min_followers",
            "status",
            "accepted_count",
            "all_creators_selected",
            "can_apply",
            "apply_blocked_reason",
        ]
        read_only_fields = fields

    def _state(self, campaign) -> dict:
        # Imported here: the proposals app depends on this one, so a top-level import would be circular.
        from apps.proposals.apply_state import accepted_count, apply_state

        cache = self.__dict__.setdefault("_state_cache", {})
        if campaign.pk not in cache:
            can_apply, reason = apply_state(campaign, self.context["request"].user)
            accepted = accepted_count(campaign)
            cache[campaign.pk] = {
                "accepted_count": accepted,
                "all_creators_selected": accepted >= campaign.creators_needed,
                "can_apply": can_apply,
                "apply_blocked_reason": reason,
            }
        return cache[campaign.pk]

    def get_accepted_count(self, campaign) -> int:
        return self._state(campaign)["accepted_count"]

    def get_all_creators_selected(self, campaign) -> bool:
        return self._state(campaign)["all_creators_selected"]

    def get_can_apply(self, campaign) -> bool:
        return self._state(campaign)["can_apply"]

    @extend_schema_field(
        {"type": "string", "nullable": True, "enum": ["active_proposal", "proposal_rejected", "campaign_closed"]}
    )
    def get_apply_blocked_reason(self, campaign):
        return self._state(campaign)["apply_blocked_reason"]


class BrandCampaignListFilterSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Campaign.Status.choices, required=False)


class FunnelSerializer(serializers.Serializer):
    received = serializers.IntegerField(help_text="Every proposal received, withdrawn ones included.")
    shortlisted = serializers.IntegerField()
    accepted = serializers.IntegerField()
    rejected = serializers.IntegerField()
    withdrawn = serializers.IntegerField()


class AcceptedVsNeededSerializer(serializers.Serializer):
    accepted = serializers.IntegerField()
    needed = serializers.IntegerField()


class CampaignMetricsSerializer(serializers.Serializer):
    views = serializers.IntegerField(help_text="Times creators opened this campaign.")
    funnel = FunnelSerializer()
    accepted_vs_needed = AcceptedVsNeededSerializer()
    avg_proposed_rate = serializers.DecimalField(max_digits=10, decimal_places=2, allow_null=True)
    budget_per_creator = serializers.DecimalField(max_digits=10, decimal_places=2)
    acceptance_rate = serializers.FloatField(
        allow_null=True,
        help_text="Currently accepted / received, from 0 to 1. Null until a proposal arrives.",
    )
