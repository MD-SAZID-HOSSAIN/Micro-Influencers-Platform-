from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.accounts.models import Role

from .models import BrandProfile, CreatorProfile


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_profile_for_new_user(sender, instance, created, **kwargs):
    if not created:
        return
    if instance.role == Role.CREATOR:
        CreatorProfile.objects.get_or_create(user=instance)
    elif instance.role == Role.BRAND:
        BrandProfile.objects.get_or_create(user=instance)
