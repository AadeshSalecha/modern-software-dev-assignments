---
name: hyfin-drive-organizer
description: Moves the running user's own Hyfin-related My Drive files into the six-workstream folder tree (Guarantees, Funds, GAIA, Fund Forge, BUS, Org/Team) in the shared Hyfin Team Drive. It only looks at files the user owns in their own My Drive; it never scans, proposes moves for, or reorganizes anything already inside a shared drive. Use this whenever anyone on the Hyfin team asks to organize, sort, clean up, or file the Hyfin Drive, wants their own Drive files moved into the shared drive, mentions "the new folder structure," asks where a file should live, or wants the Drive kept in sync with the org restructure going forward. Also trigger for a "weekly Hyfin Drive sync" or similar recurring request. Starts with a surface and access check, only touches Hyfin-related files (never a person's day-job or personal files), runs a report-then-approve flow, never moves a file without a person approving it first, always moves rather than copies so existing sharing links keep working, and automatically parks anything that looks like compensation, PII, health, or legal-sensitive material for manual review instead of guessing where it goes.
---

# Hyfin Drive Organizer

Moves the running person's own Hyfin-related files from their My Drive into the six-workstream folder tree inside the shared Hyfin Team Drive. Any Hyfin team member should be able to run it.

**Scope, which matters most: My Drive files the runner owns, and nothing else.** The only candidates are files that live in the runner's own My Drive, are owned by the runner, and are not inside any shared drive. Everything already inside a shared drive is out of scope, even if the runner is an organizer of that drive and even if the files there look unsorted or are owned by the runner. That includes the Hyfin Team Drive's existing legacy folders and files, the "Hyfin AssetCo Data Rooms" shared drive, and any other shared drive the runner can see. Don't scan them, don't propose moves for them, and don't list them in the report. The reason: shared drives hold folders and files that teammates reach through folder-level shares, so moving things around inside them can silently cut people off, and other team members have already organized or are responsible for them. If the runner has nothing in their own My Drive that is Hyfin-related, the right outcome is a short report saying so with zero proposed moves, not a search for something else to do.

Some team members have a day job alongside their Hyfin work, so their My Drive is a mix. This skill only ever moves Hyfin-related files. Anything without a clear Hyfin signal is left exactly where it is. Two modes:

- **Full sort**: on demand, scans everything the runner owns in My Drive. Run this the first time, or whenever someone asks to "organize" or "clean up" their Hyfin files.
- **Weekly sync**: scans only My Drive files the runner owns that were created or modified in the last 7 days. This is what the Saturday 4am ET scheduled run should call (see "Setting up the weekly schedule" below). A scheduled run only sees the My Drive of the person whose account it runs under.

Both modes share the same access check, classify, report, approve, move pipeline. The only difference is the date window in Step 2.

The classification rules live at the bottom of this file: the folder taxonomy ("Folder taxonomy and cues") and the sensitivity check ("Sensitivity check"). Read both before classifying anything. For every file that passes the Hyfin gate (Step 3), the sensitivity check runs before any classification.

The Google Drive tools may be deferred. Call ToolSearch for "Google Drive" before using any of them if they aren't already loaded, and use whatever parameter names that search returns. Don't assume the ones documented here haven't drifted. If the Drive connector is installed but turned off in this chat, ask the person to enable it in the chat's connector settings.

## The one rule that matters most: move, never copy

Always relocate a file by updating its parent folder (Drive `update_file` with `parentId`, or the Move dialog in the Drive web UI). Never use `copy_file` and then delete or abandon the original. A move keeps the file ID, the URL, and the file's own permissions, so anyone who was sent a link (including people outside Hyfin, and "anyone with the link" shares) keeps their access. A copy gets a new ID and a new URL and does not inherit the original's sharing, so every link already sent to a client, partner, or teammate stops working. If a situation ever seems to call for a copy (for example the move is refused), stop and ask the person instead of copying.

One caveat: a shared drive's admin settings can restrict sharing outside the organization, and in that case Google may remove outside access when a file lands there. This was not observed in testing (an anyone-with-link file kept its link after a move), but for any file that has external or link sharing, confirm the sharing survived after the move and tell the person if it didn't.

## Before you start: run it in Claude Desktop Cowork

This skill works best, with far fewer permission prompts, in a session that is linked to the person's computer through Claude Desktop in Cowork mode. That is what gives the session the browser pane used in Step 5A. A session started on the web is not linked to the computer, so every Drive move goes through the connector and can trigger its own approval prompt.

Check the tool list. If browser pane tools (for example `Claude_Browser` tools) or `remote-devices` tools are present, the session is probably linked, so say nothing about it and continue (don't tell the person their computer is linked until a call to one of those tools has actually succeeded). If they are absent, the session is probably on the web. In that case, before doing anything else, tell the person once, briefly: for fewer permission prompts they should start a new session in the Claude Desktop app with Cowork, make sure the computer is linked, and run this skill there (a link added mid-session doesn't always take effect, so a fresh session is more reliable). Then ask whether they want to switch or continue here. If they want to continue here, carry on with the connector route (5B) and don't bring it up again.

## Step 0: Access diagnostic

Before scanning anything, confirm the person running this can actually write to the shared Drive.

1. Find the shared Hyfin Drive root. As of October 2026 it is a shared drive named "Hyfin Team Drive" (the Drive API reports its root folder as "Drive") with root ID `<shared-drive-root-id>`. Verify with `get_file_metadata` before relying on that ID. Its existing top-level folders are the legacy structure (`01_Internal and Workplanning`, `02_Market Research`, `03_Fund Forge`, `04_Guarantee Facilities`, `05_AssetCos`, `06_Funds`, `07_GAIA`). Never move, rename, or trash those.
2. Call `get_file_permissions` on the root and find the runner's own entry. Writer, fileOrganizer, or organizer: proceed. Reader, commenter, or no entry: stop. Tell the person plainly what role they have, that moves and folder creation will fail with "caller does not have permission", and that an organizer (currently <name redacted>) needs to raise their role. Do nothing else in this case.
3. Look at the same permissions list for broader access. Every Hyfin member should be able to use this skill and see filed documents. If the list shows only named individuals and no Hyfin domain or group entry, tell the person that other teammates may not be able to run the skill or open filed files, and suggest an organizer add the Hyfin domain or a group. Report this only. Never change sharing yourself.
4. If a later move fails with a permission error even though the role looked sufficient, report which file and stop rather than retrying in a loop.

## Step 1: Locate the destination tree

Search the shared Hyfin Drive for each top-level folder in the taxonomy below (`00-Needs-Review`, `01-Guarantees`, etc.) and each of their sub-folders. Keep a lookup of `folder name -> folder ID` for the rest of the run. The new tree sits alongside the legacy folders, so on a first run most of it will not exist yet.

Don't create the whole tree up front. That would add a pile of empty top-level folders that everyone sees. Create a missing folder (folder mime type `application/vnd.google-apps.folder`, nested correctly, parents first) only in Step 5, and only when an approved move needs it. Creating folders works fine through the Drive connector. If the folder appeared in the meantime, reuse it.

## Step 2: Find candidate files

There is exactly one source: **the runner's own My Drive.** Search for files the runner owns that are not inside any shared drive (query `owner = 'me'`, excluding folder mime types). A file counts as being in My Drive only if its parent chain ends at the runner's My Drive root, so drop any result that sits inside a shared drive (for example one whose parent is a folder in the Hyfin Team Drive or the Hyfin AssetCo Data Rooms drive, or one that reports a shared-drive ID), even if the runner is its owner or organizer. Look up parent folder titles so the report can show the My Drive folder each file currently lives in.

Never scan, search for, or propose moves for anything inside a shared drive. That covers the Hyfin Team Drive's legacy folders (`01_Internal and Workplanning`, `02_Market Research`, `04_Guarantee Facilities`, and the rest), files already filed under the new tree, and every other shared drive the runner can see. This is true even when the runner is an organizer there and the files look unsorted. Don't mention them in the report either, except for a single line at the top if the person asked about them.

Don't count files owned by someone else, files merely shared with the runner, or files they can only see through a shared drive. The runner can't move other people's files, and listing them is noise. Leave them out silently. If there are many, one summary line at the end ("N files shared with you are owned by others, so their owners would need to run this skill") is enough, with no filenames.

If this search finds nothing Hyfin-related, stop after the report. Say plainly that there is nothing to move from the person's My Drive.

**Hyfin-related files only.** Many team members have a day job or school work alongside Hyfin, so their My Drive is a mix. Only files with a clear Hyfin signal are candidates for moving: the filename, path, or title matches a cue in the taxonomy below, or it clearly refers to Hyfin work (Hyfin, GAIA, Tara, CORE, Dhamana, named Hyfin vehicles, Hyfin teammates in a Hyfin context). Judge this from the filename, path, and title only, never by opening the file. If there is no clear Hyfin signal (coursework, a day-job document, a personal file, or a title you simply can't place), leave the file alone. Don't propose it, don't run the sensitivity check on it, and don't classify it. List such files by name only in a short "Not touching" section of the report so the person can pull any of them in if they disagree.

**Weekly sync:** same search, restricted to files created or modified in the last 7 days. Use a rolling 7-day window computed from the current date rather than a persisted "last run" timestamp, which is simpler and self-healing if a run is missed. Files that were already moved out of My Drive in an earlier run no longer match the My Drive search, so they don't resurface.

Paginate until the search stops returning a next-page token. Flag likely duplicates (same title, near-identical size) in the report. Never trash a duplicate.

## Step 3: Classify each candidate

For each file, in order:

0. **Hyfin gate.** Apply the "Hyfin-related files only" rule from Step 2. A My Drive file with no clear Hyfin signal stops here and goes on the "Not touching" list. This matters because a person's personal or day-job files (a tax form, a payslip from another employer) would otherwise trip the sensitivity check and get proposed for the shared drive.
1. **Sensitivity check.** For files that passed the gate, run the file's name, path, and title against the sensitivity check below. If it trips, mark it for `00-Needs-Review` with reason `sensitive - manual review` and move on. Do not classify it further, do not open it to check.
2. **Otherwise, classify against the taxonomy below.** Match filename, current folder context, and title against the cues for each folder. Assign one destination and a confidence (high / medium / low).
3. **Low confidence or no reasonable match** goes to `00-Needs-Review` with reason `unclear match`, not a forced guess. (This is for files that are clearly Hyfin but don't fit a folder. A My Drive file with no Hyfin signal at all never gets here; it was already left alone at step 0.)

Don't open and read full file contents to classify. Filename, path, and title are enough for the great majority of files. If a title alone is genuinely ambiguous, a quick skim of the first few lines is fine.

**Sharing check (read-only).** For every file that is proposed to move, call `get_file_permissions` and note whether it has anyone-with-link access or any non-Hyfin person or domain. Show this as a "shared externally" marker in the report so the runner knows which moves matter most for link continuity. Do this after classification so sensitivity-flagged files are not inspected beyond their metadata. Also note any file whose parent My Drive folder is itself shared with other people: a file's own permissions survive a move, but access that people had only through the folder's share does not follow the file into the shared drive. Mark those rows (for example "teammates lose folder-level access") so the runner can decide. Folders can't be moved by the connector, so moving a whole shared My Drive folder needs the browser pane route (5A), which keeps the folder's contents and sharing together.

## Step 4: Build the approval report

This has to be a real per-file decision the person makes with one click each, not a printout. Use the Visualizer:

1. Call `visualize:read_me` with modules `["elicitation", "interactive"]` before your first `show_widget` call.
2. Render a widget listing every candidate file, grouped by proposed destination (Needs Review as its own group at the top). Each row shows: file name, current My Drive folder, proposed destination, one-line reason, the external-sharing marker if any, and three controls: **Approve**, **Recategorize** (dropdown of every folder in the taxonomy), **Skip** (leave it where it is). Default selection is Approve for normal matches and Skip for anything in Needs Review. The person should have to actively choose to move a flagged file, never the reverse. Nothing moves until the person submits.
   Below the table, add a short collapsed "Not touching" section listing, by filename only, the My Drive files that were left alone for having no clear Hyfin signal, each with a one-click "Pull in" option that lets the person pick a destination. State the counts up front ("proposing N moves, leaving M files alone"). The person can call out any proposed move they don't want, or any left-alone file they do want moved, after seeing the table.
3. For sensitivity-flagged rows, show only the filename and the reason (`sensitive - manual review`), not any content from the file.
4. Give it a Submit button that calls `sendPrompt()` with a plain structured summary of every decision (file ID, file title, action, destination if recategorized). Don't wire up any direct Drive API calls inside the widget. It only collects decisions; you execute them after they land back in chat.

If the Visualizer isn't available on this surface, fall back to a plain table in chat and ask the person to reply with their decisions. The widget is the intended path for single-click-per-file.

## Step 5: Execute approved moves

When the decisions come back:

- **Approve**: move the file (update its parent folder to the proposed destination ID).
- **Recategorize**: move it to whichever folder the person picked instead.
- **Skip**: leave it exactly where it is. Don't move sensitivity-flagged files unless the person explicitly picked a destination for one.

Create any missing destination folders first (parents before children), then move files. Moving into a shared drive transfers ownership of the file to the shared drive. Mention this once in the final summary.

There are two ways to execute the moves. Always start by testing the browser pane route (5A). If it isn't available or doesn't work, pivot to the connector route (5B) without further fuss.

### 5A: Browser pane route (Claude Desktop Cowork only)

The browser pane drives the Drive web UI with the person's own signed-in session. Its advantage is that it can move folders (which the connector can't) and that a one-time site-level allowance for drive.google.com replaces a permission prompt on every single move. Its cost is more steps per item (about 6 to 8 actions), so it is best for folders and for runs where per-file connector prompts would be unmanageable.

1. **Confirm the surface.** The browser pane only exists in Claude Desktop Cowork, which is why the "Before you start" section asks the person to run this skill in a fresh Claude Desktop Cowork session. Before using the pane, ask the person to confirm that is where they are running it. If they say no, or the browser pane tools aren't in the tool list, skip straight to 5B.
2. **Test it quickly.** Navigate the pane to a folder in the shared Hyfin Drive. If the pane says the site isn't allowed, call `request_access` for `https://drive.google.com` (ask for site scope so it persists) and retry once. Then look at what loads:
   - Page shows the folder contents under the Hyfin Team Drive: the pane works, continue.
   - Page shows "You need access" or is signed into a non-Hyfin account (for example a personal Gmail): the pane is signed into the wrong account. Do not click "Request access", do not try to sign in, and do not request access to accounts.google.com. Tell the person once that the pane needs to be signed into their Hyfin account, which only they can do. If they can't do that right away, pivot to 5B.
   - Any other failure (tools missing, access refused, page won't load after one retry): pivot to 5B immediately. Don't spend more than a couple of calls diagnosing it.
3. **Move through the Drive UI.** Open the shared drive root or the parent folder, find the item's row, right-click it, choose Organize, then Move, select the destination folder in the dialog (confirm the path line at the bottom shows the right destination), and press Move. Drive then shows a "Move item?" confirmation ("moving this item within a shared drive may change its permissions"). Confirm it, since the person already approved the move in Step 4. Folders move together with everything inside them.
4. **Verify with the connector, not the browser.** After each move, call `get_file_metadata` and confirm the new `parentId`. Do not trust the browser screenshot alone, since a dialog may still be waiting for confirmation.
5. Never click Request access, Share, or anything that changes sharing, and never enter credentials. Stay on drive.google.com.

### 5B: Connector route (fallback, and the default for plain file moves when 5A isn't wanted)

Use Drive `update_file` with `parentId`. Facts about this route:

- It can't move folders. Moving any folder, whether from My Drive into the shared drive or between folders inside the shared drive, fails with "The caller does not have permission" even for an organizer. For folders on this route, recreate the folder structure inside the shared Drive and move the files individually. Afterwards, check that the old My Drive folder is actually empty (search by its ID as the parent), and only then ask the person whether to trash it. Never trash a folder that still has contents, and never trash anything the person didn't ask you to trash. Creating folders works fine.
- Each `update_file` call is a separate tool call, and depending on the client each one can trigger its own approval prompt that shows only file IDs and no titles. Do the moves one at a time, in order, rather than firing many in parallel, so the person is only ever asked about one thing at once. Before the first move, print a numbered plan table (number, file title, file ID, destination) and execute in that same order so each prompt can be matched to a row. Tell the person how many prompts to expect.
- The person can avoid the prompts by setting the Drive connector's update tool to always allow for the session in connector settings, or by choosing the always-allow option on the first prompt. This is their setting to change, not yours. If they have done so, you may issue moves in parallel.
- For scheduled runs, the scheduled task needs its approval mode set to automatic, otherwise unattended runs will stall on the first prompt.
- Don't change a file's title just to make a prompt more readable. A title change is a real edit.

### After the moves (both routes)

Confirm with a search or `get_file_metadata` that every moved file reports its new parent. For any file marked as externally shared, re-check its permissions and tell the person if the sharing did not survive.

Finish with a short summary: how many moved, how many skipped, how many are still sitting in Needs Review and need a human to sort by hand, any files whose external sharing needs a second look, which route (5A or 5B) was used and why, and any access problems found in Step 0.

**End of the first manual run: offer the weekly schedule.** If this was the person's first manual run of the skill in this conversation (and they don't already have a "Hyfin Drive weekly sync" scheduled task, which you can check with the scheduled-task list tool), end the summary by proposing, in one or two sentences, to set up a weekly report-only schedule and to run a quick permission test of it. Ask once. If they say no, drop it and don't raise it again. If they say yes, follow "Setting up the weekly schedule" below.

## Setting up the weekly schedule

Only do this after the person says yes (see the end of "After the moves"), or when they ask for a schedule directly.

**Which tools to use.** Create scheduled tasks with the scheduled-task tools (the Claude Code Remote connector's create, list, update, delete, and fire tools, which may be deferred, so load them with ToolSearch). Never use local cron tools. Those run inside the current session and are lost when it ends, so the schedule would silently never run. If no scheduled-task tools exist on this surface, walk the person to the Scheduled Tasks UI (Cowork's Scheduled panel or `/schedule`) rather than guessing at a path, and give them the cadence and prompt below to paste.

**1. Create the weekly task (report-only).**

- **Cadence:** weekly, Saturday, about 4:00 AM Eastern. Write the cron in Eastern time (for example `CRON_TZ=America/New_York 54 3 * * 6`, nudged a few minutes off the hour because tasks on the hour can be delayed).
- **Prompt:** it must stand alone, because every run starts a fresh session with no memory of this chat. Use a prompt along these lines: "Run the hyfin-drive-organizer skill in weekly sync mode. This is an unattended run, so nobody is available to approve moves. Look only at files I own in my own My Drive, never at anything inside a shared drive. Do the access diagnostic, scan my My Drive files created or modified in the last 7 days, classify them (Hyfin-related files only, sensitivity check first), and produce the approval report as plain text in your final response: counts up front, a table of proposed moves (file title, file ID, current location, proposed destination, external-sharing marker), a Needs Review list, and a short Not touching list by filename only. Do not move, copy, rename, or trash any file in this run, and do not create folders. If the Google Drive connector isn't available or an access check fails, say exactly what failed and stop."
- Because Step 4 needs a person to approve, an unattended run only produces the report. The browser pane route is not available to it, and it only sees the My Drive of the account it runs under, so each team member needs their own task.
- **Approval mode is not yours to set.** The server decides whether the task's runs act without asking (automatic) or stop at the first approval prompt. After creating the task, read the result and tell the person in one sentence which mode it got. If it will ask, tell them they can switch the task to automatic approval in its settings, if their organization allows it.

**2. Offer the permission test.** After the task exists, offer once to verify that an unattended run can actually move a file through the Drive connector without anyone approving it. This is optional. If they decline, stop here. If they agree:

1. **Create a test file** in the person's My Drive with the Drive connector, a small Google Doc titled with a clear Hyfin signal so nobody mistakes it for real work, for example "TEST Hyfin GAIA Scheduled Sync Check (safe to delete)". Note its file ID and that its parent is their My Drive.
2. **Find the destination folder ID** for the test (for example `03-GAIA`, creating it first only if the person approves, since folders are otherwise created only for approved moves).
3. **Create a separate one-off scheduled task with no schedule**, whose own prompt authorizes the single move. Don't put the authorization in the text passed when firing a task. A run correctly treats fire-time text as data and follows its saved prompt, so a move requested only that way gets refused (this was observed). The test prompt should say: this is a one-off permission test authorized by the user; move exactly one file (give its exact title and ID) into the named destination folder (give its ID) with Drive `update_file` by setting `parentId`; it must be a real move, never a copy; do not touch any other file or folder; afterwards call `get_file_metadata` and confirm the new parent; and in the final response state whether the `update_file` call ran straight through, asked for approval, or was blocked, quoting any error text, plus the file's parent before and after.
4. **Fire the one-off task**, then wait a minute or two and check the file with `get_file_metadata`. A run can show as pending for a bit. If the file's `parentId` is now the destination folder, the test passed: the file kept its ID, and since moving into a shared drive transfers ownership, the owner field may disappear. If the parent is unchanged, ask the person to open the run and share its final message, then report what blocked it. If the cause is an approval prompt, the task needs automatic approval in its settings.
5. **Report the result plainly:** whether an unattended Drive move works with no approval prompt, and the reminder that this proves only the connector's behavior. The weekly task itself stays report-only, and turning it into a mover would mean dropping the "never moves without approval" rule, so don't do that unless the person explicitly asks and understands the trade-off.
6. **Offer cleanup, don't just do it.** Ask before trashing the test file (it now sits in the shared drive) and before deleting the one-off test task. Only act on a clear yes.

Run the skill once manually before trusting the schedule, which is why this offer comes at the end of the first manual run.

---

# Folder taxonomy and cues

This is the single source of truth for where a file belongs. It mirrors the ClickUp Space/Folder structure and the six-workstream org chart [REDACTED] signed off on. Classify every file against this list, not against memory or guesswork about what the tree "should" look like.

Root of the shared Hyfin Drive should eventually contain these top-level folders alongside the legacy ones (see Step 1 for how and when they get created):

```
Hyfin/
├── 00-Needs-Review/
├── 01-Guarantees/
│   ├── Cambodia-EVGF/
│   ├── BRD/
│   ├── Dhamana/
│   ├── CEFIL-NCGCL-Guarantee/
│   └── Other-Guarantees-PH-Malaysia-Ethiopia-Agrivoltaics/
├── 02-Funds/
│   ├── AssetCo-Pipeline/
│   ├── CAFF/
│   ├── CMRF/
│   └── CEFIL-Green-NBFC/
├── 03-GAIA/
│   ├── Tara-Deliverable/
│   ├── OEM-AVL-Agent/
│   ├── Credit-Assessment-Agent-GAIA-Roadmap/
│   └── News-Agent/
├── 04-Fund-Forge/
├── 05-BUS/
└── 06-Org-Team/
    ├── Front-Office/
    │   └── Advisory-Board/
    ├── Back-Office/
    ├── Team-Hiring/
    └── AI-Native-Org/
```

`00-Needs-Review` is not a workstream. It's the parking lot for anything that fails classification or trips the sensitivity check. Never guess a destination for a file that belongs here. Park it and say why.

Match on filename, the file's current folder or path, and (only if those are ambiguous) a light skim of the file's title or first lines, not a full read. Cues are illustrative, not exhaustive. Use judgment for anything that clearly fits a bucket by subject matter even if it doesn't contain the literal keyword.

| Folder | Cues |
|---|---|
| Cambodia-EVGF | "EVGF", "Cambodia", "[REDACTED]", "AVL" (when paired with Cambodia) |
| BRD | "BRD", "[REDACTED]" + guarantee/facility context |
| Dhamana | "Dhamana", Islamic finance / risk-sharing guarantee structuring |
| CEFIL-NCGCL-Guarantee | "CEFIL", "NCGCL", "Pakistan" + guarantee/facility context |
| Other-Guarantees-... | "PhilGuar", "Philippines", "Malaysia", "Ethiopia", "Agrivoltaics", "Renew2030" + guarantee context |
| AssetCo-Pipeline | "AssetCo", named opportunities ([REDACTED], [REDACTED], [REDACTED], [REDACTED], [REDACTED], [REDACTED], [REDACTED], [REDACTED], [REDACTED], [REDACTED]), "[REDACTED]", "[REDACTED]" |
| CAFF | "CAFF", "Catalytic Aggregation", "CORE Anchor Fund", "anchor fund" |
| CMRF | "CMRF", "Clean Mobility Receivables", "[REDACTED]" + fund context |
| CEFIL-Green-NBFC | "CEFIL", "Green NBFC", "Pakistan" + fund/lending context (not guarantee) |
| Tara-Deliverable | "Tara", "financial institution mapping", "FI mapping", "[REDACTED]" |
| OEM-AVL-Agent | "OEM", "AVL", "Approved Vendor List", "[REDACTED]" |
| Credit-Assessment-Agent-GAIA-Roadmap | "Credit Assessment Agent", "Cap Stack Agent", "BUS Agent" (legacy names), "GAIA roadmap" |
| News-Agent | "News Agent", market/news monitoring for GAIA |
| Fund-Forge | "Fund Forge", "[REDACTED]" |
| BUS | "The BUS", "back-up servicer", "[REDACTED]" |
| Front-Office | front-office ops, deal-facing admin not tied to a specific vehicle |
| Advisory-Board | "advisory board", board member recruitment/bios |
| Back-Office | ops, bookkeeping, [REDACTED], [REDACTED], benefits admin (see sensitivity check) |
| Team-Hiring | job descriptions, hiring pipeline, interview notes (not individual comp, see sensitivity check) |
| AI-Native-Org | internal AI tooling, prompts, Claude Projects/skills documentation, sprint process |

If a file plausibly fits two folders, prefer the more specific one (a Pakistan guarantee memo goes to `CEFIL-NCGCL-Guarantee`, not the parent `01-Guarantees`). Files that belong at a parent level with no clear sub-item (for example a cross-cutting GAIA overview, tracker, or roadmap-adjacent document) go directly in the parent folder (`03-GAIA/`), not forced into a sub-item.

---

# Sensitivity check (run before classification)

This check runs first, before any workstream classification. If a file trips it, skip classification entirely and park it in `00-Needs-Review` with reason `sensitive - manual review`. Never propose a workstream destination for a flagged file, even a low-confidence guess.

Check filename, current folder path, and (if still ambiguous) the document title only. Never open or summarize the body of a file to decide this. Reading a sensitive file's contents to double-check is the wrong move. Over-flag instead.

## Flag on any of these (filename, path, or title match)

- Compensation and pay: comp, compensation, salary, salaries, pay band, pay bands, offer letter, bonus, raise, equity grant, cap table, option grant, vesting
- Payroll and benefits admin tied to a named person: payroll, W-2, W2, 1099, paystub, direct deposit, tax withholding
- Personal identifiers: SSN, social security, passport, government ID, background check
- Employment actions: termination, severance, PIP, performance improvement plan, disciplinary
- Health: medical, health insurance claim, workers comp (the claim or case itself, not the general benefits policy document)
- Legal exposure: lawsuit, dispute, demand letter, settlement, subpoena, NDA violation
- Anything with an individual's full name paired with a dollar figure, a review score, or a medical or legal term in the filename

## Do not flag

General policy documents with no individual tied to them (for example "Hyfin Benefits Overview", "Vacation Policy", "Hiring Process Playbook") are not sensitive on their own. They go through normal classification into `Back-Office` or `Team-Hiring`. Only individual-specific instances (a named person's offer, comp, or case file) trigger the flag.

When in doubt, flag it. A false positive costs someone one extra click in the review folder. A false negative puts comp or health data in a shared team folder.
