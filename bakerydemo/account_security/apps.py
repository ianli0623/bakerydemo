from django.apps import AppConfig


class AccountSecurityConfig(AppConfig):
    default_auto_field = "django.db.models.AutoField"
    name = "bakerydemo.account_security"
    verbose_name = "Account security"

    def ready(self):
        from . import signals  # noqa: F401
