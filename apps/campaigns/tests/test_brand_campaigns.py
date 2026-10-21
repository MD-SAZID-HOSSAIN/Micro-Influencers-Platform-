from datetime import timedelta

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Role
from apps.accounts.tests.factories import UserFactory
from apps.campaigns.models import Campaign
from apps.campaigns.tests.factories import CampaignFactory

LIST = "/api/v1/brand/campaigns/"


def detail(pk):
    return f"/api/v1/brand/campaigns/{pk}/"


def payload(**overrides):
    data = {
        "title": "Summer launch",
        "description": "Show our new sunscreen to your followers.",
        "niche": "beauty",
        "platform": "instagram",
        "budget": "250.00",
        "deadline": (timezone.now() + timedelta(days=10)).isoformat(),
        "deliverables": "2 posts, 1 reel",
    }
    data.update(overrides)
    return data


@pytest.fixture
def brand(db):
    return UserFactory(role=Role.BRAND)


# ---- create ---------------------------------------------------------------------------


def test_create_defaults_to_draft_and_creators_needed_1(brand, auth_client):
    response = auth_client(brand).post(LIST, payload(), format="json")

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "draft"
    assert body["creators_needed"] == 1
    assert body["min_followers"] is None
    assert body["published_at"] is None
    assert body["closed_at"] is None
    assert body["budget"] == "250.00"
    campaign = Campaign.objects.get(pk=body["id"])
    assert campaign.brand == brand


def test_status_cannot_be_set_on_create(brand, auth_client):
    response = auth_client(brand).post(LIST, payload(status="published"), format="json")

    assert response.json()["status"] == "draft"


@pytest.mark.parametrize("value, ok", [(0, False), (1, True), (20, True), (21, False), (-3, False)])
def test_creators_needed_must_be_between_1_and_20(brand, auth_client, value, ok):
    response = auth_client(brand).post(LIST, payload(creators_needed=value), format="json")

    assert (response.status_code == 201) is ok
    if not ok:
        assert "creators_needed" in response.json()["error"]["details"]


def test_creators_needed_must_be_a_whole_number(brand, auth_client):
    response = auth_client(brand).post(LIST, payload(creators_needed="2.5"), format="json")

    assert response.status_code == 400


def test_db_check_constraint_blocks_creators_needed_21(brand):
    with pytest.raises(IntegrityError), transaction.atomic():
        CampaignFactory(brand=brand, creators_needed=21)


def test_db_check_constraint_blocks_creators_needed_0(brand):
    with pytest.raises(IntegrityError), transaction.atomic():
        CampaignFactory(brand=brand, creators_needed=0)


@pytest.mark.parametrize("budget", ["0", "0.00", "-5", "abc"])
def test_budget_must_be_positive(brand, auth_client, budget):
    response = auth_client(brand).post(LIST, payload(budget=budget), format="json")

    assert response.status_code == 400
    assert "budget" in response.json()["error"]["details"]


@pytest.mark.parametrize(
    "field", ["title", "description", "niche", "platform", "budget", "deadline", "deliverables"]
)
def test_required_fields(brand, auth_client, field):
    data = payload()
    del data[field]

    response = auth_client(brand).post(LIST, data, format="json")

    assert response.status_code == 400
    assert field in response.json()["error"]["details"]


@pytest.mark.parametrize("override", [{"niche": "astrology"}, {"platform": "myspace"}, {"min_followers": -1}])
def test_invalid_values_rejected(brand, auth_client, override):
    assert auth_client(brand).post(LIST, payload(**override), format="json").status_code == 400


def test_minimum_followers_is_optional_and_stored(brand, auth_client):
    response = auth_client(brand).post(LIST, payload(min_followers=2500), format="json")

    assert response.json()["min_followers"] == 2500


def test_deadline_in_the_past_is_rejected(brand, auth_client):
    past = (timezone.now() - timedelta(days=1)).isoformat()

    response = auth_client(brand).post(LIST, payload(deadline=past), format="json")

    assert response.status_code == 400
    assert "deadline" in response.json()["error"]["details"]


def test_html_in_text_fields_is_stripped(brand, auth_client):  # RF2
    response = auth_client(brand).post(
        LIST,
        payload(
            title="<script>alert(1)</script>Launch",
            description="<img src=x onerror=alert(1)>Great",
            deliverables="<b>2 posts</b>",
        ),
        format="json",
    )

    body = response.json()
    assert body["title"] == "alert(1)Launch"
    assert body["description"] == "Great"
    assert body["deliverables"] == "2 posts"


# ---- read / update / delete (drafts) --------------------------------------------------------


def test_draft_can_be_edited(brand, auth_client):
    campaign = CampaignFactory(brand=brand)

    response = auth_client(brand).patch(
        detail(campaign.pk), {"title": "New title", "creators_needed": 3}, format="json"
    )

    assert response.status_code == 200
    campaign.refresh_from_db()
    assert (campaign.title, campaign.creators_needed) == ("New title", 3)


def test_draft_can_be_deleted(brand, auth_client):
    campaign = CampaignFactory(brand=brand)

    assert auth_client(brand).delete(detail(campaign.pk)).status_code == 204
    assert not Campaign.objects.filter(pk=campaign.pk).exists()


def test_put_is_not_allowed(brand, auth_client):
    campaign = CampaignFactory(brand=brand)

    assert auth_client(brand).put(detail(campaign.pk), payload(), format="json").status_code == 405


def test_brand_sees_only_own_campaigns_newest_first(brand, auth_client):
    older = CampaignFactory(brand=brand, title="Older")
    newer = CampaignFactory(brand=brand, title="Newer")
    CampaignFactory()  # another brand's campaign

    response = auth_client(brand).get(LIST)

    assert [c["id"] for c in response.json()["results"]] == [newer.id, older.id]


def test_list_can_be_filtered_by_status(brand, auth_client):
    draft = CampaignFactory(brand=brand)
    CampaignFactory(brand=brand, status=Campaign.Status.PUBLISHED)

    response = auth_client(brand).get(LIST, {"status": "draft"})

    assert [c["id"] for c in response.json()["results"]] == [draft.id]
    assert auth_client(brand).get(LIST, {"status": "bogus"}).status_code == 400


# ---- access control --------------------------------------------------------------------------


@pytest.mark.parametrize("method, suffix", [("get", ""), ("patch", ""), ("delete", ""), ("post", "publish/"), ("post", "close/")])
def test_another_brands_campaign_is_404(brand, auth_client, method, suffix):  # RF3
    victim = CampaignFactory()
    url = detail(victim.pk) + suffix

    response = getattr(auth_client(brand), method)(url, {"title": "hijack"}, format="json")

    assert response.status_code == 404
    victim.refresh_from_db()
    assert victim.title != "hijack"
    assert victim.status == Campaign.Status.DRAFT


def test_creators_cannot_use_brand_campaign_endpoints(db, auth_client):
    creator = UserFactory(role=Role.CREATOR)
    campaign = CampaignFactory()

    assert auth_client(creator).get(LIST).status_code == 403
    assert auth_client(creator).post(LIST, payload(), format="json").status_code == 403
    assert auth_client(creator).get(detail(campaign.pk)).status_code == 403


def test_logged_out_is_401(db):
    assert APIClient().get(LIST).status_code == 401


# ---- may creators withdraw? (the brand's choice when it posts) ----------------------------------------------


def test_allow_withdrawal_defaults_to_true_and_can_be_turned_off_in_a_draft(brand, auth_client):
    client = auth_client(brand)

    default = client.post(LIST, payload(), format="json")
    strict = client.post(LIST, payload(allow_withdrawal=False), format="json")

    assert default.status_code == 201 and default.json()["allow_withdrawal"] is True
    assert strict.status_code == 201 and strict.json()["allow_withdrawal"] is False
    assert client.patch(detail(default.json()["id"]), {"allow_withdrawal": False}, format="json").json()[
        "allow_withdrawal"
    ] is False


def test_the_choice_is_fixed_once_the_campaign_is_published(brand, auth_client):
    campaign = CampaignFactory(brand=brand, status=Campaign.Status.PUBLISHED, allow_withdrawal=True)

    response = auth_client(brand).patch(detail(campaign.pk), {"allow_withdrawal": False}, format="json")

    assert response.status_code == 409
    campaign.refresh_from_db()
    assert campaign.allow_withdrawal is True


def test_creators_see_the_rule_before_they_apply(db, auth_client):
    creator = UserFactory(role=Role.CREATOR)
    strict = CampaignFactory(status=Campaign.Status.PUBLISHED, allow_withdrawal=False)
    open_one = CampaignFactory(status=Campaign.Status.PUBLISHED, allow_withdrawal=True)

    assert auth_client(creator).get(f"/api/v1/campaigns/{strict.pk}/").json()["allow_withdrawal"] is False
    assert auth_client(creator).get(f"/api/v1/campaigns/{open_one.pk}/").json()["allow_withdrawal"] is True

