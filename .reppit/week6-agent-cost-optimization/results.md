# Results log: Week 6

All runs: starter incident, `python3 tools/practice.py --keep`, Node 24, this container's Claude Code
2.1.332, cost from `rate_card.json`. Raw `summary.json` and `usage.jsonl` per run are in `runs/`
(the full logs under `week6/runs/` are gitignored). Tables made with `analyze_run.py --table`.

## Baseline: unmodified `run.sh` (Sonnet, effort high, default tools)

| Run | Result | Repair | Impact | Cost | Requests | Time | Incident | Regr. | Compat | In | Out | Cache read | Cache write |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 20261126-101810-1 | FAIL | 0.4444 | 0.5698 | $1.260 | 38 | 303.4 s | 4/9 | 10/10 | 2/2 | 78 | 37,711 | 3,419,684 | 135,234 |

mean cost $1.260, worst $1.260, 1 runs

Cache writes were billed at the 1-hour rate ($4.00/M): $0.54 of the $1.26.

## Option A, first version (commit 1b556ac): prep + one Sonnet session, effort medium, 4 tools

| Run | Result | Repair | Impact | Cost | Requests | Time | Incident | Regr. | Compat | In | Out | Cache read | Cache write |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 20261126-120000-1 | PASS | 1.0 | 1.0 | $0.207 | 11 | 93.8 s | 9/9 | 10/10 | 2/2 | 22 | 8,404 | 268,768 | 38,565 |
| 20261126-120152-1 | PASS | 1.0 | 1.0 | $0.247 | 14 | 106.6 s | 9/9 | 10/10 | 2/2 | 28 | 10,013 | 430,712 | 41,617 |
| 20261126-120152-2 | PASS | 1.0 | 1.0 | $0.226 | 12 | 102.4 s | 9/9 | 10/10 | 2/2 | 24 | 9,512 | 336,657 | 38,867 |
| 20261126-120152-3 | PASS | 1.0 | 1.0 | $0.215 | 12 | 93.8 s | 9/9 | 10/10 | 2/2 | 24 | 8,702 | 313,626 | 38,480 |
| 20261126-120152-4 | PASS | 1.0 | 1.0 | $0.202 | 10 | 95.7 s | 9/9 | 10/10 | 2/2 | 20 | 8,629 | 242,517 | 36,746 |
| 20261126-120152-5 | PASS | 1.0 | 1.0 | $0.219 | 11 | 95.0 s | 9/9 | 10/10 | 2/2 | 22 | 8,327 | 323,489 | 41,388 |

mean cost $0.219, worst $0.247, 6 runs

- 6 of 6 pass. No stop-hook block and no resume fired in any run: the agent ran `kit/check.sh`
  itself and stopped on a clear gate.
- Cost split of the mean run: cache writes about 44%, output about 39%, cache reads about 13%.
- 10 to 13 tool calls per run, all Bash; context grew from about 10k to about 40k tokens.
- In the one transcript read in full (120000-1) the agent wrote the ledger last, already ticked,
  not first as the prompt asks.
