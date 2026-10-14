from decimal import ROUND_HALF_UP, Decimal

from django.db import IntegrityError, transaction
from django.db.models import Avg, Count

from apps.accounts.models import User
from apps.core.exceptions import Conflict
from apps.profiles.models import CreatorProfile
from apps.proposals.services import _lock_for_brand

from .models import Review


class NotCompleted(Conflict):
    default_code = "not_completed"
    default_detail = "You can review a creator once the collaboration is marked Completed."


class AlreadyReviewed(Conflict):
    default_code = "already_reviewed"
    default_detail = "This collaboration has already been reviewed."


def recalculate_rating(creator_id: int) -> None:
    """Recompute a creator's average rating and review count from their reviews.

    The creator's profile row is locked first, so simultaneous reviews (or an admin removing
    one) are counted one at a time and the stored figures never go stale.
    """
    with transaction.atomic():
        profile = CreatorProfile.objects.select_for_update().filter(user_id=creator_id).first()
        if profile is None:
            return
        totals = Review.objects.filter(creator_id=creator_id).aggregate(
            average=Avg("rating"), count=Count("id")
        )
        profile.rating_count = totals["count"]
        profile.rating_avg = (
            Decimal(str(totals["average"])).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            if totals["count"]
            else None
        )
        profile.save(update_fields=["rating_avg", "rating_count"])


def create_review(*, brand: User, proposal_id: int, rating: int, text: str = "") -> Review:
    """Rate the creator of a Completed collaboration. One review each; not editable afterwards."""
    with transaction.atomic():
        _, proposal = _lock_for_brand(brand, proposal_id)  # another brand's proposal is a 404
        if proposal.completed_at is None:
            raise NotCompleted()
        if Review.objects.filter(proposal=proposal).exists():
            raise AlreadyReviewed()
        try:
            with transaction.atomic():  # savepoint
                review = Review.objects.create(
                    proposal=proposal,
                    brand=brand,
                    creator_id=proposal.creator_id,
                    rating=rating,
                    text=text,
                )
        except IntegrityError:
            raise AlreadyReviewed()
        recalculate_rating(proposal.creator_id)
    return review
