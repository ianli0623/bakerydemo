# Fast-ID Passkey PoC Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an opt-in Fast-ID passkey provider that supports registration and sign-in for existing tenant users while preserving the current local Windows Hello implementation and password recovery path.

**Architecture:** Keep the existing same-origin Django URLs, templates, and framework-free browser code. A provider adapter selects the existing local implementation or a new server-side Fast-ID client through `FAST_ID_ENABLED`; Django owns all remote tokens, local user mapping, session state, throttling, and audit behavior.

**Tech Stack:** Python 3, Django 6, Wagtail 7.4, PostgreSQL-compatible Django models, `httpx` 0.28, WebAuthn browser APIs, Django test framework, `prek`.

**Vendor-contract amendment:** The later-supplied API flow and vendor backend
manual document HTTP Basic Client ID/Secret token operations and
`POST /api/webauthn/token/verify`. Tasks 1, 3, 4, 5, and 6 below use that
verified-subject contract instead of the earlier provisional unverified-token
design.

**Spec:** `docs/superpowers/specs/2026-10-05-fast-id-poc-design.md`

## Global Constraints

- Keep all existing `windows-hello/` routes and page templates stable.
- `FAST_ID_ENABLED=false` must preserve current local Windows Hello behavior exactly.
- Password login must remain available after Fast-ID registration.
- Never expose the management token, user token, Client Secret, or raw remote response in HTML, JavaScript, URLs, exceptions, logs, fixtures, snapshots, or commits.
- Never accept a token supplied by the browser as authenticated identity.
- Do not create Fast-ID tenant users or migrate existing local passkey credentials in this PoC.
- Automated tests must use an injected fake HTTP transport and must never call the live Fast-ID service.
- Implement every behavior test-first and commit only after its focused tests pass.

## Task 1: Add Fast-ID Settings and Deployment Checks

**Files:**

- Modify: `bakerydemo/settings/base.py`
- Modify: `bakerydemo/settings/production.py`
- Modify: `bakerydemo/account_security/checks.py`
- Modify: `bakerydemo/account_security/tests/test_security_checks.py`
- Modify: `bakerydemo/account_security/tests/test_settings.py`

**Settings contract:**

- `FAST_ID_ENABLED: bool = False`
- `FAST_ID_BASE_URL: str = ""`
- `FAST_ID_TENANT_ID: str = ""`
- `FAST_ID_TENANT_KEY: str = ""`
- `FAST_ID_CLIENT_ID: str = ""`
- `FAST_ID_CLIENT_SECRET: str = ""`
- `FAST_ID_MANAGEMENT_API_TOKEN: str = ""`
- `FAST_ID_RP_ID: str = ""`
- `FAST_ID_ORIGIN: str = ""`
- `FAST_ID_TIMEOUT_SECONDS: float = 5.0`

- [ ] Add failing settings tests proving Fast-ID is disabled by default, production settings parse a case-insensitive boolean, load all documented variables, parse a positive timeout, and never print secret values.
- [ ] Add failing system-check tests proving disabled Fast-ID has no new errors; enabled Fast-ID rejects missing required values, non-HTTPS base URL/origin, invalid timeout, and an RP ID unrelated to the origin host.
- [ ] Run the focused tests and confirm the new assertions fail for missing implementation:

  ```powershell
  $env:DJANGO_SETTINGS_MODULE='bakerydemo.settings.test'
  .\.venv\Scripts\python.exe manage.py test bakerydemo.account_security.tests.test_settings bakerydemo.account_security.tests.test_security_checks
  ```

- [ ] Define safe defaults in `base.py` and load environment overrides in `production.py`. Use the Client ID/Secret only for the documented server-to-server HTTP Basic token operations.
- [ ] Extend `account_security_configuration_check()` with stable Fast-ID error IDs beginning at `account_security.E007`; report setting names and safe remediation only, never setting values.
- [ ] Re-run the focused tests and confirm they pass.
- [ ] Commit the settings boundary:

  ```powershell
  git add bakerydemo/settings/base.py bakerydemo/settings/production.py bakerydemo/account_security/checks.py bakerydemo/account_security/tests/test_security_checks.py bakerydemo/account_security/tests/test_settings.py
  git commit -m "feat: validate Fast-ID configuration"
  ```

## Task 2: Add the Local Fast-ID User Mapping

**Files:**

- Modify: `bakerydemo/account_security/models.py`
- Create: `bakerydemo/account_security/migrations/0007_fastiduserlink.py`
- Modify: `bakerydemo/account_security/tests/test_passkey_models.py`

**Model contract:**

```python
class FastIdUserLink(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="fast_id_link",
    )
    tenant_key = models.CharField(max_length=128)
    external_user_id = models.CharField(max_length=128)
    registered_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

The pair `(tenant_key, external_user_id)` is unique. No remote token, Client Secret, credential ID, or public key is stored.

- [ ] Add failing model tests for one-to-one user ownership, tenant/external-ID uniqueness, nullable registration timestamp, and cascade deletion.
- [ ] Run the focused test and confirm it fails because the model does not exist:

  ```powershell
  $env:DJANGO_SETTINGS_MODULE='bakerydemo.settings.test'
  .\.venv\Scripts\python.exe manage.py test bakerydemo.account_security.tests.test_passkey_models
  ```

- [ ] Implement `FastIdUserLink` with explicit verbose names and the unique constraint.
- [ ] Generate the migration, inspect it to ensure it only creates the new table and constraint, then run migration consistency checks:

  ```powershell
  .\.venv\Scripts\python.exe manage.py makemigrations account_security
  .\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
  ```

- [ ] Re-run the focused model tests and confirm they pass.
- [ ] Commit the mapping model:

  ```powershell
  git add bakerydemo/account_security/models.py bakerydemo/account_security/migrations/0007_fastiduserlink.py bakerydemo/account_security/tests/test_passkey_models.py
  git commit -m "feat: map Django users to Fast-ID"
  ```

## Task 3: Implement the Fast-ID HTTP Boundary

**Files:**

- Modify: `requirements/base.txt`
- Create: `bakerydemo/account_security/fast_id.py`
- Create: `bakerydemo/account_security/tests/test_fast_id_client.py`

**Public interfaces:**

```python
class FastIdError(Exception):
    reason: str

@dataclass(frozen=True)
class FastIdAuthenticationResult:
    external_user_id: str

class FastIdClient:
    @classmethod
    def from_settings(cls, *, transport=None) -> "FastIdClient": ...
    def list_users(self) -> list[dict]: ...
    def issue_user_token(self, user_id: str) -> str: ...
    def registration_initialize(self, user_token: str) -> dict: ...
    def registration_finalize(self, user_token: str, credential: dict) -> bool: ...
    def authentication_initialize(self) -> dict: ...
    def authentication_finalize(
        self, credential: dict
    ) -> FastIdAuthenticationResult: ...
```

- [ ] Add `httpx>=0.28,<0.29` to the base requirements and install/sync dependencies using the repository's normal environment command.
- [ ] Write `httpx.MockTransport` tests for every endpoint path, method, JSON body, expected response field, and timeout.
- [ ] Add a regression test where the configured management token already starts with `Bearer ` and assert the outgoing `Authorization` header contains exactly one prefix.
- [ ] Add failure tests for network timeout, non-2xx status, non-JSON body, missing `data`, malformed authentication result, and unverified, expired, or revoked token-verification results. Assert each raises a safe `FastIdError.reason` and that neither configured secret appears in `str(exc)`.
- [ ] Run the client tests and confirm they fail because `fast_id.py` does not exist:

  ```powershell
  $env:DJANGO_SETTINGS_MODULE='bakerydemo.settings.test'
  .\.venv\Scripts\python.exe manage.py test bakerydemo.account_security.tests.test_fast_id_client
  ```

- [ ] Implement a small `httpx.Client` wrapper that joins paths safely, encodes JSON, enforces the configured timeout, validates response shapes, and normalizes all remote failures into documented safe reason codes.
- [ ] Normalize the management authorization value by stripping any existing case-insensitive `Bearer` prefix before adding exactly one prefix. Use HTTP Basic Client ID/Secret for user-token issuance and token verification; use user tokens only on registration calls that require them.
- [ ] Accept the authentication token only from the immediate server-to-server finalize response, send it to `/api/webauthn/token/verify`, and require verified, unexpired, non-revoked output with a non-empty `claims.sub`. Do not expose or return the raw identity token.
- [ ] Re-run the client tests and confirm they pass.
- [ ] Commit the HTTP boundary:

  ```powershell
  git add requirements/base.txt bakerydemo/account_security/fast_id.py bakerydemo/account_security/tests/test_fast_id_client.py
  git commit -m "feat: add Fast-ID API client"
  ```

## Task 4: Add Local and Fast-ID Provider Adapters

**Files:**

- Create: `bakerydemo/account_security/passkey_providers.py`
- Create: `bakerydemo/account_security/tests/test_passkey_providers.py`
- Modify if required for a narrow reusable helper: `bakerydemo/account_security/passkeys.py`

**Provider contracts:**

```python
@dataclass(frozen=True)
class ProviderStart:
    options: dict
    state: dict

@dataclass(frozen=True)
class ProviderRegistrationResult:
    user: User

@dataclass(frozen=True)
class ProviderAuthenticationResult:
    user: User
    credential: PasskeyCredential | None = None

def get_passkey_provider(): ...
```

Each provider implements `start_registration(user)`, `finish_registration(user, enrolment, credential_payload, state)`, `start_authentication()`, and `finish_authentication(credential_payload, state)`.

- [ ] Add tests proving `get_passkey_provider()` returns the local adapter when the flag is off and Fast-ID when it is on.
- [ ] Add local-adapter characterization tests proving it delegates to the existing `build_*`, `complete_registration`, and `verify_login_credential` functions without changing local credential storage.
- [ ] Add Fast-ID lookup tests for case-insensitive normalized email matching and rejection of zero matches, multiple matches, empty external IDs, a tenant mismatch, or an existing link that points to another external user.
- [ ] Add Fast-ID registration tests proving it obtains a user token, returns only public-key options plus server-side state, creates/updates the mapping after an unambiguous match, marks `registered_at` only after successful finalize, consumes the enrolment once, and does not disable the password.
- [ ] Add authentication tests proving only an active staff Django user with a registered Fast-ID link matching the verified external subject is returned. Cover missing or unregistered links, inactive users, non-staff users, and unverified, expired, revoked, or malformed results.
- [ ] Add explicit tests proving a token field injected into `credential_payload` is ignored and cannot choose the authenticated user.
- [ ] Run the provider tests and confirm they fail because the adapters do not exist:

  ```powershell
  $env:DJANGO_SETTINGS_MODULE='bakerydemo.settings.test'
  .\.venv\Scripts\python.exe manage.py test bakerydemo.account_security.tests.test_passkey_providers
  ```

- [ ] Implement the local adapter as a thin delegation layer. Do not modify the existing local WebAuthn verification rules.
- [ ] Implement the Fast-ID adapter with transaction-safe link resolution. Use normalized email for lookup, reject ambiguity, never create a remote tenant user, and never save user or management tokens.
- [ ] Preserve the existing enrolment authorization and consumption semantics, except deliberately ignore `disable_password` for Fast-ID so the recovery password remains usable.
- [ ] Tag every serialized provider state with `provider: "local"` or `provider: "fast_id"`; reject a state created by another provider.
- [ ] Re-run the provider tests and the existing passkey service tests:

  ```powershell
  .\.venv\Scripts\python.exe manage.py test bakerydemo.account_security.tests.test_passkey_providers bakerydemo.account_security.tests.test_passkey_enrolment bakerydemo.account_security.tests.test_passkey_login bakerydemo.account_security.tests.test_passkey_services
  ```

- [ ] Commit the provider layer:

  ```powershell
  git add bakerydemo/account_security/passkey_providers.py bakerydemo/account_security/passkeys.py bakerydemo/account_security/tests/test_passkey_providers.py
  git commit -m "feat: add selectable passkey providers"
  ```

## Task 5: Integrate the Provider into Existing Django Views

**Files:**

- Modify: `bakerydemo/account_security/passkey_views.py`
- Create: `bakerydemo/account_security/tests/test_fast_id_passkey_views.py`
- Modify as needed for preserved behavior: `bakerydemo/account_security/tests/test_passkey_enrolment.py`
- Modify as needed for preserved behavior: `bakerydemo/account_security/tests/test_passkey_login.py`

**Session-state contract:**

- Store only JSON-serializable provider state in the existing server-side Django session.
- Store registration and authentication state separately.
- Record `created_at` and reject state older than `ACCOUNT_SECURITY_WEBAUTHN_CHALLENGE_TTL_SECONDS`.
- Pop state before final verification so both successful and failed attempts are single-use.
- Never include provider state, tokens, or raw remote errors in a response.

- [ ] Add integration tests for successful Fast-ID registration through the existing option/verify URLs, including enrolment-code authorization, a marked link, one success audit record, Django login, and a still-usable password.
- [ ] Add tests for successful Fast-ID authentication through the existing option/verify URLs, including throttle reset, safe audit metadata, and login of the correct active staff account.
- [ ] Add rejection tests for missing state, expired state, provider mismatch, replay after success, replay after failure, and browser-supplied identity token. Verify each returns the existing generic user-facing error and never leaks secrets.
- [ ] Add remote timeout, unavailable service, malformed response, and unknown/ambiguous user view tests. Assert safe internal audit reason codes and generic response text.
- [ ] Add feature-flag-off regression tests showing the existing local option and verify paths still create/use local `PasskeyCredential` records.
- [ ] Run the view tests and confirm the new Fast-ID cases fail before integration:

  ```powershell
  $env:DJANGO_SETTINGS_MODULE='bakerydemo.settings.test'
  .\.venv\Scripts\python.exe manage.py test bakerydemo.account_security.tests.test_fast_id_passkey_views bakerydemo.account_security.tests.test_passkey_enrolment bakerydemo.account_security.tests.test_passkey_login
  ```

- [ ] Replace direct ceremony calls in `passkey_views.py` with the selected provider while retaining current CSRF decorators, staff checks, rate-limit behavior, JSON response shapes, audit calls, and URL names.
- [ ] Clear session state on expiry, success, and every failure path. Return `503` only for a Fast-ID service availability failure where the existing contract permits it; use `400` for invalid ceremony state/credential and `429` for existing throttling.
- [ ] Keep templates and `passkeys.js` unchanged unless a failing compatibility test demonstrates a required, provider-neutral adjustment.
- [ ] Re-run the focused tests and the complete account-security test package:

  ```powershell
  .\.venv\Scripts\python.exe manage.py test bakerydemo.account_security.tests
  ```

- [ ] Commit view integration:

  ```powershell
  git add bakerydemo/account_security/passkey_views.py bakerydemo/account_security/tests/test_fast_id_passkey_views.py bakerydemo/account_security/tests/test_passkey_enrolment.py bakerydemo/account_security/tests/test_passkey_login.py
  git commit -m "feat: integrate Fast-ID passkey flow"
  ```

## Task 6: Document Configuration, Rollout, and Rollback

**Files:**

- Modify: `docs/SEMI_E187_Linux_Deployment_Guide_zh-TW.md`
- Create or modify if already present: `.env.example`
- Modify: `.gitignore` only if needed to keep `.env` ignored and `.env.example` tracked

- [ ] Add a Fast-ID deployment section listing every environment variable with placeholders only. Document Client ID/Secret and management-token roles, and require all credentials to remain server-side.
- [ ] Document the safe rollout sequence: rotate the previously exposed management token, configure HTTPS domain/RP/CORS, run checks and migrations, keep `FAST_ID_ENABLED=false`, deploy, enable on the test domain, then smoke-test only the two pre-created tenant users.
- [ ] Document rollback as setting `FAST_ID_ENABLED=false` and restarting the application; clarify that local credentials and mapping rows remain intact.
- [ ] Document that production smoke testing must confirm the deployed vendor endpoint version, response contract, and tenant isolation behavior.
- [ ] Add `.env.example` placeholders only if the repository does not already have an equivalent tracked configuration example. Confirm it contains no actual tenant IDs, Client ID, token, Client Secret, email address, or domain supplied by the customer.
- [ ] Run documentation and secret-safety checks:

  ```powershell
  rg -n "eyJ|FAST_ID_MANAGEMENT_API_TOKEN=Bearer|FAST_ID_CLIENT_SECRET=.+" --glob '!*.pdf' --glob '!*.png' .
  git diff --check
  ```

- [ ] Commit documentation:

  ```powershell
  git add docs/SEMI_E187_Linux_Deployment_Guide_zh-TW.md .env.example .gitignore
  git commit -m "docs: add Fast-ID deployment guidance"
  ```

## Task 7: Complete Repository Verification

**Files:**

- Modify only files required to fix failures caused by this branch.

- [ ] Confirm no migration drift:

  ```powershell
  $env:DJANGO_SETTINGS_MODULE='bakerydemo.settings.test'
  .\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
  ```

- [ ] Run Django system checks with Fast-ID disabled, then with safe placeholder HTTPS settings and Fast-ID enabled. Confirm both expected configurations pass without exposing values.
- [ ] Run the focused account-security suite:

  ```powershell
  .\.venv\Scripts\python.exe manage.py test bakerydemo.account_security.tests
  ```

- [ ] Run the full Django test suite:

  ```powershell
  .\.venv\Scripts\python.exe manage.py test
  ```

- [ ] Run all repository hooks with UTF-8 enabled to avoid the Windows CP950 DjHTML issue:

  ```powershell
  $env:PYTHONUTF8='1'
  uvx --from prek==0.5.5 prek run --all-files
  ```

- [ ] Run final hygiene checks:

  ```powershell
  git diff --check
  git status --short
  git log --oneline --decorate -10
  ```

- [ ] Review the final diff against the design spec. Confirm there are no live Fast-ID calls in tests, no secret values, no React dependency, no new public route, no auto-provisioning, and no password disablement.
- [ ] If verification required code corrections, commit only those scoped corrections with a descriptive message and repeat every failed check.

## Required Review Focus

Before accepting the implementation, reviewers must verify these regression tests exist and pass:

1. A management token already containing `Bearer ` produces exactly one authorization prefix.
2. Missing or duplicate normalized Fast-ID email matches fail closed.
3. Unverified, expired, revoked, unsuccessful, or malformed authentication and token-verification results fail closed.
4. Provider-mismatched, expired, or replayed session state is rejected and cleared.
5. Timeout, non-JSON, and non-2xx remote failures produce generic user errors and safe audit reasons without leaking either secret.

## Manual Smoke Test (After Automated Verification Only)

Perform this separately on the approved HTTPS test domain; do not automate it and do not run it against production data without authorization.

- [ ] Rotate the management token that was previously shared in conversation and update the server-side environment.
- [ ] Confirm the Fast-ID tenant allows the exact test origin and RP ID.
- [ ] Register a passkey for each pre-created tenant user using a valid one-time local enrolment code.
- [ ] Sign out and sign in with the registered passkey for each user.
- [ ] Confirm password sign-in still works for both users.
- [ ] Confirm audit entries contain safe reason codes and no token, Client Secret, assertion, or raw Fast-ID response.
- [ ] Disable `FAST_ID_ENABLED`, restart the application, and confirm the existing local Windows Hello provider is restored.
