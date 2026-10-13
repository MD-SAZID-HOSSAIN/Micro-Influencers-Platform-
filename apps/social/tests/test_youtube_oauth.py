from datetime import timedelta
from urllib.parse import parse_qs, urlparse

import pytest
from django.core import signing
from django.core.cache import cache
from freezegun import freeze_time
from rest_framework.test import APIClient

from apps.accounts.models import Role
from apps.accounts.tests.factories import UserFactory
from apps.social.crypto import decrypt
from apps.social.models import PlatformStats, YouTubeConnection
from apps.social.tests.fakes import make_connection
from apps.social.youtube_client import TokenRevoked, TokenSet, TransientApiError

BASE = "/api/v1/social/youtube/"
CONNECT = BASE + "connect/"
CALLBACK = BASE + "callback/"
RECENT = BASE + "recent-content/"
SUCCESS = "http://frontend.test/settings/connections?youtube=success"


def error_redirect(reason):
    return f"http://frontend.test/settings/connections?youtube=error&reason={reason}"


@pytest.fixture
def creator(db):
    return UserFactory(role=Role.CREATOR)


def get_state(client):
    url = client.get(CONNECT).json()["authorization_url"]
    return parse_qs(urlparse(url).query)["state"][0]


def callback(state, code="auth-code", **extra):
    params = {"state": state, "code": code, **extra}
    return APIClient().get(CALLBACK, params)  # no Authorization header: it is a browser redirect


# ---- connect ------------------------------------------------------------------------------


def test_connect_returns_google_url_with_a_signed_single_use_state(creator, fake_youtube, auth_client):
    response = auth_client(creator).get(CONNECT)

    assert response.status_code == 200
    url = response.json()["authorization_url"]
    assert url.startswith("https://accounts.google.com/o/oauth2/v2/auth")
    state = parse_qs(urlparse(url).query)["state"][0]
    payload = signing.loads(state, salt="youtube-oauth", max_age=600)
    assert payload["uid"] == creator.id
    assert cache.get(f"youtube-oauth-nonce:{payload['nonce']}") is not None


def test_each_connect_call_gets_a_fresh_state(creator, fake_youtube, auth_client):
    client = auth_client(creator)

    assert get_state(client) != get_state(client)


def test_only_creators_can_start_a_connection(db, fake_youtube, auth_client):
    brand = UserFactory(role=Role.BRAND)

    assert auth_client(brand).get(CONNECT).status_code == 403
    assert APIClient().get(CONNECT).status_code == 401


# ---- callback: success -----------------------------------------------------------------------


def test_callback_with_valid_state_stores_encrypted_tokens_and_verified_stats(
    creator, fake_youtube, auth_client, run_on_commit
):
    state = get_state(auth_client(creator))

    with run_on_commit():
        response = callback(state)

    assert response.status_code == 302
    assert response["Location"] == SUCCESS
    connection = YouTubeConnection.objects.get(creator=creator)
    assert connection.access_token_enc != "exchanged-at"
    assert "exchanged-rt" not in connection.refresh_token_enc
    assert decrypt(connection.access_token_enc) == "exchanged-at"
    assert decrypt(connection.refresh_token_enc) == "exchanged-rt"
    assert connection.status == YouTubeConnection.Status.CONNECTED
    assert fake_youtube.exchange_calls == ["auth-code"]
    assert fake_youtube.fetch_calls == ["exchanged-at"]  # first sync ran in the background
    stats = PlatformStats.objects.get(creator=creator, platform="youtube")
    assert stats.is_verified is True
    assert stats.followers == 10000


def test_callback_replaces_manual_youtube_stats_with_verified_ones(
    creator, fake_youtube, auth_client, run_on_commit
):
    PlatformStats.objects.create(
        creator=creator, platform="youtube", followers=5, engagement_rate="1.00", is_verified=False
    )
    state = get_state(auth_client(creator))

    with run_on_commit():
        callback(state)

    stats = PlatformStats.objects.get(creator=creator, platform="youtube")
    assert (stats.is_verified, stats.followers) == (True, 10000)


def test_reconnect_after_revocation_restores_connected_status(
    creator, fake_youtube, auth_client, run_on_commit
):
    connection = make_connection(
        creator, status=YouTubeConnection.Status.NEEDS_RECONNECT, followers=77
    )
    connection.last_error = "token_revoked"
    connection.save(update_fields=["last_error"])
    PlatformStats.objects.filter(creator=creator).update(is_outdated=True)
    state = get_state(auth_client(creator))

    with run_on_commit():
        response = callback(state)

    assert response["Location"] == SUCCESS
    connection.refresh_from_db()
    assert connection.status == YouTubeConnection.Status.CONNECTED
    assert connection.last_error == ""
    stats = PlatformStats.objects.get(creator=creator, platform="youtube")
    assert stats.is_outdated is False
    assert stats.followers == 10000


def test_callback_without_a_new_refresh_token_keeps_the_existing_one(
    creator, fake_youtube, auth_client, run_on_commit
):
    make_connection(creator, refresh="old-rt")
    fake_youtube.exchange_result = TokenSet("fresh-at", None, 3600)
    state = get_state(auth_client(creator))

    with run_on_commit():
        callback(state)

    connection = YouTubeConnection.objects.get(creator=creator)
    assert decrypt(connection.refresh_token_enc) == "old-rt"
    assert decrypt(connection.access_token_enc) == "fresh-at"


def test_callback_is_reachable_without_an_auth_header(creator, fake_youtube, auth_client):
    state = get_state(auth_client(creator))

    assert callback(state).status_code == 302


def test_callback_only_accepts_get(db):
    assert APIClient().post(CALLBACK, {}).status_code == 405


# ---- callback: failures -----------------------------------------------------------------------


def test_tampered_state_redirects_with_error_and_stores_nothing(creator, fake_youtube, auth_client):
    state = get_state(auth_client(creator))

    response = callback(state[:-3] + "xyz")

    assert response["Location"] == error_redirect("invalid_state")
    assert not YouTubeConnection.objects.exists()
    assert fake_youtube.exchange_calls == []


def test_state_cannot_be_reused(creator, fake_youtube, auth_client, run_on_commit):
    state = get_state(auth_client(creator))
    with run_on_commit():
        assert callback(state)["Location"] == SUCCESS

    second = callback(state)

    assert second["Location"] == error_redirect("invalid_state")
    assert fake_youtube.exchange_calls == ["auth-code"]


def test_expired_state_is_rejected(creator, fake_youtube, auth_client):
    with freeze_time("2026-10-13 12:00:00") as clock:
        state = get_state(auth_client(creator))
        clock.tick(timedelta(seconds=601))

        response = callback(state)

    assert response["Location"] == error_redirect("invalid_state")
    assert fake_youtube.exchange_calls == []


def test_state_for_a_non_creator_is_rejected(db, fake_youtube):
    brand = UserFactory(role=Role.BRAND)
    cache.set("youtube-oauth-nonce:n1", True, 600)
    state = signing.dumps({"uid": brand.id, "nonce": "n1"}, salt="youtube-oauth")

    assert callback(state)["Location"] == error_redirect("invalid_state")
    assert not YouTubeConnection.objects.exists()


def test_state_signed_for_another_purpose_is_rejected(creator, fake_youtube):
    cache.set("youtube-oauth-nonce:n1", True, 600)
    state = signing.dumps({"uid": creator.id, "nonce": "n1"}, salt="something-else")

    assert callback(state)["Location"] == error_redirect("invalid_state")


@pytest.mark.parametrize("params", [{}, {"state": ""}, {"code": "x"}])
def test_missing_state_is_rejected(db, fake_youtube, params):
    response = APIClient().get(CALLBACK, params)

    assert response["Location"] == error_redirect("invalid_state")


def test_user_denied_consent(creator, fake_youtube, auth_client):
    state = get_state(auth_client(creator))

    response = APIClient().get(CALLBACK, {"error": "access_denied", "state": state})

    assert response["Location"] == error_redirect("access_denied")
    assert fake_youtube.exchange_calls == []
    assert not YouTubeConnection.objects.exists()


@pytest.mark.parametrize("failure", [TokenRevoked(), TransientApiError("503")])
def test_failed_code_exchange_redirects_with_error(creator, fake_youtube, auth_client, failure):
    fake_youtube.exchange_result = failure
    state = get_state(auth_client(creator))

    response = callback(state)

    assert response["Location"] == error_redirect("exchange_failed")
    assert not YouTubeConnection.objects.exists()


def test_no_refresh_token_and_no_existing_connection_is_an_error(creator, fake_youtube, auth_client):
    fake_youtube.exchange_result = TokenSet("at", None, 3600)
    state = get_state(auth_client(creator))

    response = callback(state)

    assert response["Location"] == error_redirect("no_refresh_token")
    assert not YouTubeConnection.objects.exists()


# ---- disconnect, status, recent content ---------------------------------------------------------


def test_disconnect_deletes_tokens_and_keeps_stats_as_unverified(creator, auth_client):
    make_connection(creator, followers=4321)

    response = auth_client(creator).delete(BASE)

    assert response.status_code == 204
    assert not YouTubeConnection.objects.filter(creator=creator).exists()
    stats = PlatformStats.objects.get(creator=creator, platform="youtube")
    assert stats.followers == 4321
    assert stats.is_verified is False


def test_disconnect_is_idempotent(creator, auth_client):
    client = auth_client(creator)

    assert client.delete(BASE).status_code == 204
    assert client.delete(BASE).status_code == 204


def test_after_disconnect_manual_entry_is_allowed_again(creator, auth_client):
    make_connection(creator)
    client = auth_client(creator)
    client.delete(BASE)

    response = client.put(
        "/api/v1/creators/me/stats/youtube/",
        {"followers": 99, "engagement_rate": "2.00"},
        format="json",
    )

    assert response.status_code == 200


def test_status_when_not_connected(creator, auth_client):
    body = auth_client(creator).get(BASE).json()

    assert body["connected"] is False
    assert body["status"] is None
    assert body["needs_reconnect"] is False


def test_status_when_connected_never_leaks_tokens(creator, auth_client):
    make_connection(creator, access="super-secret-at", refresh="super-secret-rt")

    response = auth_client(creator).get(BASE)

    body = response.json()
    assert body["connected"] is True
    assert body["status"] == "connected"
    assert body["needs_reconnect"] is False
    assert body["is_outdated"] is False
    assert body["last_synced_at"] is not None
    assert "super-secret" not in response.content.decode()
    assert not {"access_token", "refresh_token", "access_token_enc", "refresh_token_enc"} & set(body)


def test_status_flags_a_connection_that_needs_reconnecting(creator, auth_client):
    make_connection(creator, status=YouTubeConnection.Status.NEEDS_RECONNECT)
    PlatformStats.objects.filter(creator=creator).update(is_outdated=True)

    body = auth_client(creator).get(BASE).json()

    assert body["needs_reconnect"] is True
    assert body["is_outdated"] is True


def test_recent_content_returns_the_cached_videos(creator, auth_client):
    connection = make_connection(creator)
    connection.recent_content = [{"video_id": "v1", "title": "T", "url": "https://y/v1", "published_at": "x"}]
    connection.save(update_fields=["recent_content"])

    response = auth_client(creator).get(RECENT)

    assert response.status_code == 200
    assert response.json()[0]["video_id"] == "v1"


def test_recent_content_is_empty_when_not_connected(creator, auth_client):
    assert auth_client(creator).get(RECENT).json() == []


@pytest.mark.parametrize("path, method", [(BASE, "get"), (BASE, "delete"), (RECENT, "get")])
def test_endpoints_are_creator_only(db, auth_client, path, method):
    brand = UserFactory(role=Role.BRAND)

    assert getattr(auth_client(brand), method)(path).status_code == 403
    assert getattr(APIClient(), method)(path).status_code == 401
