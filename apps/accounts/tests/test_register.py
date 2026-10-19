import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.accounts.services import register_user
from apps.core.exceptions import DomainError

URL = "/api/v1/auth/register/"


def payload(**overrides):
    data = {
        "role": "creator",
        "full_name": "Amina Rahman",
        "email": "amina@example.com",
        "username": "amina",
        "password": "S3curePass!",
        "mobile_number": "+8801712345678",
    }
    data.update(overrides)
    return data


@pytest.fixture
def client():
    return APIClient()


@pytest.mark.django_db
def test_register_creator_returns_201_without_password(client):
    response = client.post(URL, payload(), format="json")

    assert response.status_code == 201
    body = response.json()
    assert body["role"] == "creator"
    assert body["email"] == "amina@example.com"
    assert body["username"] == "amina"
    assert "password" not in body
    assert "access" not in body
    assert User.objects.get(username="amina").role == Role.CREATOR


@pytest.mark.django_db
def test_register_brand(client):
    response = client.post(URL, payload(role="brand", username="acme", email="a@acme.com"), format="json")

    assert response.status_code == 201
    assert response.json()["role"] == "brand"


@pytest.mark.django_db
def test_register_requires_role_before_details(client):
    data = payload()
    del data["role"]

    response = client.post(URL, data, format="json")

    assert response.status_code == 400
    assert "role" in response.json()["error"]["details"]


@pytest.mark.django_db
def test_password_shorter_than_8_rejected(client):
    response = client.post(URL, payload(password="short7!"), format="json")

    assert response.status_code == 400
    assert "password" in response.json()["error"]["details"]


@pytest.mark.django_db
def test_password_of_exactly_8_characters_accepted(client):
    response = client.post(URL, payload(password="tq7Xw9Zk"), format="json")

    assert response.status_code == 201


@pytest.mark.django_db
def test_duplicate_email_case_insensitive_rejected(client):
    client.post(URL, payload(email="A@x.com", username="first"), format="json")

    response = client.post(URL, payload(email="a@x.com", username="second"), format="json")

    assert response.status_code == 400
    assert "email" in response.json()["error"]["details"]


@pytest.mark.django_db
def test_duplicate_username_rejected(client):
    client.post(URL, payload(), format="json")

    response = client.post(URL, payload(email="other@example.com"), format="json")

    assert response.status_code == 400
    assert "username" in response.json()["error"]["details"]


@pytest.mark.django_db
def test_duplicate_username_differing_only_by_case_rejected(client):
    client.post(URL, payload(username="Amina"), format="json")

    response = client.post(URL, payload(username="amina", email="other@example.com"), format="json")

    assert response.status_code == 400
    assert "username" in response.json()["error"]["details"]


@pytest.mark.django_db
def test_admin_role_not_registrable(client):
    response = client.post(URL, payload(role="admin"), format="json")

    assert response.status_code == 400
    assert "role" in response.json()["error"]["details"]
    assert not User.objects.filter(role=Role.ADMIN).exists()


@pytest.mark.django_db
def test_register_user_service_rejects_admin_role():
    with pytest.raises(DomainError):
        register_user(
            role="admin",
            full_name="Evil",
            email="e@x.com",
            username="evil",
            password="S3curePass!",
            mobile_number="+8801712345678",
        )


@pytest.mark.django_db
def test_password_is_hashed_not_stored_in_plain_text(client):
    client.post(URL, payload(), format="json")

    user = User.objects.get(username="amina")

    assert user.password != "S3curePass!"
    assert "S3curePass!" not in user.password
    assert user.check_password("S3curePass!")


def test_production_password_hasher_is_djangos_default():
    from django.conf import global_settings

    from config.settings import base

    assert not hasattr(base, "PASSWORD_HASHERS")
    assert global_settings.PASSWORD_HASHERS[0].endswith("PBKDF2PasswordHasher")


@pytest.mark.django_db
@pytest.mark.parametrize("number", ["+8801712345678", "01712345678", "+880 1712-345678"])
def test_valid_mobile_numbers_accepted(client, number):
    response = client.post(URL, payload(mobile_number=number), format="json")

    assert response.status_code == 201


@pytest.mark.django_db
@pytest.mark.parametrize("number", ["abc", "123", "+1234567890123456", ""])
def test_invalid_mobile_numbers_rejected(client, number):
    response = client.post(URL, payload(mobile_number=number), format="json")

    assert response.status_code == 400
    assert "mobile_number" in response.json()["error"]["details"]


@pytest.mark.django_db
def test_html_in_full_name_is_stripped(client):
    client.post(URL, payload(full_name="<script>x</script>Amina"), format="json")

    assert User.objects.get(username="amina").full_name == "xAmina"


@pytest.mark.django_db
def test_register_is_throttled(client):
    for i in range(5):
        ok = client.post(URL, payload(username=f"u{i}", email=f"u{i}@x.com"), format="json")
        assert ok.status_code == 201

    response = client.post(URL, payload(username="u9", email="u9@x.com"), format="json")

    assert response.status_code == 429


@pytest.mark.django_db
@pytest.mark.parametrize("password", ["12345678", "password", "qwertyuiop", "99999999"])
def test_common_or_all_digit_passwords_are_rejected(client, password):
    response = client.post(URL, payload(password=password), format="json")

    assert response.status_code == 400
    assert "password" in response.json()["error"]["details"]


@pytest.mark.django_db
def test_a_password_that_is_just_the_username_is_rejected(client):
    response = client.post(URL, payload(username="amina_rahman", password="amina_rahman"), format="json")

    assert response.status_code == 400
    assert "password" in response.json()["error"]["details"]
