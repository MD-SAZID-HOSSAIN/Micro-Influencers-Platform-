"""Per-campaign analytics for brands (FR-23): view counting and proposal metrics."""
from decimal import ROUND_HALF_UP, Decimal

from django.db.models import Avg, Count, F, Q, Sum
from django.utils import timezone

from apps.accounts.models import User
from apps.proposals.models import Proposal

from .models import Campaign, CampaignView


def record_campaign_view(campaign: Campaign, creator: User) -> None:
    """Count one opening of the campaign by this creator (a counter on one row, safe under concurrency)."""
    view, _ = CampaignView.objects.get_or_create(campaign=campaign, creator=creator)
    CampaignView.objects.filter(pk=view.pk).update(
        view_count=F("view_count") + 1, last_viewed_at=timezone.now()
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
