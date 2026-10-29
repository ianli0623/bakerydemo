import re
from pathlib import Path
from unittest import TestCase

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
NGINX_SITE = REPOSITORY_ROOT / "deploy" / "nginx" / "semi-e187.conf"


class NginxDeploymentConfigTests(TestCase):
    def setUp(self):
        self.config = NGINX_SITE.read_text(encoding="utf-8")

    def test_https_proxy_preserves_application_security_headers(self):
        https_server = self.config.split("listen 443 ssl;", 1)[1]
        server_directives = https_server.split("location ", 1)[0]
        self.assertNotIn("Content-Security-Policy:", server_directives)
        self.assertNotIn("X-Frame-Options:", server_directives)

        locations = re.findall(r"location [^{]+\{([^{}]*)\}", https_server)
        proxy_locations = [body for body in locations if "proxy_pass" in body]
        self.assertGreaterEqual(len(proxy_locations), 5)
        for body in proxy_locations:
            with self.subTest(location=body.splitlines()[1].strip()):
                self.assertNotRegex(
                    body, r"(?:more_set_headers|add_header).*Content-Security-Policy"
                )
                self.assertNotRegex(
                    body, r"(?:more_set_headers|add_header).*X-Frame-Options"
                )
                self.assertNotIn("proxy_hide_header Content-Security-Policy", body)

    def test_direct_assets_have_complete_fallback_headers(self):
        for route in ("/static/", "/media/"):
            with self.subTest(route=route):
                match = re.search(
                    r"location " + re.escape(route) + r" \{([^{}]*)\}",
                    self.config,
                )
                self.assertIsNotNone(match)
                body = match[1]
                for directive in (
                    "default-src 'none'",
                    "base-uri 'none'",
                    "object-src 'none'",
                    "form-action 'none'",
                    "frame-ancestors 'self'",
                    "X-Frame-Options: SAMEORIGIN",
                    "X-Content-Type-Options: nosniff",
                ):
                    self.assertIn(directive, body)

    def test_versioned_site_preserves_the_live_routing_contract(self):
        expected_fragments = (
            "server_name lularm.com www.lularm.com;",
            "alias /srv/semi-e187/app/bakerydemo/collect_static/;",
            "alias /srv/semi-e187/app/bakerydemo/media/;",
            "location ^~ /account/security/",
            "location ~ ^/(admin|django-admin|api/v2|images|documents)(/|$)",
            "location = /api/site-settings/",
            "location = /sitemap.xml",
            "proxy_pass http://127.0.0.1:8000;",
            "proxy_pass http://127.0.0.1:3100;",
        )

        for fragment in expected_fragments:
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, self.config)

    def test_https_server_uses_the_current_http2_directive(self):
        self.assertIn("http2 on;", self.config)
        self.assertNotRegex(self.config, r"listen [^;]*\bhttp2;")
