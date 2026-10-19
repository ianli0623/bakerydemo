# E187 Production Domain Cutover Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Serve the Nuxt frontend at `https://e187.tw/` and the Django/Wagtail backend at `https://e187.tw/admin/`, while accepting both `e187.tw` and `www.e187.tw` on `semi187-portal`.

**Architecture:** Preserve the existing systemd services and Nginx path routing. Update the public-domain settings and the existing `/etc/nginx/sites-available/semi-e187` virtual host, retaining backups so the change can be rolled back immediately.

**Tech Stack:** Ubuntu, Nginx, systemd, Nuxt, Django/Wagtail, Cloudflare or customer gateway HTTP origin forwarding.

**Spec:** Current user request in this chat.

## Global Constraints

- Do not expose secrets from `/etc/semi-e187/backend.env`.
- Back up every production configuration file before editing it.
- Validate configuration before reload or restart.
- Keep `semi-e187-backend`, `semi-e187-frontend`, and `nginx` available throughout the cutover.
- Public frontend URL is `https://e187.tw/`; public backend URL is `https://e187.tw/admin/`.
- Both `e187.tw` and `www.e187.tw` must reach the same Nginx virtual host.

## Review Focus

- Host header acceptance for both domains.
- Correct separation of backend paths and frontend catch-all routing.
- Django host and canonical URL configuration.
- Fast-ID RP ID and Origin alignment with the production domain.
- Safe rollback if Nginx or application checks fail.

---

### Task 1: Preflight and Baseline

**Files:**
- Inspect: `/etc/nginx/sites-available/semi-e187`
- Inspect: `/etc/semi-e187/backend.env`
- Inspect: `/etc/semi-e187/frontend.env`

**Interfaces:**
- Consumes: Existing active systemd services and current Nginx route layout.
- Produces: A verified baseline and exact settings to change.

- [ ] Verify Nginx routes, active services, listening ports, and current public-domain environment values without printing secrets.
- [ ] Verify `e187.tw` and `www.e187.tw` resolve and reach the customer gateway.

### Task 2: Apply Production Domain Configuration

**Files:**
- Modify: `/etc/nginx/sites-available/semi-e187`
- Modify: `/etc/semi-e187/backend.env`
- Modify: `/etc/semi-e187/frontend.env`

**Interfaces:**
- Consumes: Baseline values from Task 1.
- Produces: Both domains accepted by Nginx, Django canonical host `e187.tw`, Nuxt API base `https://e187.tw`, and Fast-ID origin/RP settings aligned with `e187.tw`.

- [ ] Create timestamped backups of all files that will change.
- [ ] Set Nginx `server_name e187.tw www.e187.tw` while preserving existing path routing.
- [ ] Set Django allowed/canonical host and Fast-ID domain values to the production domain.
- [ ] Set the Nuxt backend base URL to `https://e187.tw`.
- [ ] Run `nginx -t` and Django deployment checks before activating changes.
- [ ] Reload Nginx and restart only the application services whose environment changed.

### Task 3: End-to-End Verification

**Files:**
- Verify: `/etc/nginx/sites-available/semi-e187`
- Verify: `/etc/semi-e187/backend.env`
- Verify: `/etc/semi-e187/frontend.env`

**Interfaces:**
- Consumes: Activated configuration from Task 2.
- Produces: Evidence that frontend, backend, services, and both domains work.

- [ ] Confirm all three services are active and ports `80`, `8000`, and `3100` are listening.
- [ ] Confirm local Host-header requests route `/` to Nuxt and `/admin/` to Django for both domains.
- [ ] Confirm public `https://e187.tw/`, `https://www.e187.tw/`, and `https://e187.tw/admin/` return expected non-error responses.
- [ ] Record any remaining external Fast-ID or Cloudflare configuration dependency.
