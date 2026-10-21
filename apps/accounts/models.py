from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import F
from django.db.models.functions import Lower


class Role(models.TextChoices):
    CREATOR = "creator", "Creator"
    BRAND = "brand", "Brand"
    ADMIN = "admin", "Admin"


class User(AbstractUser):
    email = models.EmailField()
    full_name = models.CharField(max_length=150)
    mobile_number = models.CharField(max_length=20)
    role = models.CharField(max_length=10, choices=Role.choices)
    # Bumped on logout and password reset; JWTs carrying an older value are rejected.
    token_version = models.PositiveIntegerField(default=0)

    def set_password(self, raw_password):
        """Changing a password also ends every login made with the old one (so an old or stolen login stops working)."""
        super().set_password(raw_password)
        if self.pk is not None:  # saved straight away, so it holds even when the caller saves only some fields
            type(self).objects.filter(pk=self.pk).update(token_version=F("token_version") + 1)
            self.token_version = (self.token_version or 0) + 1
    # Logging in never requires a verified email; only notification emails do.
    email_verified = models.BooleanField(default=False)
    email_notifications_enabled = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(Lower("email"), name="uniq_user_email_ci"),
            models.UniqueConstraint(Lower("username"), name="uniq_user_username_ci"),
        ]


class CodePurpose(models.TextChoices):
    PASSWORD_RESET = "password_reset", "Password reset"
    EMAIL_VERIFICATION = "email_verification", "Email verification"


class OneTimeCode(models.Model):
    """A short-lived, single-use 6-digit code. Only a keyed hash of the code is stored."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="one_time_codes")
    purpose = models.CharField(max_length=20, choices=CodePurpose.choices)
    code_hash = models.CharField(max_length=64)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["user", "purpose", "-created_at"])]
