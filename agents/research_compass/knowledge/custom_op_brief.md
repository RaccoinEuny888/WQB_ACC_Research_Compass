# Custom operator 精簡版（給 R2-2）

> 來源：`doc/agent_challenge/WQB_Custom Operator_transcript.md`（WQB Taiwan Team Simon 的 Custom Operator 講座逐字稿，60 分鐘）。本檔是羅盤濃縮，給新手看；引用時說「Custom Operator 講座」。
> 機器端的實作：`src/custom_op.py`（展開 `$名稱(...)`）＋ `src/custom_op_definition.py`（你自己的 operator 定義，`MAPPING`）；worker 送模擬前會自動展開（`src/worker.py`），所以 template 裡可以直接寫 `$名稱(...)`。

## 一句話

**Custom operator ＝ 把你常用的幾個 operator 組合，取一個名字。** template 裡寫 `$TS_DELTA_RANK(data, 10)`，送出前機器自動展開成 `ts_delta(rank(data), 10)`。

## 為什麼需要（講座 Section 1）

簡單 template `<tvr_ctrl>(<gp_op>(<ts_op>(<data>, <days>), <gp>))` 有兩個做不到的事：
1. **複雜度受限**：想讓 `<ts_op>` 是「先 rank 再 ts_rank」這種兩層組合，單一 space 放不進去。
2. **參數不齊**：同一個 space 想放 `ts_decay_linear`（要天數）和 `ts_delta_limit`（要成交量比例），參數形狀不同，字串替換做不到，最後只能放棄其中一種。

Custom operator 解決這兩件事，還有第三個好處：**縮短「思想距離」**——你腦中多了一個 `$ts_median_diff` 這種工具，下次想 idea 時就會直接想到它。

## 在這台機器上怎麼寫（三步）

1. 打開 `src/custom_op_definition.py`，加一個 function：吃字串、回傳展開後的 expression 字串。
   ```python
   def ts_delta_rank(data, days):
       return f"ts_delta(rank({data}), {days})"
   ```
2. 把它登記進 `MAPPING`：`"ts_delta_rank": ts_delta_rank,`
3. template 或 expression 裡用 `$ts_delta_rank(<field>, <days>)`。機器已附兩個範例：`$ts_median_diff(data, days)`（data 減過去 d 天中位數）、`$vec_min_max_norm(data)`。

規則：
- 一定要是 **function 形式**、前面加 `$`，參數用逗號分開；可以巢狀（`$a($b(x, 5), 10)`，由內往外展開）。
- 展開後的式子裡**用 `add(a, b)` 不要用 `a + b`**（字串替換對符號運算不友善；SuperAlpha 會把 expression 塞進網址，符號更容易出錯）。
- 平台不允許**沒用到的變數**；多行 custom operator 展開後若留下沒用到的變數會被拒絕（講座 Section 2：這是 Genius tie-breaker 判定的需要）。機器會在送出前清掉冗餘行，但自己寫的時候還是先避免。
- 多行寫法（講座 `group_rank_pct_diff`）：中間變數用 hash 取名（`c_` + hash），避免兩個 custom operator 撞名、也方便去掉重複行。
- 可以有自己的 keyword 參數（例如 `mode=1/2` 切換兩種組法），不必跟平台 operator 的參數一樣。

## 講座現場的三個範例（隨手想的，示範「怎麼發想」）

| 名稱 | 組合 | 想法 |
|---|---|---|
| `$SMART_JUMP_DECAY(x, d, sensitivity)` | `jump_decay(ts_backfill(x, d), d, sensitivity=…)` | 先回補缺值再做 jump decay，兩邊共用同一個天數很合理 |
| `$SAFE_GROUP_SCALE(data, n, group)` | `group_scale(winsorize(data, std=n), group)` | `group_scale` 是 (x−min)/(max−min)，一個極端值就把全組壓扁；先 winsorize 再 scale |
| `$CUSTOM_MAXTRADE(alpha)` | `ts_delta_limit(scale(alpha), volume*close…, limit_volume=0.1)` | 用成交金額限制每日換手，相當於自己做 max trade；先 `scale` 到 book size 才有意義 |

講者的話：這三個只是隨便想的，「你可以想到 30 個、300 個」。看平台 operator 文件，找你**常常把兩個以上 operator 疊在一起**的用法，那就是你的 custom operator。

## 不用 custom operator 也能做的「字串技巧」（講座 String manipulation）

template 本身就是字串替換，有三招：
1. **Options**：先算 `alpha`，再寫 `alpha_decay_1 = ts_decay_linear(alpha, <days>); alpha_decay_2 = hump(alpha, hump=<h>); alpha_decay_3 = ts_target_tvr_hump(alpha, …);` 最後一行 `alpha_decay_<decay_option>`——同一個 space 放參數不同的 operator。
2. **Pre-defined public parameters**：開頭先 `data = <data>; group = <group>; days = <days>;`，後面各層共用 `days`（`ts_rank` 和 `ts_zscore` 的天數意義相近，共用可以讓 space 更合理）。
3. **Multiple variables substitution**：一個基因位一次替換兩個變數，例如 `<ab_pair>` 的選項是 `'a = anl14_low_revenue_fp4; b = anl14_high_revenue_fp4;'`，用來做有 pairing rule 的 pair template。

## 講者的三個提醒（Suggestions）

1. **不要過度複雜**：`alpha_1/alpha_2/alpha_3` 各是一大串不同的 template 再用 `alpha_<option>` 選，不如拆成三個 GA——塞在一起你分不出哪個真的有效。
2. **做 train／validation 切分**：custom operator 越多，overfit 風險越高。
3. **一定要分析結果**：講者的做法是對每個基因位統計「in-sample 過門檻的支數、validation Sharpe ÷ training Sharpe、平均 turnover」——例如 `group` 選項裡某個奇怪的 statistical grouping 數量少又 validation 爛，就直接拿掉；`ts_decay_linear` 明顯降 turnover。平台上有些奇怪的 grouping 只會讓你 overfit，不要亂用。

## 跟 A6／R4 的關係

第 3 點「分析每個基因位」就是 A6 教的分析圖表的進階版，也是 R4 調 scorer 時「看整個 batch 有沒有在進步」的依據。
