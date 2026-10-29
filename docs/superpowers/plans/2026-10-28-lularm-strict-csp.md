# Lularm Strict CSP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Emit complete nonce-based security policies from the Nuxt and Django applications, while allowing Nginx to preserve dynamic application headers and retaining safe headers for directly served assets.

**Architecture:** Nuxt SSR owns the public-page CSP and uses a fresh nonce on every response. Django owns security headers for backend routes, while Nginx stops replacing application CSP values and applies a fallback only to responses it serves itself. All work is verified locally; deployment is excluded.

**Tech Stack:** Nuxt 4.5, `nuxt-security` 2.7.0, Node test runner, Django, `django-csp` 3.8, Django test runner, Nginx configuration and HTTP/TLS tests.

**Spec:** `docs/superpowers/specs/2026-10-28-lularm-strict-csp-design.md`

## Global Constraints

- Do not deploy to `lularm.com`, `e187.tw`, or any VM.
- Do not change databases, Fast-ID settings, API secrets, or certificate data.
- Do not treat the Cloudflare Insights CORS response as application-owned.
- Do not weaken script execution with a functional dependency on `unsafe-inline`.
- Preserve same-origin Wagtail preview framing.

## Review Focus

- Root redirect responses must carry CSP and `X-Frame-Options`, not only rendered pages; Task 1 tests both `/` and `/en/`.
- Two SSR requests must not reuse a nonce; Task 1 compares independent responses.
- The nonce in each CSP header must be present on generated inline elements; Task 1 parses the returned HTML.
- Django admin responses must remain same-origin frameable while blocking cross-origin framing; Task 2 checks the emitted policy and `SAMEORIGIN`.
- Nginx must not replace application-generated CSP while static/media responses retain fallback protection; Task 3 tests both boundaries.

---

### Task 1: Nuxt SSR strict CSP

**Files:**
- Modify: `nuxt-bakery-demo/package.json`
- Modify: `nuxt-bakery-demo/package-lock.json`
- Modify: `nuxt-bakery-demo/nuxt.config.ts`
- Create: `nuxt-bakery-demo/tests/integration/security-headers.test.ts`

**Interfaces:**
- Consumes: Nuxt Nitro output at `nuxt-bakery-demo/.output/server/index.mjs`.
- Produces: HTML responses containing an enforced nonce-based CSP and `X-Frame-Options: SAMEORIGIN`.

- [x] **Step 1: Write the failing built-server integration test**

Create a Node test that starts the built Nitro server on a dedicated local port, waits until `/en/` responds, and asserts:

- `/` and `/en/` contain CSP and `X-Frame-Options: SAMEORIGIN`.
- CSP defines `default-src`, `script-src`, `style-src`, `img-src`, `connect-src`, `font-src`, `frame-src`, `media-src`, `manifest-src`, `worker-src`, `form-action`, `object-src`, `base-uri`, and `frame-ancestors`.
- `script-src` contains a nonce and does not contain `unsafe-inline`.
- Inline generated script/style elements carry the response nonce.
- Two `/en/` responses contain different nonces.
- The child server is terminated even when an assertion fails.

- [x] **Step 2: Build and run the test to verify RED**

Run: `npm run test:integration`

Expected: FAIL because the current Nuxt response has no application-owned strict CSP.

- [x] **Step 3: Install and configure `nuxt-security` 2.7.0**

Run: `npm install --save-exact nuxt-security@2.7.0`

Add `nuxt-security` to `modules`, enable SSR nonces, and configure these exact
directives:

- `default-src`: `'self'`
- `script-src`: `'self'`, `'strict-dynamic'`, `'nonce-{{nonce}}'`
- `script-src-attr`: `'none'`
- `style-src`: `'self'`, `'nonce-{{nonce}}'`
- `style-src-attr`: `'none'`
- `img-src`: `'self'`, `data:`, `blob:`
- `connect-src`: `'self'`
- `font-src`: `'self'`, `data:`
- `frame-src`: `'self'`, `https://www.youtube-nocookie.com`, `https://player.vimeo.com`
- `media-src`: `'self'`
- `manifest-src`: `'self'`
- `worker-src`: `'self'`, `blob:`
- `form-action`: `'self'`
- `object-src`: `'none'`
- `base-uri`: `'self'`
- `frame-ancestors`: `'self'`

Preserve the existing i18n, runtime configuration, API proxy, and prerender
settings.

- [x] **Step 4: Rebuild and run the integration test to verify GREEN**

Run: `npm run test:integration`

Expected: PASS with unique matching nonces and no missing directive.

- [x] **Step 5: Run existing frontend tests and type checking**

Run: `npm test`

Run: `npm run typecheck`

Expected: all existing tests pass and type checking exits 0.

- [x] **Step 6: Commit the Nuxt deliverable**

```bash
git add nuxt-bakery-demo/package.json nuxt-bakery-demo/package-lock.json nuxt-bakery-demo/nuxt.config.ts nuxt-bakery-demo/tests/integration/security-headers.test.ts
git commit -m "fix: enforce strict CSP in Nuxt"
```

### Task 2: Django/Wagtail response security policy

**Files:**
- Modify: `bakerydemo/settings/production.py`
- Modify: `bakerydemo/account_security/tests/test_settings.py`
- Create: `bakerydemo/account_security/tests/test_response_security_headers.py`

**Interfaces:**
- Consumes: `csp.middleware.CSPMiddleware` and Django `XFrameOptionsMiddleware`.
- Produces: enforced backend CSP plus `X-Frame-Options: SAMEORIGIN` without changing authentication or Fast-ID behavior.

- [x] **Step 1: Extend production-settings tests and add a response test**

Assert that production settings install CSP middleware in the response path, disable report-only mode, define the same explicit resource/form/base/frame directives, and retain `X_FRAME_OPTIONS = "SAMEORIGIN"`. Exercise the actual middleware around a real `HttpResponse` and assert the emitted headers.

- [x] **Step 2: Run focused tests to verify RED**

Run: `python manage.py test bakerydemo.account_security.tests.test_settings bakerydemo.account_security.tests.test_response_security_headers --settings=bakerydemo.settings.test`

Expected: FAIL because production currently does not unconditionally enforce the complete policy.

- [x] **Step 3: Configure production CSP minimally**

Place request-local CSP and clickjacking middleware outside short-circuiting
redirect middleware. Authorize trusted Wagtail inline initializers, theme JS,
and admin CSS with request nonces; leave arbitrary injected scripts unauthorized.
Keep same-origin scripts/styles and the supported YouTube/Vimeo frame origins.
Set `CSP_REPORT_ONLY = False` and `X_FRAME_OPTIONS = "SAMEORIGIN"`.
Do not alter dev/test HTTPS behavior.

- [x] **Step 4: Run focused tests to verify GREEN**

Run: `python manage.py test bakerydemo.account_security.tests.test_settings bakerydemo.account_security.tests.test_response_security_headers --settings=bakerydemo.settings.test`

Expected: PASS.

- [x] **Step 5: Run Django system checks**

Run: `python manage.py check --settings=bakerydemo.settings.test`

Expected: no issues.

- [x] **Step 6: Commit the Django deliverable**

```bash
git add bakerydemo/settings/production.py bakerydemo/account_security/tests/test_settings.py bakerydemo/account_security/tests/test_response_security_headers.py
git commit -m "fix: enforce backend security headers"
```

### Task 3: Nginx header ownership boundary

**Files:**
- Modify: `deploy/nginx/semi-e187.conf`
- Modify: `bakerydemo/base/tests/test_nginx_deployment_config.py`
- Create: `bakerydemo/base/tests/test_nginx_response_headers.py`

**Interfaces:**
- Consumes: application-generated CSP and clickjacking headers from Tasks 1 and 2.
- Produces: proxy routes that preserve those headers and direct asset routes with fallback protection.

- [x] **Step 1: Replace the old structural header assertion with boundary assertions**

Assert that the HTTPS server preserves upstream CSP/X-Frame-Options through conditional maps, and `/static/`, `/media/`, redirects and Nginx-generated errors receive fallback protection. Verify actual HTTP/TLS responses as well as configuration structure.

- [x] **Step 2: Run the Nginx regression test to verify RED**

Run: `python -m unittest bakerydemo.base.tests.test_nginx_deployment_config -v`

Expected: FAIL because the current server block globally replaces CSP.

- [x] **Step 3: Update the versioned Nginx configuration**

Replace the global fixed policy with maps that retain the upstream policy verbatim when present and supply a defensive fallback when absent. Keep proxy routing unchanged. Cover direct assets, redirects, 413 and 502 responses.

- [x] **Step 4: Run the Nginx regression test to verify GREEN**

Run: `python -m unittest bakerydemo.base.tests.test_nginx_deployment_config -v`

Expected: PASS.

- [x] **Step 5: Commit the Nginx deliverable**

```bash
git add deploy/nginx/semi-e187.conf bakerydemo/base/tests/test_nginx_deployment_config.py
git commit -m "fix: preserve application CSP at proxy"
```

### Task 4: Local-only end-to-end verification

**Files:**
- Modify: `docs/superpowers/plans/2026-10-28-lularm-strict-csp.md`
- Modify: `docs/superpowers/specs/2026-10-28-lularm-strict-csp-design.md`
- Create: `docs/SEMI_E187_Strict_CSP_Local_Verification_zh-TW.md`

**Interfaces:**
- Consumes: all deliverables from Tasks 1-3.
- Produces: recorded local evidence and no deployment side effects.

- [x] **Step 1: Run the complete local verification set**

Run the Nuxt build/integration test, existing Nuxt tests, type check, focused Django tests, Django system check, Nginx regression tests, Ruff on changed Python files, and Prettier on changed TypeScript/config files.

Expected: every locally runnable command exits 0. Run the full Django suite with an isolated in-memory SQLite database and explicitly set `NGINX_TEST_BINARY` so runtime Nginx tests are not skipped.

- [x] **Step 2: Inspect the final diff and confirm the deployment gate**

Run: `git diff --check`

Run: `git status --short`

Expected: only Strict CSP implementation, compatibility tests and verification documentation are changed in this worktree. No Strict CSP artifact is deployed. The separately authorized temporary IP-access task is outside this plan.

- [x] **Step 3: Request independent review and resolve findings once**

Review focus: nonce correctness, Wagtail compatibility, header ownership, process cleanup, and accidental deployment/config-secret changes.

- [x] **Step 4: Mark the plan complete and report local results**

Update this plan's checkboxes only after fresh verification. Do not deploy; ask for separate approval before any test-environment update.

## Completion evidence — 2026-10-29

Tasks 1–4 and the independent-review fix pass are complete locally. The final
run passed 357 Django tests (including 8 Nginx checks), 93 Nuxt unit tests,
1 freshly built Nitro integration test, type checking, system/migration
checks and targeted formatting. Offline runtime execution passed in isolated
headless Chrome. Details, review findings, rulings and deployment limitations:
`docs/SEMI_E187_Strict_CSP_Local_Verification_zh-TW.md`.

No Strict CSP artifacts were deployed. Keep the branch/worktree for inspection;
the active sites' separately configured IP gates remain unchanged.
