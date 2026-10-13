from django.db import models


class Platform(models.TextChoices):
    INSTAGRAM = "instagram", "Instagram"
    YOUTUBE = "youtube", "YouTube"
    TIKTOK = "tiktok", "TikTok"
    FACEBOOK = "facebook", "Facebook"


class Niche(models.TextChoices):
    FITNESS = "fitness", "Fitness"
    TECH = "tech", "Tech"
    BEAUTY = "beauty", "Beauty"
    FOOD = "food", "Food"
    TRAVEL = "travel", "Travel"
    OTHER = "other", "Other"
