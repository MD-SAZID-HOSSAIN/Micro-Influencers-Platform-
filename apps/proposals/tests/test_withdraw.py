import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Role
from apps.accounts.tests.factories import UserFactory
from apps.campaigns.models import Campaign
from apps.campaigns.tests.factories import CampaignFactory
from apps.notifications.models import Kind, Notification
from apps.proposals.models import Proposal
from apps.proposals.tests.factories import ProposalFactory

S = Proposal.Status


def withdraw_url(pk):
    return f"/api/v1/creators/me/proposals/{pk}/withdraw/"


@pytest.fixture
def creator(db):
    return UserFactory(role=Role.CREATOR, full_name="Amina Rahman")


def withdraw(auth_client, creator, proposal, **body):
    return auth_client(creator).post(withdraw_url(proposal.pk), body, format="json")


def error_code(response):
    return response.json()["error"]["code"]


def reload(proposal):
    proposal.refresh_from_db()
    return proposal


@pytest.mark.parametrize("status", [S.PENDING, S.SHORTLISTED])
def test_withdraw_before_acceptance_needs_no_reason(creator, auth_client, status):
    proposal = ProposalFactory(creator=creator, status=status)

    response = withdraw(auth_client, creator, proposal)

    assert response.status_code == 200
    assert response.json()["status"] == "withdrawn"
    assert reload(proposal).status == S.WITHDRAWN


def test_withdraw_accepted_requires_a_reason(creator, auth_client):
    proposal = ProposalFactory(creator=creator, status=S.ACCEPTED)

    for body in ({}, {"reason": ""}, {"reason": "   "}):
        response = withdraw(auth_client, creator, proposal, **body)
        assert response.status_code == 400
        assert "reason" in response.json()["error"]["details"]
    assert reload(proposal).status == S.ACCEPTED


def test_withdraw_accepted_with_a_reason_stores_it(creator, auth_client):
    proposal = ProposalFactory(creator=creator, status=S.ACCEPTED)

    response = withdraw(auth_client, creator, proposal, reason="Family emergency")

    assert response.status_code == 200
    assert response.json()["withdrawal_reason"] == "Family emergency"
    assert reload(proposal).withdrawal_reason == "Family emergency"


@pytest.mark.parametrize("length, ok", [(300, True), (301, False)])
def test_withdrawal_reason_is_limited_to_300_characters(creator, auth_client, length, ok):
    proposal = ProposalFactory(creator=creator, status=S.ACCEPTED)

    response = withdraw(auth_client, creator, proposal, reason="x" * length)

    assert (response.status_code == 200) is ok


def test_html_in_the_reason_is_stripped(creator, auth_client):
    proposal = ProposalFactory(creator=creator, status=S.ACCEPTED)

    response = withdraw(auth_client, creator, proposal, reason="<script>x</script>Sorry")

    assert response.json()["withdrawal_reason"] == "xSorry"


@pytest.mark.parametrize("status", [S.REJECTED, S.WITHDRAWN])
def test_rejected_and_already_withdrawn_proposals_cannot_be_withdrawn(creator, auth_client, status):
    proposal = ProposalFactory(creator=creator, status=status)

    response = withdraw(auth_client, creator, proposal, reason="x")

    assert response.status_code == 409
    assert error_code(response) == "invalid_transition"
    assert reload(proposal).status == status


def test_withdrawing_an_accepted_proposal_tells_the_brand_a_slot_opened(creator, auth_client):
    proposal = ProposalFactory(creator=creator, status=S.ACCEPTED)

    withdraw(auth_client, creator, proposal, reason="Sorry")

    note = Notification.objects.get(user=proposal.campaign.brand)
    assert note.kind == Kind.PROPOSAL_WITHDRAWN
    assert note.payload == {
        "campaign_id": proposal.campaign_id,
        "proposal_id": proposal.id,
        "slot_opened": True,
    }
    assert "slot" in note.message.lower()


def test_withdrawing_a_pending_proposal_does_not_claim_a_slot_opened(creator, auth_client):
    proposal = ProposalFactory(creator=creator, status=S.PENDING)

    withdraw(auth_client, creator, proposal)

    note = Notification.objects.get(user=proposal.campaign.brand)
    assert note.payload["slot_opened"] is False
    assert "slot" not in note.message.lower()


def test_withdrawal_is_allowed_after_the_campaign_closed(creator, auth_client):
    campaign = CampaignFactory(status=Campaign.Status.CLOSED)
    proposal = ProposalFactory(campaign=campaign, creator=creator, status=S.ACCEPTED)

    assert withdraw(auth_client, creator, proposal, reason="Cannot make it").status_code == 200


def test_cannot_withdraw_another_creators_proposal(creator, auth_client):  # RF3
    someone_elses = ProposalFactory(status=S.PENDING)

    response = withdraw(auth_client, creator, someone_elses)

    assert response.status_code == 404
    assert reload(someone_elses).status == S.PENDING


def test_unknown_proposal_is_404(creator, auth_client):
    assert auth_client(creator).post(withdraw_url(999999), {}, format="json").status_code == 404


def test_brands_cannot_withdraw_and_logged_out_gets_401(creator):
    proposal = ProposalFactory(creator=creator)
    brand = proposal.campaign.brand
    from apps.accounts.services import issue_access_token

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {issue_access_token(brand)}")

    assert client.post(withdraw_url(proposal.pk), {}, format="json").status_code == 403
    assert APIClient().post(withdraw_url(proposal.pk), {}, format="json").status_code == 401


# ---- the brand's choice when it posts: may creators withdraw? ------------------------------------------------


@pytest.mark.parametrize("status", [S.PENDING, S.SHORTLISTED, S.ACCEPTED])
def test_a_creator_cannot_withdraw_when_the_brand_turned_withdrawing_off(creator, auth_client, status):
    campaign = CampaignFactory(status=Campaign.Status.PUBLISHED, allow_withdrawal=False)
    proposal = ProposalFactory(creator=creator, campaign=campaign, status=status)

    response = withdraw(auth_client, creator, proposal, reason="Changed my mind")

    assert response.status_code == 403
    assert error_code(response) == "withdrawal_not_allowed"
    assert reload(proposal).status == status
    assert not Notification.objects.filter(user=campaign.brand, kind=Kind.PROPOSAL_WITHDRAWN).exists()


def test_withdrawing_is_allowed_by_default(creator, auth_client):
    campaign = CampaignFactory(status=Campaign.Status.PUBLISHED)
    proposal = ProposalFactory(creator=creator, campaign=campaign, status=S.PENDING)

    assert campaign.allow_withdrawal is True
    assert withdraw(auth_client, creator, proposal).status_code == 200
    assert reload(proposal).status == S.WITHDRAWN


def test_the_creators_own_list_says_whether_each_campaign_allows_withdrawing(creator, auth_client):
    locked = ProposalFactory(creator=creator, campaign=CampaignFactory(allow_withdrawal=False))
    open_one = ProposalFactory(creator=creator, campaign=CampaignFactory(allow_withdrawal=True))

    rows = auth_client(creator).get("/api/v1/creators/me/proposals/").json()["results"]

    flags = {row["id"]: row["campaign"]["allow_withdrawal"] for row in rows}
    assert flags == {locked.id: False, open_one.id: True}
