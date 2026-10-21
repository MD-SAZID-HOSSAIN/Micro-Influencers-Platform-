"""Deterministic demo data for local development and frontend integration. Never used in production.

Every demo account is derived from its own index, so ``demo_creator_003`` is the same person
whether 10 or 1000 creators are seeded, and running the seeder again only tops up what is missing.
"""
import random
import zlib
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.hashers import make_password
from django.db.models import Q
from django.utils import timezone

from apps.accounts.models import Role, User
from apps.campaigns.models import Campaign
from apps.core.choices import Niche, Platform
from apps.profiles.models import BrandProfile, CreatorProfile, PortfolioItem
from apps.proposals.models import Proposal
from apps.social.models import BrandSocialAccount, PlatformStats

DEMO_PASSWORD = "DemoPass123!"
CREATOR_PREFIX = "demo_creator_"
BRAND_PREFIX = "demo_brand_"

FIRST_NAMES = ["Amina", "Rafi", "Nadia", "Tanvir", "Sara", "Imran", "Lina", "Farhan", "Maya", "Omar", "Priya", "Zane"]
LAST_NAMES = ["Rahman", "Khan", "Ahmed", "Hossain", "Chowdhury", "Islam", "Sharma", "Patel", "Ali", "Begum"]
PLACES = [
    ("Dhaka", "Bangladesh"),
    ("Chattogram", "Bangladesh"),
    ("Mumbai", "India"),
    ("Karachi", "Pakistan"),
    ("London", "United Kingdom"),
    ("Toronto", "Canada"),
]
COMPANIES = ["Acme Foods", "Bright Fit", "Nova Tech", "Glow Beauty", "Wander Co", "Spice Route", "Pixel Gear", "Green Fork"]
BIOS = [
    "Sharing honest reviews and everyday tips with my community.",
    "Creating short, practical content for people who like to try new things.",
    "Full-time creator. Collaborations welcome.",
]
DELIVERABLES = ["2 posts, 1 reel", "1 video review", "3 stories and 1 post", "1 dedicated video"]
COVER_MESSAGES = [
    "I think my audience is a great fit for this campaign.",
    "I have worked with similar brands and would love to collaborate.",
    "My followers engage a lot with this kind of content.",
]


def _rng(label: str) -> random.Random:
    return random.Random(label)


def _bulk_users(usernames, role, hashed_password, full_names):
    users = [
        User(
            username=username,
            email=f"{username}@demo.test",
            full_name=full_name,
            # crc32, not hash(): str hashes change between Python runs and the data must be stable.
            mobile_number="+8801" + str(zlib.crc32(username.encode()) % 10**9).zfill(9),
            role=role,
            password=hashed_password,
        )
        for username, full_name in zip(usernames, full_names)
    ]
    return User.objects.bulk_create(users)


def _seed_creators(target: int, hashed: str) -> int:
    existing = User.objects.filter(username__startswith=CREATOR_PREFIX).count()
    indexes = range(existing + 1, target + 1)
    if not indexes:
        return 0
    rngs = {i: _rng(f"creator-{i}") for i in indexes}
    names = [f"{rngs[i].choice(FIRST_NAMES)} {rngs[i].choice(LAST_NAMES)}" for i in indexes]
    users = _bulk_users([f"{CREATOR_PREFIX}{i:03d}" for i in indexes], Role.CREATOR, hashed, names)

    profiles, stats, portfolio = [], [], []
    now = timezone.now()
    for i, user in zip(indexes, users):
        rng = rngs[i]
        platform = rng.choice(Platform.values)
        city, country = rng.choice(PLACES)
        profiles.append(
            CreatorProfile(
                user=user,
                bio=rng.choice(BIOS),
                niche=rng.choice(Niche.values),
                primary_platform=platform,
                city=city,
                country=country,
                rate_post=Decimal(rng.randint(20, 400)) if rng.random() < 0.9 else None,
                rate_story=Decimal(rng.randint(10, 200)) if rng.random() < 0.6 else None,
                rate_video=Decimal(rng.randint(50, 800)) if rng.random() < 0.7 else None,
            )
        )
        # YouTube is Verified by Google sign-in (most of the demo ones). The other platforms are typed by hand, so in
        # the demo data an admin has already approved them: they show on the profile and are Verified.
        verified = platform != Platform.YOUTUBE or rng.random() < 0.8
        stats.append(
            PlatformStats(
                creator=user,
                platform=platform,
                followers=rng.randint(1_000, 100_000),
                engagement_rate=Decimal(rng.randint(80, 900)) / 100,
                is_verified=verified,
                last_synced_at=now - timedelta(hours=rng.randint(1, 48)),
            )
        )
        for n in range(rng.randint(0, 3)):
            portfolio.append(
                PortfolioItem(creator=user, url=f"https://example.com/{user.username}/work-{n + 1}", caption=f"Past work {n + 1}")
            )
    CreatorProfile.objects.bulk_create(profiles)
    PlatformStats.objects.bulk_create(stats)
    PortfolioItem.objects.bulk_create(portfolio)
    return len(indexes)


def _seed_brands(target: int, hashed: str) -> int:
    existing = User.objects.filter(username__startswith=BRAND_PREFIX).count()
    indexes = range(existing + 1, target + 1)
    if not indexes:
        return 0
    users = _bulk_users(
        [f"{BRAND_PREFIX}{i:02d}" for i in indexes],
        Role.BRAND,
        hashed,
        [f"Brand Owner {i}" for i in indexes],
    )
    BrandProfile.objects.bulk_create(
        [
            BrandProfile(
                user=user,
                company_name=f"{COMPANIES[i % len(COMPANIES)]} {i}",
                industry=_rng(f"brand-{i}").choice(["Food", "Fitness", "Tech", "Beauty", "Travel"]),
                website=f"https://brand{i}.example.com",
                about="A demo brand for local development.",
            )
            for i, user in zip(indexes, users)
        ]
    )
    return len(indexes)


def _seed_campaigns_and_proposals(target: int) -> tuple[int, int]:
    brands = list(User.objects.filter(username__startswith=BRAND_PREFIX).order_by("username"))
    creators = list(User.objects.filter(username__startswith=CREATOR_PREFIX).values_list("id", flat=True))
    existing = Campaign.objects.filter(brand__username__startswith=BRAND_PREFIX).count()
    indexes = range(existing, target)
    if not brands or not indexes:
        return 0, 0

    now = timezone.now()
    campaigns = []
    for i in indexes:
        rng = _rng(f"campaign-{i}")
        roll = rng.random()
        status = (
            Campaign.Status.DRAFT if roll < 0.15 else Campaign.Status.CLOSED if roll < 0.40 else Campaign.Status.PUBLISHED
        )
        deadline = now - timedelta(days=rng.randint(1, 30)) if status == Campaign.Status.CLOSED else now + timedelta(days=rng.randint(2, 30))
        campaigns.append(
            Campaign(
                brand=brands[i % len(brands)],
                title=f"Demo campaign {i + 1}",
                description="Tell your audience about our product in your own voice.",
                niche=rng.choice(Niche.values),
                platform=rng.choice(Platform.values),
                budget=Decimal(rng.randint(50, 1500)),
                deadline=deadline,
                deliverables=rng.choice(DELIVERABLES),
                creators_needed=rng.randint(1, 5),
                min_followers=rng.choice([None, 1_000, 5_000, 20_000]),
                allow_withdrawal=i % 4 != 3,  # every fourth demo campaign does not let creators withdraw
                status=status,
                published_at=None if status == Campaign.Status.DRAFT else now - timedelta(days=rng.randint(1, 20)),
                closed_at=deadline if status == Campaign.Status.CLOSED else None,
            )
        )
    created = Campaign.objects.bulk_create(campaigns)

    proposals = []
    for i, campaign in zip(indexes, created):
        if campaign.status == Campaign.Status.DRAFT or not creators:
            continue
        rng = _rng(f"proposals-{i}")
        accepted = 0
        for creator_id in rng.sample(creators, min(len(creators), rng.randint(3, 12))):  # one per creator
            status = rng.choices(
                [Proposal.Status.PENDING, Proposal.Status.SHORTLISTED, Proposal.Status.ACCEPTED, Proposal.Status.REJECTED, Proposal.Status.WITHDRAWN],
                weights=[40, 20, 15, 15, 10],
            )[0]
            if status == Proposal.Status.ACCEPTED:
                if accepted >= campaign.creators_needed:
                    status = Proposal.Status.SHORTLISTED
                else:
                    accepted += 1
            proposals.append(
                Proposal(
                    campaign=campaign,
                    creator_id=creator_id,
                    status=status,
                    cover_message=rng.choice(COVER_MESSAGES),
                    proposed_rate=campaign.budget,  # the rate is fixed by the brand
                    portfolio_links=[],
                    experience_note="",
                    withdrawal_reason="Schedule conflict" if status == Proposal.Status.WITHDRAWN and rng.random() < 0.5 else "",
                )
            )
    Proposal.objects.bulk_create(proposals)
    return len(created), len(proposals)


def _apply_verification() -> None:
    """Make the demo accounts follow the verification rules (and repair data seeded before them).

    Brands need a verified email and one verified platform to publish and accept (demo brands get an approved
    Instagram link). Creators need a verified email and a connected YouTube channel (Verified stats) to apply: every
    fifth demo creator (005, 010, ...) is left without a channel, so the blocked state can be tried. Demo emails end in
    @demo.test, so notification emails are switched off for them (nothing is sent to addresses that do not exist).
    Safe to repeat.
    """
    demo_users = User.objects.filter(Q(username__startswith=BRAND_PREFIX) | Q(username__startswith=CREATOR_PREFIX))
    demo_users.exclude(email_verified=True, email_notifications_enabled=False).update(
        email_verified=True, email_notifications_enabled=False
    )
    brands = list(User.objects.filter(username__startswith=BRAND_PREFIX).values_list("id", "username"))
    connected = set(
        BrandSocialAccount.objects.filter(brand_id__in=[brand_id for brand_id, _ in brands]).values_list(
            "brand_id", flat=True
        )
    )
    # In the demo data an admin has already approved the Instagram link, so the demo brands are fully verified.
    BrandSocialAccount.objects.bulk_create(
        [
            BrandSocialAccount(
                brand_id=brand_id,
                platform="instagram",
                handle_url=f"https://instagram.com/{username}",
                is_verified=True,
                review_status=BrandSocialAccount.Review.APPROVED,
            )
            for brand_id, username in brands
            if brand_id not in connected
        ]
    )
    names = dict(brands)
    seeded_but_unapproved = [  # links seeded before admin approval existed
        link.pk
        for link in BrandSocialAccount.objects.filter(
            brand_id__in=list(names), platform="instagram", is_verified=False
        ).only("id", "brand_id", "handle_url")
        if link.handle_url == f"https://instagram.com/{names[link.brand_id]}"
    ]
    BrandSocialAccount.objects.filter(pk__in=seeded_but_unapproved).update(
        is_verified=True, review_status=BrandSocialAccount.Review.APPROVED, review_note=""
    )

    now = timezone.now()
    numbers = {
        user_id: int(username.removeprefix(CREATOR_PREFIX))
        for user_id, username in User.objects.filter(username__startswith=CREATOR_PREFIX).values_list("id", "username")
    }
    without_youtube = [user_id for user_id, n in numbers.items() if n % 5 == 0]
    with_youtube = [user_id for user_id, n in numbers.items() if n % 5 != 0]
    youtube = PlatformStats.objects.filter(platform=Platform.YOUTUBE)

    # Seeded Instagram/TikTok/Facebook numbers have no typed link; they count as already approved by an admin.
    PlatformStats.objects.filter(creator_id__in=list(numbers), handle_url__isnull=True).exclude(
        platform=Platform.YOUTUBE
    ).update(is_verified=True, review_status=PlatformStats.Review.APPROVED, review_note="", updated_at=now)

    youtube.filter(creator_id__in=without_youtube, is_verified=True).update(is_verified=False, updated_at=now)
    existing = dict(youtube.filter(creator_id__in=with_youtube).values_list("creator_id", "is_verified"))
    youtube.filter(creator_id__in=[c for c, verified in existing.items() if not verified]).update(
        is_verified=True, updated_at=now
    )

    missing = []
    for user_id in with_youtube:
        if user_id in existing:
            continue
        rng = _rng(f"creator-youtube-{numbers[user_id]}")
        missing.append(
            PlatformStats(
                creator_id=user_id,
                platform=Platform.YOUTUBE,
                followers=rng.randint(1_000, 100_000),
                engagement_rate=Decimal(rng.randint(80, 900)) / 100,
                is_verified=True,
                last_synced_at=now,
            )
        )
    PlatformStats.objects.bulk_create(missing)


def seed(*, creators: int = 200, brands: int = 20, campaigns: int = 100) -> dict[str, int]:
    """Top the demo data up to the requested sizes. Returns how many of each were created."""
    hashed = make_password(DEMO_PASSWORD)
    new_creators = _seed_creators(creators, hashed)
    new_brands = _seed_brands(brands, hashed)
    _apply_verification()
    new_campaigns, new_proposals = _seed_campaigns_and_proposals(campaigns)
    return {
        "creators": new_creators,
        "brands": new_brands,
        "campaigns": new_campaigns,
        "proposals": new_proposals,
    }
