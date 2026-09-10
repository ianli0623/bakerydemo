# Native PostgreSQL Cutover Implementation Plan

**Goal:** Make PostgreSQL Server 18 installed on Windows the persistent database used by the SEMI E187 Bakery Wagtail administration site, while retaining recoverable source backups.

**Architecture:** Export the populated Docker PostgreSQL database, restore it into the native Windows service, configure Django through the git-ignored `.env`, validate record counts and permissions, then stop—but do not remove—the Docker source.

**Spec:** `docs/superpowers/specs/2026-09-09-postgresql-cutover.md`

## Completed tasks

- [x] Confirm the native `postgresql-x64-18` service is installed, running, and configured for automatic startup.
- [x] Use native endpoint `127.0.0.1:5434` because port `5432` is occupied by another local service.
- [x] Create a custom-format dump of the Docker `bakerydemo` source database.
- [x] Create the native `bakerydemo` database and restricted `bakery_user` application role.
- [x] Restore the dump without copying source ownership or privileges.
- [x] Compare users, pages, images, documents, security states, and password-history counts.
- [x] Store the native connection URL only in the ignored `.env` file.
- [x] Run migrations and Django system checks against the native database.
- [x] Verify unauthenticated and authenticated administration responses and the public API.
- [x] Confirm the live backend process has established connections to port `5434`.
- [x] Stop the Docker source container without deleting its container or data volume.

## Verification summary

- Django database backend: `postgresql`
- Database endpoint: `127.0.0.1:5434`
- Administration login response: HTTP 200
- Authenticated administration homepage: HTTP 200
- Public API page count: 10
- Application role: no superuser, database-creation, role-creation, or replication privileges
- Backup SHA-256: `3E9A64E4AA417098D79C4EBB19F12684A1219B8AA631919D8A833AB238AF4C9B`

The backup is stored outside the repository, and no database credentials are included in version control.
