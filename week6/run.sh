#!/usr/bin/env bash
# Entry point. The grader runs `./run.sh task.md` from this directory, with no terminal and
# nobody to answer questions, for at most 10 minutes. When it exits, app/services/{api,router,
# worker} and the files under out/ are scored.
#
# What it does:
#   1. kit/prepare.sh   no model: snapshot the release, set unused code aside, install the
#                       instruction files, load the evidence into work/evidence.db
#   2. one Claude Code session on the medium model, with four tools and a stop hook that
#      runs kit/check.sh
#   3. if the gate still fails and time remains, one resume of that session with its output
#   4. kit/prepare.sh --restore   put app/ back in its shipped layout
#
# Settings can be overridden for experiments: KIT_MODEL, KIT_EFFORT, KIT_MAX_TURNS, KIT_TOOLS,
# KIT_NO_HOOK=1 (stop hook off), KIT_NO_RESUME=1, KIT_VARIANT=flags (no kit at all).
set -u

TASK_FILE="${1:?usage: ./run.sh <task-file>}"
cd "$(dirname "$0")" || exit 1
STARTED=$(date +%s)
MAIN_LIMIT=460    # seconds for the main session
HARD_STOP=565     # nothing new starts after this many seconds

# Cache writes at the 5-minute rate: the run is one short session, so a longer-lived cache
# buys nothing and costs 60% more per token written.
export FORCE_PROMPT_CACHING_5M=1
export DISABLE_AUTOUPDATER=1

limited() { # limited <seconds> <command...>: stop the command when the time is up
  local seconds=$1
  shift
  if command -v timeout >/dev/null 2>&1; then
    timeout "$seconds" "$@"
    return $?
  fi
  "$@" &
  local pid=$!
  (sleep "$seconds" && kill -TERM "$pid" 2>/dev/null) &
  local watchdog=$!
  wait "$pid"
  local status=$?
  kill "$watchdog" 2>/dev/null
  return $status
}

if [ "${KIT_VARIANT:-}" = "flags" ]; then
  # Experiment: the baseline prompt with only the harness flags changed. No kit, no notes.
  if [ -d tools/starter ]; then
    echo "run.sh: development checkout; use python3 tools/practice.py" >&2
    exit 3
  fi
  mv CLAUDE.md CLAUDE.md.off 2>/dev/null
  mv AGENTS.md AGENTS.md.off 2>/dev/null
  limited "$MAIN_LIMIT" claude -p "$(cat "$TASK_FILE")" --model "${KIT_MODEL:-claude-sonnet-5-5}" \
    --effort "${KIT_EFFORT:-medium}" --tools "${KIT_TOOLS:-Bash,Read,Edit,Write}" --strict-mcp-config \
    --setting-sources project --permission-mode bypassPermissions --output-format stream-json --verbose
  exit 0
fi

kit/prepare.sh
prepared=$?
if [ "$prepared" -eq 3 ]; then
  exit 3 # the development checkout: prepare.sh has said why
fi

PROMPT="$(
  cat kit/prompt.md
  cat work/start.txt 2>/dev/null
  echo
  cat work/evidence.txt 2>/dev/null
  printf '\n<ticket file="%s">\n' "$TASK_FILE"
  cat "$TASK_FILE"
  printf '\n</ticket>\n'
)"

SESSION=$(python3 -c 'import uuid; print(uuid.uuid4())')
FLAGS=(
  --model "${KIT_MODEL:-claude-sonnet-5-5}"
  --effort "${KIT_EFFORT:-medium}"
  --tools "${KIT_TOOLS:-Bash,Read,Edit,Write}"
  --strict-mcp-config
  --setting-sources project
  --permission-mode bypassPermissions
  --output-format stream-json --verbose
)

limited "$MAIN_LIMIT" claude -p "$PROMPT" --session-id "$SESSION" \
  --max-turns "${KIT_MAX_TURNS:-90}" "${FLAGS[@]}"
echo "run.sh: main session ended with status $? after $(($(date +%s) - STARTED)) s"

# One more go if the gate is still red and there is time to act on it.
if ! report=$(kit/check.sh 2>&1); then
  elapsed=$(($(date +%s) - STARTED))
  echo "run.sh: gate after the session:"
  echo "$report" | head -45
  if [ "$elapsed" -lt 400 ] && [ "${KIT_NO_RESUME:-}" != "1" ]; then
    limited $((HARD_STOP - 15 - elapsed)) claude -p "kit/check.sh still reports the following. Fix it, keeping the code in a state that builds, then stop.

$(echo "$report" | head -45)" --resume "$SESSION" --max-turns 30 "${FLAGS[@]}"
    echo "run.sh: resumed session ended with status $? after $(($(date +%s) - STARTED)) s"
  fi
else
  echo "run.sh: gate is clear"
fi

kit/prepare.sh --restore
exit 0
