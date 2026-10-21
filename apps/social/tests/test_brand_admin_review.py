"""A brand's Instagram, TikTok or Facebook link counts only after an admin approves it."""
import pytest

from apps.accounts.models import Role
from apps.accounts.tests.factories import UserFactory
from apps.adminpanel.models import AdminActionLog
from apps.campaigns.models import Campaign
from apps.campaigns.tests.factories import CampaignFactory
from apps.social.models import BrandSocialAccount

QUEUE = "/api/v1/admin/brand-platforms/"
OWN = "/api/v1/brands/me/social/{}/"


def approve_url(pk):
    return f"/api/v1/admin/brand-platforms/{pk}/approve/"


def reject_url(pk):
    return f"/api/v1/admin/brand-platforms/{pk}/reject/"


@pytest.fixture
def brand(db):
    return UserFactory(role=Role.BRAND, platform_connected=False)


@pytest.fixture
def admin(db):
    return UserFactory(role=Role.ADMIN)


def add_link(auth_client, brand, platform="instagram"):
    response = auth_client(brand).put(OWN.format(platform), {"handle_url": f"https://{platform}.com/acme"}, format="json")
    assert response.status_code == 200
    return BrandSocialAccount.objects.get(brand=brand, platform=platform)


def can_publish(auth_client, brand):
    draft = CampaignFactory(brand=brand)
    return auth_client(brand).post(f"/api/v1/brand/campaigns/{draft.pk}/publish/").status_code == 200


def test_a_brand_cannot_publish_until_an_admin_approves_the_link(brand, admin, auth_client):
    account = add_link(auth_client, brand)
    assert can_publish(auth_client, brand) is False

    assert auth_client(admin).post(approve_url(account.pk), {}, format="json").status_code == 200

    assert can_publish(auth_client, brand) is True
    account.refresh_from_db()
    assert account.is_verified is True and account.review_status == "approved"


def test_saving_a_new_link_sends_an_approved_one_back_to_review(brand, admin, auth_client):
    account = add_link(auth_client, brand)
    auth_client(admin).post(approve_url(account.pk), {}, format="json")

    auth_client(brand).put(OWN.format("instagram"), {"handle_url": "https://instagram.com/other"}, format="json")

    account.refresh_from_db()
    assert account.review_status == "pending" and account.is_verified is False
    assert can_publish(auth_client, brand) is False


def test_the_queue_shows_pending_links_with_the_brand_and_never_youtube(brand, admin, auth_client):
    add_link(auth_client, brand, "tiktok")
    BrandSocialAccount.objects.create(
        brand=brand, platform="youtube", handle_url="https://youtube.com/@acme", is_verified=True
    )

    rows = auth_client(admin).get(QUEUE).json()["results"]

    assert [r["platform"] for r in rows] == ["tiktok"]
    assert rows[0]["brand"]["username"] == brand.username
    assert rows[0]["handle_url"] == "https://tiktok.com/acme" and rows[0]["review_status"] == "pending"


def test_rejecting_needs_a_reason_and_the_brand_sees_it(brand, admin, auth_client):
    account = add_link(auth_client, brand)

    assert auth_client(admin).post(reject_url(account.pk), {}, format="json").status_code == 400
    response = auth_client(admin).post(reject_url(account.pk), {"reason": "This is not your official page."}, format="json")

    assert response.status_code == 200
    mine = auth_client(brand).get("/api/v1/brands/me/social/").json()[0]
    assert mine["review_status"] == "rejected" and mine["review_note"] == "This is not your official page."
    assert mine["is_verified"] is False
    assert auth_client(brand).get("/api/v1/auth/me/").json()["platform_status"] == "none"


def test_approving_and_rejecting_are_written_to_the_audit_trail(brand, admin, auth_client):
    account = add_link(auth_client, brand)
    auth_client(admin).post(approve_url(account.pk), {}, format="json")
    auth_client(admin).post(reject_url(account.pk), {"reason": "Changed my mind."}, format="json")

    actions = list(AdminActionLog.objects.order_by("id").values_list("action", "target_type", "target_id"))

    assert actions == [
        ("brand_platform.approve", "brand_platform", account.pk),
        ("brand_platform.reject", "brand_platform", account.pk),
    ]
    assert can_publish(auth_client, brand) is False  # the approval was taken back


def test_a_youtube_account_cannot_be_reviewed(brand, admin, auth_client):
    youtube = BrandSocialAccount.objects.create(
        brand=brand, platform="youtube", handle_url="https://youtube.com/@acme", is_verified=True
    )

    assert auth_client(admin).post(approve_url(youtube.pk), {}, format="json").status_code == 404
    assert auth_client(admin).post(reject_url(youtube.pk), {"reason": "x"}, format="json").status_code == 404
    youtube.refresh_from_db()
    assert youtube.is_verified is True


def test_only_admins_can_review(brand, auth_client):
    account = add_link(auth_client, brand)
    creator = UserFactory(role=Role.CREATOR)

    for user in (brand, creator):
        client = auth_client(user)
        assert client.get(QUEUE).status_code == 403
        assert client.post(approve_url(account.pk), {}, format="json").status_code == 403
        assert client.post(reject_url(account.pk), {"reason": "x"}, format="json").status_code == 403
    account.refresh_from_db()
    assert account.is_verified is False
    assert Campaign.objects.filter(brand=brand).count() == 0
