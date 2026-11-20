---
name: dataset-profile
description: 研究羅盤 R1-2：把一個 dataset 的欄位按經濟語意分群、識別變體、每群選 ≤3 個代表欄位（主／擁擠／藍海），寫成 profile JSON（Intro／型態／命名／分群），讓地圖頁「dataset 圖鑑」長出這個 dataset 的卡。純本機、不打 API。用法 /dataset-profile <dataset> [--key USA_TOP3000_d1]
argument-hint: <dataset> [--key REGION_UNIVERSE_dDELAY]
---

# /dataset-profile <dataset>

使用者輸入：`$ARGUMENTS`。全部從 open machine 根目錄執行。這是研究羅盤 R1-2 用的 skill，由主對話執行；欄位 >100 時分群草稿派 subagent，主對話覆核。

## 鐵則

- **純本機**：唯一資料來源是 `DB/ResearchDB/data/latest/<key>/data_fields_raw/<dataset>.json`（每個欄位有 `id`、`description`、`type`、`coverage`、`alphaCount`、`userCount`、`pyramidMultiplier`）。沒有這個檔就說「本機沒同步 <key>／沒有這個 dataset」並停，不打 API。
- **分類是先驗，不是判決**：代表欄位沒訊號 ≠ 整群死刑；profile 決定的是花模擬額度的順序。
- 代表欄位的 id 必須在 raw JSON **逐字存在**（反幻覺）；`representatives` 的值一律是欄位 id 字串。
- 不送模擬、不改 open machine；只寫 `DB/ResearchDB/data/subdataset/`。

## 第 1 步：讀輸入

1. `--key` 沒給就用本機同步過的站裡第一個有這個 dataset 的（`ls DB/ResearchDB/data/latest/`）。
2. 讀 raw JSON；數欄位總數、type 分布、coverage 分布、alphaCount 分布。
3. `DB/ResearchDB/data/subdataset/<dataset>_<key>_profile.json` 已存在 → 問使用者要更新還是看現有的；更新走增量（保留人讀三欄的手改）。
4. 欄位 >100：派一個 subagent（general-purpose）做分群草稿——給它本檔第 2、3 步的規則＋raw JSON 路徑，只收回 JSON（groups／ungrouped）；主對話逐群覆核再落檔。

## 第 2 步：語意分群

- 分群單位是**經濟概念**，不是命名 pattern（命名只是線索）。目標 5～15 群；一群回答一個問題（獲利趨勢、槓桿風險、營收動能、情緒分歧、估值…）。
- 群內識別**變體**：同一訊號只差回看期（`_l1/_l2/_l3`）、財報期（`_fy1/_fp2`）、統計量（`_avg/_std/_min/_max`）、離散化（`_class`）的欄位互為變體；進 template 只由代表出面。
- 看不懂的欄位放 `ungrouped`，不要硬塞。

## 第 3 步：每群選代表（≤3，三角色）

| 角色 | 判準 | 目的 |
|---|---|---|
| primary 主代表 | 群內 coverage 最高 | 最可測、backfill 失真最小 |
| crowded 擁擠代表 | 群內 alphaCount 最高（coverage ≥ 0.6） | 最快確認這群有沒有訊號 |
| blueocean 藍海代表 | 群內 alphaCount 最低**且** coverage ≥ 0.6 | 低相關的便宜入口 |

- 同一欄位身兼多角 → 去重。
- coverage 底線 0.6 的原因：低 alphaCount 有兩種成因——沒人挖 vs 挖不動；不設底線挑進來的常是後者。
- 整群 alphaCount 全 0（全新 dataset）→ 只選主代表＋語意差異最大的次代表。

## 第 4 步：落檔

`DB/ResearchDB/data/subdataset/<dataset>_<key>_profile.json`：

```json
{
  "dataset": "analyst14",
  "key": "USA_TOP3000_d1",
  "generated": "2026-11-19",
  "field_total": 500,
  "intro": "2～3 句白話：這是什麼資料、可以把它想像成什麼、它在量什麼",
  "data_shape": {
    "type_mix": "MATRIX 456 / VECTOR 44",
    "coverage_summary": "整體 0.85；水準類高、計數類 0.5 以下",
    "quirks": "已知的坑：description 不可信的例子、某段資料消失、level shift 等；沒有就寫「尚未發現」"
  },
  "naming": {
    "pattern": "anl14_{統計量}_{會計項目}_{期間}",
    "segments": {"統計量": ["mean", "low", "high"], "期間": ["fp1", "fy1"]},
    "exceptions": "不符規律的欄位群說明"
  },
  "groups": [
    {
      "group": "profitability_trend",
      "semantic": "獲利趨勢預測（淨利／EPS 方向）",
      "representatives": {"primary": "anl14_mean_eps_fp1", "crowded": "anl14_mean_eps_fy1", "blueocean": "anl14_low_eps_fp3"},
      "fields": ["群內全部欄位 id"],
      "variant_note": "每個訊號有 fp1～fp5／fy1～fy4 期間變體"
    }
  ],
  "ungrouped": ["看不懂的欄位 id"]
}
```

人讀三欄（`intro`、`data_shape`、`naming`）是圖鑑卡直接顯示的內容，要寫得像給別人看的一句話。

## 完成的標準

- [ ] 全部欄位都有歸屬（含 ungrouped），總數對得上 raw JSON
- [ ] 每群代表 ≤3、逐字確認存在、藍海代表 coverage ≥ 0.6
- [ ] 人讀三欄填齊
- [ ] profile 落檔；`python3 agents/research_compass/cli/onboard.py card add "<dataset>" --lane 研究中 --note "profile 落檔，N 群"`（已有同名卡就 `card move`）
- [ ] 重跑 `python3 agents/research_compass/cli/guide_page.py`，圖鑑卡出現
- [ ] 向使用者回報：幾群、各群代表、建議先試哪幾群；**不送模擬**
