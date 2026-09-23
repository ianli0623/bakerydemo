# Windows Hello Passwordless Admin Design

## Goal

Allow authorised Wagtail staff users to sign in without entering a username or
password. Windows Hello performs local user verification through the customer's
ARCANITE USB fingerprint reader, while the site authenticates a discoverable
WebAuthn credential.

## Scope

This feature applies to the Django and Wagtail administration surfaces. It does
not change public Nuxt authentication because the public site has no user login.

The first release provides:

- passwordless, usernameless WebAuthn login for active staff users;
- one-time enrolment codes created by an administrator;
- Windows Hello platform-authenticator registration with required user
  verification and discoverable credentials;
- multiple credentials per user for a second registered Windows device;
- administrator credential revocation and enrolment-code regeneration;
- security audit events for enrolment, login success/failure and revocation;
- coexistence with the existing password login during migration;
- a documented break-glass password administrator account.

The first release does not:

- store fingerprint images or biometric templates;
- guarantee that Windows used a fingerprint rather than a Windows Hello PIN;
- make the ARCANITE reader portable between computers;
- integrate Microsoft Entra ID;
- add authentication to the public Nuxt frontend.

## User flows

### Create a passwordless user

1. A superuser opens the existing Wagtail user creation screen.
2. The superuser chooses `Windows Hello（無密碼）` as the authentication method.
3. The user is saved with `set_unusable_password()` and cannot use the password
   login form.
4. The system creates a cryptographically random single-use enrolment code,
   stores only its SHA-256 digest and shows the raw code once to the creator.
5. The creator sends the username and code to the user through an approved
   channel. The code expires after 15 minutes.

### Enrol Windows Hello

1. The user opens `/account/security/windows-hello/enrol/` on the Windows
   computer that will be used for administration.
2. The user enters the username and one-time enrolment code.
3. The server validates the code using a constant-time digest comparison, marks
   an enrolment session as pending and issues a one-time WebAuthn challenge.
4. The browser requests a platform authenticator, a discoverable credential and
   required user verification. Windows Hello prompts for fingerprint or its
   operating-system fallback.
5. The server verifies origin, RP ID, challenge and user verification through
   the `webauthn` package, stores the credential and consumes the enrolment code
   atomically.
6. The user is signed into Django with the normal model backend and redirected
   to Wagtail.

### Passwordless login

1. The Wagtail login page offers `使用 Windows Hello 登入` without a username
   field being required for this path.
2. The server issues a one-time authentication challenge without an allow-list,
   so Windows can select a discoverable credential.
3. The credential ID in the signed response maps to an active credential and
   therefore to a Django user.
4. The server verifies the response, confirms the user is active and staff,
   updates the signature counter and last-used timestamp, rotates the session
   and signs the user in.
5. Invalid, expired, replayed or revoked credentials receive the same generic
   error message and create a failed audit event.

### Recovery and revocation

- A superuser can revoke an individual credential immediately.
- A superuser can invalidate existing enrolment codes and generate a new code.
- A user may register a second Windows device while signed in, using a fresh
  enrolment code.
- At least one named break-glass superuser keeps a strong password and is not
  converted automatically. Its credentials are stored outside the application
  according to the deployment runbook.

## Architecture

### WebAuthn verification

Use `webauthn>=3.0,<3.1` for server-side option generation and cryptographic
verification. Browser code uses the standard `navigator.credentials.create()`
and `navigator.credentials.get()` APIs with local base64url conversion; no CDN
or external JavaScript is loaded on the admin login page.

Production values are explicit settings:

- `ACCOUNT_SECURITY_WEBAUTHN_RP_ID`: hostname only, for example
  `cms.example.com`;
- `ACCOUNT_SECURITY_WEBAUTHN_ORIGIN`: exact HTTPS origin, for example
  `https://cms.example.com`;
- `ACCOUNT_SECURITY_WEBAUTHN_RP_NAME`: `SEMI E187`;
- `ACCOUNT_SECURITY_WEBAUTHN_ENROLMENT_TTL_SECONDS`: `900`;
- `ACCOUNT_SECURITY_WEBAUTHN_CHALLENGE_TTL_SECONDS`: `300`.

Development and tests use `localhost` and `http://localhost:8000`. Production
system checks reject HTTP origins, mismatched RP IDs and missing values.

### Data model

`PasskeyCredential` stores:

- user relation;
- unique base64url credential ID;
- credential public key bytes;
- opaque WebAuthn user handle bytes;
- signature counter;
- device type and backup state returned by the verification library;
- authenticator transports;
- administrator-readable label;
- created, last-used and revoked timestamps.

`PasskeyEnrolment` stores:

- user and creator relations;
- unique SHA-256 code digest, never the raw code;
- expiry, consumed and revoked timestamps;
- whether successful enrolment disables the user's password.

`PasskeyAuditEvent` stores:

- event type and success flag;
- optional target user, actor and credential relations;
- IP address and truncated user-agent string;
- event timestamp;
- a short reason code that never contains a challenge, code, public key or
  biometric information.

### Session state

Registration and authentication challenges are stored in the server-side Django
session with their issue timestamp and purpose. A challenge is removed before
verification, which makes retries and replay fail closed. Enrolment sessions
store the validated enrolment row ID rather than the raw code.

### Existing password policy

Password users keep the current 90-day expiry, complexity, history and Axes
lockout behaviour. `PasswordPolicyMiddleware` skips expiry enforcement only
when the authenticated user has no usable password and owns at least one active
passkey. A passwordless user without an active credential cannot reach the
admin.

The existing password form remains available during migration. A successful
passkey registration may disable the password only when its enrolment record
explicitly requests that conversion.

### Authorisation

- Only active staff or superusers may complete enrolment or passwordless login.
- Only superusers may create enrolment codes for another user, revoke another
  user's credential or view the passkey management report.
- POST, CSRF protection and database transactions are required for every state
  change.
- Login endpoints use uniform errors and rate limiting independent of
  `django-axes`, because no password backend is invoked.

## Admin interface

The existing Wagtail login keeps the password form during rollout and adds a
visually primary Windows Hello button. The enrolment page uses Wagtail styling,
Traditional Chinese labels and an accessible live status message.

A superuser-only `Windows Hello 管理` report lists staff users, active credential
count, last use and pending enrolment expiry. Actions allow code generation and
credential revocation. Raw enrolment codes are displayed once and never appear
again in list pages, logs, URLs or browser history.

## Error handling

- Unsupported browser: explain that Edge or Chrome on Windows 10/11 with
  Windows Hello configured is required.
- Invalid or expired enrolment code: generic failure, no account-existence leak.
- Cancelled Windows prompt: remain signed out and allow a safe retry with a new
  challenge.
- Origin, RP ID, challenge or signature failure: generic failure plus an audit
  reason code.
- Revoked/inactive/non-staff user: generic failure without identifying which
  condition failed.
- Signature counter regression: reject the login and record a cloned-credential
  warning event.

## Testing

Automated tests cover model constraints, one-time-code hashing and expiry,
registration option requirements, verification success/failure, usernameless
login, challenge replay, inactive/non-staff users, revoked credentials,
password-policy bypass, permissions, audit events and production checks.

Manual acceptance testing uses the customer's ARCANITE reader on current Edge
and Chrome, checks fingerprint and Windows PIN fallback, cancellation, second
device registration, revocation, expired enrolment and the break-glass account.

## Rollout

1. Deploy schema and settings while password login remains enabled.
2. Enrol two pilot administrators and validate audit records.
3. Enrol remaining staff users, preferably with two devices each.
4. Convert selected users to unusable passwords only after successful enrolment.
5. Keep and test the break-glass account before considering removal of the
   visible password form in a later release.
