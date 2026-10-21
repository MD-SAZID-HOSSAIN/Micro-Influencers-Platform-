"""A brand connects any of YouTube, Instagram, TikTok or Facebook; one verified platform is enough.

YouTube is connected with Google sign-in (the only proof of ownership available). The other three are links
the brand types: they wait for an admin ("pending") and are Verified only once the admin approves them.
"""
from urllib.parse import parse_qs, urlparse

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Role
from apps.accounts.tests.factories import UserFactory
from apps.social.models import BrandSocialAccount
from apps.social.youtube_client import ChannelNotFound

BASE = "/api/v1/brands/me/social/"
YOUTUBE_CONNECT = BASE + "youtube/connect/"
YOUTUBE_COMPLETE = BASE + "youtube/complete/"


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


def test_youtube_cannot_be_typed_in_it_needs_google_sign_in(brand, auth_client):
    response = put(auth_client(brand), "youtube", "https://www.youtube.com/@acme")

    assert response.status_code == 400
    assert error_code(response) == "google_signin_required"
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


# ---- YouTube with Google sign-in -----------------------------------------------------------------------------


def state_from(client):
    url = client.get(YOUTUBE_CONNECT).json()["authorization_url"]
    return parse_qs(urlparse(url).query)["state"][0]


def test_connecting_youtube_saves_a_verified_account_and_revokes_the_google_access(
    brand, auth_client, fake_youtube, run_on_commit
):
    client = auth_client(brand)
    state = state_from(client)

    with run_on_commit():  # the revoke is a background job that runs once the account is saved
        response = client.post(YOUTUBE_COMPLETE, {"state": state, "code": "auth-code"}, format="json")

    assert response.status_code == 200
    account = BrandSocialAccount.objects.get(brand=brand, platform="youtube")
    assert account.is_verified is True and account.handle_url == "https://www.youtube.com/@brandchannel"
    body = response.json()
    assert len(body) == 1
    assert (body[0]["platform"], body[0]["handle_url"], body[0]["is_verified"]) == (
        "youtube",
        "https://www.youtube.com/@brandchannel",
        True,
    )
    assert fake_youtube.exchange_calls == ["auth-code"]
    assert fake_youtube.revoked  # a brand needs no ongoing access, so none is kept


def test_another_brands_state_cannot_be_used(brand, auth_client, fake_youtube):
    other = UserFactory(role=Role.BRAND, platform_connected=False)
    state = state_from(auth_client(other))

    response = auth_client(brand).post(YOUTUBE_COMPLETE, {"state": state, "code": "x"}, format="json")

    assert response.status_code == 400 and error_code(response) == "invalid_state"
    assert not BrandSocialAccount.objects.exists()


def test_a_state_can_only_be_used_once(brand, auth_client, fake_youtube):
    client = auth_client(brand)
    state = state_from(client)
    assert client.post(YOUTUBE_COMPLETE, {"state": state, "code": "x"}, format="json").status_code == 200

    again = client.post(YOUTUBE_COMPLETE, {"state": state, "code": "x"}, format="json")

    assert again.status_code == 400 and error_code(again) == "invalid_state"


def test_a_google_account_with_no_channel_is_a_clear_error(brand, auth_client, fake_youtube):
    fake_youtube.channel_link_result = ChannelNotFound()
    client = auth_client(brand)

    response = client.post(YOUTUBE_COMPLETE, {"state": state_from(client), "code": "x"}, format="json")

    assert response.status_code == 400 and error_code(response) == "no_channel"
    assert not BrandSocialAccount.objects.exists()


def test_removing_youtube_deletes_it(brand, auth_client, fake_youtube):
    client = auth_client(brand)
    client.post(YOUTUBE_COMPLETE, {"state": state_from(client), "code": "x"}, format="json")

    assert client.delete(f"{BASE}youtube/").status_code == 204
    assert not BrandSocialAccount.objects.filter(brand=brand).exists()


def test_creators_cannot_use_the_brand_youtube_flow(db, auth_client):
    creator = UserFactory(role=Role.CREATOR)

    assert auth_client(creator).get(YOUTUBE_CONNECT).status_code == 403
    assert auth_client(creator).post(YOUTUBE_COMPLETE, {"state": "x", "code": "y"}, format="json").status_code == 403
