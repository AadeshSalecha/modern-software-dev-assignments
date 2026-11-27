#!/usr/bin/env bash
# Stop hook: run the gate when the agent wants to stop. A failing gate sends its output back
# (exit status 2): three times in any case, then only while the session has budget left.
# KIT_STAGE=report or repair (set by run.sh when two agents share the work) limits the gate to
# that agent's part. When the gate passes and the session still has budget, see below.
cd "$(dirname "$0")/.." || exit 0
[ -d tools/starter ] && exit 0   # the development checkout: this hook is for graded runs only
[ -d work ] || exit 0
[ "${KIT_NO_HOOK:-}" = "1" ] && exit 0   # experiments only
stage="${KIT_STAGE:-all}"
counter="work/.stop_blocks.$stage"
blocks=$(cat "$counter" 2>/dev/null || echo 0)
# Three times whatever the budget says. After that only while the session still has money and
# time (kit/budget.py), and never more than eight times: a failing build or scenario is not
# something to hand in while there is room to fix it.
if [ "$blocks" -ge 3 ]; then
  [ "$blocks" -ge 8 ] && exit 0
  python3 kit/budget.py --session-room 2>/dev/null || exit 0
fi
if [ "$stage" = "all" ]; then
  output=$(python3 kit/check.py --hook 2>&1)
else
  output=$(python3 kit/check.py --hook --only "$stage" 2>&1)
fi
status=$?
if [ "$status" -eq 0 ]; then
  # Nothing blocks. A first solve that stops with a good part of its share of the budget unused
  # is told so, once, with a list of checks to spend it on (kit/budget.py decides).
  if [ "$stage" = "all" ] && [ "${KIT_PHASE:-}" = "solve" ] && [ "${KIT_NO_NUDGE:-}" != "1" ]; then
    given=$(cat work/.nudged 2>/dev/null || echo 0)
    if [ "$given" -lt 3 ]; then
      note=$(python3 kit/budget.py --nudge "$given" 2>/dev/null)
      if [ -n "$note" ]; then
        echo $((given + 1)) >work/.nudged
        echo "$note" >&2
        exit 2
      fi
    fi
  fi
  exit 0
fi
echo $((blocks + 1)) >"$counter"
{
  echo "Before you stop, kit/check.sh reports (check $((blocks + 1))):"
  echo "$output" | head -45
} >&2
exit 2
