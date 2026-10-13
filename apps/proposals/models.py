from django.conf import settings
from django.db import models
from django.db.models import Q


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


ACTIVE_STATUSES = (
    Proposal.Status.PENDING,
    Proposal.Status.SHORTLISTED,
    Proposal.Status.ACCEPTED,
)
