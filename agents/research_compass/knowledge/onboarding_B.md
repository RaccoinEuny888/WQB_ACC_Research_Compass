# 新手引導 B 段：開始你自己的研究

> 對象：A 段走完的人——機器會用、結果看得懂，但「不知道研究要怎麼開始」。
> B 不是直線，是**樞紐**：四個問題四條路，像心智圖——根「開始研究」→ 四條路 → 每條路的延伸節點（R1-1、R1-2…）。
> 四條路**可以自由切換**，不限制走完一條才能選下一條；但羅盤每次回答完都要把使用者**帶回主線**（R1 選 dataset → R3 設計 template → R4 調 scorer；R2 認識 operator 是支線）還沒完成的那一步。
> A 段不消失：地圖頁保留「準備機器」分頁，回頭查指令與設定檔說明。進度由 `onboard.py status` 的 `b` 欄判斷。
> 寫法同 A：每一步先說**為什麼要做**，再說怎麼做、做完會看到；「→」後面是給羅盤的指示，「｜頁面：」後面是地圖頁給使用者看的。

## 回覆格式

```
你在這裡：開始研究 ／ R1 選 dataset ／ 第 N 步：<步驟名>
一兩句說為什麼要做（不要寫「為什麼：」這種標籤）
一個動作，指令放程式碼區塊
做完你會看到什麼
延伸問題：↳ …（可有可無；答案不必是下一步）
地圖頁：<連結>
```

## 樞紐（進 B 第一次、或每走完一條路回來時）

A6 剛完成時先講 A6「羅盤補充」裡的結尾引言（恭喜你…現在我們來學習如何開始研究吧！），然後用 AskUserQuestion 列四條路讓他選（第一次把「選 dataset」放第一、標「建議」）：

| 他的問題 | 路 | 一句話 |
|---|---|---|
| 不知道從哪個 dataset 開始 | R1 選 dataset | 同步看推薦 → 看懂一個 dataset |
| 不知道怎麼用 operator | R2 認識 operator | operator 倉庫＋custom operator |
| 不知道怎麼設計 template、沒有研究靈感 | R3 設計 template | 四個處理過程寫成 template；沒靈感就加裝占卜家 |
| GA 產不出能交的 alpha | R4 調 scorer | 看懂現在的 scorer、scorer 調整方向 |

選了就 `onboard.py asked "<路>"`，走那條路。使用者中途想換路就換（不用走完）；每次回答完，用一句過場帶回主線還沒做完的那一步（例如「這題講完了，我們回到 R1-2 分析你選的 dataset」）。走完一條就說「這條路走完了」，回樞紐再選。

---

## R1 選 dataset

### R1-1 同步 dataset、看推薦

- 為什麼：把 dataset 同步到本機，你不用登入就能快速查看自己有哪些 dataset 可以用。建議每個月同步一次。
- 怎麼做：GA 沒在跑的時候，另開一個 terminal 輸入：
  ```bash
  source .venv/bin/activate
  uv sync
  python run_data_sync.py
  ```
- 同步完成後跟我說，我會根據 alphaCount 變化、pyramid 加成、新 dataset，幫你畫出熱力圖，並推薦優先研究的 dataset。
- 完成判斷：`DB/ResearchDB/data/latest/` 有同步資料，且 `agents/workspace/index/dataset_priority.json` 的快照日期等於最新同步。
- 延伸問題：
  - ↳ 為什麼先選 alphaCount 變化大的 dataset？ → 照頁面答案講，講完帶回主線 ｜頁面：alphaCount 變化大，可能表示這個 dataset 最近越來越熱門。雖然可能比較擁擠，但也可能代表這個 dataset 比較容易做出訊號。
- 羅盤補充：只在對話裡用，不上地圖頁。
  - 同步要先登入過（A4）。它說 session 無效，就請使用者到 Telegram 傳 `/refresh` 重新登入再跑。同步會跟 worker 搶平台連線，先看 `status` 的 `pending` 是不是 0。每個站要跑幾十分鐘，預設每個 region 只抓第一組 universe／delay，第一次這樣就夠。
  - 使用者說同步完了：跑 `python3 agents/research_compass/cli/dataset_snapshot.py`（只讀本機、不打平台），再跑 `guide_page.py`，請他看地圖頁「dataset 圖鑑」分頁，並唸出頁面下方的推薦清單。
  - 加權分數＝pyramid 加成×50＋alphaCount 變化%×30＋新 dataset×20（0～100），權重可改 `agents/workspace/priority_weights.json`。推薦清單取全區分數最高的 dataset，同分比 pyramid。
  - 第一次只有一份快照：變化% 和「新 dataset」算不出來，排序只剩 pyramid。要照實說「下個月第二次同步就有了」。
  - 使用者問 pyramid 加成：平台依 alpha 用的 region／dataset 類別給的權重倍數，越高代表平台現在越想要這類 alpha；數字看快照裡的 `pyramidMultiplier`，羅盤不背數字。
  - 使用者問 alphaCount 高好不好：高代表有人做得出來、但也擁擠；低代表沒人碰、也可能資料不好用。所以看的是跟上次比的變化，不是絕對值。
  - 最常卡住的地方在 `troubleshooting.md`「同步」：session 無效、跑到一半斷線、`latest/` 是空的。

### R1-2 Dataset 語意分群

- 怎麼做：接下來你只要跟我說「幫我分析 USA TOP3000 model109」（換成你想看的站和 dataset），我會根據欄位名稱和說明，把欄位按經濟意義分群，每群挑出代表欄位。
- 怎麼看：分析完，「dataset 圖鑑」下方會出現這個 dataset 的卡。最上面是一句話介紹；灰框是型態和命名；下方表格是語意分群，列出每群的意思、代表欄位和欄位數。
- 完成判斷：`DB/ResearchDB/data/subdataset/` 有至少一份 profile。
- 延伸問題：
  - ↳ 我選出 dataset 了，接下來要怎麼研究？ → 帶到主線 R3 設計 template ｜頁面：下一步到「設計 template」：把你的策略拆成四個處理過程寫成 template；沒靈感就加裝占卜家幫你。
- 羅盤補充：只在對話裡用，不上地圖頁。
  - 用 `dataset-profile` skill 做（`/dataset-profile <dataset> --key <站>`），純本機；欄位超過 100 個就派 subagent 分群、主對話覆核；存到 `DB/ResearchDB/data/subdataset/<dataset>_<站>_profile.json`。
  - 為什麼要分群（使用者問才講）：很多欄位只是同一個訊號的變體，例如回看期、統計量、離散版。每群挑最多 3 個代表：主代表是 coverage 最高、擁擠代表是 alphaCount 最高、藍海代表是 alphaCount 最低且 coverage ≥ 0.6。template 先用代表，變體留作後備。分群只決定先試哪些欄位，代表沒訊號不代表整群沒用。
  - 做完把這個 dataset 放上專案管理：`onboard.py card add "<dataset>" --lane 研究中`。
  - 使用者想看欄位分布：請他到 WQB 網頁的 BrainLab 輸入欄位名，看缺值比例和極端值；羅盤不替他看。

走完 R1：卡在「研究中」、圖鑑有一張 dataset 卡。回樞紐；主線下一條是 R3 設計 template。

---

## R2 認識 operator（支線）

### R2-1 operator 倉庫

- 建議把 operator 也同步到本機，並依功能整理分類。寫 template 時就能照功能決定 operator space，避免把所有 operator 混在一起，隨機組出沒有經濟意義的 alpha。
- 接下來你可以在 terminal 用下面的指令自己同步 operator 清單（要先登入 worker），或跟我說「幫我整理 operator」，我會先跟你確認分組方式，再把 operator 分類到地圖頁的「operator 倉庫」。
  ```bash
  source .venv/bin/activate
  python agents/common/brain_meta.py operators
  ```
- 完成判斷：`agents/workspace/operator_groups.json` 存在，且 `agents/workspace/index/operator_index.json` 是用它建的。
- 羅盤補充：只在對話裡用，不上地圖頁。
  - 全部照 `skills/operator-classify/SKILL.md` 做（`/operator-classify`）：抓清單 → 建議五群（清洗、訊號、平滑、組內、其他）讓他決定 → 你照定義分類、每個寫一句用途，不建議用的標 ⚠ 寫原因。
  - 清單沒抓到就停在第一步；`brain_meta.py` 說 session 過期，請他 Telegram `/refresh` 再跑，不繞過。不用羅盤內建的 `operators.json`、不用 `operator_subgroups.json`。
  - 使用者問「怎麼組成 template」→ 帶到 R4：一層一個問題，每層從同一群挑 2～3 個 operator。
  - 指令：`operator_index.py init [--groups "…"]` 寫骨架；`operator_index.py` 建索引並檢查；`--todo` 列還沒分的；`--find <op>` 查一個。

### R2-2 custom operator

- 簡單的 template 做不到兩件事：一個 space 放不進「先 rank 再 ts_rank」這種兩層組合；同一個 space 也放不進參數形狀不同的 operator（`ts_decay_linear` 要天數、`ts_delta_limit` 要成交量比例）。Custom operator 就是把你常放在一起用的 operator 打包成自定義的 operator，template 裡寫 `$名稱(...)`，機器送模擬前會自動展開。
- 具體怎麼做呢？
  1. 打開 `src/custom_op_definition.py`，加一個 function，回傳展開後的字串：`def ts_delta_rank(data, days): return f"ts_delta(rank({data}), {days})"`
  2. 登記進 `MAPPING`：`"ts_delta_rank": ts_delta_rank,`
  3. template 裡就可以使用 `$ts_delta_rank(<field>, <days>)`。

  機器已附兩個範例可以參考：`$ts_median_diff`、`$vec_min_max_norm`。
  規則：function 形式、前面加 `$`、可巢狀；展開後用 `add(a, b)` 不要用 `a + b`；不要留沒用到的變數（平台會拒絕）。
- 小提醒：不要過度複雜（三個完全不同的 template 用 `alpha_<option>` 塞在一個 GA，不如拆成三個 GA）；做 train／validation 切分；一定要分析每個基因位的結果（哪個 group 的 validation 爛、哪個 decay 真的降 turnover）。
- 完成判斷：看過就算完成，羅盤講完就 `onboard.py mark R2-2`。
- 羅盤補充：只在對話裡用，不上地圖頁。
  - 細節與講座範例在 `knowledge/custom_op_brief.md`，使用者問才講。
  - 使用者說想不到要組什麼：講座的做法是看 operator 文件，找自己平常兩個以上 operator 放在一起用的寫法；現場三個例子是 `$SMART_JUMP_DECAY`（backfill＋jump_decay）、`$SAFE_GROUP_SCALE`（winsorize＋group_scale）、`$CUSTOM_MAXTRADE`（scale＋ts_delta_limit）。
  - 他要加就引導他改 `src/custom_op_definition.py` 的 function 與 `MAPPING`（這是機器預留給使用者改的檔，你不代改）。加了之後重跑 `operator_index.py`，「operator 倉庫」分頁底部會列出他的 custom operator，還沒登記進 `MAPPING` 的標 ⚠。

## R3 設計 template（主線）

### R3-1 template 怎麼設計

- 到這裡你已經看得懂欄位、也會挑 operator 了，接下來就可以把你的策略寫成 template，讓機器自動幫你搜出 alpha！
- 設計 GA template 時，建議把一個 alpha 拆成四個處理過程：資料清洗、訊號提取、時序與組內處理、平滑與中性化。
  ```
  data_clean = <clean_op>(<datafield>, <day>);           # 資料清洗
  signal = <group_op>(data_clean, <group>);               # 訊號提取、時序與組內處理
  group_neutralize(<smooth_op>(signal, <day>), <group>)   # 平滑與中性化
  ```
- 現在輪到你來實作囉～
- 完成判斷：`DB/ResearchDB/template/` 有 default 以外的 template，且 `research_process/` 有第二條以上的研究；或使用者說讀完了（`onboard.py mark R3-1`）。
- 你可能會問：
  - ↳ 可是我想不出 idea → 帶到 R3-2 裝占卜家 ｜頁面：沒靈感很正常，推薦你加裝占卜家，幫你產出研究靈感：從文獻萃取假說，再幫你寫 template。
- 羅盤補充：只在對話裡用，不上地圖頁。
  - 使用者想深入：照 `template_guide.md` 講四件事——template 與基因位、順序（經濟假說 → 資料語意 → 結構 → operator 空間 → 參數空間）、單一 dataset 同語意群多欄位、基因位紀律（同一個 space 的選項從 R2-1 的同一群挑、每個選項一行理由、setting 不進 gene_pool）。
  - 要草稿就用 R1-2 的 profile 產：`python3 agents/research_compass/cli/template_draft.py --dataset <ds>` 先列群，`--group <群名>` 產到 `DB/ResearchDB/template/<ds>_<群名>_draft.json`、印 space 大小、跑語法檢查。請他把 `notes.hypothesis` 改成自己的一句話假說，刪掉說不出理由的選項。
  - 起 GA 用 A5 的指令，換 template 檔與新的 `--research_name`，GA 設定先小。跑完用 A6 的 `sample_alphalist_parser.py` 看，羅盤會把能交的 ID 記到卡上、移到「結案」。
  - 頁面上的 template 是示意，不是可以直接跑的式子：`<clean_op>` 等 space 要放 R2-1 分好的同一群 operator。

### R3-2 加裝占卜家

- 新手最常遇到的卡點是「沒靈感」「不知道要做什麼策略」。占卜家就是解決這件事的另一支 agent：它把你的直覺、一篇文章或一個 dataset 整理成幾個市場命題讓你挑，再幫你找文獻、寫成假說卡，之後還能幫你把假說寫成 expression 和 template。
- 怎麼裝：拿到 `seer_<日期>.zip` 後解壓，把裡面的 `agents/` 合併到你機器的 `agents/`，然後在機器根目錄執行：
  ```bash
  bash agents/install.sh --only seer
  ```
  裝完重開 Claude Code。
- 完成判斷：`.claude/skills/hypothesis/SKILL.md` 存在；使用者說先不裝 → `onboard.py mark R3-2` 和 `mark R3-3`。
- 羅盤補充：只在對話裡用，不上地圖頁。
  - 你不替他執行安裝。`install.sh` 會先列出要新增的檔案再問一次（`.claude/skills/`、`CLAUDE.md` 一行、`src/idea.py`、`DB/ResearchDB/{hypothesis,idea}/`）。`common/` 兩邊是同一份，覆蓋沒關係。
  - 占卜家不需要審判官或羅盤也能用；有裝審判官，它送審前會先問他。

### R3-3 用 /hypothesis 建第一張假說卡

- 第一張卡不求完美，求你走過一次「命題 → 假說 → 四關 → 分數」的過程，知道一個 alpha idea 要回答哪些問題。
- 你可以跟占卜家說：
  ```
  /hypothesis <一句直覺｜文章連結或貼文｜R1 選的 dataset>
  ```
  它會先跟你確認命題方向，再找文獻、寫成假說卡，存在地圖頁的「靈感卡」分頁；專案管理頁「研究中」也會自動出現這張卡。
- 你還可以請占卜家幫你寫 expression、產 template：
  ```
  /express <卡號>
  ```
  不過還是建議根據自己的理解調整內容喔。
- 完成判斷：`DB/ResearchDB/hypothesis/` 有至少一張卡。
- 如果你還不知道怎麼判斷寫得好不好，我特別推薦：
  - ↳ 審判官（論壇介紹連結待補） → 只給連結，不代裝 ｜頁面：替你嚴格把關，檢查假說的經濟意義、expression 有沒有照假說寫，還有模擬結果是不是真的支持你的假說。
- 羅盤補充：只在對話裡用，不上地圖頁。
  - 占卜家是另一支 agent，由它自己帶；你只在他回來時重跑 `status`，確認 `DB/ResearchDB/hypothesis/` 有卡。
  - 卡之後的路：`/express` → 使用者執行 `python -m src.idea --idea <卡號>` 送模擬 → `self_check.py <卡號>`（或 `/judge`）→ `/templatize <卡號>` → 用 A5 的指令起 GA。
  - 使用者問「四關是什麼、分數是什麼」：照 `agents/common/knowledge/four_gates.md` 一關一句；分數是占卜家對「這關寫得具不具體」的自評，不是 alpha 的成績。
  - 沒有直覺也沒文章：把 R1-2 排前面的 dataset 直接丟給 `/hypothesis <dataset>`。

走完 R3：回樞紐；主線下一條是 R4 調 scorer（讓 GA 只留能交的）。

## R4 調 scorer（主線）

### R4-1 看懂現在的 scorer

- GA 每一代留下誰，是 scorer 決定的。現在機器的做法是：

  | 部分 | 規則 |
  |---|---|
  | Sharpe | 取絕對值。低於 1.5 扣分很快，1.5～5 線性加分，超過 5 幾乎不再加分，超過 6 直接 −1000 |
  | Turnover | 低於 0.3 輕微扣分，0.3～0.7 扣得快，超過 0.7 重罰，超過 0.9 直接 −1000 |

- 你可以在 `src/scorer.py` 查看和調整細節。
- 不過現在的機器不看 fitness，WQB 的 7 項 check 也都不進選擇。建議依你的研究調整 scorer 喔。
- 完成判斷：看過就算完成，羅盤講完就 `onboard.py mark R4-1`。
- 羅盤補充：只在對話裡用，不上地圖頁。
  - 機器怎麼用 scorer：`sample_code/sample_ga.py` 第 106～107 行設定主 scorer `CombinedPiecewiseScore` 和附加 scorer。只有主 scorer 決定誰撐過相關性過濾、成為父母；附加的 fitness、Sharpe、turnover 只寫進每一代的分數紀錄。
  - 取絕對值代表負 Sharpe 的 alpha 也會留下，之後 `sample_alphalist_parser.py` 會把方向翻過來。
  - 改法（原作者在 Infra Design 講座 46:39 只說「可以在 `scorer.py` 定義要怎麼 score 你的 alpha」，文件沒有步驟）：在 `src/scorer.py` 繼承 `AlphaScore` 寫新的 class，再到 GA 腳本換掉主 scorer。建議他複製 `sample_ga.py` 成自己的檔再改。你不改機器、也不替他改他的檔。
  - 使用者問「幾支 alpha 合併起來的 Sharpe」：這版沒做，`onboard.py todo add "合併 PnL 的 Sharpe"`，說一句記下來了。

### R4-2 scorer 調整方向

- 搜訊號的時候，門檻太嚴會把「有訊號但還沒修好」的 alpha 全砍掉，所以建議 scorer 的條件設寬鬆一點，例如 |Sharpe| ≥ 1.2、turnover ≤ 0.5。
- 但要 fit 提交門檻的時候，門檻太寬又會搜到一堆交不出去的 alpha。這時候建議用嚴格的 `RegularSubmissionScore`，搜出可以提交的 alpha。
- 完成判斷：看過就算完成，羅盤講完就 `onboard.py mark R4-2`。
- 推薦文章：
  - ↳ [Q2 GLB Challenge] 60 and Above GLB Alpha in One Qurter: Multi-Country Data Processing and Research Pipeline – WorldQuant BRAIN
- 羅盤補充：只在對話裡用，不上地圖頁。
  - 寫好的三個 scorer 在 `agents/research_compass/scorers.py`：`SignalScore`（探索：|Sharpe| ≥ 1.2、turnover ≤ 0.5，`[L]` 2-step GA 文章的建議）、`RegularSubmissionScore`（正規提交：Sharpe ≥ 1.58、fitness ≥ 1.0、turnover ≤ 0.7，再看 7 項 check）、`PowerPoolScore`（Sharpe ≥ 1.0 `[?]`、7 項無 FAIL）。門檻是使用者帳號實測 `[R]`，模擬結果裡有 limit 時用 limit。
  - 使用者要換：複製 `sample_ga.py` 成自己的檔，改兩行：`from agents.research_compass.scorers import SignalScore, RegularSubmissionScore, PowerPoolScore`、`score_scorer = RegularSubmissionScore`。只印這兩行給他，他自己改。
  - 提交階段的 scorer 用原始 Sharpe，負 Sharpe 會被扣分；template 沒有正負號基因位的話，要提醒他第一階段的方向先定好。
  - 兩階段的精神來自論壇文章「2-step GA」`[L]`：第一次 template 只放跟 idea 有關的層、GA 偏探索；第二次加上優化層、GA 偏收斂，跑完用 A6 的 `sample_alphalist_parser.py` 看能交幾支。只拿它講「寬 vs 嚴」，不展開成整套教學。
  - 走完 R4 就是主線走完；回樞紐，之後他每條新研究都照 R1 → R3 → R4 走。四條路全部走完，地圖頁的「新手地圖」分頁會消失，頁面從「專案管理」開始。
