# SPC 官方 webinar 要點（摘錄）

> 來源：WQ 官方 SPC webinar 投影片（2026-07 場次），原文英文，以下為摘錄與白話說明。
> 規則全文見同資料夾 `SPC_official_guideline.md`；平台表單欄位見 `submission_form_fields.md`。

## 1. 不要依每日 PnL 頻繁換 prompt

> "Submit each prompt thoughtfully, don't replace prompts frequently based on daily PnL stats."

白話：每日排名與每日 PnL 噪音很大，不能拿單日表現當依據去改權重或換 prompt。

## 2. 跨 prompt 權重分配：Weight ∝ Edge × Repeatability × Diversification

| 因子 | 官方定義（白話） | 實務操作 |
|---|---|---|
| Edge | prompt 背後的經濟邏輯站不站得住 | 經濟論點越紮實，權重越高 |
| Repeatability | 能否跨景氣循環穩定發揮 | regime 無關的給穩定權重；regime 依賴型依當前景氣調升調降，可歸零 |
| Diversification | 題材是否獨特 | 冷門、非共識切入給更高權重 |

官方範例的成熟期權重落在約 0.45~0.70 之間（四個 prompt），是「已觀察一段時間後」的量級參考，
不是新提交的起始值。新提交建議從低權重觀察期開始（見 `../spec/FORMAT_SPEC.md` 表單欄位）。
