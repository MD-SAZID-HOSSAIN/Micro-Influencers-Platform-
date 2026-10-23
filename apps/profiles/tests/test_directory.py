import itertools

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Role
from apps.accounts.tests.factories import UserFactory
from apps.profiles.models import CreatorProfile, PortfolioItem
from apps.social.models import PlatformStats

LIST = "/api/v1/creators/"
_counter = itertools.count(1)


def detail(user_id):
    return f"/api/v1/creators/{user_id}/"


def make_creator(
    *,
    name=None,
    username=None,
    niche="fitness",
    platform="instagram",
    followers=1000,
    engagement="3.00",
    verified=None,  # None: approved for Instagram/TikTok/Facebook (an admin checked them), not Verified for YouTube
    city="Dhaka",
    country="Bangladesh",
    rate_post=None,
    rate_story=None,
    rate_video=None,
    with_stats=True,
    is_active=True,
):
    n = next(_counter)
    user = UserFactory(
        role=Role.CREATOR,
        full_name=name or f"Creator {n}",
        username=username or f"creator{n}",
        is_active=is_active,
        email_verified=verified is True,  # a Verified creator also has a confirmed email
    )
    CreatorProfile.objects.filter(user=user).update(
        niche=niche,
        primary_platform=platform,
        city=city,
        country=country,
        rate_post=rate_post,
        rate_story=rate_story,
        rate_video=rate_video,
    )
    if with_stats:
        PlatformStats.objects.create(
            creator=user,
            platform=platform,
            followers=followers,
            engagement_rate=engagement,
            is_verified=(platform != "youtube") if verified is None else verified,
        )
    return user


@pytest.fixture
def brand(db):
    return UserFactory(role=Role.BRAND)


def ids(response):
    return [row["id"] for row in response.json()["results"]]


def search(auth_client, brand, **params):
    return auth_client(brand).get(LIST, params)


# ---- filters ---------------------------------------------------------------------------


def test_filter_by_niche(brand, auth_client):
    fit = make_creator(niche="fitness")
    make_creator(niche="tech")

    assert ids(search(auth_client, brand, niche="fitness")) == [fit.id]


def test_filter_by_primary_platform(brand, auth_client):
    yt = make_creator(platform="youtube")
    make_creator(platform="instagram")

    assert ids(search(auth_client, brand, platform="youtube")) == [yt.id]


def test_filter_by_follower_range_uses_primary_platform_only(brand, auth_client):
    low = make_creator(followers=500)
    mid = make_creator(followers=5000)
    make_creator(followers=50000)
    PlatformStats.objects.create(  # huge following on a non-primary platform must not count
        creator=low, platform="tiktok", followers=9_000_000, engagement_rate="1.00"
    )

    response = search(auth_client, brand, min_followers=1000, max_followers=10000)

    assert ids(response) == [mid.id]


def test_filter_by_engagement_range(brand, auth_client):
    make_creator(engagement="1.50")
    ok = make_creator(engagement="4.00")
    make_creator(engagement="9.00")

    assert ids(search(auth_client, brand, min_engagement="3", max_engagement="5")) == [ok.id]


def test_filter_by_location_matches_city_or_country_case_insensitively(brand, auth_client):
    dhaka = make_creator(city="Dhaka", country="Bangladesh")
    paris = make_creator(city="Paris", country="France")
    make_creator(city="Berlin", country="Germany")

    assert ids(search(auth_client, brand, location="dhaka")) == [dhaka.id]
    assert ids(search(auth_client, brand, location="FRANCE")) == [paris.id]


def test_filter_by_rate_range_matches_when_any_rate_is_inside(brand, auth_client):
    cheap = make_creator(rate_post=50)
    mid = make_creator(rate_post=900, rate_video=150)
    make_creator(rate_post=900, rate_story=800)
    make_creator()  # no rates at all

    response = search(auth_client, brand, min_rate=100, max_rate=200)

    assert ids(response) == [mid.id]
    assert cheap.id not in ids(response)


def test_filter_verified_only(brand, auth_client):
    verified = make_creator(platform="youtube", followers=5000, verified=True)
    make_creator(platform="youtube", followers=5000, verified=False)
    make_creator(with_stats=False)

    assert ids(search(auth_client, brand, verified_only="true")) == [verified.id]


def test_an_approved_instagram_creator_is_not_verified(brand, auth_client):
    make_creator(platform="instagram", followers=90000)  # admin-approved numbers show, but do not verify

    card = search(auth_client, brand).json()["results"][0]

    assert card["followers"] == 90000 and card["is_verified"] is False
    assert ids(search(auth_client, brand, verified_only="true")) == []


def test_keyword_matches_name_and_username(brand, auth_client):
    by_name = make_creator(name="Amina Rahman", username="fitamina")
    by_username = make_creator(name="Someone Else", username="rahman_travels")
    make_creator(name="Nobody", username="nobody")

    response = search(auth_client, brand, q="rahman")

    assert sorted(ids(response)) == sorted([by_name.id, by_username.id])


def test_filters_combine_with_and(brand, auth_client):
    match = make_creator(niche="fitness", platform="youtube", followers=5000, verified=True)
    make_creator(niche="fitness", platform="youtube", followers=5000, verified=False)
    make_creator(niche="tech", platform="youtube", followers=5000, verified=True)

    response = search(
        auth_client, brand, niche="fitness", platform="youtube", min_followers=1000, verified_only="true"
    )

    assert ids(response) == [match.id]


@pytest.mark.parametrize(
    "params",
    [
        {"min_followers": "abc"},
        {"min_followers": "-5"},
        {"min_engagement": "x"},
        {"ordering": "bogus"},
        {"verified_only": "maybe"},
        {"niche": "astrology"},
        {"platform": "myspace"},
    ],
)
def test_invalid_query_parameters_are_rejected(brand, auth_client, params):
    response = search(auth_client, brand, **params)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation_error"


# ---- sorting and pagination ----------------------------------------------------------------


def test_default_order_is_followers_descending(brand, auth_client):
    small = make_creator(followers=100)
    big = make_creator(followers=9000)
    mid = make_creator(followers=500)

    assert ids(search(auth_client, brand)) == [big.id, mid.id, small.id]


def test_sort_by_followers_both_directions(brand, auth_client):
    small, big = make_creator(followers=100), make_creator(followers=9000)

    assert ids(search(auth_client, brand, ordering="followers")) == [small.id, big.id]
    assert ids(search(auth_client, brand, ordering="-followers")) == [big.id, small.id]


def test_sort_by_engagement(brand, auth_client):
    low, high = make_creator(engagement="1.00"), make_creator(engagement="8.00")

    assert ids(search(auth_client, brand, ordering="-engagement")) == [high.id, low.id]


def test_sort_by_rate_uses_the_cheapest_rate(brand, auth_client):
    pricey = make_creator(rate_post=500, rate_video=450)
    cheap = make_creator(rate_story=40, rate_post=900)

    assert ids(search(auth_client, brand, ordering="rate")) == [cheap.id, pricey.id]
    assert ids(search(auth_client, brand, ordering="-rate")) == [pricey.id, cheap.id]


@pytest.mark.parametrize("ordering", ["followers", "-followers", "engagement", "rate", "-rate"])
def test_creator_without_data_is_listed_and_sorts_last(brand, auth_client, ordering):
    with_data = make_creator(followers=10, engagement="1.00", rate_post=10)
    nothing = make_creator(with_stats=False)

    assert ids(search(auth_client, brand, ordering=ordering)) == [with_data.id, nothing.id]


def test_pagination_page_size_and_cap(brand, auth_client):
    for _ in range(55):
        make_creator()

    default = search(auth_client, brand).json()
    capped = search(auth_client, brand, page_size=100).json()

    assert default["count"] == 55
    assert len(default["results"]) == 20
    assert len(capped["results"]) == 50
    assert search(auth_client, brand, page=3).status_code == 200


def test_suspended_creators_are_hidden(brand, auth_client):
    visible = make_creator()
    make_creator(is_active=False)

    assert ids(search(auth_client, brand)) == [visible.id]


def test_card_fields(brand, auth_client):
    creator = make_creator(name="Amina", niche="food", platform="youtube", followers=4200, engagement="5.25", verified=True)
    CreatorProfile.objects.filter(user=creator).update(photo_url="https://img.example.com/a.png")

    card = search(auth_client, brand).json()["results"][0]

    assert card == {
        "id": creator.id,
        "name": "Amina",
        "photo_url": "https://img.example.com/a.png",
        "niche": "food",
        "primary_platform": "youtube",
        "followers": 4200,
        "engagement_rate": "5.25",
        "is_verified": True,
        "rating_avg": None,
        "rating_count": 0,
    }


def test_card_for_creator_without_stats_has_null_numbers(brand, auth_client):
    make_creator(with_stats=False)

    card = search(auth_client, brand).json()["results"][0]

    assert card["followers"] is None
    assert card["engagement_rate"] is None
    assert card["is_verified"] is False
    assert card["photo_url"] is None


def test_list_uses_a_constant_number_of_queries(brand, auth_client, django_assert_max_num_queries):
    for _ in range(30):
        make_creator(verified=True)
    client = auth_client(brand)

    with django_assert_max_num_queries(6):
        response = client.get(LIST, {"page_size": 30})

    assert len(response.json()["results"]) == 30


# ---- access control ------------------------------------------------------------------------


def test_creators_cannot_browse_the_directory(db, auth_client):
    other = make_creator()

    assert auth_client(other).get(LIST).status_code == 403
    assert auth_client(other).get(detail(other.id)).status_code == 403


def test_logged_out_visitors_are_rejected(db):
    creator = make_creator()

    assert APIClient().get(LIST).status_code == 401
    assert APIClient().get(detail(creator.id)).status_code == 401


# ---- profile view ----------------------------------------------------------------------------


def test_detail_shows_full_profile_with_stats_labels_and_portfolio(brand, auth_client):
    creator = make_creator(name="Amina", followers=4200, verified=True, rate_post=100, rate_story=50, rate_video=300)
    CreatorProfile.objects.filter(user=creator).update(bio="Fitness coach", photo_url=None)
    PlatformStats.objects.create(
        creator=creator, platform="tiktok", followers=77, engagement_rate="2.00", is_verified=False
    )
    PortfolioItem.objects.create(creator=creator, url="https://example.com/p1", caption="First")

    body = auth_client(brand).get(detail(creator.id)).json()

    assert body["id"] == creator.id
    assert body["full_name"] == "Amina"
    assert body["bio"] == "Fitness coach"
    assert body["city"] == "Dhaka"
    assert body["rate_post"] == "100.00"
    assert body["rate_story"] == "50.00"
    assert body["rate_video"] == "300.00"
    stats = {s["platform"]: s for s in body["stats"]}
    assert stats["instagram"]["is_verified"] is True
    assert stats["instagram"]["last_synced_at"] is None or isinstance(stats["instagram"]["last_synced_at"], str)
    assert "tiktok" not in stats  # typed, still waiting for an admin: hidden from brands
    assert "review_status" not in stats["instagram"] and "review_note" not in stats["instagram"]
    assert [p["caption"] for p in body["portfolio"]] == ["First"]


def test_detail_never_exposes_private_account_data(brand, auth_client):
    creator = make_creator()

    response = auth_client(brand).get(detail(creator.id))
    text = response.content.decode()

    assert creator.email not in text
    assert creator.mobile_number not in text
    assert "completion_percent" not in response.json()


def test_detail_unknown_or_non_creator_or_suspended_is_404(brand, auth_client):
    suspended = make_creator(is_active=False)
    client = auth_client(brand)

    assert client.get(detail(999999)).status_code == 404
    assert client.get(detail(brand.id)).status_code == 404
    assert client.get(detail(suspended.id)).status_code == 404
