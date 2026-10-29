"""Run against a local Nginx/OpenResty with headers-more when configured."""

import http.client
import ipaddress
import os
import secrets
import socket
import ssl
import subprocess
import tempfile
import threading
import time
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import TestCase, skipUnless

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

NGINX_BINARY = os.environ.get("NGINX_TEST_BINARY")
SITE_FILE = Path(__file__).resolve().parents[3] / "deploy/nginx/semi-e187.conf"


class ApplicationHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        nonce = secrets.token_urlsafe(24)
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header(
            "Content-Security-Policy",
            f"default-src 'self'; script-src 'nonce-{nonce}'; "
            "form-action 'self'; frame-ancestors 'self';",
        )
        self.send_header("X-Frame-Options", "SAMEORIGIN")
        self.end_headers()
        self.wfile.write(f'<script nonce="{nonce}"></script>'.encode())

    def log_message(self, _format, *args):
        pass


def free_port():
    with socket.socket() as connection:
        connection.bind(("127.0.0.1", 0))
        return connection.getsockname()[1]


@skipUnless(NGINX_BINARY, "Set NGINX_TEST_BINARY to a local headers-more Nginx")
class NginxResponseHeadersTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.scratch = tempfile.TemporaryDirectory(prefix="csp-nginx-")
        cls.addClassCleanup(cls.scratch.cleanup)
        cls.root = Path(cls.scratch.name)
        for directory in ("static", "media", "logs"):
            (cls.root / directory).mkdir()
        (cls.root / "static/example.css").write_text("body { color: black; }")
        (cls.root / "media/example.txt").write_text("example")

        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
        certificate = (
            x509.CertificateBuilder()
            .subject_name(name)
            .issuer_name(name)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.now(UTC) - timedelta(minutes=1))
            .not_valid_after(datetime.now(UTC) + timedelta(hours=1))
            .add_extension(
                x509.SubjectAlternativeName(
                    [x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]
                ),
                critical=False,
            )
            .sign(key, hashes.SHA256())
        )
        cert_file = cls.root / "cert.pem"
        cert_file.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
        (cls.root / "key.pem").write_bytes(
            key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            )
        )
        cls.tls = ssl.create_default_context(cafile=str(cert_file))

        upstream = ThreadingHTTPServer(("127.0.0.1", 0), ApplicationHandler)
        upstream.daemon_threads = True
        cls.addClassCleanup(upstream.server_close)
        cls.addClassCleanup(upstream.shutdown)
        threading.Thread(target=upstream.serve_forever, daemon=True).start()
        cls.http_port, cls.https_port = free_port(), free_port()
        site = SITE_FILE.read_text(encoding="utf-8")
        replacements = {
            "listen 80;": f"listen 127.0.0.1:{cls.http_port};",
            "listen [::]:80;": "",
            "listen 443 ssl;": f"listen 127.0.0.1:{cls.https_port} ssl;",
            "listen [::]:443 ssl;": "",
            "/etc/letsencrypt/live/lularm.com/fullchain.pem": cert_file.as_posix(),
            "/etc/letsencrypt/live/lularm.com/privkey.pem": (
                cls.root / "key.pem"
            ).as_posix(),
            "/srv/semi-e187/app/bakerydemo/collect_static/": (
                cls.root / "static"
            ).as_posix()
            + "/",
            "/srv/semi-e187/app/bakerydemo/media/": (cls.root / "media").as_posix()
            + "/",
            "127.0.0.1:8000": f"127.0.0.1:{upstream.server_port}",
            "127.0.0.1:3100": f"127.0.0.1:{upstream.server_port}",
        }
        for old, new in replacements.items():
            site = site.replace(old, new)
        config = cls.root / "nginx.conf"
        config.write_text(
            "worker_processes 1; daemon off; master_process off; "
            "pid nginx.pid; error_log logs/error.log; "
            "events { worker_connections 64; } "
            "http { access_log off; " + site + " }",
            encoding="utf-8",
        )
        cls.command = [NGINX_BINARY, "-p", cls.root.as_posix() + "/", "-c", str(config)]
        subprocess.run(cls.command + ["-t"], check=True, capture_output=True)
        cls.process = subprocess.Popen(
            cls.command,
            cwd=cls.root,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        cls.addClassCleanup(cls.stop_nginx)
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            try:
                with socket.create_connection(("127.0.0.1", cls.https_port), 0.2):
                    return
            except OSError:
                if cls.process.poll() is not None:
                    raise RuntimeError((cls.root / "logs/error.log").read_text()) from None
                time.sleep(0.05)
        raise TimeoutError("Local Nginx did not start")

    @classmethod
    def stop_nginx(cls):
        if cls.process.poll() is None:
            subprocess.run(cls.command + ["-s", "quit"], capture_output=True)
            try:
                cls.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                cls.process.kill()
                cls.process.wait(timeout=5)

    def request(self, path, secure=True):
        connection = (
            http.client.HTTPSConnection(
                "127.0.0.1", self.https_port, context=self.tls, timeout=5
            )
            if secure
            else http.client.HTTPConnection("127.0.0.1", self.http_port, timeout=5)
        )
        try:
            connection.request("GET", path, headers={"Host": "lularm.com"})
            response = connection.getresponse()
            return (
                response.status,
                dict(response.getheaders()),
                response.read().decode(),
            )
        finally:
            connection.close()

    def test_proxy_routes_preserve_upstream_nonce_and_fido_cache_headers(self):
        for path in ("/en/", "/admin/", "/account/security/windows-hello/login/"):
            with self.subTest(path=path):
                status, headers, body = self.request(path)
                self.assertEqual(status, 200)
                nonce = body.split('nonce="')[1].split('"')[0]
                self.assertIn(
                    "'nonce-" + nonce + "'", headers["Content-Security-Policy"]
                )
                self.assertEqual(headers["X-Frame-Options"], "SAMEORIGIN")
                if path.startswith("/account/security/"):
                    self.assertEqual(headers["Cache-Control"], "no-store")

    def test_assets_and_missing_assets_receive_fallback_headers(self):
        for path, expected in (
            ("/static/example.css", 200),
            ("/media/example.txt", 200),
            ("/static/missing.css", 404),
            ("/media/missing.txt", 404),
        ):
            with self.subTest(path=path):
                status, headers, _body = self.request(path)
                self.assertEqual(status, expected)
                self.assertIn("default-src 'none'", headers["Content-Security-Policy"])
                self.assertIn("form-action 'none'", headers["Content-Security-Policy"])
                self.assertEqual(headers["X-Frame-Options"], "SAMEORIGIN")
                self.assertEqual(headers["X-Content-Type-Options"], "nosniff")

    def test_http_redirect_receives_fallback_headers(self):
        status, headers, _body = self.request("/en/", secure=False)
        self.assertEqual(status, 301)
        self.assertEqual(headers["Location"], "https://lularm.com/en/")
        self.assertIn("default-src 'none'", headers["Content-Security-Policy"])
