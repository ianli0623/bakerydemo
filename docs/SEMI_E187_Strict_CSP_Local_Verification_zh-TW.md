# Strict CSP 本機修正與驗證紀錄

日期：2026-10-29（Asia/Taipei）

分支：`codex/lularm-strict-csp`

實作目錄：`D:/Ian/github/bakerydemo/.worktrees/lularm-strict-csp`

本次完成應用程式安全標頭、Nginx 邊界與相容性修正，僅在本機驗證並提交。未部署至測試／正式環境，現行兩站的 IP 白名單維持原設定。

## 修正結果

- Nuxt SSR 使用每次回應獨立的 nonce，涵蓋首頁轉址及一般頁面，腳本／樣式不依賴 `unsafe-inline`。
- Django 生產環境的 CSP 與 SAMEORIGIN 標頭涵蓋一般頁面及 HTTPS、補斜線、密碼政策等提前轉址。
- Wagtail 日期、選擇器、inline panel、主題腳本及管理介面樣式在可信的產生位置加入 nonce；任意插入的腳本不會自動取得授權。
- 保留既有 YouTube／Vimeo 播放器所需的明確 frame 來源及全螢幕權限。
- 離線 HTML 換用適合 offline.js 的政策，移除失效的 SSR hash／nonce 政策。
- Nginx 保留上游 CSP（包含 nonce）與 X-Frame-Options。靜態／媒體檔案、HTTP 轉址及 Nginx 自行產生的 413／502 錯誤有防禦性 fallback。
- 一般 `npm test` 不依賴已建置的 `.output`；`npm run test:integration` 會先重新建置再驗證 Nitro。

## 獨立審查與修正

整體分支曾交由獨立審查者檢查。以下六個問題均已修正；各問題先以回歸測試重現，再確認修正後通過。

| 問題 | 驗證方式 |
| --- | --- |
| Wagtail 的可信 inline 初始化及本機樣式被阻擋 | 真實頁面編輯器渲染、日期／選擇器／panel 渲染、插入腳本負向對照 |
| 提前回應的轉址缺少 CSP／X-Frame-Options | 實際 Django client 測試 HTTPS、補斜線及密碼政策轉址 |
| 既有影片嵌入來源被阻擋 | 對現行 getEmbedPresentation 產生的影片來源檢查政策與全螢幕權限 |
| 離線匯出仍帶有失效的 SSR 政策 | 轉換回歸測試及隔離 Chrome 直接開啟 file:// 檔案，確認字級控制執行 |
| 單元測試依賴不存在或過期的建置輸出 | 暫時移開 `.output` 時仍能執行 93 項單元測試；整合指令強制先 build |
| Nginx 自行產生的 413／502 缺少保護 | 使用實際本機 Nginx HTTP/TLS 回應測試 |

另修正既有導覽測試：改以 HTML 節點查詢及 CSS 規則內容判定隱藏搜尋列，不再把 `<style>` 的屬性字串寫死。此調整保留原本的行為斷言及 nonce 保護。

## 最終驗證

| 項目 | 結果 |
| --- | --- |
| 完整 Django 測試 | 357 項通過，沒有跳過；使用記憶體 SQLite，未操作既有資料庫 |
| Nginx 設定及實際 HTTP/TLS 測試 | 8 項通過，已包含於上述 357 項；nonce、靜態 200/404、301、413、502、FIDO 路徑 no-store 均有驗證 |
| Nuxt 單元測試 | 93 項通過 |
| Nuxt production build 與 SSR 整合測試 | build 成功，1 項整合測試通過；兩次 HTML 回應 nonce 不同且與元素一致 |
| Nuxt 型別檢查 | 通過 |
| Django system check／makemigrations --check --dry-run | 無問題／無模型變更 |
| Ruff check／format、Prettier、DjHTML、git diff --check | 通過 |
| 離線檔案 Chrome 驗證 | 通過；使用獨立暫存使用者目錄，未改用戶瀏覽器設定 |

主要重現指令（在此 worktree 執行）：

```powershell
$env:DATABASE_URL = 'sqlite:///:memory:'
$env:NGINX_TEST_BINARY = 'D:\Ian\github\bakerydemo\.codex-tmp\strict-csp-nginx\runtime\openresty-1.27.1.2-win64\nginx.exe'
& 'D:\Ian\github\bakerydemo\.venv\Scripts\python.exe' manage.py test --settings=bakerydemo.settings.test --noinput
& 'D:\Ian\github\bakerydemo\.venv\Scripts\python.exe' manage.py check --settings=bakerydemo.settings.test
& 'D:\Ian\github\bakerydemo\.venv\Scripts\python.exe' manage.py makemigrations --check --dry-run --settings=bakerydemo.settings.test

Set-Location nuxt-bakery-demo
npm test
npm run test:integration
npm run typecheck
```

本機 Nginx runtime 不是專案依賴。沒有設定 `NGINX_TEST_BINARY` 時會跳過該組 runtime 測試，不能將該次執行視為已驗證代理行為。

## 執行判斷與限制

以下整理本次計畫的判斷與其限制，避免把本機結果誤當成線上驗收。

1. Windows 的 WSL Bash 無法啟動，故以同一計畫的手動 ledger 取代 SDD shell helper；缺少 helper 的自動化中繼資訊，改由 Git commit 與執行結果追蹤。
2. 原計畫的裸 `python -m unittest` 未設定 Django；改用 Django test runner，完整測試使用隔離 SQLite。能驗證渲染／安全回應，未涵蓋 PostgreSQL 專有差異。
3. Nitro localhost 測試及建置因 sandbox 的連線／檔案 EPERM 限制改於 sandbox 外執行相同指令；有確認服務輸出、測試結果及子程序清理，仍可能存在執行環境差異。
4. 除原本的結構測試，增加實際 Nginx 測試；Docker engine 不可用，採官方 portable OpenResty 1.27.1.2 Windows 版，未安裝主機服務。未驗證未來 Linux 的 module 套件配置，部署當時仍須 nginx -t。
5. 最初要求的審查模型因容量無法啟動，改用當時可用的獨立審查者；完成整體審查及一次修正，未宣稱另有第二次獨立複審。
6. 保留影片來源的明確 allowlist 及全螢幕能力，而非封鎖所有外部 frame；新增影片供應商時須重新評估來源。
7. Wagtail 7 的 Python chooser 初始化沒有可直接使用的 nonce hook，故以限縮的產生點 adapter 及模板覆寫補上授權；未採整頁 script 改寫。升級 Wagtail 時須重跑相容性測試。
8. Nginx 以條件 map 補足缺少上游標頭的錯誤回應，不使用會覆蓋 nonce 的固定政策；若上游自行產生錯誤政策仍會保留，因此應用程式與代理兩端測試都需執行。
9. 離線匯出採獨立政策；單元／整合測試分開執行以避免過期輸出。後續驗證必須包含 `npm run test:integration`，不能只執行單元測試。
10. 未執行真實 Fast-ID／客戶證書 API 交易、部署後 Cloudflare 行為或新版線上 ZAP 掃描；本機驗證不代表線上中風險已歸零。既存相依套件稽核警告未納入此次廣泛升級。

沒有另行延後的 Minor 審查項目；Nginx 錯誤回應問題已提升為本次必修範圍並完成驗證。

## 後續部署前

- 仍需另外取得部署授權；本次沒有合併 main、推送或更新主機上的程式。
- 備份實際啟用的 Nginx 設定，保留現行 IP 白名單與可信代理設定；不可直接用此分支的測試站 Nginx 範本覆蓋現場設定。
- 在目標 Linux 執行 nginx -t，確認 headers-more module、網域、憑證及實際啟用檔案後才 reload。
- 部署後驗證前後台操作與邊緣快取，再對應用程式範圍重新執行 ZAP。Cloudflare 控制的外部主機及 `/cdn-cgi/` 應與應用程式問題分別判讀。
