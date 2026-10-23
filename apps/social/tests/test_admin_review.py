"""Instagram, TikTok and Facebook numbers are typed by the creator and shown publicly only after an admin approves."""
import pytest

from apps.accounts.models import Role
from apps.accounts.tests.factories import UserFactory
from apps.accounts.verification import creator_is_verified
from apps.adminpanel.models import AdminActionLog
from apps.profiles.models import CreatorProfile
from apps.social.models import PlatformStats

QUEUE = "/api/v1/admin/platform-stats/"
OWN = "/api/v1/creators/me/stats/{}/"


def approve_url(pk):
    return f"/api/v1/admin/platform-stats/{pk}/approve/"


def reject_url(pk):
    return f"/api/v1/admin/platform-stats/{pk}/reject/"


def detail_url(creator):
    return f"/api/v1/creators/{creator.id}/"


@pytest.fixture
def creator(db):
    return UserFactory(role=Role.CREATOR)


@pytest.fixture
def brand(db):
    return UserFactory(role=Role.BRAND)


@pytest.fixture
def admin(db):
    return UserFactory(role=Role.ADMIN)


def type_stats(auth_client, creator, platform="instagram", **overrides):
    data = {"followers": 12000, "engagement_rate": "4.5", "handle_url": f"https://{platform}.com/amina"}
    data.update(overrides)
    return auth_client(creator).put(OWN.format(platform), data, format="json")


def public_platforms(auth_client, brand, creator):
    return [s["platform"] for s in auth_client(brand).get(detail_url(creator)).json()["stats"]]


# ---- what the creator types ----------------------------------------------------------------------------------


def test_typed_numbers_wait_for_an_admin(creator, auth_client):
    body = type_stats(auth_client, creator).json()

    assert body["is_verified"] is False
    assert body["review_status"] == "pending"
    assert body["review_note"] == ""


@pytest.mark.parametrize("platform", ["instagram", "tiktok", "facebook"])
def test_a_profile_link_on_that_platform_is_required(creator, auth_client, platform):
    for bad in (None, "", "https://example.com/amina", f"https://{platform}.com/", "not a link"):
        response = type_stats(auth_client, creator, platform, handle_url=bad)

        assert response.status_code == 400, bad
        assert "handle_url" in response.json()["error"]["details"]
    assert not PlatformStats.objects.filter(creator=creator, platform=platform).exists()


def test_editing_approved_numbers_sends_them_back_to_review(creator, admin, auth_client):
    type_stats(auth_client, creator)
    stats_id = PlatformStats.objects.get(creator=creator).id
    auth_client(admin).post(approve_url(stats_id), {}, format="json")

    body = type_stats(auth_client, creator, followers=90000).json()

    assert body["review_status"] == "pending" and body["is_verified"] is False


# ---- what brands and the creator see ------------------------------------------------------------------------


def test_numbers_are_hidden_from_brands_until_approved(creator, brand, admin, auth_client):
    type_stats(auth_client, creator)
    stats_id = PlatformStats.objects.get(creator=creator).id
    assert public_platforms(auth_client, brand, creator) == []

    auth_client(admin).post(approve_url(stats_id), {}, format="json")

    assert public_platforms(auth_client, brand, creator) == ["instagram"]


def test_the_creator_still_sees_their_own_pending_numbers(creator, auth_client):
    type_stats(auth_client, creator)

    mine = auth_client(creator).get("/api/v1/creators/me/").json()["stats"]

    assert [(s["platform"], s["review_status"]) for s in mine] == [("instagram", "pending")]


def test_a_pending_primary_platform_shows_no_followers_in_the_directory(creator, brand, admin, auth_client):
    type_stats(auth_client, creator)
    CreatorProfile.objects.filter(user=creator).update(primary_platform="instagram")

    def card():
        results = auth_client(brand).get("/api/v1/creators/").json()["results"]
        return next(c for c in results if c["id"] == creator.id)

    assert card()["followers"] is None and card()["is_verified"] is False

    auth_client(admin).post(approve_url(PlatformStats.objects.get(creator=creator).id), {}, format="json")

    assert card()["followers"] == 12000  # the approved numbers show
    assert card()["is_verified"] is False  # but they never make the creator Verified


def test_approved_instagram_does_not_make_a_creator_verified(creator, admin, auth_client):
    type_stats(auth_client, creator)
    auth_client(admin).post(approve_url(PlatformStats.objects.get(creator=creator).id), {}, format="json")

    assert creator_is_verified(creator) is False  # a creator is Verified by a connected YouTube channel only


# ---- the admin ----------------------------------------------------------------------------------------------


def test_the_queue_lists_pending_numbers_with_the_creator_and_link(creator, admin, auth_client):
    type_stats(auth_client, creator, "tiktok")
    type_stats(auth_client, UserFactory(role=Role.CREATOR), "facebook")
    PlatformStats.objects.create(creator=creator, platform="youtube", followers=5, engagement_rate="1.00")

    rows = auth_client(admin).get(QUEUE).json()["results"]

    assert [r["platform"] for r in rows] == ["tiktok", "facebook"]  # oldest first, no YouTube
    assert rows[0]["creator"]["username"] == creator.username
    assert rows[0]["handle_url"] == "https://tiktok.com/amina"
    assert rows[0]["followers"] == 12000 and rows[0]["review_status"] == "pending"


def test_the_queue_can_show_approved_and_rejected(creator, admin, auth_client):
    type_stats(auth_client, creator, "tiktok")
    stats_id = PlatformStats.objects.get(creator=creator).id
    auth_client(admin).post(reject_url(stats_id), {"reason": "Link is not your page."}, format="json")

    assert auth_client(admin).get(QUEUE).json()["results"] == []
    rejected = auth_client(admin).get(QUEUE, {"status": "rejected"}).json()["results"]
    assert [r["id"] for r in rejected] == [stats_id]


def test_approving_marks_verified_and_writes_the_audit_trail(creator, admin, auth_client):
    type_stats(auth_client, creator, "facebook")
    stats_id = PlatformStats.objects.get(creator=creator).id

    response = auth_client(admin).post(approve_url(stats_id), {}, format="json")

    assert response.status_code == 200 and response.json()["review_status"] == "approved"
    stats = PlatformStats.objects.get(pk=stats_id)
    assert stats.is_verified is True
    entry = AdminActionLog.objects.get(action="stats.approve")
    assert entry.admin == admin and entry.target_id == stats_id and entry.reason


def test_rejecting_needs_a_reason_and_the_creator_sees_it(creator, admin, auth_client):
    type_stats(auth_client, creator)
    stats_id = PlatformStats.objects.get(creator=creator).id

    assert auth_client(admin).post(reject_url(stats_id), {}, format="json").status_code == 400
    response = auth_client(admin).post(reject_url(stats_id), {"reason": "Followers do not match."}, format="json")

    assert response.status_code == 200
    mine = auth_client(creator).get("/api/v1/creators/me/").json()["stats"][0]
    assert mine["review_status"] == "rejected" and mine["review_note"] == "Followers do not match."
    assert mine["is_verified"] is False
    assert AdminActionLog.objects.filter(action="stats.reject").count() == 1


def test_rejecting_takes_back_an_approval(creator, brand, admin, auth_client):
    type_stats(auth_client, creator)
    stats_id = PlatformStats.objects.get(creator=creator).id
    auth_client(admin).post(approve_url(stats_id), {}, format="json")

    auth_client(admin).post(reject_url(stats_id), {"reason": "Changed my mind."}, format="json")

    assert public_platforms(auth_client, brand, creator) == []


def test_youtube_numbers_cannot_be_reviewed(creator, admin, auth_client):
    stats = PlatformStats.objects.create(
        creator=creator, platform="youtube", followers=5000, engagement_rate="1.00", is_verified=True
    )

    assert auth_client(admin).post(approve_url(stats.id), {}, format="json").status_code == 404
    assert auth_client(admin).post(reject_url(stats.id), {"reason": "x"}, format="json").status_code == 404
    assert PlatformStats.objects.get(pk=stats.pk).is_verified is True


def test_only_admins_can_review(creator, brand, auth_client):
    type_stats(auth_client, creator)
    stats_id = PlatformStats.objects.get(creator=creator).id

    for user in (creator, brand):
        client = auth_client(user)
        assert client.get(QUEUE).status_code == 403
        assert client.post(approve_url(stats_id), {}, format="json").status_code == 403
        assert client.post(reject_url(stats_id), {"reason": "x"}, format="json").status_code == 403
    assert PlatformStats.objects.get(pk=stats_id).is_verified is False
