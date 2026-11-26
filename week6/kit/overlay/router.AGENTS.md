# router

Python 3, standard library only. One process owns the queue.

- Listens on port base+2. Store: `$SWITCHYARD_STATE/router/router.db` (SQLite; schema in
  `store.py`, created with `create table if not exists`, so a store written by the shipped
  release keeps its old shape until you alter it yourself). Log:
  `$SWITCHYARD_STATE/logs/router.log` (`key=value`; `Log.write` in `store.py`).
- `POST /bus` takes messages of versions 1, 2 and 3 (`bus.py`): `200` when applied or
  already applied, `422` when malformed. `main.py` remembers each message's identity so
  that it is applied once.
- `GET /__admin/state` must keep the fields `app/contracts/harness.md` lists; the replay
  harness reads `next_wake` and `deliveries[]` from it.
- Tests: `python3 -m unittest discover -s tests 2>&1 | tail -15` in this directory.
