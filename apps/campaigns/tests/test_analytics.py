from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Role
from apps.accounts.tests.factories import UserFactory
from apps.campaigns.models import Campaign, CampaignView
from apps.campaigns.tests.factories import CampaignFactory
from apps.proposals.models import Proposal
from apps.proposals.tests.factories import ProposalFactory

S = Proposal.Status


def analytics_url(pk):
    return f"/api/v1/brand/campaigns/{pk}/analytics/"


def detail_url(pk):
    return f"/api/v1/campaigns/{pk}/"


@pytest.fixture
def campaign(db):
    return CampaignFactory(status=Campaign.Status.PUBLISHED, creators_needed=3, budget=Decimal("500.00"))


def metrics(auth_client, campaign):
    response = auth_client(campaign.brand).get(analytics_url(campaign.pk))
    assert response.status_code == 200
    return response.json()


# ---- the empty state -----------------------------------------------------------------------------------


def test_a_campaign_nobody_has_seen_or_applied_to(campaign, auth_client):
    assert metrics(auth_client, campaign) == {
        "views": 0,
        "funnel": {"received": 0, "shortlisted": 0, "accepted": 0, "rejected": 0, "withdrawn": 0},
        "accepted_vs_needed": {"accepted": 0, "needed": 3},
        "avg_proposed_rate": None,
        "budget_per_creator": "500.00",
        "acceptance_rate": None,
    }


# ---- the proposal funnel ----------------------------------------------------------------------------------


def test_funnel_counts_by_current_status_and_received_includes_withdrawn(campaign, auth_client):
    for status in (S.PENDING, S.PENDING, S.SHORTLISTED, S.ACCEPTED, S.ACCEPTED, S.REJECTED, S.WITHDRAWN):
        ProposalFactory(campaign=campaign, status=status)

    funnel = metrics(auth_client, campaign)["funnel"]

    assert funnel == {"received": 7, "shortlisted": 1, "accepted": 2, "rejected": 1, "withdrawn": 1}


def test_accepted_versus_needed(campaign, auth_client):
    ProposalFactory(campaign=campaign, status=S.ACCEPTED)
    ProposalFactory(campaign=campaign, status=S.ACCEPTED)

    assert metrics(auth_client, campaign)["accepted_vs_needed"] == {"accepted": 2, "needed": 3}


def test_acceptance_rate_is_accepted_over_received(campaign, auth_client):
    ProposalFactory(campaign=campaign, status=S.ACCEPTED)
    for status in (S.PENDING, S.REJECTED, S.SHORTLISTED):
        ProposalFactory(campaign=campaign, status=status)

    assert metrics(auth_client, campaign)["acceptance_rate"] == 0.25


def test_an_accepted_then_withdrawn_proposal_counts_as_received_but_not_accepted(campaign, auth_client):
    ProposalFactory(campaign=campaign, status=S.ACCEPTED)
    ProposalFactory(campaign=campaign, status=S.WITHDRAWN, withdrawal_reason="Sorry")  # was accepted, now gone

    body = metrics(auth_client, campaign)

    assert body["funnel"]["received"] == 2 and body["funnel"]["accepted"] == 1
    assert body["acceptance_rate"] == 0.5


def test_acceptance_rate_is_rounded_to_four_places(campaign, auth_client):
    ProposalFactory(campaign=campaign, status=S.ACCEPTED)
    ProposalFactory(campaign=campaign, status=S.PENDING)
    ProposalFactory(campaign=campaign, status=S.PENDING)

    assert metrics(auth_client, campaign)["acceptance_rate"] == 0.3333


def test_average_proposed_rate_is_compared_with_the_budget_per_creator(campaign, auth_client):
    ProposalFactory(campaign=campaign, proposed_rate=Decimal("400.00"))
    ProposalFactory(campaign=campaign, proposed_rate=Decimal("650.50"), status=S.REJECTED)
    ProposalFactory(campaign=campaign, proposed_rate=Decimal("300.00"), status=S.WITHDRAWN)

    body = metrics(auth_client, campaign)

    assert body["avg_proposed_rate"] == "450.17"
    assert body["budget_per_creator"] == "500.00"


def test_other_campaigns_proposals_are_not_counted(campaign, auth_client):
    ProposalFactory(campaign=campaign)
    ProposalFactory(campaign=CampaignFactory(brand=campaign.brand, status=Campaign.Status.PUBLISHED))

    assert metrics(auth_client, campaign)["funnel"]["received"] == 1


# ---- views --------------------------------------------------------------------------------------------------


def test_a_creator_opening_the_campaign_counts_a_view(campaign, auth_client):
    creator = UserFactory(role=Role.CREATOR)

    auth_client(creator).get(detail_url(campaign.pk))

    assert metrics(auth_client, campaign)["views"] == 1
    assert CampaignView.objects.get(campaign=campaign, creator=creator).view_count == 1


def test_repeat_views_by_the_same_creator_add_to_the_count_not_to_the_rows(campaign, auth_client):
    creator = UserFactory(role=Role.CREATOR)
    client = auth_client(creator)

    for _ in range(3):
        client.get(detail_url(campaign.pk))

    assert CampaignView.objects.filter(campaign=campaign).count() == 1
    assert metrics(auth_client, campaign)["views"] == 3


def test_views_add_up_across_creators(campaign, auth_client):
    for _ in range(4):
        auth_client(UserFactory(role=Role.CREATOR)).get(detail_url(campaign.pk))

    assert metrics(auth_client, campaign)["views"] == 4


def test_views_of_a_closed_campaign_still_count_but_drafts_and_the_list_do_not(db, auth_client):
    closed = CampaignFactory(status=Campaign.Status.CLOSED)
    draft = CampaignFactory(status=Campaign.Status.DRAFT)
    creator = UserFactory(role=Role.CREATOR)
    client = auth_client(creator)

    client.get(detail_url(closed.pk))
    assert client.get(detail_url(draft.pk)).status_code == 404
    client.get("/api/v1/campaigns/")  # browsing the list is not opening a campaign

    assert CampaignView.objects.filter(campaign=closed).count() == 1
    assert not CampaignView.objects.filter(campaign=draft).exists()
    assert CampaignView.objects.count() == 1


def test_the_brand_looking_at_its_own_campaign_is_not_a_view(campaign, auth_client):
    auth_client(campaign.brand).get(f"/api/v1/brand/campaigns/{campaign.pk}/")
    auth_client(campaign.brand).get(analytics_url(campaign.pk))

    assert not CampaignView.objects.exists()


@pytest.mark.django_db(transaction=True)
def test_simultaneous_views_by_one_creator_are_all_counted():
    from concurrent.futures import ThreadPoolExecutor

    from django.db import connection

    from apps.accounts.services import issue_access_token

    campaign = CampaignFactory(status=Campaign.Status.PUBLISHED)
    creator = UserFactory(role=Role.CREATOR)
    token = issue_access_token(creator)

    def open_campaign(_):
        try:
            client = APIClient()
            client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
            return client.get(detail_url(campaign.pk)).status_code
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=6) as pool:
        statuses = list(pool.map(open_campaign, range(6)))

    assert statuses == [200] * 6
    assert CampaignView.objects.get(campaign=campaign, creator=creator).view_count == 6


# ---- access -----------------------------------------------------------------------------------------------------


def test_another_brands_analytics_are_404(campaign, auth_client):  # RF3
    stranger = UserFactory(role=Role.BRAND)

    assert auth_client(stranger).get(analytics_url(campaign.pk)).status_code == 404
    assert auth_client(stranger).get(analytics_url(999999)).status_code == 404


def test_creators_and_logged_out_visitors_are_rejected(campaign, auth_client):
    creator = UserFactory(role=Role.CREATOR)

    assert auth_client(creator).get(analytics_url(campaign.pk)).status_code == 403
    assert APIClient().get(analytics_url(campaign.pk)).status_code == 401


def test_the_proposal_metrics_cost_a_constant_number_of_queries(campaign, auth_client, django_assert_max_num_queries):
    for _ in range(25):
        ProposalFactory(campaign=campaign)
    client = auth_client(campaign.brand)

    with django_assert_max_num_queries(5):
        response = client.get(analytics_url(campaign.pk))

    assert response.json()["funnel"]["received"] == 25
