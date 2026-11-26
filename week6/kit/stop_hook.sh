#!/usr/bin/env bash
# Stop hook: run the gate when the agent wants to stop. A failing gate sends its output back
# (exit status 2), at most 4 times in a run; after that the agent may stop whatever the gate says.
cd "$(dirname "$0")/.." || exit 0
[ -d tools/starter ] && exit 0   # the development checkout: this hook is for graded runs only
[ -d work ] || exit 0
[ "${KIT_NO_HOOK:-}" = "1" ] && exit 0   # experiments only
blocks=$(cat work/.stop_blocks 2>/dev/null || echo 0)
[ "$blocks" -ge 4 ] && exit 0
output=$(python3 kit/check.py --hook 2>&1)
status=$?
[ "$status" -eq 0 ] && exit 0
echo $((blocks + 1)) >work/.stop_blocks
{
  echo "Not finished: kit/check.sh reports (stop check $((blocks + 1)) of at most 4)"
  echo "$output" | head -45
} >&2
exit 2
