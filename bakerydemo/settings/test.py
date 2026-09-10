from .base import *  # noqa
from .base import STORAGES
# #############
# General

ALLOWED_HOSTS = ["*"]

# Don't redirect to HTTPS in tests or send the HSTS header
ACCOUNT_SECURITY_ENFORCE_PRODUCTION_CHECKS = False
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_HSTS_SECONDS = 0

STORAGES["staticfiles"]["BACKEND"] = (
    "django.contrib.staticfiles.storage.StaticFilesStorage"
)

# Use local memory caching instead of redis when testing locally
# to prevent caching shenanigans
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

# Wagtail
WAGTAILADMIN_BASE_URL = "http://localhost:8000"

# Task queue configuration to ensure tasks run immediately in the test environment
# https://docs.wagtail.org/en/stable/releases/6.4.html#background-tasks-run-at-end-of-current-transaction
TASKS = {
    "default": {
        "BACKEND": "django_tasks.backends.immediate.ImmediateBackend",
        "ENQUEUE_ON_COMMIT": False,
    }
}

# #############
# Performance

# By default, Django uses a computationally difficult algorithm for passwords hashing.
# We don't need such a strong algorithm in tests, so use MD5
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
