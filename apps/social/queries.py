from django.db.models import BooleanField, DecimalField, OuterRef, Q, QuerySet, Subquery, Value
from django.db.models.functions import Coalesce

from .models import PlatformStats


def annotate_primary_stats(
    rows: QuerySet,
    *,
    creator_field: str = "user_id",
    platform_field: str = "primary_platform",
) -> QuerySet:
    """Annotate rows with the numbers for their creator's own primary platform.

    By default ``rows`` are CreatorProfile objects. For other models, say where the creator's
    id and primary platform live, e.g. ``creator_field="creator_id"`` and
    ``platform_field="creator__creator_profile__primary_platform"`` for proposals.

    Adds ``primary_followers``, ``primary_engagement`` (both None when the creator has no
    public stats there) and ``primary_verified`` (False when there are none).
    """
    stats = PlatformStats.objects.filter(
        Q(platform="youtube") | Q(is_verified=True),  # Instagram, TikTok and Facebook count once an admin approved them
        creator_id=OuterRef(creator_field),
        platform=OuterRef(platform_field),
    )
    return rows.annotate(
        primary_followers=Subquery(stats.values("followers")[:1]),
        primary_engagement=Subquery(
            stats.values("engagement_rate")[:1],
            output_field=DecimalField(max_digits=5, decimal_places=2),
        ),
        primary_verified=Coalesce(
            Subquery(stats.values("is_verified")[:1]),
            Value(False),
            output_field=BooleanField(),
        ),
    )
