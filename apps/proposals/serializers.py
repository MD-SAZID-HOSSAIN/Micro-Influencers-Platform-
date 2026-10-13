from decimal import Decimal

from django.core.exceptions import ObjectDoesNotExist
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework.reverse import reverse

from apps.campaigns.models import Campaign
from apps.campaigns.serializers import brand_summary
from apps.core.choices import Platform
from apps.core.fields import SafeCharField
from apps.core.validators import validate_safe_url

from .models import Deliverable, Proposal

MAX_PORTFOLIO_LINKS = 3
MAX_WITHDRAWAL_REASON = 300


class ProposalSubmitSerializer(serializers.Serializer):
    cover_message = SafeCharField(max_length=3000)
    proposed_rate = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal("0.01")
    )
    portfolio_links = serializers.ListField(
        child=serializers.CharField(max_length=500, validators=[validate_safe_url]),
        max_length=MAX_PORTFOLIO_LINKS,
        required=False,
        default=list,
    )
    experience_note = SafeCharField(max_length=2000, allow_blank=True, required=False, default="")


class WithdrawSerializer(serializers.Serializer):
    reason = SafeCharField(max_length=MAX_WITHDRAWAL_REASON, allow_blank=True, required=False)


class CreatorSummarySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    niche = serializers.CharField(allow_null=True)
    platform = serializers.CharField(allow_null=True)
    followers = serializers.IntegerField(allow_null=True)
    engagement_rate = serializers.DecimalField(max_digits=5, decimal_places=2, allow_null=True)
    is_verified = serializers.BooleanField()
    rating_avg = serializers.DecimalField(max_digits=3, decimal_places=2, allow_null=True)
    rating_count = serializers.IntegerField()


class BrandProposalSerializer(serializers.ModelSerializer):
    """A proposal as the brand that received it sees it.

    Expects a queryset annotated by ``annotate_primary_stats`` (creator_id / primary platform).
    """

    creator = serializers.SerializerMethodField()
    profile_url = serializers.SerializerMethodField()
    withdrawal_reason = serializers.SerializerMethodField()

    class Meta:
        model = Proposal
        fields = [
            "id",
            "creator",
            "proposed_rate",
            "cover_message",
            "portfolio_links",
            "experience_note",
            "status",
            "withdrawal_reason",
            "profile_url",
            "completed_at",
            "created_at",
        ]
        read_only_fields = fields

    @extend_schema_field(CreatorSummarySerializer)
    def get_creator(self, proposal) -> dict:
        try:
            profile = proposal.creator.creator_profile
            niche, platform = profile.niche, profile.primary_platform
            rating_avg, rating_count = profile.rating_avg, profile.rating_count
        except ObjectDoesNotExist:
            niche = platform = rating_avg = None
            rating_count = 0
        summary = {
            "id": proposal.creator_id,
            "name": proposal.creator.full_name,
            "niche": niche,
            "platform": platform,
            "followers": proposal.primary_followers,
            "engagement_rate": proposal.primary_engagement,
            "is_verified": proposal.primary_verified,
            "rating_avg": rating_avg,
            "rating_count": rating_count,
        }
        return CreatorSummarySerializer(summary).data  # formats decimals like every other endpoint

    def get_profile_url(self, proposal) -> str:
        return reverse("creator-detail", kwargs={"user_id": proposal.creator_id})

    def get_withdrawal_reason(self, proposal) -> str | None:
        return proposal.withdrawal_reason or None


class ProposalSerializer(serializers.ModelSerializer):
    """A proposal as its own creator sees it."""

    class Meta:
        model = Proposal
        fields = [
            "id",
            "campaign_id",
            "status",
            "cover_message",
            "proposed_rate",
            "portfolio_links",
            "experience_note",
            "withdrawal_reason",
            "completed_at",
            "created_at",
        ]
        read_only_fields = fields


class ProposalActionResultSerializer(serializers.Serializer):
    """What a brand needs after shortlisting/accepting/rejecting: the new status and the counter."""

    id = serializers.IntegerField()
    status = serializers.ChoiceField(choices=Proposal.Status.choices)
    accepted_count = serializers.IntegerField()
    creators_needed = serializers.IntegerField()


class MyProposalBrandSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()


class MyProposalCampaignSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    title = serializers.CharField()
    status = serializers.ChoiceField(choices=Campaign.Status.choices)
    brand = MyProposalBrandSerializer()


class MyProposalSerializer(serializers.ModelSerializer):
    """One row of a creator's application list: status only, no messaging or negotiation."""

    campaign = serializers.SerializerMethodField()
    withdrawal_reason = serializers.SerializerMethodField()

    class Meta:
        model = Proposal
        fields = [
            "id",
            "status",
            "proposed_rate",
            "created_at",
            "completed_at",
            "withdrawal_reason",
            "campaign",
        ]
        read_only_fields = fields

    @extend_schema_field(MyProposalCampaignSerializer)
    def get_campaign(self, proposal) -> dict:
        campaign = proposal.campaign
        brand = brand_summary(campaign.brand)
        return {
            "id": campaign.id,
            "title": campaign.title,
            "status": campaign.status,
            "brand": {"id": brand["id"], "name": brand["name"]},
        }

    def get_withdrawal_reason(self, proposal) -> str | None:
        return proposal.withdrawal_reason or None


class DeliverableSerializer(serializers.ModelSerializer):
    """A link to published content. Used for create (all fields) and for partial update."""

    post_url = serializers.CharField(max_length=500, validators=[validate_safe_url])
    platform = serializers.ChoiceField(choices=Platform.choices)
    note = SafeCharField(max_length=500, allow_blank=True, required=False)

    class Meta:
        model = Deliverable
        fields = ["id", "post_url", "platform", "note", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class CompletionResultSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    status = serializers.ChoiceField(choices=Proposal.Status.choices)
    completed_at = serializers.DateTimeField()


class DeliverableCreatorSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()


class CampaignDeliverablesRowSerializer(serializers.Serializer):
    """One accepted creator and everything they have delivered for a campaign."""

    proposal_id = serializers.IntegerField(source="id")
    creator = serializers.SerializerMethodField()
    completed_at = serializers.DateTimeField(allow_null=True)
    deliverables = DeliverableSerializer(many=True)

    @extend_schema_field(DeliverableCreatorSerializer)
    def get_creator(self, proposal) -> dict:
        return {"id": proposal.creator_id, "name": proposal.creator.full_name}
