import re
from urllib.parse import urlparse

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.checks import Error, Tags, register
from django.core.exceptions import ValidationError


def _valid_rp_id(value):
    labels = value.split(".")
    return bool(labels) and all(
        re.fullmatch(
            r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?",
            label,
        )
        for label in labels
    )


def _valid_https_origin(value):
    parsed = urlparse(value)
    try:
        _port = parsed.port
    except ValueError:
        return False
    return (
        parsed.scheme == "https"
        and bool(parsed.netloc)
        and parsed.username is None
        and parsed.password is None
        and parsed.path in {"", "/"}
        and not parsed.params
        and not parsed.query
        and not parsed.fragment
    )


def _check_fast_id_settings():
    if not getattr(settings, "FAST_ID_ENABLED", False):
        return []

    required_names = (
        "FAST_ID_BASE_URL",
        "FAST_ID_TENANT_ID",
        "FAST_ID_TENANT_KEY",
        "FAST_ID_CLIENT_ID",
        "FAST_ID_CLIENT_SECRET",
        "FAST_ID_MANAGEMENT_API_TOKEN",
        "FAST_ID_RP_ID",
        "FAST_ID_ORIGIN",
    )
    missing_names = [name for name in required_names if not getattr(settings, name, "")]
    if missing_names:
        return [
            Error(
                "Fast-ID is enabled but required server settings are missing: "
                + ", ".join(missing_names),
                id="account_security.E007",
            )
        ]

    errors = []
    if not _valid_https_origin(settings.FAST_ID_BASE_URL):
        errors.append(
            Error(
                "FAST_ID_BASE_URL must be an HTTPS origin without a path.",
                id="account_security.E008",
            )
        )

    rp_id = settings.FAST_ID_RP_ID
    parsed_origin = urlparse(settings.FAST_ID_ORIGIN)
    origin_host = parsed_origin.hostname or ""
    rp_id_lower = rp_id.lower()
    origin_matches_rp = origin_host == rp_id_lower or origin_host.endswith(
        f".{rp_id_lower}"
    )
    if (
        not _valid_rp_id(rp_id)
        or not _valid_https_origin(settings.FAST_ID_ORIGIN)
        or not origin_matches_rp
    ):
        errors.append(
            Error(
                "FAST_ID_ORIGIN must be an HTTPS origin on FAST_ID_RP_ID or its subdomain.",
                id="account_security.E009",
            )
        )

    timeout = getattr(settings, "FAST_ID_TIMEOUT_SECONDS", 0)
    if not isinstance(timeout, (int, float)) or timeout <= 0:
        errors.append(
            Error(
                "FAST_ID_TIMEOUT_SECONDS must be a positive number.",
                id="account_security.E010",
            )
        )
    return errors


@register(Tags.security, deploy=True)
def check_account_security_settings(app_configs, **kwargs):
    errors = _check_fast_id_settings()
    if not getattr(
        settings,
        "ACCOUNT_SECURITY_ENFORCE_PRODUCTION_CHECKS",
        False,
    ):
        return errors

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

    rp_id = getattr(settings, "ACCOUNT_SECURITY_WEBAUTHN_RP_ID", "")
    origin = getattr(settings, "ACCOUNT_SECURITY_WEBAUTHN_ORIGIN", "")
    if not rp_id or not origin:
        errors.append(
            Error(
                "WebAuthn RP ID and origin must be configured in production.",
                id="account_security.E004",
            )
        )
        return errors

    rp_id_is_valid = _valid_rp_id(rp_id)
    if not rp_id_is_valid:
        errors.append(
            Error(
                "WebAuthn RP ID must be a hostname without a scheme, port, or path.",
                id="account_security.E005",
            )
        )

    parsed_origin = urlparse(origin)
    origin_host = parsed_origin.hostname or ""
    rp_id_lower = rp_id.lower()
    origin_matches_rp = origin_host == rp_id_lower or origin_host.endswith(
        f".{rp_id_lower}"
    )
    try:
        _origin_port = parsed_origin.port
        origin_port_is_valid = True
    except ValueError:
        origin_port_is_valid = False
    origin_is_valid = (
        parsed_origin.scheme == "https"
        and bool(parsed_origin.netloc)
        and origin_port_is_valid
        and parsed_origin.username is None
        and parsed_origin.password is None
        and parsed_origin.path in {"", "/"}
        and not parsed_origin.params
        and not parsed_origin.query
        and not parsed_origin.fragment
        and (not rp_id_is_valid or origin_matches_rp)
    )
    if not origin_is_valid:
        errors.append(
            Error(
                "WebAuthn origin must be an HTTPS origin on the RP ID or its subdomain.",
                id="account_security.E006",
            )
        )

    return errors
