from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import pytest
from django.db import IntegrityError, connection, transaction
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Role
from apps.accounts.tests.factories import UserFactory
from apps.campaigns.models import Campaign
from apps.campaigns.tests.factories import CampaignFactory
from apps.core.exceptions import DomainError
from apps.profiles.models import BrandProfile, CreatorProfile
from apps.proposals.models import Proposal
from apps.proposals.tests.factories import ProposalFactory
from apps.reviews.models import Review
from apps.reviews.services import create_review, recalculate_rating
from apps.social.models import PlatformStats

S = Proposal.Status


def review_url(pk):
    return f"/api/v1/brand/proposals/{pk}/review/"


def reviews_of(creator_id):
    return f"/api/v1/creators/{creator_id}/reviews/"


def completed(creator=None, brand=None, **kwargs):
    """A finished collaboration: Accepted and marked Completed."""
    campaign = CampaignFactory(
        status=Campaign.Status.PUBLISHED, **({"brand": brand} if brand else {}), **kwargs
    )
    extra = {"creator": creator} if creator else {}
    return ProposalFactory(campaign=campaign, status=S.ACCEPTED, completed_at=timezone.now(), **extra)


def post(auth_client, proposal, **body):
    data = {"rating": 5, "text": "Great to work with."}
    data.update(body)
    return auth_client(proposal.campaign.brand).post(review_url(proposal.pk), data, format="json")


def profile(creator):
    return CreatorProfile.objects.get(user=creator)


def error_code(response):
    return response.json()["error"]["code"]


# ---- writing a review ------------------------------------------------------------------------------------


def test_brand_reviews_a_completed_collaboration(db, auth_client):
    proposal = completed()

    response = post(auth_client, proposal, rating=4, text="Reliable and quick.")

    assert response.status_code == 201
    data = response.json()
    assert data["rating"] == 4 and data["text"] == "Reliable and quick."
    assert data["brand"]["id"] == proposal.campaign.brand_id
    assert data["campaign"] == {"id": proposal.campaign_id, "title": proposal.campaign.title}
    review = Review.objects.get(pk=data["id"])
    assert (review.proposal, review.creator, review.brand) == (proposal, proposal.creator, proposal.campaign.brand)


def test_the_text_is_optional(db, auth_client):
    proposal = completed()

    response = auth_client(proposal.campaign.brand).post(review_url(proposal.pk), {"rating": 3}, format="json")

    assert response.status_code == 201
    assert response.json()["text"] == ""


@pytest.mark.parametrize("status, completed_at", [(S.PENDING, None), (S.SHORTLISTED, None), (S.ACCEPTED, None), (S.WITHDRAWN, None)])
def test_only_a_completed_collaboration_can_be_reviewed(db, auth_client, status, completed_at):
    proposal = ProposalFactory(status=status, completed_at=completed_at)

    response = post(auth_client, proposal)

    assert response.status_code == 409
    assert error_code(response) == "not_completed"
    assert not Review.objects.exists()


def test_only_the_owning_brand_can_review(db, auth_client):  # RF3
    proposal = completed()
    stranger = UserFactory(role=Role.BRAND)

    response = auth_client(stranger).post(review_url(proposal.pk), {"rating": 1, "text": "sabotage"}, format="json")

    assert response.status_code == 404
    assert not Review.objects.exists()
    assert auth_client(stranger).post(review_url(999999), {"rating": 1}, format="json").status_code == 404


def test_one_review_per_collaboration(db, auth_client):
    proposal = completed()
    assert post(auth_client, proposal, rating=5).status_code == 201

    second = post(auth_client, proposal, rating=1)

    assert second.status_code == 409
    assert error_code(second) == "already_reviewed"
    assert Review.objects.get(proposal=proposal).rating == 5


def test_the_database_also_enforces_one_review_per_collaboration_and_the_rating_range(db):
    proposal = completed()
    brand, creator = proposal.campaign.brand, proposal.creator
    Review.objects.create(proposal=proposal, brand=brand, creator=creator, rating=5)

    with pytest.raises(IntegrityError), transaction.atomic():
        Review.objects.create(proposal=proposal, brand=brand, creator=creator, rating=4)
    other = completed()
    for bad in (0, 6):
        with pytest.raises(IntegrityError), transaction.atomic():
            Review.objects.create(proposal=other, brand=other.campaign.brand, creator=other.creator, rating=bad)


@pytest.mark.parametrize("rating", [0, 6, -1, "abc", 2.5, None])
def test_rating_must_be_a_whole_number_from_1_to_5(db, auth_client, rating):
    response = post(auth_client, completed(), rating=rating)

    assert response.status_code == 400
    assert "rating" in response.json()["error"]["details"]


@pytest.mark.parametrize("length, ok", [(500, True), (501, False)])
def test_review_text_is_limited_to_500_characters(db, auth_client, length, ok):
    response = post(auth_client, completed(), text="x" * length)

    assert (response.status_code == 201) is ok


def test_html_in_the_review_text_is_stripped(db, auth_client):  # RF2
    assert post(auth_client, completed(), text="<script>x</script>Great").json()["text"] == "xGreat"


def test_a_review_cannot_be_edited_or_deleted(db, auth_client):
    proposal = completed()
    review_id = post(auth_client, proposal).json()["id"]
    client = auth_client(proposal.campaign.brand)

    for method in ("put", "patch", "delete"):
        assert getattr(client, method)(review_url(proposal.pk), {"rating": 1}, format="json").status_code == 405
    assert Review.objects.get(pk=review_id).rating == 5


def test_creators_cannot_review_and_logged_out_gets_401(db, auth_client):
    proposal = completed()

    assert auth_client(proposal.creator).post(review_url(proposal.pk), {"rating": 5}, format="json").status_code == 403
    assert APIClient().post(review_url(proposal.pk), {"rating": 5}, format="json").status_code == 401


# ---- the rating on the profile --------------------------------------------------------------------------------


def test_average_and_count_are_recalculated_after_each_review(db, auth_client):
    creator = UserFactory(role=Role.CREATOR)
    assert (profile(creator).rating_avg, profile(creator).rating_count) == (None, 0)

    post(auth_client, completed(creator=creator), rating=5)
    assert (profile(creator).rating_avg, profile(creator).rating_count) == (Decimal("5.00"), 1)
    post(auth_client, completed(creator=creator), rating=4)
    post(auth_client, completed(creator=creator), rating=4)

    assert (profile(creator).rating_avg, profile(creator).rating_count) == (Decimal("4.33"), 3)


def test_another_creators_rating_is_untouched(db, auth_client):
    creator, bystander = UserFactory(role=Role.CREATOR), UserFactory(role=Role.CREATOR)

    post(auth_client, completed(creator=creator), rating=2)

    assert profile(bystander).rating_count == 0 and profile(bystander).rating_avg is None


def test_recalculate_rating_handles_removal_down_to_zero(db, auth_client):
    creator = UserFactory(role=Role.CREATOR)
    post(auth_client, completed(creator=creator), rating=3)
    Review.objects.all().delete()

    recalculate_rating(creator.id)

    assert (profile(creator).rating_avg, profile(creator).rating_count) == (None, 0)


@pytest.mark.django_db(transaction=True)
def test_simultaneous_reviews_of_one_creator_are_all_counted():
    if connection.vendor == "sqlite":
        pytest.skip("Requires PostgreSQL row locks; SQLite table locks on concurrent threads")
    creator = UserFactory(role=Role.CREATOR)
    proposals = [completed(creator=creator) for _ in range(8)]

    def review(proposal):
        try:
            create_review(brand=proposal.campaign.brand, proposal_id=proposal.pk, rating=4, text="")
            return "ok"
        except DomainError as exc:
            return exc.default_code
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(review, proposals))

    assert results == ["ok"] * 8
    assert (profile(creator).rating_avg, profile(creator).rating_count) == (Decimal("4.00"), 8)


# ---- where the rating shows up ----------------------------------------------------------------------------------


def rated_creator(avg_rating_values, **kwargs):
    creator = UserFactory(role=Role.CREATOR, **kwargs)
    for value in avg_rating_values:
        proposal = completed(creator=creator)
        Review.objects.create(proposal=proposal, brand=proposal.campaign.brand, creator=creator, rating=value)
    recalculate_rating(creator.id)
    return creator


def test_the_rating_shows_on_directory_cards_and_the_profile(db, auth_client):
    creator = rated_creator([5, 4])
    brand = UserFactory(role=Role.BRAND)
    client = auth_client(brand)

    card = next(c for c in client.get("/api/v1/creators/").json()["results"] if c["id"] == creator.id)
    detail = client.get(f"/api/v1/creators/{creator.id}/").json()

    assert (card["rating_avg"], card["rating_count"]) == ("4.50", 2)
    assert (detail["rating_avg"], detail["rating_count"]) == ("4.50", 2)


def test_the_rating_shows_on_the_creators_own_profile_and_on_proposals(db, auth_client):
    creator = rated_creator([3])
    own = auth_client(creator).get("/api/v1/creators/me/").json()
    campaign = CampaignFactory(status=Campaign.Status.PUBLISHED)
    ProposalFactory(campaign=campaign, creator=creator)

    item = auth_client(campaign.brand).get(f"/api/v1/brand/campaigns/{campaign.pk}/proposals/").json()["results"][0]

    assert (own["rating_avg"], own["rating_count"]) == ("3.00", 1)
    assert (item["creator"]["rating_avg"], item["creator"]["rating_count"]) == ("3.00", 1)


def test_unrated_creators_show_null_and_zero(db, auth_client):
    creator = UserFactory(role=Role.CREATOR)
    card = next(
        c for c in auth_client(UserFactory(role=Role.BRAND)).get("/api/v1/creators/").json()["results"] if c["id"] == creator.id
    )

    assert (card["rating_avg"], card["rating_count"]) == (None, 0)


def test_directory_minimum_rating_filter_and_rating_sort(db, auth_client):
    low, mid, high = rated_creator([2]), rated_creator([4]), rated_creator([5])
    unrated = UserFactory(role=Role.CREATOR)
    client = auth_client(UserFactory(role=Role.BRAND))

    def ids(**params):
        return [c["id"] for c in client.get("/api/v1/creators/", params).json()["results"]]

    assert sorted(ids(min_rating="4")) == sorted([mid.id, high.id])
    assert ids(ordering="-rating")[:3] == [high.id, mid.id, low.id]
    assert ids(ordering="rating")[:3] == [low.id, mid.id, high.id]
    assert ids(ordering="-rating")[-1] == unrated.id  # unrated sorts last either way
    assert ids(ordering="rating")[-1] == unrated.id
    assert client.get("/api/v1/creators/", {"min_rating": "6"}).status_code == 400
    assert client.get("/api/v1/creators/", {"min_rating": "abc"}).status_code == 400


# ---- the reviews of a creator ---------------------------------------------------------------------------------------


def test_brand_reads_a_creators_reviews_newest_first_with_who_wrote_them(db, auth_client):
    creator = UserFactory(role=Role.CREATOR)
    first = completed(creator=creator)
    BrandProfile.objects.filter(user=first.campaign.brand).update(company_name="Acme Foods")
    post(auth_client, first, rating=5, text="First")
    second = completed(creator=creator)
    post(auth_client, second, rating=3, text="Second")

    body = auth_client(UserFactory(role=Role.BRAND)).get(reviews_of(creator.id)).json()

    assert body["count"] == 2
    assert [r["text"] for r in body["results"]] == ["Second", "First"]
    assert body["results"][1]["brand"] == {"id": first.campaign.brand_id, "name": "Acme Foods"}


def test_reviews_list_access_rules(db, auth_client):
    creator = UserFactory(role=Role.CREATOR)
    suspended = UserFactory(role=Role.CREATOR, is_active=False)
    brand = UserFactory(role=Role.BRAND)

    assert auth_client(creator).get(reviews_of(creator.id)).status_code == 403
    assert APIClient().get(reviews_of(creator.id)).status_code == 401
    assert auth_client(brand).get(reviews_of(999999)).status_code == 404
    assert auth_client(brand).get(reviews_of(brand.id)).status_code == 404  # not a creator
    assert auth_client(brand).get(reviews_of(suspended.id)).status_code == 404
    assert auth_client(brand).get(reviews_of(creator.id)).json()["results"] == []


def test_stats_still_drive_the_other_card_fields(db, auth_client):
    creator = rated_creator([5])
    PlatformStats.objects.create(creator=creator, platform="instagram", followers=10, engagement_rate="1.00")
    CreatorProfile.objects.filter(user=creator).update(primary_platform="instagram")

    card = next(
        c for c in auth_client(UserFactory(role=Role.BRAND)).get("/api/v1/creators/").json()["results"] if c["id"] == creator.id
    )

    assert card["followers"] == 10 and card["rating_avg"] == "5.00"
