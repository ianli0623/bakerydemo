# SEMI E187 全新 Ubuntu 主機軟體安裝與初始化手冊

更新日期：2026-10-21

## 1. 文件目的

本文件說明如何在全新的 Ubuntu Linux 主機安裝 SEMI E187 網站需要的基礎軟體，並建立正式環境的帳號、目錄、PostgreSQL、Redis、Nginx、systemd 與環境設定檔。

本文件以 Ubuntu 26.04 LTS x86_64 為基準。完成本文件後，再依照 [`SEMI_E187_Production_Deployment_Runbook_zh-TW.md`](SEMI_E187_Production_Deployment_Runbook_zh-TW.md) 建立第一個 release、部署程式並執行上線驗證。

## 2. 安裝原則

- 使用 Ubuntu 官方套件庫，不執行來源不明的遠端安裝腳本。
- 對外只開放經客戶核准的 HTTP／HTTPS 或管理入口。
- PostgreSQL、Redis、Django 與 Nuxt 服務只監聽本機位址。
- 正式程式以 `deploy` 系統帳號執行，不使用 `root` 執行網站服務。
- 程式使用 `/srv/semi-e187/releases/` 的不可變 release，`/srv/semi-e187/app` 只作為目前版本的軟連結。
- 密碼、Token、Client Secret 只放在 `/etc/semi-e187/*.env` 或組織核准的密碼管理器，不加入 Git。
- 不在全新主機直接執行 `apt upgrade`、重新開機、防火牆變更或憑證申請，除非已取得客戶核准並確認遠端管理不會中斷。

## 3. 部署前需要確認的資料

開始前應向客戶確認：

| 項目 | 說明 |
| --- | --- |
| 主機資訊 | 主機名稱、Ubuntu 版本、CPU、RAM、磁碟與時區 |
| 管理方式 | RVP Web Terminal、SSH 或其他經核准的管道 |
| 正式網域 | `e187.tw`、`www.e187.tw` 是否都導向本主機或客戶閘道 |
| HTTPS | 憑證由客戶閘道終止，或由本機 Nginx／Certbot 管理 |
| 網路規則 | 允許的來源 IP、對外連接埠及是否另有 Security Group |
| 資料來源 | 建立空白資料庫，或移轉既有 PostgreSQL 與媒體檔案 |
| Fast-ID | Base URL、Tenant、Client、管理 Token、RP ID 與允許的 Origin |
| 管理者帳號 | 由客戶指定建立方式；不要在環境檔保存管理者密碼 |

## 4. 確認主機與資源

登入新主機後，先執行唯讀檢查：

```bash
hostnamectl
uname -a
cat /etc/os-release
id
date --iso-8601=seconds
timedatectl
df -h /
free -h
ip address
```

確認項目：

- 作業系統為核准的 Ubuntu LTS x86_64。
- 目前登入的是客戶指定的管理帳號。
- 根目錄有足夠空間存放多個 release、套件、媒體與備份。
- 時間與 NTP 同步正常。
- 主機名稱與目標資產一致，避免操作到其他環境。

如客戶要求台北時區，可在核准後設定：

```bash
sudo timedatectl set-timezone Asia/Taipei
timedatectl
```

## 5. 更新套件索引並安裝系統軟體

只更新套件索引，不在未核准的情況下執行整套作業系統升級：

```bash
sudo apt-get update
```

安裝專案需要的軟體：

```bash
sudo apt-get install -y --no-install-recommends \
  git \
  nginx \
  libnginx-mod-http-headers-more-filter \
  curl \
  ca-certificates \
  openssl \
  build-essential \
  gettext \
  python3 \
  python3-venv \
  python3-dev \
  libpq-dev \
  libjpeg-dev \
  zlib1g-dev \
  libwebp-dev \
  postgresql \
  postgresql-client \
  redis-server \
  nodejs \
  npm
```

確認版本：

```bash
git --version
python3 --version
node --version
npm --version
psql --version
redis-server --version
nginx -v
openssl version
```

本專案 `nuxt-bakery-demo/package.json` 要求 Node.js `>=22`。若 Ubuntu 套件提供的 Node.js 低於 22，停止安裝並由系統管理者核准 Node.js 來源；不要自行執行網路上的安裝腳本。

可用下列指令檢查 Node.js 主版本：

```bash
node_major="$(node --version | sed -E 's/^v([0-9]+).*/\1/')"
test "$node_major" -ge 22
```

## 6. 建立部署帳號與目錄

建立不可互動登入的 `deploy` 系統帳號：

```bash
id deploy >/dev/null 2>&1 || \
  sudo useradd \
    --system \
    --create-home \
    --home-dir /home/deploy \
    --shell /usr/sbin/nologin \
    deploy
```

建立程式、共用資料及備份目錄：

```bash
sudo install -d -o deploy -g deploy \
  /srv/semi-e187/releases \
  /srv/semi-e187/shared/media \
  /srv/semi-e187/backups

sudo install -d -m 0750 -o root -g deploy \
  /etc/semi-e187
```

確認權限：

```bash
id deploy
ls -ld \
  /srv/semi-e187 \
  /srv/semi-e187/releases \
  /srv/semi-e187/shared/media \
  /srv/semi-e187/backups \
  /etc/semi-e187
```

`/srv/semi-e187/app` 不要先建立成一般目錄。完成第一個 release 後，由部署流程建立指向 release 的軟連結。

## 7. 初始化 PostgreSQL

### 7.1 啟動服務

```bash
sudo systemctl enable --now postgresql
sudo systemctl status postgresql --no-pager
```

### 7.2 建立應用程式角色與資料庫

先產生資料庫密碼：

```bash
openssl rand -hex 32
```

將結果存入組織核准的密碼管理器，不要貼到部署紀錄或 Git。

開啟 PostgreSQL 管理介面：

```bash
sudo -u postgres psql
```

在 `psql` 中執行：

```sql
CREATE ROLE bakery_user LOGIN;
\password bakery_user

CREATE DATABASE semie187
    OWNER bakery_user
    ENCODING 'UTF8'
    TEMPLATE template0;

\q
```

測試本機連線：

```bash
psql -h 127.0.0.1 \
  -U bakery_user \
  -d semie187 \
  -W \
  -c "SELECT current_database(), current_user;"
```

確認 PostgreSQL 只監聽核准的位址：

```bash
sudo ss -lntp | grep 5432
```

網站與資料庫位於同一台主機時，不需要對外開放 `5432`。

## 8. 初始化 Redis

```bash
sudo systemctl enable --now redis-server
sudo systemctl status redis-server --no-pager
redis-cli ping
```

正常結果為：

```text
PONG
```

確認 Redis 只監聽本機位址：

```bash
sudo ss -lntp | grep 6379
```

Redis 用於登入失敗計數與暫時鎖定，不保存網站內容。不得將 `6379` 開放到外部網路。

## 9. 建立正式環境設定檔

### 9.1 產生 Django Secret Key

```bash
openssl rand -hex 64
```

Secret Key 與資料庫密碼必須使用不同值。

### 9.2 建立後端設定

```bash
sudoedit /etc/semi-e187/backend.env
```

依正式環境填入下列欄位；範例值必須全部替換：

```dotenv
DJANGO_SETTINGS_MODULE=bakerydemo.settings.production
DJANGO_SECRET_KEY=REPLACE_WITH_RANDOM_SECRET
DJANGO_ALLOWED_HOSTS=e187.tw,www.e187.tw
PRIMARY_HOST=e187.tw
DATABASE_URL=postgresql://bakery_user:REPLACE_WITH_DB_PASSWORD@127.0.0.1:5432/semie187
REDIS_URL=redis://127.0.0.1:6379
WEBAUTHN_RP_ID=e187.tw
WEBAUTHN_ORIGIN=https://e187.tw
DJANGO_LOG_LEVEL=INFO
SECURE_HSTS_SECONDS=2592000

FAST_ID_ENABLED=false
FAST_ID_BASE_URL=REPLACE_WITH_FAST_ID_API_ORIGIN
FAST_ID_TENANT_ID=REPLACE_WITH_TENANT_ID
FAST_ID_TENANT_KEY=REPLACE_WITH_TENANT_KEY
FAST_ID_CLIENT_ID=REPLACE_WITH_CLIENT_ID
FAST_ID_CLIENT_SECRET=REPLACE_WITH_CLIENT_SECRET
FAST_ID_MANAGEMENT_API_TOKEN=REPLACE_WITH_ROTATED_MANAGEMENT_TOKEN
FAST_ID_RP_ID=e187.tw
FAST_ID_ORIGIN=https://e187.tw
FAST_ID_TIMEOUT_SECONDS=5
```

設定原則：

- `PRIMARY_HOST` 與 RP ID 只填主機名稱，不包含 `https://` 或路徑。
- Origin 必須是實際使用的 HTTPS Origin。
- Fast-ID 管理平台必須允許正式 Origin。
- Client Secret、管理 Token 及使用者 Token 只能留在 Django 伺服器端。
- Fast-ID 未完成正式驗證前保持 `FAST_ID_ENABLED=false`。
- 不在環境檔加入管理者密碼或臨時緊急密碼。

### 9.3 建立前端設定

```bash
sudoedit /etc/semi-e187/frontend.env
```

填入：

```dotenv
NODE_ENV=production
NITRO_HOST=127.0.0.1
NITRO_PORT=3100
NUXT_BAKERY_BASE_URL=https://e187.tw
```

### 9.4 設定檔權限

```bash
sudo chown root:deploy \
  /etc/semi-e187/backend.env \
  /etc/semi-e187/frontend.env

sudo chmod 0640 \
  /etc/semi-e187/backend.env \
  /etc/semi-e187/frontend.env
```

只檢查欄位名稱，不輸出值：

```bash
sudo awk -F= '
  /^[A-Z0-9_]+=/ { print $1 }
' /etc/semi-e187/backend.env

sudo awk -F= '
  /^[A-Z0-9_]+=/ { print $1 }
' /etc/semi-e187/frontend.env
```

## 10. 建立 systemd 服務

建立服務前，第一個 release 必須已依正式部署手冊完成建置，且 `/srv/semi-e187/app` 已指向該 release。

### 10.1 Django／Wagtail 後端服務

建立 `/etc/systemd/system/semi-e187-backend.service`：

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
TimeoutStartSec=60
TimeoutStopSec=30
PrivateTmp=true
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
```

### 10.2 Nuxt 前端服務

建立 `/etc/systemd/system/semi-e187-frontend.service`：

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
EnvironmentFile=/etc/semi-e187/frontend.env
Environment=NODE_ENV=production
ExecStart=/usr/bin/node /srv/semi-e187/app/nuxt-bakery-demo/.output/server/index.mjs
Restart=on-failure
RestartSec=5
TimeoutStartSec=60
TimeoutStopSec=30
PrivateTmp=true
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
```

重新載入 systemd，但在 release、migration 與靜態檔案尚未準備完成前不要啟動服務：

```bash
sudo systemctl daemon-reload
sudo systemctl cat semi-e187-backend
sudo systemctl cat semi-e187-frontend
```

## 11. 設定 Nginx

`lularm.com` 測試環境的完整設定已納入 Git：
`deploy/nginx/semi-e187.conf`。在該測試機更新時，先備份現有設定，
再安裝受版控檔案：

```bash
cd /srv/semi-e187/app
timestamp="$(date +%Y%m%d-%H%M%S)"
sudo cp -a \
  /etc/nginx/sites-available/semi-e187 \
  "/etc/nginx/sites-available/semi-e187.bak-${timestamp}"
sudo install -o root -g root -m 0644 \
  deploy/nginx/semi-e187.conf \
  /etc/nginx/sites-available/semi-e187
sudo nginx -t && sudo systemctl reload nginx
```

下列設定則是全新 `e187.tw` 環境的基礎範例；網域及憑證仍須依客戶
核准資料調整。安全標頭使用 `headers-more`，避免
`/account/security/` 自訂 `Cache-Control` 時破壞 Nginx 原生
`add_header` 的繼承。

建立 `/etc/nginx/sites-available/semi-e187`：

```nginx
server {
    listen 80;
    listen [::]:80;

    server_name e187.tw www.e187.tw;
    client_max_body_size 12m;

    server_tokens off;
    more_clear_headers 'Server';
    more_clear_headers 'X-Powered-By';
    more_set_headers "Content-Security-Policy: frame-ancestors 'self'; object-src 'none'; base-uri 'self';";
    more_set_headers "X-Frame-Options: SAMEORIGIN";

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

停用 Ubuntu 預設網站並啟用專案網站：

```bash
sudo test -e /etc/nginx/sites-enabled/default \
  && sudo unlink /etc/nginx/sites-enabled/default \
  || true

sudo ln -sfn \
  /etc/nginx/sites-available/semi-e187 \
  /etc/nginx/sites-enabled/semi-e187

sudo nginx -t \
  && sudo systemctl enable --now nginx \
  && sudo systemctl reload nginx
```

若客戶的閘道會在 VM 前方終止 HTTPS，必須確認閘道會傳遞原始 Host 與 HTTPS 協定資訊。未經客戶確認，不要自行在 VM 申請另一張憑證或變更閘道路由。

## 12. 設定 HTTPS

依客戶網路架構選擇一種方式。

### 12.1 客戶閘道終止 HTTPS

客戶負責公開憑證，並將流量轉送至 `semi187-portal` 的 HTTP `80` 或指定內部連接埠。確認：

- `e187.tw` 與 `www.e187.tw` 都導向同一套服務。
- 閘道傳遞正確的 `Host`、`X-Forwarded-For` 與原始 HTTPS 狀態。
- VM 的 HTTP 連接埠只允許客戶閘道或核准來源存取。
- 公開網站以 HTTPS 開啟，瀏覽器不顯示憑證錯誤。

### 12.2 VM 上的 Nginx 終止 HTTPS

只有在 DNS 已指向本機、`80`／`443` 可由憑證機構連線且客戶核准後，才安裝 Certbot：

```bash
sudo apt-get install -y --no-install-recommends \
  certbot \
  python3-certbot-nginx

sudo certbot --nginx \
  -d e187.tw \
  -d www.e187.tw

sudo certbot renew --dry-run
sudo nginx -t && sudo systemctl reload nginx
```

正式 WebAuthn／Fast-ID 註冊只能在最終 HTTPS 網域執行。變更 RP ID 或 Origin 可能使既有 Passkey 無法使用。

## 13. 網路與防火牆原則

本專案需要的連接埠：

| 連接埠 | 綁定位址 | 是否公開 | 用途 |
| --- | --- | --- | --- |
| `80` | `0.0.0.0`／`::` | 依閘道架構 | HTTP 或閘道轉送 |
| `443` | `0.0.0.0`／`::` | VM 終止 TLS 時公開 | HTTPS |
| `3100` | `127.0.0.1` | 否 | Nuxt |
| `8000` | `127.0.0.1` | 否 | Django／Wagtail |
| `5432` | `127.0.0.1` | 否 | PostgreSQL |
| `6379` | `127.0.0.1` | 否 | Redis |

確認監聽狀態：

```bash
sudo ss -lntp
```

如果主機透過 RVP 管理且沒有標準 SSH，或前方另有客戶防火牆／Security Group，不要直接執行 `ufw enable`。先向客戶確認管理來源與回復方式，避免封鎖自己的管理連線。

## 14. 建立第一個程式 release

執行正式部署手冊的下列章節：

1. 本機部署前檢查。
2. 建立新 release。
3. 建置 Python 後端與 Nuxt 前台。
4. 執行 Django `manage.py check`。
5. 建立 `/srv/semi-e187/app` 軟連結。

首次部署尚無舊版本可回復，因此切換前必須先確認：

```bash
test -f "$release/DEPLOYED_COMMIT"
test -x "$release/.venv/bin/python"
test -f "$release/nuxt-bakery-demo/.output/server/index.mjs"
test -L "$release/bakerydemo/media"
```

建立目前版本連結：

```bash
sudo ln -s "$release" /srv/semi-e187/app
readlink -f /srv/semi-e187/app
```

如果 `/srv/semi-e187/app` 已存在，停止操作並先確認內容；不要直接覆蓋。

## 15. 初始化或移轉資料庫

### 15.1 全新空白資料庫

```bash
sudo bash -lc \
  "set -a; source /etc/semi-e187/backend.env; set +a; \
   cd /srv/semi-e187/app; \
   .venv/bin/python manage.py migrate --noinput; \
   .venv/bin/python manage.py collectstatic --noinput; \
   .venv/bin/python manage.py check --deploy \
     --settings=bakerydemo.settings.production"
```

依客戶核准流程建立第一個管理者：

```bash
sudo bash -lc \
  "set -a; source /etc/semi-e187/backend.env; set +a; \
   cd /srv/semi-e187/app; \
   .venv/bin/python manage.py createsuperuser"
```

管理者密碼由操作人員在隱藏提示中輸入，不保存於命令、環境檔或部署文件。

### 15.2 移轉既有資料

若需要移轉既有 PostgreSQL 與媒體檔案：

1. 不執行 `createsuperuser`。
2. 保持目標資料庫為空。
3. 停止來源環境寫入。
4. 建立並驗證 PostgreSQL custom-format 備份。
5. 備份媒體、圖片、文件及使用者照片。
6. 還原資料與媒體後再執行 migration、`collectstatic` 及部署檢查。

資料移轉屬於獨立的高風險作業，必須另行確認來源、目標、停機時間、備份及回復方式。

## 16. 啟動服務

資料庫、release、環境檔及靜態檔案都準備完成後：

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now semi-e187-backend
sudo systemctl enable --now semi-e187-frontend
sudo systemctl enable --now nginx
```

確認狀態：

```bash
systemctl is-active \
  postgresql \
  redis-server \
  nginx \
  semi-e187-backend \
  semi-e187-frontend
```

五個服務都應顯示 `active`。

## 17. 安裝完成驗證

### 17.1 本機服務

```bash
curl -sS -o /dev/null -w 'backend=%{http_code}\n' \
  http://127.0.0.1:8000/admin/

curl -sS -o /dev/null -w 'frontend=%{http_code}\n' \
  http://127.0.0.1:3100/

sudo nginx -t
```

### 17.2 公開網址

```bash
curl -L -sS -o /dev/null \
  -w 'site=%{http_code} %{url_effective}\n' \
  https://e187.tw/

curl -L -sS -o /dev/null \
  -w 'www=%{http_code} %{url_effective}\n' \
  https://www.e187.tw/

curl -L -sS -o /dev/null \
  -w 'admin=%{http_code} %{url_effective}\n' \
  https://e187.tw/admin/
```

### 17.3 錯誤日誌

```bash
sudo journalctl -u postgresql -n 100 --no-pager
sudo journalctl -u redis-server -n 100 --no-pager
sudo journalctl -u nginx -n 100 --no-pager
sudo journalctl -u semi-e187-backend -n 100 --no-pager
sudo journalctl -u semi-e187-frontend -n 100 --no-pager
```

### 17.4 瀏覽器驗證

至少確認：

1. 繁體中文與英文頁面可正常開啟。
2. 圖片、CSS 與 JavaScript 正常載入。
3. 上方選單與頁面路由正常。
4. `/admin/` 可以開啟登入頁。
5. 管理者可登入 Wagtail。
6. 測試新增及讀取內容。
7. Email 密碼登入正常。
8. HTTPS、WebAuthn RP ID 與 Origin 確認後，再測試 Fast-ID／Windows Hello。

## 18. 安裝完成檢查表

### 系統與套件

- [ ] 已確認主機名稱、Ubuntu 版本、時間與資源。
- [ ] 已安裝 Git、Python、Node.js、PostgreSQL、Redis、Nginx 與編譯套件。
- [ ] Node.js 主版本為 22 以上。
- [ ] PostgreSQL、Redis 與 Nginx 已設定開機啟動。

### 帳號與目錄

- [ ] 已建立不可互動登入的 `deploy` 系統帳號。
- [ ] 已建立 releases、shared、backups 與 `/etc/semi-e187`。
- [ ] `/srv/semi-e187/app` 是 release 軟連結，不是一般程式目錄。
- [ ] 媒體目錄位於 `/srv/semi-e187/shared/media`。

### 資料與機密

- [ ] 已建立 `semie187` 資料庫及專用角色。
- [ ] PostgreSQL 與 Redis 未對外開放。
- [ ] `backend.env` 與 `frontend.env` 權限為 `0640`、擁有者為 `root:deploy`。
- [ ] 環境檔沒有管理者密碼。
- [ ] Git 沒有 `.env`、資料庫備份、媒體備份或 Token。

### 網站服務

- [ ] systemd 服務檔與 Nginx 設定已通過檢查。
- [ ] Nginx 正確區分 Nuxt 與 Django 路由。
- [ ] HTTPS 憑證與終止位置已由客戶確認。
- [ ] 只公開核准的 HTTP／HTTPS 或管理入口。
- [ ] 五個必要服務皆為 `active`。
- [ ] 本機及公開網址健康檢查正常。
- [ ] 已完成瀏覽器功能驗證。
