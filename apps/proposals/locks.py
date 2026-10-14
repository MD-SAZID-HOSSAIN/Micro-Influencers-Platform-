"""Row locks shared by every operation that changes a proposal's standing in a campaign.

LOCK ORDER: always the campaign first, then the proposal.

Accepting, rejecting, shortlisting, withdrawing, completing and reviewing all go through
``lock_proposal_for_brand`` (or take the same two locks the same way). Locking the campaign first is
what makes "accepted never exceeds Creators Needed" hold when many requests arrive at once, and using
one order everywhere is what stops two requests waiting on each other forever (a deadlock).
Do not lock them in the opposite order anywhere.
"""
from rest_framework.exceptions import NotFound

from apps.accounts.models import User
from apps.campaigns.models import Campaign

from .models import Proposal


def lock_proposal_for_brand(brand: User, proposal_id: int) -> tuple[Campaign, Proposal]:
    """Lock the campaign, then the proposal, for the brand that owns the campaign.

    Anyone else's proposal is a 404 (never a 403). The proposal comes back with its creator loaded.
    Must be called inside ``transaction.atomic()``.
    """
    campaign_id = (
        Proposal.objects.filter(pk=proposal_id, campaign__brand=brand)
        .values_list("campaign_id", flat=True)
        .first()
    )
    if campaign_id is None:
        raise NotFound("Proposal not found.")
    campaign = Campaign.objects.select_for_update().get(pk=campaign_id)
    proposal = Proposal.objects.select_for_update().select_related("creator").get(pk=proposal_id)
    return campaign, proposal
