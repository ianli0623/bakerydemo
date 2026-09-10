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
}}))
'''
        environment = os.environ.copy()
        for key in (
            "PRIMARY_HOST",
            "SECURE_SSL_REDIRECT",
            "SECURE_HSTS_SECONDS",
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
