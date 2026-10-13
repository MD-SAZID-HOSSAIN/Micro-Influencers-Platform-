"""The email channel for in-app notifications (FR-24).

One fixed sentence per event, one button into the app, and a footer link to the notification
settings. No names, titles, rates, proposal text or stats are ever put in an email body.
"""
from dataclasses import dataclass

from django.conf import settings

from apps.accounts.models import User
from apps.core.emailing import queue_email

from .models import Kind


@dataclass(frozen=True)
class EmailEvent:
    subject: str
    sentence: str
    path: str  # relative to FRONTEND_URL; may use {campaign_id}


# The paths are the frontend routes these emails link to (the person must log in to see them).
EMAIL_EVENTS = {
    Kind.PROPOSAL_SHORTLISTED: EmailEvent(
        "You were shortlisted for a campaign",
        "A brand shortlisted your proposal.",
        "/creator/applications",
    ),
    Kind.PROPOSAL_ACCEPTED: EmailEvent(
        "Your proposal was accepted",
        "A brand accepted your proposal.",
        "/creator/applications",
    ),
    Kind.PROPOSAL_REJECTED: EmailEvent(
        "Your proposal was not selected",
        "A brand decided not to move forward with your proposal.",
        "/creator/applications",
    ),
    Kind.ACCOUNT_RECONNECT: EmailEvent(
        "Reconnect your YouTube account",
        "Your YouTube connection has expired. Reconnect it to keep your stats up to date.",
        "/settings/connections",
    ),
    Kind.PROPOSAL_RECEIVED: EmailEvent(
        "New proposal received",
        "A creator sent a proposal to one of your campaigns.",
        "/brand/campaigns/{campaign_id}/proposals",
    ),
    Kind.PROPOSAL_WITHDRAWN: EmailEvent(
        "A creator withdrew a proposal",
        "A creator withdrew their proposal.",
        "/brand/campaigns/{campaign_id}/proposals",
    ),
    Kind.CAMPAIGN_AUTO_CLOSED: EmailEvent(
        "Your campaign has closed",
        "One of your campaigns closed because its application deadline passed.",
        "/brand/campaigns/{campaign_id}",
    ),
}
SETTINGS_PATH = "/settings/notifications"
SLOT_OPENED_SENTENCE = " A slot has opened for your campaign."


def wants_email(user: User) -> bool:
    """Only active users with a verified address who have not switched notification emails off."""
    return bool(user.is_active and user.email_verified and user.email_notifications_enabled)


def queue_notification_email(*, to: str, kind: str, payload: dict) -> None:
    event = EMAIL_EVENTS[Kind(kind)]
    sentence = event.sentence
    if kind == Kind.PROPOSAL_WITHDRAWN and payload.get("slot_opened"):
        sentence += SLOT_OPENED_SENTENCE
    base = settings.FRONTEND_URL.rstrip("/")
    queue_email(
        to,
        event.subject,
        "notification",
        {
            "sentence": sentence,
            "url": base + event.path.format(**payload),
            "settings_url": base + SETTINGS_PATH,
        },
    )
