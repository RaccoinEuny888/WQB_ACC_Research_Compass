# Template 怎麼設計（給 R3-1；新手版）

> 來源：三篇論壇文章（`doc/agent_challenge/論壇文章訓練資料/md/`）：
> ① `[研究方法論🔍] Alpha Template 簡介`（YW42946）② `[2026 Q3 Challenge] Template Design 的小提醒`（ZH78994）③ `Template Capacity: Single dataset, Multiple datafield data diversity 量化數據實證`（TW77745）；
> 再加 `agents/common/knowledge/template_doctrine.md`（占卜家／審判官共用的原則）與 `GA Template 設計`（四模組骨架）。本檔是羅盤濃縮；引用時用文章名。

## 1. template 是什麼（文章 ①）

一條 expression 把會變的部分挖成空格，就是 template。文章 ① 的例子：

```
group_rank(ts_rank(eps, 252), industry)      ← 一條 expression：EPS 比自己過去高、又比同業高 → 做多
<group_compare_op>(<ts_compare_op>(<company_fundamentals>, <days>), <group>)   ← template
```

每個 `<空格>` 是一個**基因位**，GA 從你給的選項裡挑：欄位可以換成 DPS、CPS、BPS、sales；`ts_rank` 可以換 `ts_zscore`、`ts_delta`；`group_rank` 可以換 `group_zscore`、`group_neutralize`；天數與 group 也是選項。所有選項相乘就是 **space 的大小**（A5 的 Template 框每行都標了）。

## 2. 先有假說，再有 template（文章 ②）

順序是固定的：**經濟假說 → 資料語意 → template 結構 → operator 空間 → 參數空間 → 模擬 → 驗證。** 倒過來（先堆 operator 再找故事）就是在 space 裡撿噪音。template 的價值不是「一次生很多 alpha」，是「限制出一個合理的、解釋得了的搜尋空間」——**更少但更合理的 alpha**。

好的 template 三個特徵（文章 ②）：有清楚的經濟解釋；每一層 operator 都有明確功能；能自然延伸成一個合理的研究空間。

## 3. 一層回答一個問題（四模組骨架）

```
data   = <清洗>( <欄位> )          # 原始值哪裡髒？缺值回補、壓極端值、除以規模
signal = <訊號>( data, <d> )        # 機制對應的量是什麼？變化、差距、比值、新鮮度
smooth = <平滑>( signal, <d2> )     # 持有期多長？快平滑保留近期、慢平滑穩定但稀釋
out    = <組內>( smooth, <group> )  # 跟誰比？同業／同市場內的相對值，避免變成國家或產業的賭注
```

A5 的 `default_template.json` 就是這個骨架：取欄位 → 跟自己過去比 → 同群比較 → 平滑 → 決定多空。

**operator 的順序承載意義**（文章 ②）：`group_rank(ts_delta(x, d), industry)` 是「同業內比較近期變化」；`ts_delta(group_rank(x, industry), d)` 是「同業排名的變化」。這是兩個不同的假說，不要當成同一個 template 的兩個選項。

## 4. Benchmark 是 template 的一部分（文章 ②）

進階的單欄位 template：先建 benchmark（同業＝group、歷史＝ts），再比較（deviation），再看 deviation 的動態（持續、加速、反轉）。同一個欄位換一個 benchmark，就是另一個假說，所以 benchmark 要分開寫成一個基因位。第二層 ts operator 不是「多加一層複雜度」，它描述的是訊號本身的 persistence／acceleration／reversal。

## 5. Pair template 要先有 pairing rule（文章 ②）

兩個欄位組合（spread、ratio、relative movement、term structure），先寫它們為什麼語意相容（預期 vs 實際、分子 vs 分母、訊號 vs 它的 benchmark），再決定比較方法、順序、horizon。語法能跑不代表有經濟意義；沒有 rule 的 pair 不開基因位。

## 6. 單一 dataset、多欄位（文章 ③ 的實證）

一個 template 綁一個 dataset、在欄位基因位放同 dataset 的**同語意群**多個欄位，比跨 dataset 混欄位穩：文章 ③ 用 anl69 的 EBIT／EBITDA 家族（同一語意群 14 個欄位）跑 GA，92 支 alpha、相關性 0.7 以下 24 支；單一欄位的實驗 combine 後 4～5 支就飽和，多欄位要到 22 支才飽和——多欄位帶來的多樣性是真的，但「同一 template 裡很像的欄位」帶來的額外增益有限。

這就是 R1-2 分群的用途：**欄位基因位放一個語意群的代表與變體**，不要放整個 dataset。留言裡 YW42946 的提醒：template 的 operator 數量可以推到 5～10 個，太簡單的 template 會讓 alpha 過度依賴「資料的簡單運算」。

## 7. 基因位的紀律（`template_doctrine.md`）

- 同一個基因位的選項要**同一群**（功能相近且運算結構相同：輸入數量、有沒有 lookback 一致），分群在 R2 你自己做的 operator 倉庫。結構相同還不夠，選項要是「同一個想法的不同算法」，不是「不同的想法」（例：`vector_neut` 剝離 vs `vector_proj` 保留，不能同槽）。
- 每個基因位要有一行理由；說不出理由的選項刪掉。
- universe／region／delay／neutralization／decay／truncation 是 setting，**不進 gene_pool**（放進去 GA 會收斂到 setting 的差異而不是訊號的差異）。
- 組合數大不是優點；超過 10,000 要有剪枝說明。

## 8. 寫之前答四個問題（`提升 Alpha 穩健性的四個問題`）

1. 訊號在大小型股是否同號？2. 換相鄰視窗是否平滑變化？3. 換同一群的 operator 是否仍同號？4. 去掉任一層訊號消失了嗎——消失的那層就是訊號真正來源，要能用假說解釋。

## 9. 第一個自己的 template 怎麼寫（R3-1 實作的做法）

1. 從 R1-2 的 profile 挑**一群**（例如 `profitability_trend`），欄位基因位放這群的 3 個代表（再加幾個變體也可以）。
2. 用四模組骨架，每層放 2～3 個同一群的 operator、天數放 3～5 個值（`template_draft.py` 會幫你產一份草稿）。
3. 在 JSON 旁邊（或檔名）寫下這個 template 的一句話假說：「<這群欄位> 的 <什麼變化>，相對 <同業/市場> 高的股票會 <漲/跌>，因為 <機制>」。
4. `syntax_check.py -t` 通過 → 放 `DB/ResearchDB/template/` → 用 A5 的指令起 GA（新的 `--research_name`，GA 設定先小）。
5. 跑完用 A6 的 `sample_alphalist_parser.py` 看；回頭用第 8 節的四個問題檢查。
