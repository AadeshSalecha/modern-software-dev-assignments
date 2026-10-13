# Weekly report-only schedule, and the optional permission test

Do this only when the person asks for a schedule, or says yes to the offer at the end of their first manual run.

## Which tools

Use the client's scheduled-task (routine) tools: create, list, update, delete and fire. Load them with ToolSearch first; they are often deferred. Never use local cron or in-session loop tools: they live inside the current session and die with it, so the schedule would silently never run. If no scheduled-task tool exists, point the person at their client's Scheduled tasks UI and give them the cadence and prompt below to paste.

Before creating anything, list existing tasks. If one named "Hyfin Drive weekly sync" (or doing the same job) exists, don't create a duplicate; offer to update it instead.

## 1. Create the weekly task

- **Name:** Hyfin Drive weekly sync
- **Cadence:** Saturdays around 4:00 AM Eastern, nudged off the hour: `CRON_TZ=America/New_York 54 3 * * 6`
- **Prompt** (it must stand alone; each run starts a fresh session with no memory of this chat):

> Run the hyfin-drive-organizer skill in weekly sync mode. This is an unattended run, so nobody can approve moves. Look only at files I own in my own My Drive, never at anything inside a shared drive. Do the access diagnostic, scan my My Drive files created or modified in the last 7 days, classify them (Hyfin gate first, then the sensitivity check, then the taxonomy), and give the approval report as plain text in your final response: counts up front, proposed moves (title, file ID, current folder, destination, sharing marker), the Needs Review list, and the Not touching list by filename only. Do not move, copy, rename or trash anything, and do not create folders. If the Drive connector isn't available or the access check fails, say exactly what failed and stop.

After creating it, read the result and tell the person in one sentence whether the server gave it automatic approval or ask-first approval. That mode is set by the server and their organization, not by you. A scheduled run only sees the My Drive of the account it runs under, so each teammate needs their own task, and the browser pane is never available to it.

## 2. Optional permission test

Offer once to check that an unattended run can move a file through the connector with nobody approving. If they decline, stop.

1. Create a small Google Doc in their My Drive with a clear Hyfin signal and an obvious throwaway title, for example "TEST Hyfin GAIA Scheduled Sync Check (safe to delete)". Note its ID.
2. Find the destination folder ID (for example `03-GAIA`). Create the folder only if the person approves.
3. Create a **separate one-off task with no schedule** whose saved prompt authorizes the single move. Never put the authorization in fire-time text: runs treat that as data and refuse (observed). The saved prompt says: this is a one-off permission test authorized by the user; move exactly this one file (exact title and ID) into this folder (ID) by changing its parent; a real move, never a copy; touch nothing else; afterwards read the file's metadata and confirm the new parent; in the final response say whether the move ran straight through, asked for approval or was blocked, quoting any error, plus the parent before and after.
4. Fire the one-off task, wait a minute or two, then read the file's metadata. A run can sit as pending for a while. Parent now equals the destination: passed (same ID; the owner field may vanish because the shared drive owns it). Parent unchanged: ask the person to open the run and share its final message, then report what blocked it.
5. Report plainly whether an unattended connector move works without a prompt. This proves only the connector's behaviour. The weekly task stays report-only; making it a mover would drop the "never move without approval" rule, so don't, unless the person explicitly asks and understands the trade-off.
6. Ask before trashing the test file and before deleting the one-off task. Act only on a clear yes.
