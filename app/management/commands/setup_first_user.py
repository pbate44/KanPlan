import os
import sys

from django.contrib.auth import get_user_model
from django.core.management import BaseCommand, call_command


class Command(BaseCommand):
    help = "Offer to create an account if none exist yet (used by the start scripts and Docker)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--from-env",
            action="store_true",
            help="Don't prompt; create the account from DJANGO_SUPERUSER_USERNAME/PASSWORD if set.",
        )

    def handle(self, *args, from_env=False, **options):
        if get_user_model().objects.exists():
            return

        if from_env:
            username = os.environ.get("DJANGO_SUPERUSER_USERNAME")
            if username and os.environ.get("DJANGO_SUPERUSER_PASSWORD"):
                # createsuperuser reads the password from the environment itself.
                call_command(
                    "createsuperuser",
                    interactive=False,
                    username=username,
                    email=os.environ.get("DJANGO_SUPERUSER_EMAIL", ""),
                )
                self.stdout.write(f"Created account '{username}'.")
            return

        if not sys.stdin.isatty():
            return

        self.stdout.write("\nNo accounts exist yet.")
        answer = input("Create one now? [Y/n] ").strip().lower()
        if answer.startswith("n"):
            self.stdout.write("Skipped. You can sign up from the login page instead.\n")
            return

        try:
            call_command("createsuperuser")
        except (SystemExit, KeyboardInterrupt):
            self.stdout.write("\nSkipped. You can sign up from the login page instead.\n")
