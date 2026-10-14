from getpass import getpass

from django.contrib.auth.validators import UnicodeUsernameValidator
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_email

from apps.accounts.models import Role, User

MIN_PASSWORD_LENGTH = 8


class Command(BaseCommand):
    help = (
        "Create an admin account. Admins cannot register through the API. "
        "The password is prompted for and is never accepted as an argument."
    )

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True)
        parser.add_argument("--username", required=True)
        parser.add_argument("--full-name", default="")

    def handle(self, *args, **options):
        email = options["email"].strip().lower()
        username = options["username"].strip()
        try:
            validate_email(email)
        except ValidationError:
            raise CommandError(f"{options['email']!r} is not a valid email address.")
        try:
            UnicodeUsernameValidator()(username)
        except ValidationError:
            raise CommandError(f"{username!r} is not a valid username.")
        if User.objects.filter(email__iexact=email).exists() or User.objects.filter(
            username__iexact=username
        ).exists():
            raise CommandError("An account with that email or username already exists.")

        password = getpass("Password: ")
        if len(password) < MIN_PASSWORD_LENGTH:
            raise CommandError(f"The password must be at least {MIN_PASSWORD_LENGTH} characters.")
        if password != getpass("Password (again): "):
            raise CommandError("The passwords do not match.")

        User.objects.create_user(
            username=username,
            email=email,
            password=password,
            full_name=options["full_name"] or username,
            mobile_number="",
            role=Role.ADMIN,
        )
        self.stdout.write(self.style.SUCCESS(f"Admin '{username}' created. Log in through the admin panel."))
