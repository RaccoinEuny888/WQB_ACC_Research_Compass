"""平台中繼資料（最低讀權限）：operators、dataset 清單。

  python agents/common/brain_meta.py operators [--refresh]
  python agents/common/brain_meta.py datasets --region USA --universe TOP3000 --delay 1 [--refresh]
  python agents/common/brain_meta.py session-status

規則（設計文件 §0 鐵律 5）：
- 先讀本機快取（agents/workspace/cache/）；只有沒有或 --refresh 才連平台。
- 連平台只用 open machine 既有的 src.worker.MyOwnSess，只做 GET。
- session 過期（login_time.pkl 太舊、或平台回 401）→ 停下來，提醒使用者啟動 worker 並登入（/refresh），exit code 2。
  不自行開 session、不讀 cookie、不讀 .env。
- 判斷 session 新鮮度只看 login_time.pkl 的檔案 mtime，不讀其內容。
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from agents.common import paths  # noqa: E402

API = "https://api.worldquantbrain.com"
OPERATORS_API = "https://api.worldquantbrain.com/operators"      # 同 src/data_sync.py 的寫法：端點寫成常數
DATASETS_API = "https://api.worldquantbrain.com/data-sets"
RELOGIN_MSG = ("平台 session 已過期或不存在。請啟動 open machine 的 worker 並登入（Telegram 下 /refresh），"
               "登入後再執行一次。agent 不會自行登入。")


def _timeout_hours() -> float:
    try:
        paths.bootstrap_open_machine()
        from src.worker import TIME_OUT_HOURS  # type: ignore
        return float(TIME_OUT_HOURS)
    except Exception:
        return 4.0


def session_status() -> dict:
    p = paths.ROOT / "login_time.pkl"
    if not p.exists():
        return {"fresh": False, "reason": "沒有 login_time.pkl（worker 從未登入）"}
    age_h = (time.time() - p.stat().st_mtime) / 3600
    limit = _timeout_hours()
    return {"fresh": age_h < limit, "age_hours": round(age_h, 2), "limit_hours": limit,
            "reason": None if age_h < limit else f"上次登入已 {age_h:.1f} 小時，超過 worker 的 {limit:.0f} 小時"}


def _get(path: str, params: dict | None = None):
    """用 open machine 的 session 做一次 GET。401 → 回 None 並印提醒。"""
    st = session_status()
    if not st["fresh"]:
        print(f"[session] {st['reason']}\n{RELOGIN_MSG}")
        return None
    try:
        paths.bootstrap_open_machine()
        from src.worker import MyOwnSess  # type: ignore
        sess = MyOwnSess()
    except Exception as e:  # telegram token 缺、模組缺…
        print(f"[session] 無法建立 open machine 的 session：{e}\n{RELOGIN_MSG}")
        return None
    url = path if path.startswith("http") else API + path
    try:
        resp = sess.sess.get(url, params=params, timeout=60)
    except Exception as e:
        print(f"[network] {e}")
        return None
    if resp.status_code == 401:
        print(f"[session] 平台回 401。\n{RELOGIN_MSG}")
        return None
    if resp.status_code != 200:
        print(f"[api] {url} 回 {resp.status_code}：{resp.text[:200]}")
        return None
    return resp.json()


def _cache(name: str) -> Path:
    return paths.OUT.CACHE / name


def operators(refresh: bool = False) -> Path | None:
    c = _cache("operators.json")
    if c.exists() and not refresh:
        print(f"[cache] {paths.rel(c)}（{len(json.load(open(c, encoding='utf-8')))} 個 operator）")
        return c
    data = _get(OPERATORS_API)
    if data is None:
        fb = paths.resolve_operators_path()
        print(f"[fallback] 改用 {paths.rel(fb) if fb else '（無）'}")
        return fb
    ops = data if isinstance(data, list) else data.get("results", data)
    paths.ensure_parent(c)
    with open(c, "w", encoding="utf-8") as f:
        json.dump(ops, f, ensure_ascii=False, indent=2)
    print(f"[saved] {paths.rel(c)}（{len(ops)} 個 operator，使用者帳號可用清單）")
    return c


def datasets(region: str, universe: str, delay: int, refresh: bool = False) -> Path | None:
    key = paths.setting_key(region, universe, delay)
    c = _cache(f"datasets_{key}.json")
    if c.exists() and not refresh:
        print(f"[cache] {paths.rel(c)}")
        return c
    out, offset, limit = [], 0, 50
    while True:
        page = _get(DATASETS_API, {"instrumentType": "EQUITY", "region": region, "universe": universe,
                                   "delay": delay, "limit": limit, "offset": offset})
        if page is None:
            return None
        results = page.get("results", [])
        out.extend(results)
        offset += limit
        if len(results) < limit or offset >= page.get("count", 0):
            break
    paths.ensure_parent(c)
    with open(c, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"[saved] {paths.rel(c)}（{len(out)} 個 dataset）")
    return c


def main() -> int:
    ap = argparse.ArgumentParser(description="平台中繼資料（最低讀權限）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    o = sub.add_parser("operators"); o.add_argument("--refresh", action="store_true")
    d = sub.add_parser("datasets"); d.add_argument("--region", required=True); d.add_argument("--universe", required=True)
    d.add_argument("--delay", type=int, required=True); d.add_argument("--refresh", action="store_true")
    sub.add_parser("session-status")
    args = ap.parse_args()
    if args.cmd == "session-status":
        print(json.dumps(session_status(), ensure_ascii=False))
        return 0
    if args.cmd == "operators":
        return 0 if operators(args.refresh) else 2
    return 0 if datasets(args.region, args.universe, args.delay, args.refresh) else 2


if __name__ == "__main__":
    sys.exit(main())
