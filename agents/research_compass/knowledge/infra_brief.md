# 機器是怎麼運作的

> 只在使用者想了解或想複習時才講。內容整理自 WQB 台灣團隊的 infra 設計說明。對使用者講的時候不提「課堂／課程」。

## 三句話版（複習用）

1. 人負責想 alpha idea、決定研究方向、寫 template；機器負責優化參數：產生 expression、送模擬、存結果、留下好的再產生下一批。
2. 產生 expression 的程式（例如 GA）和送模擬的程式（worker）是分開的：前者把 expression 寫進 `pending`，後者一支支送去 WQB、把結果寫進 `complete`。
3. 所以 worker 斷線不會影響研究，重開就接著做；你也可以同時跑好幾個研究，共用一個 worker。

## 精簡版（給想弄懂的人，約 2 分鐘）

**為什麼要自動化**
在 WQB 網頁上手動做研究：想 alpha idea → 寫 expression → 按 Simulate → 看結果 → 改。好處是理解深，壞處是花時間、不系統、容易卡在局部。自動化之後，人只做最有價值的事：想 alpha idea、決定研究方向、寫 template；後面的參數優化、模擬、存檔、篩選交給機器。alpha 數量多又夠分散，合起來的表現才會好，也才有得挑。

**最直覺的做法與它的問題**
寫一支程式：登入 → 產生一批 expression → 一支支模擬 → 存結果 → 依成績產生下一批。問題有三個：
- 網路一斷整支程式就死掉，跑到一半的進度很難接回來。
- 想同時跑多支模擬要開多個執行緒，容易同時敲太多次平台而被擋（429），程式也容易出錯。
- 一個研究佔滿了同時模擬的名額，第二個研究只能排隊。

**這台機器的設計**

```
GA（研究程式） ──寫入──▶ pending ──讀取──▶ worker ──送模擬──▶ 平台
          ▲                                        │
          └────────讀取──── complete ◀──寫入結果───┘
```

- **研究程式（例如 GA）**（像研究員）：只管產生 expression 和分析結果，只跟兩個資料夾打交道，不直接連 WQB。
- **worker**（像工廠裡的作業員）：只做一件事——從 `pending` 拿 expression 去模擬，結果寫到 `complete`。它不管 expression 是誰產生的。
- 每條 expression 連同設定算出一個唯一的檔名，所以多個研究同時跑也不會拿錯別人的結果。
- worker 用單一執行緒輪流問「你跑完了沒」：有一支跑完就存起來，從 `pending` 補一條新的進來，一直維持名額全滿。一次模擬要半分鐘到幾分鐘，輪流問的時間可以忽略。
- 結果直接存平台回傳的 JSON，一支 alpha 一個檔，不用 CSV 或 notebook（量大時讀寫很慢）。

**資料的四層**

研究流程（一個 alpha idea 從資料到提交的完整過程）→ 一次研究（其中一個階段，例如一次 GA）→ 一代（一批 expression）→ 一條 expression 的請求與結果。

**登入**
程式登入後會把登入狀態記住，不用每次重登。顧問帳號需要生物辨識：機器把掃臉連結傳到你的 Telegram，你在手機上完成，家裡的程式就能繼續跑。

**安全**
帳密不可寫在程式碼裡，也不可上傳到公開的地方；平台發現外洩會停權。

## 對應到這台機器的資料夾

| 說法 | 這台機器 |
|---|---|
| 待送清單（pending） | `DB/AlphaDB/pending/` |
| 已完成（complete） | `DB/AlphaDB/complete/`（PnL 在 `DB/AlphaDB/pnl/`） |
| worker | `worker_main.py`（`python3 worker_main.py`；想掛掉自動重開用 `bash worker_main.sh`） |
| 研究程式（GA） | `sample_code/sample_ga.py`，進度與每一代存在 `DB/ResearchDB/research_process/<研究名稱>/` |
| 一代 | `research_process/<研究名稱>/alphalist_1`、`alphalist_2`…（一代一個） |
| 搜尋範圍的設定 | `DB/ResearchDB/template/`（式子與可替換的選項）、`setting/`（模擬設定）、`ga_config/`（GA 怎麼跑） |
