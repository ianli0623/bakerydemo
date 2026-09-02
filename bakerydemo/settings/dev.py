from .base import *  # noqa: F403

DEBUG = True

ACCOUNT_SECURITY_ENFORCE_PRODUCTION_CHECKS = False
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# WAGTAILADMIN_BASE_URL required for notification emails
WAGTAILADMIN_BASE_URL = "http://localhost:8000"

ALLOWED_HOSTS = ["*"]

try:
    from .local import *  # noqa
except ImportError:
    pass
