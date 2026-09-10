# Native PostgreSQL Cutover Specification

## Goal

Move the SEMI E187 Bakery Wagtail database from the temporary Docker PostgreSQL service to PostgreSQL Server 18 installed directly on Windows, without losing content or account-security data.

## Source and target

- Application worktree: `D:\Ian\github\bakerydemo\.worktrees\semi-e187-multilingual`
- Source container: `bakerydemo-postgres`
- Source endpoint: `127.0.0.1:5433`
- Target Windows service: `postgresql-x64-18`
- Target endpoint: `127.0.0.1:5434`
- Database: `bakerydemo`
- Application role: `bakery_user`

Port `5434` is used because another local service already owns port `5432`.

## Requirements

- Create a custom-format PostgreSQL backup before changing the connection.
- Do not print or commit database passwords.
- Store the local `DATABASE_URL` only in the git-ignored `.env` file.
- Restore the source dump with ownership assigned to the restricted application role.
- Confirm users, pages, images, documents, security states, and password history match before cutover.
- Run Django migrations and system checks against native PostgreSQL.
- Verify the administration site and API while the Docker source database is stopped.
- Retain the stopped Docker container and its volume as an additional rollback point.

## Verified record counts

| Record type | Docker source | Native target |
|---|---:|---:|
| Users | 3 | 3 |
| Pages | 11 | 11 |
| Images | 3 | 3 |
| Documents | 0 | 0 |
| Security states | 3 | 3 |
| Password history | 5 | 5 |

The final Django connection reports the `postgresql` backend at `127.0.0.1:5434`. The native service is configured for automatic startup, and the application role has no superuser, database-creation, role-creation, or replication privileges.
