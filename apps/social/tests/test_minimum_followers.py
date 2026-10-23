"""A creator is Verified, and can apply, only with at least MIN_CREATOR_FOLLOWERS YouTube subscribers (1,000 by default).

The count is checked every time the stats are read from Google (when connecting, on the daily sync and on Refresh), so a
creator who grows past the minimum becomes Verified and one who drops below it stops being Verified. A connected channel
below the minimum stays connected and is told exactly why.
"""
import pytest

from apps.accounts.models import Role
from apps.accounts.tests.factories import UserFactory
from apps.campaigns.models import Campaign
from apps.campaigns.tests.factories import CampaignFactory
from apps.social import services
from apps.social.models import PlatformStats, YouTubeConnection
from apps.social.tests.fakes import make_connection, snapshot

APPLY_BODY = {"cover_message": "Hello"}


@pytest.fixture
def creator(db):
    return UserFactory(role=Role.CREATOR, email_verified=True)


def sync_with(fake_youtube, creator, subscribers):
    """Read the channel from (fake) Google with this many subscribers and store the result."""
    fake_youtube.default_snapshot = snapshot(subscribers=subscribers)
    connection = YouTubeConnection.objects.get(creator=creator)
    services.sync_connection(connection)
    return PlatformStats.objects.get(creator=creator, platform="youtube")


def apply(auth_client, creator):
    campaign = CampaignFactory(status=Campaign.Status.PUBLISHED)
    return auth_client(creator).post(f"/api/v1/campaigns/{campaign.pk}/proposals/", APPLY_BODY, format="json")


def error(response):
    return response.json()["error"]


def test_the_default_minimum_is_one_thousand(settings):
    assert settings.MIN_CREATOR_FOLLOWERS == 1000


# ---- the stats are re-judged every time they are read from Google ------------------------------------------


@pytest.mark.parametrize("subscribers, verified", [(0, False), (999, False), (1000, True), (1001, True), (250_000, True)])
def test_the_first_sync_verifies_only_channels_at_or_above_the_minimum(creator, fake_youtube, subscribers, verified):
    make_connection(creator, with_stats=False)

    stats = sync_with(fake_youtube, creator, subscribers)

    assert stats.followers == subscribers and stats.is_verified is verified
    assert YouTubeConnection.objects.get(creator=creator).status == YouTubeConnection.Status.CONNECTED


def test_a_channel_that_drops_below_the_minimum_loses_verified_but_stays_connected(creator, fake_youtube):
    make_connection(creator, followers=5000)  # verified, 5,000 subscribers

    stats = sync_with(fake_youtube, creator, 800)

    assert stats.followers == 800 and stats.is_verified is False
    assert YouTubeConnection.objects.get(creator=creator).status == YouTubeConnection.Status.CONNECTED


def test_a_channel_that_grows_past_the_minimum_becomes_verified_at_the_next_sync(creator, fake_youtube):
    make_connection(creator, with_stats=False)
    assert sync_with(fake_youtube, creator, 900).is_verified is False

    assert sync_with(fake_youtube, creator, 1200).is_verified is True


def test_raising_the_minimum_applies_at_the_next_sync(creator, fake_youtube, settings):
    make_connection(creator, with_stats=False)
    assert sync_with(fake_youtube, creator, 1500).is_verified is True

    settings.MIN_CREATOR_FOLLOWERS = 2000

    assert sync_with(fake_youtube, creator, 1500).is_verified is False


# ---- applying -----------------------------------------------------------------------------------------------


def test_a_verified_creator_above_the_minimum_can_apply(creator, auth_client):
    make_connection(creator, followers=1000)

    assert apply(auth_client, creator).status_code == 201


def test_a_connected_channel_below_the_minimum_cannot_apply_and_is_told_why(creator, auth_client, fake_youtube):
    make_connection(creator, with_stats=False)
    PlatformStats.objects.create(
        creator=creator, platform="youtube", followers=640, engagement_rate="2.00", is_verified=False
    )

    response = apply(auth_client, creator)

    assert response.status_code == 403
    assert error(response)["code"] == "creator_followers_too_low"
    assert "640" in error(response)["message"] and "1,000" in error(response)["message"]


def test_without_a_connected_channel_the_error_is_still_connect_youtube(creator, auth_client):
    response = apply(auth_client, creator)

    assert response.status_code == 403 and error(response)["code"] == "creator_youtube_required"


def test_typed_stats_never_count_whatever_the_number(creator, auth_client):
    PlatformStats.objects.create(
        creator=creator, platform="youtube", followers=900_000, engagement_rate="2.00", is_verified=False
    )

    response = apply(auth_client, creator)

    assert response.status_code == 403 and error(response)["code"] == "creator_youtube_required"


def test_a_verified_flag_does_not_beat_a_raised_minimum_before_the_next_sync(creator, auth_client, settings):
    make_connection(creator, followers=1500)  # verified when the minimum was 1,000
    settings.MIN_CREATOR_FOLLOWERS = 2000

    response = apply(auth_client, creator)

    assert response.status_code == 403 and error(response)["code"] == "creator_followers_too_low"


# ---- what the website is told ---------------------------------------------------------------------------------


def test_the_youtube_status_says_how_many_subscribers_and_what_is_needed(creator, auth_client):
    make_connection(creator, with_stats=False)
    PlatformStats.objects.create(
        creator=creator, platform="youtube", followers=640, engagement_rate="2.00", is_verified=False
    )

    body = auth_client(creator).get("/api/v1/social/youtube/").json()

    assert body["followers"] == 640
    assert body["minimum_followers"] == 1000
    assert body["below_minimum"] is True


def test_the_status_is_not_below_minimum_for_a_big_enough_or_unconnected_creator(creator, auth_client):
    unconnected = auth_client(creator).get("/api/v1/social/youtube/").json()
    assert (unconnected["followers"], unconnected["below_minimum"]) == (None, False)

    make_connection(creator, followers=5000)

    connected = auth_client(creator).get("/api/v1/social/youtube/").json()
    assert (connected["followers"], connected["below_minimum"], connected["minimum_followers"]) == (5000, False, 1000)


def test_the_creator_dashboard_carries_the_same_fields(creator, auth_client):
    make_connection(creator, with_stats=False)
    PlatformStats.objects.create(
        creator=creator, platform="youtube", followers=640, engagement_rate="2.00", is_verified=False
    )

    youtube = auth_client(creator).get("/api/v1/creators/me/dashboard/").json()["youtube"]

    assert (youtube["followers"], youtube["minimum_followers"], youtube["below_minimum"]) == (640, 1000, True)


# ---- the back door is closed ----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "method, path",
    [
        ("post", "/api/v1/social/youtube/direct-connect/"),
        ("post", "/api/v1/social/direct-connect/instagram/"),
        ("post", "/api/v1/social/direct-connect/youtube/"),
        ("get", "/api/v1/social/challenge/instagram/"),
    ],
)
def test_the_endpoints_that_verified_stats_without_proof_no_longer_exist(creator, auth_client, method, path):
    client = auth_client(creator)

    if method == "post":
        response = client.post(path, {"handle": "anything", "followers": 999999}, format="json")
    else:
        response = client.get(path)

    assert response.status_code == 404
    assert not PlatformStats.objects.filter(creator=creator).exists()


def test_no_stats_can_be_marked_verified_by_typing_them(creator, auth_client):
    response = auth_client(creator).put(
        "/api/v1/creators/me/stats/youtube/",
        {"followers": 900000, "engagement_rate": "5.00", "is_verified": True},
        format="json",
    )

    assert response.status_code == 400
    assert not PlatformStats.objects.filter(creator=creator, platform="youtube").exists()
    assert apply(auth_client, creator).status_code == 403
