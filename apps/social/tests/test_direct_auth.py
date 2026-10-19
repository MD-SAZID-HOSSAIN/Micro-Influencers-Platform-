import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Role
from apps.accounts.tests.factories import UserFactory
from apps.social.models import PlatformStats, YouTubeConnection


@pytest.fixture
def creator(db):
    return UserFactory(role=Role.CREATOR)


def test_social_challenge_generates_code(creator, auth_client):
    client = auth_client(creator)
    res = client.get("/api/v1/social/challenge/instagram/")
    assert res.status_code == 200
    data = res.json()
    assert data["platform"] == "instagram"
    assert data["challenge_code"].startswith("MIC-")
    assert "instructions" in data


def test_direct_connect_with_challenge_success(creator, auth_client):
    client = auth_client(creator)
    # 1. Get challenge
    ch = client.get("/api/v1/social/challenge/instagram/").json()
    code = ch["challenge_code"]

    # 2. Submit challenge code
    res = client.post(
        "/api/v1/social/direct-connect/instagram/",
        {
            "handle": "@rajon_creative",
            "verification_method": "challenge",
            "auth_code": code,
            "followers": 35000,
            "engagement_rate": "4.20",
        },
        format="json",
    )
    assert res.status_code == 200
    data = res.json()
    assert data["is_verified"] is True
    assert data["handle_url"] == "https://instagram.com/rajon_creative"
    assert data["followers"] == 35000


def test_direct_connect_with_challenge_wrong_code_fails(creator, auth_client):
    client = auth_client(creator)
    client.get("/api/v1/social/challenge/instagram/")

    res = client.post(
        "/api/v1/social/direct-connect/instagram/",
        {
            "handle": "@someone_else",
            "verification_method": "challenge",
            "auth_code": "WRONG-CODE",
            "followers": 1000000,
        },
        format="json",
    )
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "challenge_failed"


def test_direct_connect_with_direct_auth(creator, auth_client):
    client = auth_client(creator)
    res = client.post(
        "/api/v1/social/direct-connect/facebook/",
        {
            "handle": "RajonOfficialPage",
            "verification_method": "direct_auth",
            "followers": 18500,
            "engagement_rate": "3.50",
        },
        format="json",
    )
    assert res.status_code == 200
    data = res.json()
    assert data["is_verified"] is True
    assert data["handle_url"] == "https://facebook.com/RajonOfficialPage"
    assert data["followers"] == 18500


# ---- a channel linked by handle is refreshed from its public page, never through Google ---------------------


def public_channel(subscribers):
    return {
        "success": True,
        "subscribers": subscribers,
        "canonical_url": "https://www.youtube.com/@rajon",
        "title": "Rajon",
        "handle": "@rajon",
        "videos_count": 10,
        "avatar_url": "",
    }


@pytest.fixture
def linked_channel(creator, auth_client, monkeypatch):
    """A creator who linked a channel by handle (no Google sign-in); the public page says 5,000 subscribers."""
    monkeypatch.setattr("apps.social.youtube_public.fetch_public_channel", lambda url: public_channel(5000))
    res = auth_client(creator).post(
        "/api/v1/social/youtube/direct-connect/", {"handle_url": "https://youtube.com/@rajon"}, format="json"
    )
    assert res.status_code == 200
    return creator


def test_refresh_reads_the_public_page_and_never_calls_google(
    linked_channel, auth_client, fake_youtube, monkeypatch, run_on_commit
):
    monkeypatch.setattr("apps.social.youtube_public.fetch_public_channel", lambda url: public_channel(7000))

    with run_on_commit():
        res = auth_client(linked_channel).post("/api/v1/social/youtube/refresh/")

    assert res.status_code == 202
    assert fake_youtube.fetch_calls == [] and fake_youtube.refresh_calls == []
    stats = PlatformStats.objects.get(creator=linked_channel, platform="youtube")
    assert stats.followers == 7000 and stats.is_verified and not stats.is_outdated
    assert YouTubeConnection.objects.get(creator=linked_channel).status == YouTubeConnection.Status.CONNECTED


def test_a_second_refresh_inside_the_cooldown_is_refused(linked_channel, auth_client, fake_youtube):
    client = auth_client(linked_channel)
    assert client.post("/api/v1/social/youtube/refresh/").status_code == 202

    again = client.post("/api/v1/social/youtube/refresh/")

    assert again.status_code == 429
    assert again.json()["error"]["code"] == "refresh_cooldown"


def test_the_daily_sync_of_a_linked_channel_does_not_ask_google_or_flag_it(linked_channel, fake_youtube, monkeypatch):
    from apps.social import services

    monkeypatch.setattr("apps.social.youtube_public.fetch_public_channel", lambda url: public_channel(9000))
    connection = YouTubeConnection.objects.get(creator=linked_channel)

    services.sync_connection(connection)

    assert fake_youtube.fetch_calls == [] and fake_youtube.refresh_calls == []
    connection.refresh_from_db()
    assert connection.status == YouTubeConnection.Status.CONNECTED
    assert PlatformStats.objects.get(creator=linked_channel, platform="youtube").followers == 9000
