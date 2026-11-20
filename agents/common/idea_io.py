"""idea JSON 與 setting JSON 的讀寫（三支 agent 與 src/idea.py 共用的格式約定）。

idea JSON：
{
  "card_id": "H-261115-003",
  "version": 1,
  "setting_file": "H-261115-003.json",        # DB/ResearchDB/setting/ 內
  "expressions": [
    {"role": "main", "author": "seer", "expr": "...", "hash": null},
    {"role": "naive", ...}, {"role": "falsify", ..., "differs_only_in": "..."},
    {"role": "user", "author": "user", "expr": "..."}
  ],
  "design_notes": {...}                        # 審判官看不到（blind_pack 剝掉）
}
expressions 也接受純字串（相容素材包的舊格式），讀入時一律正規化成 dict。
"""
from __future__ import annotations

import json
from pathlib import Path

from . import paths

ROLES = ("main", "naive", "falsify", "user")


def load_idea(card_or_path: str) -> tuple[Path, dict]:
    p = paths.resolve_file(card_or_path, paths.OUT.IDEA)
    if not p.exists():
        raise FileNotFoundError(f"找不到 idea 檔：{paths.rel(p)}")
    with open(p, "r", encoding="utf-8") as f:
        idea = json.load(f)
    idea["expressions"] = normalize_expressions(idea.get("expressions", []))
    return p, idea


def normalize_expressions(items: list) -> list[dict]:
    out = []
    for i, it in enumerate(items, 1):
        if isinstance(it, str):
            out.append({"role": "user" if i > 1 else "main", "author": "user", "expr": it, "hash": None})
        elif isinstance(it, dict):
            d = dict(it)
            d.setdefault("role", "user")
            d.setdefault("author", "seer" if d["role"] in ("main", "naive", "falsify") else "user")
            d.setdefault("hash", None)
            if "expr" not in d:
                raise ValueError(f"expressions 第 {i} 項缺 expr")
            out.append(d)
        else:
            raise ValueError(f"expressions 第 {i} 項格式不對：{type(it).__name__}")
    return out


def save_idea(path: Path, idea: dict) -> Path:
    paths.ensure_parent(path)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(idea, f, ensure_ascii=False, indent=2)
    return path


def load_setting(name_or_path: str) -> tuple[Path, dict]:
    p = paths.resolve_file(name_or_path, paths.OUT.SETTING)
    if not p.exists():
        raise FileNotFoundError(f"找不到 setting 檔：{paths.rel(p)}")
    with open(p, "r", encoding="utf-8") as f:
        return p, json.load(f)


def setting_rud(setting: dict) -> tuple[str, str, int]:
    """region / universe / delay；setting 若是優化陣列模式取第一個。"""
    def first(v):
        return v[0] if isinstance(v, list) else v
    return first(setting["region"]), first(setting["universe"]), int(first(setting["delay"]))


def is_fixed_setting(setting: dict) -> bool:
    return not any(isinstance(v, list) for v in setting.values())


def blind(idea: dict) -> dict:
    """給審判官的盲包：去掉 design_notes 與任何 *_notes 欄位。"""
    out = {k: v for k, v in idea.items() if not (k == "design_notes" or k.endswith("_notes"))}
    out["expressions"] = [{k: v for k, v in e.items() if not k.endswith("notes")} for e in idea["expressions"]]
    return out
