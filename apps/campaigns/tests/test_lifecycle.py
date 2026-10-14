from datetime import timedelta

import pytest
from django.utils import timezone

from apps.accounts.models import Role
from apps.accounts.tests.factories import UserFactory
from apps.campaigns.models import Campaign
from apps.campaigns.services import close_campaign, publish_campaign
from apps.campaigns.tests.factories import CampaignFactory
from apps.core.exceptions import Conflict
from apps.notifications.models import Notification


def url(pk, action=""):
    return f"/api/v1/brand/campaigns/{pk}/{action}"


@pytest.fixture
def brand(db):
    return UserFactory(role=Role.BRAND)


def error_code(response):
    return response.json()["error"]["code"]


# ---- publish ------------------------------------------------------------------------------


def test_publish_moves_a_draft_to_published(brand, auth_client):
    campaign = CampaignFactory(brand=brand)

    response = auth_client(brand).post(url(campaign.pk, "publish/"))

    assert response.status_code == 200
    assert response.json()["status"] == "published"
    campaign.refresh_from_db()
    assert campaign.status == Campaign.Status.PUBLISHED
    assert campaign.published_at is not None


def test_publish_requires_a_future_deadline(brand, auth_client):
    campaign = CampaignFactory(brand=brand, deadline=timezone.now() - timedelta(minutes=1))

    response = auth_client(brand).post(url(campaign.pk, "publish/"))

    assert response.status_code == 400
    assert error_code(response) == "deadline_in_past"
    campaign.refresh_from_db()
    assert campaign.status == Campaign.Status.DRAFT


def test_publishing_twice_is_an_invalid_transition(brand, auth_client):
    campaign = CampaignFactory(brand=brand, status=Campaign.Status.PUBLISHED)

    response = auth_client(brand).post(url(campaign.pk, "publish/"))

    assert response.status_code == 409
    assert error_code(response) == "invalid_campaign_transition"


# ---- published campaigns are frozen ----------------------------------------------------------


@pytest.mark.parametrize("status", [Campaign.Status.PUBLISHED, Campaign.Status.CLOSED])
def test_published_and_closed_campaigns_cannot_be_edited_or_deleted(brand, auth_client, status):
    campaign = CampaignFactory(brand=brand, status=status)
    client = auth_client(brand)

    patch = client.patch(url(campaign.pk), {"title": "Changed"}, format="json")
    delete = client.delete(url(campaign.pk))

    assert patch.status_code == delete.status_code == 409
    assert error_code(patch) == error_code(delete) == "campaign_not_editable"
    campaign.refresh_from_db()
    assert campaign.title != "Changed"


def test_invalid_edit_of_a_published_campaign_still_reports_not_editable(brand, auth_client):
    campaign = CampaignFactory(brand=brand, status=Campaign.Status.PUBLISHED)

    response = auth_client(brand).patch(url(campaign.pk), {"creators_needed": 99}, format="json")

    assert error_code(response) == "campaign_not_editable"


# ---- close -----------------------------------------------------------------------------------


def test_close_published_campaign(brand, auth_client):
    campaign = CampaignFactory(brand=brand, status=Campaign.Status.PUBLISHED)

    response = auth_client(brand).post(url(campaign.pk, "close/"))

    assert response.status_code == 200
    assert response.json()["status"] == "closed"
    campaign.refresh_from_db()
    assert campaign.closed_at is not None


def test_closed_campaign_cannot_be_reopened(brand, auth_client):
    campaign = CampaignFactory(brand=brand, status=Campaign.Status.CLOSED)

    response = auth_client(brand).post(url(campaign.pk, "publish/"))

    assert response.status_code == 409
    assert error_code(response) == "invalid_campaign_transition"
    campaign.refresh_from_db()
    assert campaign.status == Campaign.Status.CLOSED


def test_closing_a_closed_campaign_is_idempotent(brand, auth_client):
    campaign = CampaignFactory(brand=brand, status=Campaign.Status.CLOSED)
    closed_at = campaign.closed_at

    response = auth_client(brand).post(url(campaign.pk, "close/"))

    assert response.status_code == 200
    campaign.refresh_from_db()
    assert campaign.closed_at == closed_at


def test_closing_a_draft_is_an_invalid_transition(brand, auth_client):
    campaign = CampaignFactory(brand=brand)

    response = auth_client(brand).post(url(campaign.pk, "close/"))

    assert response.status_code == 409
    assert error_code(response) == "invalid_campaign_transition"


def test_manual_close_does_not_send_the_auto_close_notification(brand, auth_client):
    campaign = CampaignFactory(brand=brand, status=Campaign.Status.PUBLISHED)

    auth_client(brand).post(url(campaign.pk, "close/"))

    assert not Notification.objects.filter(user=brand).exists()


# ---- service functions ------------------------------------------------------------------------


def test_service_publish_and_close_roundtrip(brand):
    campaign = CampaignFactory(brand=brand)

    publish_campaign(campaign)
    assert campaign.status == Campaign.Status.PUBLISHED
    close_campaign(campaign)
    assert campaign.status == Campaign.Status.CLOSED


def test_service_rejects_publishing_a_non_draft(brand):
    campaign = CampaignFactory(brand=brand, status=Campaign.Status.CLOSED)

    with pytest.raises(Conflict):
        publish_campaign(campaign)
