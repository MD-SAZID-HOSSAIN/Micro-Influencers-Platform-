from rest_framework import serializers
from rest_framework.reverse import reverse

from apps.campaigns.models import Campaign
from apps.campaigns.serializers import CampaignCardSerializer
from apps.proposals.serializers import MyProposalSerializer
from apps.social.models import YouTubeConnection


class DashboardYouTubeSerializer(serializers.Serializer):
    connected = serializers.BooleanField()
    status = serializers.ChoiceField(choices=YouTubeConnection.Status.choices, allow_null=True)
    needs_reconnect = serializers.BooleanField()
    last_synced_at = serializers.DateTimeField(allow_null=True)
    is_outdated = serializers.BooleanField()


class PerformanceSerializer(serializers.Serializer):
    proposals_sent = serializers.IntegerField()
    accepted = serializers.IntegerField()
    acceptance_rate = serializers.FloatField(
        allow_null=True, help_text="Ratio from 0 to 1 (0.5 = 50%); null until a proposal is sent."
    )


class CreatorDashboardSerializer(serializers.Serializer):
    profile_completion = serializers.IntegerField()
    youtube = DashboardYouTubeSerializer()
    available_campaigns = CampaignCardSerializer(many=True)
    applications = MyProposalSerializer(many=True)
    accepted_campaigns = MyProposalSerializer(many=True)
    performance = PerformanceSerializer()


class BrandDashboardCampaignSerializer(serializers.ModelSerializer):
    """One quick-link row. Expects ``proposal_count`` / ``accepted_count`` annotations."""

    proposals_url = serializers.SerializerMethodField()
    proposal_count = serializers.IntegerField(help_text="All proposals received, withdrawn included.")
    accepted_count = serializers.IntegerField(help_text="Proposals currently Accepted.")

    class Meta:
        model = Campaign
        fields = [
            "id",
            "title",
            "status",
            "proposals_url",
            "proposal_count",
            "accepted_count",
            "creators_needed",
        ]
        read_only_fields = fields

    def get_proposals_url(self, campaign) -> str:
        return reverse("brand-campaign-proposals", kwargs={"pk": campaign.pk})


class BrandDashboardSerializer(serializers.Serializer):
    total_campaigns = serializers.IntegerField()
    active_campaigns = serializers.IntegerField(help_text="Campaigns currently Published.")
    total_proposals = serializers.IntegerField(help_text="Across all campaigns, withdrawn included.")
    shortlisted_count = serializers.IntegerField(help_text="Proposals currently Shortlisted.")
    accepted_count = serializers.IntegerField(help_text="Proposals currently Accepted.")
    campaigns = BrandDashboardCampaignSerializer(many=True, help_text="The 50 newest campaigns.")
