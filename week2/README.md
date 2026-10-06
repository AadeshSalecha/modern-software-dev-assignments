# keep-mcp

A FastMCP server over stdio for the official Google Keep API
(`keep.googleapis.com/v1`). It exposes note search, detail, create, share, and
delete tools. Delete previews by default, requires a later user confirmation
before commit, and refuses unmanaged notes in safe mode.

## Google Cloud and Workspace setup

Do this once in a Google Cloud project associated with the Workspace
organization whose Keep account you want to use:

1. Create/select the Cloud project. Enable **Google Keep API**
   (`keep.googleapis.com`) and **IAM Service Account Credentials API**
   (`iamcredentials.googleapis.com`).
2. Configure the OAuth consent screen as **Internal**. Create a **Desktop app**
   OAuth client and download its client JSON. Store it outside the repository;
   the default is `~/.config/keep-mcp/client_secret.json`.
3. Create a service account for delegated Keep access and enable **Google
   Workspace domain-wide delegation** on it; note its OAuth client ID. Do
   **not** create or download a service-account key. Grant the signed-in
   Workspace user **Service Account Token Creator** on this service account;
   the server uses that user's OAuth token to call IAM `signJwt`.
4. In the Workspace Admin console, add the service account's OAuth client ID
   under **Security → Access and data control → API controls → Domain-wide
   delegation**. Authorize only
   `https://www.googleapis.com/auth/keep`.
5. The user login asks for `openid`, `email`, and
   `https://www.googleapis.com/auth/iam`; these identify the principal and let
   it call `signJwt`. Google refuses Keep scopes on the user consent screen with
   `invalid_scope` (issue 210500028), so Keep authority comes from the admin's
   exact `auth/keep` DWD grant. Organization policy blocks service-account key
   creation, which is why this setup signs the delegation JWT through IAM
   instead of using a key file.

If using non-default paths or a different service account, set
`KEEP_OAUTH_CLIENT_FILE` and `KEEP_DWD_SERVICE_ACCOUNT` in your shell or in a
local `.env` copied from `.env.example`. `.env` is gitignored. Defaults are
defined in `src/keep_mcp/config.py`.

## Install, sign in, and run

Install dependencies, then do the one-time browser login:

```bash
cd week2
uv sync
uv run keep-mcp login
```

The refresh token is cached with mode 0600 at
`~/.local/state/keep-mcp/token.json`. Start the stdio server (normally the MCP
client starts it):

```bash
uv run keep-mcp
```

The OAuth login is the only command that opens a browser. Tool calls refresh
silently; a revoked login returns `auth_revoked` and tells the user to run
`uv run keep-mcp login` again.

## Register with an agent

`.mcp.json.example` is the stdio registration template. Adjust the
`--directory` path to the absolute location of this `week2` directory, then
copy its `mcpServers` entry:

- **Claude Code:** use that entry in a project `.mcp.json`, or register it with
  `claude mcp add keep -- uv --directory /absolute/path/week2 run keep-mcp`.
- **Factory Droid:** project MCP configuration lives in
  `.factory/mcp.json`; use the same JSON entry there. In the CLI, the server can
  be selected with `--only-tools MCP:keep`.

The example contains no OAuth client secret or token. Its local paths and
service-account name are configuration, not credentials. Keep the real
`.mcp.json`, `.factory/mcp.json` if it contains local data, and `.env` out of
version control.

## Tools

| Tool | What it does | Read/Write | Composes with |
|---|---|---|---|
| `search_notes` | Case-insensitive substring search over title, text, and checklist items; returns names | Read | Produces a `name` for all other tools |
| `get_note` | Shaped text/checklist details, collaborators, and timestamps | Read | Takes a name from search/create or an exact user-supplied `notes/...` name |
| `create_note` | Creates a text or checklist note | Write | Name feeds get/share/delete |
| `share_note` | Adds WRITER access for up to 10 people, skipping existing collaborators | Write, idempotent | Name from search/create; confirm with `get_note` |
| `delete_note` | Permanent delete with dry-run preview, separate confirmation, and safe-mode guard | Destructive | Name from search/create |

## Tests

Offline tests run the real server and MCP framing in memory with fake Keep and
auth clients:

```bash
cd week2
uv run pytest -q
```

The opt-in live test starts the actual stdio server and uses the signed-in Keep
account. It creates only `[mcp-test]` notes, cleans them up, and deliberately
does not alter the five pre-existing `[mcp-demo]` notes (currently in trash):

```bash
KEEP_LIVE=1 uv run python scripts/smoke_live.py
```

The revoked-token failure demo uses a temporary poisoned copy of the token file
and leaves the real token untouched:

```bash
KEEP_LIVE=1 uv run python scripts/smoke_live.py --revoked-token
```

## Cleanup

After the assignment, remove the agent registration; revoke the “Keep MCP”
grant under Google Account security; remove the service account's DWD entry in
the Admin console; then delete the service account or project and disable the
Keep/IAM Credentials APIs if no longer needed. Delete the local cached token and
managed-note registry, and remove the downloaded OAuth client JSON when done.
Search Keep for leftover `[mcp-test]` notes and delete only those assignment
test notes. **Do not modify or delete the five `[mcp-demo]` notes.** Full
resource-by-resource teardown notes are in
`/home/factory-user/keep-mcp-setup/CLEANUP.md` (outside this repository).
