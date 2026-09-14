import json
from datetime import UTC, datetime

from django import forms
from django.conf import settings
from django.contrib.auth import login
from django.db import IntegrityError
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_POST
from webauthn.helpers import base64url_to_bytes
from webauthn.helpers.exceptions import WebAuthnException

from .models import PasskeyEnrolment
from .passkeys import (
    PasskeyCeremonyError,
    build_authentication_options,
    build_registration_options,
    complete_registration,
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
    enrolment = _active_session_enrolment(request)
    if enrolment is None:
        return HttpResponseForbidden()

    options_json = build_registration_options(enrolment.user)
    options = json.loads(options_json)
    request.session[REGISTRATION_CHALLENGE_SESSION_KEY] = {
        "challenge": options["challenge"],
        "user_handle": options["user"]["id"],
        "issued_at": timezone.now().timestamp(),
    }
    return JsonResponse(options)


def _pop_valid_registration_challenge(request):
    state = request.session.pop(REGISTRATION_CHALLENGE_SESSION_KEY, None)
    if not isinstance(state, dict):
        return None
    try:
        issued_at = datetime.fromtimestamp(float(state["issued_at"]), tz=UTC)
        challenge = base64url_to_bytes(state["challenge"])
        user_handle = base64url_to_bytes(state["user_handle"])
    except (KeyError, TypeError, ValueError):
        return None
    ttl = settings.ACCOUNT_SECURITY_WEBAUTHN_CHALLENGE_TTL_SECONDS
    if (timezone.now() - issued_at).total_seconds() >= ttl:
        return None
    return challenge, user_handle


@require_POST
def passkey_registration_verify(request):
    enrolment = _active_session_enrolment(request)
    challenge_state = _pop_valid_registration_challenge(request)
    if enrolment is None or challenge_state is None:
        return _forbidden_json(GENERIC_REGISTRATION_ERROR)

    try:
        payload = json.loads(request.body)
        credential_payload = payload["credential"]
        transports = payload.get("transports", [])
    except (json.JSONDecodeError, KeyError, TypeError):
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
    except (KeyError, TypeError, ValueError):
        return None
    ttl = settings.ACCOUNT_SECURITY_WEBAUTHN_CHALLENGE_TTL_SECONDS
    if (timezone.now() - issued_at).total_seconds() >= ttl:
        return None
    return challenge


@require_POST
def passkey_authentication_verify(request):
    challenge = _pop_valid_authentication_challenge(request)
    if challenge is None:
        record_passkey_event(
            "login_failed",
            success=False,
            request=request,
            reason="invalid_challenge",
        )
        return _forbidden_json(GENERIC_LOGIN_ERROR)

    try:
        payload = json.loads(request.body)
        credential_payload = payload["credential"]
    except (json.JSONDecodeError, KeyError, TypeError):
        record_passkey_event(
            "login_failed",
            success=False,
            request=request,
            reason="invalid_request",
        )
        return _forbidden_json(GENERIC_LOGIN_ERROR)

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
        record_passkey_event(
            "login_failed",
            success=False,
            request=request,
            reason=reason,
        )
        return _forbidden_json(GENERIC_LOGIN_ERROR)

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
