"""Nhập PDF TCVN vào Obsidian: metadata từ bìa, hash và conflict safety."""
from __future__ import annotations

import hashlib
import json

import pytest

from bridge_evolution.knowledge import reference_docs


def _fake_inspector(path):
    part = int(path.stem.removeprefix("p"))
    raw = path.read_bytes()
    return {
        "part": part,
        "pages": part + 10,
        "source_filename": path.name,
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
        "text_layer": True,
        "raw": raw,
    }


def _source(tmp_path, parts=(1, 3)):
    source = tmp_path / "source"
    source.mkdir()
    for part in parts:
        (source / f"p{part}.pdf").write_bytes(f"pdf-{part}".encode())
    return source


def test_extract_part_uses_cover_number_not_filename():
    text = "TCVN 11823 - 10:2017\nPHẦN 10: NỀN MÓNG"
    assert reference_docs._extract_standard_part(text) == 10


def test_import_writes_original_pdfs_curated_notes_and_manifest(
        tmp_path, monkeypatch):
    source = _source(tmp_path)
    vault = tmp_path / "Vault tiếng Việt"
    vault.mkdir()
    monkeypatch.setattr(reference_docs, "_inspect_pdf", _fake_inspector)

    result = reference_docs.import_tcvn_collection(source, vault)

    root = vault / "DYLIGHT Bridge Evolution" / "Standards" / "TCVN 11823-2017"
    assert result["documents"] == 2
    assert result["parts"] == [1, 3]
    assert result["total_pages"] == 24
    assert len(result["written"]) == 5
    assert result["conflicts"] == []
    assert (root / "PDF" / "TCVN 11823-1-2017.pdf").read_bytes() == b"pdf-1"
    assert (root / "PDF" / "TCVN 11823-3-2017.pdf").read_bytes() == b"pdf-3"
    index = (root / "00 - TCVN 11823-2017.md").read_text(encoding="utf-8")
    note = (root / "Parts" / "TCVN 11823-3-2017 - Tải trọng và hệ số tải trọng.md").read_text(encoding="utf-8")
    assert "Các phần có trong thư mục nguồn: **1, 3**" in index
    assert "Không có tệp mang số phần" in index
    assert "Nguồn tham khảo, không phải rule thực thi" in note
    assert "Tĩnh tải DC, DW, EV" in note
    assert "## Liên kết Brain 2" in note
    assert "[[DYLIGHT Bridge Evolution/Rules/STR-001|STR-001]]" in note
    assert "[[DYLIGHT Bridge Evolution/Variables/prestress_layout_id|prestress_layout_id]]" in note
    assert "dylight-standard" in note
    assert "![[DYLIGHT Bridge Evolution/Standards/TCVN 11823-2017/PDF/TCVN 11823-3-2017.pdf]]" in note
    manifest = json.loads(
        (root / reference_docs.REFERENCE_MANIFEST).read_text(encoding="utf-8"))
    assert manifest["documents"]["3"]["source_sha256"] == hashlib.sha256(b"pdf-3").hexdigest()
    assert str(source.resolve()) not in json.dumps(manifest)


def test_import_is_idempotent(tmp_path, monkeypatch):
    source = _source(tmp_path)
    vault = tmp_path / "vault"
    vault.mkdir()
    monkeypatch.setattr(reference_docs, "_inspect_pdf", _fake_inspector)
    reference_docs.import_tcvn_collection(source, vault)

    second = reference_docs.import_tcvn_collection(source, vault)

    assert second["planned_writes"] == []
    assert second["written"] == []
    assert len(second["unchanged"]) == 5
    assert second["conflicts"] == []
    assert second["manifest_changed"] is False


def test_user_edited_note_blocks_entire_update(tmp_path, monkeypatch):
    source = _source(tmp_path)
    vault = tmp_path / "vault"
    vault.mkdir()
    monkeypatch.setattr(reference_docs, "_inspect_pdf", _fake_inspector)
    reference_docs.import_tcvn_collection(source, vault)
    note = (vault / "DYLIGHT Bridge Evolution" / "Standards" /
            "TCVN 11823-2017" / "Parts" /
            "TCVN 11823-1-2017 - Yêu cầu chung.md")
    edited = note.read_text(encoding="utf-8") + "\nGhi chú riêng.\n"
    note.write_text(edited, encoding="utf-8")

    result = reference_docs.import_tcvn_collection(source, vault)

    assert result["conflicts"] == ["Parts/TCVN 11823-1-2017 - Yêu cầu chung.md"]
    assert result["written"] == []
    assert note.read_text(encoding="utf-8") == edited


def test_source_change_updates_managed_files_when_no_user_edit(
        tmp_path, monkeypatch):
    source = _source(tmp_path)
    vault = tmp_path / "vault"
    vault.mkdir()
    monkeypatch.setattr(reference_docs, "_inspect_pdf", _fake_inspector)
    reference_docs.import_tcvn_collection(source, vault)
    (source / "p3.pdf").write_bytes(b"pdf-3-new")

    result = reference_docs.import_tcvn_collection(source, vault)

    assert result["conflicts"] == []
    assert set(result["written"]) == {
        "00 - TCVN 11823-2017.md",
        "PDF/TCVN 11823-3-2017.pdf",
        "Parts/TCVN 11823-3-2017 - Tải trọng và hệ số tải trọng.md",
    }


def test_dry_run_creates_nothing(tmp_path, monkeypatch):
    source = _source(tmp_path)
    vault = tmp_path / "vault"
    vault.mkdir()
    monkeypatch.setattr(reference_docs, "_inspect_pdf", _fake_inspector)

    result = reference_docs.import_tcvn_collection(source, vault, dry_run=True)

    assert len(result["planned_writes"]) == 5
    assert result["written"] == []
    assert not (vault / "DYLIGHT Bridge Evolution").exists()


def test_duplicate_standard_part_is_rejected(tmp_path, monkeypatch):
    source = _source(tmp_path, parts=(1, 2))
    vault = tmp_path / "vault"
    vault.mkdir()

    def duplicate(path):
        info = _fake_inspector(path)
        info["part"] = 1
        return info

    monkeypatch.setattr(reference_docs, "_inspect_pdf", duplicate)
    with pytest.raises(ValueError, match="Trùng số phần"):
        reference_docs.import_tcvn_collection(source, vault)


def test_collection_path_cannot_escape_vault(tmp_path, monkeypatch):
    source = _source(tmp_path)
    vault = tmp_path / "vault"
    vault.mkdir()
    monkeypatch.setattr(reference_docs, "_inspect_pdf", _fake_inspector)
    with pytest.raises(ValueError, match="không an toàn"):
        reference_docs.import_tcvn_collection(
            source, vault, collection_folder="../escape")
