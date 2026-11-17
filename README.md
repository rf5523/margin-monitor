# 融資水位儀表板

每天晚上 **22:00 自動抓證交所資料**、算水位差、更新儀表板；**23:00 用 LINE 推播**最新結果給你。不用開電腦，全程跑在 GitHub 免費伺服器上。

## 算法

| 項目 | 算法 |
|---|---|
| X | 融資餘額（億）÷ 2100 × 100 |
| Y | 加權指數 ÷ 17306 × 100 |
| 水位差 | X − Y（百分點） |

| 水位差 | 訊號 |
|---|---|
| ≥ 30 | 🔴 極度危險 |
| ≥ 26 | 🟠 危險 |
| < 26 | 🟢 觀察 |

## 資料來源

證交所官網公開 JSON（不是爬儀表板網頁，那頁是 JS 動態載入，抓 HTML 拿不到數字）：

- 融資餘額：`https://www.twse.com.tw/exchangeReport/MI_MARGN?response=json&date=YYYYMMDD&selectType=ALL`
→ 第 1 張表「信用交易統計」裡「融資金額（仟元）」的「今日餘額」，除以 100,000 換算成「億」。
已驗證：2026-11-16 為 524,497,993 仟元 ＝ 5,244.98 億。
- 加權指數：`https://www.twse.com.tw/exchangeReport/FMTQIK?response=json&date=YYYYMMDD`
→ 當月資料中該日期的「發行量加權股價指數」。
已驗證：2026-11-16 為 41,040.08；X=249.76、Y=237.14、差值 +12.62（觀察），與線上儀表板一致。

## 檔案說明

```
fetch_margin.py # 22:00 抓取 + 計算，寫入 docs/data.json（只用標準函式庫）
notify_line.py # 23:00 讀 docs/data.json，用 LINE 推播
docs/
index.html # 儀表板（最新訊號、走勢圖、歷史表，不依賴外部套件）
data.json # 歷史資料（日期為 key，每筆含 margin/index/x/y/diff/label/level）
.github/workflows/
update.yml # 每天 22:00 台北（UTC 14:00）跑 fetch_margin.py
notify.yml # 每天 23:00 台北（UTC 15:00）跑 notify_line.py
```

## 使用方法（第一次設定，約 10 分鐘）

### 第 1 步：把檔案放進 GitHub repo

有兩種做法，擇一：

**A. 你已經有 `rf5523/margin-monitor`（建議）**：這個 repo 的 `docs/data.json` 格式跟這包完全一樣，
最新資料已經到 2026-11-16。只要把 `fetch_margin.py`、`notify_line.py`、
`.github/workflows/update.yml`、`.github/workflows/notify.yml`、`docs/index.html`
覆蓋／補進去就好，`docs/data.json` 不用動，歷史不會丟。

**B. 全新 repo**：在 GitHub 開一個新的 repo（例如 `margin-monitor`），把這包全部檔案上傳
（網頁上傳或 `git push` 都可以），`docs/data.json` 已內含最近約 45 天的回補資料。

### 第 2 步：開啟 GitHub Pages（儀表板網址）

repo → **Settings → Pages** → **Build and deployment**：
- Source 選 **Deploy from a branch**
- Branch 選 **main**，資料夾選 **/docs**，按 Save。

等 1–2 分鐘，儀表板就在 `https://<你的帳號>.github.io/<repo 名稱>/`。
如果是沿用 `rf5523/margin-monitor`，網址不變：`https://rf5523.github.io/margin-monitor/`。

> 若你用 B 做法開了新 repo，`notify_line.py` 的推播連結預設仍指向舊站。
> 改法：到 repo 的 notify workflow 裡加兩個環境變數，或直接改 `notify_line.py`
> 最上方的 `MARGIN_DATA_URL` / `MARGIN_PAGE_URL` 預設值。

### 第 3 步：設定 LINE 推播（兩個 Secrets）

repo → **Settings → Secrets and variables → Actions → New repository secret**，各建一個：

| Secret 名稱 | 值 | 去哪裡拿 |
|---|---|---|
| `LINE_CHANNEL_ACCESS_TOKEN` | Channel access token（長字串） | [LINE Developers](https://developers.line.biz/) → 你的 Messaging API Channel → Messaging API → 最下方按 **Issue** |
| `LINE_USER_ID` | 你的 LINE User ID（U 開頭） | 先把該 Channel 的官方帳號加為好友、傳任意訊息，再到 LINE Developers 的 Webhook／或用 `GET https://api.line.me/v2/bot/profile/{userId}` 查；也可以用 LINE Notify 以外的方式在後台看。多人接收時用英文逗號隔開 |

> ⚠️ Token 只貼在 GitHub Secrets，不要貼在聊天室、不要 commit 進 repo。

### 第 4 步：手動測試一次

repo → **Actions** 分頁：

1. 點 **update-margin-data** → **Run workflow** → 等它跑完變綠色。
到 **docs/data.json** 看最新一筆是不是今天（交易日晚上才會有今天的；白天測會是最近一個交易日）。
2. 點 **notify-line** → **Run workflow** → 你的 LINE 應該馬上收到一則推播。
沒收到：先看該次執行的 log（通常是 Secret 名稱打錯或 token 過期）。

測試沒問題之後就不用再管了，之後每天自動跑。

### 第 5 步：之後每天自動發生的事

| 時間（台北） | 做的事 |
|---|---|
| 22:00 | `update.yml` 抓證交所當天資料，算好寫入 `docs/data.json`，自動 commit，儀表板更新 |
| 23:00 | `notify.yml` 讀最新一筆，用 LINE 推給你 |

推播長這樣：

```
2026-11-16
融資餘額: 5,244.98 億
加權指數: 41,040.08
水位差 X-Y: +12.62(觀察)
判斷: >=30 極度危險、>=26 危險、<26 觀察
詳細: https://rf5523.github.io/margin-monitor/
資料來源: 臺灣證券交易所
```

## 本地測試（不用 GitHub 也能跑）

```bash
python fetch_margin.py --date 20261116 --dry-run # 抓指定日期，只印不寫檔
python fetch_margin.py --dry-run # 抓最近有資料的交易日
python fetch_margin.py --backfill-days 30 # 回補最近 30 天
LINE_CHANNEL_ACCESS_TOKEN=x LINE_USER_ID=Uxxx python notify_line.py --dry-run # 只印推播文字
```

只用 Python 標準函式庫，Python 3.10 以上直接跑，不用 pip。

## 常見問題

- **假日／休市沒新資料？** 22:00 那次抓不到今天，程式會自動往前找最近一個交易日；
23:00 推播會改推最近一筆，並在訊息開頭註明「今日尚無新資料」。
- **22:00 還沒看到今天的資料？** 證交所通常傍晚才公布當天融資餘額，GitHub 排程本身也可能延遲
幾分鐘到十幾分鐘；隔天早上看一定有。若連續兩天都沒更新，到 Actions 看 update 那次的 log。
- **23:00 沒收到 LINE？** 依序檢查：(1) Secrets 兩個名字有沒有打對；
(2) token 有沒有過期（LINE Developers 重新 Issue 一個再貼）；
(3) User ID 是不是 U 開頭、是不是加了該官方帳號好友；
(4) Actions 裡 notify-line 那次的 log 寫什麼。
- **想改基準或門檻？** 改 `fetch_margin.py` 最上方的 `MARGIN_BASE`（2100）、
`INDEX_BASE`（17306），以及 `classify()` 裡的 26／30；`notify_line.py` 訊息裡的判斷文字也要一起改。
- **這訊號能直接拿來交易嗎？** 不行。它只是「融資相對指數超漲的程度」，
訊號出現時先檢查部位與風險，不要單憑一個數字進出。
