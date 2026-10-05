# SEMI E187 Linux 前後台、PostgreSQL 與 Windows Hello 部署手冊

最後更新：2026-09-17

## 1. 文件目的

本手冊說明如何在 Ubuntu 24.04 LTS 上部署 SEMI E187 專案，包括：

- Nuxt 前台
- Wagtail／Django 後台
- PostgreSQL 18
- Redis 登入失敗限制快取
- Windows Hello／WebAuthn 無密碼登入
- systemd 服務
- Nginx 反向代理
- HTTPS 憑證
- Windows PostgreSQL 與媒體檔案移轉
- 更新、備份、還原及問題排除

本流程不使用 Docker，並假設 PostgreSQL、Redis、Wagtail、Nuxt 與 Nginx 安裝在同一台 Linux 主機。

文件中的正式網域暫時使用 `semi.example.com`。部署前必須全部替換成實際網域。

> Windows Hello 在使用者的 Windows 電腦上執行。Linux 伺服器不需要安裝指紋辨識器驅動，也不保存指紋、Windows PIN 或私密金鑰。

## 2. 部署前重要確認

Windows Hello 功能必須先完成測試並合併至 `main`，再部署正式環境。正式伺服器不要直接部署開發中的 worktree 或含有未提交變更的分支。

部署時記錄版本：

```bash
cd /srv/semi-e187/app
git status --short --branch
git rev-parse HEAD
```

確認以下檔案已存在：

```bash
test -f bakerydemo/account_security/passkeys.py
test -f bakerydemo/account_security/migrations/0003_passkeycredential_passkeyauditevent_passkeyenrolment_and_more.py
test -f bakerydemo/account_security/migrations/0004_passkeyenrolment_passkey_one_pending_per_user.py
```

任一檔案不存在時，代表目前版本尚未包含完整 Windows Hello 功能，應停止部署並先處理版本整合。

## 3. 部署完成後的網址

| 功能 | 網址 |
|---|---|
| 網站入口 | `https://semi.example.com/` |
| 英文版 | `https://semi.example.com/en/` |
| 繁體中文版 | `https://semi.example.com/zh-tw/` |
| Wagtail 後台 | `https://semi.example.com/admin/` |
| Django 管理後台 | `https://semi.example.com/django-admin/` |
| Windows Hello 登入 | `https://semi.example.com/account/security/windows-hello/login/` |
| Windows Hello 註冊 | `https://semi.example.com/account/security/windows-hello/enrol/` |

## 4. 系統架構與連接埠

| 元件 | 監聽位址 | 是否公開 | 用途 |
|---|---|---|---|
| Nginx | `0.0.0.0:80`、`0.0.0.0:443` | 是 | HTTPS、靜態檔案與反向代理 |
| Nuxt 前台 | `127.0.0.1:3100` | 否 | SSR 前台與 `/api/bakery/` |
| Wagtail 後台 | `127.0.0.1:8000` | 否 | 後台、API、媒體與 WebAuthn |
| PostgreSQL | `127.0.0.1:5432` | 否 | 網站內容、帳號、Passkey 公開金鑰與稽核紀錄 |
| Redis | `127.0.0.1:6379` | 否 | 跨 uWSGI Worker 的登入失敗計數與暫時鎖定 |

對外只開放 SSH、HTTP 與 HTTPS，不要開放 `3100`、`8000`、`5432` 或 `6379`。

> 路由注意事項：不要把整個 `/api/` 都轉送到 Wagtail。Nuxt 使用 `/api/bakery/`，Wagtail 使用 `/api/v2/` 與 `/api/site-settings/`。

## 5. DNS 設定

在網域管理介面建立 A Record：

```text
semi.example.com -> Linux 主機公開 IP
```

確認 DNS：

```bash
nslookup semi.example.com
```

開始註冊正式 Windows Hello 憑證前，DNS 與 HTTPS 必須已完成並固定。變更 WebAuthn RP ID 會讓既有憑證無法使用。

## 6. 安裝系統套件

```bash
sudo apt update
sudo apt upgrade -y

sudo apt install -y \
  git nginx curl ca-certificates build-essential gettext snapd \
  python3.12 python3.12-venv python3.12-dev \
  libpq-dev libjpeg-dev zlib1g-dev libwebp-dev \
  redis-server
```

建立部署帳號與程式目錄：

```bash
sudo adduser --disabled-password --gecos "" deploy
sudo install -d -o deploy -g deploy /srv/semi-e187
```

## 7. 安裝 PostgreSQL 18

### 7.1 加入 PostgreSQL 官方 Ubuntu 套件庫

```bash
sudo apt install -y postgresql-common
sudo /usr/share/postgresql-common/pgdg/apt.postgresql.org.sh

sudo apt update
sudo apt install -y postgresql-18 postgresql-client-18
```

啟動並設定開機自動啟動：

```bash
sudo systemctl enable --now postgresql
sudo systemctl status postgresql --no-pager
psql --version
```

### 7.2 建立資料庫專用密碼

產生 64 字元、可安全放入 `DATABASE_URL` 的十六進位密碼：

```bash
openssl rand -hex 32
```

將結果保存在組織核准的密碼管理器，不要加入 Git。

### 7.3 建立角色與資料庫

```bash
sudo -u postgres psql
```

進入 PostgreSQL 後執行：

```sql
CREATE ROLE semi_app LOGIN;
\password semi_app

CREATE DATABASE semi_e187
    OWNER semi_app
    ENCODING 'UTF8'
    TEMPLATE template0;

\q
```

測試連線：

```bash
psql -h 127.0.0.1 -U semi_app -d semi_e187 -W \
  -c "SELECT current_database(), current_user, version();"
```

PostgreSQL 與網站在同一台主機時，不需要接受外部連線，也不要在防火牆開放 `5432`。

## 8. 設定 Redis

啟動並設定開機自動啟動：

```bash
sudo systemctl enable --now redis-server
sudo systemctl status redis-server --no-pager
redis-cli ping
```

正常結果：

```text
PONG
```

確認只監聽本機位址：

```bash
sudo ss -lntp | grep 6379
```

Redis 在本專案只保存短暫的登入失敗計數，不保存網站內容。Redis 故障時，Windows Hello 登入限制會採取安全拒絕，不應忽略故障後繼續驗證。

## 9. 下載專案程式

```bash
sudo -iu deploy

git clone https://github.com/ianli0623/bakerydemo.git \
  /srv/semi-e187/app

cd /srv/semi-e187/app
git checkout main
git pull --ff-only
git status --short --branch
git rev-parse HEAD

exit
```

若 GitHub Repository 是私人專案，請先替 `deploy` 帳號設定唯讀 GitHub Deploy Key。

建議正式部署使用已核准的 Git tag 或明確 commit，不要依賴未記錄的分支最新狀態。

## 10. 安裝 Python 後端

```bash
sudo -iu deploy
cd /srv/semi-e187/app

python3.12 -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip wheel
pip install -r requirements/production.txt

python -c "import webauthn; print('webauthn import OK')"

exit
```

`requirements/production.txt` 會間接載入 `requirements/base.txt`，其中包含 `webauthn` 套件。

## 11. 安裝 Node.js 24

目前專案的 `.nvmrc` 指定 Node.js 24。

```bash
sudo -iu deploy

curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.6/install.sh | bash

export NVM_DIR="$HOME/.nvm"
source "$NVM_DIR/nvm.sh"

cd /srv/semi-e187/app
nvm install
nvm use

node --version
npm --version

exit
```

## 12. 建立正式環境變數

### 12.1 建立設定目錄

```bash
sudo install -d -m 750 -o root -g deploy /etc/semi-e187
```

建議產生三組不同的值：

```bash
# Django SECRET_KEY
openssl rand -hex 64

# PostgreSQL 密碼
openssl rand -hex 32

# ADMIN_PASSWORD：將 Aa1! 與隨機值接在一起
printf 'Aa1!'
openssl rand -hex 24
```

三組值不得相同，也不得提交至 GitHub。

### 12.2 後端設定

```bash
sudo nano /etc/semi-e187/backend.env
```

填入：

```dotenv
DJANGO_SETTINGS_MODULE=bakerydemo.settings.production
DJANGO_SECRET_KEY=PASTE_RANDOM_SECRET_KEY
DJANGO_ALLOWED_HOSTS=semi.example.com
PRIMARY_HOST=semi.example.com
DATABASE_URL=postgresql://semi_app:PASTE_DB_PASSWORD@127.0.0.1:5432/semi_e187
REDIS_URL=redis://127.0.0.1:6379
WEBAUTHN_RP_ID=semi.example.com
WEBAUTHN_ORIGIN=https://semi.example.com
ADMIN_PASSWORD=Aa1!PASTE_RANDOM_VALUE
DJANGO_LOG_LEVEL=INFO
SECURE_HSTS_SECONDS=2592000
```

注意事項：

- `PRIMARY_HOST` 不包含 `https://`。
- `WEBAUTHN_RP_ID` 只能是主機名稱，不包含協定、連接埠或路徑。
- `WEBAUTHN_ORIGIN` 必須是使用者實際開啟後台的完整 HTTPS Origin，不包含額外路徑。
- `WEBAUTHN_ORIGIN` 的主機必須等於 RP ID，或是 RP ID 的子網域。
- 使用者開始註冊後，不要任意變更 RP ID。
- 多個 `DJANGO_ALLOWED_HOSTS` 使用逗號分隔，中間不要加入空白。
- `ADMIN_PASSWORD` 是正式環境安全檢查所需的獨立密碼，至少 12 字元並符合密碼政策。
- 即使移轉既有管理者帳號，仍需設定符合規則的 `ADMIN_PASSWORD`。

### 12.3 前端設定

```bash
sudo nano /etc/semi-e187/frontend.env
```

填入：

```dotenv
NODE_ENV=production
NITRO_HOST=127.0.0.1
NITRO_PORT=3100
NUXT_BAKERY_BASE_URL=https://semi.example.com
```

`NUXT_BAKERY_BASE_URL` 使用公開 HTTPS 網域，可避免 Wagtail 圖片網址被轉換成訪客無法存取的 `127.0.0.1` 位址。

### 12.4 保護環境設定檔

```bash
sudo chown root:deploy /etc/semi-e187/backend.env
sudo chown root:deploy /etc/semi-e187/frontend.env
sudo chmod 640 /etc/semi-e187/backend.env
sudo chmod 640 /etc/semi-e187/frontend.env
```

## 13. 初始化資料庫

請依情況選擇其中一種方式。

### 13.1 全新空白網站

```bash
sudo -iu deploy
cd /srv/semi-e187/app
source .venv/bin/activate

set -a
source /etc/semi-e187/backend.env
set +a

python manage.py migrate --noinput
python manage.py createsuperuser
python manage.py collectstatic --noinput
python manage.py check --deploy \
  --settings=bakerydemo.settings.production

exit
```

### 13.2 移轉目前 Windows PostgreSQL

先不要執行 `createsuperuser`，並保持 Linux 目標資料庫為空。依照第 20 章完成資料庫與媒體檔案還原，再執行 migration、靜態檔案收集與部署檢查。

### 13.3 驗證 Windows Hello migration

```bash
sudo -iu deploy
cd /srv/semi-e187/app
source .venv/bin/activate

set -a
source /etc/semi-e187/backend.env
set +a

python manage.py showmigrations account_security

exit
```

應至少看到：

```text
[X] 0003_passkeycredential_passkeyauditevent_passkeyenrolment_and_more
[X] 0004_passkeyenrolment_passkey_one_pending_per_user
```

確認 PostgreSQL 資料表：

```bash
sudo -u postgres psql -d semi_e187 -c "\dt account_security_passkey*"
```

應包含：

- `account_security_passkeycredential`
- `account_security_passkeyenrolment`
- `account_security_passkeyauditevent`

資料表保存公開金鑰、憑證識別碼、一次性註冊碼雜湊與稽核事件；不保存指紋、Windows PIN、私密金鑰或註冊碼明文。

### 13.4 部署檢查

`check --deploy` 不得出現：

- `account_security.E001`：`ADMIN_PASSWORD` 未設定或不符合密碼政策。
- `account_security.E002`：HTTPS、HSTS 或 Secure Cookie 未完整啟用。
- `account_security.E003`：Wagtail 後台網址不是 HTTPS。
- `account_security.E004`：WebAuthn RP ID 或 Origin 未設定。
- `account_security.E005`：RP ID 格式不正確。
- `account_security.E006`：Origin 不是有效 HTTPS Origin，或不屬於 RP ID 網域。

## 14. 建置 Nuxt 前台

```bash
sudo -iu deploy
cd /srv/semi-e187/app/nuxt-bakery-demo

export NVM_DIR="$HOME/.nvm"
source "$NVM_DIR/nvm.sh"
nvm use 24

npm ci
npm test
npm run typecheck
npm run build

exit
```

建置完成後，Nuxt 正式執行入口為：

```text
.output/server/index.mjs
```

## 15. 建立 Wagtail systemd 服務

```bash
sudo nano /etc/systemd/system/semi-e187-backend.service
```

填入：

```ini
[Unit]
Description=SEMI E187 Wagtail backend
After=network.target postgresql.service redis-server.service
Requires=postgresql.service redis-server.service

[Service]
Type=simple
User=deploy
Group=deploy
WorkingDirectory=/srv/semi-e187/app
EnvironmentFile=/etc/semi-e187/backend.env
Environment=VIRTUAL_ENV=/srv/semi-e187/app/.venv
ExecStart=/srv/semi-e187/app/.venv/bin/uwsgi --master --workers 2 --threads 4 --http-socket 127.0.0.1:8000 --wsgi-file bakerydemo/wsgi.py --need-app --die-on-term --vacuum
Restart=on-failure
RestartSec=5
KillSignal=SIGTERM

[Install]
WantedBy=multi-user.target
```

Redis 讓兩個 uWSGI Worker 共用 Windows Hello 登入失敗次數。如果移除 Redis 並改用記憶體快取，每個 Worker 會有不同計數，不適合正式環境。

## 16. 建立 Nuxt systemd 服務

```bash
sudo nano /etc/systemd/system/semi-e187-frontend.service
```

填入：

```ini
[Unit]
Description=SEMI E187 Nuxt frontend
After=network.target semi-e187-backend.service
Requires=semi-e187-backend.service

[Service]
Type=simple
User=deploy
Group=deploy
WorkingDirectory=/srv/semi-e187/app/nuxt-bakery-demo
Environment=HOME=/home/deploy
EnvironmentFile=/etc/semi-e187/frontend.env
ExecStart=/bin/bash -lc 'source /home/deploy/.nvm/nvm.sh && nvm use 24 >/dev/null && exec node .output/server/index.mjs'
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

## 17. 設定 Nginx

```bash
sudo nano /etc/nginx/sites-available/semi-e187
```

填入：

```nginx
server {
    listen 80;
    listen [::]:80;

    server_name semi.example.com;
    client_max_body_size 12m;

    location /static/ {
        alias /srv/semi-e187/app/bakerydemo/collect_static/;
        access_log off;
        expires 7d;
    }

    location /media/ {
        alias /srv/semi-e187/app/bakerydemo/media/;
    }

    location ^~ /account/security/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
        add_header Cache-Control "no-store" always;
    }

    location ~ ^/(admin|django-admin|api/v2|images|documents)(/|$) {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location = /api/site-settings/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location = /sitemap.xml {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location / {
        proxy_pass http://127.0.0.1:3100;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

啟用：

```bash
sudo ln -s /etc/nginx/sites-available/semi-e187 \
  /etc/nginx/sites-enabled/semi-e187

sudo nginx -t
sudo systemctl reload nginx
```

## 18. 設定防火牆與 HTTPS

### 18.1 防火牆

```bash
sudo ufw allow OpenSSH
sudo ufw allow "Nginx Full"
sudo ufw enable
sudo ufw status
```

如果雲端供應商另有 Security Group，也只能公開：

- SSH `22`
- HTTP `80`
- HTTPS `443`

不得公開 PostgreSQL `5432`、Redis `6379`、Wagtail `8000` 或 Nuxt `3100`。

### 18.2 安裝 HTTPS 憑證

```bash
sudo snap install --classic certbot
sudo ln -sf /snap/bin/certbot /usr/local/bin/certbot

sudo certbot --nginx -d semi.example.com
sudo certbot renew --dry-run
```

重新載入 Nginx：

```bash
sudo nginx -t
sudo systemctl reload nginx
```

Windows Hello 正式註冊只能在最終 HTTPS 網域完成。不要先在伺服器 IP、臨時網域或 HTTP 網址註冊正式使用者。

## 19. 啟動前後台服務

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now semi-e187-backend
sudo systemctl enable --now semi-e187-frontend
```

查看狀態：

```bash
sudo systemctl status postgresql --no-pager
sudo systemctl status redis-server --no-pager
sudo systemctl status semi-e187-backend --no-pager
sudo systemctl status semi-e187-frontend --no-pager
sudo systemctl status nginx --no-pager
```

查看紀錄：

```bash
sudo journalctl -u semi-e187-backend -n 100 --no-pager
sudo journalctl -u semi-e187-frontend -n 100 --no-pager
sudo journalctl -u redis-server -n 100 --no-pager
```

## 20. 從 Windows 移轉 PostgreSQL 與媒體檔案

### 20.1 停止 Windows 後台寫入

備份前先停止 Windows 上的 Wagtail 後台，避免備份完成後又有人修改資料。

### 20.2 Windows 建立 PostgreSQL 備份

在 PowerShell 執行：

```powershell
New-Item -ItemType Directory -Force D:\semi-e187-backup

& "C:\Program Files\PostgreSQL\18\bin\pg_dump.exe" `
  --host 127.0.0.1 `
  --port 5432 `
  --username CURRENT_DB_USER `
  --dbname CURRENT_DB_NAME `
  --format custom `
  --no-owner `
  --no-acl `
  --file D:\semi-e187-backup\semi-e187.dump
```

將 `CURRENT_DB_USER` 與 `CURRENT_DB_NAME` 換成 Windows 實際設定。

### 20.3 備份圖片、文件與使用者照片

```powershell
tar.exe -czf D:\semi-e187-backup\semi-e187-media.tar.gz `
  -C D:\Ian\github\bakerydemo\bakerydemo media
```

PostgreSQL 只保存媒體路徑，實際圖片與文件位於 `bakerydemo/media`，因此資料庫與媒體目錄都必須搬移。

### 20.4 傳送至 Linux

```powershell
scp D:\semi-e187-backup\semi-e187.dump `
  deploy@semi.example.com:/tmp/

scp D:\semi-e187-backup\semi-e187-media.tar.gz `
  deploy@semi.example.com:/tmp/
```

### 20.5 還原至 Linux PostgreSQL

以下操作以空白 `semi_e187` 資料庫為前提。若目標資料庫已有正式資料，不可直接覆蓋，應另外建立空白資料庫測試還原。

```bash
sudo systemctl stop semi-e187-frontend semi-e187-backend

sudo -u postgres pg_restore \
  --exit-on-error \
  --no-owner \
  --role=semi_app \
  --dbname=semi_e187 \
  /tmp/semi-e187.dump
```

還原媒體目錄：

```bash
sudo tar -xzf /tmp/semi-e187-media.tar.gz \
  -C /srv/semi-e187/app/bakerydemo

sudo chown -R deploy:deploy \
  /srv/semi-e187/app/bakerydemo/media
```

### 20.6 套用新 migration

```bash
sudo -iu deploy
cd /srv/semi-e187/app
source .venv/bin/activate

set -a
source /etc/semi-e187/backend.env
set +a

python manage.py migrate --noinput
python manage.py showmigrations account_security
python manage.py collectstatic --noinput
python manage.py check --deploy \
  --settings=bakerydemo.settings.production

exit
```

啟動服務：

```bash
sudo systemctl start semi-e187-backend
sudo systemctl start semi-e187-frontend
```

### 20.7 Windows Hello 憑證移轉限制

WebAuthn 憑證受到 RP ID 約束：

```text
localhost != semi.example.com
```

若使用者原本在 `http://localhost:8000` 註冊，即使三張 Passkey 資料表完整移到 Linux，原憑證仍不能登入正式網域。正式上線後必須：

1. 使用緊急管理者密碼帳號登入。
2. 撤銷或停用舊網域憑證。
3. 為使用者產生新的 15 分鐘一次性註冊碼。
4. 請使用者在 `https://semi.example.com/account/security/windows-hello/enrol/` 重新註冊。

若來源與目標使用完全相同的 RP ID，憑證資料才可能沿用；仍應逐一實測。

## 21. Windows Hello 正式啟用流程

### 21.1 保留緊急管理者

至少保留一個不供日常使用的超級使用者密碼帳號：

- 使用獨立高強度密碼並保存於核准的密碼保管庫。
- 不要替此帳號停用密碼。
- 定期測試登入並記錄日期。
- 僅在 Windows Hello 或 Redis 全面故障、憑證全部遺失時使用。

### 21.2 建立 Windows Hello 使用者

1. 使用超級使用者登入 Wagtail。
2. 開啟「設定 → 使用者 → 新增使用者」。
3. 填寫帳號、電子郵件與姓名。
4. 指定至少一個角色群組，或授予管理者權限；角色不可留白。
5. 選擇「Windows Hello（無密碼）」登入方式。
6. 儲存並立即複製只顯示一次的註冊碼。
7. 註冊碼 15 分鐘後失效，且成功使用後不可再次使用。
8. 使用者在自己的 Windows 電腦開啟正式註冊網址，輸入帳號及註冊碼。
9. 依 Windows Hello 提示使用指紋、臉部辨識或 PIN 完成註冊。

### 21.3 既有帳號與第二台裝置

超級使用者可在「報表 → Windows Hello 管理」產生新註冊碼。每台 Windows 電腦必須分別註冊；把 ARCANITE 指紋讀取器插入另一台電腦，不會自動帶入原本的私密金鑰。

既有密碼帳號加註冊 Windows Hello 後，可以保留密碼登入。原密碼仍受密碼效期、複雜度、密碼歷史及登入失敗鎖定規則管理。

### 21.4 撤銷與重新註冊

1. 超級使用者開啟「報表 → Windows Hello 管理」。
2. 找到遺失或不再使用的憑證並撤銷。
3. 產生新的註冊碼。
4. 請使用者在新電腦或重設後的 Windows 重新註冊。

撤銷最後一組憑證前，先確認使用者有其他可用憑證、密碼登入方式或已取得新註冊碼。

## 22. 上線驗證

### 22.1 指令驗證

```bash
curl -I https://semi.example.com/en/
curl -I https://semi.example.com/zh-tw/
curl -I https://semi.example.com/admin/login/
curl -I https://semi.example.com/account/security/windows-hello/login/
curl "https://semi.example.com/api/site-settings/?locale=en"

redis-cli ping

sudo -iu deploy bash -lc '
  cd /srv/semi-e187/app &&
  source .venv/bin/activate &&
  set -a && source /etc/semi-e187/backend.env && set +a &&
  python manage.py showmigrations account_security &&
  python manage.py check --deploy --settings=bakerydemo.settings.production
'
```

### 22.2 前後台驗證

- [ ] 根網址會導向預期語系。
- [ ] 英文與繁體中文可以切換。
- [ ] 密碼管理者可以登入 Wagtail。
- [ ] 首次登入強制改密碼功能正常。
- [ ] 密碼到期提醒正常。
- [ ] 帳號登入失敗五次鎖定功能正常。
- [ ] 首頁及主要頁面均可讀取。
- [ ] 圖片、Wagtail rendition、文件及使用者照片正常。
- [ ] HTTP 自動轉向 HTTPS。
- [ ] PostgreSQL、Redis、8000 與 3100 未公開。

### 22.3 Windows Hello 驗證

請在 Windows 電腦使用 Edge 與 Chrome 實測：

- [ ] 管理者可建立 Windows Hello 使用者，且角色為必填。
- [ ] 註冊碼只顯示一次，15 分鐘後失效。
- [ ] 錯誤、過期、撤銷或重複使用的註冊碼會失敗。
- [ ] 使用 ARCANITE／Windows Hello 可完成首次註冊。
- [ ] 登出後可使用 Windows Hello 再次登入。
- [ ] Windows PIN 作為 Windows Hello 備援方式時可登入。
- [ ] 使用者取消或逾時不會建立登入 Session。
- [ ] 第二台 Windows 電腦可以另外註冊。
- [ ] 撤銷後，該憑證下一次登入立即失敗。
- [ ] 五次 WebAuthn 驗證失敗後暫停 15 分鐘。
- [ ] Redis 停止時，Windows Hello 登入會安全拒絕，而不是略過限制。
- [ ] Windows Hello 專用帳號不會被導向密碼到期頁。
- [ ] 沒有可用憑證的無密碼帳號無法進入後台。
- [ ] 緊急管理者密碼帳號仍可正常登入。
- [ ] 註冊、登入、失敗、限流與撤銷均有稽核紀錄。

網站只能確認 Windows Hello 完成了使用者驗證，無法判斷該次使用的是指紋、臉部辨識或 PIN。

## 23. 日後發布更新

更新前先備份 PostgreSQL 與 `bakerydemo/media`，並確認工作目錄沒有手動修改。

```bash
sudo -iu deploy
cd /srv/semi-e187/app

git status --short --branch
git checkout main
git pull --ff-only
git rev-parse HEAD

source .venv/bin/activate
pip install -r requirements/production.txt

set -a
source /etc/semi-e187/backend.env
set +a

python manage.py migrate --noinput
python manage.py showmigrations account_security
python manage.py collectstatic --noinput
python manage.py check --deploy \
  --settings=bakerydemo.settings.production

cd nuxt-bakery-demo
export NVM_DIR="$HOME/.nvm"
source "$NVM_DIR/nvm.sh"
nvm use 24

npm ci
npm test
npm run typecheck
npm run build

exit
```

重新啟動：

```bash
sudo systemctl restart semi-e187-backend
sudo systemctl restart semi-e187-frontend
sudo nginx -t
sudo systemctl reload nginx
```

更新後重新執行第 22 章驗證。

## 24. 備份與還原

### 24.1 PostgreSQL 備份

```bash
sudo install -d -m 700 -o postgres -g postgres \
  /var/backups/semi-e187

sudo -u postgres pg_dump -Fc \
  -d semi_e187 \
  -f /var/backups/semi-e187/semi-e187.dump
```

PostgreSQL 備份會包含帳號、公開金鑰、Credential ID、註冊碼雜湊與稽核資料，必須視為敏感資料妥善保護。

### 24.2 媒體檔案備份

```bash
sudo tar -czf \
  /var/backups/semi-e187/semi-e187-media.tar.gz \
  -C /srv/semi-e187/app/bakerydemo media
```

### 24.3 備份原則

- 將資料庫與媒體備份複製到另一台主機或受保護的物件儲存空間。
- 加密備份並限制存取權限。
- 定期測試還原。
- Redis 僅保存短暫限流狀態，不需要納入永久備份。
- 不要把備份檔提交至 Git。

## 25. 回復上一版本

程式回復前先備份現況資料庫及媒體檔案。不要在沒有完整備份的情況下反向執行 migration。

若舊版本程式可以忽略新增資料表，可切回前一個已核准 Git tag 並重新安裝相符套件、建置 Nuxt、收集靜態檔案及重新啟動服務；是否需要資料庫回復，必須先在還原測試環境驗證。

Windows Hello 已註冊憑證依賴資料庫中的公開金鑰紀錄。若回復資料庫到註冊前時間點，該時間點之後建立的憑證將無法登入。

## 26. 常見問題排除

| 問題 | 檢查方式 | 處理方向 |
|---|---|---|
| 首頁讀取失敗 | 查看前後台 `journalctl` | 確認服務啟動及 `NUXT_BAKERY_BASE_URL` |
| 圖片破圖 | 直接開啟圖片網址 | 確認 media 已搬移、權限正確且 CMS 網址為公開 HTTPS |
| 後台重複轉向 | 檢查 `X-Forwarded-Proto` | Nginx 必須傳送 `$scheme` 給 Wagtail |
| 資料庫連線失敗 | 使用 `psql -h 127.0.0.1` | 確認角色、密碼、資料庫及 PostgreSQL 服務 |
| Redis 無法連線 | `redis-cli ping`、查看 Redis journal | 確認 Redis 服務及 `REDIS_URL` |
| Windows Hello 回傳 503 | 查看 Redis 與後台 journal | Passkey 限流快取故障時會安全拒絕 |
| Windows Hello 沒有可用憑證 | 確認 RP ID 與目前網域 | 在正式網域重新產生註冊碼並註冊 |
| WebAuthn `SecurityError` | 比對網址與 `WEBAUTHN_RP_ID` | RP ID 不可包含協定、路徑或錯誤網域 |
| WebAuthn `NotAllowedError` | 確認是否取消、逾時或無可用憑證 | 重新操作或重新註冊 |
| `account_security.E004` | 檢查 WebAuthn 環境變數 | 設定 RP ID 與 Origin |
| `account_security.E005` | 檢查 RP ID 格式 | 只保留主機名稱 |
| `account_security.E006` | 檢查 Origin | 使用與正式後台一致的 HTTPS Origin |
| 502 Bad Gateway | 查看 systemd 狀態 | 確認 3100 或 8000 實際監聽 |
| 靜態檔案缺少 | 檢查 `collect_static` | 重新執行 `collectstatic` 並檢查 Nginx alias |
| 部署檢查 E001 | 檢查 `ADMIN_PASSWORD` | 設定符合密碼政策的獨立密碼 |
| 部署檢查 E003 | 檢查 `PRIMARY_HOST` | 設定正式網域且不要加入 `https://` |

常用診斷指令：

```bash
sudo systemctl status postgresql --no-pager
sudo systemctl status redis-server --no-pager
sudo systemctl status semi-e187-backend --no-pager
sudo systemctl status semi-e187-frontend --no-pager
sudo systemctl status nginx --no-pager

sudo ss -lntp
sudo nginx -t
redis-cli ping

sudo journalctl -u semi-e187-backend -n 100 --no-pager
sudo journalctl -u semi-e187-frontend -n 100 --no-pager
sudo journalctl -u redis-server -n 100 --no-pager
```

## 27. 正式上線檢查表

- [ ] Windows Hello 程式已經合併至 `main` 或核准的 release tag。
- [ ] 已記錄實際部署 commit。
- [ ] DNS 已指向正確的 Linux 公開 IP。
- [ ] PostgreSQL 使用專用 `semi_app` 角色。
- [ ] 應用程式沒有使用 `postgres` 超級使用者連線。
- [ ] Redis 只監聽本機且未對外開放。
- [ ] `backend.env` 與 `frontend.env` 權限為 `640`。
- [ ] 環境設定檔未加入 Git。
- [ ] 資料庫密碼、Django SECRET_KEY 與 ADMIN_PASSWORD 使用不同值。
- [ ] `WEBAUTHN_RP_ID` 為固定正式主機名稱。
- [ ] `WEBAUTHN_ORIGIN` 與實際後台 HTTPS Origin 完全一致。
- [ ] migration `0003`、`0004` 已套用。
- [ ] 三張 Passkey 資料表存在。
- [ ] `collectstatic` 與 `check --deploy` 已完成。
- [ ] `check --deploy` 沒有 `E001` 至 `E006`。
- [ ] `npm test`、`npm run typecheck` 與 `npm run build` 已完成。
- [ ] systemd 前後台服務已設為開機自動啟動。
- [ ] Nginx 已轉送 `/account/security/` 並禁止快取相關回應。
- [ ] 防火牆沒有開放 5432、6379、8000 與 3100。
- [ ] Certbot 自動更新測試成功。
- [ ] 至少保留一個緊急管理者密碼帳號。
- [ ] 已在 Windows Edge 與 Chrome 驗證註冊及登入。
- [ ] 已驗證撤銷、重新註冊、第二裝置與五次失敗鎖定。
- [ ] 英文、繁中、後台、圖片、文件及帳號安全流程均已驗證。
- [ ] PostgreSQL 與 media 備份存放在另一個安全位置。
- [ ] 已實際測試資料庫及媒體檔案還原。

## 28. 官方參考資料

- [Microsoft Learn：WebAuthn APIs](https://learn.microsoft.com/en-us/windows/security/identity-protection/hello-for-business/webauthn-apis)
- [W3C Web Authentication](https://www.w3.org/TR/webauthn-3/)
- [py_webauthn Registration](https://duo-labs.github.io/py_webauthn/registration.html)
- [py_webauthn Authentication](https://duo-labs.github.io/py_webauthn/authentication.html)
- [PostgreSQL Ubuntu 安裝](https://www.postgresql.org/download/linux/ubuntu/)
- [PostgreSQL pg_dump](https://www.postgresql.org/docs/18/app-pgdump.html)
- [PostgreSQL 備份與還原](https://www.postgresql.org/docs/18/backup-dump.html)
- [Django Sessions](https://docs.djangoproject.com/en/6.0/topics/http/sessions/)
- [Django 正式部署](https://docs.djangoproject.com/en/6.0/howto/deployment/)
- [Django check --deploy](https://docs.djangoproject.com/en/6.0/ref/django-admin/#cmdoption-check-deploy)
- [Nuxt Node.js 部署](https://nuxt.com/docs/3.x/getting-started/deployment)
- [Nginx 反向代理](https://nginx.org/en/docs/http/ngx_http_proxy_module.html)
- [Certbot Nginx](https://certbot.eff.org/instructions?os=snap&ws=nginx)
- [NVM](https://github.com/nvm-sh/nvm)

