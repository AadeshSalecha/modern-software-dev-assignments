#!/usr/bin/env bash
# Build the Gradescope zip from week6/, leaving out everything that is not the setup:
# past practice logs (runs/ holds earlier reports and diffs of app/), scratch output, the
# starter's scoring files, caches, and writeup.md (it describes the starter incident's cause;
# it is handed in through the repository link, not the zip).
#
#   .reppit/week6-agent-cost-optimization/make_submission.sh [output.zip]
set -euo pipefail
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
OUT="${1:-$REPO/week6-submission.zip}"
cd "$REPO/week6"
if [ -e app/_deprecated ] || [ -e work ] || [ -e .pristine ]; then
  echo "week6/ holds leftovers of a run (app/_deprecated, work/ or .pristine/); clean it first" >&2
  exit 1
fi
rm -f "$OUT"
zip -r -q "$OUT" . \
  -x 'runs/*' 'out/*' 'tools/starter/*' 'app/.build/*' 'writeup.md' \
  -x '*__pycache__*' '*.pyc' '*.pytest_cache*' '*.DS_Store' '*node_modules*'
listing=$(unzip -Z1 "$OUT")
if echo "$listing" | grep -E '^(runs|out|work|\.pristine|tools/starter)/|^writeup\.md$' >&2; then
  echo "paths above must not be in the zip" >&2
  exit 1
fi
for needed in run.sh AGENTS.md CLAUDE.md .claude/settings.json kit/prepare.sh kit/check.py kit/prompt.md task.md; do
  echo "$listing" | grep -qx "$needed" || { echo "missing from the zip: $needed" >&2; exit 1; }
done
echo "$OUT: $(echo "$listing" | wc -l | tr -d ' ') entries, $(du -h "$OUT" | cut -f1)"
