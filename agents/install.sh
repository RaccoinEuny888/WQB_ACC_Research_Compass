#!/usr/bin/env bash
# 安裝三支 agent 到這台 open machine 的 Claude Code 設定。
#   bash agents/install.sh                 # 全部（先列清單，再問一次 y/N）
#   bash agents/install.sh --only seer|inquisitor|compass
#   bash agents/install.sh --yes --force   # 不問、覆蓋既有檔
# 只新增，不修改 open machine 既有程式。會做的事：
#   1. .claude/skills/<name>/SKILL.md      ← agents/*/skills/*/SKILL.md
#   2. .claude/agents/<name>.md            ← agents/*/AGENT.md
#   3. CLAUDE.md 加一行 @agents/hypothesis_seer/SEER.md（占卜家＝主對話）
#   4. src/idea.py                         ← agents/tools/idea.py（使用者執行 idea → payload → pending）
#   5. 建 DB/ResearchDB/hypothesis/ 與 DB/ResearchDB/idea/
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"
ONLY="all"; YES=0; FORCE=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --only) ONLY="$2"; shift 2;;
    --yes) YES=1; shift;;
    --force) FORCE=1; shift;;
    *) echo "未知參數 $1"; exit 1;;
  esac
done
want() { [[ "$ONLY" == "all" || "$ONLY" == "$1" ]]; }

PLAN=()
want seer       && PLAN+=(".claude/skills/{hypothesis,papers,express,templatize,spc}/SKILL.md" "CLAUDE.md ← 加一行 @agents/hypothesis_seer/SEER.md" "src/idea.py ← agents/tools/idea.py" "DB/ResearchDB/hypothesis/  DB/ResearchDB/idea/")
want inquisitor && PLAN+=(".claude/agents/expression-inquisitor.md" ".claude/skills/judge/SKILL.md" "DB/ResearchDB/hypothesis/  DB/ResearchDB/idea/")
want compass    && PLAN+=(".claude/skills/{research-compass,dataset-profile,operator-classify}/SKILL.md" "agents/workspace/{cache,index,dashboard}/")
echo "將在 $ROOT 新增／更新："
printf '  - %s\n' "${PLAN[@]}" | awk '!seen[$0]++'
echo "不會修改 src/ 既有檔案；不會讀 .env、session.pkl、login_time.pkl。"
if [[ $YES -ne 1 ]]; then read -r -p "繼續？[y/N] " a; [[ "$a" == "y" || "$a" == "Y" ]] || { echo "取消"; exit 0; }; fi

copy() { # src dst
  if [[ -e "$2" && $FORCE -ne 1 ]]; then
    if cmp -s "$1" "$2"; then echo "  = $2（相同）"; else echo "  ! $2 已存在且不同，略過（--force 覆蓋）"; fi
  else mkdir -p "$(dirname "$2")"; cp "$1" "$2"; echo "  + $2"; fi
}
install_skills() { for s in "$@"; do copy "agents/$1_dir_placeholder" "/dev/null" 2>/dev/null || true; done; }

if want seer; then
  for s in hypothesis papers express templatize spc; do copy "agents/hypothesis_seer/skills/$s/SKILL.md" ".claude/skills/$s/SKILL.md"; done
  LINE="@agents/hypothesis_seer/SEER.md"
  if [[ -f CLAUDE.md ]] && grep -qF "$LINE" CLAUDE.md; then echo "  = CLAUDE.md 已含 $LINE";
  else { [[ -f CLAUDE.md ]] && printf '\n' >> CLAUDE.md; printf '# Hypothesis Seer（主對話設定，見 agents/README.md）\n%s\n' "$LINE" >> CLAUDE.md; echo "  + CLAUDE.md ← $LINE"; }; fi
  copy agents/tools/idea.py src/idea.py
  mkdir -p DB/ResearchDB/hypothesis DB/ResearchDB/idea && echo "  + DB/ResearchDB/hypothesis/ DB/ResearchDB/idea/"
fi
if want inquisitor; then
  copy agents/expression_inquisitor/AGENT.md .claude/agents/expression-inquisitor.md
  copy agents/expression_inquisitor/skills/judge/SKILL.md .claude/skills/judge/SKILL.md
  mkdir -p DB/ResearchDB/hypothesis DB/ResearchDB/idea
fi
if want compass; then
  for s in research-compass dataset-profile operator-classify; do copy "agents/research_compass/skills/$s/SKILL.md" ".claude/skills/$s/SKILL.md"; done
  mkdir -p agents/workspace/cache agents/workspace/index agents/workspace/dashboard
fi
echo "完成。重新開啟 Claude Code 後可用：/hypothesis /papers /express /templatize /judge /research-compass /dataset-profile /operator-classify（依安裝項目）。"
echo "檢查：python agents/common/syntax_check.py -e \"rank(close)\""
