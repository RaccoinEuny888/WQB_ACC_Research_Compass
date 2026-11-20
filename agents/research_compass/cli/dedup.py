"""開新卡前查重（唯讀；占卜家在 /hypothesis 第 3 步呼叫，也可直接用）。

  python agents/research_compass/cli/dedup.py --text "ESG 高但負面新聞多 → 做空" [--dataset esg_x] [--tag greenwashing] [--json]

比對：mechanism_tag 完全相同（權重最高）、dataset 相同、假說文字相似（中文字元 bigram ＋ 英文 token 的 Jaccard）。
判定：
  BLOCK  撞到 rejected 卡（tag 相同或相似度 ≥ 0.5）→ 不建卡，附原卡
  WARN   撞到 approved / abandoned / 其他進行中卡（相似度 ≥ 0.35 或 tag 相同）→ 新卡要寫差異或復活條件
  OK     沒有相近的卡
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from agents.common import card as cardmod  # noqa: E402


def _grams(text: str) -> set[str]:
    text = (text or "").lower()
    toks = set(re.findall(r"[a-z][a-z0-9_]+", text))
    cjk = re.sub(r"[^一-鿿]", "", text)
    toks |= {cjk[i:i + 2] for i in range(len(cjk) - 1)}
    return toks


def similarity(a: str, b: str) -> float:
    ga, gb = _grams(a), _grams(b)
    if not ga or not gb:
        return 0.0
    return len(ga & gb) / len(ga | gb)


def dedup(text: str, dataset: str | None = None, tag: str | None = None, top: int = 3) -> dict:
    cards = cardmod.all_cards()
    scored = []
    for c in cards:
        sim = similarity(text, str(c.get("hypothesis", "")))
        tag_hit = bool(tag) and str(c.get("mechanism_tag", "")).lower() == tag.lower()
        ds_hit = bool(dataset) and str(c.get("dataset", "")).lower() == str(dataset).lower()
        score = sim + (0.5 if tag_hit else 0) + (0.1 if ds_hit else 0)
        scored.append({"card_id": c.get("id"), "status": c.get("status"), "mechanism_tag": c.get("mechanism_tag"),
                       "dataset": c.get("dataset"), "hypothesis": c.get("hypothesis"), "similarity": round(sim, 2),
                       "tag_match": tag_hit, "dataset_match": ds_hit, "score": round(score, 2), "path": c.get("_path")})
    scored.sort(key=lambda x: -x["score"])
    verdict, reasons = "OK", []
    for s in scored[:top]:
        how = "機制標籤相同" if s["tag_match"] else f"相似度 {s['similarity']}"
        if s["status"] == "rejected" and (s["tag_match"] or s["similarity"] >= 0.5):
            verdict = "BLOCK"
            reasons.append(f"{s['card_id']} 已處決（{s['mechanism_tag']}），{how}")
        elif s["tag_match"] or s["similarity"] >= 0.35:
            if verdict != "BLOCK":
                verdict = "WARN"
            tail = "；abandoned → 新卡要寫復活條件" if s["status"] == "abandoned" else "；新卡要寫差異"
            reasons.append(f"{s['card_id']}（{s['status']}）相近：{how}{tail}")
    return {"verdict": verdict, "reasons": reasons, "n_cards": len(cards), "nearest": scored[:top]}


def main() -> int:
    ap = argparse.ArgumentParser(description="查重")
    ap.add_argument("--text", required=True)
    ap.add_argument("--dataset", default=None)
    ap.add_argument("--tag", default=None)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    r = dedup(args.text, args.dataset, args.tag)
    if args.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        print(f"[dedup] {r['verdict']}（本機 {r['n_cards']} 張卡）")
        for x in r["reasons"]:
            print(f"  - {x}")
        for s in r["nearest"]:
            print(f"  {s['card_id']} {s['status']:<14} sim={s['similarity']:.2f} tag={s['mechanism_tag']} ds={s['dataset']} | {str(s['hypothesis'])[:70]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
