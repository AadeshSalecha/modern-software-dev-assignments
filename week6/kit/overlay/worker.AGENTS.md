# worker

Go, standard library only. `internal/standardwebhooks` is vendored signing code: leave it.

- Listens on port base+3. Journal: `$SWITCHYARD_STATE/worker/journal.jsonl`; after a
  restart `recovery.go` settles what the journal says was held. Log:
  `$SWITCHYARD_STATE/logs/worker.jsonl`.
- One tick: settle, lease one delivery from the router, journal, send, journal, report,
  close. Attempt ids are derived from the worker id and the journal counter (`attemptID`).
- Tests: `go test -count=1 ./... 2>&1 | tail -15` in this directory. The harness builds the
  binary itself; a compile error stops every scenario.
