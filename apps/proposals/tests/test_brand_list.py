import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Role
from apps.accounts.tests.factories import UserFactory
from apps.campaigns.models import Campaign
from apps.campaigns.tests.factories import CampaignFactory
from apps.profiles.models import CreatorProfile
from apps.proposals.models import Proposal
from apps.proposals.tests.factories import ProposalFactory
from apps.reviews.models import Review
from apps.social.models import PlatformStats

S = Proposal.Status


def list_url(campaign_id):
    return f"/api/v1/brand/campaigns/{campaign_id}/proposals/"


@pytest.fixture
def brand(db):
    return UserFactory(role=Role.BRAND)


@pytest.fixture
def campaign(brand):
    return CampaignFactory(brand=brand, status=Campaign.Status.PUBLISHED, creators_needed=3)


def fetch(auth_client, brand, campaign, **params):
    return auth_client(brand).get(list_url(campaign.pk), params)


def ids(response):
    return [row["id"] for row in response.json()["results"]]


def make_creator(*, name="Amina Rahman", niche="fitness", platform="instagram", followers=4200, engagement="5.25", verified=True):
    user = UserFactory(role=Role.CREATOR, full_name=name)
    CreatorProfile.objects.filter(user=user).update(niche=niche, primary_platform=platform)
    if followers is not None:
        PlatformStats.objects.create(
            creator=user,
            platform=platform,
            followers=followers,
            engagement_rate=engagement,
            is_verified=verified,
        )
    return user


# ---- the brand's own review ----------------------------------------------------------------------


def test_a_proposal_carries_the_brands_review_or_null_so_the_screen_can_offer_one(brand, campaign, auth_client):
    reviewed = ProposalFactory(campaign=campaign, status=S.ACCEPTED, completed_at=timezone.now())
    not_reviewed = ProposalFactory(campaign=campaign, status=S.ACCEPTED, completed_at=timezone.now())
    Review.objects.create(proposal=reviewed, brand=brand, creator=reviewed.creator, rating=4, text="Good work")

    rows = {row["id"]: row for row in fetch(auth_client, brand, campaign).json()["results"]}

    assert rows[reviewed.id]["review"]["rating"] == 4
    assert rows[reviewed.id]["review"]["text"] == "Good work"
    assert rows[not_reviewed.id]["review"] is None


# ---- ordering, filtering, visibility -------------------------------------------------------------


def test_newest_first(brand, campaign, auth_client):
    older = ProposalFactory(campaign=campaign)
    newer = ProposalFactory(campaign=campaign)

    assert ids(fetch(auth_client, brand, campaign)) == [newer.id, older.id]


def test_withdrawn_proposals_are_hidden_by_default_and_shown_with_the_filter(brand, campaign, auth_client):
    visible = [ProposalFactory(campaign=campaign, status=s) for s in (S.PENDING, S.SHORTLISTED, S.ACCEPTED, S.REJECTED)]
    withdrawn = ProposalFactory(campaign=campaign, status=S.WITHDRAWN)

    default = ids(fetch(auth_client, brand, campaign))
    only_withdrawn = ids(fetch(auth_client, brand, campaign, status="withdrawn"))

    assert withdrawn.id not in default
    assert sorted(default) == sorted(p.id for p in visible)
    assert only_withdrawn == [withdrawn.id]


@pytest.mark.parametrize("status", [S.PENDING, S.SHORTLISTED, S.ACCEPTED, S.REJECTED])
def test_status_filter(brand, campaign, auth_client, status):
    wanted = ProposalFactory(campaign=campaign, status=status)
    for other in (s for s in S if s != status):
        ProposalFactory(campaign=campaign, status=other)

    assert ids(fetch(auth_client, brand, campaign, status=status.value)) == [wanted.id]


def test_invalid_status_filter_is_rejected(brand, campaign, auth_client):
    assert fetch(auth_client, brand, campaign, status="bogus").status_code == 400


def test_only_this_campaigns_proposals_are_listed(brand, campaign, auth_client):
    mine = ProposalFactory(campaign=campaign)
    ProposalFactory(campaign=CampaignFactory(brand=brand, status=Campaign.Status.PUBLISHED))

    assert ids(fetch(auth_client, brand, campaign)) == [mine.id]


def test_closed_campaigns_proposals_are_still_listed(brand, auth_client):
    closed = CampaignFactory(brand=brand, status=Campaign.Status.CLOSED)
    proposal = ProposalFactory(campaign=closed)

    assert ids(fetch(auth_client, brand, closed)) == [proposal.id]


# ---- the accepted counter ------------------------------------------------------------------------------


def test_accepted_count_counts_only_currently_accepted(brand, campaign, auth_client):
    ProposalFactory(campaign=campaign, status=S.ACCEPTED)
    ProposalFactory(campaign=campaign, status=S.ACCEPTED)
    ProposalFactory(campaign=campaign, status=S.WITHDRAWN, withdrawal_reason="Sorry")  # was accepted, now gone
    ProposalFactory(campaign=campaign, status=S.PENDING)

    body = fetch(auth_client, brand, campaign).json()

    assert body["accepted_count"] == 2
    assert body["creators_needed"] == 3


def test_accepted_count_ignores_the_status_filter_and_paging(brand, campaign, auth_client):
    ProposalFactory(campaign=campaign, status=S.ACCEPTED)
    for _ in range(5):
        ProposalFactory(campaign=campaign, status=S.PENDING)

    body = fetch(auth_client, brand, campaign, status="pending", page_size=2).json()

    assert body["accepted_count"] == 1
    assert body["count"] == 5
    assert len(body["results"]) == 2


def test_empty_campaign_has_zero_counts(brand, campaign, auth_client):
    body = fetch(auth_client, brand, campaign).json()

    assert body["results"] == []
    assert (body["accepted_count"], body["creators_needed"], body["count"]) == (0, 3, 0)


# ---- item content ----------------------------------------------------------------------------------------


def test_item_shows_everything_the_brand_needs_to_decide(brand, campaign, auth_client):
    creator = make_creator()
    proposal = ProposalFactory(
        campaign=campaign,
        creator=creator,
        proposed_rate="275.50",
        cover_message="I would be a great fit.",
        portfolio_links=["https://instagram.com/p/1", "https://youtu.be/abc"],
        experience_note="Five years of fitness content.",
    )

    item = fetch(auth_client, brand, campaign).json()["results"][0]

    assert item == {
        "id": proposal.id,
        "creator": {
            "id": creator.id,
            "name": "Amina Rahman",
            "niche": "fitness",
            "platform": "instagram",
            "followers": 4200,
            "engagement_rate": "5.25",
            "is_verified": False,  # approved Instagram numbers show, but only YouTube plus a confirmed email verifies
            "rating_avg": None,
            "rating_count": 0,
        },
        "proposed_rate": "275.50",
        "cover_message": "I would be a great fit.",
        "portfolio_links": ["https://instagram.com/p/1", "https://youtu.be/abc"],
        "experience_note": "Five years of fitness content.",
        "status": "pending",
        "withdrawal_reason": None,
        "profile_url": f"/api/v1/creators/{creator.id}/",
        "completed_at": None,
        "review": None,
        "created_at": item["created_at"],
    }


def test_a_creator_with_verified_youtube_and_a_confirmed_email_is_shown_as_verified(brand, campaign, auth_client):
    creator = make_creator(platform="youtube", followers=5000)
    creator.email_verified = True
    creator.save(update_fields=["email_verified"])
    ProposalFactory(campaign=campaign, creator=creator)

    item = fetch(auth_client, brand, campaign).json()["results"][0]

    assert item["creator"]["is_verified"] is True


def test_creator_without_stats_has_null_numbers(brand, campaign, auth_client):
    ProposalFactory(campaign=campaign, creator=make_creator(followers=None))

    creator = fetch(auth_client, brand, campaign).json()["results"][0]["creator"]

    assert creator["followers"] is None
    assert creator["engagement_rate"] is None
    assert creator["is_verified"] is False


def test_stats_come_from_the_creators_primary_platform_only(brand, campaign, auth_client):
    creator = make_creator(platform="youtube", followers=900)
    PlatformStats.objects.create(creator=creator, platform="tiktok", followers=5_000_000, engagement_rate="9.00")
    ProposalFactory(campaign=campaign, creator=creator)

    assert fetch(auth_client, brand, campaign).json()["results"][0]["creator"]["followers"] == 900


def test_withdrawal_reason_is_shown_for_a_withdrawn_accepted_creator(brand, campaign, auth_client):
    ProposalFactory(campaign=campaign, status=S.WITHDRAWN, withdrawal_reason="Family emergency")

    item = fetch(auth_client, brand, campaign, status="withdrawn").json()["results"][0]

    assert item["withdrawal_reason"] == "Family emergency"


# ---- access ------------------------------------------------------------------------------------------------------


def test_another_brands_campaign_is_404(brand, auth_client):  # RF3
    other = CampaignFactory(status=Campaign.Status.PUBLISHED)
    ProposalFactory(campaign=other)

    assert fetch(auth_client, brand, other).status_code == 404
    assert auth_client(brand).get(list_url(999999)).status_code == 404


def test_creators_are_rejected(campaign, auth_client):
    creator = UserFactory(role=Role.CREATOR)

    assert auth_client(creator).get(list_url(campaign.pk)).status_code == 403
    assert APIClient().get(list_url(campaign.pk)).status_code == 401


def test_query_count_is_constant_for_fifty_proposals(brand, campaign, auth_client, django_assert_max_num_queries):
    for _ in range(50):
        ProposalFactory(campaign=campaign, creator=make_creator())
    client = auth_client(brand)

    with django_assert_max_num_queries(7):
        response = client.get(list_url(campaign.pk), {"page_size": 50})

    assert len(response.json()["results"]) == 50
