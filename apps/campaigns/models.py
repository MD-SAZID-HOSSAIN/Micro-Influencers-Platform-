from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.core.choices import Niche, Platform

MAX_CREATORS_NEEDED = 20


class Campaign(models.Model):
    """A brand's job listing. Lifecycle: Draft -> Published -> Closed (never reopened)."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        CLOSED = "closed", "Closed"

    brand = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="campaigns"
    )
    title = models.CharField(max_length=200)
    description = models.TextField()
    niche = models.CharField(max_length=20, choices=Niche.choices)
    platform = models.CharField(max_length=20, choices=Platform.choices)
    budget = models.DecimalField(max_digits=10, decimal_places=2)  # per creator
    deadline = models.DateTimeField()  # application deadline
    deliverables = models.TextField()  # per creator, e.g. "2 Instagram posts, 1 reel"
    creators_needed = models.PositiveSmallIntegerField(default=1)
    min_followers = models.PositiveIntegerField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    published_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(creators_needed__gte=1, creators_needed__lte=MAX_CREATORS_NEEDED),
                name="campaign_creators_needed_1_20",
            ),
            models.CheckConstraint(condition=Q(budget__gt=0), name="campaign_budget_positive"),
        ]
        indexes = [
            models.Index(fields=["status", "deadline"]),
            models.Index(fields=["brand", "status"]),
        ]

    def __str__(self):
        return f"Campaign({self.pk}, {self.title!r}, {self.status})"
