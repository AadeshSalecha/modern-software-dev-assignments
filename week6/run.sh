#!/usr/bin/env bash
# Entry point. The grader runs `./run.sh task.md` from this directory, with no terminal and
# nobody to answer questions, for at most 10 minutes. When it exits, app/services/{api,router,
# worker} and the files under out/ are scored.
#
# What it does:
#   1. kit/prepare.sh   no model: snapshot the release, set unused code aside, install the
#                       instruction files, load the evidence into work/evidence.db
#   2. the main agent   one headless session that repairs and reports (see MAIN below)
#   3. the gate         kit/check.sh; if it fails and time remains, one more session with
#                       its output
#   4. kit/prepare.sh --restore   put app/ back in its shipped layout (also on a signal)
#
# Who does what is three settings, each "<harness>:<model>:<effort>" with harness claude or
# codex. The defaults are what is submitted; the grader passes no environment, so it gets them.
#   KIT_MAIN     the main agent
#   KIT_REPORT   if set, this agent writes the report in parallel and the main agent only repairs
#   KIT_RESCUE   if set, a failing gate goes to this agent in a new session; otherwise the main
#                agent gets it (resumed, for claude)
# Other switches for experiments: KIT_TOOLS, KIT_MAX_TURNS, KIT_NO_HOOK=1, KIT_NO_RESUME=1,
# KIT_VARIANT=flags (the bare ticket with only the harness flags changed), KIT_MAIN_END,
# KIT_HARD_STOP.
set -u

TASK_FILE="${1:?usage: ./run.sh <task-file>}"
cd "$(dirname "$0")" || exit 1
ROOT=$PWD
STARTED=$(date +%s)
MAIN_END=${KIT_MAIN_END:-470}   # agents started first are stopped this many seconds after the start
HARD_STOP=${KIT_HARD_STOP:-570} # everything here is finished by then, 30 s before the grader's limit

MAIN="${KIT_MAIN:-claude:claude-sonnet-5-5:medium}"
REPORT="${KIT_REPORT:-}"
RESCUE="${KIT_RESCUE:-}"

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
BACKGROUND=""
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

kill_tree() { # kill_tree <pid>: the process and everything under it
  local pid=$1 child
  for child in $(pgrep -P "$pid" 2>/dev/null); do
    kill_tree "$child"
  done
  kill -TERM "$pid" 2>/dev/null
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
  [ -n "$CHILD" ] && kill_tree "$CHILD"
  [ -n "$BACKGROUND" ] && kill_tree "$BACKGROUND"
  if [ "$PREPARED" -eq 1 ]; then
    stop_services
    kit/prepare.sh --restore
  fi
}
trap finish EXIT
trap 'exit 143' TERM INT

# --- one headless session ----------------------------------------------------------------
agent() { # agent <harness:model:effort> <start|resume> <seconds> <stage> <prompt>
  local spec=$1 mode=$2 seconds=$3 stage=$4 prompt=$5
  local harness model effort
  IFS=: read -r harness model effort <<<"$spec"
  effort="${effort:-medium}"
  case "$harness" in
    claude)
      local flags=(
        --model "$model" --effort "$effort"
        --tools "${KIT_TOOLS:-Bash,Read,Edit,Write}"
        --strict-mcp-config --setting-sources project
        --permission-mode bypassPermissions
        --output-format stream-json --verbose
      )
      local began status
      began=$(date +%s)
      if [ "$mode" = "resume" ] && [ -s "work/.session.$stage" ]; then
        KIT_STAGE="$stage" limited "$seconds" claude -p "$prompt" --resume "$(cat "work/.session.$stage")" \
          --max-turns 30 "${flags[@]}"
      else
        python3 -c 'import uuid; print(uuid.uuid4())' >"work/.session.$stage"
        KIT_STAGE="$stage" limited "$seconds" claude -p "$prompt" --session-id "$(cat "work/.session.$stage")" \
          --max-turns "${KIT_MAX_TURNS:-90}" "${flags[@]}"
      fi
      status=$?
      if [ "$status" -ne 0 ] && [ $(($(date +%s) - began)) -lt 20 ]; then
        # It stopped at once: most likely a flag this version of the harness does not know.
        # Run the invocation the assignment guarantees.
        echo "run.sh: claude exited $status within 20 s; running it again with the basic flags"
        rm -f "work/.session.$stage"
        KIT_STAGE="$stage" limited $((seconds - 20)) claude -p "$prompt" --model "$model" \
          --permission-mode bypassPermissions --output-format stream-json --verbose
        status=$?
      fi
      return $status
      ;;
    codex)
      # Codex reads the root AGENTS.md by itself. It has no stop hook here; the gate below
      # and the second session stand in for it.
      local began status
      began=$(date +%s)
      KIT_STAGE="$stage" limited "$seconds" codex exec -m "$model" -c "model_reasoning_effort=\"$effort\"" \
        --dangerously-bypass-approvals-and-sandbox --skip-git-repo-check --json "$prompt"
      status=$?
      if [ "$status" -ne 0 ] && [ $(($(date +%s) - began)) -lt 20 ]; then
        echo "run.sh: codex exited $status within 20 s; running it again with the basic flags"
        KIT_STAGE="$stage" limited $((seconds - 20)) codex exec -m "$model" \
          --dangerously-bypass-approvals-and-sandbox --skip-git-repo-check "$prompt"
        status=$?
      fi
      return $status
      ;;
    *)
      echo "run.sh: unknown harness in '$spec'" >&2
      return 2
      ;;
  esac
}

harness_of() { echo "${1%%:*}"; }

compose() { # compose <prompt file>: the fixed prompt, the notes from prep, then the ticket
  cat "$1"
  cat work/start.txt 2>/dev/null
  echo
  cat work/evidence.txt 2>/dev/null
  printf '\n<ticket file="%s">\n' "$TASK_FILE"
  cat "$TASK_FILE"
  printf '\n</ticket>\n'
}

if [ "${KIT_VARIANT:-}" = "flags" ]; then
  # Experiment: the baseline prompt with only the harness flags changed. No kit, no notes.
  if [ -d tools/starter ]; then
    echo "run.sh: development checkout; use python3 tools/practice.py" >&2
    exit 3
  fi
  mv CLAUDE.md CLAUDE.md.off 2>/dev/null
  mv AGENTS.md AGENTS.md.off 2>/dev/null
  mkdir -p work
  KIT_NO_HOOK=1 agent "$MAIN" start "$MAIN_END" all "$(cat "$TASK_FILE")"
  exit 0
fi

kit/prepare.sh
prepared=$?
if [ "$prepared" -eq 3 ]; then
  exit 3 # the development checkout: prepare.sh has said why
fi
PREPARED=1

if [ -n "$REPORT" ]; then
  # Two agents: the report in the background, the repair in front. Each has its own prompt
  # and is checked on its own part.
  (agent "$REPORT" start $((MAIN_END - $(elapsed))) report "$(compose kit/prompt-report.md)" >work/.report.log 2>&1) &
  BACKGROUND=$!
  agent "$MAIN" start $((MAIN_END - $(elapsed))) repair "$(compose kit/prompt-repair.md)"
  echo "run.sh: repair session ($MAIN) ended with status $? after $(elapsed) s"
  wait "$BACKGROUND"
  echo "run.sh: report session ($REPORT) ended with status $? after $(elapsed) s; its output follows"
  BACKGROUND=""
  cat work/.report.log
  main_stage=repair
else
  agent "$MAIN" start $((MAIN_END - $(elapsed))) all "$(compose kit/prompt.md)"
  echo "run.sh: main session ($MAIN) ended with status $? after $(elapsed) s"
  main_stage=all
fi
stop_services

# One more go if the gate is still red and there is time to act on it.
if limited $((HARD_STOP - 60 - $(elapsed))) kit/check.sh >work/.gate.txt 2>&1; then
  echo "run.sh: gate is clear"
else
  echo "run.sh: gate after the session:"
  head -45 work/.gate.txt
  stop_services
  if [ "$(elapsed)" -lt 400 ] && [ "${KIT_NO_RESUME:-}" != "1" ]; then
    again="kit/check.sh still reports the following. Fix it, keeping the code in a state that builds, then stop.

$(head -45 work/.gate.txt)"
    handover="An earlier session worked on the ticket in task.md and stopped. Its notes are in work/ledger.md, its scenarios in work/scenarios/, its report script in work/report.py, and its changes are in app/services (compare with .pristine/app/services). $again"
    untouched=1
    for service in api router worker; do
      diff -rq -x AGENTS.md -x __pycache__ ".pristine/app/services/$service" "app/services/$service" >/dev/null 2>&1 || untouched=0
    done
    if [ "$untouched" -eq 1 ] && [ ! -s work/ledger.md ] && [ -z "$(ls out 2>/dev/null)" ]; then
      # The first session left nothing at all (it did not start, or was refused): the next
      # one gets the whole job, not a hand-over.
      handover="$(compose kit/prompt.md)"
      again="$handover"
      rm -f "work/.session.$main_stage"
    fi
    if [ -n "$RESCUE" ]; then
      agent "$RESCUE" start $((HARD_STOP - 10 - $(elapsed))) rescue "$handover"
      echo "run.sh: rescue session ($RESCUE) ended with status $? after $(elapsed) s"
    elif [ "$(harness_of "$MAIN")" = "claude" ]; then
      agent "$MAIN" resume $((HARD_STOP - 10 - $(elapsed))) "$main_stage" "$again"
      echo "run.sh: resumed session ended with status $? after $(elapsed) s"
    else
      agent "$MAIN" start $((HARD_STOP - 10 - $(elapsed))) rescue "$handover"
      echo "run.sh: second session ($MAIN) ended with status $? after $(elapsed) s"
    fi
  fi
fi
exit 0
