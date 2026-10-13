from rest_framework import serializers

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
