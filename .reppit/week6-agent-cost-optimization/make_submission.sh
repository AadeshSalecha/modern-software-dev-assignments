#!/usr/bin/env bash
# Build the Gradescope zip from week6/.
#
#   .reppit/week6-agent-cost-optimization/make_submission.sh [output.zip]          slim (default)
#   .reppit/week6-agent-cost-optimization/make_submission.sh --full [output.zip]   with app/ and incident/
#
# Slim: the setup only (about 35 files). app/ and incident/ carry one note each, because the
# grader replaces both, and task.md, with its own copies before every run (assignment.md, "How
# a Graded Run Works"). Gradescope's upload unpacks a zip in the browser and sends every file;
# with the full folder (260 files) each file came back "Server responded with 500 code".
#
# Both forms leave out past practice logs (runs/ holds earlier reports and diffs of app/),
# scratch output, the starter's scoring files, caches, and writeup.md (it describes the starter
# incident's cause; it is handed in through the repository link, not the zip).
set -euo pipefail
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
MODE=slim
if [ "${1:-}" = "--full" ]; then
  MODE=full
  shift
fi
OUT="${1:-$REPO/week6-submission.zip}"
case "$OUT" in /*) ;; *) OUT="$PWD/$OUT" ;; esac
cd "$REPO/week6"
if [ -e app/_deprecated ] || [ -e work ] || [ -e .pristine ]; then
  echo "week6/ holds leftovers of a run (app/_deprecated, work/ or .pristine/); clean it first" >&2
  exit 1
fi

STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT
mkdir -p "$STAGE/week6"
# Everything that is the setup, by name: nothing gets in by accident.
for item in run.sh AGENTS.md CLAUDE.md .gitignore .claude kit rate_card.json task.md assignment.md tools; do
  [ -e "$item" ] && cp -R "$item" "$STAGE/week6/$item"
done
rm -rf "$STAGE/week6/tools/starter"
find "$STAGE/week6" \( -name __pycache__ -o -name .pytest_cache -o -name .DS_Store -o -name '*.pyc' \) -prune -exec rm -rf {} +
if [ "$MODE" = "full" ]; then
  cp -R app incident "$STAGE/week6/"
  rm -rf "$STAGE/week6/app/.build"
  find "$STAGE/week6/app" \( -name __pycache__ -o -name .pytest_cache -o -name node_modules \) -prune -exec rm -rf {} +
else
  mkdir -p "$STAGE/week6/app" "$STAGE/week6/incident"
  note="Left out of the upload on purpose. The grader puts its own copy of this folder here before each run (assignment.md, How a Graded Run Works), and Gradescope's upload fails on the full folder's file count."
  echo "$note" >"$STAGE/week6/app/README.md"
  echo "$note" >"$STAGE/week6/incident/README.md"
fi

rm -f "$OUT"
(cd "$STAGE/week6" && zip -r -q "$OUT" .)
listing=$(unzip -Z1 "$OUT")
if echo "$listing" | grep -E '^(runs|out|work|\.pristine|tools/starter)/|^writeup\.md$' >&2; then
  echo "paths above must not be in the zip" >&2
  exit 1
fi
for needed in run.sh AGENTS.md CLAUDE.md .claude/settings.json kit/prepare.sh kit/check.py kit/prompt.md task.md; do
  echo "$listing" | grep -qx "$needed" || { echo "missing from the zip: $needed" >&2; exit 1; }
done
files=$(echo "$listing" | grep -vc '/$')
echo "$OUT ($MODE): $files files, $(du -h "$OUT" | cut -f1)"
