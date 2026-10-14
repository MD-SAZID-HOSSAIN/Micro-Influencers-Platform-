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
FULL_MESSAGE = "All creators for this campaign have already been selected."


def action_url(pk, action):
    return f"/api/v1/brand/proposals/{pk}/{action}/"


@pytest.fixture
def brand(db):
    return UserFactory(role=Role.BRAND)


@pytest.fixture
def campaign(brand):
    return CampaignFactory(
        brand=brand, status=Campaign.Status.PUBLISHED, creators_needed=2, title="Summer launch"
    )


def act(auth_client, brand, proposal, action):
    return auth_client(brand).post(action_url(proposal.pk, action))


def reload(proposal):
    proposal.refresh_from_db()
    return proposal


def error_code(response):
    return response.json()["error"]["code"]


# ---- the full transition matrix ---------------------------------------------------------------------

TARGET = {"shortlist": S.SHORTLISTED, "accept": S.ACCEPTED, "reject": S.REJECTED}
ALLOWED = {
    S.PENDING: {"shortlist", "accept", "reject"},
    S.SHORTLISTED: {"accept", "reject"},
    S.ACCEPTED: {"accept"},  # idempotent: stays Accepted
    S.REJECTED: set(),
    S.WITHDRAWN: set(),
}


@pytest.mark.parametrize("status", list(S))
@pytest.mark.parametrize("action", ["shortlist", "accept", "reject"])
def test_transition_matrix(brand, campaign, auth_client, status, action):
    proposal = ProposalFactory(campaign=campaign, status=status)

    response = act(auth_client, brand, proposal, action)

    if action in ALLOWED[status]:
        assert response.status_code == 200
        assert reload(proposal).status == TARGET[action]
        assert response.json()["status"] == TARGET[action].value
    else:
        assert response.status_code == 409
        assert error_code(response) == "invalid_transition"
        assert reload(proposal).status == status


def test_withdrawn_proposals_cannot_be_acted_on_and_creator_is_not_notified(brand, campaign, auth_client):
    proposal = ProposalFactory(campaign=campaign, status=S.WITHDRAWN)

    act(auth_client, brand, proposal, "accept")

    assert not Notification.objects.filter(user=proposal.creator).exists()


# ---- notifications ------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "action, kind",
    [
        ("shortlist", Kind.PROPOSAL_SHORTLISTED),
        ("accept", Kind.PROPOSAL_ACCEPTED),
        ("reject", Kind.PROPOSAL_REJECTED),
    ],
)
def test_each_action_notifies_the_creator(brand, campaign, auth_client, action, kind):
    proposal = ProposalFactory(campaign=campaign)

    act(auth_client, brand, proposal, action)

    note = Notification.objects.get(user=proposal.creator)
    assert note.kind == kind
    assert "Summer launch" in note.message
    assert note.payload == {"campaign_id": campaign.id, "proposal_id": proposal.id}


def test_a_blocked_action_leaves_no_notification_behind(brand, auth_client):
    full = CampaignFactory(brand=brand, status=Campaign.Status.PUBLISHED, creators_needed=1)
    ProposalFactory(campaign=full, status=S.ACCEPTED)
    blocked = ProposalFactory(campaign=full, status=S.PENDING)

    response = act(auth_client, brand, blocked, "accept")

    assert response.status_code == 409
    assert not Notification.objects.filter(user=blocked.creator).exists()
    assert reload(blocked).status == S.PENDING


# ---- campaign state ---------------------------------------------------------------------------------------


def test_actions_remain_available_after_the_campaign_closed(brand, auth_client):
    closed = CampaignFactory(brand=brand, status=Campaign.Status.CLOSED, creators_needed=3)
    proposals = [ProposalFactory(campaign=closed) for _ in range(3)]

    assert act(auth_client, brand, proposals[0], "shortlist").status_code == 200
    assert act(auth_client, brand, proposals[1], "accept").status_code == 200
    assert act(auth_client, brand, proposals[2], "reject").status_code == 200


# ---- capacity ------------------------------------------------------------------------------------------------


def test_accept_is_blocked_when_the_campaign_is_full(brand, auth_client):
    full = CampaignFactory(brand=brand, status=Campaign.Status.PUBLISHED, creators_needed=2)
    ProposalFactory(campaign=full, status=S.ACCEPTED)
    ProposalFactory(campaign=full, status=S.ACCEPTED)
    blocked = ProposalFactory(campaign=full, status=S.PENDING)

    response = act(auth_client, brand, blocked, "accept")

    assert response.status_code == 409
    assert error_code(response) == "campaign_full"
    assert response.json()["error"]["message"] == FULL_MESSAGE
    assert reload(blocked).status == S.PENDING


def test_shortlist_and_reject_still_work_on_a_full_campaign(brand, auth_client):
    full = CampaignFactory(brand=brand, status=Campaign.Status.PUBLISHED, creators_needed=1)
    ProposalFactory(campaign=full, status=S.ACCEPTED)
    to_shortlist = ProposalFactory(campaign=full, status=S.PENDING)
    to_reject = ProposalFactory(campaign=full, status=S.PENDING)

    assert act(auth_client, brand, to_shortlist, "shortlist").status_code == 200
    assert act(auth_client, brand, to_reject, "reject").status_code == 200


def test_a_shortlisted_proposal_cannot_be_accepted_into_a_full_campaign(brand, auth_client):
    full = CampaignFactory(brand=brand, status=Campaign.Status.PUBLISHED, creators_needed=1)
    ProposalFactory(campaign=full, status=S.ACCEPTED)
    shortlisted = ProposalFactory(campaign=full, status=S.SHORTLISTED)

    assert error_code(act(auth_client, brand, shortlisted, "accept")) == "campaign_full"


def test_withdrawal_of_an_accepted_creator_frees_the_slot_even_after_the_campaign_closed(
    brand, auth_client
):
    campaign = CampaignFactory(brand=brand, status=Campaign.Status.PUBLISHED, creators_needed=1)
    accepted = ProposalFactory(campaign=campaign, status=S.ACCEPTED)
    waiting = ProposalFactory(campaign=campaign, status=S.PENDING)
    assert error_code(act(auth_client, brand, waiting, "accept")) == "campaign_full"

    Campaign.objects.filter(pk=campaign.pk).update(status=Campaign.Status.CLOSED)
    creator_client = APIClient()
    from apps.accounts.services import issue_access_token

    creator_client.credentials(HTTP_AUTHORIZATION=f"Bearer {issue_access_token(accepted.creator)}")
    withdrawal = creator_client.post(
        f"/api/v1/creators/me/proposals/{accepted.pk}/withdraw/", {"reason": "Cannot make it"}, format="json"
    )
    assert withdrawal.status_code == 200

    response = act(auth_client, brand, waiting, "accept")

    assert response.status_code == 200
    assert response.json()["accepted_count"] == 1


# ---- idempotency ------------------------------------------------------------------------------------------------


def test_double_click_accept_counts_once_with_no_error_and_one_notification(brand, campaign, auth_client):
    proposal = ProposalFactory(campaign=campaign)

    first = act(auth_client, brand, proposal, "accept")
    second = act(auth_client, brand, proposal, "accept")

    assert first.status_code == second.status_code == 200
    assert first.json()["accepted_count"] == second.json()["accepted_count"] == 1
    assert Proposal.objects.filter(campaign=campaign, status=S.ACCEPTED).count() == 1
    assert Notification.objects.filter(user=proposal.creator).count() == 1


def test_accepting_an_already_accepted_proposal_works_even_when_the_campaign_is_full(brand, auth_client):
    full = CampaignFactory(brand=brand, status=Campaign.Status.PUBLISHED, creators_needed=1)
    accepted = ProposalFactory(campaign=full, status=S.ACCEPTED)

    response = act(auth_client, brand, accepted, "accept")

    assert response.status_code == 200
    assert response.json()["status"] == "accepted"


# ---- result body ----------------------------------------------------------------------------------------------------


def test_response_carries_the_updated_counter(brand, campaign, auth_client):
    first, second = ProposalFactory(campaign=campaign), ProposalFactory(campaign=campaign)

    one = act(auth_client, brand, first, "accept").json()
    two = act(auth_client, brand, second, "accept").json()

    assert (one["id"], one["accepted_count"], one["creators_needed"]) == (first.id, 1, 2)
    assert two["accepted_count"] == 2


# ---- access ----------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("action", ["shortlist", "accept", "reject"])
def test_another_brands_proposal_is_404(brand, auth_client, action):  # RF3
    foreign = ProposalFactory()

    response = act(auth_client, brand, foreign, action)

    assert response.status_code == 404
    assert reload(foreign).status == S.PENDING
    assert not Notification.objects.filter(user=foreign.creator).exists()


def test_unknown_proposal_is_404(brand, auth_client):
    assert auth_client(brand).post(action_url(999999, "accept")).status_code == 404


def test_creators_cannot_act_on_proposals(campaign, auth_client):
    proposal = ProposalFactory(campaign=campaign)

    assert act(auth_client, proposal.creator, proposal, "accept").status_code == 403
    assert APIClient().post(action_url(proposal.pk, "accept")).status_code == 401
    assert reload(proposal).status == S.PENDING


def test_actions_are_post_only(brand, campaign, auth_client):
    proposal = ProposalFactory(campaign=campaign)

    assert auth_client(brand).get(action_url(proposal.pk, "accept")).status_code == 405
