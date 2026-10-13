from decimal import Decimal

from rest_framework import serializers

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
