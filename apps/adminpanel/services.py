"""Admin operations (FR-22). Every state change writes an AdminActionLog row in the same transaction."""
from datetime import timedelta

from django.db import transaction
from django.db.models import Count, F, Q
from django.db.models.functions import TruncDate
from django.utils import timezone
from rest_framework.exceptions import NotFound

from apps.accounts.models import Role, User
from apps.campaigns.models import Campaign
from apps.campaigns.services import close_campaign
from apps.core.exceptions import Conflict
from apps.proposals.models import Proposal
from apps.reviews.models import Review
from apps.reviews.services import recalculate_rating
from apps.social.models import BrandSocialAccount, PlatformStats

from .models import AdminActionLog

SIGNUP_DAYS = 30


class CannotModifySelf(Conflict):
    default_code = "cannot_modify_self"
    default_detail = "Admins cannot suspend or delete their own account."


class AlreadySuspended(Conflict):
    default_code = "already_suspended"
    default_detail = "This account is already suspended."


class AlreadyActive(Conflict):
    default_code = "already_active"
    default_detail = "This account is not suspended."


def _log(admin: User, action: str, target_type: str, target_id: int, target_label: str, reason: str) -> None:
    AdminActionLog.objects.create(
        admin=admin,
        admin_label=admin.username,
        action=action,
        target_type=target_type,
        target_id=target_id,
        target_label=target_label[:200],
        reason=reason,
    )


def _target_user(admin: User, user_id: int) -> User:
    target = User.objects.select_for_update().filter(pk=user_id).first()
    if target is None:
        raise NotFound("User not found.")
    if target.pk == admin.pk:
        raise CannotModifySelf()
    return target


def suspend_user(*, admin: User, user_id: int, reason: str) -> User:
    """Block login and invalidate the account's tokens at once."""
    with transaction.atomic():
        target = _target_user(admin, user_id)
        if not target.is_active:
            raise AlreadySuspended()
        target.is_active = False
        target.token_version = F("token_version") + 1
        target.save(update_fields=["is_active", "token_version"])
        target.refresh_from_db()
        _log(admin, "user.suspend", "user", target.pk, target.username, reason)
    return target


def reactivate_user(*, admin: User, user_id: int, reason: str) -> User:
    with transaction.atomic():
        target = _target_user(admin, user_id)
        if target.is_active:
            raise AlreadyActive()
        target.is_active = True
        target.save(update_fields=["is_active"])
        _log(admin, "user.reactivate", "user", target.pk, target.username, reason)
    return target


def delete_user(*, admin: User, user_id: int, reason: str) -> None:
    """Delete an account and everything it owns. Ratings the account had given are recalculated."""
    with transaction.atomic():
        target = _target_user(admin, user_id)
        rated_creators = list(
            Review.objects.filter(brand=target).values_list("creator_id", flat=True).distinct()
        )
        _log(admin, "user.delete", "user", target.pk, target.username, reason)  # before the row is gone
        target.delete()
        for creator_id in rated_creators:
            recalculate_rating(creator_id)


def close_campaign_as_admin(*, admin: User, campaign_id: int, reason: str) -> Campaign:
    """Close a Published campaign. Closing one that is already Closed does nothing and logs nothing."""
    with transaction.atomic():
        campaign = Campaign.objects.filter(pk=campaign_id).first()
        if campaign is None:
            raise NotFound("Campaign not found.")
        if campaign.status == Campaign.Status.CLOSED:
            return campaign
        close_campaign(campaign)  # a Draft raises invalid_campaign_transition
        _log(admin, "campaign.close", "campaign", campaign.pk, campaign.title, reason)
    return campaign


def remove_review(*, admin: User, review_id: int, reason: str) -> None:
    """Delete an inappropriate review and recalculate the creator's rating."""
    with transaction.atomic():
        review = Review.objects.select_related("brand").filter(pk=review_id).first()
        if review is None:
            raise NotFound("Review not found.")
        creator_id = review.creator_id
        _log(admin, "review.remove", "review", review.pk, f"by {review.brand.username}", reason)
        review.delete()
        recalculate_rating(creator_id)


def _typed_stats(stats_id: int) -> PlatformStats:
    """Only Instagram, TikTok and Facebook numbers are reviewed: YouTube is proven by Google sign-in."""
    stats = (
        PlatformStats.objects.select_for_update(of=("self",))
        .select_related("creator")
        .filter(pk=stats_id)
        .exclude(platform="youtube")
        .first()
    )
    if stats is None:
        raise NotFound("Platform stats not found.")
    return stats


def approve_platform_stats(*, admin: User, stats_id: int, reason: str = "") -> PlatformStats:
    """Mark a creator's typed numbers Verified: from now on they show on the creator's profile."""
    with transaction.atomic():
        stats = _typed_stats(stats_id)
        stats.is_verified = True
        stats.review_status = PlatformStats.Review.APPROVED
        stats.review_note = ""
        stats.save(update_fields=["is_verified", "review_status", "review_note", "updated_at"])
        label = f"{stats.creator.username} {stats.platform}"
        _log(admin, "stats.approve", "platform_stats", stats.pk, label, reason or "Checked the profile link.")
    return stats


def reject_platform_stats(*, admin: User, stats_id: int, reason: str) -> PlatformStats:
    """Turn typed numbers down (or take back an approval). They are hidden and the creator sees the reason."""
    with transaction.atomic():
        stats = _typed_stats(stats_id)
        stats.is_verified = False
        stats.review_status = PlatformStats.Review.REJECTED
        stats.review_note = reason
        stats.save(update_fields=["is_verified", "review_status", "review_note", "updated_at"])
        label = f"{stats.creator.username} {stats.platform}"
        _log(admin, "stats.reject", "platform_stats", stats.pk, label, reason)
    return stats


def _typed_brand_platform(account_id: int) -> BrandSocialAccount:
    """Only typed Instagram, TikTok and Facebook links are reviewed: YouTube is proven by Google sign-in."""
    account = (
        BrandSocialAccount.objects.select_for_update(of=("self",))
        .select_related("brand")
        .filter(pk=account_id)
        .exclude(platform="youtube")
        .first()
    )
    if account is None:
        raise NotFound("Brand platform not found.")
    return account


def approve_brand_platform(*, admin: User, account_id: int, reason: str = "") -> BrandSocialAccount:
    """The link is the brand's official page: it now counts towards verifying the brand."""
    with transaction.atomic():
        account = _typed_brand_platform(account_id)
        account.is_verified = True
        account.review_status = BrandSocialAccount.Review.APPROVED
        account.review_note = ""
        account.save(update_fields=["is_verified", "review_status", "review_note"])
        label = f"{account.brand.username} {account.platform}"
        _log(admin, "brand_platform.approve", "brand_platform", account.pk, label, reason or "Checked the page.")
    return account


def reject_brand_platform(*, admin: User, account_id: int, reason: str) -> BrandSocialAccount:
    """Turn a link down (or take back an approval). The brand sees the reason."""
    with transaction.atomic():
        account = _typed_brand_platform(account_id)
        account.is_verified = False
        account.review_status = BrandSocialAccount.Review.REJECTED
        account.review_note = reason
        account.save(update_fields=["is_verified", "review_status", "review_note"])
        label = f"{account.brand.username} {account.platform}"
        _log(admin, "brand_platform.reject", "brand_platform", account.pk, label, reason)
    return account


def overview() -> dict:
    """Headline numbers for the admin dashboard."""
    totals = User.objects.aggregate(
        total=Count("id"),
        suspended=Count("id", filter=Q(is_active=False)),
        **{role.value: Count("id", filter=Q(role=role)) for role in Role},
    )
    today = timezone.now().date()
    first_day = today - timedelta(days=SIGNUP_DAYS - 1)
    per_day = {
        row["day"]: row["n"]
        for row in User.objects.filter(date_joined__date__gte=first_day)
        .annotate(day=TruncDate("date_joined"))
        .values("day")
        .annotate(n=Count("id"))
    }
    by_status = dict(
        Campaign.objects.values_list("status").annotate(n=Count("id")).order_by()
    )
    return {
        "users": {
            "total": totals["total"],
            "suspended": totals["suspended"],
            "by_role": {role.value: totals[role.value] for role in Role},
        },
        "signups": [
            {"date": (first_day + timedelta(days=i)).isoformat(), "count": per_day.get(first_day + timedelta(days=i), 0)}
            for i in range(SIGNUP_DAYS)
        ],
        "campaigns_by_status": {status.value: by_status.get(status.value, 0) for status in Campaign.Status},
        "total_proposals": Proposal.objects.count(),
    }
