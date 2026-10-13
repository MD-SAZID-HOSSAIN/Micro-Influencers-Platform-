from django.contrib.auth.models import AbstractUser
from django.db import models
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
