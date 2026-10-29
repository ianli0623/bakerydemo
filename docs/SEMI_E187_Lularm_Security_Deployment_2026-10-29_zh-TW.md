# lularm.com 測試區安全修正部署紀錄

完成時間：2026-10-29 14:32（Asia/Taipei）。

## 範圍與版本

- 測試主機：`semi-test`，`35.234.40.148`。
- 測試網址：`https://lularm.com/`、`https://www.lularm.com/`。
- 正式站 `e187.tw`／`www.e187.tw` 未變更。
- 保留前台白名單 `59.124.166.223`、`140.96.158.97`；其餘來源仍為維護中（503）。
- 僅部署 Strict CSP、nonce、Nginx 標頭邊界及本機 CORS 安全修正，未帶入其他 main 功能差異。

| 項目 | 實際值 |
| --- | --- |
| 原應用基底 | `afdc03057199a41ff4d6799899e9ad273c9034b1` |
| 安全修正來源 | `895e10d2bf29cb281526fec866634fcf42af01cb` |
| 新版本目錄 | `/srv/semi-e187/releases/20261029T060618Z-895e10d-security` |
| 生效連結 | `/srv/semi-e187/app` |
| 備份與操作紀錄 | `/srv/semi-e187/backups/strict-csp-895e10d` |
| 安全補丁 SHA-256 | `50f1e7d623cfbec0ab0650549a496851400e133bbfc18336d70a0d67159893db` |

此次是原應用基底加安全補丁，不是整棵 `895e10d` 原始碼的完整替換。
`DEPLOYED_COMMIT` 保留基底版本，另以 `SECURITY_PATCH_COMMIT` 與
`SECURITY_PATCH_BASE` 記錄安全更新；不要只看單一 DEPLOYED_COMMIT 判斷是否已套用修正。

## 執行方式

1. 驗證 SSH 主機指紋及 hostname，確認只操作測試機。
2. 備份 PostgreSQL、Nginx、backend.env 與 frontend.env；備份目錄為 root 700，環境檔副本為 600，未下載或公開憑證值。
3. 複製目前版本至新 release，僅套用從 `eb3eaa0..895e10d` 產生的安全差異。既有 Windows 換行格式於新副本的補丁輸入檔正規化，未改動原版本。
4. 沿用既有 Python 套件版本，修正複製後 venv CLI 的目錄指向；以 Node 24 依 lockfile 執行 npm ci、測試、型別檢查與 production build。
5. 僅在新 release 執行 collectstatic。共用媒體連結保留，未執行 migrate 或變更既有資料庫內容。
6. 將安全標頭與條件 map 合併至實際啟用的 Nginx 檔案；保留來源 IP 信任、兩個白名單 IP、路由、憑證及禁止快取設定。
7. 先以暫存 uWSGI／Nitro 及隔離 Linux Nginx 埠驗證，再以原子方式切換 app 連結、啟動服務及 reload Nginx。
8. 由公開網域驗證前後台、nonce、靜態資源及不同 IP 的回應，完成瀏覽器操作確認。

環境檔位元內容已比對，與部署前一致。systemd unit、帳號、Fast-ID Token、金鑰、網域與 TLS 憑證沒有變更。

## 驗證結果

| 項目 | 結果 |
| --- | --- |
| 測試主機 Django check／collectstatic | 通過 |
| 測試主機 Django 測試 | 356 項，跳過 4 項選用的 Nginx executable 測試；其餘通過，使用隔離記憶體 SQLite |
| 測試主機 Nuxt 單元測試 | 76 項通過 |
| Nuxt typecheck／production build／SSR CSP 整合 | 通過，1 項整合測試通過 |
| 實際 Linux Nginx | nginx -t、隔離 HTTP/2 標頭與部署後來源站回應檢查通過 |
| lularm.com 與 www.lularm.com 前台 | 200，完整 CSP、SAMEORIGIN、nosniff、no-store |
| 公開 HTML nonce | 每次回應不同，與 CSP 及 HTML 元素相符 |
| 公開 JS/CSS | 200，沒有 CORS 萬用字元，含 nosniff |
| 後台登入與 Windows Hello 登入頁 | 200，CSP／HTML nonce 相符；Windows Hello 路徑保留 no-store |
| 白名單外來源 | 503；偽造 X-Forwarded-For 為白名單 IP 仍為 503 |
| 瀏覽器 | 首頁、認識標準頁、導覽與字級放大／還原可操作 |
| 服務 | nginx、semi-e187-backend、semi-e187-frontend 均 active |

測試區保留原應用基底，因此其測試數量與完整本機分支的 357／93 項不同。
本機 Nginx runtime 測試曾通過；目標 Linux 另外執行了實際隔離及來源站檢查，未將跳過的四項計為通過。

首次切換後的檢查曾因 HTTP/2 使用小寫標頭而被大小寫敏感斷言誤判，已自動回復原版本。
檢查改為不區分大小寫後，先驗證隔離 Nginx，再重新切換並通過所有公開入口檢查。

## 已知限制與待驗收

- 尚未產生新的 ZAP 報告，不宣稱線上中風險已歸零；請使用新的 ZAP 工作階段重掃測試網域。
- 只檢查登入頁，沒有以使用者的 Windows Hello 執行真實 FIDO 認證，也未新增／刪除帳號或金鑰。
- 瀏覽器有一則 `Hydration completed but contains mismatches.`。觀察到 Cloudflare 先將聯絡信箱改寫為保護連結，Vue 完成後還原為 mailto，可能相關，但原因未在本次定案。頁面、導覽、信箱連結及字級互動均可使用；未另行更動 Cloudflare 設定。
- 沒有從 `140.96.158.97` 的實際網路發出請求；已確認該 IP 與原 IP 均保留在生效白名單中。

## 需要回復時

備份內已保存受保護的 `rollback.py`，在測試機執行：

```sh
sudo python3 /srv/semi-e187/backups/strict-csp-895e10d/rollback.py
```

腳本僅回復 app 連結與 Nginx，不回復資料庫或環境檔。
它會先確認目前仍是本次 release、Nginx 未被後續修改，避免覆蓋新加入的白名單或其他變更。
若檢查拒絕回復，請先比對新設定並人工合併，勿直接用舊檔覆蓋。

部署細節與建置輸出位於同一備份目錄的 `deployment.json`、`build.log`、
`nginx.before.conf`、`nginx.candidate.conf`、`database.dump` 及操作腳本。
