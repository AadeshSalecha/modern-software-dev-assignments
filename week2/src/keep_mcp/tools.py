"""The five core tools.

The docstrings here *are* the contract: they say where every ID comes from, what
the agent gets back, and what to do with a failure. The schemas carry the hard
constraints (``NoteName`` pattern, ``state`` literal, ``max_results`` bounds,
discriminated ``content`` union, ``dry_run`` default), so an agent that only
reads the JSON schema still calls these correctly.

Nothing in this module raises out of a tool: :func:`_boundary` converts every
failure into ``ok=false`` plus an :class:`~keep_mcp.errors.ErrorInfo`.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Annotated, Any

from pydantic import BaseModel, EmailStr, Field

from .errors import ToolFailure, internal_error, invalid_argument, unknown_recipient
from .guard import ManagedNotes, delete_policy
from .keep_client import JSON, KeepApi
from .models import (
    ChecklistBody,
    ChecklistItemView,
    ChecklistChild,
    Collaborator,
    CreateNoteResult,
    DeleteNoteResult,
    DeletePreview,
    GetNoteResult,
    NoteContent,
    NoteDetail,
    NoteKind,
    NoteState,
    SearchHit,
    SearchNotesResult,
    ShareNoteResult,
    TextBody,
)

logger = logging.getLogger(__name__)

PAGE_SIZE = 100
SNIPPET_CHARS = 160

TRASH_FILTERS: dict[str, str | None] = {"active": "-trashed", "trashed": "trashed", "any": None}

_RECIPIENT_INDEX_RE = re.compile(r"requests\[(\d+)]")


# --------------------------------------------------------------------------- #
# wire helpers (Keep's own shapes stay in this module)
# --------------------------------------------------------------------------- #
def _title(note: JSON) -> str:
    return str(note.get("title") or "")


def _body(note: JSON) -> JSON:
    body = note.get("body")
    return body if isinstance(body, dict) else {}


def _text(note: JSON) -> str:
    text = (_body(note).get("text") or {}).get("text")
    return text if isinstance(text, str) else ""


def _items(note: JSON) -> list[JSON]:
    body = _body(note)
    if "list" not in body:
        return []
    raw = (body.get("list") or {}).get("listItems") or []
    return [item for item in raw if isinstance(item, dict)]


def _item_text(item: JSON) -> str:
    text = (item.get("text") or {}).get("text")
    return text if isinstance(text, str) else ""


def _children(item: JSON) -> list[JSON]:
    raw = item.get("childListItems") or []
    return [child for child in raw if isinstance(child, dict)]


def _item_texts(note: JSON) -> list[str]:
    texts: list[str] = []
    for item in _items(note):
        texts.append(_item_text(item))
        texts.extend(_item_text(child) for child in _children(item))
    return [text for text in texts if text]


def _kind(note: JSON) -> NoteKind:
    return "checklist" if "list" in _body(note) else "text"


def _is_trashed(note: JSON) -> bool:
    return bool(note.get("trashTime")) or note.get("trashed") is True


def _collaborators(note: JSON) -> list[Collaborator]:
    out: list[Collaborator] = []
    for permission in note.get("permissions") or []:
        if not isinstance(permission, dict):
            continue
        email = permission.get("email") or (permission.get("user") or {}).get("email")
        if isinstance(email, str) and email:
            out.append(Collaborator(email=email, role=str(permission.get("role") or "UNKNOWN")))
    return out


def _shared_with_count(note: JSON) -> int:
    return sum(1 for person in _collaborators(note) if person.role.upper() != "OWNER")


def _attachment_count(note: JSON) -> int:
    attachments = note.get("attachments")
    return len(attachments) if isinstance(attachments, list) else 0


def _clip(text: str, limit: int) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[: max(1, limit - 1)].rstrip() + "\u2026"


def _snippet(text: str, needle: str, limit: int = SNIPPET_CHARS) -> str:
    """Up to ``limit`` characters of context around the first match."""
    flat = " ".join(text.split())
    if not flat:
        return ""
    index = flat.lower().find(needle) if needle else -1
    if index < 0 or index <= 40:
        return _clip(flat, limit)
    return "\u2026" + _clip(flat[index - 40 :], limit - 1)


def _rfc3339(moment: datetime) -> str:
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _recency(hit: SearchHit) -> float:
    """Sort key for merged scans: parsed ``updated``, epoch for missing times."""
    try:
        return datetime.fromisoformat(str(hit.updated).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


def _time_filter(updated_after: datetime | None) -> str | None:
    if updated_after is None:
        return None
    return f'update_time > "{_rfc3339(updated_after)}"'


def _join_filters(*parts: str | None) -> str | None:
    present = [part for part in parts if part]
    return " AND ".join(present) if present else None


def _checklist_view(note: JSON) -> list[ChecklistItemView]:
    return [
        ChecklistItemView(
            text=_item_text(item),
            checked=bool(item.get("checked")),
            children=[
                ChecklistChild(text=_item_text(child), checked=bool(child.get("checked")))
                for child in _children(item)
            ],
        )
        for item in _items(note)
    ]


def _detail(note: JSON) -> NoteDetail:
    kind = _kind(note)
    return NoteDetail(
        name=str(note.get("name") or ""),
        title=_title(note),
        kind=kind,
        text=_text(note) if kind == "text" else None,
        checklist=_checklist_view(note) if kind == "checklist" else None,
        collaborators=_collaborators(note),
        attachment_count=_attachment_count(note),
        created=note.get("createTime"),
        updated=note.get("updateTime"),
    )


def _preview(note: JSON) -> DeletePreview:
    return DeletePreview(
        name=str(note.get("name") or ""),
        title=_title(note),
        kind=_kind(note),
        updated=note.get("updateTime"),
        collaborators=_collaborators(note),
        attachment_count=_attachment_count(note),
    )


def _hit(note: JSON, needle: str) -> SearchHit:
    if needle:
        item_match = next((text for text in _item_texts(note) if needle in text.lower()), None)
        if item_match is not None:
            snippet = _snippet(item_match, needle)
        elif needle in _title(note).lower():
            snippet = _snippet(_text(note) or ", ".join(_item_texts(note)), "")
        else:
            snippet = _snippet(_text(note) or ", ".join(_item_texts(note)), needle)
    else:
        snippet = _snippet(_text(note) or "; ".join(_item_texts(note)), "")
    return SearchHit(
        name=str(note.get("name") or ""),
        title=_title(note),
        snippet=snippet,
        kind=_kind(note),
        updated=note.get("updateTime"),
        shared_with_count=_shared_with_count(note),
    )


def _matches(note: JSON, needle: str) -> bool:
    if not needle:
        return True
    return needle in _title(note).lower() or needle in _text(note).lower() or any(
        needle in text.lower() for text in _item_texts(note)
    )


def _item_wire(item: Any) -> JSON:
    payload: JSON = {"text": {"text": item.text}, "checked": bool(item.checked)}
    if getattr(item, "children", None):
        payload["childListItems"] = [
            {"text": {"text": child.text}, "checked": bool(child.checked)} for child in item.children
        ]
    return payload


def _checklist_wire(content: ChecklistBody) -> JSON:
    """Checklist body in Keep's wire shape, rejecting what the live API rejects.

    Verified against the live API (2026-10-06): a create where a parent item is
    ``checked`` but one of its ``childListItems`` is not fails with
    HTTP 400 ``INVALID_ARGUMENT`` on ``child_list_items[n].checked``. Unchecked
    parents may carry children in either state, and a checked child under a
    checked parent round-trips fine.
    """
    for item in content.items:
        if not item.checked:
            continue
        unchecked = [child.text for child in item.children if not child.checked]
        if unchecked:
            raise ToolFailure(
                invalid_argument(
                    "Keep rejects a checked checklist item with unchecked sub-items: item "
                    f"{item.text!r} is checked but its sub-item(s) {', '.join(repr(t) for t in unchecked)} "
                    "are not.",
                    hint="Check every child of that item too, or leave the parent item unchecked.",
                )
            )
    return {"list": {"listItems": [_item_wire(item) for item in content.items]}}


def _body_wire(content: TextBody | ChecklistBody) -> JSON:
    if isinstance(content, ChecklistBody):
        return _checklist_wire(content)
    return {"text": {"text": content.text}}


async def _boundary(model: type[BaseModel], where: str, coro: Any) -> Any:
    """Await ``coro`` and turn any failure into the tool's structured result."""
    try:
        return await coro
    except ToolFailure as failure:
        return model(ok=False, error=failure.info)
    except Exception:  # noqa: BLE001 - the agent must never see a traceback
        logger.exception("unexpected error in tool %s", where)
        return model(ok=False, error=internal_error(where))


def _offending_recipient(message: str, candidates: list[str]) -> str | None:
    match = _RECIPIENT_INDEX_RE.search(message)
    if not match:
        return None
    index = int(match.group(1))
    return candidates[index] if 0 <= index < len(candidates) else None


# --------------------------------------------------------------------------- #
# tools
# --------------------------------------------------------------------------- #
class KeepTools:
    """Implementation of the five core tools, bound to one API client + registry."""

    def __init__(self, *, api: KeepApi, registry: ManagedNotes, safe_mode: bool = True) -> None:
        self._api = api
        self._registry = registry
        self._safe_mode = safe_mode

    # ------------------------------------------------------------------ #
    async def search_notes(
        self,
        query: Annotated[
            str,
            Field(max_length=500, description="Case-insensitive substring; empty matches every note in `state`."),
        ] = "",
        state: Annotated[
            NoteState,
            Field(description='Which notes to look at: "active" (not trashed), "trashed", or "any".'),
        ] = "active",
        updated_after: Annotated[
            datetime | None,
            Field(description="Only notes updated at or after this RFC3339 timestamp."),
        ] = None,
        max_results: Annotated[int, Field(ge=1, le=200, description="Maximum notes to return (1-200).")] = 50,
    ) -> SearchNotesResult:
        """Find notes and return the `name` values every other tool needs.

        Start here when the user describes a note by title/content or does not give
        a resource name. Use a returned `name` exactly as-is; `create_note` also
        returns names for chaining. Never invent or rewrite a resource name.

        Matching is a case-insensitive substring test against the note title, the
        text body, and checklist item text (including nested items); it is not
        fuzzy or stemmed ("grocery" does not match "groceries"). If a natural-
        language query returns no hits, try a likely spelling/plural variant before
        searching everything with an empty query. Notes are returned newest first.

        Args:
            query: What to look for, e.g. "grocer". Empty means "everything in `state`".
            state: "active" searches non-trashed notes, "trashed" searches only the
                trash, "any" searches both.
            updated_after: ISO timestamp; only notes changed since then are returned.
            max_results: Cap on returned notes; `truncated=true` tells you the cap bit.

        Returns:
            ok=true with `notes`, each holding `name`, `title`, `snippet`, `kind`
            ("text" or "checklist"), `updated`, and `shared_with_count`.
        """
        return await _boundary(
            SearchNotesResult,
            "search_notes",
            self._do_search(
                query=query, state=state, updated_after=updated_after, max_results=max_results
            ),
        )

    async def get_note(
        self,
        name: Annotated[
            str,
            Field(
                pattern=r"^notes/[A-Za-z0-9_-]+$",
                min_length=len("notes/") + 1,
                max_length=250,
                description=(
                    "Note name from search_notes or create_note, e.g. 'notes/1uFilIj6vTG4f...'."
                ),
            ),
        ],
    ) -> GetNoteResult:
        """Read one note by exact resource `name`, shaped for the agent: contents, collaborators, timestamps.

        The name may come from `search_notes` or `create_note`, or be an exact
        resource name supplied by the user. Pass it unchanged; do not search for an
        explicit resource name as if it were title text.

        Args:
            name: A resource name returned by `search_notes` or `create_note`, or
                an exact `notes/...` name supplied by the user (for example
                `notes/1uFilIj6vTG4f...`). A name that is deleted, malformed, or
                not visible to this account cannot be told apart by Google: it fails
                with `category="not_found"`, `code="note_not_accessible"`, and a hint
                to search for a fresh name. Do not retry that same name.

        Returns:
            ok=true with `note`: `title`, `kind`, either `text` or `checklist`
            (each item keeps `checked` and one level of `children`),
            `collaborators`, `attachment_count`, `created`, and `updated`.
        """
        return await _boundary(GetNoteResult, "get_note", self._do_get(name))

    async def create_note(
        self,
        title: Annotated[
            str,
            Field(min_length=1, max_length=1_000, description="Title for the new note."),
        ],
        content: Annotated[
            NoteContent,
            Field(
                description=(
                    'Note body. Pick the shape with "kind": '
                    '{"kind": "text", "text": "..."} or '
                    '{"kind": "checklist", "items": [{"text": "...", "checked": false, '
                    '"children": [{"text": "sub-item", "checked": false}]}]}. '
                    "A body is mandatory: the Keep API rejects an empty note. In a checklist, "
                    "a checked item must also have all of its children checked (a Keep rule "
                    "on create; unchecked parents may carry children in either state)."
                )
            ),
        ],
    ) -> CreateNoteResult:
        """Create a note in the signed-in user's Keep account and return its `name`.

        Args:
            title: The note title.
            content: The body, a discriminated union: `{"kind": "text", "text": ...}`
                or `{"kind": "checklist", "items": [...]}` where an item may carry
                `checked` and one level of `children`. A checked item must have all
                of its children checked too - the Keep API rejects the note
                otherwise (and rejects a note with no body, which is why this
                argument is required).

        Returns:
            ok=true with `name` (feed it to `get_note`, `share_note`, `delete_note`),
            `title`, `kind`, `created`, and `managed=true`, meaning this server
            recorded the note as its own so `delete_note` may remove it later.
        """
        return await _boundary(CreateNoteResult, "create_note", self._do_create(title, content))

    async def delete_note(
        self,
        name: Annotated[
            str,
            Field(
                pattern=r"^notes/[A-Za-z0-9_-]+$",
                min_length=len("notes/") + 1,
                max_length=250,
                description="Note name from search_notes (or the name returned by create_note).",
            ),
        ],
        dry_run: Annotated[
            bool,
            Field(description="Default true: preview only. Set false to actually delete."),
        ] = True,
        allow_foreign: Annotated[
            bool,
            Field(
                description=(
                    "Default false. Needed to delete a note keep-mcp did not create while "
                    "KEEP_SAFE_MODE is on."
                )
            ),
        ] = False,
    ) -> DeleteNoteResult:
        """Permanently delete a note. Copy its name exactly; preview first; commit only after later confirmation.

        Keep has no undo here, so this tool has a brake: `dry_run` defaults to true
        and returns a preview (title, kind, collaborators, last update) without
        deleting anything. Show that preview and ask the user to confirm. Never call
        `dry_run=false` in the same assistant turn as the preview, even when the
        user's initial request asked for deletion. Only a clear confirmation in a
        later user turn authorizes a second call with `dry_run=false`.
        Pass `name` exactly as returned by `search_notes`; do not reconstruct it from
        the title or make up a resource path.

        Safe mode also refuses notes this server did not create: those fail with
        `category="policy"`, `code="managed_notes_only"`, and an `override` field
        naming `allow_foreign` and `KEEP_SAFE_MODE`. A dry run still previews them
        and adds a `warnings` entry.

        Args:
            name: The note name from `search_notes` (or `create_note`).
            dry_run: true (default) previews; false deletes forever, and may be used
                only after showing the preview and receiving clear user confirmation
                in a later turn.
            allow_foreign: set true to delete one note that `search_notes` found but
                keep-mcp did not create.

        Returns:
            Dry run: ok=true, `deleted=false`, `preview`, and any `warnings`.
            Commit: ok=true, `deleted=true`, and the same `preview` of what was removed.
        """
        return await _boundary(
            DeleteNoteResult,
            "delete_note",
            self._do_delete(name=name, dry_run=dry_run, allow_foreign=allow_foreign),
        )

    async def share_note(
        self,
        name: Annotated[
            str,
            Field(
                pattern=r"^notes/[A-Za-z0-9_-]+$",
                min_length=len("notes/") + 1,
                max_length=250,
                description="Note name from search_notes or create_note.",
            ),
        ],
        emails: Annotated[
            list[EmailStr],
            Field(
                min_length=1,
                max_length=10,
                description="Up to 10 Google account addresses to share with; each gets the WRITER role.",
            ),
        ],
    ) -> ShareNoteResult:
        """Share a note with people, granting each of them the WRITER role.

        Idempotent: the note's current collaborators are read first, addresses that
        already have access are reported in `skipped` and left alone, and only the
        new ones are sent to the API in a single atomic call (so re-running the same
        call adds nobody and changes nothing).

        Args:
            name: The note name from `search_notes` or `create_note`.
            emails: 1-10 addresses of existing Google accounts. An address Google
                cannot resolve fails with `category="input"`,
                `code="unknown_recipient"`, and names the address; nothing is shared
                in that case.

        Returns:
            ok=true with `added` (just shared), `skipped` (already had access), and
            `shared_with` (the note's full collaborator list with roles, where the
            `OWNER` entry is the account that owns the note).
        """
        return await _boundary(ShareNoteResult, "share_note", self._do_share(name, list(emails)))

    # ------------------------------------------------------------------ #
    # implementations
    # ------------------------------------------------------------------ #
    async def _do_search(
        self,
        *,
        query: str,
        state: NoteState,
        updated_after: datetime | None,
        max_results: int,
    ) -> SearchNotesResult:
        needle = (query or "").strip().lower()
        time_filter = _time_filter(updated_after)
        # Which list scans to run, as (server-side filter, trash term used
        # client-side if the API rejects the combination). Verified live
        # (2026-10-06): notes.list with no filter hides trashed notes, and a
        # time filter does not constrain trash state (trashed notes are
        # included). So:
        #   - active / trashed: one scan with the trash filter (combined with
        #     the time filter when present);
        #   - any + updated_after: one scan with the bare time filter, which
        #     already spans both trash sides;
        #   - any alone: the default (active) view plus a "trashed" scan,
        #     merged, so "any" really means both.
        if state == "any":
            if time_filter:
                scans: list[tuple[str | None, str | None]] = [(time_filter, None)]
            else:
                scans = [(None, None), ("trashed", None)]
        else:
            trash = TRASH_FILTERS[state]
            scans = [(_join_filters(time_filter, trash), trash)]

        seen: set[str] = set()
        hits: list[SearchHit] = []
        truncated = False
        for filter_str, fallback_trash in scans:
            page_hits, page_truncated = await self._scan_with_fallback(
                filter_str, fallback_trash, time_filter, needle, max_results
            )
            truncated = truncated or page_truncated
            for hit in page_hits:
                if hit.name in seen:
                    continue  # a note trashed between the two scans could appear twice
                seen.add(hit.name)
                hits.append(hit)
        if len(hits) > max_results:
            hits = hits[:max_results]
            truncated = True
        if len(scans) > 1:
            # two list scans meet in one order: newest first, missing times last
            hits.sort(key=_recency, reverse=True)
        return SearchNotesResult(
            ok=True,
            query=query,
            state=state,
            count=len(hits),
            notes=hits,
            truncated=truncated,
        )

    async def _scan_with_fallback(
        self,
        filter_str: str | None,
        fallback_trash: str | None,
        time_filter: str | None,
        needle: str,
        max_results: int,
    ) -> tuple[list[SearchHit], bool]:
        try:
            return await self._scan(filter_str, needle, max_results, client_side_trash=None)
        except ToolFailure as failure:
            combined = bool(time_filter and filter_str != time_filter)
            filter_rejected = (
                combined
                and failure.info.code == "invalid_argument"
                and "filter" in failure.info.message.lower()
            )
            if not filter_rejected:
                raise
            # The live API accepted the combination when probed (2026-10-06),
            # but the probe in SPEC 1 could not confirm it in advance; keep the
            # recovery path so a rejection degrades instead of failing.
            logger.warning(
                "Keep rejected the combined filter %r; retrying with %r and filtering trash client-side",
                filter_str,
                time_filter,
            )
            return await self._scan(time_filter, needle, max_results, client_side_trash=fallback_trash)

    async def _scan(
        self,
        filter_str: str | None,
        needle: str,
        max_results: int,
        *,
        client_side_trash: str | None,
    ) -> tuple[list[SearchHit], bool]:
        hits: list[SearchHit] = []
        page_token: str | None = None
        while True:
            page = await self._api.list_notes(page_size=PAGE_SIZE, page_token=page_token, filter=filter_str)
            for note in page.get("notes") or []:
                if not isinstance(note, dict):
                    continue
                if client_side_trash == "trashed" and not _is_trashed(note):
                    continue
                if client_side_trash == "-trashed" and _is_trashed(note):
                    continue
                if not _matches(note, needle):
                    continue
                hits.append(_hit(note, needle))
                if len(hits) > max_results:
                    return hits[:max_results], True
            page_token = page.get("nextPageToken")
            if not page_token:
                break
        return hits, False

    async def _do_get(self, name: str) -> GetNoteResult:
        return GetNoteResult(ok=True, note=_detail(await self._api.get_note(name)))

    async def _do_create(self, title: str, content: TextBody | ChecklistBody) -> CreateNoteResult:
        note = await self._api.create_note({"title": title, "body": _body_wire(content)})
        name = note.get("name")
        if not isinstance(name, str) or not name:
            raise ToolFailure(internal_error("create_note (no name in the API response)"))
        self._registry.add(name, title)
        kind: NoteKind = "checklist" if isinstance(content, ChecklistBody) else "text"
        return CreateNoteResult(
            ok=True,
            name=name,
            title=title,
            kind=kind,
            created=note.get("createTime"),
            managed=True,
        )

    async def _do_delete(self, *, name: str, dry_run: bool, allow_foreign: bool) -> DeleteNoteResult:
        note = await self._api.get_note(name)
        managed = self._registry.contains(name)
        refusal = delete_policy(
            name=name, registry=self._registry, safe_mode=self._safe_mode, allow_foreign=allow_foreign
        )
        warnings = [f"{refusal.message} {refusal.override or ''}".strip()] if refusal else []
        if dry_run:
            return DeleteNoteResult(
                ok=True,
                name=name,
                dry_run=True,
                deleted=False,
                managed=managed,
                preview=_preview(note),
                warnings=warnings,
            )
        if refusal is not None:
            raise ToolFailure(refusal)
        await self._api.delete_note(name)
        self._registry.remove(name)
        return DeleteNoteResult(
            ok=True,
            name=name,
            dry_run=False,
            deleted=True,
            managed=managed,
            preview=_preview(note),
        )

    async def _do_share(self, name: str, emails: list[str]) -> ShareNoteResult:
        note = await self._api.get_note(name)
        existing = {person.email.lower() for person in _collaborators(note)}
        unique: list[str] = []
        seen: set[str] = set()
        for email in emails:
            address = str(email)
            if address.lower() in seen:
                continue
            seen.add(address.lower())
            unique.append(address)
        added = [address for address in unique if address.lower() not in existing]
        skipped = [address for address in unique if address.lower() in existing]
        shared_with = _collaborators(note)
        if added:
            try:
                await self._api.create_permissions(name, added)
            except ToolFailure as failure:
                if failure.info.code == "unknown_recipient":
                    raise ToolFailure(
                        unknown_recipient(_offending_recipient(failure.info.message, added))
                    ) from None
                raise
            shared_with = shared_with + [Collaborator(email=address, role="WRITER") for address in added]
        return ShareNoteResult(
            ok=True,
            name=name,
            added=added,
            skipped=skipped,
            shared_with=shared_with,
        )


__all__ = ["KeepTools"]
