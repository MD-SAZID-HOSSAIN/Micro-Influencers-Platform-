from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.core.demo_data import BRAND_PREFIX, CREATOR_PREFIX, DEMO_PASSWORD, seed


class Command(BaseCommand):
    help = (
        "Create deterministic demo creators, brands, campaigns and proposals for local development. "
        "Safe to run repeatedly: it only adds what is missing. Refuses to run unless DEBUG is on."
    )

    def add_arguments(self, parser):
        parser.add_argument("--creators", type=int, default=200)
        parser.add_argument("--brands", type=int, default=20)
        parser.add_argument("--campaigns", type=int, default=100)

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("seed_demo creates accounts with a public password, so it only runs when DEBUG is on.")
        created = seed(
            creators=options["creators"], brands=options["brands"], campaigns=options["campaigns"]
        )
        summary = ", ".join(f"{count} {name}" for name, count in created.items())
        self.stdout.write(self.style.SUCCESS(f"Created {summary}."))
        self.stdout.write(
            f"Log in as {CREATOR_PREFIX}001 or {BRAND_PREFIX}01 with password {DEMO_PASSWORD}"
        )
