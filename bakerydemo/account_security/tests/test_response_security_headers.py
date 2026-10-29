from functools import lru_cache
from html.parser import HTMLParser
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.middleware.clickjacking import XFrameOptionsMiddleware
from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.urls import reverse
from django.utils.module_loading import import_string
from wagtail.admin.widgets import AdminDateInput
from wagtail.images.widgets import AdminImageChooser
from wagtail.models import Page

from bakerydemo.account_security.services import sync_password_change
from bakerydemo.base.models import HomePage

from . import test_settings as settings_tests


@lru_cache(maxsize=1)
def production_security_settings():
    production = settings_tests.AccountSecuritySettingsTests()._read_settings(
        "bakerydemo.settings.production", {"PRIMARY_HOST": "cms.example.com"}
    )
    return {
        **production["csp_configuration"],
        "MIDDLEWARE": production["middleware"],
        "X_FRAME_OPTIONS": production["x_frame_options"],
        "SECURE_SSL_REDIRECT": True,
    }


class InlineElements(HTMLParser):
    def __init__(self):
        super().__init__()
        self.elements = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "style" or (
            tag == "script"
            and "src" not in attrs
            and attrs.get("type", "text/javascript") in ("text/javascript", "module")
        ):
            self.elements.append(attrs)


class ResponseSecurityHeadersTests(SimpleTestCase):
    def setUp(self):
        self.config = production_security_settings()
        overrides = self.settings(**self.config)
        overrides.enable()
        self.addCleanup(overrides.disable)
        self.middleware = import_string(
            next(name for name in self.config["MIDDLEWARE"] if "CSPMiddleware" in name)
        )

    def test_django_middleware_emits_complete_enforced_headers(self):
        request = RequestFactory().get("/admin/")
        response = self.middleware(
            XFrameOptionsMiddleware(lambda _request: HttpResponse("ok"))
        )(request)

        self.assertEqual(response.headers["X-Frame-Options"], "SAMEORIGIN")
        self.assertNotIn("Content-Security-Policy-Report-Only", response.headers)
        policy = response.headers["Content-Security-Policy"]
        for directive in (
            "default-src 'self'",
            "script-src 'self'",
            "style-src 'self'",
            "script-src-attr 'none'",
            "style-src-attr 'none'",
            "img-src 'self' data: blob:",
            "connect-src 'self'",
            "font-src 'self' data:",
            "frame-src 'self'",
            "media-src 'self'",
            "manifest-src 'self'",
            "worker-src 'self' blob:",
            "form-action 'self'",
            "object-src 'none'",
            "base-uri 'self'",
            "frame-ancestors 'self'",
            "upgrade-insecure-requests",
        ):
            with self.subTest(directive=directive):
                self.assertIn(directive, policy)
        self.assertNotIn("'unsafe-inline'", policy)

    def test_trusted_wagtail_widgets_receive_nonce_but_injected_script_does_not(self):
        def render_widgets(_request):
            html = AdminDateInput().render("date", None, attrs={"id": "id_date"})
            html += AdminImageChooser().render("image", None, attrs={"id": "id_image"})
            html += render_to_string(
                "wagtailadmin/panels/inline_panel.html",
                {
                    "self": SimpleNamespace(
                        formset=SimpleNamespace(
                            prefix="items", management_form="", non_form_errors=[]
                        ),
                        children=[],
                        empty_child=None,
                    ),
                    "options_json": '{"formsetPrefix":"items"}',
                },
            )
            html += '<script id="untrusted">alert(1)</script>'
            return HttpResponse(html)

        response = self.middleware(render_widgets)(RequestFactory().get("/admin/"))
        parser = InlineElements()
        parser.feed(response.content.decode())
        trusted = [item for item in parser.elements if item.get("id") != "untrusted"]
        self.assertGreaterEqual(len(trusted), 3)
        for item in trusted:
            self.assertTrue(item.get("nonce"), item)
            self.assertIn(
                "'nonce-" + item["nonce"] + "'", response["Content-Security-Policy"]
            )
        self.assertNotIn("nonce", parser.elements[-1])


class BackendRedirectSecurityTests(TestCase):
    def setUp(self):
        overrides = self.settings(**production_security_settings())
        overrides.enable()
        self.addCleanup(overrides.disable)
        self.user = get_user_model().objects.create_superuser(
            username="csp-admin",
            email="csp-admin@example.com",
            password="Temporary-Password-1!",
        )
        self.client.force_login(self.user)

    def test_security_headers_cover_password_policy_and_common_redirects(self):
        for path, status in (("/admin/", 302), ("/admin", 301)):
            with self.subTest(path=path):
                response = self.client.get(path, secure=True)
                self.assertEqual(response.status_code, status)
                self.assertIn("Content-Security-Policy", response)
                self.assertEqual(response.get("X-Frame-Options"), "SAMEORIGIN")

    def test_https_redirect_also_receives_security_headers(self):
        response = self.client.get("/admin/")
        self.assertEqual(response.status_code, 301)
        self.assertIn("Content-Security-Policy", response)
        self.assertEqual(response.get("X-Frame-Options"), "SAMEORIGIN")

    def test_real_page_editor_has_authorized_inline_scripts_and_styles(self):
        sync_password_change(self.user, must_change_password=False)
        page = Page.get_first_root_node().add_child(
            instance=HomePage(
                title="CSP editor test",
                slug="csp-editor-test",
                hero_text="CSP test",
                hero_cta="Read more",
            )
        )
        response = self.client.get(
            reverse("wagtailadmin_pages:edit", args=[page.pk]), secure=True
        )
        self.assertEqual(response.status_code, 200)
        parser = InlineElements()
        parser.feed(response.content.decode())
        self.assertGreater(len(parser.elements), 0)
        for item in parser.elements:
            self.assertTrue(item.get("nonce"), item)
            self.assertIn(
                "'nonce-" + item["nonce"] + "'", response["Content-Security-Policy"]
            )
