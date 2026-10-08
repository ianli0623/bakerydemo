from dataclasses import dataclass
from urllib.parse import quote

import httpx
from django.conf import settings


class FastIdError(Exception):
    def __init__(self, reason):
        self.reason = reason
        super().__init__(f"Fast-ID request failed ({reason}).")


@dataclass(frozen=True)
class FastIdAuthenticationResult:
    external_user_id: str


class FastIdClient:
    def __init__(
        self,
        *,
        base_url,
        tenant_key,
        client_id,
        client_secret,
        management_api_token,
        timeout,
        transport=None,
    ):
        self.base_url = base_url.rstrip("/")
        self.tenant_key = tenant_key
        self.client_id = client_id
        self.client_secret = client_secret
        self.management_api_token = management_api_token
        self.timeout = timeout
        self.transport = transport

    @classmethod
    def from_settings(cls, *, transport=None):
        return cls(
            base_url=settings.FAST_ID_BASE_URL,
            tenant_key=settings.FAST_ID_TENANT_KEY,
            client_id=settings.FAST_ID_CLIENT_ID,
            client_secret=settings.FAST_ID_CLIENT_SECRET,
            management_api_token=settings.FAST_ID_MANAGEMENT_API_TOKEN,
            timeout=settings.FAST_ID_TIMEOUT_SECONDS,
            transport=transport,
        )

    @staticmethod
    def _bearer(token):
        normalized = token.strip()
        if normalized.lower().startswith("bearer "):
            normalized = normalized[7:].strip()
        if not normalized:
            raise FastIdError("configuration_error")
        return f"Bearer {normalized}"

    @property
    def _basic_auth(self):
        return httpx.BasicAuth(self.client_id, self.client_secret)

    def _request(
        self,
        method,
        path,
        *,
        auth=None,
        headers=None,
        json=None,
        accepted_statuses=(),
    ):
        try:
            with httpx.Client(
                base_url=self.base_url,
                timeout=self.timeout,
                transport=self.transport,
            ) as client:
                response = client.request(
                    method,
                    path,
                    auth=auth,
                    headers=headers,
                    json=json,
                )
        except httpx.TimeoutException as exc:
            raise FastIdError("remote_timeout") from exc
        except httpx.HTTPError as exc:
            raise FastIdError("remote_unavailable") from exc

        if response.status_code in accepted_statuses:
            return response.status_code
        if not response.is_success:
            raise FastIdError("remote_http_error")
        try:
            payload = response.json()
        except ValueError as exc:
            raise FastIdError("invalid_response") from exc
        if not isinstance(payload, dict):
            raise FastIdError("invalid_response")
        return payload

    @staticmethod
    def _success_data(payload):
        if payload.get("success") is not True:
            raise FastIdError("remote_rejected")
        if "data" not in payload:
            raise FastIdError("invalid_response")
        return payload["data"]

    @classmethod
    def _public_key_options(cls, payload):
        if "publicKey" in payload:
            options = payload["publicKey"]
        else:
            data = cls._success_data(payload)
            options = data.get("publicKey") if isinstance(data, dict) else None
            if options is None:
                options = data
        if not isinstance(options, dict):
            raise FastIdError("invalid_response")
        return options

    def list_users(self):
        tenant_key = quote(self.tenant_key, safe="")
        payload = self._request(
            "GET",
            f"/api/tenant/{tenant_key}/users",
            headers={"Authorization": self._bearer(self.management_api_token)},
        )
        data = self._success_data(payload)
        if not isinstance(data, list):
            raise FastIdError("invalid_response")
        return data

    def create_user(self, email, name):
        tenant_key = quote(self.tenant_key, safe="")
        payload = self._request(
            "POST",
            f"/api/tenant/{tenant_key}/user",
            headers={"Authorization": self._bearer(self.management_api_token)},
            json={"email": email, "name": name},
        )
        data = self._success_data(payload)
        if not isinstance(data, dict):
            raise FastIdError("invalid_response")
        return data

    def delete_user(self, user_id):
        tenant_key = quote(self.tenant_key, safe="")
        external_user_id = quote(user_id, safe="")
        payload = self._request(
            "DELETE",
            f"/api/tenant/{tenant_key}/user/{external_user_id}",
            headers={"Authorization": self._bearer(self.management_api_token)},
            accepted_statuses=(204, 404),
        )
        if payload == 404:
            return False
        if payload == 204:
            return True
        if payload.get("success") is not True:
            raise FastIdError("remote_rejected")
        return True

    def issue_user_token(self, user_id):
        tenant_key = quote(self.tenant_key, safe="")
        external_user_id = quote(user_id, safe="")
        payload = self._request(
            "POST",
            f"/api/tenant/{tenant_key}/user/{external_user_id}/token",
            headers={"Authorization": self._bearer(self.management_api_token)},
        )
        data = self._success_data(payload)
        token = data.get("token") if isinstance(data, dict) else data
        if not isinstance(token, str) or not token.strip():
            raise FastIdError("invalid_response")
        return token

    def registration_initialize(self, user_token):
        tenant_key = quote(self.tenant_key, safe="")
        payload = self._request(
            "POST",
            f"/api/webauthn/{tenant_key}/registration/initialize",
            headers={"Authorization": self._bearer(user_token)},
        )
        return self._public_key_options(payload)

    def registration_finalize(self, user_token, credential):
        tenant_key = quote(self.tenant_key, safe="")
        payload = self._request(
            "POST",
            f"/api/webauthn/{tenant_key}/registration/finalize",
            headers={"Authorization": self._bearer(user_token)},
            json=credential,
        )
        if payload.get("success") is not True:
            raise FastIdError("remote_rejected")
        data = payload.get("data", True)
        if isinstance(data, dict) and data.get("verified") is not True:
            raise FastIdError("invalid_registration")
        if data is False or data is None:
            raise FastIdError("invalid_registration")
        return True

    def authentication_initialize(self):
        tenant_key = quote(self.tenant_key, safe="")
        payload = self._request(
            "POST",
            f"/api/webauthn/{tenant_key}/authentication/initialize",
        )
        return self._public_key_options(payload)

    def authentication_finalize(self, credential):
        tenant_key = quote(self.tenant_key, safe="")
        payload = self._request(
            "POST",
            f"/api/webauthn/{tenant_key}/authentication/finalize",
            json=credential,
        )
        data = self._success_data(payload)
        token = data.get("token") if isinstance(data, dict) else data
        if not isinstance(token, str) or not token.strip():
            raise FastIdError("invalid_authentication")

        verification_payload = self._request(
            "POST",
            "/api/webauthn/token/verify",
            auth=self._basic_auth,
            json={"token": token},
        )
        verification = self._success_data(verification_payload)
        if not isinstance(verification, dict):
            raise FastIdError("invalid_authentication")
        claims = verification.get("claims")
        external_user_id = claims.get("sub") if isinstance(claims, dict) else None
        if (
            verification.get("verified") is not True
            or verification.get("expired") is not False
            or verification.get("revoked") is not False
            or not isinstance(external_user_id, str)
            or not external_user_id.strip()
        ):
            raise FastIdError("invalid_authentication")
        return FastIdAuthenticationResult(external_user_id=external_user_id)
