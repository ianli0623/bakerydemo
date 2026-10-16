from getpass import getpass

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from bakerydemo.account_security.services import set_user_password


class Command(BaseCommand):
    help = "Interactively reset the demo admin password."

    def handle(self, **options):
        User = get_user_model()
        try:
            admin_user = User.objects.get(username="admin")
        except User.DoesNotExist as err:
            raise CommandError("Cannot find admin user.") from err

        try:
            password = getpass("New admin password: ")
            confirmation = getpass("New admin password (again): ")
        except (EOFError, KeyboardInterrupt) as err:
            raise CommandError("Password entry was cancelled.") from err

        if password != confirmation:
            raise CommandError("The entered passwords do not match.")

        try:
            set_user_password(
                admin_user,
                password,
                must_change_password=True,
            )
        except ValidationError as err:
            raise CommandError(
                "The entered admin password does not satisfy password policy."
            ) from err

        self.stdout.write(
            self.style.SUCCESS(
                "Admin password reset. The user must change it after signing in."
            )
        )
