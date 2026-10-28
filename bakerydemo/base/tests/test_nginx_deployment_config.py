from pathlib import Path
from unittest import TestCase

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
NGINX_SITE = REPOSITORY_ROOT / "deploy" / "nginx" / "semi-e187.conf"


class NginxDeploymentConfigTests(TestCase):
    def setUp(self):
        self.config = NGINX_SITE.read_text(encoding="utf-8")

    def test_security_headers_do_not_depend_on_add_header_inheritance(self):
        self.assertIn(
            'more_set_headers "Content-Security-Policy: frame-ancestors '
            "'self'; object-src 'none'; base-uri 'self';\";",
            self.config,
        )
        self.assertIn(
            'more_set_headers "X-Frame-Options: SAMEORIGIN";',
            self.config,
        )
        self.assertNotIn("frame-ancestors 'none'", self.config)
        self.assertNotIn("X-Frame-Options: DENY", self.config)
        self.assertNotIn("add_header Content-Security-Policy", self.config)
        self.assertNotIn("add_header X-Frame-Options", self.config)

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
