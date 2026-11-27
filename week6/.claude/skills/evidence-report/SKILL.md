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
  `conflict`). `endpoint_id` comes from records that name the endpoint; `url_endpoint` is
  only what the address of a request looked like.
- `responses` (view): every record of an HTTP status for a delivery, from any file
  (`source`, `delivery_id`, `attempt_id`, `status`, `ts`). Status `0` means no answer.
- `attempts` and `leases`: one row per attempt id and per lease id, with what each file says
  about it side by side: `<file>_n` records, `<file>_ts` and `<file>_ts_last` on that file's
  clock, `<file>_status`. `n_deliveries` above 1 means the id was used for more than one
  delivery; `status_conflict` means two files give different statuses. Use these when the
  question is about attempts, retries, leases or how often something was sent: one request
  appears in several files and must be counted once.
- Clock gaps between files are printed at the end of `work/evidence.txt`.
- `skipped`: corrupted rows per file. A total over all files is `sum(corrupted_rows)`.

## What decides whether a report is right

1. **The ticket's definitions are the specification.** Turn each sentence of the request
   into a condition on primary facts: what was accepted, created, sent, answered, and when.
   A record in which a service states a conclusion (a `msg` or `op` such as `…ignored`,
   `…stale`, `…rejected`) shows what that service believed then, which may be the defect
   itself. Use such records as leads; never let them replace the ticket's definition.
2. **No file is complete, so build every set from all the files that can show a member.**
   A row that was cut is gone from its file, and with it one member of anything you select
   from that file alone. For each set the ticket's definition names (the requests that were
   accepted, the events of a merchant, the deliveries that were answered), write down which
   kinds of record show that a member exists: the record of the service that did it, and
   records made downstream that could not exist without it (the router handling a message
   shows the api published it; a worker's attempt shows the delivery was created and
   leased). Take the union, then count how many members each source alone would have
   missed. `events`, `deliveries`, `responses`, `attempts` and `leases` already combine the
   files for those ids; for any other kind of fact, combine them yourself.
   `select * from skipped` shows how many rows each file lost.
3. **Order records by one file's own `ts`**, then `line_no`: lines arrive late and out of
   order. Clocks differ between files by up to minutes. Where the ticket ties a time to one
   service ("accepted by the api at", "leased at"), take both sides of the comparison from
   that service's file; compare across files only after correcting by the printed gap, and
   look at the records that fall within the gap's spread one by one.
4. **What may fill a hole, and what may not.** A record made downstream of a fact
   establishes the fact (rule 2), so use it: take from it what it could not have been
   written without (which message arrived, about which ids), not its verdict. A record in
   which a service classifies something does not establish what it claims (rule 1), and a
   missing attribute is never guessed. If, with every file used, an attribute your
   definition needs is still missing for some id because its only record was cut, then by
   `app/contracts/evidence.md` the report does not depend on that id: leave it out, and say
   how many you left.
5. **Exactness.** Complete ids; one entry per the key the ticket names; every id the entry
   asks for; whole numbers as whole numbers. For each figure, re-read the sentence that
   defines it and compute it over exactly the set it names.
6. **Look before you write.** Print the result's size and its breakdown by merchant or
   endpoint, and follow two or three rows by hand through the per-file tables.

## Writing the file

Put the query in a small script, `work/report.py` (`sqlite3` and `json` only), that writes
the file under `out/` in exactly the shape the ticket shows, and run it again after any
change. `kit/check.sh` compares the shape with the ticket's example; it cannot tell whether
the content is right.
