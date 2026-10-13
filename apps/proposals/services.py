from decimal import Decimal

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound, ValidationError

from apps.accounts.models import User
from apps.campaigns.models import Campaign
from apps.core.exceptions import Conflict
from apps.notifications.models import Kind
from apps.notifications.services import notify

from .models import ACTIVE_STATUSES, Proposal


class CampaignClosed(Conflict):
    default_code = "campaign_closed"
    default_detail = "This campaign is no longer accepting applications."


class ProposalExists(Conflict):
    default_code = "proposal_exists"
    default_detail = "You already have an active proposal for this campaign."


class ProposalRejected(Conflict):
    default_code = "proposal_rejected"
    default_detail = "Your proposal for this campaign was rejected and cannot be resubmitted."


class InvalidTransition(Conflict):
    default_code = "invalid_transition"
    default_detail = "This change is not allowed for the proposal's current status."


def submit_proposal(
    *,
    creator: User,
    campaign_id: int,
    cover_message: str,
    proposed_rate: Decimal,
    portfolio_links: list[str],
    experience_note: str,
) -> Proposal:
    """Apply to a campaign.

    The campaign row is locked so simultaneous submits are handled one at a time; the
    partial unique constraint is the backstop. The deadline is checked here as well as by
    the auto-close job, which only runs every few minutes.
    """
    with transaction.atomic():
        campaign = (
            Campaign.objects.select_for_update()
            .filter(pk=campaign_id, status__in=[Campaign.Status.PUBLISHED, Campaign.Status.CLOSED])
            .first()
        )
        if campaign is None:
            raise NotFound("Campaign not found.")
        if campaign.status != Campaign.Status.PUBLISHED or campaign.deadline <= timezone.now():
            raise CampaignClosed()

        history = Proposal.objects.filter(campaign=campaign, creator=creator)
        if history.filter(status__in=ACTIVE_STATUSES).exists():
            raise ProposalExists()
        if history.filter(status=Proposal.Status.REJECTED).exists():
            raise ProposalRejected()

        try:
            with transaction.atomic():  # savepoint: an IntegrityError must not poison the outer transaction
                proposal = Proposal.objects.create(
                    campaign=campaign,
                    creator=creator,
                    cover_message=cover_message,
                    proposed_rate=proposed_rate,
                    portfolio_links=portfolio_links,
                    experience_note=experience_note,
                )
        except IntegrityError:
            raise ProposalExists()

        notify(
            campaign.brand,
            Kind.PROPOSAL_RECEIVED,
            f'{creator.full_name} sent a proposal for "{campaign.title}".',
            campaign_id=campaign.id,
            proposal_id=proposal.id,
        )
    return proposal


def withdraw_proposal(*, creator: User, proposal_id: int, reason: str | None) -> Proposal:
    """Withdraw an active proposal. Withdrawing an Accepted one needs a reason and frees its slot.

    Locks the campaign first and the proposal second, the same order as accepting, so the two
    can never deadlock.
    """
    campaign_id = (
        Proposal.objects.filter(pk=proposal_id, creator=creator)
        .values_list("campaign_id", flat=True)
        .first()
    )
    if campaign_id is None:
        raise NotFound("Proposal not found.")

    with transaction.atomic():
        campaign = Campaign.objects.select_for_update().get(pk=campaign_id)
        proposal = Proposal.objects.select_for_update().get(pk=proposal_id)
        if proposal.status not in ACTIVE_STATUSES:
            raise InvalidTransition()

        reason = (reason or "").strip()
        was_accepted = proposal.status == Proposal.Status.ACCEPTED
        if was_accepted and not reason:
            raise ValidationError(
                {"reason": ["A reason is required when withdrawing an accepted proposal."]}
            )

        proposal.status = Proposal.Status.WITHDRAWN
        proposal.withdrawal_reason = reason
        proposal.save(update_fields=["status", "withdrawal_reason", "updated_at"])

        slot_note = " A slot has opened." if was_accepted else ""
        notify(
            campaign.brand,
            Kind.PROPOSAL_WITHDRAWN,
            f'{creator.full_name} withdrew their proposal for "{campaign.title}".{slot_note}',
            campaign_id=campaign.id,
            proposal_id=proposal.id,
            slot_opened=was_accepted,
        )
    return proposal
