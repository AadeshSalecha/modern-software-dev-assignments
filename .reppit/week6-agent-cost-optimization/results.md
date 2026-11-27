# Results log: Week 6

All runs: starter incident, `python3 tools/practice.py --keep`, Node 24, Claude Code 2.1.332 in the
cloud container, cost from `rate_card.json`. `runs/<stamp>/` holds each run's `summary.json` and
`usage.jsonl`; `runs/index.tsv` maps labels to runs. Full logs (`week6/runs/`) are gitignored.
Rebuilt by `make_results.py`.

## Summary

| Setup | Passed | Mean repair | Mean impact | Mean cost | Cost range | Mean requests | Mean time | Longest |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| baseline | 1/3 | 0.63 | 0.86 | $1.496 | $1.21 to $2.02 | 36 | 391 s | 570 s |
| flags | 2/3 | 0.81 | 1.00 | $0.526 | $0.42 to $0.65 | 27 | 184 s | 233 s |
| A-v1 | 6/6 | 1.00 | 1.00 | $0.219 | $0.20 to $0.25 | 12 | 98 s | 107 s |
| nohook | 3/3 | 1.00 | 1.00 | $0.192 | $0.17 to $0.21 | 11 | 82 s | 93 s |
| effort-high | 3/3 | 1.00 | 1.00 | $0.358 | $0.35 to $0.37 | 17 | 170 s | 180 s |
| effort-low | 1/3 | 1.00 | 0.82 | $0.164 | $0.16 to $0.17 | 11 | 76 s | 79 s |
| haiku | 3/3 | 1.00 | 1.00 | $0.067 | $0.05 to $0.08 | 31 | 363 s | 439 s |
| A-v2 | 3/3 | 1.00 | 1.00 | $0.222 | $0.21 to $0.23 | 11 | 105 s | 107 s |
| A-v2-low | 2/3 | 1.00 | 0.91 | $0.185 | $0.17 to $0.20 | 12 | 91 s | 96 s |
| haiku-low | 2/3 | 0.96 | 1.00 | $0.045 | $0.04 to $0.06 | 29 | 262 s | 306 s |
| A-v2-emptyhome | 1/1 | 1.00 | 1.00 | $0.210 | $0.21 to $0.21 | 10 | 101 s | 101 s |
| A-v3 | 4/5 | 1.00 | 0.91 | $0.213 | $0.19 to $0.26 | 12 | 98 s | 111 s |
| A-v4 | 5/5 | 1.00 | 1.00 | $0.197 | $0.19 to $0.21 | 12 | 88 s | 91 s |
| split-haiku-report | 3/3 | 1.00 | 1.00 | $0.196 | $0.19 to $0.20 | 23 | 94 s | 103 s |
| haiku-main-sonnet-rescue | 3/3 | 1.00 | 1.00 | $0.093 | $0.05 to $0.15 | 38 | 375 s | 458 s |
| codex-luna | 0/1 | 0.44 | 1.00 | $0.010 | $0.01 to $0.01 | 12 | 111 s | 111 s |
| codex-terra | 2/2 | 1.00 | 1.00 | $0.102 | $0.08 to $0.12 | 14 | 140 s | 140 s |
| A-v5 | 3/3 | 1.00 | 1.00 | $0.230 | $0.21 to $0.24 | 12 | 102 s | 107 s |
| from-zip | 2/2 | 1.00 | 1.00 | $0.244 | $0.24 to $0.25 | 14 | 126 s | 136 s |
| codex-terra-v5 | 3/3 | 1.00 | 1.00 | $0.101 | $0.09 to $0.11 | 16 | 170 s | 187 s |
| codex-luna-v5 | 1/2 | 0.72 | 1.00 | $0.029 | $0.02 to $0.03 | 38 | 328 s | 375 s |
| sonnet-main-terra-rescue | 2/2 | 1.00 | 1.00 | $0.274 | $0.24 to $0.31 | 16 | 149 s | 173 s |
| forced-rescue-terra | 2/2 | 1.00 | 1.00 | $0.100 | $0.09 to $0.10 | 17 | 180 s | 185 s |
| terra-main-sonnet-rescue | 2/2 | 1.00 | 1.00 | $0.095 | $0.09 to $0.10 | 16 | 157 s | 157 s |
| v2-sonnet-plus-sonnet-low | 2/2 | 1.00 | 1.00 | $0.411 | $0.36 to $0.47 | 24 | 91 s | 107 s |
| v2-sonnet-terra | 2/2 | 1.00 | 1.00 | $0.359 | $0.33 to $0.39 | 28 | 179 s | 191 s |
| v2-haiku-low-plus-sonnet | 2/2 | 1.00 | 1.00 | $0.247 | $0.22 to $0.28 | 44 | 280 s | 348 s |
| v2b-judge-exercise | 1/1 | 1.00 | 1.00 | $0.365 | $0.36 to $0.36 | 22 | 156 s | 156 s |
| v2c-sonnet-plus-haiku | 2/2 | 1.00 | 1.00 | $0.395 | $0.31 to $0.47 | 44 | 299 s | 308 s |
| v2e-zip-sonnet-low | 2/2 | 1.00 | 1.00 | $0.472 | $0.47 to $0.48 | 28 | 218 s | 229 s |
| v2f-zip-sonnet-low | 2/2 | 1.00 | 1.00 | $0.508 | $0.47 to $0.55 | 30 | 190 s | 195 s |
| v2g-sonnet-terra | 2/2 | 1.00 | 1.00 | $0.472 | $0.43 to $0.51 | 37 | 291 s | 309 s |
| v3a-budget | 2/2 | 1.00 | 1.00 | $0.492 | $0.45 to $0.53 | 28 | 193 s | 198 s |
| v3b-budget | 2/2 | 1.00 | 1.00 | $0.523 | $0.52 to $0.53 | 33 | 241 s | 272 s |
| v3-budget-sonnet-terra | 2/2 | 1.00 | 1.00 | $0.571 | $0.53 to $0.61 | 46 | 407 s | 435 s |
| v3c-budget | 2/2 | 1.00 | 1.00 | $0.526 | $0.52 to $0.53 | 32 | 233 s | 236 s |
| v3c-budget-sonnet-terra | 2/2 | 1.00 | 1.00 | $0.502 | $0.47 to $0.54 | 40 | 366 s | 370 s |
| rep-new-starter | 0/4 | 0.00 | 1.00 | $0.074 | $0.07 to $0.08 | 6 | 32 s | 34 s |
| v3d-budget-sonnet-terra | 1/1 | 1.00 | 1.00 | $0.443 | $0.44 to $0.44 | 41 | 344 s | 344 s |
| v4-haiku-haiku | 2/2 | 1.00 | 1.00 | $0.376 | $0.37 to $0.38 | 56 | 322 s | 358 s |
| v4b-haiku-sonnetlow | 1/1 | 1.00 | 1.00 | $0.467 | $0.47 to $0.47 | 43 | 203 s | 203 s |
| raw-sonnetlow-starter | 0/1 | 0.00 | 0.93 | $0.254 | $0.25 to $0.25 | 13 | 82 s | 82 s |
| v2d-from-zip | 1/1 | 1.00 | 1.00 | $0.243 | $0.24 to $0.24 | 13 | 113 s | 113 s |
| v4-sonnet-terra-terra | 1/1 | 1.00 | 1.00 | $0.655 | $0.66 to $0.66 | 60 | 388 s | 388 s |

## baseline

Unmodified `run.sh`: Sonnet, effort high, default tools, bare ticket.

| Run | Result | Repair | Impact | Cost | Requests | Time | Incident | Regr. | Compat | Output | Cache read | Cache write |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 20261126-101810-1 | FAIL | 0.44 | 0.57 | $1.260 | 38 | 303 s | 4/9 | 10/10 | 2/2 | 37,711 | 3,419,684 | 135,234 |
| 20261126-125854-1 | FAIL | 0.44 | 1.00 | $1.207 | 30 | 301 s | 4/9 | 10/10 | 2/2 | 39,072 | 2,730,717 | 135,792 |
| 20261126-125854-2 | PASS | 1.00 | 1.00 | $2.020 | 39 | 570 s | 9/9 | 10/10 | 2/2 | 75,743 | 5,139,807 | 187,006 |

Failures:
- 20261126-101810-1: [incident] a repeat the deployed release queued for a retry is not sent once the release is replaced
- 20261126-101810-1: [incident] a repeat whose original was delivered is never sent
- 20261126-101810-1: [incident] repeats of several payments are each stopped
- 20261126-101810-1: [incident] a repeat that is being sent when the release is replaced is not retried
- 20261126-101810-1: [incident] starting the replaced release twice stops nothing more
- 20261126-125854-1: [incident] a repeat the deployed release queued for a retry is not sent once the release is replaced
- 20261126-125854-1: [incident] a repeat whose original was delivered is never sent
- 20261126-125854-1: [incident] repeats of several payments are each stopped
- 20261126-125854-1: [incident] a repeat that is being sent when the release is replaced is not retried
- 20261126-125854-1: [incident] starting the replaced release twice stops nothing more
- 20261126-101810-1: impact figures 6/6 right, precision 0.283, recall 0.283

## flags

Bare ticket, no kit. Only harness flags changed: 4 tools, no MCP, 5-minute cache, effort medium.

| Run | Result | Repair | Impact | Cost | Requests | Time | Incident | Regr. | Compat | Output | Cache read | Cache write |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 20261126-121206-1 | PASS | 1.00 | 1.00 | $0.648 | 32 | 233 s | 9/9 | 10/10 | 2/2 | 24,261 | 1,886,414 | 86,697 |
| 20261126-121206-2 | PASS | 1.00 | 1.00 | $0.511 | 27 | 178 s | 9/9 | 10/10 | 2/2 | 21,136 | 1,285,225 | 68,430 |
| 20261126-121206-3 | FAIL | 0.44 | 1.00 | $0.417 | 21 | 140 s | 4/9 | 10/10 | 2/2 | 16,802 | 906,575 | 63,476 |

Failures:
- 20261126-121206-3: [incident] a repeat the deployed release queued for a retry is not sent once the release is replaced
- 20261126-121206-3: [incident] a repeat whose original was delivered is never sent
- 20261126-121206-3: [incident] repeats of several payments are each stopped
- 20261126-121206-3: [incident] a repeat that is being sent when the release is replaced is not retried
- 20261126-121206-3: [incident] starting the replaced release twice stops nothing more

## A-v1

Option A (commit 1b556ac): prep + kit + one Sonnet session, effort medium, 4 tools, stop hook.

| Run | Result | Repair | Impact | Cost | Requests | Time | Incident | Regr. | Compat | Output | Cache read | Cache write |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 20261126-120000-1 | PASS | 1.00 | 1.00 | $0.207 | 11 | 94 s | 9/9 | 10/10 | 2/2 | 8,404 | 268,768 | 38,565 |
| 20261126-120152-1 | PASS | 1.00 | 1.00 | $0.247 | 14 | 107 s | 9/9 | 10/10 | 2/2 | 10,013 | 430,712 | 41,617 |
| 20261126-120152-2 | PASS | 1.00 | 1.00 | $0.226 | 12 | 102 s | 9/9 | 10/10 | 2/2 | 9,512 | 336,657 | 38,867 |
| 20261126-120152-3 | PASS | 1.00 | 1.00 | $0.215 | 12 | 94 s | 9/9 | 10/10 | 2/2 | 8,702 | 313,626 | 38,480 |
| 20261126-120152-4 | PASS | 1.00 | 1.00 | $0.202 | 10 | 96 s | 9/9 | 10/10 | 2/2 | 8,629 | 242,517 | 36,746 |
| 20261126-120152-5 | PASS | 1.00 | 1.00 | $0.219 | 11 | 95 s | 9/9 | 10/10 | 2/2 | 8,327 | 323,489 | 41,388 |

## nohook

A-v1 with the stop hook and the resume switched off.

| Run | Result | Repair | Impact | Cost | Requests | Time | Incident | Regr. | Compat | Output | Cache read | Cache write |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 20261126-124417-1 | PASS | 1.00 | 1.00 | $0.170 | 9 | 67 s | 9/9 | 10/10 | 2/2 | 6,279 | 196,502 | 34,984 |
| 20261126-124417-2 | PASS | 1.00 | 1.00 | $0.210 | 13 | 93 s | 9/9 | 10/10 | 2/2 | 8,681 | 331,847 | 36,080 |
| 20261126-124417-3 | PASS | 1.00 | 1.00 | $0.195 | 12 | 86 s | 9/9 | 10/10 | 2/2 | 7,949 | 302,595 | 33,893 |

## effort-high

A-v1 with `--effort high`.

| Run | Result | Repair | Impact | Cost | Requests | Time | Incident | Regr. | Compat | Output | Cache read | Cache write |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 20261126-124845-1 | PASS | 1.00 | 1.00 | $0.357 | 19 | 164 s | 9/9 | 10/10 | 2/2 | 15,238 | 727,976 | 52,847 |
| 20261126-124845-2 | PASS | 1.00 | 1.00 | $0.372 | 15 | 180 s | 9/9 | 10/10 | 2/2 | 17,572 | 578,504 | 55,211 |
| 20261126-124845-3 | PASS | 1.00 | 1.00 | $0.346 | 17 | 164 s | 9/9 | 10/10 | 2/2 | 15,581 | 606,088 | 51,912 |

## effort-low

A-v1 with `--effort low`.

| Run | Result | Repair | Impact | Cost | Requests | Time | Incident | Regr. | Compat | Output | Cache read | Cache write |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 20261126-122138-1 | FAIL | 1.00 | 0.73 | $0.159 | 11 | 75 s | 9/9 | 10/10 | 2/2 | 6,046 | 233,982 | 29,871 |
| 20261126-122138-2 | PASS | 1.00 | 1.00 | $0.159 | 11 | 79 s | 9/9 | 10/10 | 2/2 | 6,307 | 234,882 | 29,059 |
| 20261126-122138-3 | FAIL | 1.00 | 0.73 | $0.174 | 10 | 74 s | 9/9 | 10/10 | 2/2 | 6,260 | 238,250 | 35,165 |

Failures:
- 20261126-122138-1: impact figures 2/6 right, precision 1.0, recall 1.0
- 20261126-122138-3: impact figures 2/6 right, precision 1.0, recall 1.0

## haiku

A-v1 with `claude-haiku-5-5` for the whole session (effort medium).

| Run | Result | Repair | Impact | Cost | Requests | Time | Incident | Regr. | Compat | Output | Cache read | Cache write |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 20261126-122547-1 | PASS | 1.00 | 1.00 | $0.064 | 33 | 328 s | 9/9 | 10/10 | 2/2 | 56,362 | 2,191,031 | 109,549 |
| 20261126-122547-2 | PASS | 1.00 | 1.00 | $0.054 | 25 | 324 s | 9/9 | 10/10 | 2/2 | 54,436 | 1,550,705 | 92,193 |
| 20261126-122547-3 | PASS | 1.00 | 1.00 | $0.083 | 34 | 439 s | 9/9 | 10/10 | 2/2 | 81,334 | 2,652,374 | 127,999 |

## A-v2

A-v1 plus one sentence in the report skill about what each figure adds up over (commit 8a70799).

| Run | Result | Repair | Impact | Cost | Requests | Time | Incident | Regr. | Compat | Output | Cache read | Cache write |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 20261126-135202-1 | PASS | 1.00 | 1.00 | $0.232 | 12 | 106 s | 9/9 | 10/10 | 2/2 | 9,190 | 324,969 | 42,889 |
| 20261126-135202-2 | PASS | 1.00 | 1.00 | $0.223 | 11 | 107 s | 9/9 | 10/10 | 2/2 | 10,178 | 291,040 | 36,689 |
| 20261126-135202-3 | PASS | 1.00 | 1.00 | $0.212 | 11 | 101 s | 9/9 | 10/10 | 2/2 | 8,890 | 303,262 | 37,218 |

## A-v2-low

A-v2 with `--effort low`.

| Run | Result | Repair | Impact | Cost | Requests | Time | Incident | Regr. | Compat | Output | Cache read | Cache write |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 20261126-135737-1 | FAIL | 1.00 | 0.73 | $0.173 | 12 | 83 s | 9/9 | 10/10 | 2/2 | 6,988 | 260,447 | 30,675 |
| 20261126-135737-2 | PASS | 1.00 | 1.00 | $0.198 | 13 | 95 s | 9/9 | 10/10 | 2/2 | 8,934 | 288,166 | 31,869 |
| 20261126-135737-3 | PASS | 1.00 | 1.00 | $0.186 | 12 | 96 s | 9/9 | 10/10 | 2/2 | 8,343 | 259,121 | 30,589 |

Failures:
- 20261126-135737-1: impact figures 2/6 right, precision 1.0, recall 1.0

## haiku-low

A-v2 with `claude-haiku-5-5` and `--effort low`.

| Run | Result | Repair | Impact | Cost | Requests | Time | Incident | Regr. | Compat | Output | Cache read | Cache write |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 20261126-140231-1 | PASS | 1.00 | 1.00 | $0.058 | 36 | 306 s | 9/9 | 10/10 | 2/2 | 49,298 | 2,126,693 | 92,895 |
| 20261126-140231-2 | FAIL | 0.89 | 1.00 | $0.041 | 27 | 249 s | 8/9 | 10/10 | 2/2 | 34,903 | 1,499,313 | 71,652 |
| 20261126-140231-3 | PASS | 1.00 | 1.00 | $0.036 | 23 | 232 s | 9/9 | 10/10 | 2/2 | 35,714 | 1,042,003 | 65,247 |

Failures:
- 20261126-140231-2: [incident] a repeat that is being sent when the release is replaced is not retried

## A-v2-emptyhome

A-v2 with HOME pointed at an empty directory, as in the grader.

| Run | Result | Repair | Impact | Cost | Requests | Time | Incident | Regr. | Compat | Output | Cache read | Cache write |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 20261126-141558-1 | PASS | 1.00 | 1.00 | $0.210 | 10 | 101 s | 9/9 | 10/10 | 2/2 | 8,075 | 262,449 | 41,274 |

## A-v3

After the independent review (commit 94f7d88): bounded run.sh, skippable contract checks, reworded skills.

| Run | Result | Repair | Impact | Cost | Requests | Time | Incident | Regr. | Compat | Output | Cache read | Cache write |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 20261126-143532-1 | FAIL | 1.00 | 0.57 | $0.258 | 14 | 111 s | 9/9 | 10/10 | 2/2 | 10,183 | 427,251 | 45,413 |
| 20261126-143532-2 | PASS | 1.00 | 1.00 | $0.188 | 10 | 88 s | 9/9 | 10/10 | 2/2 | 7,876 | 236,974 | 34,321 |
| 20261126-143532-3 | PASS | 1.00 | 1.00 | $0.205 | 12 | 98 s | 9/9 | 10/10 | 2/2 | 8,581 | 328,209 | 34,674 |
| 20261126-143532-4 | PASS | 1.00 | 1.00 | $0.223 | 13 | 102 s | 9/9 | 10/10 | 2/2 | 8,714 | 376,942 | 39,157 |
| 20261126-143532-5 | PASS | 1.00 | 1.00 | $0.192 | 9 | 89 s | 9/9 | 10/10 | 2/2 | 7,994 | 220,967 | 35,856 |

Failures:
- 20261126-143532-1: impact figures 6/6 right, precision 0.283, recall 0.283

## A-v4

A-v3 plus the report rule on missing facts and no advertised check skipping (commit c39352d). The submitted default.

| Run | Result | Repair | Impact | Cost | Requests | Time | Incident | Regr. | Compat | Output | Cache read | Cache write |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 20261126-145135-1 | PASS | 1.00 | 1.00 | $0.215 | 12 | 91 s | 9/9 | 10/10 | 2/2 | 8,539 | 299,030 | 39,698 |
| 20261126-145135-2 | PASS | 1.00 | 1.00 | $0.195 | 11 | 87 s | 9/9 | 10/10 | 2/2 | 7,598 | 290,747 | 35,960 |
| 20261126-145135-3 | PASS | 1.00 | 1.00 | $0.195 | 13 | 89 s | 9/9 | 10/10 | 2/2 | 7,680 | 335,857 | 33,924 |
| 20261126-145135-4 | PASS | 1.00 | 1.00 | $0.188 | 11 | 83 s | 9/9 | 10/10 | 2/2 | 7,594 | 274,534 | 33,956 |
| 20261126-145135-5 | PASS | 1.00 | 1.00 | $0.193 | 11 | 90 s | 9/9 | 10/10 | 2/2 | 7,625 | 271,143 | 35,700 |

## split-haiku-report

A-v4 with the report written by `claude-haiku-5-5` in parallel while Sonnet only repairs.

| Run | Result | Repair | Impact | Cost | Requests | Time | Incident | Regr. | Compat | Output | Cache read | Cache write |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 20261126-145927-1 | PASS | 1.00 | 1.00 | $0.191 | 21 | 82 s | 9/9 | 10/10 | 2/2 | 17,836 | 428,140 | 63,224 |
| 20261126-145927-2 | PASS | 1.00 | 1.00 | $0.196 | 24 | 96 s | 9/9 | 10/10 | 2/2 | 24,235 | 545,317 | 65,150 |
| 20261126-145927-3 | PASS | 1.00 | 1.00 | $0.202 | 25 | 103 s | 9/9 | 10/10 | 2/2 | 26,372 | 632,542 | 75,198 |

## haiku-main-sonnet-rescue

A-v4 with `claude-haiku-5-5` as the main agent and Sonnet only if the gate fails.

| Run | Result | Repair | Impact | Cost | Requests | Time | Incident | Regr. | Compat | Output | Cache read | Cache write |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 20261126-150427-1 | PASS | 1.00 | 1.00 | $0.147 | 46 | 458 s | 9/9 | 10/10 | 2/2 | 59,437 | 2,638,957 | 116,419 |
| 20261126-150427-2 | PASS | 1.00 | 1.00 | $0.048 | 23 | 268 s | 9/9 | 10/10 | 2/2 | 47,583 | 1,252,135 | 91,524 |
| 20261126-150427-3 | PASS | 1.00 | 1.00 | $0.085 | 44 | 398 s | 9/9 | 10/10 | 2/2 | 71,850 | 3,437,826 | 118,260 |

## codex-luna

A-v4 with Codex and `gpt-6-luna` for the whole session (run on the Mac).

| Run | Result | Repair | Impact | Cost | Requests | Time | Incident | Regr. | Compat | Output | Cache read | Cache write |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| mac-20261126-160840-1 | FAIL | 0.44 | 1.00 | $0.010 | 12 | 111 s | 4/9 | 10/10 | 2/2 | 3,201 | 372,224 | 0 |

## codex-terra

A-v4 with Codex and `gpt-6.1-terra` for the whole session (run on the Mac).

| Run | Result | Repair | Impact | Cost | Requests | Time | Incident | Regr. | Compat | Output | Cache read | Cache write |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| mac-20261126-161259-1 | PASS | 1.00 | 1.00 | $0.121 | 14 | 140 s | 9/9 | 10/10 | 2/2 | 4,749 | 523,648 | 0 |
| mac-20261126-161259-2 | PASS | 1.00 | 1.00 | $0.083 | 13 | 139 s | 9/9 | 10/10 | 2/2 | 4,551 | 501,632 | 0 |

## A-v5

A-v4 plus the hand-over check in the gate, random port choice and one prompt sentence (commit 4450fb7).

| Run | Result | Repair | Impact | Cost | Requests | Time | Incident | Regr. | Compat | Output | Cache read | Cache write |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 20261126-152520-1 | PASS | 1.00 | 1.00 | $0.242 | 13 | 102 s | 9/9 | 10/10 | 2/2 | 9,416 | 373,069 | 44,173 |
| 20261126-152520-2 | PASS | 1.00 | 1.00 | $0.206 | 11 | 95 s | 9/9 | 10/10 | 2/2 | 8,892 | 279,595 | 35,438 |
| 20261126-152520-3 | PASS | 1.00 | 1.00 | $0.242 | 12 | 107 s | 9/9 | 10/10 | 2/2 | 9,651 | 376,912 | 43,277 |

## from-zip

A-v5 plus the flag fallback, run from an unpacked copy of the submission zip.

| Run | Result | Repair | Impact | Cost | Requests | Time | Incident | Regr. | Compat | Output | Cache read | Cache write |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 20261126-155525-1 | PASS | 1.00 | 1.00 | $0.250 | 13 | 116 s | 9/9 | 10/10 | 2/2 | 9,891 | 382,250 | 45,171 |
| mac-20261126-173232-1 | PASS | 1.00 | 1.00 | $0.239 | 14 | 136 s | 9/9 | 10/10 | 2/2 | 9,342 | 421,472 | 41,279 |

## codex-terra-v5

A-v5 with Codex and `gpt-6.1-terra` for the whole session (Mac).

| Run | Result | Repair | Impact | Cost | Requests | Time | Incident | Regr. | Compat | Output | Cache read | Cache write |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| mac-20261126-163225-1 | PASS | 1.00 | 1.00 | $0.110 | 20 | 187 s | 9/9 | 10/10 | 2/2 | 5,508 | 831,104 | 0 |
| mac-20261126-163225-2 | PASS | 1.00 | 1.00 | $0.089 | 13 | 150 s | 9/9 | 10/10 | 2/2 | 5,287 | 508,160 | 0 |
| mac-20261126-163225-3 | PASS | 1.00 | 1.00 | $0.105 | 14 | 171 s | 9/9 | 10/10 | 2/2 | 5,895 | 548,480 | 0 |

## codex-luna-v5

A-v5 with Codex and `gpt-6-luna` for the whole session (Mac).

| Run | Result | Repair | Impact | Cost | Requests | Time | Incident | Regr. | Compat | Output | Cache read | Cache write |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| mac-20261126-164114-1 | PASS | 1.00 | 1.00 | $0.023 | 29 | 282 s | 9/9 | 10/10 | 2/2 | 9,299 | 1,293,824 | 0 |
| mac-20261126-164114-2 | FAIL | 0.44 | 1.00 | $0.035 | 46 | 375 s | 4/9 | 10/10 | 2/2 | 11,675 | 2,253,056 | 0 |

## sonnet-main-terra-rescue

Sonnet as the main agent and `gpt-6.1-terra` (Codex) only if the gate fails, on the Mac's Claude Code 2.1.284.

| Run | Result | Repair | Impact | Cost | Requests | Time | Incident | Regr. | Compat | Output | Cache read | Cache write |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| mac-20261126-170838-1 | PASS | 1.00 | 1.00 | $0.236 | 14 | 125 s | 9/9 | 10/10 | 2/2 | 8,803 | 409,603 | 42,802 |
| mac-20261126-170838-2 | PASS | 1.00 | 1.00 | $0.312 | 17 | 173 s | 9/9 | 10/10 | 2/2 | 12,881 | 609,442 | 48,842 |

## forced-rescue-terra

Rescue path exercised on purpose: the main agent names a model that does not exist, so `gpt-6.1-terra` gets the whole job (Mac).

| Run | Result | Repair | Impact | Cost | Requests | Time | Incident | Regr. | Compat | Output | Cache read | Cache write |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| mac-20261126-171351-1 | PASS | 1.00 | 1.00 | $0.105 | 18 | 185 s | 9/9 | 10/10 | 2/2 | 5,725 | 757,632 | 0 |
| mac-20261126-171857-1 | PASS | 1.00 | 1.00 | $0.094 | 16 | 175 s | 9/9 | 10/10 | 2/2 | 5,385 | 636,416 | 0 |

## terra-main-sonnet-rescue

`gpt-6.1-terra` (Codex) as the main agent and Sonnet only if the gate fails (Mac).

| Run | Result | Repair | Impact | Cost | Requests | Time | Incident | Regr. | Compat | Output | Cache read | Cache write |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| mac-20261126-172200-1 | PASS | 1.00 | 1.00 | $0.094 | 15 | 157 s | 9/9 | 10/10 | 2/2 | 5,217 | 615,680 | 0 |
| mac-20261126-172200-2 | PASS | 1.00 | 1.00 | $0.097 | 17 | 157 s | 9/9 | 10/10 | 2/2 | 5,273 | 684,544 | 0 |

## v2-sonnet-plus-sonnet-low

After submission 1 (commit a26d96f): gate that blocks only on objective failures, attempt and lease tables, two solvers at once (Sonnet medium here, Sonnet low in a copy), cross-check, follow-ups only when a run fails or the reports differ.

| Run | Result | Repair | Impact | Cost | Requests | Time | Incident | Regr. | Compat | Output | Cache read | Cache write |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 20261126-195529-1 | PASS | 1.00 | 1.00 | $0.466 | 24 | 107 s | 9/9 | 10/10 | 2/2 | 18,375 | 672,747 | 85,820 |
| 20261126-195529-2 | PASS | 1.00 | 1.00 | $0.356 | 24 | 74 s | 9/9 | 10/10 | 2/2 | 13,684 | 586,449 | 64,235 |

## v2-sonnet-terra

The same with `gpt-6.1-terra` (Codex) as the second solver, on the Mac (commit 9466643). No follow-up was needed in either run.

| Run | Result | Repair | Impact | Cost | Requests | Time | Incident | Regr. | Compat | Output | Cache read | Cache write |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| mac-20261126-212646-1 | PASS | 1.00 | 1.00 | $0.330 | 27 | 168 s | 9/9 | 10/10 | 2/2 | 14,043 | 935,231 | 44,972 |
| mac-20261126-212646-2 | PASS | 1.00 | 1.00 | $0.388 | 30 | 191 s | 9/9 | 10/10 | 2/2 | 17,621 | 1,141,861 | 48,464 |

## v2-haiku-low-plus-sonnet

The same with a weak main solver on purpose (Haiku, effort low) and Sonnet as the second, to see a follow-up fire (commit 9466643).

| Run | Result | Repair | Impact | Cost | Requests | Time | Incident | Regr. | Compat | Output | Cache read | Cache write |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 20261126-202646-1 | PASS | 1.00 | 1.00 | $0.277 | 56 | 348 s | 9/9 | 10/10 | 2/2 | 60,028 | 3,393,695 | 142,140 |
| 20261126-202646-2 | PASS | 1.00 | 1.00 | $0.217 | 33 | 213 s | 9/9 | 10/10 | 2/2 | 33,672 | 1,501,927 | 103,855 |

## v2b-judge-exercise

Sonnet main; a stand-in second solver hands in the main solver's report minus three entries, so the report decision (Sonnet, effort high) runs with a real model (commit 66c9cc4).

| Run | Result | Repair | Impact | Cost | Requests | Time | Incident | Regr. | Compat | Output | Cache read | Cache write |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 20261126-203900-1 | PASS | 1.00 | 1.00 | $0.365 | 22 | 156 s | 9/9 | 10/10 | 2/2 | 15,382 | 487,020 | 64,862 |

## v2c-sonnet-plus-haiku

Comparison session after every cross-check, kept only if no worse; one prompt sentence on every way into the defect; Sonnet main, Haiku medium second (commit 65eb375). Run 1 used both follow-ups.

| Run | Result | Repair | Impact | Cost | Requests | Time | Incident | Regr. | Compat | Output | Cache read | Cache write |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 20261126-204327-1 | PASS | 1.00 | 1.00 | $0.475 | 43 | 308 s | 9/9 | 10/10 | 2/2 | 61,262 | 1,766,990 | 159,483 |
| 20261126-204327-2 | PASS | 1.00 | 1.00 | $0.315 | 44 | 290 s | 9/9 | 10/10 | 2/2 | 52,472 | 2,035,730 | 123,928 |

## v2e-zip-sonnet-low

A later zip (commit 8a6fdb5: failing runs saved as replayable files), unpacked, with Sonnet at effort low as the second solver so that every step runs here. The comparison session ran in both runs.

| Run | Result | Repair | Impact | Cost | Requests | Time | Incident | Regr. | Compat | Output | Cache read | Cache write |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 20261126-210551-1 | PASS | 1.00 | 1.00 | $0.476 | 30 | 229 s | 9/9 | 10/10 | 2/2 | 18,997 | 897,181 | 78,283 |
| 20261126-210551-2 | PASS | 1.00 | 1.00 | $0.469 | 25 | 207 s | 9/9 | 10/10 | 2/2 | 18,903 | 729,862 | 82,661 |

## v2f-zip-sonnet-low

The zip for submission 2 (commit 54cab27: the main session always does the comparison, the better repair is chosen after it; spending lines 0.64 and 0.70), unpacked, Sonnet at effort low as the second solver.

| Run | Result | Repair | Impact | Cost | Requests | Time | Incident | Regr. | Compat | Output | Cache read | Cache write |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 20261126-211406-1 | PASS | 1.00 | 1.00 | $0.548 | 33 | 195 s | 9/9 | 10/10 | 2/2 | 22,083 | 1,060,412 | 88,289 |
| 20261126-211406-2 | PASS | 1.00 | 1.00 | $0.469 | 27 | 186 s | 9/9 | 10/10 | 2/2 | 17,958 | 812,929 | 83,242 |

## v2g-sonnet-terra

The submitted pairing at the commit of the zip for submission 2 (51ef415), on the Mac with nothing set: Sonnet main, `gpt-6.1-terra` (Codex) second, comparison session in every run.

| Run | Result | Repair | Impact | Cost | Requests | Time | Incident | Regr. | Compat | Output | Cache read | Cache write |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| mac-20261127-092216-1 | PASS | 1.00 | 1.00 | $0.434 | 34 | 274 s | 9/9 | 10/10 | 2/2 | 19,276 | 1,366,263 | 54,210 |
| mac-20261127-092216-2 | PASS | 1.00 | 1.00 | $0.509 | 40 | 309 s | 9/9 | 10/10 | 2/2 | 21,128 | 1,542,977 | 54,612 |

## v3a-budget

First budget-aware version: kit/budget.py, one message to a solver that stops with its share unused, follow-ups at effort high when affordable (dev tree, before commit 77a8706). Sonnet main, Sonnet low second.

| Run | Result | Repair | Impact | Cost | Requests | Time | Incident | Regr. | Compat | Output | Cache read | Cache write |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 20261127-083019-1 | PASS | 1.00 | 1.00 | $0.532 | 30 | 198 s | 9/9 | 10/10 | 2/2 | 20,894 | 905,457 | 93,089 |
| 20261127-083019-2 | PASS | 1.00 | 1.00 | $0.451 | 27 | 188 s | 9/9 | 10/10 | 2/2 | 17,335 | 797,913 | 79,059 |

## v3b-budget

Commit 77a8706: the stop hook persists on hard failures and open ledger lines while budget remains; finish round; cross-check counts a scenario that only the other repair passes. Sonnet main, Sonnet low second.

| Run | Result | Repair | Impact | Cost | Requests | Time | Incident | Regr. | Compat | Output | Cache read | Cache write |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 20261127-084616-1 | PASS | 1.00 | 1.00 | $0.527 | 34 | 272 s | 9/9 | 10/10 | 2/2 | 20,839 | 1,068,387 | 84,690 |
| 20261127-084616-2 | PASS | 1.00 | 1.00 | $0.519 | 32 | 209 s | 9/9 | 10/10 | 2/2 | 19,700 | 1,021,457 | 87,753 |

## v3-budget-sonnet-terra

Commit 77a8706 with the real pairing on the Mac. The second solver's repair was installed in both runs on a count of failures; fixed in the next commit.

| Run | Result | Repair | Impact | Cost | Requests | Time | Incident | Regr. | Compat | Output | Cache read | Cache write |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| mac-20261127-094617-1 | PASS | 1.00 | 1.00 | $0.612 | 51 | 435 s | 9/9 | 10/10 | 2/2 | 27,757 | 2,354,639 | 63,854 |
| mac-20261127-094617-2 | PASS | 1.00 | 1.00 | $0.529 | 42 | 379 s | 9/9 | 10/10 | 2/2 | 24,136 | 1,835,032 | 59,981 |

## v3c-budget

Commit 7bfe15c: budget messages follow the agent's own open items; private bus formats left out of the comparison; the main repair stands unless the other is objectively better. Sonnet main, Sonnet low second.

| Run | Result | Repair | Impact | Cost | Requests | Time | Incident | Regr. | Compat | Output | Cache read | Cache write |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 20261127-090318-1 | PASS | 1.00 | 1.00 | $0.530 | 29 | 236 s | 9/9 | 10/10 | 2/2 | 20,167 | 937,449 | 93,856 |
| 20261127-090318-2 | PASS | 1.00 | 1.00 | $0.522 | 34 | 230 s | 9/9 | 10/10 | 2/2 | 20,444 | 1,068,324 | 84,272 |

## v3c-budget-sonnet-terra

Commit 7bfe15c with the real pairing on the Mac.

| Run | Result | Repair | Impact | Cost | Requests | Time | Incident | Regr. | Compat | Output | Cache read | Cache write |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| mac-20261127-100319-1 | PASS | 1.00 | 1.00 | $0.467 | 38 | 370 s | 9/9 | 10/10 | 2/2 | 21,784 | 1,555,098 | 52,664 |
| mac-20261127-100319-2 | PASS | 1.00 | 1.00 | $0.536 | 42 | 362 s | 9/9 | 10/10 | 2/2 | 24,585 | 1,871,478 | 58,233 |

## rep-new-starter

Report only (KIT_VARIANT=report), rewritten report skill (commit 0e0854c): one Sonnet session answers the report request and nothing else. Repair is 0 by construction.

| Run | Result | Repair | Impact | Cost | Requests | Time | Incident | Regr. | Compat | Output | Cache read | Cache write |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 20261127-093023-1 | FAIL | 0.00 | 1.00 | $0.073 | 7 | 32 s | 0/9 | 10/10 | 2/2 | 3,105 | 88,842 | 13,091 |
| 20261127-093023-2 | FAIL | 0.00 | 1.00 | $0.081 | 7 | 34 s | 0/9 | 10/10 | 2/2 | 3,539 | 94,268 | 14,602 |
| 20261127-093023-3 | FAIL | 0.00 | 1.00 | $0.074 | 6 | 31 s | 0/9 | 10/10 | 2/2 | 3,239 | 74,890 | 13,720 |
| 20261127-093023-4 | FAIL | 0.00 | 1.00 | $0.069 | 6 | 30 s | 0/9 | 10/10 | 2/2 | 2,928 | 72,438 | 12,787 |

Failures:
- 20261127-093023-1: [incident] a payment sent again after the api stopped before answering is one event
- 20261127-093023-1: [incident] a payment sent again after an api restart is one event
- 20261127-093023-1: [incident] a payment sent again after the api stopped while publishing is one event
- 20261127-093023-1: [incident] a payment sent again two hours after an api restart is one event
- 20261127-093023-1: [incident] a repeat the deployed release queued for a retry is not sent once the release is replaced
- 20261127-093023-1: [incident] a repeat whose original was delivered is never sent
- 20261127-093023-1: [incident] repeats of several payments are each stopped
- 20261127-093023-1: [incident] a repeat that is being sent when the release is replaced is not retried
- 20261127-093023-1: [incident] starting the replaced release twice stops nothing more
- 20261127-093023-2: [incident] a payment sent again after the api stopped before answering is one event
- 20261127-093023-2: [incident] a payment sent again after an api restart is one event
- 20261127-093023-2: [incident] a payment sent again after the api stopped while publishing is one event
- 20261127-093023-2: [incident] a payment sent again two hours after an api restart is one event
- 20261127-093023-2: [incident] a repeat the deployed release queued for a retry is not sent once the release is replaced
- 20261127-093023-2: [incident] a repeat whose original was delivered is never sent
- 20261127-093023-2: [incident] repeats of several payments are each stopped
- 20261127-093023-2: [incident] a repeat that is being sent when the release is replaced is not retried
- 20261127-093023-2: [incident] starting the replaced release twice stops nothing more
- 20261127-093023-3: [incident] a payment sent again after the api stopped before answering is one event
- 20261127-093023-3: [incident] a payment sent again after an api restart is one event
- 20261127-093023-3: [incident] a payment sent again after the api stopped while publishing is one event
- 20261127-093023-3: [incident] a payment sent again two hours after an api restart is one event
- 20261127-093023-3: [incident] a repeat the deployed release queued for a retry is not sent once the release is replaced
- 20261127-093023-3: [incident] a repeat whose original was delivered is never sent
- 20261127-093023-3: [incident] repeats of several payments are each stopped
- 20261127-093023-3: [incident] a repeat that is being sent when the release is replaced is not retried
- 20261127-093023-3: [incident] starting the replaced release twice stops nothing more
- 20261127-093023-4: [incident] a payment sent again after the api stopped before answering is one event
- 20261127-093023-4: [incident] a payment sent again after an api restart is one event
- 20261127-093023-4: [incident] a payment sent again after the api stopped while publishing is one event
- 20261127-093023-4: [incident] a payment sent again two hours after an api restart is one event
- 20261127-093023-4: [incident] a repeat the deployed release queued for a retry is not sent once the release is replaced
- 20261127-093023-4: [incident] a repeat whose original was delivered is never sent
- 20261127-093023-4: [incident] repeats of several payments are each stopped
- 20261127-093023-4: [incident] a repeat that is being sent when the release is replaced is not retried
- 20261127-093023-4: [incident] starting the replaced release twice stops nothing more

## v3d-budget-sonnet-terra

Commit 0e0854c, the zip for submission 2, with the real pairing on the Mac.

| Run | Result | Repair | Impact | Cost | Requests | Time | Incident | Regr. | Compat | Output | Cache read | Cache write |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| mac-20261127-103337-1 | PASS | 1.00 | 1.00 | $0.443 | 41 | 344 s | 9/9 | 10/10 | 2/2 | 20,431 | 1,676,146 | 48,104 |

## v4-haiku-haiku

After submission 2 (commit 92c089b): tolerant workspace copy, fallback solvers, a third session that derives the report from the raw files. Haiku as second solver and for the raw-file report.

| Run | Result | Repair | Impact | Cost | Requests | Time | Incident | Regr. | Compat | Output | Cache read | Cache write |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 20261127-110945-1 | PASS | 1.00 | 1.00 | $0.369 | 57 | 358 s | 9/9 | 10/10 | 2/2 | 60,446 | 2,080,118 | 148,587 |
| 20261127-110945-2 | PASS | 1.00 | 1.00 | $0.382 | 55 | 286 s | 9/9 | 10/10 | 2/2 | 67,561 | 2,121,346 | 159,913 |

## v4b-haiku-sonnetlow

Commit e0b42c6: reports compared part by part. Haiku as second solver, Sonnet at effort low for the raw-file report.

| Run | Result | Repair | Impact | Cost | Requests | Time | Incident | Regr. | Compat | Output | Cache read | Cache write |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 20261127-113307-1 | PASS | 1.00 | 1.00 | $0.467 | 43 | 203 s | 9/9 | 10/10 | 2/2 | 30,242 | 1,172,759 | 103,381 |

## raw-sonnetlow-starter

Only the raw-file report session (KIT_VARIANT=raw-report), Sonnet at effort low. Repair is 0 by construction.

| Run | Result | Repair | Impact | Cost | Requests | Time | Incident | Regr. | Compat | Output | Cache read | Cache write |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 20261127-112822-1 | FAIL | 0.00 | 0.93 | $0.254 | 13 | 82 s | 0/9 | 10/10 | 2/2 | 8,653 | 374,924 | 51,819 |

Failures:
- 20261127-112822-1: [incident] a payment sent again after the api stopped before answering is one event
- 20261127-112822-1: [incident] a payment sent again after an api restart is one event
- 20261127-112822-1: [incident] a payment sent again after the api stopped while publishing is one event
- 20261127-112822-1: [incident] a payment sent again two hours after an api restart is one event
- 20261127-112822-1: [incident] a repeat the deployed release queued for a retry is not sent once the release is replaced
- 20261127-112822-1: [incident] a repeat whose original was delivered is never sent
- 20261127-112822-1: [incident] repeats of several payments are each stopped
- 20261127-112822-1: [incident] a repeat that is being sent when the release is replaced is not retried
- 20261127-112822-1: [incident] starting the replaced release twice stops nothing more
- 20261127-112822-1: impact figures 5/6 right, precision 1.0, recall 1.0

## v2d-from-zip

The zip for submission 2, unpacked, nothing set (commit b407568). No Codex in the container, so the second solver cannot start: the run shows that case.

| Run | Result | Repair | Impact | Cost | Requests | Time | Incident | Regr. | Compat | Output | Cache read | Cache write |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 20261126-210148-1 | PASS | 1.00 | 1.00 | $0.243 | 13 | 113 s | 9/9 | 10/10 | 2/2 | 8,859 | 381,754 | 46,394 |

## v4-sonnet-terra-terra



| Run | Result | Repair | Impact | Cost | Requests | Time | Incident | Regr. | Compat | Output | Cache read | Cache write |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| mac-20261127-120946-1 | PASS | 1.00 | 1.00 | $0.655 | 60 | 388 s | 9/9 | 10/10 | 2/2 | 30,155 | 2,542,394 | 58,622 |

## Other incidents (INC-2231, INC-2307, INC-2318)

Incidents built to test the setup on tickets it was not designed around; see
`transfer/README.md` and each folder's `NOTES.md`. Scored by each incident's `judge.py` with the
assignment's formulas. Labels without an incident number are INC-2231. `rep-` labels are
report-only runs with the kit and `raw-` report-only runs from the raw files (repair 0 by
construction in both); `terse-` are tickets with the recovery requirement cut to half a
sentence, run with one Sonnet session; `sub1-` is the first submission's version;
`v2zip-` the two-solver version of 2026-11-26; `v3c-`/`v3d-` the budget-aware versions.

| Setup | Run | Result | Repair | Impact | Cost | Requests | Time | Incident | Regr. | Compat |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| baseline | 20261126-153950-1 | PASS | 1.0 | 1.0 | $1.592 | 40 | 405 s | 9/9 | 9/9 | 4/4 |
| baseline | 20261126-153950-2 | PASS | 1.0 | 1.0 | $1.023 | 27 | 249 s | 9/9 | 9/9 | 4/4 |
| codex-luna | 20261126-170021-1 | PASS | 1.0 | 1.0 | $0.029 | 23 | 481 s | 9/9 | 9/9 | 4/4 |
| codex-terra | 20261126-165400-1 | PASS | 1.0 | 1.0 | $0.110 | 19 | 183 s | 9/9 | 9/9 | 4/4 |
| codex-terra | 20261126-165400-2 | PASS | 1.0 | 1.0 | $0.147 | 21 | 186 s | 9/9 | 9/9 | 4/4 |
| raw-haiku-2231 | 20261127-112336-1 | FAIL | 0.0 | 0.0 | $0.038 | 21 | 221 s | 0/9 | 9/9 | 4/4 |
| raw-haiku-2307 | 20261127-112336-1 | FAIL | 0.0 | 0.0 | $0.046 | 26 | 221 s | 0/19 | 21/21 | 6/6 |
| raw-haiku-2318 | 20261127-112336-1 | FAIL | 0.0 | 0.96 | $0.049 | 25 | 221 s | 0/19 | 19/19 | 6/6 |
| raw-sonnet-2231 | 20261127-112336-1 | FAIL | 0.0 | 0.9429 | $0.197 | 10 | 79 s | 0/9 | 9/9 | 4/4 |
| raw-sonnet-2307 | 20261127-112336-1 | FAIL | 0.0 | 1.0 | $0.230 | 11 | 88 s | 0/19 | 21/21 | 6/6 |
| raw-sonnet-2318 | 20261127-112337-1 | FAIL | 0.0 | 1.0 | $0.180 | 13 | 69 s | 0/19 | 19/19 | 6/6 |
| raw-sonnetlow-2231 | 20261127-112822-1 | FAIL | 0.0 | 0.9429 | $0.237 | 17 | 91 s | 0/9 | 9/9 | 4/4 |
| raw-sonnetlow-2307 | 20261127-112822-1 | FAIL | 0.0 | 1.0 | $0.210 | 12 | 79 s | 0/19 | 21/21 | 6/6 |
| raw-sonnetlow-2318 | 20261127-112822-1 | FAIL | 0.0 | 1.0 | $0.172 | 15 | 70 s | 0/19 | 19/19 | 6/6 |
| rep-new-2231 | 20261127-092755-1 | FAIL | 0.0 | 1.0 | $0.072 | 5 | 27 s | 0/9 | 9/9 | 4/4 |
| rep-new-2231 | 20261127-092755-2 | FAIL | 0.0 | 1.0 | $0.081 | 6 | 33 s | 0/9 | 9/9 | 4/4 |
| rep-new-2307 | 20261127-092755-1 | FAIL | 0.0 | 1.0 | $0.094 | 6 | 41 s | 0/19 | 21/21 | 6/6 |
| rep-new-2307 | 20261127-092755-2 | FAIL | 0.0 | 1.0 | $0.087 | 6 | 31 s | 0/19 | 21/21 | 6/6 |
| rep-new-2307 | 20261127-092755-3 | FAIL | 0.0 | 1.0 | $0.081 | 5 | 29 s | 0/19 | 21/21 | 6/6 |
| rep-new-2318 | 20261127-092755-1 | FAIL | 0.0 | 1.0 | $0.081 | 6 | 28 s | 0/19 | 19/19 | 6/6 |
| rep-new-2318 | 20261127-092755-2 | FAIL | 0.0 | 1.0 | $0.072 | 5 | 24 s | 0/19 | 19/19 | 6/6 |
| rep-old-2307 | 20261127-092755-1 | FAIL | 0.0 | 0.6222 | $0.061 | 6 | 24 s | 0/19 | 21/21 | 6/6 |
| rep-old-2307 | 20261127-092755-2 | FAIL | 0.0 | 0.6222 | $0.068 | 6 | 28 s | 0/19 | 21/21 | 6/6 |
| rep-old-2307 | 20261127-092755-3 | FAIL | 0.0 | 0.6222 | $0.075 | 6 | 27 s | 0/19 | 21/21 | 6/6 |
| sonnet-main-terra-rescue | 20261126-172727-1 | PASS | 1.0 | 1.0 | $0.413 | 23 | 250 s | 9/9 | 9/9 | 4/4 |
| sonnet-medium | 20261126-150246-1 | PASS | 1.0 | 1.0 | $0.364 | 25 | 179 s | 9/9 | 9/9 | 4/4 |
| sonnet-medium | 20261126-150246-2 | PASS | 1.0 | 1.0 | $0.270 | 14 | 136 s | 9/9 | 9/9 | 4/4 |
| sonnet-medium | 20261126-150246-3 | FAIL | 0.9231 | 1.0 | $0.281 | 19 | 187 s | 9/9 | 9/9 | 3/4 |
| sonnet-medium-v5 | 20261126-153044-1 | PASS | 1.0 | 1.0 | $0.448 | 28 | 234 s | 9/9 | 9/9 | 4/4 |
| sonnet-medium-v5 | 20261126-153044-2 | PASS | 1.0 | 1.0 | $0.265 | 18 | 150 s | 9/9 | 9/9 | 4/4 |
| sonnet-medium-v5 | 20261126-153044-3 | PASS | 1.0 | 1.0 | $0.300 | 19 | 146 s | 9/9 | 9/9 | 4/4 |
| sub1-2307 | 20261127-093346-1 | FAIL | 1.0 | 0.6222 | $0.262 | 13 | 141 s | 19/19 | 21/21 | 6/6 |
| sub1-2307 | 20261127-093346-2 | FAIL | 1.0 | 0.6222 | $0.199 | 10 | 105 s | 19/19 | 21/21 | 6/6 |
| sub1-2318 | 20261127-093346-1 | FAIL | 0.8232 | 1.0 | $0.635 | 31 | 381 s | 17/19 | 19/19 | 4/6 |
| sub1-2318 | 20261127-093346-2 | PASS | 1.0 | 1.0 | $0.598 | 32 | 363 s | 19/19 | 19/19 | 6/6 |
| terse-solo-2231 | 20261127-104602-1 | PASS | 1.0 | 1.0 | $0.439 | 20 | 199 s | 9/9 | 9/9 | 4/4 |
| terse-solo-2231 | 20261127-104602-2 | PASS | 1.0 | 1.0 | $0.365 | 23 | 184 s | 9/9 | 9/9 | 4/4 |
| terse-solo-2307 | 20261127-104602-1 | PASS | 1.0 | 1.0 | $0.471 | 24 | 244 s | 19/19 | 21/21 | 6/6 |
| terse-solo-2307 | 20261127-104602-2 | PASS | 1.0 | 1.0 | $0.393 | 24 | 219 s | 19/19 | 21/21 | 6/6 |
| terse-solo-2318 | 20261127-104602-1 | PASS | 1.0 | 1.0 | $0.577 | 20 | 300 s | 19/19 | 19/19 | 6/6 |
| terse-solo-2318 | 20261127-104602-2 | PASS | 1.0 | 1.0 | $0.500 | 20 | 251 s | 19/19 | 19/19 | 6/6 |
| v2-sonnet-plus-haiku | 20261126-195841-1 | PASS | 1.0 | 1.0 | $0.423 | 53 | 342 s | 9/9 | 9/9 | 4/4 |
| v2c-sonnet-plus-haiku | 20261126-204327-1 | PASS | 1.0 | 1.0 | $0.304 | 34 | 252 s | 9/9 | 9/9 | 4/4 |
| v2c-sonnet-plus-haiku | 20261126-204327-2 | PASS | 1.0 | 1.0 | $0.524 | 67 | 388 s | 9/9 | 9/9 | 4/4 |
| v2e-zip-sonnet-low | 20261126-210551-1 | PASS | 1.0 | 1.0 | $0.597 | 38 | 230 s | 9/9 | 9/9 | 4/4 |
| v2e-zip-sonnet-low | 20261126-210551-2 | PASS | 1.0 | 1.0 | $0.621 | 39 | 272 s | 9/9 | 9/9 | 4/4 |
| v2f-zip-sonnet-plus-haiku | 20261126-211406-1 | PASS | 1.0 | 1.0 | $0.524 | 51 | 463 s | 9/9 | 9/9 | 4/4 |
| v2f-zip-sonnet-plus-haiku | 20261126-211406-2 | PASS | 1.0 | 1.0 | $0.481 | 56 | 396 s | 9/9 | 9/9 | 4/4 |
| v2g-sonnet-terra | 20261127-093228-1 | PASS | 1.0 | 1.0 | $0.564 | 49 | 348 s | 9/9 | 9/9 | 4/4 |
| v2zip-2307-sonnet-low | 20261127-094633-1 | FAIL | 1.0 | 0.6222 | $0.616 | 34 | 303 s | 19/19 | 21/21 | 6/6 |
| v2zip-2307-sonnet-low | 20261127-094633-2 | FAIL | 1.0 | 0.6222 | $0.589 | 29 | 258 s | 19/19 | 21/21 | 6/6 |
| v2zip-2318-sonnet-low | 20261127-094633-1 | PASS | 1.0 | 1.0 | $0.856 | 41 | 326 s | 19/19 | 19/19 | 6/6 |
| v2zip-2318-sonnet-low | 20261127-094633-2 | PASS | 1.0 | 1.0 | $0.662 | 32 | 201 s | 19/19 | 19/19 | 6/6 |
| v3b-budget-sonnet-plus-haiku | 20261127-084616-1 | PASS | 1.0 | 1.0 | $0.386 | 37 | 272 s | 9/9 | 9/9 | 4/4 |
| v3b-budget-sonnet-plus-haiku | 20261127-084616-2 | PASS | 1.0 | 1.0 | $0.376 | 30 | 244 s | 9/9 | 9/9 | 4/4 |
| v3c-2307-sonnet-low | 20261127-091629-1 | FAIL | 1.0 | 0.6222 | $0.592 | 29 | 302 s | 19/19 | 21/21 | 6/6 |
| v3c-2307-sonnet-low | 20261127-091629-2 | PASS | 1.0 | 1.0 | $0.705 | 36 | 239 s | 19/19 | 21/21 | 6/6 |
| v3c-2307-sonnet-terra | 20261127-101630-1 | PASS | 1.0 | 1.0 | $0.674 | 48 | 368 s | 19/19 | 21/21 | 6/6 |
| v3c-2318-sonnet-low | 20261127-091629-1 | PASS | 1.0 | 1.0 | $0.786 | 37 | 244 s | 19/19 | 19/19 | 6/6 |
| v3c-2318-sonnet-low | 20261127-091629-2 | PASS | 1.0 | 1.0 | $0.779 | 39 | 221 s | 19/19 | 19/19 | 6/6 |
| v3c-2318-sonnet-terra | 20261127-102247-1 | PASS | 1.0 | 1.0 | $0.643 | 50 | 316 s | 19/19 | 19/19 | 6/6 |
| v3d-2231-sonnet-terra | 20261127-105117-1 | PASS | 1.0 | 1.0 | $0.649 | 55 | 385 s | 9/9 | 9/9 | 4/4 |
| v3d-2307-sonnet-terra | 20261127-103927-1 | PASS | 1.0 | 1.0 | $0.538 | 38 | 364 s | 19/19 | 21/21 | 6/6 |
| v3d-2318-sonnet-terra | 20261127-104554-1 | PASS | 1.0 | 1.0 | $0.689 | 44 | 314 s | 19/19 | 19/19 | 6/6 |
| v4-2231-haiku | 20261127-110945-1 | PASS | 1.0 | 1.0 | $0.562 | 74 | 378 s | 9/9 | 9/9 | 4/4 |
| v4-2318-haiku | 20261127-110945-1 | PASS | 1.0 | 1.0 | $0.588 | 61 | 412 s | 19/19 | 19/19 | 6/6 |
| v4b-2231 | 20261127-113307-1 | PASS | 1.0 | 1.0 | $0.559 | 45 | 282 s | 9/9 | 9/9 | 4/4 |
| v4b-2307 | 20261127-113307-1 | PASS | 1.0 | 1.0 | $0.713 | 46 | 267 s | 19/19 | 21/21 | 6/6 |

## Notes from reading the logs

- **Baseline.** Cache writes were billed at the 1-hour rate ($4.00/M), about 43% of each run. All
  three runs fixed the cause for new traffic. Two stopped there and failed the five scenarios in
  which the shipped release has already written repeats before it is replaced; the one that
  passed spent 570 s and hit the $2.00 cap. One run (101810-1) also named the wrong event of each
  pair in 19 of 33 key groups, after a log line (`event.repeated`) overrode the ticket's definition.
- **Flags only.** Same prompt as the baseline. Cost falls by about 65% from the flags alone:
  the base prompt drops from about 26k to about 6k tokens and every cache write is at the 5-minute
  rate. Correctness is still a coin flip on the same five scenarios (2 of 3 passed).
- **Option A, medium effort.** 13 of 13 pass across A-v1, nohook, A-v2 and the empty-home run.
  10 to 14 requests, all tool calls through Bash, context from about 10k to about 40k tokens.
  The stop hook never blocked and the resume never fired: the agent ran `kit/check.sh` itself.
  The ledger was written last and already ticked in the transcripts read, not first.
- **Effort.** High costs about 60% more for the same result. Low gets the report's totals wrong
  in 3 of 6 runs (it adds up per event where the ticket says per entry); the repair is right every
  time. The added sentence in the skill moved low effort from 1/3 to 2/3, which three runs cannot
  tell from noise. Low effort is dropped.
- **Haiku.** With the kit, Haiku at medium effort passes 3 of 3 at about a third of Sonnet's cost
  but takes 320 to 440 s of the 600 s allowed, with 25 to 34 requests and 54k to 81k output
  tokens. At low effort it is faster (230 to 310 s) and fails one incident scenario in 1 of 3 runs
  (a delivery that is being sent while the release is replaced).
- **Empty home.** One run with HOME set to an empty directory (cold Go build cache, no user
  settings) passes in 101 s at $0.21, so nothing depends on this machine's user-level setup.
