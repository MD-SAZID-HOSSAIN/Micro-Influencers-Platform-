import time

import pytest
from django.core.management import CommandError, call_command
from django.db import connection
from django.db.models import Count, Q
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.campaigns.models import Campaign
from apps.profiles.models import BrandProfile, CreatorProfile
from apps.proposals.models import Proposal
from apps.social.models import BrandSocialAccount, PlatformStats

DEMO_PASSWORD = "DemoPass123!"


@pytest.fixture
def debug_on(settings):
    settings.DEBUG = True


def seed(**kwargs):
    call_command("seed_demo", stdout=None, **kwargs)


def counts():
    return {
        "creators": User.objects.filter(role=Role.CREATOR).count(),
        "brands": User.objects.filter(role=Role.BRAND).count(),
        "campaigns": Campaign.objects.count(),
        "proposals": Proposal.objects.count(),
    }


# ---- the command --------------------------------------------------------------------------------


def test_creates_the_requested_counts_and_is_idempotent(db, debug_on):
    seed(creators=20, brands=3, campaigns=10)
    first = counts()

    seed(creators=20, brands=3, campaigns=10)

    assert (first["creators"], first["brands"], first["campaigns"]) == (20, 3, 10)
    assert first["proposals"] > 0
    assert counts() == first


def test_running_again_with_larger_numbers_tops_up_without_duplicating(db, debug_on):
    seed(creators=10, brands=2, campaigns=5)

    seed(creators=15, brands=3, campaigns=8)

    after = counts()
    assert (after["creators"], after["brands"], after["campaigns"]) == (15, 3, 8)
    assert len(set(User.objects.values_list("username", flat=True))) == User.objects.count()


def test_refuses_to_run_when_debug_is_off(db, settings):
    settings.DEBUG = False

    with pytest.raises(CommandError, match="DEBUG"):
        seed(creators=5, brands=1, campaigns=2)

    assert User.objects.count() == 0


def test_demo_accounts_can_log_in_with_the_documented_password(db, debug_on):
    seed(creators=3, brands=2, campaigns=2)
    client = APIClient()

    for username, role in (("demo_creator_001", "creator"), ("demo_brand_01", "brand")):
        response = client.post(
            "/api/v1/auth/login/", {"identifier": username, "password": DEMO_PASSWORD}, format="json"
        )
        assert response.status_code == 200
        assert response.json()["user"]["role"] == role


def test_demo_data_does_not_depend_on_python_hash_randomisation(db, debug_on):
    seed(creators=1, brands=0, campaigns=0)

    # A fixed literal: it would change from run to run if the seeder used the built-in hash().
    assert User.objects.get(username="demo_creator_001").mobile_number == "+8801175237566"


def test_each_demo_user_is_the_same_regardless_of_how_many_were_seeded(db, debug_on):
    seed(creators=10, brands=1, campaigns=0)
    profile = CreatorProfile.objects.get(user__username="demo_creator_003")
    niche = profile.niche
    stats = PlatformStats.objects.filter(creator=profile.user, platform=profile.primary_platform)
    followers = stats.get().followers
    User.objects.filter(username__startswith="demo_").delete()

    seed(creators=30, brands=1, campaigns=0)

    profile = CreatorProfile.objects.get(user__username="demo_creator_003")
    assert profile.niche == niche
    stats = PlatformStats.objects.filter(creator=profile.user, platform=profile.primary_platform)
    assert stats.get().followers == followers


def test_demo_brands_are_email_verified_and_demo_creators_have_youtube_except_every_fifth(db, debug_on):
    seed(creators=10, brands=3, campaigns=0)

    assert not User.objects.filter(role=Role.BRAND, email_verified=False).exists()
    for i in range(1, 11):
        verified = PlatformStats.objects.filter(
            creator__username=f"demo_creator_{i:03d}", platform="youtube", is_verified=True
        ).exists()
        assert verified == (i % 5 != 0), i


def test_seeding_again_repairs_accounts_created_before_the_verification_rules(db, debug_on):
    seed(creators=5, brands=2, campaigns=0)
    User.objects.filter(role=Role.BRAND).update(email_verified=False)
    PlatformStats.objects.filter(platform="youtube").delete()

    seed(creators=5, brands=2, campaigns=0)

    assert not User.objects.filter(role=Role.BRAND, email_verified=False).exists()
    assert PlatformStats.objects.filter(creator__username="demo_creator_001", platform="youtube", is_verified=True).exists()


# ---- the data respects the product's rules --------------------------------------------------------------


def test_seeded_data_respects_the_business_rules(db, debug_on):
    seed(creators=60, brands=6, campaigns=40)

    over_accepted = Campaign.objects.annotate(
        accepted=Count("proposals", filter=Q(proposals__status=Proposal.Status.ACCEPTED))
    ).filter(accepted__gt=models_f("creators_needed"))
    assert not over_accepted.exists()
    assert not Campaign.objects.filter(creators_needed__lt=1).exists()
    assert not Campaign.objects.filter(creators_needed__gt=20).exists()
    # Nothing is left Published with a deadline that already passed.
    assert not Campaign.objects.filter(
        status=Campaign.Status.PUBLISHED, deadline__lte=timezone.now()
    ).exists()
    # Every status appears, so the frontend can see all states.
    assert set(Campaign.objects.values_list("status", flat=True)) == set(Campaign.Status.values)
    assert set(Proposal.objects.values_list("status", flat=True)) == set(Proposal.Status.values)
    # Profiles exist and the primary platform has stats; verified stats carry a sync time.
    assert CreatorProfile.objects.count() == 60 and BrandProfile.objects.count() == 6
    for profile in CreatorProfile.objects.all()[:60]:
        assert PlatformStats.objects.filter(
            creator_id=profile.user_id, platform=profile.primary_platform
        ).exists()
    assert not PlatformStats.objects.filter(is_verified=True, last_synced_at__isnull=True).exists()
    assert PlatformStats.objects.filter(is_verified=True).exists()
    assert PlatformStats.objects.filter(is_verified=False).exists()


def models_f(name):
    from django.db.models import F

    return F(name)


# ---- speed -----------------------------------------------------------------------------------------------------


def test_list_endpoints_are_fast_with_realistic_volumes(db, debug_on, django_assert_max_num_queries):
    seed(creators=200, brands=20, campaigns=100)
    login = lambda username: _client_for(username)  # noqa: E731
    brand, creator = login("demo_brand_01"), login("demo_creator_001")
    busy = (
        Campaign.objects.exclude(status=Campaign.Status.DRAFT)
        .annotate(n=Count("proposals"))
        .order_by("-n")
        .first()
    )
    busy_client = _client_for(busy.brand.username)

    checks = [
        (brand, "/api/v1/creators/", 6),
        (creator, "/api/v1/campaigns/", 6),
        (busy_client, f"/api/v1/brand/campaigns/{busy.pk}/proposals/", 7),
        (creator, "/api/v1/creators/me/dashboard/", 12),
        (brand, "/api/v1/brands/me/dashboard/", 6),
    ]
    for client, url, budget in checks:
        with django_assert_max_num_queries(budget):
            started = time.perf_counter()
            response = client.get(url, {"page_size": 50} if "dashboard" not in url else {})
            elapsed = time.perf_counter() - started
        assert response.status_code == 200, url
        assert elapsed < 1.0, f"{url} took {elapsed:.2f}s"


def _client_for(username):
    from apps.accounts.services import issue_access_token

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {issue_access_token(User.objects.get(username=username))}")
    return client


# ---- indexes -----------------------------------------------------------------------------------------------------


def _index_columns(table):
    with connection.cursor() as cursor:
        constraints = connection.introspection.get_constraints(cursor, table)
    return [
        tuple(info["columns"])
        for info in constraints.values()
        if info["index"] or info["unique"] or info["primary_key"]
    ]


@pytest.mark.parametrize(
    "table, columns",
    [
        ("campaigns_campaign", ("status", "deadline")),
        ("campaigns_campaign", ("brand_id", "status")),
        ("proposals_proposal", ("campaign_id", "status", "created_at")),
        ("proposals_proposal", ("creator_id", "created_at")),
        ("social_platformstats", ("creator_id", "platform")),
        ("notifications_notification", ("user_id", "is_read", "created_at")),
    ],
)
def test_the_indexes_the_list_queries_rely_on_exist(db, table, columns):
    assert columns in _index_columns(table)


def test_the_verification_step_uses_a_handful_of_queries_however_many_creators_there_are(
    db, debug_on, django_assert_max_num_queries
):
    from apps.core import demo_data

    seed(creators=40, brands=3, campaigns=0)
    PlatformStats.objects.filter(platform="youtube").delete()  # force it to create the missing rows
    User.objects.filter(role=Role.BRAND).update(email_verified=False)

    with django_assert_max_num_queries(10):
        demo_data._apply_verification()

    for i in range(1, 41):
        verified = PlatformStats.objects.filter(
            creator__username=f"demo_creator_{i:03d}", platform="youtube", is_verified=True
        ).exists()
        assert verified == (i % 5 != 0), i
    assert not User.objects.filter(role=Role.BRAND, email_verified=False).exists()
    assert BrandSocialAccount.objects.count() == 3  # every demo brand has a connected platform


def test_the_verification_step_gives_the_same_youtube_numbers_every_time(db, debug_on):
    from apps.core import demo_data

    seed(creators=12, brands=1, campaigns=0)
    PlatformStats.objects.filter(platform="youtube").delete()
    demo_data._apply_verification()
    first = dict(PlatformStats.objects.filter(platform="youtube").values_list("creator__username", "followers"))
    PlatformStats.objects.filter(platform="youtube").delete()

    demo_data._apply_verification()

    second = dict(PlatformStats.objects.filter(platform="youtube").values_list("creator__username", "followers"))
    assert first == second and len(first) == 10  # 12 creators, minus demo_creator_005 and _010


def test_seeding_again_gives_brands_that_lost_their_platform_a_connected_one(db, debug_on):
    seed(creators=1, brands=2, campaigns=0)
    BrandSocialAccount.objects.all().delete()

    seed(creators=1, brands=2, campaigns=0)

    assert BrandSocialAccount.objects.filter(brand__username__startswith="demo_brand_").count() == 2
    assert not BrandSocialAccount.objects.filter(is_verified=True).exists()  # a typed link is never "Verified"
