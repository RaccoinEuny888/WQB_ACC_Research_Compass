"""假說卡（DB/ResearchDB/hypothesis/<card_id>.md）的讀寫、狀態與版本。

用法：
  python agents/common/card.py new-id                          # 下一個卡號 H-YYMMDD-NNN
  python agents/common/card.py show H-261115-003               # frontmatter → JSON
  python agents/common/card.py list [--status approved]        # 所有卡一覽
  python agents/common/card.py validate H-261115-003           # 必填欄位與四關段落是否齊全
  python agents/common/card.py set-status H-261115-003 approved --actor inquisitor --reason "stage=card 讚美女神"
  python agents/common/card.py bump-version H-261115-003 --actor seer --reason "依教條 #1 拿掉 trade_when"

卡片格式見 agents/common/knowledge/four_gates.md 與設計文件 §3.2。
frontmatter 只支援「key: 純量」與「key: [a, b]」兩種寫法，刻意不依賴 PyYAML。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from agents.common import paths, ledger  # noqa: E402

STATUSES = [
    "draft", "rejected_by_seer", "self_checked", "under_review", "approved", "conditional", "needs_work", "rejected",
    "expr_ready", "simulating", "expr_self_checked", "expr_approved", "template_approved", "ga_running",
    "validated", "abandoned", "unreviewed",
]
# self_checked＝占卜家自檢過、未送審（v2 預設）；needs_work＝審判官要求修改但沒說機制錯；rejected 只給「機制被證偽」。
# expr_self_checked＝沒有審判官時，模擬結果過了 self_check.py（main Sharpe>1、turnover<0.5、K1、K2）。
CHANNELS = ("alpha", "spc", "both")
REQUIRED_KEYS = ["id", "hypothesis", "direction", "status", "version", "created", "origin",
                 "dataset", "region", "universe", "delay", "mechanism_tag"]
REQUIRED_SECTIONS = ["# 文獻", "# 第 1 關", "# 第 2 關", "# 第 3 關", "# 第 4 關", "4.3", "4.4", "4.5", "# 版本紀錄"]
CARD_ID_RE = re.compile(r"^H-(\d{6})-(\d{3})$")


# ------------------------------------------------------------------ frontmatter
def _parse_scalar(s: str):
    s = s.strip()
    if s in ("null", "~", ""):
        return None
    if s.lower() in ("true", "false"):
        return s.lower() == "true"
    if re.fullmatch(r"-?\d+", s):
        return int(s)
    if re.fullmatch(r"-?\d+\.\d+", s):
        return float(s)
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
        return s[1:-1]
    return s


def _parse_value(s: str):
    s = s.strip()
    if s.startswith("[") and s.endswith("]"):
        inner = s[1:-1].strip()
        return [] if not inner else [_parse_scalar(x) for x in inner.split(",")]
    return _parse_scalar(s)


def _dump_value(v) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, list):
        return "[" + ", ".join(_dump_value(x) for x in v) + "]"
    if isinstance(v, str) and (":" in v or v.strip() != v or v == ""):
        return json.dumps(v, ensure_ascii=False)
    return str(v)


def split_card(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        return {}, text
    parts = text.split("\n---", 1)
    head = parts[0][3:]
    body = parts[1][1:] if len(parts) > 1 else ""
    fm: dict = {}
    for line in head.splitlines():
        line = line.split(" #", 1)[0].rstrip()
        if not line.strip() or ":" not in line:
            continue
        k, v = line.split(":", 1)
        fm[k.strip()] = _parse_value(v)
    return fm, body


def join_card(fm: dict, body: str) -> str:
    lines = ["---"] + [f"{k}: {_dump_value(v)}" for k, v in fm.items()] + ["---"]
    return "\n".join(lines) + "\n" + body.lstrip("\n")


def read_card(card_id: str) -> tuple[Path, dict, str]:
    p = paths.card_path(card_id) if not Path(card_id).exists() else Path(card_id)
    if not p.exists():
        raise FileNotFoundError(f"找不到假說卡：{paths.rel(p)}")
    text = p.read_text(encoding="utf-8")
    fm, body = split_card(text)
    return p, fm, body


def write_card(p: Path, fm: dict, body: str) -> Path:
    paths.ensure_parent(p)
    p.write_text(join_card(fm, body), encoding="utf-8")
    return p


# ------------------------------------------------------------------ ops
def all_cards() -> list[dict]:
    out = []
    if not paths.OUT.HYPOTHESIS.exists():
        return out
    for p in sorted(paths.OUT.HYPOTHESIS.glob("H-*.md")):
        fm, _ = split_card(p.read_text(encoding="utf-8"))
        fm.setdefault("id", p.stem)
        fm["_path"] = paths.rel(p)
        fm["_mtime"] = p.stat().st_mtime
        out.append(fm)
    return out


def new_id(today: date | None = None) -> str:
    today = today or date.today()
    prefix = f"H-{today.strftime('%y%m%d')}-"
    used = set()
    for c in all_cards():
        if str(c.get("id", "")).startswith(prefix):
            used.add(int(str(c["id"])[-3:]))
    for r in ledger.read_all():
        cid = r.get("card_id") or ""
        if cid.startswith(prefix):
            used.add(int(cid[-3:]))
    n = (max(used) + 1) if used else 1
    return f"{prefix}{n:03d}"


def validate(card_id: str) -> list[dict]:
    issues = []
    try:
        p, fm, body = read_card(card_id)
    except FileNotFoundError as e:
        return [{"level": "ERROR", "message": str(e)}]
    for k in REQUIRED_KEYS:
        if k not in fm or fm[k] in (None, ""):
            issues.append({"level": "ERROR", "message": f"frontmatter 缺 {k}"})
    if fm.get("status") not in STATUSES:
        issues.append({"level": "ERROR", "message": f"status 不合法：{fm.get('status')}（合法：{STATUSES}）"})
    if "confidence" in fm:
        try:
            c = int(fm["confidence"])
            if not 1 <= c <= 10:
                raise ValueError
        except (TypeError, ValueError):
            issues.append({"level": "ERROR", "message": f"confidence 要是 1～10 的整數：{fm.get('confidence')}"})
    elif fm.get("status") == "self_checked":
        issues.append({"level": "WARN", "message": "status 是 self_checked 但沒有 confidence（總分 1～10）"})
    if fm.get("direction") not in ("long", "short", "both"):
        issues.append({"level": "ERROR", "message": "direction 必須是 long / short / both"})
    if fm.get("channel", "alpha") not in CHANNELS:
        issues.append({"level": "ERROR", "message": f"channel 必須是 {CHANNELS}（alpha＝expression／GA 通道；spc＝Systematic Predictions Challenge prompt）"})
    if "channel" not in fm:
        issues.append({"level": "WARN", "message": "frontmatter 沒有 channel，視為 alpha；4.4 應提議 alpha / spc / both"})
    if fm.get("id") and not CARD_ID_RE.match(str(fm["id"])):
        issues.append({"level": "ERROR", "message": f"id 格式應為 H-YYMMDD-NNN：{fm['id']}"})
    for s in REQUIRED_SECTIONS:
        if s not in body:
            issues.append({"level": "ERROR", "message": f"缺段落：{s}"})
    for tag in ("反向證偽", "naive"):
        if tag not in body:
            issues.append({"level": "ERROR", "message": f"第 4 關缺對照組說明：{tag}"})
    for tag, msg in (("horizon", "4.4 缺 signal horizon（看多長）"), ("真的壞掉", "4.2 失效條件要分：強／弱但正常／真的壞掉")):
        if tag not in body:
            issues.append({"level": "ERROR", "message": msg})
    if not re.search(r"\[(L|H|O|R|\?)\]", body):
        issues.append({"level": "WARN", "message": "全文沒有任何證據標籤 [L]/[H]/[O]/[R]/[?]"})
    return issues


def set_status(card_id: str, status: str, actor: str, reason: str) -> dict:
    if status not in STATUSES:
        raise ValueError(f"status 不合法：{status}")
    p, fm, body = read_card(card_id)
    old = fm.get("status")
    fm["status"] = status
    write_card(p, fm, body)
    return ledger.append(actor, "status_changed", fm.get("id", card_id),
                         {"from": old, "to": status, "reason": reason}, [paths.rel(p)])


def bump_version(card_id: str, actor: str, reason: str) -> dict:
    p, fm, body = read_card(card_id)
    old = int(fm.get("version", 1) or 1)
    fm["version"] = old + 1
    line = f"- v{old + 1}（{date.today().isoformat()}）：{reason}\n"
    if "# 版本紀錄" in body:
        head, tail = body.split("# 版本紀錄", 1)
        nl = tail.find("\n")
        tail = tail[:nl + 1] + line + tail[nl + 1:] if nl >= 0 else tail + "\n" + line
        body = head + "# 版本紀錄" + tail
    else:
        body = body.rstrip("\n") + "\n\n# 版本紀錄\n" + line
    write_card(p, fm, body)
    return ledger.append(actor, "card_revised", fm.get("id", card_id),
                         {"from_version": old, "to_version": old + 1, "reason": reason}, [paths.rel(p)])


# ------------------------------------------------------------------ CLI
def _main() -> int:
    ap = argparse.ArgumentParser(description="假說卡工具")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("new-id")
    s = sub.add_parser("show"); s.add_argument("card")
    l = sub.add_parser("list"); l.add_argument("--status", default=None)
    v = sub.add_parser("validate"); v.add_argument("card")
    st = sub.add_parser("set-status"); st.add_argument("card"); st.add_argument("status", choices=STATUSES)
    st.add_argument("--actor", required=True, choices=sorted(ledger.ACTORS)); st.add_argument("--reason", required=True)
    bv = sub.add_parser("bump-version"); bv.add_argument("card")
    bv.add_argument("--actor", required=True, choices=sorted(ledger.ACTORS)); bv.add_argument("--reason", required=True)
    args = ap.parse_args()

    if args.cmd == "new-id":
        print(new_id())
    elif args.cmd == "show":
        _, fm, _ = read_card(args.card)
        print(json.dumps(fm, ensure_ascii=False, indent=2))
    elif args.cmd == "list":
        cards = [c for c in all_cards() if args.status is None or c.get("status") == args.status]
        if not cards:
            print("（本機沒有假說卡）")
        for c in cards:
            print(f"{c.get('id'):14s} v{c.get('version', '?'):<3} {str(c.get('status')):17s} "
                  f"{str(c.get('dataset')):18s} {c.get('region')}/{c.get('universe')}/d{c.get('delay')}  "
                  f"{str(c.get('hypothesis'))[:60]}")
    elif args.cmd == "validate":
        issues = validate(args.card)
        if not issues:
            print("[PASS] 卡片格式齊全")
            return 0
        for i in issues:
            print(f"[{i['level']}] {i['message']}")
        return 1 if any(i["level"] == "ERROR" for i in issues) else 0
    elif args.cmd == "set-status":
        print(json.dumps(set_status(args.card, args.status, args.actor, args.reason), ensure_ascii=False))
    elif args.cmd == "bump-version":
        print(json.dumps(bump_version(args.card, args.actor, args.reason), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(_main())
