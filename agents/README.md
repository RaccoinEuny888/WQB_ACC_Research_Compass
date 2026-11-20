# agents/ — 三支研究 agent（WQB 2026 Q4 Local Agent Challenge）

給 WorldQuant BRAIN 新手顧問用的三支 Claude Code agent，裝在 open machine 上，只讀自己機器的資料、不呼叫 simulation API。

| Agent | 類別 | 一句話 |
|---|---|---|
| **Hypothesis Seer（Alpha 靈感占卜家）** | Alpha Idea、Expression | 輸入研究方向、dataset 或論文，輸出一張附正反文獻、可被證偽的假說靈感卡，以及通過語法檢查的 expression 與 GA template。 |
| **Expression Inquisitor（經濟意義審判官）** | Others | 審查假說是否通過四個關卡經濟意義檢驗，再把 expression 翻成白話，判斷它是否真的有假說所說的經濟意義。 |
| **Research Compass（研究進度羅盤）** | Data、Others | 讀自己 machine 上的研究紀錄，告訴你目前有哪些研究、卡在哪裡、哪些還沒做過，讓你清楚知道你的研究進度。 |

## 安裝

需求：open machine 已能跑（`.venv`、`run_data_sync.py` 同步過至少一個 region）、Claude Code。

```bash
bash agents/install.sh            # 先列清單再問一次；--only seer|inquisitor|compass 只裝一支；--yes --force 不問、覆蓋
```

它只新增檔案：`.claude/skills/*`、`.claude/agents/*`、`CLAUDE.md` 一行引入、`src/idea.py`、`DB/ResearchDB/{hypothesis,idea}/`。不改任何 `src/` 既有程式。
占卜家是主對話（`CLAUDE.md` 引入 `agents/hypothesis_seer/SEER.md`）；審判官是它的 subagent，可選；羅盤獨立。三支各自單獨裝都能完整使用。
（選用）讓語法檢查用你帳號的 operator 清單：`python agents/common/brain_meta.py operators`（需要 worker 已登入；過期會提醒你登入，不會自己登）。

## 流程

```
/research-compass   研究羅盤：A 段一步一步帶你把機器準備好、啟動第一次 GA；B 段四條路（選 dataset、認識 operator、設計 template、調 scorer）
                    地圖頁 agents/workspace/dashboard/index.html：新手地圖、專案管理、靈感卡、dataset 圖鑑、operator 倉庫
/dataset-profile <dataset> [--key 站]
                    羅盤：把一個 dataset 的欄位按經濟意義分群、每群挑代表欄位，地圖頁「dataset 圖鑑」長出這個 dataset 的卡
/operator-classify  羅盤：教你抓自己帳號的 operator 清單 → 建議分群方式讓你決定 → 羅盤照定義把每個 operator 分進去、各寫一句用途，地圖頁長出「operator 倉庫」
/hypothesis <方向|dataset|datafield|論文|空>
                    占卜家：第一站 ≤3 個市場命題（可量化嗎、channel 建議）讓你選 → 第二站 文獻 ≤5 篇 → 假說 → 四關 → 建卡 → 有裝審判官就問要不要送審；沒裝才自檢打分（只點出偏低的那關）
/express <card>     占卜家：挑欄位 → 四模組（清洗→訊號→平滑→組內）main / naive / 反向證偽三條 → 語法通過 → 寫 setting + idea
python -m src.idea --idea <card>        ← 你自己執行：idea → payload → AlphaDB/pending，hash 寫回 idea；worker 送模擬
python -m src.idea --status <card>      ← 看每條在哪一格、成績
/judge <card> [--expr "你自己寫的式子"]
                    審判官：白話反解釋 → 實作教條 → 用卡上預寫的 K1～K4 分析結果 → 讚美女神／懺悔後再審／處決（占卜家轉達時說：通過／重新占卜／拒絕）
/templatize <card>  占卜家：結果過了審判官或 self_check.py（Sharpe>1、tvr<0.5、K1、K2）→ template（同 subgroup 才互換、每個基因位寫理由）→ 有審判官就送審 → 寫入 DB/ResearchDB/template/
/spc universe       SPC 通道前置：ISIN|MIC 主清單（你貼回或 agent 用 WebSearch 抓）→ 審判官 Luhn／MIC／去重／反查 → DB/ResearchDB/spc/universe/
/spc <card>         占卜家：channel 含 spc 的卡 → 切子清單（~50 檔，跟著假說切面）→ 英文 prompt（方向機械、全名單給分、格式鎖定尾註）
                    → 審判官 stage=spc → 預測試 → 你在乾淨視窗跑 3 次存 runs/ → /judge --stage spc（spc_validate.py 全清單）→ finalize
/spc submitted <card> --name … --weight 0.05   ← 你在平台提交後告訴它登記；之後 /spc checked、/spc status（覆蓋 ≥500）
python sample_code/sample_ga.py --research_name <card>_<slug> --template_file <card>_<slug>.json --setting_file <card>.json
                    ← 你自己跑 GA；研究名稱保留 <card>_ 前綴，羅盤才連得回卡
```

## 四關（一張假說卡要回答的四個問題）

1 現象與機制　2 對手與為何不修正　3 為何持續（套利限制）　4 證偽設計（可反駁預測、失效條件、naive 對照、反向證偽組、候選欄位、生死線 K1～K4）。
任一關寫不具體 → 占卜家給低分、照樣建卡，由你決定。審判官審：理由說不說得通、是不是自圓其說、欄位搭配合不合理、有沒有經濟意義。定義：`agents/common/knowledge/four_gates.md`。

## 寫入哪裡

| 產出 | 位置 |
|---|---|
| 假說卡、判決書、帳本 | `DB/ResearchDB/hypothesis/<card>.md`、`hypothesis/reviews/`、`hypothesis/ledger.jsonl` |
| idea、setting | `DB/ResearchDB/idea/<card>.json`、`DB/ResearchDB/setting/<card>.json` |
| template | `DB/ResearchDB/template/<card>_<slug>.json`（＋ `.notes.json`） |
| SPC | `DB/ResearchDB/spc/universe/master_<日期>.json`、`spc/<card>/{sections.json, prompt.json, prompt.txt, universe.txt, runs/, validation_v*.md, form_final.md}`、`spc/registry.jsonl` |
| payload → pending | **你**執行 `python -m src.idea`；agent 不碰 `DB/AlphaDB/` |
| 快取、索引、Dashboard、羅盤 profile | `agents/workspace/` |

## 目錄

```
agents/
├── install.sh  README.md
├── tools/idea.py                      # 安裝後複製到 src/idea.py
├── common/                            # 三支共用
│   ├── paths.py ledger.py card.py idea_io.py brain_meta.py
│   ├── fastexpr_parser.py syntax_check.py templatizer.py templatize.py
│   └── knowledge/                     # four_gates、vague_logic_patterns、expression_doctrine、template_doctrine、operator_recipes、
│                                      # ga_tips、ga_template_design、examples/、operators.json、operator_subgroups.json（v4+）、sources.md
├── hypothesis_seer/   SEER.md  skills/{hypothesis,papers,express,templatize}  cli/{pick_fields,build_idea}.py
├── expression_inquisitor/  AGENT.md  skills/judge  cli/{blind_pack,result_pack,template_check}.py
├── research_compass/  skills/{research-compass,dataset-profile,operator-classify}  cli/{onboard,guide_page,dataset_snapshot,operator_index,template_draft,dedup}.py  knowledge/
└── workspace/         cache/ index/ dashboard/ compass_profile.json
```

## 合規與資料權限

- 不呼叫 Brain simulation API；payload 與 `pending/` 由使用者的 `src/idea.py` 與 worker 處理。
- 研究與模擬資料只讀本機本人；中繼資料（operators、dataset 清單）本機沒有才透過 open machine 既有 `MyOwnSess` 唯讀查詢，session 過期即停下提醒登入。
- 不讀 `.env`、`session.pkl`、`login_time.pkl`（只看 `login_time.pkl` 的檔案時間判斷是否過期）。
- 分享時只分享 `agents/` 程式與去識別範例；`agents/workspace/` 與 `DB/` 內容不要貼。

## 已知限制

- operators 與欄位清單因帳號而異；內建 `operators.json` 是預設清單，建議用 `brain_meta.py operators` 換成自己的。
- 沒有 WebSearch 的環境文獻品質取決於使用者提供的來源；未經檢索確認的文獻一律 `[?]`。
- 審判官的反解釋受 operator 語意理解限制；custom operator（`$`）只做存在性檢查。
- 羅盤的進度由本機檔案自動判斷；熱力圖只涵蓋本機同步過的站；舊版 Dashboard 封存在 `doc/agent_challenge/archive_compass_v1_dashboard/`；多人共用一台 machine 不支援。
- 不處理 SuperAlpha／Selection／Python 語言 alpha。
