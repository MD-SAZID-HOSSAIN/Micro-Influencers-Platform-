from django.db import transaction
from django.utils import timezone

from apps.core.exceptions import Conflict, DomainError
from apps.notifications.models import Kind
from apps.notifications.services import notify

from .models import Campaign


class CampaignNotEditable(Conflict):
    default_code = "campaign_not_editable"
    default_detail = "Only draft campaigns can be edited or deleted."


class InvalidCampaignTransition(Conflict):
    default_code = "invalid_campaign_transition"
    default_detail = "This change is not allowed for the campaign's current status."


class DeadlineInPast(DomainError):
    status_code = 400
    default_code = "deadline_in_past"
    default_detail = "The application deadline must be in the future."


def _locked(campaign: Campaign) -> Campaign:
    return Campaign.objects.select_for_update().get(pk=campaign.pk)


def publish_campaign(campaign: Campaign) -> Campaign:
    """Draft -> Published. The deadline must still be in the future."""
    with transaction.atomic():
        locked = _locked(campaign)
        if locked.status != Campaign.Status.DRAFT:
            raise InvalidCampaignTransition()
        now = timezone.now()
        if locked.deadline <= now:
            raise DeadlineInPast()
        locked.status = Campaign.Status.PUBLISHED
        locked.published_at = now
        locked.save(update_fields=["status", "published_at", "updated_at"])
    campaign.refresh_from_db()
    return campaign


def close_campaign(campaign: Campaign, *, auto: bool = False) -> Campaign:
    """Published -> Closed (idempotent for an already Closed campaign; never reopens).

    ``auto=True`` marks a deadline closure and tells the brand about it.
    """
    with transaction.atomic():
        locked = _locked(campaign)
        if locked.status == Campaign.Status.CLOSED:
            campaign.refresh_from_db()
            return campaign
        if locked.status != Campaign.Status.PUBLISHED:
            raise InvalidCampaignTransition()
        locked.status = Campaign.Status.CLOSED
        locked.closed_at = timezone.now()
        locked.save(update_fields=["status", "closed_at", "updated_at"])
        if auto:
            notify(
                locked.brand,
                Kind.CAMPAIGN_AUTO_CLOSED,
                f'Your campaign "{locked.title}" was closed because its application deadline passed.',
                campaign_id=locked.id,
            )
    campaign.refresh_from_db()
    return campaign


def update_campaign(campaign: Campaign, changes: dict) -> Campaign:
    """Edit a Draft. Anything published or closed is frozen."""
    with transaction.atomic():
        locked = _locked(campaign)
        if locked.status != Campaign.Status.DRAFT:
            raise CampaignNotEditable()
        for field, value in changes.items():
            setattr(locked, field, value)
        locked.save()
    return locked


def delete_campaign(campaign: Campaign) -> None:
    """Delete a Draft. Anything published or closed is kept for its proposals' sake."""
    with transaction.atomic():
        locked = _locked(campaign)
        if locked.status != Campaign.Status.DRAFT:
            raise CampaignNotEditable()
        locked.delete()
