# 三個設定檔逐行說明（初稿，「怎麼調」欄待資深顧問修訂）

> 位置：`DB/ResearchDB/ga_config/`、`setting/`、`template/`。跑 GA 時用 `--ga_config_file`、`--setting_file`、`--template_file` 指定檔名。
> 「控制什麼」來自程式碼；「怎麼調」是初稿，不確定處標 [?]。

## 1. GA 設定檔（`ga_config/default_ga_config.json`）：GA 怎麼跑

| 欄位 | 控制什麼 | 怎麼調 |
|---|---|---|
| `parent_num` | 每一代留下幾支表現最好的當父母 | 新手 5。越大保留越多樣、收斂越慢 |
| `kid_num` | 每一代產生幾支 alpha（＝每一代送幾支模擬） | 新手 30。越大每代看得越廣、越花時間與模擬額度 |
| `generation_num` | 最多跑幾代 | 新手 3。總模擬數大約是 `kid_num × generation_num` |
| `mutation_rate` | 產生下一代時，每個選項隨機換掉的機率 | 預設 0.05。太高會變成隨機亂試，太低容易卡住 [?] |
| `early_stop_patience` | 連續幾代平均成績沒進步就提早停 | 預設 3 |
| `bcorr_threshold` | 同一代裡兩支 alpha 太像（相關性高於這個值）時只留較好的 | 預設 0.7。越低越強調多樣性 |
| `pnl_wait_timeout_seconds` | 等每日損益資料最多等幾秒 | 一般不用動 |
| `pnl_poll_seconds` | 多久檢查一次損益資料好了沒 | 一般不用動 |
| `arc_layer` | 跑完後，要不要拿代表性的 alpha 多跑一層 ARC（Region Agnostic Alpha） | 第一次建議 `false`（比較快）。想跑 ARC 時改 `true` |
| `arc_setting_file` | ARC 那一層用哪個模擬設定檔 | `arc_layer` 為 `true` 時才有用；預設 `default_arc_setting.json`（region 為 `ALL`） |

**想加跑 ARC Alpha**：把 `arc_layer` 設為 `true`，並確認 `arc_setting_file` 指向 `setting/` 裡 region 為 `ALL` 的設定檔。GA 本身照常跑，結束後會多一個階段。

## 2. 模擬設定檔（`setting/default_setting.json`）：每支 alpha 用什麼條件模擬

和平台網頁 Simulate 旁邊的設定是同一組。

| 欄位 | 控制什麼 | 怎麼調 |
|---|---|---|
| `region` | 哪個市場（USA、EUR、ASI、GLB…；`ALL` 代表 ARC） | 依你要研究的市場；要先同步過該市場的資料 |
| `universe` | 股票池（如 TOP3000） | 要是該 region 有的 universe；越大通常 alpha 越多 [?] |
| `delay` | 用前一天（1）還是當天（0）的資料 | 一般 1 |
| `neutralization` | 對什麼做中性化（MARKET、SECTOR、INDUSTRY、SUBINDUSTRY、STATISTICAL…） | **重點**。GA 支援多基因位：寫成清單（例 `["INDUSTRY", "SUBINDUSTRY"]`）就會一起搜尋 |
| `decay` | 把訊號做幾天的線性平滑 | **重點**。建議設 0，平滑改在 template 裡用 operator 做（例 `ts_decay_linear`），GA 才能一起優化 |
| `truncation` | 單一股票最大權重 | **重點**。universe 越大，建議設越小 |
| `pasteurization` | 是否把不在 universe 的股票設為空值 | 一般 ON |
| `nanHandling` | 空值怎麼處理 | 一般 OFF |
| `unitHandling` | 單位檢查 | 一般 VERIFY |
| `maxTrade` / `maxPosition` | 交易量與部位上限 | 依 region 的建議 [?] |
| `testPeriod` | 留多長的期間當測試期 | 例 `P1Y` |
| `instrumentType` / `language` | 固定值 | 不用動 |
| `visualization` | 是否產生視覺化結果 | **建議開 true**，並把結果存到本地。機器目前不支援存下來；使用者想要就記到待辦（`onboard.py todo add "visualization 開啟並把結果存到本地"`），這一版只記錄 |

欄位的值如果寫成清單（例如 `"decay": [0, 5, 10]`），GA 會把它也當成要搜尋的選項。新手先用固定值。

## 3. Template（`template/default_template.json`）：決定機器要試哪些 expression

| 欄位 | 控制什麼 | 怎麼調 |
|---|---|---|
| `template` | 一條 expression；要開 space 就把欄位替換成 `<名稱>` | 先讀懂每一行在算什麼，再決定要把哪些欄位開成 space |
| `gene_pool` | 每個空格可以填哪些選項 | 選項要能代表同一個想法；說不出理由的選項不要放。所有空格的選項數相乘＝這個 template 能組出幾條 expression |

以預設 template 為例：

```
data = winsorize(ts_backfill(vec_avg(<model_data>), 63), std=4);   ← 取一個欄位，補缺值、壓極端值
compare_days = <compare_days>;                                      ← 要比多久以前
compare_data = <compare_data>;                                      ← 跟自己過去的什麼比（變化量／波動／平均）
diff = <diff_op>(data, compare_data);                               ← 怎麼比（相減／相除／迴歸取殘差）
(<sign>) * <ts_decay_op>(<group_compare_op>(diff, <group_compare_group>), <ts_decay_days>)
                                                                    ← 跟同一群股票比 → 平滑 → 決定方向
```

- 想換資料：改 `<model_data>` 的選項（欄位要在你同步過的資料裡）。
- region、universe、delay 不放在 `gene_pool`，它們屬於模擬設定檔。
