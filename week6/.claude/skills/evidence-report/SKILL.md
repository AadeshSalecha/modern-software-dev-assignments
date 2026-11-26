---
name: evidence-report
description: Answer a ticket's report or impact question from the incident evidence, already loaded in work/evidence.db. Use before writing any file under out/, and when looking for the pattern behind an incident.
---

# Reports from the evidence packet

`incident/` is already loaded into SQLite at `work/evidence.db`, following
`app/contracts/evidence.md`: rows cut short are skipped and counted, lines the shipper sent
twice are one record, cut ids in the merchant export are resolved, amounts are in minor
units. Do not parse the raw files again. `work/evidence.txt` lists every table, record kind
and field (a `?` marks a field only some records have).

```
python3 kit/evidence.py sql "select msg, count(*) from api group by 1"   # 40 rows shown; aggregate
python3 kit/evidence.py schema
```

## Tables

- One table per file (`api`, `router`, `worker`, `egress`, `merchant_export`, `snapshot_*`).
  Columns are the fields that file has. `ts` is epoch seconds on that file's own clock,
  `line_no` the first line the record appeared on, `copies` how often it appeared.
- `events`: one row per event id with what all files together say about it
  (`merchant_id`, `type`, `amount_minor`, `currency`, `sources`, `conflict`).
- `deliveries`: one row per delivery id (`event_id`, `endpoint_id`, `resend_of`, `sources`,
  `conflict`).
- `responses` (view): every record of an HTTP status for a delivery, from any file
  (`source`, `delivery_id`, `attempt_id`, `status`, `ts`). Status `0` means no answer.
- `skipped`: corrupted rows per file. A total over all files is `sum(corrupted_rows)`.

## What decides whether a report is right

1. **The ticket's definitions are the specification.** Turn each sentence of the request
   into a condition on primary facts: what was accepted, created, sent, answered, and when.
   A record in which a service states a conclusion (a `msg` or `op` such as `…ignored`,
   `…stale`, `…rejected`) shows what that service believed then, which may be the defect
   itself. Use such records as leads; never let them replace the ticket's definition.
2. **No file is complete, so a fact counts if any file records it.** Start from `events`,
   `deliveries` and `responses`, which already combine the files. "Has a 2xx in the egress
   log" is a different, smaller set than "got a 2xx".
3. **Order records by one file's own `ts`**, then `line_no`: lines arrive late and out of
   order. Clocks differ between files by up to minutes; do not order across files.
4. **Check for holes.** A fact your definition needs may exist in a single file and be
   missing for some ids (its row was cut). Count how many ids in play lack it before you
   trust the result.
5. **Exactness.** Complete ids; one entry per the key the ticket names; every id the entry
   asks for; whole numbers as whole numbers; only keys with something to report where the
   ticket says to leave out the rest.
6. **Look before you write.** Print the result's size and its breakdown by merchant or
   endpoint, and follow two or three rows by hand through the per-file tables.

## Writing the file

Put the query in a small script, `work/report.py` (`sqlite3` and `json` only), that writes
the file under `out/` in exactly the shape the ticket shows, and run it again after any
change. `kit/check.sh` compares the shape with the ticket's example; it cannot tell whether
the content is right.
