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
