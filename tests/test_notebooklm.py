"""Snapshot NotebookLM: validate, render và conflict safety."""
from __future__ import annotations

import json

import pytest

from bridge_evolution.cli import main as cli_main
from bridge_evolution.knowledge.notebooklm import (
    import_notebooklm_snapshot,
    load_notebooklm_snapshot,
)


def _snapshot():
    notebook_id = "10048ac9-71c9-4dbf-b78e-e41c6e261652"
    return {
        "snapshot_schema_version": 1,
        "captured_date": "2026-08-20",
        "scope": "bridge",
        "selection_rule": "test",
        "provenance": "test",
        "notebooks": [{
            "notebook_id": notebook_id,
            "url": f"https://notebook.google.com/notebook/{notebook_id}",
            "title": "TCVN 11823-5 concrete bridge",
            "updated": "20 thg 8, 2026",
            "declared_source_count": 2,
            "observed_source_items": 1,
            "non_item_source_count": 1,
            "public": False,
            "source_inventory": [{"name": "part05.pdf", "count": 1}],
            "conversation_prompts": ["Kiểm tra gì?"],
            "summary": "Bản tóm tắt do NotebookLM tạo.",
        }],
    }


def _write_snapshot(tmp_path, data=None):
    path = tmp_path / "snapshot.json"
    path.write_text(json.dumps(data or _snapshot(), ensure_ascii=False),
                    encoding="utf-8")
    return path


def test_bundled_snapshot_is_complete():
    snapshot = load_notebooklm_snapshot()
    assert len(snapshot["notebooks"]) == 32
    assert sum(item["declared_source_count"]
               for item in snapshot["notebooks"]) == 218
    assert sum(item["observed_source_items"]
               for item in snapshot["notebooks"]) == 215


def test_import_renders_index_and_reference_note(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    snapshot_path = _write_snapshot(tmp_path)

    result = import_notebooklm_snapshot(vault, snapshot_path=snapshot_path)

    root = vault / "DYLIGHT Bridge Evolution" / "NotebookLM"
    note = (root / "10048ac9-71c9-4dbf-b78e-e41c6e261652.md").read_text(
        encoding="utf-8")
    index = (root / "00 - NotebookLM Bridge Library.md").read_text(
        encoding="utf-8")
    assert result["notebooks"] == 1
    assert result["declared_sources"] == 2
    assert len(result["written"]) == 2
    assert "AI-generated / UNVERIFIED" in note
    assert "[[DYLIGHT Bridge Evolution/Standards/TCVN 11823-2017/Parts/TCVN 11823-5-2017 - Kết cấu bê tông|TCVN 11823-5:2017]]" in note
    assert "part05.pdf" in note
    assert "Kiểm tra gì?" in note
    assert "Notebook: **1**" in index


def test_import_is_idempotent_and_detects_user_edit(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    snapshot_path = _write_snapshot(tmp_path)
    import_notebooklm_snapshot(vault, snapshot_path=snapshot_path)

    second = import_notebooklm_snapshot(vault, snapshot_path=snapshot_path)
    assert second["planned_writes"] == []
    assert len(second["unchanged"]) == 2
    assert second["manifest_changed"] is False

    note = (vault / "DYLIGHT Bridge Evolution" / "NotebookLM" /
            "10048ac9-71c9-4dbf-b78e-e41c6e261652.md")
    edited = note.read_text(encoding="utf-8") + "\nGhi chú riêng.\n"
    note.write_text(edited, encoding="utf-8")
    conflict = import_notebooklm_snapshot(vault, snapshot_path=snapshot_path)
    assert conflict["conflicts"] == [note.name]
    assert conflict["written"] == []
    assert note.read_text(encoding="utf-8") == edited


def test_invalid_source_count_is_rejected(tmp_path):
    data = _snapshot()
    data["notebooks"][0]["observed_source_items"] = 2
    path = _write_snapshot(tmp_path, data)
    with pytest.raises(ValueError, match="không cân bằng|không đủ"):
        load_notebooklm_snapshot(path)


def test_cli_import_notebooklm(tmp_path, capsys):
    vault = tmp_path / "vault"
    vault.mkdir()
    snapshot_path = _write_snapshot(tmp_path)

    exit_code = cli_main([
        "knowledge-import-notebooklm", "--vault", str(vault),
        "--snapshot", str(snapshot_path),
    ])

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert output["status"] == "SUCCESS"
    assert output["notebooks"] == 1
