"""R2-1 operator 倉庫：用「你帳號的 operator 清單」＋「你決定的分群方式」＋「羅盤的分類」做一份索引給地圖頁。

三步（都在羅盤對話裡做，見 skills/operator-classify）：
  1. 抓你帳號的清單：python agents/common/brain_meta.py operators   → agents/workspace/cache/operators.json
  2. 決定分群方式：python agents/research_compass/cli/operator_index.py init [--groups "清洗,訊號,平滑,組內,其他"]
       → agents/workspace/operator_groups.json（分群骨架＋待分類清單；羅盤照自己的理解填 assignments）
  3. 建索引：python agents/research_compass/cli/operator_index.py            → agents/workspace/index/operator_index.json
       python agents/research_compass/cli/operator_index.py --find ts_delta  # 查一個 operator 在哪一群
       python agents/research_compass/cli/operator_index.py --todo           # 列還沒分類的

只讀本機。清單只用你帳號的（cache 或 data/latest），不用羅盤內建的；分群表是你和羅盤一起做的，不是羅盤預先給的。
custom operator：src/custom_op_definition.py 的 MAPPING（你自己定義的 $名稱）。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from agents.common import paths  # noqa: E402

OUT = paths.OUT.INDEX / "operator_index.json"
GROUPS = paths.AGENTS / "workspace" / "operator_groups.json"

# 羅盤建議的分群方式（使用者可以改名、加減群）；每群回答一個問題
DEFAULT_SCHEME = [
    {"id": "clean", "name": "清洗", "question": "原始值哪裡髒？缺值回補、壓極端值、去單位"},
    {"id": "signal", "name": "訊號", "question": "機制對應的量是什麼？變化、差距、比值、波動、相關"},
    {"id": "smooth", "name": "平滑", "question": "持有多久？時序平滑與換手控制"},
    {"id": "group", "name": "組內", "question": "跟誰比？同業／同市場內的相對值"},
    {"id": "other", "name": "其他", "question": "不進四層 pipeline 的工具，以及羅盤建議盡量不要用的 operator（每個寫原因）"},
]


def user_operators_path() -> Path | None:
    """只用使用者自己的清單：brain_meta 抓的快取 → run_data_sync 同步的；都沒有就 None（不退回內建清單）。"""
    for p in (paths.OUT.CACHE / "operators.json", paths.OM.DATA_LATEST / "operators.json"):
        if p.exists():
            return p
    return None


def load_operators() -> tuple[list[dict], str]:
    p = user_operators_path()
    if not p:
        return [], ""
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return [], paths.rel(p)
    if isinstance(data, dict) and "results" in data:
        data = data["results"]
    ops = [o for o in data if isinstance(o, dict) and o.get("name")]
    ops.sort(key=lambda o: (o.get("category") or "", o["name"]))
    return ops, paths.rel(p)


def load_custom_ops() -> list[dict]:
    """讀 src/custom_op_definition.py 的 MAPPING：只抓名稱與 function 的 return 字串，不執行。"""
    p = paths.ROOT / "src" / "custom_op_definition.py"
    if not p.exists():
        return []
    src = p.read_text(encoding="utf-8")
    out = []
    for m in re.finditer(r"def\s+(\w+)\s*\(([^)]*)\)\s*:\s*\n\s*return\s+f?[\"'](.+?)[\"']", src):
        out.append({"func": m.group(1), "args": m.group(2).strip(), "expands_to": m.group(3)})
    names = dict(re.findall(r"[\"'](\w+)[\"']\s*:\s*(\w+)", src.split("MAPPING")[-1])) if "MAPPING" in src else {}
    for o in out:
        o["name"] = next((k for k, v in names.items() if v == o["func"]), o["func"])
        o["registered"] = o["func"] in names.values()
    return out


def init(groups: str | None) -> dict:
    """寫分群骨架：scheme（使用者決定）＋ 待分類的 operator 清單（名稱、平台分類、定義、說明）＋ 空的 assignments。"""
    ops, src = load_operators()
    if not ops:
        raise SystemExit("還沒有你帳號的 operator 清單。先跑：python agents/common/brain_meta.py operators（要先登入 worker）")
    if groups:
        names = [g.strip() for g in groups.split(",") if g.strip()]
        by_name = {g["name"]: g for g in DEFAULT_SCHEME}
        scheme = [by_name.get(n) or {"id": f"g{i + 1}", "name": n, "question": ""} for i, n in enumerate(names)]
    else:
        scheme = [dict(g) for g in DEFAULT_SCHEME]
    old = {}
    if GROUPS.exists():
        try:
            old = json.loads(GROUPS.read_text(encoding="utf-8")).get("assignments", {})
        except Exception:
            old = {}
    valid = {g["id"] for g in scheme}
    rep = {"generated": datetime.now().strftime("%Y-%m-%d"), "source": src, "decided_by": "user",
           "scheme": scheme,
           "to_classify": [{"name": o["name"], "category": o.get("category", ""), "definition": o.get("definition", ""),
                            "description": o.get("description", "")} for o in ops],
           "assignments": {k: v for k, v in old.items() if isinstance(v, dict) and v.get("group") in valid}}
    paths.ensure_parent(GROUPS)
    GROUPS.write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    return rep


def build() -> dict:
    ops, src = load_operators()
    if not ops:
        raise SystemExit("還沒有你帳號的 operator 清單。先跑：python agents/common/brain_meta.py operators（要先登入 worker）")
    if not GROUPS.exists():
        raise SystemExit(f"還沒有分群表 {paths.rel(GROUPS)}。先跑：python agents/research_compass/cli/operator_index.py init")
    g = json.loads(GROUPS.read_text(encoding="utf-8"))
    scheme = g.get("scheme") or DEFAULT_SCHEME
    assigns: dict[str, dict] = g.get("assignments") or {}
    by_name = {o["name"]: o for o in ops}
    unknown = sorted(n for n in assigns if n not in by_name)
    valid = {s["id"] for s in scheme}
    bad_group = sorted(n for n, a in assigns.items() if not isinstance(a, dict) or a.get("group") not in valid)
    groups = []
    for s in scheme:
        rows = []
        for n, a in assigns.items():
            if n in by_name and isinstance(a, dict) and a.get("group") == s["id"]:
                o = by_name[n]
                rows.append({"name": n, "definition": o.get("definition", ""), "description": o.get("description", ""),
                             "category": o.get("category", ""), "note": a.get("note", ""), "avoid": bool(a.get("avoid"))})
        rows.sort(key=lambda r: (r["avoid"], r["name"]))
        groups.append({"id": s["id"], "name": s["name"], "question": s.get("question", ""), "operators": rows, "n": len(rows)})
    unassigned = [{"name": o["name"], "category": o.get("category", ""), "definition": o.get("definition", "")}
                  for o in ops if o["name"] not in assigns]
    rep = {"generated": datetime.now().isoformat(timespec="seconds"), "source": src, "n_operators": len(ops),
           "scheme_source": paths.rel(GROUPS), "decided_by": g.get("decided_by", "user"),
           "groups": groups, "n_assigned": len(ops) - len(unassigned), "unassigned": unassigned,
           "problems": {"unknown_names": unknown, "bad_group": bad_group}, "custom_ops": load_custom_ops()}
    paths.ensure_parent(OUT)
    OUT.write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    return rep


def render(rep: dict) -> str:
    out = [f"operator 倉庫：清單 {rep['source']}（{rep['n_operators']} 個，你帳號的）；分群表 {rep['scheme_source']}；已分 {rep['n_assigned']} 個"]
    for g in rep["groups"]:
        out.append(f"\n{g['name']}（{g['n']}）— {g['question']}")
        for r in g["operators"]:
            out.append(f"  {'⚠ ' if r['avoid'] else ''}{r['name']:<24} {r['note']}")
    if rep["unassigned"]:
        out.append(f"\n還沒分類（{len(rep['unassigned'])}）：" + ", ".join(x["name"] for x in rep["unassigned"]))
    pr = rep["problems"]
    if pr["unknown_names"]:
        out.append("⚠ 分群表裡有清單沒有的名字（打錯或帳號沒有）：" + ", ".join(pr["unknown_names"]))
    if pr["bad_group"]:
        out.append("⚠ 群 id 不在 scheme 裡：" + ", ".join(pr["bad_group"]))
    if rep["custom_ops"]:
        out.append("\n你的 custom operator（src/custom_op_definition.py）：")
        for c in rep["custom_ops"]:
            out.append(f"  ${c['name']}({c['args']}) → {c['expands_to']}" + ("" if c["registered"] else "　⚠ 還沒登記進 MAPPING"))
    out.append(f"\n[存檔] {paths.rel(OUT)}；地圖頁重跑 guide_page.py 會更新「operator 倉庫」分頁")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description="operator 倉庫（你的清單、你的分群）")
    ap.add_argument("cmd", nargs="?", default="build", choices=["build", "init"])
    ap.add_argument("--groups", help="init 用：群名用逗號分開，例如「清洗,訊號,平滑,組內,其他」；不給就用羅盤建議的五群")
    ap.add_argument("--find", help="找一個 operator 在哪一群")
    ap.add_argument("--todo", action="store_true", help="只列還沒分類的 operator（含定義與說明，給羅盤分類用）")
    args = ap.parse_args()
    if args.cmd == "init":
        rep = init(args.groups)
        print(f"[分群骨架] {paths.rel(GROUPS)}：{len(rep['scheme'])} 群（{'、'.join(s['name'] for s in rep['scheme'])}），"
              f"待分類 {len(rep['to_classify'])} 個，沿用舊分類 {len(rep['assignments'])} 個")
        return 0
    rep = build()
    if args.todo:
        for x in rep["unassigned"]:
            o = next((o for o in load_operators()[0] if o["name"] == x["name"]), {})
            print(f"{x['name']}｜{x['category']}｜{x['definition']}｜{o.get('description', '')}")
        print(f"（{len(rep['unassigned'])} 個還沒分類）")
        return 0
    if args.find:
        for g in rep["groups"]:
            for r in g["operators"]:
                if r["name"] == args.find:
                    print(f"{args.find}：{g['name']}（{g['question']}）\n  {r['definition']}\n  {r['description']}\n  羅盤的說明：{r['note']}"
                          + ("\n  ⚠ 建議盡量不要用" if r["avoid"] else "")
                          + f"\n  同一群：{', '.join(x['name'] for x in g['operators'] if x['name'] != args.find and not x['avoid']) or '—'}")
                    return 0
        print(f"{args.find}：不在清單裡，或還沒分類"); return 1
    print(render(rep))
    return 0


if __name__ == "__main__":
    sys.exit(main())
