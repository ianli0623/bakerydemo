# SEMI E187 繁中／英文多語系設計

## 狀態

- 日期：2026-08-31
- 狀態：使用者已核准聊天中的架構、介面、資料流與驗證方向
- 範圍：Wagtail 後台、Bakery 公開 API、Nuxt 前台與五頁既有 SEMI E187 內容

## 目標

1. 保留現有繁體中文網址，並以 `/en/` 前綴提供完整英文網站。
2. 將首頁、認識標準、導入資源、驗證與合規、案例與生態的全部中文內容翻譯成英文。
3. 將英文內容建立為 Wagtail 原生翻譯頁並直接發布。
4. 讓編輯者可在 Wagtail 後台修改、預覽及重新發布每一個英文欄位。
5. 在 Nuxt 前台加入與來源 HTML 相同的無障礙工具列，以及可用的繁中／English 切換。
6. 讓字體大小 A+／A／A- 控制實際生效並保存瀏覽器偏好。

## 非目標

- 不在 Nuxt 內複製一套不可編輯的英文頁面資料。
- 不把每個 Wagtail 欄位改成 `*_zh`、`*_en` 的平行欄位。
- 不加入線上機器翻譯服務，也不在日後重新執行匯入時覆蓋人工編修內容。
- 不加入繁中與英文以外的語言。

## 現況與限制

- Wagtail 已啟用國際化功能，但內容語系仍是 Bakery 範例的 `en`、`de`、`ar`。
- 現有 SEMI E187 中文頁面被標記為 `en`，必須在建立英文翻譯前校正成 `zh-hant`。
- Nuxt 尚未安裝多語系模組，所有網址與介面文字均視為單一語系。
- Nuxt 的首頁 API 查詢寫死頁面 ID `60`；一般頁面也固定查詢此首頁的子頁。
- `SiteSettings` 是每站設定，不具 Wagtail 翻譯關聯；其中網站名稱、頁尾及聯絡文字需要新的可翻譯資料來源。
- 原始 HTML 的 English 連結指向 `VerB_en.html`，但來源資料夾沒有該檔案；英文初稿因此由現有五頁中文內容翻譯產生。

## 選定方案

採用 Wagtail 原生 locale 與頁面翻譯關係作為唯一內容來源。繁中與英文各自擁有一組 `HomePage`／`StandardPage`，兩者以 Wagtail `translation_key` 關聯。Nuxt 僅保存固定介面字串，完整頁面內容一律經 Bakery API 讀取。

此方案相較於同頁雙欄位或 Nuxt 靜態翻譯檔，能維持乾淨的後台編輯介面、支援獨立發布狀態，並避免將 CMS 內容散落在前端程式。

## 語系與網址

內容語系只保留：

- `zh-hant`：繁體中文，預設語系
- `en`：English

公開網址採以下規則：

| 頁面 | 繁體中文 | English |
| --- | --- | --- |
| 首頁 | `/` | `/en/` |
| 認識標準 | `/about/` | `/en/about/` |
| 導入資源 | `/resources/` | `/en/resources/` |
| 驗證與合規 | `/certification/` | `/en/certification/` |
| 案例與生態 | `/ecosystem/` | `/en/ecosystem/` |

英文沿用與繁中相同的 slug，降低導覽、對應頁及 API 查詢複雜度。Nuxt 使用 `prefix_except_default` 路由策略，使既有中文網址不變。

## Wagtail 內容設計

### 頁面

1. 新增 `zh-hant` locale，保留 `en` locale。
2. 將現有 SEMI E187 首頁與四個子頁校正為 `zh-hant`，保留頁面 ID、現有內容與發布狀態。
3. 透過 Wagtail 的翻譯關係建立英文首頁與四個英文子頁。
4. 翻譯所有可見與中繼資料，包括：
   - 頁面標題、SEO title、search description
   - Hero、CTA、引言與所有 StreamField 區塊
   - 卡片、表格、流程步驟、案例資料、控制項及連結文字
   - 圖片 caption 與替代文字中屬於頁面內容的部分
5. 圖片和外部文件可由兩個語系共用；翻譯頁的頁面連結必須指向同語系頁面。
6. 英文翻譯完成後直接發布。

### 全站文字

保留 `SiteSettings` 管理不需翻譯的電話、Email、頁尾 Logo 及導覽來源；新增 `LocalizedSiteContent` 可翻譯全站內容模型。此模型使用 `TranslatableMixin`，並加入 `DraftStateMixin`、`RevisionMixin` 與 `PreviewableMixin`，使每個語系都有可預覽及發布的修訂。模型至少包含：

- title suffix
- site name
- site tagline
- contact heading
- contact name
- contact context
- footer introduction
- organisation text

該模型在 Wagtail 後台以獨立內容項目呈現繁中與 English 版本。公開 API 依 locale 選取對應版本。主要導覽仍由同一組頁面選擇器管理，序列化時自動轉成目標 locale 的翻譯頁。

### 編輯流程

- 編輯者從 Wagtail「頁面」選擇繁中或 English 頁面，修改後可預覽並發布。
- 全站頁尾及聯絡文字從可翻譯的全站內容項目修改。
- 每個語系維持自己的草稿與發布狀態。
- 初次英文匯入採只建立模式；發現既有英文翻譯時停止並回報，不覆蓋人工內容。

## 英文初稿匯入

新增可重複檢查但不可重複覆蓋的管理命令，執行順序為：

1. 檢查五個繁中來源頁、圖片及必要設定都存在。
2. 檢查是否已存在 English 翻譯；任一頁已存在時不進行破壞性覆蓋。
3. 以程式內受版本控制的英文翻譯資料建立五個翻譯頁及全站 English 內容。
4. 重新連結英文 CTA、導覽及頁內連結至 English 頁面。
5. 驗證必填欄位和區塊結構。
6. 發布五個英文頁面。
7. 輸出建立頁面、區塊、連結與警告摘要。

英文翻譯資料涵蓋目前 Wagtail 中的實際五頁內容，不以來源 HTML 的 Tailwind 標記作為前台執行來源。這可讓首次匯入可測試、可審查，並確保後續人工內容不被重新翻譯覆蓋。

在更動 locale 或建立翻譯頁前必須先備份資料庫。

## Bakery 公開 API

### locale 參數

Nuxt 代理端點與 Wagtail 自訂設定端點接受 allowlist 中的 locale：`zh-hant` 或 `en`。缺省值為 `zh-hant`，其他值回傳 400。

### 首頁與頁面解析

- 移除 Nuxt 的固定首頁 ID `60`。
- 從 Wagtail `Site.root_page` 取得預設首頁，再透過翻譯關係取得指定 locale 的首頁。
- 一般頁面只在該 locale 首頁的子樹中查詢。
- 查詢結果必須是 live、public 且 locale 相符的頁面。

### 全站設定回應

`/api/site-settings/?locale=<locale>` 回傳：

- 正規化後的 locale
- 該語系首頁 ID 與路徑
- 該語系網站名稱、頁尾及聯絡文字
- 已轉換成該語系頁面的導覽項目
- 每個導覽項目的穩定 slug 與公開路徑

若全站文字翻譯不存在或未發布，API 回傳明確的 404／內容未提供狀態，不混用另一語系文字。

## Nuxt 前台

### 多語系路由與固定文字

- 加入 Nuxt i18n 模組，使用 `zh-hant` 預設語系及 `en` 語系。
- `zh-hant` 不加網址前綴；English 加 `/en/`。
- 按鈕、ARIA label、錯誤、載入、聯絡欄位標籤等固定介面字串放入 Nuxt locale message。
- 標題、段落、卡片、表格、案例、頁尾內容等 CMS 文字不放入 Nuxt locale message。
- 每次 Bakery API 請求都從目前 route locale 傳送 locale。
- 設定 `<html lang>`、SEO title、description、canonical 與 `hreflang` 替代網址。

### 無障礙工具列

在主導覽上方加入與來源 HTML 相同的深藍色 36px 工具列：

- 左側：跳到主要內容、字體大小、A+、A、A-
- 右側：繁體中文、English
- 工具列於桌面顯示；手機主選單另外保留語言切換入口
- 目前語系使用可見及 `aria-current` 狀態標示
- 語系切換保留相同頁面 slug，例如 `/about/` 與 `/en/about/`

字體大小採三段固定倍率，作用於 `document.documentElement` 的資料屬性或 CSS custom property。使用者選擇寫入 localStorage；伺服器端渲染期間使用預設值，掛載後才讀取偏好，避免 hydration 不一致。控制按鈕具可辨識的 aria-label 與鍵盤焦點樣式。

## 異常與退化行為

- 不支援的 locale：回傳 400，不猜測語言。
- 指定語系頁面不存在或未發布：回傳 404，Nuxt 顯示該語系的「頁面尚未提供」。
- Bakery API 無法連線：保留錯誤狀態並使用目前語系顯示，不混用中文／英文資料。
- English 翻譯匯入已存在：命令停止並列出衝突，不覆蓋。
- 找不到頁面連結的目標翻譯：匯入停止發布並回報缺少項目。
- localStorage 不可用：字體控制仍在當次瀏覽有效，只是不保存。
- 行動裝置工具列隱藏時：語言切換仍可從主選單操作。

## 測試策略

### Django／Wagtail

- 語系設定只包含 `zh-hant` 與 `en`。
- locale 參數驗證、缺省值與錯誤回應。
- 指定 locale 能找到正確首頁與五頁翻譯。
- 導覽項目能轉換成相同 translation key 的目標語系頁。
- 全站文字依 locale 回傳且不跨語系 fallback。
- 英文匯入建立完整、已發布且互相關聯的五頁。
- 第二次執行匯入不覆蓋既有英文內容。
- 缺少來源頁、區塊或翻譯連結時維持原資料不變。

### Nuxt

- locale 與網址互轉。
- 每個代理 API 都轉送 locale。
- `/` 與 `/en/` 載入不同語系內容。
- 五個頁面的語言切換保留相同 slug。
- 工具列固定文字、目前語系狀態及手機切換入口正確。
- A+／A／A- 邊界、預設值與偏好保存。
- 翻譯不存在、API 中斷及不合法 locale 的錯誤畫面。
- 型別檢查與正式建置成功。

### 手動驗收

1. 瀏覽十個公開網址，確認所有可見內文與導覽語言一致。
2. 在 Wagtail 修改一段 English 內文，預覽、發布並確認前台更新。
3. 桌面與手機寬度測試主導覽和語言切換。
4. 僅使用鍵盤操作跳至主要內容、字體按鈕、語言切換及主選單。
5. 重新整理頁面確認字體大小偏好保留。
6. 檢查各頁 `<html lang>`、title、description、canonical 及 hreflang。

## 上線與回復

1. 匯出並備份目前資料庫。
2. 執行資料庫 migration 與 locale 校正。
3. 以 dry-run 驗證英文翻譯資料及關聯。
4. 執行正式英文匯入並發布。
5. 啟動 Wagtail 與 Nuxt，完成自動及手動驗收。

若匯入失敗，交易會回滾，不留下半套翻譯頁。若前台部署失敗，可回復 Nuxt 程式版本；已建立的 Wagtail 翻譯頁仍保留於後台，不影響既有繁中網址。

## 驗收標準

- 十個預期網址均可載入正確語系且沒有混合語言。
- 工具列內容與來源 HTML 一致，A+／A／A- 和語言切換可用。
- Wagtail 後台可直接修改所有英文頁面與全站文字。
- 英文初稿完整匯入、直接發布且不會在日後被自動覆蓋。
- API 不再依賴固定頁面 ID，且所有查詢具 locale 邊界。
- Django、Nuxt 自動測試、型別檢查及正式建置通過。
