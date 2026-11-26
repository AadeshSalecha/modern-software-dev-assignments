# Results log: Week 6

All runs: starter incident, `python3 tools/practice.py --keep`, Node 24, Claude Code 2.1.332 in this
container, cost from `rate_card.json`. `runs/<stamp>/` holds each run's `summary.json` and
`usage.jsonl`; `runs/index.tsv` maps labels to runs. Full logs (`week6/runs/`) are gitignored.

## Summary

| Setup | Passed | Mean repair | Mean impact | Mean cost | Cost range | Mean requests | Mean time |
| --- | --- | --- | --- | --- | --- | --- | --- |
| baseline | 1/3 | 0.63 | 0.86 | $1.496 | $1.21 to $2.02 | 36 | 391 s |
| A-v1 | 6/6 | 1.00 | 1.00 | $0.219 | $0.20 to $0.25 | 12 | 98 s |
| flags | 2/3 | 0.81 | 1.00 | $0.526 | $0.42 to $0.65 | 27 | 184 s |
| effort-low | 1/3 | 1.00 | 0.82 | $0.164 | $0.16 to $0.17 | 11 | 76 s |
| haiku | 3/3 | 1.00 | 1.00 | $0.067 | $0.05 to $0.08 | 31 | 363 s |
| nohook | 3/3 | 1.00 | 1.00 | $0.192 | $0.17 to $0.21 | 11 | 82 s |
| effort-high | 3/3 | 1.00 | 1.00 | $0.358 | $0.35 to $0.37 | 17 | 170 s |

## baseline

Unmodified `run.sh`: Sonnet, effort high, default tools, bare ticket

| Run | Result | Repair | Impact | Cost | Requests | Time | Incident | Regr. | Compat | In | Out | Cache read | Cache write |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 20261126-101810-1 | FAIL | 0.4444 | 0.5698 | $1.260 | 38 | 303.4 s | 4/9 | 10/10 | 2/2 | 78 | 37,711 | 3,419,684 | 135,234 |
| 20261126-125854-1 | FAIL | 0.4444 | 1.0 | $1.207 | 30 | 301.1 s | 4/9 | 10/10 | 2/2 | 60 | 39,072 | 2,730,717 | 135,792 |
| 20261126-125854-2 | PASS | 1.0 | 1.0 | $2.020 | 39 | 569.6 s | 9/9 | 10/10 | 2/2 | 78 | 75,743 | 5,139,807 | 187,006 |

mean cost $1.496, worst $2.020, 3 runs

## A-v1

Option A (commit 1b556ac): prep + kit + one Sonnet session, effort medium, 4 tools, stop hook

| Run | Result | Repair | Impact | Cost | Requests | Time | Incident | Regr. | Compat | In | Out | Cache read | Cache write |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 20261126-120000-1 | PASS | 1.0 | 1.0 | $0.207 | 11 | 93.8 s | 9/9 | 10/10 | 2/2 | 22 | 8,404 | 268,768 | 38,565 |
| 20261126-120152-1 | PASS | 1.0 | 1.0 | $0.247 | 14 | 106.6 s | 9/9 | 10/10 | 2/2 | 28 | 10,013 | 430,712 | 41,617 |
| 20261126-120152-2 | PASS | 1.0 | 1.0 | $0.226 | 12 | 102.4 s | 9/9 | 10/10 | 2/2 | 24 | 9,512 | 336,657 | 38,867 |
| 20261126-120152-3 | PASS | 1.0 | 1.0 | $0.215 | 12 | 93.8 s | 9/9 | 10/10 | 2/2 | 24 | 8,702 | 313,626 | 38,480 |
| 20261126-120152-4 | PASS | 1.0 | 1.0 | $0.202 | 10 | 95.7 s | 9/9 | 10/10 | 2/2 | 20 | 8,629 | 242,517 | 36,746 |
| 20261126-120152-5 | PASS | 1.0 | 1.0 | $0.219 | 11 | 95.0 s | 9/9 | 10/10 | 2/2 | 22 | 8,327 | 323,489 | 41,388 |

mean cost $0.219, worst $0.247, 6 runs

## flags

Bare ticket, no kit; only harness flags changed (4 tools, no MCP, 5-minute cache, effort medium)

| Run | Result | Repair | Impact | Cost | Requests | Time | Incident | Regr. | Compat | In | Out | Cache read | Cache write |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 20261126-121206-1 | PASS | 1.0 | 1.0 | $0.648 | 32 | 233.1 s | 9/9 | 10/10 | 2/2 | 64 | 24,261 | 1,886,414 | 86,697 |
| 20261126-121206-2 | PASS | 1.0 | 1.0 | $0.511 | 27 | 177.9 s | 9/9 | 10/10 | 2/2 | 54 | 21,136 | 1,285,225 | 68,430 |
| 20261126-121206-3 | FAIL | 0.4444 | 1.0 | $0.417 | 21 | 140.5 s | 4/9 | 10/10 | 2/2 | 42 | 16,802 | 906,575 | 63,476 |

mean cost $0.526, worst $0.648, 3 runs

## effort-low

Option A with `--effort low`

| Run | Result | Repair | Impact | Cost | Requests | Time | Incident | Regr. | Compat | In | Out | Cache read | Cache write |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 20261126-122138-1 | FAIL | 1.0 | 0.7333 | $0.159 | 11 | 75.2 s | 9/9 | 10/10 | 2/2 | 22 | 6,046 | 233,982 | 29,871 |
| 20261126-122138-2 | PASS | 1.0 | 1.0 | $0.159 | 11 | 78.7 s | 9/9 | 10/10 | 2/2 | 22 | 6,307 | 234,882 | 29,059 |
| 20261126-122138-3 | FAIL | 1.0 | 0.7333 | $0.174 | 10 | 74.0 s | 9/9 | 10/10 | 2/2 | 20 | 6,260 | 238,250 | 35,165 |

mean cost $0.164, worst $0.174, 3 runs

## haiku

Option A with `--model claude-haiku-5-5` for the whole session

| Run | Result | Repair | Impact | Cost | Requests | Time | Incident | Regr. | Compat | In | Out | Cache read | Cache write |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 20261126-122547-1 | PASS | 1.0 | 1.0 | $0.064 | 33 | 328.0 s | 9/9 | 10/10 | 2/2 | 66 | 56,362 | 2,191,031 | 109,549 |
| 20261126-122547-2 | PASS | 1.0 | 1.0 | $0.054 | 25 | 323.5 s | 9/9 | 10/10 | 2/2 | 50 | 54,436 | 1,550,705 | 92,193 |
| 20261126-122547-3 | PASS | 1.0 | 1.0 | $0.083 | 34 | 438.9 s | 9/9 | 10/10 | 2/2 | 68 | 81,334 | 2,652,374 | 127,999 |

mean cost $0.067, worst $0.083, 3 runs

## nohook

Option A with the stop hook and the resume switched off

| Run | Result | Repair | Impact | Cost | Requests | Time | Incident | Regr. | Compat | In | Out | Cache read | Cache write |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 20261126-124417-1 | PASS | 1.0 | 1.0 | $0.170 | 9 | 67.3 s | 9/9 | 10/10 | 2/2 | 18 | 6,279 | 196,502 | 34,984 |
| 20261126-124417-2 | PASS | 1.0 | 1.0 | $0.210 | 13 | 93.0 s | 9/9 | 10/10 | 2/2 | 26 | 8,681 | 331,847 | 36,080 |
| 20261126-124417-3 | PASS | 1.0 | 1.0 | $0.195 | 12 | 86.1 s | 9/9 | 10/10 | 2/2 | 24 | 7,949 | 302,595 | 33,893 |

mean cost $0.192, worst $0.210, 3 runs

## effort-high

Option A with `--effort high`

| Run | Result | Repair | Impact | Cost | Requests | Time | Incident | Regr. | Compat | In | Out | Cache read | Cache write |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 20261126-124845-1 | PASS | 1.0 | 1.0 | $0.357 | 19 | 164.4 s | 9/9 | 10/10 | 2/2 | 38 | 15,238 | 727,976 | 52,847 |
| 20261126-124845-2 | PASS | 1.0 | 1.0 | $0.372 | 15 | 180.5 s | 9/9 | 10/10 | 2/2 | 30 | 17,572 | 578,504 | 55,211 |
| 20261126-124845-3 | PASS | 1.0 | 1.0 | $0.346 | 17 | 164.0 s | 9/9 | 10/10 | 2/2 | 34 | 15,581 | 606,088 | 51,912 |

mean cost $0.358, worst $0.372, 3 runs
