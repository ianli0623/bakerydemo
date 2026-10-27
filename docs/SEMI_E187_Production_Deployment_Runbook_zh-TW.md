# SEMI E187 正式環境部署操作手冊

更新日期：2026-10-21

## 1. 文件目的

本文件說明如何將 `main` 分支部署至客戶正式主機 `semi187-portal`，適用於日常程式更新，不包含首次安裝作業系統、PostgreSQL、Nginx 或 TLS 憑證的流程。

正式環境採用不可變版本目錄（immutable release）：每次部署都在 `/srv/semi-e187/releases/` 建立新版本，完成建置及檢查後，再切換 `/srv/semi-e187/app` 軟連結。不要直接刪除目前版本，也不要在 `/srv/semi-e187/app` 執行 `git pull`。

## 2. 正式環境資訊

| 項目 | 設定 |
| --- | --- |
| 主機名稱 | `semi187-portal` |
| 管理入口 | RVP Web Terminal |
| 前台網址 | `https://e187.tw/`、`https://www.e187.tw/` |
| 後台網址 | `https://e187.tw/admin/` |
| 發布目錄 | `/srv/semi-e187/releases/<日期時間>-<短版 commit>` |
| 目前版本連結 | `/srv/semi-e187/app` |
| 共用媒體目錄 | `/srv/semi-e187/shared/media` |
| 備份目錄 | `/srv/semi-e187/backups` |
| 後端環境設定 | `/etc/semi-e187/backend.env` |
| 前端環境設定 | `/etc/semi-e187/frontend.env` |
| 後端服務 | `semi-e187-backend`，內部連接埠 `8000` |
| 前端服務 | `semi-e187-frontend`，內部連接埠 `3100` |
| Web 服務 | `nginx`，對外連接埠 `80`、`443` |

環境設定檔可能包含資料庫密碼、Django Secret Key、Fast-ID Token 及 Client Secret。不得將檔案內容貼到聊天、部署紀錄或 Git；只確認檔案是否存在、權限及必要欄位是否已設定。

## 3. 判斷部署類型

部署前先比較正式環境 commit 與預計發布 commit：

```powershell
cd D:\Ian\github\bakerydemo

$deployedCommit = "<正式環境 DEPLOYED_COMMIT>"
$releaseCommit = git rev-parse HEAD
git diff --name-status "${deployedCommit}..${releaseCommit}"
```

依變更內容選擇流程：

| 變更範圍 | 流程 | 資料庫備份 |
| --- | --- | --- |
| 只有 `nuxt-bakery-demo/` 與文件 | 第 8 節「前台限定部署」 | 不需要 |
| Django、Python 套件、migration、Wagtail model 或後台程式 | 第 9 節「完整部署」 | 必須 |
| `/etc/semi-e187/*.env`、Nginx、systemd、網域或憑證 | 另列變更計畫並先備份設定檔 | 視變更內容決定 |

若無法確認變更是否影響資料庫，使用完整部署流程。

## 4. 本機部署前檢查

### 4.1 同步並確認 main

```powershell
cd D:\Ian\github\bakerydemo

git fetch origin
git switch main
git pull --ff-only origin main
git status --short --branch
git rev-parse HEAD
git rev-parse origin/main
```

必須符合以下條件才可繼續：

- 工作目錄沒有未提交的檔案。
- 本機 `HEAD` 與 `origin/main` 為相同 commit。
- 預計發布的檔案已完成程式碼審查。
- `.env`、資料庫備份、媒體備份、建置輸出與 `rbac/` 未納入 commit。

### 4.2 執行後端檢查

```powershell
cd D:\Ian\github\bakerydemo

.\.venv\Scripts\python.exe manage.py check `
  --settings=bakerydemo.settings.test
```

完整後端測試使用專案內暫存目錄，避免 Windows 暫存目錄權限問題：

```powershell
$testTemp = "D:\Ian\github\bakerydemo\.codex-tmp\test-temp"
New-Item -ItemType Directory -Force -Path $testTemp | Out-Null

$oldDatabaseUrl = $env:DATABASE_URL
$oldPythonUtf8 = $env:PYTHONUTF8
$oldTemp = $env:TEMP
$oldTmp = $env:TMP

try {
  $env:DATABASE_URL = "sqlite:///:memory:"
  $env:PYTHONUTF8 = "1"
  $env:TEMP = $testTemp
  $env:TMP = $testTemp

  .\.venv\Scripts\python.exe manage.py test `
    --settings=bakerydemo.settings.test
} finally {
  $env:DATABASE_URL = $oldDatabaseUrl
  $env:PYTHONUTF8 = $oldPythonUtf8
  $env:TEMP = $oldTemp
  $env:TMP = $oldTmp
}
```

### 4.3 執行格式與靜態檢查

```powershell
cd D:\Ian\github\bakerydemo

$env:PYTHONUTF8 = "1"
$env:PREK_HOME = "D:\Ian\github\bakerydemo\.codex-tmp\prek-home"
$env:UV_CACHE_DIR = "D:\Ian\github\bakerydemo\.codex-tmp\uv-cache"
$env:UV_TOOL_DIR = "D:\Ian\github\bakerydemo\.codex-tmp\uv-tools"

uvx prek run --all-files
```

### 4.4 執行前台測試與建置

```powershell
cd D:\Ian\github\bakerydemo\nuxt-bakery-demo

npm ci
npm test
npm run typecheck
npm run build
```

所有檢查通過後，記錄完整 commit：

```powershell
cd D:\Ian\github\bakerydemo
git rev-parse HEAD
```

## 5. 正式主機部署前檢查

登入 RVP，選擇 `semi187-portal`，開啟 Web Terminal，執行：

```bash
hostname
id
date --iso-8601=seconds
df -h / /srv
free -h

readlink -f /srv/semi-e187/app
cat /srv/semi-e187/app/DEPLOYED_COMMIT

systemctl is-active nginx semi-e187-backend semi-e187-frontend
sudo nginx -t
```

預期結果：

- 主機名稱為 `semi187-portal`。
- `/srv` 有足夠空間建立新 release。
- 三個服務皆顯示 `active`。
- `nginx -t` 顯示設定檢查成功。
- `DEPLOYED_COMMIT` 與本次預計發布 commit 不同；若相同且服務正常，不必重複部署。

## 6. 建立新 release

以下範例從 GitHub 下載指定 commit。`commit` 必須填入已通過本機檢查的完整 SHA，不可使用浮動的 `main` 壓縮檔。

```bash
commit="<完整 commit SHA>"
short_commit="${commit:0:7}"
release_id="$(date +%Y%m%d-%H%M%S)-${short_commit}"
archive="/tmp/bakerydemo-${short_commit}.tar.gz"
release="/srv/semi-e187/releases/${release_id}"

curl -fL --retry 3 --connect-timeout 15 \
  -o "$archive" \
  "https://github.com/ianli0623/bakerydemo/archive/${commit}.tar.gz"

test -s "$archive"
sudo install -d -o deploy -g deploy "$release"
sudo -u deploy tar -xzf "$archive" \
  --strip-components=1 \
  -C "$release"

printf '%s\n' "$commit" \
  | sudo -u deploy tee "$release/DEPLOYED_COMMIT" >/dev/null
```

只有在 `$release` 明確位於 `/srv/semi-e187/releases/` 下時，才可建立媒體連結：

```bash
case "$release" in
  /srv/semi-e187/releases/*) ;;
  *) echo "不安全的 release 路徑：$release"; exit 1 ;;
esac

sudo -u deploy rm -rf "$release/bakerydemo/media"
sudo -u deploy ln -s \
  /srv/semi-e187/shared/media \
  "$release/bakerydemo/media"
```

## 7. 建置新 release

建置期間不切換 `/srv/semi-e187/app`，正式站仍使用舊版本。

### 7.1 建置 Python 後端

```bash
sudo -u deploy python3 -m venv "$release/.venv"

sudo -u deploy "$release/.venv/bin/pip" install --upgrade pip
sudo -u deploy "$release/.venv/bin/pip" install \
  -r "$release/requirements.txt"
```

### 7.2 建置 Nuxt 前台

```bash
sudo -u deploy bash -lc \
  "cd '$release/nuxt-bakery-demo' && npm ci && npm run build"
```

不得用 `npm install` 取代 `npm ci`。若 `package-lock.json` 與 `package.json` 不一致，停止部署並回到本機修正。

### 7.3 執行 Django 設定檢查

```bash
sudo bash -lc \
  "set -a; source /etc/semi-e187/backend.env; set +a; \
   cd '$release'; \
   '$release/.venv/bin/python' manage.py check"
```

顯示 `System check identified no issues` 後才可進行版本切換。

## 8. 前台限定部署

只有在第 3 節確認變更未包含 Django、Python 套件、migration、環境設定或 Nginx 設定時，才使用本節。

### 8.1 產生 Django 靜態檔案

新 release 沒有 `collect_static`，即使只修改 Nuxt，也必須先產生後台靜態檔案，避免切換軟連結後 `/static/` 失效。

```bash
sudo bash -lc \
  "set -a; source /etc/semi-e187/backend.env; set +a; \
   cd '$release'; \
   '$release/.venv/bin/python' manage.py collectstatic --noinput"
```

### 8.2 切換 release 並只重啟前台

```bash
old_target="$(readlink -f /srv/semi-e187/app)"

if sudo systemctl stop semi-e187-frontend \
  && sudo ln -sfn "$release" /srv/semi-e187/app \
  && sudo systemctl start semi-e187-frontend \
  && test "$(systemctl is-active semi-e187-frontend)" = "active"
then
  printf 'DEPLOYED=%s\nPREVIOUS=%s\n' \
    "$(readlink -f /srv/semi-e187/app)" \
    "$old_target"
else
  sudo ln -sfn "$old_target" /srv/semi-e187/app
  sudo systemctl restart semi-e187-frontend
  printf 'ROLLED_BACK=%s\n' "$old_target"
  exit 1
fi
```

此流程不執行資料庫備份、migration，也不重新啟動後端服務。舊 release 必須保留，以便回復及維持既有後端程序正常運作。

## 9. 完整部署

只要包含 Django、Python 套件、migration、Wagtail model 或後台功能變更，就使用本節。

### 9.1 備份 PostgreSQL

```bash
backup="/srv/semi-e187/backups/pre-${release_id}.dump"

sudo install -d -o deploy -g deploy /srv/semi-e187/backups

sudo bash -lc \
  "set -a; source /etc/semi-e187/backend.env; set +a; \
   pg_dump --format=custom --file='$backup' \"\$DATABASE_URL\""

sudo chown deploy:deploy "$backup"
test -s "$backup"
```

備份檔不存在或大小為 0 時停止部署。

### 9.2 檢查並套用 migration

```bash
sudo bash -lc \
  "set -a; source /etc/semi-e187/backend.env; set +a; \
   cd '$release'; \
   '$release/.venv/bin/python' manage.py migrate --plan"

sudo bash -lc \
  "set -a; source /etc/semi-e187/backend.env; set +a; \
   cd '$release'; \
   '$release/.venv/bin/python' manage.py migrate --noinput"

sudo bash -lc \
  "set -a; source /etc/semi-e187/backend.env; set +a; \
   cd '$release'; \
   '$release/.venv/bin/python' manage.py collectstatic --noinput"
```

先人工檢視 `migrate --plan`；出現非預期的資料表刪除、欄位移除或大型資料轉換時，不可直接套用。

### 9.3 原子切換並設定失敗回復

```bash
old_target="$(readlink -f /srv/semi-e187/app)"

sudo systemctl stop semi-e187-frontend semi-e187-backend
sudo ln -sfn "$release" /srv/semi-e187/app

if sudo systemctl start semi-e187-backend semi-e187-frontend \
  && test "$(systemctl is-active semi-e187-backend)" = "active" \
  && test "$(systemctl is-active semi-e187-frontend)" = "active"
then
  printf 'DEPLOYED=%s\nPREVIOUS=%s\n' \
    "$(readlink -f /srv/semi-e187/app)" \
    "$old_target"
else
  sudo ln -sfn "$old_target" /srv/semi-e187/app
  sudo systemctl restart semi-e187-backend semi-e187-frontend
  printf 'ROLLED_BACK=%s\n' "$old_target"
  exit 1
fi
```

若新版本已套用不可逆的 migration，切回舊程式不代表資料庫也自動回復。必須先停止寫入，再依核准的資料庫還原程序處理。

## 10. 部署後驗證

### 10.1 版本與服務

```bash
printf 'COMMIT='
cat /srv/semi-e187/app/DEPLOYED_COMMIT

readlink -f /srv/semi-e187/app
systemctl is-active nginx semi-e187-backend semi-e187-frontend
```

### 10.2 HTTP 健康檢查

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

curl -L -sS -o /dev/null \
  -w 'hello=%{http_code} %{url_effective}\n' \
  https://e187.tw/account/security/windows-hello/login/
```

上述網址應回傳正常的 `2xx`，或依預期導向登入頁後回傳 `2xx`。

### 10.3 錯誤日誌

```bash
sudo journalctl \
  -u semi-e187-backend \
  -u semi-e187-frontend \
  --since '10 minutes ago' \
  -p err \
  --no-pager
```

### 10.4 瀏覽器功能確認

至少人工確認：

1. 繁體中文與英文首頁可以開啟。
2. 上方選單可以切換各頁面。
3. 首頁資料可以從 Wagtail 正常載入。
4. `/admin/` 可以開啟登入頁。
5. 圖片、CSS、JavaScript 與後台靜態檔正常。
6. 本次修改的畫面與功能符合需求。
7. 若本次涉及登入，完成 Email 密碼及 Fast-ID／Windows Hello 測試。

## 11. 回復上一個 release

程式切換後若健康檢查失敗，使用部署時記錄的 `PREVIOUS` 路徑：

```bash
previous="<部署時輸出的 PREVIOUS 路徑>"

case "$previous" in
  /srv/semi-e187/releases/*) ;;
  *) echo "不安全的回復路徑：$previous"; exit 1 ;;
esac

sudo systemctl stop semi-e187-frontend semi-e187-backend
sudo ln -sfn "$previous" /srv/semi-e187/app
sudo systemctl start semi-e187-backend semi-e187-frontend

readlink -f /srv/semi-e187/app
cat /srv/semi-e187/app/DEPLOYED_COMMIT
systemctl is-active nginx semi-e187-backend semi-e187-frontend
```

回復後重新執行第 10 節。若部署包含 migration，不可未經確認直接反向 migration 或覆蓋正式資料庫。

## 12. 部署完成後整理

- 保留目前 release、上一個 release 及本次資料庫備份，直到驗收完成。
- 驗收完成後才刪除 `/tmp/bakerydemo-<短版 commit>.tar.gz`。
- 不得刪除 `/etc/semi-e187/`、`/srv/semi-e187/shared/` 或仍被 `/srv/semi-e187/app` 指向的 release。
- 記錄部署時間、完整 commit、release 路徑、執行者、驗證結果與是否發生回復。
- 不要在紀錄中保存密碼、Token、Client Secret 或完整環境設定內容。

## 13. 正式部署檢查表

### 部署前

- [ ] 已確認目標主機為 `semi187-portal`。
- [ ] 本機 `main` 與 `origin/main` commit 相同。
- [ ] 工作目錄沒有未提交檔案。
- [ ] Django 檢查與測試通過。
- [ ] Prek、Nuxt 測試、型別檢查與正式建置通過。
- [ ] 已比較正式版本與新版本的檔案差異。
- [ ] 已選擇前台限定部署或完整部署。
- [ ] 正式主機磁碟空間足夠，既有服務正常。

### 部署中

- [ ] 新 release 已寫入正確的 `DEPLOYED_COMMIT`。
- [ ] 媒體目錄已連結至 `/srv/semi-e187/shared/media`。
- [ ] Python 與 Nuxt 建置成功。
- [ ] Django `manage.py check` 通過。
- [ ] 完整部署已建立有效的 PostgreSQL 備份。
- [ ] `collectstatic` 已完成。
- [ ] 已記錄切換前的 `old_target`。

### 部署後

- [ ] `/srv/semi-e187/app` 指向新 release。
- [ ] `nginx`、後端與前端服務皆為 `active`。
- [ ] 前台、`www`、後台與登入頁健康檢查正常。
- [ ] 最近 10 分鐘沒有新的應用程式錯誤日誌。
- [ ] 已用瀏覽器確認本次修改。
- [ ] 舊 release 與必要備份仍保留。
