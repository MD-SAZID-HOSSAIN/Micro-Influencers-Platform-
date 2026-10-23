from decimal import Decimal
import pytest

from apps.accounts.models import Role
from apps.accounts.tests.factories import UserFactory
from apps.profiles.models import CreatorProfile
from apps.social.models import PlatformStats
from apps.social.queries import annotate_primary_stats


def annotated(user):
    return annotate_primary_stats(CreatorProfile.objects.filter(user=user)).get()


@pytest.fixture
def creator(db):
    user = UserFactory(role=Role.CREATOR, email_verified=True)
    CreatorProfile.objects.filter(user=user).update(primary_platform="youtube")
    return user


def test_annotation_uses_the_primary_platform_only(creator):
    PlatformStats.objects.create(
        creator=creator, platform="instagram", followers=900, engagement_rate="9.00", is_verified=False
    )
    PlatformStats.objects.create(
        creator=creator, platform="youtube", followers=5000, engagement_rate="3.50", is_verified=True
    )

    profile = annotated(creator)

    assert profile.primary_followers == 5000
    assert profile.primary_engagement == Decimal("3.50")
    assert profile.primary_verified is True


def test_creator_without_primary_stats_gets_none_and_not_verified(creator):
    PlatformStats.objects.create(
        creator=creator, platform="instagram", followers=900, engagement_rate="9.00", is_verified=True
    )

    profile = annotated(creator)

    assert profile.primary_followers is None
    assert profile.primary_engagement is None
    assert profile.primary_verified is False


def test_creator_without_primary_platform_gets_none(db):
    user = UserFactory(role=Role.CREATOR)
    PlatformStats.objects.create(creator=user, platform="youtube", followers=5, engagement_rate="1.00")

    assert annotated(user).primary_followers is None


def test_annotation_does_not_mix_up_creators(creator):
    other = UserFactory(role=Role.CREATOR)
    CreatorProfile.objects.filter(user=other).update(primary_platform="youtube")
    PlatformStats.objects.create(creator=creator, platform="youtube", followers=111, engagement_rate="1.00")
    PlatformStats.objects.create(creator=other, platform="youtube", followers=222, engagement_rate="2.00")

    rows = {p.user_id: p.primary_followers for p in annotate_primary_stats(CreatorProfile.objects.all())}

    assert rows == {creator.id: 111, other.id: 222}


def test_an_approved_instagram_primary_platform_does_not_verify_the_creator(creator):
    CreatorProfile.objects.filter(user=creator).update(primary_platform="instagram")
    PlatformStats.objects.create(
        creator=creator, platform="instagram", followers=50000, engagement_rate="5.00", is_verified=True
    )

    profile = annotated(creator)

    assert profile.primary_followers == 50000  # the approved numbers still show
    assert profile.primary_verified is False  # but only YouTube plus a confirmed email verifies a creator


def test_a_creator_needs_a_confirmed_email_to_be_verified(creator):
    PlatformStats.objects.create(
        creator=creator, platform="youtube", followers=5000, engagement_rate="3.50", is_verified=True
    )
    creator.email_verified = False
    creator.save(update_fields=["email_verified"])

    assert annotated(creator).primary_verified is False


def test_a_youtube_channel_under_the_minimum_does_not_verify_the_creator(creator, settings):
    PlatformStats.objects.create(
        creator=creator, platform="youtube", followers=settings.MIN_CREATOR_FOLLOWERS - 1, engagement_rate="3.50", is_verified=True
    )

    assert annotated(creator).primary_verified is False
