import json
from binascii import Error as BinasciiError
from datetime import UTC, datetime

from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model, login
from django.core.cache import caches
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.crypto import salted_hmac
from django.utils.translation import gettext_lazy as _
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST
from wagtail.admin import messages
from webauthn.helpers import base64url_to_bytes
from webauthn.helpers.exceptions import WebAuthnException

from .models import PasskeyCredential, PasskeyEnrolment
from .passkeys import (
    PasskeyCeremonyError,
    build_authentication_options,
    build_registration_options,
    complete_registration,
    create_enrolment,
    record_passkey_event,
    validate_enrolment,
    verify_login_credential,
)

ENROLMENT_SESSION_KEY = "account_security_passkey_enrolment_id"
REGISTRATION_CHALLENGE_SESSION_KEY = "account_security_passkey_registration_challenge"
AUTHENTICATION_CHALLENGE_SESSION_KEY = (
    "account_security_passkey_authentication_challenge"
)
GENERIC_ENROLMENT_ERROR = _(
    "The enrolment details are invalid or expired. Ask an administrator for a new code."
)
GENERIC_REGISTRATION_ERROR = _(
    "Windows Hello registration could not be completed. Please try again."
)
GENERIC_LOGIN_ERROR = _(
    "Windows Hello sign-in could not be completed. Please try again."
)
cache = caches[getattr(settings, "ACCOUNT_SECURITY_PASSKEY_CACHE_ALIAS", "default")]


class PasskeyThrottleUnavailable(Exception):
    pass


def _passkey_failure_key(request, credential_id):
    ip_address = request.META.get("REMOTE_ADDR", "unknown")
    digest = salted_hmac(
        "account_security.passkey_failure",
        f"{ip_address}\0{credential_id or 'unknown'}",
    ).hexdigest()
    return f"account-security:passkey-failures:{digest}"


def _passkey_is_rate_limited(request, credential_id):
    key = _passkey_failure_key(request, credential_id)
    limit = settings.ACCOUNT_SECURITY_PASSKEY_FAILURE_LIMIT
    try:
        failures = cache.get(key, 0)
    except Exception as error:
        raise PasskeyThrottleUnavailable from error
    if not isinstance(failures, int):
        raise PasskeyThrottleUnavailable
    return failures >= limit


def _increment_passkey_failures(request, credential_id):
    key = _passkey_failure_key(request, credential_id)
    timeout = settings.ACCOUNT_SECURITY_PASSKEY_LOCKOUT_SECONDS
    try:
        added = cache.add(key, 1, timeout=timeout)
        if added is None:
            raise PasskeyThrottleUnavailable
        if added:
            return 1
        failures = cache.incr(key)
    except PasskeyThrottleUnavailable:
        raise
    except Exception as error:
        raise PasskeyThrottleUnavailable from error
    if not isinstance(failures, int):
        raise PasskeyThrottleUnavailable
    return failures


def _clear_passkey_failures(request, credential_id):
    try:
        deleted = cache.delete(_passkey_failure_key(request, credential_id))
    except Exception as error:
        raise PasskeyThrottleUnavailable from error
    if deleted is None:
        raise PasskeyThrottleUnavailable


def _rate_limited_json(request, *, reason):
    record_passkey_event(
        "login_rate_limited",
        success=False,
        request=request,
        reason=reason,
    )
    response = JsonResponse({"error": str(GENERIC_LOGIN_ERROR)}, status=429)
    response["Retry-After"] = str(settings.ACCOUNT_SECURITY_PASSKEY_LOCKOUT_SECONDS)
    return response


def _throttle_unavailable_json(request):
    record_passkey_event(
        "login_rate_limited",
        success=False,
        request=request,
        reason="throttle_unavailable",
    )
    response = JsonResponse({"error": str(GENERIC_LOGIN_ERROR)}, status=503)
    response["Retry-After"] = str(settings.ACCOUNT_SECURITY_PASSKEY_LOCKOUT_SECONDS)
    return response


def _reject_passkey_login(request, credential_id, reason):
    try:
        failures = _increment_passkey_failures(request, credential_id)
    except PasskeyThrottleUnavailable:
        return _throttle_unavailable_json(request)
    if failures >= settings.ACCOUNT_SECURITY_PASSKEY_FAILURE_LIMIT:
        return _rate_limited_json(request, reason="failure_limit_reached")
    record_passkey_event(
        "login_failed",
        success=False,
        request=request,
        reason=reason,
    )
    return _forbidden_json(GENERIC_LOGIN_ERROR)


class PasskeyEnrolmentForm(forms.Form):
    username = forms.CharField(label=_("Username"), max_length=150)
    enrolment_code = forms.CharField(
        label=_("Windows Hello enrolment code"),
        max_length=128,
        strip=True,
        widget=forms.PasswordInput(
            render_value=True, attrs={"autocomplete": "one-time-code"}
        ),
    )


def passkey_enrol(request):
    registration_ready = False
    if request.method == "POST":
        request.session.pop(ENROLMENT_SESSION_KEY, None)
        request.session.pop(REGISTRATION_CHALLENGE_SESSION_KEY, None)
    form = PasskeyEnrolmentForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        enrolment = validate_enrolment(
            form.cleaned_data["username"],
            form.cleaned_data["enrolment_code"],
        )
        if (
            enrolment is None
            or not enrolment.user.is_active
            or not enrolment.user.is_staff
        ):
            record_passkey_event(
                "enrolment_rejected",
                success=False,
                request=request,
                reason="invalid_or_expired",
            )
            form.add_error(None, GENERIC_ENROLMENT_ERROR)
        else:
            request.session[ENROLMENT_SESSION_KEY] = enrolment.pk
            registration_ready = True

    return render(
        request,
        "account_security/passkey_enrol.html",
        {
            "form": form,
            "registration_ready": registration_ready,
        },
    )


def _active_session_enrolment(request):
    enrolment_id = request.session.get(ENROLMENT_SESSION_KEY)
    if not enrolment_id:
        return None
    return (
        PasskeyEnrolment.objects.select_related("user")
        .filter(
            pk=enrolment_id,
            consumed_at__isnull=True,
            revoked_at__isnull=True,
            expires_at__gt=timezone.now(),
            user__is_active=True,
            user__is_staff=True,
        )
        .first()
    )


def _forbidden_json(message):
    return JsonResponse({"error": str(message)}, status=403)


@require_POST
def passkey_registration_options(request):
    request.session.pop(REGISTRATION_CHALLENGE_SESSION_KEY, None)
    enrolment = _active_session_enrolment(request)
    if enrolment is None:
        return HttpResponseForbidden()

    options_json = build_registration_options(enrolment.user)
    options = json.loads(options_json)
    request.session[REGISTRATION_CHALLENGE_SESSION_KEY] = {
        "challenge": options["challenge"],
        "user_handle": options["user"]["id"],
        "enrolment_id": enrolment.pk,
        "issued_at": timezone.now().timestamp(),
    }
    return JsonResponse(options)


def _pop_valid_registration_challenge(request, enrolment_id):
    state = request.session.pop(REGISTRATION_CHALLENGE_SESSION_KEY, None)
    if not isinstance(state, dict):
        return None
    try:
        issued_at = datetime.fromtimestamp(float(state["issued_at"]), tz=UTC)
        challenge = base64url_to_bytes(state["challenge"])
        user_handle = base64url_to_bytes(state["user_handle"])
        state_enrolment_id = int(state["enrolment_id"])
    except (BinasciiError, KeyError, TypeError, ValueError):
        return None
    if state_enrolment_id != enrolment_id:
        return None
    ttl = settings.ACCOUNT_SECURITY_WEBAUTHN_CHALLENGE_TTL_SECONDS
    if (timezone.now() - issued_at).total_seconds() >= ttl:
        return None
    return challenge, user_handle


@require_POST
@transaction.atomic
def passkey_registration_verify(request):
    enrolment = _active_session_enrolment(request)
    challenge_state = _pop_valid_registration_challenge(
        request,
        enrolment.pk if enrolment is not None else None,
    )
    if enrolment is None or challenge_state is None:
        request.session.pop(ENROLMENT_SESSION_KEY, None)
        record_passkey_event(
            "registration_failed",
            success=False,
            user=enrolment.user if enrolment is not None else None,
            request=request,
            reason="invalid_context",
        )
        return _forbidden_json(GENERIC_REGISTRATION_ERROR)

    try:
        payload = json.loads(request.body)
        credential_payload = payload["credential"]
        transports = payload.get("transports", [])
    except (json.JSONDecodeError, KeyError, TypeError):
        record_passkey_event(
            "registration_failed",
            success=False,
            user=enrolment.user,
            request=request,
            reason="invalid_request",
        )
        return _forbidden_json(GENERIC_REGISTRATION_ERROR)

    challenge, user_handle = challenge_state
    try:
        credential = complete_registration(
            user=enrolment.user,
            enrolment=enrolment,
            credential_payload=credential_payload,
            challenge=challenge,
            user_handle=user_handle,
            transports=transports,
        )
    except (IntegrityError, PasskeyCeremonyError, WebAuthnException) as error:
        if isinstance(error, PasskeyCeremonyError):
            reason = str(error)
        elif isinstance(error, IntegrityError):
            reason = "duplicate_credential"
        else:
            reason = "invalid_registration"
        record_passkey_event(
            "registration_failed",
            success=False,
            user=enrolment.user,
            request=request,
            reason=reason,
        )
        return _forbidden_json(GENERIC_REGISTRATION_ERROR)

    request.session.pop(ENROLMENT_SESSION_KEY, None)
    record_passkey_event(
        "registration_succeeded",
        success=True,
        user=enrolment.user,
        credential=credential,
        request=request,
    )
    login(
        request,
        enrolment.user,
        backend="django.contrib.auth.backends.ModelBackend",
    )
    return JsonResponse({"redirect": reverse("wagtailadmin_home")})


def passkey_login(request):
    return render(request, "account_security/passkey_login.html")


@require_POST
def passkey_authentication_options(request):
    options = json.loads(build_authentication_options())
    request.session[AUTHENTICATION_CHALLENGE_SESSION_KEY] = {
        "challenge": options["challenge"],
        "issued_at": timezone.now().timestamp(),
    }
    return JsonResponse(options)


def _pop_valid_authentication_challenge(request):
    state = request.session.pop(AUTHENTICATION_CHALLENGE_SESSION_KEY, None)
    if not isinstance(state, dict):
        return None
    try:
        issued_at = datetime.fromtimestamp(float(state["issued_at"]), tz=UTC)
        challenge = base64url_to_bytes(state["challenge"])
    except (BinasciiError, KeyError, TypeError, ValueError):
        return None
    ttl = settings.ACCOUNT_SECURITY_WEBAUTHN_CHALLENGE_TTL_SECONDS
    if (timezone.now() - issued_at).total_seconds() >= ttl:
        return None
    return challenge


@require_POST
@transaction.atomic
def passkey_authentication_verify(request):
    try:
        payload = json.loads(request.body)
        credential_payload = payload["credential"]
        credential_id = credential_payload.get("id")
        if not isinstance(credential_id, str):
            credential_id = None
    except (json.JSONDecodeError, KeyError, TypeError):
        _pop_valid_authentication_challenge(request)
        return _reject_passkey_login(request, None, "invalid_request")

    try:
        rate_limited = _passkey_is_rate_limited(request, credential_id)
    except PasskeyThrottleUnavailable:
        _pop_valid_authentication_challenge(request)
        return _throttle_unavailable_json(request)
    if rate_limited:
        _pop_valid_authentication_challenge(request)
        return _rate_limited_json(request, reason="failure_limit_reached")

    challenge = _pop_valid_authentication_challenge(request)
    if challenge is None:
        return _reject_passkey_login(
            request,
            credential_id,
            "invalid_challenge",
        )

    try:
        credential = verify_login_credential(
            credential_payload=credential_payload,
            challenge=challenge,
        )
    except (PasskeyCeremonyError, WebAuthnException) as error:
        reason = (
            str(error)
            if isinstance(error, PasskeyCeremonyError)
            else "invalid_authentication"
        )
        return _reject_passkey_login(request, credential_id, reason)

    try:
        _clear_passkey_failures(request, credential_id)
    except PasskeyThrottleUnavailable:
        return _throttle_unavailable_json(request)
    record_passkey_event(
        "login_succeeded",
        success=True,
        user=credential.user,
        credential=credential,
        request=request,
    )
    login(
        request,
        credential.user,
        backend="django.contrib.auth.backends.ModelBackend",
    )
    return JsonResponse({"redirect": reverse("wagtailadmin_home")})


def _require_superuser(request):
    if not request.user.is_authenticated or not request.user.is_superuser:
        raise PermissionDenied


def _passkey_management_context(*, enrolment_code=None, enrolment_user=None):
    now = timezone.now()
    user_rows = []
    user_model = get_user_model()
    users = (
        user_model.objects.filter(is_staff=True)
        .prefetch_related("passkey_credentials", "passkey_enrolments")
        .order_by(user_model.USERNAME_FIELD)
    )
    for user in users:
        active_credentials = [
            credential
            for credential in user.passkey_credentials.all()
            if credential.revoked_at is None
        ]
        pending_enrolments = [
            enrolment
            for enrolment in user.passkey_enrolments.all()
            if enrolment.consumed_at is None
            and enrolment.revoked_at is None
            and enrolment.expires_at > now
        ]
        user_rows.append(
            {
                "user": user,
                "active_credentials": active_credentials,
                "pending_enrolments": pending_enrolments,
            }
        )
    return {
        "user_rows": user_rows,
        "enrolment_code": enrolment_code,
        "enrolment_user": enrolment_user,
    }


@require_GET
def passkey_management(request):
    _require_superuser(request)
    return render(
        request,
        "account_security/passkey_management.html",
        _passkey_management_context(),
    )


@require_POST
@never_cache
@transaction.atomic
def passkey_generate_enrolment(request, user_id):
    _require_superuser(request)
    user = get_object_or_404(
        get_user_model(),
        pk=user_id,
        is_active=True,
        is_staff=True,
    )
    _enrolment, raw_code = create_enrolment(
        user,
        request.user,
        disable_password_on_success=not user.has_usable_password(),
    )
    record_passkey_event(
        "enrolment_created",
        success=True,
        user=user,
        actor=request.user,
        request=request,
    )
    return render(
        request,
        "account_security/passkey_management.html",
        _passkey_management_context(
            enrolment_code=raw_code,
            enrolment_user=user,
        ),
    )


@require_POST
@transaction.atomic
def passkey_revoke(request, credential_id):
    _require_superuser(request)
    credential = get_object_or_404(
        PasskeyCredential.objects.select_related("user"),
        pk=credential_id,
        revoked_at__isnull=True,
    )
    credential.revoked_at = timezone.now()
    credential.save(update_fields=["revoked_at"])
    record_passkey_event(
        "credential_revoked",
        success=True,
        user=credential.user,
        actor=request.user,
        credential=credential,
        request=request,
    )
    messages.success(request, _("The Windows Hello credential was revoked."))
    return redirect("account_security_passkey_management")
