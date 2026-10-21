"""Giving Google access back is a background job, so the person never waits for Google's answer.

Used by both flows: a brand connecting YouTube (access is given back at once, none is kept) and a creator
disconnecting. The token travels to the job encrypted, and if the queue is down the access is still given back right
away, so it is never left behind.
"""
from urllib.parse import parse_qs, urlparse

import pytest

from apps.accounts.models import Role
from apps.accounts.tests.factories import UserFactory
from apps.social import services, tasks
from apps.social.crypto import decrypt, encrypt
from apps.social.tests.fakes import make_connection

BRAND_CONNECT = "/api/v1/brands/me/social/youtube/connect/"
BRAND_COMPLETE = "/api/v1/brands/me/social/youtube/complete/"


@pytest.fixture
def queued(monkeypatch):
    """Capture the jobs the services queue instead of running them."""
    calls = []

    def fake_enqueue(task, *args, **kwargs):
        calls.append((task, args))
        return True

    monkeypatch.setattr("apps.social.services.enqueue", fake_enqueue)
    return calls


@pytest.fixture
def brand(db):
    return UserFactory(role=Role.BRAND, platform_connected=False)


def brand_connects_youtube(client, run_on_commit):
    url = client.get(BRAND_CONNECT).json()["authorization_url"]
    state = parse_qs(urlparse(url).query)["state"][0]
    with run_on_commit():
        return client.post(BRAND_COMPLETE, {"state": state, "code": "auth-code"}, format="json")


def test_a_brand_connecting_youtube_queues_the_revoke_and_does_not_call_google_itself(
    brand, auth_client, fake_youtube, queued, run_on_commit
):
    response = brand_connects_youtube(auth_client(brand), run_on_commit)

    assert response.status_code == 200
    assert fake_youtube.revoked == []  # Google was not asked during the request
    revokes = [args for task, args in queued if task is tasks.revoke_token_task]
    assert len(revokes) == 1
    encrypted_token, user_id = revokes[0]
    assert user_id == brand.id
    assert encrypted_token != "exchanged-rt" and decrypt(encrypted_token) == "exchanged-rt"  # never plain in the queue


def test_the_queued_job_gives_the_access_back_at_google(fake_youtube):
    tasks.revoke_token_task(encrypt("exchanged-rt"), 7)

    assert fake_youtube.revoked == ["exchanged-rt"]


def test_the_job_survives_an_unreadable_token_and_a_google_failure(fake_youtube, caplog):
    tasks.revoke_token_task("not-a-valid-encrypted-token", 7)  # must not raise
    fake_youtube.revoke_error = RuntimeError("Google is down")

    tasks.revoke_token_task(encrypt("some-token"), 7)  # must not raise either

    assert fake_youtube.revoked == []


def test_if_the_queue_is_down_the_access_is_still_given_back_at_once(
    brand, auth_client, fake_youtube, monkeypatch, run_on_commit
):
    monkeypatch.setattr("apps.social.services.enqueue", lambda task, *args, **kwargs: False)

    response = brand_connects_youtube(auth_client(brand), run_on_commit)

    assert response.status_code == 200
    assert fake_youtube.revoked == ["exchanged-rt"]


def test_a_brand_whose_google_account_has_no_channel_still_gives_the_access_back(
    brand, auth_client, fake_youtube, queued, run_on_commit
):
    from apps.social.youtube_client import ChannelNotFound

    fake_youtube.channel_link_result = ChannelNotFound()

    response = brand_connects_youtube(auth_client(brand), run_on_commit)

    assert response.status_code == 400
    assert len([1 for task, _ in queued if task is tasks.revoke_token_task]) == 1


def test_a_creator_disconnecting_queues_the_revoke_instead_of_calling_google(
    db, fake_youtube, queued, run_on_commit
):
    creator = UserFactory(role=Role.CREATOR)
    make_connection(creator, refresh="rt-1")

    with run_on_commit():
        services.disconnect(creator)

    assert fake_youtube.revoked == []
    revokes = [args for task, args in queued if task is tasks.revoke_token_task]
    assert len(revokes) == 1 and decrypt(revokes[0][0]) == "rt-1" and revokes[0][1] == creator.id


def test_the_helper_other_modules_use_is_public():
    assert callable(services.revoke_token_quietly)
    assert not hasattr(services, "_revoke_quietly")
