from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from bakerydemo.account_security.services import set_user_password


class Command(BaseCommand):
    def handle(self, **options):
        User = get_user_model()
        try:
            admin_user = User.objects.get(username="admin")
        except User.DoesNotExist as err:
            raise CommandError("Cannot find admin user.") from err

        try:
            set_user_password(
                admin_user,
                settings.ADMIN_PASSWORD,
                must_change_password=True,
            )
        except ValidationError as err:
            raise CommandError(
                "The configured admin password does not satisfy password policy."
            ) from err
