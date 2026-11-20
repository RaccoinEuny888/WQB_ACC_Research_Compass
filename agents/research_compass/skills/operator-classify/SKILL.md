---
name: operator-classify
description: 研究羅盤 R2-1：先教使用者抓自己帳號的 operator 清單，再建議分群方式（清洗、訊號、平滑、組內、其他）讓使用者決定，最後羅盤照自己的理解把每個 operator 分進去、每個寫一句用途，建成地圖頁的「operator 倉庫」。純本機；清單是使用者的，分群是使用者定的。用法 /operator-classify
argument-hint: [空 | redo]
---

# /operator-classify

使用者輸入：`$ARGUMENTS`。全部從 open machine 根目錄執行。這是研究羅盤 R2-1 用的 skill，由主對話執行。

## 鐵則

- **清單是使用者的**：只用 `agents/workspace/cache/operators.json`（`brain_meta.py operators` 抓的）或 `DB/ResearchDB/data/latest/operators.json`；沒有就教他抓，不用羅盤內建的清單。
- **分群方式是使用者決定的**：羅盤只建議，不替他定。
- **分類是羅盤自己的理解**：每個 operator 一句話說它在這層做什麼；看不懂的寫「看不懂：…」放「其他」，不硬塞。不建議用的寫原因，標 `avoid`。
- 分類是先驗，不是判決：之後寫 template 發現某個 operator 放錯層，跟羅盤說一聲改分群表就好。
- 不打平台（抓清單那一步由使用者自己執行 `brain_meta.py`；它說 session 過期就停下來請他開 worker 登入，不繞過）。

## 第 1 步：抓使用者自己的 operator 清單

1. `ls agents/workspace/cache/operators.json DB/ResearchDB/data/latest/operators.json 2>/dev/null`。有 → 跳第 2 步。
2. 沒有 → 跟他說為什麼要抓自己的（每個帳號能用的 operator 不同，分類要照他真的有的來做），請他執行：
   ```bash
   source .venv/bin/activate
   python agents/common/brain_meta.py operators
   ```
   要先登入過 worker（A4）。它印「session 已過期」→ 請他 Telegram `/refresh` 重新登入再跑；不要替他想別的辦法。抓到後會印 `[saved] agents/workspace/cache/operators.json（N 個 operator）`。

## 第 2 步：建議分群方式，讓他決定

先講一句為什麼：operator 是 expression 的動詞，一百多個照字母背不起來；按「在 template 的哪一層做什麼事」分群，寫 template 時每一層只從同一群挑，就知道哪個該放哪。

建議的五群（`operator_index.py` 的 `DEFAULT_SCHEME`）：

| 群 | 回答的問題 |
|---|---|
| 清洗 | 原始值哪裡髒？缺值回補、壓極端值、去單位 |
| 訊號 | 機制對應的量是什麼？變化、差距、比值、波動、相關 |
| 平滑 | 持有多久？時序平滑與換手控制 |
| 組內 | 跟誰比？同業／同市場內的相對值 |
| 其他 | 不進四層 pipeline 的工具（加減乘除、邏輯），以及羅盤建議盡量不要用的 operator |

**有 AskUserQuestion 就用**（一題：「照這五群」／「我要改群名或加減群」）；沒有就用文字問、等他回。他改了就照他的：
```bash
python agents/research_compass/cli/operator_index.py init                       # 照建議的五群
python agents/research_compass/cli/operator_index.py init --groups "清洗,訊號,平滑,組內,風險,其他"   # 他自己定的
```
這會寫 `agents/workspace/operator_groups.json`：`scheme`（他定的群）、`to_classify`（他清單上每個 operator 的名稱、平台分類、定義、說明）、`assignments`（空的，或上次分過的）。

## 第 3 步：羅盤分類

1. 讀 `agents/workspace/operator_groups.json` 的 `to_classify`。
2. 每個 operator 照**定義與說明**判斷它在哪一層做什麼，寫進 `assignments`：
   ```json
   "ts_backfill": {"group": "clean", "note": "缺值用過去 d 天最近的值補上；第一層先補再算，免得後面全是 NaN"},
   "trade_when": {"group": "other", "note": "條件成立才換部位；新手常拿它拼接，審判官的常見退回原因", "avoid": true},
   "bucket": {"group": "other", "note": "看不懂：把值切成區間的用法還不確定"}
   ```
   - `group` 一定是 `scheme` 裡的 `id`；`note` 一句話、新手看得懂；不建議用的加 `"avoid": true` 並在 note 寫原因（例如 `agents/common/knowledge/expression_doctrine.md` 列的常見退回原因，有裝占卜家才有這個檔；沒有就照自己的理解寫）。
   - 同一個 operator 兩層都像（例如 `ts_rank` 既像訊號也像平滑）：放你認為**主要**的那層，note 裡提另一層。
   - 一次分完；超過 150 個就分兩批，但都在主對話做（不派 subagent，分類要能跟他解釋）。
3. 用 Write 工具把 `assignments` 寫回 `agents/workspace/operator_groups.json`（保留 `scheme`、`to_classify`、`source`），`decided_by` 寫 `"user"`。
4. 建索引並檢查：
   ```bash
   python agents/research_compass/cli/operator_index.py
   ```
   它會列每群、⚠ 名字打錯或群 id 不對、還沒分類的；有就修到乾淨。`--todo` 列還沒分類的；`--find <op>` 查一個。
5. `python agents/research_compass/cli/guide_page.py`，請他看地圖頁「operator 倉庫」分頁：每群一個下拉、每個 operator 的定義、平台說明、羅盤的一句話；⚠ 的是建議少用。

## 回報

「你的帳號有 N 個 operator，照你定的 M 群分好了：清洗 a 個、訊號 b 個、…、其他 e 個（其中 k 個建議少用）。還沒分的 j 個（列名字）。分類好的 operator 在地圖頁「operator 倉庫」分頁。寫 template 時，同一個 space 的選項從同一群挑。」
然後帶回主線（R2 是支線；主線還沒做完的那一步）。`$ARGUMENTS` 是 `redo` → 從第 2 步重做（`init` 會沿用舊分類裡群 id 仍存在的）。
