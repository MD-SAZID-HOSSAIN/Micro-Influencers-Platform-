import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.accounts.models import Role
from apps.accounts.services import issue_access_token
from apps.accounts.tests.factories import DEFAULT_PASSWORD, UserFactory

LOGIN = "/api/v1/auth/login/"
LOGOUT = "/api/v1/auth/logout/"
ME = "/api/v1/auth/me/"


@pytest.fixture
def client():
    return APIClient()


def login(client, identifier, password=DEFAULT_PASSWORD):
    return client.post(LOGIN, {"identifier": identifier, "password": password}, format="json")


def bearer(client, token):
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return client


@pytest.mark.django_db
def test_login_with_email(client):
    user = UserFactory(email="amina@example.com")

    response = login(client, "amina@example.com")

    assert response.status_code == 200
    assert response.json()["user"]["id"] == user.id
    assert response.json()["access"]


@pytest.mark.django_db
def test_login_with_username(client):
    user = UserFactory(username="amina")

    response = login(client, "amina")

    assert response.status_code == 200
    assert response.json()["user"]["id"] == user.id


@pytest.mark.django_db
def test_login_email_ignores_case_and_surrounding_whitespace(client):
    UserFactory(email="amina@example.com")

    assert login(client, "  Amina@Example.COM ").status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize("role", [Role.CREATOR, Role.BRAND])
def test_login_returns_role_for_routing(client, role):
    UserFactory(username="someone", role=role)

    response = login(client, "someone")

    assert response.json()["user"]["role"] == role.value


@pytest.mark.django_db
def test_wrong_password_returns_clear_error_identical_to_unknown_user(client):
    UserFactory(username="amina")

    wrong_password = login(client, "amina", "not-the-password")
    unknown_user = login(client, "nobody", "whatever1")

    assert wrong_password.status_code == unknown_user.status_code == 401
    assert wrong_password.json() == unknown_user.json()
    error = wrong_password.json()["error"]
    assert error["code"] == "invalid_credentials"
    assert error["message"] == "Invalid email/username or password."


@pytest.mark.django_db
def test_inactive_user_cannot_login(client):
    UserFactory(username="suspended", is_active=False)

    response = login(client, "suspended")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"


@pytest.mark.django_db
def test_token_lifetime_is_24_hours():
    token = AccessToken(issue_access_token(UserFactory()))

    assert token["exp"] - token["iat"] == 24 * 60 * 60


@pytest.mark.django_db
def test_token_carries_token_version_claim():
    user = UserFactory(token_version=3)

    assert AccessToken(issue_access_token(user))["tv"] == 3


@pytest.mark.django_db
def test_protected_route_without_token_is_401(client):
    response = client.get(ME)

    assert response.status_code == 401


@pytest.mark.django_db
def test_me_returns_current_user(client):
    user = UserFactory()

    response = bearer(client, issue_access_token(user)).get(ME)

    assert response.status_code == 200
    assert response.json()["id"] == user.id


@pytest.mark.django_db
def test_garbage_token_is_401(client):
    assert bearer(client, "not.a.jwt").get(ME).status_code == 401


@pytest.mark.django_db
def test_token_with_old_token_version_rejected(client):
    user = UserFactory()
    token = issue_access_token(user)
    user.token_version += 1
    user.save(update_fields=["token_version"])

    assert bearer(client, token).get(ME).status_code == 401


@pytest.mark.django_db
def test_token_of_deactivated_user_rejected(client):
    user = UserFactory()
    token = issue_access_token(user)
    user.is_active = False
    user.save(update_fields=["is_active"])

    assert bearer(client, token).get(ME).status_code == 401


@pytest.mark.django_db
def test_logout_invalidates_token(client):
    user = UserFactory()
    token = issue_access_token(user)
    bearer(client, token)
    assert client.get(ME).status_code == 200

    assert client.post(LOGOUT).status_code == 204

    assert client.get(ME).status_code == 401
    user.refresh_from_db()
    assert user.token_version == 1


@pytest.mark.django_db
def test_logout_requires_authentication(client):
    assert client.post(LOGOUT).status_code == 401


@pytest.mark.django_db
def test_login_after_logout_issues_working_token(client):
    user = UserFactory(username="amina")
    bearer(client, issue_access_token(user)).post(LOGOUT)
    client.credentials()

    token = login(client, "amina").json()["access"]

    assert bearer(client, token).get(ME).status_code == 200


@pytest.mark.django_db
def test_login_throttled(client):
    for _ in range(10):
        assert login(client, "nobody", "whatever1").status_code == 401

    assert login(client, "nobody", "whatever1").status_code == 429
