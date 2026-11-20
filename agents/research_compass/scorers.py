"""研究羅盤 R4：用提交標準打分的 scorer（給 GA 用）。

用法（在你自己複製的 GA 腳本裡改兩行；不要改 sample_code/sample_ga.py 本體）：
    from agents.research_compass.scorers import SignalScore, RegularSubmissionScore, PowerPoolScore
    score_scorer = RegularSubmissionScore          # 或 SignalScore（探索）／PowerPoolScore
需要 PYTHONPATH 含 open machine 根目錄與 src/（A5 的 export 那行已經有）。

三個 scorer 對應兩個階段（來源：論壇文章「2-step GA：把 Alpha 拆成 Signal 與 Optimization」[L]）：
  SignalScore            探索訊號用，門檻寬：|Sharpe| ≥ 1.2、turnover ≤ 0.5（文章建議值）；不看 checks。
  RegularSubmissionScore 要 fit 正規提交門檻用，門檻嚴：Sharpe ≥ 1.58、fitness ≥ 1.0、turnover ≤ 0.7，
                         再看平台 7 項 check（PASS +1、FAIL −1）。門檻值優先用每支 alpha 結果裡的 limit，沒有才用預設 [R]。
  PowerPoolScore         要 fit Power Pool 用：Sharpe ≥ 1.0 [?]、7 項無 FAIL（WARNING 可）、PPA 閘門 FAIL 重罰。

分數的形狀（三個都一樣的想法）：
  每個指標算「離門檻多遠」= (值 − 門檻) ÷ 門檻，截在 1 以內（超過門檻很多不再加分，避免 GA 追極端值）；
  turnover 反過來算 (門檻 − 值) ÷ 門檻。幾個指標相加，再加 checks 的加減分。
  極端值（|Sharpe| > 6、turnover > 0.9）一律 −1000，同 src/scorer.py 的做法。
只讀 alpha 物件已有的結果；不打平台。
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

try:
    from scorer import AlphaScore  # open machine 的 src/scorer.py（PYTHONPATH 含 src/）
except ImportError:  # 直接用 python 跑羅盤程式時
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
    from scorer import AlphaScore

# 預設門檻 [R]（使用者帳號 2026-11 實測；見 knowledge/checks_guide.md）。alpha 結果裡有 limit 時以 limit 為準。
REGULAR_DEFAULT = {"sharpe": 1.58, "fitness": 1.0, "turnover": 0.70}
POWER_POOL_DEFAULT = {"sharpe": 1.0}          # [?] 實測落在 0.94～1.19 之間
SIGNAL_DEFAULT = {"sharpe": 1.2, "turnover": 0.5}   # [L] 2-step GA 文章的建議
REGULAR_CHECKS = ["LOW_SHARPE", "LOW_FITNESS", "HIGH_TURNOVER", "HIGH_DRAWDOWN",
                  "CONCENTRATED_WEIGHT", "LOW_SUB_UNIVERSE_SHARPE", "LOW_2Y_SHARPE"]
PPA_GATES = ["PROD_CORRELATION", "POWER_POOL_CORRELATION", "MATCHES_THEMES"]
EXTREME = -1000.0


def _f(x) -> float:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return math.nan
    return v


def _metrics(alpha) -> tuple[float, float, float]:
    return _f(alpha["sharpe"]), _f(alpha["fitness"]), _f(alpha["turnover"])


def _checks(alpha) -> dict[str, dict]:
    try:
        cs = alpha.get_checks() or []
    except Exception:
        cs = []
    out = {}
    for c in cs if isinstance(cs, list) else []:
        if isinstance(c, dict) and c.get("name"):
            out[c["name"]] = c
    return out


def _limit(checks: dict, name: str, default: float) -> float:
    v = _f((checks.get(name) or {}).get("limit"))
    return default if math.isnan(v) else v


def margin(value: float, limit: float, lower_is_better: bool = False) -> float:
    """離門檻多遠，截在 1：剛好在門檻＝0，差一倍＝−1，超過門檻一倍以上＝1。"""
    if math.isnan(value) or limit == 0:
        return -1.0
    m = (limit - value) / limit if lower_is_better else (value - limit) / limit
    return min(m, 1.0)


def _extreme(sharpe: float, turnover: float) -> bool:
    return (not math.isnan(sharpe) and abs(sharpe) > 6) or (not math.isnan(turnover) and turnover > 0.9)


class SignalScore(AlphaScore):
    """第一階段（探索）：只問「有沒有訊號」。|Sharpe| 用絕對值，方向留給第二階段的 template 決定。"""

    @classmethod
    def score(cls, alpha) -> float:
        s, _, t = _metrics(alpha)
        if _extreme(s, t):
            return EXTREME
        return margin(abs(s), SIGNAL_DEFAULT["sharpe"]) + margin(t, SIGNAL_DEFAULT["turnover"], lower_is_better=True)

    @classmethod
    def name(cls) -> str:
        return "signal_loose"


class RegularSubmissionScore(AlphaScore):
    """第二階段（fit 正規提交）：Sharpe、fitness、turnover 離門檻多遠 ＋ 7 項 check（PASS +1、FAIL −1）。"""

    @classmethod
    def score(cls, alpha) -> float:
        s, f, t = _metrics(alpha)
        if _extreme(s, t):
            return EXTREME
        cs = _checks(alpha)
        total = (margin(s, _limit(cs, "LOW_SHARPE", REGULAR_DEFAULT["sharpe"]))
                 + margin(f, _limit(cs, "LOW_FITNESS", REGULAR_DEFAULT["fitness"]))
                 + margin(t, _limit(cs, "HIGH_TURNOVER", REGULAR_DEFAULT["turnover"]), lower_is_better=True))
        for n in REGULAR_CHECKS:
            r = (cs.get(n) or {}).get("result")
            total += 1.0 if r == "PASS" else (-1.0 if r == "FAIL" else 0.0)
        return total

    @classmethod
    def name(cls) -> str:
        return "regular_submission"


class PowerPoolScore(AlphaScore):
    """fit Power Pool：Sharpe 線較低、WARNING 不扣分；7 項 FAIL −1，PPA 閘門 FAIL −3（相關性、主題）。"""

    @classmethod
    def score(cls, alpha) -> float:
        s, _, t = _metrics(alpha)
        if _extreme(s, t):
            return EXTREME
        cs = _checks(alpha)
        total = margin(s, POWER_POOL_DEFAULT["sharpe"]) + margin(t, _limit(cs, "HIGH_TURNOVER", REGULAR_DEFAULT["turnover"]), lower_is_better=True)
        for n in REGULAR_CHECKS:
            if (cs.get(n) or {}).get("result") == "FAIL":
                total -= 1.0
        for n in PPA_GATES:
            if (cs.get(n) or {}).get("result") == "FAIL":
                total -= 3.0
        return total

    @classmethod
    def name(cls) -> str:
        return "power_pool"


COMPASS_SCORERS = {"SignalScore": SignalScore, "RegularSubmissionScore": RegularSubmissionScore, "PowerPoolScore": PowerPoolScore}
