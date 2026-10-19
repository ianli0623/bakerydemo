# semi187-portal Production Deployment Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Safely deploy the latest `origin/main` release to the customer-provided `semi187-portal` Ubuntu VM with backups, atomic cutover, health checks, and rollback.

**Architecture:** The target is a fresh Ubuntu VM. Install only the named runtime packages, create a dedicated `deploy` account and `/srv/semi-e187` layout, then build an immutable release under `/srv/semi-e187/releases/<timestamp>-<commit>`. Keep secrets in root-readable `/etc/semi-e187/*.env`, shared media outside the release, and switch `/srv/semi-e187/app` only after all checks pass.

**Tech Stack:** Ubuntu, Nginx, systemd, Django/Wagtail/uWSGI, PostgreSQL, Nuxt/Node.js

**Spec:** User request in the current Codex chat dated 2026-10-13.

## Global Constraints

- Treat `semi187-portal` as a customer production environment.
- Do not run `apt upgrade`, reboot, or change firewall, DNS, or customer gateway settings.
- Install only the explicitly approved packages. Do not add third-party APT repositories or execute remote install scripts.
- Use Ubuntu's Python 3.14 and Node.js 22 packages; the project supports Node.js `>=22`.
- Do not configure a public TLS certificate until the customer confirms how `lularm.com` will be routed to `192.168.1.145`.
- Do not copy local `.env`, databases, media, build output, or ignored `rbac/` into the release archive.
- Preserve `/etc/semi-e187/backend.env`, `/etc/semi-e187/frontend.env`, the production database, and shared media.
- Do not delete the previous release until the user has accepted the deployment.
- Stop immediately if identity, disk space, package lock, build, migration check, service, or HTTP verification fails.
- Do not copy local secrets to the VM until the user separately approves transmission to this specific customer host.

## Review Focus

- Confirm the RVP terminal is connected to `semi187-portal`, not another asset.
- Confirm `origin/main` and local `main` resolve to the same commit before packaging.
- Confirm the deployed commit; do not redeploy an identical healthy release.
- Confirm database and environment files are backed up without printing secrets.
- Confirm rollback restores the previous symlink and services if cutover fails.

---

### Task 1: Read-only production inventory

**Files:** None.

- [ ] Run only these read-only commands in the RVP terminal:

```bash
set -euo pipefail
hostname
id
date --iso-8601=seconds
df -h / /srv
free -h
readlink -f /srv/semi-e187/app
cat /srv/semi-e187/app/DEPLOYED_COMMIT 2>/dev/null || true
systemctl is-active nginx semi-e187-backend semi-e187-frontend
systemctl show -p WorkingDirectory --value semi-e187-backend
systemctl show -p WorkingDirectory --value semi-e187-frontend
sudo nginx -t
curl -L -sS -o /dev/null -w 'site=%{http_code} %{url_effective}\n' https://lularm.com/
curl -L -sS -o /dev/null -w 'admin=%{http_code} %{url_effective}\n' https://lularm.com/admin/
```

- [x] Verify the hostname is `semi187-portal` and inventory the host.
- [x] Record that the VM is fresh: `/srv` is empty, the application services do not exist, and no service is listening on ports 80, 443, 8000, or 3100.
- [x] Record that `lularm.com` currently resolves through Cloudflare to another environment; its HTTP 200 response is not a health check for this VM.

### Task 1B: Bootstrap the approved runtime

**Files:** System packages; `/srv/semi-e187`; `/etc/semi-e187`; system account `deploy`.

- [x] After action-time approval, install only the runtime packages:

```bash
set -euo pipefail
sudo apt-get update
sudo apt-get install -y --no-install-recommends \
  git nginx curl ca-certificates build-essential gettext \
  python3-venv python3-dev libpq-dev libjpeg-dev zlib1g-dev libwebp-dev \
  redis-server postgresql postgresql-client nodejs npm
```

- [x] Create the non-login deployment account and directory layout without deleting anything:

```bash
set -euo pipefail
id deploy >/dev/null 2>&1 || sudo useradd --system --create-home --home-dir /home/deploy --shell /usr/sbin/nologin deploy
sudo install -d -o deploy -g deploy \
  /srv/semi-e187/releases \
  /srv/semi-e187/shared/media \
  /srv/semi-e187/backups
sudo install -d -o root -g root -m 0750 /etc/semi-e187
sudo systemctl enable --now postgresql redis-server
```

- [x] Verify installed versions and services before creating any database, environment file, systemd unit, or Nginx site:

```bash
python3 --version
node --version
npm --version
psql --version
nginx -v
systemctl is-active postgresql redis-server
```

- [ ] Decision gate: obtain the approved data source (existing PostgreSQL/media migration or a new empty site) and confirm the customer gateway/DNS route for `https://lularm.com` before public cutover.

### Task 2: Verify and package local `main`

**Files:** Read-only Git worktree; create a temporary archive under `.codex-tmp/deploy/`.

- [ ] Run locally in PowerShell:

```powershell
cd D:\Ian\github\bakerydemo
git fetch origin
git switch main
git pull --ff-only origin main
git status --short --branch
git rev-parse HEAD
git rev-parse origin/main
```

- [ ] Require a clean tracked worktree and matching `HEAD`/`origin/main` commits.
- [ ] Run release checks before creating the archive:

```powershell
.\.venv\Scripts\python.exe manage.py check --settings=bakerydemo.settings.test
$oldDatabaseUrl = $env:DATABASE_URL
$oldUtf8 = $env:PYTHONUTF8
try {
  $env:DATABASE_URL = 'sqlite:///:memory:'
  $env:PYTHONUTF8 = '1'
  .\.venv\Scripts\python.exe manage.py test --settings=bakerydemo.settings.test
  uvx prek run --all-files
} finally {
  if ($null -eq $oldDatabaseUrl) { Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue } else { $env:DATABASE_URL = $oldDatabaseUrl }
  if ($null -eq $oldUtf8) { Remove-Item Env:PYTHONUTF8 -ErrorAction SilentlyContinue } else { $env:PYTHONUTF8 = $oldUtf8 }
}
cd .\nuxt-bakery-demo
npm ci
npm test
npm run typecheck
npm run build
cd ..
```

- [ ] Stop if `npm ci` reports an out-of-sync `package-lock.json`; do not substitute `npm install` on the production deployment.
- [ ] Create and hash the tracked-files-only archive:

```powershell
$commit = git rev-parse --short=7 HEAD
New-Item -ItemType Directory -Force .codex-tmp\deploy | Out-Null
git archive --format=tar.gz --output ".codex-tmp\deploy\bakerydemo-$commit.tar.gz" HEAD
Get-FileHash ".codex-tmp\deploy\bakerydemo-$commit.tar.gz" -Algorithm SHA256
```

### Task 3: Upload and stage the release

**Files:** Upload the archive through the RVP file manager to `/tmp/`; create `/srv/semi-e187/releases/<timestamp>-<commit>`.

- [ ] Upload only `bakerydemo-<commit>.tar.gz` after verifying that it contains no `.env`, database, static export, or `rbac/` files.
- [ ] Run on the VM:

```bash
set -euo pipefail
commit=<approved-full-commit>
short_commit=${commit:0:7}
release_id="$(date +%Y%m%d-%H%M%S)-${short_commit}"
archive="/tmp/bakerydemo-${short_commit}.tar.gz"
release="/srv/semi-e187/releases/${release_id}"
test -s "$archive"
sudo install -d -o deploy -g deploy "$release"
sudo -u deploy tar -xzf "$archive" -C "$release"
printf '%s\n' "$commit" | sudo -u deploy tee "$release/DEPLOYED_COMMIT" >/dev/null
```

- [ ] Link shared media without replacing existing files:

```bash
sudo install -d -o deploy -g deploy /srv/semi-e187/shared/media
sudo -u deploy rm -rf "$release/bakerydemo/media"
sudo -u deploy ln -s /srv/semi-e187/shared/media "$release/bakerydemo/media"
```

### Task 4: Build the staged release without changing live services

- [ ] Build the Python environment:

```bash
sudo -u deploy python3 -m venv "$release/.venv"
sudo -u deploy "$release/.venv/bin/pip" install --upgrade pip
sudo -u deploy "$release/.venv/bin/pip" install -r "$release/requirements.txt"
```

- [ ] Build Nuxt reproducibly:

```bash
sudo -u deploy bash -lc "cd '$release/nuxt-bakery-demo' && npm ci && npm run build"
```

- [ ] Run Django checks with the production environment without printing environment values:

```bash
sudo bash -lc "set -a; source /etc/semi-e187/backend.env; set +a; cd '$release'; '$release/.venv/bin/python' manage.py check"
```

### Task 5: Back up and apply database/static changes

- [ ] Back up the production database before migrations:

```bash
backup="/srv/semi-e187/backups/pre-${release_id}.dump"
sudo install -d -o deploy -g deploy /srv/semi-e187/backups
sudo bash -lc "set -a; source /etc/semi-e187/backend.env; set +a; pg_dump --format=custom --file='$backup' \"\$DATABASE_URL\""
sudo chown deploy:deploy "$backup"
test -s "$backup"
```

- [ ] Review and apply migrations, then collect static files:

```bash
sudo bash -lc "set -a; source /etc/semi-e187/backend.env; set +a; cd '$release'; '$release/.venv/bin/python' manage.py migrate --plan"
sudo bash -lc "set -a; source /etc/semi-e187/backend.env; set +a; cd '$release'; '$release/.venv/bin/python' manage.py migrate --noinput"
sudo bash -lc "set -a; source /etc/semi-e187/backend.env; set +a; cd '$release'; '$release/.venv/bin/python' manage.py collectstatic --noinput"
```

### Task 6: Atomic cutover with rollback

- [ ] Record the current target and switch only after every previous step passes:

```bash
old_target="$(readlink -f /srv/semi-e187/app)"
sudo systemctl stop semi-e187-frontend semi-e187-backend
sudo ln -sfn "$release" /srv/semi-e187/app
if ! sudo systemctl start semi-e187-backend semi-e187-frontend; then
  sudo ln -sfn "$old_target" /srv/semi-e187/app
  sudo systemctl restart semi-e187-backend semi-e187-frontend
  exit 1
fi
```

- [ ] If either service or HTTP verification fails, immediately restore `$old_target` and restart both services.

### Task 7: Production verification and handoff

- [ ] Verify the deployed commit, services, HTTP pages, and error logs:

```bash
cat /srv/semi-e187/app/DEPLOYED_COMMIT
systemctl is-active nginx semi-e187-backend semi-e187-frontend
curl -L -sS -o /dev/null -w 'site=%{http_code} %{url_effective}\n' https://lularm.com/
curl -L -sS -o /dev/null -w 'admin=%{http_code} %{url_effective}\n' https://lularm.com/admin/
curl -L -sS -o /dev/null -w 'hello=%{http_code} %{url_effective}\n' https://lularm.com/account/security/windows-hello/login/
sudo journalctl -u semi-e187-backend -u semi-e187-frontend --since '10 minutes ago' -p err --no-pager
```

- [ ] Remove only the uploaded `/tmp/bakerydemo-<commit>.tar.gz` after verification.
- [ ] Retain the previous release and database backup until the user explicitly approves cleanup.
