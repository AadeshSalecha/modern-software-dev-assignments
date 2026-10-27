# Week 4 Write-up

**Repo chosen** and link to your fork:
> **Stanford-SURF/SWIM** (Simulation for Ward Inpatient Management), branch `los-daily-predictor`
> (https://github.com/Stanford-SURF/SWIM/tree/los-daily-predictor). SWIM is a hospital patient-flow
> simulator. It is a Python simulation engine with a FastAPI backend and a Next.js UI, about 840 commits from
> Fork here: https://github.com/AadeshSalecha/SWIM_Private_Fork (it was a private repo, that I got permission to publish a subset of, hence it is not "officially" a fork)
> Disclosure: I'm a recent collaborator. 11 of the repo's 841 commits are mine, all in the LOS model files and `los_analysis/`. The engine, backend, UI and test suite were written by other people, and the redesigned engine was new to me.

**File you wrote** (`AGENTS.md` or `CLAUDE.md`):
> `AGENTS.md` at the repo root, 75 lines.
> `CLAUDE.md` with a single line, `@AGENTS.md`, so Claude Code and other agents
> (Codex, Cursor, etc.) both load the same file.


## Part I: Exploration

| | Finding |
|---|---|
| Build / run | There is no build step: the engine is plain Python 3.12. `pip install -r los_analysis/requirements.txt` gives a working engine and pytest environment. `simulation/pyproject.toml` (Poetry) can't be installed because it has a path dependency on `/LOSDeterminerInterface`, and it lacks pytest, pyyaml and xgboost. Data is not in git: you need `data_for_share/` (from Box) plus `swim-backend/database/swim.db`, built with `python swim-backend/database/build_swim_db.py --force` (~5 min). To run the server: `cd swim-backend && uvicorn app.main:app --port 3002`, then `POST /api/simulate {"start_time","days","personas"}`. To run without the server: `python los_analysis/sim/run_sim.py --model replay --start 2023-01-01 --days 1 --out /tmp/sim.json` (2 min 10 s measured, mostly data loading). `docker compose up` is broken on this branch because it builds `postgres_init/`, which was deleted. `simulation/makefile` and `main.sh` submit Slurm jobs on Stanford's Sherlock cluster. |
| Test | pytest. Run from `simulation/` so `from src...` resolves. **Unit tests:** `cd simulation && python -m pytest -q src/components/_4_event_simulation_NEW/tests/unit` gives 418 passed in 1.6 s with no data needed. **Full suite:** `cd simulation && PYTHONPATH=../swim-backend SWIM_DATABASE_PATH=../swim-backend/database/swim.db python -m pytest -q src/components/_4_event_simulation_NEW/tests` gives 442 passed in 13.5 min. Without `PYTHONPATH`, 10 integration tests fail with `ModuleNotFoundError: No module named 'app'`, because the engine imports the backend's DAOs. Without `SWIM_DATABASE_PATH`, 11 fail with `swim.db not found`, because the DB path is resolved relative to the working directory. Part III caught the second one. Nothing in the repo documents either. **Backend tests:** `swim-backend/tests/` uses an autouse session fixture that starts uvicorn on :3002 and symlinks `data_for_share` when it's missing. The "e2e" test prints MAE but never asserts on it. |
| Lint / format | Only `black --check`, through `.pre-commit-config.yaml`; there's no linter or type checker. The repo is **not** black-clean: `black --check simulation/src swim-backend` reports that 75 files would be reformatted and 3 can't be parsed. That's why "format only the files you touched" made it into the file. |
| Key directories and entry points | The engine is in `simulation/src/components/_4_event_simulation_NEW/`. `api_runner.run_simulation()` sets things up and `core/central_processor.py` runs the 5-minute tick loop. Each tick runs four sequences (`arrival`, `leave_request`, `assignment`, `physical_move`). Each one is a `Sequencer` that runs `when`, then `what`, then `do`, using personas from `personas/<seq>/<role>/<name>.py` that are registered with `@register`. Sequences talk only through `core/state/information_layer.py`. The backend is `swim-backend/app/main.py` (FastAPI, `/api/simulate`, `/api/personas`) and `app/dao/` (raw-sqlite DAOs that the engine also imports). `los_analysis/` holds offline model training and evaluation. `custom-ui/` is Next.js on port 3001. |
| Unstated conventions | (1) A new persona has to be imported in its folder's `__init__.py` or it silently never registers. (2) Persona tests are named `test_persona_<seq>_<role>_<name>.py` and use fakes, not the DB. (3) `simulated_visit_id` is the patient key. Historical CSNs are written only through `replay.register_visit()`, and two AST-scanning tests (`test_identifier_discipline.py`, `test_state_split_invariants.py`) fail if you write location or CSN state anywhere else. (4) The engine uses naive Pacific datetimes, while the DB and census cache use UTC `...Z` strings. (5) "Census" means inpatient units only (`non_ambulatory=1`). (6) `DATA_FOLDER` defaults to `../data_for_share` relative to the working directory, so commands only work from `simulation/` or `swim-backend/`. (7) A request's `personas` block replaces that whole sequence's config rather than merging into it. |
| Off-limits (generated, vendored) | Generated files: model artifacts in `simulation/src/io/ckpt/aadesh_los*/` (from `los_analysis/training/*/run_all.sh`), `swim-backend/validation_results/census_cache/*.json` (from `precompute_census.py`), `los_analysis/figures/` and `baselines/mae_2023.json`. Sensitive: `data_for_share/`, `swim.db` and anything with CSNs or MRNs (patient data), plus a **tracked `.env` with DB credentials**. Legacy code that looks live: `simulation/src/io/database` and `src/config/db.py` (Postgres), and the Prefect/Slurm scripts. Stale docs: the root `CLAUDE.md`, `NEW/README.md`, `docs/`, `task*.md`. |

**How you figured it out**: what you asked the agent, what you had to read yourself:
> I worked in a clean git worktree of the branch and gave a read-only Explore subagent a narrow brief. It
> had to report, with file:line references, (1) the real engine entry point and how personas register,
> (2) which paths named in the existing CLAUDE.md still exist, (3) every test file and what it needs,
> (4) conventions found in code (env vars, IDs, time zones, import style) and (5) generated files. I told it
> to treat the existing CLAUDE.md as a claim to check, not as the source of truth. That turned out to be the
> most useful instruction. The 145-line root CLAUDE.md describes a request queue, a Placement Handler and
> `HistoricalTransferEmitter`, none of which exist on this branch: the D1–D4 redesign commits moved them to a
> gitignored `archive/`.
>
> Then I checked everything that would go in the file by running it myself instead of trusting the agent.
> The agent said the integration tests "need data". Running them showed that data wasn't enough: they also
> need `PYTHONPATH=../swim-backend`, which became the most important line in the file. The agent also
> guessed the database build takes 20–30 min, but that was the old `Update DB` path. `build_swim_db.py` takes
> about 5 min. I read `registry.py`, `api_runner._DEFAULT_PERSONAS` and `unit_avg_los.py` to confirm the
> persona recipe. I also ran `black --check` to find out whether "run black" was safe advice (it isn't, on
> the whole repo).


## Part II: The File

**Anything you deliberately left out**, and why:
> - **The architecture essay.** The old CLAUDE.md spent about 60 lines on *why* there's a single request
>   queue. Even where it's still true, an agent can get it by reading `sequencer.py`. I kept one sentence of
>   purpose (historical replay first, then swap in one persona and measure) because that explains why
>   "never patch a specific patient" matters.
> - **File-by-file descriptions** of `core/` and `types/`. The map covers the five files that are entry
>   points, and the agent can find the rest.
> - **Generic style rules** (docstrings, type hints, naming). The code is consistent enough that an agent
>   copies it. The persona section points at one file to copy instead of listing rules.
> - **The old "Headless Claude Code" section** (how to run `claude -p --dangerously-skip-permissions`). It
>   describes how the developer runs their tools, not how the repo works.
> - **`custom-ui/`, Terraform, Grafana and the Sphinx docs.** Each gets at most half a line. Almost no task
>   touches them, and each line costs context on every task.
> - **Things that change often**, such as current MAE numbers and which LOS model is best. They'd go stale
>   within a week. They belong in `los_analysis/README.md`, which already has them.
> - **My own conda env name** (`swim-los-test`). It's specific to my machine, not to the repo.

**The hardest call** on what to include:
> The **Guardrails** section. Writing it, I wanted to warn about every trap I'd hit, and there are a lot: the
> broken Poetry file, Prefect being an import-only dependency, the CSV-vs-DB split, the backend's
> `GET /api/events/...` endpoints, the gitignored `archive/`, and the warm-up patients' `step_start_time`
> quirk. I kept a trap only if a plausible agent action would cause real damage or a confusing failure:
> leaking patient data or `.env`, following the stale docs, running `docker compose up` or `black .`,
> letting the backend build a broken DB, or hand-editing model artifacts. The `step_start_time` quirk was the
> closest call. It's a real bug magnet, but only for LOS-persona work, so it belongs in a code comment or a
> nested file, not in the root file every task loads. The other close call was replacing the existing
> CLAUDE.md rather than editing it. Its "never hardcode patient-specific fixes" rule is the one thing it got
> right, so I kept that as one line under Conventions and dropped the rest.


## Part III: Trying It Out

| # | Task | Did the agent use your commands and conventions? |
|---|---|---|
| 1 | *"Run the simulation engine's tests and tell me whether everything passes."* | **It used the commands exactly, and that exposed a bug in my file.** It ran the fast unit tier first (418 passed), as the "Slow runs" line says, and then pasted the full-suite command verbatim, including `PYTHONPATH=../swim-backend`. It got **11 failures**, all `FileNotFoundError: swim.db not found`. It didn't call this an engine bug. It traced the failures to `_get_db_path()` in `arrival_generation.py`, which looks for `swim-backend/database/swim.db` *relative to the working directory*, while my command `cd`s into `simulation/`. Rerunning the failing files with `SWIM_DATABASE_PATH` set made all of them pass. It edited nothing, didn't read `.env`, and reported the failure honestly instead of "fixing" the tests. The cause was mine: when I verified "442 passed" during exploration, I had `SWIM_DATABASE_PATH` exported, and I dropped it when I copied the command into the file. |
| 2 | *"Add a new `leave_request.when` persona called `fixed_los` … constructor argument `hours`, default 48. Add a test and make sure it works."* | **Yes, on every convention the file named.** It copied `unit_avg_los.py` (relative imports, `lead_time_minutes = 10`, read-only `candidates`). It added `from . import fixed_los` to `__init__.py`, the silent-failure trap I'd bolded. It named the test `tests/unit/test_persona_leave_request_when_fixed_los.py` and built it from fakes (18 tests, no DB). It ran `black` on only its two files, ran the fast unit tier (438 passed, which I confirmed), and kept its end-to-end check to `--days 1`. Two things went beyond the file. First, it noticed on its own that `step_start_time` is the last bed move for patients already present at the start, which is the quirk I'd deliberately left out. It flagged this rather than silently copying `blended_los`'s fix. Second, my "one simulation" command only covers built-in models (`run_sim.py --model replay...`), so it had to write a scratch runner to try a new persona. That runner first failed with `No module named 'paths'` until it found `los_analysis/paths.setup()`. |

**One thing you'd change** about the file after watching it get used:
> **Make the full-suite command self-sufficient:**
> `cd simulation && PYTHONPATH=../swim-backend SWIM_DATABASE_PATH=../swim-backend/database/swim.db python -m pytest -q src/components/_4_event_simulation_NEW/tests`,
> with one sentence explaining that the data paths are resolved relative to the working directory. I've
> made this change in the submitted `AGENTS.md`, and the corrected command passes on a fresh worktree:
> **442 passed in 14 min 55 s**, without setting `DATA_FOLDER`. The lesson is about process as much as content. Task 1 showed the agent will paste a
> documented command *literally* and trust it over its own judgment, so every command in the file has to be
> verified in a clean shell with no leftover env vars, not in the terminal where I'd been exploring.
>
> Runner-up, from task 2: add one line showing how to run a simulation with an arbitrary persona config
> (`paths.setup()` and then `run_simulation(personas=...)`). "Add a persona and try it" is the most common
> task in this repo, and right now an agent has to reinvent that runner each time.


## Submission
1. `Command (⌘) + F` for `TODO`. No results means you're done.
2. Push all changes to your remote repository and submit via Gradescope.
