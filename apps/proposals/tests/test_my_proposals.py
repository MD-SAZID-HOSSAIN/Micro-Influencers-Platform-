import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Role
from apps.accounts.tests.factories import UserFactory
from apps.campaigns.models import Campaign
from apps.campaigns.tests.factories import CampaignFactory
from apps.profiles.models import BrandProfile
from apps.proposals.models import Proposal
from apps.proposals.tests.factories import ProposalFactory

S = Proposal.Status
LIST = "/api/v1/creators/me/proposals/"


@pytest.fixture
def creator(db):
    return UserFactory(role=Role.CREATOR)


def ids(response):
    return [row["id"] for row in response.json()["results"]]


def test_lists_every_status_including_withdrawn(creator, auth_client):
    mine = [ProposalFactory(creator=creator, status=s) for s in S]

    response = auth_client(creator).get(LIST)

    assert response.status_code == 200
    assert sorted(ids(response)) == sorted(p.id for p in mine)
    assert {row["status"] for row in response.json()["results"]} == {s.value for s in S}


def test_newest_first(creator, auth_client):
    older = ProposalFactory(creator=creator)
    newer = ProposalFactory(creator=creator)

    assert ids(auth_client(creator).get(LIST)) == [newer.id, older.id]


def test_a_resubmission_is_a_separate_entry_next_to_the_withdrawn_one(creator, auth_client):
    campaign = CampaignFactory(status=Campaign.Status.PUBLISHED)
    withdrawn = ProposalFactory(campaign=campaign, creator=creator, status=S.WITHDRAWN)
    resubmitted = ProposalFactory(campaign=campaign, creator=creator, status=S.PENDING)

    results = auth_client(creator).get(LIST).json()["results"]

    assert [(r["id"], r["status"]) for r in results] == [
        (resubmitted.id, "pending"),
        (withdrawn.id, "withdrawn"),
    ]


def test_only_my_own_proposals_are_visible(creator, auth_client):  # RF3
    mine = ProposalFactory(creator=creator)
    ProposalFactory()  # someone else's

    assert ids(auth_client(creator).get(LIST)) == [mine.id]


def test_status_filter(creator, auth_client):
    accepted = ProposalFactory(creator=creator, status=S.ACCEPTED)
    ProposalFactory(creator=creator, status=S.PENDING)
    ProposalFactory(creator=creator, status=S.WITHDRAWN)

    assert ids(auth_client(creator).get(LIST, {"status": "accepted"})) == [accepted.id]
    assert auth_client(creator).get(LIST, {"status": "bogus"}).status_code == 400


def test_a_closed_campaign_is_still_shown(creator, auth_client):
    closed = CampaignFactory(status=Campaign.Status.CLOSED)
    proposal = ProposalFactory(campaign=closed, creator=creator, status=S.ACCEPTED)

    item = auth_client(creator).get(LIST).json()["results"][0]

    assert item["id"] == proposal.id
    assert item["campaign"]["status"] == "closed"


def test_item_shape_is_status_only(creator, auth_client):
    brand = UserFactory(role=Role.BRAND, full_name="Owner")
    BrandProfile.objects.filter(user=brand).update(company_name="Acme Foods")
    campaign = CampaignFactory(brand=brand, status=Campaign.Status.PUBLISHED, title="Summer launch")
    proposal = ProposalFactory(
        campaign=campaign, creator=creator, status=S.WITHDRAWN,
        proposed_rate="275.50", withdrawal_reason="Family emergency",
    )

    item = auth_client(creator).get(LIST).json()["results"][0]

    assert item == {
        "id": proposal.id,
        "status": "withdrawn",
        "proposed_rate": "275.50",
        "created_at": item["created_at"],
        "completed_at": None,
        "withdrawal_reason": "Family emergency",
        "campaign": {
            "id": campaign.id,
            "title": "Summer launch",
            "status": "published",
            "brand": {"id": brand.id, "name": "Acme Foods"},
        },
    }


def test_withdrawal_reason_is_null_when_there_is_none(creator, auth_client):
    ProposalFactory(creator=creator)

    assert auth_client(creator).get(LIST).json()["results"][0]["withdrawal_reason"] is None


def test_empty_list(creator, auth_client):
    body = auth_client(creator).get(LIST).json()

    assert body["results"] == []
    assert body["count"] == 0


def test_the_list_cannot_be_used_to_edit_proposals(creator, auth_client):
    proposal = ProposalFactory(creator=creator)

    assert auth_client(creator).patch(LIST, {"cover_message": "x"}, format="json").status_code == 405
    assert auth_client(creator).post(LIST, {}, format="json").status_code == 405
    assert Proposal.objects.get(pk=proposal.pk).cover_message != "x"


def test_brands_are_rejected_and_logged_out_gets_401(db, auth_client):
    brand = UserFactory(role=Role.BRAND)

    assert auth_client(brand).get(LIST).status_code == 403
    assert APIClient().get(LIST).status_code == 401


def test_query_count_is_constant(creator, auth_client, django_assert_max_num_queries):
    for _ in range(30):
        ProposalFactory(creator=creator)
    client = auth_client(creator)

    with django_assert_max_num_queries(5):
        response = client.get(LIST, {"page_size": 30})

    assert len(response.json()["results"]) == 30
