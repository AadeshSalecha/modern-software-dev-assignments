#!/usr/bin/env python3
"""Load an evidence packet into SQLite, following app/contracts/evidence.md.

    python3 kit/evidence.py build  [incident_dir] [db]   load the packet, print a summary
    python3 kit/evidence.py schema [db]                  tables, columns, record kinds
    python3 kit/evidence.py skipped [db]                 corrupted rows per file and in total
    python3 kit/evidence.py sql "<select ...>" [--limit N] [--db db]

What the loader does, and nothing more:

* A row cut short is corrupted. It is counted every time it appears and never parsed
  (invalid JSON; a log line that ends in a field with no value or in a bare token;
  an export row with fewer columns than the header).
* Identical lines in the shipped logs are one record (the shipper resends batches).
  `copies` says how often the line appeared.
* Every file becomes one table whose columns are the keys actually seen.
* `events`, `deliveries` and `responses` join what every file says about an id,
  because no single file is complete.

It knows nothing about any particular incident.
"""

import bisect
import csv
import gzip
import json
import os
import re
import sqlite3
import statistics
import sys
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DB = os.path.join(ROOT, "work", "evidence.db")
DEFAULT_INCIDENT = os.path.join(ROOT, "incident")

# contracts/messages/README.md, "Currencies". Re-read from that file when it is there.
MINOR_DIGITS = {"USD": 2, "EUR": 2, "GBP": 2, "JPY": 0, "KWD": 3}

# One fact, the names it goes by in the different files.
ALIASES = {
    "event_id": ("event_id", "event"),
    "delivery_id": ("delivery_id", "delivery", "webhook_id"),
    "endpoint_id": ("endpoint_id", "endpoint"),
    "attempt_id": ("attempt_id", "attempt"),
    "merchant_id": ("merchant_id", "merchant"),
    "status": ("status", "http_status"),
    "lease_id": ("lease_id", "lease"),
}
KIND_COLUMNS = ("msg", "op", "kind")
RESERVED_TABLES = {"events", "deliveries", "responses", "skipped", "event_facts", "delivery_facts", "snapshots",
                   "attempts", "leases"}
ISO = re.compile(r"^(\d{4})-(\d\d)-(\d\d)T(\d\d):(\d\d):(\d\d)Z$")
KEY = re.compile(r"^([A-Za-z_][\w.\-]*)=(.*)$", re.S)
INT = re.compile(r"^-?\d+$")
RESERVED = {"line_no", "copies", "ts", "ts_iso", "file"}


def column(name):
    name = re.sub(r"\W", "_", str(name)).strip("_").lower() or "field"
    return name + "_" if name in RESERVED or name[0].isdigit() else name


def iso_to_epoch(text):
    m = ISO.match(text) if isinstance(text, str) else None
    if not m:
        return None
    try:
        return int(datetime(*map(int, m.groups()), tzinfo=timezone.utc).timestamp())
    except ValueError:
        return None


def epoch_to_iso(seconds):
    try:
        return datetime.fromtimestamp(int(seconds), tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except (ValueError, OverflowError, OSError, TypeError):
        return None


def open_text(path):
    if path.endswith(".gz"):
        return gzip.open(path, "rt", encoding="utf-8", errors="replace", newline="")
    return open(path, encoding="utf-8", errors="replace", newline="")


def physical_lines(path):
    """Lines of a file without their line ending. Blank lines are not rows."""
    with open_text(path) as handle:
        try:
            for number, line in enumerate(handle, 1):
                line = line.rstrip("\r\n")
                if line.strip():
                    yield number, line
        except (OSError, EOFError):
            return


# --- parsers: each returns a dict of fields, or None when the row is corrupted --------


def parse_json_line(line):
    try:
        value = json.loads(line)
    except ValueError:
        return None
    if not isinstance(value, dict):
        return None
    ts = iso_to_epoch(value.get("ts"))
    clock_key = "ts" if ts is not None else None
    if ts is None and isinstance(value.get("t"), (int, float)) and not isinstance(value.get("t"), bool):
        ts, clock_key = int(value["t"]), "t"
    row = {}
    for key, item in value.items():
        if key == clock_key:
            continue
        if isinstance(item, bool):
            item = int(item)
        elif isinstance(item, (dict, list)):
            item = json.dumps(item, sort_keys=True)
        row[column(key)] = item
    row["ts"] = ts
    row["ts_iso"] = value["ts"] if clock_key == "ts" else epoch_to_iso(ts)
    return row


def tokens(line):
    """Split on spaces outside double quotes. Returns None if a quote is left open."""
    out, current, quoted = [], [], False
    for ch in line:
        if ch == '"':
            quoted = not quoted
            current.append(ch)
        elif ch == " " and not quoted:
            if current:
                out.append("".join(current))
                current = []
        else:
            current.append(ch)
    if quoted:
        return None
    if current:
        out.append("".join(current))
    return out


def typed(text):
    if len(text) >= 2 and text[0] == '"' and text[-1] == '"':
        return text[1:-1]
    if INT.match(text):
        return int(text)
    return text


def parse_log_line(line):
    """`<timestamp> [bare tokens] key=value ...`. A complete line ends in a field with a value."""
    parts = tokens(line)
    if not parts:
        return None
    last = KEY.match(parts[-1])
    if not last or last.group(2) in ("", '"'):
        return None
    row, bare = {}, []
    ts = iso_to_epoch(parts[0])
    for part in parts[1:] if ts is not None else parts:
        m = KEY.match(part)
        if m:
            row[column(m.group(1))] = typed(m.group(2))
        else:
            bare.append(part)
    row["ts"], row["ts_iso"] = ts, (parts[0] if ts is not None else None)
    # A request line: <writer> <METHOD> <address> <status>
    if len(bare) == 4 and bare[1].isupper() and "://" in bare[2]:
        row.setdefault("writer", bare[0])
        row.setdefault("method", bare[1])
        row.setdefault("url", bare[2])
        row.setdefault("status", typed(bare[3]))
        tail = bare[2].rstrip("/").rsplit("/", 1)[-1].split("?")[0]
        if re.match(r"^ep_\w+$", tail):
            row.setdefault("url_endpoint", tail)
    else:
        for number, value in enumerate(bare, 1):
            row[f"p{number}"] = typed(value)
    return row


def parse_csv_line(line):
    try:
        return next(csv.reader([line]))
    except (csv.Error, StopIteration):
        return None


# --- loading --------------------------------------------------------------------------


class Source:
    """One table: the file, or the files, that share a name (router.log, router.log.1)."""

    def __init__(self, name, kind):
        self.name, self.kind = name, kind
        self.paths = []  # (path, name relative to the packet)
        self.rows = []  # dicts, each with line_no and copies
        self.corrupted = {}  # relative name -> rows cut short
        self.duplicates = 0
        self.notes = []


def table_name(filename):
    return column(filename.split(".")[0])


def classify(filename):
    base = filename[:-3] if filename.endswith(".gz") else filename
    base = re.sub(r"\.\d+$", "", base)  # a rotated file: router.log.1
    if base.endswith((".ndjson", ".jsonl")):
        return "json"
    if base.endswith(".log"):
        return "log"
    if base.endswith(".csv"):
        return "csv"
    return None


def discover(incident_dir):
    sources, snapshots, other = {}, [], []
    for folder, dirs, files in os.walk(incident_dir):
        dirs.sort()
        inside = os.path.relpath(folder, incident_dir)
        for entry in sorted(files):
            path = os.path.join(folder, entry)
            relative = entry if inside == "." else os.path.join(inside, entry)
            if inside.split(os.sep)[0] == "snapshots" and entry.endswith(".json"):
                snapshots.append(path)
                continue
            kind = classify(entry)
            if kind is None:
                other.append(relative)
                continue
            name = ("" if inside == "." else column(inside) + "_") + table_name(entry)
            if name in RESERVED_TABLES or name.startswith(("snapshot_", "_")):
                name += "_file"
            if name in sources and sources[name].kind != kind:
                name = f"{name}_{kind}"
            sources.setdefault(name, Source(name, kind)).paths.append((path, relative))
    return list(sources.values()), snapshots, other


def load_lines(source):
    parse = parse_json_line if source.kind == "json" else parse_log_line
    seen = {}
    for path, relative in source.paths:
        source.corrupted.setdefault(relative, 0)
        for number, line in physical_lines(path):
            row = parse(line)
            if row is None:
                source.corrupted[relative] += 1
                continue
            if line in seen:
                seen[line]["copies"] += 1
                source.duplicates += 1
                continue
            row["line_no"], row["copies"] = number, 1
            if len(source.paths) > 1:
                row["file"] = relative
            seen[line] = row
            source.rows.append(row)


def load_csv(source):
    counts = {}
    for path, relative in source.paths:
        header = None
        source.corrupted.setdefault(relative, 0)
        for number, line in physical_lines(path):
            cells = parse_csv_line(line)
            if header is None:
                header = [column(c) for c in (cells or [])]
                continue
            if cells is None or len(cells) < len(header):
                source.corrupted[relative] += 1
                continue
            row = {name: (value if value != "" else None) for name, value in zip(header, cells)}
            row["line_no"] = number
            if len(source.paths) > 1:
                row["file"] = relative
            counts.setdefault(line, []).append(row)
            source.rows.append(row)
    for same in counts.values():
        for row in same:
            row["copies"] = len(same)
    repeated = sum(len(same) - 1 for same in counts.values() if len(same) > 1)
    if repeated:
        source.notes.append(
            f"{repeated} rows repeat an earlier row exactly; all are kept (see `copies`), "
            "because the export is one row per request"
        )


def minor_digits(incident_dir):
    digits = dict(MINOR_DIGITS)
    readme = os.path.join(os.path.dirname(os.path.abspath(incident_dir)), "app", "contracts", "messages", "README.md")
    try:
        with open(readme, encoding="utf-8") as handle:
            for line in handle:
                cells = [c.strip() for c in line.strip().strip("|").split("|")]
                if len(cells) >= 2 and INT.match(cells[1]):
                    for code in re.findall(r"`([A-Z]{3})`", cells[0]):
                        digits[code] = int(cells[1])
    except OSError:
        pass
    return digits


def to_minor(amount, currency, digits):
    """A major-unit amount as written by the merchant's tools, in minor units. None if not exact."""
    if amount is None or currency not in digits:
        return None
    try:
        value = Decimal(str(amount).replace(",", "").strip())
    except InvalidOperation:
        return None
    scaled = value * (Decimal(10) ** digits[currency])
    return int(scaled) if scaled == scaled.to_integral_value() else None


def local_minutes(text):
    for pattern in ("%m/%d/%Y %H:%M", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M", "%d/%m/%Y %H:%M"):
        try:
            return datetime.strptime(text.strip(), pattern).replace(tzinfo=timezone.utc)
        except (ValueError, AttributeError):
            continue
    return None


def first_present(row, names):
    for name in names:
        if row.get(name) is not None:
            return row[name]
    return None


def finish_export(source, known_deliveries, request_times, digits):
    """Resolve cut ids, convert amounts, and estimate the export's clock offset."""
    unresolved = cut = inexact = 0
    deltas = []
    ordered = sorted(known_deliveries)
    for row in source.rows:
        raw = first_present(row, ("webhook_id", "delivery_id", "delivery"))
        resolved = None
        if raw in known_deliveries:
            resolved = raw
        elif raw:
            at = bisect.bisect_left(ordered, raw)
            matches = [d for d in ordered[at : at + 2] if d.startswith(raw)]
            if len(matches) == 1:
                resolved, cut = matches[0], cut + 1
            else:
                unresolved += 1
        row["delivery_id"] = resolved
        if "amount" in row and "currency" in row:
            row["amount_minor"] = to_minor(row.get("amount"), row.get("currency"), digits)
            inexact += row["amount_minor"] is None and row.get("amount") is not None
        status = first_present(row, ("http_status", "status"))
        row["status"] = int(status) if status is not None and INT.match(str(status)) else None
        stamp = local_minutes(row["received_at"]) if row.get("received_at") else None
        row["received_local"] = stamp.strftime("%Y-%m-%dT%H:%M") if stamp else None
        if stamp and resolved in request_times:
            naive = int(stamp.timestamp())
            deltas.append(min((t - naive for t in request_times[resolved]), key=abs))
    offset = None
    if len(deltas) >= 5:
        offset = int(round(statistics.median(deltas) / 900.0)) * 900
        for row in source.rows:
            stamp = local_minutes(row["received_at"]) if row.get("received_at") else None
            row["ts"] = int(stamp.timestamp()) + offset if stamp else None
            row["ts_iso"] = epoch_to_iso(row["ts"]) if row["ts"] is not None else None
        hours = -offset / 3600.0
        source.notes.append(
            f"`received_at` is local time, about UTC{hours:+g}h (estimated from {len(deltas)} requests also seen "
            "elsewhere); `ts` is that estimate, to the minute"
        )
    else:
        for row in source.rows:
            row["ts"] = row["ts_iso"] = None
        source.notes.append("`received_at` is local time with an unknown offset; `ts` is empty")
    if cut:
        source.notes.append(f"{cut} cut ids resolved to the one delivery they start (`delivery_id`)")
    if unresolved:
        source.notes.append(f"{unresolved} rows have an id that matches no known delivery, or several")
    if inexact:
        source.notes.append(f"{inexact} amounts could not be converted exactly (`amount_minor` empty)")


def load_snapshots(paths):
    """Each list of objects in a snapshot becomes rows of snapshot_<key>."""
    tables, notes = {}, []
    for path in paths:
        name = os.path.basename(path)
        try:
            with open(path, encoding="utf-8", errors="replace") as handle:
                data = json.load(handle)
        except (OSError, ValueError):
            notes.append(f"snapshots/{name} is not readable JSON; not loaded and not counted as a row")
            continue
        if not isinstance(data, dict):
            continue
        scalars = {column(k): v for k, v in data.items() if not isinstance(v, (list, dict))}
        scalars["snapshot"] = name
        tables.setdefault("snapshots", []).append(scalars)
        for key, items in data.items():
            if isinstance(items, list) and items and all(isinstance(i, dict) for i in items):
                for item in items:
                    row = {"snapshot": name, "snapshot_now": data.get("now")}
                    for k, v in item.items():
                        row[column(k)] = json.dumps(v, sort_keys=True) if isinstance(v, (dict, list)) else v
                    tables.setdefault("snapshot_" + column(key), []).append(row)
    return tables, notes


def incomplete_rows(source):
    """Log lines that pass the corruption rule but lack a field nearly every line of their kind has."""
    kind_col = next((k for k in KIND_COLUMNS if any(k in r for r in source.rows[:50])), None)
    groups = {}
    for row in source.rows:
        groups.setdefault(row.get(kind_col) if kind_col else None, []).append(row)
    found = []
    for rows in groups.values():
        if len(rows) < 20:
            continue
        counts = {}
        for row in rows:
            for key in row:
                counts[key] = counts.get(key, 0) + 1
        usual = {k for k, n in counts.items() if n >= 0.99 * len(rows)}
        found += [r["line_no"] for r in rows if not usual <= set(r)]
    return sorted(found)


# --- database -------------------------------------------------------------------------


def create_table(db, name, rows, lead=("line_no", "copies", "ts", "ts_iso")):
    columns = [c for c in lead if any(c in r for r in rows)]
    for row in rows:
        for key in row:
            if key not in columns:
                columns.append(key)
    if not columns:
        return []
    quoted = ", ".join(f'"{c}"' for c in columns)
    db.execute(f'DROP TABLE IF EXISTS "{name}"')
    db.execute(f'CREATE TABLE "{name}" ({quoted})')
    db.executemany(
        f'INSERT INTO "{name}" VALUES ({", ".join("?" for _ in columns)})',
        ([row.get(c) for c in columns] for row in rows),
    )
    for fact, names in ALIASES.items():
        if fact == "status":
            continue
        for candidate in names:
            if candidate in columns:
                db.execute(f'CREATE INDEX "{name}_{candidate}" ON "{name}" ("{candidate}")')
    return columns


def pick(columns, fact):
    for candidate in ALIASES[fact]:
        if candidate in columns:
            return f'"{candidate}"'
    return "NULL"


def any_of(columns, names):
    for candidate in names:
        if candidate in columns:
            return f'"{candidate}"'
    return "NULL"


def build_views(db, tables):
    """tables: {name: columns}. Facts are collected from every table that carries them."""
    event_parts, delivery_parts, response_parts = [], [], []
    for name, columns in tables.items():
        ts = '"ts"' if "ts" in columns else ('"snapshot_now"' if "snapshot_now" in columns else "NULL")
        line = '"line_no"' if "line_no" in columns else "NULL"
        event, endpoint = pick(columns, "event_id"), pick(columns, "endpoint_id")
        delivery = pick(columns, "delivery_id")
        if name == "snapshot_deliveries" and "id" in columns:
            delivery = '"id"'
        if event != "NULL":
            event_parts.append(
                f"SELECT '{name}' AS source, {event} AS event_id, {pick(columns, 'merchant_id')} AS merchant_id, "
                f"{any_of(columns, ('type',))} AS type, {any_of(columns, ('amount_minor',))} AS amount_minor, "
                f"{any_of(columns, ('currency',))} AS currency, {ts} AS ts, {line} AS line_no "
                f'FROM "{name}" WHERE {event} IS NOT NULL'
            )
        if delivery != "NULL":
            delivery_parts.append(
                f"SELECT '{name}' AS source, {delivery} AS delivery_id, {event} AS event_id, "
                f"{endpoint} AS endpoint_id, {any_of(columns, ('url_endpoint',))} AS url_endpoint, "
                f"{any_of(columns, ('resend_of',))} AS resend_of, {ts} AS ts, "
                f'{line} AS line_no FROM "{name}" WHERE {delivery} IS NOT NULL'
            )
            status = pick(columns, "status")
            if name == "merchant_export" and "status" in columns:
                status = '"status"'
            if status != "NULL":
                response_parts.append(
                    f"SELECT '{name}' AS source, {delivery} AS delivery_id, {pick(columns, 'attempt_id')} AS attempt_id, "
                    f"{status} AS status, {ts} AS ts, {line} AS line_no "
                    f'FROM "{name}" WHERE {delivery} IS NOT NULL AND {status} IS NOT NULL'
                )
    for view in ("event_facts", "delivery_facts", "responses"):
        db.execute(f"DROP VIEW IF EXISTS {view}")
    for table in ("events", "deliveries"):
        db.execute(f"DROP TABLE IF EXISTS {table}")
    made = []
    if event_parts:
        db.execute("CREATE VIEW event_facts AS " + " UNION ALL ".join(event_parts))
        db.execute(
            """CREATE TABLE events AS SELECT event_id,
                 max(merchant_id) AS merchant_id, max(type) AS type,
                 max(amount_minor) AS amount_minor, max(currency) AS currency,
                 group_concat(DISTINCT source) AS sources,
                 (count(DISTINCT merchant_id) > 1 OR count(DISTINCT type) > 1
                  OR count(DISTINCT amount_minor) > 1 OR count(DISTINCT currency) > 1) AS conflict
               FROM event_facts GROUP BY event_id"""
        )
        db.execute("CREATE UNIQUE INDEX events_id ON events (event_id)")
        made += ["event_facts", "events"]
    if delivery_parts:
        db.execute("CREATE VIEW delivery_facts AS " + " UNION ALL ".join(delivery_parts))
        db.execute(
            """CREATE TABLE deliveries AS SELECT delivery_id,
                 max(event_id) AS event_id, max(endpoint_id) AS endpoint_id,
                 max(url_endpoint) AS url_endpoint, max(resend_of) AS resend_of,
                 group_concat(DISTINCT source) AS sources,
                 (count(DISTINCT event_id) > 1 OR count(DISTINCT endpoint_id) > 1) AS conflict
               FROM delivery_facts GROUP BY delivery_id"""
        )
        db.execute("CREATE UNIQUE INDEX deliveries_id ON deliveries (delivery_id)")
        db.execute("CREATE INDEX deliveries_event ON deliveries (event_id)")
        made += ["delivery_facts", "deliveries"]
    if response_parts:
        db.execute("CREATE VIEW responses AS " + " UNION ALL ".join(response_parts))
        made.append("responses")
    return made


def joined_by(sources, fact, extras):
    """One record per value of `fact` (per attempt, per lease), with what each file says about it.

    For every file that names the id: how many records, the first and last time on that file's
    clock, and the HTTP statuses it gives. `extras` are single-valued fields taken from whichever
    record carries them. An id used for more than one delivery gets one row per delivery.
    """
    found, names = {}, []
    for source in sources:
        used = False
        for row in source.rows:
            ident = first_present(row, ALIASES[fact])
            if not isinstance(ident, str):
                continue
            used = True
            delivery = first_present(row, ALIASES["delivery_id"])
            entry = found.setdefault(ident, {"deliveries": {}, "files": {}, "extras": {}})
            if isinstance(delivery, str):
                entry["deliveries"][delivery] = entry["deliveries"].get(delivery, 0) + 1
            per = entry["files"].setdefault(source.name, {"n": 0, "first": None, "last": None, "status": []})
            per["n"] += 1
            ts = row.get("ts")
            if ts is not None:
                per["first"] = ts if per["first"] is None else min(per["first"], ts)
                per["last"] = ts if per["last"] is None else max(per["last"], ts)
            status = first_present(row, ALIASES["status"])
            if status is not None and status not in per["status"]:
                per["status"].append(status)
            for extra in extras:
                value = first_present(row, ALIASES.get(extra, (extra,)))
                if value is not None:
                    entry["extras"].setdefault(extra, value)
        if used:
            names.append(source.name)
    rows = []
    for ident, entry in found.items():
        deliveries = sorted(entry["deliveries"], key=lambda d: -entry["deliveries"][d]) or [None]
        row = {fact: ident, "delivery_id": deliveries[0], "n_deliveries": len(entry["deliveries"])}
        for extra in extras:
            row[extra] = entry["extras"].get(extra)
        statuses = set()
        for name in names:
            per = entry["files"].get(name)
            row[f"{name}_n"] = per["n"] if per else 0
            row[f"{name}_ts"] = per["first"] if per else None
            row[f"{name}_ts_last"] = per["last"] if per else None
            if per and per["status"]:
                row[f"{name}_status"] = per["status"][0] if len(per["status"]) == 1 else "/".join(map(str, per["status"]))
                statuses.update(per["status"])
            else:
                row[f"{name}_status"] = None
        row["sources"] = ",".join(name for name in names if name in entry["files"])
        row["status_conflict"] = int(len(statuses) > 1)
        rows.append(row)
    return rows


def clock_gaps(sources):
    """How far apart two files' clocks put the first record of the same id (b minus a, seconds).
    For each pair of files the kind of id with the tightest spread is kept."""
    first = {}  # file -> kind -> id -> first ts
    for source in sources:
        for row in source.rows:
            ts = row.get("ts")
            if ts is None:
                continue
            for kind in ("attempt_id", "lease_id", "delivery_id", "event_id"):
                ident = first_present(row, ALIASES[kind])
                if isinstance(ident, str):
                    seen = first.setdefault(source.name, {}).setdefault(kind, {})
                    if ident not in seen or ts < seen[ident]:
                        seen[ident] = ts
    out, names = [], sorted(first)
    for i, a in enumerate(names):
        for b in names[i + 1 :]:
            best = None
            for kind in ("attempt_id", "lease_id", "delivery_id", "event_id"):
                ids_a, ids_b = first[a].get(kind, {}), first[b].get(kind, {})
                gaps = sorted(ids_b[k] - ids_a[k] for k in ids_a.keys() & ids_b.keys())
                if len(gaps) < 20:
                    continue
                low, mid, high = gaps[len(gaps) // 10], gaps[len(gaps) // 2], gaps[(len(gaps) * 9) // 10]
                if best is None or (high - low) < (best[5] - best[3]):
                    best = (a, b, kind.replace("_id", ""), len(gaps), mid, low, high)
            if best:
                out.append({"file_a": best[0], "file_b": best[1], "via": best[2], "n": best[3],
                            "median_s": best[4], "p10_s": best[5], "p90_s": best[6]})
    return out


def build(incident_dir, db_path):
    if not os.path.isdir(incident_dir):
        raise SystemExit(f"no evidence directory at {incident_dir}")
    sources, snapshot_paths, other = discover(incident_dir)
    digits = minor_digits(incident_dir)
    for source in sources:
        if source.kind == "csv":
            load_csv(source)
        else:
            load_lines(source)

    known, request_times = set(), {}
    for source in sources:
        if source.kind == "csv":
            continue
        for row in source.rows:
            delivery = first_present(row, ALIASES["delivery_id"])
            if isinstance(delivery, str):
                known.add(delivery)
                if row.get("ts") is not None and row.get("url") is not None:
                    request_times.setdefault(delivery, []).append(row["ts"])
    snapshot_tables, snapshot_notes = load_snapshots(snapshot_paths)
    for row in snapshot_tables.get("snapshot_deliveries", []):
        if isinstance(row.get("id"), str):
            known.add(row["id"])
    for source in sources:
        if source.kind == "csv":
            finish_export(source, known, request_times, digits)
        elif source.kind == "log":
            lines = incomplete_rows(source)
            if lines:
                source.notes.append(
                    f"{len(lines)} lines lack a field their kind nearly always has (not counted as corrupted); "
                    f"first at line {', '.join(map(str, lines[:5]))}"
                )

    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    if os.path.exists(db_path):
        os.remove(db_path)
    db = sqlite3.connect(db_path)
    tables = {}
    for source in sources:
        columns = create_table(db, source.name, source.rows)
        if columns:
            tables[source.name] = columns
    for name, rows in snapshot_tables.items():
        tables[name] = create_table(db, name, rows, lead=("snapshot", "snapshot_now"))

    db.execute("CREATE TABLE skipped (file TEXT, corrupted_rows INTEGER)")
    db.executemany(
        "INSERT INTO skipped VALUES (?, ?)",
        [(relative, count) for s in sources for relative, count in s.corrupted.items()],
    )
    db.execute("CREATE TABLE _kinds (source TEXT, kind_column TEXT, kind TEXT, n INTEGER, fields TEXT)")
    for source in sources:
        kind_col = next((k for k in KIND_COLUMNS if k in tables.get(source.name, [])), None)
        groups = {}
        for row in source.rows:
            fields = groups.setdefault(row.get(kind_col) if kind_col else None, {"n": 0, "fields": {}})
            fields["n"] += 1
            for key, value in row.items():
                if value is not None and key not in RESERVED and key != kind_col:
                    fields["fields"][key] = fields["fields"].get(key, 0) + 1
        for kind, info in groups.items():
            names = [k if n == info["n"] else f"{k}?" for k, n in info["fields"].items()]
            db.execute(
                "INSERT INTO _kinds VALUES (?, ?, ?, ?, ?)",
                (source.name, kind_col, None if kind is None else str(kind), info["n"], " ".join(names)),
            )
    db.execute("CREATE TABLE _notes (source TEXT, note TEXT)")
    for source in sources:
        if source.duplicates:
            db.execute(
                "INSERT INTO _notes VALUES (?, ?)",
                (source.name, f"{source.duplicates} repeated lines collapsed (shipper resends); see `copies`"),
            )
        for note in source.notes:
            db.execute("INSERT INTO _notes VALUES (?, ?)", (source.name, note))
    for note in snapshot_notes:
        db.execute("INSERT INTO _notes VALUES (?, ?)", ("snapshots", note))
    for entry in other:
        db.execute("INSERT INTO _notes VALUES (?, ?)", ("packet", f"{entry} was not loaded (unknown kind of file)"))
    build_views(db, tables)
    attempts = joined_by(sources, "attempt_id", ("lease_id", "attempt_no", "endpoint_id", "outcome"))
    if attempts:
        create_table(db, "attempts", attempts, lead=("attempt_id", "delivery_id"))
    leases = joined_by(sources, "lease_id", ("worker", "attempt_no", "expires", "outcome", "returned"))
    if leases:
        create_table(db, "leases", leases, lead=("lease_id", "delivery_id"))
    db.execute("CREATE TABLE _clock_gaps (file_a TEXT, file_b TEXT, via TEXT, n INTEGER, median_s INTEGER, p10_s INTEGER, p90_s INTEGER)")
    db.executemany(
        "INSERT INTO _clock_gaps VALUES (:file_a, :file_b, :via, :n, :median_s, :p10_s, :p90_s)", clock_gaps(sources)
    )
    db.commit()
    db.close()
    return db_path


# --- reading --------------------------------------------------------------------------


def connect(db_path):
    if not os.path.exists(db_path):
        raise SystemExit(f"no database at {db_path}; run: python3 kit/evidence.py build")
    return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)


def has(db, name):
    return db.execute("SELECT 1 FROM sqlite_master WHERE name = ?", (name,)).fetchone() is not None


def print_skipped(db):
    rows = db.execute("SELECT file, corrupted_rows FROM skipped ORDER BY file").fetchall()
    for name, count in rows:
        print(f"  {name:<24} {count}")
    print(f"  {'total':<24} {sum(count for _, count in rows)}")


def coverage(db, table, facts, id_column):
    if not has(db, table):
        return None
    total = db.execute(f"SELECT count(*), sum(conflict) FROM {table}").fetchone()
    per = db.execute(
        f"SELECT source, count(DISTINCT {id_column}) FROM {facts} GROUP BY source ORDER BY 2 DESC"
    ).fetchall()
    return total, per


def print_schema(db):
    print("corrupted rows (skipped, counted each time they appear):")
    print_skipped(db)
    print()
    print("tables (one per file; `ts` is epoch seconds on that file's own clock, `ts_iso` the same as text)")
    names = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY rowid")]
    for name in names:
        if name.startswith("_") or name in ("skipped", "events", "deliveries", "attempts", "leases"):
            continue
        count = db.execute(f'SELECT count(*) FROM "{name}"').fetchone()[0]
        kinds = db.execute(
            "SELECT kind_column, kind, n, fields FROM _kinds WHERE source = ? ORDER BY n DESC", (name,)
        ).fetchall()
        print(f"{name}  ({count} rows)")
        if not kinds:
            columns = [r[1] for r in db.execute(f'PRAGMA table_info("{name}")')]
            print("    " + " ".join(columns))
        for kind_col, kind, n, fields in kinds:
            label = f"{kind_col}={kind}" if kind_col else "(all rows)"
            print(f"    {label:<28} {n:>6}  {fields}")
        for (note,) in db.execute("SELECT note FROM _notes WHERE source = ?", (name,)):
            print(f"    note: {note}")
    for (source, note) in db.execute("SELECT source, note FROM _notes WHERE source IN ('snapshots', 'packet')"):
        print(f"note: {note}")
    print()
    print("joined across files (a `?` after a field above means only some rows have it)")
    for table, facts, id_column, columns in (
        ("events", "event_facts", "event_id", "event_id merchant_id type amount_minor currency sources conflict"),
        ("deliveries", "delivery_facts", "delivery_id", "delivery_id event_id endpoint_id url_endpoint resend_of sources conflict"),
    ):
        found = coverage(db, table, facts, id_column)
        if not found:
            continue
        (total, conflicts), per = found
        seen = ", ".join(f"{source} {n}" for source, n in per)
        print(f"{table}  ({total} ids; {conflicts or 0} with conflicting facts)  columns: {columns}")
        print(f"    ids seen per file: {seen}")
        if table == "deliveries":
            other = db.execute(
                "SELECT count(*) FROM deliveries WHERE url_endpoint IS NOT NULL AND endpoint_id IS NOT NULL "
                "AND url_endpoint <> endpoint_id"
            ).fetchone()[0]
            print(
                "    `endpoint_id` comes from records that name the endpoint; `url_endpoint` is the last part of the "
                f"address a request went to, when it looks like an endpoint id ({other} deliveries where the two differ)"
            )
    if has(db, "responses"):
        per = db.execute("SELECT source, count(*) FROM responses GROUP BY source ORDER BY 2 DESC").fetchall()
        print("responses  (view: every row that carries a delivery and an HTTP status)")
        print("    columns: source delivery_id attempt_id status ts line_no")
        print("    rows per file: " + ", ".join(f"{source} {n}" for source, n in per))
    print("event_facts, delivery_facts  (views: the per-file rows behind `events` and `deliveries`)")
    for table, ident in (("attempts", "attempt_id"), ("leases", "lease_id")):
        if not has(db, table):
            continue
        columns = [r[1] for r in db.execute(f"PRAGMA table_info({table})")]
        total, shared, conflicts = db.execute(
            f"SELECT count(*), sum(n_deliveries > 1), sum(status_conflict) FROM {table}"
        ).fetchone()
        print(f"{table}  ({total} ids; {shared or 0} used for more than one delivery; {conflicts or 0} where files give "
              "different statuses)")
        print("    one row per id with, for each file that names it: <file>_n records, <file>_ts first and "
              "<file>_ts_last last time on that file's clock, <file>_status")
        print("    columns: " + " ".join(columns))
    gaps = db.execute("SELECT file_a, file_b, via, n, median_s, p10_s, p90_s FROM _clock_gaps").fetchall() if has(db, "_clock_gaps") else []
    if gaps:
        print("clock gaps (first record of the same id, second file minus first; clocks are not synchronised):")
        for a, b, via, n, mid, low, high in gaps:
            plural = {"delivery": "deliveries"}.get(via, via + "s")
            print(f"    {b} - {a}: {mid:+d} s  (80% between {low:+d} and {high:+d}; {n} {plural})")
        print("    compare times inside one file where you can; across files only with these gaps in mind")


def run_sql(db, query, limit):
    try:
        cursor = db.execute(query)
    except sqlite3.Error as problem:
        raise SystemExit(f"sql error: {problem}")
    if cursor.description is None:
        return
    print("\t".join(d[0] for d in cursor.description))
    shown = 0
    for row in cursor:
        if shown >= limit:
            more = 1 + sum(1 for _ in cursor)
            print(f"... {more} more rows (raise --limit, or aggregate)")
            break
        print("\t".join("" if v is None else str(v) for v in row))
        shown += 1


def main(argv):
    if len(argv) < 2 or argv[1] in ("-h", "--help"):
        print(__doc__)
        return 0
    command, rest = argv[1], argv[2:]
    if command == "build":
        incident = rest[0] if rest else DEFAULT_INCIDENT
        db_path = rest[1] if len(rest) > 1 else DEFAULT_DB
        build(incident, db_path)
        db = connect(db_path)
        print(f"evidence database: {os.path.relpath(db_path)}")
        print_schema(db)
        return 0
    limit, db_path, positional = 40, DEFAULT_DB, []
    index = 0
    while index < len(rest):
        if rest[index] == "--limit":
            limit, index = int(rest[index + 1]), index + 2
        elif rest[index] == "--db":
            db_path, index = rest[index + 1], index + 2
        else:
            positional.append(rest[index])
            index += 1
    if command == "sql":
        if not positional:
            raise SystemExit('usage: evidence.py sql "<select ...>" [--limit N] [--db db]')
        run_sql(connect(db_path), positional[0], limit)
    elif command == "schema":
        print_schema(connect(positional[0] if positional else db_path))
    elif command == "skipped":
        print_skipped(connect(positional[0] if positional else db_path))
    else:
        raise SystemExit(f"unknown command {command}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except BrokenPipeError:
        sys.exit(0)
