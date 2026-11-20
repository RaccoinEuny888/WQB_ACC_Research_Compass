# 實作教條：expression 寫法的審查清單

> 用途：審判官審式（stage=expr）時逐條比對；占卜家寫 expression 前先自查。
> 每條：樣式／為何可疑／可接受的條件／怎麼改。命中就引「教條 #N」。
> 原則：**expression 的每一層 operator 都要能用一句白話說出「這一層在算什麼、對誰比、看多長」**；說不出來的那一層就是嫌疑。
> 來源標記：`[L]` 論壇文章或平台文件、`[R]` 使用者裁定、`[O]` 本機觀察。

| # | 樣式 | 為何可疑 | 可接受的條件 | 怎麼改 |
|---|---|---|---|---|
| 1 | `trade_when(cond, alpha, exit)` 當開關 | LLM 很愛用；沒有明確、嚴格的觸發理由時通常沒訊號，只是在挑樣本、製造事件稀疏 `[R]` | 觸發條件本身有經濟意義（例：公告後 N 天）、頻率合理、卡上第 4 關寫了為什麼要在這個時點進出 | 拿掉開關，先驗證主訊號本身；要用就把觸發條件寫進卡 |
| 2 | 四則拼接多個訊號，例 `subtract(max(p_base, p_t3, p_t10), min(min(p_base, p_t3), p_t10))` | 拼出來的量沒有單位、沒有對應的經濟量，等於在造一個沒人能解釋的指標；容易過擬合 `[R]` | 有明確經濟意義的比值或差值，例：分析師目標價 ÷ cap（消除幣別與規模：台幣數值大但規模小）、淨利 ÷ 總資產 | 只留一個能講出白話的量；需要比較就用 benchmark 的差（見教條 #8） |
| 3 | 同一欄位多視窗堆疊（`x_3d, x_10d, x_60d` 一起用）無選窗理由 | 在搜參數空間，不是在表達假說 `[L] 橫看成嶺側成峰` | 卡上寫了為何是這些視窗（揭露頻率、持有期） | 選一個對應持有期的視窗；其他交給 template 的基因位 |
| 4 | 魔術數字、過深巢狀 `ts_*`（三層以上） | 每一層都稀釋語意；常數說不出口 `[L] Template Design 的小提醒` | 每個常數有一行理由，或已開成基因位。**第二層 ts 若描述的是第一層 signal 的 dynamics（persistence／acceleration／reversal）而且卡上寫明，是合理的巢狀** `[L] Template Design 的小提醒` | 拆層：清洗 → 訊號 → 平滑 → 組內，每層一句話 |
| 4b | ts 類 operator 的 lookback 用了序列（例 `ts_delay(x, ts_arg_min(x, d))`） | 平台只接受常數：`lookback must be constant or string` `[L] Missing Neutralization Operators Solution` | 不接受（`syntax_check.py` 直接 ERROR） | 用 `operator_recipes.md` §4 的 `ts_max_diff` 配方 |
| 5 | group op 與 ts op 順序與假說相反 | 先 ts 再 group ≠ 先 group 再 ts；順序承載意義 `[L] Template Design 的小提醒` | 順序對得上白話反解釋 | 依假說改順序：比「同業內的相對變化」→ 先 ts_delta 再 group_rank；比「相對位置的變化」→ 反之 |
| 6 | VECTOR 欄位未經 `vec_*` | 語法可能過，但語意錯（等於拿整個向量的預設聚合） | 已聚合且聚合方式有理由（avg／sum／max 各代表不同假說） | 明寫 `vec_avg` / `vec_sum` / `vec_max` 並在卡上說為什麼 |
| 7 | `divide(x, y)` 分母未處理零／負值／量綱 | 比值爆掉或方向翻轉（負的分母會把符號反過來） | 分母為正且與分子同量綱；或先 `abs`／`max(y, eps)` | 換成 `regression_neut` 或對分母加保護 |
| 8 | 直接用水準值（level）而沒有 benchmark | 水準值混入規模、產業、歷史慣性；benchmark 的建構是 template 的一部分 `[L] Template Design 的小提醒` | 卡上說明為何水準本身就是訊號（罕見） | 先定 peer（group）或 historical（ts）benchmark，再比較，再看 deviation 的動態 |
| 9 | 隨機湊兩個欄位做 pair | 沒有 pairing rule 與語意相容性 `[L] Template Design 的小提醒` | 兩個欄位量的是同一件事的兩個面向（例：預期 vs 實現） | 先寫 pairing rule 再組 |
| 10 | 用 `rank` 之後再做跨期差分 | rank 是橫斷面相對位置，跨期差分後語意變成「排名變化」，通常不是卡上說的量 | 卡上就是要「排名變化」 | 先 ts 再 rank，或改用 `ts_rank` |
| 11 | universe／region／delay／neutralization 當基因位 | 它們是 hyperparameter，放進 gene_pool 會破壞 GA 的歸納偏置 `[L] 強勢基因、GA Template 設計` | 不接受 | 放回 setting 檔 |
| 12 | 不同 subgroup 的 operator 放同一個基因位 | 槽位語意漂移（例 `ts_mean` 與 `ts_delta` 互換） `[L] Operator Subgroup 分類 v4` | 不接受 | 查 `operator_subgroups.json`，同 subgroup 才互換 |
| 13 | 最後一行是賦值 | 平台報 Unexpected end of input `[O]` | 不接受 | 最後一行改成輸出式 |
| 14 | 缺 naive 對照或反向證偽組 | 沒有對照，結果無法歸因 | 不接受（卡 4.3 要求） | 補兩組，反向組與主構造只差一個變數 |

## 四模組寫法（來源：GA Template 設計、Template Design 的小提醒）

```
資料清洗  Data Cleaning   backfill／winsorize／除以 cap 或 assets／vec_* 聚合   → 回答：原始值哪裡髒？
訊號提取  Signal          level／change／spread／freshness／volatility         → 回答：機制對應的量是什麼？
時序平滑  Smoothing       ts_decay_linear／ts_mean（快 vs 慢）                  → 回答：持有期多長？
組內處理  Group           group_neutralize／group_rank／group_zscore           → 回答：跟誰比？
```

每一層一句白話；寫不出那一句的層刪掉。目標是「更少但更合理」的 expression，不是更多層。

## 審判官的判決對應

- 命中 #4b、#11、#12、#13、#14 → 處決（機械規則，不聽解釋）。
- 命中 #1～#10 → 懺悔後再審，除非「可接受的條件」在卡上有寫（有寫 → 讚美女神，並在判決書註明）。
