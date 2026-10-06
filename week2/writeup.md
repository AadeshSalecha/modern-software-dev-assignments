# Week 2 Write-up

## Part I: The Server

**API chosen**, and why:
> The official Google Keep API (`keep.googleapis.com/v1`): Keep is the notes service I use, and the supported API exposes real text/checklist notes, collaborators, and deletes. I use the official API rather than scraping the web UI. The server wraps five composable operations: search, get, create, share, and delete.

**How to run it** (one command):
```bash
cd week2 && uv run keep-mcp
```
One-time interactive sign-in before starting the server: `cd week2 && uv run keep-mcp login`.

| Tool | What it does | Read/Write | Composes with |
|---|---|---|---|
| `search_notes` | Substring-search title, text, or checklist items; returns shaped hits and resource names | Read | Produces `name` for `get_note`, `share_note`, and `delete_note` |
| `get_note` | Returns shaped text/checklist state, collaborators, and timestamps | Read | Takes the name from search, create, or an exact user-supplied resource name |
| `create_note` | Creates a non-empty text or checklist note and returns its name | Write | Feeds `get_note`, `share_note`, and `delete_note` |
| `share_note` | Adds up to 10 WRITER collaborators; existing collaborators are skipped | Write, idempotent | Takes a name from search/create; verify with `get_note` |
| `delete_note` | Permanent delete; defaults to a preview and safe-mode guard | Destructive | Takes a name from search/create; commits only after a later confirmation |

## Part II: Agent Ergonomics

| Decision | Where | Why |
|---|---|---|
| Schema-level constraint | `src/keep_mcp/models.py:21-37,43-97`; `src/keep_mcp/tools.py:308-322,355-366` | `NoteState` is a Literal, names must match `^notes/[A-Za-z0-9_-]+$`, result bounds are constrained, and note content is a required discriminated text/checklist union. Invalid shapes fail at the schema boundary. |
| Output shaping (fields kept vs. dropped) | `src/keep_mcp/models.py:103-166`; `src/keep_mcp/tools.py:168-225` | Search keeps name/title/snippet/kind/update/shared count; detail keeps text or checked checklist items, collaborators, attachments count, and timestamps. Raw Keep keys such as `body`, `listItems`, and `textContent` are not passed through. |
| Structured errors (retry vs. don't-retry) | `src/keep_mcp/errors.py:55-64,102-135,166-192`; `src/keep_mcp/tools.py:277-285` | Errors carry a category, code, `retryable`, optional retry delay, and an actionable hint; tool boundaries return structured `ok=false` data rather than leaking tracebacks. |
| Docstring that chains tools together | `src/keep_mcp/tools.py:324-345,369-386`; server-wide workflow in `src/keep_mcp/server.py:29-61` | Search says where names come from, get accepts the exact returned/user-supplied resource name, and server instructions tell the agent to search first when a note is described by content. |
| Brake on the write tool | `src/keep_mcp/tools.py:429-480`; `src/keep_mcp/server.py:46-51,68-73` | `dry_run=true` previews by default; permanent commit requires an explicit confirmation in a later user turn. Safe mode also refuses to commit deletes for notes the server did not create. |

**One thing changed after watching the agent misuse a tool:**
> The first G3 run previewed then immediately called `delete_note(dry_run=false)`; an intermediate retry supplied a reconstructed name that returned `note_not_accessible`. The first G4 run searched an explicit resource ID as text and stopped. I strengthened delete instructions to require a later confirmation and exact names, clarified that explicit IDs go straight to `get_note` and must not be retried, and documented substring/plural behavior after `grocery` returned no hits. Protocol tests now assert this guidance. Afterward G3 previewed and asked, committing only after “Yes, delete it”; G4 returned `note_not_accessible` without retry; G1 tried `groceries`, chained to `get_note`, and answered “oat milk and bananas.”

## Part III: OAuth

**Flow**: how a token is obtained, cached, and refreshed:
> `uv run keep-mcp login` runs authorization-code OAuth with PKCE, a local callback, state validation, and offline access (`src/keep_mcp/auth.py:431-443,445-489,491-530`). The refresh token is cached at `~/.local/state/keep-mcp/token.json` with mode 0600. Tool calls silently refresh the user token as needed, resolve the verified email from userinfo, use that user token to call IAM `signJwt` on the configured service account, exchange the signed delegation assertion for a Keep token, and cache the Keep token in memory until 60 seconds before expiry (`src/keep_mcp/auth.py:259-270,279-321,326-426`). No service-account key is stored or created.

**Scopes requested**, and why each is necessary:
> The user consent screen requests only `openid`, `email`, and `https://www.googleapis.com/auth/iam` (`src/keep_mcp/auth.py:63-66`). `openid` requests the OpenID Connect identity; `email` provides the verified account address that becomes the delegation subject (`auth.py:326-368`). `iam` lets that same user's token call `signJwt` on the service account (the user has Token Creator; `auth.py:370-405`). Google refuses Keep scopes on the consent screen with `400 invalid_scope` (issue tracker 210500028), so `https://www.googleapis.com/auth/keep` is **not** requested from the user. Instead, an administrator grants exactly that Keep scope to the service account through domain-wide delegation; the signed JWT carries it (`auth.py:61,370-381`). The user credential cannot read Keep by itself, and DWD is only exercised using that authenticated user's token. This hybrid is also necessary because the organization blocks service-account key creation.

**Secrets**: what's in env, what's gitignored:
> `KEEP_OAUTH_CLIENT_FILE` points to the downloaded Desktop client JSON (default `~/.config/keep-mcp/client_secret.json`); `KEEP_TOKEN_FILE` points to the 0600 cached token outside the repo. The optional `.env` holds only local configuration/paths and is ignored. The real `.mcp.json` and `.factory/mcp.json` are ignored; `.mcp.json.example` contains the stdio command and non-secret configuration. `.gitignore` excludes `.env*` (except the example), `.mcp.json*` (except the example), client-secret/credential JSON, token files, `.factory/mcp.json`, and `.venv` (`.gitignore:1-25`). No token, client secret, or service-account key belongs in the repository.

**Token dies mid-session**: what the agent sees:
> A revoked/expired refresh grant returns structured `login_revoked` / `auth_revoked`, `retryable=false`, says that no browser was opened, and gives `uv run keep-mcp login` as the next action (`src/keep_mcp/errors.py:126-135`). The server remains available and does not start OAuth inside a tool call. The captured revoked-token run is in `docs/failure_revoked_token.txt:1-31`; it uses a temporary invalid-token copy and leaves the real token file untouched.

## Part IV: Integration

**Registration config** (`.mcp.json.example`) and the client you used:
> `.mcp.json.example:1-20` registers `keep` over stdio with `uv --directory <week2-path> run keep-mcp`, the OAuth/token/state paths, the DWD service-account setting, and safe mode. Claude Code was not installed, so I used Factory Droid CLI v0.233.0 as the MCP client. The same `mcpServers` stdio entry can be copied to Claude Code's project `.mcp.json` (or registered with `claude mcp add`) after adjusting the local path. Droid reads the equivalent project config from `.factory/mcp.json`; I restricted the run with `--only-tools MCP:keep`. Droid docs use `.factory/mcp.json` for project configs.

**End-to-end transcript**: the prompt, the tools that fired with their arguments, the result:
```text
Prompt: “What's still unchecked on my grocery list in Keep?”

search_notes {"query":"grocery","state":"active","max_results":20}
  -> ok=true, count=0
search_notes {"query":"groceries","state":"active","max_results":20}
  -> ok=true, count=1: “[mcp-test] Groceries”, name=notes/<id>, kind=checklist
get_note {"name":"notes/<id>"}
  -> checklist: oat milk unchecked; coffee checked; bananas unchecked; bread checked
Answer: “Still unchecked: oat milk and bananas.”
```
The full redacted trace, including compact tool results, is `docs/agent_transcript_chain.txt`.

**A failure, handled**: what you provoked, what the agent saw, what it did next:
```text
Prompt: “Show me the Keep note notes/<id>” (test resource name scrubbed)
get_note {"name":"notes/<id>"}
  -> ok=false, code=note_not_accessible, category=not_found, retryable=false;
     hint says to get a fresh name from search_notes
Agent: reported that it could not access the note; it did not retry the same ID.
```
Full trace: `docs/agent_transcript_failure.txt`. Separately, `docs/failure_revoked_token.txt` records the mid-session revoked-login failure.

**Protocol-level test**: what it covers and how to run it:
> The L1 suite uses `fastmcp.Client(server)` over in-memory MCP framing with `FakeKeepClient` and `FakeAuth` (`tests/conftest.py:1-6,42-51`; `tests/helpers.py:44-67`). `tests/test_protocol.py` checks tool discovery/schema, annotations, chaining, output shape, structured results, and the delete brake; `tests/test_errors.py` exercises actionable errors at the protocol boundary. Run offline with `cd week2 && uv run pytest -q`. The separate real-server stdio smoke is `KEEP_LIVE=1 uv run python scripts/smoke_live.py`; captured evidence is `docs/smoke_live_output.txt`.

## Submission
1. Confirm this write-up has no unfinished placeholders.
2. Confirm no tokens, client secrets, cached token file, or real `.mcp.json` are committed.
3. Push all changes to your remote repository and submit via Gradescope.
4. Clean up (optional): remove the server from your agent config, delete your cached token, and revoke the OAuth app's access.
