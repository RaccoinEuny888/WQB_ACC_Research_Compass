"""Templatizer — expression → template 自動化引擎（移植自素材包 tools/src/templatizer.py）

1. operator → <opN_sg{編號}>，池 = 同 subgroup 且帳號可用的 op（operator_subgroups.json v4）
2. 數字常數 → 標準區間：平滑類 → [2,5,10,21,42]；backfill → [63,252]；其他 → days 池；std → [2,3,4]
3. group 常數 → <gN>，池 = [market, sector, industry, subindustry]
4. datafield 與變數名保持固定（要泛化在產出後手動改）
utility 類 op（add/multiply/if_else/比較）不開基因位——它們是結構膠水。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from agents.common import paths  # noqa: E402
from agents.common.fastexpr_parser import (AlphaParser, parse_program, Node, Num, Var, Call, BinOp,  # noqa: E402
                                        UnaryOp, Paren, Ternary, Assign)

SUBGROUPS_PATH = paths.KNOWLEDGE / "operator_subgroups.json"
GROUP_CONSTANTS = {"market", "sector", "industry", "subindustry", "country", "currency", "exchange"}
GROUP_POOL = ["market", "sector", "industry", "subindustry"]
DAYS_POOL = [10, 20, 30, 60, 90, 120, 180, 270, 360, 720]
DECAY_POOL = [2, 5, 10, 21, 42]
BACKFILL_POOL = [63, 252]
STD_POOL = [2, 3, 4]
DAYS_PARAM_NAMES = {"d", "days", "lookback", "window", "period"}
SKIP_MODULES = {"utility"}
FORBIDDEN_GENES = {"universe", "region", "delay", "neutralization", "decay", "truncation"}


def load_subgroups() -> dict:
    with open(SUBGROUPS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


class Templatizer:
    def __init__(self, verbose: bool = True):
        sg = load_subgroups()
        self.subgroups = sg["subgroups"]
        self.op_to_sg = sg["operator_to_subgroup"]
        self.parser = AlphaParser.from_available(verbose=verbose)
        self.available_ops = set(self.parser.ops.keys())
        self.slot_meta: dict[str, dict] = {}

    def templatize(self, expr: str) -> dict:
        stmts = parse_program(expr)
        self._gene_pool: dict[str, list] = {}
        self.slot_meta = {}
        self._op_counter = self._d_counter = self._g_counter = self._std_counter = 0
        for stmt in stmts:
            self._walk(stmt.value if isinstance(stmt, Assign) else stmt)
        template = ";\n".join(s.to_expr() for s in stmts)
        return {"template": template, "gene_pool": self._gene_pool}

    def notes_skeleton(self, result: dict, card_id: str = "") -> dict:
        """給占卜家填理由的 notes 骨架（每個基因位一行 why）。"""
        return {
            "card_id": card_id,
            "template_file": "",
            "slots": [{"slot": k, **self.slot_meta.get(k, {}), "options": v, "why": ""} for k, v in result["gene_pool"].items()],
            "pruned": [],
            "doctrine_check": {"same_subgroup": None, "no_hyperparameter_gene": None, "every_slot_has_why": None},
        }

    # ------------------------------------------------------------
    def _walk(self, node: Node) -> None:
        if isinstance(node, Call):
            self._maybe_slot_operator(node)
            self._slot_args(node)
            for a in node.args:
                self._walk(a)
            for _, v in node.kwargs:
                self._walk(v)
        elif isinstance(node, BinOp):
            self._walk(node.left); self._walk(node.right)
        elif isinstance(node, UnaryOp):
            self._walk(node.operand)
        elif isinstance(node, Paren):
            self._walk(node.inner)
        elif isinstance(node, Ternary):
            self._walk(node.cond); self._walk(node.if_true); self._walk(node.if_false)

    def _maybe_slot_operator(self, call: Call) -> None:
        if call.is_custom:
            return
        sg_code = self.op_to_sg.get(call.name)
        if sg_code is None:
            return
        sg = self.subgroups[sg_code]
        if sg["module"] in SKIP_MODULES:
            return
        pool = [op for op in sg["operators"] if op in self.available_ops]
        if len(pool) < 2:
            return
        self._op_counter += 1
        slot = f"<op{self._op_counter}_sg{sg_code.replace('.', '_')}>"
        pool = [call.name] + [op for op in pool if op != call.name]
        self._gene_pool[slot] = pool
        self.slot_meta[slot] = {"kind": "operator", "module": sg["module"], "subgroup": sg_code, "subgroup_name": sg["name"]}
        call.name = slot

    def _slot_args(self, call: Call) -> None:
        orig_name = call.name
        if orig_name.startswith("<") and orig_name in self._gene_pool:
            orig_name = self._gene_pool[orig_name][0]
        spec = self.parser.ops.get(orig_name)
        sg_code = self.op_to_sg.get(orig_name, "")
        sg_module = self.subgroups.get(sg_code, {}).get("module", "")
        for i, a in enumerate(call.args):
            param = spec.positional[i] if (spec and spec.parse_ok and i < len(spec.positional)) else ""
            if isinstance(a, Num) and param.lower() in DAYS_PARAM_NAMES:
                call.args[i] = self._make_days_slot(a, orig_name, sg_module)
            elif isinstance(a, Var) and a.name in GROUP_CONSTANTS and (param.lower() == "group" or "group" in orig_name):
                self._g_counter += 1
                slot = f"<g{self._g_counter}>"
                self._gene_pool[slot] = [a.name] + [g for g in GROUP_POOL if g != a.name]
                self.slot_meta[slot] = {"kind": "group", "operator": orig_name}
                call.args[i] = Var(slot)
        for j, (k, v) in enumerate(call.kwargs):
            if isinstance(v, Num) and k.lower() == "std":
                self._std_counter += 1
                slot = f"<std{self._std_counter}>"
                orig = int(float(v.value)) if float(v.value).is_integer() else float(v.value)
                self._gene_pool[slot] = [orig] + [s for s in STD_POOL if s != orig]
                self.slot_meta[slot] = {"kind": "std", "operator": orig_name}
                call.kwargs[j] = (k, Var(slot))
            elif isinstance(v, Num) and k.lower() in DAYS_PARAM_NAMES:
                call.kwargs[j] = (k, self._make_days_slot(v, orig_name, sg_module))

    def _make_days_slot(self, num: Num, op_name: str, sg_module: str) -> Var:
        self._d_counter += 1
        slot = f"<d{self._d_counter}>"
        orig = int(float(num.value)) if float(num.value).is_integer() else float(num.value)
        if "backfill" in op_name:
            base, kind = BACKFILL_POOL, "backfill_days"
        elif sg_module.startswith("smoothing") or "decay" in op_name:
            base, kind = DECAY_POOL, "decay_days"
        else:
            base, kind = DAYS_POOL, "lookback_days"
        self._gene_pool[slot] = [orig] + [d for d in base if d != orig]
        self.slot_meta[slot] = {"kind": kind, "operator": op_name}
        return Var(slot)


# ------------------------------------------------------------------ 工具
def count_combinations(gene_pool: dict) -> int:
    n = 1
    for values in gene_pool.values():
        n *= max(len(values), 1)
    return n


def check_gene_pool(gene_pool: dict, subgroups: dict | None = None) -> list[dict]:
    """審判官 stage=template 的機械規則：禁入項、同 subgroup、空池。"""
    issues = []
    sg = subgroups or load_subgroups()
    op_to_sg = sg["operator_to_subgroup"]
    for slot, values in gene_pool.items():
        low = slot.lower()
        if any(f in low for f in FORBIDDEN_GENES):
            issues.append({"level": "ERROR", "message": f"{slot}：universe/region/delay/neutralization 等 hyperparameter 不可進 gene_pool（template_doctrine #8）"})
        if not values:
            issues.append({"level": "ERROR", "message": f"{slot}：空池"})
            continue
        ops = [v for v in values if isinstance(v, str) and v in op_to_sg]
        if len(ops) >= 2:
            codes = {op_to_sg[o] for o in ops}
            if len(codes) > 1:
                issues.append({"level": "ERROR", "message": f"{slot}：跨 subgroup 混放 {sorted(codes)}（template_doctrine #7；operators={ops}）"})
        if isinstance(values[0], str) and values[0] in op_to_sg and len(values) == 1:
            issues.append({"level": "WARN", "message": f"{slot}：只有一個選項，等於沒開基因位，建議寫死"})
    return issues


def wrap_with_opt_block(signal_template: dict, opt_block_file: str = "optimization_block.json") -> dict:
    p = paths.OM.TEMPLATE / opt_block_file
    if not p.exists():
        raise FileNotFoundError(f"找不到 {paths.rel(p)}（--opt-block 需要使用者自備 optimization block）")
    with open(p, "r", encoding="utf-8") as f:
        opt = json.load(f)
    sig_stmts = [s.strip() for s in signal_template["template"].split(";") if s.strip()]
    sig_final, sig_prefix = sig_stmts[-1], sig_stmts[:-1]
    combined_template = ";\n".join(sig_prefix + [opt["template"].replace("<signal>", sig_final)])
    combined_pool = dict(signal_template.get("gene_pool", {}))
    for k, v in opt["gene_pool"].items():
        if k in combined_pool:
            raise ValueError(f"gene_pool 佔位符衝突：{k}")
        combined_pool[k] = v
    return {"template": combined_template, "gene_pool": combined_pool}
