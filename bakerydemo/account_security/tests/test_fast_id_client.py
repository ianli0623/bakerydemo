import json

import httpx
from django.test import SimpleTestCase, override_settings

from bakerydemo.account_security.fast_id import FastIdClient, FastIdError

FAST_ID_SETTINGS = {
    "FAST_ID_BASE_URL": "https://fido.example.com",
    "FAST_ID_TENANT_ID": "tenant-id",
    "FAST_ID_TENANT_KEY": "tenant-key",
    "FAST_ID_CLIENT_ID": "client-id",
    "FAST_ID_CLIENT_SECRET": "client-secret",
    "FAST_ID_MANAGEMENT_API_TOKEN": "Bearer management-token",
    "FAST_ID_TIMEOUT_SECONDS": 2.5,
}


@override_settings(**FAST_ID_SETTINGS)
class FastIdClientTests(SimpleTestCase):
    def client_for(self, handler):
        return FastIdClient.from_settings(transport=httpx.MockTransport(handler))

    def test_list_users_uses_one_management_bearer_prefix(self):
        def handler(request):
            self.assertEqual(request.method, "GET")
            self.assertEqual(request.url.path, "/api/tenant/tenant-key/users")
            self.assertEqual(
                request.headers["authorization"],
                "Bearer management-token",
            )
            return httpx.Response(
                200,
                json={
                    "success": True,
                    "data": [
                        {
                            "id": "external-1",
                            "email": "person@example.com",
                            "name": "Person",
                            "enabled": True,
                        }
                    ],
                },
            )

        users = self.client_for(handler).list_users()

        self.assertEqual(users[0]["id"], "external-1")

    def test_create_user_sends_identity_with_management_bearer(self):
        def handler(request):
            self.assertEqual(request.method, "POST")
            self.assertEqual(request.url.path, "/api/tenant/tenant-key/user")
            self.assertEqual(
                request.headers["authorization"],
                "Bearer management-token",
            )
            self.assertEqual(
                json.loads(request.content),
                {
                    "email": "person@example.com",
                    "name": "Display Name",
                },
            )
            return httpx.Response(
                200,
                json={
                    "success": True,
                    "data": {
                        "id": "external-1",
                        "email": "person@example.com",
                        "name": "Display Name",
                        "enabled": True,
                    },
                },
            )

        user = self.client_for(handler).create_user(
            "person@example.com",
            "Display Name",
        )

        self.assertEqual(user["id"], "external-1")
        self.assertEqual(user["email"], "person@example.com")

    def test_delete_user_uses_management_bearer(self):
        def handler(request):
            self.assertEqual(request.method, "DELETE")
            self.assertEqual(
                request.url.path,
                "/api/tenant/tenant-key/user/external-1",
            )
            self.assertEqual(
                request.headers["authorization"],
                "Bearer management-token",
            )
            return httpx.Response(200, json={"success": True})

        deleted = self.client_for(handler).delete_user("external-1")

        self.assertTrue(deleted)

    def test_delete_user_treats_missing_remote_user_as_already_deleted(self):
        client = self.client_for(lambda request: httpx.Response(404))

        deleted = client.delete_user("missing-user")

        self.assertFalse(deleted)

    def test_delete_user_accepts_no_content_success(self):
        client = self.client_for(lambda request: httpx.Response(204))

        deleted = client.delete_user("external-1")

        self.assertTrue(deleted)

    def test_delete_user_rejects_unsuccessful_response(self):
        client = self.client_for(
            lambda request: httpx.Response(200, json={"success": False})
        )

        with self.assertRaises(FastIdError) as caught:
            client.delete_user("external-1")

        self.assertEqual(caught.exception.reason, "remote_rejected")

    def test_issue_user_token_uses_one_management_bearer_prefix(self):
        def handler(request):
            self.assertEqual(request.method, "POST")
            self.assertEqual(
                request.url.path,
                "/api/tenant/tenant-key/user/external-1/token",
            )
            self.assertEqual(
                request.headers["authorization"],
                "Bearer management-token",
            )
            return httpx.Response(
                200,
                json={"success": True, "data": "short-lived-user-token"},
            )

        token = self.client_for(handler).issue_user_token("external-1")

        self.assertEqual(token, "short-lived-user-token")

    def test_registration_calls_use_user_token_and_credential_payload(self):
        requests = []

        def handler(request):
            requests.append(request)
            if request.url.path.endswith("/initialize"):
                return httpx.Response(
                    200,
                    json={
                        "success": True,
                        "data": {
                            "challenge": "Y2hhbGxlbmdl",
                            "rp": {"id": "example.com"},
                        },
                    },
                )
            return httpx.Response(
                200,
                json={"success": True, "data": {"verified": True}},
            )

        client = self.client_for(handler)
        options = client.registration_initialize("user-token")
        verified = client.registration_finalize(
            "user-token",
            {"id": "credential-id", "type": "public-key"},
        )

        self.assertEqual(options["challenge"], "Y2hhbGxlbmdl")
        self.assertTrue(verified)
        self.assertEqual(
            [request.url.path for request in requests],
            [
                "/api/webauthn/tenant-key/registration/initialize",
                "/api/webauthn/tenant-key/registration/finalize",
            ],
        )
        self.assertTrue(
            all(
                request.headers["authorization"] == "Bearer user-token"
                for request in requests
            )
        )
        self.assertEqual(
            json.loads(requests[1].content),
            {"id": "credential-id", "type": "public-key"},
        )

    def test_webauthn_calls_accept_vendor_public_key_response_shape(self):
        def handler(request):
            if request.url.path.endswith("/registration/initialize"):
                return httpx.Response(
                    200,
                    json={
                        "publicKey": {
                            "challenge": "registration-challenge",
                            "user": {"id": "opaque-user-handle"},
                        }
                    },
                )
            if request.url.path.endswith("/registration/finalize"):
                return httpx.Response(200, json={"success": True})
            return httpx.Response(
                200,
                json={"publicKey": {"challenge": "authentication-challenge"}},
            )

        client = self.client_for(handler)

        registration = client.registration_initialize("user-token")
        finalized = client.registration_finalize(
            "user-token",
            {"id": "credential-id"},
        )
        authentication = client.authentication_initialize()

        self.assertEqual(registration["challenge"], "registration-challenge")
        self.assertTrue(finalized)
        self.assertEqual(authentication["challenge"], "authentication-challenge")

    def test_authentication_finalize_verifies_returned_token_server_side(self):
        requests = []

        def handler(request):
            requests.append(request)
            if request.url.path.endswith("/authentication/initialize"):
                return httpx.Response(
                    200,
                    json={
                        "success": True,
                        "data": {"challenge": "Y2hhbGxlbmdl"},
                    },
                )
            if request.url.path.endswith("/authentication/finalize"):
                return httpx.Response(
                    200,
                    json={"success": True, "data": "verifying-only-token"},
                )
            self.assertEqual(request.url.path, "/api/webauthn/token/verify")
            self.assertEqual(
                request.headers["authorization"],
                "Basic Y2xpZW50LWlkOmNsaWVudC1zZWNyZXQ=",
            )
            self.assertEqual(
                json.loads(request.content),
                {"token": "verifying-only-token"},
            )
            return httpx.Response(
                200,
                json={
                    "success": True,
                    "data": {
                        "verified": True,
                        "expired": False,
                        "revoked": False,
                        "claims": {"sub": "external-1"},
                    },
                },
            )

        client = self.client_for(handler)
        options = client.authentication_initialize()
        result = client.authentication_finalize(
            {"id": "credential-id", "type": "public-key"}
        )

        self.assertEqual(options["challenge"], "Y2hhbGxlbmdl")
        self.assertEqual(result.external_user_id, "external-1")
        self.assertEqual(len(requests), 3)

    def test_authentication_rejects_unverified_expired_revoked_or_missing_subject(self):
        cases = (
            (
                {
                    "verified": False,
                    "expired": False,
                    "revoked": False,
                    "claims": {"sub": "external-1"},
                },
                "unverified",
            ),
            (
                {
                    "verified": True,
                    "expired": True,
                    "revoked": False,
                    "claims": {"sub": "external-1"},
                },
                "expired",
            ),
            (
                {
                    "verified": True,
                    "expired": False,
                    "revoked": True,
                    "claims": {"sub": "external-1"},
                },
                "revoked",
            ),
            (
                {"verified": True, "expired": False, "revoked": False, "claims": {}},
                "missing subject",
            ),
        )

        for verify_data, label in cases:
            with self.subTest(label=label):

                def handler(request, verify_data=verify_data):
                    if request.url.path.endswith("/authentication/finalize"):
                        return httpx.Response(
                            200,
                            json={"success": True, "data": "token"},
                        )
                    return httpx.Response(
                        200,
                        json={"success": True, "data": verify_data},
                    )

                with self.assertRaises(FastIdError) as caught:
                    self.client_for(handler).authentication_finalize(
                        {"id": "credential-id"}
                    )

                self.assertEqual(caught.exception.reason, "invalid_authentication")

    def test_remote_failures_have_safe_reason_without_secrets(self):
        def timeout_handler(request):
            raise httpx.ConnectTimeout(
                "client-secret management-token", request=request
            )

        def status_handler(request):
            return httpx.Response(
                502,
                json={"error": "client-secret management-token"},
            )

        def invalid_json_handler(request):
            return httpx.Response(200, content=b"not-json")

        def rejected_handler(request):
            return httpx.Response(
                200,
                json={
                    "success": False,
                    "error": "client-secret management-token",
                },
            )

        cases = (
            (timeout_handler, "remote_timeout"),
            (status_handler, "remote_http_error"),
            (invalid_json_handler, "invalid_response"),
            (rejected_handler, "remote_rejected"),
        )

        for handler, expected_reason in cases:
            with self.subTest(reason=expected_reason):
                with self.assertRaises(FastIdError) as caught:
                    self.client_for(handler).list_users()

                self.assertEqual(caught.exception.reason, expected_reason)
                self.assertNotIn("client-secret", str(caught.exception))
                self.assertNotIn("management-token", str(caught.exception))

    def test_missing_data_is_an_invalid_response(self):
        client = self.client_for(
            lambda request: httpx.Response(200, json={"success": True})
        )

        with self.assertRaises(FastIdError) as caught:
            client.list_users()

        self.assertEqual(caught.exception.reason, "invalid_response")
