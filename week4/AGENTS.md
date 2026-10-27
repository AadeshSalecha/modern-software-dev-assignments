# AGENTS.md: SWIM (Simulation for Ward Inpatient Management)

SWIM simulates patient flow through Stanford hospital inpatient units: arrivals, leave requests, bed
assignments and moves, on a 5-minute tick. The engine is validated by **historical replay**. Run it with
personas that replay recorded decisions and compare simulated census to actual census. Then swap in one
model persona (for example an LOS predictor) and attribute the change in error to that persona.

## Map
All engine paths are under `simulation/src/components/_4_event_simulation_NEW/` (written `NEW/` below).
- `NEW/api_runner.py` `run_simulation()` builds state, the four modules and the default personas
  (`_DEFAULT_PERSONAS`). `NEW/core/central_processor.py` runs the tick loop.
- Each tick runs four sequences in order: `arrival`, `leave_request`, `assignment`, `physical_move`.
  `NEW/core/sequencer.py` runs `when.candidates`, then `what.decide`, then `do.execute`. Sequences talk
  only through `NEW/core/state/information_layer.py`.
- `NEW/personas/<sequence>/<when|what|do>/<name>.py` holds the pluggable decision makers, registered with
  `@register(sequence=, role=, name=)` from `NEW/personas/registry.py`.
- `swim-backend/app/main.py` is the FastAPI app. It runs `POST /api/simulate` and serves the
  `GET /api/personas` listing. `swim-backend/app/dao/` holds the SQLite DAOs; the engine imports these too.
- `custom-ui/` is the Next.js front end (`npm run dev`, port 3001).

## Setup and commands (Python 3.12; run from the repo root unless a `cd` is shown)
- Environment: `pip install -r requirements.txt` covers the engine, models and pytest. The
  backend also needs `pip install -r swim-backend/requirements.txt requests`.
- Data is not in git. You need `data_for_share/` (the unzipped Box "SWIM/Data Folders/data.zip") and
  `swim-backend/database/swim.db`. Build the database with
  `python swim-backend/database/build_swim_db.py --force` (about 5 min).
- Fast tests (no data, about 2 s):
  `cd simulation && python -m pytest -q src/components/_4_event_simulation_NEW/tests/unit`
- Full engine suite, which includes 1-day simulations and takes about 14 min:
  `cd simulation && PYTHONPATH=../swim-backend SWIM_DATABASE_PATH=../swim-backend/database/swim.db python -m pytest -q src/components/_4_event_simulation_NEW/tests`.
  Both variables are required, because data paths are resolved relative to the working directory. Without
  them, the integration tests fail with `No module named 'app'` or `swim.db not found`.
- Backend: `cd swim-backend && uvicorn app.main:app --port 3002`. Then send
  `POST /api/simulate {"start_time": "2023-01-01T00:00:00", "days": 1, "personas": {...}}`. A `personas`
  entry replaces that whole sequence's config.
- Format: `black <files you changed>` (pre-commit runs `black --check`).

## Conventions
- To add a persona, create `NEW/personas/<seq>/<role>/<name>.py`. Copy the style of
  `leave_request/when/unit_avg_los.py`: relative imports, a `lead_time_minutes` class attribute, and
  read-only `when` logic. **Also add `from . import <name>` to that folder's `__init__.py`**, or the
  persona never registers. Test it in `NEW/tests/unit/test_persona_<seq>_<role>_<name>.py` using fakes,
  not the DB.
- IDs: `simulated_visit_id` is the engine's patient key. Historical CSNs live only in
  `replay.visit_to_csn`, written through `register_visit()`. `test_identifier_discipline.py` and
  `test_state_split_invariants.py` scan the source and fail if you write `patient_locations` or
  `visit_to_csn` outside the allowlisted writers. Route moves through `PhysicalWorld.move`/`discharge`.
- Time: the engine uses **naive Pacific** datetimes. The DB and the census cache use UTC strings ending in
  `Z`. Convert with `swim-backend/app/utils/timezone_utils.py` and never compare the two directly.
- Census means inpatient units only (`unit.non_ambulatory = 1`), on both the simulated and actual sides.
- To fix a replay-vs-census mismatch, change preprocessing, the census query or the engine so the fix
  holds for every date. Never patch a specific patient or timestamp.

## Guardrails
- **Patient data.** `data_for_share/`, `swim.db` and any file with `csn` or MRN
  values must never be committed, printed in bulk or pasted into issues. Never hard-code a real patient ID
  in tests; use synthetic ones such as `900000001`. DB credentials go in an untracked `.env` (keys are
  listed in `.env.example`). Never commit `.env` or echo it.
- **Stale docs.** Do not trust `NEW/README.md`, `docs/`, `task*.md` or `DEAD_CODE_PLAN.md`. They describe
  the pre-redesign request queue, handlers and emitters, which were moved to the gitignored `archive/`.
- **Legacy code.** Do not use `docker compose up`: it builds `postgres_init/`, which this branch deleted.
  Also leave alone `simulation/main.sh`/`makefile` (Sherlock/Slurm Prefect jobs) and `src/io/database`
  (Postgres). Prefect is only an import dependency of the arrival path, so no server is needed.
- **Missing database.** If `swim.db` is missing, backend startup silently creates an incomplete one
  without `unit.non_ambulatory`. Rebuild it with `build_swim_db.py --force`. Do not use the
  `migrate_*.py` scripts.
- **Derived data is not in this copy, and must never be committed.** That covers the LOS model artifacts
  (`simulation/src/io/ckpt/aadesh_los*/`), the census cache
  (`swim-backend/validation_results/census_cache/*.json`) and `NEW/baselines/*.json`, all of which come
  from patient data. `.gitignore` blocks them. Without the artifacts, the LOS model tests skip and the
  `blended_los`/`daily_remaining_los` personas cannot load. Rebuild the census cache with
  `swim-backend/validation/precompute_census.py`.
- **Do not reformat the repo.** `black .` would reformat 75 files; format only the files you touched.
- **Slow runs.** Any simulation spends about 2 min loading data, and a simulated month takes about 8 min.
  Use `--days 1` unless asked for more, and run the unit tests before the full suite.
