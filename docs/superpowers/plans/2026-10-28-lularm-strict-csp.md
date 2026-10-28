# Lularm Strict CSP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Emit complete nonce-based security policies from the Nuxt and Django applications, while allowing Nginx to preserve dynamic application headers and retaining safe headers for directly served assets.

**Architecture:** Nuxt SSR owns the public-page CSP and uses a fresh nonce on every response. Django owns security headers for backend routes, while Nginx stops replacing application CSP values and applies a fallback only to responses it serves itself. All work is verified locally; deployment is excluded.

**Tech Stack:** Nuxt 4.5, `nuxt-security` 2.7.0, Node test runner, Django, `django-csp` 3.8, Python `unittest`, Nginx configuration tests.

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
- Create: `nuxt-bakery-demo/tests/security-headers.integration.test.ts`

**Interfaces:**
- Consumes: Nuxt Nitro output at `nuxt-bakery-demo/.output/server/index.mjs`.
- Produces: HTML responses containing an enforced nonce-based CSP and `X-Frame-Options: SAMEORIGIN`.

- [ ] **Step 1: Write the failing built-server integration test**

Create a Node test that starts the built Nitro server on a dedicated local port, waits until `/en/` responds, and asserts:

- `/` and `/en/` contain CSP and `X-Frame-Options: SAMEORIGIN`.
- CSP defines `default-src`, `script-src`, `style-src`, `img-src`, `connect-src`, `font-src`, `frame-src`, `media-src`, `manifest-src`, `worker-src`, `form-action`, `object-src`, `base-uri`, and `frame-ancestors`.
- `script-src` contains a nonce and does not contain `unsafe-inline`.
- Inline generated script/style elements carry the response nonce.
- Two `/en/` responses contain different nonces.
- The child server is terminated even when an assertion fails.

- [ ] **Step 2: Build and run the test to verify RED**

Run: `npm run build && node --test --experimental-strip-types tests/security-headers.integration.test.ts`

Expected: FAIL because the current Nuxt response has no application-owned strict CSP.

- [ ] **Step 3: Install and configure `nuxt-security` 2.7.0**

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
- `frame-src`: `'self'`
- `media-src`: `'self'`
- `manifest-src`: `'self'`
- `worker-src`: `'self'`, `blob:`
- `form-action`: `'self'`
- `object-src`: `'none'`
- `base-uri`: `'self'`
- `frame-ancestors`: `'self'`

Preserve the existing i18n, runtime configuration, API proxy, and prerender
settings.

- [ ] **Step 4: Rebuild and run the integration test to verify GREEN**

Run: `npm run build && node --test --experimental-strip-types tests/security-headers.integration.test.ts`

Expected: PASS with unique matching nonces and no missing directive.

- [ ] **Step 5: Run existing frontend tests and type checking**

Run: `npm test`

Run: `npm run typecheck`

Expected: all existing tests pass and type checking exits 0.

- [ ] **Step 6: Commit the Nuxt deliverable**

```bash
git add nuxt-bakery-demo/package.json nuxt-bakery-demo/package-lock.json nuxt-bakery-demo/nuxt.config.ts nuxt-bakery-demo/tests/security-headers.integration.test.ts
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

- [ ] **Step 1: Extend production-settings tests and add a response test**

Assert that production settings install CSP middleware in the response path, disable report-only mode, define the same explicit resource/form/base/frame directives, and retain `X_FRAME_OPTIONS = "SAMEORIGIN"`. Exercise the actual middleware around a real `HttpResponse` and assert the emitted headers.

- [ ] **Step 2: Run focused tests to verify RED**

Run: `python -m unittest bakerydemo.account_security.tests.test_settings bakerydemo.account_security.tests.test_response_security_headers -v`

Expected: FAIL because production currently does not unconditionally enforce the complete policy.

- [ ] **Step 3: Configure production CSP minimally**

Insert CSP middleware before clickjacking middleware and set the same explicit
resource/form/base/frame directives as Task 1, except Django uses
`script-src 'self'` and `style-src 'self'` because the Wagtail templates load
their executable scripts and styles from same-origin static URLs. Set
`CSP_REPORT_ONLY = False` and `X_FRAME_OPTIONS = "SAMEORIGIN"`. Do not alter
dev/test HTTPS behavior.

- [ ] **Step 4: Run focused tests to verify GREEN**

Run: `python -m unittest bakerydemo.account_security.tests.test_settings bakerydemo.account_security.tests.test_response_security_headers -v`

Expected: PASS.

- [ ] **Step 5: Run Django system checks**

Run: `python manage.py check --settings=bakerydemo.settings.test`

Expected: no issues.

- [ ] **Step 6: Commit the Django deliverable**

```bash
git add bakerydemo/settings/production.py bakerydemo/account_security/tests/test_settings.py bakerydemo/account_security/tests/test_response_security_headers.py
git commit -m "fix: enforce backend security headers"
```

### Task 3: Nginx header ownership boundary

**Files:**
- Modify: `deploy/nginx/semi-e187.conf`
- Modify: `bakerydemo/base/tests/test_nginx_deployment_config.py`

**Interfaces:**
- Consumes: application-generated CSP and clickjacking headers from Tasks 1 and 2.
- Produces: proxy routes that preserve those headers and direct asset routes with fallback protection.

- [ ] **Step 1: Replace the old structural header assertion with boundary assertions**

Assert that the HTTPS server has no global fixed CSP or X-Frame-Options override, proxy locations do not replace application CSP, and `/static/` plus `/media/` receive complete fallback CSP, `SAMEORIGIN`, and `X-Content-Type-Options: nosniff`.

- [ ] **Step 2: Run the Nginx regression test to verify RED**

Run: `python -m unittest bakerydemo.base.tests.test_nginx_deployment_config -v`

Expected: FAIL because the current server block globally replaces CSP.

- [ ] **Step 3: Update the versioned Nginx configuration**

Remove the global fixed security-header override, keep proxy routing unchanged, and apply fallback headers only inside direct static/media locations.

- [ ] **Step 4: Run the Nginx regression test to verify GREEN**

Run: `python -m unittest bakerydemo.base.tests.test_nginx_deployment_config -v`

Expected: PASS.

- [ ] **Step 5: Commit the Nginx deliverable**

```bash
git add deploy/nginx/semi-e187.conf bakerydemo/base/tests/test_nginx_deployment_config.py
git commit -m "fix: preserve application CSP at proxy"
```

### Task 4: Local-only end-to-end verification

**Files:**
- Modify: `docs/superpowers/plans/2026-10-28-lularm-strict-csp.md`

**Interfaces:**
- Consumes: all deliverables from Tasks 1-3.
- Produces: recorded local evidence and no deployment side effects.

- [ ] **Step 1: Run the complete local verification set**

Run the Nuxt build/integration test, existing Nuxt tests, type check, focused Django tests, Django system check, Nginx regression tests, Ruff on changed Python files, and Prettier on changed TypeScript/config files.

Expected: every locally runnable command exits 0. Report any full-suite database permission limitation separately rather than hiding it.

- [ ] **Step 2: Inspect the final diff and confirm the deployment gate**

Run: `git diff --check`

Run: `git status --short`

Expected: only planned files plus the pre-existing unrelated documentation changes are present; no VM, SSH, PuTTY, or deployment command was executed.

- [ ] **Step 3: Request independent review and resolve findings once**

Review focus: nonce correctness, Wagtail compatibility, header ownership, process cleanup, and accidental deployment/config-secret changes.

- [ ] **Step 4: Mark the plan complete and report local results**

Update this plan's checkboxes only after fresh verification. Do not deploy; ask for separate approval before any test-environment update.

