from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest
from django.db import connection
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Role
from apps.accounts.tests.factories import UserFactory
from apps.campaigns.models import Campaign
from apps.campaigns.tests.factories import CampaignFactory
from apps.core.exceptions import DomainError
from apps.notifications.models import Kind, Notification
from apps.proposals.models import Proposal
from apps.proposals.services import submit_proposal
from apps.proposals.tests.factories import ProposalFactory

S = Proposal.Status


def submit_url(campaign_id):
    return f"/api/v1/campaigns/{campaign_id}/proposals/"


def campaign_url(campaign_id):
    return f"/api/v1/campaigns/{campaign_id}/"


def body(**overrides):
    data = {
        "cover_message": "I run a fitness page with an engaged audience.",
        "proposed_rate": "250.00",
        "portfolio_links": ["https://instagram.com/p/1"],
        "experience_note": "Worked with three sports brands.",
    }
    data.update(overrides)
    return data


@pytest.fixture
def creator(db):
    return UserFactory(role=Role.CREATOR, full_name="Amina Rahman")


@pytest.fixture
def campaign(db):
    return CampaignFactory(status=Campaign.Status.PUBLISHED, title="Summer launch")


def submit(auth_client, creator, campaign, **overrides):
    return auth_client(creator).post(submit_url(campaign.pk), body(**overrides), format="json")


def error_code(response):
    return response.json()["error"]["code"]


# ---- the happy path -----------------------------------------------------------------------------


def test_submit_creates_a_pending_proposal_and_notifies_the_brand(creator, campaign, auth_client):
    response = submit(auth_client, creator, campaign)

    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "pending"
    assert data["proposed_rate"] == "250.00"
    assert data["portfolio_links"] == ["https://instagram.com/p/1"]
    assert data["campaign_id"] == campaign.id
    proposal = Proposal.objects.get(pk=data["id"])
    assert (proposal.creator, proposal.campaign, proposal.status) == (creator, campaign, S.PENDING)
    note = Notification.objects.get(user=campaign.brand)
    assert note.kind == Kind.PROPOSAL_RECEIVED
    assert "Amina Rahman" in note.message and "Summer launch" in note.message
    assert note.payload == {"campaign_id": campaign.id, "proposal_id": proposal.id}


def test_links_and_note_are_optional(creator, campaign, auth_client):
    data = {"cover_message": "Hello", "proposed_rate": "100"}

    response = auth_client(creator).post(submit_url(campaign.pk), data, format="json")

    assert response.status_code == 201
    assert response.json()["portfolio_links"] == []
    assert response.json()["experience_note"] == ""


# ---- one active proposal per campaign --------------------------------------------------------------


@pytest.mark.parametrize("status", [S.PENDING, S.SHORTLISTED, S.ACCEPTED])
def test_second_active_proposal_is_a_conflict(creator, campaign, auth_client, status):
    ProposalFactory(campaign=campaign, creator=creator, status=status)

    response = submit(auth_client, creator, campaign)

    assert response.status_code == 409
    assert error_code(response) == "proposal_exists"
    assert Proposal.objects.filter(campaign=campaign, creator=creator).count() == 1


def test_resubmitting_after_rejection_is_blocked(creator, campaign, auth_client):  # RF4
    ProposalFactory(campaign=campaign, creator=creator, status=S.REJECTED)

    response = submit(auth_client, creator, campaign)

    assert response.status_code == 409
    assert error_code(response) == "proposal_rejected"


def test_resubmitting_after_withdrawal_on_a_published_campaign_creates_a_new_row(creator, campaign, auth_client):
    ProposalFactory(campaign=campaign, creator=creator, status=S.WITHDRAWN)

    response = submit(auth_client, creator, campaign)

    assert response.status_code == 201
    assert Proposal.objects.filter(campaign=campaign, creator=creator).count() == 2


def test_resubmitting_after_withdrawal_on_a_closed_campaign_is_blocked(creator, auth_client):  # RF4
    campaign = CampaignFactory(status=Campaign.Status.CLOSED)
    ProposalFactory(campaign=campaign, creator=creator, status=S.WITHDRAWN)

    response = submit(auth_client, creator, campaign)

    assert response.status_code == 409
    assert error_code(response) == "campaign_closed"


def test_two_simultaneous_submits_create_exactly_one_active_proposal(transactional_db):  # RF4
    if connection.vendor == "sqlite":
        pytest.skip("Requires PostgreSQL row locks; SQLite table locks on concurrent threads")
    creator = UserFactory(role=Role.CREATOR)
    campaign = CampaignFactory(status=Campaign.Status.PUBLISHED)

    def attempt(_):
        try:
            submit_proposal(
                creator=creator,
                campaign_id=campaign.pk,
                cover_message="Hi",
                proposed_rate="100",
                portfolio_links=[],
                experience_note="",
            )
            return "ok"
        except DomainError as exc:  # a clean 409, not a 500
            return exc.default_code
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = sorted(pool.map(attempt, range(2)))

    assert results == ["ok", "proposal_exists"]
    assert Proposal.objects.filter(campaign=campaign, creator=creator).count() == 1


# ---- the campaign must be open --------------------------------------------------------------------------


def test_submit_to_a_closed_campaign_is_a_conflict(creator, auth_client):
    campaign = CampaignFactory(status=Campaign.Status.CLOSED)

    response = submit(auth_client, creator, campaign)

    assert response.status_code == 409
    assert error_code(response) == "campaign_closed"


def test_submit_after_the_deadline_but_before_the_auto_close_job_is_a_conflict(creator, auth_client):  # RF1
    campaign = CampaignFactory(
        status=Campaign.Status.PUBLISHED, deadline=timezone.now() - timedelta(minutes=1)
    )

    response = submit(auth_client, creator, campaign)

    assert response.status_code == 409
    assert error_code(response) == "campaign_closed"
    assert not Proposal.objects.exists()


def test_submit_to_a_draft_or_missing_campaign_is_404(creator, auth_client):
    draft = CampaignFactory(status=Campaign.Status.DRAFT)

    assert submit(auth_client, creator, draft).status_code == 404
    assert auth_client(creator).post(submit_url(999999), body(), format="json").status_code == 404


# ---- input validation -----------------------------------------------------------------------------------


def test_more_than_three_links_are_rejected(creator, campaign, auth_client):
    links = [f"https://example.com/{n}" for n in range(4)]

    response = submit(auth_client, creator, campaign, portfolio_links=links)

    assert response.status_code == 400
    assert "portfolio_links" in response.json()["error"]["details"]


def test_exactly_three_links_are_accepted(creator, campaign, auth_client):
    links = [f"https://example.com/{n}" for n in range(3)]

    assert submit(auth_client, creator, campaign, portfolio_links=links).status_code == 201


@pytest.mark.parametrize("link", ["javascript:alert(1)", "data:text/html,x", "example.com/p"])
def test_unsafe_links_are_rejected(creator, campaign, auth_client, link):  # RF2
    response = submit(auth_client, creator, campaign, portfolio_links=[link])

    assert response.status_code == 400
    assert "portfolio_links" in response.json()["error"]["details"]


def test_html_is_stripped_from_text_fields(creator, campaign, auth_client):  # RF2
    response = submit(
        auth_client,
        creator,
        campaign,
        cover_message="<script>alert(1)</script>Hello",
        experience_note="<b>Five</b> years",
    )

    data = response.json()
    assert data["cover_message"] == "alert(1)Hello"
    assert data["experience_note"] == "Five years"


@pytest.mark.parametrize("rate", ["0", "-5", "abc"])
def test_proposed_rate_must_be_positive(creator, campaign, auth_client, rate):
    response = submit(auth_client, creator, campaign, proposed_rate=rate)

    assert response.status_code == 400
    assert "proposed_rate" in response.json()["error"]["details"]


@pytest.mark.parametrize("field", ["cover_message", "proposed_rate"])
def test_required_fields(creator, campaign, auth_client, field):
    data = body()
    del data[field]

    response = auth_client(creator).post(submit_url(campaign.pk), data, format="json")

    assert response.status_code == 400
    assert field in response.json()["error"]["details"]


def test_a_proposal_cannot_be_edited(creator, campaign, auth_client):
    proposal = ProposalFactory(campaign=campaign, creator=creator)
    client = auth_client(creator)

    assert client.put(submit_url(campaign.pk), body(), format="json").status_code == 405
    assert client.patch(submit_url(campaign.pk), body(), format="json").status_code == 405
    assert client.patch(f"/api/v1/creators/me/proposals/{proposal.pk}/withdraw/", {"cover_message": "x"}, format="json").status_code == 405


def test_brands_cannot_submit_and_logged_out_gets_401(campaign, auth_client):
    brand = UserFactory(role=Role.BRAND)

    assert auth_client(brand).post(submit_url(campaign.pk), body(), format="json").status_code == 403
    assert APIClient().post(submit_url(campaign.pk), body(), format="json").status_code == 401


# ---- apply state on the campaign detail (FR-12) ---------------------------------------------------------------


def apply_state(auth_client, creator, campaign):
    data = auth_client(creator).get(campaign_url(campaign.pk)).json()
    return data["can_apply"], data["apply_blocked_reason"]


def test_apply_state_with_no_proposal(creator, campaign, auth_client):
    assert apply_state(auth_client, creator, campaign) == (True, None)


@pytest.mark.parametrize("status", [S.PENDING, S.SHORTLISTED, S.ACCEPTED])
def test_apply_state_blocked_by_an_active_proposal(creator, campaign, auth_client, status):
    ProposalFactory(campaign=campaign, creator=creator, status=status)

    assert apply_state(auth_client, creator, campaign) == (False, "active_proposal")


def test_apply_state_blocked_by_a_rejected_proposal(creator, campaign, auth_client):
    ProposalFactory(campaign=campaign, creator=creator, status=S.REJECTED)

    assert apply_state(auth_client, creator, campaign) == (False, "proposal_rejected")


def test_apply_state_reopens_after_withdrawal_while_published(creator, campaign, auth_client):
    ProposalFactory(campaign=campaign, creator=creator, status=S.WITHDRAWN)

    assert apply_state(auth_client, creator, campaign) == (True, None)


def test_apply_state_closed_campaign(creator, auth_client):
    campaign = CampaignFactory(status=Campaign.Status.CLOSED)

    assert apply_state(auth_client, creator, campaign) == (False, "campaign_closed")


def test_apply_state_withdrawn_proposal_on_a_closed_campaign_stays_blocked(creator, auth_client):
    campaign = CampaignFactory(status=Campaign.Status.CLOSED)
    ProposalFactory(campaign=campaign, creator=creator, status=S.WITHDRAWN)

    assert apply_state(auth_client, creator, campaign) == (False, "campaign_closed")


def test_apply_state_published_but_past_deadline_counts_as_closed(creator, auth_client):
    campaign = CampaignFactory(
        status=Campaign.Status.PUBLISHED, deadline=timezone.now() - timedelta(minutes=1)
    )

    assert apply_state(auth_client, creator, campaign) == (False, "campaign_closed")


def test_an_active_proposal_is_reported_even_when_the_campaign_has_closed(creator, auth_client):
    campaign = CampaignFactory(status=Campaign.Status.CLOSED)
    ProposalFactory(campaign=campaign, creator=creator, status=S.ACCEPTED)

    assert apply_state(auth_client, creator, campaign) == (False, "active_proposal")


def test_other_creators_proposals_do_not_block_me(creator, campaign, auth_client):
    ProposalFactory(campaign=campaign, status=S.ACCEPTED)  # someone else's

    assert apply_state(auth_client, creator, campaign) == (True, None)


def test_accepted_count_and_all_creators_selected(creator, auth_client):
    campaign = CampaignFactory(status=Campaign.Status.PUBLISHED, creators_needed=2)
    ProposalFactory(campaign=campaign, status=S.ACCEPTED)
    for status in (S.PENDING, S.SHORTLISTED, S.REJECTED, S.WITHDRAWN):
        ProposalFactory(campaign=campaign, status=status)

    data = auth_client(creator).get(campaign_url(campaign.pk)).json()
    assert (data["accepted_count"], data["all_creators_selected"]) == (1, False)

    ProposalFactory(campaign=campaign, status=S.ACCEPTED)
    data = auth_client(creator).get(campaign_url(campaign.pk)).json()
    assert (data["accepted_count"], data["all_creators_selected"]) == (2, True)


# ---- suspended brands ------------------------------------------------------------------------


def test_applying_to_a_suspended_brands_campaign_is_a_404(creator, auth_client):
    suspended = UserFactory(role=Role.BRAND, is_active=False)
    campaign = CampaignFactory(status=Campaign.Status.PUBLISHED, brand=suspended)

    response = submit(auth_client, creator, campaign)

    assert response.status_code == 404
    assert not Proposal.objects.filter(campaign=campaign).exists()
