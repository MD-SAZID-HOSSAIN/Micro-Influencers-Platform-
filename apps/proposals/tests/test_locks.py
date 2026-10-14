"""The helper that takes the campaign-then-proposal lock is shared by three apps, so it is public and tested.

Accepting, withdrawing, completing and reviewing all lock the campaign row first and the proposal row
second. If any of them took the locks in the other order, two simultaneous requests could wait for each
other forever (a deadlock). Keeping the order in one named, documented place is what stops that.
"""
import ast
from pathlib import Path

import pytest
from django.db import connection, transaction
from django.test.utils import CaptureQueriesContext
from rest_framework.exceptions import NotFound

from apps.campaigns.models import Campaign
from apps.campaigns.tests.factories import CampaignFactory
from apps.proposals.locks import lock_proposal_for_brand
from apps.proposals.tests.factories import ProposalFactory

APPS_DIR = Path(__file__).resolve().parents[2]


@pytest.fixture
def proposal(db):
    return ProposalFactory(campaign=CampaignFactory(status=Campaign.Status.PUBLISHED))


def test_returns_the_campaign_and_proposal_for_the_owning_brand(proposal):
    campaign, locked = lock_proposal_for_brand(proposal.campaign.brand, proposal.pk)

    assert (campaign.pk, locked.pk) == (proposal.campaign_id, proposal.pk)
    assert locked.creator_id == proposal.creator_id  # the creator comes with it: callers notify them


def test_another_brands_proposal_is_not_found(proposal):
    stranger = CampaignFactory().brand

    with pytest.raises(NotFound):
        lock_proposal_for_brand(stranger, proposal.pk)


def test_an_unknown_proposal_is_not_found(proposal):
    with pytest.raises(NotFound):
        lock_proposal_for_brand(proposal.campaign.brand, 999999)


def test_the_campaign_is_locked_before_the_proposal(proposal):
    with transaction.atomic(), CaptureQueriesContext(connection) as queries:
        lock_proposal_for_brand(proposal.campaign.brand, proposal.pk)

    locking = [q["sql"] for q in queries.captured_queries if "FOR UPDATE" in q["sql"]]
    assert len(locking) == 2
    assert "campaigns_campaign" in locking[0]
    assert "proposals_proposal" in locking[1]


def test_no_app_reaches_into_another_apps_private_names():
    """A leading underscore means 'internal to this module'. Importing one from another app hides a
    dependency (here: the lock order) from anyone refactoring the module that defines it."""
    offenders = []
    for path in APPS_DIR.rglob("*.py"):
        relative = path.relative_to(APPS_DIR)
        if "migrations" in relative.parts or "tests" in relative.parts:
            continue
        own_app = relative.parts[0]
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.ImportFrom) or not node.module or node.level:
                continue
            parts = node.module.split(".")
            if parts[0] != "apps" or len(parts) < 2 or parts[1] == own_app:
                continue
            for alias in node.names:
                if alias.name.startswith("_") and not alias.name.startswith("__"):
                    offenders.append(f"{relative}: from {node.module} import {alias.name}")

    assert offenders == []
