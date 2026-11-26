#!/usr/bin/env bash
# Stop hook: run the gate when the agent wants to stop. A failing gate sends its output back
# (exit status 2), at most 4 times in a run; after that the agent may stop whatever the gate says.
# KIT_STAGE=report or repair (set by run.sh when two agents share the work) limits the gate to
# that agent's part.
cd "$(dirname "$0")/.." || exit 0
[ -d tools/starter ] && exit 0   # the development checkout: this hook is for graded runs only
[ -d work ] || exit 0
[ "${KIT_NO_HOOK:-}" = "1" ] && exit 0   # experiments only
stage="${KIT_STAGE:-all}"
counter="work/.stop_blocks.$stage"
blocks=$(cat "$counter" 2>/dev/null || echo 0)
[ "$blocks" -ge 4 ] && exit 0
if [ "$stage" = "all" ]; then
  output=$(python3 kit/check.py --hook 2>&1)
else
  output=$(python3 kit/check.py --hook --only "$stage" 2>&1)
fi
status=$?
[ "$status" -eq 0 ] && exit 0
echo $((blocks + 1)) >"$counter"
{
  echo "Not finished: kit/check.sh reports (stop check $((blocks + 1)) of at most 4)"
  echo "$output" | head -45
} >&2
exit 2
