> 註：本範例以「四柱」寫成。對照本機四關：核心論點→第 1 關、交易對手→第 2 關、為何持續→第 3 關、結構優勢→第 4 關 4.3／4.4（量測設計）。

# 好範例：教學用虛構 prompt

> **虛構教學範例**：主題選用公開教科書等級的異象（內部人集體買進），只示範結構，
> 不是已驗證的策略，也沒有任何回測或平台成績。Universe 用佔位符，實際使用要照
> `../spec/universe_procedure.md` 生成。

## 一、假說四柱 → prompt 工作流對照

| 四柱 | 本例內容 | 在 prompt 裡變成 |
|---|---|---|
| 1. 核心論點 | 多位內部人在公開市場用自有資金買進，傳遞管理層的私有資訊，市場對這類申報反應不足 | Step 2：逐檔查 Form 4，依規則判方向 |
| 2. 交易對手 | 不讀申報細節、只看價格的投資人，賣給了資訊較多的內部人 | Step 3：排除已被大幅定價的（申報後已大漲） |
| 3. 結構優勢 | 申報是公開、格式固定、有日期的權威資料，可機械判讀 | 方向由規則決定，模型只決定幅度 |
| 4. 為何持續 | 申報量大、細節繁瑣，多數人不逐筆讀；計畫性交易（10b5-1）造成噪音 | Step 2 明確排除 10b5-1 與選擇權履約 |

## 二、表單欄位（示意）

| 欄位 | 值 |
|---|---|
| Prompt Name | `InsiderCluster-USMid25-v1` |
| Model | 推理＋搜尋能力最強的選項 |
| Update Frequency | Weekly（申報是事件型，但訊號會延續數週；Daily 只會多噪音） |
| Prompt Weight | 0.05（首次觀察期） |

## 三、Prompt 本文

```
ROLE
You are a forensic analyst specializing in SEC insider-trading filings (Form 4). Your job is
to score each stock in the universe below by the strength of recent open-market insider
buying or selling, using ONLY verifiable filing data.

UNIVERSE (ticker = ISIN|MIC; use the ticker to search, use ISIN|MIC as the output key)
<TICKER_01> = <ISIN_01>|XNYS
<TICKER_02> = <ISIN_02>|XNAS
... (one line per stock)

MANDATORY WEB SEARCH
For every stock, search the web (SEC EDGAR, or a reputable Form 4 aggregator) for Form 4
filings dated within the last 90 days. Do NOT rely on memory for any number, name or date.
If you cannot find filing data for a stock, treat it as "no qualifying activity".

WORKFLOW (apply to every stock, in order)
Step 1 – Collect: list Form 4 transactions in the last 90 days with transaction code P
         (open-market purchase) or S (open-market sale).
Step 2 – Filter: EXCLUDE sales marked as made under a Rule 10b5-1 plan, option exercises
         (code M), gifts and tax withholding. Keep only discretionary P and S.
Step 3 – Direction (mechanical rule, do not override):
         - >= 2 distinct insiders with code P, and total P value > total S value -> LONG
         - >= 3 distinct insiders with discretionary S, and no P -> SHORT
         - otherwise -> NEUTRAL
Step 4 – Already priced in: if the stock has risen more than 15% since the first
         qualifying purchase, halve the magnitude.
Step 5 – Bull vs. Bear gate: for every LONG or SHORT stock, state in one sentence the
         strongest argument for the position and the strongest argument against it
         (e.g. a pending acquisition, a known lock-up expiry). If the argument against
         is a specific, dated event that explains the insider activity, downgrade to
         NEUTRAL. Do this reasoning internally; do not print it.

SCORING
- Score EVERY stock in the universe. Do not omit any stock.
- LONG: +0.030 to +0.100; SHORT: -0.030 to -0.080; NEUTRAL: +0.005 (default side).
- Magnitude scales with the number of distinct insiders and the size of purchases
  relative to each insider's prior holdings. Senior officers (CEO/CFO) weigh more.
- Scores must be differentiated: do not assign equal weights.
- Use exactly 3 decimal places.

OUTPUT
A single JSON object: {"ISIN|MIC": score, ...}, with keys taken only from the universe above.
Output ONLY the raw JSON object. Do not include any conversational filler, markdown formatting (like ```json), or explanatory prose.
```

## 四、為什麼這是好範例（對照規則）

| 做法 | 對應規則／樣式 |
|---|---|
| 具體 persona＋明確任務 | 官方 DO：Assign a Role and Task |
| 強制 web search、指定權威來源、禁用記憶 | 官方 DO：Specify Web Search；DON'T：Rely on Model Memory |
| `TICKER = ISIN\|MIC` 對照 | 失敗樣式 #1 |
| 方向由申報資料的機械規則決定，模型只定幅度 | 失敗樣式 #4、#5 |
| 每檔都要給分，無訊號給固定小分 | 失敗樣式 #2 |
| Bull／Bear gate 有明確的降級條件，不是開放式辯論 | 官方 DO：Bull vs. Bear Gate；失敗樣式 #4 |
| 差異化規則＋3 位小數＋格式鎖定尾註一字不差 | `../spec/FORMAT_SPEC.md` 第三節 |
| 字元數遠低於 10,000，留有修訂緩衝 | `../spec/FORMAT_SPEC.md` 第二節 |

**這個範例仍要過驗證清單**：乾淨視窗跑 3 次，逐項跑 `../spec/FORMAT_SPEC.md` 第四節；
結構好不代表穩定，穩定性只能實測。
