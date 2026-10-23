"""One YouTube channel can verify one account, and the channel is remembered so later checks can use it."""
import pytest

from apps.accounts.models import Role
from apps.accounts.tests.factories import UserFactory
from apps.social.models import PlatformStats, YouTubeConnection
from apps.social.services import sync_connection
from apps.social.tests.fakes import make_connection, snapshot
from apps.social.tests.test_youtube_oauth import complete, error_code, get_state
from apps.social.youtube_client import ChannelNotFound


@pytest.fixture
def first(db):
    return UserFactory(role=Role.CREATOR)


@pytest.fixture
def second(db):
    return UserFactory(role=Role.CREATOR)


def connect(auth_client, creator):
    client = auth_client(creator)
    return complete(client, get_state(client))


def test_the_channel_is_remembered_on_the_connection(first, fake_youtube, auth_client):
    assert connect(auth_client, first).status_code == 200

    assert YouTubeConnection.objects.get(creator=first).channel_id == "UC-amina"


def test_a_channel_cannot_be_connected_to_two_accounts(first, second, fake_youtube, auth_client):
    assert connect(auth_client, first).status_code == 200

    response = connect(auth_client, second)

    assert response.status_code == 400 and error_code(response) == "channel_in_use"
    assert not YouTubeConnection.objects.filter(creator=second).exists()
    assert YouTubeConnection.objects.filter(channel_id="UC-amina").count() == 1


def test_a_creator_can_reconnect_their_own_channel(first, fake_youtube, auth_client):
    connect(auth_client, first)

    assert connect(auth_client, first).status_code == 200
    assert YouTubeConnection.objects.filter(creator=first).count() == 1


def test_two_different_channels_are_fine(first, second, fake_youtube, auth_client):
    connect(auth_client, first)
    fake_youtube.channel_id_result = "UC-someone-else"

    assert connect(auth_client, second).status_code == 200


def test_a_google_account_without_a_channel_is_refused_and_nothing_is_saved(first, fake_youtube, auth_client):
    fake_youtube.channel_id_result = ChannelNotFound()

    response = connect(auth_client, first)

    assert response.status_code == 400 and error_code(response) == "no_channel"
    assert not YouTubeConnection.objects.filter(creator=first).exists()


def test_an_older_connection_gets_its_channel_filled_in_by_the_next_sync(first, fake_youtube):
    connection = make_connection(first, channel_id="")

    sync_connection(connection)

    connection.refresh_from_db()
    assert connection.channel_id == "UC-amina"
    assert PlatformStats.objects.get(creator=first, platform="youtube").is_verified is True


def test_a_second_older_connection_on_the_same_channel_is_not_trusted(first, second, fake_youtube):
    make_connection(first, channel_id="UC-amina")
    duplicate = make_connection(second, channel_id="")
    fake_youtube.default_snapshot = snapshot(subscribers=20_000, channel_id="UC-amina")

    sync_connection(duplicate)

    duplicate.refresh_from_db()
    stats = PlatformStats.objects.get(creator=second, platform="youtube")
    assert duplicate.channel_id == "" and duplicate.last_error == "channel_in_use"
    assert stats.is_verified is False and stats.is_outdated is True
