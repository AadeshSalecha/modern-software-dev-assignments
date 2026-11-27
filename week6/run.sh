#!/usr/bin/env bash
# Entry point. The grader runs `./run.sh task.md` from this directory, with no terminal and
# nobody to answer questions, for at most 10 minutes. When it exits, app/services/{api,router,
# worker} and the files under out/ are scored.
#
# What it does:
#   1. kit/prepare.sh   no model: snapshot the release, set unused code aside, install the
#                       instruction files, load the evidence into work/evidence.db
#   2. two solvers      each does the whole job on its own, at the same time: the main agent
#                       here, the second agent in a copy of this workspace. They are different
#                       harnesses and model families on purpose. A third session answers
#                       only the report request, from the raw files, without the kit's
#                       database or skills
#   3. kit/cross.py     no model: every scenario either solver wrote is run on both repairs,
#                       and the two reports are compared
#   4. follow-up        the main solver's session is resumed with the other solver's change,
#                       ledger and scenarios, and the runs its own repair fails, and settles
#                       each difference by the ticket. If its own gate still fails after
#                       that and money and time are left, it gets one more session on that.
#                       A result is kept only if it is no worse than what it started from;
#                       then the better of the two repairs is chosen again.
#                       If the reports differ, a fresh session decides between them
#   5. install          the better repair and the decided report end up here;
#                       kit/prepare.sh --restore puts app/ back in its shipped layout
#
# After step 2 this workspace already holds a complete answer; later steps only replace a
# part of it when the replacement checks out. Step 4 is skipped when time or money is short.
#
# Settings, each "<harness>:<model>:<effort>" with harness claude or codex. The defaults are
# what is submitted; the grader passes no environment, so it gets them.
#   KIT_MAIN     the main solver
#   KIT_SECOND   the second solver; empty for one solver only
#   KIT_THIRD    the session that derives the report from the raw files; empty for none
#   KIT_JUDGE    the session that decides between different reports
#   KIT_SECOND_FALLBACK, KIT_THIRD_FALLBACK   what runs if those two do not get going
# Other switches for experiments: KIT_TOOLS, KIT_MAX_TURNS, KIT_NO_HOOK=1, KIT_NO_FOLLOWUP=1,
# KIT_VARIANT=flags (the bare ticket with only the harness flags changed), report (only the
# report, by one session with the kit) or raw-report (only the session that derives the report
# from the raw files), KIT_SOLVE_END,
# KIT_HARD_STOP, KIT_FIX_BUDGET, KIT_JUDGE_BUDGET, KIT_RECONCILE=fails, KIT_KEEP_B=1, KIT_MONEY,
# KIT_MAIN_SHARE, KIT_ADAPT=0 (follow-ups keep their effort), KIT_NO_NUDGE=1 (no word about unused budget).
set -u

TASK_FILE="${1:?usage: ./run.sh <task-file>}"
cd "$(dirname "$0")" || exit 1
ROOT=$PWD
STARTED=$(date +%s)
# An upload keeps no file modes, and the grader makes run.sh executable again and nothing
# else. So nothing here is started by its path: every helper goes through bash or python3.
# The modes are put back as well, for agents that start a helper by its path.
chmod u+x kit/*.sh kit/*.py 2>/dev/null
SOLVE_END=${KIT_SOLVE_END:-300}        # solvers are stopped this many seconds after the start
HARD_STOP=${KIT_HARD_STOP:-570}        # everything here is finished by then, 30 s before the grader's limit
FIX_END=$((HARD_STOP - 130))           # the comparison session is stopped then, so its result can be checked
# Spending lines, in dollars of estimated spend so far. Full cost credit ends at $0.75 and each
# cent above costs about half a point. A comparison cost 4 to 17 cents in ten runs, so it
# starts below 0.60. A report decision costs about 15 cents, but two different reports mean
# one of them is wrong and the report is a third of the correctness score, so it may start
# up to 0.70.
FIX_BUDGET=${KIT_FIX_BUDGET:-0.60}
JUDGE_BUDGET=${KIT_JUDGE_BUDGET:-0.70}
RECONCILE=${KIT_RECONCILE:-always}     # always: compare the two repairs every time; fails: only when a run fails

MAIN="${KIT_MAIN:-claude:claude-sonnet-5-5:medium}"
SECOND="${KIT_SECOND-codex:gpt-6.1-terra:medium}"
THIRD="${KIT_THIRD-codex:gpt-6.1-terra:medium}"
JUDGE="${KIT_JUDGE:-claude:claude-sonnet-5-5:medium}"
# If the harness of the second or third agent does not get going here (the first graded run of
# this design made no request to it at all), a Claude Code session takes its place: that
# harness is known to work wherever the main solver does.
SECOND_FALLBACK="${KIT_SECOND_FALLBACK-claude:claude-haiku-5-5:medium}"
THIRD_FALLBACK="${KIT_THIRD_FALLBACK-claude:claude-sonnet-5-5:low}" # Haiku rarely finishes this in time
REPORT_END=${KIT_REPORT_END:-220}      # the report-only session is stopped this many seconds after the start

# One limit for money and one clock for the whole run, which kit/budget.py reports to this
# script, to the stop hook and to the agents. Sessions that have room are given more of it:
# the main solver is told once if it stops with a good part of its share unused, and the
# follow-up sessions run at effort high when the run can afford that (KIT_ADAPT=0: never).
export KIT_MONEY="${KIT_MONEY:-0.72}"  # dollars the run means to stay under; full cost credit ends at 0.75
MAIN_SHARE=${KIT_MAIN_SHARE:-0.30}     # of which the main solver's first session may use this much
SECOND_SHARE=${KIT_SECOND_SHARE:-0.18} # and the second solver this much (it is told; see also its time limit)
export KIT_STARTED=$STARTED
export KIT_LOGS="$ROOT/work/logs"

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
# Cache writes at the 5-minute rate: no session here lasts longer, and the 1-hour rate costs
# 60% more per token written.
export FORCE_PROMPT_CACHING_5M=1
export DISABLE_AUTOUPDATER=1

# --- running things with a deadline, and tidying up whatever happens ------------------
CHILD=""
BACKGROUND=""
B_ROOT=""
C_ROOT=""
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

stop_services() { # replay services started from a workspace detach themselves; stop any left
  local root
  for root in "$ROOT" "$B_ROOT"; do
    [ -n "$root" ] || continue
    pkill -f "$root/app/services/" 2>/dev/null
    pkill -f "$root/app/.build/" 2>/dev/null
    pkill -f "$root/.pristine/app/" 2>/dev/null
  done
  return 0
}

PREPARED=0
finish() {
  trap - EXIT TERM INT
  [ -n "$CHILD" ] && kill_tree "$CHILD"
  for pid in $BACKGROUND; do
    kill_tree "$pid"
  done
  if [ "$PREPARED" -eq 1 ]; then
    stop_services
    bash kit/prepare.sh --restore
  fi
  # The second workspace is a copy of everything: what was worth keeping is in work/cross/.
  if [ -n "$B_ROOT" ] && [ "$B_ROOT" != "$ROOT" ] && [ -d "$B_ROOT/kit" ] && [ "${KIT_KEEP_B:-}" != "1" ]; then
    rm -rf "$B_ROOT"
  fi
  if [ -n "$C_ROOT" ] && [ "$C_ROOT" != "$ROOT" ] && [ -d "$C_ROOT/contracts" ] && [ "${KIT_KEEP_B:-}" != "1" ]; then
    rm -rf "$C_ROOT"
  fi
}
trap finish EXIT
trap 'exit 143' TERM INT

# --- one headless session ----------------------------------------------------------------
agent() { # agent <harness:model:effort> <start|resume> <seconds> <name> <prompt>, in the current directory
  local spec=$1 mode=$2 seconds=$3 stage=$4 prompt=$5
  local harness model effort began status
  IFS=: read -r harness model effort <<<"$spec"
  effort="${effort:-medium}"
  began=$(date +%s)
  export KIT_DEADLINE=$(($(elapsed) + seconds)) # for kit/budget.py: when this session is stopped
  case "$harness" in
    claude)
      local flags=(
        --model "$model" --effort "$effort"
        --tools "${KIT_TOOLS:-Bash,Read,Edit,Write}"
        --strict-mcp-config --setting-sources project
        --permission-mode bypassPermissions
        --output-format stream-json --verbose
      )
      if [ "$mode" = "resume" ] && [ -s "work/.session.$stage" ]; then
        KIT_STAGE="$stage" limited "$seconds" claude -p "$prompt" --resume "$(cat "work/.session.$stage")" \
          --max-turns 40 "${flags[@]}"
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
      # Codex reads the root AGENTS.md by itself. It has no stop hook here.
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

show() { # show <log>...: the end of each session log. The whole of them would push this
  # script's own lines past the 5 MB that the practice tool and the grader keep of its output.
  local log
  for log in "$@"; do
    [ -f "$log" ] || continue
    echo "run.sh: ---- $(basename "$log"), last 600 kB of $(wc -c <"$log" | tr -d ' ') bytes ----"
    tail -c 600000 "$log"
    echo
  done
}

log_for() { # log_for <step> <spec>: where that session's output goes (kit/spend.py reads the name)
  local rest=${2#*:}
  echo "$ROOT/work/logs/$1.$(harness_of "$2").${rest%%:*}.jsonl"
}

affordable() { # affordable <dollars> <seconds>: spend so far is below the first, time gone below the second
  [ "$(elapsed)" -lt "$2" ] && python3 kit/spend.py --under "$1" work/logs
}

with_room() { # with_room <harness:model:effort> <dollars>: the same at effort high if the run can spend that much more
  local rest=${1#*:}
  if [ "${KIT_ADAPT:-1}" = "1" ] && python3 kit/budget.py --room "$2" 2>/dev/null; then
    echo "${1%%:*}:${rest%%:*}:high"
  else
    echo "$1"
  fi
}

compose() { # compose <prompt file> [extra file]: the fixed prompt, the notes from prep, then the ticket
  cat "$1"
  if [ -n "${2:-}" ]; then
    cat "$2" 2>/dev/null
  else
    cat work/start.txt 2>/dev/null
    echo
    cat work/evidence.txt 2>/dev/null
  fi
  printf '\n<ticket file="%s">\n' "$TASK_FILE"
  cat "$TASK_FILE"
  printf '\n</ticket>\n'
}

COPY_PROBLEM=""
usable_copy() { # usable_copy <dir> <needed path>...: all of it is there and programs can be run from there
  local place=$1 need
  shift
  for need in "$@"; do
    [ -e "$place/$need" ] || {
      COPY_PROBLEM="$need is missing"
      return 1
    }
  done
  mkdir -p "$place/work" 2>/dev/null
  printf '#!/bin/sh\nexit 0\n' >"$place/work/.probe" 2>/dev/null && chmod +x "$place/work/.probe" 2>/dev/null &&
    "$place/work/.probe" 2>/dev/null || {
    COPY_PROBLEM="programs cannot be run from there"
    return 1
  }
  rm -f "$place/work/.probe"
  return 0
}

# A graded run is another account than the one that put the files here, so some path under app/
# may not be readable. Copies therefore take what can be taken and are then checked for what a
# session needs; one failed file must not cost the run its second opinion.
make_copy() { # a second workspace for the second solver: outside this one, or else inside it
  local place
  for place in "$(mktemp -d "${TMPDIR:-/tmp}/week6-b.XXXXXX" 2>/dev/null)" "$ROOT/.second"; do
    [ -n "$place" ] || continue
    rm -rf "$ROOT/.second" 2>/dev/null
    mkdir -p "$place/work/scenarios" "$place/out" 2>/dev/null || continue
    cp -R AGENTS.md CLAUDE.md .claude kit app .pristine "$place/" 2>/dev/null
    [ -f rate_card.json ] && cp rate_card.json "$place/" 2>/dev/null
    cp "$TASK_FILE" "$place/task.md" 2>/dev/null
    cp work/start.txt work/evidence.txt work/evidence.db "$place/work/" 2>/dev/null
    ln -s "$ROOT/incident" "$place/incident" 2>/dev/null || cp -R incident "$place/incident" 2>/dev/null
    if usable_copy "$place" AGENTS.md task.md kit/check.py kit/rollout.py app/services/api app/services/router \
      app/services/worker app/bin/replaylib.py app/contracts .pristine/app/services incident; then
      B_ROOT=$place
      return 0
    fi
    echo "run.sh: no second workspace at $place: $COPY_PROBLEM"
    rm -rf "$place" 2>/dev/null
  done
  B_ROOT=""
  return 1
}

make_room() { # a bare folder for the report-only session: the ticket, the raw evidence, the contracts
  local place
  for place in "$(mktemp -d "${TMPDIR:-/tmp}/week6-c.XXXXXX" 2>/dev/null)" "$ROOT/.third"; do
    [ -n "$place" ] || continue
    rm -rf "$ROOT/.third" 2>/dev/null
    mkdir -p "$place/work" "$place/out" 2>/dev/null || continue
    cp "$TASK_FILE" "$place/task.md" 2>/dev/null
    cp -R app/contracts "$place/contracts" 2>/dev/null
    ln -s "$ROOT/incident" "$place/incident" 2>/dev/null || cp -R incident "$place/incident" 2>/dev/null
    if usable_copy "$place" task.md contracts/evidence.md incident; then
      C_ROOT=$place
      return 0
    fi
    echo "run.sh: no folder for the report-only session at $place: $COPY_PROBLEM"
    rm -rf "$place" 2>/dev/null
  done
  C_ROOT=""
  return 1
}

got_going() { # got_going <log>: the harness reached its model and did something
  grep -q -e '"type":"item.completed"' -e '"type":"assistant"' -e '"type":"turn.completed"' "$1" 2>/dev/null
}

# with_fallback <first spec> <fallback spec> <log name> <seconds from the start> <stage> <prompt>
# Runs the first agent in the current directory. If its harness comes back within a minute
# without having done anything, the fallback runs in its place.
with_fallback() {
  local first=$1 fallback=$2 name=$3 until=$4 stage=$5 prompt=$6 began log
  began=$(date +%s)
  log=$(log_for "$name" "$first")
  KIT_SESSION=$name agent "$first" start $((until - $(elapsed))) "$stage" "$prompt" >"$log" 2>&1
  if ! got_going "$log" && [ -n "$fallback" ] && [ $(($(date +%s) - began)) -lt 60 ]; then
    echo "run.sh: $first did not get going as $name (see its output below); $fallback takes its place" >>"$log"
    KIT_SESSION=${name}2 agent "$fallback" start $((until - $(elapsed))) "$stage" "$prompt" >"$(log_for "${name}2" "$fallback")" 2>&1
  fi
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
  KIT_NO_HOOK=1 agent "$MAIN" start "$SOLVE_END" all "$(cat "$TASK_FILE")"
  exit 0
fi

bash kit/prepare.sh
prepared=$?
if [ "$prepared" -eq 3 ]; then
  exit 3 # the development checkout: prepare.sh has said why
fi
PREPARED=1
mkdir -p work/logs work/cross work/scenarios out
# Everything after this leans on what preparation leaves behind: the snapshot of the release
# (comparisons, release replacement, the second workspace) and the evidence database (the
# report). If it did not get that far, for whatever reason, the two are made here.
if [ ! -d .pristine/app/services ] || [ ! -s work/start.txt ] || { [ -d incident ] && [ ! -s work/evidence.db ]; }; then
  echo "run.sh: preparation did not complete (status $prepared); making the snapshot and the evidence database here"
  if [ ! -d .pristine/app/services ] && [ -d app/services ]; then
    mkdir -p .pristine/app
    for part in services bin scenarios; do
      [ -d "app/$part" ] && [ ! -e ".pristine/app/$part" ] && cp -R "app/$part" ".pristine/app/$part" 2>/dev/null
    done
  fi
  [ -s work/start.txt ] || echo "preparation was cut short: the notes that normally stand here are missing" >work/start.txt
  if [ -d incident ] && [ ! -s work/evidence.db ]; then
    python3 kit/evidence.py build incident work/evidence.db >work/evidence.txt 2>&1 ||
      echo "evidence: loading failed: $(tail -1 work/evidence.txt)" >>work/start.txt
  fi
fi
echo "run.sh: prepared after $(elapsed) s: snapshot $([ -d .pristine/app/services ] && echo yes || echo NO)," \
  "evidence database $([ -s work/evidence.db ] && echo yes || echo NO)," \
  "service notes $([ -f app/services/router/AGENTS.md ] && echo yes || echo NO)," \
  "harness $([ -f work/.no_harness ] && echo NO || echo yes)"
PROMPT="$(compose kit/prompt.md)"

if [ "${KIT_VARIANT:-}" = "raw-report" ]; then
  # Experiment: only the session that derives the report from the raw files, to measure it.
  if make_room; then
    RAW_PROMPT="$(cat kit/prompt-report-raw.md)
$(printf '\n<ticket file="%s">\n' "$TASK_FILE")
$(cat "$TASK_FILE")
</ticket>"
    (cd "$C_ROOT" && KIT_NO_HOOK=1 with_fallback "$THIRD" "$THIRD_FALLBACK" c "$REPORT_END" report "$RAW_PROMPT")
    show work/logs/c.*.jsonl work/logs/c2.*.jsonl
    mkdir -p out && cp "$C_ROOT"/out/* out/ 2>/dev/null
    cp "$C_ROOT/report.py" work/report-raw.py 2>/dev/null
  fi
  echo "run.sh: raw-file report only, after $(elapsed) s; estimated spend: $(python3 kit/spend.py work/logs | tail -1)"
  exit 0
fi

if [ "${KIT_VARIANT:-}" = "report" ]; then
  # Experiment: one session that answers only the report request, to measure the report
  # skill by itself. Nothing under app/ is meant to change.
  cat >work/.report-only.md <<'EOF'
Answer only the report request of the ticket below (its second part). Do not change anything
under `app/`. Read `.claude/skills/evidence-report/SKILL.md` first, write the file under
`out/` with a script `work/report.py`, run `bash kit/check.sh --only report`, and finish in three
lines.

Start-of-run notes:
EOF
  A_LOG=$(log_for a "$MAIN")
  KIT_NO_HOOK=1 KIT_SESSION=a agent "$MAIN" start "$SOLVE_END" report "$(compose work/.report-only.md)" >"$A_LOG" 2>&1
  cat "$A_LOG"
  echo "run.sh: report only; estimated spend: $(python3 kit/spend.py work/logs | tail -1)"
  exit 0
fi

# One more session for the main solver, and a check of what it hands back.
# improve <name> <prompt>: resumes the main session with <prompt>. Its result is kept only if
# the repair is no worse than before: it builds, the gate has not started failing, and on the
# same scenarios it fails no more runs than the repair it started from. Anything else, or no
# time to check, and the services go back to how they were. Sets gate_now for the caller.
improve() {
  local name=$1 prompt=$2 spec log keep verdict now was usable gate_before=$gate_now gate_after service
  rm -rf work/cross/before work/cross/before-root
  mkdir -p work/cross/before
  for service in api router worker; do
    cp -R "app/services/$service" work/cross/before/ 2>/dev/null
  done
  spec=$(with_room "$MAIN" 0.30) # effort high if the run can afford it; a judge may be running too
  log=$(log_for "$name" "$spec")
  KIT_SESSION=$name KIT_PHASE=$name agent "$spec" resume $((FIX_END - $(elapsed))) all "$prompt" >"$log" 2>&1
  echo "run.sh: $name session ($spec) ended with status $? after $(elapsed) s"
  show "$log"
  stop_services
  keep=0
  verdict="there was no time left to check it"
  if [ "$(elapsed)" -lt $((HARD_STOP - 80)) ]; then
    limited 45 bash kit/check.sh --only repair >work/cross/gate-after.txt 2>&1
    gate_after=$?
    stop_services
    # The repair as it was, as a workspace of its own, so that both are run on the same scenarios.
    mkdir -p work/cross/before-root/work/scenarios work/cross/vs-before
    cp -R app work/cross/before-root/app 2>/dev/null
    for service in api router worker; do
      rm -rf "work/cross/before-root/app/services/$service"
      cp -R "work/cross/before/$service" "work/cross/before-root/app/services/$service" 2>/dev/null
    done
    rm -f work/cross/vs-before/decision.env
    limited $((HARD_STOP - 25 - $(elapsed))) python3 kit/cross.py --b "$ROOT/work/cross/before-root" --repairs-only \
      --out work/cross/vs-before >work/cross/log-vs-before.txt 2>&1
    stop_services
    now=$(grep "^A_FAILS=" work/cross/vs-before/decision.env 2>/dev/null | cut -d= -f2)
    was=$(grep "^B_FAILS=" work/cross/vs-before/decision.env 2>/dev/null | cut -d= -f2)
    usable=$(grep "^A_USABLE=" work/cross/vs-before/decision.env 2>/dev/null | cut -d= -f2)
    case "$now" in '' | *[!0-9]*) now="" ;; esac
    case "$was" in '' | *[!0-9]*) was="" ;; esac
    if [ -z "$now" ] || [ -z "$was" ]; then
      verdict="the check of the result did not finish"
    elif [ "$usable" != "1" ]; then
      verdict="it does not build"
    elif [ "$gate_before" -eq 0 ] && [ "$gate_after" -ne 0 ]; then
      verdict="kit/check.sh passed before and fails now"
    elif [ "$now" -gt "$was" ]; then
      verdict="on the same scenarios it fails $now runs and the repair before it failed $was"
    else
      keep=1
      verdict="it builds, the gate is no worse, and on the same scenarios it fails $now runs (before: $was)"
    fi
  fi
  if [ "$keep" -eq 1 ]; then
    echo "run.sh: keeping the main repair after the $name session: $verdict"
    gate_now=$gate_after
    cp work/cross/gate-after.txt work/cross/gate.txt 2>/dev/null
  else
    echo "run.sh: going back to the main repair as it was before the $name session: $verdict"
    for service in api router worker; do
      if [ -d "work/cross/before/$service" ]; then
        rm -rf "work/cross/dropped-$service"
        mv "app/services/$service" "work/cross/dropped-$service" 2>/dev/null
        cp -R "work/cross/before/$service" "app/services/$service"
      fi
    done
  fi
  rm -rf work/cross/before-root
}

# --- 2. the solvers ------------------------------------------------------------------------
B_PID=""
C_PID=""
if [ -n "$SECOND" ] && make_copy; then
  B_LOG=$(log_for b "$SECOND")
  (cd "$B_ROOT" && KIT_SHARE=$SECOND_SHARE with_fallback "$SECOND" "$SECOND_FALLBACK" b "$SOLVE_END" all "$PROMPT") &
  B_PID=$!
  BACKGROUND="$B_PID"
  echo "run.sh: second solver ($SECOND) started in $B_ROOT"
else
  [ -n "$SECOND" ] && echo "run.sh: no second workspace could be made; going on without a second solver"
  SECOND=""
fi
# A third session answers only the report request, from the raw files, in a folder that has
# neither the kit's database nor its skills: a way to the report that shares nothing with the
# other two but the ticket.
if [ -n "$THIRD" ] && make_room; then
  RAW_PROMPT="$(cat kit/prompt-report-raw.md)
$(printf '\n<ticket file="%s">\n' "$TASK_FILE")
$(cat "$TASK_FILE")
</ticket>"
  (cd "$C_ROOT" && KIT_NO_HOOK=1 with_fallback "$THIRD" "$THIRD_FALLBACK" c "$REPORT_END" report "$RAW_PROMPT") &
  C_PID=$!
  BACKGROUND="$BACKGROUND $C_PID"
  echo "run.sh: report-only session ($THIRD) started in $C_ROOT"
else
  [ -n "$THIRD" ] && echo "run.sh: no folder for the report-only session could be made; going on without it"
  THIRD=""
fi
A_LOG=$(log_for a "$MAIN")
KIT_SESSION=a KIT_SHARE=$MAIN_SHARE KIT_PHASE=solve agent "$MAIN" start $((SOLVE_END - $(elapsed))) all "$PROMPT" >"$A_LOG" 2>&1
echo "run.sh: main solver ($MAIN) ended with status $? after $(elapsed) s"
A_ENDED=$(elapsed)
show "$A_LOG"
if [ -n "$SECOND" ]; then
  # The second solver gets two and a half more minutes (and at least 200 s in all): the main
  # solver's session is resumed later, and its cached context is gone five minutes after its
  # last turn.
  b_left=150
  [ $((A_ENDED + b_left)) -lt 200 ] && b_left=$((200 - A_ENDED))
  (
    waited=0
    while [ "$waited" -lt "$b_left" ]; do
      sleep 5
      waited=$((waited + 5))
      # It is also stopped when the run has less than ten cents left: what remains is for the
      # report decision and the comparison, which do more for the answer than its last steps.
      if [ $((waited % 15)) -eq 0 ] && ! python3 kit/budget.py --room 0.10 2>/dev/null; then
        break
      fi
    done
    kill_tree "$B_PID"
  ) >/dev/null 2>&1 &
  B_TIMER=$!
  wait "$B_PID"
  echo "run.sh: second solver ended with status $? after $(elapsed) s; its output follows"
  pkill -P "$B_TIMER" 2>/dev/null
  kill "$B_TIMER" 2>/dev/null
  wait "$B_TIMER" 2>/dev/null
  show work/logs/b.*.jsonl work/logs/b2.*.jsonl
fi
if [ -n "$C_PID" ]; then
  wait "$C_PID"
  echo "run.sh: report-only session ended with status $? after $(elapsed) s; its output follows"
  show work/logs/c.*.jsonl work/logs/c2.*.jsonl
  ls "$C_ROOT/out" 2>/dev/null | sed 's/^/run.sh: it wrote out\//'
fi
BACKGROUND=""
stop_services

# --- 3. cross-check, 4. follow-up, 5. install ---------------------------------------------
BEST=a
A_FAILS=0
A_CHANGED=0
B_CHANGED=0
REPORTS=same
if [ -n "$SECOND" ] || [ -n "$THIRD" ]; then
  if [ -z "$SECOND" ]; then
    B_ROOT="$ROOT/work/cross/no-second" # nothing there: the reports are still compared
    mkdir -p "$B_ROOT"
  fi
  limited 140 python3 kit/cross.py --b "$B_ROOT" ${C_ROOT:+--c "$C_ROOT"} >work/cross/log.txt 2>&1
  echo "run.sh: cross-check after $(elapsed) s:"
  head -40 work/cross/log.txt
  stop_services
  if [ -s work/cross/decision.env ]; then
    BEST=$(grep '^BEST=' work/cross/decision.env | cut -d= -f2)
    A_FAILS=$(grep '^A_FAILS=' work/cross/decision.env | cut -d= -f2)
    A_CHANGED=$(grep '^A_CHANGED=' work/cross/decision.env | cut -d= -f2)
    B_CHANGED=$(grep '^B_CHANGED=' work/cross/decision.env | cut -d= -f2)
    REPORTS=$(grep '^REPORTS=' work/cross/decision.env | cut -d= -f2)
  fi
  case "$BEST" in a | b) ;; *) BEST=a ;; esac
  case "$A_FAILS" in '' | *[!0-9]*) A_FAILS=0 ;; esac

  JUDGE_PID=""
  if [ "${KIT_NO_FOLLOWUP:-}" != "1" ]; then
    # 4a. The reports. Settled without a judge: the one made from the raw files agrees with
    #     one of the others, or the main solver has none. Otherwise a fresh session works out
    #     each difference. The main solver's report is kept aside either way.
    mkdir -p work/cross/out-a && cp out/* work/cross/out-a/ 2>/dev/null
    if [ "$REPORTS" = "settled" ] && ls work/cross/decided/* >/dev/null 2>&1; then
      mkdir -p out && cp work/cross/decided/* out/
      echo "run.sh: the reports settle it without a judge; out/ now holds: $(ls work/cross/decided | tr '\n' ' ')"
    fi
    if [ "$REPORTS" = "decide" ] && affordable "$JUDGE_BUDGET" $((HARD_STOP - 140)); then
      judge_spec=$(with_room "$JUDGE" 0.24) # about 15 cents at effort high, and a comparison may follow
      JUDGE_LOG=$(log_for judge "$judge_spec")
      judge_prompt="$(compose kit/prompt-adjudicate.md work/cross/reports.txt)"
      (KIT_NO_HOOK=1 KIT_SESSION=judge agent "$judge_spec" start $((HARD_STOP - 40 - $(elapsed))) judge "$judge_prompt") >"$JUDGE_LOG" 2>&1 &
      JUDGE_PID=$!
      BACKGROUND="$JUDGE_PID"
    fi

    # 4b. The main solver's session is resumed with the other solver's change, ledger and
    #     scenarios, the runs its own repair fails, and what the gate still reports.
    want_fix=0
    if [ "$A_CHANGED" = "1" ] && [ -n "$SECOND" ]; then
      [ "$A_FAILS" -gt 0 ] && want_fix=1
      [ "$RECONCILE" = "always" ] && [ "$B_CHANGED" = "1" ] && want_fix=1
    fi
    # Money is kept back for a report decision that has started, and for a session whose
    # cached context has expired by now (a resumed session then pays to write it again).
    fix_line=$FIX_BUDGET
    [ -n "$JUDGE_PID" ] && fix_line=$(python3 -c "print($FIX_BUDGET - 0.10)")
    if [ $(($(elapsed) - A_ENDED)) -gt 230 ]; then
      fix_line=$(python3 -c "print($fix_line - 0.15)")
    fi
    gate_now=""
    if [ "$want_fix" -eq 1 ] && affordable "$fix_line" $((FIX_END - 80)); then
      limited 60 bash kit/check.sh --only repair >work/cross/gate.txt 2>&1
      gate_now=$?
      stop_services
      fix_prompt="$(cat kit/prompt-reconcile.md work/cross/fix.txt 2>/dev/null)"
      [ -s work/cross/fix.txt ] || fix_prompt="$fix_prompt
(none: your repair passes every run)"
      if [ "$gate_now" -ne 0 ] && grep -q '^BLOCKING' work/cross/gate.txt; then
        fix_prompt="$fix_prompt

Before any of that: kit/check.sh --only repair fails on your repair as it is now. Deal with this first.

$(head -30 work/cross/gate.txt)"
      fi
      improve compare "$fix_prompt"
    fi
    # 4c. Still failing its own gate, with money and time left: one more session on exactly
    #     that. Handing in a repair whose own checks fail is what the budget is there to prevent.
    if [ -n "$gate_now" ] && [ "$gate_now" -ne 0 ] && grep -q '^BLOCKING' work/cross/gate.txt 2>/dev/null &&
      [ "$(elapsed)" -lt $((FIX_END - 90)) ] && python3 kit/budget.py --room 0.12 2>/dev/null; then
      finish_prompt="$(cat kit/prompt-finish.md)

$(python3 kit/budget.py 2>/dev/null)

$(head -40 work/cross/gate.txt)"
      improve finish "$finish_prompt"
    fi
    # The better of the two repairs, now that the main one may have changed.
    if [ -n "$gate_now" ] && [ "$(elapsed)" -lt $((HARD_STOP - 45)) ]; then
      mkdir -p work/cross/after
      limited $((HARD_STOP - 20 - $(elapsed))) python3 kit/cross.py --b "$B_ROOT" --repairs-only \
        --out work/cross/after >work/cross/log-after.txt 2>&1
      head -8 work/cross/log-after.txt
      best_after=$(grep "^BEST=" work/cross/after/decision.env 2>/dev/null | cut -d= -f2)
      case "$best_after" in a | b) BEST=$best_after ;; esac
      stop_services
      echo "run.sh: the better repair is now $BEST"
    fi
    if [ -n "$JUDGE_PID" ]; then
      wait "$JUDGE_PID"
      echo "run.sh: report decision ($judge_spec) ended with status $? after $(elapsed) s"
      show "$JUDGE_LOG"
      for report in work/cross/out-a/*.json; do
        [ -e "$report" ] || continue
        if ! python3 -c 'import json, sys; json.load(open(sys.argv[1]))' "out/$(basename "$report")" 2>/dev/null; then
          echo "run.sh: the decided $(basename "$report") is missing or not JSON; keeping the first report"
          cp "$report" "out/$(basename "$report")"
        fi
      done
    fi
    BACKGROUND=""
  fi

  if [ "$BEST" = "b" ] && [ -n "$SECOND" ]; then
    for service in api router worker; do
      if [ -d "$B_ROOT/app/services/$service" ]; then
        mv "app/services/$service" "work/cross/a-$service" 2>/dev/null
        cp -R "$B_ROOT/app/services/$service" "app/services/$service"
      fi
    done
    echo "run.sh: installed the second solver's repair"
  fi
fi
echo "run.sh: finished after $(elapsed) s; estimated spend: $(python3 kit/spend.py work/logs | tail -1)"
exit 0
