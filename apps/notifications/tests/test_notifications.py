import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Role
from apps.accounts.tests.factories import UserFactory
from apps.notifications.models import Kind, Notification
from apps.notifications.services import notify

LIST = "/api/v1/notifications/"
READ_ALL = "/api/v1/notifications/read-all/"


def read_url(pk):
    return f"/api/v1/notifications/{pk}/read/"


@pytest.fixture
def user(db):
    return UserFactory(role=Role.CREATOR)


def test_notify_creates_unread_notification_with_payload(user):
    note = notify(user, Kind.PROPOSAL_ACCEPTED, "You were accepted.", campaign_id=7, proposal_id=9)

    stored = Notification.objects.get(pk=note.pk)
    assert stored.user == user
    assert stored.kind == "proposal_accepted"
    assert stored.message == "You were accepted."
    assert stored.payload == {"campaign_id": 7, "proposal_id": 9}
    assert stored.is_read is False


def test_notify_rejects_unknown_kind(user):
    with pytest.raises(ValueError):
        notify(user, "proposal_acepted", "typo")


def test_every_kind_in_the_plan_exists():
    assert {k.value for k in Kind} == {
        "proposal_shortlisted",
        "proposal_accepted",
        "proposal_rejected",
        "account_reconnect",
        "proposal_received",
        "proposal_withdrawn",
        "campaign_auto_closed",
    }


def test_list_returns_newest_first_with_unread_count(user, auth_client):
    notify(user, Kind.PROPOSAL_SHORTLISTED, "first")
    notify(user, Kind.PROPOSAL_ACCEPTED, "second", campaign_id=3)
    notify(user, Kind.PROPOSAL_REJECTED, "third")

    response = auth_client(user).get(LIST)

    assert response.status_code == 200
    body = response.json()
    assert [n["message"] for n in body["results"]] == ["third", "second", "first"]
    assert body["unread_count"] == 3
    assert body["count"] == 3
    first = body["results"][1]
    assert first["kind"] == "proposal_accepted"
    assert first["payload"] == {"campaign_id": 3}
    assert first["is_read"] is False
    assert "created_at" in first


def test_unread_count_covers_all_pages_and_only_my_notifications(user, auth_client):
    other = UserFactory(role=Role.BRAND)
    for n in range(25):
        notify(user, Kind.PROPOSAL_RECEIVED, f"n{n}")
    notify(other, Kind.PROPOSAL_RECEIVED, "not mine")

    body = auth_client(user).get(LIST).json()

    assert len(body["results"]) == 20
    assert body["count"] == 25
    assert body["unread_count"] == 25


def test_list_excludes_other_users_notifications(user, auth_client):
    notify(UserFactory(role=Role.BRAND), Kind.PROPOSAL_RECEIVED, "not mine")

    assert auth_client(user).get(LIST).json()["results"] == []


def test_mark_read_only_for_owner_404_otherwise(user, auth_client):
    other = UserFactory(role=Role.BRAND)
    theirs = notify(other, Kind.PROPOSAL_RECEIVED, "theirs")

    response = auth_client(user).post(read_url(theirs.pk))

    assert response.status_code == 404
    theirs.refresh_from_db()
    assert theirs.is_read is False


def test_mark_read_marks_and_returns_the_notification(user, auth_client):
    note = notify(user, Kind.PROPOSAL_ACCEPTED, "yes")
    client = auth_client(user)

    response = client.post(read_url(note.pk))

    assert response.status_code == 200
    assert response.json()["is_read"] is True
    assert client.get(LIST).json()["unread_count"] == 0


def test_mark_read_is_idempotent(user, auth_client):
    note = notify(user, Kind.PROPOSAL_ACCEPTED, "yes")
    client = auth_client(user)

    assert client.post(read_url(note.pk)).status_code == 200
    assert client.post(read_url(note.pk)).status_code == 200
    note.refresh_from_db()
    assert note.is_read is True


def test_read_all_marks_only_my_notifications(user, auth_client):
    other = UserFactory(role=Role.BRAND)
    notify(user, Kind.PROPOSAL_ACCEPTED, "a")
    notify(user, Kind.PROPOSAL_REJECTED, "b")
    theirs = notify(other, Kind.PROPOSAL_RECEIVED, "c")
    client = auth_client(user)

    response = client.post(READ_ALL)

    assert response.status_code == 200
    assert response.json() == {"marked_read": 2}
    assert client.get(LIST).json()["unread_count"] == 0
    theirs.refresh_from_db()
    assert theirs.is_read is False


def test_read_all_with_nothing_unread_marks_zero(user, auth_client):
    assert auth_client(user).post(READ_ALL).json() == {"marked_read": 0}


def test_notifications_require_auth(db):
    client = APIClient()

    assert client.get(LIST).status_code == 401
    assert client.post(READ_ALL).status_code == 401
    assert client.post(read_url(1)).status_code == 401
