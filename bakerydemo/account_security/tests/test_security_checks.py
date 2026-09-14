from django.test import SimpleTestCase, override_settings

from bakerydemo.account_security.checks import check_account_security_settings


class AccountSecurityChecksTests(SimpleTestCase):
    @override_settings(
        ACCOUNT_SECURITY_ENFORCE_PRODUCTION_CHECKS=True,
        ADMIN_PASSWORD="changeme",
        WAGTAILADMIN_BASE_URL="http://example.com",
        SECURE_SSL_REDIRECT=False,
        SESSION_COOKIE_SECURE=False,
        CSRF_COOKIE_SECURE=False,
        SECURE_HSTS_SECONDS=0,
        ACCOUNT_SECURITY_WEBAUTHN_RP_ID="example.com",
        ACCOUNT_SECURITY_WEBAUTHN_ORIGIN="https://cms.example.com",
    )
    def test_insecure_production_settings_are_errors(self):
        errors = check_account_security_settings(None)

        self.assertEqual(
            {error.id for error in errors},
            {
                "account_security.E001",
                "account_security.E002",
                "account_security.E003",
            },
        )

    @override_settings(
        ACCOUNT_SECURITY_ENFORCE_PRODUCTION_CHECKS=True,
        ADMIN_PASSWORD="Valid-Deployment-Password-1!",
        WAGTAILADMIN_BASE_URL="https://cms.example.com",
        SECURE_SSL_REDIRECT=True,
        SESSION_COOKIE_SECURE=True,
        CSRF_COOKIE_SECURE=True,
        SECURE_HSTS_SECONDS=3600,
        ACCOUNT_SECURITY_WEBAUTHN_RP_ID="example.com",
        ACCOUNT_SECURITY_WEBAUTHN_ORIGIN="https://cms.example.com",
    )
    def test_secure_production_settings_pass(self):
        self.assertEqual(check_account_security_settings(None), [])

    @override_settings(ACCOUNT_SECURITY_ENFORCE_PRODUCTION_CHECKS=False)
    def test_local_development_skips_production_only_errors(self):
        self.assertEqual(check_account_security_settings(None), [])

    @override_settings(
        ACCOUNT_SECURITY_ENFORCE_PRODUCTION_CHECKS=True,
        ADMIN_PASSWORD="Valid-Deployment-Password-1!",
        WAGTAILADMIN_BASE_URL="https://cms.example.com",
        SECURE_SSL_REDIRECT=True,
        SESSION_COOKIE_SECURE=True,
        CSRF_COOKIE_SECURE=True,
        SECURE_HSTS_SECONDS=3600,
        ACCOUNT_SECURITY_WEBAUTHN_RP_ID="",
        ACCOUNT_SECURITY_WEBAUTHN_ORIGIN="",
    )
    def test_missing_webauthn_settings_are_an_error(self):
        errors = check_account_security_settings(None)

        self.assertEqual(
            {error.id for error in errors},
            {"account_security.E004"},
        )

    @override_settings(
        ACCOUNT_SECURITY_ENFORCE_PRODUCTION_CHECKS=True,
        ADMIN_PASSWORD="Valid-Deployment-Password-1!",
        WAGTAILADMIN_BASE_URL="https://cms.example.com",
        SECURE_SSL_REDIRECT=True,
        SESSION_COOKIE_SECURE=True,
        CSRF_COOKIE_SECURE=True,
        SECURE_HSTS_SECONDS=3600,
        ACCOUNT_SECURITY_WEBAUTHN_RP_ID="https://example.com:443/path",
        ACCOUNT_SECURITY_WEBAUTHN_ORIGIN="https://cms.example.com",
    )
    def test_rp_id_cannot_contain_scheme_port_or_path(self):
        errors = check_account_security_settings(None)

        self.assertEqual(
            {error.id for error in errors},
            {"account_security.E005"},
        )

    @override_settings(
        ACCOUNT_SECURITY_ENFORCE_PRODUCTION_CHECKS=True,
        ADMIN_PASSWORD="Valid-Deployment-Password-1!",
        WAGTAILADMIN_BASE_URL="https://cms.example.com",
        SECURE_SSL_REDIRECT=True,
        SESSION_COOKIE_SECURE=True,
        CSRF_COOKIE_SECURE=True,
        SECURE_HSTS_SECONDS=3600,
        ACCOUNT_SECURITY_WEBAUTHN_RP_ID="example.com",
        ACCOUNT_SECURITY_WEBAUTHN_ORIGIN="http://unrelated.example.net/path",
    )
    def test_origin_must_be_https_exact_and_match_rp_id(self):
        errors = check_account_security_settings(None)

        self.assertEqual(
            {error.id for error in errors},
            {"account_security.E006"},
        )
