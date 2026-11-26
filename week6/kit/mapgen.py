#!/usr/bin/env python3
"""Print a map of one service directory: its source files, where each definition starts,
short constants with their values, crash points, and test files.

    python3 kit/mapgen.py app/services/router

The map is made from the tree as it is now, so its line numbers are right for this run.
"""

import os
import re
import sys

SOURCE = (".ts", ".js", ".py", ".go")
SKIP_DIRS = {"internal", "node_modules", "__pycache__", "vendor", ".build", "state"}
DEFINITIONS = {
    ".ts": [
        r"^(?:export\s+)?(?:async\s+)?function\s+(\w+)",
        r"^(?:export\s+)?(?:abstract\s+)?class\s+(\w+)",
        r"^\s{2}(?:async\s+)?(\w+)\([^)]*\)[^;{]*\{\s*$",
    ],
    ".py": [r"^(?:async\s+)?def\s+(\w+)", r"^class\s+(\w+)", r"^\s{4}(?:async\s+)?def\s+(\w+)"],
    ".go": [r"^func\s+(?:\([^)]*\)\s*)?(\w+)", r"^type\s+(\w+)"],
}
DEFINITIONS[".js"] = DEFINITIONS[".ts"]
CONSTANTS = {
    ".ts": r"^(?:export\s+)?const\s+([A-Z][A-Z0-9_]+)\s*(?::[^=]+)?=\s*(.+?);?\s*$",
    ".js": r"^(?:export\s+)?const\s+([A-Z][A-Z0-9_]+)\s*=\s*(.+?);?\s*$",
    ".py": r"^([A-Z][A-Z0-9_]+)\s*=\s*(.+?)\s*(?:#.*)?$",
    ".go": r"^(?:const|var)\s+(\w+)\s*(?:\w+\s*)?=\s*(.+?)\s*(?://.*)?$",
}
CRASH = re.compile(r"\bcrash\((\d+)\)")
KEYWORDS = {"if", "for", "while", "switch", "catch", "function", "return", "constructor"}


def is_test(relative):
    parts = relative.replace("\\", "/").split("/")
    name = parts[-1]
    return "test" in parts[:-1] or "tests" in parts[:-1] or name.endswith("_test.go") or ".test." in name or name.startswith("test_")


def walk(root):
    for folder, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not d.startswith("."))
        for name in sorted(files):
            if name.endswith(SOURCE):
                yield os.path.relpath(os.path.join(folder, name), root)


def describe(root, relative):
    ext = os.path.splitext(relative)[1]
    names, crashes, count = [], [], 0
    try:
        with open(os.path.join(root, relative), encoding="utf-8", errors="replace") as handle:
            for number, line in enumerate(handle, 1):
                count = number
                for point in CRASH.findall(line):
                    if not re.search(r"(def|func|function)\s", line):
                        crashes.append(f"{number}({point})")
                constant = re.match(CONSTANTS[ext], line)
                if constant and len(constant.group(2)) <= 44:
                    names.append(f"{constant.group(1)}={constant.group(2)}@{number}")
                    continue
                for pattern in DEFINITIONS[ext]:
                    found = re.match(pattern, line)
                    if found and found.group(1) not in KEYWORDS:
                        names.append(f"{found.group(1)}@{number}")
                        break
    except OSError:
        return None
    return count, names, crashes


def main(argv):
    if len(argv) != 2 or not os.path.isdir(argv[1]):
        print(__doc__)
        return 2
    root = argv[1]
    tests, crash_lines = [], []
    print("Source files (`name@line`; made from the tree at the start of this run):")
    for relative in walk(root):
        if is_test(relative):
            tests.append(relative)
            continue
        found = describe(root, relative)
        if not found:
            continue
        count, names, crashes = found
        print(f"- `{relative}` ({count} lines): " + " ".join(names))
        if crashes:
            crash_lines.append(f"`{relative}` " + " ".join(crashes))
    if crash_lines:
        print("Crash points, as `line(number)`: " + "; ".join(crash_lines))
    if tests:
        print("Tests: " + ", ".join(f"`{t}`" for t in tests))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
