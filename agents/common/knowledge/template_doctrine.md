# Template 設計原則（整理自論壇文章，附出處）

> 用途：占卜家 `/templatize` 的設計依據；審判官 stage=template 的判準。
> 出處縮寫見 `sources.md`。所有原則都是 `[L]`。

## 1. 設計順序

**經濟假說 → 資料語意 → template 結構 → operator 空間 → 參數空間。** 倒過來（先堆 operator 再找故事）就是在搜尋空間裡撿噪音。`[L] Template Design 的小提醒`

## 2. Operator 的順序承載意義

`group_rank(ts_delta(x, d), industry)` 是「同業內比較近期變化」；`ts_delta(group_rank(x, industry), d)` 是「同業排名的變化」。兩者假說不同，不能當成同一個 template 的兩個選項。`[L] Template Design 的小提醒`

## 3. Benchmark 的建構是 template 的一部分

先定 benchmark（peer＝group、historical＝ts），再比較（deviation），再看 deviation 的動態（變化、持續、收斂）。template 要把這三段分開寫，每段一個基因位。`[L] Template Design 的小提醒`

## 4. Pair 要先有 pairing rule

兩個欄位要組合，先寫它們為什麼語意相容（預期 vs 實現、分子 vs 分母、訊號 vs 其 benchmark）。沒有 rule 的 pair 不開基因位。`[L] Template Design 的小提醒`

## 5. Less is more

組合數大不是優點。每個基因位要有一行理由；說不出理由的選項刪掉；一個 template 的訊號層通常只需要一個欄位、一個比較、一個平滑、一個組內處理。「橫看成嶺側成峰」的實證：同一個 dataset，剪過的 template yield rate 高於大而全的 template。`[L] 橫看成嶺側成峰`
operator 數量也算：替代配方（`operator_recipes.md`）會讓 operator 變多，`templatize.py` 會印出 operator 數；GA 評分時可以把 unique operator 數當負分。`[L] Missing Neutralization Operators Solution`

## 6. 單一 dataset、多欄位的容量

一個 template 綁一個 dataset、在欄位基因位上放同 dataset 的多個欄位，比跨 dataset 混欄位穩定；欄位要先依語意分組，同組才放進同一個基因位。`[L] Template Capacity`

## 7. 同 subgroup 才能互換

基因位內的 operator 必須語意功能相近**且**運算結構相同（輸入數量與角色一致、是否含 lookback 一致）。分類表見 `operator_subgroups.json`（v4+）。`[L] Operator Subgroup 分類`
結構相同還不夠，**同一槽位的選項要能代表同一個經濟想法**：「橫看成嶺側成峰」實證 `vector_neut／regression_neut`（取垂直分量＝剝離）與 `vector_proj／regression_proj`（取平行分量＝保留）意義差距顯著，放在同一槽位只是佔用模擬資源、最後也沒被選到；因此 v4+ 已把它們拆成 2.6e（neut）與 2.6f（proj）`[R]`。模板化後請再看一次每個槽位：選項之間是「同一個想法的不同算法」，還是「不同的想法」？後者刪掉。`[L] 橫看成嶺側成峰`

## 8. Hyperparameter 不進 gene_pool

universe、region、delay、neutralization、decay、truncation 屬於 setting，不是基因。放進 gene_pool 會讓「強勢基因」吃掉多樣性，GA 收斂到 setting 的差異而不是訊號的差異。`[L] 強勢基因；GA Template 設計`

## 9. 缺 operator 用替代配方

帳號沒有某些 neutralization／group operator 時，用 `group_sum`、`group_mean`、`group_count` 等組出等價構造；完整配方（vector_neut、regression_neut、group_sum、ts_min/max、hump）見 `operator_recipes.md`。替代配方要在 notes 裡註明。`[L] Missing Neutralization Operators Solution`

## 10. 四模組骨架

```
data   = <清洗>( <欄位> )            # backfill / winsorize / vec_* / 除以規模
signal = <訊號>( data, <d> )          # delta / spread / ratio / freshness
smooth = <平滑>( signal, <d2> )       # decay / mean（快 vs 慢）
out    = <組內>( smooth, <group> )    # neutralize / rank / zscore
```

每一層對應一個問題：原始值哪裡髒？機制對應的量是什麼？持有期多長？跟誰比？`[L] GA Template 設計`

## 11. 穩健性四問（寫 template 前答一次）

1. 訊號在不同 universe 子集（大小型股）是否同號？
2. 換一個相鄰視窗結果是否平滑變化（而不是跳動）？
3. 換一個同 subgroup 的 operator 是否仍同號？
4. 去掉任何一層之後訊號消失了嗎？消失的那層就是訊號的真正來源，要能用假說解釋。`[L] 提升 Alpha 穩健性的四個問題`

## 12. Combined／finance level 提醒

多個訊號相加前，先確認每個訊號單獨有經濟意義；finance level 的組合（同一經濟主題的多個量）比跨主題硬加穩定。本機只處理單一 alpha，這條用來提醒不要在一條 expression 裡偷偷做 combo（見實作教條 #2）。`[L] Combined Alpha performance TIPS: Finance level`

## 審判官 stage=template 的機械規則

- 每基因位內全部 operator 同 subgroup（#7）。
- gene_pool 不含 universe／region／delay／neutralization（#8）。
- notes 裡每個基因位有一行理由（#5）。
- 抽樣展開至少 3 條通過 syntax_check（含欄位存在性）。
- 組合數印出；超過 10,000 要有剪枝說明。
