from decimal import Decimal

from django.utils import timezone
from rest_framework import serializers

from apps.core.choices import Niche, Platform
from apps.core.fields import SafeCharField

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


class BrandCampaignListFilterSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Campaign.Status.choices, required=False)
