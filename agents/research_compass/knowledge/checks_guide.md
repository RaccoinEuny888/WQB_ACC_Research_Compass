# 平台 checks 白話對照（給 A6「哪些可以交」用）

> WQB 網頁上每支 alpha 的 Submission 區會列一排 check，**全部 PASS 才能提交**。
> 門檻（limit）與實際值（value）都記在本機的模擬結果裡（`DB/AlphaDB/complete/<alpha>`），機器附的 `sample_code/sample_alphalist_parser.py` 會整理成 CSV，不用背數字。
> 來源：check 名稱與語意來自平台模擬結果本身；一句話說明是羅盤整理，標 `[?]` 的請以 WQB 網頁上 Learn 區的 submission criteria 說明為準。

| check | 一句話 | 新手怎麼處理 |
|---|---|---|
| `LOW_SHARPE` | Sharpe（報酬／波動）低於門檻：訊號不夠穩 | 先看是不是整個 space 都低；是的話換 template 或 dataset，不是就讓 GA 多跑幾代 |
| `LOW_FITNESS` | Fitness（綜合 Sharpe、報酬、turnover 的分數）低於門檻 | 通常跟 turnover 太高或報酬太低有關，先看另外兩項 |
| `HIGH_TURNOVER` | 換手率太高：每天換太多部位，交易成本吃掉報酬 | 在 template 加平滑（`ts_decay_linear`、`ts_mean`）或用較長的回看天數 |
| `LOW_TURNOVER` | 換手率太低：幾乎不動 | 少見；通常是 expression 幾乎是常數 |
| `HIGH_DRAWDOWN` | 最大回撤太深 | 看 PnL 圖是不是某一段崩掉；常見於 universe 小或訊號集中 |
| `CONCENTRATED_WEIGHT` | 權重太集中在少數股票 | 加 `rank`／`group_rank`、`winsorize`，或 setting 的 `truncation` 調小 |
| `LOW_SUB_UNIVERSE_SHARPE` | 在較小的子股票池（例如 TOP3000 裡的 TOP1000）表現不夠 | 訊號只在小型股有效；試 `group_neutralize` 或換 universe |
| `LOW_2Y_SHARPE` | 最近兩年的 Sharpe 不夠：訊號在衰退 | 近期失效的 idea，別硬交 |
| `LOW_ROBUST_UNIVERSE_SHARPE` | 在更嚴格的「穩健 universe」裡 Sharpe 不夠 `[?]` | 同上，看是不是靠少數股票撐 |
| `SELF_CORRELATION` | 跟你自己已提交的 alpha 太像 | 換 dataset 或換構造，不要只改參數 |
| `PROD_CORRELATION` | 跟平台生產線上的 alpha 太像 | 同上；alphaCount 高的 dataset 常遇到 |
| `MATCHES_COMPETITION` | 是否符合某個比賽的規則（不影響一般提交） | 不用管，除非你在參賽 |
| `MATCHES_THEMES` | 是否符合主題 Power Pool 的規則 `[?]` | 不影響一般提交 |
| `UNITS` | 單位檢查：expression 把不同單位的東西加在一起 | 用 `rank`／`zscore` 先把資料變成無單位 |
| `DATA_DIVERSITY` | 資料多樣性：用到的 dataset／欄位是否夠分散 `[?]` | 一般提交不卡；Power Pool 才會看 |
| `IS_LADDER_SHARPE` | 分年看的 Sharpe 是否平穩（階梯檢查）`[?]` | 某幾年特別差就要注意 |
| `REGULAR_SUBMISSION` | 總結：能不能走一般提交 | 其他項都過它就過 |
| `POWER_POOL_SUBMISSION` | 總結：能不能進 Power Pool | 門檻比一般提交高 |

## 兩種提交的標準（使用者實測整理，2026-11；門檻以本機結果裡的 limit 為準）

**Regular alpha（正規提交）**：平台在模擬結果就會判的 7 項（`sample_alphalist_parser.py` 的 `regular_checks_pass` 看的就是這 7 項），**全部 literal PASS**，WARNING 也算不過。

| 檢查 | 門檻（使用者帳號實際值） | 備註 |
|---|---|---|
| `LOW_SHARPE` | Sharpe ≥ 1.58 | USA／EUR／GLB／ASI／TWN 都是 1.58（公開文件常寫 1.25，以平台回傳的 limit 為準）；DEU／GBR 少數紀錄 2.69 |
| `LOW_FITNESS` | fitness ≥ 1.0 | fitness = Sharpe × √(年報酬 ÷ max(turnover, 0.125))，turnover 低於 12.5% 後再降也沒用 |
| `HIGH_TURNOVER`／`LOW_TURNOVER` | 1% ≤ turnover ≤ 70% | |
| `LOW_2Y_SHARPE`（IS_LADDER） | 近 2 年 Sharpe ≥ 1.58 | 與 Sharpe 門檻同值 |
| `LOW_SUB_UNIVERSE_SHARPE` | sub-universe Sharpe ≥ 0.52 × 本身 Sharpe | 門檻跟著 Sharpe 走，看比值不看絕對值 |
| `CONCENTRATED_WEIGHT` | 單一持股權重 ≤ 10% | 常因不補值導致，先看 dataclean |
| region 子區域 | GLB：AMER／EMEA／APAC 各 ≥ 1.0；ASI：JPN ≥ 1.0 | 不在 7 項裡，GLB 要自己看結果裡的 checks |

**Power Pool alpha（PPA）**：7 項**無 FAIL 即可，WARNING 允許**（`src/alphalist_parser.py` 的 `get_power_pool_checks` 也是這個定義）。使用者實測（O1）：Sharpe 1.19／fitness 0.55／subU 0.61 的 alpha 符合 PPA 資格（LOW_SHARPE、LOW_FITNESS 只標 WARNING），Sharpe 0.94 的標 FAIL → PPA 的 Sharpe 線在 0.94～1.19 之間，與非官方說法「≥ 1.0」一致；fitness 下限未測出。另有 PPA 專屬閘門，模擬時 PENDING、到網頁 check 才判：
- `PROD_CORRELATION` ≤ 0.70（實案 0.74 被擋）
- `POWER_POOL_CORRELATION`：與其他 Power Pool alpha 的相關性，上限不確定（非官方文件寫 < 0.5）`[?]`
- `MATCHES_THEMES`：必須命中當期 Power Pool 主題（例如 "D1 Power Pool Oct`26"），不命中標 WARNING 擋提交
- 非官方另稱 PPA 要是「簡化 alpha」：operator ≤ 8、datafield ≤ 3 `[?]`

所以 `sample_alphalist_parser.py` 的 `power_pool_checks_pass` 是**候選**：7 項無 FAIL、專屬閘門沒 FAIL；最終要到 WQB 網頁上 check。
- 有些 check 在本機結果裡是 `PENDING`（平台還沒算完，例如相關性類），parser 不會把它當 FAIL；到 WQB 網頁上打開那支 alpha 才看得到最終結果。
- 第一次跑（3 代、90 支）很可能一支都沒全過，這是正常的；這一步的目的是看懂 check，不是交出 alpha。
