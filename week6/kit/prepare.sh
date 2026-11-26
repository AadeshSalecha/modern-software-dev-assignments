#!/usr/bin/env bash
# Deterministic set-up before the agent starts, and the matching tidy-up after it.
#
#   kit/prepare.sh             snapshot the release, set unused code aside, install the
#                              instruction files, load the evidence
#   kit/prepare.sh --restore   put app/ back in its shipped layout, keeping the agent's edits
#
# It never runs in the development checkout (where tools/starter/ exists), because it moves
# files inside app/. practice.py and the grader both run it in a copy without that folder.
# Exit status: 0 done, 3 refused (development checkout). Nothing here calls a model.

set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT" || exit 1
OVERLAY=kit/overlay
MOVED=work/.moved
INSTALLED=work/.installed
SET_ASIDE=(sdk legacy services/router-next deploy/helm)

if [ -d tools/starter ] && [ "${KIT_FORCE:-}" != "1" ]; then
  echo "prepare.sh: this is the development checkout (tools/starter/ exists); not touching app/." >&2
  echo "prepare.sh: run the setup with: python3 tools/practice.py --keep" >&2
  exit 3
fi

restore() {
  if [ -f "$MOVED" ]; then
    while IFS=$'\t' read -r from to; do
      if [ -e "$to" ] && [ ! -e "$from" ]; then
        mkdir -p "$(dirname "$from")" && mv "$to" "$from"
      fi
    done <"$MOVED"
    rm -f "$MOVED"
  fi
  if [ -f "$INSTALLED" ]; then
    while IFS= read -r path; do
      [ -n "$path" ] && rm -f "$path"
    done <"$INSTALLED"
    rm -f "$INSTALLED"
  fi
  for name in AGENTS.md CLAUDE.md; do
    if [ -f "app/_deprecated/old-$name.txt" ] && [ ! -e "app/$name" ]; then
      mv "app/_deprecated/old-$name.txt" "app/$name"
    fi
  done
  rm -f app/_deprecated/README.md
  rmdir app/_deprecated 2>/dev/null || true
}

set_aside() {
  mkdir -p app/_deprecated
  : >"$MOVED"
  for item in "${SET_ASIDE[@]}"; do
    target="app/_deprecated/$(basename "$item")"
    if [ -e "app/$item" ] && [ ! -e "$target" ]; then
      mv "app/$item" "$target" && printf '%s\t%s\n' "app/$item" "$target" >>"$MOVED"
    fi
  done
}

install_file() { # source destination
  [ -f "$1" ] || return 0
  mkdir -p "$(dirname "$2")" && cp "$1" "$2" && echo "$2" >>"$INSTALLED"
}

if [ "${1:-}" = "--restore" ]; then
  restore
  exit 0
fi

mkdir -p work/scenarios out
{
  echo "toolchain: python $(python3 -c 'import platform; print(platform.python_version())' 2>&1)," \
    "node $(node -v 2>&1 | head -1), $(go version 2>&1 | head -1 | cut -d' ' -f3-4)"
} >work/start.txt

# 1. The release as shipped, for comparison and for rollout checks.
if [ ! -d .pristine/app ] && [ -d app/services ]; then
  mkdir -p .pristine/app
  for part in services bin scenarios; do
    [ -d "app/$part" ] && cp -R "app/$part" ".pristine/app/$part"
  done
  find .pristine -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null
fi

# 2. Code no scored service uses moves to app/_deprecated/, unless that breaks the release.
if [ -d app ] && [ ! -f "$MOVED" ]; then
  set_aside
  shipped=(app/scenarios/*.json)
  if [ -e "${shipped[0]}" ]; then
    if python3 kit/rollout.py "${shipped[@]}" >work/.shipped.txt 2>&1; then
      echo "release as shipped: all ${#shipped[@]} scenarios in app/scenarios pass" >>work/start.txt
    else
      # Put everything back and see whether the move was the cause.
      while IFS=$'\t' read -r from to; do
        [ -e "$to" ] && mv "$to" "$from"
      done <"$MOVED"
      : >"$MOVED"
      if python3 kit/rollout.py "${shipped[@]}" >work/.shipped.txt 2>&1; then
        echo "release as shipped: all ${#shipped[@]} scenarios in app/scenarios pass (nothing was set aside)" >>work/start.txt
      else
        set_aside
        {
          echo "release as shipped: scenarios in app/scenarios do NOT all pass before any change:"
          head -12 work/.shipped.txt
        } >>work/start.txt
      fi
    fi
  fi
fi

# 3. Instruction files. The shipped app/AGENTS.md and app/CLAUDE.md are kept, out of the way.
if [ -d app ] && [ ! -f "$INSTALLED" ]; then
  : >"$INSTALLED"
  mkdir -p app/_deprecated
  for name in AGENTS.md CLAUDE.md; do
    [ -f "app/$name" ] && mv "app/$name" "app/_deprecated/old-$name.txt"
  done
  cp "$OVERLAY/deprecated.README.md" app/_deprecated/README.md 2>/dev/null
  install_file "$OVERLAY/app.AGENTS.md" app/AGENTS.md
  if [ -f app/AGENTS.md ]; then
    printf '@AGENTS.md\n' >app/CLAUDE.md && echo app/CLAUDE.md >>"$INSTALLED"
  fi
  for service in api router worker; do
    [ -d "app/services/$service" ] || continue
    target="app/services/$service/AGENTS.md"
    [ -e "$target" ] && continue
    {
      cat "$OVERLAY/$service.AGENTS.md" 2>/dev/null
      echo
      python3 kit/mapgen.py "app/services/$service" 2>/dev/null
    } >"$target"
    echo "$target" >>"$INSTALLED"
  done
fi

# 4. The evidence, loaded once.
if [ -d incident ]; then
  if python3 kit/evidence.py build incident work/evidence.db >work/evidence.txt 2>&1; then
    echo "evidence: loaded into work/evidence.db (summary below, also in work/evidence.txt)" >>work/start.txt
  else
    echo "evidence: loading failed: $(tail -1 work/evidence.txt)" >>work/start.txt
  fi
fi
exit 0
