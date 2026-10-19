"""Brands need a verified email to publish and accept; creators need a connected YouTube channel to apply."""
import pytest

from apps.accounts.models import Role
from apps.accounts.tests.factories import UserFactory
from apps.campaigns.models import Campaign
from apps.campaigns.tests.factories import CampaignFactory
from apps.proposals.models import Proposal
from apps.proposals.tests.factories import ProposalFactory
from apps.social.models import PlatformStats

CAMPAIGNS = "/api/v1/brand/campaigns/"
PROPOSAL_BODY = {"cover_message": "Hello", "proposed_rate": "100"}


def error_code(response):
    return response.json()["error"]["code"]


def apply_to(auth_client, creator, campaign):
    return auth_client(creator).post(
        f"/api/v1/campaigns/{campaign.pk}/proposals/", PROPOSAL_BODY, format="json"
    )


# ---- brands: email verification --------------------------------------------------------------------


@pytest.fixture
def unverified_brand(db):
    return UserFactory(role=Role.BRAND, email_verified=False)


def test_unverified_brand_cannot_publish(unverified_brand, auth_client):
    draft = CampaignFactory(brand=unverified_brand)

    response = auth_client(unverified_brand).post(f"{CAMPAIGNS}{draft.pk}/publish/")

    assert response.status_code == 403
    assert error_code(response) == "brand_email_unverified"
    draft.refresh_from_db()
    assert draft.status == Campaign.Status.DRAFT and draft.published_at is None


def test_brand_can_publish_once_email_is_verified(unverified_brand, auth_client):
    draft = CampaignFactory(brand=unverified_brand)
    unverified_brand.email_verified = True
    unverified_brand.save(update_fields=["email_verified"])

    response = auth_client(unverified_brand).post(f"{CAMPAIGNS}{draft.pk}/publish/")

    assert response.status_code == 200
    draft.refresh_from_db()
    assert draft.status == Campaign.Status.PUBLISHED


def test_unverified_brand_can_still_save_edit_and_delete_drafts(unverified_brand, auth_client):
    created = auth_client(unverified_brand).post(
        CAMPAIGNS,
        {
            "title": "Draft",
            "description": "Promote our product.",
            "niche": "fitness",
            "platform": "instagram",
            "budget": "100.00",
            "deadline": "2099-01-01T00:00:00Z",
            "deliverables": "1 post",
        },
        format="json",
    )
    assert created.status_code == 201
    pk = created.json()["id"]

    assert auth_client(unverified_brand).patch(f"{CAMPAIGNS}{pk}/", {"title": "New"}, format="json").status_code == 200
    assert auth_client(unverified_brand).delete(f"{CAMPAIGNS}{pk}/").status_code == 204


@pytest.mark.parametrize("status", [Proposal.Status.PENDING, Proposal.Status.SHORTLISTED])
def test_unverified_brand_cannot_accept(unverified_brand, auth_client, status):
    campaign = CampaignFactory(brand=unverified_brand, status=Campaign.Status.PUBLISHED, creators_needed=2)
    proposal = ProposalFactory(campaign=campaign, status=status)

    response = auth_client(unverified_brand).post(f"/api/v1/brand/proposals/{proposal.pk}/accept/")

    assert response.status_code == 403
    assert error_code(response) == "brand_email_unverified"
    proposal.refresh_from_db()
    assert proposal.status == status


def test_unverified_brand_can_still_shortlist_and_reject(unverified_brand, auth_client):
    campaign = CampaignFactory(brand=unverified_brand, status=Campaign.Status.PUBLISHED, creators_needed=2)
    first, second = ProposalFactory.create_batch(2, campaign=campaign)

    assert auth_client(unverified_brand).post(f"/api/v1/brand/proposals/{first.pk}/shortlist/").status_code == 200
    assert auth_client(unverified_brand).post(f"/api/v1/brand/proposals/{second.pk}/reject/").status_code == 200


# ---- creators: connected YouTube channel ---------------------------------------------------------------


@pytest.fixture
def campaign(db):
    return CampaignFactory(status=Campaign.Status.PUBLISHED)


def test_creator_with_no_stats_cannot_apply(campaign, auth_client):
    creator = UserFactory(role=Role.CREATOR)

    response = apply_to(auth_client, creator, campaign)

    assert response.status_code == 403
    assert error_code(response) == "creator_youtube_required"
    assert not Proposal.objects.filter(creator=creator).exists()


@pytest.mark.parametrize("platform", ["instagram", "tiktok", "facebook", "youtube"])
def test_manual_unverified_stats_do_not_count(campaign, auth_client, platform):
    creator = UserFactory(role=Role.CREATOR)
    PlatformStats.objects.create(
        creator=creator, platform=platform, followers=50_000, engagement_rate="5.00", is_verified=False
    )

    response = apply_to(auth_client, creator, campaign)

    assert response.status_code == 403
    assert error_code(response) == "creator_youtube_required"


def test_creator_with_verified_youtube_can_apply_to_any_platform_campaign(db, auth_client):
    creator = UserFactory(role=Role.CREATOR, youtube_verified=True)
    instagram_campaign = CampaignFactory(status=Campaign.Status.PUBLISHED, platform="instagram")

    response = apply_to(auth_client, creator, instagram_campaign)

    assert response.status_code == 201


def test_creator_loses_the_right_to_apply_when_youtube_is_disconnected(campaign, auth_client):
    creator = UserFactory(role=Role.CREATOR, youtube_verified=True)
    PlatformStats.objects.filter(creator=creator, platform="youtube").update(is_verified=False)

    response = apply_to(auth_client, creator, campaign)

    assert response.status_code == 403
    assert error_code(response) == "creator_youtube_required"


def test_creator_email_verification_does_not_replace_youtube(campaign, auth_client):
    creator = UserFactory(role=Role.CREATOR, email_verified=True)

    assert apply_to(auth_client, creator, campaign).status_code == 403
