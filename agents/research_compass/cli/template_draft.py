"""R3-1 第一個自己的 template：從 dataset profile 的一個語意群產一份四模組骨架的 template 草稿，並跑語法檢查。

  python agents/research_compass/cli/template_draft.py --dataset analyst14 --group profitability_trend
  python agents/research_compass/cli/template_draft.py --dataset analyst14            # 列出這個 dataset 的群
  python agents/research_compass/cli/template_draft.py --dataset analyst14 --group g --name my_template

草稿只是起點：欄位基因位放該群的代表（＋變體），每層放 2～3 個同一群的 operator、天數 3～5 個值；
空間大小會印出來。寫完請自己改：刪掉說不出理由的選項、把一句話假說寫在 notes。
輸出：DB/ResearchDB/template/<name>.json（open machine 的正常輸入）；不送模擬。
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from agents.common import paths  # noqa: E402

SUBDATASET = paths.OM.DATA / "subdataset"

# 四模組骨架（同 default_template.json 的精神；每個 space 的選項都在同一群）
TEMPLATE = (
    "data = winsorize(ts_backfill(<field>, <backfill_days>), std=4);\n"
    "signal = <signal_op>(data, <signal_days>);\n"
    "smooth = <smooth_op>(signal, <smooth_days>);\n"
    "(<sign>) * <group_op>(smooth, <group>)"
)
GENE_POOL = {
    "<backfill_days>": [21, 63],
    "<signal_op>": ["ts_delta", "ts_av_diff", "ts_returns"],            # 訊號層：跟自己過去比（x + d）
    "<signal_days>": [10, 21, 63, 126, 252],
    "<smooth_op>": ["ts_decay_linear", "ts_mean"],                       # 平滑層（x + d）
    "<smooth_days>": [5, 10, 21],
    "<sign>": [1, -1],
    "<group_op>": ["group_rank", "group_zscore", "group_neutralize"],    # 組內層（x + group）
    "<group>": ["market", "sector", "industry"],
}
NOTES = {
    "<field>": "R1-2 這一群的代表欄位（主／擁擠／藍海）＋變體；一個 template 只放一個語意群",
    "<signal_op>": "訊號層：跟自己過去比。三個選項是同一個想法（變化）的不同算法",
    "<signal_days>": "變化看多長：短到一季、長到一年",
    "<smooth_op>": "平滑：快（decay）vs 慢（mean）",
    "<group_op>": "組內層：跟同群比。想法相同、算法不同",
    "<group>": "跟誰比：全市場／產業／細產業",
    "<sign>": "方向由資料決定；寫假說時先猜一個，跑完對照",
}


def load_profile(dataset: str, key: str | None) -> dict | None:
    cands = sorted(SUBDATASET.glob(f"{dataset}_*_profile.json")) if SUBDATASET.exists() else []
    if key:
        cands = [c for c in cands if c.name == f"{dataset}_{key}_profile.json"]
    if not cands:
        return None
    return json.loads(cands[0].read_text(encoding="utf-8"))


def space_size(pool: dict) -> int:
    n = 1
    for v in pool.values():
        n *= max(len(v), 1)
    return n


def draft(prof: dict, group: str, extra_variants: int = 2) -> tuple[dict, dict]:
    g = next((x for x in prof.get("groups", []) if x.get("group") == group), None)
    if not g:
        raise SystemExit(f"profile 裡沒有群 {group}；有的群：{', '.join(x.get('group', '') for x in prof.get('groups', []))}")
    reps = [v for v in (g.get("representatives") or {}).values() if isinstance(v, str)]
    fields = list(dict.fromkeys(reps))
    for f in g.get("fields") or []:
        if len(fields) >= len(reps) + extra_variants:
            break
        if f not in fields:
            fields.append(f)
    pool = {"<field>": fields, **{k: list(v) for k, v in GENE_POOL.items()}}
    # 只留帳號有的 operator（清單：cache → data/latest → 內建）
    have = None
    p = paths.resolve_operators_path()
    if p:
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            data = data.get("results", data) if isinstance(data, dict) else data
            have = {o["name"] for o in data if isinstance(o, dict) and o.get("name")}
        except Exception:
            have = None
    if have:
        for k in ("<signal_op>", "<smooth_op>", "<group_op>"):
            kept = [o for o in pool[k] if o in have]
            pool[k] = kept or pool[k][:1]
    hypo = (f"假說（請改成你的話）：{prof.get('dataset')} 的「{g.get('semantic', group)}」相對同群的近期變化，"
            f"<高／低> 的股票之後會 <漲／跌>，因為 <機制>。")
    tpl = {"template": TEMPLATE, "gene_pool": pool,
           "notes": {"hypothesis": hypo, "dataset": prof.get("dataset"), "key": prof.get("key"), "group": group,
                     "semantic": g.get("semantic", ""), "generated": datetime.now().strftime("%Y-%m-%d"),
                     "by": "research_compass template_draft.py（草稿，請自己修）", "gene_reasons": NOTES}}
    return tpl, g


def main() -> int:
    ap = argparse.ArgumentParser(description="第一個自己的 template（草稿）")
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--key", help="站，例如 USA_TOP3000_d1（profile 有多站時指定）")
    ap.add_argument("--group", help="profile 裡的群名；不給就列出所有群")
    ap.add_argument("--name", help="輸出檔名（不含 .json）；預設 <dataset>_<group>_draft")
    ap.add_argument("--variants", type=int, default=2, help="代表之外再放幾個變體（預設 2）")
    args = ap.parse_args()
    prof = load_profile(args.dataset, args.key)
    if not prof:
        print(f"找不到 {args.dataset} 的 profile（{paths.rel(SUBDATASET)}）→ 先做 R1-2：跟羅盤說「幫我分析 {args.dataset}」"); return 2
    if not args.group:
        print(f"{prof['dataset']}（{prof.get('key')}）的群：")
        for g in prof.get("groups", []):
            reps = (g.get("representatives") or {})
            print(f"  {g.get('group')}　{g.get('semantic', '')}　代表：{', '.join(str(v) for v in reps.values())}（{len(g.get('fields') or [])} 個欄位）")
        print("選一群：--group <群名>"); return 0
    tpl, g = draft(prof, args.group, args.variants)
    name = args.name or f"{args.dataset}_{args.group}_draft"
    out = paths.OM.TEMPLATE / f"{name}.json"
    if out.exists():
        print(f"{paths.rel(out)} 已存在，換個 --name 或先刪掉"); return 1
    paths.ensure_parent(out)
    out.write_text(json.dumps(tpl, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[草稿] {paths.rel(out)}")
    print(f"  欄位（{len(tpl['gene_pool']['<field>'])}）：{', '.join(tpl['gene_pool']['<field>'])}")
    print(f"  space 大小：{space_size(tpl['gene_pool']):,}（kid_num 30 × 3 代只會試 90 個點，先小再大）")
    print(f"  {tpl['notes']['hypothesis']}")
    print("\n語法檢查：")
    r = subprocess.run([sys.executable, str(paths.AGENTS / "common" / "syntax_check.py"), "-t", name], capture_output=True, text=True, cwd=paths.ROOT)
    print((r.stdout or r.stderr).strip()[-1500:])
    print(f"\n下一步：改 notes 裡的假說、刪掉說不出理由的選項，然後用 A5 的指令起 GA：--template_file {name}.json --research_name <新名字>")
    return 0 if r.returncode == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
