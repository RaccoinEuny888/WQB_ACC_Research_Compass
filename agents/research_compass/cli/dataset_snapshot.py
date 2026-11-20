"""R1-2 Dataset Priority：把每次 run_data_sync.py 的結果聚合成 dataset 層快照，跟上一次比，排出優先順序。

  python agents/research_compass/cli/dataset_snapshot.py            # 建快照（缺的補）→ 算優先順序 → 印各站 Top N
  python agents/research_compass/cli/dataset_snapshot.py --top 10
  python agents/research_compass/cli/dataset_snapshot.py --list     # 列出有哪些快照
  python agents/research_compass/cli/dataset_snapshot.py --json

只讀本機：DB/ResearchDB/data/<同步日期>/<REGION>_<UNIVERSE>_d<DELAY>/data_fields_raw/*.json（run_data_sync.py 每跑一次存一個日期資料夾）。
不打平台 API、不動 src/data_sync.py。
快照：agents/workspace/snapshots/<日期>_dataset_metadata.json
優先順序：agents/workspace/index/dataset_priority.json（地圖頁「dataset 圖鑑」的資料來源）

排序規則（使用者 2026-11-19 裁定）：加權分數 0～100 ＝ pyramid 加成 × 50 ＋ alphaCount 變化%（大的往前）× 30 ＋ 新 dataset × 20；
權重可在 agents/workspace/priority_weights.json 改（預設是羅盤定的 [R]）。只有一份快照時後兩項算不出（當 0），照實標「無法比較」。
正規化：pyramid = (倍數−1)/(本次最大倍數−1)；變化% = 正成長 ÷ 本次最大正成長（負的算 0）；新 = 1/0。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from agents.common import paths  # noqa: E402

SNAP_DIR = paths.WORKSPACE / "snapshots"
PRIORITY = paths.OUT.INDEX / "dataset_priority.json"
SYNC_CYCLE_DAYS = 30     # 使用者裁定：資料同步週期 30 天
WEIGHTS_FILE = paths.WORKSPACE / "priority_weights.json"
DEFAULT_WEIGHTS = {"pyramid": 50, "change": 30, "new": 20}   # 順序 pyramid → 變化% → 新，權重由大到小 [R]


def load_weights() -> dict:
    w = dict(DEFAULT_WEIGHTS)
    if WEIGHTS_FILE.exists():
        try:
            w.update({k: float(v) for k, v in json.loads(WEIGHTS_FILE.read_text(encoding="utf-8")).items() if k in w})
        except Exception:
            pass
    return w
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


# ------------------------------------------------------------------ 同步資料夾
def sync_folders() -> list[tuple[str, Path]]:
    """(日期, 資料夾) 由舊到新。日期資料夾優先；沒有就用 latest 的檔案時間。"""
    root = paths.OM.DATA
    if not root.exists():
        return []
    out = []
    for d in root.iterdir():
        if d.is_dir() and DATE_RE.match(d.name) and any(d.glob("*/data_fields_raw")):
            out.append((d.name, d))
    if not out and (root / "latest").exists() and any((root / "latest").glob("*/data_fields_raw")):
        mt = max((p.stat().st_mtime for p in (root / "latest").glob("*/data_fields.json")), default=time.time())
        out.append((datetime.fromtimestamp(mt).strftime("%Y-%m-%d"), root / "latest"))
    return sorted(out)


def sync_age_days() -> float | None:
    f = sync_folders()
    if not f:
        return None
    last = f[-1][1]
    mt = max((p.stat().st_mtime for p in last.glob("*/data_fields.json")), default=last.stat().st_mtime)
    return round((time.time() - mt) / 86400, 1)


# ------------------------------------------------------------------ 快照
def aggregate(folder: Path) -> dict:
    """一個同步資料夾 → {key: [dataset 層中繼資料...]}。dataset 層的 alphaCount = 欄位加總、pyramid = 欄位最大值、coverage = 平均。"""
    out: dict[str, list[dict]] = {}
    for kd in sorted(folder.iterdir()):
        raw = kd / "data_fields_raw"
        if not kd.is_dir() or not raw.exists():
            continue
        m = re.match(r"^(.+)_(.+)_d(\d+)$", kd.name)
        rows_out = []
        for p in sorted(raw.glob("*.json")):
            try:
                rows = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                continue
            if not isinstance(rows, list) or not rows:
                continue
            n = len(rows)
            types: dict[str, int] = defaultdict(int)
            for r in rows:
                types[str(r.get("type") or "?")] += 1
            first = rows[0]
            cat = first.get("category") or {}
            sub = first.get("subcategory") or {}
            ds = first.get("dataset") or {}
            rows_out.append({
                "id": p.stem, "name": ds.get("name") if isinstance(ds, dict) else None,
                "category": cat.get("name") if isinstance(cat, dict) else str(cat or ""),
                "subcategory": sub.get("name") if isinstance(sub, dict) else str(sub or ""),
                "region": m.group(1) if m else None, "universe": m.group(2) if m else None, "delay": int(m.group(3)) if m else None,
                "fieldCount": n,
                "alphaCount": int(sum((r.get("alphaCount") or 0) for r in rows)),
                "userCount": int(max((r.get("userCount") or 0) for r in rows)),
                "coverage": round(sum((r.get("coverage") or 0) for r in rows) / n, 3),
                "pyramidMultiplier": round(max((r.get("pyramidMultiplier") or 1) for r in rows), 2),
                "types": dict(types),
            })
        out[kd.name] = rows_out
    return out


def build_snapshots(refresh: bool = False) -> list[Path]:
    paths.ensure_parent(SNAP_DIR / "x")
    made = []
    for date, folder in sync_folders():
        dest = SNAP_DIR / f"{date}_dataset_metadata.json"
        if dest.exists() and not refresh:
            continue
        data = aggregate(folder)
        dest.write_text(json.dumps({"date": date, "source": paths.rel(folder), "built_at": datetime.now().isoformat(timespec="seconds"),
                                    "data": data}, ensure_ascii=False, indent=1), encoding="utf-8")
        made.append(dest)
    return made


def load_snapshots() -> list[dict]:
    if not SNAP_DIR.exists():
        return []
    out = []
    for p in sorted(SNAP_DIR.glob("*_dataset_metadata.json")):
        try:
            out.append(json.loads(p.read_text(encoding="utf-8")))
        except Exception:
            pass
    return out


# ------------------------------------------------------------------ 你用過哪些 dataset（complete/ 的 expression 對欄位→dataset）
def touched_datasets() -> dict[str, int]:
    """{dataset: 用過幾支}。欄位→dataset 對照來自 data/latest/<key>/data_fields.json；expression 來自 DB/AlphaDB/complete/ 的 payload.regular。只讀本機。"""
    f2d: dict[str, str] = {}
    for d in paths.synced_data_dirs():
        try:
            for ds, ids in json.loads((d / "data_fields.json").read_text(encoding="utf-8")).items():
                for fid in ids:
                    f2d.setdefault(fid, ds)
        except Exception:
            continue
    used: dict[str, int] = defaultdict(int)
    if f2d and paths.OM.COMPLETE.exists():
        for p in paths.OM.COMPLETE.iterdir():
            try:
                regular = (json.loads(p.read_text(encoding="utf-8")).get("payload") or {}).get("regular") or ""
            except Exception:
                continue
            for ds in {f2d[tok] for tok in set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", regular)) if tok in f2d}:
                used[ds] += 1
    return dict(used)


# ------------------------------------------------------------------ 優先順序
def _index(snap: dict) -> dict[tuple[str, str], dict]:
    return {(key, ds["id"]): ds for key, lst in snap["data"].items() for ds in lst}


def priority(cur: dict, last: dict | None) -> dict:
    w = load_weights()
    used = touched_datasets()
    last_idx = _index(last) if last else {}
    last_ids = {ds_id for (_, ds_id) in last_idx}
    per_key: dict[str, list[dict]] = {}
    for key, lst in cur["data"].items():
        rows = []
        for ds in lst:
            prev = last_idx.get((key, ds["id"]))
            change = None
            if prev is not None and (prev.get("alphaCount") or 0) > 0:
                change = round((ds["alphaCount"] - prev["alphaCount"]) / prev["alphaCount"] * 100, 1)
            is_new = bool(last) and ds["id"] not in last_ids
            rows.append({**ds, "alpha_change_pct": change, "alpha_change_abs": (ds["alphaCount"] - prev["alphaCount"]) if prev else None,
                         "is_new": is_new, "used_by_me": used.get(ds["id"], 0)})
        # 加權分數：pyramid × w ＋ 變化% × w ＋ 新 × w（各自正規化到 0～1）
        max_pm = max((r["pyramidMultiplier"] for r in rows), default=1.0)
        max_ch = max((r["alpha_change_pct"] for r in rows if r["alpha_change_pct"] is not None and r["alpha_change_pct"] > 0), default=0.0)
        for r in rows:
            pyr = (r["pyramidMultiplier"] - 1.0) / (max_pm - 1.0) if max_pm > 1.0 else 0.0
            ch = (max(0.0, r["alpha_change_pct"]) / max_ch) if (r["alpha_change_pct"] is not None and max_ch > 0) else 0.0
            r["score_parts"] = {"pyramid": round(w["pyramid"] * pyr, 1), "change": round(w["change"] * ch, 1), "new": round(w["new"] * (1.0 if r["is_new"] else 0.0), 1)}
            r["score"] = round(sum(r["score_parts"].values()), 1)
        rows.sort(key=lambda r: (-r["score"], -r["pyramidMultiplier"], -(r["alpha_change_pct"] or 0)))
        for i, r in enumerate(rows, 1):
            r["rank"] = i
        per_key[key] = rows
    # 熱力圖格子：category × key → 該格排序最前的 dataset
    cells: dict[str, dict] = {}
    for key, rows in per_key.items():
        by_cat: dict[str, list[dict]] = defaultdict(list)
        for r in rows:
            by_cat[r["category"] or "?"].append(r)
        for cat, lst in by_cat.items():
            top = lst[0]
            cells[f"{cat}|{key}"] = {"top": top["id"], "score": top["score"], "pyramid": top["pyramidMultiplier"], "change_pct": top["alpha_change_pct"],
                                     "is_new": top["is_new"], "n": len(lst),
                                     "datasets": [{k: r[k] for k in ("id", "rank", "score", "pyramidMultiplier", "alpha_change_pct", "is_new", "alphaCount", "coverage", "fieldCount", "userCount", "used_by_me")} for r in lst]}
    return {"snapshot": cur["date"], "compared_to": last["date"] if last else None, "generated_at": datetime.now().isoformat(timespec="seconds"),
            "rule": f"加權分數 = pyramid 加成×{w['pyramid']:g} + alphaCount 變化%×{w['change']:g} + 新 dataset×{w['new']:g}", "weights": w, "sync_cycle_days": SYNC_CYCLE_DAYS,
            "sync_age_days": sync_age_days(), "keys": list(per_key), "per_key": per_key, "cells": cells}


def run(refresh: bool = False) -> dict | None:
    build_snapshots(refresh)
    snaps = load_snapshots()
    if not snaps:
        return None
    rep = priority(snaps[-1], snaps[-2] if len(snaps) > 1 else None)
    paths.ensure_parent(PRIORITY)
    PRIORITY.write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    return rep


def render(rep: dict, top: int) -> str:
    out = [f"快照 {rep['snapshot']}" + (f"，跟 {rep['compared_to']} 比" if rep["compared_to"] else "（只有一份快照：變化% 與「新 dataset」這次算不出來，下次同步後才有）"),
           f"排序：{rep['rule']}"]
    age = rep.get("sync_age_days")
    if age is not None:
        out.append(f"上次同步距今 {age} 天" + ("　⚠ 超過 30 天，建議重新跑 run_data_sync.py" if age > SYNC_CYCLE_DAYS else "（週期 30 天）"))
    for key, rows in rep["per_key"].items():
        out.append(f"\n{key}（{len(rows)} 個 dataset）")
        out.append(f"  {'#':>2} {'dataset':<22} {'分數':>5} {'pyramid':>7} {'變化%':>7} {'新':>2} {'alphaCount':>10} {'cov':>5} {'欄位':>5} {'你用過':>6}  category")
        for r in rows[:top]:
            ch = "—" if r["alpha_change_pct"] is None else f"{r['alpha_change_pct']:+.1f}"
            mine = f"{r['used_by_me']} 支" if r.get("used_by_me") else ""
            out.append(f"  {r['rank']:>2} {r['id']:<22} {r['score']:>5} {r['pyramidMultiplier']:>7} {ch:>7} {'🆕' if r['is_new'] else '':>2} {r['alphaCount']:>10} {r['coverage']:>5} {r['fieldCount']:>5} {mine:>6}  {r['category']}")
    out.append(f"\n[存檔] {paths.rel(PRIORITY)}；圖鑑頁重跑 guide_page.py 會更新")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description="Dataset Priority（本機快照）")
    ap.add_argument("--top", type=int, default=5)
    ap.add_argument("--refresh", action="store_true", help="重建所有快照")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    if args.list:
        for s in load_snapshots():
            print(f"  {s['date']}  來源 {s['source']}  站 {', '.join(s['data'])}")
        return 0
    rep = run(args.refresh)
    if rep is None:
        print("本機沒有同步資料（DB/ResearchDB/data/ 沒有日期資料夾或 latest/）→ 先跑 python run_data_sync.py")
        return 2
    print(json.dumps(rep, ensure_ascii=False, indent=1) if args.json else render(rep, args.top))
    return 0


if __name__ == "__main__":
    sys.exit(main())
