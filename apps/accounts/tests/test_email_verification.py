import re
from datetime import timedelta

import pytest
from django.core import mail
from freezegun import freeze_time
from rest_framework.test import APIClient

from apps.accounts.models import OneTimeCode, Role, User
from apps.accounts.services import issue_access_token
from apps.accounts.tests.factories import DEFAULT_PASSWORD, UserFactory

REGISTER = "/api/v1/auth/register/"
LOGIN = "/api/v1/auth/login/"
ME = "/api/v1/auth/me/"
VERIFY = "/api/v1/auth/email/verify/"
RESEND = "/api/v1/auth/email/resend/"
SETTINGS = "/api/v1/settings/notifications/"
RESET_REQUEST = "/api/v1/auth/password-reset/request/"


def last_code():
    match = re.search(r"\b(\d{6})\b", mail.outbox[-1].body)
    assert match, mail.outbox[-1].body
    return match.group(1)


def error_code(response):
    return response.json()["error"]["code"]


@pytest.fixture
def user(db):
    return UserFactory(role=Role.BRAND, email="amina@example.com", email_verified=False)


def register(client, run_on_commit, **overrides):
    data = {
        "role": "brand",
        "full_name": "Amina Rahman",
        "email": "new@example.com",
        "username": "newuser",
        "password": DEFAULT_PASSWORD,
        "mobile_number": "+8801712345678",
    }
    data.update(overrides)
    with run_on_commit():
        return client.post(REGISTER, data, format="json")


# ---- after registration ---------------------------------------------------------------------------


def test_a_verification_code_is_emailed_after_registration(db, run_on_commit):
    response = register(APIClient(), run_on_commit)

    assert response.status_code == 201
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["new@example.com"]
    assert re.search(r"\b\d{6}\b", mail.outbox[0].body)
    assert OneTimeCode.objects.filter(user__email="new@example.com", purpose="email_verification").count() == 1


@pytest.mark.parametrize("role", ["creator", "brand"])
def test_both_roles_get_a_verification_code_after_registration(db, run_on_commit, role):
    response = register(APIClient(), run_on_commit, role=role)

    assert response.status_code == 201
    assert len(mail.outbox) == 1 and mail.outbox[0].to == ["new@example.com"]
    assert re.search(r"\b\d{6}\b", mail.outbox[0].body)
    assert OneTimeCode.objects.filter(user__email="new@example.com", purpose="email_verification").count() == 1


def test_a_creator_can_verify_their_email_with_the_code(db, run_on_commit):
    client = APIClient()
    register(client, run_on_commit, role="creator")
    token = client.post(LOGIN, {"identifier": "newuser", "password": DEFAULT_PASSWORD}, format="json").json()["access"]
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    response = client.post(VERIFY, {"code": last_code()}, format="json")

    assert response.status_code == 200
    assert User.objects.get(username="newuser").email_verified is True


def test_a_verified_email_does_not_let_a_creator_apply_without_youtube(db, auth_client):
    """Creators are Verified by connecting YouTube; the email code is a separate check."""
    from apps.campaigns.models import Campaign
    from apps.campaigns.tests.factories import CampaignFactory

    creator = UserFactory(role=Role.CREATOR, email_verified=True)
    campaign = CampaignFactory(status=Campaign.Status.PUBLISHED)

    response = auth_client(creator).post(
        f"/api/v1/campaigns/{campaign.pk}/proposals/", {"cover_message": "Hello"}, format="json"
    )

    assert response.status_code == 403
    assert error_code(response) == "creator_youtube_required"


def test_a_creator_can_still_reset_a_forgotten_password(db, run_on_commit):
    UserFactory(role=Role.CREATOR, email="amina@example.com")

    with run_on_commit():
        response = APIClient().post(RESET_REQUEST, {"email": "amina@example.com"}, format="json")

    assert response.status_code == 200
    assert len(mail.outbox) == 1 and "reset" in mail.outbox[0].subject.lower()


def test_new_accounts_are_unverified_and_can_still_log_in(db, run_on_commit):
    client = APIClient()
    register(client, run_on_commit)

    login = client.post(LOGIN, {"identifier": "newuser", "password": DEFAULT_PASSWORD}, format="json")

    assert login.status_code == 200
    assert login.json()["user"]["email_verified"] is False
    assert User.objects.get(username="newuser").email_verified is False


def test_me_shows_whether_the_email_is_verified(user, auth_client):
    assert auth_client(user).get(ME).json()["email_verified"] is False
    User.objects.filter(pk=user.pk).update(email_verified=True)

    assert auth_client(user).get(ME).json()["email_verified"] is True


# ---- verifying -----------------------------------------------------------------------------------------


def test_the_right_code_verifies_the_email(db, run_on_commit, auth_client):
    register(APIClient(), run_on_commit)
    account = User.objects.get(username="newuser")

    response = auth_client(account).post(VERIFY, {"code": last_code()}, format="json")

    assert response.status_code == 200
    assert response.json()["email_verified"] is True
    account.refresh_from_db()
    assert account.email_verified is True


def test_a_wrong_code_is_rejected_with_a_verification_error_code(db, run_on_commit, auth_client):
    register(APIClient(), run_on_commit)
    account = User.objects.get(username="newuser")
    wrong = "000000" if last_code() != "000000" else "111111"

    response = auth_client(account).post(VERIFY, {"code": wrong}, format="json")

    assert response.status_code == 400
    assert error_code(response) == "invalid_verification_code"
    account.refresh_from_db()
    assert account.email_verified is False


def test_five_wrong_attempts_lock_the_code(db, run_on_commit, auth_client):
    register(APIClient(), run_on_commit)
    account = User.objects.get(username="newuser")
    correct = last_code()
    wrong = "000000" if correct != "000000" else "111111"
    client = auth_client(account)

    for _ in range(5):
        assert client.post(VERIFY, {"code": wrong}, format="json").status_code == 400
    response = client.post(VERIFY, {"code": correct}, format="json")

    assert error_code(response) == "verification_code_locked"
    account.refresh_from_db()
    assert account.email_verified is False


def test_an_expired_code_is_rejected(db, run_on_commit, auth_client):
    with freeze_time("2026-10-13 12:00:00") as clock:
        register(APIClient(), run_on_commit)
        account = User.objects.get(username="newuser")
        client = auth_client(account)
        code = last_code()
        clock.tick(timedelta(minutes=10, seconds=1))

        response = client.post(VERIFY, {"code": code}, format="json")

    assert error_code(response) == "verification_code_expired"


def test_a_code_works_only_once(db, run_on_commit, auth_client):
    register(APIClient(), run_on_commit)
    account = User.objects.get(username="newuser")
    code = last_code()
    client = auth_client(account)
    assert client.post(VERIFY, {"code": code}, format="json").status_code == 200

    assert error_code(client.post(VERIFY, {"code": code}, format="json")) == "verification_code_used"


def test_a_password_reset_code_cannot_verify_an_email(user, run_on_commit, auth_client):
    with run_on_commit():
        APIClient().post(RESET_REQUEST, {"email": user.email}, format="json")
    reset_code = last_code()

    response = auth_client(user).post(VERIFY, {"code": reset_code}, format="json")

    assert response.status_code == 400
    user.refresh_from_db()
    assert user.email_verified is False


def test_the_code_must_be_six_digits(user, auth_client):
    response = auth_client(user).post(VERIFY, {"code": "12ab56"}, format="json")

    assert response.status_code == 400
    assert "code" in response.json()["error"]["details"]


# ---- resending -------------------------------------------------------------------------------------------


def test_resend_within_60_seconds_is_rejected(db, run_on_commit, auth_client):
    with freeze_time("2026-10-13 12:00:00") as clock:
        register(APIClient(), run_on_commit)
        account = User.objects.get(username="newuser")
        client = auth_client(account)
        clock.tick(timedelta(seconds=59))

        response = client.post(RESEND)

    assert response.status_code == 429
    assert error_code(response) == "resend_cooldown"
    assert len(mail.outbox) == 1


def test_resend_after_the_cooldown_sends_a_new_code_and_voids_the_old_one(db, run_on_commit, auth_client):
    with freeze_time("2026-10-13 12:00:00") as clock:
        register(APIClient(), run_on_commit)
        account = User.objects.get(username="newuser")
        client = auth_client(account)
        first = last_code()
        clock.tick(timedelta(seconds=61))

        with run_on_commit():
            response = client.post(RESEND)
        second = last_code()

        assert response.status_code == 200
        assert len(mail.outbox) == 2
        if first != second:  # a 1-in-a-million collision would make this check meaningless
            assert error_code(client.post(VERIFY, {"code": first}, format="json")) == "invalid_verification_code"
        assert client.post(VERIFY, {"code": second}, format="json").status_code == 200


def test_the_first_resend_works_for_an_account_with_no_code_yet(user, run_on_commit, auth_client):
    with run_on_commit():
        response = auth_client(user).post(RESEND)

    assert response.status_code == 200
    assert len(mail.outbox) == 1


def test_resend_for_an_already_verified_account_is_a_conflict(user, auth_client):
    User.objects.filter(pk=user.pk).update(email_verified=True)

    response = auth_client(user).post(RESEND)

    assert response.status_code == 409
    assert error_code(response) == "already_verified"
    assert mail.outbox == []


def test_verification_codes_are_sent_even_when_notification_emails_are_off(user, run_on_commit, auth_client):
    User.objects.filter(pk=user.pk).update(email_notifications_enabled=False)

    with run_on_commit():
        auth_client(user).post(RESEND)

    assert len(mail.outbox) == 1


def test_verify_and_resend_require_authentication(db):
    assert APIClient().post(VERIFY, {"code": "123456"}, format="json").status_code == 401
    assert APIClient().post(RESEND).status_code == 401


# ---- notification settings -----------------------------------------------------------------------------------


def test_notification_settings_default_to_on(user, auth_client):
    response = auth_client(user).get(SETTINGS)

    assert response.status_code == 200
    assert response.json() == {"email_enabled": True, "email_verified": False}


def test_notification_emails_can_be_switched_off_and_on(user, auth_client):
    client = auth_client(user)

    off = client.patch(SETTINGS, {"email_enabled": False}, format="json")
    assert off.json()["email_enabled"] is False
    user.refresh_from_db()
    assert user.email_notifications_enabled is False

    on = client.patch(SETTINGS, {"email_enabled": True}, format="json")
    assert on.json()["email_enabled"] is True


def test_notification_settings_cannot_set_the_verified_flag(user, auth_client):
    auth_client(user).patch(SETTINGS, {"email_enabled": True, "email_verified": True}, format="json")

    user.refresh_from_db()
    assert user.email_verified is False


def test_notification_settings_validation_and_auth(user, auth_client):
    assert auth_client(user).patch(SETTINGS, {"email_enabled": "maybe"}, format="json").status_code == 400
    assert auth_client(user).put(SETTINGS, {"email_enabled": True}, format="json").status_code == 405
    assert APIClient().get(SETTINGS).status_code == 401


def test_settings_work_for_brands_too(db, auth_client):
    brand = UserFactory(role=Role.BRAND)

    assert auth_client(brand).get(SETTINGS).status_code == 200


def test_issue_access_token_is_unaffected_by_verification(user):
    assert issue_access_token(user)  # sanity: verification never gates tokens
