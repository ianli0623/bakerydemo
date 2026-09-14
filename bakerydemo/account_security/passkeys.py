import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import validate_ipv46_address
from django.db import transaction
from django.utils import timezone
from webauthn import generate_registration_options, verify_registration_response
from webauthn.helpers import (
    base64url_to_bytes,
    bytes_to_base64url,
    options_to_json,
)
from webauthn.helpers.structs import (
    AuthenticatorAttachment,
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from .models import PasskeyAuditEvent, PasskeyCredential, PasskeyEnrolment
from .services import get_security_state

DEFAULT_ENROLMENT_TTL_SECONDS = 900
DUMMY_CODE_DIGEST = "0" * 64


class PasskeyCeremonyError(Exception):
    pass


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


def build_registration_options(user):
    existing_credentials = [
        PublicKeyCredentialDescriptor(
            id=base64url_to_bytes(credential_id),
        )
        for credential_id in user.passkey_credentials.filter(
            revoked_at__isnull=True
        ).values_list("credential_id", flat=True)
    ]
    options = generate_registration_options(
        rp_id=settings.ACCOUNT_SECURITY_WEBAUTHN_RP_ID,
        rp_name=settings.ACCOUNT_SECURITY_WEBAUTHN_RP_NAME,
        user_name=user.get_username(),
        user_id=secrets.token_bytes(32),
        user_display_name=user.get_full_name() or user.get_username(),
        authenticator_selection=AuthenticatorSelectionCriteria(
            authenticator_attachment=AuthenticatorAttachment.PLATFORM,
            resident_key=ResidentKeyRequirement.REQUIRED,
            require_resident_key=True,
            user_verification=UserVerificationRequirement.REQUIRED,
        ),
        exclude_credentials=existing_credentials,
    )
    return options_to_json(options)


def _enum_value(value):
    return value.value if hasattr(value, "value") else str(value)


@transaction.atomic
def complete_registration(
    *,
    user,
    enrolment,
    credential_payload,
    challenge,
    user_handle,
    transports,
):
    now = timezone.now()
    locked_enrolment = PasskeyEnrolment.objects.select_for_update().get(
        pk=enrolment.pk,
        user=user,
    )
    if (
        locked_enrolment.consumed_at is not None
        or locked_enrolment.revoked_at is not None
        or locked_enrolment.expires_at <= now
        or not user.is_active
        or not user.is_staff
    ):
        raise PasskeyCeremonyError("inactive_enrolment")

    verification = verify_registration_response(
        credential=credential_payload,
        expected_challenge=challenge,
        expected_rp_id=settings.ACCOUNT_SECURITY_WEBAUTHN_RP_ID,
        expected_origin=settings.ACCOUNT_SECURITY_WEBAUTHN_ORIGIN,
        require_user_verification=True,
    )
    credential = PasskeyCredential.objects.create(
        user=user,
        credential_id=bytes_to_base64url(verification.credential_id),
        credential_public_key=verification.credential_public_key,
        user_handle=user_handle,
        sign_count=verification.sign_count,
        device_type=_enum_value(verification.credential_device_type),
        backed_up=verification.credential_backed_up,
        transports=list(transports or []),
    )

    if locked_enrolment.disable_password_on_success:
        user.set_unusable_password()
        user.save(update_fields=["password"])
        state = get_security_state(user)
        state.must_change_password = False
        state.password_changed_at = None
        state.save(
            update_fields=[
                "must_change_password",
                "password_changed_at",
                "updated_at",
            ]
        )

    locked_enrolment.consumed_at = now
    locked_enrolment.save(update_fields=["consumed_at"])
    return credential


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
