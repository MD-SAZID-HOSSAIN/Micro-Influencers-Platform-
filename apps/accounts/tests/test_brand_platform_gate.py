"""A brand is fully verified only with a confirmed email AND one verified platform.

A verified platform is an Instagram, TikTok or Facebook link an admin approved. YouTube never counts for a brand.
A typed link that is still waiting for an admin does not count. Until the brand is verified it cannot publish a
campaign or accept a proposal; saving drafts, shortlisting and rejecting stay open.
"""
import pytest

from apps.accounts.models import Role
from apps.accounts.tests.factories import UserFactory
from apps.campaigns.models import Campaign
from apps.campaigns.tests.factories import CampaignFactory
from apps.proposals.models import Proposal
from apps.proposals.tests.factories import ProposalFactory
from apps.social.models import BrandSocialAccount

CAMPAIGNS = "/api/v1/brand/campaigns/"


def error_code(response):
    return response.json()["error"]["code"]


@pytest.fixture
def brand_without_platform(db):
    return UserFactory(role=Role.BRAND, email_verified=True, platform_connected=False)


def connect(brand, platform="instagram", verified=True):
    """A verified platform by default. verified=False is a typed link still waiting for an admin."""
    return BrandSocialAccount.objects.create(
        brand=brand,
        platform=platform,
        handle_url=f"https://{platform}.com/acme",
        is_verified=verified,
        review_status="approved" if verified else "pending",
    )


def publish(auth_client, brand, campaign):
    return auth_client(brand).post(f"{CAMPAIGNS}{campaign.pk}/publish/")


def accept(auth_client, brand, proposal):
    return auth_client(brand).post(f"/api/v1/brand/proposals/{proposal.pk}/accept/")


def test_a_brand_with_a_verified_email_but_no_platform_cannot_publish(brand_without_platform, auth_client):
    draft = CampaignFactory(brand=brand_without_platform)

    response = publish(auth_client, brand_without_platform, draft)

    assert response.status_code == 403
    assert error_code(response) == "brand_platform_required"
    draft.refresh_from_db()
    assert draft.status == Campaign.Status.DRAFT


def test_a_brand_with_a_verified_email_but_no_platform_cannot_accept(brand_without_platform, auth_client):
    campaign = CampaignFactory(brand=brand_without_platform, status=Campaign.Status.PUBLISHED, creators_needed=2)
    proposal = ProposalFactory(campaign=campaign, status=Proposal.Status.PENDING)

    response = accept(auth_client, brand_without_platform, proposal)

    assert response.status_code == 403 and error_code(response) == "brand_platform_required"
    proposal.refresh_from_db()
    assert proposal.status == Proposal.Status.PENDING


@pytest.mark.parametrize("platform", ["instagram", "tiktok", "facebook"])
def test_any_one_approved_link_is_enough(brand_without_platform, auth_client, platform):
    connect(brand_without_platform, platform)
    draft = CampaignFactory(brand=brand_without_platform)

    response = publish(auth_client, brand_without_platform, draft)

    assert response.status_code == 200
    draft.refresh_from_db()
    assert draft.status == Campaign.Status.PUBLISHED


def test_youtube_does_not_verify_a_brand(brand_without_platform, auth_client):
    connect(brand_without_platform, "youtube")
    draft = CampaignFactory(brand=brand_without_platform)

    response = publish(auth_client, brand_without_platform, draft)

    assert response.status_code == 403 and error_code(response) == "brand_platform_required"


def test_a_typed_link_waiting_for_an_admin_does_not_count(brand_without_platform, auth_client):
    connect(brand_without_platform, "tiktok", verified=False)
    draft = CampaignFactory(brand=brand_without_platform)
    campaign = CampaignFactory(brand=brand_without_platform, status=Campaign.Status.PUBLISHED, creators_needed=2)
    proposal = ProposalFactory(campaign=campaign, status=Proposal.Status.PENDING)

    for response in (publish(auth_client, brand_without_platform, draft), accept(auth_client, brand_without_platform, proposal)):
        assert response.status_code == 403 and error_code(response) == "brand_platform_required"


def test_a_rejected_link_does_not_count(brand_without_platform, auth_client):
    account = connect(brand_without_platform, "facebook", verified=False)
    BrandSocialAccount.objects.filter(pk=account.pk).update(review_status="rejected", review_note="Not your page.")
    draft = CampaignFactory(brand=brand_without_platform)

    response = publish(auth_client, brand_without_platform, draft)

    assert response.status_code == 403 and error_code(response) == "brand_platform_required"


def test_the_email_is_checked_before_the_platform(db, auth_client):
    brand = UserFactory(role=Role.BRAND, email_verified=False, platform_connected=False)
    draft = CampaignFactory(brand=brand)

    response = publish(auth_client, brand, draft)

    assert response.status_code == 403 and error_code(response) == "brand_email_unverified"


def test_a_verified_platform_does_not_replace_the_email_code(db, auth_client):
    brand = UserFactory(role=Role.BRAND, email_verified=False, platform_connected=False)
    connect(brand, "instagram")
    draft = CampaignFactory(brand=brand)

    response = publish(auth_client, brand, draft)

    assert response.status_code == 403 and error_code(response) == "brand_email_unverified"


def test_removing_the_last_platform_blocks_the_brand_again(brand_without_platform, auth_client):
    connect(brand_without_platform, "instagram")
    first, second = CampaignFactory.create_batch(2, brand=brand_without_platform)
    assert publish(auth_client, brand_without_platform, first).status_code == 200

    assert auth_client(brand_without_platform).delete("/api/v1/brands/me/social/instagram/").status_code == 204

    response = publish(auth_client, brand_without_platform, second)
    assert response.status_code == 403 and error_code(response) == "brand_platform_required"


def test_drafts_shortlist_and_reject_stay_open_without_a_platform(brand_without_platform, auth_client):
    campaign = CampaignFactory(brand=brand_without_platform, status=Campaign.Status.PUBLISHED, creators_needed=2)
    first, second = ProposalFactory.create_batch(2, campaign=campaign)
    client = auth_client(brand_without_platform)

    assert client.post(f"/api/v1/brand/proposals/{first.pk}/shortlist/").status_code == 200
    assert client.post(f"/api/v1/brand/proposals/{second.pk}/reject/").status_code == 200
    assert CampaignFactory(brand=brand_without_platform).status == Campaign.Status.DRAFT


def test_the_me_payload_says_whether_a_brand_has_a_platform(brand_without_platform, auth_client):
    client = auth_client(brand_without_platform)
    me = client.get("/api/v1/auth/me/").json()
    assert (me["platform_connected"], me["platform_status"]) == (False, "none")

    connect(brand_without_platform, "instagram", verified=False)
    me = client.get("/api/v1/auth/me/").json()
    assert (me["platform_connected"], me["platform_status"]) == (False, "pending")

    connect(brand_without_platform, "youtube")  # does not count
    me = client.get("/api/v1/auth/me/").json()
    assert (me["platform_connected"], me["platform_status"]) == (False, "pending")

    connect(brand_without_platform, "facebook")
    me = client.get("/api/v1/auth/me/").json()
    assert (me["platform_connected"], me["platform_status"]) == (True, "verified")


def test_the_me_payload_has_no_platform_flag_for_creators(db, auth_client):
    creator = UserFactory(role=Role.CREATOR)

    me = auth_client(creator).get("/api/v1/auth/me/").json()
    assert me["platform_connected"] is None and me["platform_status"] is None
