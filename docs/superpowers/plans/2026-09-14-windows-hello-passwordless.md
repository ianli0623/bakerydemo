# Windows Hello Passwordless Admin Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add passwordless, usernameless Windows Hello login and secure one-time enrolment for Wagtail staff users.

**Architecture:** The existing `account_security` app owns WebAuthn data, ceremonies and Wagtail integration. The maintained `webauthn` package performs cryptographic option generation and verification; Django sessions hold single-use challenges, while PostgreSQL stores public credentials, hashed enrolment codes and audit events.

**Tech Stack:** Django 6, Wagtail 7.4, PostgreSQL, `webauthn` 3.x, vanilla browser WebAuthn JavaScript, Django TestCase.

**Spec:** `docs/superpowers/specs/2026-09-14-windows-hello-passwordless-design.md`

## Global Constraints

- Normal Windows Hello login must not request a username or password.
- Registration uses a platform authenticator, a discoverable credential and required user verification.
- Production requires a fixed HTTPS origin and matching RP ID; localhost HTTP is development-only.
- Store only the SHA-256 digest of the 15-minute, single-use enrolment code.
- Never store biometric data, raw challenges, raw enrolment codes in database logs, or authentication payloads in audit details.
- Existing password users retain the 90-day expiry, complexity, history and Axes lockout flow.
- A passwordless user bypasses password expiry only after an active credential exists.
- Only superusers manage another user's enrolment or credentials.
- Password login remains available during the initial rollout for the break-glass account.
- All mutable endpoints use POST, CSRF protection and database transactions.

---

### Task 1: Credential, enrolment and audit persistence

**Files:**
- Modify: `requirements/base.txt`
- Modify: `bakerydemo/account_security/models.py`
- Create: `bakerydemo/account_security/migrations/0003_passkey_models.py`
- Create: `bakerydemo/account_security/passkeys.py`
- Create: `bakerydemo/account_security/tests/test_passkey_models.py`
- Create: `bakerydemo/account_security/tests/test_passkey_services.py`

**Interfaces:**
- Produces: `PasskeyCredential`, `PasskeyEnrolment`, `PasskeyAuditEvent` models.
- Produces: `create_enrolment(user, created_by, *, disable_password_on_success) -> tuple[PasskeyEnrolment, str]`.
- Produces: `validate_enrolment(username, raw_code, *, at=None) -> PasskeyEnrolment | None`.
- Produces: `record_passkey_event(event_type, *, success, user=None, actor=None, credential=None, request=None, reason="") -> PasskeyAuditEvent`.
- Consumes: existing Django user model and `account_security` application.

- [ ] **Step 1: Pin the verification dependency**

Add this line to `requirements/base.txt`:

```text
webauthn>=3.0,<3.1
```

- [ ] **Step 2: Write model tests that fail before the models exist**

Create tests that assert unique credential IDs, multiple credentials per user,
default active state and cascade behaviour:

```python
class PasskeyCredentialTests(TestCase):
    def test_user_can_own_two_active_credentials(self):
        first = credential_factory(self.user, credential_id="first")
        second = credential_factory(self.user, credential_id="second")
        self.assertNotEqual(first.pk, second.pk)
        self.assertIsNone(first.revoked_at)

    def test_credential_id_is_globally_unique(self):
        credential_factory(self.user, credential_id="duplicate")
        with self.assertRaises(IntegrityError):
            credential_factory(self.other_user, credential_id="duplicate")
```

- [ ] **Step 3: Run the model tests and confirm the missing imports fail**

Run:

```powershell
$env:DATABASE_URL='sqlite:///:memory:'
& ..\..\.venv\Scripts\python.exe manage.py test bakerydemo.account_security.tests.test_passkey_models --settings=bakerydemo.settings.test
```

Expected: failure because the three passkey models do not exist.

- [ ] **Step 4: Add focused models and indexes**

Implement:

```python
class PasskeyCredential(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="passkey_credentials")
    credential_id = models.CharField(max_length=1024, unique=True)
    credential_public_key = models.BinaryField()
    user_handle = models.BinaryField(max_length=64)
    sign_count = models.PositiveBigIntegerField(default=0)
    device_type = models.CharField(max_length=32, blank=True)
    backed_up = models.BooleanField(default=False)
    transports = models.JSONField(default=list, blank=True)
    label = models.CharField(max_length=100, default="Windows Hello")
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

class PasskeyEnrolment(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="passkey_enrolments")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_passkey_enrolments")
    code_digest = models.CharField(max_length=64, unique=True)
    disable_password_on_success = models.BooleanField(default=True)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

class PasskeyAuditEvent(models.Model):
    event_type = models.CharField(max_length=40)
    success = models.BooleanField()
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="passkey_audit_events")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="passkey_actions")
    credential = models.ForeignKey(PasskeyCredential, null=True, blank=True, on_delete=models.SET_NULL, related_name="audit_events")
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    reason = models.CharField(max_length=40, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
```

Add indexes for active credentials by user, active enrolments by user/expiry,
and audit events by timestamp/user.

- [ ] **Step 5: Generate and inspect the migration**

Run:

```powershell
$env:DATABASE_URL='sqlite:///:memory:'
& ..\..\.venv\Scripts\python.exe manage.py makemigrations account_security --settings=bakerydemo.settings.test
& ..\..\.venv\Scripts\python.exe manage.py sqlmigrate account_security 0003 --settings=bakerydemo.settings.test
```

Expected: three tables, their foreign keys, unique credential/code constraints
and intended indexes.

- [ ] **Step 6: Write failing enrolment-service tests**

Cover digest-only storage, 15-minute expiry, constant result for unknown users,
revocation of older unused codes and one-time consumption:

```python
def test_create_enrolment_returns_raw_code_but_stores_only_digest(self):
    enrolment, raw_code = create_enrolment(self.user, self.admin, disable_password_on_success=True)
    self.assertNotEqual(enrolment.code_digest, raw_code)
    self.assertEqual(enrolment.code_digest, hashlib.sha256(raw_code.encode()).hexdigest())
    self.assertNotIn(raw_code, repr(enrolment.__dict__))

def test_validate_enrolment_rejects_expired_code(self):
    enrolment, raw_code = create_enrolment(self.user, self.admin, disable_password_on_success=True)
    self.assertIsNone(validate_enrolment(self.user.username, raw_code, at=enrolment.expires_at))
```

- [ ] **Step 7: Implement token and audit services**

Use `secrets.token_urlsafe(32)`, SHA-256 and `secrets.compare_digest`. Revoke
previous unused enrolments for the same user in a transaction. Extract request
IP without trusting arbitrary forwarded headers; production proxy handling stays
with Django's configured proxy settings.

- [ ] **Step 8: Run Task 1 tests and the existing account-security suite**

Run:

```powershell
$env:DATABASE_URL='sqlite:///:memory:'
& ..\..\.venv\Scripts\python.exe manage.py test bakerydemo.account_security --settings=bakerydemo.settings.test
```

Expected: all account-security tests pass.

- [ ] **Step 9: Commit Batch 1**

```powershell
git add requirements/base.txt bakerydemo/account_security/models.py bakerydemo/account_security/migrations/0003_passkey_models.py bakerydemo/account_security/passkeys.py bakerydemo/account_security/tests/test_passkey_models.py bakerydemo/account_security/tests/test_passkey_services.py
git commit -m "feat: add Windows Hello credential foundation"
```

---

### Task 2: One-time Windows Hello enrolment

**Files:**
- Modify: `bakerydemo/settings/base.py`
- Modify: `bakerydemo/settings/dev.py`
- Modify: `bakerydemo/settings/test.py`
- Modify: `bakerydemo/settings/production.py`
- Modify: `bakerydemo/account_security/forms.py`
- Modify: `bakerydemo/account_security/user_views.py`
- Modify: `bakerydemo/account_security/urls.py`
- Modify: `bakerydemo/account_security/passkeys.py`
- Create: `bakerydemo/account_security/passkey_views.py`
- Create: `bakerydemo/account_security/templates/account_security/passkey_enrolment_created.html`
- Create: `bakerydemo/account_security/templates/account_security/passkey_enrol.html`
- Create: `bakerydemo/account_security/static/account_security/passkeys.js`
- Create: `bakerydemo/account_security/tests/test_passkey_enrolment.py`
- Modify: `bakerydemo/account_security/tests/test_user_creation.py`

**Interfaces:**
- Consumes: Task 1 models and enrolment services.
- Produces: `build_registration_options(user) -> str`.
- Produces: `complete_registration(*, user, enrolment, credential, challenge) -> PasskeyCredential`.
- Produces URL names: `account_security:passkey_enrol`, `passkey_registration_options`, `passkey_registration_verify`.

- [ ] **Step 1: Write failing creation-flow tests**

Post a Wagtail user form with `authentication_method=windows_hello` and assert:

```python
self.assertFalse(user.has_usable_password())
self.assertTemplateUsed(response, "account_security/passkey_enrolment_created.html")
self.assertContains(response, "Windows Hello 註冊碼")
self.assertNotIn(response.context["enrolment_code"], str(dict(self.client.session)))
```

Keep the current temporary-password test by posting
`authentication_method=temporary_password`.

- [ ] **Step 2: Add the authentication-method field and creation result**

Add a required choice field with `windows_hello` first and selected by default.
For that choice call `set_unusable_password()` and let `TemporaryPasswordCreateView`
create the enrolment after the user is saved. Render the raw code once. For the
temporary-password choice preserve the existing page and policy unchanged.

- [ ] **Step 3: Write failing enrolment page and option tests**

Assert generic invalid-code output, code expiry, staff-only target, session state
without raw code, and WebAuthn options containing:

```python
self.assertEqual(options["rp"]["id"], "localhost")
self.assertEqual(options["authenticatorSelection"]["authenticatorAttachment"], "platform")
self.assertEqual(options["authenticatorSelection"]["residentKey"], "required")
self.assertEqual(options["authenticatorSelection"]["userVerification"], "required")
```

- [ ] **Step 4: Add WebAuthn settings**

Set development/test defaults to RP ID `localhost`, origin
`http://localhost:8000`, RP name `SEMI E187`, enrolment TTL `900` and challenge
TTL `300`. Production derives RP ID from `PRIMARY_HOST` unless explicit
`WEBAUTHN_RP_ID` is set, and derives the HTTPS origin unless explicit
`WEBAUTHN_ORIGIN` is set.

- [ ] **Step 5: Implement registration option generation and verification**

Call `generate_registration_options()` with a random 32-byte user handle,
`AuthenticatorAttachment.PLATFORM`, `ResidentKeyRequirement.REQUIRED`,
`UserVerificationRequirement.REQUIRED` and active credential exclusions. Convert
options with `options_to_json()`.

Call `verify_registration_response()` with the session challenge, exact configured
origin and RP ID, and `require_user_verification=True`. Store only the verified
credential ID, public key, sign counter, device type, backup flag and declared
transports.

- [ ] **Step 6: Implement the enrolment views and vanilla browser bridge**

The HTML form posts username and code. A valid submission stores only the
enrolment primary key in session. JavaScript POSTs with Django's CSRF token to
obtain options, converts base64url values to `ArrayBuffer`, calls
`navigator.credentials.create()`, serialises the response and POSTs it for
verification. On success redirect to `wagtailadmin_home`.

- [ ] **Step 7: Enforce one-time challenge and enrolment consumption**

Pop the challenge from session before verification. Wrap credential creation,
enrolment consumption and optional `set_unusable_password()` in one atomic
transaction. A replay must fail and must not create a second credential.

- [ ] **Step 8: Run Task 2 tests and all account-security tests**

```powershell
$env:DATABASE_URL='sqlite:///:memory:'
& ..\..\.venv\Scripts\python.exe manage.py test bakerydemo.account_security --settings=bakerydemo.settings.test
```

Expected: all tests pass with no raw code appearing in database or session.

- [ ] **Step 9: Commit Batch 2**

```powershell
git add bakerydemo/settings bakerydemo/account_security
git commit -m "feat: add Windows Hello enrolment flow"
```

---

### Task 3: Usernameless passwordless Wagtail login

**Files:**
- Modify: `bakerydemo/account_security/passkeys.py`
- Modify: `bakerydemo/account_security/passkey_views.py`
- Modify: `bakerydemo/account_security/urls.py`
- Modify: `bakerydemo/account_security/static/account_security/passkeys.js`
- Modify: `bakerydemo/templates/wagtailadmin/login.html`
- Create: `bakerydemo/account_security/templates/account_security/passkey_login.html`
- Create: `bakerydemo/account_security/tests/test_passkey_login.py`

**Interfaces:**
- Consumes: active `PasskeyCredential` records from Tasks 1 and 2.
- Produces: `build_authentication_options() -> str` with no allow-list.
- Produces: `verify_login_credential(credential_payload, challenge) -> PasskeyCredential`.
- Produces URL names: `account_security:passkey_login`, `passkey_authentication_options`, `passkey_authentication_verify`.

- [ ] **Step 1: Write failing option and login tests**

Assert that options require user verification and do not include
`allowCredentials`. Mock only the cryptographic verifier boundary and test the
application behaviour:

```python
@patch("bakerydemo.account_security.passkeys.verify_authentication_response")
def test_valid_discoverable_credential_logs_staff_user_in(self, verify):
    verify.return_value = SimpleNamespace(new_sign_count=4, credential_device_type="single_device", credential_backed_up=False)
    response = self.client.post(self.verify_url, data=self.payload, content_type="application/json")
    self.assertEqual(response.status_code, 200)
    self.assertEqual(int(self.client.session["_auth_user_id"]), self.user.pk)
```

- [ ] **Step 2: Add negative security tests**

Cover inactive user, non-staff user, revoked credential, unknown credential,
expired/missing challenge, replayed challenge, verifier exception and regressed
non-zero sign counter. Every response must use one generic error and remain
signed out.

- [ ] **Step 3: Implement usernameless option generation**

Call `generate_authentication_options()` with configured RP ID,
`UserVerificationRequirement.REQUIRED` and no credential allow-list. Store a
fresh challenge and issue time in session, replacing any older challenge.

- [ ] **Step 4: Implement verified Django login**

Read the base64url credential ID before cryptographic verification and find one
active credential. Pop the challenge before calling
`verify_authentication_response()`. Verify exact origin/RP ID and required user
verification. Reject unsafe sign-counter regression, update the counter and
last-used timestamp, then call:

```python
login(request, credential.user, backend="django.contrib.auth.backends.ModelBackend")
```

Return JSON containing only the Wagtail home redirect URL.

- [ ] **Step 5: Add the Wagtail login entry point**

Extend the existing override so `below_login` contains a visually clear
`使用 Windows Hello 登入` link. The destination page contains no username or
password field and automatically starts authentication only after an explicit
button click.

- [ ] **Step 6: Extend browser JavaScript for authentication**

POST for authentication options, convert challenge to bytes, call
`navigator.credentials.get()`, serialise ID/rawId/clientDataJSON/
authenticatorData/signature/userHandle, POST verification and follow the returned
redirect. Map browser cancellation and unsupported WebAuthn to accessible,
generic Traditional Chinese status text.

- [ ] **Step 7: Run focused and regression tests**

```powershell
$env:DATABASE_URL='sqlite:///:memory:'
& ..\..\.venv\Scripts\python.exe manage.py test bakerydemo.account_security.tests.test_passkey_login bakerydemo.account_security.tests.test_login_lockout --settings=bakerydemo.settings.test
```

Expected: passkey tests pass and the existing five-failure password lockout
continues to pass.

- [ ] **Step 8: Commit Batch 3**

```powershell
git add bakerydemo/account_security bakerydemo/templates/wagtailadmin/login.html
git commit -m "feat: add passwordless Windows Hello admin login"
```

---

### Task 4: Administration, policy integration and production hardening

**Files:**
- Modify: `bakerydemo/account_security/middleware.py`
- Modify: `bakerydemo/account_security/checks.py`
- Modify: `bakerydemo/account_security/wagtail_hooks.py`
- Modify: `bakerydemo/account_security/passkey_views.py`
- Modify: `bakerydemo/account_security/urls.py`
- Create: `bakerydemo/account_security/templates/account_security/passkey_management.html`
- Create: `bakerydemo/account_security/tests/test_passkey_management.py`
- Modify: `bakerydemo/account_security/tests/test_middleware.py`
- Modify: `bakerydemo/account_security/tests/test_security_checks.py`
- Modify: `bakerydemo/account_security/locale/zh_Hant/LC_MESSAGES/django.po`
- Create: `docs/windows-hello-admin-runbook.md`

**Interfaces:**
- Consumes: all prior passkey services, models and views.
- Produces: superuser-only credential report, code generation and revoke actions.
- Produces: production system-check IDs `account_security.E004` through `E006`.

- [ ] **Step 1: Write failing password-policy integration tests**

Assert a passwordless user with an active credential reaches Wagtail, while a
passwordless user without one fails closed. Existing password users must still
be redirected when expired.

- [ ] **Step 2: Implement precise middleware bypass**

Add `is_passkey_only_user(user)` that returns true only when the password is
unusable and an unrevoked credential exists. Skip password-expiry enforcement
only for that case; do not bypass unrelated admin authorisation.

- [ ] **Step 3: Write management permission and action tests**

Assert superusers can list credentials, generate a replacement enrolment and
revoke a credential via POST. Staff users receive 403. Revocation records actor,
target, credential and IP, and the credential fails on the next login.

- [ ] **Step 4: Add the management report and Wagtail menu entry**

Register a `Windows Hello 管理` report under Reports. Show username, active
credential count, labels, last use and pending expiry. Display a raw replacement
code only on the immediate POST response and never on subsequent GET responses.

- [ ] **Step 5: Add passkey-specific login throttling**

Cache failed verification counts by a salted hash of IP plus credential ID for
15 minutes. Return HTTP 429 after five failures, include `Retry-After`, and clear
the relevant counter after successful verification. Never use username in this
usernameless path.

- [ ] **Step 6: Add production configuration checks**

Tests must reject missing values, HTTP non-localhost origin, RP ID containing a
scheme/port/path, and an origin host that is neither the RP ID nor its subdomain.
Tests accept `http://localhost:8000` only when production enforcement is false.

- [ ] **Step 7: Add audit assertions for every ceremony outcome**

Ensure registration success/failure, login success/failure/rate-limit,
enrolment creation/expiry and credential revocation have stable event and reason
codes. Assert challenge, raw code, public key and biometric terms are absent from
stored audit fields.

- [ ] **Step 8: Translate visible copy and compile messages**

Add Traditional Chinese translations for enrolment, login, management, generic
errors and expiry. Run:

```powershell
& ..\..\.venv\Scripts\python.exe manage.py compilemessages -l zh_Hant
```

- [ ] **Step 9: Write the operator runbook**

Document environment variables, migrations, pilot rollout, user enrolment,
second-device setup, revocation, recovery, break-glass testing and the fact that
WebAuthn cannot report whether Windows used fingerprint or PIN.

- [ ] **Step 10: Run the full verification suite**

```powershell
$env:DATABASE_URL='sqlite:///:memory:'
& ..\..\.venv\Scripts\python.exe manage.py check --settings=bakerydemo.settings.test
& ..\..\.venv\Scripts\python.exe manage.py test --settings=bakerydemo.settings.test
npm ci
npm run lint
```

Expected: Django checks pass, all tests pass and client lint reports no errors.

- [ ] **Step 11: Perform manual Windows acceptance tests**

On the customer Windows computer, verify Edge and Chrome enrolment/login with the
ARCANITE reader, cancellation, PIN fallback, expired code, second device,
revocation, lockout and break-glass access. Record browser/Windows versions and
results in the delivery notes without recording fingerprint data.

- [ ] **Step 12: Commit Batch 4**

```powershell
git add bakerydemo/account_security bakerydemo/settings docs/windows-hello-admin-runbook.md
git commit -m "feat: harden Windows Hello administration"
```

