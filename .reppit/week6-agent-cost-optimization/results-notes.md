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
