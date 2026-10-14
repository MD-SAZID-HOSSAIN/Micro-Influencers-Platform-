from django.conf import settings
from django.db import models


class Kind(models.TextChoices):
    PROPOSAL_SHORTLISTED = "proposal_shortlisted", "Proposal shortlisted"
    PROPOSAL_ACCEPTED = "proposal_accepted", "Proposal accepted"
    PROPOSAL_REJECTED = "proposal_rejected", "Proposal rejected"
    ACCOUNT_RECONNECT = "account_reconnect", "Account needs reconnecting"
    PROPOSAL_RECEIVED = "proposal_received", "New proposal received"
    PROPOSAL_WITHDRAWN = "proposal_withdrawn", "Proposal withdrawn"
    CAMPAIGN_AUTO_CLOSED = "campaign_auto_closed", "Campaign closed at deadline"


class Notification(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications"
    )
    kind = models.CharField(max_length=30, choices=Kind.choices)
    message = models.CharField(max_length=255)
    # IDs the frontend needs to link to the right page, e.g. {"campaign_id": 3}.
    payload = models.JSONField(default=dict, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["user", "is_read", "-created_at"])]
