from datetime import timedelta
from decimal import Decimal

import pytest
from celery.schedules import crontab
from django.utils import timezone
from freezegun import freeze_time
from rest_framework.test import APIClient

from apps.accounts.models import Role
from apps.accounts.tests.factories import UserFactory
from apps.notifications.models import Kind, Notification
from apps.social.crypto import decrypt
from apps.social.models import PlatformStats, YouTubeConnection
from apps.social.services import sync_connection
from apps.social.tasks import sync_all_youtube, sync_connection_task
from apps.social.tests.fakes import make_connection, snapshot
from apps.social.youtube_client import (
    ChannelNotFound,
    QuotaExceeded,
    SubscribersHidden,
    YouTubeError,
    TokenRevoked,
    TransientApiError,
)

REFRESH = "/api/v1/social/youtube/refresh/"


@pytest.fixture
def creator(db):
    return UserFactory(role=Role.CREATOR)


def stats_of(creator):
    return PlatformStats.objects.get(creator=creator, platform="youtube")


def reload(connection):
    connection.refresh_from_db()
    return connection


# ---- core sync -----------------------------------------------------------------------


@freeze_time("2026-10-13 12:00:00")
def test_sync_updates_followers_engagement_and_last_synced(creator, fake_youtube):
    connection = make_connection(creator, followers=100)
    PlatformStats.objects.filter(creator=creator).update(is_outdated=True)

    sync_connection(connection)

    stats = stats_of(creator)
    assert stats.followers == 10000
    assert stats.engagement_rate == Decimal("4.20")
    assert stats.handle_url == "https://www.youtube.com/@amina"
    assert stats.is_verified is True
    assert stats.is_outdated is False
    assert stats.last_synced_at == timezone.now()
    assert reload(connection).recent_content[0]["video_id"] == "v1"


def test_first_sync_creates_the_verified_stats_row(creator, fake_youtube):
    connection = make_connection(creator, with_stats=False)

    sync_connection(connection)

    assert stats_of(creator).is_verified is True
    assert stats_of(creator).followers == 10000


def test_valid_access_token_is_used_without_refreshing(creator, fake_youtube):
    sync_connection(make_connection(creator, access="still-good"))

    assert fake_youtube.refresh_calls == []
    assert fake_youtube.fetch_calls == ["still-good"]


def test_expired_access_token_is_refreshed_first(creator, fake_youtube):
    connection = make_connection(creator, access="old-at", refresh="the-rt", expires_in=-10)

    sync_connection(connection)

    assert fake_youtube.refresh_calls == ["the-rt"]
    assert fake_youtube.fetch_calls == ["refreshed-at"]
    connection = reload(connection)
    assert decrypt(connection.access_token_enc) == "refreshed-at"
    assert decrypt(connection.refresh_token_enc) == "the-rt"
    assert connection.access_expires_at > timezone.now()


def test_token_about_to_expire_is_refreshed(creator, fake_youtube):
    sync_connection(make_connection(creator, expires_in=30))

    assert len(fake_youtube.refresh_calls) == 1


def test_a_rotated_refresh_token_is_stored(creator, fake_youtube):
    from apps.social.youtube_client import TokenSet

    fake_youtube.refresh_result = TokenSet("new-at", "rotated-rt", 3600)
    connection = make_connection(creator, expires_in=-10)

    sync_connection(connection)

    assert decrypt(reload(connection).refresh_token_enc) == "rotated-rt"


# ---- failure handling ----------------------------------------------------------------


def test_revoked_token_marks_needs_reconnect_keeps_stats_outdated_and_notifies_once(
    creator, fake_youtube
):  # RF5
    connection = make_connection(creator, access="revoked-at", followers=777)
    fake_youtube.fetch_results["revoked-at"] = TokenRevoked()

    sync_connection(connection)

    assert reload(connection).status == YouTubeConnection.Status.NEEDS_RECONNECT
    stats = stats_of(creator)
    assert stats.followers == 777
    assert stats.is_outdated is True
    assert stats.is_verified is True
    notes = Notification.objects.filter(user=creator)
    assert notes.count() == 1
    assert notes[0].kind == Kind.ACCOUNT_RECONNECT
    assert notes[0].payload == {"platform": "youtube"}


def test_revocation_discovered_while_refreshing_is_handled_the_same_way(creator, fake_youtube):  # RF5
    fake_youtube.refresh_result = TokenRevoked()
    connection = make_connection(creator, expires_in=-10, followers=555)

    sync_connection(connection)

    assert reload(connection).status == YouTubeConnection.Status.NEEDS_RECONNECT
    assert stats_of(creator).followers == 555
    assert stats_of(creator).is_outdated is True
    assert Notification.objects.filter(user=creator, kind=Kind.ACCOUNT_RECONNECT).count() == 1


def test_second_failed_sync_does_not_notify_again(creator, fake_youtube):  # RF5
    connection = make_connection(creator, access="revoked-at")
    fake_youtube.fetch_results["revoked-at"] = TokenRevoked()

    sync_connection(connection)
    sync_connection(reload(connection))
    sync_connection_task.apply(args=[connection.id])

    assert Notification.objects.filter(user=creator).count() == 1
    assert fake_youtube.fetch_calls == ["revoked-at"]  # a dead connection is not retried daily


def test_missing_stats_row_does_not_break_revocation_handling(creator, fake_youtube):
    connection = make_connection(creator, access="revoked-at", with_stats=False)
    fake_youtube.fetch_results["revoked-at"] = TokenRevoked()

    sync_connection(connection)

    assert reload(connection).status == YouTubeConnection.Status.NEEDS_RECONNECT
    assert Notification.objects.filter(user=creator).count() == 1


def test_transient_task_settings():
    assert sync_connection_task.autoretry_for == (TransientApiError,)
    assert sync_connection_task.retry_backoff is True
    assert sync_connection_task.max_retries == 5


@pytest.mark.parametrize("error", [TransientApiError("503"), QuotaExceeded("quota")])
def test_transient_error_leaves_stats_untouched_and_retries(creator, fake_youtube, error):  # RF5
    connection = make_connection(creator, access="flaky-at", followers=321)
    fake_youtube.fetch_results["flaky-at"] = error

    result = sync_connection_task.apply(args=[connection.id])

    assert result.state == "FAILURE"
    assert len(fake_youtube.fetch_calls) == 6  # first attempt + 5 retries
    stats = stats_of(creator)
    assert stats.followers == 321
    assert stats.is_outdated is False
    assert reload(connection).status == YouTubeConnection.Status.CONNECTED
    assert not Notification.objects.filter(user=creator).exists()


def test_google_account_without_channel_marks_stats_outdated_quietly(creator, fake_youtube):
    connection = make_connection(creator, access="no-channel-at", followers=42)
    fake_youtube.fetch_results["no-channel-at"] = ChannelNotFound()

    sync_connection(connection)

    assert stats_of(creator).followers == 42
    assert stats_of(creator).is_outdated is True
    assert reload(connection).last_error == "no_channel"
    assert not Notification.objects.filter(user=creator).exists()


def test_hidden_subscriber_count_keeps_old_stats_outdated_and_says_why(creator, fake_youtube):
    connection = make_connection(creator, access="hidden-at", followers=42)
    fake_youtube.fetch_results["hidden-at"] = SubscribersHidden()

    sync_connection(connection)

    assert stats_of(creator).followers == 42
    assert stats_of(creator).is_outdated is True
    assert reload(connection).last_error == "subscribers_hidden"
    assert not Notification.objects.filter(user=creator).exists()


def test_hidden_subscribers_on_a_first_sync_create_no_verified_stats(creator, fake_youtube):
    connection = make_connection(creator, access="hidden-at", with_stats=False)
    fake_youtube.fetch_results["hidden-at"] = SubscribersHidden()

    sync_connection(connection)

    assert not PlatformStats.objects.filter(creator=creator, platform="youtube").exists()
    assert reload(connection).last_error == "subscribers_hidden"


def test_an_unexpected_google_error_is_logged_and_raised(creator, fake_youtube, caplog):
    connection = make_connection(creator, access="odd-at")
    fake_youtube.fetch_results["odd-at"] = YouTubeError("HTTP 400 (invalidParameter)")

    with caplog.at_level("WARNING", logger="apps.social.services"), pytest.raises(YouTubeError):
        sync_connection(connection)

    assert f"creator {creator.id}" in caplog.text and "invalidParameter" in caplog.text


def test_task_for_a_deleted_connection_is_a_quiet_no_op(db, fake_youtube):
    result = sync_connection_task.apply(args=[999999])

    assert result.state == "SUCCESS"
    assert fake_youtube.fetch_calls == []


# ---- the daily batch -----------------------------------------------------------------


def test_sync_all_continues_after_one_creator_fails(db, fake_youtube):  # RF5
    first, middle, last = (UserFactory(role=Role.CREATOR) for _ in range(3))
    make_connection(first, access="at-a", followers=1)
    make_connection(middle, access="at-b", followers=2)
    make_connection(last, access="at-c", followers=3)
    fake_youtube.fetch_results["at-a"] = snapshot(subscribers=1111, channel_id="UC-a")
    fake_youtube.fetch_results["at-b"] = RuntimeError("unexpected Google weirdness")
    fake_youtube.fetch_results["at-c"] = snapshot(subscribers=3333, channel_id="UC-c")

    enqueued = sync_all_youtube()

    assert enqueued == 3
    assert stats_of(first).followers == 1111
    assert stats_of(middle).followers == 2  # untouched, not erased
    assert stats_of(last).followers == 3333


def test_sync_all_isolates_a_revoked_creator_from_the_rest(db, fake_youtube):  # RF5
    ok, revoked = UserFactory(role=Role.CREATOR), UserFactory(role=Role.CREATOR)
    make_connection(ok, access="at-ok", followers=1)
    make_connection(revoked, access="at-revoked", followers=2)
    fake_youtube.fetch_results["at-revoked"] = TokenRevoked()

    sync_all_youtube()

    assert stats_of(ok).followers == 10000
    assert reload(revoked.youtube_connection).status == YouTubeConnection.Status.NEEDS_RECONNECT


def test_sync_all_skips_connections_that_need_reconnecting(db, fake_youtube):
    healthy, dead = UserFactory(role=Role.CREATOR), UserFactory(role=Role.CREATOR)
    make_connection(healthy, access="at-healthy")
    make_connection(dead, access="at-dead", status=YouTubeConnection.Status.NEEDS_RECONNECT)

    enqueued = sync_all_youtube()

    assert enqueued == 1
    assert fake_youtube.fetch_calls == ["at-healthy"]


def test_beat_schedule_contains_daily_sync(settings):
    entry = settings.CELERY_BEAT_SCHEDULE["sync-all-youtube"]

    assert entry["task"] == "apps.social.tasks.sync_all_youtube"
    assert entry["schedule"] == crontab(hour=3, minute=0)


def test_tasks_are_registered_with_celery():
    from config.celery import app

    app.loader.import_default_modules()

    assert "apps.social.tasks.sync_all_youtube" in app.tasks
    assert "apps.social.tasks.sync_connection_task" in app.tasks


# ---- manual refresh --------------------------------------------------------------------


def test_manual_refresh_schedules_a_sync(creator, fake_youtube, auth_client, run_on_commit):
    make_connection(creator, access="at-manual", followers=1)

    with run_on_commit():
        response = auth_client(creator).post(REFRESH)

    assert response.status_code == 202
    assert fake_youtube.fetch_calls == ["at-manual"]
    assert stats_of(creator).followers == 10000
    assert reload(creator.youtube_connection).last_manual_refresh_at is not None


def test_manual_refresh_within_cooldown_is_429(creator, fake_youtube, auth_client, run_on_commit):
    make_connection(creator)
    with freeze_time("2026-10-13 12:00:00") as clock:
        client = auth_client(creator)  # token must be issued under the frozen clock
        with run_on_commit():
            assert client.post(REFRESH).status_code == 202
        clock.tick(timedelta(seconds=899))

        response = client.post(REFRESH)

    assert response.status_code == 429
    assert response.json()["error"]["code"] == "refresh_cooldown"
    assert len(fake_youtube.fetch_calls) == 1


def test_manual_refresh_after_cooldown_is_202(creator, fake_youtube, auth_client, run_on_commit):
    make_connection(creator)
    with freeze_time("2026-10-13 12:00:00") as clock:
        client = auth_client(creator)  # token must be issued under the frozen clock
        with run_on_commit():
            client.post(REFRESH)
        clock.tick(timedelta(seconds=901))

        with run_on_commit():
            response = client.post(REFRESH)

    assert response.status_code == 202
    assert len(fake_youtube.fetch_calls) == 2


def test_manual_refresh_when_reconnect_is_needed_is_409(creator, fake_youtube, auth_client):
    make_connection(creator, status=YouTubeConnection.Status.NEEDS_RECONNECT)

    response = auth_client(creator).post(REFRESH)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "reconnect_required"


def test_manual_refresh_without_a_connection_is_404(creator, auth_client):
    assert auth_client(creator).post(REFRESH).status_code == 404


def test_manual_refresh_is_creator_only(db, auth_client):
    brand = UserFactory(role=Role.BRAND)

    assert auth_client(brand).post(REFRESH).status_code == 403
    assert APIClient().post(REFRESH).status_code == 401


# ---- the daily batch is spread out, not fired all at once ----------------------------------------------


def _capture_starts(monkeypatch):
    """Record (connection id, countdown seconds) for every sync the daily job schedules."""
    starts = []
    monkeypatch.setattr(
        sync_connection_task,
        "apply_async",
        lambda args=None, countdown=0, **kwargs: starts.append((args[0], countdown)),
    )
    return starts


def test_the_daily_job_spreads_the_syncs_evenly_over_the_window(db, settings, monkeypatch):
    settings.YOUTUBE_SYNC_SPREAD_SECONDS = 1800
    connections = [make_connection(UserFactory(role=Role.CREATOR), with_stats=False) for _ in range(40)]
    starts = _capture_starts(monkeypatch)

    enqueued = sync_all_youtube()

    countdowns = [countdown for _, countdown in starts]
    assert enqueued == 40
    assert [cid for cid, _ in starts] == sorted(c.id for c in connections)
    assert countdowns[0] == 0  # the first creator starts straight away
    assert countdowns == sorted(countdowns) and len(set(countdowns)) == 40  # one start every 45 seconds
    assert countdowns[-1] < 1800  # and everything starts inside the window


def test_a_single_connection_starts_immediately(db, settings, monkeypatch):
    settings.YOUTUBE_SYNC_SPREAD_SECONDS = 1800
    make_connection(UserFactory(role=Role.CREATOR), with_stats=False)
    starts = _capture_starts(monkeypatch)

    sync_all_youtube()

    assert [countdown for _, countdown in starts] == [0]


def test_a_spread_of_zero_switches_spreading_off(db, settings, monkeypatch):
    settings.YOUTUBE_SYNC_SPREAD_SECONDS = 0
    for _ in range(5):
        make_connection(UserFactory(role=Role.CREATOR), with_stats=False)
    starts = _capture_starts(monkeypatch)

    sync_all_youtube()

    assert {countdown for _, countdown in starts} == {0}


def test_the_default_window_is_half_an_hour(settings):
    assert settings.YOUTUBE_SYNC_SPREAD_SECONDS == 1800


def test_a_background_queue_outage_does_not_fail_a_manual_refresh(creator, fake_youtube, auth_client, run_on_commit, caplog):
    import logging
    from unittest import mock

    from kombu.exceptions import OperationalError

    make_connection(creator)

    with mock.patch("apps.social.tasks.sync_connection_task.delay", side_effect=OperationalError("broker down")):
        with caplog.at_level(logging.ERROR):
            with run_on_commit():
                response = auth_client(creator).post(REFRESH)

    assert response.status_code == 202
    assert "Could not queue" in caplog.text
