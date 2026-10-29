from django.apps import AppConfig


class AccountSecurityConfig(AppConfig):
    default_auto_field = "django.db.models.AutoField"
    name = "bakerydemo.account_security"
    verbose_name = "Account security"

    def ready(self):
        from django.contrib import admin

        from .csp import install_wagtail_chooser_nonce
        from .forms import SecurityAdminAuthenticationForm

        admin.site.login_form = SecurityAdminAuthenticationForm
        install_wagtail_chooser_nonce()

        from . import checks, signals  # noqa: F401
