# Electronic Certificate Registry Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the certificate registry demo records with live records from the customer electronic-certificate API without exposing the API key to browsers.

**Architecture:** Nuxt Nitro exposes a same-origin `/api/esign/certificates` endpoint. A focused server utility reads private runtime config, sends `X-API-Key` to the internal upstream API, validates its response, and returns a normalized UI model; the page consumes only that UI model.

**Tech Stack:** Nuxt 4, Vue 3, Nitro/H3, ofetch, TypeScript, Node test runner

**Spec:** `docs/superpowers/specs/2026-10-27-esign-certificate-registry-integration-design.md`

## Global Constraints

- Upstream base URL is configured by `ESIGN_API_BASE_URL`; the supplied value is `http://192.168.1.123:8011`.
- API credentials are configured by `ESIGN_API_KEY` and must remain private server runtime config.
- Upstream endpoint is `GET /api/v1/external/certificates` with the `X-API-Key` header.
- Missing issue date and workflow status display as `-`; no values are inferred.
- Never fall back to sample data after a live API failure.
- Do not commit or print the customer's real API key.

## Review Focus

- A missing base URL or API key must produce a controlled 500 response without credential content.
- A malformed upstream payload must be rejected instead of partially rendering misleading data.
- Timeout, network, and non-2xx upstream failures must become a generic 502 response.
- An empty valid `data` array must render the existing empty state rather than an error.
- Every supported status (`PENDING`, `VALID`, `SUSPENDED`, `REVOKED`) must filter and translate correctly.

---

### Task 1: Define and validate the certificate API model

**Files:**

- Create: `nuxt-bakery-demo/shared/types/esign.ts`
- Create: `nuxt-bakery-demo/server/utils/esign-certificates-core.ts`
- Test: `nuxt-bakery-demo/tests/esign-certificates.test.ts`

**Interfaces:**

- Produces: `CertificateStatus`, `CertificateRegistryRecord`, `CertificateListResponse`.
- Produces: `normalizeESignBaseUrl(value: string): string`.
- Produces: `toCertificateRegistryRecords(payload: unknown): CertificateRegistryRecord[]`.
- Produces: `toESignErrorDetails(error: unknown): { statusCode: number; statusMessage: string }`.

- [x] **Step 1: Write failing tests for URL normalization, all four status mappings, missing UI fields as `-`, empty data, malformed payload, and generic upstream errors.**
- [x] **Step 2: Run `npm test -- tests/esign-certificates.test.ts` from `nuxt-bakery-demo` and verify the tests fail because the new modules do not exist.**
- [x] **Step 3: Add the shared types and minimal pure validation/normalization functions.**
- [x] **Step 4: Re-run the focused test and verify it passes.**

### Task 2: Add the private server-side API proxy

**Files:**

- Modify: `nuxt-bakery-demo/nuxt.config.ts`
- Create: `nuxt-bakery-demo/server/utils/esign-certificates.ts`
- Create: `nuxt-bakery-demo/server/api/esign/certificates.get.ts`
- Modify: `nuxt-bakery-demo/tests/esign-certificates.test.ts`
- Modify: `nuxt-bakery-demo/.env.example`

**Interfaces:**

- Consumes: Task 1 model and normalizers.
- Produces: `fetchESignCertificates(event: H3Event, dependencies?: ESignDependencies): Promise<CertificateListResponse>`.
- Produces: same-origin `GET /api/esign/certificates`.

- [x] **Step 1: Add failing tests asserting the exact upstream path, normalized Base URL, `X-API-Key` header, successful payload conversion, missing configuration, and upstream failure handling.**
- [x] **Step 2: Run the focused test and verify the new behavior fails for the expected missing implementation.**
- [x] **Step 3: Add private runtime config keys, server utility, route, and documented placeholder environment variables.**
- [x] **Step 4: Re-run the focused test and verify it passes without logging the key.**

### Task 3: Replace demo records in the certificate page

**Files:**

- Modify: `nuxt-bakery-demo/app/utils/compliance-registry.ts`
- Modify: `nuxt-bakery-demo/app/pages/compliance-registry.vue`
- Modify: `nuxt-bakery-demo/i18n/locales/zh-hant.json`
- Modify: `nuxt-bakery-demo/i18n/locales/en.json`
- Modify: `nuxt-bakery-demo/tests/semi-presentation.test.ts`

**Interfaces:**

- Consumes: `CertificateListResponse` from `/api/esign/certificates`.
- Produces: searchable and certificate-status-filterable live registry UI with loading, retry, empty, and detail states.

- [x] **Step 1: Replace sample-oriented tests with failing tests for the four live statuses, text/status filtering, and absent workflow filtering.**
- [x] **Step 2: Run the focused presentation test and verify it fails because the page still uses demo records.**
- [x] **Step 3: Remove sample records, load the same-origin API with `useFetch`, add accessible loading/error/retry states, translate the four statuses, and retain `-` for unavailable fields.**
- [x] **Step 4: Re-run the focused presentation test and verify it passes.**

### Task 4: Configure the local secret and verify the integration

**Files:**

- Modify without displaying secret: `nuxt-bakery-demo/.env`
- Verify only: all files changed in Tasks 1-3

**Interfaces:**

- Consumes: customer-provided API key entered as `ESIGN_API_KEY`.
- Produces: local Nuxt server able to reach the internal API when the host network permits it.

- [x] **Step 1: Add `ESIGN_API_BASE_URL=http://192.168.1.123:8011` and an `ESIGN_API_KEY` entry to the ignored local `.env`, without printing its value.**
- [x] **Step 2: Run `npm test`, `npm run typecheck`, and `npm run build` from `nuxt-bakery-demo`; all must exit successfully.**
- [x] **Step 3: Run repository formatting/lint checks applicable to the changed files and confirm no secret-like value is tracked by Git.**
- [x] **Step 4: If the internal API is reachable from the current host, start Nuxt and manually verify loading, four status labels, search, status filter, reset, detail, empty, and upstream-error states; otherwise report that network verification remains for the deployment host.**

## Self-review

- Spec coverage: every design requirement maps to Tasks 1-4.
- Type consistency: the server route and page share `CertificateListResponse`; filters use the normalized `CertificateStatus` union.
- Review focus coverage: configuration, malformed payload, upstream failures, empty data, and four statuses are explicitly tested.
- Scope: certificate mutations, downloads, pagination, issue-date inference, and workflow inference remain excluded.
