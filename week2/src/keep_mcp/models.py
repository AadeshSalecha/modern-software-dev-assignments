"""Input and output models.

Two rules from the assignment drive this file:

* Constraints live in the schema, not in prose. ``content`` is a discriminated
  union, so "no body" and "two bodies" are unrepresentable, and a note name can
  only be the ``notes/<id>`` shape the Keep API accepts.
* Outputs are shaped. Keep's raw ``Note`` JSON (``body``, ``listItems``,
  ``textContent``, ``permissions``, ...) never reaches the agent; each tool
  returns a small model with an ``error`` slot.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from .errors import ErrorInfo

NoteKind = Literal["text", "checklist"]
NoteState = Literal["active", "trashed", "any"]

_MAX_NOTE_NAME = 250

NoteName = Annotated[
    str,
    Field(
        pattern=r"^notes/[A-Za-z0-9_-]+$",
        min_length=len("notes/") + 1,
        max_length=_MAX_NOTE_NAME,
        description=(
            "Keep resource name exactly as returned by search_notes or create_note, "
            "for example 'notes/1uFilIj6vTG4f...'. Not a URL and not a bare id."
        ),
    ),
]


# --------------------------------------------------------------------------- #
# create_note input: a discriminated union, so a note always has a body
# --------------------------------------------------------------------------- #
class TextBody(BaseModel):
    """A plain-text note body."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["text"] = Field(description='Set to "text" for a plain-text note.')
    text: str = Field(
        min_length=1,
        max_length=20_000,
        description="The note text; newlines are preserved. Keep rejects a note with an empty body.",
    )


class ChecklistChild(BaseModel):
    """A sub-item of a checklist item (Keep supports exactly one level of nesting)."""

    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=1_000, description="Sub-item text.")
    checked: bool = Field(
        default=False,
        description="Whether the sub-item is ticked. A checked parent requires checked sub-items.",
    )


class ChecklistItem(ChecklistChild):
    """One checklist entry, optionally with indented sub-items."""

    children: list[ChecklistChild] = Field(
        default_factory=list,
        max_length=50,
        description=(
            "Optional indented sub-items; Keep supports one level of nesting. "
            "When this item is checked, every sub-item must be checked too."
        ),
    )


class ChecklistBody(BaseModel):
    """A checklist note body."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["checklist"] = Field(description='Set to "checklist" for an item list.')
    items: list[ChecklistItem] = Field(
        min_length=1,
        max_length=200,
        description="Checklist items in display order. At least one is required: Keep rejects an empty body.",
    )


NoteContent = Annotated[
    TextBody | ChecklistBody,
    Field(discriminator="kind", description='Note body; pick "text" or "checklist" with the kind field.'),
]


# --------------------------------------------------------------------------- #
# shaped output
# --------------------------------------------------------------------------- #
class SearchHit(BaseModel):
    """One search result."""

    name: str = Field(description="Pass this to get_note, share_note, or delete_note.")
    title: str = Field(default="", description="Note title (may be empty).")
    snippet: str = Field(
        default="",
        description=(
            "Up to 160 characters of context around the match: the matching checklist item "
            "when the hit was in one, otherwise the start of the text body."
        ),
    )
    kind: NoteKind = Field(description='Body shape: "text" or "checklist".')
    updated: str | None = Field(default=None, description="RFC3339 last-modified time reported by Keep.")
    shared_with_count: int = Field(
        default=0,
        description="How many people besides the owner can access the note.",
    )


class SearchNotesResult(BaseModel):
    """Result of ``search_notes``."""

    ok: bool
    query: str = Field(default="", description="The query that was searched for (echoed back).")
    state: NoteState = Field(default="active", description="Which slice of notes was searched.")
    count: int = Field(default=0, description="Number of notes returned in this page of results.")
    notes: list[SearchHit] = Field(default_factory=list, description="Matching notes, newest first.")
    truncated: bool = Field(
        default=False,
        description="True when more notes matched than max_results: narrow the query or raise max_results.",
    )
    error: ErrorInfo | None = None


class ChecklistItemView(BaseModel):
    """A checklist entry as stored in Keep."""

    text: str
    checked: bool = False
    children: list[ChecklistChild] = Field(default_factory=list)


class Collaborator(BaseModel):
    """One entry from the note's permission list."""

    email: str = Field(description="Google account with access to the note.")
    role: str = Field(description='Keep role, e.g. "OWNER", "WRITER", "READER".')


class NoteDetail(BaseModel):
    """The shaped note returned by ``get_note``."""

    name: str
    title: str = ""
    kind: NoteKind
    text: str | None = Field(default=None, description="Body text, when the note is a text note.")
    checklist: list[ChecklistItemView] | None = Field(
        default=None, description="Checklist entries with checked state, when the note is a checklist."
    )
    collaborators: list[Collaborator] = Field(default_factory=list)
    attachment_count: int = Field(default=0, description="Number of Keep attachments (not fetched by this server).")
    created: str | None = Field(default=None, description="RFC3339 create time.")
    updated: str | None = Field(default=None, description="RFC3339 update time.")


class GetNoteResult(BaseModel):
    """Result of ``get_note``."""

    ok: bool
    note: NoteDetail | None = None
    error: ErrorInfo | None = None


class CreateNoteResult(BaseModel):
    """Result of ``create_note``."""

    ok: bool
    name: str | None = Field(default=None, description="Name of the new note; feed it to the other tools.")
    title: str | None = None
    kind: NoteKind | None = None
    created: str | None = Field(default=None, description="RFC3339 create time.")
    managed: bool = Field(
        default=False,
        description="True once keep-mcp recorded the note in its managed-notes registry (needed for delete_note).",
    )
    error: ErrorInfo | None = None


class DeletePreview(BaseModel):
    """What a delete would remove, returned by a dry run."""

    name: str
    title: str = ""
    kind: NoteKind
    updated: str | None = None
    collaborators: list[Collaborator] = Field(default_factory=list)
    attachment_count: int = 0


class DeleteNoteResult(BaseModel):
    """Result of ``delete_note``."""

    ok: bool
    name: str | None = None
    dry_run: bool = Field(default=True, description="True when nothing was deleted (the default).")
    deleted: bool = Field(default=False, description="True only after a committed delete.")
    managed: bool = Field(default=False, description="Whether keep-mcp created this note.")
    preview: DeletePreview | None = Field(default=None, description="What would be (or was) deleted.")
    warnings: list[str] = Field(
        default_factory=list,
        description="Reasons a committed delete would be refused; shown on dry runs.",
    )
    error: ErrorInfo | None = None


class ShareNoteResult(BaseModel):
    """Result of ``share_note``."""

    ok: bool
    name: str | None = None
    added: list[str] = Field(default_factory=list, description="Addresses granted WRITER on this call.")
    skipped: list[str] = Field(
        default_factory=list, description="Addresses that already had access and were left untouched."
    )
    shared_with: list[Collaborator] = Field(
        default_factory=list, description="The full collaborator list after this call."
    )
    error: ErrorInfo | None = None
