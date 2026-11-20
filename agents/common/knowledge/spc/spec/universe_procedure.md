# Universe 清單生成程序（Pre-compiled ISIN|MIC）

> 目的：把「查識別碼」從正式 prompt 裡拿掉，讓 LLM 把算力全部用在分析。
> 這是官方建議的 Chain of Prompts 技巧（見 `../rules/SPC_official_guideline.md` Advanced Tip）。

## 生成程序（在乾淨的 chat 視窗執行）

**分批生成，每批 ≤ 50 檔**：一次生成數百檔會漏失和幻覺，分批是硬規則。
例如美股市值前 500 大，按排名切 10 批（1-50、51-100、…、451-500）。

前置 prompt 範本（每批替換排名區間）：

```
Search the web for the current list of US-listed companies ranked #<N1>–#<N2> by market
capitalization (NYSE and NASDAQ common stocks only; exclude ETFs, ADRs of foreign issuers,
and preferred shares). For each company, output exactly one line in the format:
TICKER, COMPANY NAME, ISIN|MIC
Use the primary listing exchange MIC (XNYS for NYSE, XNAS for NASDAQ).
Verify each ISIN via a reliable source; do not rely on memory.
Output ONLY the list, no prose.
```

## 驗證規則（每批生成後逐項檢查，全過才入庫）

1. **ISIN 格式**：12 碼＝2 碼國別＋9 位英數＋1 位檢查碼（正則 `^[A-Z]{2}[A-Z0-9]{9}[0-9]$`）。
   不限 `US` 開頭：海外註冊但直接在 NYSE／NASDAQ 掛牌的普通股（非 ADR）用當地國別碼
2. **ISIN 檢查碼**：用 Luhn 演算法實際驗算最後一碼（格式對但檢查碼錯＝無效 ISIN）
3. **MIC 白名單**：美股主板只接受 `XNYS`、`XNAS`，出現其他值＝生成錯誤，重查該檔
4. **數量核對**：每批實際行數＝要求數量
5. **跨批去重**：ISIN 不得重複（雙重上市、改名會造成重複，保留主上市）
6. **反查**：抽查只能攔到一部分錯誤（「格式正確但對應到另一家公司」這類錯，抽查常漏掉）。
   主清單建議**全量反查**一次：在另一個乾淨視窗問「這個 ISIN 是哪家公司」，比對公司名
7. 有錯的檔單獨重查，不整批重生成

## 檔案格式

- **主清單**（JSON）：每筆 `{rank, ticker, name, isin, mic}`，按市值排序；純資料
- **驗證記錄**（md）：生成過程、批次驗證表、糾錯紀錄；供稽核，不是正式清單
- **主題子清單**（prompt 直接貼用）：建議格式 `TICKER = ISIN|MIC`，一行一檔。
  不要只貼裸 `ISIN|MIC`，原因見 `../lessons/failure_patterns.md` #1

## 子清單切割判準

切法**跟著假說走**，不是機械均分：

| 切面 | 例子 | 適用的假說類型 |
|---|---|---|
| Sector | 科技、金融各一份 | 產業內比較型 |
| 市值帶 | 排名後段的中型股 | 關注度、資訊擴散類（超大型股沒有低關注溢價） |
| 事件窗 | 未來 2~4 週公布財報的公司 | 財報事件類（每季重生成） |
| 波動帶 | 隱含波動率前段 | 波動、選擇權類 |

規則：
- 一個 prompt 配一份子清單；**整個組合合計 ≥ 500 檔獨立標的**（官方要求）
- 單份子清單的大小：官方建議 ~50 檔
- 同一檔出現在 2 個以上 prompt 時，在登記簿的覆蓋統計中註記

## 更新政策

- 主清單每季重生成（成分會變）；生成日寫進檔名，超過 90 天視為過期
- 事件窗子清單在每季財報季前重生成
- 舊清單不刪，改加 `_expired` 後綴保留（已提交的 prompt 引用的清單要能對照）
