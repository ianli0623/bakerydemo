import json
import os
import subprocess
import sys

from django.test import SimpleTestCase


class AccountSecuritySettingsTests(SimpleTestCase):
    def _read_settings(self, module, extra_env=None):
        script = f'''\
import importlib
import json
s = importlib.import_module("{module}")
print(json.dumps({{
    "ssl": getattr(s, "SECURE_SSL_REDIRECT", False),
    "session": getattr(s, "SESSION_COOKIE_SECURE", False),
    "csrf": getattr(s, "CSRF_COOKIE_SECURE", False),
    "hsts": getattr(s, "SECURE_HSTS_SECONDS", 0),
    "proxy": getattr(s, "SECURE_PROXY_SSL_HEADER", None),
    "admin_url": getattr(s, "WAGTAILADMIN_BASE_URL", ""),
    "production_checks": getattr(
        s, "ACCOUNT_SECURITY_ENFORCE_PRODUCTION_CHECKS", False
    ),
    "passkey_cache_alias": getattr(
        s, "ACCOUNT_SECURITY_PASSKEY_CACHE_ALIAS", "default"
    ),
    "passkey_cache_ignore_exceptions": getattr(s, "CACHES", {{}}).get(
        getattr(s, "ACCOUNT_SECURITY_PASSKEY_CACHE_ALIAS", "default"), {{}}
    ).get("OPTIONS", {{}}).get("IGNORE_EXCEPTIONS"),
    "database_engine": s.DATABASES["default"]["ENGINE"],
    "postgres_app": "django.contrib.postgres" in s.INSTALLED_APPS,
    "fast_id_enabled": getattr(s, "FAST_ID_ENABLED", False),
    "fast_id_base_url": getattr(s, "FAST_ID_BASE_URL", ""),
    "fast_id_tenant_id": getattr(s, "FAST_ID_TENANT_ID", ""),
    "fast_id_tenant_key": getattr(s, "FAST_ID_TENANT_KEY", ""),
    "fast_id_client_id": getattr(s, "FAST_ID_CLIENT_ID", ""),
    "fast_id_has_client_secret": bool(getattr(s, "FAST_ID_CLIENT_SECRET", "")),
    "fast_id_has_management_token": bool(
        getattr(s, "FAST_ID_MANAGEMENT_API_TOKEN", "")
    ),
    "fast_id_rp_id": getattr(s, "FAST_ID_RP_ID", ""),
    "fast_id_origin": getattr(s, "FAST_ID_ORIGIN", ""),
    "fast_id_timeout": getattr(s, "FAST_ID_TIMEOUT_SECONDS", None),
}}))
'''
        environment = os.environ.copy()
        for key in (
            "PRIMARY_HOST",
            "SECURE_SSL_REDIRECT",
            "SECURE_HSTS_SECONDS",
            "REDIS_TLS_URL",
            "REDIS_URL",
            "FAST_ID_ENABLED",
            "FAST_ID_BASE_URL",
            "FAST_ID_TENANT_ID",
            "FAST_ID_TENANT_KEY",
            "FAST_ID_CLIENT_ID",
            "FAST_ID_CLIENT_SECRET",
            "FAST_ID_MANAGEMENT_API_TOKEN",
            "FAST_ID_RP_ID",
            "FAST_ID_ORIGIN",
            "FAST_ID_TIMEOUT_SECONDS",
        ):
            environment.pop(key, None)
        environment.update(extra_env or {})
        result = subprocess.run(
            [sys.executable, "-c", script],
            check=True,
            capture_output=True,
            text=True,
            env=environment,
        )
        return json.loads(result.stdout.strip().splitlines()[-1])

    def test_production_enforces_https_and_secure_cookies(self):
        production = self._read_settings(
            "bakerydemo.settings.production",
            {"PRIMARY_HOST": "cms.example.com"},
        )

        self.assertTrue(production["ssl"])
        self.assertTrue(production["session"])
        self.assertTrue(production["csrf"])
        self.assertGreater(production["hsts"], 0)
        self.assertTrue(production["production_checks"])
        self.assertEqual(
            production["proxy"],
            ["HTTP_X_FORWARDED_PROTO", "https"],
        )
        self.assertEqual(
            production["admin_url"],
            "https://cms.example.com",
        )

    def test_production_passkey_throttle_cache_fails_closed(self):
        production = self._read_settings(
            "bakerydemo.settings.production",
            {
                "PRIMARY_HOST": "cms.example.com",
                "REDIS_URL": "redis://localhost:6379",
            },
        )

        self.assertEqual(production["passkey_cache_alias"], "passkey_throttle")
        self.assertFalse(production["passkey_cache_ignore_exceptions"])

    def test_production_https_cannot_be_disabled_by_environment(self):
        production = self._read_settings(
            "bakerydemo.settings.production",
            {
                "PRIMARY_HOST": "cms.example.com",
                "SECURE_SSL_REDIRECT": "false",
            },
        )

        self.assertTrue(production["ssl"])

    def test_dev_and_test_keep_local_http_available(self):
        for module in (
            "bakerydemo.settings.dev",
            "bakerydemo.settings.test",
        ):
            with self.subTest(module=module):
                local = self._read_settings(module)
                self.assertFalse(local["ssl"])
                self.assertFalse(local["session"])
                self.assertFalse(local["csrf"])
                self.assertFalse(local["production_checks"])

    def test_postgresql_database_url_enables_django_postgres_app(self):
        settings = self._read_settings(
            "bakerydemo.settings.dev",
            {"DATABASE_URL": ("postgresql://example:secret@localhost:5432/example")},
        )

        self.assertEqual(
            settings["database_engine"],
            "django.db.backends.postgresql",
        )
        self.assertTrue(settings["postgres_app"])

    def test_fast_id_is_disabled_by_default(self):
        production = self._read_settings(
            "bakerydemo.settings.production",
            {"PRIMARY_HOST": "cms.example.com"},
        )

        self.assertFalse(production["fast_id_enabled"])
        self.assertEqual(production["fast_id_timeout"], 5.0)

    def test_production_loads_fast_id_settings_without_printing_secrets(self):
        production = self._read_settings(
            "bakerydemo.settings.production",
            {
                "PRIMARY_HOST": "cms.example.com",
                "FAST_ID_ENABLED": "TrUe",
                "FAST_ID_BASE_URL": "https://fido.example.com",
                "FAST_ID_TENANT_ID": "tenant-id",
                "FAST_ID_TENANT_KEY": "tenant-key",
                "FAST_ID_CLIENT_ID": "client-id",
                "FAST_ID_CLIENT_SECRET": "test-client-secret",
                "FAST_ID_MANAGEMENT_API_TOKEN": "test-management-token",
                "FAST_ID_RP_ID": "example.com",
                "FAST_ID_ORIGIN": "https://login.example.com",
                "FAST_ID_TIMEOUT_SECONDS": "3.5",
            },
        )

        self.assertTrue(production["fast_id_enabled"])
        self.assertEqual(production["fast_id_base_url"], "https://fido.example.com")
        self.assertEqual(production["fast_id_tenant_id"], "tenant-id")
        self.assertEqual(production["fast_id_tenant_key"], "tenant-key")
        self.assertEqual(production["fast_id_client_id"], "client-id")
        self.assertTrue(production["fast_id_has_client_secret"])
        self.assertTrue(production["fast_id_has_management_token"])
        self.assertEqual(production["fast_id_rp_id"], "example.com")
        self.assertEqual(production["fast_id_origin"], "https://login.example.com")
        self.assertEqual(production["fast_id_timeout"], 3.5)
