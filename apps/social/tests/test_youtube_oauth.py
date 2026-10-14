"""Connecting YouTube is a two-step flow so the link can only be finished by the person who started it.

1. The creator (logged in) asks /connect/ for the Google URL. It carries a signed, single-use ``state``.
2. Google sends the browser to /callback/ (no login possible there). The server only checks the state's
   signature and redirects to the frontend with ``code`` and ``state``. It changes nothing.
3. The frontend, logged in as the creator, POSTs both to /complete/. The server checks that the state
   was issued to THAT creator, then exchanges the code and saves the tokens.

Without step 3's identity check, a creator could send someone else a connect link and end up
with that person's channel shown as Verified on their own profile (OAuth login CSRF).
"""
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
COMPLETE = BASE + "complete/"
RECENT = BASE + "recent-content/"
FRONTEND_PAGE = "http://frontend.test/settings/connections"


def error_redirect(reason):
    return f"{FRONTEND_PAGE}?youtube=error&reason={reason}"


@pytest.fixture
def creator(db):
    return UserFactory(role=Role.CREATOR)


def get_state(client):
    url = client.get(CONNECT).json()["authorization_url"]
    return parse_qs(urlparse(url).query)["state"][0]


def google_redirects_back(state, code="auth-code", **extra):
    """What the browser does after Google's consent screen: a plain GET with no Authorization header."""
    return APIClient().get(CALLBACK, {"state": state, "code": code, **extra})


def complete(client, state, code="auth-code"):
    return client.post(COMPLETE, {"state": state, "code": code}, format="json")


def error_code(response):
    return response.json()["error"]["code"]


# ---- step 1: connect ------------------------------------------------------------------------------


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


# ---- step 2: Google's redirect (no login, no side effects) ------------------------------------------------


def test_callback_only_redirects_to_the_frontend_carrying_the_code_and_state(creator, fake_youtube, auth_client):
    state = get_state(auth_client(creator))

    response = google_redirects_back(state, code="the-google-code")

    assert response.status_code == 302
    location = urlparse(response["Location"])
    assert f"{location.scheme}://{location.netloc}{location.path}" == FRONTEND_PAGE
    assert parse_qs(location.query) == {"youtube": ["confirm"], "code": ["the-google-code"], "state": [state]}


def test_callback_changes_nothing(creator, fake_youtube, auth_client):
    state = get_state(auth_client(creator))
    nonce = signing.loads(state, salt="youtube-oauth")["nonce"]

    google_redirects_back(state)

    assert not YouTubeConnection.objects.exists()  # nothing is linked yet
    assert fake_youtube.exchange_calls == []  # Google's code has not been used
    assert cache.get(f"youtube-oauth-nonce:{nonce}") is not None  # the state can still be completed


def test_callback_is_reachable_without_an_auth_header(creator, fake_youtube, auth_client):
    state = get_state(auth_client(creator))

    assert google_redirects_back(state).status_code == 302


def test_callback_only_accepts_get(db):
    assert APIClient().post(CALLBACK, {}).status_code == 405


def test_callback_rejects_a_tampered_state_straight_away(creator, fake_youtube, auth_client):
    state = get_state(auth_client(creator))

    response = google_redirects_back(state[:-3] + "xyz")

    assert response["Location"] == error_redirect("invalid_state")


def test_callback_rejects_an_expired_state(creator, fake_youtube, auth_client):
    with freeze_time("2026-10-13 12:00:00") as clock:
        state = get_state(auth_client(creator))
        clock.tick(timedelta(seconds=601))

        response = google_redirects_back(state)

    assert response["Location"] == error_redirect("invalid_state")


def test_callback_rejects_a_state_signed_for_another_purpose(creator, fake_youtube):
    state = signing.dumps({"uid": creator.id, "nonce": "n1"}, salt="something-else")

    assert google_redirects_back(state)["Location"] == error_redirect("invalid_state")


@pytest.mark.parametrize("params", [{}, {"state": ""}, {"code": "x"}, {"state": "abc"}])
def test_callback_rejects_missing_or_junk_parameters(db, fake_youtube, params):
    response = APIClient().get(CALLBACK, params)

    assert response["Location"] == error_redirect("invalid_state")


def test_user_denied_consent(creator, fake_youtube, auth_client):
    state = get_state(auth_client(creator))

    response = APIClient().get(CALLBACK, {"error": "access_denied", "state": state})

    assert response["Location"] == error_redirect("access_denied")
    assert fake_youtube.exchange_calls == []
    assert not YouTubeConnection.objects.exists()


# ---- step 3: the logged-in creator completes the link ---------------------------------------------------------


def test_completing_stores_encrypted_tokens_and_starts_the_first_sync(creator, fake_youtube, auth_client, run_on_commit):
    client = auth_client(creator)
    state = get_state(client)
    google_redirects_back(state)

    with run_on_commit():
        response = complete(client, state)

    assert response.status_code == 200
    assert response.json()["connected"] is True and response.json()["status"] == "connected"
    connection = YouTubeConnection.objects.get(creator=creator)
    assert connection.access_token_enc != "exchanged-at"
    assert "exchanged-rt" not in connection.refresh_token_enc
    assert decrypt(connection.access_token_enc) == "exchanged-at"
    assert decrypt(connection.refresh_token_enc) == "exchanged-rt"
    assert fake_youtube.exchange_calls == ["auth-code"]
    assert fake_youtube.fetch_calls == ["exchanged-at"]  # the first sync ran in the background
    stats = PlatformStats.objects.get(creator=creator, platform="youtube")
    assert (stats.is_verified, stats.followers) == (True, 10000)


def test_someone_elses_connect_link_cannot_be_finished_by_another_creator(db, fake_youtube, auth_client):
    attacker, victim = UserFactory(role=Role.CREATOR), UserFactory(role=Role.CREATOR)
    attackers_state = get_state(auth_client(attacker))
    # The victim is tricked into approving the attacker's link; Google sends THEIR code with the attacker's state.
    google_redirects_back(attackers_state, code="victims-google-code")

    response = complete(auth_client(victim), attackers_state, code="victims-google-code")

    assert response.status_code == 400
    assert error_code(response) == "invalid_state"
    assert fake_youtube.exchange_calls == []  # the victim's code was never even used
    assert not YouTubeConnection.objects.exists()  # neither account got linked
    assert not PlatformStats.objects.exists()


def test_a_refused_attempt_does_not_burn_the_rightful_owners_state(db, fake_youtube, auth_client, run_on_commit):
    owner, other = UserFactory(role=Role.CREATOR), UserFactory(role=Role.CREATOR)
    owners_client = auth_client(owner)
    state = get_state(owners_client)
    assert complete(auth_client(other), state).status_code == 400

    with run_on_commit():
        response = complete(owners_client, state)

    assert response.status_code == 200
    assert YouTubeConnection.objects.get().creator == owner


def test_completing_requires_a_logged_in_creator(creator, fake_youtube, auth_client):
    state = get_state(auth_client(creator))
    brand = UserFactory(role=Role.BRAND)

    assert APIClient().post(COMPLETE, {"state": state, "code": "x"}, format="json").status_code == 401
    assert complete(auth_client(brand), state).status_code == 403
    assert not YouTubeConnection.objects.exists()


def test_a_state_can_be_completed_only_once(creator, fake_youtube, auth_client, run_on_commit):
    client = auth_client(creator)
    state = get_state(client)
    with run_on_commit():
        assert complete(client, state).status_code == 200

    second = complete(client, state)

    assert second.status_code == 400 and error_code(second) == "invalid_state"
    assert fake_youtube.exchange_calls == ["auth-code"]


def test_an_expired_state_is_rejected(creator, fake_youtube, auth_client):
    with freeze_time("2026-10-13 12:00:00") as clock:
        client = auth_client(creator)  # the login token must be issued under the frozen clock too
        state = get_state(client)
        clock.tick(timedelta(seconds=601))

        response = complete(client, state)

    assert response.status_code == 400 and error_code(response) == "invalid_state"
    assert fake_youtube.exchange_calls == []


def test_a_tampered_state_or_one_signed_for_another_purpose_is_rejected(creator, fake_youtube, auth_client):
    client = auth_client(creator)
    state = get_state(client)
    cache.set("youtube-oauth-nonce:n1", True, 600)
    foreign = signing.dumps({"uid": creator.id, "nonce": "n1"}, salt="something-else")

    assert error_code(complete(client, state[:-3] + "xyz")) == "invalid_state"
    assert error_code(complete(client, foreign)) == "invalid_state"
    assert fake_youtube.exchange_calls == []


@pytest.mark.parametrize("failure", [TokenRevoked(), TransientApiError("503")])
def test_a_failed_code_exchange_is_reported_and_stores_nothing(creator, fake_youtube, auth_client, failure):
    fake_youtube.exchange_result = failure
    client = auth_client(creator)

    response = complete(client, get_state(client))

    assert response.status_code == 400 and error_code(response) == "exchange_failed"
    assert not YouTubeConnection.objects.exists()


def test_no_refresh_token_and_no_existing_connection_is_an_error(creator, fake_youtube, auth_client):
    fake_youtube.exchange_result = TokenSet("at", None, 3600)
    client = auth_client(creator)

    response = complete(client, get_state(client))

    assert response.status_code == 400 and error_code(response) == "no_refresh_token"
    assert not YouTubeConnection.objects.exists()


def test_without_a_new_refresh_token_the_existing_one_is_kept(creator, fake_youtube, auth_client, run_on_commit):
    make_connection(creator, refresh="old-rt")
    fake_youtube.exchange_result = TokenSet("fresh-at", None, 3600)
    client = auth_client(creator)

    with run_on_commit():
        complete(client, get_state(client))

    connection = YouTubeConnection.objects.get(creator=creator)
    assert decrypt(connection.refresh_token_enc) == "old-rt"
    assert decrypt(connection.access_token_enc) == "fresh-at"


def test_completing_replaces_manual_youtube_stats_with_verified_ones(creator, fake_youtube, auth_client, run_on_commit):
    PlatformStats.objects.create(
        creator=creator, platform="youtube", followers=5, engagement_rate="1.00", is_verified=False
    )
    client = auth_client(creator)

    with run_on_commit():
        complete(client, get_state(client))

    stats = PlatformStats.objects.get(creator=creator, platform="youtube")
    assert (stats.is_verified, stats.followers) == (True, 10000)


def test_reconnecting_after_a_revocation_restores_the_connection(creator, fake_youtube, auth_client, run_on_commit):
    connection = make_connection(creator, status=YouTubeConnection.Status.NEEDS_RECONNECT, followers=77)
    connection.last_error = "token_revoked"
    connection.save(update_fields=["last_error"])
    PlatformStats.objects.filter(creator=creator).update(is_outdated=True)
    client = auth_client(creator)

    with run_on_commit():
        response = complete(client, get_state(client))

    assert response.status_code == 200
    connection.refresh_from_db()
    assert connection.status == YouTubeConnection.Status.CONNECTED and connection.last_error == ""
    stats = PlatformStats.objects.get(creator=creator, platform="youtube")
    assert (stats.is_outdated, stats.followers) == (False, 10000)


@pytest.mark.parametrize("body", [{}, {"state": "x"}, {"code": "x"}, {"state": "", "code": ""}])
def test_completing_needs_both_the_state_and_the_code(creator, fake_youtube, auth_client, body):
    response = auth_client(creator).post(COMPLETE, body, format="json")

    assert response.status_code == 400
    assert error_code(response) == "validation_error"


def test_completing_is_throttled(creator, fake_youtube, auth_client):
    client = auth_client(creator)
    for _ in range(20):
        assert complete(client, "junk").status_code == 400

    assert complete(client, "junk").status_code == 429


# ---- disconnect, status, recent content ---------------------------------------------------------------------


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


# ---- when Redis is down ---------------------------------------------------------------------------------------
# The OAuth state's one-time nonce lives in the shared cache. If it is unreachable the flow cannot be made
# safe, so it must say so plainly (503) rather than crash, and must not half-complete.


def test_connect_says_temporarily_unavailable_when_the_cache_is_down(creator, fake_youtube, auth_client, redis_down):
    response = auth_client(creator).get(CONNECT)

    assert response.status_code == 503
    assert error_code(response) == "temporarily_unavailable"


def test_completing_says_temporarily_unavailable_and_changes_nothing_when_the_cache_is_down(
    creator, fake_youtube, auth_client, redis_down
):
    state = signing.dumps({"uid": creator.id, "nonce": "n1"}, salt="youtube-oauth")  # validly signed

    response = complete(auth_client(creator), state)

    assert response.status_code == 503
    assert error_code(response) == "temporarily_unavailable"
    assert fake_youtube.exchange_calls == []  # Google's code was not used up
    assert not YouTubeConnection.objects.exists()


def test_a_background_queue_outage_after_connecting_does_not_fail_the_request(
    creator, fake_youtube, auth_client, run_on_commit, caplog
):
    import logging
    from unittest import mock

    from kombu.exceptions import OperationalError

    client = auth_client(creator)
    state = get_state(client)

    with mock.patch("apps.social.tasks.sync_connection_task.delay", side_effect=OperationalError("broker down")):
        with caplog.at_level(logging.ERROR):
            with run_on_commit():
                response = complete(client, state)

    assert response.status_code == 200  # the link was saved; the first sync happens with the next daily run
    assert YouTubeConnection.objects.filter(creator=creator).exists()
    assert "Could not queue" in caplog.text
