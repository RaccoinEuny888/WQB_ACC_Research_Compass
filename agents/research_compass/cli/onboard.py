"""新手引導 A 段的進度檢查與待辦（唯讀檢查；只寫 agents/workspace/）。

  python agents/research_compass/cli/onboard.py status [--json]     # 檢查 A1～A7，回報目前在哪一步
  python agents/research_compass/cli/onboard.py mark A3              # 使用者回報完成（A3 Telegram 無法自動判斷）
  python agents/research_compass/cli/onboard.py todo add "想用 Telegram 查剩餘模擬額度"
  python agents/research_compass/cli/onboard.py todo list
  python agents/research_compass/cli/onboard.py asked "機器是怎麼運作的"   # 記錄使用者問過的延伸問題
  python agents/research_compass/cli/onboard.py card add "分析師資料" --lane 方向待定 [--note "…"]   # 專案管理頁的卡
  python agents/research_compass/cli/onboard.py card move "分析師資料" --lane 研究中
  python agents/research_compass/cli/onboard.py card list
  python agents/research_compass/cli/onboard.py close my_first_ga --regular ID1,ID2 --power-pool ID1   # 羅盤讀完 sample_alphalist_parser.py 的 CSV 後呼叫

專案管理頁四條泳道：方向待定 → 研究中 → 模擬中 → 結案。research_process/ 裡的每條研究自動出現在「模擬中」
（跑完的標「跑完了」）；前兩條泳道的卡由羅盤用 card add/move 記；羅盤讀 sample_alphalist_parser.py 的結果後用 close 把可交的 alpha ID 記進卡並移到「結案」。

不讀 .env／session.pkl／login_time.pkl 的內容：.env 只看檔案是否存在，登入只看 login_time.pkl 的檔案時間。
"""
from __future__ import annotations

import argparse
import json
import platform
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from agents.common import paths  # noqa: E402

PROGRESS = paths.WORKSPACE / "compass_progress.json"
STEPS = [("A1", "裝好 Python 環境"), ("A2", "填入帳號"), ("A3", "接上 Telegram"),
         ("A4", "打開 worker 並登入"), ("A5", "啟動第一次 GA"), ("A6", "看懂第一次的結果"),
         ("A7", "認識專案管理")]
LOGIN_VALID_HOURS = 4
LANES = [("方向待定", "有想研究的念頭，但還沒決定要用哪個 dataset 或 template"),
         ("研究中", "dataset 或 template 已經決定，正在設計 expression／template"),
         ("模擬中", "GA 正在跑或剛跑完，等結果、看結果"),
         ("結案", "結果看過了；能交的 alpha ID 記在卡上（regular／Power Pool）")]
LANE_IDS = [l for l, _ in LANES]


def load_progress() -> dict:
    if PROGRESS.exists():
        try:
            p = json.loads(PROGRESS.read_text(encoding="utf-8"))
            # 2026-11-20 路線改名 B1～B5 → R1～R5：舊進度檔的標記照樣算數
            p["marked"] = {(("R" + k[1:]) if re.fullmatch(r"B[1-5]-\d", k) else k): v for k, v in p.get("marked", {}).items()}
            # 2026-11-20 R3 研究靈感＋R4 設計 template 合併成 R3、R5 改成 R4：舊標記搬到新編號（只有這兩個是靠 mark 的）
            if p.get("route_version", 1) < 2:
                old = p["marked"]
                p["marked"] = {{"R4-1": "R3-1", "R5-2": "R4-2"}.get(k, k): v for k, v in old.items()}
                p["route_version"] = 2
            return p
        except Exception:
            pass
    return {"marked": {}, "todos": [], "asked": [], "started_at": None, "route_version": 2}


def save_progress(p: dict) -> None:
    paths.ensure_parent(PROGRESS)
    PROGRESS.write_text(json.dumps(p, ensure_ascii=False, indent=2), encoding="utf-8")


def _memory() -> dict:
    info = {"os": platform.system(), "ram_gb": None, "swap_gb": None, "low_memory_vm": False}
    try:
        if info["os"] == "Linux":
            mem = {}
            for line in Path("/proc/meminfo").read_text().splitlines():
                k, v = line.split(":", 1)
                mem[k] = int(v.strip().split()[0])   # kB
            info["ram_gb"] = round(mem.get("MemTotal", 0) / 1024 / 1024, 1)
            info["swap_gb"] = round(mem.get("SwapTotal", 0) / 1024 / 1024, 1)
            info["low_memory_vm"] = info["ram_gb"] <= 2.5 and info["swap_gb"] == 0
        elif info["os"] == "Darwin":
            out = subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True).stdout.strip()
            info["ram_gb"] = round(int(out) / 1024 ** 3, 1) if out else None
    except Exception:
        pass
    return info


def _count(folder: Path) -> int:
    return len([p for p in folder.iterdir() if not p.name.startswith(".")]) if folder.exists() else 0


def _research_lines() -> list[dict]:
    """每條研究：跑到第幾代（check_point）、有幾代的 alphalist、分析做好了沒。只讀 JSON 與檔名，不開 pickle。"""
    out = []
    rp = paths.OM.RESEARCH_PROCESS
    if not rp.exists():
        return out
    for d in sorted(rp.iterdir()):
        if not d.is_dir() or d.name.startswith("."):
            continue
        g = None
        cp = d / "check_point"
        if cp.exists():
            try:
                g = json.loads(cp.read_text(encoding="utf-8")).get("g")
            except Exception:
                pass
        n_gen = len(list(d.glob("alphalist_*")))
        summary = d / "analysis" / "experiment_summary.json"
        out.append({"name": d.name, "generation": g if g is not None else n_gen, "n_alphalists": n_gen,
                    "analysis_done": summary.exists(),
                    "updated_at": datetime.fromtimestamp(d.stat().st_mtime).isoformat(timespec="minutes")})
    return out


def hypothesis_cards() -> list[dict]:
    """占卜家的假說卡（DB/ResearchDB/hypothesis/H-*.md）；沒裝占卜家就是空的。只讀 frontmatter。"""
    try:
        from agents.common import card as card_mod
        return card_mod.all_cards()
    except Exception:
        return []


# 假說卡的 status → 泳道（validated／abandoned／rejected 不上看板）
HYPO_LANE = {"draft": "方向待定", "self_checked": "研究中", "under_review": "研究中", "approved": "研究中", "conditional": "研究中",
             "needs_work": "研究中", "unreviewed": "研究中", "expr_ready": "研究中", "simulating": "模擬中", "expr_self_checked": "研究中",
             "expr_approved": "研究中", "template_approved": "模擬中", "ga_running": "模擬中"}


def lanes(prog: dict, lines: list[dict]) -> list[dict]:
    """專案管理頁：四條泳道。research_process 的研究自動進「模擬中」；占卜家的假說卡依 status 自動放；羅盤記的卡依 lane 放。"""
    cards = {l: [] for l in LANE_IDS}
    manual = prog.get("cards", [])
    manual_titles = {c["title"] for c in manual}
    for hc in hypothesis_cards():
        lane = HYPO_LANE.get(str(hc.get("status")))
        if not lane or hc.get("id") in manual_titles:
            continue
        conf = hc.get("confidence")
        cards[lane].append({"title": f"{hc.get('id')}　{str(hc.get('hypothesis', ''))[:40]}", "auto": True, "kind": "hypothesis",
                            "note": f"假說卡 · {hc.get('status')}" + (f" · 信心 {conf}/10" if conf is not None else "") + (f" · {hc.get('dataset')}" if hc.get("dataset") else ""),
                            "at": str(hc.get("created", ""))[:10], "status": str(hc.get("status")), "card_id": str(hc.get("id"))})
    for c in manual:
        if c.get("lane") in cards and not c.get("done"):
            cards[c["lane"]].append({"title": c["title"], "note": c.get("note", ""), "at": c.get("added_at", "")[:10], "auto": False,
                                     "regular_ids": c.get("regular_ids", []), "power_pool_ids": c.get("power_pool_ids", [])})
    for ln in lines:
        if ln["name"] in manual_titles:
            continue
        note = f"分析做好了（跑了 {ln['n_alphalists']} 代）" if ln["analysis_done"] else f"跑到第 {ln['generation']} 代"
        cards["模擬中"].append({"title": ln["name"], "note": note, "at": ln["updated_at"][:10], "auto": True,
                               "status": "跑完了" if ln["analysis_done"] else "進行中"})
    return [{"lane": l, "desc": desc, "cards": cards[l]} for l, desc in LANES]


B1_STEPS = [("R1-1", "同步 dataset、看推薦"), ("R1-2", "Dataset 語意分群")]
ROUTES = [("R1", "選 dataset"), ("R2", "認識 operator"), ("R3", "設計 template"), ("R4", "調 scorer")]
# 四條路的小步（R1 另在 B1_STEPS）
ROUTE_STEPS = {
    "R2": [("R2-1", "operator 倉庫"), ("R2-2", "custom operator")],
    "R3": [("R3-1", "template 怎麼設計"), ("R3-2", "加裝占卜家"), ("R3-3", "用 /hypothesis 建第一張假說卡")],
    "R4": [("R4-1", "看懂現在的 scorer"), ("R4-2", "scorer 調整方向")],
}
SUBDATASET = paths.OM.DATA / "subdataset"


def profiles() -> list[dict]:
    out = []
    for p in sorted(SUBDATASET.glob("*_profile.json")) if SUBDATASET.exists() else []:
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            out.append({"dataset": d.get("dataset"), "key": d.get("key"), "n_groups": len(d.get("groups") or []),
                        "field_total": d.get("field_total"), "generated": d.get("generated"), "path": paths.rel(p)})
        except Exception:
            pass
    return out


def b_status(prog: dict, lines: list[dict]) -> dict:
    """B 段：R1～R4 每條路的小步，自動判斷或 mark。"""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import dataset_snapshot  # noqa: E402
    synced = [d.name for d in paths.synced_data_dirs()]
    age = dataset_snapshot.sync_age_days()
    stale = age is not None and age > dataset_snapshot.SYNC_CYCLE_DAYS
    pr = None
    if dataset_snapshot.PRIORITY.exists():
        try:
            pr = json.loads(dataset_snapshot.PRIORITY.read_text(encoding="utf-8"))
        except Exception:
            pr = None
    folders = dataset_snapshot.sync_folders()
    latest_date = folders[-1][0] if folders else None
    pr_fresh = bool(pr) and pr.get("snapshot") == latest_date
    profs = profiles()
    done = {"R1-1": bool(synced) and pr_fresh, "R1-2": bool(profs)}
    # 地圖頁左側只放短字；詳細的站清單在 status 的 synced
    why = {
        "R1-1": ("已同步" + ("（超過 30 天，建議重跑）" if stale else "")) if done["R1-1"]
                else ("已同步，還沒算推薦" if synced else "還沒同步"),
        "R1-2": f"已分析 {len(profs)} 個 dataset" if profs else "還沒分析",
    }
    b1_current = next((s for s, _ in B1_STEPS if not done[s]), None)
    marked = prog.get("marked", {})
    # R2：索引是用「使用者的清單＋使用者定的分群」建的（operator_groups.json 存在且索引已分類）
    op_groups = (paths.AGENTS / "workspace" / "operator_groups.json").exists()
    op_index, n_assigned, n_ops = False, 0, 0
    oi = paths.OUT.INDEX / "operator_index.json"
    if oi.exists() and op_groups:
        try:
            d = json.loads(oi.read_text(encoding="utf-8"))
            n_assigned, n_ops = int(d.get("n_assigned", 0)), int(d.get("n_operators", 0))
            op_index = "scheme_source" in d and n_assigned > 0
        except Exception:
            op_index = False
    # R2-2 custom operator 是說明，看過就算完成（羅盤講完就 mark）
    done.update({"R2-1": op_index, "R2-2": bool(marked.get("R2-2"))})
    why.update({"R2-1": f"已分類 {n_assigned}/{n_ops} 個" if op_index else ("有分群表，還沒分類" if op_groups else "還沒分類"),
                "R2-2": "看過了" if marked.get("R2-2") else "還沒看"})
    # R3 設計 template：自己的 template＋第二條研究（或 mark）；占卜家裝了沒（或說先不裝）；有沒有假說卡（或說先不裝）
    tpls = [p.name for p in paths.OM.TEMPLATE.glob("*.json") if p.name != "default_template.json"] if paths.OM.TEMPLATE.exists() else []
    own_ga = bool(tpls) and len(lines) >= 2
    seer = (paths.ROOT / ".claude" / "skills" / "hypothesis" / "SKILL.md").exists()
    hcards = hypothesis_cards()
    done.update({"R3-1": own_ga or bool(marked.get("R3-1")), "R3-2": seer or bool(marked.get("R3-2")), "R3-3": bool(hcards) or bool(marked.get("R3-3"))})
    why.update({"R3-1": (f"自己的 template：{', '.join(tpls[:3])}" if own_ga else ("使用者說讀完了" if marked.get("R3-1") else
                         (f"有 template（{', '.join(tpls[:3])}）但還沒起第二條 GA" if tpls else "還沒有自己的 template"))),
                "R3-2": "占卜家已安裝" if seer else ("先不裝" if marked.get("R3-2") else "還沒裝占卜家"),
                "R3-3": (f"{len(hcards)} 張假說卡" if hcards else ("先不裝" if marked.get("R3-3") else "還沒有假說卡"))})
    # R4 調 scorer：兩步都是說明，羅盤講過就 mark（看過就算完成）
    done.update({"R4-1": bool(marked.get("R4-1")), "R4-2": bool(marked.get("R4-2"))})
    why.update({"R4-1": "看過了" if marked.get("R4-1") else "還沒看",
                "R4-2": "看過了" if marked.get("R4-2") else "還沒看"})
    routes = [{"id": "R1", "name": "選 dataset", "done": done["R1-2"], "why": "走完" if done["R1-2"] else (f"在 {b1_current}" if b1_current else ""), "available": True,
               "steps": [{"id": s, "name": n, "done": done[s], "why": why[s]} for s, n in B1_STEPS]}]
    for rid, name in ROUTES[1:]:
        steps = ROUTE_STEPS[rid]
        avail = True
        st_rows = [{"id": s, "name": n, "done": bool(done.get(s)), "why": why.get(s, "實作中")} for s, n in steps]
        r_done = avail and all(x["done"] for x in st_rows)
        r_cur = next((x["id"] for x in st_rows if not x["done"]), None) if avail else None
        routes.append({"id": rid, "name": name, "done": r_done, "why": ("走完" if r_done else (f"在 {r_cur}" if r_cur else "")) if avail else "實作中",
                       "available": avail, "steps": st_rows})
    all_done = all(r["done"] for r in routes)
    return {"steps": [{"id": s, "name": n, "done": done[s], "why": why[s]} for s, n in B1_STEPS],
            "mainline": ["R1", "R3", "R4"],
            "all_done": all_done,
            "current": b1_current, "routes": routes, "synced": synced, "sync_age_days": age, "sync_stale": stale,
            "priority": {"exists": bool(pr), "fresh": pr_fresh, "snapshot": pr.get("snapshot") if pr else None,
                         "compared_to": pr.get("compared_to") if pr else None},
            "profiles": profs}


def check() -> dict:
    prog = load_progress()
    root = paths.ROOT
    venv = (root / ".venv").exists()
    env_file = (root / ".env").exists()
    lt = root / "login_time.pkl"
    login_age_h = round((time.time() - lt.stat().st_mtime) / 3600, 1) if lt.exists() else None
    n_complete = _count(paths.OM.COMPLETE)
    n_pending = _count(paths.OM.PENDING)
    n_running = _count(paths.OM.RUNNING)
    line_info = _research_lines()
    lines = [x["name"] for x in line_info]
    ga_cfg = {}
    cfg_p = paths.OM.GA_CONFIG / "default_ga_config.json"
    if cfg_p.exists():
        try:
            ga_cfg = json.loads(cfg_p.read_text(encoding="utf-8"))
        except Exception:
            pass
    marked = prog.get("marked", {})
    done = {
        "A1": venv,
        "A2": env_file,
        # Telegram：使用者回報；若 worker 已登入過（要靠 Telegram /refresh 才登得進去）也視為完成
        "A3": bool(marked.get("A3")) or lt.exists() or n_complete > 0,
        "A4": (login_age_h is not None and login_age_h < LOGIN_VALID_HOURS) or n_complete > 0 or bool(marked.get("A4")),
        "A5": len(lines) > 0 or bool(marked.get("A5")),
        "A6": any(x["analysis_done"] for x in line_info) or bool(marked.get("A6")),
        # 專案管理介紹：羅盤在開場講過就 mark；也是「第一次見面」的判斷
        "A7": bool(marked.get("A7")),
    }
    running = [x for x in line_info if not x["analysis_done"]]
    why = {
        "A1": ".venv/ 存在" if venv else "找不到 .venv/",
        "A2": ".env 檔存在（未讀內容）" if env_file else "找不到 .env",
        "A3": ("使用者回報完成" if marked.get("A3") else "已有登入或模擬紀錄，代表 Telegram 可用") if done["A3"] else "尚未回報 Telegram 設定完成",
        "A4": (f"登入紀錄 {login_age_h} 小時前" if login_age_h is not None else "尚無登入紀錄") + f"；complete/ 有 {n_complete} 筆",
        "A5": f"research_process/ 有 {len(lines)} 條研究" if lines else "research_process/ 還沒有研究",
        "A6": ("analysis/ 已有產出" if done["A6"] else
               ("、".join(f"{x['name']} 跑到第 {x['generation']} 代" for x in running) + "；分析還沒產出" if running else "還沒有研究可以看")),
        "A7": "開場已介紹過" if done["A7"] else "還沒介紹過（第一次見面）",
    }
    current = next((s for s, _ in STEPS if not done[s]), None)
    b = b_status(prog, line_info) if current is None else None
    est = None
    if ga_cfg.get("kid_num") and ga_cfg.get("generation_num"):
        est = int(ga_cfg["kid_num"]) * int(ga_cfg["generation_num"])
    return {
        "checked_at": datetime.now().isoformat(timespec="seconds"),
        "steps": [{"id": s, "name": n, "done": done[s], "why": why[s]} for s, n in STEPS],
        "current": current, "phase": "A" if current else "B",
        "b": b,
        "n_done": sum(done.values()), "n_total": len(STEPS),
        "login": {"age_hours": login_age_h, "valid": login_age_h is not None and login_age_h < LOGIN_VALID_HOURS},
        "queues": {"pending": n_pending, "running": n_running, "complete": n_complete},
        "research_lines": lines,
        "research_detail": line_info,
        "lanes": lanes(prog, line_info),
        "ga_config": {k: ga_cfg.get(k) for k in ("parent_num", "kid_num", "generation_num", "arc_layer")},
        "ga_estimated_simulations": est,
        "ga_suggested": {"parent_num": 5, "kid_num": 30, "generation_num": 3, "arc_layer": False},
        "memory": _memory(),
        "todos": prog.get("todos", []), "asked": prog.get("asked", []),
    }


def render(st: dict) -> str:
    out = []
    if st["phase"] == "B":
        b = st["b"]
        out.append("機器會用、第一次結果也看過了（A1～A7 都完成）→ B 段（樞紐）。")
        mr = next((r for rid in b.get("mainline", []) for r in b["routes"] if r["id"] == rid and r["available"] and not r["done"]), None)
        ms = next((s for s in mr["steps"] if not s["done"]), None) if mr else None
        out.append(f"你在這裡：開始研究 ／ 主線 {mr['id']} {mr['name']} ／ 第 {ms['id'][-1]} 步：{ms['name']}" if (mr and ms)
                   else "你在這裡：主線都走完了；四條路隨時可以再走")
        for r in b["routes"]:
            for s in r["steps"]:
                mark = "✔" if s["done"] else ("▶" if (ms and s["id"] == ms["id"]) else "·")
                out.append(f"  {mark} {s['id']} {s['name']} — {s['why']}")
        out.append("  四條路：" + "；".join(f"{r['id']} {r['name']}（{r['why']}）" for r in b["routes"]))
    else:
        cur = next(s for s in st["steps"] if s["id"] == st["current"])
        out.append(f"你在這裡：準備機器 第 {st['current'][1]} 步／共 {st['n_total']} 步：{cur['name']}（已完成 {st['n_done']} 步）")
    for s in (st["steps"] if st["phase"] == "A" else []):
        mark = "✔" if s["done"] else ("▶" if s["id"] == st["current"] else "·")
        out.append(f"  {mark} {s['id']} {s['name']} — {s['why']}")
    m = st["memory"]
    if m.get("low_memory_vm"):
        out.append(f"  ⚠ 這台是 Linux、記憶體 {m['ram_gb']} GB、沒有 swap → 先設 swap 再開 VS Code（troubleshooting.md：OOM）")
    g = st["ga_config"]
    if any(v is not None for v in g.values()):
        out.append(f"  GA 設定：parent_num={g['parent_num']} kid_num={g['kid_num']} generation_num={g['generation_num']} arc_layer={g['arc_layer']}"
                   f" → 約 {st['ga_estimated_simulations']} 支模擬（建議 5／30／3／false）")
    q = st["queues"]
    out.append(f"  佇列：pending {q['pending']}、running {q['running']}、complete {q['complete']}；登入："
               + ("有效" if st["login"]["valid"] else ("已過期（Telegram 傳 /refresh）" if st["login"]["age_hours"] is not None else "尚未登入過")))
    for x in st["research_detail"]:
        out.append(f"  研究 {x['name']}：" + ("分析做好了" if x["analysis_done"] else f"跑到第 {x['generation']} 代，分析還沒產出"))
    if st["todos"]:
        out.append("  待辦：" + "；".join(t["text"] for t in st["todos"] if not t.get("done")))
    for lane in st["lanes"]:
        if lane["cards"]:
            out.append(f"  泳道「{lane['lane']}」：" + "；".join(c["title"] + (f"（{c['note']}）" if c.get("note") else "") for c in lane["cards"]))
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description="新手引導 A 段")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("status"); s.add_argument("--json", action="store_true")
    m = sub.add_parser("mark"); m.add_argument("step", choices=[x for x, _ in STEPS] + [s for v in ROUTE_STEPS.values() for s, _ in v] + [s for s, _ in B1_STEPS]); m.add_argument("--undo", action="store_true")
    t = sub.add_parser("todo"); t.add_argument("action", choices=["add", "list", "done"]); t.add_argument("text", nargs="?")
    a = sub.add_parser("asked"); a.add_argument("text")
    c = sub.add_parser("card"); c.add_argument("action", choices=["add", "move", "done", "list"]); c.add_argument("title", nargs="?")
    c.add_argument("--lane", choices=LANE_IDS); c.add_argument("--note", default="")
    cl = sub.add_parser("close"); cl.add_argument("title"); cl.add_argument("--regular", default=""); cl.add_argument("--power-pool", dest="power_pool", default="")
    args = ap.parse_args()
    prog = load_progress()
    if not prog.get("started_at"):
        prog["started_at"] = datetime.now().isoformat(timespec="seconds"); save_progress(prog)

    if args.cmd == "status":
        st = check()
        print(json.dumps(st, ensure_ascii=False, indent=2) if args.json else render(st))
    elif args.cmd == "mark":
        prog.setdefault("marked", {})
        if args.undo:
            prog["marked"].pop(args.step, None)
        else:
            prog["marked"][args.step] = datetime.now().isoformat(timespec="seconds")
        save_progress(prog); print(f"[mark] {args.step} {'取消' if args.undo else '完成'}")
    elif args.cmd == "todo":
        prog.setdefault("todos", [])
        if args.action == "add":
            if not args.text:
                print("要給待辦內容"); return 1
            prog["todos"].append({"text": args.text, "added_at": datetime.now().isoformat(timespec="seconds"), "done": False})
            save_progress(prog); print(f"[todo] 已記錄：{args.text}")
        elif args.action == "done":
            for x in prog["todos"]:
                if args.text and args.text in x["text"]:
                    x["done"] = True
            save_progress(prog); print("[todo] 已更新")
        else:
            if not prog["todos"]:
                print("（沒有待辦）")
            for x in prog["todos"]:
                print(f"  {'✔' if x.get('done') else '·'} {x['text']}（{x['added_at'][:10]}）")
    elif args.cmd == "asked":
        prog.setdefault("asked", []).append({"text": args.text, "at": datetime.now().isoformat(timespec="seconds")})
        save_progress(prog); print("[asked] 已記錄")
    elif args.cmd == "close":
        # 羅盤用：把一條研究的可交 alpha ID 記進卡、移到「結案」（沒有卡就建一張）
        cards = prog.setdefault("cards", [])
        now = datetime.now().isoformat(timespec="seconds")
        hit = next((x for x in cards if x["title"] == args.title), None)
        reg = [x for x in (args.regular or "").split(",") if x]
        pp = [x for x in (args.power_pool or "").split(",") if x]
        note = f"regular {len(reg)} 支、Power Pool {len(pp)} 支"
        if not hit:
            hit = {"title": args.title, "lane": "結案", "note": note, "added_at": now, "history": [], "done": False}
            cards.append(hit)
        hit.update({"lane": "結案", "note": note, "regular_ids": reg, "power_pool_ids": pp, "closed_at": now})
        hit.setdefault("history", []).append({"lane": "結案", "at": now})
        save_progress(prog); print(f"[card] {args.title} → 「結案」：{note}")
    elif args.cmd == "card":
        cards = prog.setdefault("cards", [])
        now = datetime.now().isoformat(timespec="seconds")
        if args.action == "list":
            for lane in lanes(prog, _research_lines()):
                print(f"{lane['lane']}（{lane['desc']}）")
                for x in lane["cards"]:
                    print(f"  · {x['title']}" + (f" — {x['note']}" if x.get("note") else "") + ("　[自動]" if x.get("auto") else ""))
            return 0
        if not args.title:
            print("要給卡的名稱"); return 1
        hit = next((x for x in cards if x["title"] == args.title), None)
        if args.action == "add":
            if hit:
                print(f"[card] 已有同名的卡（在「{hit['lane']}」）"); return 1
            cards.append({"title": args.title, "lane": args.lane or "方向待定", "note": args.note, "added_at": now,
                          "history": [{"lane": args.lane or "方向待定", "at": now}], "done": False})
            save_progress(prog); print(f"[card] 已放到「{args.lane or '方向待定'}」：{args.title}")
        elif args.action == "move":
            if not hit or not args.lane:
                print("找不到這張卡，或沒給 --lane"); return 1
            hit["lane"] = args.lane; hit.setdefault("history", []).append({"lane": args.lane, "at": now})
            if args.note:
                hit["note"] = args.note
            save_progress(prog); print(f"[card] {args.title} → 「{args.lane}」")
        elif args.action == "done":
            if not hit:
                print("找不到這張卡"); return 1
            hit["done"] = True; save_progress(prog); print(f"[card] {args.title} 已結案")
    return 0


if __name__ == "__main__":
    sys.exit(main())
