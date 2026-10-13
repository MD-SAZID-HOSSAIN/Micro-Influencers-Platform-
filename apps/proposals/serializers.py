from decimal import Decimal

from django.core.exceptions import ObjectDoesNotExist
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework.reverse import reverse

from apps.core.fields import SafeCharField
from apps.core.validators import validate_safe_url

from .models import Proposal

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
            "created_at",
        ]
        read_only_fields = fields

    @extend_schema_field(CreatorSummarySerializer)
    def get_creator(self, proposal) -> dict:
        try:
            profile = proposal.creator.creator_profile
            niche, platform = profile.niche, profile.primary_platform
        except ObjectDoesNotExist:
            niche = platform = None
        summary = {
            "id": proposal.creator_id,
            "name": proposal.creator.full_name,
            "niche": niche,
            "platform": platform,
            "followers": proposal.primary_followers,
            "engagement_rate": proposal.primary_engagement,
            "is_verified": proposal.primary_verified,
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
            "created_at",
        ]
        read_only_fields = fields


class ProposalActionResultSerializer(serializers.Serializer):
    """What a brand needs after shortlisting/accepting/rejecting: the new status and the counter."""

    id = serializers.IntegerField()
    status = serializers.ChoiceField(choices=Proposal.Status.choices)
    accepted_count = serializers.IntegerField()
    creators_needed = serializers.IntegerField()
