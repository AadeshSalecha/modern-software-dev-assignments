# Test fixtures

All fixtures are scrubbed copies of real `keep.googleapis.com/v1` responses
(`keep-mcp-setup/secrets/probe_output.txt`, 2026-10-06). Every email address is
`user@example.com` (or `owner@example.com` in hand-built fake data) and every
note/permission id is replaced with a `AAAsample...` placeholder that still
matches `^notes/[A-Za-z0-9_-]+$`. No token, client secret, or account identifier
from `secrets/` appears in this repository.

| File | Provenance |
|---|---|
| `note_text.json` | probe step 5b/7, `notes.create` + `notes.get` of a text note (verbatim shape) |
| `note_checklist.json` | probe step 6/7, checklist note with `checked` round-tripping |
| `list_empty.json` | probe step 2: an account with nothing to list answers `{}`, not `{"notes": []}` |
| `notes_list_two.json` | composed from the two note fixtures above (probe never dumped a non-empty `notes.list` body) |
| `error_403_note.json` | probe step 7b/9b: a missing, malformed, or deleted note returns **403 PERMISSION_DENIED**, never 404 |
| `error_400_invalid_filter.json` | probe step 3: `trashed:false` / `trashed = false` are invalid filters |
| `error_400_empty_body.json` | probe step 5: title-only create is rejected on field `note.body` |
| `error_400_unknown_recipient.json` | probe step 8a: share with an unknown user. The probe output truncated the `description`, so that one string is reconstructed; the `field` (`requests[0].permission`) is verbatim |
| `error_429_rate_limited.json` | constructed: no 429 was provoked live; Google's documented shape |
| `error_503_unavailable.json` | constructed: no 5xx was provoked live; Google's documented shape |
| `auth_oauth_client_placeholder.json` | shape of a Desktop `client_secret` JSON with placeholder credentials |
| `auth_userinfo.json` | shape of `openidconnect.googleapis.com/v1/userinfo` (`email`, `email_verified`) |
| `auth_refresh_response.json` | refresh-token grant shape; scope string taken from the live demo run |
| `auth_jwt_bearer_response.json` | jwt-bearer grant shape; `expires_in: 3599` matches the live demo run |
| `auth_signjwt_response.json` | `iamcredentials ...:signJwt` shape (`signedJwt`) |
| `auth_token_file_existing_format.json` | the token-file format the server must also accept when it finds one on disk (`refresh_token`/`access_token`/`expires_in`/`scope`, no timestamp) |
