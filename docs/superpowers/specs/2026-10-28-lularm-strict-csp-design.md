# Lularm Strict CSP Security Headers Design

## Intent

Resolve the application-owned medium-risk findings in the ZAP report generated
on 2026-10-28 at 15:39 without breaking Nuxt rendering, Wagtail previews,
Fast-ID, or the certificate API. Complete and verify the work locally before
any deployment to `www.lularm.com`.

## Evidence and root cause

The new report contains seven medium-risk alerts:

- Four alerts report an incomplete CSP: missing `form-action`, missing resource
  directives, and unsafe inline script/style handling.
- Two alerts report responses without CSP or anti-clickjacking protection.
- One alert concerns permissive CORS on
  `static.cloudflareinsights.com`, which is controlled by Cloudflare.

The current CSP is a fixed Nginx header containing only `frame-ancestors`,
`object-src`, and `base-uri`. It cannot safely authorize Nuxt's generated
inline elements without either weakening the policy with `unsafe-inline` or
adding a per-request nonce. It can also overwrite a dynamic application CSP.

## Goals

- Generate an enforced strict CSP in the Nuxt SSR application with a fresh
  nonce for every HTML response.
- Add a complete directive set including `form-action`, resource directives,
  `object-src`, `base-uri`, and `frame-ancestors`.
- Emit CSP and anti-clickjacking protection from Django responses as well.
- Stop the global Nginx rule from replacing application-generated CSP headers.
- Preserve security headers for Nginx-served static and media responses.
- Add automated tests that fail if the strict policy or routing boundary is
  removed.

## Non-goals

- Do not deploy to the test or production environment in this change.
- Do not alter databases, Fast-ID settings, API secrets, or certificate data.
- Do not attempt to change Cloudflare's CORS response. The external host must
  be excluded from the application ZAP context or Browser Insights must be
  disabled before the final scan.
- Do not suppress application-owned ZAP alerts without changing behavior.

## Approaches

1. **Application-layer strict CSP with SSR nonces (selected).** Use
   `nuxt-security` for Nuxt SSR, configure Django response headers, and retain
   Nginx only as the boundary for assets it serves directly. This removes the
   need for `unsafe-inline` while keeping Nuxt hydration functional.
2. **Complete static CSP in Nginx.** This is operationally simple, but cannot
   attach a fresh nonce to Nuxt-generated inline elements. A policy strict
   enough for ZAP can break the page, while `unsafe-inline` remains a finding.
3. **ZAP exclusions only.** This reduces the report count without improving
   the application's security and is rejected for application-owned findings.

## Selected design

### Nuxt frontend

- Add the official Nuxt module-directory package `nuxt-security` and pin it in
  the frontend lockfile.
- Enable SSR nonce support and an enforced CSP.
- Define explicit policies for scripts, styles, images, fonts, connections,
  frames, media, manifests, workers, forms, objects, base URLs, and framing.
- Keep Cloudflare Insights out of the trusted policy unless the application
  intentionally requires it; Cloudflare-injected behavior is verified
  separately at the edge.

### Django/Wagtail backend

- Use the existing security and clickjacking middleware for
  `X-Frame-Options: SAMEORIGIN`.
- Configure the existing `django-csp` integration as an enforced policy for
  production responses, with explicit `form-action`, `frame-ancestors`, and
  resource directives.
- Preserve same-origin framing required by Wagtail preview functionality.
- Supply request nonces only at trusted template/widget construction points.
  Wagtail 7 chooser/date/inline-panel initializers and the local theme/admin
  CSS require these nonces; never authorize all scripts by rewriting HTML.
- Wrap early redirects with CSP and clickjacking middleware as well.

### Nginx boundary

- Remove the global fixed CSP that would replace Nuxt's per-request nonce.
- Preserve or add compatible fallback headers only for responses served
  directly by Nginx, such as `/static/` and `/media/`.
- Continue passing application response headers unchanged through the Nuxt and
  Django proxy locations.
- Conditional maps supply fallback headers for Nginx-generated errors when
  upstream headers are absent, including HTTP 413 and 502.

### Compatibility retained after independent review

- Permit the existing supported YouTube/Vimeo frame origins explicitly, with
  compatible fullscreen permissions; keep arbitrary frame origins blocked.
- Give converted offline HTML its own same-origin script/style policy after
  removing the obsolete SSR CSP hashes/nonces. Verify offline.js in Chrome.
- Keep ordinary unit tests independent of ignored build output. The separate
  `npm run test:integration` command always builds before testing Nitro.

## Local verification

- A new Nuxt test first fails without the strict CSP configuration, then passes
  after implementation.
- Nuxt unit tests, type checking, and production build pass.
- A locally served Nuxt HTML response contains a fresh nonce in both the CSP
  header and generated script/style elements, without a functional reliance on
  `unsafe-inline`.
- Django security-header tests pass and confirm enforced CSP plus
  `SAMEORIGIN`.
- Nginx regression tests confirm the proxy no longer overwrites dynamic CSP
  and assets retain defensive headers.
- No test or deployment command modifies the test VM.

## Deployment gate

Deployment is a separate, explicit action after local verification is reported
and approved. Before deployment, back up the live Nginx configuration, validate
the repository configuration with `nginx -t`, and retain a rollback command.
The active sites currently have a separately authorized exact-IP preview gate.
Preserve that gate and its trusted-proxy settings when later merging security
header changes; do not replace a live site file wholesale with this test-site
template. This local change does not deploy or remove the live IP restrictions.
After deployment, rescan only `lularm.com` and `www.lularm.com`, excluding
Cloudflare-controlled hosts and `/cdn-cgi/` paths.
