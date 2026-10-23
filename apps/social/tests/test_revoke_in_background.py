"""Giving Google access back is a background job, so the person never waits for Google's answer.

Used when a creator disconnects YouTube. The token travels to the job encrypted, and if the queue is down the access
is still given back right away, so it is never left behind.
"""
import pytest

from apps.accounts.models import Role
from apps.accounts.tests.factories import UserFactory
from apps.social import services, tasks
from apps.social.crypto import decrypt, encrypt
from apps.social.tests.fakes import make_connection


@pytest.fixture
def queued(monkeypatch):
    """Capture the jobs the services queue instead of running them."""
    calls = []

    def fake_enqueue(task, *args, **kwargs):
        calls.append((task, args))
        return True

    monkeypatch.setattr("apps.social.services.enqueue", fake_enqueue)
    return calls


def test_the_queued_job_gives_the_access_back_at_google(fake_youtube):
    tasks.revoke_token_task(encrypt("exchanged-rt"), 7)

    assert fake_youtube.revoked == ["exchanged-rt"]


def test_the_job_survives_an_unreadable_token_and_a_google_failure(fake_youtube, caplog):
    tasks.revoke_token_task("not-a-valid-encrypted-token", 7)  # must not raise
    fake_youtube.revoke_error = RuntimeError("Google is down")

    tasks.revoke_token_task(encrypt("some-token"), 7)  # must not raise either

    assert fake_youtube.revoked == []


def test_if_the_queue_is_down_the_access_is_still_given_back_at_once(
    db, fake_youtube, monkeypatch, run_on_commit
):
    monkeypatch.setattr("apps.social.services.enqueue", lambda task, *args, **kwargs: False)
    creator = UserFactory(role=Role.CREATOR)
    make_connection(creator, refresh="rt-1")

    with run_on_commit():
        services.disconnect(creator)

    assert fake_youtube.revoked == ["rt-1"]


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
