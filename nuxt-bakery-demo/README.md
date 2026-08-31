# SEMI E187 Nuxt 前台

這個 Nuxt 4 專案透過同源 Server API 讀取 Wagtail 已發布內容，將後台管理的
SEMI E187 首頁、四個主題頁、網站選單與聯絡資料呈現在
`http://localhost:3100/`。

## 串接架構

```text
瀏覽器
  │ GET /api/bakery/*
  ▼
Nuxt Server API（Nitro）
  │ GET /api/v2/pages/*、/api/site-settings/
  ▼
Wagtail（內容、網站設定、圖片）
```

瀏覽器只呼叫 Nuxt 的同源 API，不會取得 Wagtail 的實際來源網址，也不需要
額外設定 CORS。Wagtail API v2 與公開網站設定端點只回傳已發布、可公開的欄位，
不需要 API Key。

## 專案需求

- Node.js 22 以上與 npm
- Python 3.10 以上
- 五個來源頁面：`index.html`、`about.html`、`resources.html`、
  `certification.html`、`ecosystem.html`
- 三張必要圖片：`contret01.jpg`、`GPM+contret.jpg`、`GPM01.jpg`

第一次安裝後端套件：

```powershell
cd D:\Ian\github\bakerydemo
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements\development.txt
```

第一次安裝前端套件：

```powershell
cd D:\Ian\github\bakerydemo\nuxt-bakery-demo
npm ci
Copy-Item .env.example .env
```

`.env` 內容：

```dotenv
NUXT_BAKERY_BASE_URL=http://127.0.0.1:8000
```

修改 `.env` 後必須重新啟動 Nuxt。這個檔案已排除於 Git 之外。

## 啟動專案

開啟第一個 PowerShell 啟動 Wagtail：

```powershell
cd D:\Ian\github\bakerydemo
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py runserver 8000
```

可使用的後端網址：

- Wagtail 前台：`http://127.0.0.1:8000/`
- Wagtail 後台：`http://127.0.0.1:8000/admin/`
- Page API：`http://127.0.0.1:8000/api/v2/pages/`
- 公開網站設定：`http://127.0.0.1:8000/api/site-settings/`

開啟第二個 PowerShell 啟動 Nuxt：

```powershell
cd D:\Ian\github\bakerydemo\nuxt-bakery-demo
npm run dev
```

前台網址：`http://localhost:3100/`

## 前台路由與選單

| 路由 | Wagtail 內容 |
|---|---|
| `/` | Home ID 60：SEMI E187 首頁 |
| `/about/` | 認識標準 |
| `/resources/` | 導入資源 |
| `/certification/` | 驗證與合規 |
| `/ecosystem/` | 案例與生態 |

主要選單由 Wagtail 的「SEMI E187 網站設定」內明確排序，不再依一般頁面的
`Show in menus` 自動收錄。因此 `TEST`、`AXCC`、`CCC` 等既有頁面可維持原本
發布狀態，但不會出現在 SEMI E187 導覽。新增頁面後若需要放入選單，請在後台
網站設定的「主要導覽」欄位加入並排序。

## Nuxt Server API

| Nuxt API | Wagtail API | 用途 |
|---|---|---|
| `/api/bakery/home` | `/api/v2/pages/60/?fields=*` | 首頁與結構化內容 |
| `/api/bakery/site-settings` | `/api/site-settings/` | 品牌、導覽、聯絡與頁尾資料 |
| `/api/bakery/navigation` | `/api/site-settings/` | 相容用的排序導覽清單 |
| `/api/bakery/pages/{slug}` | `/api/v2/pages/?type=base.StandardPage&slug={slug}` | 主題頁明細 |

快速檢查：

```powershell
Invoke-RestMethod -Uri 'http://localhost:3100/api/bakery/home'
Invoke-RestMethod -Uri 'http://localhost:3100/api/bakery/site-settings'
Invoke-RestMethod -Uri 'http://localhost:3100/api/bakery/navigation'
Invoke-RestMethod -Uri 'http://localhost:3100/api/bakery/pages/about'
```

## Wagtail 可編輯內容

HomePage 與 StandardPage 的 Page body 支援：

- 標題、Rich Text、附說明圖片、引言、嵌入內容
- 卡片群組（Card grid）
- 文件表格（Document table）
- 有順序的驗證流程（Process steps）
- 設備廠商案例（Case study）
- 內部、外部與尚未提供的共用連結

未知的新區塊會被前台略過，不會使整頁停止呈現。沒有目的地的來源連結會顯示
「即將提供」而不可點擊；外部連結只允許安全的 HTTP、HTTPS、電話與郵件網址。

## 匯入 SEMI E187 來源資料

管理指令只解析允許的內容區段，不會執行來源 HTML 中的 script、Tailwind 設定或
其他指令。預演與正式發布必須擇一指定。

先執行不寫入資料庫的預演：

```powershell
cd D:\Ian\github\bakerydemo
.\.venv\Scripts\python.exe manage.py import_semi_e187 `
  --html-dir 'C:\Users\eerr0\Downloads' `
  --asset-dir 'C:\Users\eerr0\Downloads\SEMI_E187_SITE_0723\SEMI E187 SITE 0723' `
  --dry-run
```

確認報告只包含 Home ID 60、四個目標頁面與三張圖片後，再正式發布：

```powershell
.\.venv\Scripts\python.exe manage.py import_semi_e187 `
  --html-dir 'C:\Users\eerr0\Downloads' `
  --asset-dir 'C:\Users\eerr0\Downloads\SEMI_E187_SITE_0723\SEMI E187 SITE 0723' `
  --publish
```

指令以固定 slug 與圖片識別資料更新內容，可安全重複執行；第二次執行會更新同一批
頁面與圖片，不會重複建立。選用的 ADI 頁尾 logo 若不存在，會改用文字品牌，不會
產生破圖。

## 資料庫備份與復原

正式匯入前應停止 Wagtail，並為目前 SQLite 檔建立新的時間戳備份：

```powershell
cd D:\Ian\github\bakerydemo
$semiTimestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$semiBackup = Join-Path (Get-Location) "bakerydemodb.before-semi-e187-$semiTimestamp"
Copy-Item -LiteralPath '.\bakerydemodb' -Destination $semiBackup
Get-Item -LiteralPath '.\bakerydemodb', $semiBackup | Select-Object FullName, Length
```

需要回復時，先停止 Wagtail，再將 `bakerydemodb` 另存為目前狀態，最後把指定的
時間戳備份複製回去：

```powershell
$restoreSource = 'D:\Ian\github\bakerydemo\bakerydemodb.before-semi-e187-YYYYMMDD-HHMMSS'
Copy-Item -LiteralPath '.\bakerydemodb' -Destination '.\bakerydemodb.before-restore' -Force
Copy-Item -LiteralPath $restoreSource -Destination '.\bakerydemodb' -Force
```

匯入的圖片也會寫入 Wagtail media storage；若回復資料庫，對應的匯入媒體檔可在
確認無其他資料引用後另行清理。請勿覆寫或刪除使用者原有的
`bakerydemodb.backup-20260827`。

## 測試與正式建置

```powershell
cd D:\Ian\github\bakerydemo\nuxt-bakery-demo
npm test
npm run typecheck
npm run build
```

後端檢查：

```powershell
cd D:\Ian\github\bakerydemo
$env:DJANGO_SETTINGS_MODULE = 'bakerydemo.settings.test'
.\.venv\Scripts\python.exe manage.py test
Remove-Item Env:DJANGO_SETTINGS_MODULE
.\.venv\Scripts\python.exe manage.py check
```

## 常見問題

### Nuxt 顯示無法連線到 CMS

依序確認 Wagtail 是否在 port 8000 執行、`.env` 是否使用正確的
`NUXT_BAKERY_BASE_URL`，以及修改 `.env` 後是否重新啟動 Nuxt。

### 頁面沒有出現在主選單

確認頁面已發布，並在 Wagtail 的 SEMI E187 網站設定內加入「主要導覽」。單獨
勾選頁面的 `Show in menus` 不會改變這個選單。

### Port 已被使用

Wagtail 使用 port 8000，Nuxt 使用 port 3100。請先停止占用相同 port 的程序，再
重新啟動開發伺服器。

## Rich Text 安全

Nuxt 會以 `v-html` 顯示已發布、由 Wagtail 編輯者管理的 Rich Text。不要把未經
信任的訪客輸入直接存入這些欄位；若來源包含訪客輸入，應先在伺服器端清理 HTML。
