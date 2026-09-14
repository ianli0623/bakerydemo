# Windows Hello 後台登入操作手冊

本功能以 WebAuthn 通行金鑰整合 Windows Hello。ARCANITE 指紋讀取器應接在管理者的 Windows 電腦，而不是 Linux 伺服器。伺服器只保存公開金鑰及稽核紀錄，不保存指紋、Windows PIN、私密金鑰、原始註冊碼或驗證封包。

> Windows Hello 可能依該電腦的安全性設定允許 PIN 作為備援。網站只能確認 Windows Hello 已完成使用者驗證，無法判斷這次使用的是指紋或 PIN。

## 正式環境設定

正式後台必須使用固定網域及 HTTPS。以下假設後台網址為 `https://admin.example.com`：

```dotenv
PRIMARY_HOST=admin.example.com
WEBAUTHN_RP_ID=admin.example.com
WEBAUTHN_ORIGIN=https://admin.example.com
```

- `WEBAUTHN_RP_ID` 只能是主機名稱，不可包含 `https://`、連接埠或路徑。
- `WEBAUTHN_ORIGIN` 必須是使用者實際開啟後台的完整 HTTPS Origin。
- 開始讓使用者註冊後，不應任意變更網域；通行金鑰會受到 RP ID 限制。
- 反向代理須正確傳遞 HTTPS 狀態，並維持安全 Cookie、HSTS 及 HTTPS 重新導向設定。

部署新版程式後執行：

```bash
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py check --deploy
sudo systemctl restart bakerydemo
```

本機開發可使用 `http://localhost:8000`；IP 位址或其他 HTTP 網址不視為相同的 WebAuthn 網站。

## 建立 Windows Hello 專用使用者

1. 使用超級使用者登入 Wagtail 後台。
2. 開啟「設定 → 使用者 → 新增使用者」。
3. 在「登入方式」選擇「Windows Hello（無密碼）」並儲存。
4. 立即複製畫面上只顯示一次的註冊碼。註冊碼會在 15 分鐘後失效。
5. 請使用者在其 Windows 電腦開啟 `/account/security/windows-hello/enrol/`。
6. 輸入帳號及註冊碼，按下「註冊 Windows Hello」，再依 Windows 提示掃描指紋。
7. 完成後會直接登入後台。Windows Hello 專用帳號不套用首次改密碼、90 天密碼效期及密碼歷史規則。

## 既有帳號與第二台裝置

超級使用者可在「報表 → Windows Hello 管理」為既有帳號產生新的註冊碼。每台電腦都必須各自完成一次註冊；把 ARCANITE 讀取器插到另一台電腦不會自動取得登入資格。

既有密碼帳號加註冊 Windows Hello 後仍保留密碼登入，以利分批導入。原有密碼仍受 90 天效期、複雜度、最近三次密碼歷史及五次失敗鎖定規則保護。

## 撤銷、遺失與復原

1. 超級使用者開啟「報表 → Windows Hello 管理」。
2. 找到使用者及遺失裝置的憑證，按「撤銷」。
3. 若需重新綁定，按「產生註冊碼」，再請使用者於新電腦完成註冊。
4. 撤銷最後一組憑證前，先確認使用者有其他可用憑證或已取得新的註冊碼。

註冊、登入、失敗、限流及撤銷會寫入通行金鑰稽核資料表。登入驗證連續失敗五次後，同一來源與憑證會暫停 15 分鐘。

## 緊急管理者帳號

至少保留一個不供日常使用的超級使用者密碼帳號：

- 使用符合密碼政策的獨立高強度密碼，放在組織核准的密碼保管庫。
- 不要為此帳號移除密碼，也不要與個人帳號共用。
- 定期確認帳號可登入、密碼未過期，並記錄測試日期。
- 僅在 Windows Hello 全面故障或所有憑證遺失時使用，使用後檢查稽核紀錄。

## 驗收清單

- Edge 與 Chrome 均可使用 ARCANITE 完成首次註冊及後續登入。
- 取消或逾時時只顯示一般錯誤，不會登入。
- 過期或重複使用的註冊碼會失敗。
- 已用過的驗證挑戰不能重放。
- 第二台 Windows 電腦可另外註冊並登入。
- 撤銷後，該憑證下一次登入立即失敗。
- 五次驗證失敗會暫停 15 分鐘。
- Windows Hello 專用帳號不會被導向密碼到期頁。
- 無可用憑證的無密碼帳號無法進入後台。
- 緊急管理者密碼帳號仍可正常登入。

驗收紀錄可保存 Windows 版本、瀏覽器版本、裝置型號、測試日期與結果，但不得記錄指紋資料或 Windows PIN。
