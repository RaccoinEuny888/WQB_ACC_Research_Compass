"""expression → template（移植自素材包 tools/templatize.py）

  python agents/common/templatize.py --from-idea H-261115-003 [--role main] -o H-261115-003_slug
  python agents/common/templatize.py -e "group_zscore(ts_delta(close, 20), industry)" -o my_template
  python agents/common/templatize.py -t my_template --opt-block -o my_template_opt   # 只包優化層（需自備 optimization_block.json）
  --dry   只印不寫

輸出：DB/ResearchDB/template/<name>.json 與 <name>.notes.json（骨架，每個基因位的 why 由占卜家填）。
產出後請人工刪減 gene_pool，再跑 syntax_check.py -t 驗證。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from agents.common import paths, idea_io  # noqa: E402
from agents.common.templatizer import Templatizer, wrap_with_opt_block, count_combinations, check_gene_pool  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="expression → template 自動化")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("-e", "--expression")
    g.add_argument("--from-idea", help="卡號或 idea 檔")
    g.add_argument("-t", "--template", help="既有 template（只做 --opt-block）")
    ap.add_argument("--role", default="main", help="idea 內的 role（預設 main）")
    ap.add_argument("--index", type=int, default=None, help="或用 1-based 編號")
    ap.add_argument("--opt-block", action="store_true")
    ap.add_argument("--opt-block-file", default="optimization_block.json")
    ap.add_argument("-o", "--output", required=True, help="輸出檔名（存到 DB/ResearchDB/template/）")
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()

    card_id = ""
    tz = Templatizer()
    if args.template:
        with open(paths.resolve_file(args.template, paths.OM.TEMPLATE), "r", encoding="utf-8") as f:
            result = json.load(f)
    else:
        if args.expression:
            expr = args.expression
        else:
            _, idea = idea_io.load_idea(args.from_idea)
            card_id = idea.get("card_id", "")
            exprs = idea["expressions"]
            if args.index:
                e = exprs[args.index - 1]
            else:
                cands = [x for x in exprs if x.get("role") == args.role]
                if not cands:
                    print(f"idea 裡沒有 role={args.role} 的 expression（有：{[x.get('role') for x in exprs]}）")
                    return 1
                e = cands[0]
            expr = e["expr"]
            print(f"[載入] {card_id} role={e.get('role')}：\n{expr}\n")
        result = tz.templatize(expr)
    if args.opt_block:
        result = wrap_with_opt_block(result, args.opt_block_file)

    name = args.output[:-5] if args.output.endswith(".json") else args.output
    out_path = paths.OM.TEMPLATE / f"{name}.json"
    notes_path = paths.OM.TEMPLATE / f"{name}.notes.json"
    notes = tz.notes_skeleton(result, card_id)
    notes["template_file"] = out_path.name

    print("=" * 60)
    print("Template:")
    print(result["template"])
    print("-" * 60)
    import re as _re
    n_ops = len(set(_re.findall(r"\b([a-z_][a-z0-9_]*)\s*\(", result["template"])))
    n_slots_op = sum(1 for k in result["gene_pool"] if k.startswith("<op"))
    print(f"基因位 {len(result['gene_pool'])} 個，組合數 {count_combinations(result['gene_pool']):,}；"
          f"固定 operator {n_ops} 個 + operator 基因位 {n_slots_op} 個（替代配方會讓數量變多，見 operator_recipes.md §6）")
    for k, v in result["gene_pool"].items():
        preview = str(v if len(v) <= 6 else v[:6] + ["..."])
        print(f"  {k}: {preview}")
    issues = check_gene_pool(result["gene_pool"])
    for i in issues:
        print(f"  [{i['level']}] {i['message']}")
    print("-" * 60)
    if args.dry:
        print("（--dry 未寫檔）")
        return 0
    paths.ensure_parent(out_path)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    with open(notes_path, "w", encoding="utf-8") as f:
        json.dump(notes, f, ensure_ascii=False, indent=2)
    print(f"已存：{paths.rel(out_path)}")
    print(f"註解骨架：{paths.rel(notes_path)}（每個基因位填一行 why；填不出來的選項刪掉）")
    print(f"下一步：python agents/common/syntax_check.py -t {out_path.name} -s <setting>")
    return 0


if __name__ == "__main__":
    sys.exit(main())
