# 缺 operator 的替代配方

> 來源：`[L] Missing Neutralization Operators Solution`（YW82626 原文；YW42946、WW28434、WP54924 回覆）。
> 用法：`/express` 寫式子前先 `syntax_check`，operator 不存在時查這裡；用了配方要在 idea 的 design_notes 與卡上註明「替代配方」。
> 觀念：缺 operator 不是壞事，被迫把運算拆開後，可以調整的部分反而變多。

## 1. `vector_neut(x, f)`（把 x 對 f 正交化）

```
ab = group_sum(x * f, market);
bb = group_sum(f * f, market);
x - (ab / bb) * f
```
- `market` 就是全 universe；原文用 `country` 近似，ASI 實測差異不大。改用 `industry` 等 group 就變成 `group_vector_neut`。
- `bb` 可能接近 0，分母加保護（例 `max(bb, 1e-8)`）。

## 2. `regression_neut(y, x)`（y 對 x 做橫斷面迴歸取殘差）

```
g = market;
mean_x = group_mean(x, 1, g);
mean_y = group_mean(y, 1, g);
dx = x - mean_x;
dy = y - mean_y;
s_xy = group_sum(dx * dy, g);
s_xx = group_sum(dx * dx, g);
w = s_xy / s_xx;
b = mean_y - w * mean_x;
y - (x * w + b)
```
- USA 實測與原 operator 一致。
- `s_xx` 接近 0 時數值不穩，加 epsilon 或 `max(s_xx, 1e-8)`（WW28434）。
- `group_mean(x, weight, group)` 的**第 2 個參數是 weight**，等權就填 `1`。

## 3. `group_sum(x, g)` 缺

```
group_mean(x, 1, g) * group_count(x, g)
```
- 另一個近似：`x / group_normalize(x, g)`（省 operator 數，但符號是絕對值，必要時乘 `sign(group_mean(x, 1, g))`）。
- 先問自己為什麼需要 group_sum：它把同組壓成同一個數，多半只是拿來跟 x 比，不如直接在 `group_mean` 的 weight 上下功夫。

## 4. `ts_min(x, d)`／`ts_max(x, d)` 缺

```
mn = x - ts_max_diff(-x, d);     # ts_min
mx = x - ts_max_diff(x, d);      # ts_max
minmax_mid = x - (mn + mx) / 2;
```
- 有 `ts_max` 沒 `ts_min` 時：`-ts_max(-x, d)`。
- **不要**用 `ts_delay(x, ts_arg_min(x, d))` 這類寫法：所有 ts 類 operator 的 lookback `d` 必須是常數（數字，或指向數字的變數），不能是另一個序列，平台會報 `lookback must be constant or string`。`syntax_check.py` 會擋。

## 5. 其他

| 缺 | 替代 |
|---|---|
| `ts_target_tvr_hump` | `hump(x, hump=…)` |
| `tanh` | 其他值域調整（`sigmoid`、`rank`、`zscore` 後 `winsorize`）；見教條「數學硬扭不是多樣性」 |
| `group_std_dev(x, g)` | `power(group_mean(power(x - group_mean(x, 1, g), 2), 1, g), 0.5)` |

## 6. operator 數量

替代配方會增加 operator 數。GA 評分時可以把 unique operator 數當負分（YW42946）；`templatize.py` 會印出 operator 數，超過你的上限就回頭精簡。
