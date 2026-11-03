# 2026-11-03 Trivy 套件漏洞修正紀錄

## 修正範圍

本次僅在本機隔離工作目錄修正、測試及重新打包，未部署至伺服器。

原始部署包的 Trivy 0.76.1 報告有 93 筆告警（Critical 3、High 39、Medium 36、Low 15），皆來自 `nuxt-bakery-demo/package-lock.json`。擴大掃描另發現根目錄開發工具鎖定檔有 31 筆告警，本次亦一併修正。

## 主要版本調整

| 套件 | 原版本 | 修正後鎖定版本 |
| --- | --- | --- |
| Nuxt／Nuxt Vite builder | 4.5.2 | 4.6.4 |
| Vue／Vue SSR renderer | 3.5.41 | 3.5.44 |
| vue-i18n／Intlify | 10.0.8、11.4.10 | 11.4.17 |
| Vite | 8.2.2 | 8.3.5 |
| node-forge | 1.4.0 | 1.4.2 |
| glob | 10.5.0、13.0.6 | 14.0.3 |
| minimatch | 5.1.9、9.0.9、10.2.6 | 11.0.4 |
| undici | 8.10.0 | 8.12.3 |
| devalue | 5.9.1 | 5.9.4、6.0.3 |
| seroval | 1.6.2 | 1.7.7 |
| source-map-js | 1.2.1 | 1.2.2 |

其餘間接套件透過相容版本更新；舊版 simple-git、shell-quote 與 argv-parser 已不在新相依樹中。

上游父套件尚未調整 glob／minimatch 的版本範圍，因此採用限定父套件的 npm overrides，並測試實際檔案追蹤與目錄篩選行為。minimatch 11 已移除部分正規表示式 API，故未將舊主版本任意全域覆寫。[glob 14 變更紀錄](https://github.com/isaacs/node-glob/blob/v14.0.2/changelog.md)、[minimatch 11 變更紀錄](https://github.com/isaacs/minimatch/blob/v11.0.1/changelog.md)。

根目錄改用 ESLint 10 與修補版 Stylelint，並更新其鎖定檔。無障礙與相容性測試使用的套件已明確列為 devDependencies，避免依賴上游偶然提供的間接套件。

## 本機驗證結果

| 驗證項目 | 結果 |
| --- | --- |
| Trivy：Nuxt 鎖定檔，包含開發相依 | 0 筆告警 |
| Trivy：根目錄開發工具鎖定檔 | 0 筆告警 |
| Trivy：產物隨附套件 manifest 建立的 SBOM | 41 個套件，0 筆告警 |
| 前台單元測試 | 95 項通過 |
| Nuxt 型別檢查與正式 SSR 建置 | 通過 |
| 正式 SSR／CSP 整合測試 | 4 項通過 |
| 開發資源 CORS／nosniff 測試 | 21 項通過 |
| Django 測試，含本機 Nginx 驗證 | 357 項通過，使用記憶體資料庫 |
| Ruff、Curlylint、DjHTML、ESLint、Stylelint、Prettier | 通過 |

使用 Trivy 0.76.1；漏洞資料庫更新時間為 `2026-11-03T01:30:30Z`。未忽略任何漏洞 ID 或風險等級。來源掃描將開發 node_modules／暫存建置目錄分開處理；部署資料夾另行完整掃描。

一般 `trivy filesystem` 不會辨識本次 `.output` 的套件 manifest，不能單憑該路徑掃描回傳 0 就視為已覆蓋執行期。本次另從 `.output/server/node_modules/**/package.json` 取得實際名稱與版本，核對其均存在於已驗證的鎖定檔，再建立 SBOM 供 Trivy 掃描。已打包到 JavaScript 內的套件另由來源鎖定檔涵蓋。

報告反映指定時間漏洞資料庫的已知套件告警，不代表網站弱點掃描、主機作業系統或未安裝的 Python 相依套件均已完成安全驗收。

## 部署前的版本需求

- 本次建置使用 Node.js **24.22.2**，已同步 `.nvmrc`。
- Nuxt 最低需求為 `^22.22.3 || ^24.15.0 || >=26.0.0`；舊版 Node.js 24.11.1 不符合需求。
- 上傳前須確認主機與 systemd 實際使用的 Node.js 路徑。此次未更動主機版本或服務。
- 新部署包不包含實際環境檔、API Key、資料庫、媒體、Windows 虛擬環境或原始開發 node_modules；Nitro 隨附的執行期模組必須保留。
- Ubuntu 仍需安裝 Python 相依套件，依正式部署手冊檢查環境、資料庫 migration 與服務切換。Fast-ID、客戶內網 API 與 Linux 實機流程仍須部署後驗收。

重新驗證部署資料夾時，可使用：

```bash
trivy filesystem --scanners vuln --include-dev-deps --exit-code 1 /path/to/release
trivy sbom --scanners vuln --exit-code 1 /path/to/release/security/nuxt-runtime.cdx.json
```

部署包內的 `security` 目錄保留掃描結果與執行期 SBOM；`SHA256SUMS` 用於核對包內檔案是否與本機驗證版本一致。
