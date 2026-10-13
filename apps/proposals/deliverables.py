"""Deliverables (FR-20): the content an accepted creator published, and the brand marking it Completed."""
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound

from apps.accounts.models import User
from apps.core.exceptions import Conflict

from .models import Deliverable, Proposal
from .services import InvalidTransition, _lock_for_brand

MAX_DELIVERABLES = 20


class DeliverablesLocked(Conflict):
    default_code = "deliverables_locked"
    default_detail = "Deliverables can only be changed while the proposal is accepted and not yet completed."


class DeliverablesFull(Conflict):
    default_code = "deliverables_full"
    default_detail = f"A proposal can have at most {MAX_DELIVERABLES} deliverables."


def _lock_own_proposal(creator: User, proposal_id: int) -> Proposal:
    """Lock the creator's own proposal for editing its deliverables (anyone else's is a 404)."""
    proposal = Proposal.objects.select_for_update().filter(pk=proposal_id, creator=creator).first()
    if proposal is None:
        raise NotFound("Proposal not found.")
    return proposal


def _ensure_editable(proposal: Proposal) -> None:
    if proposal.status != Proposal.Status.ACCEPTED or proposal.completed_at is not None:
        raise DeliverablesLocked()


def list_deliverables(*, creator: User, proposal_id: int):
    if not Proposal.objects.filter(pk=proposal_id, creator=creator).exists():
        raise NotFound("Proposal not found.")
    return Deliverable.objects.filter(proposal_id=proposal_id)


def submit_deliverable(
    *, creator: User, proposal_id: int, post_url: str, platform: str, note: str = ""
) -> Deliverable:
    with transaction.atomic():
        proposal = _lock_own_proposal(creator, proposal_id)
        _ensure_editable(proposal)
        if proposal.deliverables.count() >= MAX_DELIVERABLES:
            raise DeliverablesFull()
        return Deliverable.objects.create(
            proposal=proposal, post_url=post_url, platform=platform, note=note
        )


def update_deliverable(*, creator: User, proposal_id: int, deliverable_id: int, changes: dict) -> Deliverable:
    with transaction.atomic():
        proposal = _lock_own_proposal(creator, proposal_id)
        deliverable = proposal.deliverables.filter(pk=deliverable_id).first()
        if deliverable is None:
            raise NotFound("Deliverable not found.")
        _ensure_editable(proposal)
        for field, value in changes.items():
            setattr(deliverable, field, value)
        deliverable.save()
        return deliverable


def delete_deliverable(*, creator: User, proposal_id: int, deliverable_id: int) -> None:
    with transaction.atomic():
        proposal = _lock_own_proposal(creator, proposal_id)
        deliverable = proposal.deliverables.filter(pk=deliverable_id).first()
        if deliverable is None:
            raise NotFound("Deliverable not found.")
        _ensure_editable(proposal)
        deliverable.delete()


def complete_proposal(*, brand: User, proposal_id: int) -> Proposal:
    """Mark an Accepted collaboration Completed. Final; repeating it changes nothing.

    Uses the same lock order as accepting and withdrawing (campaign, then proposal).
    """
    with transaction.atomic():
        _, proposal = _lock_for_brand(brand, proposal_id)
        if proposal.completed_at is not None:
            return proposal
        if proposal.status != Proposal.Status.ACCEPTED:
            raise InvalidTransition()
        proposal.completed_at = timezone.now()
        proposal.save(update_fields=["completed_at", "updated_at"])
    return proposal
