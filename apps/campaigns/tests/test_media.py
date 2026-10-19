from pathlib import Path

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.accounts.models import Role
from apps.accounts.tests.factories import UserFactory
from apps.campaigns.models import Campaign, CampaignMedia
from apps.campaigns.tests.factories import CampaignFactory

JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 64
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
WEBP = b"RIFF\x24\x00\x00\x00WEBPVP8 " + b"\x00" * 64
MP4 = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 64
WEBM = b"\x1a\x45\xdf\xa3" + b"\x00" * 64


def media_url(campaign_id):
    return f"/api/v1/brand/campaigns/{campaign_id}/media/"


def item_url(campaign_id, media_id):
    return f"/api/v1/brand/campaigns/{campaign_id}/media/{media_id}/"


def upload(auth_client, user, campaign, content=JPEG, name="photo.jpg", content_type="image/jpeg"):
    file = SimpleUploadedFile(name, content, content_type=content_type)
    return auth_client(user).post(media_url(campaign.pk), {"file": file}, format="multipart")


def error_code(response):
    return response.json()["error"]["code"]


@pytest.fixture(autouse=True)
def media_root(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    return tmp_path


@pytest.fixture
def brand(db):
    return UserFactory(role=Role.BRAND)


@pytest.fixture
def draft(brand):
    return CampaignFactory(brand=brand, status=Campaign.Status.DRAFT)


# ---- what can be uploaded ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "content, kind, extension",
    [
        (JPEG, "photo", ".jpg"),
        (PNG, "photo", ".png"),
        (WEBP, "photo", ".webp"),
        (MP4, "video", ".mp4"),
        (WEBM, "video", ".webm"),
    ],
)
def test_supported_files_are_stored_with_a_generated_name(brand, draft, auth_client, media_root, content, kind, extension):
    response = upload(auth_client, brand, draft, content, name="holiday photo.exe", content_type="application/x-msdownload")

    assert response.status_code == 201
    data = response.json()
    assert data["kind"] == kind
    assert data["url"].startswith("http://testserver/media/campaigns/") and data["url"].endswith(extension)
    stored = CampaignMedia.objects.get(pk=data["id"])
    assert Path(media_root, stored.file.name).exists()
    assert "holiday" not in stored.file.name  # the uploader's filename is never used


def test_a_text_file_renamed_to_jpg_is_refused(brand, draft, auth_client):
    response = upload(auth_client, brand, draft, b"not an image at all", name="evil.jpg", content_type="image/jpeg")

    assert response.status_code == 400
    assert error_code(response) == "unsupported_media"
    assert not CampaignMedia.objects.exists()


def test_no_file_is_a_validation_error(brand, draft, auth_client):
    response = auth_client(brand).post(media_url(draft.pk), {}, format="multipart")

    assert response.status_code == 400
    assert "file" in response.json()["error"]["details"]


def test_a_photo_over_the_size_limit_is_refused(brand, draft, auth_client, settings):
    settings.MEDIA_MAX_PHOTO_BYTES = 100

    response = upload(auth_client, brand, draft, JPEG + b"\x00" * 200)

    assert response.status_code == 413
    assert error_code(response) == "media_too_large"
    assert not CampaignMedia.objects.exists()


def test_a_video_over_the_size_limit_is_refused(brand, draft, auth_client, settings):
    settings.MEDIA_MAX_VIDEO_BYTES = 100

    response = upload(auth_client, brand, draft, MP4 + b"\x00" * 200, "clip.mp4", "video/mp4")

    assert response.status_code == 413


# ---- two photos or one video ---------------------------------------------------------------------


def test_up_to_two_photos_then_a_conflict(brand, draft, auth_client):
    assert upload(auth_client, brand, draft).status_code == 201
    assert upload(auth_client, brand, draft, PNG, "b.png", "image/png").status_code == 201

    third = upload(auth_client, brand, draft)

    assert third.status_code == 409
    assert error_code(third) == "media_limit_reached"
    assert draft.media.count() == 2


def test_one_video_and_no_second_one(brand, draft, auth_client):
    assert upload(auth_client, brand, draft, MP4, "a.mp4", "video/mp4").status_code == 201

    second = upload(auth_client, brand, draft, WEBM, "b.webm", "video/webm")

    assert second.status_code == 409
    assert error_code(second) == "media_limit_reached"


def test_a_video_cannot_join_photos_and_photos_cannot_join_a_video(brand, auth_client):
    with_photo = CampaignFactory(brand=brand)
    with_video = CampaignFactory(brand=brand)
    assert upload(auth_client, brand, with_photo).status_code == 201
    assert upload(auth_client, brand, with_video, MP4, "a.mp4", "video/mp4").status_code == 201

    assert upload(auth_client, brand, with_photo, MP4, "a.mp4", "video/mp4").status_code == 409
    assert upload(auth_client, brand, with_video).status_code == 409


# ---- who can do it, and when ---------------------------------------------------------------------


def test_another_brands_campaign_is_a_404(draft, auth_client):
    other = UserFactory(role=Role.BRAND)

    assert upload(auth_client, other, draft).status_code == 404
    assert not CampaignMedia.objects.exists()


def test_creators_cannot_upload(draft, auth_client):
    creator = UserFactory(role=Role.CREATOR)

    assert upload(auth_client, creator, draft).status_code == 403


def test_anonymous_cannot_upload(draft):
    from rest_framework.test import APIClient

    response = APIClient().post(media_url(draft.pk), {"file": SimpleUploadedFile("a.jpg", JPEG)}, format="multipart")

    assert response.status_code == 401


def test_a_published_campaign_is_frozen(brand, auth_client):
    published = CampaignFactory(brand=brand, status=Campaign.Status.PUBLISHED)

    response = upload(auth_client, brand, published)

    assert response.status_code == 409
    assert error_code(response) == "campaign_not_editable"


# ---- removing ------------------------------------------------------------------------------------------


def test_removing_deletes_the_row_and_the_file(brand, draft, auth_client, media_root, run_on_commit):
    created = upload(auth_client, brand, draft).json()
    path = Path(media_root, CampaignMedia.objects.get(pk=created["id"]).file.name)
    assert path.exists()

    with run_on_commit():
        response = auth_client(brand).delete(item_url(draft.pk, created["id"]))

    assert response.status_code == 204
    assert not CampaignMedia.objects.exists()
    assert not path.exists()


def test_removing_frees_the_slot(brand, draft, auth_client):
    first = upload(auth_client, brand, draft).json()
    upload(auth_client, brand, draft, PNG, "b.png", "image/png")
    auth_client(brand).delete(item_url(draft.pk, first["id"]))

    assert upload(auth_client, brand, draft).status_code == 201


def test_removing_something_that_is_not_there_is_a_404(brand, draft, auth_client):
    assert auth_client(brand).delete(item_url(draft.pk, 999)).status_code == 404


def test_another_brand_cannot_remove_media(brand, draft, auth_client):
    created = upload(auth_client, brand, draft).json()
    other = UserFactory(role=Role.BRAND)

    assert auth_client(other).delete(item_url(draft.pk, created["id"])).status_code == 404
    assert draft.media.count() == 1


def test_published_media_cannot_be_removed(brand, draft, auth_client):
    created = upload(auth_client, brand, draft).json()
    Campaign.objects.filter(pk=draft.pk).update(status=Campaign.Status.PUBLISHED)

    response = auth_client(brand).delete(item_url(draft.pk, created["id"]))

    assert response.status_code == 409
    assert draft.media.count() == 1


def test_deleting_the_campaign_removes_its_files(brand, draft, auth_client, media_root, run_on_commit):
    created = upload(auth_client, brand, draft).json()
    path = Path(media_root, CampaignMedia.objects.get(pk=created["id"]).file.name)

    with run_on_commit():
        response = auth_client(brand).delete(f"/api/v1/brand/campaigns/{draft.pk}/")

    assert response.status_code == 204
    assert not path.exists()


# ---- where the media shows up --------------------------------------------------------------------------


def test_the_brand_sees_media_on_its_campaign(brand, draft, auth_client):
    upload(auth_client, brand, draft)

    body = auth_client(brand).get(f"/api/v1/brand/campaigns/{draft.pk}/").json()

    assert [m["kind"] for m in body["media"]] == ["photo"]
    assert body["media"][0]["url"].startswith("http://testserver/media/")


def test_creators_see_media_on_a_published_campaign(brand, auth_client):
    campaign = CampaignFactory(brand=brand, status=Campaign.Status.DRAFT)
    upload(auth_client, brand, campaign, MP4, "a.mp4", "video/mp4")
    Campaign.objects.filter(pk=campaign.pk).update(status=Campaign.Status.PUBLISHED)
    creator = UserFactory(role=Role.CREATOR)

    body = auth_client(creator).get(f"/api/v1/campaigns/{campaign.pk}/").json()

    assert [m["kind"] for m in body["media"]] == ["video"]
