> 註：本範例以「四柱」寫成。對照本機四關：核心論點→第 1 關、交易對手→第 2 關、為何持續→第 3 關、結構優勢→第 4 關 4.3／4.4（量測設計）。

# 壞範例：教學用虛構 prompt（逐句標出問題）

> **虛構教學範例**：刻意集中常見錯誤，供 agent 學習辨識。不是任何真實提交的 prompt。

## 一、Prompt 本文

```
You are a world-class stock picker. [A]

Find the best stocks with strong momentum, good sentiment and solid fundamentals, and
avoid the bad ones. [B]

Universe:
<ISIN_01>|XNYS
<ISIN_02>|XNAS
... (80 lines) [C]

Use your knowledge of these companies' recent earnings and analyst views. [D]
If a stock has no clear signal, you may skip it. [E]
Think carefully about whether the market will react positively or negatively to the
latest news for each company, and decide the direction. [F]
Give each selected stock a score between -1 and 1. [G]

Return the results in JSON. [H]
```

## 二、問題逐條對照

| 標記 | 問題 | 違反的規則／命中的樣式 | 改法 |
|---|---|---|---|
| [A] | 泛稱 persona，沒有專長、沒有任務邊界 | 官方 DO：Assign a Role and Task | 貼合假說的具體角色（見好範例的 forensic filing analyst） |
| [B] | 模糊指令，沒有量化判準，也沒有經濟機制 | 官方 DON'T：Avoid Vague Requests | 寫出四柱、把每柱轉成有判準的步驟 |
| [C] | 裸 ISIN，模型得先花搜尋額度辨識身分 | 失敗樣式 #1 | `TICKER = ISIN\|MIC` 對照 |
| [D] | 要模型用記憶，沒要求 web search | 官方 DON'T：Do Not Rely on Model Memory；DO：Specify Web Search | 強制搜尋＋指定權威來源＋禁用記憶數字 |
| [E] | 允許省略 | 失敗樣式 #2 | 全名單給分，無訊號給固定小分 |
| [F] | 方向交給模型「自己綜合新聞判斷」 | 失敗樣式 #4 | 方向錨定在單一權威、格式固定的數據 |
| [G] | 值域過大、沒要求差異化、沒規定小數位 | `../spec/FORMAT_SPEC.md` 第三節 | ±0.010~±0.100、3 位小數、強制差異化 |
| [H] | 沒有格式鎖定尾註，模型會加 ```json 圍欄和說明文字 | 官方 Format Locking Hint | 結尾一字不差加上官方尾註 |
| （缺） | 沒有 Bull／Bear gate | 官方 DO：Bull vs. Bear Gate | 每檔先論多空兩面，並給明確的降級條件 |
| （缺） | 沒寫輸出 key 必須來自清單 | `../spec/FORMAT_SPEC.md` 第三節第 1 條 | 明示「keys taken only from the universe above」 |

## 三、會出現什麼結果（推測，H）

- 輸出夾帶說明文字或 markdown 圍欄，JSON parse 失敗
- 只給十幾檔分數，跨輪名單大幅漂移
- 分數集中在少數幾個整數值（如 0.5、-0.5），差異化不過
- 跨輪方向大量翻轉，且看不出模型有沒有真的查資料
