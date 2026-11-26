# api

TypeScript, run directly by node (types are stripped, nothing is compiled; no dependencies).

- Listens on port base+1. Store: `$SWITCHYARD_STATE/api/api.db` (SQLite; schema in
  `src/store.ts`, created with `create table if not exists`, so a store written by the
  shipped release keeps its old shape until you alter it yourself). Log:
  `$SWITCHYARD_STATE/logs/api.ndjson`.
- It talks to the router only through the outbox: rows are posted to the router's `/bus` on
  tick, oldest first. `200` marks a row published; `422` marks it rejected for good.
- Only erasable TypeScript runs: no `enum`, `namespace` or constructor parameter
  properties, and imports keep their `.ts` extension.
- Tests: `npm test --silent 2>&1 | tail -15` in this directory.
