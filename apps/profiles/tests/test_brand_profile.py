import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Role
from apps.accounts.tests.factories import UserFactory
from apps.profiles.models import BrandProfile

ME = "/api/v1/brands/me/"


def detail(user_id):
    return f"/api/v1/brands/{user_id}/"


@pytest.fixture
def brand(db):
    return UserFactory(role=Role.BRAND, full_name="Acme Owner", username="acme")


def test_new_brand_profile_is_empty(brand, auth_client):
    response = auth_client(brand).get(ME)

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == brand.id
    assert body["company_name"] == ""
    assert body["logo_url"] is None


def test_patch_updates_company_profile(brand, auth_client):
    response = auth_client(brand).patch(
        ME,
        {
            "company_name": "Acme Foods",
            "industry": "Food",
            "website": "https://acme.example.com",
            "logo_url": "https://acme.example.com/logo.png",
            "about": "We make snacks.",
        },
        format="json",
    )

    assert response.status_code == 200
    assert response.json()["company_name"] == "Acme Foods"
    assert BrandProfile.objects.get(user=brand).website == "https://acme.example.com"


@pytest.mark.parametrize("field", ["website", "logo_url"])
@pytest.mark.parametrize("url", ["javascript:alert(1)", "data:image/svg+xml,x", "acme.com"])
def test_unsafe_website_and_logo_rejected(brand, auth_client, field, url):  # RF2
    response = auth_client(brand).patch(ME, {field: url}, format="json")

    assert response.status_code == 400
    assert field in response.json()["error"]["details"]


def test_html_in_about_and_company_name_is_stripped(brand, auth_client):  # RF2
    response = auth_client(brand).patch(
        ME, {"about": "<img src=x onerror=alert(1)>Snacks", "company_name": "<b>Acme</b>"}, format="json"
    )

    assert response.json()["about"] == "Snacks"
    assert response.json()["company_name"] == "Acme"


def test_blank_logo_url_returns_null(brand, auth_client):
    client = auth_client(brand)
    client.patch(ME, {"logo_url": "https://acme.example.com/logo.png"}, format="json")

    assert client.patch(ME, {"logo_url": ""}, format="json").json()["logo_url"] is None


def test_blank_website_is_allowed(brand, auth_client):
    assert auth_client(brand).patch(ME, {"website": ""}, format="json").status_code == 200


def test_creator_cannot_use_brand_me_endpoint(db, auth_client):
    creator = UserFactory(role=Role.CREATOR)

    assert auth_client(creator).get(ME).status_code == 403


def test_creator_can_view_brand_profile_by_id(brand, auth_client):
    BrandProfile.objects.filter(user=brand).update(company_name="Acme Foods", industry="Food")
    creator = UserFactory(role=Role.CREATOR)

    response = auth_client(creator).get(detail(brand.id))

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == brand.id
    assert body["company_name"] == "Acme Foods"
    assert body["industry"] == "Food"


def test_brand_cannot_view_brand_profile_by_id(brand, auth_client):
    other = UserFactory(role=Role.BRAND)

    assert auth_client(brand).get(detail(other.id)).status_code == 403


def test_unauthenticated_brand_profile_is_401(brand):
    assert APIClient().get(detail(brand.id)).status_code == 401


def test_unknown_brand_id_is_404(db, auth_client):
    creator = UserFactory(role=Role.CREATOR)

    assert auth_client(creator).get(detail(999999)).status_code == 404


def test_a_creators_id_is_not_a_brand_profile(db, auth_client):
    creator = UserFactory(role=Role.CREATOR)
    other_creator = UserFactory(role=Role.CREATOR)

    assert auth_client(creator).get(detail(other_creator.id)).status_code == 404


def test_brand_can_upload_and_delete_logo(brand, auth_client):
    from django.core.files.uploadedfile import SimpleUploadedFile

    client = auth_client(brand)
    image = SimpleUploadedFile("logo.png", b"\x89PNG\r\n\x1a\nfakeimagecontent", content_type="image/png")
    response = client.post("/api/v1/brands/me/logo/", {"logo": image}, format="multipart")
    assert response.status_code == 200
    assert "/media/logos/" in response.json()["logo_url"]
    assert BrandProfile.objects.get(user=brand).logo_url is not None

    del_resp = client.delete("/api/v1/brands/me/logo/")
    assert del_resp.status_code == 200
    assert del_resp.json()["logo_url"] is None
    assert BrandProfile.objects.get(user=brand).logo_url is None
