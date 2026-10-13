from decimal import Decimal

import factory

from apps.accounts.models import Role
from apps.accounts.tests.factories import UserFactory
from apps.campaigns.models import Campaign
from apps.campaigns.tests.factories import CampaignFactory
from apps.proposals.models import Proposal


class ProposalFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Proposal

    campaign = factory.SubFactory(CampaignFactory, status=Campaign.Status.PUBLISHED)
    creator = factory.SubFactory(UserFactory, role=Role.CREATOR)
    status = Proposal.Status.PENDING
    cover_message = "I would love to work with you."
    proposed_rate = Decimal("300.00")
    portfolio_links = factory.LazyFunction(list)
    experience_note = ""
