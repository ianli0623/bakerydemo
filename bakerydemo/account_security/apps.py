from django.apps import AppConfig


class AccountSecurityConfig(AppConfig):
    default_auto_field = "django.db.models.AutoField"
    name = "bakerydemo.account_security"
    verbose_name = "Account security"

    def ready(self):
        from django.contrib import admin

        from .forms import SecurityAdminAuthenticationForm

        admin.site.login_form = SecurityAdminAuthenticationForm

        from . import signals  # noqa: F401
