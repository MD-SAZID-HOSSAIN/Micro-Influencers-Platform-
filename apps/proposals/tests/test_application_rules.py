"""The brand's minimum followers is a requirement, and a suspended creator cannot be accepted."""
import pytest

from apps.accounts.models import Role
from apps.accounts.tests.factories import UserFactory
from apps.campaigns.models import Campaign
from apps.campaigns.tests.factories import CampaignFactory
from apps.proposals.models import Proposal
from apps.proposals.tests.factories import ProposalFactory
from apps.social.models import PlatformStats

BODY = {"cover_message": "Hello", "portfolio_links": [], "experience_note": ""}


def apply_to(auth_client, creator, campaign):
    return auth_client(creator).post(f"/api/v1/campaigns/{campaign.pk}/proposals/", BODY, format="json")


def error_code(response):
    return response.json()["error"]["code"]


@pytest.fixture
def creator(db):
    return UserFactory(role=Role.CREATOR, youtube_verified=True)  # 10,000 YouTube subscribers


# ---- minimum followers ---------------------------------------------------------------------------------


def test_a_creator_under_the_minimum_cannot_apply(creator, auth_client):
    campaign = CampaignFactory(status=Campaign.Status.PUBLISHED, platform="youtube", min_followers=50_000)

    response = apply_to(auth_client, creator, campaign)

    assert response.status_code == 403 and error_code(response) == "not_eligible"
    assert "50,000" in response.json()["error"]["message"] and "10,000" in response.json()["error"]["message"]
    assert not Proposal.objects.filter(creator=creator).exists()


@pytest.mark.parametrize("minimum", [None, 1_000, 10_000])
def test_a_creator_at_or_over_the_minimum_can_apply(creator, auth_client, minimum):
    campaign = CampaignFactory(status=Campaign.Status.PUBLISHED, platform="youtube", min_followers=minimum)

    assert apply_to(auth_client, creator, campaign).status_code == 201


def test_approved_numbers_on_the_campaign_platform_must_reach_the_minimum(creator, auth_client):
    PlatformStats.objects.create(
        creator=creator, platform="instagram", followers=1_000, engagement_rate="3.00", is_verified=True
    )
    campaign = CampaignFactory(status=Campaign.Status.PUBLISHED, platform="instagram", min_followers=5_000)

    response = apply_to(auth_client, creator, campaign)

    assert response.status_code == 403 and error_code(response) == "not_eligible"


def test_numbers_an_admin_has_not_approved_do_not_count_either_way(creator, auth_client):
    PlatformStats.objects.create(
        creator=creator, platform="instagram", followers=900_000, engagement_rate="3.00", is_verified=False,
        review_status="pending",
    )
    campaign = CampaignFactory(status=Campaign.Status.PUBLISHED, platform="instagram", min_followers=5_000)

    # No visible Instagram numbers, so nothing to compare: a verified YouTube creator may apply to any platform.
    assert apply_to(auth_client, creator, campaign).status_code == 201


def test_a_verified_youtube_creator_may_still_apply_to_another_platform(creator, auth_client):
    campaign = CampaignFactory(status=Campaign.Status.PUBLISHED, platform="tiktok", min_followers=100_000)

    assert apply_to(auth_client, creator, campaign).status_code == 201


# ---- suspended creators -----------------------------------------------------------------------------------


def test_a_suspended_creators_proposal_cannot_be_accepted(db, auth_client):
    campaign = CampaignFactory(status=Campaign.Status.PUBLISHED, creators_needed=2)
    proposal = ProposalFactory(campaign=campaign, status=Proposal.Status.PENDING)
    type(proposal.creator).objects.filter(pk=proposal.creator.pk).update(is_active=False)

    response = auth_client(campaign.brand).post(f"/api/v1/brand/proposals/{proposal.pk}/accept/")

    assert response.status_code == 409 and error_code(response) == "creator_unavailable"
    proposal.refresh_from_db()
    assert proposal.status == Proposal.Status.PENDING


def test_a_suspended_creators_proposal_can_still_be_rejected(db, auth_client):
    campaign = CampaignFactory(status=Campaign.Status.PUBLISHED, creators_needed=2)
    proposal = ProposalFactory(campaign=campaign, status=Proposal.Status.PENDING)
    type(proposal.creator).objects.filter(pk=proposal.creator.pk).update(is_active=False)

    response = auth_client(campaign.brand).post(f"/api/v1/brand/proposals/{proposal.pk}/reject/")

    assert response.status_code == 200
