from django.http import HttpResponse
from django.middleware.clickjacking import XFrameOptionsMiddleware
from django.test import RequestFactory, SimpleTestCase, override_settings

from csp.middleware import CSPMiddleware


@override_settings(
    CSP_REPORT_ONLY=False,
    CSP_DEFAULT_SRC=("'self'",),
    CSP_SCRIPT_SRC=("'self'",),
    CSP_SCRIPT_SRC_ATTR=("'none'",),
    CSP_STYLE_SRC=("'self'",),
    CSP_STYLE_SRC_ATTR=("'none'",),
    CSP_IMG_SRC=("'self'", "data:", "blob:"),
    CSP_CONNECT_SRC=("'self'",),
    CSP_FONT_SRC=("'self'", "data:"),
    CSP_FRAME_SRC=("'self'",),
    CSP_MEDIA_SRC=("'self'",),
    CSP_MANIFEST_SRC=("'self'",),
    CSP_WORKER_SRC=("'self'", "blob:"),
    CSP_FORM_ACTION=("'self'",),
    CSP_OBJECT_SRC=("'none'",),
    CSP_BASE_URI=("'self'",),
    CSP_FRAME_ANCESTORS=("'self'",),
    CSP_UPGRADE_INSECURE_REQUESTS=True,
    X_FRAME_OPTIONS="SAMEORIGIN",
)
class ResponseSecurityHeadersTests(SimpleTestCase):
    def test_django_middleware_emits_complete_enforced_headers(self):
        request = RequestFactory().get("/admin/")
        get_response = CSPMiddleware(
            XFrameOptionsMiddleware(lambda _request: HttpResponse("ok"))
        )

        response = get_response(request)

        self.assertEqual(response.headers["X-Frame-Options"], "SAMEORIGIN")
        self.assertNotIn("Content-Security-Policy-Report-Only", response.headers)
        policy = response.headers["Content-Security-Policy"]
        expected_directives = (
            "default-src 'self'",
            "script-src 'self'",
            "script-src-attr 'none'",
            "style-src 'self'",
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
        )
        for directive in expected_directives:
            with self.subTest(directive=directive):
                self.assertIn(directive, policy)

        self.assertNotIn("'unsafe-inline'", policy)
