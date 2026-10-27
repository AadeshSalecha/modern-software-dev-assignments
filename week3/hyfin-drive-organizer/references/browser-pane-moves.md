# Route 5A: moves through the Drive web UI (browser pane)

Use this route for folders and for anything that already lives inside a shared drive, which the connector cannot move. It drives drive.google.com in the person's own signed-in session. It costs roughly 6 to 8 actions per item, so plain single-file moves from My Drive are usually faster on the connector route.

## Preconditions

1. Browser-pane tools are in the tool list (Claude Desktop, Cowork mode, computer linked). If not, skip this route.
2. Navigate to a Hyfin Team Drive folder. If the client says the site isn't allowed, request site-scoped access for `https://drive.google.com` once and retry once.
3. Read what loaded:
   - The folder contents under the Hyfin Team Drive: continue.
   - "You need access", a sign-in page, or a non-Hyfin account (a personal Gmail): stop. Tell the person once that the pane must be signed into their Hyfin account and only they can do that. Do not click Request access, do not sign in, do not visit accounts.google.com.
   - Anything else after one retry: fall back to the connector route or a manual list. Don't spend more than a couple of calls diagnosing.

## Moving one item

Move items one at a time. Shift-click and ctrl-click multi-select did not work in the pane.

1. Open the item's current folder and find its row.
2. Wait about 2 seconds, then screenshot. Screenshots lag one step behind clicks.
3. Right-click the row. Wait, then screenshot again **before** choosing anything. The screenshot frame is about 800 px wide, so menu positions shift from what you expect; a blind click once hit "Move to trash" (it was cancelled and nothing was deleted).
4. Choose Organize, then Move.
5. In the Move dialog's search box, paste the destination folder's URL (`https://drive.google.com/drive/folders/<folder ID>`). This jumps straight to the folder. Double-click the result to drill into it.
6. Screenshot and confirm the breadcrumb at the bottom of the dialog shows the right destination path. If it doesn't, fix it before pressing anything.
7. Press Move. If Drive shows "Move item?" (moving within a shared drive may change permissions), confirm it; the person already approved this move.
8. Verify with the connector: read the item's metadata and check that its parent is the destination folder ID. Don't trust the screen, since a dialog can still be pending behind a screenshot that looks done.
9. If the item was externally shared, read its permissions and compare with the before snapshot. Moves inside a shared drive can drop direct permissions.

Folders move together with their contents and keep their own sharing.

## Never

Click Share, Request access, or anything that changes sharing; enter credentials; leave drive.google.com; use "Make a copy"; delete or trash anything.
