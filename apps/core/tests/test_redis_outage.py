"""When Redis is unreachable, people must still be able to log in, register and reset a password.

Redis backs the rate-limit counters (and the YouTube OAuth state). Before, any cache error inside a
throttled view became an HTTP 500, so a Redis outage meant nobody could log in or recover an account.
Rate limiting now pauses (and says so in the log) instead of taking the site down.
"""
import logging

import pytest
from django.core import mail
from django.core.exceptions import ImproperlyConfigured
from rest_framework.test import APIClient

from apps.accounts.models import Role
from apps.accounts.tests.factories import DEFAULT_PASSWORD, UserFactory
from apps.core.throttling import FailOpenScopedRateThrottle

LOGIN = "/api/v1/auth/login/"
REGISTER = "/api/v1/auth/register/"
RESET = "/api/v1/auth/password-reset/request/"
ADMIN_LOGIN = "/api/v1/admin/auth/login/"


def login(client, identifier, password=DEFAULT_PASSWORD, path=LOGIN):
    return client.post(path, {"identifier": identifier, "password": password}, format="json")


# ---- the throttle fails open ----------------------------------------------------------------------


def test_login_works_while_the_cache_is_down_and_the_pause_is_logged(db, redis_down, caplog):
    UserFactory(username="amina")

    with caplog.at_level(logging.WARNING):
        response = login(APIClient(), "amina")

    assert response.status_code == 200
    assert "Rate limiting is unavailable" in caplog.text


def test_a_wrong_password_is_still_a_401_not_a_500_while_the_cache_is_down(db, redis_down):
    assert login(APIClient(), "nobody", "whatever1").status_code == 401


def test_registration_works_while_the_cache_is_down(db, redis_down):
    response = APIClient().post(
        REGISTER,
        {
            "role": "creator",
            "full_name": "Amina Rahman",
            "email": "amina@example.com",
            "username": "amina",
            "password": DEFAULT_PASSWORD,
            "mobile_number": "+8801712345678",
        },
        format="json",
    )

    assert response.status_code == 201


def test_password_reset_works_while_the_cache_is_down(db, redis_down, run_on_commit):
    UserFactory(email="amina@example.com")

    with run_on_commit():
        response = APIClient().post(RESET, {"email": "amina@example.com"}, format="json")

    assert response.status_code == 200
    assert len(mail.outbox) == 1


def test_the_admin_login_works_while_the_cache_is_down(db, redis_down):
    UserFactory(role=Role.ADMIN, username="root")

    assert login(APIClient(), "root", path=ADMIN_LOGIN).status_code == 200


def test_authenticated_throttled_endpoints_also_keep_working(db, redis_down, auth_client):
    user = UserFactory(role=Role.BRAND, email_verified=False)  # only brands verify their email

    response = auth_client(user).post("/api/v1/auth/email/resend/")

    assert response.status_code == 200


# ---- but real mistakes are not hidden ---------------------------------------------------------------


def test_a_throttle_scope_with_no_configured_rate_is_still_an_error_not_a_silent_pass(db):
    """Failing open is for connection trouble only; a typo in a scope name must not switch limiting off."""

    class View:
        throttle_scope = "scope_nobody_configured"

    class Request:
        user = None
        META = {"REMOTE_ADDR": "127.0.0.1"}

    with pytest.raises(ImproperlyConfigured):
        FailOpenScopedRateThrottle().allow_request(Request(), View())


def test_limits_are_still_enforced_when_the_cache_is_healthy(db):
    client = APIClient()
    for _ in range(10):
        assert login(client, "nobody", "whatever1").status_code == 401

    assert login(client, "nobody", "whatever1").status_code == 429


# ---- it fails fast, not slowly --------------------------------------------------------------------------


def test_the_redis_cache_has_short_timeouts_so_an_outage_cannot_hang_requests():
    from config.settings import base

    options = base.CACHES["default"]["OPTIONS"]

    assert 0 < options["socket_connect_timeout"] <= 5
    assert 0 < options["socket_timeout"] <= 5
