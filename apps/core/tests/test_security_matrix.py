"""Whole-API security checks that walk the URLconf, so new routes are covered automatically.

If you add a route and one of these tests fails, that is the point: decide on purpose whether
the route is public, role-gated, or open to any logged-in user, and record it here.
"""
import os
import re
import secrets
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest
from cryptography.fernet import Fernet
from django.urls import get_resolver
from django.urls.resolvers import URLPattern, URLResolver
from rest_framework.permissions import AllowAny
from rest_framework.test import APIClient
from rest_framework.throttling import ScopedRateThrottle

from apps.accounts.models import Role
from apps.accounts.services import issue_access_token
from apps.accounts.tests.factories import UserFactory
from apps.core.permissions import IsAdminRole, IsBrand, IsCreator

BASE_DIR = Path(__file__).resolve().parents[3]

PUBLIC_ROUTES = {
    "/api/v1/health/",
    "/api/v1/auth/register/",
    "/api/v1/auth/login/",
    "/api/v1/admin/auth/login/",  # admin accounts only; ordinary accounts get invalid_credentials
    "/api/v1/auth/password-reset/request/",
    "/api/v1/auth/password-reset/confirm/",
    "/api/v1/social/youtube/callback/",  # a browser redirect from Google; protected by a signed state
    "/api/schema/",
    "/api/docs/",
}

# Open to any logged-in user, whatever their role.
ANY_AUTHENTICATED_ROUTES = {
    "/api/v1/auth/logout/",
    "/api/v1/auth/me/",
    "/api/v1/auth/email/verify/",
    "/api/v1/auth/email/resend/",
    "/api/v1/settings/notifications/",
    "/api/v1/notifications/",
    "/api/v1/notifications/read-all/",
    "/api/v1/notifications/1/read/",
}

ROLE_BY_PERMISSION = {IsCreator: Role.CREATOR, IsBrand: Role.BRAND, IsAdminRole: Role.ADMIN}
METHODS = ("get", "post", "put", "patch", "delete")


def _walk(patterns, prefix=""):
    for pattern in patterns:
        route = prefix + str(pattern.pattern)
        if isinstance(pattern, URLResolver):
            yield from _walk(pattern.url_patterns, route)
        elif isinstance(pattern, URLPattern):
            yield route, pattern.callback


def _concrete(route):
    return "/" + re.sub(
        r"<(\w+):(\w+)>", lambda m: "1" if m.group(1) == "int" else "instagram", route
    )


def routes():
    """[(path, view_class, [implemented methods])] for every route in the project."""
    found = []
    for route, callback in _walk(get_resolver().url_patterns):
        view_class = getattr(callback, "cls", None) or getattr(callback, "view_class", None)
        if view_class is None:
            continue
        allowed = getattr(view_class, "http_method_names", METHODS)
        methods = [m for m in METHODS if m in allowed and hasattr(view_class, m)]
        found.append((_concrete(route), view_class, methods))
    return found


def required_role(view_class):
    for permission in getattr(view_class, "permission_classes", []):
        if permission in ROLE_BY_PERMISSION:
            return ROLE_BY_PERMISSION[permission]
    return None


def is_allow_any(view_class):
    return AllowAny in getattr(view_class, "permission_classes", [])


def call(path, method, token=None):
    client = APIClient()
    if token:
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return getattr(client, method)(path, {}, format="json")


# ---- the walker itself ------------------------------------------------------------------------


def test_the_walker_finds_the_whole_api():
    found = routes()

    assert len(found) >= 40  # a broken walker must not let the other tests pass vacuously
    assert "/api/v1/campaigns/1/proposals/" in {path for path, _, _ in found}


def test_every_route_is_classified_as_public_role_gated_or_any_authenticated():
    unclassified = []
    for path, view_class, _ in routes():
        if path in PUBLIC_ROUTES or required_role(view_class) or path in ANY_AUTHENTICATED_ROUTES:
            continue
        unclassified.append(path)

    assert unclassified == [], f"Classify these routes in test_security_matrix.py: {unclassified}"


def test_public_routes_are_exactly_the_allow_any_views():
    allow_any = {path for path, view_class, _ in routes() if is_allow_any(view_class)}

    assert allow_any == PUBLIC_ROUTES


# ---- authentication ------------------------------------------------------------------------------


def test_every_route_requires_auth_except_the_public_list(db):
    failures = []
    for path, _, methods in routes():
        if path in PUBLIC_ROUTES:
            continue
        for method in methods:
            status = call(path, method).status_code
            if status != 401:
                failures.append((method.upper(), path, status))

    assert failures == []


def test_wrong_roles_are_forbidden_on_every_role_gated_route(db):
    users = {role: UserFactory(role=role) for role in Role}
    tokens = {role: issue_access_token(user) for role, user in users.items()}
    failures, checked = [], 0
    for path, view_class, methods in routes():
        role = required_role(view_class)
        if role is None:
            continue
        for other in Role:
            if other == role:
                continue
            for method in methods:
                checked += 1
                status = call(path, method, tokens[other]).status_code
                if status != 403:
                    failures.append((other.value, method.upper(), path, status))

    assert checked > 50  # every (role-gated route, method, wrong role) combination
    assert failures == []


# ---- secrets never leave the server -----------------------------------------------------------------

FORBIDDEN_KEYS = {
    "password",
    "access_token",
    "refresh_token",
    "access_token_enc",
    "refresh_token_enc",
    "code_hash",
    "token_version",
}


def _keys(value):
    if isinstance(value, dict):
        for key, inner in value.items():
            yield key
            yield from _keys(inner)
    elif isinstance(value, list):
        for inner in value:
            yield from _keys(inner)


def test_no_secret_fields_or_values_appear_in_any_response(db):
    from apps.campaigns.models import Campaign
    from apps.campaigns.tests.factories import CampaignFactory
    from apps.notifications.models import Kind
    from apps.notifications.services import notify
    from apps.profiles.models import PortfolioItem
    from apps.proposals.tests.factories import ProposalFactory
    from apps.social.tests.fakes import make_connection

    creator = UserFactory(role=Role.CREATOR)
    brand = UserFactory(role=Role.BRAND)
    connection = make_connection(creator, access="ya29.SECRET-ACCESS", refresh="1//SECRET-REFRESH")
    PortfolioItem.objects.create(creator=creator, url="https://example.com/p")
    campaign = CampaignFactory(brand=brand, status=Campaign.Status.PUBLISHED)
    ProposalFactory(campaign=campaign, creator=creator)
    notify(creator, Kind.PROPOSAL_ACCEPTED, "hello")

    secrets_that_must_not_leak = [
        "ya29.SECRET-ACCESS",
        "1//SECRET-REFRESH",
        connection.access_token_enc,
        connection.refresh_token_enc,
        creator.password,
        brand.password,
    ]
    creator_urls = [
        "/api/v1/auth/me/",
        "/api/v1/creators/me/",
        "/api/v1/creators/me/stats/",
        "/api/v1/creators/me/portfolio/",
        "/api/v1/creators/me/proposals/",
        "/api/v1/creators/me/dashboard/",
        "/api/v1/social/youtube/",
        "/api/v1/social/youtube/recent-content/",
        "/api/v1/notifications/",
        "/api/v1/campaigns/",
        f"/api/v1/campaigns/{campaign.pk}/",
    ]
    brand_urls = [
        "/api/v1/auth/me/",
        "/api/v1/brands/me/",
        "/api/v1/brands/me/dashboard/",
        "/api/v1/brand/campaigns/",
        f"/api/v1/brand/campaigns/{campaign.pk}/proposals/",
        "/api/v1/creators/",
        f"/api/v1/creators/{creator.pk}/",
    ]
    responses = [
        (url, APIClient(HTTP_AUTHORIZATION=f"Bearer {issue_access_token(user)}").get(url))
        for user, urls in ((creator, creator_urls), (brand, brand_urls))
        for url in urls
    ]
    login = APIClient().post(
        "/api/v1/auth/login/", {"identifier": creator.username, "password": "S3curePass!"}, format="json"
    )
    responses.append(("/api/v1/auth/login/", login))

    for url, response in responses:
        assert response.status_code == 200, url
        assert FORBIDDEN_KEYS.isdisjoint(_keys(response.json())), url
        text = response.content.decode()
        for secret in secrets_that_must_not_leak:
            assert secret not in text, f"{url} leaked a secret"


# ---- throttling -------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "path, scope",
    [
        ("/api/v1/auth/login/", "login"),
        ("/api/v1/admin/auth/login/", "admin_login"),
        ("/api/v1/auth/register/", "register"),
        ("/api/v1/auth/password-reset/request/", "password_reset"),
        ("/api/v1/auth/password-reset/confirm/", "password_reset_confirm"),
        ("/api/v1/auth/email/verify/", "email_verify"),
        ("/api/v1/auth/email/resend/", "email_resend"),
    ],
)
def test_abuse_prone_endpoints_are_throttled(settings, path, scope):
    view_class = next(v for p, v, _ in routes() if p == path)

    assert ScopedRateThrottle in view_class.throttle_classes
    assert view_class.throttle_scope == scope
    assert scope in settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]


def test_a_spoofed_forwarded_for_header_does_not_bypass_throttling(db):
    client = APIClient()
    for n in range(10):
        response = client.post(
            "/api/v1/auth/login/",
            {"identifier": "nobody", "password": "wrong-password"},
            format="json",
            HTTP_X_FORWARDED_FOR=f"203.0.113.{n}",  # a different "client" every time
        )
        assert response.status_code == 401

    response = client.post(
        "/api/v1/auth/login/",
        {"identifier": "nobody", "password": "wrong-password"},
        format="json",
        HTTP_X_FORWARDED_FOR="203.0.113.200",
    )

    assert response.status_code == 429


# ---- errors do not leak -------------------------------------------------------------------------------------------


def test_server_errors_use_the_envelope_and_leak_nothing(db):
    client = APIClient(raise_request_exception=False)
    with mock.patch(
        "apps.accounts.views.authenticate_login", side_effect=RuntimeError("secret internals /srv/app.py")
    ):
        response = client.post(
            "/api/v1/auth/login/", {"identifier": "a", "password": "b"}, format="json"
        )

    assert response.status_code == 500
    assert response.json() == {
        "error": {"code": "server_error", "message": "Something went wrong.", "details": None}
    }
    text = response.content.decode()
    assert "secret internals" not in text and "Traceback" not in text and "/srv/app.py" not in text


def test_unknown_urls_return_the_json_envelope(db):
    response = APIClient().get("/api/v1/definitely/not/a/route/")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


# ---- CORS ---------------------------------------------------------------------------------------------------------


def test_cors_allows_the_frontend_and_rejects_other_origins(db):
    client = APIClient()
    headers = {"HTTP_ACCESS_CONTROL_REQUEST_METHOD": "POST", "HTTP_ACCESS_CONTROL_REQUEST_HEADERS": "authorization"}

    allowed = client.options("/api/v1/auth/login/", HTTP_ORIGIN="http://frontend.test", **headers)
    rejected = client.options("/api/v1/auth/login/", HTTP_ORIGIN="http://evil.test", **headers)

    assert allowed["Access-Control-Allow-Origin"] == "http://frontend.test"
    assert "Access-Control-Allow-Origin" not in rejected


def test_cors_does_not_allow_credentials(db):
    response = APIClient().options(
        "/api/v1/auth/login/",
        HTTP_ORIGIN="http://frontend.test",
        HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
    )

    assert response.get("Access-Control-Allow-Credentials") != "true"  # bearer tokens, no cookies


# ---- production settings -----------------------------------------------------------------------------------------------


def _prod_env(**overrides):
    env = {
        **os.environ,
        "DJANGO_SETTINGS_MODULE": "config.settings.prod",
        "SECRET_KEY": secrets.token_urlsafe(64),
        "ALLOWED_HOSTS": "api.example.com",
        "CORS_ALLOWED_ORIGINS": "https://app.example.com",
        "FRONTEND_URL": "https://app.example.com",
        "OAUTH_ENCRYPTION_KEY": Fernet.generate_key().decode(),
    }
    env.update(overrides)
    return {k: v for k, v in env.items() if v is not None}


def _run(args, env):
    return subprocess.run(
        [sys.executable, *args], cwd=BASE_DIR, env=env, capture_output=True, text=True, timeout=120
    )


def test_production_settings_pass_django_deploy_checks_with_no_warnings():
    result = _run(["manage.py", "check", "--deploy", "--fail-level", "WARNING"], _prod_env())

    assert result.returncode == 0, result.stdout + result.stderr
    assert "no issues" in result.stdout.lower()


@pytest.mark.parametrize(
    "override, message",
    [
        ({"SECRET_KEY": ""}, "SECRET_KEY"),
        ({"ALLOWED_HOSTS": ""}, "ALLOWED_HOSTS"),
        ({"ALLOWED_HOSTS": "*"}, "ALLOWED_HOSTS"),
        ({"CORS_ALLOWED_ORIGINS": "*"}, "CORS_ALLOWED_ORIGINS"),
        ({"CORS_ALLOWED_ORIGINS": ""}, "CORS_ALLOWED_ORIGINS"),
        ({"OAUTH_ENCRYPTION_KEY": ""}, "OAUTH_ENCRYPTION_KEY"),
    ],
)
def test_production_refuses_to_start_with_unsafe_configuration(override, message):
    result = _run(["-c", "import config.settings.prod"], _prod_env(**override))

    assert result.returncode != 0
    assert message in result.stderr


def test_production_enforces_https_and_secure_cookies():
    code = (
        "import config.settings.prod as s;"
        "assert s.SECURE_SSL_REDIRECT is True;"
        "assert s.SECURE_HSTS_SECONDS >= 31536000;"
        "assert s.SESSION_COOKIE_SECURE and s.CSRF_COOKIE_SECURE;"
        "assert s.DEBUG is False;"
        "assert s.NUM_PROXIES == 1"
    )
    result = _run(["-c", code], _prod_env())

    assert result.returncode == 0, result.stderr
