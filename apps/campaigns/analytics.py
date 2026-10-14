"""Per-campaign analytics for brands (FR-23): view counting and proposal metrics."""
from decimal import ROUND_HALF_UP, Decimal

from django.db import connection
from django.db.models import Avg, Count, Q, Sum
from django.utils import timezone

from apps.accounts.models import User
from apps.proposals.models import Proposal

from .models import Campaign, CampaignView


def record_campaign_view(campaign: Campaign, creator: User) -> None:
    """Count one opening of the campaign by this creator, in exactly one atomic statement.

    This runs every time a creator opens a campaign page. A single PostgreSQL upsert creates the
    creator's row on their first view and adds 1 to it afterwards, so there is no read-then-write
    race and a first view costs the same as a repeat one.
    """
    table = connection.ops.quote_name(CampaignView._meta.db_table)
    with connection.cursor() as cursor:
        cursor.execute(
            f"INSERT INTO {table} (campaign_id, creator_id, view_count, last_viewed_at) "
            "VALUES (%s, %s, 1, %s) "
            "ON CONFLICT (campaign_id, creator_id) DO UPDATE "
            f"SET view_count = {table}.view_count + 1, last_viewed_at = EXCLUDED.last_viewed_at",
            [campaign.pk, creator.pk, timezone.now()],
        )


def campaign_metrics(campaign: Campaign) -> dict:
    """The proposal funnel, accepted-versus-needed, rate-versus-budget and acceptance rate.

    Everything is by the proposals' *current* status: withdrawn proposals count as received, and
    a proposal that was accepted and then withdrawn does not count as accepted.
    """
    status = Proposal.Status
    totals = Proposal.objects.filter(campaign=campaign).aggregate(
        received=Count("id"),
        shortlisted=Count("id", filter=Q(status=status.SHORTLISTED)),
        accepted=Count("id", filter=Q(status=status.ACCEPTED)),
        rejected=Count("id", filter=Q(status=status.REJECTED)),
        withdrawn=Count("id", filter=Q(status=status.WITHDRAWN)),
        average_rate=Avg("proposed_rate"),
    )
    views = CampaignView.objects.filter(campaign=campaign).aggregate(total=Sum("view_count"))["total"]
    received, accepted = totals["received"], totals["accepted"]
    return {
        "views": views or 0,
        "funnel": {key: totals[key] for key in ("received", "shortlisted", "accepted", "rejected", "withdrawn")},
        "accepted_vs_needed": {"accepted": accepted, "needed": campaign.creators_needed},
        "avg_proposed_rate": (
            Decimal(str(totals["average_rate"])).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            if received
            else None
        ),
        "budget_per_creator": campaign.budget,
        "acceptance_rate": round(accepted / received, 4) if received else None,
    }
