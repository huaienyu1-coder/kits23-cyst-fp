# YouTube 去廣告部署包

> 這個資料夾和本 repo 的 KiTS23 研究程式**無關**，是獨立的工具包，放在
> `claude/youtube-ad-blocker-deploy-xv2yuy` 分支上。不建議合併進 `main`。
>
> 資料整理日期：2026-11。所有工具都是**免費、開源**的。

---

## 先看結論：你在哪裡看 YouTube，就用哪一個

| 你在哪裡看 | 推薦做法 | 擋廣告效果 |
|---|---|---|
| 電腦：**Firefox** | uBlock Origin（完整版）+ SponsorBlock | ★★★ 最穩定 |
| 電腦：**Chrome / Edge** | uBlock Origin **Lite** + SponsorBlock | ★★ 大多能擋，偶爾漏 |
| 電腦：**Brave** | 內建 Shields 就會擋，不用另外裝 | ★★★ |
| **Android** | ReVanced（改裝官方 App）／NewPipe／Firefox + uBlock Origin | ★★★ |
| **iPhone / iPad** | 改用 **Brave 瀏覽器**看 YouTube（或 Safari + uBlock Origin Lite） | ★★（官方 App 內擋不了） |
| 家裡有 NAS／小主機 | 自架 Invidious（沒有廣告的 YouTube 網頁前端） | ★★（需要維護） |

**為什麼 Chrome 只能用「Lite」？** 完整版 uBlock Origin 使用 Manifest V2 架構，Chrome 138 起預設停用，
Chrome 139 連企業政策例外也移除，2026-08-31 更從 Chrome 線上應用程式商店下架。在 Chrome 上
唯一的官方選擇是作者另外做的 Manifest V3 版本 **uBlock Origin Lite**。想要最強的 YouTube 擋廣告，請用 **Firefox**。

**SponsorBlock 是什麼？** 它不是擋廣告，而是**自動跳過影片裡 YouTuber 自己講的業配段落**
（這種內嵌在影片裡的廣告，任何擋廣告工具都擋不到）。資料由使用者群眾標記。不需要可以不裝。

---

## 我在 GitHub／網路上找到並評估過的工具

| 工具 | 原始碼 | 用途 | 結論 |
|---|---|---|---|
| uBlock Origin | [gorhill/uBlock](https://github.com/gorhill/uBlock) | 完整版擋廣告（Firefox） | ✅ 採用 |
| uBlock Origin Lite | [uBlockOrigin/uBOL-home](https://github.com/uBlockOrigin/uBOL-home) | MV3 版擋廣告（Chrome／Edge／Safari） | ✅ 採用 |
| SponsorBlock | [ajayyy/SponsorBlock](https://github.com/ajayyy/SponsorBlock) | 跳過影片內業配 | ✅ 採用 |
| Invidious + companion | [iv-org/invidious](https://github.com/iv-org/invidious) | 自架無廣告 YouTube 前端 | ✅ 選用（方案 C） |
| ReVanced | [ReVanced](https://github.com/ReVanced) | 改裝 Android 官方 YouTube App | ✅ Android 推薦 |
| NewPipe | [TeamNewPipe/NewPipe](https://github.com/TeamNewPipe/NewPipe) | Android 輕量 YouTube 用戶端 | ✅ Android 推薦 |
| 各種小型「YouTube Ad Blocker」擴充／使用者腳本（例如 `iqbal-rashed/youtube-ad-blocker`、`SysAdminDoc/YoutubeAdblock`、`TheRealJoelmatic/RemoveAdblockThing`） | — | 單一功能擋 YouTube 廣告或反偵測彈窗 | ❌ 不採用 |

最後一列不採用的原因：多為個人維護的小專案，常需要「手動載入未封裝擴充」或給予大量網站權限，
YouTube 一改版就容易失效；跟 uBlock Origin 同時開還可能互相衝突。我沒有逐一審查它們的程式碼，
所以不建議裝在你的電腦上——上面那幾個主流工具已經涵蓋同樣的功能，而且有大量使用者與長期維護。

---

## 方案 A：手動安裝（最快，大約 1 分鐘）

**請認明開發者**：uBlock Origin／Lite 是 **Raymond Hill (gorhill)**；SponsorBlock 是 **Ajay Ramachandran (ajayyy)**。
商店裡有很多名字相似的山寨版。

| 瀏覽器 | 擋廣告 | 跳過業配 |
|---|---|---|
| Firefox | [uBlock Origin](https://addons.mozilla.org/firefox/addon/ublock-origin/) | [SponsorBlock](https://addons.mozilla.org/firefox/addon/sponsorblock/) |
| Chrome | [uBlock Origin Lite](https://chromewebstore.google.com/detail/ublock-origin-lite/ddkjiahejlhfcafbddmgiahcphecmpfh) | [SponsorBlock](https://chromewebstore.google.com/detail/sponsorblock-for-youtube/mnjggcdmjocbbbhaepdhchncahnbgone) |
| Edge | [uBlock Origin Lite](https://microsoftedge.microsoft.com/addons/detail/ublock-origin-lite/cimighlppcgcoapaliogpjjdehbnofhn) | [SponsorBlock](https://microsoftedge.microsoft.com/addons/detail/sponsorblock-for-youtube-/mbmgnelfcpoecdepckhlhegpcehmpmji) |
| Safari（Mac／iPhone／iPad） | App Store 搜尋「uBlock Origin Lite」（開發者 Raymond Hill），官方連結見 [uBOL-home](https://github.com/uBlockOrigin/uBOL-home) | — |

Chrome／Edge 裝好 uBlock Origin Lite 後：點工具列拼圖圖示 → 釘選 uBlock Origin Lite →
到 YouTube 點它的圖示，確認模式是「最佳（Optimal）」或「完整（Complete）」。

---

## 方案 B：一鍵部署腳本（自動幫所有瀏覽器裝好）

腳本使用瀏覽器官方的「企業政策」功能（`ExtensionSettings`，模式 `normal_installed`）：
瀏覽器啟動時會自動從**官方商店**下載安裝擴充功能，之後也會自動更新。你仍然可以在瀏覽器裡停用它們。

| 瀏覽器 | 自動安裝 |
|---|---|
| Chrome | uBlock Origin Lite + SponsorBlock |
| Edge | uBlock Origin Lite + SponsorBlock |
| Firefox | uBlock Origin（完整版）+ SponsorBlock |

> **正常現象**：使用政策後，Chrome／Edge 會顯示「**由貴機構管理**」。這只代表有政策存在，
> 不是中毒，也沒有人在監控你。執行移除腳本後就會消失。
>
> **公司／學校的電腦**請不要執行，可能違反 IT 規定或被既有政策覆蓋。

### 下載

在 GitHub 上切換到 `claude/youtube-ad-blocker-deploy-xv2yuy` 分支 → 綠色 **Code** 按鈕 → **Download ZIP**，
解壓縮後進入 `youtube-adblock` 資料夾。

### Windows

1. （建議）解壓縮**之前**，在 ZIP 檔上按右鍵 → 內容 → 勾選「**解除封鎖**」→ 確定。可避免 SmartScreen 警告。
2. 進入 `youtube-adblock\windows`，雙擊 **`install.cmd`**。
3. 跳出 UAC（使用者帳戶控制）時按「**是**」。
4. 看到「完成！」後，把 Chrome／Edge／Firefox **完全關閉再重開**，約 1 分鐘內擴充功能會自動出現。

移除：雙擊 **`uninstall.cmd`**。

進階用法（在 PowerShell 中執行）：

```powershell
cd youtube-adblock\windows
# 不要 SponsorBlock、略過 Edge
powershell -ExecutionPolicy Bypass -File .\youtube-adblock.ps1 -Action Install -NoSponsorBlock -SkipEdge
# 查看目前狀態（不需管理員）
powershell -ExecutionPolicy Bypass -File .\youtube-adblock.ps1 -Action Status
```

腳本只會新增／移除自己的項目；你原本若已有其他 `ExtensionSettings` 政策，會被保留。
寫入位置：`HKLM\SOFTWARE\Policies\Google\Chrome`、`...\Microsoft\Edge`、`...\Mozilla\Firefox` 底下的 `ExtensionSettings` 值。

### macOS

**最簡單的方法（建議，不用描述檔）**：看你用哪個瀏覽器，只裝一個就好——

- **Safari**：App Store 安裝 [uBlock Origin Lite](https://apps.apple.com/app/id6745342698)（需 macOS 13.5 以上）→
  打開 Safari → 選單列「Safari」→「設定⋯」→「延伸功能」→ 勾選 uBlock Origin Lite → 網站權限選「允許」。
- **Chrome**：用 Chrome 打開 [uBlock Origin Lite](https://chromewebstore.google.com/detail/ublock-origin-lite/ddkjiahejlhfcafbddmgiahcphecmpfh) →「加到 Chrome」→「新增擴充功能」。
- **Firefox**：用 Firefox 打開 [uBlock Origin](https://addons.mozilla.org/firefox/addon/ublock-origin/) →「新增至 Firefox」。

**進階：用描述檔一次裝好 Chrome／Edge／Firefox**

1. 雙擊 **`macos/youtube-adblock.mobileconfig`**（會提示「已下載描述檔」）。
2. 打開描述檔設定頁，點「YouTube 去廣告」→ **安裝** → 輸入電腦密碼：
   - macOS 14 以後：**系統設定 → 一般 → 裝置管理**
   - macOS 13：系統設定 → 隱私權與安全性 → 描述檔
   - macOS 12 以前：系統偏好設定 → 描述檔
3. 完全關閉瀏覽器再重開（⌘Q），約 1 分鐘內擴充功能會自動出現。

移除：同一個頁面選取描述檔 → 按「−」移除。

Safari 不吃這個描述檔，請照方案 A 從 App Store 安裝 uBlock Origin Lite，然後
Safari → 設定 → 延伸功能 → 勾選 uBlock Origin Lite，並允許它在 youtube.com 上執行。

### Linux

```bash
cd youtube-adblock/linux
sudo bash youtube-adblock.sh install                     # 安裝
sudo bash youtube-adblock.sh install --no-sponsorblock   # 只要擋廣告
bash youtube-adblock.sh status                           # 查看狀態
sudo bash youtube-adblock.sh uninstall                   # 移除
```

會寫入：`/etc/opt/chrome/policies/managed/`、`/etc/chromium/policies/managed/`（以及 snap 版 Chromium 的
`/etc/chromium-browser/...`）、`/etc/opt/edge/policies/managed/`，以及 `/etc/firefox/policies/policies.json`
（若檔案已存在會**合併**，並先備份為 `policies.json.bak-youtube-adblock`）。
Flatpak 版的瀏覽器讀不到這些路徑，請改用方案 A 手動安裝。

### 確認有沒有生效

在網址列輸入：Chrome `chrome://policy`、Edge `edge://policy`、Firefox `about:policies`，
應該看到 `ExtensionSettings`，狀態為「確定／OK」。若擴充功能沒出現，在 `chrome://policy` 按「重新載入政策」後重開瀏覽器。

---

## 手機

### Android

1. **ReVanced（最推薦，用官方 App 的體驗）**：用 ReVanced Manager 修補官方 YouTube App，
   去除廣告，還有背景播放、內建 SponsorBlock。**只從 [revanced.app](https://revanced.app) 或
   [github.com/ReVanced](https://github.com/ReVanced) 下載**，網路上有很多假冒的「ReVanced APK」網站。
2. **NewPipe（不想改 App）**：輕量、不用登入、沒廣告，可背景播放與下載。從
   [newpipe.net](https://newpipe.net) 或 F-Droid 安裝。
3. **用瀏覽器看**：[Firefox for Android](https://play.google.com/store/apps/details?id=org.mozilla.firefox)
   + [uBlock Origin](https://addons.mozilla.org/android/addon/ublock-origin/)，或 Brave 瀏覽器。

### iPhone / iPad

> **先講清楚**：iPhone 上的**官方 YouTube App 沒有任何工具能擋廣告**（Apple 不允許其他 App 改動 YouTube App）。
> 擋廣告工具只能在「瀏覽器」裡運作，所以做法是：**改用瀏覽器看 YouTube，把它當成 YouTube App 用**。
> 介面跟 App 很像，登入 Google 帳號後訂閱、紀錄、播放清單都一樣。

#### 推薦：Brave 瀏覽器（最簡單，不用設定）

1. App Store 安裝 [**Brave**](https://apps.apple.com/app/id1052879175)（免費）。
2. 打開 Brave，網址列輸入 `youtube.com`，右上角登入你的 Google 帳號。廣告預設就會被擋掉。
3. 把 YouTube 加到 Brave 的「我的最愛」，之後一打開 Brave 就能點進去。
4. （選用）背景播放／鎖定畫面繼續聽：Brave 設定 →「媒體」（Media）→ 開啟「背景音訊」（Background Audio）。
5. （選用）讓別人傳的 YouTube 連結（LINE、Messenger…）直接用 Brave 開：
   - 設定 → App → 預設 App → 瀏覽器 App → 選 **Brave**；
   - 長按 YouTube App →「移除 App」（不想刪可以先移到資料庫）。沒有 YouTube App 時，連結就會改用預設瀏覽器開。
   - **LINE** 預設用自己的內建瀏覽器開連結（擋不到廣告）：LINE 主頁 → 右上角齒輪「設定」→「LINE Labs」→
     開啟「**使用預設瀏覽器開啟連結**」。

#### 也可以：Safari + uBlock Origin Lite（需要 iOS 18.5 以上）

1. App Store 安裝 [**uBlock Origin Lite**](https://apps.apple.com/app/id6745342698)（開發者 Raymond Hill，免費）。
2. 打開 設定 → App → Safari → 延伸功能 → uBlock Origin Lite → 開啟「**允許延伸功能**」，
   網站權限選「**允許**」所有網站（給的權限不夠，YouTube 廣告會擋不乾淨）。
3. 用 Safari 開 `youtube.com` 並登入。
4. 同一頁的延伸功能清單裡，**把其他擋廣告工具（例如 AdBlock 系列）關掉**，只留 uBlock Origin Lite，避免互相衝突。

查 iOS 版本：設定 → 一般 → 關於本機 → iOS 版本。

> 確認沒裝到山寨版：開發者要是 **Raymond Hill**，而且用官方連結
> <https://apps.apple.com/app/ublock-origin-lite/id6745342698>（來自 [uBOL-home](https://github.com/uBlockOrigin/uBOL-home)）
> 打開時，按鈕顯示「打開」就代表你裝的就是這個。App Store 評分數是**依國家／地區分開計算**的，
> 加上 iPhone 版 2025 年才上架，台灣區評分數少是正常的。

#### 不建議

- **改 DNS／裝「全手機擋廣告」App**（AdGuard DNS、NextDNS 等）：擋不到 YouTube App 的廣告（廣告和影片來自同一個伺服器），還可能讓 YouTube 壞掉。
- **側載改裝版 YouTube App**（uYou、YTLite 之類的 IPA）：要用電腦側載、免費帳號每 7 天要重簽一次，來源也難以確認安全，不適合一般使用者。
- 想**繼續用官方 App 又沒廣告**，唯一的官方方法是 **YouTube Premium**（付費）。

---

## 方案 C（選用）：自架 Invidious

[Invidious](https://invidious.io) 是開源的 YouTube 替代網頁前端：沒有廣告、不追蹤、不用 Google 帳號也能訂閱頻道。
適合家裡有 NAS、迷你電腦或一直開著的電腦，而且已安裝 Docker 的人。

```bash
cd youtube-adblock/invidious
bash setup.sh        # 自動產生隨機密鑰（.env）→ 下載映像檔 → 啟動
```

打開 <http://localhost:3000> 即可使用。

- **家裡其他裝置也要用**：把 `.env` 裡的 `INVIDIOUS_BIND=127.0.0.1` 改成 `0.0.0.0`，執行
  `docker compose up -d`，然後用 `http://<這台主機的區網 IP>:3000` 連線。**不要直接開放到網際網路**；
  要外連請自行加上 HTTPS 反向代理。
- **更新**（YouTube 改版導致無法播放時通常更新就好）：`docker compose pull && docker compose up -d`
- **停止**：`docker compose down`
- **重要限制**：YouTube 會封鎖雲端機房（VPS、Railway 等）的 IP，所以**請架在家用網路**上。
  即使如此，YouTube 仍不時會讓 Invidious 暫時失效，這是本方案的維護成本。
- 搭配瀏覽器擴充 [LibRedirect](https://github.com/libredirect/browser_extension) 可以把所有 YouTube 連結自動導向你的 Invidious。

`docker-compose.yml` 是依照[官方安裝文件](https://docs.invidious.io/installation/)精簡而成（Invidious +
invidious-companion + PostgreSQL），資料表由 `check_tables: true` 自動建立。

---

## 疑難排解

**還是有廣告，或出現「YouTube 不允許使用廣告攔截器」的提示**

- Firefox（uBlock Origin）：點 uBO 圖示 → 齒輪（控制台）→「過濾規則清單」→「立即更新」，
  確認「uBlock filters – Quick fixes」有勾選。然後重新整理 YouTube。
- Chrome／Edge（uBlock Origin Lite）：在 YouTube 頁面點 uBOL 圖示，把模式拉到「**完整（Complete）**」後重新整理。
  再到 `chrome://extensions` → uBlock Origin Lite → 詳細資料 →「網站存取權」設為「**在所有網站上**」。
- **只保留一個擋廣告工具**：停用 AdBlock、AdBlock Plus、AdGuard 擴充等其他擋廣告工具，避免互相衝突。
- 確認瀏覽器與擴充功能都是最新版。YouTube 和擋廣告工具一直在互相攻防，偶爾會有幾天失效，通常會很快修好。

**擴充功能沒有自動出現（方案 B）**

- 瀏覽器要**完全關閉**（Windows 右下角系統匣裡背景執行的也要結束）再開。
- 檢查 `chrome://policy`／`edge://policy`／`about:policies` 是否有 `ExtensionSettings`。
- 無痕視窗預設不跑擴充功能：到擴充功能詳細資料開啟「允許在無痕模式下執行」。

**關於條款**：使用擋廣告工具本身一般不違法，但違反 YouTube 服務條款，YouTube 可能顯示警告或限制播放。
想支持創作者、又不想看廣告，官方方案是 YouTube Premium。

---

## 檔案說明

```
youtube-adblock/
├── README.md                          ← 本說明
├── windows/
│   ├── install.cmd                    ← 雙擊安裝
│   ├── uninstall.cmd                  ← 雙擊移除
│   └── youtube-adblock.ps1            ← 主程式（Install / Uninstall / Status）
├── macos/
│   └── youtube-adblock.mobileconfig   ← 雙擊安裝的設定描述檔
├── linux/
│   └── youtube-adblock.sh             ← install / uninstall / status
└── invidious/
    ├── docker-compose.yml             ← 自架 Invidious
    └── setup.sh                       ← 產生密鑰並啟動
```

## 參考資料

- uBlock Origin 在 Chrome 上的現況（MV2 移除時程）：<https://ublockorigin.com/chrome/>
- Google 的 Manifest V2 淘汰時程：<https://developer.chrome.com/docs/extensions/develop/migrate/mv2-deprecation-timeline>
- uBlock Origin Lite 官方文件／管理設定：<https://github.com/uBlockOrigin/uBOL-home/wiki>
- Chrome `ExtensionSettings` 政策：<https://support.google.com/chrome/a/answer/9867568>
- Edge `ExtensionSettings` 政策：<https://learn.microsoft.com/en-us/deployedge/microsoft-edge-manage-extensions-ref-guide>
- Firefox 政策（ExtensionSettings）：<https://mozilla.github.io/policy-templates/>
- Invidious 安裝文件：<https://docs.invidious.io/installation/>
