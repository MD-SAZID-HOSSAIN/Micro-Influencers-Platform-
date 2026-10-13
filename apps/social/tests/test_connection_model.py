import json

import pytest

from apps.accounts.models import Role
from apps.accounts.tests.factories import UserFactory
from apps.social.crypto import encrypt
from apps.social.models import YouTubeConnection
from apps.social.serializers import YouTubeConnectionSerializer


@pytest.fixture
def connection(db):
    creator = UserFactory(role=Role.CREATOR)
    return YouTubeConnection.objects.create(
        creator=creator,
        access_token_enc=encrypt("plain-access-token"),
        refresh_token_enc=encrypt("plain-refresh-token"),
        access_expires_at="2030-01-01T00:00:00Z",
    )


def test_defaults(connection):
    assert connection.status == YouTubeConnection.Status.CONNECTED
    assert connection.recent_content == []
    assert connection.last_manual_refresh_at is None


def test_one_connection_per_creator(connection):
    with pytest.raises(Exception):
        YouTubeConnection.objects.create(
            creator=connection.creator,
            access_token_enc="x",
            refresh_token_enc="y",
            access_expires_at="2030-01-01T00:00:00Z",
        )


def test_connection_serializer_never_contains_tokens(connection):
    data = YouTubeConnectionSerializer(connection).data
    dumped = json.dumps(data, default=str)

    assert set(data) == {"status", "connected_at"}
    for secret in ("plain-access-token", "plain-refresh-token", connection.access_token_enc, connection.refresh_token_enc):
        assert secret not in dumped


def test_stored_tokens_are_not_plaintext(connection):
    stored = YouTubeConnection.objects.get(pk=connection.pk)

    assert "plain-access-token" not in stored.access_token_enc
    assert "plain-refresh-token" not in stored.refresh_token_enc
