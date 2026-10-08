# Fast-ID Passkey PoC Design

## Objective

Add an opt-in Fast-ID passkey provider to the existing Wagtail account security
flow without removing or weakening the current local Windows Hello
implementation. The PoC proves automatic Tenant User lifecycle management,
registration, and sign-in while preserving password sign-in as a recovery path.

## Scope

The PoC includes:

- a `FAST_ID_ENABLED` feature flag;
- server-side Fast-ID configuration and validation;
- creation, deletion, lookup, and local mapping of a Fast-ID tenant user by email;
- passkey registration through Fast-ID;
- passkey authentication through Fast-ID followed by a Django session login;
- the existing enrolment-code authorization before registration;
- the existing passkey login throttle and local audit records;
- automated tests that use a fake HTTP boundary and never contact Fast-ID.

The PoC excludes:

- authenticator listing, renaming, and deletion;
- migration of existing local passkey credentials to Fast-ID;
- removal of password authentication;
- accepting a Fast-ID token supplied by the browser as proof of identity;
- accepting an unverified identity token supplied by the browser;
- live Fast-ID registration or destructive API calls in automated tests.

## Selected Approach

Use a provider adapter behind the existing Django endpoints. Templates and the
framework-free `passkeys.js` continue calling same-origin Django URLs. Django
selects the local provider when `FAST_ID_ENABLED` is false and the Fast-ID
provider when it is true.

This is preferred over adding parallel public routes because it keeps one user
experience and one CSRF boundary. It is preferred over browser-to-Fast-ID calls
because no management or user token is exposed to JavaScript, browser storage,
URLs, or logs.

## Configuration

The Fast-ID provider reads these environment variables through Django settings:

- `FAST_ID_ENABLED`, default `false`;
- `FAST_ID_BASE_URL`, required when enabled;
- `FAST_ID_TENANT_ID`, required when enabled;
- `FAST_ID_TENANT_KEY`, required when enabled;
- `FAST_ID_CLIENT_ID`, retained for the documented tenant configuration;
- `FAST_ID_CLIENT_SECRET`, required for the documented HTTP Basic login-token verification;
- `FAST_ID_MANAGEMENT_API_TOKEN`, required when enabled;
- `FAST_ID_RP_ID`, required when enabled;
- `FAST_ID_ORIGIN`, required when enabled;
- `FAST_ID_TIMEOUT_SECONDS`, default `5`.

The management token may be stored with or without the `Bearer ` prefix. The
HTTP client normalizes it to exactly one prefix. No secret value may be included
in exceptions, logs, templates, responses, fixtures, or committed example
configuration.

System checks fail deployment when Fast-ID is enabled and a required setting is
missing, the base URL or origin is not HTTPS, or the RP ID does not match the
configured origin host. The existing local provider settings remain valid when
Fast-ID is disabled.

## Components

### Fast-ID HTTP client

A focused client owns all remote paths, JSON encoding, authorization headers,
timeouts, response validation, and exception normalization. It supports:

- `POST /api/tenant/{tenant_key}/user`;
- `GET /api/tenant/{tenant_key}/users`;
- `DELETE /api/tenant/{tenant_key}/user/{user_id}`;
- `POST /api/tenant/{tenant_key}/user/{user_id}/token`;
- `POST /api/webauthn/{tenant_key}/registration/initialize`;
- `POST /api/webauthn/{tenant_key}/registration/finalize`;
- `POST /api/webauthn/{tenant_key}/authentication/initialize`;
- `POST /api/webauthn/{tenant_key}/authentication/finalize`;
- `POST /api/webauthn/token/verify`.

The client accepts an injectable HTTP transport so tests exercise parsing and
error handling without network access. Remote non-2xx responses, invalid JSON,
missing required fields, and timeouts become typed internal errors with safe
reason codes.

### Provider adapter

The provider interface covers four operations:

- create registration options for an authorized Django user;
- finalize registration for that user;
- create authentication options;
- finalize authentication and return the authenticated Django user.

The local adapter delegates to the existing `passkeys.py` behavior without
changing its credential storage or verification rules. The Fast-ID adapter uses
the remote client and never creates a local `PasskeyCredential`.

### Fast-ID user link

A new one-to-one model maps a Django user to a Fast-ID user identifier. It
stores the tenant key, external user ID, registration timestamp, and normal
created/updated timestamps. It does not store a credential public key, a user
token, the management token, or the Client Secret.

When a newly created Wagtail Windows Hello user is provisioned, the provider
requires that no matching Tenant User already exists, creates one through the
Fast-ID management API, validates the returned ID and normalized email, and then
stores the local link. This prevents a deleted and recreated local account from
silently inheriting an old remote authenticator. Existing Django users entering
registration may still resolve exactly one pre-created Tenant User by normalized
email as a migration path. Missing, duplicate, empty, or mismatched records are
rejected. If saving the local link fails after remote creation, Django attempts
to remove the newly created remote Tenant User.

## Account Lifecycle

- A new Wagtail Windows Hello user is created in Fast-ID before an enrolment code
  is issued. A remote provisioning failure prevents local account creation.
- Deleting a linked account first disables it locally, deletes the Fast-ID Tenant
  User, and then deletes the local account. A remote failure restores the prior
  active state. If the remote deletion succeeds but the local deletion fails,
  the local linked account remains inactive so the operation can be retried
  safely. A missing remote record is treated as an idempotent success.
- Linked single and bulk deletions are blocked while `FAST_ID_ENABLED=false`,
  because Django cannot safely remove the remote identity in that state.
- The confirmation page warns that the local account and remote Tenant User are
  deleted permanently. Device-resident passkeys may still require user cleanup.

## Registration Flow

1. The user supplies their Django account email and the existing one-time
   enrolment code.
2. Django validates the code, active status, and staff status exactly as it does
   today.
3. Django resolves the matching Fast-ID tenant user and requests a user token
   with the backend-only management token.
4. Django calls Fast-ID registration initialize with the user token and returns
   only `publicKey` options to the browser.
5. The browser runs `navigator.credentials.create()` and posts the serialized
   credential to the existing Django verification endpoint.
6. Django calls Fast-ID registration finalize using the same short-lived user
   token held in the server-side session.
7. On success, Django consumes the local enrolment record, timestamps the
   Fast-ID link, records an audit event, and creates a Django session.

The user token and registration context are single-use and expire using the
existing WebAuthn challenge TTL. Password authentication remains usable even
if the enrolment originally requested password disablement; the PoC must not
remove the recovery password.

## Authentication Flow

1. The browser calls the existing same-origin authentication-options endpoint.
2. Django calls Fast-ID authentication initialize and returns only `publicKey`
   options.
3. The browser runs `navigator.credentials.get()` and posts the serialized
   assertion to Django.
4. Django sends that assertion directly to Fast-ID authentication finalize.
5. Django accepts the returned token only from the immediate TLS-protected
   server-to-server finalize response. A token supplied by the browser is never
   accepted.
6. Django calls the documented `/api/webauthn/token/verify` endpoint with HTTP
   Basic Client ID/Secret authentication.
7. Django requires a verified, unexpired, non-revoked result, extracts
   `claims.sub`, and resolves the unique registered Fast-ID user link for the
   configured tenant.
8. Django clears the existing throttle counter, records a success audit event,
   and creates the normal Django session.

The PoC does not decode or trust the JWT locally. The vendor verification
endpoint is the identity authority, and its verified subject is mapped to the
local Django user. Production smoke testing must confirm the deployed API
version and tenant isolation behavior.

## Failure and Security Behavior

- Fast-ID failures fail closed; they never fall back to an authenticated local
  passkey result.
- Password login remains a separate explicit user choice.
- Remote errors shown to users use the existing generic registration or login
  text.
- Internal audit reasons distinguish timeout, unavailable service, malformed
  response, unknown Fast-ID user, ambiguous user, invalid Fast-ID result, and
  inactive local account without recording secrets.
- Existing CSRF protection, one-time session state, challenge TTL, login
  throttling, secure cookies, and staff checks remain in force.
- Email is the authentication identifier; username remains a display alias.
- Fast-ID user creation must return the requested normalized email and a
  non-empty external ID before Django stores the link.
- Registration and authentication state is removed after success, failure, or
  expiry so a user token cannot be replayed through Django.

## User Interface

The PoC keeps the current Wagtail-styled Windows Hello pages and accessible
status announcements. No React runtime is added. The browser code continues to
perform only WebAuthn byte conversion, `navigator.credentials.create/get`, and
same-origin POST requests.

The existing password-login link remains visible. Fast-ID-specific service
details and raw error bodies are not displayed.

## Testing

Automated tests cover:

- feature flag off preserves existing local passkey behavior;
- enabled-setting validation and safe token normalization;
- tenant-user lookup by normalized email and rejection of missing or duplicate
  matches;
- automatic Tenant User creation and deletion, returned-identity validation,
  compensation after local persistence failure, and safe retry after partial
  deletion;
- registration initialize/finalize success and single-use state;
- password remains usable after Fast-ID registration;
- authentication success creates a Django session for the correct active staff
  user;
- browser-supplied identity tokens are ignored;
- expired, revoked, unverified, malformed, or unsuccessful Fast-ID responses fail;
- remote timeout, invalid JSON, and non-2xx responses return generic errors and
  audit safe reason codes;
- management Token and Client Secret never appear in rendered responses or
  logged exception text.

The focused account-security test suite, Django system checks, and the full
repository lint command must pass. Live testing is a separate manual smoke test
on `https://lularm.com` using dedicated test users created through Wagtail and a
rotated management token.

## Rollback

Setting `FAST_ID_ENABLED=false` restores the existing local Windows Hello
provider without deleting local credentials or Fast-ID links. The new mapping
table can remain dormant. No data migration rewrites existing passkey records.
Deletion of a linked account remains blocked until Fast-ID is enabled again.

## Production Follow-up

Before enabling Fast-ID as a production authentication provider:

- confirm the production Fast-ID endpoint version, response contract, and
  tenant isolation behavior;
- replace the previously exposed management token;
- define management-token rotation and revocation procedures;
- decide whether to add authenticator listing, renaming, and deletion;
- add scheduled reconciliation for the rare case where a process terminates
  between the remote and local lifecycle operations;
- confirm whether Client Credentials should replace the long-lived management
  token.
