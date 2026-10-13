---
name: hyfin-drive-organizer
description: >-
  Files a Hyfin team member's own Hyfin work from their personal My Drive into
  the Hyfin Team Drive's six-workstream folders (Guarantees, Funds, GAIA, Fund
  Forge, BUS, Org/Team). It proposes a destination for each file, shows an
  approval table, and moves only what the person approves. Use this skill
  whenever someone wants to organize, sort, tidy or clean up their Hyfin files
  or Drive, asks where a Hyfin doc should live, wants files moved into the team
  drive or "the new structure", has GAIA, Tara, Dhamana, CEFIL, CAFF or Fund
  Forge docs scattered in their Drive, wants a preview of proposed moves, or
  asks to run or schedule the weekly Hyfin Drive sync. Use it even if they
  never say "skill" or name a folder. It only touches files the person owns in
  their own My Drive and leaves personal or day-job files and everything
  already inside a shared drive alone. Not for renaming or editing a single
  file, sharing or permissions, finding a file, or questions about what a
  folder contains.
license: Proprietary (Hyfin internal)
compatibility: >-
  Needs a Google Drive connector that can search files, read metadata and
  permissions, create folders and change a file's parent folder. The optional
  browser-pane route needs Claude Desktop in Cowork mode, linked to the
  computer and already signed in to the person's Hyfin Google account. The
  weekly schedule needs a scheduled-task tool.
metadata:
  author: Aadesh Salecha
  organization: Hyfin
  version: "2.0"
---

# Hyfin Drive Organizer

Moves the runner's own Hyfin-related files out of their My Drive and into the six-workstream tree in the shared drive named **Hyfin Team Drive**, through a report, approve, move flow. Any Hyfin team member can run it.

## Scope: My Drive files the runner owns, nothing else

Candidates are files that sit in the runner's own My Drive, are owned by the runner, and are not inside any shared drive. Everything already inside a shared drive is out of scope, even when the runner is an organizer there and the files look unsorted. Don't scan it, don't propose moves for it, don't list it. Teammates reach shared-drive content through folder-level shares, so reshuffling it silently cuts people off; an earlier version of this skill did exactly that and its proposals were bad.

If the runner has nothing Hyfin-related in My Drive, the correct result is a short report with zero proposed moves. Don't go looking for something else to do.

## Safety rules (no exceptions)

- Never move anything without a submitted approval from the person. Unattended runs only report.
- Move, never copy. A move is a change of parent folder and keeps the file ID, URL and the file's own sharing; a copy gets a new ID and every link already sent to a partner or teammate breaks. If a move is refused, stop and tell the person. Never work around it with a copy.
- Never change sharing, never click Share or Request access, never trash anything the person didn't explicitly ask to trash (duplicates included).
- Never sign in, enter credentials or request account access in the browser pane. Only the person can sign it in.
- Never retry a failing move in a loop. One failure on an item: report it, move on or stop.
- Never open a file's contents to classify it or to check sensitivity. Filename, path and title only.

## Modes

Pick from the request; default to a full sort.

| Mode | Window | Ends with |
|---|---|---|
| Full sort ("organize my Hyfin files") | everything the runner owns in My Drive | approval report, then moves |
| Report only ("just show me", "don't move anything") | as full sort | approval report; stop |
| Weekly sync ("run the weekly sync", scheduled runs) | created or modified in the last 7 days (rolling, from today's date) | approval report; moves only if a person is present and submits |
| Schedule setup ("set up the Saturday sync") | none | read `references/weekly-schedule.md` and follow it |

## Tools

Load the Drive tools with ToolSearch (search "Google Drive"), or the client's equivalent, before the first call, and use the tool and parameter names the live schema returns. Never assume names from memory; they differ between clients and change over time. If the connector is installed but switched off, ask the person to enable it. The steps below say what each call needs to do, not which tool to call.

Behaviour that holds whatever the tools are called: a move is a parent change; the connector can create folders and can move a single file from My Drive into a shared drive; it cannot move folders, and it cannot move anything that is already inside a shared drive (both fail with "The caller does not have permission").

## Pipeline

**1. Surface.** If browser-pane tools are in the tool list, the browser route is possible later. If not, say once that Claude Desktop Cowork (in a fresh session, computer linked) gives fewer permission prompts, ask whether to switch or continue, and if they continue use the connector route without raising it again.

**2. Access diagnostic.** Find the shared drive: search for a folder titled `01-Guarantees` (or any other top-level taxonomy folder) and read its parent. Accept that parent as the root only if its metadata reports no parent, no owner and the title "Drive" (how the API names a shared-drive root). Also read the metadata of `root`, the alias for the runner's My Drive: it reports the title "My Drive" and the runner as owner. The two root IDs look alike (both start with `0A`), so never tell them apart by ID shape. If you find more than one candidate shared-drive root, ask. Then read the root's permissions and find the runner's own entry. Writer, fileOrganizer or organizer: continue. Reader, commenter or no entry: stop and tell them their role, that moves will fail, and that a drive organizer has to raise it. If the list has only named people and no Hyfin domain or group entry, mention that new teammates may not see filed files. Report only; never edit sharing.

**3. Destination tree.** Read `references/taxonomy.md` now. Look up each taxonomy folder by exact title under the root and keep a `path -> folder ID` map. Missing folders are normal. Don't create any yet.

**4. Candidates.** Search for non-folder files owned by the runner, apply the mode's date window, paginate until no next-page token. Drop anything whose parent chain doesn't end at the runner's My Drive root (files inside a shared drive report no owner, so an owner filter already excludes most of them). Record each file's current My Drive folder name. Files owned by others never appear; if many are visible, one summary line at the end with a count and no filenames.

**5. Classify, in this order, per file.**
1. **Hyfin gate.** Is there a clear Hyfin signal in the filename, path or title (a cue from the taxonomy, or plainly Hyfin work)? No signal: put it on the Not touching list and stop processing it. Do not run the sensitivity check on it.
2. **Sensitivity.** Read `references/sensitivity.md` before the first file. If it trips: destination `00-Needs-Review`, reason `sensitive - manual review`, no further classification.
3. **Taxonomy.** One destination plus confidence (high, medium, low), using the decision rules below.

**6. Sharing check (read-only).** For every non-sensitive file proposed to move, read its permissions (sensitive files get no inspection beyond their name). Mark rows with anyone-with-link access or a non-Hyfin account as shared externally, and save that permission list as the "before" snapshot. Also mark files whose parent My Drive folder is shared with other people: the file's own sharing survives the move, folder-level access does not.

**7. Approval report.** Build the report data as JSON in the shape documented at the top of `scripts/build_report.py`, then run:

```bash
python3 scripts/build_report.py report.json --html approval-report.html --text approval-report.txt
```

The script validates the data (Needs Review first, sensitive rows show no detail, defaults correct, counts match) and fills `assets/approval-report.html`. Fix every error it prints before showing anything. Show the HTML with the client's inline widget tool if there is one (read that tool's usage notes first); otherwise, and always for unattended runs, show the plain-text report. If Python isn't available, fill the `REPORT_DATA` block in the template by hand and follow `assets/approval-report.txt` for the text layout. Nothing moves until the decisions come back through Submit or a typed reply.

**8. Execute.** Approve moves to the proposed folder, Recategorize to the chosen one, Skip leaves the file where it is, Pull in moves a Not-touching file to the chosen folder. Create a missing destination folder only now, only for an approved move, parents first; reuse it if it appeared meanwhile. Moving into a shared drive transfers ownership to the drive: say so once.
- Folders, or anything already inside a shared drive: browser route only. Read `references/browser-pane-moves.md` before the first UI move.
- Single files from My Drive: connector route. Read `references/connector-moves.md` before the first connector move.
- If neither route works for an item, list it for the person to move by hand.

**9. Verify.** Re-read every moved file's metadata and confirm its parent is the destination and its ID is unchanged. Don't trust a screenshot or a success message. For every externally shared file, read its permissions again and compare with the before snapshot. Report any difference to the person; never assume sharing survived and never re-share.

**10. Summary.** Moved, skipped, still in Needs Review, sharing differences, route used and why, access findings from step 2. On a first manual run, if no "Hyfin Drive weekly sync" task exists, offer once to set up the weekly report-only schedule (`references/weekly-schedule.md`).

## Decision rules for ambiguous files

- No Hyfin signal, or a title you can't place: leave it alone (Not touching). A day-job payslip must never become a proposed move.
- Unsure whether it's sensitive: flag it. A false positive costs one click; a false negative puts someone's pay or health data in a team folder.
- Fits two folders: choose the more specific one (a Pakistan guarantee memo goes to `CEFIL-NCGCL-Guarantee`, not `01-Guarantees`).
- Clearly one workstream but no sub-item fits (a cross-cutting GAIA tracker): the workstream's top folder (`03-GAIA`).
- Clearly Hyfin, low confidence or no reasonable match: `00-Needs-Review`, reason `unclear match`. Don't force a guess.
- Likely duplicates (same title, similar size): flag both in the report. Never trash either.

## Gotchas

- **Sharing can change inside a shared drive.** My Drive to shared drive keeps a file's own sharing. Moves between folders inside a shared drive can drop direct permissions: a `.docx` lost its two outside collaborators that way while a Slides file and an anyone-with-link file kept theirs. That is why step 6 snapshots and step 9 diffs.
- **The connector cannot move folders, and cannot move anything already in a shared drive.** "The caller does not have permission" there is not a role problem and not transient (it failed 10 of 10 times for an organizer). Don't retry. Use the browser route or hand it to the person.
- **The two roots look alike.** My Drive's root and a shared drive's root both have `0A...` IDs. Tell them apart by metadata: "My Drive" with an owner versus "Drive" with no owner.
- **Ownership transfers** when a file lands in a shared drive. Mention it once, in the summary.
- **Scheduled runs are unattended.** They can only produce the report. Authorization to move must be written into a saved task prompt, never passed as fire-time text (runs correctly treat that as data and refuse), and the task's approval mode is set by the server, not by you.
- **The browser pane lags one step.** Wait about two seconds before each screenshot, and screenshot after a right-click before choosing a menu item. One blind click once landed on "Move to trash".
- **Verify with metadata, not the screen.** A dialog may still be waiting for confirmation behind a screenshot that looks finished.
- **Never open files to classify.** Reading a sensitive file to double-check is the wrong move; over-flag instead.
- **Ungated files skip the sensitivity check entirely.** Run it only after the Hyfin gate, otherwise personal tax forms and payslips get "parked for review" in the team drive.
- **Other people's files** can't be moved by the runner. One count line, no filenames.
- **Don't rename to make a prompt readable.** Per-move approval prompts may show only file IDs; print a numbered plan instead (see `references/connector-moves.md`). A title change is a real edit.
- **Deferred tools.** Drive tools are often not loaded at start. Load them first and read the parameter names from the live schema.
