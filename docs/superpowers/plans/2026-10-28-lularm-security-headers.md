# Lularm Test Security Headers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the two application-owned medium-risk header findings from `www.lularm.com` and keep the third-party Cloudflare Beacon finding outside the ZAP application scope.

**Architecture:** Apply minimal security headers at the test VM's Nginx HTTPS server block, with a timestamped backup and syntax-tested rollback. Keep Cloudflare analytics unchanged and correct the ZAP scan boundary rather than modifying a third-party CORS policy.

**Tech Stack:** Ubuntu, Nginx, Cloudflare, OWASP ZAP 2.17.0

**Spec:** `docs/superpowers/specs/2026-10-28-lularm-security-headers-design.md`

## Global Constraints

- Target only the `www.lularm.com` / `lularm.com` test environment.
- Do not modify databases, application code, Fast-ID settings, or secrets.
- Do not reload Nginx unless `nginx -t` succeeds.
- Keep a recoverable copy of the original Nginx configuration.
- Treat `static.cloudflareinsights.com` as an external service.

## Review Focus

- Nginx `add_header` inheritance must cover Nuxt, Wagtail, static, media, and error responses.
- CSP must not block Fast-ID, APIs, JavaScript, CSS, images, or fonts.
- Wagtail same-origin previews must remain available with `frame-ancestors 'self'` and `SAMEORIGIN`; cross-origin iframe embedding remains blocked.
- Cloudflare must preserve the origin security headers on public responses.
- ZAP must not crawl or report third-party Cloudflare hosts as application-owned findings.

---

### Task 1: Apply Nginx security headers

**Files:**
- Modify on test VM: `/etc/nginx/sites-available/semi-e187`
- Backup on test VM: `/etc/nginx/sites-available/semi-e187.bak-<timestamp>`

**Interfaces:**
- Consumes: Existing HTTPS `server` block for `lularm.com`.
- Produces: Public CSP and `X-Frame-Options` response headers.

- [x] **Step 1: Capture the failing header check**

Run `curl -sSIL https://www.lularm.com/` and confirm the final response lacks
`Content-Security-Policy` and `X-Frame-Options`.

- [x] **Step 2: Back up the active site configuration**

Create a timestamped copy outside `sites-enabled` so Nginx does not load it.

- [x] **Step 3: Add the approved headers to the HTTPS server block**

Add the exact CSP and `X-Frame-Options` values from the design document.

- [x] **Step 4: Validate and reload Nginx**

Run `sudo nginx -t` and reload only when it succeeds. Restore the backup if
validation or the post-reload health check fails.

- [x] **Step 5: Verify public responses and application routes**

Confirm both headers and test the home, English, admin, and account security
routes.

### Task 2: Correct ZAP scan scope

**Files:**
- Modify locally: ZAP context for the lularm test environment.

**Interfaces:**
- Consumes: The existing ZAP session and Cloudflare-injected Beacon URL.
- Produces: A scan restricted to application-owned hosts.

- [x] **Step 1: Include only the application domains**

Use a context include expression covering HTTPS `lularm.com` and
`www.lularm.com`.

- [x] **Step 2: Exclude the Cloudflare Insights host**

Exclude `https://static.cloudflareinsights.com/.*` from the context.

- [ ] **Step 2a: Exclude Cloudflare-managed same-host paths**

Exclude `https://(www\\.)?lularm\\.com/cdn-cgi/.*` from the context so
Cloudflare-generated responses are not attributed to the application origin.

- [ ] **Step 3: Rescan and regenerate the report**

Confirm the Cloudflare CORS alert is absent from the application report and
the two origin header alerts no longer reproduce.

### Task 3: Record evidence and rollback information

**Files:**
- No product files.

**Interfaces:**
- Consumes: Nginx validation, HTTP checks, and ZAP results.
- Produces: A concise completion record without secrets.

- [x] **Step 1: Record the backup path and header values**

Do not record passwords, private keys, API keys, or tokens.

- [x] **Step 2: Check recent Nginx errors**

Run `journalctl -u nginx` for the deployment window and confirm there are no
new errors.

- [x] **Step 3: Report any ZAP rescan limitation separately**

If ZAP cannot be automated or requires user interaction, report the exact
remaining manual step without claiming the third alert is fixed.

### Task 4: Version the Nginx remediation

**Files:**
- Create: `deploy/nginx/semi-e187.conf`
- Create: `bakerydemo/base/tests/test_nginx_deployment_config.py`
- Modify: `docs/SEMI_E187_Fresh_Ubuntu_Server_Setup_zh-TW.md`
- Modify: `docs/superpowers/specs/2026-10-28-lularm-security-headers-design.md`
- Modify: `docs/superpowers/plans/2026-10-28-lularm-security-headers.md`

**Interfaces:**
- Consumes: The verified live `/etc/nginx/sites-available/semi-e187` routing and security-header values.
- Produces: A reviewable Nginx site file and a regression test that prevents removal or regression of the security directives.

- [x] **Step 1: Write the failing deployment-config test**

Assert that `deploy/nginx/semi-e187.conf` exists, contains the exact CSP and
`X-Frame-Options` values via `more_set_headers`, preserves the frontend,
backend, static, media, sitemap, and account-security routes, and does not use
native `add_header` for either security header.

- [x] **Step 2: Run the focused test and confirm RED**

Run `python -m unittest bakerydemo.base.tests.test_nginx_deployment_config -v`.
Expected: fail because the versioned Nginx configuration does not exist.

- [x] **Step 3: Add the versioned Nginx site configuration**

Create `deploy/nginx/semi-e187.conf` from the verified test VM configuration,
including `lularm.com`, the TLS certificate paths, all current proxy routes,
and the two `more_set_headers` directives.

- [x] **Step 4: Document prerequisites and installation**

Update the fresh-Ubuntu guide to install the headers-more module, explain the
versioned test-site file, require a timestamped backup, and retain `nginx -t`
before reload.

- [x] **Step 5: Run focused and repository checks**

Run the focused unit test, `python manage.py check` with test settings, and the
applicable formatting/lint checks. Record any unrelated existing limitation.

- [x] **Step 6: Commit and push only task files**

Stage the exact files listed above, confirm unrelated working-tree changes are
unstaged, commit to `main`, and push `main` to `origin`.
