"""Creator-facing campaign discovery: which campaigns are visible and how they are filtered."""
from django.db.models import Q, QuerySet
from django.utils import timezone
from rest_framework import serializers

from apps.core.choices import Niche, Platform
from apps.social.models import PlatformStats

from .models import Campaign


class CampaignFilterSerializer(serializers.Serializer):
    q = serializers.CharField(required=False, allow_blank=True, max_length=100)
    niche = serializers.ChoiceField(choices=Niche.choices, required=False)
    platform = serializers.ChoiceField(choices=Platform.choices, required=False)
    min_budget = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0, required=False)
    max_budget = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0, required=False)
    deadline_before = serializers.DateTimeField(required=False)
    deadline_after = serializers.DateTimeField(required=False)


def open_campaigns() -> QuerySet:
    """Published campaigns still accepting applications, from brands that are not suspended.

    The deadline is checked here as well as by the auto-close job, which only runs every few
    minutes, so an expired campaign never shows up in the gap.
    """
    return Campaign.objects.filter(
        status=Campaign.Status.PUBLISHED,
        deadline__gt=timezone.now(),
        brand__is_active=True,
    ).select_related("brand__brand_profile")


def discovery_queryset(params: dict) -> QuerySet:
    campaigns = open_campaigns()
    if q := params.get("q"):
        campaigns = campaigns.filter(Q(title__icontains=q) | Q(description__icontains=q))
    if niche := params.get("niche"):
        campaigns = campaigns.filter(niche=niche)
    if platform := params.get("platform"):
        campaigns = campaigns.filter(platform=platform)
    if (value := params.get("min_budget")) is not None:
        campaigns = campaigns.filter(budget__gte=value)
    if (value := params.get("max_budget")) is not None:
        campaigns = campaigns.filter(budget__lte=value)
    if value := params.get("deadline_before"):
        campaigns = campaigns.filter(deadline__lte=value)
    if value := params.get("deadline_after"):
        campaigns = campaigns.filter(deadline__gte=value)
    return campaigns.order_by("-published_at", "-id")


def followers_by_platform(user) -> dict[str, int]:
    return dict(PlatformStats.objects.filter(creator=user).values_list("platform", "followers"))
