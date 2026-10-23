"""A creator stays Verified only while Google can still confirm the channel.

When access is revoked or expires, or the channel hides its subscribers, the last numbers are kept but marked
outdated. Outdated numbers do not count as proof until a refresh or a reconnect confirms them again.
"""
import pytest

from apps.accounts.models import Role
from apps.accounts.tests.factories import UserFactory
from apps.accounts.verification import creator_is_verified
from apps.campaigns.models import Campaign
from apps.campaigns.tests.factories import CampaignFactory
from apps.proposals.models import Proposal
from apps.social.models import PlatformStats


@pytest.fixture
def creator(db):
    return UserFactory(role=Role.CREATOR, youtube_verified=True)


def apply_to(auth_client, creator):
    campaign = CampaignFactory(status=Campaign.Status.PUBLISHED)
    body = {"cover_message": "Hello", "portfolio_links": [], "experience_note": ""}
    return auth_client(creator).post(f"/api/v1/campaigns/{campaign.pk}/proposals/", body, format="json")


def mark_outdated(creator, outdated=True):
    PlatformStats.objects.filter(creator=creator, platform="youtube").update(is_outdated=outdated)


def test_fresh_stats_verify_the_creator(creator, auth_client):
    assert creator_is_verified(creator) is True
    assert apply_to(auth_client, creator).status_code == 201


def test_outdated_stats_no_longer_verify_the_creator(creator, auth_client):
    mark_outdated(creator)

    assert creator_is_verified(creator) is False
    response = apply_to(auth_client, creator)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "creator_youtube_reconnect"
    assert not Proposal.objects.filter(creator=creator).exists()


def test_the_profile_stops_showing_verified_while_the_stats_are_outdated(creator, auth_client):
    client = auth_client(creator)
    assert client.get("/api/v1/creators/me/").json()["is_verified"] is True

    mark_outdated(creator)

    assert client.get("/api/v1/creators/me/").json()["is_verified"] is False


def test_a_refresh_that_clears_the_flag_restores_verification(creator, auth_client):
    mark_outdated(creator)
    mark_outdated(creator, outdated=False)  # what a successful sync does

    assert creator_is_verified(creator) is True
    assert apply_to(auth_client, creator).status_code == 201


def test_outdated_stats_are_not_verified_in_the_brand_directory(creator, auth_client):
    brand = UserFactory(role=Role.BRAND)
    from apps.profiles.models import CreatorProfile

    CreatorProfile.objects.filter(user=creator).update(primary_platform="youtube")
    results = lambda: auth_client(brand).get("/api/v1/creators/").json()["results"]  # noqa: E731
    assert next(c for c in results() if c["id"] == creator.id)["is_verified"] is True

    mark_outdated(creator)

    assert next(c for c in results() if c["id"] == creator.id)["is_verified"] is False
