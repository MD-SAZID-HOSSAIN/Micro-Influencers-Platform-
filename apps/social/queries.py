from django.db.models import BooleanField, OuterRef, QuerySet, Subquery, Value
from django.db.models.functions import Coalesce

from .models import PlatformStats


def annotate_primary_stats(profiles: QuerySet) -> QuerySet:
    """Annotate CreatorProfile rows with the numbers for their own primary platform.

    Adds ``primary_followers``, ``primary_engagement`` (both None when the creator has
    no stats there) and ``primary_verified`` (False when there are none).
    """
    stats = PlatformStats.objects.filter(
        creator_id=OuterRef("user_id"), platform=OuterRef("primary_platform")
    )
    return profiles.annotate(
        primary_followers=Subquery(stats.values("followers")[:1]),
        primary_engagement=Subquery(stats.values("engagement_rate")[:1]),
        primary_verified=Coalesce(
            Subquery(stats.values("is_verified")[:1]),
            Value(False),
            output_field=BooleanField(),
        ),
    )
