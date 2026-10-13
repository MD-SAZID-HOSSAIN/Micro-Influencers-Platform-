from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.core.choices import Platform


class Proposal(models.Model):
    """A creator's application to a campaign. Lightweight: status updates only, no messaging."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SHORTLISTED = "shortlisted", "Shortlisted"
        ACCEPTED = "accepted", "Accepted"
        REJECTED = "rejected", "Rejected"
        WITHDRAWN = "withdrawn", "Withdrawn"

    campaign = models.ForeignKey(
        "campaigns.Campaign", on_delete=models.CASCADE, related_name="proposals"
    )
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="proposals"
    )
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    cover_message = models.TextField()
    proposed_rate = models.DecimalField(max_digits=10, decimal_places=2)
    portfolio_links = models.JSONField(default=list, blank=True)  # up to 3 URLs
    experience_note = models.TextField(blank=True, default="")
    withdrawal_reason = models.CharField(max_length=300, blank=True, default="")
    # Set when the brand marks the collaboration Completed: final, and unlocks the review.
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            # A creator may have many Withdrawn/Rejected rows per campaign, but only one live one.
            models.UniqueConstraint(
                fields=["campaign", "creator"],
                condition=Q(status__in=["pending", "shortlisted", "accepted"]),
                name="uniq_active_proposal_per_creator_campaign",
            )
        ]
        indexes = [
            models.Index(fields=["campaign", "status", "-created_at"]),
            models.Index(fields=["creator", "-created_at"]),
        ]

    def __str__(self):
        return f"Proposal({self.pk}, campaign={self.campaign_id}, {self.status})"


class Deliverable(models.Model):
    """A link to published content that an accepted creator delivered for a campaign."""

    proposal = models.ForeignKey(Proposal, on_delete=models.CASCADE, related_name="deliverables")
    post_url = models.URLField(max_length=500)
    platform = models.CharField(max_length=20, choices=Platform.choices)
    note = models.CharField(max_length=500, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self):
        return f"Deliverable({self.pk}, proposal={self.proposal_id})"


ACTIVE_STATUSES = (
    Proposal.Status.PENDING,
    Proposal.Status.SHORTLISTED,
    Proposal.Status.ACCEPTED,
)
