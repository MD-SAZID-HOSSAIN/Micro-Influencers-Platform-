from rest_framework import serializers

from apps.campaigns.serializers import brand_summary
from apps.core.fields import SafeCharField

from .models import Review


class ReviewCreateSerializer(serializers.Serializer):
    rating = serializers.IntegerField(min_value=1, max_value=5)
    text = SafeCharField(max_length=500, allow_blank=True, required=False, default="")


class ReviewBrandSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()


class ReviewCampaignSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    title = serializers.CharField()


class ReviewSerializer(serializers.ModelSerializer):
    brand = serializers.SerializerMethodField()
    campaign = serializers.SerializerMethodField()

    class Meta:
        model = Review
        fields = ["id", "rating", "text", "brand", "campaign", "created_at"]
        read_only_fields = fields

    def get_brand(self, review) -> dict:
        summary = brand_summary(review.brand)
        return {"id": summary["id"], "name": summary["name"]}

    def get_campaign(self, review) -> dict:
        campaign = review.proposal.campaign
        return {"id": campaign.id, "title": campaign.title}
