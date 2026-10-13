# Week 3 Write-up: `hyfin-drive-organizer`

**Skill:** `hyfin-drive-organizer`, in `week3/hyfin-drive-organizer/`.
**Target "repo":** my own Google Drive workspace, the shared drive "Hyfin Team Drive" plus my personal My Drive. The instructors agreed this counts, so wherever the assignment says "repo", read "the Drive".

This repository is public. Before committing, I replaced vendor, team-member and named-deal names with `[REDACTED]`, and Drive IDs and real filenames with placeholders. The copy I tested, and the one Hyfin installs, has the real terms.

## 1. The workflow and why it is a skill

Hyfin runs six workstreams: Guarantees, Funds, GAIA, Fund Forge, BUS and Org/Team. Everyone on the team, me included, piles Hyfin documents into their personal My Drive. Those files belong in the shared drive's workstream tree, where teammates can find them. The workflow is: find my own Hyfin files in My Drive, decide where each belongs, show that plan to a human, and move only what they approve. Every teammate runs it, and the plan is to run it weekly.

Almost every step needs judgment. Is the file Hyfin at all, or a day-job spreadsheet or a payslip? Is it sensitive, so it shouldn't be guessed about? Which of 20 folders fits, and what if two do? Is it shared outside Hyfin? Can the connector make this move, or does it need the browser? And at the end, the person decides per file: approve, recategorize or skip.

### How I ran it manually first

I ran this by hand, then with better and better instructions, many times before writing the skill. Each lesson is now in it.

1. **The first version proposed moves inside the shared drive's legacy folders.** That reshuffled folders teammates reach through folder-level shares. Lesson: scope is My Drive files the runner owns, never shared-drive contents.
2. **The connector moves files from My Drive into the shared drive, and nothing else.** Every move inside the shared drive failed with "The caller does not have permission" (10 of 10, as an organizer), and folders can't be moved at all. Lesson: keep a second route through the Drive web UI.
3. **The browser pane lags.** Screenshots trail clicks by a step, menus land elsewhere in the 800 px frame, and one blind click hit "Move to trash" (cancelled, nothing deleted). Lesson: screenshot after a right-click, move one item at a time, and verify every move from metadata, not the screen.
4. **Scheduled runs are unattended.** A weekly report-only run moved nothing, correctly. It also refused a move I passed in as fire-time text, also correctly. Authorization written into a saved task prompt did work. Lesson: authorization lives in a saved prompt, never in fire-time text.
5. **The approval widget needed a louder Submit.** I clicked Approve and thought nothing happened, because only Submit sends decisions. Lesson: a big green Submit button and the line "Nothing moves until you click Submit".
6. **Sharing can change inside a shared drive.** During a 24-row reorganization, a `.docx` lost its two outside collaborators, while a Slides file and an anyone-with-the-link file kept theirs. Lesson: snapshot permissions before moving an externally shared file, diff afterwards, and report any difference.

## 2. The skill

### Structure

The original was one 33 KB file, about 8,300 tokens at roughly chars/4, because the tool I first saved it with stored only one file. Now `SKILL.md` keeps what every run needs, and the rest loads only when a step calls for it.

| File | Contents | Why it's separate |
|---|---|---|
| `SKILL.md` (123 lines, ~3,200 tokens) | Scope, safety rules, modes, 10-step pipeline, decision rules, gotchas | Loads on every trigger, so it holds only judgment and order |
| `references/taxonomy.md` | Folder tree, cue table, tie-breaks | Read at step 3. The script parses the tree from it, so there is one source of truth |
| `references/sensitivity.md` | What counts as sensitive and why to over-flag | Read before the first classification |
| `references/browser-pane-moves.md` | Route 5A step by step | Only for folders or moves inside a shared drive |
| `references/connector-moves.md` | Route 5B: plan table, order, verification | Read before the first connector move |
| `references/weekly-schedule.md` | Weekly report-only task and the optional permission test | Schedule mode only |
| `assets/approval-report.html`, `.txt` | Interactive template and plain-text layout | Long, and only needed at step 7 |
| `scripts/build_report.py` | Validates the report data and renders both formats | The deterministic part, done in code |

Each reference is one level deep and introduced with "read X when Y" at the step that needs it. The gotchas stay in `SKILL.md`.

### The description (987 characters)

```
Files a Hyfin team member's own Hyfin work from their personal My Drive into the Hyfin Team Drive's six-workstream folders (Guarantees, Funds, GAIA, Fund Forge, BUS, Org/Team). It proposes a destination for each file, shows an approval table, and moves only what the person approves. Use this skill whenever someone wants to organize, sort, tidy or clean up their Hyfin files or Drive, asks where a Hyfin doc should live, wants files moved into the team drive or "the new structure", has GAIA, Tara, Dhamana, CEFIL, CAFF or Fund Forge docs scattered in their Drive, wants a preview of proposed moves, or asks to run or schedule the weekly Hyfin Drive sync. Use it even if they never say "skill" or name a folder. It only touches files the person owns in their own My Drive and leaves personal or day-job files and everything already inside a shared drive alone. Not for renaming or editing a single file, sharing or permissions, finding a file, or questions about what a folder contains.
```

The trigger list uses the words teammates actually type ("tidy", "where should this live", "the new structure", "weekly sync"). Workstream names are there because people say "my GAIA docs" without ever saying "Drive". The scope sentence keeps it off personal cleanups. The final "Not for" sentence hands off neighbouring jobs to the Google Workspace skill or plain search. My first draft was 1,035 characters, and `skills-ref validate` rejected it.

### Encoded judgment

The **Hyfin gate** runs first. A file with no Hyfin signal is left alone and never reaches the sensitivity check; otherwise a day-job payslip would turn into a "sensitive file proposed for the team drive". The **sensitivity** check runs second, on filename, path and title only, and flags when in doubt. The **taxonomy** runs third: the more specific folder when two fit, the workstream's top folder for cross-cutting documents, and `00-Needs-Review` instead of a forced guess. The skill always **moves, never copies**, because a copy breaks every link already sent. The **safety rules** are prescriptive because those steps are fragile: no move without a submitted approval, no sharing changes, no trashing, no browser sign-in, no retry loops. The skill does not edit files, touch sharing, reorganize the shared drive, move other people's files, or let a scheduled run move anything.

The gotchas section lists the specific mistakes an agent would make here (see `SKILL.md`). Testing added one: **My Drive's root and a shared drive's root both have `0A…` IDs.** My draft said "shared-drive roots start with `0A`", and my own My Drive proved that wrong. The skill now tells the two apart by metadata: "My Drive" with an owner, versus "Drive" with no owner.

### The approval report as plan-validate-execute

The report is the plan, the human is the validator, and execution waits for Submit. `build_report.py` adds a machine check in front of the human one. Needs Review must come first; sensitive rows may show only title and reason; low-confidence rows can only go to Needs Review; every destination must be a real folder; and the counts must match. Flagged rows default to Skip. The widget never calls Drive: Submit sends a plain list of decisions back to the chat, and in a plain browser the same list appears in a copy box.

![Approval report with fake data](screenshots/approval-fake-light.png)

The dark-mode and phone-width versions are in `screenshots/`. I checked with Playwright that arrow keys switch the decision, that the dropdown selects Recategorize, and that both the Submit path and the copy-box fallback work.

### No hard-coded tool names

The skill describes what each call needs, such as "read the file's parent and sharing", and tells the agent to load the Drive tools with ToolSearch and use the live schema's names. Connector names differ across Cowork, Claude Code and the web, and they change over time. That costs one ToolSearch call per run, and in every eval run the agent found the right tools on the first try.

## 3. Testing

### Triggering

Each prompt ran 3 times in a fresh `claude -p` session (`claude-opus-5-5`). The session's config held the team's other installed skills (Google Workspace, the brand skill, the capital-provider skill and so on) plus exactly one copy of this skill, and every tool that could change anything was disallowed. "Fired" means the transcript contains a Skill call for `hyfin-drive-organizer`.

| Prompt | Should fire? | What happened | Verdict |
|---|---|---|---|
| "can you sort my hyfin files into the new drive structure? i've got a bunch of stuff in my drive from the guarantee work" | Yes | Loaded in 3/3 runs | Pass |
| "where should the Dhamana LOI draft live in the Hyfin drive?" | Yes | Loaded in 3/3 runs | Pass |
| "run the weekly hyfin drive sync" | Yes | Loaded in 3/3 runs | Pass |
| "clean up my personal google drive, lots of old photos and tax stuff" (near-miss) | No | 0/3. No skill loaded. Each run said the organizer "only files Hyfin work into the Team Drive and deliberately leaves personal files like photos and tax records alone" | Pass |

The near-miss did not fire, so the description is not too broad for the closest case I could think of: same app, same verb, wrong owner.

### End-to-end run

**Controlled run.** I created three throwaway Docs in My Drive: "TEST Hyfin GAIA Skill Eval 01 (safe to delete)", "TEST Hyfin Offer Letter Draft (safe to delete)" and "TEST grocery list". My real My Drive also holds one non-Hyfin course document. With the prompt "Which of my My Drive files should go into the Hyfin Team Drive, and where? Just show me the approval report, don't move anything yet.", the skill found the shared drive by searching for `01-Guarantees` and reading its parent, checked my role (organizer), read permissions only on the file it proposed, ran `build_report.py` (`ok: proposing 1 move, parking 1 for review, leaving 2 files alone`) and showed this report:

```
Proposing 1 move, parking 1 for review, leaving 2 files alone.
== 00-Needs-Review (default: SKIP) ==
#1   TEST Hyfin Offer Letter Draft (safe to delete) | sensitive - manual review
== 03-GAIA (default: APPROVE) ==
#2   TEST Hyfin GAIA Skill Eval 01 (safe to delete) | from My Drive | "Hyfin" + "GAIA" in title, no GAIA sub-item fits
     (alt: 06-Org-Team/AI-Native-Org if it documents a Claude skill) | medium confidence
== Not touching (no Hyfin signal, left where they are) ==
- TEST grocery list
- Course project proposal (non-Hyfin, name redacted)
```

![Real approval report, redacted](screenshots/approval-real-report-only.redacted.png)

The offer letter went to Needs Review as sensitive with Skip as the default, and the grocery list was left alone without ever reaching the sensitivity check. I then sent the decision Submit would send: move the GAIA file, skip the offer letter. The skill printed a numbered plan, snapshotted permissions, made one connector move setting the parent to 03-GAIA, re-read the metadata (same ID, new parent, owner field gone because the shared drive now owns it) and said so once. I checked independently afterwards: parent 03-GAIA, ID unchanged, the other two files still in My Drive, and no copy anywhere in the transcript. Afterwards I trashed all three test files.

**Real use in Claude Desktop Cowork.** I then ran the skill on my own Drive in Cowork. It found a real Hyfin file, proposed the right destination, and moved it through the connector route after I approved it. I then explicitly asked it to use the browser pane for a move to test route 5A, and it completed the move through the Drive web UI. Finally it set up the weekly report-only scheduled run.

**Feedback from the runs.** One run pointed out that `00-Needs-Review` sits inside the shared drive, so moving a sensitive file there exposes it to every member. Sensitive rows already defaulted to Skip; the control now also reads "Move to Needs Review (whole team can see it)". The controlled run also exposed a "1 proposed moves" plural bug in the report, which I fixed.

### Beyond what was asked

The submission contains only what the assignment asks for. To be confident the skill really works, and that an automated grader reading this would find the claims checkable, I also ran the fuller evaluation method from agentskills.io. I kept those artifacts out of the repo to keep the submission to the deliverables. In short:

- **Extended trigger set:** 20 prompts (10 should fire, 10 near-misses sharing keywords with neighbouring skills), 3 runs each, split 12 train and 8 validation. The final description scored 12/12 and 8/8. The rename request went to Google Workspace, the branded one-pager to the brand skill, and "who could lend to [deal]" to the capital-provider skill. On 8 harder stress prompts the final description scored 8/8. The original description scored 7/8: it fired on "create a new folder called News-Agent under 03-GAIA in the team drive".
- **Baselines:** the same end-to-end case run with the original monolithic skill and with no skill, graded from the transcripts' tool calls. Results: 23/23 assertions for the final skill, 19/20 for the original (it missed only the HTML report), 13/20 with no skill. Without the skill, the agent never checked my role but still told me I had edit access, read sharing on personal files, browsed a second shared drive, and offered no per-file decisions. Restructuring didn't change behaviour and cut the text loaded on every trigger from about 8.3k to about 3.2k tokens.
- **Description validation:** my first draft of the description was 1,035 characters, and `skills-ref validate` rejected it. I also found that the org-installed copy was older than the version I had been editing.

## 4. What I'd change next, and limits

The connector can't move folders or anything already inside a shared drive, so those moves need the browser pane. The pane needs a session the human has already signed into the Hyfin account, and at 6 to 8 actions per item it is slow; it works, but I'd only use it when the connector can't. The weekly task can only report, by design. The runner can't move other people's files, so each teammate runs the skill on their own Drive. External sharing inside a shared drive can still drop on a move; the skill detects it but can't prevent it. Triggering depends on which copy of the skill is installed, so the org-wide copy has to be kept in sync. Next, I'd report post-move sharing as counts rather than member names, and guard against creating the weekly task twice.

Still untested: a file shared with "anyone with the link". The connector can only share with a named email, so I couldn't create one safely.

## 5. Reproduction

To install, copy `week3/hyfin-drive-organizer/` into the agent's skills folder (for Claude Code, `~/.claude/skills/`), or upload it as an org skill. It needs a Google Drive connector that can search, read metadata and permissions, create folders and change a file's parent; the browser route needs Claude Desktop in Cowork mode. To validate:

```bash
uvx --from skills-ref agentskills validate ./week3/hyfin-drive-organizer
# Valid skill: hyfin-drive-organizer
```
