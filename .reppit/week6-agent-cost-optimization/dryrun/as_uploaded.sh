#!/usr/bin/env bash
# What a submission zip does once it has been through an upload, without calling a model.
#
#   dryrun/as_uploaded.sh <submission.zip> [VAR=value ...]
#
# The zip is unpacked and every file mode is dropped, because an upload keeps none; the
# executable bit is put back on run.sh and on nothing else, which is what the grader does
# (tools/runner.py). The grader's own app/, incident/ and task.md are put in, the environment
# is emptied, and the stand-in `claude` and `codex` in this folder take the place of the
# harnesses (they make a harmless change and write a report; FAKE_* variables steer them).
# With AS_USER=<account> and root, the run happens as that account, as in grading.
#
# Exit status 0 if the run prepared the workspace, started all three sessions, compared them,
# wrote a report and left app/ in its shipped layout. The run's own lines are printed either
# way. Needs python3, go and node 24 or newer on PATH.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../../.." && pwd)"
ZIP="${1:?usage: as_uploaded.sh <submission.zip> [VAR=value ...]}"
shift
case "$ZIP" in /*) ;; *) ZIP="$PWD/$ZIP" ;; esac

BASE="$(mktemp -d "${TMPDIR:-/tmp}/as-uploaded.XXXXXX")"
trap 'rm -rf "$BASE"' EXIT
mkdir -p "$BASE/week6" "$BASE/bin" "$BASE/tmp" "$BASE/home"
(cd "$BASE/week6" && unzip -q "$ZIP") || exit 2
rm -rf "$BASE/week6/app" "$BASE/week6/incident" "$BASE/week6/tools"
cp -R "$REPO/week6/app" "$REPO/week6/incident" "$BASE/week6/"
cp "$REPO/week6/task.md" "$BASE/week6/task.md"
rm -rf "$BASE/week6/app/.build"
find "$BASE/week6/app" \( -name __pycache__ -o -name state \) -prune -exec rm -rf {} + 2>/dev/null
cp -R "$BASE/week6/app" "$BASE/app-before"
find "$BASE/week6" -type f ! -path "$BASE/week6/app/*" -exec chmod a-x {} +
chmod +x "$BASE/week6/run.sh"

cp "$HERE/claude" "$HERE/codex" "$BASE/bin/" && chmod +x "$BASE/bin/claude" "$BASE/bin/codex"
for tool in python3 node go; do
  found="$(command -v "$tool")" || { echo "as_uploaded.sh: $tool is not on PATH" >&2; exit 2; }
  ln -s "$found" "$BASE/bin/$tool"
done

run=(env -i "PATH=$BASE/bin:/usr/bin:/bin" "TMPDIR=$BASE/tmp" "HOME=$BASE/home" "$@" ./run.sh task.md)
if [ -n "${AS_USER:-}" ] && [ "$(id -u)" -eq 0 ]; then
  chown -R "$AS_USER" "$BASE" && chmod 755 "$BASE"
  run=(runuser -u "$AS_USER" -- "${run[@]}")
fi
(cd "$BASE/week6" && "${run[@]}") >"$BASE/log" 2>&1 </dev/null
status=$?

grep -a -e '^run.sh:' -e 'Permission denied' -e '^repairs:' -e '^reports:' "$BASE/log" | grep -v -e '---- ' | cut -c1-200

problems=0
bad() {
  echo "FAILED: $1"
  problems=1
}
need() { grep -a -q -e "$1" "$BASE/log" || bad "$2"; }
[ "$status" -eq 0 ] || bad "run.sh exited with status $status"
grep -a -q 'Permission denied' "$BASE/log" && bad "something was started by its path and could not run"
need 'prepared after .*snapshot yes, evidence database yes, service notes yes, harness yes' "preparation did not complete"
need 'second solver (.*) started' "the second solver did not start"
need 'report-only session (.*) started' "the report-only session did not start"
need 'cross-check after' "the cross-check did not run"
python3 -c 'import json, sys; json.load(open(sys.argv[1]))' "$BASE/week6/out/impact.json" 2>/dev/null || bad "out/impact.json is missing or not JSON"
[ -e "$BASE/week6/app/_deprecated" ] && bad "app/_deprecated was left behind"
# Outside the three services, app/ has to be exactly what the grader put there.
changed="$(diff -rq -x .build -x state -x __pycache__ "$BASE/app-before" "$BASE/week6/app" | grep -v -e '/services/api' -e '/services/router' -e '/services/worker')"
[ -n "$changed" ] && bad "app/ differs outside the three services: $(echo "$changed" | head -3)"
[ "$problems" -eq 0 ] && echo "as uploaded: ok"
exit "$problems"
