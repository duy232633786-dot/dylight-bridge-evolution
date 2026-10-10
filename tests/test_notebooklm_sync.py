"""Contract đồng bộ hai chiều NotebookLM: queue, dedupe, state và Obsidian."""
from __future__ import annotations

import json

import pytest

from bridge_evolution.knowledge.notebooklm_sync import (
    enqueue_codex_message, export_sync_dashboard, ingest_notebooklm_capture,
    load_messages, sync_status, update_message_status,
)

NOTEBOOK_ID = "1d26b485-1eb2-4698-9a6c-6b5c5b6c3e79"


def test_outbox_roundtrip_and_state_machine(tmp_path):
    result = enqueue_codex_message(
        NOTEBOOK_ID, "Kiểm tra sơ đồ nhịp 45+75+45 m.", store_dir=tmp_path)
    assert result["status"] == "PENDING"
    assert len(load_messages(tmp_path)) == 1

    delivered = update_message_status(
        result["message_id"], "DELIVERED",
        remote_ref="notebooklm://conversation/abc", store_dir=tmp_path)
    assert delivered["status"] == "DELIVERED"
    with pytest.raises(ValueError, match="chuyển trạng thái"):
        update_message_status(result["message_id"], "PENDING", store_dir=tmp_path)


def test_inbound_capture_is_deduplicated(tmp_path):
    capture = tmp_path / "capture.json"
    capture.write_text(json.dumps({
        "notebook_id": NOTEBOOK_ID,
        "project": "do-an-cau-vuot-song",
        "content": "Câu trả lời NotebookLM có dẫn nguồn.",
        "remote_ref": "notebooklm://conversation/answer-1",
        "source_refs": ["TCVN 11823-5:2017"],
    }, ensure_ascii=False), encoding="utf-8")

    first = ingest_notebooklm_capture(capture, store_dir=tmp_path)
    second = ingest_notebooklm_capture(capture, store_dir=tmp_path)
    assert first["duplicate"] is False
    assert second["duplicate"] is True
    assert len(load_messages(tmp_path, direction="notebooklm_to_codex")) == 1


def test_tampered_message_is_rejected(tmp_path):
    result = enqueue_codex_message(NOTEBOOK_ID, "Nội dung gốc", store_dir=tmp_path)
    path = tmp_path / "outbox" / f"{result['message_id']}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["content"] = "Nội dung đã sửa không cập nhật hash"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="content_sha256"):
        load_messages(tmp_path)


def test_status_and_obsidian_dashboard(tmp_path):
    store = tmp_path / "store"
    vault = tmp_path / "vault"
    vault.mkdir()
    enqueue_codex_message(NOTEBOOK_ID, "Câu hỏi thiết kế", store_dir=store)
    status = sync_status(store)
    assert status["counts"]["PENDING"] == 1
    assert status["transport_status"] == "NOT_CONFIGURED"

    result = export_sync_dashboard(vault, store_dir=store)
    note = (vault / "DYLIGHT Bridge Evolution" / "Projects" /
            "Do an cau vuot song" / "02 - NotebookLM Two-Way Sync.md")
    assert result["changed"] is True
    assert "Câu hỏi thiết kế" in note.read_text(encoding="utf-8")
