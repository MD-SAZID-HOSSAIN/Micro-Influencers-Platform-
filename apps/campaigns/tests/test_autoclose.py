from datetime import timedelta

import pytest
from celery.schedules import crontab
from django.utils import timezone
from freezegun import freeze_time

from apps.accounts.models import Role
from apps.accounts.tests.factories import UserFactory
from apps.campaigns.models import Campaign
from apps.campaigns.tasks import close_expired_campaigns
from apps.campaigns.tests.factories import CampaignFactory
from apps.notifications.models import Kind, Notification

PAST = lambda: timezone.now() - timedelta(minutes=1)  # noqa: E731
FUTURE = lambda: timezone.now() + timedelta(days=1)  # noqa: E731


@pytest.fixture
def brand(db):
    return UserFactory(role=Role.BRAND)


def status_of(campaign):
    campaign.refresh_from_db()
    return campaign.status


def test_closes_only_expired_published_campaigns_and_notifies_the_brand_once(brand):
    expired = CampaignFactory(brand=brand, title="Old one", status=Campaign.Status.PUBLISHED, deadline=PAST())
    live = CampaignFactory(brand=brand, status=Campaign.Status.PUBLISHED, deadline=FUTURE())
    draft = CampaignFactory(brand=brand, status=Campaign.Status.DRAFT, deadline=PAST())
    closed = CampaignFactory(brand=brand, status=Campaign.Status.CLOSED, deadline=PAST())

    count = close_expired_campaigns()

    assert count == 1
    assert status_of(expired) == Campaign.Status.CLOSED
    assert expired.closed_at is not None
    assert status_of(live) == Campaign.Status.PUBLISHED
    assert status_of(draft) == Campaign.Status.DRAFT
    assert status_of(closed) == Campaign.Status.CLOSED
    notes = Notification.objects.filter(user=brand)
    assert notes.count() == 1
    assert notes[0].kind == Kind.CAMPAIGN_AUTO_CLOSED
    assert "Old one" in notes[0].message
    assert notes[0].payload == {"campaign_id": expired.id}


def test_second_run_creates_no_duplicate_notification(brand):
    CampaignFactory(brand=brand, status=Campaign.Status.PUBLISHED, deadline=PAST())

    assert close_expired_campaigns() == 1
    assert close_expired_campaigns() == 0

    assert Notification.objects.filter(user=brand).count() == 1


def test_a_campaign_closes_exactly_at_its_deadline(brand):
    with freeze_time("2026-10-13 12:00:00"):
        campaign = CampaignFactory(
            brand=brand, status=Campaign.Status.PUBLISHED, deadline=timezone.now() + timedelta(hours=1)
        )
    with freeze_time("2026-10-13 12:59:59"):
        assert close_expired_campaigns() == 0
    with freeze_time("2026-10-13 13:00:00"):
        assert close_expired_campaigns() == 1

    assert status_of(campaign) == Campaign.Status.CLOSED


def test_a_manually_closed_campaign_is_not_auto_closed_or_notified(brand):
    campaign = CampaignFactory(brand=brand, status=Campaign.Status.PUBLISHED, deadline=PAST())
    campaign.status = Campaign.Status.CLOSED
    campaign.save(update_fields=["status"])

    assert close_expired_campaigns() == 0
    assert not Notification.objects.filter(user=brand).exists()


def test_each_brand_is_notified_about_its_own_campaigns(db):
    a, b = UserFactory(role=Role.BRAND), UserFactory(role=Role.BRAND)
    CampaignFactory(brand=a, status=Campaign.Status.PUBLISHED, deadline=PAST())
    CampaignFactory(brand=b, status=Campaign.Status.PUBLISHED, deadline=PAST())

    close_expired_campaigns()

    assert Notification.objects.filter(user=a).count() == 1
    assert Notification.objects.filter(user=b).count() == 1


def test_beat_schedule_runs_every_five_minutes(settings):
    entry = settings.CELERY_BEAT_SCHEDULE["close-expired-campaigns"]

    assert entry["task"] == "apps.campaigns.tasks.close_expired_campaigns"
    assert entry["schedule"] == crontab(minute="*/5")


def test_task_is_registered_with_celery():
    from config.celery import app

    app.loader.import_default_modules()

    assert "apps.campaigns.tasks.close_expired_campaigns" in app.tasks
