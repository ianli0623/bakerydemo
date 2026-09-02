from urllib.parse import urlparse

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.checks import Error, Tags, register
from django.core.exceptions import ValidationError


@register(Tags.security, deploy=True)
def check_account_security_settings(app_configs, **kwargs):
    if not getattr(
        settings,
        "ACCOUNT_SECURITY_ENFORCE_PRODUCTION_CHECKS",
        False,
    ):
        return []

    errors = []
    admin_password = getattr(settings, "ADMIN_PASSWORD", "")
    try:
        validate_password(admin_password)
    except ValidationError:
        errors.append(
            Error(
                "ADMIN_PASSWORD is missing or does not satisfy password policy.",
                id="account_security.E001",
            )
        )

    secure_transport = (
        settings.SECURE_SSL_REDIRECT
        and settings.SESSION_COOKIE_SECURE
        and settings.CSRF_COOKIE_SECURE
        and settings.SECURE_HSTS_SECONDS > 0
    )
    if not secure_transport:
        errors.append(
            Error(
                "Production admin login requires HTTPS, HSTS, and secure cookies.",
                id="account_security.E002",
            )
        )

    admin_url = urlparse(getattr(settings, "WAGTAILADMIN_BASE_URL", ""))
    if admin_url.scheme != "https" or not admin_url.netloc:
        errors.append(
            Error(
                "WAGTAILADMIN_BASE_URL must use https in production.",
                id="account_security.E003",
            )
        )

    return errors
