# Week 3 Write-up

**Skill name**, and the repo you targeted:
> `hyfin-drive-organizer` (in `week3/hyfin-drive-organizer/`). The target is my own Google Drive workspace, not a code repo: the shared drive "Hyfin Team Drive" plus my personal My Drive. The instructors agreed this counts, so wherever the assignment says "repo", read "the Drive".
>
> This repository is public. Before committing, I replaced vendor, team-member and named-deal names with `[REDACTED]`, and Drive IDs and real filenames with placeholders. The copy I tested, and the one Hyfin installs, has the real terms.


## Part I: The Workflow

**What the workflow is**, and why it's worth encoding:
> Hyfin runs six workstreams: Guarantees, Funds, GAIA, Fund Forge, BUS and Org/Team. Everyone on the team, me included, piles Hyfin documents into their personal My Drive. Those files belong in the shared drive's workstream tree, where teammates can find them. The workflow is: find my own Hyfin files in My Drive, decide where each one belongs, show that plan to a human, and move only what they approve. Every teammate runs it, and the plan is to run it weekly. Without a skill, I was pasting the same long checklist into chat every time, and the agent still made the same mistakes.

**The decision point** in it (what the agent has to judge, not just execute):
> Almost every step is a judgment call. Is this file Hyfin at all, or a day-job spreadsheet or a payslip? Is it sensitive (an offer letter, a passport scan), so it should be parked for review rather than guessed about? Which of the 20 destination folders fits, and what happens when two do? Is the file shared outside Hyfin, so its sharing has to be checked after the move? Can the Drive connector make this move, or does it need the browser? And at the end, the person decides per file: approve, recategorize or skip.

**What you learned running it manually** that you would not have guessed:
> I ran this by hand, then with better and better instructions, many times before writing the skill. Each lesson is now in it.
>
> 1. **The first version proposed moves inside the shared drive's legacy folders.** That reshuffled folders teammates reach through folder-level shares. Now the scope is My Drive files the runner owns, never shared-drive contents.
> 2. **The connector moves files from My Drive into the shared drive, and nothing else.** Every move inside the shared drive failed with "The caller does not have permission" (10 out of 10, even as an organizer), and folders can't be moved at all. So the skill has a second route through the Drive web UI.
> 3. **The browser pane lags.** Screenshots trail clicks by one step, and right-click menus land in unexpected places in the 800 px frame. One blind click hit "Move to trash" (I cancelled it; nothing was deleted). Now the skill screenshots after every right-click, moves one item at a time, and verifies each move from file metadata, not the screen.
> 4. **Scheduled runs are unattended.** A weekly report-only run correctly moved nothing. It also correctly refused a move I passed in as fire-time text. Authorization written into a saved task prompt did work.
> 5. **The approval widget needed a louder Submit.** I clicked Approve on rows and thought nothing happened, because only Submit sends decisions. Now there is a big green Submit button and the line "Nothing moves until you click Submit".
> 6. **Sharing can change inside a shared drive.** During a 24-row reorganization, a `.docx` lost its two outside collaborators, while a Slides file and an anyone-with-the-link file kept theirs. Now the skill snapshots permissions before moving an externally shared file, diffs them afterwards, and reports any difference.
> 7. **My Drive's root and a shared drive's root have look-alike IDs** (both start with `0A`). My draft said that only shared-drive roots look like that, and my own My Drive proved it wrong. The skill now tells them apart by metadata: "My Drive" with an owner, versus "Drive" with no owner.


## Part II: The Skill

**Your description**, verbatim:
```
Files a Hyfin team member's own Hyfin work from their personal My Drive into the Hyfin Team Drive's six-workstream folders (Guarantees, Funds, GAIA, Fund Forge, BUS, Org/Team). It proposes a destination for each file, shows an approval table, and moves only what the person approves. Use this skill whenever someone wants to organize, sort, tidy or clean up their Hyfin files or Drive, asks where a Hyfin doc should live, wants files moved into the team drive or "the new structure", has GAIA, Tara, Dhamana, CEFIL, CAFF or Fund Forge docs scattered in their Drive, wants a preview of proposed moves, or asks to run or schedule the weekly Hyfin Drive sync. Use it even if they never say "skill" or name a folder. It only touches files the person owns in their own My Drive and leaves personal or day-job files and everything already inside a shared drive alone. Not for renaming or editing a single file, sharing or permissions, finding a file, or questions about what a folder contains.
```

**Why it's worded that way** (what a user would type to trigger it):
> The trigger list uses the words teammates actually type: "organize", "tidy", "clean up", "where should this live", "the new structure", "weekly sync". Workstream and vehicle names are there because people say "my GAIA docs" or "the Dhamana LOI" without ever saying "Drive" or "Hyfin". "Use it even if they never say skill" is the deliberate pushiness agentskills.io recommends, because most skills fail by never firing. The scope sentence keeps it off personal Drive cleanups. The final "Not for…" sentence hands neighbouring jobs to other skills: renaming a Google Doc goes to the Google Workspace skill, and plain search and folder questions go to the Drive tools. The description is 987 characters. My first draft was 1,035, and `skills-ref validate` rejected it for exceeding the 1,024 limit.

**Judgment encoded in the body** (what it says to do when things are ambiguous, and what not to do):
> Every file goes through three checks, in a fixed order. The **Hyfin gate** comes first: a file with no Hyfin signal is left alone and never even reaches the sensitivity check. Otherwise someone's day-job payslip would turn into a "sensitive file proposed for the team drive". The **sensitivity check** comes second. It looks at the filename, path and title only, never opens the file, and flags whenever in doubt, because a false positive costs one click and a false negative puts pay data in a team folder. **Taxonomy** comes third: if two folders fit, pick the more specific one; cross-cutting documents go in the workstream's top folder; low confidence means `00-Needs-Review` instead of a forced guess. Flagged files default to Skip, because `00-Needs-Review` is itself visible to the whole drive.
>
> **What not to do** is written as hard rules, because these steps are fragile. Never move anything without a submitted approval. Move, never copy, because a copy breaks every link already sent to a partner. Never change sharing. Never trash anything the person didn't ask to trash. Never sign in or enter credentials in the browser pane. Never retry a failing move in a loop. Never touch anything already inside a shared drive.
>
> A **Gotchas** section lists the specific mistakes an agent would make here, such as the connector's folder limits, ownership transferring to the shared drive, scheduled runs only reporting, and verifying from metadata rather than the screen. The body never names a connector tool or argument. It describes what each call needs and tells the agent to load the Drive tools with ToolSearch, so the skill survives connector renames.
>
> The approval report is a plan-validate-execute step: the report is the plan, the human is the validator, and nothing executes before Submit. `scripts/build_report.py` adds a machine check before the human one.

**Supporting files**, if any, and why they aren't inline:

| File | Contents | Why it's separate |
|---|---|---|
| `references/taxonomy.md` | Folder tree, cue table for each of the 20 folders, tie-break rules | Long, and only needed once the destination tree is being located (step 3). `build_report.py` also parses the tree from it, so the folder list has a single source of truth. |
| `references/sensitivity.md` | What counts as sensitive, what doesn't, and why over-flagging is safer | Read once, before the first classification. |
| `references/browser-pane-moves.md` | Route 5A: moving through the Drive web UI step by step, with the lessons from the manual runs | Only needed for folders or moves inside a shared drive, which is rare. |
| `references/connector-moves.md` | Route 5B: numbered plan table, move order, verification, the workaround for whole folders | Read right before the first connector move. |
| `references/weekly-schedule.md` | The weekly report-only scheduled task and the optional permission test | Only needed when someone asks for a schedule. |
| `assets/approval-report.html` | Self-contained interactive approval table: Approve, Recategorize or Skip per row, a Not-touching section, and a Submit button | About 300 lines of HTML, CSS and JS that the agent fills with data; it doesn't need to read them on every run. |
| `assets/approval-report.txt` | Plain-text layout of the same report, for surfaces without widgets and for unattended runs | Example output, only needed at step 7. |
| `scripts/build_report.py` | Validates the report data and renders both the HTML and the text version | The deterministic part (ordering, defaults, counts, hiding detail on sensitive rows) is done reliably in code instead of in prose. |
| `evals/evals.json` | Output-eval cases with assertions: report-only run, test-file move, sensitive file, file with no Hyfin signal | Testing only, never loaded when the skill runs. Kept in the skill folder, where the agentskills.io evaluation guide puts it. |
| `evals/trigger_queries.json` | 28 labelled prompts: 10 should-fire, 10 near-misses that share keywords with neighbouring skills, 8 harder stress cases | Testing only. I went beyond the four prompts the assignment asks for. Each prompt ran 3 times in a fresh session; the final description scored 20/20 (train 12/12, validation 8/8) and 8/8 on the stress set. |
| `evals/files/fake-report.json` | 13-row fake report: external share, sensitive file, low-confidence file, possible duplicates, Not-touching files | Fixture for rendering and screenshotting the template without real filenames. |


## Part III: Testing

**Triggering:**

| Prompt | Should fire? | Did it? |
|---|---|---|
| "can you sort my hyfin files into the new drive structure? i've got a bunch of stuff in my drive from the guarantee work" | Yes | Yes, in 3/3 fresh sessions: the transcript shows a Skill call for `hyfin-drive-organizer`. |
| "where should the Dhamana LOI draft live in the Hyfin drive?" | Yes | Yes, 3/3. |
| "run the weekly hyfin drive sync" | Yes | Yes, 3/3. |
| "clean up my personal google drive, lots of old photos and tax stuff" | No (near-miss) | No, 0/3. No skill loaded. Each run explained that the organizer "only files Hyfin work into the Team Drive and deliberately leaves personal files like photos and tax records alone". |

**End-to-end run** on your repo, and the result:
```
How the trigger tests were run: each prompt went into a fresh `claude -p` session (claude-opus-5-5)
with the team's other installed skills plus exactly one copy of this skill, and every tool that could
change anything disallowed. "Fired" means a Skill call for hyfin-drive-organizer appears in the transcript.

1) Controlled run on my real My Drive
   Setup: three throwaway Docs in My Drive ("TEST Hyfin GAIA Skill Eval 01 (safe to delete)",
   "TEST Hyfin Offer Letter Draft (safe to delete)", "TEST grocery list"), plus one real non-Hyfin
   course document I already had there.
   Prompt: "Which of my My Drive files should go into the Hyfin Team Drive, and where?
            Just show me the approval report, don't move anything yet."
   What the skill did: found the shared drive by searching for 01-Guarantees and reading its parent,
   confirmed it from metadata, checked my role (organizer), searched files I own, read sharing only
   for the one file it proposed, then ran build_report.py:
     ok: proposing 1 move, parking 1 for review, leaving 2 files alone
   Report shown:
     Proposing 1 move, parking 1 for review, leaving 2 files alone.
     == 00-Needs-Review (default: SKIP) ==
     #1  TEST Hyfin Offer Letter Draft (safe to delete) | sensitive - manual review
     == 03-GAIA (default: APPROVE) ==
     #2  TEST Hyfin GAIA Skill Eval 01 (safe to delete) | from My Drive | "Hyfin" + "GAIA" in title,
         no GAIA sub-item fits (alt: 06-Org-Team/AI-Native-Org) | medium confidence
     == Not touching (no Hyfin signal, left where they are) ==
     - TEST grocery list
     - Course project proposal (non-Hyfin, name redacted)

   Decisions submitted: MOVE the GAIA file to 03-GAIA, SKIP the offer letter.
   What the skill did: printed a numbered plan, snapshotted permissions, made ONE connector move
   (changing the parent to 03-GAIA), re-read metadata, re-read permissions, and said once that the
   shared drive now owns the file.
   Independent check afterwards: parent = 03-GAIA, file ID unchanged, no copy in the transcript,
   offer letter and grocery list still in My Drive. All three test files were then trashed.

2) Real use in Claude Desktop Cowork
   - Found a real Hyfin file in my My Drive, proposed the correct destination, and moved it
     through the connector route after I approved it.
   - When I explicitly asked for the browser-pane route, it completed a move through the
     Drive web UI.
   - It set up the weekly report-only scheduled run.

3) Beyond what was asked
   I ran the same controlled case with the original monolithic skill and with no skill, graded
   from the tool calls in each transcript (one run each, so treat these as qualitative):
     lean skill 23/23 assertions | original skill 19/20 | no skill 13/20
   With no skill, the agent never checked my role but still told me I had edit access. It also
   read sharing on personal files, browsed a second shared drive, and offered no per-file
   decisions. The restructure didn't change behaviour and cut the text loaded on every trigger
   from about 8.3k to about 3.2k tokens. The eval definitions are in evals/. I kept the raw run
   results out of the repo to keep the submission to the deliverables.

Limits: the connector can't move folders or anything already inside a shared drive, so those
moves need the browser pane, which needs a human-signed-in session and is slow. Scheduled runs
only report. External sharing inside a shared drive can still drop on a move; the skill detects
it but can't prevent it. Still untested: a file shared with "anyone with the link" (the connector
can only share with a named email, so I couldn't create one safely).
```

![Approval report from the controlled run, filenames redacted](screenshots/approval-real-report-only.redacted.png)

![Approval report template rendered with the fake fixture](screenshots/approval-fake-light.png)


## Submission
1. `Command (⌘) + F` for `TODO`. No results means you're done.
2. Confirm the skill directory itself is committed under `week3/`.
3. Push all changes to your remote repository and submit via Gradescope.
