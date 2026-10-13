"""What a creator sees on a campaign detail: the accepted count and whether Apply is enabled."""
from django.utils import timezone

from apps.accounts.models import User
from apps.campaigns.models import Campaign

from .models import ACTIVE_STATUSES, Proposal


def accepted_count(campaign: Campaign) -> int:
    """Proposals currently Accepted (Withdrawn ones no longer count)."""
    return Proposal.objects.filter(campaign=campaign, status=Proposal.Status.ACCEPTED).count()


def apply_state(campaign: Campaign, creator: User) -> tuple[bool, str | None]:
    """(can_apply, reason_if_blocked).

    Blocked by an active proposal, then by a rejected one, then by the campaign being closed
    or past its deadline. A withdrawn proposal does not block while the campaign is open.
    """
    statuses = set(
        Proposal.objects.filter(campaign=campaign, creator=creator).values_list("status", flat=True)
    )
    if statuses & {s.value for s in ACTIVE_STATUSES}:
        return False, "active_proposal"
    if Proposal.Status.REJECTED in statuses:
        return False, "proposal_rejected"
    if campaign.status != Campaign.Status.PUBLISHED or campaign.deadline <= timezone.now():
        return False, "campaign_closed"
    return True, None
