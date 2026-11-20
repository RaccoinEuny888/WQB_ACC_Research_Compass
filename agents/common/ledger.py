"""研究帳本：DB/ResearchDB/hypothesis/ledger.jsonl，append-only。

用法：
  python agents/common/ledger.py append --actor seer --event card_created --card H-261115-003 \
      --payload '{"origin":"paper","hypothesis":"..."}' --files DB/ResearchDB/hypothesis/H-261115-003.md
  python agents/common/ledger.py query [--card H-261115-003] [--event review_issued] [--last 20]
  python agents/common/ledger.py summary

事件（actor）：
  card_created(seer) literature_collected(seer) rejected_by_seer(seer) review_issued(inquisitor)
  card_revised(seer) idea_written(seer|user) syntax_checked(seer|inquisitor) hashes_linked(user)
  results_found(inquisitor) template_built(seer) ga_command_issued(seer) run_linked(compass|user)
  status_changed(任一) note(user)
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from agents.common import paths  # noqa: E402

EVENTS = {
    "card_created", "literature_collected", "rejected_by_seer", "review_issued", "card_revised",
    "idea_written", "syntax_checked", "hashes_linked", "results_found", "template_built",
    "ga_command_issued", "run_linked", "status_changed", "note",
    # SPC 通道
    "spc_universe_built", "spc_prompt_built", "spc_pretest", "spc_runs_validated",
    "spc_submitted", "spc_weight_changed", "spc_status_checked",
}
ACTORS = {"seer", "inquisitor", "compass", "user"}
TZ = timezone(timedelta(hours=8))


def now_iso() -> str:
    return datetime.now(TZ).isoformat(timespec="seconds")


def append(actor: str, event: str, card_id: str | None = None,
           payload: dict | None = None, files: list[str] | None = None) -> dict:
    if actor not in ACTORS:
        raise ValueError(f"actor 必須是 {sorted(ACTORS)}")
    if event not in EVENTS:
        raise ValueError(f"event 必須是 {sorted(EVENTS)}")
    rec = {"ts": now_iso(), "actor": actor, "event": event, "card_id": card_id,
           "payload": payload or {}, "files": files or []}
    paths.ensure_parent(paths.OUT.LEDGER)
    with open(paths.OUT.LEDGER, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def read_all() -> list[dict]:
    if not paths.OUT.LEDGER.exists():
        return []
    out = []
    with open(paths.OUT.LEDGER, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return out


def query(card_id: str | None = None, event: str | None = None, last: int | None = None) -> list[dict]:
    recs = [r for r in read_all()
            if (card_id is None or r.get("card_id") == card_id)
            and (event is None or r.get("event") == event)]
    return recs[-last:] if last else recs


def summary() -> dict:
    recs = read_all()
    by_event = Counter(r["event"] for r in recs)
    per_card: dict[str, dict] = defaultdict(lambda: {
        "events": 0, "ideas_written": 0, "n_expressions": 0, "reviews": Counter(),
        "revisions": 0, "last_ts": None, "last_event": None})
    for r in recs:
        cid = r.get("card_id")
        if not cid:
            continue
        c = per_card[cid]
        c["events"] += 1
        c["last_ts"], c["last_event"] = r["ts"], r["event"]
        if r["event"] == "idea_written":
            c["ideas_written"] += 1
            c["n_expressions"] += len(r.get("payload", {}).get("roles", []) or [])
        elif r["event"] == "review_issued":
            c["reviews"][f'{r["payload"].get("stage", "?")}:{r["payload"].get("verdict", "?")}'] += 1
        elif r["event"] == "card_revised":
            c["revisions"] += 1
    for c in per_card.values():
        c["reviews"] = dict(c["reviews"])
    return {"n_events": len(recs), "by_event": dict(by_event), "per_card": dict(per_card)}


def _main() -> int:
    ap = argparse.ArgumentParser(description="研究帳本")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("append")
    a.add_argument("--actor", required=True, choices=sorted(ACTORS))
    a.add_argument("--event", required=True, choices=sorted(EVENTS))
    a.add_argument("--card", default=None)
    a.add_argument("--payload", default="{}", help="JSON 字串")
    a.add_argument("--files", default="", help="逗號分隔")
    q = sub.add_parser("query")
    q.add_argument("--card", default=None)
    q.add_argument("--event", default=None)
    q.add_argument("--last", type=int, default=None)
    sub.add_parser("summary")
    args = ap.parse_args()

    if args.cmd == "append":
        rec = append(args.actor, args.event, args.card, json.loads(args.payload),
                     [x for x in args.files.split(",") if x])
        print(json.dumps(rec, ensure_ascii=False))
    elif args.cmd == "query":
        for r in query(args.card, args.event, args.last):
            print(json.dumps(r, ensure_ascii=False))
    else:
        print(json.dumps(summary(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(_main())
