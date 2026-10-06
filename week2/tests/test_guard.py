"""L1 write brake and safe mode (Part II): the irreversible tool has a brake."""

from __future__ import annotations

from pathlib import Path

from fastmcp import Client

from helpers import call, error_of, make_config, make_server

TEXT_CONTENT = {"kind": "text", "text": "remember the milk"}


async def create_managed_note(client: Client, api, title: str = "[mcp-test] managed") -> str:
    created = await call(client, "create_note", {"title": title, "content": TEXT_CONTENT})
    assert created["ok"] is True
    return created["name"]


async def test_b1_default_delete_is_a_dry_run_and_changes_nothing(client: Client, api) -> None:
    name = await create_managed_note(client, api)
    result = await call(client, "delete_note", {"name": name})
    assert result["ok"] is True
    assert result["dry_run"] is True and result["deleted"] is False
    preview = result["preview"]
    assert preview["name"] == name and preview["title"] == "[mcp-test] managed"
    assert preview["updated"] and preview["collaborators"]
    assert result["warnings"] == []
    assert name in api.notes, "a dry run must not delete anything"
    assert (await call(client, "get_note", {"name": name}))["ok"] is True


async def test_b2_committing_deletes_the_note_permanently(client: Client, api, registry) -> None:
    name = await create_managed_note(client, api)
    assert registry.contains(name)
    result = await call(client, "delete_note", {"name": name, "dry_run": False})
    assert result["ok"] is True and result["deleted"] is True and result["dry_run"] is False
    assert name not in api.notes
    assert not registry.contains(name)
    gone = error_of(await call(client, "get_note", {"name": name}))
    assert gone["code"] == "note_not_accessible"


async def test_b3_foreign_note_is_refused_by_safe_mode(client: Client, api) -> None:
    name = api.seed_note(title="A real note I made in Keep", text="do not touch")
    result = await call(client, "delete_note", {"name": name, "dry_run": False})
    error = error_of(result)
    assert (error["category"], error["code"]) == ("policy", "managed_notes_only")
    assert error["retryable"] is False
    assert "intentional" in error["message"].lower()
    assert "allow_foreign" in error["override"] and "KEEP_SAFE_MODE" in error["override"]
    assert name in api.notes, "the refusal must not delete anything"


async def test_b4_allow_foreign_overrides_the_guard_for_one_note(client: Client, api) -> None:
    name = api.seed_note(title="Foreign but confirmed", text="ok to delete")
    result = await call(client, "delete_note", {"name": name, "dry_run": False, "allow_foreign": True})
    assert result["ok"] is True and result["deleted"] is True
    assert name not in api.notes


async def test_b5_safe_mode_off_removes_the_guard(tmp_path: Path) -> None:
    config = make_config(tmp_path, safe_mode=False)
    from keep_mcp.fake_client import FakeKeepClient

    api = FakeKeepClient()
    name = api.seed_note(title="Foreign", text="deletable when the guard is off")
    server = make_server(config, api=api)
    async with Client(server) as client:
        result = await call(client, "delete_note", {"name": name, "dry_run": False})
    assert result["ok"] is True and result["deleted"] is True
    assert name not in api.notes


async def test_b6_dry_run_on_a_foreign_note_previews_but_warns(client: Client, api) -> None:
    name = api.seed_note(title="Foreign", text="preview me")
    result = await call(client, "delete_note", {"name": name})
    assert result["ok"] is True
    assert result["deleted"] is False and result["managed"] is False
    assert result["preview"]["title"] == "Foreign"
    assert len(result["warnings"]) == 1
    warning = result["warnings"][0]
    assert "allow_foreign" in warning and "KEEP_SAFE_MODE" in warning
    assert name in api.notes
