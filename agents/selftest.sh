#!/usr/bin/env bash
# 安裝後自我檢查（唯讀，不送模擬、不碰平台）：bash agents/selftest.sh
cd "$(dirname "$0")/.."
PY="${PYTHON:-python3}"; [ -x .venv/bin/python ] && PY=.venv/bin/python
ok=0; bad=0
t() { local name="$1"; shift; if "$@" >/tmp/agents_selftest.log 2>&1; then echo "  [OK]   $name"; ok=$((ok+1)); else echo "  [FAIL] $name"; sed 's/^/         /' /tmp/agents_selftest.log | tail -5; bad=$((bad+1)); fi; }
echo "open machine 根目錄：$(pwd)"
echo "Python：$($PY --version 2>&1)"
t "open machine src 可 import（Alpha）"      $PY -c "import sys;sys.path.insert(0,'.');from src.alpha import Alpha"
t "已同步至少一個 region"                     bash -c "ls DB/ResearchDB/data/latest/*/data_fields.json >/dev/null 2>&1"
t "語法檢查（內建 operators）"                $PY agents/common/syntax_check.py -e "group_zscore(ts_delta(close, 20), industry)"
t "語法檢查含欄位（default_setting）"         $PY agents/common/syntax_check.py -e "rank(close)" -s default_setting.json
t "卡號產生"                                   $PY agents/common/card.py new-id
t "帳本摘要"                                   $PY agents/common/ledger.py summary
t "session 狀態（只看檔案時間）"              $PY agents/common/brain_meta.py session-status
if [ -d agents/hypothesis_seer ]; then
  t "欄位挑選"                                 $PY agents/hypothesis_seer/cli/pick_fields.py --setting default_setting.json --check close
  t "src/idea.py 已安裝"                       $PY -m src.idea --help
  t "CLAUDE.md 含占卜家引入"                   grep -q "@agents/hypothesis_seer/SEER.md" CLAUDE.md
  t "skills 已安裝（hypothesis）"              test -f .claude/skills/hypothesis/SKILL.md
fi
if [ -d agents/expression_inquisitor ]; then
  t "審判官 agent 已安裝"                      test -f .claude/agents/expression-inquisitor.md
fi
if [ -d agents/research_compass ]; then
  t "羅盤進度檢查"                             $PY agents/research_compass/cli/onboard.py status --json
  t "地圖頁產生"                               $PY agents/research_compass/cli/guide_page.py
  t "羅盤 skill 已安裝"                        test -f .claude/skills/research-compass/SKILL.md
fi
echo "結果：$ok OK / $bad FAIL"
[ $bad -eq 0 ]
