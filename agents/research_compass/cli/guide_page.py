"""新手地圖頁（A 段）：單檔 HTML → agents/workspace/dashboard/index.html

  python agents/research_compass/cli/guide_page.py [--open] [--preview A3]

分頁 1「新手地圖」：你在這裡＋A1～A7 全程地圖；每一關是下拉，內容來自 knowledge/onboarding_A.md，
        A5 另附三個設定檔的逐行說明（使用者機器上實際的值）。
分頁 2「專案管理」：A5 完成後長出四條泳道（方向待定／研究中／模擬中／結案），另有待辦；
        A5 之前只有待辦時才產生這一頁。
B 段（A1～A7 完成）整頁換成 B 版：研究地圖（樞紐＋R1 兩小步，來自 knowledge/onboarding_B.md）、專案管理、dataset 圖鑑
        （dataset_snapshot.py 的優先順序熱力圖＋ DB/ResearchDB/data/subdataset/ 的 profile 卡）。
B 段也由這一支畫（舊版 build_dashboard.py 已封存）。
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from agents.common import paths  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent))
import onboard  # noqa: E402

KNOW = paths.AGENTS / "research_compass" / "knowledge"
OUT_HTML = paths.OUT.DASHBOARD / "index.html"
e = html.escape


def _inline(s: str) -> str:
    s = e(s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r'<a href="\2" target="_blank">\1</a>', s)
    s = re.sub(r'(?<!href=")(https?://[^\s<）)"]+)', r'<a href="\1" target="_blank">\1</a>', s)
    return s


def md_to_html(md: str) -> str:
    """夠用的 Markdown 轉換：標題、清單、程式碼區塊、表格、引言、段落。"""
    out, lines, i = [], md.splitlines(), 0
    in_list = False

    def close_list():
        nonlocal in_list
        if in_list:
            out.append("</ul>"); in_list = False

    while i < len(lines):
        ln = lines[i]
        st = ln.strip()
        if st.startswith("```"):
            close_list()
            buf = []; i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                buf.append(lines[i]); i += 1
            indent = min((len(b) - len(b.lstrip()) for b in buf if b.strip()), default=0)
            out.append("<pre>" + e("\n".join(b[indent:] for b in buf)) + "</pre>")
        elif st.startswith("|") and i + 1 < len(lines) and re.match(r"^\s*\|[\s:|-]+\|\s*$", lines[i + 1]):
            close_list()
            head = [c.strip() for c in st.strip("|").split("|")]
            out.append("<table><tr>" + "".join(f"<th>{_inline(c)}</th>" for c in head) + "</tr>")
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                out.append("<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in cells) + "</tr>"); i += 1
            out.append("</table>"); continue
        elif re.match(r"^#{1,4}\s", st):
            close_list()
            n = len(st) - len(st.lstrip("#"))
            out.append(f"<h{min(n + 2, 5)}>{_inline(st.lstrip('#').strip())}</h{min(n + 2, 5)}>")
        elif re.match(r"^(\s*)([-*]|\d+\.)\s+", ln):
            if not in_list:
                out.append("<ul>"); in_list = True
            depth = (len(ln) - len(ln.lstrip())) // 2
            txt = re.sub(r"^(\s*)([-*]|\d+\.)\s+", "", ln)
            cls = ' class="q"' if txt.startswith("↳") else ""
            out.append(f'<li style="margin-left:{depth * 16}px"{cls}>{_inline(txt)}</li>')
        elif st.startswith(">"):
            close_list(); out.append(f"<blockquote>{_inline(st.lstrip('> ').strip())}</blockquote>")
        elif st == "" or st == "---":
            close_list()
        else:
            close_list(); out.append(f"<p>{_inline(st)}</p>")
        i += 1
    close_list()
    return "\n".join(out)


AGENT_ONLY = ("- 完成判斷", "- 完成時說一句", "- 完成時地圖頁", "- 最常卡住的地方", "走完 R")   # 「走完 Rn：回樞紐…」是給羅盤的過場
AGENT_BLOCK = ("- 羅盤補充",)  # 這一行連同底下縮排的子項目都只給羅盤看


def for_user(section: str) -> str:
    """onboarding_A.md 同時是羅盤的指示與地圖頁的內容；這裡把只給羅盤看的部分拿掉。
    - 「完成判斷」「完成時說一句」「最常卡住的地方」整行不顯示
    - 延伸問題 `↳ 問題 → 給羅盤的指示 ｜頁面：給使用者的答案`：只顯示問題與「頁面」那段
    """
    out = []
    skip_block = False
    for ln in section.splitlines():
        st = ln.strip()
        if skip_block:
            if ln.startswith("  ") or not st:
                continue
            skip_block = False
        if st.startswith(AGENT_BLOCK):
            skip_block = True
            continue
        if st.startswith(AGENT_ONLY):
            continue
        if "↳" in st:
            head = ln[: ln.index("↳")]
            body = st[st.index("↳"):]
            q = body.split(" → ")[0].split("｜頁面：")[0].strip()
            ans = body.split("｜頁面：", 1)[1].strip() if "｜頁面：" in body else ""
            out.append(f"{head}{q}")
            if ans:
                out.append(f"{head}  {ans}")
            continue
        ln = ln.replace("**一定要說的安全提醒**", "**安全提醒**").replace("- 一定要說：", "- 提醒：").replace("- 說明：", "- ")
        ln = re.sub(r"- 延伸問題（[^）]*）：", "- 延伸問題：", ln)
        # 頁面上不放「為什麼：」「怎麼做：」這類標籤；「怎麼做（…）：」留括號裡的話
        ln = re.sub(r"^(\s*-\s*)怎麼做（(.+?)）：", r"\1\2：", ln)
        ln = re.sub(r"^(\s*-\s*)(為什麼|怎麼做)：\s*", r"\1", ln)
        if re.fullmatch(r"\s*-\s*", ln):
            continue
        out.append(ln)
    return "\n".join(out)


def step_sections() -> dict[str, str]:
    md = (KNOW / "onboarding_A.md").read_text(encoding="utf-8")
    parts = re.split(r"^## (A\d) .*$", md, flags=re.M)
    out = {}
    for j in range(1, len(parts), 2):
        out[parts[j]] = for_user(parts[j + 1].strip())
    return out


# 每個欄位一句註解（逐行顯示在程式碼右側）；KEY_* 是新手最該看的重點行
GA_NOTES = {
    "parent_num": "每代留幾支當父母｜建議 5", "kid_num": "每代產生幾支｜建議 30", "generation_num": "跑幾代｜建議 3",
    "mutation_rate": "選項隨機換掉的機率", "early_stop_patience": "連續幾代沒進步就停",
    "bcorr_threshold": "太像的只留一支（越低越多樣）", "pnl_wait_timeout_seconds": "等 PnL 最多幾秒｜不用動",
    "pnl_poll_seconds": "多久查一次 PnL｜不用動", "arc_layer": "跑完多跑一層 ARC｜第一次 false",
    "arc_setting_file": "ARC 那層用的設定檔",
}
SETTING_NOTES = {
    "decay": "訊號平滑天數；建議設 0，並在 template 中用 op 做平滑", "delay": "1＝用前一天的資料", "instrumentType": "固定，不用動",
    "language": "固定，不用動", "nanHandling": "空值怎麼處理", "neutralization": "中性化：GA 支援多基因位",
    "pasteurization": "不在股票池的設為空值", "region": "哪個市場", "truncation": "單一股票最大權重；universe 越大，建議設越小",
    "unitHandling": "單位檢查", "universe": "股票池", "maxTrade": "交易量上限", "maxPosition": "部位上限",
    "testPeriod": "留多久當測試期", "visualization": "建議開 true，並把結果存到本地（機器目前不支援；想要可以請研究羅盤記到待辦）", "lookback": "回看天數",
    "simulationMode": "模擬模式",
}
KEY_GA = {"parent_num", "kid_num", "generation_num", "arc_layer"}
KEY_SETTING = {"region", "universe", "neutralization", "truncation", "decay", "visualization"}
TEMPLATE_HINTS = [("<model_data>", "取一個欄位，補缺值、壓極端值", False), ("compare_days =", "要跟多久以前比", False),
                  ("compare_data =", "跟自己過去的什麼比", False), ("diff =", "怎麼比（相減／相除／迴歸）", False),
                  ("<sign>", "同群比較 → 平滑 → 決定做多或做空", False)]


def _row(n: int, code: str, note: str, key: bool) -> str:
    return (f'<div class="ln{" key" if key else ""}"><span class="no">{n}</span><code class="c">{e(code)}</code>'
            f'<span class="nt">{e("# " + note) if note else ""}</span></div>')


# 檔案裡沒有、但新手應該知道的欄位：在框的最後補上（虛線、標註「檔案裡沒有」）
GA_OPTIONAL = [('"arc_layer": false,', "arc_layer"), ('"arc_setting_file": "default_arc_setting.json"', "arc_setting_file")]


def _json_panel(p: Path, notes: dict, keys: set, optional: list | None = None) -> str:
    rows, present = [], set()
    lines = p.read_text(encoding="utf-8").rstrip().splitlines()
    for i, line in enumerate(lines, 1):
        m = re.match(r'\s*"([^"]+)"\s*:', line)
        k = m.group(1) if m else None
        if k:
            present.add(k)
        rows.append(_row(i, line, notes.get(k, "") if k else "", k in keys))
    missing = [(code, k) for code, k in (optional or []) if k not in present]
    if missing:
        rows.append('<div class="addhint">要跑 ARC 時，在 } 前面加上這兩行（前一行結尾記得補逗號）：</div>')
        for code, k in missing:
            rows.append(f'<div class="ln opt"><span class="no">+</span><code class="c">  {e(code)}</code><span class="nt">{e("# " + notes.get(k, ""))}</span></div>')
    return "".join(rows)


def _template_panel(p: Path) -> str:
    t = json.loads(p.read_text(encoding="utf-8"))
    rows, n = [], 0
    n += 1; rows.append(_row(n, "template:", "要開 space 就把欄位替換成 <名稱>", True))
    for line in (t.get("template") or "").splitlines():
        n += 1
        hint = next(((h, k) for pat, h, k in TEMPLATE_HINTS if pat in line), ("", False))
        rows.append(_row(n, "  " + line, hint[0], hint[1]))
    n += 1; rows.append(_row(n, "gene_pool:", "每個空格可以填哪些選項", False))
    for k, v in (t.get("gene_pool") or {}).items():
        n += 1
        shown = json.dumps(v, ensure_ascii=False)
        shown = shown if len(shown) <= 38 else shown[:36] + "…]"
        rows.append(_row(n, f"  {k}: {shown}", f"space 大小：{len(v)}" if isinstance(v, list) else "", k == "<model_data>"))
    return "".join(rows)


def config_block(st: dict) -> str:
    panels = []
    for title, sub, folder, name, kind in (
            ("GA 設定檔", "GA 怎麼跑", paths.OM.GA_CONFIG, "default_ga_config.json", "ga"),
            ("模擬設定檔", "每條 expression 用什麼條件模擬（region、universe…）", paths.OM.SETTING, "default_setting.json", "setting"),
            ("Template", "決定要試哪些 space", paths.OM.TEMPLATE, "default_template.json", "template")):
        p = folder / name
        if not p.exists():
            panels.append(f'<div class="panel"><div class="ph"><b>{title}</b><span>{e(paths.rel(p))} 不存在</span></div></div>')
            continue
        body = (_json_panel(p, GA_NOTES, KEY_GA, GA_OPTIONAL) if kind == "ga" else
                _json_panel(p, SETTING_NOTES, KEY_SETTING) if kind == "setting" else _template_panel(p))
        panels.append(f'<div class="panel"><div class="ph"><b>{title}</b><span>{e(sub)}</span>'
                      f'<span class="path">{e(paths.rel(p))}</span></div><div class="code"><div class="inner">{body}</div></div></div>')
    est = st.get("ga_estimated_simulations")
    note = f'目前設定約會送出 <b>{est}</b> 支模擬（kid_num × generation_num）。' if est else ""
    return ('<div class="cfg"><div class="cfgh"><h4>三個設定檔（你機器上目前的值）</h4>'
            '<button class="kbtn" onclick="this.closest(\'.cfg\').classList.toggle(\'only\');'
            'this.textContent=this.closest(\'.cfg\').classList.contains(\'only\')?\'顯示全部\':\'只看重點行\'">只看重點行</button></div>'
            f'<div class="muted">紅框是第一次最該看的行。{note}</div>'
            '<div class="panels">' + "".join(panels) + "</div></div>")


CSS = """
body{font-family:-apple-system,"Noto Sans TC","PingFang TC",sans-serif;margin:0;background:#f7f4ee;color:#222;line-height:1.6}
.tabs{display:flex;gap:4px;padding:0 20px;background:#fff;border-bottom:1px solid #e6e0d4;position:sticky;top:0;z-index:5}
.tab{padding:12px 18px 8px;cursor:pointer;border-bottom:3px solid transparent;font-size:15px;font-weight:600}
.tab small{display:block;font-weight:400;font-size:11px;color:#888} .tab.on{border-color:#b7472a}
.page{display:none;padding:18px 24px;max-width:1440px} .page.on{display:block}
.here{background:#fff;border-left:6px solid #b7472a;border-radius:8px;padding:14px 18px;margin:8px 0 18px;box-shadow:0 1px 3px rgba(0,0,0,.06)}
.here .big{font-size:20px;font-weight:700} .here .sub{color:#555;font-size:13.5px}
.map{display:flex;align-items:flex-start;gap:0;margin:6px 0 22px;flex-wrap:wrap}
.node{flex:1;min-width:120px;text-align:center;position:relative;padding-top:4px}
.node .dot{width:34px;height:34px;border-radius:50%;margin:0 auto 6px;display:flex;align-items:center;justify-content:center;font-weight:700;background:#e3ddd0;color:#777;position:relative;z-index:2}
.node.done .dot{background:#4a7c6f;color:#fff} .node.cur .dot{background:#b7472a;color:#fff;box-shadow:0 0 0 5px rgba(183,71,42,.18)}
.node:not(:last-child)::after{content:"";position:absolute;top:21px;left:50%;width:100%;height:3px;background:#e3ddd0;z-index:1}
.node.done:not(:last-child)::after{background:#4a7c6f}
.node .nm{font-size:13px;font-weight:600} .node .st{font-size:11.5px;color:#888}
.node.next .dot{background:#fff;border:2px dashed #c9c2b4}
details.step{background:#fff;border:1px solid #e6e0d4;border-radius:8px;margin:8px 0;padding:0 16px}
details.step>summary{cursor:pointer;padding:12px 0;font-weight:700;font-size:15px;list-style:none;display:flex;align-items:center;gap:10px}
details.step>summary::before{content:"▸";color:#b7472a} details.step[open]>summary::before{content:"▾"}
.pill{font-size:11px;font-weight:600;border-radius:10px;padding:1px 9px;color:#fff;background:#999} .pill.done{background:#4a7c6f} .pill.cur{background:#b7472a}
.why{font-weight:400;font-size:12px;color:#888;margin-left:auto}
pre{background:#2b2b2b;color:#f1efe9;padding:10px 12px;border-radius:6px;overflow-x:auto;font-size:12.5px;line-height:1.5}
code{background:#eee9df;padding:1px 5px;border-radius:3px;font-size:12.5px} pre code{background:none}
table{border-collapse:collapse;font-size:13px;margin:8px 0;width:100%} th,td{border:1px solid #e6e0d4;padding:5px 8px;text-align:left;vertical-align:top} th{background:#efebe3}
li.q{list-style:none;margin-left:0!important;color:#2f5d8a;font-weight:600} ul{padding-left:20px}
blockquote{margin:6px 0;padding:4px 12px;border-left:3px solid #c9c2b4;color:#555}
.cfg{border-top:1px dashed #e3ddd0;margin-top:12px;padding-top:6px}
.cfgh{display:flex;align-items:center;justify-content:space-between;gap:10px} .cfgh h4{margin:8px 0}
.kbtn{border:1px solid #c9c2b4;background:#fff;border-radius:16px;padding:3px 12px;font-size:12.5px;cursor:pointer}
.panels{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin:10px 0 6px}
@media (max-width:960px){.panels{grid-template-columns:1fr}}
.panel{background:#24221f;border-radius:10px;overflow:hidden;display:flex;flex-direction:column}
.ph{display:flex;flex-wrap:wrap;align-items:baseline;gap:8px;padding:8px 12px;background:#2f2c28;color:#f1efe9;font-size:13px}
.ph span{color:#b9b2a5;font-size:11.5px} .ph .path{margin-left:auto;font-family:ui-monospace,Menlo,monospace;font-size:10.5px}
.code{padding:8px;overflow-x:auto} .inner{display:inline-block;min-width:100%}
.ln{display:grid;grid-template-columns:22px max-content minmax(max-content,1fr);gap:8px;align-items:baseline;padding:3px 8px;margin:3px 0;border:1px solid transparent;border-radius:5px;font-size:12px;line-height:1.45}
.ln .no{color:#7d776d;text-align:right;font-family:ui-monospace,Menlo,monospace} .ln .c{background:none;color:#f1efe9;white-space:pre;font-family:ui-monospace,Menlo,monospace;font-size:12px;padding:0}
.ln .nt{color:#9c958a;font-size:11.5px;text-align:right;white-space:nowrap;padding-left:16px}
.ln.key{border-color:#d4664a;background:rgba(212,102,74,.08)} .ln.key .nt{color:#f0b4a3}
.cfg.only .ln:not(.key):not(.opt){display:none}
.ln.opt{border:1px dashed #8a8170} .ln.opt .c{color:#cfc8bb} .addhint{color:#b9b2a5;font-size:11.5px;margin:10px 4px 2px}
.lanes{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:10px 0 18px} @media (max-width:1100px){.lanes{grid-template-columns:repeat(2,minmax(0,1fr))}} @media (max-width:640px){.lanes{grid-template-columns:1fr}}
.ids{font-family:ui-monospace,Menlo,monospace;font-size:11.5px;color:#2f5d8a;margin-top:4px;word-break:break-all}
.lane{background:#efebe3;border-radius:10px;padding:12px;min-height:120px} .lane h3{margin:0 0 2px;font-size:14px} .lane .desc{color:#777;font-size:12px;margin:0 0 10px}
.lane.todo-lane{max-width:420px}
.card{background:#fff;border:1px solid #e3ddd0;border-left:4px solid #2f5d8a;border-radius:8px;padding:8px 10px;margin-bottom:8px;font-size:13px}
.card.auto{border-left-color:#4a7c6f} .card .tag{float:right;font-size:11px;color:#fff;background:#999;border-radius:10px;padding:0 8px} .card .tag.run{background:#b7472a} .card .tag.fin{background:#4a7c6f}
.empty{color:#999;font-size:12px;font-style:italic}
.todo{background:#fff;border:1px solid #e3ddd0;border-left:4px solid #8a6d3b;border-radius:8px;padding:8px 10px;margin-bottom:8px;font-size:13px}
.prog{background:#fff;border:1px solid #e6e0d4;border-radius:8px;padding:8px 12px;margin:8px 0;font-size:13px} .prog b{color:#b7472a}
.muted{color:#777;font-size:12px} h3,h4,h5{margin:14px 0 6px}
.meta{color:#888;font-size:12px;margin:0 0 10px} .intro{margin:0 0 12px;color:#444;font-size:14px}
"""
JS = """
document.querySelectorAll('.tab').forEach(function(t){t.onclick=function(){
 document.querySelectorAll('.tab').forEach(function(x){x.classList.remove('on')});document.querySelectorAll('.page').forEach(function(x){x.classList.remove('on')});
 t.classList.add('on');document.getElementById(t.dataset.p).classList.add('on')}});
function filt(gid,chip,q){var bar=document.getElementById(gid+'-bar');if(chip){bar.querySelectorAll('.chip').forEach(function(x){x.classList.remove('on')});chip.classList.add('on');}
 var on=bar.querySelector('.chip.on'),v=on?on.dataset.v:'';var s=bar.querySelector('.csearch');q=(s?s.value:'').toLowerCase();
 document.querySelectorAll('#'+gid+' > .hc').forEach(function(c){var ok=(!v||c.dataset.v===v)&&(!q||c.textContent.toLowerCase().indexOf(q)>=0);c.style.display=ok?'':'none';});}
function goCard(id){var t=document.querySelector('.tab[data-p="g5"]');if(!t)return;t.click();
 var bar=document.getElementById('hcg-bar');if(bar){var s=bar.querySelector('.csearch');if(s)s.value='';filt('hcg',bar.querySelector('.chip'));}
 var r=document.getElementById('hc-'+id);if(r){r.scrollIntoView({behavior:'smooth',block:'center'});r.classList.add('flash');setTimeout(function(){r.classList.remove('flash')},2200);}}
"""


def progress_block(st: dict) -> str:
    """A6 下拉最上方：每條研究跑到哪、分析做好了沒、佇列數。"""
    q = st["queues"]
    rows = []
    for x in st.get("research_detail", []):
        state = "分析做好了，可以看 analysis/ 裡的圖表" if x["analysis_done"] else f"跑到第 <b>{x['generation']}</b> 代，分析還沒產出"
        rows.append(f'<div class="prog"><code>{e(x["name"])}</code>　{state}　<span class="muted">更新 {e(x["updated_at"].replace("T", " "))}</span></div>')
    if not rows:
        rows.append('<div class="prog muted">還沒有研究。</div>')
    rows.append(f'<div class="prog">佇列：pending <b>{q["pending"]}</b>（排隊中）、running {q["running"]}、complete <b>{q["complete"]}</b>（已回來）</div>')
    return "".join(rows)


def lanes_block(st: dict) -> str:
    out = []
    for lane in st.get("lanes", []):
        cards = []
        for c in lane["cards"]:
            tag, click, note = "", "", c.get("note", "")
            if c.get("kind") == "hypothesis":
                # 占卜家的假說卡：白話狀態；點了跳到「靈感卡」分頁的同一張卡
                lab = CARD_STATUS.get(c.get("status", ""), (c.get("status", ""),))[0]
                note = note.replace(f"· {c.get('status')}", f"· {lab}")
                tag = '<span class="tag hy">假說卡</span>'
                click = f' onclick="goCard(\'{e(c.get("card_id", ""))}\')" title="看這張卡的完整內容"'
            elif c.get("auto"):
                tag = f'<span class="tag {"fin" if c.get("status") == "跑完了" else "run"}">{e(c.get("status", ""))}</span>'
            ids = ""
            if c.get("regular_ids") or c.get("power_pool_ids"):
                ids = ('<div class="ids">' + (f'regular：{e(", ".join(c["regular_ids"]))}' if c.get("regular_ids") else "")
                       + ("<br>" if c.get("regular_ids") and c.get("power_pool_ids") else "")
                       + (f'Power Pool：{e(", ".join(c["power_pool_ids"]))}' if c.get("power_pool_ids") else "") + "</div>")
            cards.append(f'<div class="card{" auto" if c.get("auto") else ""}{" link" if click else ""}"{click}>{tag}{e(c["title"])}'
                         f'<div class="muted">{e(note)}{"　" if note else ""}{e(c.get("at", ""))}</div>{ids}</div>')
        body = "".join(cards) if cards else '<div class="empty">（還沒有）</div>'
        out.append(f'<div class="lane"><h3>{e(lane["lane"])} <span class="muted">{len(lane["cards"])}</span></h3><div class="desc">{e(lane["desc"])}</div>{body}</div>')
    return '<div class="lanes">' + "".join(out) + "</div>"


def render(st: dict) -> str:
    secs = step_sections()
    cur = st["current"]
    todos = [t for t in st.get("todos", []) if not t.get("done")]
    a5_done = next((s["done"] for s in st["steps"] if s["id"] == "A5"), False)
    if cur:
        cs = next(s for s in st["steps"] if s["id"] == cur)
        here = (f'<div class="here"><div class="sub">你在這裡</div><div class="big">準備機器　第 {cur[1]} 步／共 {st["n_total"]} 步：{e(cs["name"])}</div>'
                f'<div class="sub">已完成 {st["n_done"]} 步。回到 Claude Code 輸入 <code>/research-compass</code>，我會帶你做這一步；畫面出現看不懂的訊息，直接貼給我。</div></div>')
    else:
        here = ('<div class="here"><div class="sub">你在這裡</div><div class="big">機器會用了，第一次的結果也看過了</div>'
                '<div class="sub">接下來是你自己的研究。回到 Claude Code 輸入 <code>/research-compass</code>，從選 dataset 開始。</div></div>')
    nodes = []
    for s in st["steps"]:
        cls = "done" if s["done"] else ("cur" if s["id"] == cur else "")
        nodes.append(_node(cls, "✓" if s["done"] else s["id"][1], s["name"], "完成" if s["done"] else ("現在" if s["id"] == cur else "")))
    for n in NEXT_PHASE:
        nodes.append(f'<div class="node next"><div class="dot"></div><div class="nm" style="color:#999">{e(n)}</div><div class="st">之後</div></div>')
    steps_html = a_details(st, cur)
    tabs = [("g1", "新手地圖", "你在這裡")]
    pages = {"g1": here + '<div class="map">' + "".join(nodes) + "</div>" + steps_html}
    if a5_done or todos:
        tabs.append(("g2", "專案管理", "你的研究"))
        todo_html = ""
        if todos:
            todo_html = ('<div class="lane todo-lane"><h3>待辦 <span class="muted">' + str(len(todos)) + '</span></h3><div class="desc">想做但還沒做的事（羅盤幫你記的）</div>'
                         + "".join(f'<div class="todo">{e(t["text"])}<div class="muted">{e(t["added_at"][:10])} 記錄</div></div>' for t in todos) + '</div>')
        if a5_done:
            pages["g2"] = ('<p class="intro">每一條研究是一張卡，從左往右走：方向待定 → 研究中 → 模擬中 → 結案。GA 跑的研究會自動出現在「模擬中」；'
                           '看完結果後，研究羅盤會把能交的 alpha ID 記在卡上、移到「結案」；其他的卡跟研究羅盤說一聲，它會幫你放上去、移過去。</p>' + lanes_block(st) + todo_html)
        else:
            pages["g2"] = '<p class="intro">這裡先記下你想做的事；啟動第一次 GA 之後，這一頁會長出你的研究泳道。</p>' + todo_html
    if onboard.hypothesis_cards():
        tabs.append(("g5", "靈感卡", "占卜家的假說")); pages["g5"] = tab_hypothesis()
    nav = '<div class="tabs">' + "".join(f'<div class="tab{" on" if i == 0 else ""}" data-p="{p}">{e(t)}<small>{e(s)}</small></div>' for i, (p, t, s) in enumerate(tabs)) + "</div>"
    meta = f'<div class="meta">研究羅盤 · 更新於 {e(st["checked_at"].replace("T", " ")[:16])} · 進度由你機器上的檔案自動判斷 · 重新整理：在 Claude Code 輸入 <code>/research-compass</code></div>'
    body = "".join(f'<div class="page{" on" if i == 0 else ""}" id="{p}">{meta}{pages[p]}</div>' for i, (p, _, _) in enumerate(tabs))
    return (f'<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>研究羅盤：新手地圖</title><style>{CSS}{B_CSS}</style></head><body>{nav}{body}'
            f'<script>{JS}</script></body></html>')


# ====================================================================== B 段：研究地圖（樞紐）＋ dataset 圖鑑
B_KNOW = KNOW / "onboarding_B.md"
B_CSS = """
.journey{display:flex;align-items:stretch;margin:6px 0 22px;background:#fff;border:1px solid #e6e0d4;border-radius:12px;padding:14px 10px 6px}
.journey .aline{flex:0 0 150px;display:flex;align-items:flex-start;align-self:flex-start;margin:0} .journey .aline .node{flex:1;min-width:0}
.node.link::after{content:"";position:absolute;top:21px;left:50%;width:50%;height:3px;background:#e3ddd0;z-index:1}
.node.done.link::after{background:#4a7c6f}
.bus{flex:0 0 3px;background:#e3ddd0;margin:21px 0 83px}
.branches{flex:1;display:flex;flex-direction:column;min-width:0}
.map.branch{display:flex;flex-wrap:nowrap;min-height:104px;margin:0;align-items:flex-start}
.map.branch .node{flex:0 0 25%;min-width:0;max-width:25%;padding:4px 6px 0;box-sizing:border-box}
.map.branch .node:first-child::before{content:"";position:absolute;top:21px;right:50%;width:50%;height:3px;background:#e3ddd0;z-index:1}
.map.branch .node .dot{font-size:12.5px} .map.branch .node .nm{font-size:13px;line-height:1.35;margin-top:2px}
.map.branch .node.cur .nm{color:#b7472a} .map.branch .node.done .nm{color:#2f5d4a}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:18px;align-items:start} @media (max-width:1100px){.cols{grid-template-columns:1fr}}
.cols h3{margin:4px 0 8px;font-size:15px} .cols .panels{grid-template-columns:1fr}
.rhead{font-weight:700;font-size:13.5px;margin:14px 0 4px;color:#444}
tr.avoid td{color:#8a5a3c} tr.avoid code{background:#fbeee6}
.hm{border-collapse:separate;border-spacing:3px;font-size:12px} .hm th{background:#efebe3;padding:6px 8px;border:none;position:sticky;top:0}
.hm td{border:none;border-radius:6px;padding:6px 8px;min-width:150px;cursor:pointer;vertical-align:top;background:#f1ede4}
.hm td.p3{background:#f3c7b6} .hm td.p2{background:#f8dfcf} .hm td.p1{background:#fbeee6} .hm td.none{background:#f7f4ee;color:#bbb;cursor:default}
.hm td .top{font-family:ui-monospace,Menlo,monospace;font-weight:700} .hm td .nums{color:#555;font-size:11px}
.hm td.sel{outline:2px solid #b7472a}
.detail{display:none;background:#fff;border:1px solid #e6e0d4;border-radius:8px;padding:10px 14px;margin:10px 0} .detail.on{display:block}
.card.link{cursor:pointer} .card.link:hover{border-color:#b7472a} .tag.hy{background:#e8eef6;color:#2f5d8a}
tr.flash td{background:#fdf3e4;transition:background .3s}
.chips{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:10px 0 16px} .chip{border:1px solid #ddd5c6;background:#fff;border-radius:999px;padding:5px 14px;font-size:13px;cursor:pointer;color:#444}
.chip b{color:#b7472a;margin-left:2px} .chip.on{background:#222;color:#fff;border-color:#222} .chip.on b{color:#f3b9a4}
.csearch{margin-left:auto;border:1px solid #ddd5c6;border-radius:8px;padding:7px 12px;font-size:13px;min-width:240px;background:#fff}
.cgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:18px} .cgrid.two{grid-template-columns:repeat(auto-fill,minmax(480px,1fr))}
@media (max-width:560px){.cgrid,.cgrid.two{grid-template-columns:1fr}}
.hc{background:#fffdf8;border:1px solid #e6e0d4;border-radius:10px;padding:16px 18px 12px;display:flex;flex-direction:column;gap:10px}
.hc-top{display:flex;align-items:center;gap:8px;flex-wrap:wrap} .hc-id{color:#b7472a;font-family:Georgia,serif;font-size:17px} .hc-id.mono{font-family:ui-monospace,Menlo,monospace;font-weight:700;color:#222;font-size:15px}
.pill2{background:#ece8e0;color:#555;border-radius:999px;padding:2px 10px;font-size:12px} .pill2.bad{background:#f6dcd6;color:#b7472a;border:1px solid #e9b3a6}
.chan{margin-left:auto;border:1px dashed #d9a066;color:#b5651d;background:#fdf3e4;border-radius:999px;padding:2px 10px;font-size:12px}
.hc-title{font-weight:700;font-size:15px;line-height:1.55} .hc-desc{font-size:13.5px;line-height:1.6}
.gates{display:flex;gap:6px;flex-wrap:wrap} .gates span{background:#ece8e0;color:#666;border-radius:4px;padding:2px 8px;font-size:12px}
.hc-box{background:#efe9df;border-left:3px solid #4a7c6f;border-radius:4px;padding:10px 14px;font-size:13px;line-height:1.7} .hc-box .kv{margin:2px 0 4px}
.hc-next{font-size:12.5px;color:#2f5d8a} .hc details summary{color:#2f5d8a;cursor:pointer;font-size:13px}
.hc-foot{margin-top:auto;border-top:1px dashed #ddd5c6;padding-top:8px;display:flex;flex-wrap:wrap;gap:4px 14px;font-size:12px;color:#888} .hc-foot .ds{color:#2f5d4a;font-weight:600} .hc-foot .fn{margin-left:auto}
.hc.flash{box-shadow:0 0 0 3px #f0c9a0;transition:box-shadow .3s}
.hmtitle{border-left:4px solid #b7472a;padding-left:10px;margin:8px 0 10px;font-size:17px}
.hm2{border-collapse:separate;border-spacing:2px;font-size:13px} .hm2 th{font-weight:600;padding:4px 8px;text-align:left;color:#333}
.hm2 th small{display:block;font-weight:400;color:#999;font-size:10.5px} .hm2 th.cat{padding-right:14px;white-space:nowrap}
.hm2 th,.hm2 td{border:none;background:transparent} .hm2 td:empty{background:transparent}
.hm2 td{min-width:58px;height:30px;text-align:center;border-radius:3px;font-weight:600;cursor:default}
.hm2 td.s1{background:#dde8e0;color:#3a5a48} .hm2 td.s2{background:#b9d0c0;color:#2c4a3a} .hm2 td.s3{background:#86ab93;color:#fff}
.hm2 td.s4{background:#4f8066;color:#fff} .hm2 td.s5{background:#1f4d3a;color:#fff} .hm2 td.s0{background:#f1ede4;color:#999}
.recs{background:#fdf3e4;border:1px solid #f0d9b5;border-radius:8px;padding:10px 14px;margin:14px 0;line-height:1.9} .warn{color:#b7472a}
.dcard{margin:14px 0 22px} .dhead{display:flex;gap:12px;align-items:baseline;flex-wrap:wrap} .dname{font-family:ui-monospace,Menlo,monospace;font-weight:700;font-size:16px}
.site{color:#2f6b4f;font-size:12.5px;font-weight:600} .dcard p{margin:8px 0}
.dbox{display:grid;grid-template-columns:1fr 1fr;gap:18px;background:#efe9df;border-radius:6px;padding:12px 16px;font-size:13px;line-height:1.7}
@media (max-width:900px){.dbox{grid-template-columns:1fr}} .dbox .kv{margin:2px 0 6px}
.dcard details summary{color:#2f5d8a;cursor:pointer;margin:10px 0 4px;font-size:13.5px}
.gt{width:100%;border-collapse:collapse;font-size:13px} .gt th{text-align:left;border-bottom:1px solid #ddd;padding:6px 8px} .gt td{border-bottom:1px solid #eee;padding:7px 8px;vertical-align:top} .gt td.num{text-align:right}
.pcard{background:#fff;border:1px solid #e6e0d4;border-left:5px solid #2f5d8a;border-radius:8px;padding:12px 16px;margin:10px 0}
.pcard h4{margin:0 0 4px} .pcard .k{color:#888;font-size:12px;margin-top:8px} .pcard .g{margin:4px 0;font-size:13px} .pcard code{font-size:11.5px}
"""
B_JS = """
function hmsel(id){document.querySelectorAll('.detail').forEach(function(x){x.classList.remove('on')});document.querySelectorAll('.hm td').forEach(function(x){x.classList.remove('sel')});
 var d=document.getElementById(id);if(d){d.classList.add('on');} var c=document.querySelector('[data-d="'+id+'"]');if(c){c.classList.add('sel');}}
"""


def b_sections() -> tuple[dict[str, str], dict[str, str]]:
    """onboarding_B.md → 每一小步（### Rn-n）與 R2～R4 的段落（## Rn）。"""
    md = B_KNOW.read_text(encoding="utf-8") if B_KNOW.exists() else ""
    steps, routes = {}, {}
    for m in re.finditer(r"^### (R\d-\d) [^\n]*\n(.*?)(?=^### |^## |^---|\Z)", md, flags=re.M | re.S):
        steps[m.group(1)] = for_user(m.group(2).strip())
    for m in re.finditer(r"^## (R[2-5]) [^\n]*\n(.*?)(?=^## |\Z)", md, flags=re.M | re.S):
        routes[m.group(1)] = for_user(m.group(2).strip())
    return steps, routes


def _shade(score: float | None, hi: float) -> int:
    """加權分數 → 0～5 級深淺（相對於全表最高分）。"""
    if score is None or hi <= 0:
        return 0
    return max(1, min(5, int(score / hi * 5 + 0.999)))


def _site_label(key: str) -> tuple[str, str]:
    """USA_TOP3000_d1 → ("USA", "TOP3000")；delay 不是 1 才標出來。"""
    parts = key.split("_")
    region, rest = parts[0], parts[1:]
    delay = rest[-1] if rest and re.fullmatch(r"d\d", rest[-1]) else None
    uni = "_".join(rest[:-1] if delay else rest)
    return region, uni + (f" {delay}" if delay and delay != "d1" else "")


def recommend(pr: dict, n: int = 3) -> list[dict]:
    """全區加權分數最高的 dataset；同分比 pyramid；同一個 dataset 只留分數最高的站。"""
    rows = [dict(x, key=k) for k, xs in pr.get("per_key", {}).items() for x in xs]
    rows.sort(key=lambda x: (-(x.get("score") or 0), -(x.get("pyramidMultiplier") or 0), x.get("alphaCount") or 0))
    out, seen = [], set()
    for x in rows:
        if x["id"] in seen:
            continue
        seen.add(x["id"]); out.append(x)
        if len(out) >= n:
            break
    return out


def _rec_name(x: dict) -> str:
    region, uni = _site_label(x["key"])
    return f"{region}_{uni.replace(' ', '_')}_{x['id']}"


def profile_card(d: dict, used_n: int) -> str:
    shape = d.get("data_shape") or {}
    naming = d.get("naming") or {}
    groups = d.get("groups") or []
    key = str(d.get("key", ""))
    kv = "".join(f'<div class="kv"><b>{k}</b>　{v}</div>' for k, v in [
        ("型態", e(shape.get("type_mix", ""))),
        ("命名", (f'<code>{e(naming.get("pattern", ""))}</code>　' if naming.get("pattern") else "") + e(naming.get("exceptions", ""))),
] if v)
    trs = "".join(f'<tr><td><b>{e(g.get("group", ""))}</b></td><td>{e(g.get("semantic", ""))}</td>'
                  f'<td>{e(", ".join((g.get("representatives") or {}).values()))}</td><td class="num">{len(g.get("fields") or [])}</td></tr>' for g in groups)
    ung = len(d.get("ungrouped") or [])
    return (f'<div class="hc wide" data-v="{e(key)}">'
            f'<div class="hc-top"><span class="hc-id mono">{e(d.get("dataset", ""))}</span><span class="pill2">{len(groups)} 群</span><span class="chan">{e(key)}</span></div>'
            f'<div class="hc-desc">{e(d.get("intro", ""))}</div>'
            f'<div class="hc-box">{kv}</div>'
            f'<details open><summary>語意分群（{len(groups)}）{f"　未分類 {ung} 欄" if ung else ""}</summary>'
            f'<table class="gt"><tr><th>群</th><th>白話語意</th><th>代表欄位</th><th>欄數</th></tr>{trs}</table></details>'
            f'<div class="hc-foot"><span>{d.get("field_total", "")} 欄</span><span>{f"你用過 {used_n} 支" if used_n else "還沒用過"}</span>'
            f'<span>分析於 {e(str(d.get("generated", "")))}</span><span class="fn">{e(str(d.get("dataset", "")))}_{e(key)}_profile.json</span></div></div>')


def tab_atlas(st: dict) -> str:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import dataset_snapshot as dsn  # noqa: E402
    b = st.get("b") or {}
    out = []
    pr = None
    if dsn.PRIORITY.exists():
        try:
            pr = json.loads(dsn.PRIORITY.read_text(encoding="utf-8"))
        except Exception:
            pr = None
    if not pr:
        out.append('<p class="intro">還沒有推薦。同步完成後跟研究羅盤說一聲，它會幫你畫出熱力圖、推薦優先研究的 dataset。</p>')
    else:
        age = pr.get("sync_age_days")
        stale = age is not None and age > dsn.SYNC_CYCLE_DAYS
        sync_txt = f"上次同步：{e(pr['snapshot'])}" + (f"（{age:g} 天前）" if age is not None else "") + "　·　建議每個月同步一次" + ("　<b class=warn>⚠ 已超過 30 天，該重新同步了</b>" if stale else "")
        first = "" if pr.get("compared_to") else '<br><span class="muted">目前只有一份快照，alphaCount 變化和新 dataset 要下次同步才算得出來，這次只看 pyramid 加成。</span>'
        out.append('<h3 class="hmtitle">Dataset 推薦熱力圖</h3>'
                   '<p class="intro">推薦規則：根據 alphaCount 變化、pyramid 加成、是不是新 dataset，綜合評分選出推薦的 dataset。'
                   f'格子裡的數字是 dataset 數量，顏色越深代表這格最高的加權分數越高；滑鼠移到格子上，會顯示推薦的 dataset。<br>{sync_txt}{first}</p>')
        keys = pr["keys"]
        cats = sorted({c.split("|")[0] for c in pr["cells"]})
        hi = max((c.get("score") or 0 for c in pr["cells"].values()), default=0)
        head = "".join(f'<th><div>{e(r)}</div><small>{e(u)}</small></th>' for r, u in (_site_label(k) for k in keys))
        rows = []
        for cat in cats:
            tds = []
            for k in keys:
                cell = pr["cells"].get(f"{cat}|{k}")
                if not cell:
                    tds.append("<td></td>"); continue
                region, _ = _site_label(k)
                tip = f"{cat} × {region}：{cell['n']} 個 dataset｜推薦：{cell['top']}"
                tds.append(f'<td class="s{_shade(cell.get("score"), hi)}" title="{e(tip)}">{cell["n"]}</td>')
            rows.append(f"<tr><th class='cat'>{e(cat)}</th>{''.join(tds)}</tr>")
        out.append('<div style="overflow-x:auto"><table class="hm2"><tr><th></th>' + head + "</tr>" + "".join(rows) + "</table></div>")
        recs = recommend(pr)
        if recs:
            out.append('<div class="recs"><b>推薦 dataset：</b>' + " → ".join(f"<code>{e(_rec_name(x))}</code>" for x in recs)
                       + '<div class="muted">想看懂哪一個，跟研究羅盤說「幫我分析 USA TOP3000 model109」（換成你選的站和 dataset）。</div></div>')
    cards = []
    for p in b.get("profiles", []):
        try:
            d = json.loads((paths.ROOT / p["path"]).read_text(encoding="utf-8"))
        except Exception:
            continue
        used_n = next((x.get("used_by_me", 0) for rows in (pr or {}).get("per_key", {}).values() for x in rows if x["id"] == d.get("dataset")), 0)
        cards.append(profile_card(d, used_n))
    if cards:
        keys_c: dict[str, int] = {}
        for p in b.get("profiles", []):
            keys_c[str(p.get("key"))] = keys_c.get(str(p.get("key")), 0) + 1
        out.append('<h3 class="hmtitle">Dataset 分析</h3>' + chips_bar("dsg", [(k, k, n) for k, n in sorted(keys_c.items())], len(cards), False)
                   + f'<div class="cgrid two" id="dsg">{"".join(cards)}</div>')
    return "".join(out)


NEXT_PHASE = ["選 dataset", "設計 template", "調 scorer"]   # A 段地圖尾端的灰色預告（B 主線）


def _node(cls: str, dot: str, name: str, st_text: str, extra_cls: str = "") -> str:
    return (f'<div class="node {cls} {extra_cls}"><div class="dot">{dot}</div><div class="nm">{e(name)}</div>'
            f'<div class="st">{e(st_text)}</div></div>')


def journey_map(st: dict) -> str:
    """B 段地圖：左邊「開始研究」一個節點，分出四條線（樣式同 A 的單線），每條線往右延伸它的小步。"""
    b = st["b"]
    routes = b["routes"]
    mr = next((r for rid in b.get("mainline", []) for r in routes if r["id"] == rid and r["available"] and not r["done"]), None)
    bcur = next((s["id"] for s in mr["steps"] if not s["done"]), None) if mr else None
    root = _node("done", "✓", "開始研究", "機器會用了", "link")
    rows = []
    for r in routes:
        if r["done"]:
            rcls, rtxt = "done", "走完"
        elif any(s["id"] == bcur for s in r["steps"]):
            rcls, rtxt = "cur", "現在"
        elif not r["available"]:
            rcls, rtxt = "next", "實作中"
        else:
            rcls, rtxt = "", "可以走"
        nodes = [_node(rcls, "✓" if rcls == "done" else r["id"], r["name"], rtxt)]
        for s in r["steps"]:
            if s["done"]:
                scls, stxt = "done", "完成"
            elif s["id"] == bcur:
                scls, stxt = "cur", "現在"
            elif not r["available"]:
                scls, stxt = "next", ""
            else:
                scls, stxt = "", ""
            nodes.append(_node(scls, "✓" if scls == "done" else s["id"].split("-")[-1], s["name"], stxt))
        rows.append('<div class="map branch">' + "".join(nodes) + "</div>")
    return ('<div class="journey"><div class="map aline">' + root + '</div><div class="bus"></div>'
            '<div class="branches">' + "".join(rows) + "</div></div>")


def b_details(st: dict) -> str:
    b = st["b"]
    steps_md, routes_md = b_sections()
    cur = b["current"]
    out = []
    for r in b["routes"]:
        tag = "主線" if r["id"] in b.get("mainline", []) else "支線"
        out.append(f'<div class="rhead">{e(r["id"])}　{e(r["name"])} <span class="muted">{tag}{"" if r["available"] else "・實作中"}</span></div>')
        for s in r["steps"]:
            pill = ('<span class="pill done">完成</span>' if s["done"] else ('<span class="pill cur">現在</span>' if s["id"] == cur
                    else ('<span class="pill">實作中</span>' if not r["available"] else '<span class="pill">還沒</span>')))
            content = (md_to_html(steps_md[s["id"]]) if s["id"] in steps_md
                       else (md_to_html(routes_md.get(r["id"], "")) if s is r["steps"][0] else '<p class="muted">實作中。</p>'))
            out.append(f'<details class="step" id="s_{s["id"]}"{" open" if s["id"] == cur else ""}><summary>{e(s["id"])}　{e(s["name"])} {pill}'
                       f'<span class="why">{e(s.get("why", ""))}</span></summary>{content}</details>')
    return "".join(out)


def a_details(st: dict, open_id: str | None) -> str:
    secs = step_sections()
    out = []
    for s in st["steps"]:
        pill = '<span class="pill done">完成</span>' if s["done"] else ('<span class="pill cur">現在</span>' if s["id"] == open_id else '<span class="pill">還沒</span>')
        body = md_to_html(secs.get(s["id"], ""))
        if s["id"] == "A5":
            body += config_block(st)
        out.append(f'<details class="step"{" open" if s["id"] == open_id else ""}><summary>{s["id"][1]}　{e(s["name"])} {pill}<span class="why">{e(s["why"])}</span></summary>{body}</details>')
    return "".join(out)


def tab_operators() -> str:
    p = paths.OUT.INDEX / "operator_index.json"
    if not p.exists():
        return ('<p class="intro">還沒有索引。跟研究羅盤說「幫我整理 operator」：它會先教你抓自己帳號的 operator 清單，'
                '建議分群方式讓你決定，再把每個 operator 分進去、各寫一句用途，這裡就會長出 operator 倉庫。</p>')
    try:
        rep = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return '<p class="muted">operator_index.json 讀不出來。</p>'
    if "groups" not in rep:
        return '<p class="intro">這份索引是舊格式。跟研究羅盤說「幫我整理 operator」重做一次。</p>'
    out = [f'<p class="intro">寫 template 時每一層只回答一個問題，同一個 space 的選項從同一群挑。分群方式是你定的，每個 operator 的一句話是研究羅盤照定義寫的；'
           f'⚠ 的是羅盤建議盡量不要用的，原因寫在旁邊。<span class="muted">　清單 {e(rep["source"])}（你帳號的 {rep["n_operators"]} 個，已分 {rep["n_assigned"]} 個）</span></p>']
    for grp in rep["groups"]:
        rows = "".join(f'<tr class="{"avoid" if r["avoid"] else ""}"><td><code>{e(r["definition"] or r["name"])}</code></td><td>{"⚠ " if r["avoid"] else ""}{e(r["note"])}</td><td class="muted">{e(r["description"])}</td></tr>' for r in grp["operators"])
        out.append(f'<details class="step"><summary>{e(grp["name"])} <span class="muted" style="font-weight:400;font-size:12.5px">{e(grp["question"])}</span><span class="why">{grp["n"]} 個</span></summary>'
                   f'<table><tr><th>operator</th><th>羅盤的一句話</th><th>平台說明</th></tr>{rows or "<tr><td colspan=3 class=muted>（這群還沒有）</td></tr>"}</table></details>')
    if rep.get("unassigned"):
        out.append('<details class="step"><summary>還沒分類 <span class="why">' + str(len(rep["unassigned"])) + ' 個</span></summary><table>'
                   + "".join(f'<tr><td><code>{e(r["definition"] or r["name"])}</code></td><td class="muted">{e(r["category"])}</td></tr>' for r in rep["unassigned"]) + "</table></details>")
    if rep.get("custom_ops"):
        out.append('<h3>你的 custom operator</h3><table><tr><th>寫法</th><th>展開成</th><th></th></tr>' + "".join(
            f'<tr><td><code>${e(c["name"])}({e(c["args"])})</code></td><td><code>{e(c["expands_to"])}</code></td><td>{"" if c["registered"] else "⚠ 還沒登記進 MAPPING"}</td></tr>' for c in rep["custom_ops"]) + "</table>")
    return "".join(out)


CARD_STATUS = {  # 假說卡 status → (白話狀態, 下一步)
    "draft": ("草稿", "回占卜家把四關寫完"), "self_checked": ("自檢完成", "/express <卡號> 寫 expression；想要第二意見 /judge"),
    "under_review": ("審判官審查中", "等審判結果"), "unreviewed": ("還沒審", "/judge <卡號> 或直接 /express"),
    "approved": ("審判官通過", "/express <卡號>"), "conditional": ("有條件通過", "照審判書補完再 /express"),
    "needs_work": ("修改後再審", "照審判書改卡，card.py bump-version 後再 /judge"),
    "expr_ready": ("expression 寫好了", "執行 python -m src.idea --idea <卡號> 送模擬"),
    "simulating": ("模擬中", "結果回來後跑 self_check.py <卡號> 或 /judge"),
    "expr_self_checked": ("結果自檢通過", "/templatize <卡號>"), "expr_approved": ("結果審判通過", "/templatize <卡號>"),
    "template_approved": ("template 好了", "照 /templatize 印的指令跑 GA"), "ga_running": ("GA 跑中", "跑完用 sample_alphalist_parser.py 看能交的"),
    "rejected_by_seer": ("占卜家放棄", "—"), "validated": ("驗證成功", "—"), "abandoned": ("放棄", "—"), "rejected": ("退回（機制被證偽）", "—"),
}


CHANNEL_LABEL = {"alpha": "alpha", "spc": "SPC", "both": "alpha＋SPC"}


def _card_body(path: str) -> tuple[str, list[str]]:
    """從假說卡本文抓「# 命題」第一段和「# 自檢」四關分數；讀不到就空。"""
    try:
        txt = (paths.ROOT / path).read_text(encoding="utf-8")
    except Exception:
        return "", []
    m = re.search(r"^# 命題\s*\n(.*?)(?=^# |\Z)", txt, flags=re.M | re.S)
    prop = re.sub(r"\s+", " ", m.group(1)).strip() if m else ""
    m = re.search(r"^# 自檢\s*\n(.*?)(?=^# |\Z)", txt, flags=re.M | re.S)
    gates = re.findall(r"^\|\s*([1-4])\s*\|\s*(\d+)\s*\|", m.group(1), flags=re.M) if m else []
    # 只點出特別低的那關（≤4 分）；分數高的不用特別說
    return prop, [f"第 {k} 關偏低（{v}）" for k, v in gates if int(v) <= 4]


def chips_bar(gid: str, items: list[tuple[str, str, int]], total: int, search: bool) -> str:
    """上方切換列：全部＋各分類（值, 標籤, 數量）；可加搜尋框。"""
    chips = [f'<span class="chip on" data-v="" onclick="filt(\'{gid}\',this)">全部 <b>{total}</b></span>']
    chips += [f'<span class="chip" data-v="{e(v)}" onclick="filt(\'{gid}\',this)">{e(lab)} <b>{n}</b></span>' for v, lab, n in items]
    box = f'<input class="csearch" placeholder="搜卡號／假說／dataset…" oninput="filt(\'{gid}\',null,this.value)">' if search else ""
    return f'<div class="chips" id="{gid}-bar">{"".join(chips)}{box}</div>'


def _prop_html(prop: str, n: int = 220) -> str:
    s = prop[:n] + ("…" if len(prop) > n else "")
    if s.count("**") % 2:          # 截斷切到粗體中間：整段不加粗
        s = s.replace("**", "")
    return _inline(s)


def tab_hypothesis() -> str:
    cards = onboard.hypothesis_cards()
    if not cards:
        return ('<p class="intro">還沒有靈感卡。裝好占卜家後，在 Claude Code 輸入 <code>/hypothesis 你的直覺或一篇文章</code>，'
                '它會先整理成幾個市場命題讓你挑，再幫你寫成假說卡，卡會出現在這裡。</p>')
    order = list(CARD_STATUS)
    cards = sorted(cards, key=lambda c: (order.index(c.get("status")) if c.get("status") in order else 99, str(c.get("id"))))
    # 上方切換：依通道（alpha／SPC／alpha＋SPC），不是依狀態
    counts: dict[str, int] = {}
    for c in cards:
        ch = str(c.get("channel") or "")
        counts[ch] = counts.get(ch, 0) + 1
    items = [(ch, CHANNEL_LABEL[ch], counts[ch]) for ch in ("alpha", "spc", "both") if counts.get(ch)]
    if counts.get(""):
        items.append(("none", "未定", counts[""]))
    spc = onboard.spc_submissions()
    out = []
    for c in cards:
        cid, st_ = str(c.get("id")), str(c.get("status"))
        lab, nxt = CARD_STATUS.get(st_, (st_, "—"))
        ch = str(c.get("channel") or "")
        conf = c.get("confidence")
        prop, gates = _card_body(str(c.get("_path", "")))
        dead = st_ in ("rejected", "abandoned", "rejected_by_seer")
        site = " ".join(str(c.get(k) or "") for k in ("region", "universe")).strip()
        subs = spc.get(cid, [])
        if subs:  # SPC 提交後只記狀態與權重；全部 Fail 就不再提示下一步
            gates = gates + [f"SPC {s['prompt_name']}：{s['label']}" for s in subs]
            if ch == "spc":
                nxt = "—" if all(s["label"] == "Fail" for s in subs) else "定期回報平台狀態：/spc checked；持續 Failed 就把權重歸零"
        out.append(
            f'<div class="hc" id="hc-{e(cid)}" data-v="{e(ch or "none")}">'
            f'<div class="hc-top"><span class="hc-id">{e(cid)}</span><span class="pill2{" bad" if st_ == "rejected" else ""}">{e(lab)}</span>'
            f'{f"<span class=chan>{e(CHANNEL_LABEL.get(ch, ch))}</span>" if ch else ""}</div>'
            f'<div class="hc-title">{e(str(c.get("hypothesis") or ""))}</div>'
            + (f'<div class="gates">{"".join(f"<span>{e(x)}</span>" for x in gates)}</div>' if gates else "")
            + (f'<div class="hc-box"><b>命題</b>　{_prop_html(prop)}</div>' if prop else "")
            + ("" if dead else f'<div class="hc-next">下一步：{e(nxt.replace("<卡號>", cid))}</div>')
            + f'<div class="hc-foot"><span class="ds">{e(str(c.get("dataset") or "—"))}{f"（{e(site)}）" if site else ""}</span>'
            f'<span>{f"信心 {conf}/10" if conf not in (None, "") else ""}</span><span>{e(str(c.get("created") or ""))}</span>'
            f'<span class="fn">{e(Path(str(c.get("_path", ""))).name)}</span></div></div>')
    return (f'<p class="intro">占卜家寫的假說卡，存在 <code>DB/ResearchDB/hypothesis/</code>。沒裝審判官時，信心是占卜家四關自檢的總分（只點出偏低的那關）；有裝審判官就看判決。進行中的卡也會出現在「專案管理」的泳道上；SPC 提交後只記狀態與權重。</p>'
            + chips_bar("hcg", items, len(cards), True) + f'<div class="cgrid" id="hcg">{"".join(out)}</div>')


def render_b(st: dict) -> str:
    b = st["b"]
    cur = b["current"]
    # 主線目前位置：R1 → R3 → R4 第一個沒走完的路
    main_route = next((r for rid in b.get("mainline", []) for r in b["routes"] if r["id"] == rid and r["available"] and not r["done"]), None)
    if main_route:
        ms = next((s for s in main_route["steps"] if not s["done"]), None)
        here = (f'<div class="here"><div class="sub">你在這裡</div><div class="big">開始研究　主線 {e(main_route["id"])} {e(main_route["name"])}　第 {e(ms["id"][-1]) if ms else "?"} 步／共 {len(main_route["steps"])} 步：{e(ms["name"]) if ms else ""}</div>'
                f'<div class="sub">四條路可以隨時切換；回到 Claude Code 輸入 <code>/research-compass</code>，我會帶你做主線這一步。</div></div>')
    else:
        here = ('<div class="here"><div class="sub">你在這裡</div><div class="big">主線都走完了</div>'
                '<div class="sub">回到 Claude Code 輸入 <code>/research-compass</code>；四條路隨時可以再走。</div></div>')
    cur = cur or (ms["id"] if main_route and ms else None)
    cols = ('<p class="hubnote">四條路可以自由切換；主線是 R1 選 dataset → R3 設計 template → R4 調 scorer（R2 認識 operator 是支線），回答完任何一題都會帶你回主線還沒做完的那一步。要回頭查 A 段的指令，跟研究羅盤說就好。</p>'
            + b_details(st))
    todos = [t for t in st.get("todos", []) if not t.get("done")]
    todo_html = ""
    if todos:
        todo_html = ('<div class="lane todo-lane"><h3>待辦 <span class="muted">' + str(len(todos)) + '</span></h3><div class="desc">想做但還沒做的事（羅盤幫你記的）</div>'
                     + "".join(f'<div class="todo">{e(t["text"])}<div class="muted">{e(t["added_at"][:10])} 記錄</div></div>' for t in todos) + '</div>')
    tabs = [("g1", "新手地圖", "你在這裡"), ("g2", "專案管理", "你的研究"), ("g5", "靈感卡", "占卜家的假說"), ("g3", "dataset 圖鑑", "先看哪個"), ("g4", "operator 倉庫", "依功能分類")]
    pages = {
        "g5": tab_hypothesis(),
        "g1": here + journey_map(st) + cols,
        "g4": tab_operators(),
        "g2": ('<p class="intro">每一條研究是一張卡，從左往右走：方向待定 → 研究中 → 模擬中 → 結案。GA 跑的研究會自動出現在「模擬中」；'
               '看完結果後，研究羅盤會把能交的 alpha ID 記在卡上、移到「結案」；其他的卡跟研究羅盤說一聲，它會幫你放上去、移過去。</p>' + lanes_block(st) + todo_html),
        "g3": tab_atlas(st),
    }
    if b.get("all_done"):   # R 階段全部走完：「新手地圖」分頁不再顯示，地圖頁從專案管理開始
        tabs = [x for x in tabs if x[0] != "g1"]
    nav = '<div class="tabs">' + "".join(f'<div class="tab{" on" if i == 0 else ""}" data-p="{p}">{e(t)}<small>{e(s)}</small></div>' for i, (p, t, s) in enumerate(tabs)) + "</div>"
    meta = f'<div class="meta">研究羅盤 · 更新於 {e(st["checked_at"].replace("T", " ")[:16])} · 進度由你機器上的檔案自動判斷 · 重新整理：在 Claude Code 輸入 <code>/research-compass</code></div>'
    pages_html = "".join(f'<div class="page{" on" if i == 0 else ""}" id="{p}">{meta}{pages[p]}</div>' for i, (p, _, _) in enumerate(tabs))
    return (f'<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>研究羅盤：新手地圖</title><style>{CSS}{B_CSS}</style></head><body>{nav}{pages_html}<script>{JS}{B_JS}</script></body></html>')


def build(preview: str | None = None) -> tuple[Path, dict]:
    st = onboard.check()
    if preview and preview != "B":   # 預覽用：假裝停在 A 的某一步
        idx = [s["id"] for s in st["steps"]].index(preview)
        for j, s in enumerate(st["steps"]):
            s["done"] = j < idx
        st["current"], st["phase"], st["n_done"], st["b"] = preview, "A", idx, None
    elif preview == "B":             # 預覽 B：用目前的 B 狀態
        st["current"], st["phase"] = None, "B"
        st["b"] = st["b"] or onboard.b_status(onboard.load_progress(), st["research_detail"])
    paths.ensure_parent(OUT_HTML)
    OUT_HTML.write_text(render_b(st) if st["phase"] == "B" else render(st), encoding="utf-8")
    return OUT_HTML, st


def main() -> int:
    ap = argparse.ArgumentParser(description="新手地圖頁")
    ap.add_argument("--open", action="store_true")
    ap.add_argument("--preview", choices=[s for s, _ in onboard.STEPS] + ["B"], help="預覽：假裝停在某一步（不改任何進度）；B＝用目前狀態畫 B 版")
    args = ap.parse_args()
    p, st = build(args.preview)
    where = ("A 第 " + st["current"][1] + " 步") if st["current"] else ("B " + (st["b"]["current"] if st.get("b") and st["b"]["current"] else "R1 走完"))
    print(f"[地圖] {paths.rel(p)}（{where}；待辦 {len([t for t in st['todos'] if not t.get('done')])} 項）")
    print(f"瀏覽器打開：file://{p}")
    if args.open:
        webbrowser.open(f"file://{p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
