from decimal import Decimal
from django.db.models import F, Q, QuerySet, Value
from django.db.models.functions import Coalesce, Least, NullIf
from rest_framework import serializers

from apps.core.choices import Niche, Platform
from apps.social.queries import annotate_primary_stats

from .models import CreatorProfile

ORDERINGS = [
    "followers",
    "-followers",
    "engagement",
    "-engagement",
    "rate",
    "-rate",
    "rating",
    "-rating",
]
DEFAULT_ORDERING = "-followers"
_ORDER_FIELDS = {
    "followers": "primary_followers",
    "engagement": "primary_engagement",
    "rate": "cheapest_rate",
    "rating": "rating_avg",
}
_RATE_FIELDS = ("rate_post", "rate_story", "rate_video")


def _decimal(**kwargs):
    return serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0, required=False, **kwargs)


class DirectoryFilterSerializer(serializers.Serializer):
    """Validates the directory's query parameters; bad values give a 400, never silent no-ops."""

    q = serializers.CharField(required=False, allow_blank=True, max_length=100)
    niche = serializers.ChoiceField(choices=Niche.choices, required=False)
    platform = serializers.ChoiceField(choices=Platform.choices, required=False)
    min_followers = serializers.IntegerField(min_value=0, required=False)
    max_followers = serializers.IntegerField(min_value=0, required=False)
    min_engagement = serializers.DecimalField(
        max_digits=5, decimal_places=2, min_value=0, max_value=100, required=False
    )
    max_engagement = serializers.DecimalField(
        max_digits=5, decimal_places=2, min_value=0, max_value=100, required=False
    )
    location = serializers.CharField(required=False, allow_blank=True, max_length=100)
    min_rate = _decimal()
    max_rate = _decimal()
    verified_only = serializers.BooleanField(required=False)
    min_rating = serializers.DecimalField(
        max_digits=3, decimal_places=2, min_value=0, max_value=5, required=False
    )
    ordering = serializers.ChoiceField(choices=ORDERINGS, required=False)


def _rate_in_range(min_rate, max_rate) -> Q:
    """True when at least one of the creator's three rates lies inside the range."""
    matches = Q()
    for field in _RATE_FIELDS:
        condition = Q(**{f"{field}__isnull": False})
        if min_rate is not None:
            condition &= Q(**{f"{field}__gte": min_rate})
        if max_rate is not None:
            condition &= Q(**{f"{field}__lte": max_rate})
        matches |= condition
    return matches


def _ordered(profiles: QuerySet, ordering: str) -> QuerySet:
    field = _ORDER_FIELDS[ordering.lstrip("-")]
    expression = F(field).desc(nulls_last=True) if ordering.startswith("-") else F(field).asc(nulls_last=True)
    return profiles.order_by(expression, "user_id")


def directory_queryset(params: dict) -> QuerySet:
    """Active creators annotated with primary-platform stats, filtered and ordered."""
    max_rate_sentinel = Value(Decimal("9999999999.99"))
    cheapest_expr = NullIf(
        Least(*(Coalesce(f, max_rate_sentinel) for f in _RATE_FIELDS)),
        max_rate_sentinel,
    )
    profiles = annotate_primary_stats(
        CreatorProfile.objects.filter(user__is_active=True).select_related("user")
    ).annotate(cheapest_rate=cheapest_expr)

    if q := params.get("q"):
        profiles = profiles.filter(
            Q(user__full_name__icontains=q) | Q(user__username__icontains=q)
        )
    if niche := params.get("niche"):
        profiles = profiles.filter(niche=niche)
    if platform := params.get("platform"):
        profiles = profiles.filter(primary_platform=platform)
    if (value := params.get("min_followers")) is not None:
        profiles = profiles.filter(primary_followers__gte=value)
    if (value := params.get("max_followers")) is not None:
        profiles = profiles.filter(primary_followers__lte=value)
    if (value := params.get("min_engagement")) is not None:
        profiles = profiles.filter(primary_engagement__gte=value)
    if (value := params.get("max_engagement")) is not None:
        profiles = profiles.filter(primary_engagement__lte=value)
    if location := params.get("location"):
        profiles = profiles.filter(Q(city__icontains=location) | Q(country__icontains=location))
    min_rate, max_rate = params.get("min_rate"), params.get("max_rate")
    if min_rate is not None or max_rate is not None:
        profiles = profiles.filter(_rate_in_range(min_rate, max_rate))
    if params.get("verified_only"):
        profiles = profiles.filter(primary_verified=True)
    if (value := params.get("min_rating")) is not None:
        profiles = profiles.filter(rating_avg__gte=value)

    return _ordered(profiles, params.get("ordering") or DEFAULT_ORDERING)
