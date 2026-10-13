# hyfin-drive-organizer eval workspace

Evaluation results for `../hyfin-drive-organizer/`, laid out as agentskills.io recommends. Nothing in this folder is part of the skill, and nothing here sits in a skills directory that an agent would pick up on its own.

| Path | What it is |
|---|---|
| `skill-snapshot/old_skill/SKILL.md` | The original monolithic skill, used as the `old_skill` baseline. Verbatim except that the shared drive root ID, the organizer's name and the vendor, team and deal names in the cue table are redacted. The evals ran against the unredacted copy, which is kept outside the repo. |
| `triggers/*.json` | Raw trigger-eval results. Each query ran 3 times in a fresh `claude -p` session, with exactly one copy of the skill installed next to the team's other skills. |
| `iteration-1/eval-*/{with_skill,old_skill,without_skill}/` | End-to-end output evals: `outputs/` (redacted reports and screenshots), `timing.json`, `grading.json`. |
| `iteration-1/benchmark.json` | Pass rates, tokens and duration aggregated per configuration. |
| `iteration-1/feedback.json` | Human feedback from my manual runs, plus agent review notes from this iteration, labelled as such. |
| `scripts/run_triggers.py` | Trigger-eval runner (fresh session per run, one skill copy, unsafe tools disallowed). |
| `scripts/parse_transcript.py` | Pulls tool calls, token usage and wall time out of a subagent transcript, so grading uses the transcript instead of the agent's own account of what it did. |

Real file names and Drive IDs are replaced with placeholders such as `<test_gaia id>`, `<drive id>` or `Course project proposal (non-Hyfin, name redacted)`. Because the repo is public, vendor, team-member and named-deal names are shown as `[REDACTED]`, including in the trigger queries; the tests ran on the unredacted text.
