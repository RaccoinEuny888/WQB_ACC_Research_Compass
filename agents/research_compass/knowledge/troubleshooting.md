# 常見問題對照（回覆格式：發生什麼 → 為什麼 → 怎麼修）

> 使用者貼畫面訊息時查這裡。查不到就照實說「這個訊息我沒看過」，請他貼完整訊息，不要猜。
> 不要求使用者貼 `.env` 的內容；需要確認格式時，請他自己對照範本。

## 環境（A1）

| 現象 | 為什麼 | 怎麼修 |
|---|---|---|
| `uv: command not found` | 還沒安裝 uv | 照 https://github.com/astral-sh/uv 安裝後，關掉終端機重開一個 |
| `python: command not found` 或跑程式說找不到套件 | 沒有啟動虛擬環境 | `source .venv/bin/activate`（每開一個新終端機都要做一次），或改用 `uv run python …` |
| worker 開不起來，出現 `ModuleNotFoundError: No module named 'telebot'`／`dotenv`／`pandas` 等 | 建了虛擬環境但沒有真的把套件裝進去 | `source .venv/bin/activate` 之後執行 `uv sync`，再重開 worker |
| `ModuleNotFoundError: No module named 'src'` | 不在 open machine 資料夾，或沒設 `PYTHONPATH` | `cd` 到 open machine 資料夾；跑 GA 前執行 `export PYTHONPATH="$PWD:$PWD/src${PYTHONPATH:+:$PYTHONPATH}"` |

## 記憶體不足 OOM（雲端 VM 常見）

- 現象：VS Code 突然斷線、一直 reconnecting、顯示 window terminated unexpectedly；Python 跑到一半終端機只印 `Killed`；SSH 卡住。
- 為什麼：VM 的記憶體（RAM）太小（常見 1～2 GB），VS Code 和研究程式一起跑就用完了，系統會強制關掉最吃記憶體的程式。這不是 open machine 壞掉。
- 確認：`sudo dmesg | grep -i -E "out of memory|killed process"`
- 怎麼修：設 swap（拿一塊硬碟空間當備用記憶體）。**建議在開 VS Code 之前，先用一般 SSH 終端機做**，因為 VS Code 第一次連線、裝擴充套件時最吃記憶體。
  ```bash
  free -h          # 看目前有沒有 swap
  df -h /          # 看硬碟剩多少
  sudo fallocate -l 4G /swapfile
  sudo chmod 600 /swapfile
  sudo mkswap /swapfile
  sudo swapon /swapfile
  echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
  free -h          # Swap 那一行應出現 4.0Gi
  ```
- 要講清楚的限制：swap 讓程式不會被關掉，但不會變快；如果一直很卡，就是 VM 規格太小要升級。swap 會佔硬碟空間。少數 VPS 不允許開 swap。Mac、Windows 本機不用設。
- 大小的經驗值：RAM 1～2 GB 配 2～4 GB swap [?]（常見做法，非官方規定）。

## Telegram（A3，最常卡住）

**推薦做法（最穩）**：在 Telegram 對自己的機器人傳 `/start` → 瀏覽器開 `https://api.telegram.org/bot<你的Bot_Token>/getUpdates` → 找 `"chat":{"id":` 後面那串數字 → 填進 `.env` 的 `TELEGRAM_CHAT_ID=""`。網址裡有 token，不要截圖分享。

| 現象 | 為什麼 | 怎麼修 |
|---|---|---|
| 找不到 token | BotFather 的訊息捲走了，或還沒建機器人 | 對 `@BotFather` 傳 `/mybots` → 選你的機器人 → API Token；還沒建就傳 `/newbot` |
| 跑 `set_telegram_chat_id.py` 出現 `Error: 'result'` | 這支程式常常抓不到（token 讀不到、或 Telegram 回傳格式不如預期） | 不要再重跑，改用上面的推薦做法手動填 Chat ID |
| 跑 `set_telegram_chat_id.py` 出現 `Error: list index out of range` | 機器人還沒收到任何訊息 | 對**你自己建的機器人**（不是 BotFather）傳 `/start`，或直接改用推薦做法 |
| getUpdates 網頁顯示 `"result":[]` | 機器人還沒收到訊息，或訊息已被讀走 | 對自己的機器人再傳一次 `/start`，重新整理網頁 |
| getUpdates 網頁顯示 `"ok":false` 和 `Unauthorized` | 網址裡的 token 錯了（少字、多空格、`<>` 沒拿掉） | 從 BotFather 重新複製 token；網址格式是 `bot` 後面直接接 token，中間沒有空格 |
| 填了 id 但機器還是收不到訊息 | 填成 `message_id`（通常是 1、2 這種小數字）；或 `.env` 裡有兩行 `TELEGRAM_CHAT_ID` | 要填 `"chat":{"id":` 後面那串（通常是 9～10 位數）；`.env` 只留一行 `TELEGRAM_CHAT_ID` |
| 找不到自己建的機器人 | 忘了機器人的帳號名稱 | BotFather 建立成功的訊息裡有 `t.me/<名稱>` 連結，點它 |

## worker 與登入（A4）

| 現象 | 為什麼 | 怎麼修 |
|---|---|---|
| Telegram 收到「需要登入」 | 登入大約 4 小時過期一次，這是正常的 | 對機器人傳 `/refresh`，照連結完成生物辨識，再回 Telegram 點「我已完成登入」 |
| `/refresh` 之後沒反應 | 上一次登入流程還在進行 | 等它回「登入進行中」結束；或把 worker 視窗關掉重開（`python3 worker_main.py`）再傳一次 |
| worker 視窗自己停了 | 網路斷線或例外 | 重新執行 `python3 worker_main.py`；想要掛掉自動重開，改用 `bash worker_main.sh`（30 秒後自動重啟）。停掉不會弄丟東西：待送的在 `pending/`、做完的在 `complete/` |
| 關掉終端機 worker 就停了 | 程式跟著視窗一起結束 | 用 `tmux`：`tmux new -s worker` → 啟動 worker → `Ctrl+B` 再按 `D` 離開；`tmux attach -t worker` 回來看 |

## GA（A5）

| 現象 | 為什麼 | 怎麼修 |
|---|---|---|
| GA 視窗停在等待、沒有新訊息 | 它在等 worker 把這一代模擬做完，這是正常的 | 看 `DB/AlphaDB/pending/` 的檔案數有沒有在減少；沒有就檢查 worker 是否開著、是否需要 `/refresh` |
| 跑很久 | `kid_num × generation_num` 太大，或 `arc_layer` 開著 | 下次把數字調小、`arc_layer` 設 false；這次可以讓它跑完 |
| `pending/` 一直不動 | worker 沒開，或登入過期 | 回 A4 |
| 出現 `this research process already exists` | `--research_name` 用過了 | 輸入 Y 保留並接著上次進度跑，N 刪掉重來；或換一個新名稱 |

## 看結果（A6）

| 現象 | 為什麼 | 怎麼修 |
|---|---|---|
| GA 跑完了但 `analysis/` 沒有東西 | GA 中途被打斷（關掉 terminal、OOM、登入過期太久），最後的自動分析沒跑到 | 先 `export PYTHONPATH="$PWD:$PWD/src${PYTHONPATH:+:$PYTHONPATH}"`，再 `python3 analyze_experiment.py --research_name <名稱>`；沒跑完的代數就用同名稱再起一次 GA，選 Y 接著跑 |
| `ModuleNotFoundError: No module named 'experiment_analysis'` | 沒有設 PYTHONPATH，程式找不到 `src/` | 同一個 terminal 先跑上面那行 `export`，再執行 |
| 圖表打不開、中文變方塊 | 圖是英文標籤的 PNG，用任何看圖程式開；在遠端 VM 上要先把 `analysis/` 下載到自己電腦 | VS Code 左側檔案列表直接點 PNG 就能預覽 |
| `experiment_summary.json` 裡 `initial_fitness_mean` 是 null | 這一代沒有任何有效結果（全部模擬失敗或還沒回來） | 看 `DB/AlphaDB/error/` 有沒有檔案；有就打開看錯誤訊息貼給羅盤 |

## 同步（R1-1）

| 現象 | 為什麼 | 怎麼修 |
|---|---|---|
| `run_data_sync.py` 一跑就停、說 session 無效 | 同步要用登入過的 session | 到 Telegram 傳 `/refresh` 重新登入，再跑一次 |
| 跑到一半斷線、terminal 關掉 | 同步沒有斷點續傳 | 重跑整個；用 tmux 開著跑比較保險 |
| 跑完 `DB/ResearchDB/data/latest/` 是空的 | 中途失敗，最後的複製沒做到 | 看 `DB/ResearchDB/data/<今天日期>/` 有沒有東西；有就重跑一次讓它複製，沒有就重跑整個 |
| 同步時 GA 和 worker 都變很慢 | 同步跟 worker 共用同一個登入、搶平台連線 | 下次等 GA 跑完（pending 0）再同步 |
| `dataset_snapshot.py` 說找不到同步資料 | 它找 `data/<日期>/` 或 `data/latest/` 底下有 `data_fields_raw/` 的站 | 先確認同步真的完成；路徑不對就貼 `ls DB/ResearchDB/data/` 給羅盤 |
