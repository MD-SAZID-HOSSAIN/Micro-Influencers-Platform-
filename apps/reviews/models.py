from django.conf import settings
from django.db import models
from django.db.models import Q


class Review(models.Model):
    """A brand's rating of a creator after a completed collaboration. Written once, never edited."""

    proposal = models.OneToOneField(
        "proposals.Proposal", on_delete=models.CASCADE, related_name="review"
    )
    brand = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reviews_written"
    )
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reviews_received"
    )
    rating = models.PositiveSmallIntegerField()
    text = models.CharField(max_length=500, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.CheckConstraint(condition=Q(rating__gte=1, rating__lte=5), name="review_rating_1_5")
        ]
        indexes = [models.Index(fields=["creator", "-created_at"])]

    def __str__(self):
        return f"Review({self.pk}, creator={self.creator_id}, {self.rating}/5)"
