from decimal import Decimal

import pytest
from celery.schedules import crontab
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Role
from apps.accounts.tests.factories import UserFactory
from apps.campaigns.models import Campaign
from apps.campaigns.tests.factories import CampaignFactory
from apps.proposals.deliverable_stats import NOT_AVAILABLE, content_performance, refresh_deliverable_stats
from apps.proposals.models import Deliverable, Proposal
from apps.proposals.tasks import sync_deliverable_stats
from apps.proposals.tests.factories import ProposalFactory
from apps.social.tests.fakes import FakeYouTubeClient
from apps.social.youtube_client import QuotaExceeded, TransientApiError, VideoStats

S = Proposal.Status


def vid(n: int) -> str:
    return f"vid{n:08d}"  # always 11 characters


def watch(n: int) -> str:
    return f"https://www.youtube.com/watch?v={vid(n)}"


def content_url(pk):
    return f"/api/v1/brand/campaigns/{pk}/analytics/content/"


@pytest.fixture
def fake(monkeypatch):
    client = FakeYouTubeClient()
    monkeypatch.setattr("apps.social.services.get_youtube_client", lambda: client)
    return client


@pytest.fixture
def accepted(db):
    campaign = CampaignFactory(status=Campaign.Status.PUBLISHED, creators_needed=5)
    return ProposalFactory(campaign=campaign, status=S.ACCEPTED)


def deliver(proposal, url, platform="youtube", **kwargs):
    return Deliverable.objects.create(proposal=proposal, post_url=url, platform=platform, **kwargs)


def reload(deliverable):
    deliverable.refresh_from_db()
    return deliverable


# ---- the daily sync -------------------------------------------------------------------------------------


def test_sync_stores_views_likes_and_comments(accepted, fake):
    first = deliver(accepted, watch(1))
    fake.video_results[vid(1)] = VideoStats(views=2000, likes=150, comments=30)

    updated = refresh_deliverable_stats()

    first = reload(first)
    assert updated == 1
    assert (first.views_count, first.likes_count, first.comments_count) == (2000, 150, 30)
    assert first.stats_synced_at is not None
    assert fake.video_calls == [([vid(1)], "test-youtube-api-key")]


def test_hidden_counts_are_stored_as_unknown(accepted, fake):
    item = deliver(accepted, watch(1))
    fake.video_results[vid(1)] = VideoStats(views=500, likes=None, comments=None)

    refresh_deliverable_stats()

    item = reload(item)
    assert (item.views_count, item.likes_count, item.comments_count) == (500, None, None)


def test_without_an_api_key_nothing_is_called_or_changed(accepted, fake, settings):
    settings.YOUTUBE_API_KEY = ""
    item = deliver(accepted, watch(1))

    assert refresh_deliverable_stats() == 0
    assert fake.video_calls == []
    assert reload(item).stats_synced_at is None


def test_only_youtube_deliverables_of_accepted_proposals_with_a_video_id_are_looked_up(accepted, fake):
    wanted = deliver(accepted, watch(1))
    deliver(accepted, "https://www.instagram.com/p/abc/", platform="instagram")
    deliver(accepted, "https://www.youtube.com/@channel")  # not a video
    for status in (S.WITHDRAWN, S.REJECTED, S.PENDING):
        deliver(ProposalFactory(campaign=accepted.campaign, status=status), watch(9))
    fake.video_results[vid(1)] = VideoStats(1, 1, 1)

    refresh_deliverable_stats()

    assert fake.video_calls == [([vid(1)], "test-youtube-api-key")]
    assert reload(wanted).views_count == 1


def test_lookups_are_batched_in_fifties(accepted, fake):
    for n in range(120):
        deliver(accepted, watch(n))
        fake.video_results[vid(n)] = VideoStats(n, 0, 0)

    updated = refresh_deliverable_stats()

    assert updated == 120
    assert [len(ids) for ids, _ in fake.video_calls] == [50, 50, 20]


def test_a_video_delivered_twice_is_looked_up_once_and_both_rows_are_updated(accepted, fake):
    other = ProposalFactory(campaign=accepted.campaign, status=S.ACCEPTED)
    one, two = deliver(accepted, watch(1)), deliver(other, f"https://youtu.be/{vid(1)}")
    fake.video_results[vid(1)] = VideoStats(10, 2, 1)

    refresh_deliverable_stats()

    assert len(fake.video_calls) == 1
    assert reload(one).views_count == reload(two).views_count == 10


@pytest.mark.parametrize("error", [TransientApiError("503"), QuotaExceeded("quota")])
def test_a_failed_batch_keeps_the_previous_numbers_and_the_next_batch_still_runs(accepted, fake, error):
    old = deliver(accepted, watch(1), views_count=111, likes_count=11, comments_count=1, stats_synced_at=timezone.now())
    for n in range(2, 62):  # 60 more videos -> a second batch
        deliver(accepted, watch(n))
        fake.video_results[vid(n)] = VideoStats(n, 0, 0)
    fake.video_batch_errors = [error, None]  # the first batch fails, the second succeeds

    refresh_deliverable_stats()

    assert len(fake.video_calls) == 2
    assert reload(old).views_count == 111  # not erased by the failure
    synced = Deliverable.objects.filter(stats_synced_at__isnull=False).count()
    assert synced == 1 + 11  # the old one plus the 11 videos in the second batch (61 videos: 50 + 11)


def test_deleted_or_private_videos_keep_their_last_numbers(accepted, fake):
    item = deliver(accepted, watch(1), views_count=42, likes_count=4, comments_count=2, stats_synced_at=timezone.now())

    refresh_deliverable_stats()  # Google returns nothing for this video

    assert reload(item).views_count == 42


def test_editing_the_link_discards_the_old_videos_numbers(accepted, auth_client):
    item = deliver(accepted, watch(1), views_count=42, likes_count=4, comments_count=2, stats_synced_at=timezone.now())

    response = auth_client(accepted.creator).patch(
        f"/api/v1/creators/me/proposals/{accepted.pk}/deliverables/{item.pk}/",
        {"post_url": watch(2)},
        format="json",
    )

    assert response.status_code == 200
    item = reload(item)
    assert (item.views_count, item.likes_count, item.comments_count, item.stats_synced_at) == (None, None, None, None)


def test_editing_only_the_note_keeps_the_numbers(accepted, auth_client):
    item = deliver(accepted, watch(1), views_count=42, stats_synced_at=timezone.now())

    auth_client(accepted.creator).patch(
        f"/api/v1/creators/me/proposals/{accepted.pk}/deliverables/{item.pk}/", {"note": "edit"}, format="json"
    )

    assert reload(item).views_count == 42


def test_the_sync_runs_daily_and_is_registered_with_celery(settings):
    from config.celery import app

    entry = settings.CELERY_BEAT_SCHEDULE["sync-deliverable-stats"]
    app.loader.import_default_modules()

    assert entry["task"] == "apps.proposals.tasks.sync_deliverable_stats"
    assert entry["schedule"] == crontab(hour=4, minute=0)
    assert "apps.proposals.tasks.sync_deliverable_stats" in app.tasks


def test_the_task_returns_how_many_were_updated(accepted, fake):
    deliver(accepted, watch(1))
    fake.video_results[vid(1)] = VideoStats(1, 1, 1)

    assert sync_deliverable_stats() == 1


# ---- what the brand sees ---------------------------------------------------------------------------------


def test_the_report_shows_numbers_and_an_engagement_rate_per_deliverable(accepted, auth_client):
    item = deliver(
        accepted, watch(1), views_count=2000, likes_count=150, comments_count=50, stats_synced_at=timezone.now()
    )

    rows = auth_client(accepted.campaign.brand).get(content_url(accepted.campaign_id)).json()

    assert len(rows) == 1
    row = rows[0]
    assert row["deliverable_id"] == item.id and row["proposal_id"] == accepted.id
    assert row["creator"] == {"id": accepted.creator_id, "name": accepted.creator.full_name}
    assert (row["platform"], row["post_url"]) == ("youtube", watch(1))
    assert (row["views"], row["likes"], row["comments"]) == (2000, 150, 50)
    assert row["engagement_rate"] == "10.00"
    assert row["synced_at"] is not None


def test_engagement_rate_is_rounded_to_two_places(accepted, auth_client):
    deliver(accepted, watch(1), views_count=3000, likes_count=100, comments_count=0, stats_synced_at=timezone.now())

    row = auth_client(accepted.campaign.brand).get(content_url(accepted.campaign_id)).json()[0]

    assert row["engagement_rate"] == "3.33"


def test_not_available_where_the_api_provides_no_data(accepted, auth_client):
    deliver(accepted, "https://www.instagram.com/p/abc/", platform="instagram")  # not YouTube
    deliver(accepted, watch(2))  # not synced yet
    deliver(accepted, watch(3), views_count=500, stats_synced_at=timezone.now())  # likes/comments hidden
    deliver(accepted, watch(4), views_count=0, likes_count=0, comments_count=0, stats_synced_at=timezone.now())

    rows = {r["post_url"]: r for r in auth_client(accepted.campaign.brand).get(content_url(accepted.campaign_id)).json()}

    na = NOT_AVAILABLE
    assert (rows["https://www.instagram.com/p/abc/"]["views"], rows["https://www.instagram.com/p/abc/"]["engagement_rate"]) == (na, na)
    assert rows[watch(2)]["views"] == na and rows[watch(2)]["synced_at"] is None
    assert (rows[watch(3)]["views"], rows[watch(3)]["likes"], rows[watch(3)]["engagement_rate"]) == (500, na, na)
    assert (rows[watch(4)]["views"], rows[watch(4)]["engagement_rate"]) == (0, na)  # no views: no rate


def test_only_accepted_proposals_deliverables_are_reported(accepted, auth_client):
    deliver(accepted, watch(1))
    deliver(ProposalFactory(campaign=accepted.campaign, status=S.WITHDRAWN), watch(2))

    rows = auth_client(accepted.campaign.brand).get(content_url(accepted.campaign_id)).json()

    assert [r["post_url"] for r in rows] == [watch(1)]


def test_opening_the_report_never_calls_google(accepted, fake, auth_client):
    deliver(accepted, watch(1))

    auth_client(accepted.campaign.brand).get(content_url(accepted.campaign_id))

    assert fake.video_calls == [] and fake.fetch_calls == []


def test_report_for_a_campaign_with_no_deliverables_is_empty(accepted, auth_client):
    assert auth_client(accepted.campaign.brand).get(content_url(accepted.campaign_id)).json() == []


def test_content_performance_function_matches_the_endpoint(accepted):
    deliver(accepted, watch(1), views_count=10, likes_count=1, comments_count=0, stats_synced_at=timezone.now())

    assert content_performance(accepted.campaign)[0]["engagement_rate"] == Decimal("10.00")


def test_only_the_owning_brand_sees_the_report(accepted, auth_client):  # RF3
    stranger = UserFactory(role=Role.BRAND)

    assert auth_client(stranger).get(content_url(accepted.campaign_id)).status_code == 404
    assert auth_client(stranger).get(content_url(999999)).status_code == 404
    assert auth_client(accepted.creator).get(content_url(accepted.campaign_id)).status_code == 403
    assert APIClient().get(content_url(accepted.campaign_id)).status_code == 401
