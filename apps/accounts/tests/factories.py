import factory

from apps.accounts.models import Role, User

DEFAULT_PASSWORD = "S3curePass!"


class UserFactory(factory.django.DjangoModelFactory):
    """Brands start with a verified email (so they can publish and accept); creators start unverified.

    Pass ``youtube_verified=True`` for a creator who may apply (a connected YouTube channel).
    """

    class Meta:
        model = User
        skip_postgeneration_save = True

    username = factory.Sequence(lambda n: f"user{n}")
    email = factory.LazyAttribute(lambda o: f"{o.username}@example.com")
    full_name = factory.Sequence(lambda n: f"Test User {n}")
    mobile_number = "+8801712345678"
    role = Role.CREATOR
    email_verified = factory.LazyAttribute(lambda o: o.role == Role.BRAND)

    @factory.post_generation
    def password(self, create, extracted, **kwargs):
        self.set_password(extracted or DEFAULT_PASSWORD)
        if create:
            self.save(update_fields=["password"])

    @factory.post_generation
    def platform_connected(self, create, extracted, **kwargs):
        """Brands start with one connected platform (so they can publish and accept); pass False for none."""
        connected = extracted if extracted is not None else self.role == Role.BRAND
        if create and connected:
            from apps.social.models import BrandSocialAccount

            BrandSocialAccount.objects.create(
                brand=self, platform="instagram", handle_url=f"https://instagram.com/{self.username}"
            )

    @factory.post_generation
    def youtube_verified(self, create, extracted, **kwargs):
        if create and extracted:
            from apps.social.models import PlatformStats

            PlatformStats.objects.create(
                creator=self,
                platform="youtube",
                followers=10_000,
                engagement_rate="4.50",
                is_verified=True,
            )
