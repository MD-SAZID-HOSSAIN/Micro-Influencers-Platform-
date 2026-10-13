import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Role
from apps.accounts.tests.factories import UserFactory
from apps.campaigns.models import Campaign
from apps.campaigns.tests.factories import CampaignFactory
from apps.proposals.models import Proposal
from apps.proposals.tests.factories import ProposalFactory

S = Proposal.Status
URL = "/api/v1/brands/me/dashboard/"


@pytest.fixture
def brand(db):
    return UserFactory(role=Role.BRAND)


def dashboard(auth_client, brand):
    response = auth_client(brand).get(URL)
    assert response.status_code == 200
    return response.json()


def campaign_of(brand, status=Campaign.Status.PUBLISHED, **kwargs):
    return CampaignFactory(brand=brand, status=status, **kwargs)


def test_empty_brand_dashboard_is_all_zero(brand, auth_client):
    assert dashboard(auth_client, brand) == {
        "total_campaigns": 0,
        "active_campaigns": 0,
        "total_proposals": 0,
        "shortlisted_count": 0,
        "accepted_count": 0,
        "campaigns": [],
    }


def test_active_campaigns_counts_only_published(brand, auth_client):
    campaign_of(brand, Campaign.Status.PUBLISHED)
    campaign_of(brand, Campaign.Status.PUBLISHED)
    campaign_of(brand, Campaign.Status.DRAFT)
    campaign_of(brand, Campaign.Status.CLOSED)

    body = dashboard(auth_client, brand)

    assert body["total_campaigns"] == 4
    assert body["active_campaigns"] == 2


def test_total_proposals_includes_withdrawn(brand, auth_client):
    campaign = campaign_of(brand)
    for status in S:
        ProposalFactory(campaign=campaign, status=status)

    assert dashboard(auth_client, brand)["total_proposals"] == 5


def test_total_proposals_spans_all_of_the_brands_campaigns(brand, auth_client):
    ProposalFactory(campaign=campaign_of(brand))
    ProposalFactory(campaign=campaign_of(brand, Campaign.Status.CLOSED))

    assert dashboard(auth_client, brand)["total_proposals"] == 2


def test_shortlisted_and_accepted_counts_reflect_only_the_current_status(brand, auth_client):
    campaign = campaign_of(brand, creators_needed=5)
    ProposalFactory(campaign=campaign, status=S.SHORTLISTED)
    ProposalFactory(campaign=campaign, status=S.SHORTLISTED)
    ProposalFactory(campaign=campaign, status=S.ACCEPTED)
    ProposalFactory(campaign=campaign, status=S.WITHDRAWN, withdrawal_reason="Sorry")  # was accepted
    ProposalFactory(campaign=campaign, status=S.REJECTED)

    body = dashboard(auth_client, brand)

    assert body["shortlisted_count"] == 2
    assert body["accepted_count"] == 1


def test_campaign_rows_link_to_each_proposal_list_newest_first(brand, auth_client):
    older = campaign_of(brand, title="Older", creators_needed=3)
    newer = campaign_of(brand, Campaign.Status.DRAFT, title="Newer")
    ProposalFactory(campaign=older, status=S.ACCEPTED)
    ProposalFactory(campaign=older, status=S.PENDING)
    ProposalFactory(campaign=older, status=S.WITHDRAWN)

    rows = dashboard(auth_client, brand)["campaigns"]

    assert [r["id"] for r in rows] == [newer.id, older.id]
    assert rows[1] == {
        "id": older.id,
        "title": "Older",
        "status": "published",
        "proposals_url": f"/api/v1/brand/campaigns/{older.id}/proposals/",
        "proposal_count": 3,
        "accepted_count": 1,
        "creators_needed": 3,
    }
    assert rows[0]["proposal_count"] == 0
    assert rows[0]["proposals_url"].endswith(f"/{newer.id}/proposals/")


def test_other_brands_data_is_excluded(brand, auth_client):  # RF3
    mine = campaign_of(brand)
    ProposalFactory(campaign=mine, status=S.ACCEPTED)
    stranger = CampaignFactory(status=Campaign.Status.PUBLISHED)
    for status in (S.ACCEPTED, S.SHORTLISTED, S.PENDING):
        ProposalFactory(campaign=stranger, status=status)

    body = dashboard(auth_client, brand)

    assert body["total_campaigns"] == 1
    assert body["total_proposals"] == 1
    assert body["accepted_count"] == 1
    assert body["shortlisted_count"] == 0
    assert [r["id"] for r in body["campaigns"]] == [mine.id]


def test_rows_are_capped_at_fifty_but_totals_cover_everything(brand, auth_client):
    for _ in range(55):
        campaign_of(brand, Campaign.Status.DRAFT)

    body = dashboard(auth_client, brand)

    assert body["total_campaigns"] == 55
    assert len(body["campaigns"]) == 50


def test_creators_are_rejected_and_logged_out_gets_401(db, auth_client):
    creator = UserFactory(role=Role.CREATOR)

    assert auth_client(creator).get(URL).status_code == 403
    assert APIClient().get(URL).status_code == 401


def test_query_count_is_constant_for_twenty_campaigns(brand, auth_client, django_assert_max_num_queries):
    for _ in range(20):
        campaign = campaign_of(brand, creators_needed=3)
        for status in (S.PENDING, S.ACCEPTED, S.SHORTLISTED):
            ProposalFactory(campaign=campaign, status=status)
    client = auth_client(brand)

    with django_assert_max_num_queries(6):
        response = client.get(URL)

    assert len(response.json()["campaigns"]) == 20
