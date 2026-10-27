# Local ESign Mock API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a loopback-only Node.js Mock API that reproduces the customer electronic-certificate list contract for local Nuxt testing.

**Architecture:** A standalone TypeScript script uses Node's built-in HTTP server and exports a pure response resolver for fast tests. Nuxt is started separately with a safe, tracked `.env.mock`, so the customer's real URL and API key remain untouched and the Mock cannot become a production Nuxt route.

**Tech Stack:** Node.js 22+, TypeScript type stripping, `node:http`, Node test runner, Nuxt 4

**Spec:** `docs/superpowers/specs/2026-10-27-local-esign-mock-api-design.md`

## Global Constraints

- Bind only to `127.0.0.1:8011`; never bind to `0.0.0.0` or a LAN interface.
- Implement only `GET /api/v1/external/certificates` and require `X-API-Key`.
- Use a dedicated dummy key; never read, copy, log, or return the customer API key.
- Use only Node.js built-ins; add no package dependency.
- Keep the Mock out of Nuxt `server/` so production builds do not expose it.
- Do not overwrite either existing ignored `.env` file.

## Review Focus

- Missing or incorrect `X-API-Key` must return 401 without echoing the received key — covered by Task 1 tests.
- Any non-GET method or different path must return 404 — covered by Task 1 tests.
- All four documented certificate statuses and exact response field names must be present — covered by Task 1 tests.
- `empty`, `error`, `malformed`, and `slow` scenarios must be deterministic without making tests wait — covered by Task 1 tests.
- An unsupported `ESIGN_MOCK_SCENARIO` must fail at startup with a clear message instead of silently behaving as success — covered by Task 1 tests.

---

### Task 1: Standalone Mock API Contract and Server

**Files:**
- Create: `nuxt-bakery-demo/scripts/mock-esign-api.ts`
- Create: `nuxt-bakery-demo/tests/mock-esign-api.test.ts`

**Interfaces:**
- Consumes: Customer contract `GET /api/v1/external/certificates`, header `X-API-Key`, and statuses `PENDING | VALID | SUSPENDED | REVOKED`.
- Produces: `resolveMockESignResponse(request: MockESignRequest): MockESignResponse`, `parseMockScenario(value: string | undefined): MockScenario`, `startMockESignServer(options?: MockServerOptions): Promise<Server>`, plus constants `MOCK_ESIGN_HOST`, `MOCK_ESIGN_PORT`, and `DEFAULT_MOCK_ESIGN_API_KEY`.

- [x] **Step 1: Write failing contract tests**

  Add tests named:
  - `mock server is restricted to the loopback host and documented port`
  - `success response matches the external certificate contract and all statuses`
  - `missing or incorrect API keys return 401 without echoing credentials`
  - `unsupported methods and paths return 404`
  - `empty, error, malformed, and slow scenarios are deterministic`
  - `unsupported scenarios are rejected with a clear error`

- [x] **Step 2: Run the focused test and verify RED**

  Run: `node --test --experimental-strip-types tests/mock-esign-api.test.ts`

  Expected: FAIL with `ERR_MODULE_NOT_FOUND` for `scripts/mock-esign-api.ts`.

- [x] **Step 3: Implement the pure resolver and scenario parser**

  In `scripts/mock-esign-api.ts`, define the interfaces above. `resolveMockESignResponse` must return JSON-ready bodies and a `delayMs` value; the `slow` scenario uses `11_000` milliseconds so it exceeds the Nuxt client's 10-second timeout without delaying the unit test itself.

- [x] **Step 4: Implement the loopback HTTP server and executable guard**

  `startMockESignServer` must use `node:http`, listen on `127.0.0.1:8011`, apply `delayMs` before responding, log only the local URL and scenario, and close cleanly on `SIGINT` or `SIGTERM`. Execute the server only when the file is run directly, not when imported by tests.

- [x] **Step 5: Run the focused test and verify GREEN**

  Run: `node --test --experimental-strip-types tests/mock-esign-api.test.ts`

  Expected: all six tests PASS with no open-handle warning.

- [x] **Step 6: Commit the task if the user requests a commit**

  ```powershell
  git add nuxt-bakery-demo/scripts/mock-esign-api.ts nuxt-bakery-demo/tests/mock-esign-api.test.ts
  git commit -m "test: add local electronic certificate mock API"
  ```

### Task 2: Local Commands, Safe Environment, and Usage Guide

**Files:**
- Create: `nuxt-bakery-demo/.env.mock`
- Modify: `nuxt-bakery-demo/package.json`
- Modify: `nuxt-bakery-demo/README.md`
- Modify: `nuxt-bakery-demo/tests/mock-esign-api.test.ts`

**Interfaces:**
- Consumes: Task 1 executable `scripts/mock-esign-api.ts`, host `127.0.0.1`, port `8011`, and dummy key `local-esign-test-key`.
- Produces: `npm run mock:esign`, `npm run dev:mock`, and documented two-terminal local test procedure.

- [x] **Step 1: Add a failing configuration test**

  Test that `package.json` exposes exactly these commands:

  - `mock:esign`: `node --experimental-strip-types scripts/mock-esign-api.ts`
  - `dev:mock`: `nuxt dev --dotenv .env.mock`

  Test that `.env.mock` sets:

  - `NUXT_BAKERY_BASE_URL=http://127.0.0.1:8000`
  - `ESIGN_API_BASE_URL=http://127.0.0.1:8011`
  - `ESIGN_API_KEY=local-esign-test-key`

- [x] **Step 2: Run the focused test and verify RED**

  Run: `node --test --experimental-strip-types tests/mock-esign-api.test.ts`

  Expected: FAIL because the scripts and `.env.mock` do not exist.

- [x] **Step 3: Add the local scripts and safe Mock environment file**

  Modify `package.json` with the exact commands above and create `.env.mock` with only non-secret local values. Do not modify either ignored `.env`.

- [x] **Step 4: Document the two-terminal workflow and scenarios**

  Add a README section with:

  1. `npm run mock:esign`
  2. `npm run dev:mock`
  3. The localized compliance-registry URL
  4. PowerShell examples setting `ESIGN_MOCK_SCENARIO` for `empty`, `error`, `malformed`, and `slow`
  5. A warning that this only validates local integration, not the customer network or real API key

- [x] **Step 5: Run focused and full verification**

  Run:

  ```powershell
  node --test --experimental-strip-types tests/mock-esign-api.test.ts
  npm test
  npm run typecheck
  npm run build
  npx prettier --check scripts/mock-esign-api.ts tests/mock-esign-api.test.ts package.json README.md .env.mock
  ```

  Expected: all tests PASS, typecheck and build exit 0, and Prettier reports all matched files use its code style. If Prettier cannot infer `.env.mock`, verify it separately as exact key/value lines and rerun Prettier without that file.

- [x] **Step 6: Perform a local smoke test**

  Start `npm run mock:esign`, request the documented endpoint once with the dummy `X-API-Key`, assert HTTP 200 and four records, then stop the server. Confirm the process listens only on `127.0.0.1:8011`.

- [x] **Step 7: Commit the task if the user requests a commit**

  ```powershell
  git add nuxt-bakery-demo/.env.mock nuxt-bakery-demo/package.json nuxt-bakery-demo/README.md nuxt-bakery-demo/tests/mock-esign-api.test.ts docs/superpowers/specs/2026-10-27-local-esign-mock-api-design.md docs/superpowers/plans/2026-10-27-local-esign-mock-api.md
  git commit -m "docs: add local electronic certificate mock workflow"
  ```
