import logging
from smtplib import SMTPException
from unittest import mock

import pytest
from django.core import mail
from django.db import transaction

from apps.accounts.models import Role, User
from apps.accounts.tests.factories import UserFactory
from apps.campaigns.models import Campaign
from apps.campaigns.tests.factories import CampaignFactory
from apps.notifications.models import Kind, Notification
from apps.notifications.services import notify
from apps.proposals.models import Proposal
from apps.proposals.tests.factories import ProposalFactory
from apps.social.tests.fakes import make_connection

FRONTEND = "http://frontend.test"
SETTINGS_URL = f"{FRONTEND}/settings/notifications"


def verified(role=Role.CREATOR, **kwargs):
    return UserFactory(role=role, email_verified=True, **kwargs)


def accept_url(pk):
    return f"/api/v1/brand/proposals/{pk}/accept/"


# ---- the three acceptance criteria -------------------------------------------------------------------


def test_accepted_with_toggle_on_and_verified_email_gives_in_app_plus_email(db, auth_client, run_on_commit):
    creator = verified()
    proposal = ProposalFactory(creator=creator, campaign=CampaignFactory(status=Campaign.Status.PUBLISHED))

    with run_on_commit():
        response = auth_client(proposal.campaign.brand).post(accept_url(proposal.pk))

    assert response.status_code == 200
    assert Notification.objects.filter(user=creator, kind=Kind.PROPOSAL_ACCEPTED).count() == 1
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == [creator.email]
    assert mail.outbox[0].subject == "Your proposal was accepted"


@pytest.mark.parametrize("flags", [{"email_notifications_enabled": False}, {"email_verified": False}])
def test_toggle_off_or_unverified_email_gives_in_app_only(db, run_on_commit, flags):
    creator = UserFactory(role=Role.CREATOR, **{"email_verified": True, **flags})

    with run_on_commit():
        notify(creator, Kind.PROPOSAL_ACCEPTED, "Accepted")

    assert Notification.objects.filter(user=creator).count() == 1
    assert mail.outbox == []


def test_email_provider_down_keeps_in_app_works_retries_and_shows_no_error(db, auth_client, run_on_commit, caplog):
    creator = verified()
    proposal = ProposalFactory(creator=creator, campaign=CampaignFactory(status=Campaign.Status.PUBLISHED))

    with mock.patch("apps.core.tasks.send_mail", side_effect=SMTPException("provider down")) as send:
        with caplog.at_level(logging.ERROR):
            with run_on_commit():
                response = auth_client(proposal.campaign.brand).post(accept_url(proposal.pk))

    assert response.status_code == 200  # the user sees no error
    assert Proposal.objects.get(pk=proposal.pk).status == Proposal.Status.ACCEPTED
    assert Notification.objects.filter(user=creator, kind=Kind.PROPOSAL_ACCEPTED).exists()
    assert send.call_count == 6  # first attempt + 5 retries
    assert "Failed to send email" in caplog.text
    assert mail.outbox == []


# ---- what the email says ----------------------------------------------------------------------------------


def test_the_email_has_one_button_to_the_app_and_never_exposes_private_details(db, auth_client, run_on_commit):
    creator = verified()
    proposal = ProposalFactory(
        creator=creator,
        campaign=CampaignFactory(status=Campaign.Status.PUBLISHED),
        cover_message="SECRET PITCH TEXT",
        proposed_rate="777.00",
        experience_note="PRIVATE EXPERIENCE",
    )

    with run_on_commit():
        auth_client(proposal.campaign.brand).post(accept_url(proposal.pk))

    body = mail.outbox[0].body
    assert f"{FRONTEND}/creator/applications" in body
    assert SETTINGS_URL in body  # the footer links to Notification Settings
    for private in ("SECRET PITCH", "777", "PRIVATE EXPERIENCE", "Bearer", "token", proposal.campaign.title):
        assert private not in body
    assert body.count("http") == 2  # the button and the settings link, nothing else


@pytest.mark.parametrize(
    "kind, subject, path",
    [
        (Kind.PROPOSAL_SHORTLISTED, "You were shortlisted for a campaign", "/creator/applications"),
        (Kind.PROPOSAL_ACCEPTED, "Your proposal was accepted", "/creator/applications"),
        (Kind.PROPOSAL_REJECTED, "Your proposal was not selected", "/creator/applications"),
        (Kind.ACCOUNT_RECONNECT, "Reconnect your YouTube account", "/settings/connections"),
    ],
)
def test_creator_events_have_a_named_subject_and_a_link(db, run_on_commit, kind, subject, path):
    creator = verified()

    with run_on_commit():
        notify(creator, kind, "in-app text", campaign_id=5, proposal_id=9)

    assert mail.outbox[0].subject == subject
    assert f"{FRONTEND}{path}" in mail.outbox[0].body


@pytest.mark.parametrize(
    "kind, subject, path",
    [
        (Kind.PROPOSAL_RECEIVED, "New proposal received", "/brand/campaigns/5/proposals"),
        (Kind.PROPOSAL_WITHDRAWN, "A creator withdrew a proposal", "/brand/campaigns/5/proposals"),
        (Kind.CAMPAIGN_AUTO_CLOSED, "Your campaign has closed", "/brand/campaigns/5"),
    ],
)
def test_brand_events_have_a_named_subject_and_a_link(db, run_on_commit, kind, subject, path):
    brand = verified(Role.BRAND)

    with run_on_commit():
        notify(brand, kind, "in-app text", campaign_id=5, proposal_id=9)

    assert mail.outbox[0].subject == subject
    assert f"{FRONTEND}{path}" in mail.outbox[0].body


def test_a_withdrawal_that_opened_a_slot_says_so(db, run_on_commit):
    brand = verified(Role.BRAND)

    with run_on_commit():
        notify(brand, Kind.PROPOSAL_WITHDRAWN, "x", campaign_id=5, proposal_id=9, slot_opened=True)
        notify(brand, Kind.PROPOSAL_WITHDRAWN, "x", campaign_id=5, proposal_id=9, slot_opened=False)

    assert "slot has opened" in mail.outbox[0].body.lower()
    assert "slot" not in mail.outbox[1].body.lower()


# ---- when emails are NOT sent ------------------------------------------------------------------------------


def test_suspended_users_get_no_emails(db, run_on_commit):
    creator = verified(is_active=False)

    with run_on_commit():
        notify(creator, Kind.PROPOSAL_ACCEPTED, "Accepted")

    assert Notification.objects.filter(user=creator).count() == 1
    assert mail.outbox == []


def test_no_email_is_sent_if_the_transaction_rolls_back(db, run_on_commit):
    creator = verified()

    with run_on_commit():
        try:
            with transaction.atomic():
                notify(creator, Kind.PROPOSAL_ACCEPTED, "Accepted")
                raise RuntimeError("boom")
        except RuntimeError:
            pass

    assert mail.outbox == []
    assert not Notification.objects.filter(user=creator).exists()


def test_reconnect_email_is_sent_once_per_token_failure_not_daily(db, fake_youtube_revoked, run_on_commit):
    from apps.social.services import sync_connection

    creator, connection = fake_youtube_revoked
    with run_on_commit():
        sync_connection(connection)
        connection.refresh_from_db()
        sync_connection(connection)  # the next daily run: a dead connection is skipped

    assert [m.subject for m in mail.outbox] == ["Reconnect your YouTube account"]


@pytest.fixture
def fake_youtube_revoked(db, monkeypatch):
    from apps.social.tests.fakes import FakeYouTubeClient
    from apps.social.youtube_client import TokenRevoked

    fake = FakeYouTubeClient()
    fake.fetch_results["revoked-at"] = TokenRevoked()
    monkeypatch.setattr("apps.social.services.get_youtube_client", lambda: fake)
    creator = verified()
    return creator, make_connection(creator, access="revoked-at")


def test_password_reset_codes_ignore_the_notification_toggle_and_verification(db, run_on_commit):
    from apps.accounts.services import request_password_reset

    creator = UserFactory(
        role=Role.CREATOR, email="amina@example.com", email_verified=False, email_notifications_enabled=False
    )

    with run_on_commit():
        request_password_reset(creator.email)

    assert len(mail.outbox) == 1
    assert "password reset code" in mail.outbox[0].subject.lower()


def test_user_model_defaults(db):
    created = UserFactory()

    assert User.objects.get(pk=created.pk).email_verified is False
    assert User.objects.get(pk=created.pk).email_notifications_enabled is True
