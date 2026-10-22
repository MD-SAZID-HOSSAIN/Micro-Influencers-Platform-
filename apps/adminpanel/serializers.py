from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.accounts.models import Role, User
from apps.campaigns.models import Campaign
from apps.core.fields import SafeCharField
from apps.reviews.models import Review
from apps.social.models import BrandSocialAccount, PlatformStats

from .models import AdminActionLog


class ReasonSerializer(serializers.Serializer):
    """Every admin action records why it was taken."""

    reason = SafeCharField(max_length=500)


class OptionalReasonSerializer(serializers.Serializer):
    """Approving needs no explanation. A default note goes in the audit trail."""

    reason = SafeCharField(max_length=500, required=False, allow_blank=True)


class AdminStatsFilterSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=PlatformStats.Review.choices, required=False, default="pending")


class AdminPlatformStatsSerializer(serializers.ModelSerializer):
    """A creator's typed Instagram, TikTok or Facebook numbers, for the admin to check against the link."""

    creator = serializers.SerializerMethodField()

    class Meta:
        model = PlatformStats
        fields = [
            "id",
            "creator",
            "platform",
            "handle_url",
            "followers",
            "engagement_rate",
            "review_status",
            "review_note",
            "updated_at",
        ]
        read_only_fields = fields

    def get_creator(self, stats) -> dict:
        user = stats.creator
        return {"id": user.id, "username": user.username, "full_name": user.full_name}


class AdminBrandPlatformSerializer(serializers.ModelSerializer):
    """The Instagram, TikTok or Facebook link a brand typed, for the admin to open and check."""

    brand = serializers.SerializerMethodField()

    class Meta:
        model = BrandSocialAccount
        fields = ["id", "brand", "platform", "handle_url", "review_status", "review_note", "connected_at"]
        read_only_fields = fields

    def get_brand(self, account) -> dict:
        user = account.brand
        return {"id": user.id, "username": user.username, "full_name": user.full_name}


class AdminUserFilterSerializer(serializers.Serializer):
    q = serializers.CharField(required=False, allow_blank=True, max_length=100)
    role = serializers.ChoiceField(choices=Role.choices, required=False)
    status = serializers.ChoiceField(choices=["active", "suspended"], required=False)


class AdminUserSerializer(serializers.ModelSerializer):
    status = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "full_name",
            "email",
            "username",
            "role",
            "status",
            "email_verified",
            "date_joined",
        ]
        read_only_fields = fields

    def get_status(self, user) -> str:
        return "active" if user.is_active else "suspended"


class AdminCampaignSerializer(serializers.ModelSerializer):
    class Meta:
        model = Campaign
        fields = ["id", "title", "status", "closed_at"]
        read_only_fields = fields


class AdminPersonSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    username = serializers.CharField()
    full_name = serializers.CharField()


class AdminCampaignFilterSerializer(serializers.Serializer):
    q = serializers.CharField(required=False, allow_blank=True, max_length=100)
    status = serializers.ChoiceField(choices=Campaign.Status.choices, required=False)


class AdminCampaignRowSerializer(serializers.ModelSerializer):
    """One campaign in the moderation list. Expects a ``proposal_count`` annotation."""

    brand = serializers.SerializerMethodField()
    proposal_count = serializers.IntegerField(read_only=True, help_text="Every proposal received, withdrawn ones included.")

    class Meta:
        model = Campaign
        fields = [
            "id",
            "title",
            "status",
            "brand",
            "deadline",
            "creators_needed",
            "proposal_count",
            "created_at",
            "closed_at",
        ]
        read_only_fields = fields

    @extend_schema_field(AdminPersonSerializer)
    def get_brand(self, campaign) -> dict:
        user = campaign.brand
        return {"id": user.id, "username": user.username, "full_name": user.full_name}


class AdminReviewFilterSerializer(serializers.Serializer):
    q = serializers.CharField(required=False, allow_blank=True, max_length=100)
    rating = serializers.IntegerField(required=False, min_value=1, max_value=5)


class AdminReviewCampaignSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    title = serializers.CharField()


class AdminReviewRowSerializer(serializers.ModelSerializer):
    """One review in the moderation list: what was written, by which brand, about which creator."""

    brand = serializers.SerializerMethodField()
    creator = serializers.SerializerMethodField()
    campaign = serializers.SerializerMethodField()

    class Meta:
        model = Review
        fields = ["id", "rating", "text", "brand", "creator", "campaign", "created_at"]
        read_only_fields = fields

    @extend_schema_field(AdminPersonSerializer)
    def get_brand(self, review) -> dict:
        user = review.brand
        return {"id": user.id, "username": user.username, "full_name": user.full_name}

    @extend_schema_field(AdminPersonSerializer)
    def get_creator(self, review) -> dict:
        user = review.creator
        return {"id": user.id, "username": user.username, "full_name": user.full_name}

    @extend_schema_field(AdminReviewCampaignSerializer)
    def get_campaign(self, review) -> dict:
        campaign = review.proposal.campaign
        return {"id": campaign.id, "title": campaign.title}


class ActionAdminSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    username = serializers.CharField()


class AdminActionLogSerializer(serializers.ModelSerializer):
    admin = serializers.SerializerMethodField()

    class Meta:
        model = AdminActionLog
        fields = ["id", "admin", "action", "target_type", "target_id", "target_label", "reason", "created_at"]
        read_only_fields = fields

    def get_admin(self, entry) -> dict:
        # The admin account may have been deleted since; the label keeps the entry readable.
        return {"id": entry.admin_id, "username": entry.admin_label}


class OverviewUsersSerializer(serializers.Serializer):
    total = serializers.IntegerField()
    suspended = serializers.IntegerField()
    by_role = serializers.DictField(child=serializers.IntegerField())


class OverviewSignupSerializer(serializers.Serializer):
    date = serializers.DateField()
    count = serializers.IntegerField()


class OverviewSerializer(serializers.Serializer):
    users = OverviewUsersSerializer()
    signups = OverviewSignupSerializer(many=True)
    campaigns_by_status = serializers.DictField(child=serializers.IntegerField())
    total_proposals = serializers.IntegerField()
