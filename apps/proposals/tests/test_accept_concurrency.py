"""Accepting must never exceed Creators Needed, however many requests arrive at once.

These tests need real threads and a real PostgreSQL (row locks), hence transactional_db.
"""
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from django.db import connection
from rest_framework.test import APIClient

from apps.accounts.models import Role
from apps.accounts.services import issue_access_token
from apps.accounts.tests.factories import UserFactory
from apps.campaigns.models import Campaign
from apps.campaigns.tests.factories import CampaignFactory
from apps.core.exceptions import DomainError
from apps.notifications.models import Notification
from apps.proposals.models import Proposal
from apps.proposals.services import accept_proposal, withdraw_proposal
from apps.proposals.tests.factories import ProposalFactory

S = Proposal.Status
FULL_MESSAGE = "All creators for this campaign have already been selected."

pytestmark = pytest.mark.django_db(transaction=True)


def accepted(campaign):
    return Proposal.objects.filter(campaign=campaign, status=S.ACCEPTED).count()


def run_together(jobs):
    """Run callables on separate threads (own DB connection each), released at the same moment."""
    barrier = threading.Barrier(len(jobs))

    def wrap(job):
        try:
            barrier.wait(timeout=10)
            return job()
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
        return list(pool.map(wrap, jobs))


def accept_via_service(brand, proposal):
    def job():
        try:
            accept_proposal(brand=brand, proposal_id=proposal.pk)
            return "ok"
        except DomainError as exc:
            return exc.default_code

    return job


def test_two_simultaneous_accepts_on_the_last_slot_exactly_one_succeeds():
    brand = UserFactory(role=Role.BRAND)
    campaign = CampaignFactory(brand=brand, status=Campaign.Status.PUBLISHED, creators_needed=1)
    first, second = ProposalFactory(campaign=campaign), ProposalFactory(campaign=campaign)
    token = issue_access_token(brand)

    def accept_over_http(proposal):
        def job():
            client = APIClient()
            client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
            return client.post(f"/api/v1/brand/proposals/{proposal.pk}/accept/")

        return job

    responses = run_together([accept_over_http(first), accept_over_http(second)])

    assert sorted(r.status_code for r in responses) == [200, 409]
    loser = next(r for r in responses if r.status_code == 409)
    assert loser.json()["error"]["code"] == "campaign_full"
    assert loser.json()["error"]["message"] == FULL_MESSAGE
    assert accepted(campaign) == 1


def test_twenty_concurrent_accepts_with_three_slots_yield_exactly_three():
    brand = UserFactory(role=Role.BRAND)
    campaign = CampaignFactory(brand=brand, status=Campaign.Status.PUBLISHED, creators_needed=3)
    proposals = [ProposalFactory(campaign=campaign) for _ in range(20)]

    results = run_together([accept_via_service(brand, p) for p in proposals])

    assert results.count("ok") == 3
    assert results.count("campaign_full") == 17
    assert accepted(campaign) == 3
    assert Notification.objects.filter(kind="proposal_accepted").count() == 3


def test_concurrent_double_click_on_the_same_proposal_accepts_it_once():
    brand = UserFactory(role=Role.BRAND)
    campaign = CampaignFactory(brand=brand, status=Campaign.Status.PUBLISHED, creators_needed=3)
    proposal = ProposalFactory(campaign=campaign)

    results = run_together([accept_via_service(brand, proposal) for _ in range(5)])

    assert results == ["ok"] * 5
    assert accepted(campaign) == 1
    assert Notification.objects.filter(user=proposal.creator).count() == 1


def test_accept_racing_a_withdrawal_neither_deadlocks_nor_overfills():
    brand = UserFactory(role=Role.BRAND)
    campaign = CampaignFactory(brand=brand, status=Campaign.Status.PUBLISHED, creators_needed=1)
    holder = ProposalFactory(campaign=campaign, status=S.ACCEPTED)
    waiting = ProposalFactory(campaign=campaign)

    def withdraw():
        try:
            withdraw_proposal(creator=holder.creator, proposal_id=holder.pk, reason="Cannot make it")
            return "ok"
        except DomainError as exc:
            return exc.default_code

    results = run_together([withdraw, accept_via_service(brand, waiting)])

    assert results[0] == "ok"
    assert results[1] in {"ok", "campaign_full"}  # depends on who got the lock first
    assert accepted(campaign) <= 1
    assert Proposal.objects.get(pk=holder.pk).status == S.WITHDRAWN
