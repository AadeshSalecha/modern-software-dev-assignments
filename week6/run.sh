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
#   4. kit/prepare.sh --restore   put app/ back in its shipped layout (also on a signal)
#
# Settings can be overridden for experiments: KIT_MODEL, KIT_EFFORT, KIT_MAX_TURNS, KIT_TOOLS,
# KIT_NO_HOOK=1 (stop hook off), KIT_NO_RESUME=1, KIT_VARIANT=flags (no kit at all).
set -u

TASK_FILE="${1:?usage: ./run.sh <task-file>}"
cd "$(dirname "$0")" || exit 1
ROOT=$PWD
STARTED=$(date +%s)
MAIN_END=${KIT_MAIN_END:-470}   # the main session is stopped this many seconds after the start
HARD_STOP=${KIT_HARD_STOP:-570}  # everything here is finished by then, 30 s before the grader's limit

elapsed() { echo $(($(date +%s) - STARTED)); }

# --- environment: work with whatever the caller passes, including nothing -------------
if [ -z "${HOME:-}" ]; then
  HOME=~ # with HOME unset, bash expands ~ from the account's entry
  if [ -z "$HOME" ] || [ ! -w "$HOME" ]; then
    mkdir -p "$ROOT/work/home" && HOME="$ROOT/work/home"
  fi
  export HOME
fi
PATH="${PATH:-/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin}"
for extra in /usr/local/go/bin "$HOME/go/bin" "$HOME/.local/bin"; do
  case ":$PATH:" in
    *":$extra:"*) ;;
    *) [ -d "$extra" ] && PATH="$PATH:$extra" ;;
  esac
done
export PATH
# Cache writes at the 5-minute rate: the run is one short session, so a longer-lived cache
# buys nothing and costs 60% more per token written.
export FORCE_PROMPT_CACHING_5M=1
export DISABLE_AUTOUPDATER=1

# --- running things with a deadline, and tidying up whatever happens ------------------
CHILD=""
limited() { # limited <seconds> <command...>: stop the command when the time is up
  local seconds=$1
  shift
  [ "$seconds" -ge 1 ] || return 124
  "$@" &
  CHILD=$!
  (
    sleep "$seconds"
    kill -TERM "$CHILD" 2>/dev/null
    sleep 5
    kill -KILL "$CHILD" 2>/dev/null
  ) >/dev/null 2>&1 &
  local watchdog=$!
  wait "$CHILD"
  local status=$?
  pkill -P "$watchdog" 2>/dev/null
  kill "$watchdog" 2>/dev/null
  wait "$watchdog" 2>/dev/null
  CHILD=""
  return $status
}

stop_services() { # replay services started from this workspace detach themselves; stop any left
  pkill -f "$ROOT/app/services/" 2>/dev/null
  pkill -f "$ROOT/app/.build/" 2>/dev/null
  pkill -f "$ROOT/.pristine/app/" 2>/dev/null
  return 0
}

PREPARED=0
finish() {
  trap - EXIT TERM INT
  [ -n "$CHILD" ] && kill -TERM "$CHILD" 2>/dev/null
  if [ "$PREPARED" -eq 1 ]; then
    stop_services
    kit/prepare.sh --restore
  fi
}
trap finish EXIT
trap 'exit 143' TERM INT

MODEL="${KIT_MODEL:-claude-sonnet-5-5}"
FLAGS=(
  --model "$MODEL"
  --effort "${KIT_EFFORT:-medium}"
  --tools "${KIT_TOOLS:-Bash,Read,Edit,Write}"
  --strict-mcp-config
  --setting-sources project
  --permission-mode bypassPermissions
  --output-format stream-json --verbose
)

if [ "${KIT_VARIANT:-}" = "flags" ]; then
  # Experiment: the baseline prompt with only the harness flags changed. No kit, no notes.
  if [ -d tools/starter ]; then
    echo "run.sh: development checkout; use python3 tools/practice.py" >&2
    exit 3
  fi
  mv CLAUDE.md CLAUDE.md.off 2>/dev/null
  mv AGENTS.md AGENTS.md.off 2>/dev/null
  limited "$MAIN_END" claude -p "$(cat "$TASK_FILE")" "${FLAGS[@]}"
  exit 0
fi

kit/prepare.sh
prepared=$?
if [ "$prepared" -eq 3 ]; then
  exit 3 # the development checkout: prepare.sh has said why
fi
PREPARED=1

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
limited $((MAIN_END - $(elapsed))) claude -p "$PROMPT" --session-id "$SESSION" \
  --max-turns "${KIT_MAX_TURNS:-90}" "${FLAGS[@]}"
echo "run.sh: main session ended with status $? after $(elapsed) s"
stop_services

# One more go if the gate is still red and there is time to act on it.
if limited $((HARD_STOP - 60 - $(elapsed))) kit/check.sh >work/.gate.txt 2>&1; then
  echo "run.sh: gate is clear"
else
  echo "run.sh: gate after the session:"
  head -45 work/.gate.txt
  stop_services
  if [ "$(elapsed)" -lt 400 ] && [ "${KIT_NO_RESUME:-}" != "1" ]; then
    limited $((HARD_STOP - 10 - $(elapsed))) claude -p "kit/check.sh still reports the following. Fix it, keeping the code in a state that builds, then stop.

$(head -45 work/.gate.txt)" --resume "$SESSION" --max-turns 30 "${FLAGS[@]}"
    echo "run.sh: resumed session ended with status $? after $(elapsed) s"
  fi
fi
exit 0
