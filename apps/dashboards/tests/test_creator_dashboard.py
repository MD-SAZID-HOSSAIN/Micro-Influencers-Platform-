from datetime import timedelta

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
from apps.social.models import PlatformStats, YouTubeConnection
from apps.social.tests.fakes import make_connection

S = Proposal.Status
URL = "/api/v1/creators/me/dashboard/"


@pytest.fixture
def creator(db):
    return UserFactory(role=Role.CREATOR)


def dashboard(auth_client, creator):
    response = auth_client(creator).get(URL)
    assert response.status_code == 200
    return response.json()


def published(**kwargs):
    return CampaignFactory(status=Campaign.Status.PUBLISHED, **kwargs)


# ---- zero state ---------------------------------------------------------------------------------


def test_new_creator_dashboard_is_empty_with_a_null_rate(creator, auth_client):
    body = dashboard(auth_client, creator)

    assert body["profile_completion"] == 0
    assert body["youtube"] == {
        "connected": False,
        "status": None,
        "needs_reconnect": False,
        "last_synced_at": None,
        "is_outdated": False,
        "followers": None,
        "minimum_followers": 1000,
        "below_minimum": False,
    }
    assert body["available_campaigns"] == []
    assert body["applications"] == []
    assert body["accepted_campaigns"] == []
    assert body["performance"] == {"proposals_sent": 0, "accepted": 0, "acceptance_rate": None}


# ---- profile and connection ---------------------------------------------------------------------------


def test_profile_completion_is_included(creator, auth_client):
    CreatorProfile.objects.filter(user=creator).update(bio="Coach", niche="fitness", photo_url="https://x.example/a.png", primary_platform="youtube")

    assert dashboard(auth_client, creator)["profile_completion"] == 50


def test_connected_account_shows_last_synced_status(creator, auth_client):
    make_connection(creator)

    youtube = dashboard(auth_client, creator)["youtube"]

    assert youtube["connected"] is True
    assert youtube["status"] == "connected"
    assert youtube["needs_reconnect"] is False
    assert youtube["last_synced_at"] is not None


def test_reconnect_prompt_when_the_connection_needs_reconnecting(creator, auth_client):
    make_connection(creator, status=YouTubeConnection.Status.NEEDS_RECONNECT)
    PlatformStats.objects.filter(creator=creator).update(is_outdated=True)

    youtube = dashboard(auth_client, creator)["youtube"]

    assert youtube["needs_reconnect"] is True
    assert youtube["is_outdated"] is True
    assert youtube["last_synced_at"] is not None  # the last known stats stay visible


# ---- available campaigns ----------------------------------------------------------------------------------


def test_available_campaigns_are_the_five_newest_open_ones(creator, auth_client):
    made = [published(title=f"C{n}") for n in range(7)]
    published(deadline=timezone.now() - timedelta(minutes=1))  # expired, not yet auto-closed
    CampaignFactory(status=Campaign.Status.DRAFT)
    CampaignFactory(status=Campaign.Status.CLOSED)

    cards = dashboard(auth_client, creator)["available_campaigns"]

    assert [c["id"] for c in cards] == [c.id for c in reversed(made)][:5]


def test_available_campaigns_carry_the_eligibility_indicator(creator, auth_client):
    published(platform="instagram", min_followers=1000)
    PlatformStats.objects.create(
        creator=creator, platform="instagram", followers=5000, engagement_rate="2.00", is_verified=True
    )

    cards = dashboard(auth_client, creator)["available_campaigns"]

    assert cards[0]["eligible"] is True
    assert cards[0]["brand"]["name"]


# ---- applications -----------------------------------------------------------------------------------------


def test_applications_show_the_latest_ten_with_their_statuses(creator, auth_client):
    made = [ProposalFactory(creator=creator, status=S.PENDING) for _ in range(12)]
    ProposalFactory(status=S.ACCEPTED)  # someone else's

    rows = dashboard(auth_client, creator)["applications"]

    assert [r["id"] for r in rows] == [p.id for p in reversed(made)][:10]
    assert rows[0]["status"] == "pending"
    assert rows[0]["campaign"]["title"]


def test_accepted_campaigns_are_listed_separately_and_only_when_currently_accepted(creator, auth_client):
    accepted = ProposalFactory(creator=creator, status=S.ACCEPTED)
    ProposalFactory(creator=creator, status=S.WITHDRAWN, withdrawal_reason="Sorry")  # was accepted, now gone
    ProposalFactory(creator=creator, status=S.PENDING)
    ProposalFactory(creator=creator, status=S.REJECTED)

    body = dashboard(auth_client, creator)

    assert [r["id"] for r in body["accepted_campaigns"]] == [accepted.id]
    assert len(body["applications"]) == 4


# ---- performance --------------------------------------------------------------------------------------------


def test_withdrawn_proposals_count_as_sent(creator, auth_client):
    ProposalFactory(creator=creator, status=S.PENDING)
    ProposalFactory(creator=creator, status=S.WITHDRAWN)

    performance = dashboard(auth_client, creator)["performance"]

    assert performance == {"proposals_sent": 2, "accepted": 0, "acceptance_rate": 0.0}


def test_an_accepted_then_withdrawn_proposal_does_not_count_as_accepted(creator, auth_client):
    ProposalFactory(creator=creator, status=S.ACCEPTED)
    ProposalFactory(creator=creator, status=S.WITHDRAWN, withdrawal_reason="Sorry")  # was accepted

    performance = dashboard(auth_client, creator)["performance"]

    assert performance == {"proposals_sent": 2, "accepted": 1, "acceptance_rate": 0.5}


def test_acceptance_rate_is_a_rounded_ratio(creator, auth_client):
    ProposalFactory(creator=creator, status=S.ACCEPTED)
    ProposalFactory(creator=creator, status=S.REJECTED)
    ProposalFactory(creator=creator, status=S.PENDING)

    assert dashboard(auth_client, creator)["performance"]["acceptance_rate"] == 0.3333


def test_performance_counts_only_my_own_proposals(creator, auth_client):
    ProposalFactory(creator=creator, status=S.ACCEPTED)
    ProposalFactory(status=S.ACCEPTED)
    ProposalFactory(status=S.PENDING)

    assert dashboard(auth_client, creator)["performance"]["proposals_sent"] == 1


# ---- access and cost ---------------------------------------------------------------------------------------------


def test_brands_are_rejected_and_logged_out_gets_401(db, auth_client):
    brand = UserFactory(role=Role.BRAND)

    assert auth_client(brand).get(URL).status_code == 403
    assert APIClient().get(URL).status_code == 401


def test_query_count_is_bounded(creator, auth_client, django_assert_max_num_queries):
    make_connection(creator)
    for _ in range(8):
        published()
    for status in (S.PENDING, S.ACCEPTED, S.REJECTED, S.WITHDRAWN) * 3:
        ProposalFactory(creator=creator, status=status)
    client = auth_client(creator)

    with django_assert_max_num_queries(12):
        response = client.get(URL)

    assert response.status_code == 200


def test_status_counts_cover_every_proposal_not_just_the_ten_listed(creator, auth_client):
    for _ in range(3):
        ProposalFactory(creator=creator, status=S.SHORTLISTED)
    for _ in range(9):
        ProposalFactory(creator=creator, status=S.PENDING)
    for _ in range(11):
        ProposalFactory(creator=creator, status=S.REJECTED)

    body = dashboard(auth_client, creator)

    assert len(body["applications"]) == 10
    assert body["pending_count"] == 9
    assert body["shortlisted_count"] == 3


def test_status_counts_are_zero_for_a_new_creator_and_ignore_other_creators(creator, auth_client):
    ProposalFactory(status=S.PENDING)
    ProposalFactory(status=S.SHORTLISTED)

    body = dashboard(auth_client, creator)

    assert body["pending_count"] == 0 and body["shortlisted_count"] == 0
