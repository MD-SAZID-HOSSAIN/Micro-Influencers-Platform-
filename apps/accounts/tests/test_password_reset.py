import logging
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from smtplib import SMTPException
from unittest import mock

import pytest
from django.core import mail
from django.db import connection
from freezegun import freeze_time
from rest_framework.test import APIClient

from apps.accounts.models import OneTimeCode
from apps.accounts.services import confirm_password_reset, issue_access_token
from apps.accounts.tests.factories import DEFAULT_PASSWORD, UserFactory
from apps.core.exceptions import DomainError

REQUEST = "/api/v1/auth/password-reset/request/"
CONFIRM = "/api/v1/auth/password-reset/confirm/"
LOGIN = "/api/v1/auth/login/"
ME = "/api/v1/auth/me/"
GENERIC = "If this email is registered, a code has been sent."
NEW_PASSWORD = "BrandNewPass1"


@pytest.fixture
def client():
    return APIClient()


def request_code(client, run_on_commit, email="amina@example.com"):
    with run_on_commit():
        return client.post(REQUEST, {"email": email}, format="json")


def last_code():
    match = re.search(r"\b(\d{6})\b", mail.outbox[-1].body)
    assert match, mail.outbox[-1].body
    return match.group(1)


def confirm(client, code, email="amina@example.com", password=NEW_PASSWORD):
    return client.post(
        CONFIRM, {"email": email, "code": code, "new_password": password}, format="json"
    )


def error_code(response):
    return response.json()["error"]["code"]


@pytest.fixture
def user(db):
    return UserFactory(email="amina@example.com", username="amina")


def test_request_registered_email_sends_one_email_with_6_digit_code(client, user, run_on_commit):
    response = request_code(client, run_on_commit)

    assert response.status_code == 200
    assert response.json() == {"detail": GENERIC}
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["amina@example.com"]
    assert re.search(r"\b\d{6}\b", mail.outbox[0].body)


def test_request_unregistered_email_same_response_and_no_email(client, user, run_on_commit):
    known = request_code(client, run_on_commit)
    mail.outbox.clear()

    unknown = request_code(client, run_on_commit, email="nobody@example.com")

    assert (unknown.status_code, unknown.json()) == (known.status_code, known.json())
    assert mail.outbox == []
    assert OneTimeCode.objects.filter(user=user).count() == 1


def test_provider_down_still_returns_same_message_and_logs(client, user, run_on_commit, caplog):
    with mock.patch("apps.core.tasks.send_mail", side_effect=SMTPException("down")):
        with caplog.at_level(logging.ERROR):
            response = request_code(client, run_on_commit)

    assert response.status_code == 200
    assert response.json() == {"detail": GENERIC}
    assert "Failed to send email" in caplog.text


def test_inactive_user_gets_no_email_but_same_response(client, db, run_on_commit):
    UserFactory(email="amina@example.com", is_active=False)

    response = request_code(client, run_on_commit)

    assert response.json() == {"detail": GENERIC}
    assert mail.outbox == []


def test_email_matching_ignores_case_and_whitespace(client, user, run_on_commit):
    request_code(client, run_on_commit, email="  AMINA@Example.com ")

    assert len(mail.outbox) == 1
    assert confirm(client, last_code(), email=" Amina@example.COM ").status_code == 200


def test_correct_code_changes_password_and_old_stops_working(client, user, run_on_commit):
    request_code(client, run_on_commit)

    response = confirm(client, last_code())

    assert response.status_code == 200
    old = client.post(LOGIN, {"identifier": "amina", "password": DEFAULT_PASSWORD}, format="json")
    new = client.post(LOGIN, {"identifier": "amina", "password": NEW_PASSWORD}, format="json")
    assert old.status_code == 401
    assert new.status_code == 200


def test_expired_code_rejected(client, user, run_on_commit):
    with freeze_time("2026-10-13 10:00:00") as clock:
        request_code(client, run_on_commit)
        code = last_code()
        clock.tick(timedelta(minutes=10, seconds=1))

        response = confirm(client, code)

    assert response.status_code == 400
    assert error_code(response) == "reset_code_expired"


def test_code_still_valid_just_before_10_minutes(client, user, run_on_commit):
    with freeze_time("2026-10-13 10:00:00") as clock:
        request_code(client, run_on_commit)
        code = last_code()
        clock.tick(timedelta(minutes=9, seconds=59))

        assert confirm(client, code).status_code == 200


def test_used_code_rejected(client, user, run_on_commit):
    request_code(client, run_on_commit)
    code = last_code()
    assert confirm(client, code).status_code == 200

    response = confirm(client, code, password="AnotherPass22")

    assert response.status_code == 400
    assert error_code(response) == "reset_code_used"
    assert client.post(LOGIN, {"identifier": "amina", "password": NEW_PASSWORD}, format="json").status_code == 200


def test_five_wrong_attempts_lock_the_code(client, user, run_on_commit):
    request_code(client, run_on_commit)
    correct = last_code()
    wrong = "000000" if correct != "000000" else "111111"

    for _ in range(5):
        response = confirm(client, wrong)
        assert response.status_code == 400
        assert error_code(response) == "invalid_reset_code"

    response = confirm(client, correct)

    assert response.status_code == 400
    assert error_code(response) == "reset_code_locked"
    user.refresh_from_db()
    assert user.check_password(DEFAULT_PASSWORD)


def test_four_wrong_attempts_then_correct_code_still_works(client, user, run_on_commit):
    request_code(client, run_on_commit)
    correct = last_code()
    wrong = "000000" if correct != "000000" else "111111"
    for _ in range(4):
        confirm(client, wrong)

    assert confirm(client, correct).status_code == 200


def test_code_stored_hashed(client, user, run_on_commit):
    request_code(client, run_on_commit)
    code = last_code()

    stored = OneTimeCode.objects.get(user=user)

    assert code not in stored.code_hash
    assert len(stored.code_hash) == 64


def test_reset_logs_out_existing_sessions(client, user, run_on_commit):
    token = issue_access_token(user)
    request_code(client, run_on_commit)
    confirm(client, last_code())

    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    assert client.get(ME).status_code == 401


def test_new_code_voids_previous_code(client, user, run_on_commit):
    request_code(client, run_on_commit)
    first = last_code()
    request_code(client, run_on_commit)
    second = last_code()
    if first == second:
        pytest.skip("the two random codes collided (1 in a million)")

    assert confirm(client, first).status_code == 400
    assert confirm(client, second).status_code == 200


def test_new_password_min_8_enforced_and_does_not_consume_code(client, user, run_on_commit):
    request_code(client, run_on_commit)
    code = last_code()

    weak = confirm(client, code, password="short7!")

    assert weak.status_code == 400
    assert "new_password" in weak.json()["error"]["details"]
    assert confirm(client, code).status_code == 200


def test_unknown_email_on_confirm_looks_like_a_wrong_code(client, user):
    response = confirm(client, "123456", email="nobody@example.com")

    assert response.status_code == 400
    assert error_code(response) == "invalid_reset_code"


def test_malformed_code_is_a_validation_error(client, user):
    response = confirm(client, "12ab56")

    assert response.status_code == 400
    assert "code" in response.json()["error"]["details"]


def test_request_is_throttled(client, user, run_on_commit):
    for _ in range(5):
        assert request_code(client, run_on_commit).status_code == 200

    assert request_code(client, run_on_commit).status_code == 429


def test_confirm_is_throttled(client, user):
    for _ in range(10):
        assert confirm(client, "000000").status_code == 400

    assert confirm(client, "000000").status_code == 429


@pytest.mark.django_db(transaction=True)
def test_concurrent_confirms_with_same_code_succeed_only_once(run_on_commit):
    user = UserFactory(email="amina@example.com", username="amina")
    client = APIClient()
    with run_on_commit():
        client.post(REQUEST, {"email": user.email}, format="json")
    code = last_code()

    def attempt(password):
        try:
            confirm_password_reset(user.email, code, password)
            return "ok"
        except DomainError as exc:
            return exc.default_code
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, ["FirstNewPass11", "SecondNewPass22"]))

    assert sorted(results) == ["ok", "reset_code_used"]
