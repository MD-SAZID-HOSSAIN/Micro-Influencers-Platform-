import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Role
from apps.accounts.tests.factories import UserFactory
from apps.profiles.models import CreatorProfile
from apps.profiles.services import completion_percent
from apps.social.models import PlatformStats


def url(platform):
    return f"/api/v1/creators/me/stats/{platform}/"


LIST = "/api/v1/creators/me/stats/"
PROFILE = "/api/v1/creators/me/"


@pytest.fixture
def creator(db):
    return UserFactory(role=Role.CREATOR)


LINKS = {
    "instagram": "https://instagram.com/amina",
    "tiktok": "https://www.tiktok.com/@amina",
    "facebook": "https://facebook.com/amina",
    "youtube": "https://youtube.com/@amina",
}


def put(client, platform, **overrides):
    data = {"followers": 12000, "engagement_rate": "4.25", "handle_url": LINKS.get(platform)}
    data.update(overrides)
    return client.put(url(platform), data, format="json")


def test_manual_entry_creates_unverified_stat(creator, auth_client):
    response = put(auth_client(creator), "instagram")

    assert response.status_code == 200
    body = response.json()
    assert body["platform"] == "instagram"
    assert body["followers"] == 12000
    assert body["engagement_rate"] == "4.25"
    assert body["is_verified"] is False
    assert body["is_outdated"] is False
    assert body["last_synced_at"] is not None
    assert PlatformStats.objects.get(creator=creator, platform="instagram").followers == 12000


def test_manual_entry_updates_existing_unverified_stat(creator, auth_client):
    client = auth_client(creator)
    put(client, "instagram")

    response = put(client, "instagram", followers=15000)

    assert response.status_code == 200
    assert PlatformStats.objects.filter(creator=creator, platform="instagram").count() == 1
    assert PlatformStats.objects.get(creator=creator, platform="instagram").followers == 15000


def test_manual_entry_blocked_on_verified_platform(creator, auth_client):
    PlatformStats.objects.create(
        creator=creator, platform="youtube", followers=5000, engagement_rate="3.00", is_verified=True
    )

    response = put(auth_client(creator), "youtube", followers=999999)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "stats_verified"
    stat = PlatformStats.objects.get(creator=creator, platform="youtube")
    assert stat.followers == 5000
    assert stat.is_verified is True


@pytest.mark.parametrize("rate, ok", [("0", True), ("100", True), ("100.01", False), ("-0.5", False)])
def test_engagement_rate_must_be_between_0_and_100(creator, auth_client, rate, ok):
    response = put(auth_client(creator), "tiktok", engagement_rate=rate)

    assert (response.status_code == 200) is ok
    if not ok:
        assert "engagement_rate" in response.json()["error"]["details"]


def test_followers_cannot_be_negative(creator, auth_client):
    response = put(auth_client(creator), "tiktok", followers=-1)

    assert response.status_code == 400
    assert "followers" in response.json()["error"]["details"]


def test_followers_and_engagement_are_required(creator, auth_client):
    response = auth_client(creator).put(url("tiktok"), {}, format="json")

    details = response.json()["error"]["details"]
    assert response.status_code == 400
    assert "followers" in details and "engagement_rate" in details


def test_unsafe_handle_url_rejected(creator, auth_client):
    response = put(auth_client(creator), "instagram", handle_url="javascript:alert(1)")

    assert response.status_code == 400
    assert "handle_url" in response.json()["error"]["details"]


def test_unknown_platform_is_404(creator, auth_client):
    assert put(auth_client(creator), "myspace").status_code == 404


def test_list_returns_only_my_stats(creator, auth_client):
    other = UserFactory(role=Role.CREATOR)
    PlatformStats.objects.create(creator=other, platform="tiktok", followers=1, engagement_rate="1.00")
    client = auth_client(creator)
    put(client, "instagram")

    response = client.get(LIST)

    assert response.status_code == 200
    assert [s["platform"] for s in response.json()] == ["instagram"]


def test_creator_profile_embeds_stats(creator, auth_client):
    client = auth_client(creator)
    put(client, "instagram")

    stats = client.get(PROFILE).json()["stats"]

    assert [s["platform"] for s in stats] == ["instagram"]
    assert stats[0]["is_verified"] is False


def test_brand_gets_403_and_logged_out_gets_401(db, auth_client):
    brand = UserFactory(role=Role.BRAND)

    assert auth_client(brand).get(LIST).status_code == 403
    assert put(auth_client(brand), "instagram").status_code == 403
    assert APIClient().get(LIST).status_code == 401


def test_completion_percent_counts_stats_on_primary_platform_only(creator):
    profile = CreatorProfile.objects.get(user=creator)
    profile.primary_platform = "youtube"
    assert completion_percent(profile) == 13  # primary platform only: 1 of 8

    PlatformStats.objects.create(creator=creator, platform="instagram", followers=1, engagement_rate="1.00")
    assert completion_percent(profile) == 13  # stats exist, but not for the primary platform

    PlatformStats.objects.create(creator=creator, platform="youtube", followers=1, engagement_rate="1.00")
    assert completion_percent(profile) == 25  # primary platform + its stats: 2 of 8
