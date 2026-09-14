import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import validate_ipv46_address
from django.db import transaction
from django.utils import timezone

from .models import PasskeyAuditEvent, PasskeyEnrolment

DEFAULT_ENROLMENT_TTL_SECONDS = 900
DUMMY_CODE_DIGEST = "0" * 64


def _code_digest(raw_code):
    return hashlib.sha256(raw_code.encode("utf-8")).hexdigest()


@transaction.atomic
def create_enrolment(user, created_by, *, disable_password_on_success):
    now = timezone.now()
    PasskeyEnrolment.objects.filter(
        user=user,
        consumed_at__isnull=True,
        revoked_at__isnull=True,
    ).update(revoked_at=now)

    raw_code = secrets.token_urlsafe(32)
    ttl_seconds = getattr(
        settings,
        "ACCOUNT_SECURITY_WEBAUTHN_ENROLMENT_TTL_SECONDS",
        DEFAULT_ENROLMENT_TTL_SECONDS,
    )
    enrolment = PasskeyEnrolment.objects.create(
        user=user,
        created_by=created_by,
        code_digest=_code_digest(raw_code),
        disable_password_on_success=disable_password_on_success,
        expires_at=now + timedelta(seconds=ttl_seconds),
    )
    return enrolment, raw_code


def validate_enrolment(username, raw_code, *, at=None):
    at = at or timezone.now()
    supplied_digest = _code_digest(raw_code)
    username_field = get_user_model().USERNAME_FIELD
    username_lookup = {f"user__{username_field}__iexact": username}
    candidates = PasskeyEnrolment.objects.filter(
        **username_lookup,
        consumed_at__isnull=True,
        revoked_at__isnull=True,
        expires_at__gt=at,
    )

    found = None
    compared = False
    for enrolment in candidates:
        compared = True
        if secrets.compare_digest(enrolment.code_digest, supplied_digest):
            found = enrolment

    if not compared:
        secrets.compare_digest(DUMMY_CODE_DIGEST, supplied_digest)
    return found


def _request_ip(request):
    if request is None:
        return None
    address = request.META.get("REMOTE_ADDR")
    if not address:
        return None
    try:
        validate_ipv46_address(address)
    except ValidationError:
        return None
    return address


def record_passkey_event(
    event_type,
    *,
    success,
    user=None,
    actor=None,
    credential=None,
    request=None,
    reason="",
):
    user_agent = "" if request is None else request.META.get("HTTP_USER_AGENT", "")
    return PasskeyAuditEvent.objects.create(
        event_type=event_type[:40],
        success=success,
        user=user,
        actor=actor,
        credential=credential,
        ip_address=_request_ip(request),
        user_agent=user_agent[:255],
        reason=reason[:40],
    )
