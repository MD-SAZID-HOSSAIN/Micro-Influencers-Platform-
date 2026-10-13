from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from apps.core.choices import Niche, Platform


def _rate_field():
    return models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )


class CreatorProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="creator_profile"
    )
    photo_url = models.URLField(max_length=500, null=True, blank=True)
    bio = models.TextField(blank=True, default="")
    niche = models.CharField(max_length=20, choices=Niche.choices, null=True, blank=True)
    primary_platform = models.CharField(
        max_length=20, choices=Platform.choices, null=True, blank=True
    )
    city = models.CharField(max_length=100, blank=True, default="")
    country = models.CharField(max_length=100, blank=True, default="")
    rate_post = _rate_field()
    rate_story = _rate_field()
    rate_video = _rate_field()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"CreatorProfile({self.user_id})"


class PortfolioItem(models.Model):
    """A link to previous work (external URL only; no uploads)."""

    class Source(models.TextChoices):
        MANUAL = "manual", "Manual"
        YOUTUBE = "youtube", "YouTube"

    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="portfolio_items"
    )
    url = models.URLField(max_length=500)
    caption = models.CharField(max_length=200, blank=True, default="")
    source = models.CharField(max_length=10, choices=Source.choices, default=Source.MANUAL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]


class BrandProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="brand_profile"
    )
    company_name = models.CharField(max_length=150, blank=True, default="")
    industry = models.CharField(max_length=100, blank=True, default="")
    website = models.URLField(max_length=500, null=True, blank=True)
    logo_url = models.URLField(max_length=500, null=True, blank=True)
    about = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def display_name(self) -> str:
        """Company name, or the account holder's name until the company name is filled in."""
        return self.company_name or self.user.full_name

    def __str__(self):
        return f"BrandProfile({self.user_id})"
