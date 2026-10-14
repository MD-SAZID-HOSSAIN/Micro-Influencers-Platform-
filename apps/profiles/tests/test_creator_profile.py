import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Role
from apps.accounts.tests.factories import UserFactory
from apps.profiles.models import BrandProfile, CreatorProfile
from apps.profiles.services import completion_percent, get_or_create_profile

ME = "/api/v1/creators/me/"


@pytest.fixture
def creator(db):
    return UserFactory(role=Role.CREATOR, full_name="Amina Rahman", username="amina")


def test_profile_rows_are_created_with_the_user_by_role(db):
    creator = UserFactory(role=Role.CREATOR)
    brand = UserFactory(role=Role.BRAND)
    admin = UserFactory(role=Role.ADMIN)

    assert CreatorProfile.objects.filter(user=creator).exists()
    assert BrandProfile.objects.filter(user=brand).exists()
    assert not CreatorProfile.objects.filter(user=admin).exists()
    assert not BrandProfile.objects.filter(user=admin).exists()


def test_get_or_create_profile_returns_existing_row(creator):
    assert get_or_create_profile(creator) == CreatorProfile.objects.get(user=creator)


def test_get_or_create_profile_rejects_admin(db):
    with pytest.raises(ValueError):
        get_or_create_profile(UserFactory(role=Role.ADMIN))


def test_new_creator_profile_is_empty_with_0_percent(creator, auth_client):
    response = auth_client(creator).get(ME)

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == creator.id
    assert body["username"] == "amina"
    assert body["full_name"] == "Amina Rahman"
    assert body["photo_url"] is None
    assert body["bio"] == ""
    assert body["niche"] is None
    assert body["primary_platform"] is None
    assert body["rate_post"] is None
    assert body["completion_percent"] == 0


def test_completion_percent_exact_values(creator):
    profile = CreatorProfile.objects.get(user=creator)
    assert completion_percent(profile) == 0

    profile.photo_url = "https://img.example.com/a.png"
    profile.bio = "Fitness coach"
    profile.niche = "fitness"
    profile.primary_platform = "youtube"
    assert completion_percent(profile) == 50

    profile.city = "Dhaka"
    assert completion_percent(profile) == 50  # location needs city AND country
    profile.country = "Bangladesh"
    assert completion_percent(profile) == 63  # 5 of 8, rounded half-up

    profile.rate_video = "200.00"
    assert completion_percent(profile) == 75  # 6 of 8 (stats and portfolio come later)


def test_patch_updates_profile_and_full_name(creator, auth_client):
    response = auth_client(creator).patch(
        ME,
        {
            "full_name": "Amina R.",
            "bio": "Fitness coach",
            "niche": "fitness",
            "primary_platform": "youtube",
            "city": "Dhaka",
            "country": "Bangladesh",
            "rate_post": "150.00",
            "rate_story": "50.50",
            "rate_video": "300",
        },
        format="json",
    )

    assert response.status_code == 200
    body = response.json()
    assert body["full_name"] == "Amina R."
    assert body["niche"] == "fitness"
    assert body["rate_story"] == "50.50"
    assert body["completion_percent"] == 63
    creator.refresh_from_db()
    assert creator.full_name == "Amina R."


def test_patch_updates_only_own_profile(creator, auth_client):
    other = UserFactory(role=Role.CREATOR)

    auth_client(creator).patch(ME, {"bio": "mine"}, format="json")

    assert CreatorProfile.objects.get(user=creator).bio == "mine"
    assert CreatorProfile.objects.get(user=other).bio == ""


def test_patch_cannot_change_role_or_email(creator, auth_client):
    auth_client(creator).patch(ME, {"role": "brand", "email": "x@evil.com"}, format="json")

    creator.refresh_from_db()
    assert creator.role == Role.CREATOR
    assert creator.email != "x@evil.com"


def test_blank_photo_url_is_stored_and_returned_as_null(creator, auth_client):
    client = auth_client(creator)
    client.patch(ME, {"photo_url": "https://img.example.com/a.png"}, format="json")

    response = client.patch(ME, {"photo_url": ""}, format="json")

    assert response.status_code == 200
    assert response.json()["photo_url"] is None
    assert CreatorProfile.objects.get(user=creator).photo_url is None


@pytest.mark.parametrize(
    "url", ["javascript:alert(1)", "data:text/html,x", "//evil.com/a.png", "ftp://x.com/a.png"]
)
def test_unsafe_photo_url_rejected(creator, auth_client, url):  # RF2
    response = auth_client(creator).patch(ME, {"photo_url": url}, format="json")

    assert response.status_code == 400
    assert "photo_url" in response.json()["error"]["details"]


def test_html_in_bio_and_names_is_stripped(creator, auth_client):  # RF2
    response = auth_client(creator).patch(
        ME,
        {"bio": "<script>alert(1)</script>Hello", "city": "<b>Dhaka</b>", "full_name": "<i>Amina</i>"},
        format="json",
    )

    body = response.json()
    assert body["bio"] == "alert(1)Hello"
    assert body["city"] == "Dhaka"
    assert body["full_name"] == "Amina"


@pytest.mark.parametrize("field", ["rate_post", "rate_story", "rate_video"])
def test_negative_rate_rejected(creator, auth_client, field):
    response = auth_client(creator).patch(ME, {field: "-1"}, format="json")

    assert response.status_code == 400
    assert field in response.json()["error"]["details"]


def test_rate_can_be_cleared_with_null(creator, auth_client):
    client = auth_client(creator)
    client.patch(ME, {"rate_post": "100"}, format="json")

    response = client.patch(ME, {"rate_post": None}, format="json")

    assert response.json()["rate_post"] is None


@pytest.mark.parametrize("payload", [{"niche": "astrology"}, {"primary_platform": "myspace"}])
def test_invalid_choice_rejected(creator, auth_client, payload):
    assert auth_client(creator).patch(ME, payload, format="json").status_code == 400


def test_brand_cannot_use_creator_endpoint(db, auth_client):
    brand = UserFactory(role=Role.BRAND)

    assert auth_client(brand).get(ME).status_code == 403
    assert auth_client(brand).patch(ME, {"bio": "x"}, format="json").status_code == 403


def test_unauthenticated_gets_401(db):
    assert APIClient().get(ME).status_code == 401
