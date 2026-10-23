"""Deliverables (FR-20): the content an accepted creator published, and the brand marking it Completed."""
import logging

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound

from apps.accounts.models import User
from apps.core.choices import Platform
from apps.core.exceptions import Conflict, DomainError
from apps.social import services as social_services
from apps.social.models import YouTubeConnection
from apps.social.youtube_client import YouTubeError, youtube_video_id

from .models import Deliverable, Proposal
from .locks import lock_proposal_for_brand
from .services import InvalidTransition

logger = logging.getLogger(__name__)

MAX_DELIVERABLES = 20


class DeliverablesLocked(Conflict):
    default_code = "deliverables_locked"
    default_detail = "Deliverables can only be changed while the proposal is accepted and not yet completed."


class DeliverablesFull(Conflict):
    default_code = "deliverables_full"
    default_detail = f"A proposal can have at most {MAX_DELIVERABLES} deliverables."


class VideoNotYours(DomainError):
    status_code = 400
    default_code = "video_not_yours"
    default_detail = "This video is not on your connected YouTube channel. Submit one of your own videos."


def _check_video_is_theirs(creator: User, platform: str, post_url: str) -> None:
    """Refuse a YouTube video that belongs to a different channel than the creator's connected one.

    Without this a creator could submit somebody else's popular video and have its views and likes shown to the
    brand as their own results. The check needs the server's YouTube key. When it is missing, Google cannot be
    reached, or the creator's channel is not known yet, the link is accepted and the daily statistics sync makes
    the same comparison before it stores any number.
    """
    video_id = youtube_video_id(post_url) if platform == Platform.YOUTUBE else None
    if video_id is None or not settings.YOUTUBE_API_KEY:
        return
    channel_id = (
        YouTubeConnection.objects.filter(creator=creator).values_list("channel_id", flat=True).first() or ""
    )
    if not channel_id:
        return
    try:
        found = social_services.get_youtube_client().fetch_video_stats([video_id], settings.YOUTUBE_API_KEY)
    except YouTubeError as exc:
        logger.warning("Could not check the owner of video %s: %s", video_id, exc)
        return
    video = found.get(video_id)
    if video is not None and video.channel_id and video.channel_id != channel_id:
        raise VideoNotYours()


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
    _check_video_is_theirs(creator, platform, post_url)  # before the row lock: it may call Google
    with transaction.atomic():
        proposal = _lock_own_proposal(creator, proposal_id)
        _ensure_editable(proposal)
        if proposal.deliverables.count() >= MAX_DELIVERABLES:
            raise DeliverablesFull()
        return Deliverable.objects.create(
            proposal=proposal, post_url=post_url, platform=platform, note=note
        )


def update_deliverable(*, creator: User, proposal_id: int, deliverable_id: int, changes: dict) -> Deliverable:
    if "post_url" in changes or "platform" in changes:
        current = Deliverable.objects.filter(
            pk=deliverable_id, proposal_id=proposal_id, proposal__creator=creator
        ).first()
        if current is not None:  # anything else is reported as not found below
            _check_video_is_theirs(
                creator, changes.get("platform", current.platform), changes.get("post_url", current.post_url)
            )
    with transaction.atomic():
        proposal = _lock_own_proposal(creator, proposal_id)
        deliverable = proposal.deliverables.filter(pk=deliverable_id).first()
        if deliverable is None:
            raise NotFound("Deliverable not found.")
        _ensure_editable(proposal)
        if "post_url" in changes and changes["post_url"] != deliverable.post_url:
            deliverable.views_count = deliverable.likes_count = deliverable.comments_count = None
            deliverable.stats_synced_at = None  # the numbers belonged to the old video
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
        _, proposal = lock_proposal_for_brand(brand, proposal_id)
        if proposal.completed_at is not None:
            return proposal
        if proposal.status != Proposal.Status.ACCEPTED:
            raise InvalidTransition()
        proposal.completed_at = timezone.now()
        proposal.save(update_fields=["completed_at", "updated_at"])
    return proposal
