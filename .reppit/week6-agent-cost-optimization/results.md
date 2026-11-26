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

## Transfer incident (INC-2231, endpoint changes ignored)

A second incident built to test the setup on a ticket it was not designed around; see
`transfer/README.md`. Scored by `transfer/inc-2231/judge.py` with the assignment's formulas.

| Setup | Run | Result | Repair | Impact | Cost | Requests | Time | Incident | Regr. | Compat |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| sonnet-medium | 20261126-150246-1 | PASS | 1.0 | 1.0 | $0.364 | 25 | 179 s | 9/9 | 9/9 | 4/4 |
| sonnet-medium | 20261126-150246-2 | PASS | 1.0 | 1.0 | $0.270 | 14 | 136 s | 9/9 | 9/9 | 4/4 |
| sonnet-medium | 20261126-150246-3 | FAIL | 0.9231 | 1.0 | $0.281 | 19 | 187 s | 9/9 | 9/9 | 3/4 |

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
