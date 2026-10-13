from datetime import timedelta
from decimal import Decimal

import factory
from django.utils import timezone

from apps.accounts.models import Role
from apps.accounts.tests.factories import UserFactory
from apps.campaigns.models import Campaign


class CampaignFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Campaign

    brand = factory.SubFactory(UserFactory, role=Role.BRAND)
    title = factory.Sequence(lambda n: f"Campaign {n}")
    description = "Promote our new product to your audience."
    niche = "fitness"
    platform = "instagram"
    budget = Decimal("500.00")
    deadline = factory.LazyFunction(lambda: timezone.now() + timedelta(days=7))
    deliverables = "2 Instagram posts, 1 reel"
    creators_needed = 1
    min_followers = None
    status = Campaign.Status.DRAFT
    published_at = factory.LazyAttribute(
        lambda o: timezone.now() if o.status != Campaign.Status.DRAFT else None
    )
    closed_at = factory.LazyAttribute(
        lambda o: timezone.now() if o.status == Campaign.Status.CLOSED else None
    )
