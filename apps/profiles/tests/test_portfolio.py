from concurrent.futures import ThreadPoolExecutor

import pytest
from django.db import connection
from rest_framework.test import APIClient

from apps.accounts.models import Role
from apps.accounts.tests.factories import UserFactory
from apps.core.exceptions import DomainError
from apps.profiles.models import CreatorProfile, PortfolioItem
from apps.profiles.services import add_portfolio_item, completion_percent
from apps.social.models import PlatformStats

LIST = "/api/v1/creators/me/portfolio/"


def item_url(pk):
    return f"/api/v1/creators/me/portfolio/{pk}/"


@pytest.fixture
def creator(db):
    return UserFactory(role=Role.CREATOR)


def add(client, n=1, **overrides):
    data = {"url": f"https://instagram.com/p/{n}", "caption": f"Post {n}"}
    data.update(overrides)
    return client.post(LIST, data, format="json")


def test_add_item_with_url_and_caption(creator, auth_client):
    response = add(auth_client(creator))

    assert response.status_code == 201
    body = response.json()
    assert body["url"] == "https://instagram.com/p/1"
    assert body["caption"] == "Post 1"
    assert body["source"] == "manual"
    assert PortfolioItem.objects.get(creator=creator).caption == "Post 1"


def test_caption_is_optional_and_source_can_be_youtube(creator, auth_client):
    response = auth_client(creator).post(
        LIST, {"url": "https://youtu.be/abc", "source": "youtube"}, format="json"
    )

    assert response.status_code == 201
    assert response.json()["caption"] == ""
    assert response.json()["source"] == "youtube"


def test_unknown_source_rejected(creator, auth_client):
    assert add(auth_client(creator), source="tiktok").status_code == 400


def test_url_is_required(creator, auth_client):
    response = auth_client(creator).post(LIST, {"caption": "x"}, format="json")

    assert response.status_code == 400
    assert "url" in response.json()["error"]["details"]


def test_list_returns_only_my_items_newest_first(creator, auth_client):
    other = UserFactory(role=Role.CREATOR)
    add_portfolio_item(creator=other, url="https://example.com/theirs", caption="")
    client = auth_client(creator)
    add(client, 1)
    add(client, 2)

    response = client.get(LIST)

    assert response.status_code == 200
    assert [i["caption"] for i in response.json()] == ["Post 2", "Post 1"]


def test_eleventh_item_rejected(creator, auth_client):
    client = auth_client(creator)
    for n in range(10):
        assert add(client, n).status_code == 201

    response = add(client, 10)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "portfolio_full"
    assert PortfolioItem.objects.filter(creator=creator).count() == 10


def test_delete_frees_a_slot(creator, auth_client):
    client = auth_client(creator)
    ids = [add(client, n).json()["id"] for n in range(10)]

    assert client.delete(item_url(ids[0])).status_code == 204
    assert add(client, 99).status_code == 201


def test_cannot_delete_other_creators_item(creator, auth_client):
    other = UserFactory(role=Role.CREATOR)
    theirs = add_portfolio_item(creator=other, url="https://example.com/theirs", caption="")

    assert auth_client(creator).delete(item_url(theirs.id)).status_code == 404
    assert PortfolioItem.objects.filter(pk=theirs.pk).exists()


@pytest.mark.parametrize("url", ["javascript:alert(1)", "data:text/html,x", "//evil.com", "instagram.com/p/1"])
def test_unsafe_url_rejected(creator, auth_client, url):  # RF2
    response = add(auth_client(creator), url=url)

    assert response.status_code == 400
    assert "url" in response.json()["error"]["details"]


def test_html_in_caption_is_stripped(creator, auth_client):  # RF2
    response = add(auth_client(creator), caption="<script>alert(1)</script>Nice")

    assert response.json()["caption"] == "alert(1)Nice"


def test_brand_cannot_add_and_logged_out_gets_401(db, auth_client):
    brand = UserFactory(role=Role.BRAND)

    assert add(auth_client(brand)).status_code == 403
    assert auth_client(brand).get(LIST).status_code == 403
    assert APIClient().get(LIST).status_code == 401


def test_completion_percent_reaches_100_with_every_item(creator):
    profile = CreatorProfile.objects.get(user=creator)
    profile.photo_url = "https://img.example.com/a.png"
    profile.bio = "Coach"
    profile.niche = "fitness"
    profile.primary_platform = "youtube"
    profile.city, profile.country = "Dhaka", "Bangladesh"
    profile.rate_post = "100"
    PlatformStats.objects.create(creator=creator, platform="youtube", followers=1, engagement_rate="1.00")
    assert completion_percent(profile) == 88  # 7 of 8, rounded half-up

    add_portfolio_item(creator=creator, url="https://example.com/p", caption="")

    assert completion_percent(profile) == 100


@pytest.mark.django_db(transaction=True)
def test_parallel_adds_never_exceed_ten():
    creator = UserFactory(role=Role.CREATOR)

    def attempt(n):
        try:
            add_portfolio_item(creator=creator, url=f"https://example.com/{n}", caption="")
            return "ok"
        except DomainError as exc:
            return exc.default_code
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=12) as pool:
        results = list(pool.map(attempt, range(12)))

    assert results.count("ok") == 10
    assert results.count("portfolio_full") == 2
    assert PortfolioItem.objects.filter(creator=creator).count() == 10
