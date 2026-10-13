import factory

from apps.accounts.models import Role, User

DEFAULT_PASSWORD = "S3curePass!"


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User
        skip_postgeneration_save = True

    username = factory.Sequence(lambda n: f"user{n}")
    email = factory.LazyAttribute(lambda o: f"{o.username}@example.com")
    full_name = factory.Sequence(lambda n: f"Test User {n}")
    mobile_number = "+8801712345678"
    role = Role.CREATOR

    @factory.post_generation
    def password(self, create, extracted, **kwargs):
        self.set_password(extracted or DEFAULT_PASSWORD)
        if create:
            self.save(update_fields=["password"])
