"""Read-only aggregation for the two dashboards. Nothing here writes to the database."""
from django.db.models import Count, Q

from apps.accounts.models import User
from apps.campaigns.discovery import discovery_queryset
from apps.profiles.services import completion_percent, get_or_create_profile
from apps.proposals.models import Proposal
from apps.social.services import connection_status

AVAILABLE_CAMPAIGNS_LIMIT = 5
APPLICATIONS_LIMIT = 10
ACCEPTED_LIMIT = 20


def creator_dashboard(user: User) -> dict:
    """Everything a creator's home screen shows, as model instances plus a few plain numbers."""
    connection = connection_status(user)
    my_proposals = Proposal.objects.filter(creator=user).select_related(
        "campaign__brand__brand_profile"
    )

    totals = my_proposals.aggregate(
        sent=Count("id"),  # withdrawn proposals still count as sent
        accepted=Count("id", filter=Q(status=Proposal.Status.ACCEPTED)),  # only currently Accepted
    )
    sent, accepted = totals["sent"], totals["accepted"]

    return {
        "profile_completion": completion_percent(get_or_create_profile(user)),
        "youtube": {
            key: connection[key]
            for key in ("connected", "status", "needs_reconnect", "last_synced_at", "is_outdated")
        },
        "available_campaigns": list(discovery_queryset({})[:AVAILABLE_CAMPAIGNS_LIMIT]),
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
