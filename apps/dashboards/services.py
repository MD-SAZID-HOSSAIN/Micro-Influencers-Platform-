"""Read-only aggregation for the two dashboards. Nothing here writes to the database."""
from django.db.models import Count, Max, Q

from apps.accounts.models import User
from apps.campaigns.discovery import discovery_queryset
from apps.campaigns.models import Campaign
from apps.profiles.services import completion_percent, get_or_create_profile
from apps.proposals.models import Proposal
from apps.social.services import connection_status

AVAILABLE_CAMPAIGNS_LIMIT = 5
APPLICATIONS_LIMIT = 10
ACCEPTED_LIMIT = 20
BRAND_CAMPAIGN_ROWS_LIMIT = 50


def creator_dashboard(user: User) -> dict:
    """Everything a creator's home screen shows, as model instances plus a few plain numbers."""
    connection = connection_status(user)
    my_proposals = Proposal.objects.filter(creator=user).select_related(
        "campaign__brand__brand_profile"
    )

    totals = my_proposals.aggregate(
        sent=Count("id"),  # withdrawn proposals still count as sent
        accepted=Count("id", filter=Q(status=Proposal.Status.ACCEPTED)),  # only currently Accepted
        pending=Count("id", filter=Q(status=Proposal.Status.PENDING)),
        shortlisted=Count("id", filter=Q(status=Proposal.Status.SHORTLISTED)),
    )
    sent, accepted = totals["sent"], totals["accepted"]

    return {
        "profile_completion": completion_percent(get_or_create_profile(user)),
        "youtube": {
            key: connection[key]
            for key in ("connected", "status", "needs_reconnect", "last_synced_at", "is_outdated")
        },
        "available_campaigns": list(discovery_queryset({})[:AVAILABLE_CAMPAIGNS_LIMIT]),
        "pending_count": totals["pending"],  # over every proposal, not just the listed ones
        "shortlisted_count": totals["shortlisted"],
        "applications": list(my_proposals[:APPLICATIONS_LIMIT]),
        "accepted_campaigns": list(
            my_proposals.filter(status=Proposal.Status.ACCEPTED)[:ACCEPTED_LIMIT]
        ),
        "performance": {
            "proposals_sent": sent,
            "accepted": accepted,
            "acceptance_rate": round(accepted / sent, 4) if sent else None,
        },
    }


def brand_dashboard(user: User) -> dict:
    """A brand's home: headline counts over everything, plus rows for its newest campaigns.

    The counts come from two aggregate queries, the busiest campaign from one more and the rows
    from one annotated query, so the cost does not grow with the number of campaigns or proposals.
    """
    campaigns = Campaign.objects.filter(brand=user)
    campaign_totals = campaigns.aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(status=Campaign.Status.PUBLISHED)),
        drafts=Count("id", filter=Q(status=Campaign.Status.DRAFT)),
        newest_draft_id=Max("id", filter=Q(status=Campaign.Status.DRAFT)),
    )
    busiest = (
        campaigns.annotate(
            pending_count=Count("proposals", filter=Q(proposals__status=Proposal.Status.PENDING))
        )
        .filter(pending_count__gt=0)
        .order_by("-pending_count", "-id")
        .values("id", "title", "pending_count")
        .first()
    )
    proposal_totals = Proposal.objects.filter(campaign__brand=user).aggregate(
        total=Count("id"),  # withdrawn proposals included
        pending=Count("id", filter=Q(status=Proposal.Status.PENDING)),
        shortlisted=Count("id", filter=Q(status=Proposal.Status.SHORTLISTED)),
        accepted=Count("id", filter=Q(status=Proposal.Status.ACCEPTED)),  # only currently Accepted
    )
    rows = campaigns.annotate(
        proposal_count=Count("proposals"),
        pending_count=Count("proposals", filter=Q(proposals__status=Proposal.Status.PENDING)),
        accepted_count=Count("proposals", filter=Q(proposals__status=Proposal.Status.ACCEPTED)),
    ).order_by("-created_at", "-id")[:BRAND_CAMPAIGN_ROWS_LIMIT]

    return {
        "total_campaigns": campaign_totals["total"],
        "active_campaigns": campaign_totals["active"],
        "total_proposals": proposal_totals["total"],
        "pending_count": proposal_totals["pending"],
        "shortlisted_count": proposal_totals["shortlisted"],
        "accepted_count": proposal_totals["accepted"],
        "draft_count": campaign_totals["drafts"],
        "first_draft_id": campaign_totals["newest_draft_id"],
        "busiest_campaign": busiest,
        "campaigns": list(rows),
    }
