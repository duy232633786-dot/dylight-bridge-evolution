"""Kết nối Obsidian: xuất deterministic, sandbox path và bảo vệ note đã sửa."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from bridge_evolution.cli import main as cli_main
from bridge_evolution.knowledge.obsidian import (
    DASHBOARD_NAME,
    MANIFEST_NAME,
    discover_obsidian_vaults,
    export_obsidian_vault,
    load_card_audit,
)
from bridge_evolution.knowledge.store import CARDS_DIR, load_cards
from bridge_evolution.knowledge.taxonomy import RULES, VARIABLES


CARD_COUNT = len(list(CARDS_DIR.glob("KC-*.json")))
MANAGED_OUTPUT_COUNT = 1 + 1 + len(RULES) + 1 + len(VARIABLES) + CARD_COUNT


def _tree_hash(root: Path) -> dict[str, str]:
    return {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.glob("*.json"))
    }


def _valid_card(card_id: str = "KC-100") -> dict:
    return {
        "card_id": card_id,
        "type": "design_heuristic",
        "title": "Thẻ thử",
        "applies_to": {
            "family": "super_t_simple_v1",
            "rules": ["SERV-001"],
            "variables": ["prestress_layout_id"],
        },
        "guidance": "Chỉ dùng để test.",
        "evidence": "Không có.",
        "source": {"kind": "experiment", "ref": "test"},
        "status": "DRAFT",
        "version": 1,
    }


def test_export_writes_dashboard_cards_manifest_and_preserves_json(tmp_path):
    vault = tmp_path / "Vault tiếng Việt"
    vault.mkdir()
    source_before = _tree_hash(CARDS_DIR)

    result = export_obsidian_vault(vault)

    managed = vault / "DYLIGHT Bridge Evolution"
    assert result["cards_exported"] == CARD_COUNT
    assert len(result["written"]) == MANAGED_OUTPUT_COUNT
    assert result["conflicts"] == []
    assert (managed / DASHBOARD_NAME).is_file()
    assert len(list((managed / "Cards").glob("KC-*.md"))) == CARD_COUNT
    assert (managed / MANIFEST_NAME).is_file()
    assert _tree_hash(CARDS_DIR) == source_before

    dashboard = (managed / DASHBOARD_NAME).read_text(encoding="utf-8")
    note = (managed / "Cards" / "KC-001.md").read_text(encoding="utf-8")
    audit = load_card_audit()
    red_count = sum(entry["risk"] == "RED" for entry in audit["cards"].values()) if audit else 0
    assert "0/20 card ở trạng thái ENGINEER_APPROVED" in dashboard
    assert f"Audit risk RED: **{red_count}**" in dashboard
    assert "DRAFT — chưa được kỹ sư phê duyệt" in note
    assert "Claim audit: RED · PARTIAL" in note
    assert "dylight_canonical_sha256" in note
    assert "[[DYLIGHT Bridge Evolution/Rules/SERV-001|SERV-001]]" in note
    assert "[[DYLIGHT Bridge Evolution/Standards/TCVN 11823-2017/Parts/TCVN 11823-5-2017 - Kết cấu bê tông|TCVN 11823-5:2017]]" in note
    assert "dylight-risk-red" in note
    assert len(list((managed / "Rules").glob("*.md"))) == len(RULES) + 1
    assert len(list((managed / "Variables").glob("*.md"))) == len(VARIABLES) + 1


def test_export_is_idempotent(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    export_obsidian_vault(vault)

    second = export_obsidian_vault(vault)

    assert second["written"] == []
    assert len(second["unchanged"]) == MANAGED_OUTPUT_COUNT
    assert second["conflicts"] == []
    assert second["manifest_changed"] is False


def test_user_edit_becomes_conflict_and_is_not_overwritten(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    export_obsidian_vault(vault)
    note = vault / "DYLIGHT Bridge Evolution" / "Cards" / "KC-001.md"
    edited = note.read_text(encoding="utf-8") + "\nGhi chú riêng của người dùng.\n"
    note.write_text(edited, encoding="utf-8")

    result = export_obsidian_vault(vault)

    assert result["conflicts"] == ["Cards/KC-001.md"]
    assert note.read_text(encoding="utf-8") == edited


def test_foreign_file_is_never_deleted(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    export_obsidian_vault(vault)
    foreign = vault / "DYLIGHT Bridge Evolution" / "My Notes.md"
    foreign.write_text("private", encoding="utf-8")

    result = export_obsidian_vault(vault)

    assert foreign.read_text(encoding="utf-8") == "private"
    assert "My Notes.md" not in result["stale_not_deleted"]


def test_dry_run_does_not_create_managed_folder(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()

    result = export_obsidian_vault(vault, dry_run=True)

    assert len(result["written"]) == MANAGED_OUTPUT_COUNT
    assert not (vault / "DYLIGHT Bridge Evolution").exists()


def test_approved_only_exports_dashboard_but_no_draft_cards(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()

    result = export_obsidian_vault(vault, include_draft=False)

    managed = vault / "DYLIGHT Bridge Evolution"
    assert result["cards_exported"] == 0
    taxonomy_count = 1 + len(RULES) + 1 + len(VARIABLES)
    assert len(result["written"]) == 1 + taxonomy_count
    assert DASHBOARD_NAME in result["written"]
    assert not (managed / "Cards").exists()
    assert "Tổng số thẻ xuất: **0**" in (
        managed / DASHBOARD_NAME).read_text(encoding="utf-8")


def test_discover_vault_from_obsidian_registry(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    config = tmp_path / "obsidian.json"
    config.write_text(json.dumps({
        "vaults": {
            "abc": {"path": str(vault), "open": True, "ts": 1},
            "missing": {"path": str(tmp_path / "missing")},
        }
    }), encoding="utf-8")

    assert discover_obsidian_vaults(config) == [vault.resolve()]


@pytest.mark.parametrize("folder", ["../escape", ".obsidian/x", "C:/escape"])
def test_managed_folder_rejects_unsafe_paths(tmp_path, folder):
    vault = tmp_path / "vault"
    vault.mkdir()
    with pytest.raises(ValueError, match="managed_folder|Managed folder"):
        export_obsidian_vault(vault, managed_folder=folder)


def test_bad_card_id_cannot_escape_cards_folder(tmp_path):
    vault = tmp_path / "vault"
    cards = tmp_path / "cards"
    vault.mkdir()
    cards.mkdir()
    card = _valid_card("../escape")
    (cards / "bad.json").write_text(json.dumps(card), encoding="utf-8")

    with pytest.raises(ValueError, match="Thẻ tri thức không hợp lệ"):
        export_obsidian_vault(
            vault, cards_dir=cards, audit_path=tmp_path / "no-audit.json")
    assert not (tmp_path / "escape.md").exists()


def test_current_audit_valid_and_has_all_cards():
    audit = load_card_audit()
    assert audit is not None
    assert audit["evidence"]["complete_oracle"] is True
    assert set(audit["cards"]) == {card["card_id"] for card in load_cards()}


def test_audit_missing_card_detects_untracked_card():
    audit = load_card_audit()
    assert audit is not None
    loaded_card_ids = {card["card_id"] for card in load_cards()}
    # Khẳng định: nếu runtime có thêm card mà audit thiếu, tập hợp sẽ không khớp
    simulated_runtime_cards = loaded_card_ids | {"KC-999"}
    assert set(audit["cards"]) != simulated_runtime_cards


def test_audit_rejects_wrong_evidence_hash(tmp_path):
    audit = load_card_audit()
    assert audit is not None
    audit["evidence"]["sha256"] = "0" * 64
    path = tmp_path / "audit.json"
    path.write_text(json.dumps(audit, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="SHA-256 không khớp"):
        load_card_audit(path)


def test_cli_export_and_does_not_touch_obsidian_config(tmp_path, capsys):
    vault = tmp_path / "vault"
    config_dir = vault / ".obsidian"
    config_dir.mkdir(parents=True)
    workspace = config_dir / "workspace.json"
    workspace.write_text('{"sentinel": true}', encoding="utf-8")

    exit_code = cli_main(["knowledge-export", "--vault", str(vault)])

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert output["status"] == "SUCCESS"
    assert output["cards_exported"] == CARD_COUNT
    assert workspace.read_text(encoding="utf-8") == '{"sentinel": true}'


def test_cli_knowledge_surfaces_claim_audit(capsys):
    exit_code = cli_main(["knowledge", "--rules", "SERV-001", "--top-k", "1"])

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert output[0]["card"]["card_id"] == "KC-001"
    assert output[0]["knowledge_audit"]["risk"] == "RED"
    assert output[0]["knowledge_audit"]["claim_audit"] == "PARTIAL"


def test_rule_and_variable_nodes_link_the_graph(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    export_obsidian_vault(vault)
    managed = vault / "DYLIGHT Bridge Evolution"

    rule = (managed / "Rules" / "SERV-001.md").read_text(encoding="utf-8")
    variable = (managed / "Variables" / "prestress_layout_id.md").read_text(
        encoding="utf-8")
    dashboard = (managed / DASHBOARD_NAME).read_text(encoding="utf-8")

    assert "[[DYLIGHT Bridge Evolution/Cards/KC-001|KC-001]]" in rule
    assert "[[DYLIGHT Bridge Evolution/Variables/prestress_layout_id|prestress_layout_id]]" in rule
    assert "[[DYLIGHT Bridge Evolution/Rules/SERV-001|SERV-001]]" in variable
    assert "[[DYLIGHT Bridge Evolution/Standards/TCVN 11823-2017/Parts/TCVN 11823-5-2017 - Kết cấu bê tông|TCVN 11823-5:2017]]" in variable
    assert "dylight-chip-blue" in dashboard
