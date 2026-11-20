"""agents 共用路徑。

原則（見 doc/agent_challenge/AGENT_ARCHITECTURE_DESIGN.md §2.2）：
- import 時不建任何目錄。
- open machine 既有目錄一律唯讀引用（OM）。
- 可寫位置只有 OUT 列出的幾處；寫檔函式在寫之前才建自己的父目錄。
- 絕不讀 .env / session.pkl / login_time.pkl 的內容。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]          # open machine 根目錄
AGENTS = ROOT / "agents"
COMMON = AGENTS / "common"
KNOWLEDGE = COMMON / "knowledge"
WORKSPACE = AGENTS / "workspace"

SENSITIVE_FILES = {".env", "session.pkl", "login_time.pkl"}


class OM:
    """open machine 既有目錄（唯讀）。"""
    RESEARCH = ROOT / "DB" / "ResearchDB"
    TEMPLATE = RESEARCH / "template"
    SETTING = RESEARCH / "setting"
    GA_CONFIG = RESEARCH / "ga_config"
    RESEARCH_PROCESS = RESEARCH / "research_process"
    DATA = RESEARCH / "data"
    DATA_LATEST = DATA / "latest"

    ALPHA = ROOT / "DB" / "AlphaDB"
    PENDING = ALPHA / "pending"
    RUNNING = ALPHA / "running"
    COMPLETE = ALPHA / "complete"
    ERROR = ALPHA / "error"
    PNL = ALPHA / "pnl"
    QUEUES = {"pending": PENDING, "running": RUNNING, "complete": COMPLETE, "error": ERROR}


class OUT:
    """agents 可以寫入的位置。"""
    HYPOTHESIS = OM.RESEARCH / "hypothesis"           # 假說卡 <card_id>.md
    REVIEWS = HYPOTHESIS / "reviews"                  # 判決書
    LEDGER = HYPOTHESIS / "ledger.jsonl"              # 研究帳本
    IDEA = OM.RESEARCH / "idea"                       # idea JSON <card_id>.json
    SPC = OM.RESEARCH / "spc"                         # SPC：universe/ 主清單、<card_id>/{prompt.json, universe.txt, runs/, validation_v*.md}、registry.jsonl
    SPC_UNIVERSE = SPC / "universe"
    SPC_REGISTRY = SPC / "registry.jsonl"
    TEMPLATE = OM.TEMPLATE                            # template JSON（open machine 正常輸入）
    SETTING = OM.SETTING                              # setting JSON（open machine 正常輸入）
    CACHE = WORKSPACE / "cache"
    INDEX = WORKSPACE / "index"
    DASHBOARD = WORKSPACE / "dashboard"
    PROFILE = WORKSPACE / "compass_profile.json"


# ------------------------------------------------------------------
def ensure_parent(path: Path) -> Path:
    """寫檔前建父目錄（唯一允許建目錄的地方）。"""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    return Path(path)


def bootstrap_open_machine() -> None:
    """讓 agents 的程式能 import open machine 的 src.*。

    open machine 的 src 用相對路徑（DB/...）與 bare import（from paths import ...），
    所以要 chdir 到根目錄並把 src/ 放進 sys.path。只在需要 src.* 時呼叫。
    """
    os.chdir(ROOT)
    for p in (str(ROOT), str(ROOT / "src")):
        if p not in sys.path:
            sys.path.insert(0, p)


def rel(path: Path | str) -> str:
    """印給使用者看的相對路徑。"""
    try:
        return str(Path(path).resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def assert_not_sensitive(path: Path | str) -> None:
    if Path(path).name in SENSITIVE_FILES:
        raise PermissionError(f"agents 不讀取 {Path(path).name}")


# ------------------------------------------------------------------
def card_path(card_id: str) -> Path:
    return OUT.HYPOTHESIS / f"{card_id}.md"


def idea_path(card_id: str) -> Path:
    return OUT.IDEA / f"{card_id}.json"


def spc_dir(card_id: str) -> Path:
    return OUT.SPC / card_id


def setting_key(region: str, universe: str, delay: int | str) -> str:
    return f"{region}_{universe}_d{delay}"


def data_dir(region: str, universe: str, delay: int | str) -> Path:
    return OM.DATA_LATEST / setting_key(region, universe, delay)


def synced_data_dirs() -> list[Path]:
    """本機已同步的 <REGION>_<UNIVERSE>_d<DELAY> 目錄。"""
    if not OM.DATA_LATEST.exists():
        return []
    return sorted(p for p in OM.DATA_LATEST.iterdir() if p.is_dir() and (p / "data_fields.json").exists())


def resolve_operators_path() -> Path | None:
    """operators.json 的解析順序：使用者帳號快取 → open machine data/latest → 內建預設清單。"""
    for p in (OUT.CACHE / "operators.json", OM.DATA_LATEST / "operators.json", KNOWLEDGE / "operators.json"):
        if p.exists():
            return p
    return None


def resolve_file(name_or_path: str, folder: Path, suffix: str = ".json") -> Path:
    """接受「檔名」「不含副檔名的 id」或「路徑」。"""
    p = Path(name_or_path)
    if p.exists():
        return p
    cand = folder / (name_or_path if name_or_path.endswith(suffix) else name_or_path + suffix)
    return cand
