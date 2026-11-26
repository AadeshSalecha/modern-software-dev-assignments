# Proposals: Week 6 agent setup

Builds on `research.md` (same folder). Written 2026-11-26.

## Decisions

| # | Question | Answer | Source |
|---|---|---|---|
| D1 | Which cost number counts? | Tokens x `rate_card.json` as printed by `practice.py` (includes the 1h cache-write rate when the harness uses it). | User |
| D2 | May we add instruction files? | Yes: root `AGENTS.md`/`CLAUDE.md` with a repo map, nested files, progressive disclosure (agents.md style). | User |
| D3 | Helpers? | Yes: skills, deterministic helpers and parsers, as long as they are about the system and its evidence, not this ticket. | User |
| D4 | Confidence? | Multiple practice runs per configuration in later stages. | User |
| D5 | Harness for the submission | Assumed Claude Code only, because it is the only one measurable in this container. Codex/GPT stays a possible later experiment on the user's machine. | Assumption, to confirm |
| D6 | Target | Assumed: pass reliably first, then get under $0.75 (full cost points); leaderboard chasing only if it costs no reliability. | Assumption, to confirm |
| D7 | Knowledge from `tools/starter/` | Stays out of the setup. Only what follows from `task.md`, `contracts/` and the service code may be encoded. | Assignment rule |

## New finding since research: why the baseline report was wrong

Traced in `runs/20261126-101810-1/`. In the 19 key groups it got wrong (all `m_maple`), the api log has an
`event.repeated` line pointing at the *second* accepted event (the in-memory key table was rebuilt after
the restart). The agent's first script used the ticket's definition (earliest accept = original); its
final report names the earlier event as the repeat instead, i.e. it let a derived log line override the
ticket's literal definition. Totals still matched because both events carry the same amount.
General lesson: the ticket defines the terms; logs are evidence, not definitions.

## What both options share (the foundation)

1. **Authority and map.** A root `CLAUDE.md` (and `AGENTS.md` with the same content for Codex) of
   roughly 60 lines: trust order (`task.md` > `app/contracts/` > code > everything else), a repo map
   with what to ignore, verified system facts (ids, lease, retries, bus versions, crash points), and
   pointers to deeper files that are read only when needed.
2. **Overlay.** `app/` is replaced by the grader, so `run.sh` installs our own nested instruction
   files at start: it replaces `app/CLAUDE.md` and `app/AGENTS.md` (the stale ones) and adds a short
   one per service (how to run its tests, where crash points are, what must not move).
3. **Pruning.** `run.sh` moves directories no scored service needs (`sdk/`, `legacy/`,
   `services/router-next/`, `deploy/helm/`) out of the workspace before the agent starts. `docs/` stays
   but is labelled as leads, not truth.
4. **Evidence toolkit.** A deterministic script implementing `contracts/evidence.md` once: skip and
   count cut rows, drop shipper duplicates, resolve cut ids, normalise amounts and timestamps, and
   merge all files into one SQLite database (events, deliveries, attempts, with the source of each
   fact). The agent writes only the incident-specific query. Nothing in it knows about idempotency.
5. **Upgrade-aware checks.** A helper that runs a scenario on the untouched release (snapshotted by
   `run.sh` before the agent starts), swaps in the candidate services on the same state, drains, and
   asserts contract invariants (ends `delivered` or `dead`, nothing left queued or leased, services
   alive, crash points intact). Plus a short skill on writing replay scenarios, including the verbs the
   shipped scenarios never use.
6. **Requirements ledger.** The agent turns every clause of `task.md` into a checklist line and may
   not stop until each has a named check. A Stop hook runs the cheap deterministic part (builds,
   unit tests, report shape).
7. **Cost hygiene.** Smaller base prompt (tool allowlist, no MCP), lower effort, quiet test output,
   ranged reads instead of whole-file `cat`, a turn limit, and checking whether the 1h cache TTL can be
   switched to 5m.

## Option A: one well-equipped session

**Overview.** Keep a single `claude -p` call on Sonnet. All savings come from the foundation: the agent
starts with a map instead of exploring, never reads raw logs, and has checks that tell it when it is
actually done.

**Key changes.** `run.sh` (prep, then one call), root and nested instruction files, `tools/` helpers,
`.claude/skills/`, `.claude/settings.json` (hook, tool allowlist).

**Trade-offs.**
- For: fewest moving parts; no hand-off where information can be lost; the model that diagnoses also
  repairs; easiest to debug from one transcript; most likely to survive an unfamiliar incident.
- Against: everything is billed at Sonnet rates; the repair context is carried while writing the report
  and vice versa. Expected cost roughly $0.45 to $0.70 (estimate from the baseline split, unmeasured).
- Unhappy path: if the agent runs long, the turn limit could stop it before `out/impact.json` exists;
  mitigated by ordering (report first, since it is cheap) and by the Stop hook.

**Validate.** 5 practice runs; pass rate, mean and worst cost.

**Open questions.** Effort level; whether report-first or repair-first ordering is cheaper.

## Option B: staged pipeline with model routing

**Overview.** `run.sh` becomes an orchestrator of several short headless calls:
1. Prep (no model): overlay, prune, build the evidence database.
2. **Diagnose** (Sonnet, short, read-only): writes `spec.md` with root cause, repair design, the
   requirements ledger, acceptance scenarios, and the report definition in terms of the database.
3. **Repair** (Haiku) and **Report** (Haiku) in parallel, each in a fresh session with only its part of
   the spec and a stable shared prefix.
4. **Gate** (no model): run the checks. On failure, one escalation call to Sonnet with the failing output.

**Key changes.** Everything in A, plus per-stage prompts, the spec format, the gate script and the
escalation path.

**Trade-offs.**
- For: most tokens are billed at 1/20 the price; each stage has a small context; parallel stages help
  the 10-minute limit. Expected cost roughly $0.15 to $0.40 when no escalation is needed (unmeasured).
- Against: Haiku's ability to do a three-language repair with upgrade handling is unproven, and even
  Sonnet at high effort failed the baseline; the spec is a lossy hand-off and a wrong diagnosis is
  inherited by everything after it; more ways to fail unattended (stage crash, partial output, both
  stages editing files); an escalation can cost more than Option A outright; every stage pays its own
  base prompt.
- Unhappy path: needs explicit handling for a missing or malformed spec, a stage timeout, and a gate
  that can never be satisfied (bounded to one escalation).

**Validate.** Same 5-run protocol, plus per-stage pass rates and how often escalation fires.

**Open questions.** Whether Haiku can hold the repair at all; spec format; whether stages resume a
session (cache reuse) or start fresh.

## Recommendation

Build the shared foundation and ship **Option A** first, then test Option B's pieces as measured
experiments on top of it, in order of risk: (1) report stage on Haiku, since it is mechanical once the
database exists; (2) repair on Haiku from a Sonnet spec. Keep a piece only if it passes 5 of 5 and is
cheaper. Reasons: correctness is all-or-nothing and worth as much as cost; full cost points need only
$0.75 or less, which A plausibly reaches; there is one graded run per submission; and the write-up is
graded on experiments, which this order produces naturally (including the ones that fail).

## Questions for the user

1. Pick: A first with B's pieces as experiments (recommended), or B from the start?
2. D5: Claude Code only for now?
3. D6: is the target "reliable pass under $0.75", or is the leaderboard a goal in itself?
4. Upgrade-aware checks (foundation item 5): the ticket says the release rolls out over live regions,
   and the contracts say every delivery ends `delivered` or `dead`, so I consider this system
   knowledge. I also know from the scorer that upgrade scenarios exist. Are you comfortable with it?
5. Pruning (item 3): move unneeded directories out of the workspace, or only tell the agent to ignore them?
