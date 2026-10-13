#!/usr/bin/env python3
"""Validate approval-report data and render it as HTML and/or plain text.

Usage (run from the skill directory):
    python3 scripts/build_report.py report.json --html approval-report.html --text approval-report.txt
    python3 scripts/build_report.py report.json --check        # validate only

Standard library only. Exit code 1 and a list of errors if the data breaks a rule.

report.json shape:
{
  "mode": "full" | "weekly" | "report-only",
  "generatedAt": "2026-10-13 09:00 ET",            # free text, optional
  "rows": [                                        # every Hyfin file that passed the gate
    {"id": "<file id>", "title": "<file title>",
     "current": "<current My Drive folder name>",
     "dest": "<taxonomy path, e.g. 03-GAIA/Tara-Deliverable or 00-Needs-Review>",
     "reason": "<one line>", "confidence": "high" | "medium" | "low",
     "sensitive": false,                           # true -> dest 00-Needs-Review, reason "sensitive - manual review"
     "suggest": "<taxonomy path>",                 # optional, Needs Review rows only: preselected in Recategorize
     "external": "anyone with the link" | "2 outside accounts" | null,
     "folderShared": false,                        # parent My Drive folder is shared with others
     "duplicate": "<title of the likely duplicate>" | null}
  ],
  "notTouching": [{"id": "<file id>", "title": "<file title>"}],   # no Hyfin signal: title only
  "othersOwned": 0,                                # count of visible files owned by other people
  "notes": ["<access findings or other one-line notes>"]
}

The folder list for Recategorize comes from the tree in references/taxonomy.md, so the
taxonomy has a single source of truth.
"""
import argparse
import json
import re
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
TEMPLATE = SKILL_DIR / "assets" / "approval-report.html"
TAXONOMY = SKILL_DIR / "references" / "taxonomy.md"
NR = "00-Needs-Review"
SENSITIVE_REASON = "sensitive - manual review"
CONF = {"high", "medium", "low"}


def taxonomy_folders():
    """Parse the ``` tree in taxonomy.md into ["00-Needs-Review", "01-Guarantees", "01-Guarantees/BRD", ...]."""
    text = TAXONOMY.read_text(encoding="utf-8")
    block = re.search(r"```\n(.*?)```", text, re.S).group(1)
    paths, stack = [], []
    for line in block.splitlines():
        m = re.search(r"[0-9A-Za-z]", line)
        if not m:
            continue
        depth = m.start() // 4
        name = line[m.start():].strip().rstrip("/")
        stack = stack[:depth] + [name]
        paths.append("/".join(stack))
    return paths


def validate(data, folders):
    errors, warnings = [], []
    rows = data.get("rows", [])
    seen = set()
    if data.get("mode") not in {"full", "weekly", "report-only"}:
        errors.append("mode must be full, weekly or report-only")
    for n, r in enumerate(rows, 1):
        tag = f"row {n} ({r.get('title', '?')!r})"
        for key in ("id", "title", "dest"):
            if not r.get(key):
                errors.append(f"{tag}: missing {key}")
        if r.get("id") in seen:
            errors.append(f"{tag}: duplicate file id")
        seen.add(r.get("id"))
        if r.get("dest") and r["dest"] not in folders:
            errors.append(f"{tag}: dest {r['dest']!r} is not a taxonomy folder")
        if r.get("sensitive"):
            if r.get("dest") != NR:
                errors.append(f"{tag}: sensitive files must go to {NR}")
            if r.get("reason") != SENSITIVE_REASON:
                errors.append(f"{tag}: sensitive reason must be exactly {SENSITIVE_REASON!r}")
            extra = [k for k in ("current", "confidence", "external", "folderShared", "duplicate", "suggest") if r.get(k)]
            if extra:
                warnings.append(f"{tag}: sensitive row carries {extra}; stripped so only title and reason show")
                for k in extra:
                    r.pop(k, None)
        else:
            if r.get("confidence") not in CONF:
                errors.append(f"{tag}: confidence must be high, medium or low")
            if r.get("confidence") == "low" and r.get("dest") != NR:
                errors.append(f"{tag}: low confidence must go to {NR} (reason 'unclear match')")
            if not r.get("reason"):
                errors.append(f"{tag}: missing one-line reason")
        if r.get("suggest") and r.get("dest") != NR:
            errors.append(f"{tag}: 'suggest' is only for {NR} rows")
        if r.get("suggest") and r["suggest"] not in folders:
            errors.append(f"{tag}: suggest {r['suggest']!r} is not a taxonomy folder")
    for n, f in enumerate(data.get("notTouching", []), 1):
        if not f.get("id") or not f.get("title"):
            errors.append(f"notTouching {n}: needs id and title")
        extra = set(f) - {"id", "title"}
        if extra:
            warnings.append(f"notTouching {n}: dropped {sorted(extra)} (Not touching shows filenames only)")
            for k in extra:
                f.pop(k)
        if f.get("id") in seen:
            errors.append(f"notTouching {n}: id also appears as a proposed row")
    return errors, warnings


def plural(n, word):
    return f"{n} {word}" + ("" if n == 1 else "s")


def counts(data):
    rows = data.get("rows", [])
    park = sum(1 for r in rows if r["dest"] == NR)
    return len(rows) - park, park, len(data.get("notTouching", []))


def render_html(data, folders):
    payload = dict(data, folders=folders)
    js = json.dumps(payload, ensure_ascii=False, indent=1).replace("</", "<\\/")
    tpl = TEMPLATE.read_text(encoding="utf-8")
    pat = re.compile(r'(<script type="application/json" id="report-data">)(.*?)(</script>)', re.S)
    if not pat.search(tpl):
        raise SystemExit("template is missing the report-data block")
    return pat.sub(lambda m: m.group(1) + "\n" + js + "\n" + m.group(3), tpl, count=1)


def render_text(data, folders):
    mv, park, left = counts(data)
    mode = {"full": "full sort", "weekly": "weekly sync", "report-only": "report only"}[data["mode"]]
    out = [f"HYFIN DRIVE ORGANIZER: APPROVAL REPORT ({mode}{', ' + data['generatedAt'] if data.get('generatedAt') else ''})",
           f"Proposing {plural(mv, 'move')}, parking {park} for review, leaving {plural(left, 'file')} alone.",
           "Nothing moves until you reply with your decisions.", ""]
    for note in data.get("notes", []):
        out.append(f"Note: {note}")
    if data.get("othersOwned"):
        out.append(f"Note: {data['othersOwned']} file(s) you can see are owned by other people; only their owners can move them.")
    order = {f: i for i, f in enumerate(folders)}
    rows = sorted(enumerate(data.get("rows", []), 1),
                  key=lambda t: (t[1]["dest"] != NR, order.get(t[1]["dest"], 0), t[0]))
    current = None
    for n, r in rows:
        if r["dest"] != current:
            current = r["dest"]
            default = "SKIP" if current == NR else "APPROVE"
            out += ["", f"== {current} (default: {default}) =="]
        if r.get("sensitive"):
            out.append(f"#{n:<3} {r['title']} | {SENSITIVE_REASON} | stays private unless you choose to move it")
            continue
        bits = [f"#{n:<3} {r['title']}", f"from {r.get('current') or 'My Drive'}", r["reason"], f"{r['confidence']} confidence"]
        if r.get("suggest"):
            bits.append(f"suggested: {r['suggest']}")
        if r.get("external"):
            bits.append(f"SHARED EXTERNALLY: {r['external']}")
        if r.get("folderShared"):
            bits.append("PARENT FOLDER SHARED: teammates lose folder-level access")
        if r.get("duplicate"):
            bits.append(f"possible duplicate of {r['duplicate']!r}")
        bits.append(f"id={r['id']}")
        out.append(" | ".join(bits))
    nt = data.get("notTouching", [])
    if nt:
        out += ["", "== Not touching (no Hyfin signal, left where they are) =="]
        out += [f"- {f['title']}" for f in nt]
    out += ["", "Reply with your decisions, for example: \"approve all\", \"skip 4\", \"move 2 to 03-GAIA\",",
            "\"pull in <file name> to 06-Org-Team/Back-Office\". Rows you don't mention keep their default."]
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("report_json")
    ap.add_argument("--html")
    ap.add_argument("--text")
    ap.add_argument("--check", action="store_true", help="validate only")
    a = ap.parse_args()
    data = json.loads(Path(a.report_json).read_text(encoding="utf-8"))
    folders = taxonomy_folders()
    errors, warnings = validate(data, folders)
    for w in warnings:
        print("warning:", w, file=sys.stderr)
    if errors:
        for e in errors:
            print("error:", e, file=sys.stderr)
        sys.exit(1)
    mv, park, left = counts(data)
    print(f"ok: proposing {plural(mv, 'move')}, parking {park} for review, leaving {plural(left, 'file')} alone")
    if a.check:
        return
    if a.html:
        Path(a.html).write_text(render_html(data, folders), encoding="utf-8")
        print(f"wrote {a.html}")
    if a.text:
        Path(a.text).write_text(render_text(data, folders), encoding="utf-8")
        print(f"wrote {a.text}")


if __name__ == "__main__":
    main()
