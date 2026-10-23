"""A brand adds an Instagram, TikTok or Facebook link; one link approved by an admin is enough.

The links are typed by the brand: they wait for an admin ("pending") and count only once the admin approves them.
YouTube does not verify a brand.
"""
import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Role
from apps.accounts.tests.factories import UserFactory
from apps.accounts.verification import brand_has_platform, brand_platform_status
from apps.social.models import BrandSocialAccount

BASE = "/api/v1/brands/me/social/"


def error_code(response):
    return response.json()["error"]["code"]


@pytest.fixture
def brand(db):
    return UserFactory(role=Role.BRAND, platform_connected=False)


def put(client, platform, url):
    return client.put(f"{BASE}{platform}/", {"handle_url": url}, format="json")


# ---- typed links: Instagram, TikTok, Facebook ----------------------------------------------------------------


def test_a_new_brand_has_no_connected_platforms(brand, auth_client):
    response = auth_client(brand).get(BASE)

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.parametrize(
    "platform, url",
    [
        ("instagram", "https://www.instagram.com/acme_foods"),
        ("tiktok", "https://www.tiktok.com/@acme_foods"),
        ("facebook", "https://facebook.com/acmefoods"),
        ("facebook", "https://m.facebook.com/acmefoods"),
    ],
)
def test_a_typed_link_is_saved_as_pending_not_verified(brand, auth_client, platform, url):
    response = put(auth_client(brand), platform, url)

    assert response.status_code == 200
    body = response.json()
    assert body["platform"] == platform and body["handle_url"] == url and body["is_verified"] is False
    assert body["review_status"] == "pending" and body["review_note"] == ""
    assert BrandSocialAccount.objects.get(brand=brand, platform=platform).is_verified is False
    assert [a["platform"] for a in auth_client(brand).get(BASE).json()] == [platform]


@pytest.mark.parametrize(
    "platform, url",
    [
        ("instagram", "https://example.com/acme"),
        ("instagram", "https://instagram.com.evil.test/acme"),
        ("instagram", "https://notinstagram.com/acme"),
        ("tiktok", "https://www.instagram.com/acme"),
        ("facebook", "javascript:alert(1)"),
        ("facebook", "ftp://facebook.com/acme"),
        ("instagram", "https://instagram.com/"),
        ("instagram", "acme_foods"),
        ("instagram", ""),
    ],
)
def test_a_link_must_be_a_profile_on_that_platform(brand, auth_client, platform, url):
    response = put(auth_client(brand), platform, url)

    assert response.status_code == 400
    assert not BrandSocialAccount.objects.filter(brand=brand).exists()


def test_saving_again_replaces_the_link(brand, auth_client):
    client = auth_client(brand)
    put(client, "instagram", "https://instagram.com/old")

    put(client, "instagram", "https://instagram.com/new")

    accounts = BrandSocialAccount.objects.filter(brand=brand)
    assert accounts.count() == 1 and accounts.get().handle_url == "https://instagram.com/new"


def test_youtube_cannot_be_added_it_does_not_verify_a_brand(brand, auth_client):
    response = put(auth_client(brand), "youtube", "https://www.youtube.com/@acme")

    assert response.status_code == 400
    assert error_code(response) == "youtube_not_for_brands"
    assert not BrandSocialAccount.objects.filter(brand=brand).exists()


def test_an_unknown_platform_is_a_404(brand, auth_client):
    assert put(auth_client(brand), "myspace", "https://myspace.com/acme").status_code == 404


def test_a_brand_can_remove_a_platform(brand, auth_client):
    client = auth_client(brand)
    put(client, "instagram", "https://instagram.com/acme")

    assert client.delete(f"{BASE}instagram/").status_code == 204

    assert not BrandSocialAccount.objects.filter(brand=brand).exists()
    assert client.delete(f"{BASE}instagram/").status_code == 204  # removing twice is harmless


def test_a_brand_only_sees_and_removes_its_own_platforms(brand, auth_client):
    other = UserFactory(role=Role.BRAND, platform_connected=False)
    put(auth_client(other), "instagram", "https://instagram.com/other")

    assert auth_client(brand).get(BASE).json() == []
    auth_client(brand).delete(f"{BASE}instagram/")
    assert BrandSocialAccount.objects.filter(brand=other).count() == 1


def test_only_brands_can_use_these_endpoints(db, auth_client):
    creator = UserFactory(role=Role.CREATOR)

    assert auth_client(creator).get(BASE).status_code == 403
    assert put(auth_client(creator), "instagram", "https://instagram.com/x").status_code == 403
    assert APIClient().get(BASE).status_code == 401


# ---- YouTube does not verify a brand ------------------------------------------------------------------------


def test_a_legacy_youtube_row_is_hidden_and_never_counts(brand, auth_client):
    BrandSocialAccount.objects.create(
        brand=brand, platform="youtube", handle_url="https://www.youtube.com/@acme", is_verified=True
    )
    client = auth_client(brand)

    assert client.get(BASE).json() == []
    assert brand_has_platform(brand) is False
    assert brand_platform_status(brand) == "none"


def test_the_brand_youtube_google_sign_in_endpoints_are_gone(brand, auth_client):
    client = auth_client(brand)

    assert client.get(BASE + "youtube/connect/").status_code == 404
    assert client.post(BASE + "youtube/complete/", {"state": "x", "code": "y"}, format="json").status_code == 404


def test_only_an_approved_link_verifies_a_brand(brand, auth_client):
    put(auth_client(brand), "instagram", "https://instagram.com/acme")
    assert brand_has_platform(brand) is False and brand_platform_status(brand) == "pending"

    BrandSocialAccount.objects.filter(brand=brand).update(is_verified=True, review_status="approved")

    assert brand_has_platform(brand) is True and brand_platform_status(brand) == "verified"
