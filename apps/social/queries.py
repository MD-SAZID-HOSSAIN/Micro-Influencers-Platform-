from django.conf import settings
from django.db.models import BooleanField, Case, DecimalField, Exists, OuterRef, Q, QuerySet, Subquery, Value, When

from apps.accounts.models import User

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
    public stats there) and ``primary_verified``: whether the CREATOR is Verified, which is the same rule as
    ``creator_is_verified`` (a confirmed email and YouTube proven by Google with enough subscribers). It does not
    depend on the primary platform: an approved Instagram, TikTok or Facebook number never verifies a creator.
    """
    stats = PlatformStats.objects.filter(
        Q(platform="youtube") | Q(is_verified=True),  # Instagram, TikTok and Facebook count once an admin approved them
        creator_id=OuterRef(creator_field),
        platform=OuterRef(platform_field),
    )
    verified_youtube = PlatformStats.objects.filter(
        creator_id=OuterRef(creator_field),
        platform="youtube",
        is_verified=True,
        is_outdated=False,
        followers__gte=settings.MIN_CREATOR_FOLLOWERS,
    )
    email_confirmed = User.objects.filter(pk=OuterRef(creator_field), email_verified=True)
    return rows.annotate(
        primary_followers=Subquery(stats.values("followers")[:1]),
        primary_engagement=Subquery(
            stats.values("engagement_rate")[:1],
            output_field=DecimalField(max_digits=5, decimal_places=2),
        ),
        primary_verified=Case(
            When(Exists(verified_youtube) & Exists(email_confirmed), then=Value(True)),
            default=Value(False),
            output_field=BooleanField(),
        ),
    )
