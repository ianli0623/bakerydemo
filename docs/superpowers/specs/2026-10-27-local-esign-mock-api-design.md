# 本機電子證書 Mock API 設計

## 目的

在無法連線客戶內網 `192.168.1.123:8011` 時，提供僅限本機的測試 API，驗證 Nuxt 電子證書清單、狀態篩選、API Key 傳遞及錯誤顯示。此 Mock 不取代客戶正式 API，也不作為正式資料來源。

## 目標與限制

- 僅監聽 `127.0.0.1:8011`，不接受區域網路或外部連線。
- 模擬 `GET /api/v1/external/certificates` 與 `X-API-Key` 驗證。
- 回傳符合客戶文件的 `success`、`code`、`message`、`data` 格式。
- 測試資料涵蓋 `PENDING`、`VALID`、`SUSPENDED`、`REVOKED` 四種狀態。
- 使用固定的本機測試 Key，不讀取或回傳客戶正式 API Key。
- 不將 Mock 路由加入 Nuxt 正式伺服器，也不改變正式環境設定。

## 方案比較

1. **獨立 Node Mock API（採用）**：不新增套件、可驗證 HTTP Header 與狀態碼，而且不會隨 Nuxt 正式服務部署。
2. **Nuxt 內建 Mock 路由**：啟動較少一步，但可能被誤部署到正式環境，因此不採用。
3. **固定 JSON 檔**：最簡單，但無法驗證 API Key、HTTP 錯誤及逾時，因此不採用。

## 實作設計

- 新增 `nuxt-bakery-demo/scripts/mock-esign-api.ts`，使用 Node.js 內建 `node:http`，不加入第三方依賴。
- 新增 `npm run mock:esign` 啟動 Mock API。
- 新增安全、可提交的 `nuxt-bakery-demo/.env.mock`，讓 `npm run dev:mock` 以本機 Mock URL 與測試 Key 啟動 Nuxt；既有 `.env` 不會被覆寫。
- 預設回傳四筆不同狀態的證書。
- 可透過 `ESIGN_MOCK_SCENARIO` 模擬 `success`、`empty`、`error`、`malformed`、`slow`；預設為 `success`。
- 非指定路徑回傳 404，Key 錯誤回傳 401，不在錯誤內容中洩漏收到的 Key。
- 支援 `Ctrl+C`、`SIGTERM` 正常關閉。

## 驗證方式

- 以 Node 內建測試驗證成功資料、四種狀態、401、404、空資料及錯誤情境。
- 執行完整 `npm test`、`npm run typecheck`、Prettier 與正式建置，確認 Mock 不影響正式應用程式。
- 人工測試時分兩個終端執行 `npm run mock:esign` 與 `npm run dev:mock`，再開啟證書管理頁。

## 不包含範圍

- 不驗證客戶正式 API Key、內網路由、防火牆、資料正確性或服務可用性。
- 不部署至 `semi187-portal` 或任何正式環境。
