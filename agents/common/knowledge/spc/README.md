# SPC 交接素材包

給「把假說轉成 SPC（Systematic Predictions Challenge）prompt」功能的 agent 使用的規則、規範、
失敗樣式與範例。內容已去識別化：不含任何真實研究假說、標的清單、prompt 成品或成績。

## 資料夾地圖

```
SPC 交接/
├── README.md                       ← 本檔
├── rules/                          ← 官方來源（權威）
│   ├── SPC_official_guideline.md   ← SPC 2026 官方規則（英文）
│   ├── submission_form_fields.md   ← 平台提交表單欄位原文
│   └── official_tips.md            ← 官方 webinar 要點：別依每日 PnL 換 prompt、權重三因子
├── spec/                           ← 把官方規則轉成可執行的判準
│   ├── FORMAT_SPEC.md              ← 表單逐欄規範、10,000 字元預算、JSON 合約、提交前驗證清單
│   ├── universe_procedure.md       ← ISIN|MIC 清單生成、驗證、切割、更新
│   └── FEEDBACK_PROTOCOL.md        ← 提交後追蹤：定期檢查是否一直 fail，是就權重歸零
├── lessons/
│   └── failure_patterns.md         ← 10 種操作化失敗樣式（症狀／處方／證據等級）
└── examples/
    ├── good_prompt_example.md      ← 虛構好範例：四柱 → 工作流對照＋完整 prompt＋逐條對照規則
    └── bad_prompt_example.md       ← 虛構壞範例：逐句標出錯誤與改法
```

## 權威順序（有衝突時）

`rules/` 官方原文 ＞ `spec/` 判準 ＞ `lessons/` 經驗 ＞ `examples/` 示範。

## Agent 流程對照

| 步驟 | 做什麼 | 看哪個檔 |
|---|---|---|
| 0 | 拿到一張通過四柱檢驗的假說卡（核心論點／交易對手／結構優勢／為何持續） | 由上游 agent 提供 |
| 1 | 判斷這個假說適不適合 SPC：方向能否錨定在單一權威數據？證據會不會太稀疏？ | `lessons/failure_patterns.md` #3、#4 |
| 2 | 準備 universe（切面跟著假說走；`TICKER = ISIN\|MIC` 格式） | `spec/universe_procedure.md` |
| 3 | 組 prompt：角色 → 工作流 → 強制搜尋 → Bull/Bear gate → universe → 給分規則 → 格式鎖定尾註 | `examples/good_prompt_example.md`、`spec/FORMAT_SPEC.md` 第二、三節 |
| 4 | 自我審查：逐條對照壞範例的錯誤表 | `examples/bad_prompt_example.md` |
| 5 | 乾淨視窗實測 3 次，跑完整驗證清單（實際 parse、實際數字元） | `spec/FORMAT_SPEC.md` 第四、五節 |
| 6 | 填表單欄位（Name／Model／Frequency／首次權重 0.05~0.10） | `spec/FORMAT_SPEC.md` 第一節 |
| 7 | 提交後追蹤：定期檢查是否一直 fail，是就權重歸零 | `spec/FEEDBACK_PROTOCOL.md` |

**硬規則**：提交不可逆（不能改、不能刪，只能權重歸零），所以第 5 步沒全過不得進第 6 步。
提交動作本身由人執行，agent 的產出到「prompt 本文＋表單欄位草稿＋驗證報告」為止。

## 證據等級說明

`lessons/` 的每條樣式帶等級：`R`＝規則／官方說法、`H`＝推測未驗證、`O1`＝單一 prompt 觀察到、
`O2`＝≥ 2 份獨立 prompt 重現。O1、H 只能當「要注意的可能性」，不是通則。
