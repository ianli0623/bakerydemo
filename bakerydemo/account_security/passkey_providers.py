import copy
import json
import logging
from binascii import Error as BinasciiError
from dataclasses import dataclass

from django.conf import settings
from django.db import DatabaseError, IntegrityError, transaction
from django.utils import timezone
from webauthn.helpers import base64url_to_bytes

from .authentication import normalize_account_email
from .fast_id import FastIdClient, FastIdError
from .models import FastIdUserLink, PasskeyCredential, PasskeyEnrolment
from .passkeys import (
    PasskeyCeremonyError,
    build_authentication_options,
    build_registration_options,
    complete_registration,
    verify_login_credential,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProviderStart:
    options: dict
    state: dict


@dataclass(frozen=True)
class ProviderRegistrationResult:
    user: object
    credential: PasskeyCredential | None = None


@dataclass(frozen=True)
class ProviderAuthenticationResult:
    user: object
    credential: PasskeyCredential | None = None


def _require_provider(state, expected):
    if not isinstance(state, dict) or state.get("provider") != expected:
        raise PasskeyCeremonyError("provider_mismatch")


def _sanitized_credential(payload):
    if not isinstance(payload, dict):
        raise PasskeyCeremonyError("invalid_request")
    credential = copy.deepcopy(payload)
    for untrusted_identity_field in ("token", "email", "user", "user_id"):
        credential.pop(untrusted_identity_field, None)
    return credential


class LocalPasskeyProvider:
    name = "local"

    def start_registration(self, user):
        options = json.loads(build_registration_options(user))
        return ProviderStart(
            options=options,
            state={
                "provider": self.name,
                "challenge": options["challenge"],
                "user_handle": options["user"]["id"],
            },
        )

    def finish_registration(
        self,
        user,
        enrolment,
        credential_payload,
        state,
        *,
        transports=None,
    ):
        _require_provider(state, self.name)
        try:
            challenge = base64url_to_bytes(state["challenge"])
            user_handle = base64url_to_bytes(state["user_handle"])
        except (BinasciiError, KeyError, TypeError, ValueError):
            raise PasskeyCeremonyError("invalid_context") from None
        credential = complete_registration(
            user=user,
            enrolment=enrolment,
            credential_payload=credential_payload,
            challenge=challenge,
            user_handle=user_handle,
            transports=transports,
        )
        return ProviderRegistrationResult(user=user, credential=credential)

    def start_authentication(self):
        options = json.loads(build_authentication_options())
        return ProviderStart(
            options=options,
            state={
                "provider": self.name,
                "challenge": options["challenge"],
            },
        )

    def finish_authentication(self, credential_payload, state):
        _require_provider(state, self.name)
        try:
            challenge = base64url_to_bytes(state["challenge"])
        except (BinasciiError, KeyError, TypeError, ValueError):
            raise PasskeyCeremonyError("invalid_context") from None
        credential = verify_login_credential(
            credential_payload=credential_payload,
            challenge=challenge,
        )
        return ProviderAuthenticationResult(
            user=credential.user,
            credential=credential,
        )


class FastIdPasskeyProvider:
    name = "fast_id"

    def __init__(self, *, client=None):
        self.client = client or FastIdClient.from_settings()

    def _cleanup_remote_user(self, external_user_id):
        try:
            self.client.delete_user(external_user_id)
        except FastIdError:
            logger.error("Fast-ID cleanup failed after local provisioning error")

    def _resolve_registration_link(
        self,
        user,
        *,
        allow_create=False,
        require_new_remote=False,
    ):
        try:
            link = user.fast_id_link
        except FastIdUserLink.DoesNotExist:
            link = None
        if link is not None:
            if link.tenant_key != settings.FAST_ID_TENANT_KEY:
                raise PasskeyCeremonyError("fast_id_link_mismatch")

        email = normalize_account_email(user.email)
        if not email:
            raise PasskeyCeremonyError("fast_id_user_not_found")
        matches = []
        for candidate in self.client.list_users():
            if not isinstance(candidate, dict):
                continue
            candidate_email = candidate.get("email")
            if (
                isinstance(candidate_email, str)
                and normalize_account_email(candidate_email) == email
            ):
                matches.append(candidate)
        if require_new_remote and link is None and matches:
            raise PasskeyCeremonyError("fast_id_user_exists")
        created_remotely = False
        if not matches:
            if link is not None:
                raise PasskeyCeremonyError("fast_id_link_mismatch")
            if not allow_create:
                raise PasskeyCeremonyError("fast_id_user_not_found")
            display_name = user.get_full_name().strip() or user.get_username() or email
            matches.append(self.client.create_user(email, display_name))
            created_remotely = True
        if len(matches) != 1:
            raise PasskeyCeremonyError("fast_id_user_ambiguous")

        match = matches[0]
        external_user_id = match.get("id")
        if not isinstance(external_user_id, str) or not external_user_id.strip():
            raise PasskeyCeremonyError("fast_id_user_invalid")
        external_user_id = external_user_id.strip()
        match_email = match.get("email")
        if (
            not isinstance(match_email, str)
            or normalize_account_email(match_email) != email
        ):
            raise PasskeyCeremonyError("fast_id_user_mismatch")
        if match.get("enabled") is False:
            raise PasskeyCeremonyError("fast_id_user_inactive")
        if link is not None:
            if link.external_user_id != external_user_id:
                raise PasskeyCeremonyError("fast_id_link_mismatch")
            return link
        try:
            with transaction.atomic():
                return FastIdUserLink.objects.create(
                    user=user,
                    tenant_key=settings.FAST_ID_TENANT_KEY,
                    external_user_id=external_user_id,
                )
        except DatabaseError as exc:
            if created_remotely:
                self._cleanup_remote_user(external_user_id)
            reason = (
                "fast_id_link_conflict"
                if isinstance(exc, IntegrityError)
                else "fast_id_link_persistence_failed"
            )
            raise PasskeyCeremonyError(reason) from None

    def provision_user(self, user):
        return self._resolve_registration_link(
            user,
            allow_create=True,
            require_new_remote=True,
        )

    def deprovision_user(self, user):
        try:
            link = user.fast_id_link
        except FastIdUserLink.DoesNotExist:
            return
        if link.tenant_key != settings.FAST_ID_TENANT_KEY:
            raise PasskeyCeremonyError("fast_id_link_mismatch")
        self.client.delete_user(link.external_user_id)

    def start_registration(self, user):
        link = self._resolve_registration_link(user)
        user_token = self.client.issue_user_token(link.external_user_id)
        options = self.client.registration_initialize(user_token)
        return ProviderStart(
            options=options,
            state={
                "provider": self.name,
                "external_user_id": link.external_user_id,
                "user_token": user_token,
            },
        )

    @transaction.atomic
    def finish_registration(
        self,
        user,
        enrolment,
        credential_payload,
        state,
        *,
        transports=None,
    ):
        _require_provider(state, self.name)
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
        try:
            link = FastIdUserLink.objects.select_for_update().get(
                user=user,
                tenant_key=settings.FAST_ID_TENANT_KEY,
                external_user_id=state["external_user_id"],
            )
            user_token = state["user_token"]
        except (FastIdUserLink.DoesNotExist, KeyError, TypeError):
            raise PasskeyCeremonyError("invalid_context") from None
        if not isinstance(user_token, str) or not user_token:
            raise PasskeyCeremonyError("invalid_context")

        self.client.registration_finalize(
            user_token,
            _sanitized_credential(credential_payload),
        )
        link.registered_at = now
        link.save(update_fields=["registered_at", "updated_at"])
        locked_enrolment.consumed_at = now
        locked_enrolment.save(update_fields=["consumed_at"])
        return ProviderRegistrationResult(user=user)

    def start_authentication(self):
        return ProviderStart(
            options=self.client.authentication_initialize(),
            state={"provider": self.name},
        )

    def finish_authentication(self, credential_payload, state):
        _require_provider(state, self.name)
        result = self.client.authentication_finalize(
            _sanitized_credential(credential_payload)
        )
        link = (
            FastIdUserLink.objects.select_related("user")
            .filter(
                tenant_key=settings.FAST_ID_TENANT_KEY,
                external_user_id=result.external_user_id,
                registered_at__isnull=False,
            )
            .first()
        )
        if link is None:
            raise PasskeyCeremonyError("fast_id_user_not_found")
        if not link.user.is_active or not link.user.is_staff:
            raise PasskeyCeremonyError("inactive_user")
        return ProviderAuthenticationResult(user=link.user)


def get_passkey_provider(*, client=None):
    if getattr(settings, "FAST_ID_ENABLED", False):
        return FastIdPasskeyProvider(client=client)
    return LocalPasskeyProvider()
