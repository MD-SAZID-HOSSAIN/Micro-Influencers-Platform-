from pathlib import Path

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from apps.accounts.models import Role
from apps.accounts.tests.factories import UserFactory
from apps.campaigns.models import Campaign
from apps.campaigns.tests.factories import CampaignFactory
from apps.profiles.models import BrandProfile, CreatorProfile

JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 64
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
MP4 = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 64

PHOTO = "/api/v1/creators/me/photo/"
LOGO = "/api/v1/brands/me/logo/"


def put(auth_client, user, url, content=JPEG, name="me.jpg", content_type="image/jpeg"):
    file = SimpleUploadedFile(name, content, content_type=content_type)
    return auth_client(user).put(url, {"file": file}, format="multipart")


@pytest.fixture(autouse=True)
def media_root(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    return tmp_path


@pytest.fixture
def creator(db):
    return UserFactory(role=Role.CREATOR)


@pytest.fixture
def brand(db):
    return UserFactory(role=Role.BRAND)


def stored(media_root, relative_url: str) -> Path:
    return Path(media_root, relative_url.removeprefix("/media/"))


# ---- creator photo ---------------------------------------------------------------------------------


def test_a_creator_can_upload_a_photo(creator, auth_client, media_root):
    response = put(auth_client, creator, PHOTO, PNG, "holiday.exe", "application/x-msdownload")

    assert response.status_code == 200
    url = response.json()["photo_url"]
    assert url.startswith("/media/avatars/") and url.endswith(".png")
    assert "holiday" not in url
    assert stored(media_root, url).exists()
    assert CreatorProfile.objects.get(user=creator).photo_url == url


def test_the_new_photo_replaces_and_deletes_the_old_one(creator, auth_client, media_root, run_on_commit):
    first = put(auth_client, creator, PHOTO).json()["photo_url"]
    old_file = stored(media_root, first)

    with run_on_commit():
        second = put(auth_client, creator, PHOTO, PNG, "b.png", "image/png").json()["photo_url"]

    assert second != first
    assert stored(media_root, second).exists()
    assert not old_file.exists()


def test_removing_the_photo_clears_it_and_deletes_the_file(creator, auth_client, media_root, run_on_commit):
    url = put(auth_client, creator, PHOTO).json()["photo_url"]
    path = stored(media_root, url)

    with run_on_commit():
        response = auth_client(creator).delete(PHOTO)

    assert response.status_code == 200
    assert response.json()["photo_url"] is None
    assert not path.exists()
    assert not CreatorProfile.objects.get(user=creator).photo


def test_a_video_or_a_disguised_file_is_not_a_photo(creator, auth_client):
    video = put(auth_client, creator, PHOTO, MP4, "me.jpg", "image/jpeg")
    text = put(auth_client, creator, PHOTO, b"just text", "me.png", "image/png")

    assert video.status_code == 400 and text.status_code == 400
    assert video.json()["error"]["code"] == "unsupported_media"
    assert CreatorProfile.objects.get(user=creator).photo_url is None


def test_a_photo_over_5_mb_is_refused(creator, auth_client, settings):
    settings.MEDIA_MAX_PHOTO_BYTES = 100

    response = put(auth_client, creator, PHOTO, JPEG + b"\x00" * 200)

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "media_too_large"


def test_no_file_is_a_validation_error(creator, auth_client):
    response = auth_client(creator).put(PHOTO, {}, format="multipart")

    assert response.status_code == 400
    assert "file" in response.json()["error"]["details"]


def test_a_link_set_by_hand_replaces_an_uploaded_photo(creator, auth_client, media_root, run_on_commit):
    url = put(auth_client, creator, PHOTO).json()["photo_url"]
    path = stored(media_root, url)

    with run_on_commit():
        response = auth_client(creator).patch(
            "/api/v1/creators/me/", {"photo_url": "https://example.com/me.jpg"}, format="json"
        )

    assert response.json()["photo_url"] == "https://example.com/me.jpg"
    assert not path.exists()
    assert not CreatorProfile.objects.get(user=creator).photo


def test_the_photo_counts_towards_profile_completion(creator, auth_client):
    before = auth_client(creator).get("/api/v1/creators/me/").json()["completion_percent"]

    put(auth_client, creator, PHOTO)

    assert auth_client(creator).get("/api/v1/creators/me/").json()["completion_percent"] > before


# ---- brand logo -------------------------------------------------------------------------------------


def test_a_brand_can_upload_replace_and_remove_a_logo(brand, auth_client, media_root, run_on_commit):
    first = put(auth_client, brand, LOGO).json()["logo_url"]
    assert first.startswith("/media/logos/") and stored(media_root, first).exists()

    with run_on_commit():
        second = put(auth_client, brand, LOGO, PNG, "l.png", "image/png").json()["logo_url"]
        removed = auth_client(brand).delete(LOGO)

    assert not stored(media_root, first).exists()
    assert not stored(media_root, second).exists()
    assert removed.json()["logo_url"] is None
    assert not BrandProfile.objects.get(user=brand).logo


def test_a_brand_logo_is_refused_when_it_is_not_a_photo(brand, auth_client):
    assert put(auth_client, brand, LOGO, MP4, "l.mp4", "video/mp4").status_code == 400


# ---- who may do it ------------------------------------------------------------------------------------


def test_roles_cannot_use_each_others_endpoints(creator, brand, auth_client):
    assert put(auth_client, brand, PHOTO).status_code == 403
    assert put(auth_client, creator, LOGO).status_code == 403


def test_anonymous_users_cannot_upload():
    file = SimpleUploadedFile("a.jpg", JPEG, content_type="image/jpeg")

    assert APIClient().put(PHOTO, {"file": file}, format="multipart").status_code == 401


# ---- where the picture appears -------------------------------------------------------------------------


def test_the_picture_shows_in_login_and_me(creator, brand, auth_client):
    photo = put(auth_client, creator, PHOTO).json()["photo_url"]
    logo = put(auth_client, brand, LOGO).json()["logo_url"]

    assert auth_client(creator).get("/api/v1/auth/me/").json()["avatar_url"] == photo
    assert auth_client(brand).get("/api/v1/auth/me/").json()["avatar_url"] == logo


def test_a_user_without_a_picture_has_a_null_avatar(creator, auth_client):
    assert auth_client(creator).get("/api/v1/auth/me/").json()["avatar_url"] is None


def test_the_photo_shows_in_the_brand_facing_directory_and_detail(creator, brand, auth_client):
    photo = put(auth_client, creator, PHOTO).json()["photo_url"]

    listing = auth_client(brand).get("/api/v1/creators/").json()["results"]
    detail = auth_client(brand).get(f"/api/v1/creators/{creator.pk}/").json()

    assert [row["photo_url"] for row in listing] == [photo]
    assert detail["photo_url"] == photo


def test_the_logo_shows_on_campaign_cards(brand, auth_client):
    logo = put(auth_client, brand, LOGO).json()["logo_url"]
    campaign = CampaignFactory(brand=brand, status=Campaign.Status.PUBLISHED)
    creator = UserFactory(role=Role.CREATOR)

    card = auth_client(creator).get("/api/v1/campaigns/").json()["results"][0]

    assert card["id"] == campaign.id
    assert card["brand"]["logo_url"] == logo
