"""語法檢查器（非 LLM）— 送模擬前的守門員（移植自素材包 tools/syntax_check.py）

  python agents/common/syntax_check.py -e "rank(ts_delta(close, 20))" [-s H-261115-003]
  python agents/common/syntax_check.py -i H-261115-003            # idea 檔（DB/ResearchDB/idea/，setting 自動取 idea.setting_file）
  python agents/common/syntax_check.py -t H-261115-003_slug       # template 檔（DB/ResearchDB/template/，抽樣展開）
  --fix       規則式自動修復，idea 模式會另存 <id>_fixed.json（原檔不動）
  --json      機器可讀輸出（給 agent 解析）

-s 指定 setting（檔名或卡號）後加驗欄位存在性與 VECTOR 型別。
檢查層級：1 語法 2 語意（operators.json）3 資料（已同步 datafields）
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from agents.common import paths, idea_io  # noqa: E402
from agents.common.fastexpr_parser import AlphaParser, load_datafield_index  # noqa: E402


def _issues_ok(issues: list[dict]) -> bool:
    return not any(i["level"] == "ERROR" for i in issues)


def _print(label: str, issues: list[dict]) -> bool:
    if not issues:
        print(f"  [PASS] {label}")
        return True
    for iss in issues:
        print(f"  [{iss['level']}] {label}: {iss['message']}")
    return _issues_ok(issues)


def _context(setting_name: str | None):
    if not setting_name:
        return None, None
    _, setting = idea_io.load_setting(setting_name)
    region, universe, delay = idea_io.setting_rud(setting)
    datafields, field_types = load_datafield_index(region, universe, delay)
    print(f"[上下文] {paths.setting_key(region, universe, delay)}：{len(datafields)} 個欄位")
    return datafields, field_types


def main() -> int:
    ap = argparse.ArgumentParser(description="FASTEXPR 語法檢查器（非 LLM）")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("-e", "--expression")
    g.add_argument("-i", "--idea", help="卡號、idea 檔名或路徑")
    g.add_argument("-t", "--template", help="template 檔名或路徑")
    ap.add_argument("-s", "--setting", default=None, help="setting 檔名／卡號（加驗欄位與 VECTOR）")
    ap.add_argument("--fix", action="store_true")
    ap.add_argument("--n_random", type=int, default=5)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    parser = AlphaParser.from_available(verbose=not args.json)
    report: dict = {"mode": None, "results": [], "pass": False}
    exit_code = 0

    # ---------------- 單條
    if args.expression:
        report["mode"] = "expression"
        datafields, field_types = _context(args.setting)
        issues = parser.check(args.expression, datafields, field_types)
        fixed = None
        if args.fix and not _issues_ok(issues):
            fixed, remaining = parser.fix(args.expression, datafields, field_types)
            if not args.json:
                print("原始 issues:"); _print("expr", issues); print(f"修復後:\n{fixed}")
            ok = _print("fixed", remaining) if not args.json else _issues_ok(remaining)
            report["results"].append({"expr": args.expression, "issues": issues, "fixed": fixed, "remaining": remaining})
        else:
            ok = _print("expr", issues) if not args.json else _issues_ok(issues)
            report["results"].append({"expr": args.expression, "issues": issues})
        report["pass"] = ok
        exit_code = 0 if ok else 1

    # ---------------- idea 檔
    elif args.idea:
        report["mode"] = "idea"
        idea_path, idea = idea_io.load_idea(args.idea)
        setting_name = args.setting or idea.get("setting_file")
        datafields, field_types = _context(setting_name)
        exprs = idea["expressions"]
        if not args.json:
            print(f"[載入] {paths.rel(idea_path)}：{len(exprs)} 條 expression\n")
        n_pass = n_fixed = n_fail = 0
        fixed_exprs = []
        for i, e in enumerate(exprs, 1):
            label = f"#{i} {e.get('role', '')}"
            issues = parser.check(e["expr"], datafields, field_types)
            entry = {"index": i, "role": e.get("role"), "issues": issues}
            if _issues_ok(issues):
                if not args.json: _print(label, issues)
                fixed_exprs.append(dict(e)); n_pass += 1
            elif args.fix:
                fixed, remaining = parser.fix(e["expr"], datafields, field_types)
                entry.update({"fixed": fixed, "remaining": remaining})
                if _issues_ok(remaining):
                    if not args.json: print(f"  [FIXED] {label}: {issues[0]['message']}\n          → {fixed}")
                    ne = dict(e); ne["expr"] = fixed; fixed_exprs.append(ne); n_fixed += 1
                else:
                    if not args.json: _print(f"{label}（修復失敗）", remaining)
                    fixed_exprs.append(dict(e)); n_fail += 1
            else:
                if not args.json: _print(label, issues)
                fixed_exprs.append(dict(e)); n_fail += 1
            report["results"].append(entry)
        if not args.json:
            print(f"\n結果：{n_pass} PASS / {n_fixed} FIXED / {n_fail} FAIL（共 {len(exprs)}）")
        if args.fix and n_fixed > 0:
            out = idea_path.with_name(idea_path.stem + "_fixed.json")
            idea_out = dict(idea); idea_out["expressions"] = fixed_exprs
            idea_io.save_idea(out, idea_out)
            report["fixed_file"] = paths.rel(out)
            if not args.json:
                print(f"修復版已存：{paths.rel(out)}（確認後自行覆蓋原檔）")
        report["pass"] = n_fail == 0
        exit_code = 0 if n_fail == 0 else 1

    # ---------------- template 檔
    else:
        report["mode"] = "template"
        tpl_path = paths.resolve_file(args.template, paths.OM.TEMPLATE)
        with open(tpl_path, "r", encoding="utf-8") as f:
            tpl = json.load(f)
        datafields, field_types = _context(args.setting)
        pool = tpl.get("gene_pool", {})
        keys = list(pool.keys())
        combos = []
        for k in keys:
            for v in pool[k]:
                combo = {kk: pool[kk][0] for kk in keys}
                combo[k] = v
                combos.append(combo)
        for _ in range(args.n_random):
            combos.append({kk: random.choice(pool[kk]) for kk in keys})
        seen, n_bad = set(), 0
        for combo in combos:
            expr = tpl["template"]
            for k, v in combo.items():
                expr = expr.replace(k, str(v))
            if "<" in expr:
                msg = f"展開後仍有未替換佔位符（gene_pool 缺 key）：{[t for t in expr.split() if '<' in t][:3]}"
                if not args.json: print(f"  [ERROR] {msg}")
                report["results"].append({"level": "ERROR", "message": msg}); n_bad += 1
                break
            for iss in parser.check(expr, datafields, field_types):
                if iss["message"] not in seen:
                    seen.add(iss["message"])
                    if not args.json: print(f"  [{iss['level']}] {iss['message']}")
                    report["results"].append(iss)
                    if iss["level"] == "ERROR": n_bad += 1
        if n_bad == 0 and not args.json:
            print(f"  [PASS] {len(combos)} 組展開全部通過")
        report["n_combos_checked"] = len(combos)
        report["pass"] = n_bad == 0
        exit_code = 0 if n_bad == 0 else 1

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
