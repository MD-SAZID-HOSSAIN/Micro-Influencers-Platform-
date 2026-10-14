from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Role
from apps.accounts.tests.factories import UserFactory
from apps.campaigns.models import Campaign
from apps.campaigns.tests.factories import CampaignFactory
from apps.profiles.models import BrandProfile
from apps.social.models import PlatformStats

LIST = "/api/v1/campaigns/"


def detail(pk):
    return f"/api/v1/campaigns/{pk}/"


def published(**kwargs):
    return CampaignFactory(status=Campaign.Status.PUBLISHED, **kwargs)


@pytest.fixture
def creator(db):
    return UserFactory(role=Role.CREATOR)


def ids(response):
    return [row["id"] for row in response.json()["results"]]


def search(auth_client, creator, **params):
    return auth_client(creator).get(LIST, params)


# ---- what is listed ------------------------------------------------------------------------


def test_only_published_campaigns_are_listed(creator, auth_client):
    live = published()
    CampaignFactory(status=Campaign.Status.DRAFT)
    CampaignFactory(status=Campaign.Status.CLOSED)

    assert ids(search(auth_client, creator)) == [live.id]


def test_expired_but_not_yet_closed_campaign_is_not_listed(creator, auth_client):  # RF1
    published(deadline=timezone.now() - timedelta(minutes=1))
    live = published()

    assert ids(search(auth_client, creator)) == [live.id]


def test_newest_published_first(creator, auth_client):
    first = published()
    second = published()

    assert ids(search(auth_client, creator)) == [second.id, first.id]


# ---- filters ---------------------------------------------------------------------------------


def test_filter_by_niche_and_platform(creator, auth_client):
    match = published(niche="tech", platform="youtube")
    published(niche="tech", platform="instagram")
    published(niche="food", platform="youtube")

    assert ids(search(auth_client, creator, niche="tech", platform="youtube")) == [match.id]


def test_filter_by_budget_range(creator, auth_client):
    published(budget=Decimal("50"))
    ok = published(budget=Decimal("300"))
    published(budget=Decimal("900"))

    assert ids(search(auth_client, creator, min_budget="100", max_budget="500")) == [ok.id]


def test_filter_by_deadline_window(creator, auth_client):
    now = timezone.now()
    soon = published(deadline=now + timedelta(days=2))
    published(deadline=now + timedelta(days=20))

    assert ids(search(auth_client, creator, deadline_before=(now + timedelta(days=5)).isoformat())) == [soon.id]
    later = ids(search(auth_client, creator, deadline_after=(now + timedelta(days=5)).isoformat()))
    assert soon.id not in later and len(later) == 1


def test_deadline_filters_accept_plain_dates(creator, auth_client):
    published(deadline=timezone.now() + timedelta(days=2))
    far = (timezone.now() + timedelta(days=60)).date().isoformat()

    assert len(ids(search(auth_client, creator, deadline_before=far))) == 1


def test_keyword_search_matches_title_and_description_case_insensitively(creator, auth_client):
    by_title = published(title="Summer Sunscreen push", description="x")
    by_description = published(title="Other", description="Great for SUNSCREEN lovers")
    published(title="Unrelated", description="nothing")

    response = search(auth_client, creator, q="sunscreen")

    assert sorted(ids(response)) == sorted([by_title.id, by_description.id])


@pytest.mark.parametrize(
    "params",
    [{"niche": "astrology"}, {"platform": "myspace"}, {"min_budget": "abc"}, {"max_budget": "-1"}, {"deadline_before": "tomorrow-ish"}],
)
def test_invalid_filters_are_rejected(creator, auth_client, params):
    assert search(auth_client, creator, **params).status_code == 400


# ---- the card ------------------------------------------------------------------------------------


def test_card_fields_and_brand_block(creator, auth_client):
    brand = UserFactory(role=Role.BRAND, full_name="Owner Name")
    BrandProfile.objects.filter(user=brand).update(
        company_name="Acme Foods", logo_url="https://acme.example.com/logo.png"
    )
    campaign = published(brand=brand, title="Launch", budget=Decimal("250.00"), creators_needed=3)

    card = search(auth_client, creator).json()["results"][0]

    assert card == {
        "id": campaign.id,
        "title": "Launch",
        "brand": {"id": brand.id, "name": "Acme Foods", "logo_url": "https://acme.example.com/logo.png"},
        "niche": "fitness",
        "budget": "250.00",
        "platform": "instagram",
        "deadline": card["deadline"],
        "creators_needed": 3,
        "eligible": False,
    }


def test_brand_name_falls_back_to_the_account_holder_until_a_company_name_is_set(creator, auth_client):
    brand = UserFactory(role=Role.BRAND, full_name="Owner Name")
    published(brand=brand)

    assert search(auth_client, creator).json()["results"][0]["brand"]["name"] == "Owner Name"
    assert search(auth_client, creator).json()["results"][0]["brand"]["logo_url"] is None


# ---- eligibility indicator --------------------------------------------------------------------


def stats(creator, platform="instagram", followers=5000, verified=False):
    PlatformStats.objects.create(
        creator=creator, platform=platform, followers=followers, engagement_rate="2.00", is_verified=verified
    )


def eligible(auth_client, creator):
    return search(auth_client, creator).json()["results"][0]["eligible"]


def test_eligible_when_platform_stats_exist_and_meet_the_minimum(creator, auth_client):
    published(platform="instagram", min_followers=3000)
    stats(creator, followers=5000)

    assert eligible(auth_client, creator) is True


def test_unverified_stats_count_as_eligible(creator, auth_client):
    published(platform="instagram", min_followers=3000)
    stats(creator, followers=5000, verified=False)

    assert eligible(auth_client, creator) is True


def test_not_eligible_without_stats_for_the_platform(creator, auth_client):
    published(platform="youtube", min_followers=None)
    stats(creator, platform="instagram")

    assert eligible(auth_client, creator) is False


def test_not_eligible_below_the_minimum(creator, auth_client):
    published(platform="instagram", min_followers=6000)
    stats(creator, followers=5000)

    assert eligible(auth_client, creator) is False


def test_eligible_when_no_minimum_is_set(creator, auth_client):
    published(platform="instagram", min_followers=None)
    stats(creator, followers=1)

    assert eligible(auth_client, creator) is True


def test_eligibility_is_informational_and_never_hides_campaigns(creator, auth_client):
    published(platform="youtube", min_followers=1_000_000)

    assert len(ids(search(auth_client, creator))) == 1


# ---- detail ------------------------------------------------------------------------------------------


def test_published_detail_has_full_information(creator, auth_client):
    brand = UserFactory(role=Role.BRAND)
    campaign = published(brand=brand, description="Full description", deliverables="3 reels", min_followers=2000)

    body = auth_client(creator).get(detail(campaign.pk)).json()

    assert body["id"] == campaign.id
    assert body["description"] == "Full description"
    assert body["deliverables"] == "3 reels"
    assert body["min_followers"] == 2000
    assert body["status"] == "published"
    assert body["brand"]["id"] == brand.id  # the frontend links this to brands/{id}/
    assert "deadline" in body and "creators_needed" in body and "eligible" in body


def test_closed_campaign_detail_is_visible(creator, auth_client):
    campaign = CampaignFactory(status=Campaign.Status.CLOSED)

    response = auth_client(creator).get(detail(campaign.pk))

    assert response.status_code == 200
    assert response.json()["status"] == "closed"


def test_published_campaign_past_its_deadline_still_opens(creator, auth_client):
    campaign = published(deadline=timezone.now() - timedelta(minutes=5))

    assert auth_client(creator).get(detail(campaign.pk)).status_code == 200


def test_draft_detail_is_404(creator, auth_client):
    campaign = CampaignFactory(status=Campaign.Status.DRAFT)

    assert auth_client(creator).get(detail(campaign.pk)).status_code == 404
    assert auth_client(creator).get(detail(999999)).status_code == 404


# ---- access ---------------------------------------------------------------------------------------------


def test_brands_cannot_browse_creator_campaign_discovery(db, auth_client):
    brand = UserFactory(role=Role.BRAND)
    campaign = published()

    assert auth_client(brand).get(LIST).status_code == 403
    assert auth_client(brand).get(detail(campaign.pk)).status_code == 403


def test_logged_out_visitors_are_rejected(db):
    campaign = published()

    assert APIClient().get(LIST).status_code == 401
    assert APIClient().get(detail(campaign.pk)).status_code == 401


def test_pagination_cap(creator, auth_client):
    for _ in range(55):
        published()

    assert len(search(auth_client, creator, page_size=100).json()["results"]) == 50


def test_list_query_count_is_constant(creator, auth_client, django_assert_max_num_queries):
    stats(creator)
    for _ in range(30):
        published()
    client = auth_client(creator)

    with django_assert_max_num_queries(6):
        response = client.get(LIST, {"page_size": 30})

    assert len(response.json()["results"]) == 30
