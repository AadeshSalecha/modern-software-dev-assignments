"""L1 protocol layer: tool discovery, schema, docstrings, and the happy paths.

Every test drives the real FastMCP app through the in-memory MCP client, so the
assertions are about what an agent sees (tool list, schemas, structured content),
not about internal functions.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from fastmcp import Client

from helpers import call, error_of, fixture, make_config, make_server, note_names, raw, tools_by_name

CORE_TOOLS = {"search_notes", "get_note", "create_note", "delete_note", "share_note"}


# --------------------------------------------------------------------------- #
# D: discovery and schema (Part II)
# --------------------------------------------------------------------------- #
async def test_d1_exactly_the_core_tools_with_descriptions(client: Client) -> None:
    tools = await tools_by_name(client)
    assert set(tools) == CORE_TOOLS
    for name, tool in tools.items():
        assert tool.description, f"{name} has no description"
        assert len(tool.description.strip()) > 80, f"{name}'s description is too thin to guide an agent"


async def test_d2_annotations_tell_the_agent_what_is_safe(client: Client) -> None:
    tools = await tools_by_name(client)
    assert tools["search_notes"].annotations.read_only_hint is True
    assert tools["get_note"].annotations.read_only_hint is True
    assert tools["delete_note"].annotations.destructive_hint is True
    assert tools["share_note"].annotations.idempotent_hint is True
    assert tools["create_note"].annotations.read_only_hint is False


async def test_d3_get_note_name_is_constrained_to_keep_names(client: Client) -> None:
    schema = (await tools_by_name(client))["get_note"].input_schema
    name = schema["properties"]["name"]
    assert name["pattern"] == r"^notes/[A-Za-z0-9_-]+$"
    assert "search_notes" in name["description"]


async def test_d4_search_notes_schema_carries_state_enum_and_bounds(client: Client) -> None:
    schema = (await tools_by_name(client))["search_notes"].input_schema
    assert schema["properties"]["state"]["enum"] == ["active", "trashed", "any"]
    assert schema["properties"]["state"]["default"] == "active"
    max_results = schema["properties"]["max_results"]
    assert (max_results["minimum"], max_results["maximum"], max_results["default"]) == (1, 200, 50)


async def test_d5_create_note_content_is_a_required_discriminated_union(client: Client) -> None:
    schema = (await tools_by_name(client))["create_note"].input_schema
    assert "content" in schema["required"], "a note body must not be optional: Keep rejects empty notes"
    assert "title" in schema["required"]
    content = schema["properties"]["content"]
    branches = content["oneOf"]
    assert len(branches) == 2
    tags = {branch["properties"]["kind"]["const"] for branch in branches}
    assert tags == {"text", "checklist"}
    bodies = {tuple(branch["required"]) for branch in branches}
    assert ("kind", "text") in bodies and ("kind", "items") in bodies
    assert "null" not in json.dumps(content), "content must not be nullable"


async def test_d5b_share_note_emails_are_bounded_and_validated(client: Client) -> None:
    schema = (await tools_by_name(client))["share_note"].input_schema
    emails = schema["properties"]["emails"]
    assert (emails["minItems"], emails["maxItems"]) == (1, 10)
    assert emails["items"]["format"] == "email"
    assert "emails" in schema["required"]


async def test_d6_delete_note_dry_run_defaults_to_true(client: Client) -> None:
    schema = (await tools_by_name(client))["delete_note"].input_schema
    assert schema["properties"]["dry_run"]["default"] is True
    assert schema["properties"]["allow_foreign"]["default"] is False


async def test_d7_docstrings_agree_with_the_schemas(client: Client) -> None:
    """The lint that catches the classic rubric deduction: prose vs. schema drift."""
    for name, tool in (await tools_by_name(client)).items():
        description = tool.description or ""
        schema = tool.input_schema
        for parameter, spec in schema["properties"].items():
            assert parameter in description, f"{name}.{parameter} is not explained in the docstring"
            for value in spec.get("enum", []):
                assert str(value) in description, f"{name}.{parameter} enum value {value!r} is not named"
        if "name" in schema["properties"]:
            assert "search_notes" in description, f"{name} must say where `name` comes from"
    tools = await tools_by_name(client)
    create_doc = tools["create_note"].description or ""
    assert "text" in create_doc and "checklist" in create_doc
    get_doc = " ".join((tools["get_note"].description or "").split())
    assert "exact resource name supplied by the user" in get_doc
    assert "Pass it unchanged" in get_doc
    assert "Do not retry that same name" in get_doc
    search_doc = " ".join((tools["search_notes"].description or "").split())
    assert "not fuzzy or stemmed" in search_doc
    assert "try a likely spelling/plural variant" in search_doc
    delete_doc = " ".join((tools["delete_note"].description or "").split())
    assert "dry_run" in delete_doc and "allow_foreign" in delete_doc and "KEEP_SAFE_MODE" in delete_doc
    assert "permanent" in delete_doc.lower()
    assert "exactly as returned" in delete_doc
    assert "later user turn" in delete_doc
    assert "same assistant turn" in delete_doc


async def test_d8_instructions_describe_the_cross_tool_workflow(server) -> None:
    instructions = " ".join((server.instructions or "").split())
    assert "search_notes" in instructions
    assert "Use its returned `name`" in instructions
    assert "explicit `notes/...` resource name" in instructions
    assert "rather than searching for that ID as text" in instructions
    assert "do not retry the same name" in instructions
    assert "dry_run" in instructions or "preview" in instructions
    assert "later user" in instructions
    assert "same assistant turn" in instructions
    assert "category" in instructions and "retryable" in instructions
    for category in ("input", "not_found", "auth_setup", "rate_limited", "transient", "internal"):
        assert category in instructions


# --------------------------------------------------------------------------- #
# F: happy paths and composition (Part I)
# --------------------------------------------------------------------------- #
def seed_grocery_notes(api) -> None:
    api.seed_note(title="Groceries", items=[{"text": "Milk", "checked": True}, {"text": "Eggs"}])
    api.seed_note(title="Ideas", text="three things for the demo")
    api.seed_note(title="Meeting notes", text="standup at 9")


async def test_f1_search_matches_title_and_shapes_every_hit(client: Client, api) -> None:
    seed_grocery_notes(api)
    result = await call(client, "search_notes", {"query": "grocer"})
    assert result["ok"] is True
    assert note_names(result) and len(note_names(result)) == 1
    hit = result["notes"][0]
    assert hit["title"] == "Groceries"
    assert hit["kind"] == "checklist"
    assert hit["name"].startswith("notes/")
    assert hit["snippet"]
    assert hit["updated"] and hit["updated"].endswith("Z")
    assert hit["shared_with_count"] == 0


async def test_f1b_snippets_are_bounded_and_centred_on_the_match(client: Client, api) -> None:
    api.seed_note(title="Long note", text=("filler " * 60) + "needle in the middle " + ("tail " * 60))
    result = await call(client, "search_notes", {"query": "needle"})
    snippet = result["notes"][0]["snippet"]
    assert len(snippet) <= 160
    assert "needle" in snippet
    assert snippet.startswith("\u2026"), "a match deep in the body should show leading context"


async def test_f2_checklist_item_match_is_reported_with_that_item_as_snippet(client: Client, api) -> None:
    seed_grocery_notes(api)
    result = await call(client, "search_notes", {"query": "eggs"})
    assert len(result["notes"]) == 1
    hit = result["notes"][0]
    assert hit["title"] == "Groceries"
    assert "Eggs" in hit["snippet"]


async def test_f3_get_note_shape_does_not_leak_raw_google_keys(client: Client, api) -> None:
    seed_grocery_notes(api)
    name = note_names(await call(client, "search_notes", {"query": "grocer"}))[0]
    result = await call(client, "get_note", {"name": name})
    assert result["ok"] is True
    note = result["note"]
    assert note["title"] == "Groceries"
    assert note["kind"] == "checklist"
    assert [item["text"] for item in note["checklist"]] == ["Milk", "Eggs"]
    assert note["checklist"][0]["checked"] is True
    assert note["collaborators"][0]["role"] == "OWNER"
    assert note["created"] and note["updated"]
    blob = json.dumps(result)
    for raw_key in ("listItems", "textContent", "childListItems", "permissions", '"body"'):
        assert raw_key not in blob, f"raw Google key {raw_key} leaked into the tool result"


async def test_f4_create_text_note_is_searchable_and_registered(client: Client, api, registry) -> None:
    result = await call(
        client,
        "create_note",
        {"title": "[mcp-test] shopping", "content": {"kind": "text", "text": "buy oat milk"}},
    )
    assert result["ok"] is True
    assert result["name"].startswith("notes/")
    assert result["kind"] == "text"
    assert result["managed"] is True
    assert registry.contains(result["name"])

    found = await call(client, "search_notes", {"query": "oat milk"})
    assert note_names(found) == [result["name"]]


async def test_f5_checklist_round_trips_checked_state_and_one_level_of_children(client: Client) -> None:
    created = await call(
        client,
        "create_note",
        {
            "title": "[mcp-test] build plan",
            "content": {
                "kind": "checklist",
                "items": [
                    {
                        "text": "Build server",
                        "checked": False,
                        "children": [{"text": "Fake client", "checked": True}, {"text": "Protocol tests"}],
                    },
                    {"text": "Ship demo", "checked": True, "children": [{"text": "Record video", "checked": True}]},
                    {"text": "Writeup", "checked": False},
                ],
            },
        },
    )
    assert created["ok"] is True and created["kind"] == "checklist"
    note = (await call(client, "get_note", {"name": created["name"]}))["note"]
    assert [item["text"] for item in note["checklist"]] == ["Build server", "Ship demo", "Writeup"]
    assert [item["checked"] for item in note["checklist"]] == [False, True, False]
    assert note["checklist"][0]["children"][0] == {"text": "Fake client", "checked": True}
    assert note["checklist"][0]["children"][1]["checked"] is False
    # a checked parent must carry checked children, and both states round-trip
    assert note["checklist"][1]["checked"] is True
    assert note["checklist"][1]["children"] == [{"text": "Record video", "checked": True}]


async def test_f5b_a_checked_parent_with_an_unchecked_child_is_rejected_before_any_api_call(
    client: Client, api
) -> None:
    """Verified live 2026-10-06: notes.create answers 400 INVALID_ARGUMENT on
    note.body.list.list_items[N].child_list_items[M].checked when a checked item
    has an unchecked child. The server rejects it up front with a clear message."""
    result = await call(
        client,
        "create_note",
        {
            "title": "[mcp-test] bad combo",
            "content": {
                "kind": "checklist",
                "items": [
                    {"text": "prep the demo", "checked": True, "children": [{"text": "book room", "checked": False}]},
                ],
            },
        },
    )
    error = error_of(result)
    assert (error["category"], error["code"]) == ("input", "invalid_argument")
    assert error["retryable"] is False
    assert "prep the demo" in error["message"] and "book room" in error["message"]
    assert "checked" in error["message"], "the message must say what Keep rejects"
    assert api.calls_for("POST", "/notes") == [], "the rule fires before the API is called"


async def test_f6_share_then_get_lists_new_collaborators_as_writers(client: Client) -> None:
    created = await call(client, "create_note", {"title": "Shared", "content": {"kind": "text", "text": "hi"}})
    name = created["name"]
    shared = await call(client, "share_note", {"name": name, "emails": ["a@example.com", "b@example.com"]})
    assert shared["ok"] is True
    assert shared["added"] == ["a@example.com", "b@example.com"]
    assert shared["skipped"] == []
    note = (await call(client, "get_note", {"name": name}))["note"]
    roles = {person["email"]: person["role"] for person in note["collaborators"]}
    assert roles["a@example.com"] == "WRITER" and roles["b@example.com"] == "WRITER"


async def test_f7_resharing_skips_existing_people_and_calls_the_api_once(client: Client, api) -> None:
    created = await call(client, "create_note", {"title": "Shared", "content": {"kind": "text", "text": "hi"}})
    name = created["name"]
    await call(client, "share_note", {"name": name, "emails": ["a@example.com", "b@example.com"]})
    calls_before = len(api.calls_for("POST", "permissions:batchCreate"))

    again = await call(client, "share_note", {"name": name, "emails": ["a@example.com", "c@example.com"]})
    assert again["added"] == ["c@example.com"]
    assert again["skipped"] == ["a@example.com"]
    assert len(api.calls_for("POST", "permissions:batchCreate")) == calls_before + 1

    # and a third call with only known people makes no API call at all
    third = await call(client, "share_note", {"name": name, "emails": ["A@example.com"]})
    assert third["added"] == []
    assert third["skipped"] == ["A@example.com"]
    assert len(api.calls_for("POST", "permissions:batchCreate")) == calls_before + 1


async def test_f8_more_matches_than_max_results_sets_truncated(client: Client, api) -> None:
    for index in range(12):
        api.seed_note(title=f"Bulk {index}", text="bulk item for pagination")
    result = await call(client, "search_notes", {"query": "bulk", "max_results": 5})
    assert len(result["notes"]) == 5
    assert result["count"] == 5
    assert result["truncated"] is True


async def test_f9_state_maps_to_the_filter_the_api_accepts(client: Client, api) -> None:
    api.seed_note(title="Active", text="x")
    api.seed_note(title="Old", text="y", trashed=True)
    for state, expected in (("trashed", "trashed"), ("active", "-trashed")):
        await call(client, "search_notes", {"state": state})
        assert api.calls[-1].filter == expected, state

    # "any" really means both sides: the live API's default list view hides
    # trashed notes, so the server scans the default view and the trash and
    # merges them (verified live 2026-10-06).
    result = await call(client, "search_notes", {"state": "any"})
    emitted = [record.filter for record in api.calls_for("GET", "/notes")[-2:]]
    assert emitted == [None, "trashed"]
    assert note_names(result) and len(note_names(result)) == 2, "active and trashed must both appear"
    assert {hit["title"] for hit in result["notes"]} == {"Active", "Old"}


async def test_f9b_any_with_updated_after_is_one_time_only_scan(client: Client, api) -> None:
    """Verified live 2026-10-06: a time filter does not constrain trash state,
    so a single scan with the bare time filter already spans both trash sides."""
    api.seed_note(title="Recent active", text="x", updated=datetime(2026, 10, 6, tzinfo=timezone.utc))
    api.seed_note(
        title="Recent trashed", text="y", trashed=True, updated=datetime(2026, 10, 6, tzinfo=timezone.utc)
    )
    api.seed_note(title="Ancient", text="z", updated=datetime(2020, 1, 1, tzinfo=timezone.utc))

    result = await call(client, "search_notes", {"state": "any", "updated_after": "2026-01-01T00:00:00Z"})
    emitted = [record.filter for record in api.calls_for("GET", "/notes") if record.filter]
    assert emitted == ['update_time > "2026-01-01T00:00:00Z"'], "one scan, no trash term"
    assert {hit["title"] for hit in result["notes"]} == {"Recent active", "Recent trashed"}


async def test_f10_updated_after_emits_an_rfc3339_time_filter(client: Client, api) -> None:
    api.seed_note(title="Recent", text="x", updated=datetime(2026, 10, 6, tzinfo=timezone.utc))
    result = await call(
        client,
        "search_notes",
        {"updated_after": "2026-01-01T00:00:00Z", "state": "active"},
    )
    assert result["ok"] is True
    emitted = api.calls[-1].filter
    assert emitted == 'update_time > "2026-01-01T00:00:00Z" AND -trashed'
    assert "=" not in emitted.replace(">", ""), "booleans must never be compared with = (invalid filter)"


async def test_f10b_falls_back_to_a_time_only_filter_when_the_api_rejects_the_combination(
    tmp_path: Path,
) -> None:
    config = make_config(tmp_path)
    from keep_mcp.fake_client import FakeKeepClient

    api = FakeKeepClient(reject_combined_filter=True)
    api.seed_note(title="Active recent", text="keep me", updated=datetime(2026, 10, 6, tzinfo=timezone.utc))
    api.seed_note(
        title="Trashed recent", text="drop me", trashed=True, updated=datetime(2026, 10, 6, tzinfo=timezone.utc)
    )
    server = make_server(config, api=api)
    async with Client(server) as client:
        result = await call(client, "search_notes", {"updated_after": "2026-01-01T00:00:00Z"})
    assert result["ok"] is True
    titles = [hit["title"] for hit in result["notes"]]
    assert titles == ["Active recent"], "client-side trash filtering must drop the trashed note"
    emitted = [record.filter for record in api.calls if record.method == "GET"]
    assert emitted[0] == 'update_time > "2026-01-01T00:00:00Z" AND -trashed'
    assert emitted[-1] == 'update_time > "2026-01-01T00:00:00Z"'


async def test_f11_empty_account_returns_an_empty_list(client: Client, api) -> None:
    result = await call(client, "search_notes")
    assert result["ok"] is True
    assert result["notes"] == [] and result["count"] == 0 and result["truncated"] is False
    assert api.notes == {}


async def test_f12_pagination_walks_pages_within_the_page_size_limit(client: Client, api) -> None:
    for index in range(250):
        api.seed_note(title=f"Note {index}", text="paged content")
    result = await call(client, "search_notes", {"query": "paged", "max_results": 150})
    assert len(result["notes"]) == 150
    assert result["truncated"] is True
    page_sizes = [record.params["pageSize"] for record in api.calls_for("GET", "/notes")]
    assert page_sizes and max(page_sizes) <= 100
