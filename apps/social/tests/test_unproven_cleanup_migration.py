"""The clean-up migration for data the removed direct-connect endpoints (and a lower minimum) left behind.

Verified must mean: proven by Google sign-in AND at least MIN_CREATOR_FOLLOWERS subscribers. The migration takes the
Verified flag away from everything that does not meet that, once, when it is applied.
"""
import importlib

from django.apps import apps as django_apps
from django.utils import timezone

from apps.accounts.models import Role
from apps.accounts.tests.factories import UserFactory
from apps.social.crypto import encrypt
from apps.social.models import PlatformStats, YouTubeConnection
from apps.social.tests.fakes import make_connection

migration = importlib.import_module("apps.social.migrations.0004_unverify_unproven_stats")


def stats(creator, platform, followers, verified):
    return PlatformStats.objects.create(
        creator=creator, platform=platform, followers=followers, engagement_rate="2.00", is_verified=verified
    )


def run():
    migration.unverify_unproven_stats(django_apps, None)


def creator():
    return UserFactory(role=Role.CREATOR)


def test_verified_flags_on_instagram_tiktok_and_facebook_are_removed(db):
    person = creator()
    flags = {p: stats(person, p, 50_000, True) for p in ("instagram", "tiktok", "facebook")}

    run()

    assert not PlatformStats.objects.filter(creator=person, is_verified=True).exists()
    assert all(PlatformStats.objects.get(pk=s.pk).followers == 50_000 for s in flags.values())  # numbers stay


def test_a_channel_linked_by_handle_with_placeholder_tokens_is_unverified_and_unlinked(db):
    person = creator()
    stats(person, "youtube", 80_000, True)
    YouTubeConnection.objects.create(
        creator=person,
        access_token_enc=encrypt("direct-token"),
        refresh_token_enc=encrypt("direct-refresh"),
        access_expires_at=timezone.now(),
    )

    run()

    assert PlatformStats.objects.get(creator=person, platform="youtube").is_verified is False
    assert not YouTubeConnection.objects.filter(creator=person).exists()


def test_the_plain_text_placeholder_used_without_an_encryption_key_is_also_caught(db):
    person = creator()
    stats(person, "youtube", 80_000, True)
    YouTubeConnection.objects.create(
        creator=person,
        access_token_enc="direct-token-plain",
        refresh_token_enc="direct-refresh-plain",
        access_expires_at=timezone.now(),
    )

    run()

    assert PlatformStats.objects.get(creator=person, platform="youtube").is_verified is False
    assert not YouTubeConnection.objects.filter(creator=person).exists()


def test_a_real_google_connection_with_enough_subscribers_is_left_alone(db):
    person = creator()
    make_connection(person, followers=5_000)

    run()

    assert PlatformStats.objects.get(creator=person, platform="youtube").is_verified is True
    assert YouTubeConnection.objects.filter(creator=person).exists()


def test_a_verified_channel_below_the_minimum_loses_verified_but_keeps_its_connection(db):
    person = creator()
    make_connection(person, followers=600)

    run()

    assert PlatformStats.objects.get(creator=person, platform="youtube").is_verified is False
    assert YouTubeConnection.objects.filter(creator=person).exists()


def test_seeded_demo_style_stats_without_a_connection_are_left_alone(db):
    person = creator()
    stats(person, "youtube", 30_000, True)  # the demo seeder creates Verified YouTube stats with no connection

    run()

    assert PlatformStats.objects.get(creator=person, platform="youtube").is_verified is True


def test_running_it_twice_changes_nothing_more(db):
    person = creator()
    stats(person, "instagram", 10_000, True)
    run()

    run()

    assert not PlatformStats.objects.filter(is_verified=True).exists()
