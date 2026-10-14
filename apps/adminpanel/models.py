from django.conf import settings
from django.db import models


class AdminActionLog(models.Model):
    """Who did what to which record, and why. Entries outlive both the admin and the target."""

    # SET_NULL + a text label: deleting an admin or the target must not erase the audit trail.
    admin = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="admin_actions"
    )
    admin_label = models.CharField(max_length=150)
    action = models.CharField(max_length=40)  # e.g. "user.suspend", "campaign.close"
    target_type = models.CharField(max_length=20)
    target_id = models.BigIntegerField()
    target_label = models.CharField(max_length=200, blank=True, default="")
    reason = models.CharField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["-created_at"])]

    def __str__(self):
        return f"{self.action} {self.target_type}:{self.target_id} by {self.admin_label}"
