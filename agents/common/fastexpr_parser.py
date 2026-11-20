"""Alpha Parser — 非 LLM 的 FASTEXPR 語法／語意檢查與規則修復引擎（移植自素材包 tools/src/alpha_parser.py → agents/common/fastexpr_parser.py）

三層檢查：
1. 語法：tokenize → 遞迴下降解析（括號平衡、巢狀結構、運算子）
2. 語意：對照 operators.json —— operator 存在性、位置參數數量、keyword 參數合法性
3. 資料：對照已同步 datafields —— 欄位存在性、VECTOR 欄位必須直接餵給 vec_* 類 op

規則修復（--fix，純程式無 LLM）：
- 多給的位置參數 → 依 definition 順序轉成 key=value
- VECTOR 欄位裸用 → 自動包 vec_avg()

operators.json 解析順序（paths.resolve_operators_path）：
  agents/workspace/cache/operators.json（使用者帳號，brain_meta.py 抓的）
  → DB/ResearchDB/data/latest/operators.json（使用者自己放的）
  → agents/common/knowledge/operators.json（內建預設清單）
"""
from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from agents.common import paths  # noqa: E402


def _load_custom_ops() -> set[str]:
    """open machine 的 $ 自訂 operator 名稱（src/custom_op_definition.py）；讀不到就空集合。"""
    try:
        paths.bootstrap_open_machine()
        from src.custom_op_definition import MAPPING  # type: ignore
        return set(MAPPING.keys())
    except Exception:
        return set()


# 平台內建欄位/常數（不需檢查存在性）
BUILTIN_IDENTIFIERS = {
    "market", "sector", "industry", "subindustry", "country", "currency", "exchange",
    "open", "close", "high", "low", "volume", "returns", "vwap", "cap",
    "adv20", "sharesout", "split", "dividend",
    "true", "false", "True", "False",
    "datasets",
}

VECTOR_OP_CATEGORY = "Vector"
LOOKBACK_PARAM_NAMES = {"d", "days", "lookback", "window", "period"}


# ------------------------------------------------------------------ Tokenizer
TOKEN_RE = re.compile(r"""
    (?P<NUMBER>\d+\.\d*|\.\d+|\d+)
  | (?P<IDENT>[A-Za-z_][A-Za-z0-9_]*)
  | (?P<STRING>"[^"]*"|'[^']*')
  | (?P<OP><=|>=|==|!=|&&|\|\||[-+*/^<>!?:])
  | (?P<ASSIGN>=)
  | (?P<LPAREN>\()
  | (?P<RPAREN>\))
  | (?P<COMMA>,)
  | (?P<SEMI>;)
  | (?P<DOLLAR>\$)
  | (?P<WS>\s+)
""", re.VERBOSE)


@dataclass
class Token:
    kind: str
    value: str
    pos: int


class SyntaxIssue(Exception):
    def __init__(self, message: str, pos: int = -1):
        super().__init__(message)
        self.message = message
        self.pos = pos


def tokenize(text: str) -> list[Token]:
    tokens = []
    pos = 0
    while pos < len(text):
        m = TOKEN_RE.match(text, pos)
        if m is None:
            raise SyntaxIssue(f"無法辨識的字元 '{text[pos]}'（位置 {pos}）", pos)
        kind = m.lastgroup
        if kind != "WS":
            tokens.append(Token(kind, m.group(), pos))
        pos = m.end()
    return tokens


# ------------------------------------------------------------------ AST
@dataclass
class Node:
    def to_expr(self) -> str:
        raise NotImplementedError


@dataclass
class Num(Node):
    value: str
    def to_expr(self) -> str:
        return self.value


@dataclass
class Str(Node):
    value: str
    def to_expr(self) -> str:
        return self.value


@dataclass
class Var(Node):
    name: str
    def to_expr(self) -> str:
        return self.name


@dataclass
class Call(Node):
    name: str
    args: list = field(default_factory=list)
    kwargs: list = field(default_factory=list)
    is_custom: bool = False
    def to_expr(self) -> str:
        parts = [a.to_expr() for a in self.args]
        parts += [f"{k}={v.to_expr()}" for k, v in self.kwargs]
        prefix = "$" if self.is_custom else ""
        return f"{prefix}{self.name}({', '.join(parts)})"


@dataclass
class BinOp(Node):
    op: str
    left: Node
    right: Node
    def to_expr(self) -> str:
        return f"{self.left.to_expr()} {self.op} {self.right.to_expr()}"


@dataclass
class UnaryOp(Node):
    op: str
    operand: Node
    def to_expr(self) -> str:
        return f"{self.op}{self.operand.to_expr()}"


@dataclass
class Paren(Node):
    inner: Node
    def to_expr(self) -> str:
        return f"({self.inner.to_expr()})"


@dataclass
class Ternary(Node):
    cond: Node
    if_true: Node
    if_false: Node
    def to_expr(self) -> str:
        return f"{self.cond.to_expr()} ? {self.if_true.to_expr()} : {self.if_false.to_expr()}"


@dataclass
class Assign(Node):
    var: str
    value: Node
    def to_expr(self) -> str:
        return f"{self.var} = {self.value.to_expr()}"


# ------------------------------------------------------------------ Parser
class _Parser:
    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.i = 0

    def peek(self) -> Token | None:
        return self.tokens[self.i] if self.i < len(self.tokens) else None

    def next(self) -> Token:
        tok = self.peek()
        if tok is None:
            raise SyntaxIssue("表達式意外結束（可能缺右括號或運算元）")
        self.i += 1
        return tok

    def expect(self, kind: str) -> Token:
        tok = self.peek()
        if tok is None or tok.kind != kind:
            got = f"'{tok.value}'" if tok else "結尾"
            raise SyntaxIssue(f"預期 {kind}，但遇到 {got}", tok.pos if tok else -1)
        return self.next()

    def parse_program(self) -> list[Node]:
        stmts = []
        while self.peek() is not None:
            stmts.append(self.parse_stmt())
            if self.peek() and self.peek().kind == "SEMI":
                self.next()
            elif self.peek() is not None:
                tok = self.peek()
                raise SyntaxIssue(f"語句之間缺少分號（位置 {tok.pos}，遇到 '{tok.value}'）", tok.pos)
        if not stmts:
            raise SyntaxIssue("空表達式")
        return stmts

    def parse_stmt(self) -> Node:
        if (self.peek() and self.peek().kind == "IDENT"
                and self.i + 1 < len(self.tokens)
                and self.tokens[self.i + 1].kind == "ASSIGN"):
            var = self.next().value
            self.next()
            return Assign(var, self.parse_expr())
        return self.parse_expr()

    def parse_expr(self) -> Node:
        return self.parse_ternary()

    def parse_ternary(self) -> Node:
        cond = self.parse_or()
        if self.peek() and self.peek().value == "?":
            self.next()
            if_true = self.parse_expr()
            tok = self.peek()
            if tok is None or tok.value != ":":
                raise SyntaxIssue("三元運算子缺少 ':'")
            self.next()
            if_false = self.parse_expr()
            return Ternary(cond, if_true, if_false)
        return cond

    def _binop_level(self, sub_parse, ops: set[str]) -> Node:
        left = sub_parse()
        while self.peek() and self.peek().kind == "OP" and self.peek().value in ops:
            op = self.next().value
            right = sub_parse()
            left = BinOp(op, left, right)
        return left

    def parse_or(self) -> Node:
        return self._binop_level(self.parse_and, {"||"})

    def parse_and(self) -> Node:
        return self._binop_level(self.parse_cmp, {"&&"})

    def parse_cmp(self) -> Node:
        return self._binop_level(self.parse_add, {"<", "<=", ">", ">=", "==", "!="})

    def parse_add(self) -> Node:
        return self._binop_level(self.parse_mul, {"+", "-"})

    def parse_mul(self) -> Node:
        return self._binop_level(self.parse_unary, {"*", "/"})

    def parse_unary(self) -> Node:
        tok = self.peek()
        if tok and tok.kind == "OP" and tok.value in {"-", "!", "+"}:
            self.next()
            return UnaryOp(tok.value, self.parse_unary())
        return self.parse_power()

    def parse_power(self) -> Node:
        base = self.parse_atom()
        if self.peek() and self.peek().value == "^":
            self.next()
            return BinOp("^", base, self.parse_unary())
        return base

    def parse_atom(self) -> Node:
        tok = self.peek()
        if tok is None:
            raise SyntaxIssue("表達式意外結束（缺運算元）")
        if tok.kind == "NUMBER":
            self.next()
            return Num(tok.value)
        if tok.kind == "STRING":
            self.next()
            return Str(tok.value)
        if tok.kind == "DOLLAR":
            self.next()
            name_tok = self.expect("IDENT")
            self.expect("LPAREN")
            args, kwargs = self.parse_args()
            self.expect("RPAREN")
            return Call(name_tok.value, args, kwargs, is_custom=True)
        if tok.kind == "IDENT":
            self.next()
            if self.peek() and self.peek().kind == "LPAREN":
                self.next()
                args, kwargs = self.parse_args()
                self.expect("RPAREN")
                return Call(tok.value, args, kwargs)
            return Var(tok.value)
        if tok.kind == "LPAREN":
            self.next()
            inner = self.parse_expr()
            self.expect("RPAREN")
            return Paren(inner)
        raise SyntaxIssue(f"預期運算元，但遇到 '{tok.value}'（位置 {tok.pos}）", tok.pos)

    def parse_args(self) -> tuple[list, list]:
        args, kwargs = [], []
        if self.peek() and self.peek().kind == "RPAREN":
            return args, kwargs
        while True:
            if (self.peek() and self.peek().kind == "IDENT"
                    and self.i + 1 < len(self.tokens)
                    and self.tokens[self.i + 1].kind == "ASSIGN"):
                key = self.next().value
                self.next()
                kwargs.append((key, self.parse_expr()))
            else:
                node = self.parse_expr()
                if kwargs:
                    raise SyntaxIssue("位置參數不可出現在 keyword 參數之後")
                args.append(node)
            tok = self.peek()
            if tok and tok.kind == "COMMA":
                self.next()
                continue
            break
        return args, kwargs


def parse_program(text: str) -> list[Node]:
    """解析多語句 FASTEXPR，回傳 AST 語句清單。語法錯誤丟 SyntaxIssue。"""
    return _Parser(tokenize(text)).parse_program()


# ------------------------------------------------------------------ Operator 知識庫
@dataclass
class OpSpec:
    name: str
    category: str
    positional: list[str]
    keyword_only: dict
    variadic: bool = False
    parse_ok: bool = True
    definition: str = ""
    description: str = ""


_LITERAL_DEFAULT_RE = re.compile(r"^(\d+\.?\d*|\.\d+|true|false|True|False|\".*\"|'.*'|“.*”|‘.*’)$")


def _parse_definition(o: dict) -> OpSpec:
    name, category = o["name"], o.get("category", "")
    definition, description = o.get("definition", ""), o.get("description", "")
    try:
        start = definition.index(name + "(")
        i = start + len(name) + 1
        depth, buf = 1, ""
        while i < len(definition) and depth > 0:
            ch = definition[i]
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    break
            buf += ch
            i += 1
        if depth != 0:
            raise ValueError("unbalanced")
        parts, cur, d = [], "", 0
        for ch in buf:
            if ch == "(":
                d += 1
            elif ch == ")":
                d -= 1
            if ch == "," and d == 0:
                parts.append(cur)
                cur = ""
            else:
                cur += ch
        if cur.strip():
            parts.append(cur)
        positional, keyword_only, variadic = [], {}, False
        for raw in parts:
            p = raw.strip().replace("“", '"').replace("”", '"')
            if not p:
                continue
            if "..." in p:
                variadic = True
                continue
            if "=" in p:
                pname, default = p.split("=", 1)
                pname = pname.strip().replace(" ", "")
                default = default.strip()
                if _LITERAL_DEFAULT_RE.match(default):
                    keyword_only[pname] = default
                else:
                    positional.append(pname)
            else:
                positional.append(p.replace(" ", ""))
        return OpSpec(name, category, positional, keyword_only, variadic, True, definition, description)
    except Exception:
        return OpSpec(name, category, [], {}, False, False, definition, description)


class AlphaParser:
    """語法/語意檢查與修復的對外介面。"""

    def __init__(self, operators: list[dict], source: str = ""):
        self.ops: dict[str, OpSpec] = {o["name"]: _parse_definition(o) for o in operators}
        self.custom_ops = _load_custom_ops()
        self.source = source

    @classmethod
    def from_available(cls, verbose: bool = True) -> "AlphaParser":
        path = paths.resolve_operators_path()
        if path is None:
            raise FileNotFoundError("找不到任何 operators.json（請先跑 python agents/common/brain_meta.py operators）")
        with open(path, "r", encoding="utf-8") as f:
            ops = json.load(f)
        if verbose:
            tag = {"cache": "使用者帳號快取", "latest": "open machine data/latest", "knowledge": "內建預設清單"}
            kind = "cache" if path.parent == paths.OUT.CACHE else ("knowledge" if path.parent == paths.KNOWLEDGE else "latest")
            print(f"[operators] {len(ops)} 個，來源：{tag[kind]}（{paths.rel(path)}）")
        return cls(ops, source=str(path))

    # 相容舊名
    from_latest = from_available

    # -------------------------------------------------------------- 檢查
    def check(self, expr: str, datafields: set[str] | None = None,
              field_types: dict[str, str] | None = None) -> list[dict]:
        issues: list[dict] = []
        try:
            stmts = parse_program(expr)
        except SyntaxIssue as e:
            return [{"level": "ERROR", "message": f"語法錯誤：{e.message}"}]
        defined_vars: set[str] = set()
        self._const_vars: set[str] = set()      # 指向數字常數的變數（compare_days = 360）
        for stmt in stmts:
            if isinstance(stmt, Assign):
                self._walk(stmt.value, defined_vars, datafields, field_types, issues, None)
                defined_vars.add(stmt.var)
                if self._is_const(stmt.value):
                    self._const_vars.add(stmt.var)
            else:
                self._walk(stmt, defined_vars, datafields, field_types, issues, None)
        if stmts and isinstance(stmts[-1], Assign):
            issues.append({"level": "ERROR",
                           "message": f"最後一行是賦值（{stmts[-1].var} = ...），expression 必須以輸出式結尾"
                                      f"（平台會報 Unexpected end of input）——把最後一行改成 `{stmts[-1].var}`"})
        return issues

    def _walk(self, node, defined_vars, datafields, field_types, issues, parent_call) -> None:
        if isinstance(node, Call):
            self._check_call(node, issues)
            for a in node.args:
                self._walk(a, defined_vars, datafields, field_types, issues, node)
            for _, v in node.kwargs:
                self._walk(v, defined_vars, datafields, field_types, issues, node)
        elif isinstance(node, Var):
            self._check_identifier(node.name, defined_vars, datafields, field_types, issues, parent_call)
        elif isinstance(node, BinOp):
            self._walk(node.left, defined_vars, datafields, field_types, issues, parent_call)
            self._walk(node.right, defined_vars, datafields, field_types, issues, parent_call)
        elif isinstance(node, UnaryOp):
            self._walk(node.operand, defined_vars, datafields, field_types, issues, parent_call)
        elif isinstance(node, Paren):
            self._walk(node.inner, defined_vars, datafields, field_types, issues, parent_call)
        elif isinstance(node, Ternary):
            for sub in (node.cond, node.if_true, node.if_false):
                self._walk(sub, defined_vars, datafields, field_types, issues, parent_call)

    def _check_call(self, call: Call, issues: list) -> None:
        if call.is_custom:
            if call.name not in self.custom_ops:
                issues.append({"level": "ERROR",
                               "message": f"自訂運算符 ${call.name} 不存在（可用：{sorted(self.custom_ops)}）"})
            return
        spec = self.ops.get(call.name)
        if spec is None:
            issues.append({"level": "ERROR", "message": f"operator '{call.name}' 不存在於 operators.json（帳號不可用或拼錯）"})
            return
        if not spec.parse_ok:
            return
        n_pos = len(call.args)
        if not spec.variadic:
            if n_pos > len(spec.positional):
                extra = n_pos - len(spec.positional)
                kw_names = list(spec.keyword_only.keys())
                hint = f"多出的 {extra} 個應改具名（依序：{kw_names[:extra]}）" if kw_names else ""
                issues.append({"level": "ERROR", "fixable": "positional_to_keyword",
                               "message": f"{call.name}() 位置參數過多（給了 {n_pos}，最多 {len(spec.positional)}）。{hint}"})
            elif n_pos == 0 and spec.positional:
                issues.append({"level": "ERROR", "message": f"{call.name}() 缺少必要參數（需要 {spec.positional}）"})
        for key, _ in call.kwargs:
            if key not in spec.keyword_only and key not in spec.positional:
                issues.append({"level": "ERROR",
                               "message": f"{call.name}() 沒有 keyword 參數 '{key}'（合法：{list(spec.keyword_only.keys())}）"})
        # lookback d 必須是常數（數字、字串、或指向數字的變數），不能是另一個序列
        # 來源：Missing Neutralization Operators Solution（平台報 lookback must be constant or string）
        for i, pname in enumerate(spec.positional):
            if pname.lower() in LOOKBACK_PARAM_NAMES and i < len(call.args) and not self._is_const(call.args[i]):
                issues.append({"level": "ERROR",
                               "message": f"{call.name}() 的 lookback 參數 '{pname}' 必須是常數，不能是 `{call.args[i].to_expr()[:40]}`"
                                          f"（平台：lookback must be constant or string；見 knowledge/operator_recipes.md §4）"})
        for key, v in call.kwargs:
            if key.lower() in LOOKBACK_PARAM_NAMES and not self._is_const(v):
                issues.append({"level": "ERROR",
                               "message": f"{call.name}() 的 lookback 參數 '{key}' 必須是常數，不能是 `{v.to_expr()[:40]}`"})

    def _is_const(self, node) -> bool:
        if isinstance(node, (Num, Str)):
            return True
        if isinstance(node, UnaryOp) and node.op in "+-":
            return self._is_const(node.operand)
        if isinstance(node, Paren):
            return self._is_const(node.inner)
        if isinstance(node, Var):
            return node.name in getattr(self, "_const_vars", set()) or node.name.startswith("<")
        return False

    def _check_identifier(self, name, defined_vars, datafields, field_types, issues, parent_call) -> None:
        if name in defined_vars or name in BUILTIN_IDENTIFIERS:
            return
        if datafields is not None and name not in datafields:
            issues.append({"level": "ERROR", "message": f"欄位 '{name}' 不存在於已同步的 datafields（可能是幻覺欄位或未同步該 region）"})
            return
        if field_types is not None and field_types.get(name) == "VECTOR":
            parent_ok = (parent_call is not None and not parent_call.is_custom
                         and self.ops.get(parent_call.name) is not None
                         and self.ops[parent_call.name].category == VECTOR_OP_CATEGORY)
            if not parent_ok:
                issues.append({"level": "ERROR", "fixable": "wrap_vec_avg", "field": name,
                               "message": f"VECTOR 欄位 '{name}' 必須先經過 vec_* 類 operator（如 vec_avg）"})

    # -------------------------------------------------------------- 修復
    def fix(self, expr: str, datafields=None, field_types=None) -> tuple[str, list[dict]]:
        try:
            stmts = parse_program(expr)
        except SyntaxIssue as e:
            return expr, [{"level": "ERROR", "message": f"語法錯誤無法自動修復：{e.message}"}]
        defined_vars: set[str] = set()
        for stmt in stmts:
            target = stmt.value if isinstance(stmt, Assign) else stmt
            self._fix_node(target, defined_vars, field_types, None)
            if isinstance(stmt, Assign):
                defined_vars.add(stmt.var)
        fixed = ";\n".join(s.to_expr() for s in stmts)
        return fixed, self.check(fixed, datafields, field_types)

    def _fix_node(self, node, defined_vars, field_types, parent_call) -> None:
        def wrap_if_vector(child):
            return (isinstance(child, Var) and field_types is not None and field_types.get(child.name) == "VECTOR")

        if isinstance(node, Call):
            spec = self.ops.get(node.name) if not node.is_custom else None
            if spec and spec.parse_ok and not spec.variadic and len(node.args) > len(spec.positional):
                extra = node.args[len(spec.positional):]
                node.args = node.args[:len(spec.positional)]
                for kw_name, arg in zip(spec.keyword_only.keys(), extra):
                    node.kwargs.append((kw_name, arg))
            for i, a in enumerate(node.args):
                if wrap_if_vector(a) and not (spec and spec.category == VECTOR_OP_CATEGORY):
                    node.args[i] = Call("vec_avg", [a], [])
                else:
                    self._fix_node(a, defined_vars, field_types, node)
            for _, v in node.kwargs:
                self._fix_node(v, defined_vars, field_types, node)
        elif isinstance(node, BinOp):
            for attr in ("left", "right"):
                child = getattr(node, attr)
                if wrap_if_vector(child):
                    setattr(node, attr, Call("vec_avg", [child], []))
                else:
                    self._fix_node(child, defined_vars, field_types, parent_call)
        elif isinstance(node, UnaryOp):
            if wrap_if_vector(node.operand):
                node.operand = Call("vec_avg", [node.operand], [])
            else:
                self._fix_node(node.operand, defined_vars, field_types, parent_call)
        elif isinstance(node, Paren):
            if wrap_if_vector(node.inner):
                node.inner = Call("vec_avg", [node.inner], [])
            else:
                self._fix_node(node.inner, defined_vars, field_types, parent_call)
        elif isinstance(node, Ternary):
            for attr in ("cond", "if_true", "if_false"):
                self._fix_node(getattr(node, attr), defined_vars, field_types, parent_call)

    # -------------------------------------------------------------- 給反解釋用
    def explain_layers(self, expr: str) -> list[dict]:
        """把 expression 拆成由內到外的 operator 層，附 definition／description，給審判官寫白話反解釋用。"""
        layers: list[dict] = []
        try:
            stmts = parse_program(expr)
        except SyntaxIssue as e:
            return [{"error": e.message}]

        def visit(node, depth):
            if isinstance(node, Call):
                for a in node.args:
                    visit(a, depth + 1)
                for _, v in node.kwargs:
                    visit(v, depth + 1)
                spec = self.ops.get(node.name)
                layers.append({
                    "depth": depth, "call": node.to_expr()[:120], "operator": ("$" if node.is_custom else "") + node.name,
                    "category": spec.category if spec else ("custom" if node.is_custom else "?"),
                    "definition": spec.definition if spec else "", "description": spec.description if spec else "",
                })
            elif isinstance(node, (BinOp,)):
                visit(node.left, depth + 1); visit(node.right, depth + 1)
                layers.append({"depth": depth, "call": node.to_expr()[:120], "operator": node.op, "category": "arith",
                               "definition": "", "description": ""})
            elif isinstance(node, UnaryOp):
                visit(node.operand, depth + 1)
            elif isinstance(node, Paren):
                visit(node.inner, depth)
            elif isinstance(node, Ternary):
                for sub in (node.cond, node.if_true, node.if_false):
                    visit(sub, depth + 1)

        for stmt in stmts:
            visit(stmt.value if isinstance(stmt, Assign) else stmt, 0)
        return layers


# ------------------------------------------------------------------ Datafield 索引
def load_datafield_index(region: str, universe: str, delay: int) -> tuple[set[str], dict[str, str]]:
    """讀取某組合的 datafields。回傳 (全部欄位集合, {field_id: type})。"""
    folder = paths.data_dir(region, universe, delay)
    id_map_path = folder / "data_fields.json"
    if not id_map_path.exists():
        raise FileNotFoundError(f"找不到 {paths.rel(id_map_path)}，請先 run_data_sync.py 同步 {folder.name}")
    with open(id_map_path, "r", encoding="utf-8") as f:
        id_map = json.load(f)
    all_fields: set[str] = set()
    for ids in id_map.values():
        all_fields.update(ids)
    field_types: dict[str, str] = {}
    raw_dir = folder / "data_fields_raw"
    if raw_dir.exists():
        for fname in os.listdir(raw_dir):
            if not fname.endswith(".json"):
                continue
            try:
                with open(raw_dir / fname, "r", encoding="utf-8") as f:
                    for entry in json.load(f):
                        field_types[entry["id"]] = entry.get("type", "MATRIX")
            except Exception:
                continue
    return all_fields, field_types
