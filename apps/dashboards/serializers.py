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
    pending_count = serializers.IntegerField(
        help_text="Proposals currently Pending, over all of them (the list below shows only the newest)."
    )
    shortlisted_count = serializers.IntegerField(
        help_text="Proposals currently Shortlisted, over all of them (the list below shows only the newest)."
    )
    applications = MyProposalSerializer(many=True)
    accepted_campaigns = MyProposalSerializer(many=True)
    performance = PerformanceSerializer()


class BrandDashboardCampaignSerializer(serializers.ModelSerializer):
    """One quick-link row. Expects ``proposal_count`` / ``pending_count`` / ``accepted_count`` annotations."""

    proposals_url = serializers.SerializerMethodField()
    proposal_count = serializers.IntegerField(help_text="All proposals received, withdrawn included.")
    pending_count = serializers.IntegerField(help_text="Proposals currently Pending (no decision yet).")
    accepted_count = serializers.IntegerField(help_text="Proposals currently Accepted.")

    class Meta:
        model = Campaign
        fields = [
            "id",
            "title",
            "status",
            "proposals_url",
            "proposal_count",
            "pending_count",
            "accepted_count",
            "creators_needed",
        ]
        read_only_fields = fields

    def get_proposals_url(self, campaign) -> str:
        return reverse("brand-campaign-proposals", kwargs={"pk": campaign.pk})


class BusiestCampaignSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    title = serializers.CharField()
    pending_count = serializers.IntegerField(help_text="Proposals currently Pending on this campaign.")


class BrandDashboardSerializer(serializers.Serializer):
    total_campaigns = serializers.IntegerField()
    active_campaigns = serializers.IntegerField(help_text="Campaigns currently Published.")
    total_proposals = serializers.IntegerField(help_text="Across all campaigns, withdrawn included.")
    pending_count = serializers.IntegerField(help_text="Proposals currently Pending (no decision yet).")
    shortlisted_count = serializers.IntegerField(help_text="Proposals currently Shortlisted.")
    accepted_count = serializers.IntegerField(help_text="Proposals currently Accepted.")
    draft_count = serializers.IntegerField(help_text="Campaigns still in Draft, over all of them.")
    first_draft_id = serializers.IntegerField(
        allow_null=True, help_text="The newest Draft campaign, or null when there is none."
    )
    busiest_campaign = BusiestCampaignSerializer(
        allow_null=True, help_text="The campaign with the most Pending proposals, or null when none are pending."
    )
    campaigns = BrandDashboardCampaignSerializer(many=True, help_text="The 50 newest campaigns.")
