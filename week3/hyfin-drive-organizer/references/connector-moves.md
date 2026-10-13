# Route 5B: moves through the Google Drive connector

The default for single files moving from the runner's My Drive into the Hyfin Team Drive.

## What it can and can't do

- Can: move one file from My Drive into a shared-drive folder by changing its parent folder; create folders (folder MIME type `application/vnd.google-apps.folder`, with the parent set).
- Can't: move a folder (any folder, anywhere), or move anything that already sits inside a shared drive. Both fail with "The caller does not have permission", even for an organizer. Don't retry; send those items to the browser route or list them for the person.
- Never use the connector's copy tool for organizing, for any reason.

## Order of operations

1. Print a numbered plan table before the first move: number, file title, file ID, destination path, destination folder ID. Depending on the client, every move can raise its own approval prompt that shows only IDs, so the person needs the table to match prompts to rows. Tell them how many prompts to expect.
2. Create missing destination folders first, parents before children. Re-check by title right before creating, and reuse a folder that already exists.
3. Move the files one at a time, in table order. Each move sets the file's parent to the destination folder ID. If the person has set the update tool to always allow, parallel calls are fine.
4. After each move, read the file's metadata: the parent must be the destination ID and the file ID unchanged. The owner field may disappear because the shared drive now owns it.
5. On any error, stop on that item, quote the error text, and carry on with the next item only if the error is clearly specific to that file. A permission error on a plain My Drive file usually means the role check was wrong; stop the run and report it.

## Moving a whole My Drive folder without the browser

Recreate the folder (and its subfolders) inside the destination, move the files individually, then search for anything still parented to the old My Drive folder. Only if it is empty, ask the person whether to trash it. Never trash a folder with contents, and never trash anything unasked. Warn the person that anyone who had access only through the old folder's share loses it.

## Prompts

Don't change a file's title to make a prompt readable; that is a real edit. Turning on always-allow for the update tool is the person's setting to change, not yours.
