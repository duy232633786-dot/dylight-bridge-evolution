import json
from pathlib import Path
import shutil

import pytest

from bridge_evolution import REPO_ROOT
from bridge_evolution.collaboration import (
    build_agent_brief,
    claim_task,
    lab_status,
    review_handoff,
    submit_handoff,
    validate_lab,
    export_research_to_obsidian,
)


def _lab_copy(tmp_path: Path) -> Path:
    target = tmp_path / "multiagent"
    shutil.copytree(REPO_ROOT / "multiagent", target)
    task = {
        "schema_version": "1.0", "task_id": "BRD-999",
        "title": "Fixture task độc lập cho coordination tests",
        "research_question": "Coordination transition có atomic và độc lập reviewer không?",
        "workstream": "integration", "priority": "P0", "status": "READY",
        "owner": None, "reviewer": None, "dependencies": [],
        "required_gates": ["G0"], "claim_ceiling": "IDEA",
        "write_scope": ["tests/"],
        "acceptance_criteria": ["Transition được kiểm thử trong bản sao tạm"],
        "required_artifacts": ["README.md"],
        "safety_notes": ["Không sửa task board canonical để chạy test"],
        "review_notes": [],
    }
    (target / "tasks" / "BRD-999.json").write_text(
        json.dumps(task, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target


def test_seed_lab_is_valid_and_reports_screening_ceiling():
    result = validate_lab()
    assert result["valid"] is True
    assert result["errors"] == []
    assert result["task_count"] >= 8
    status = lab_status()
    assert status["valid"] is True
    assert status["current_project_claim_ceiling"] == "SCREENED"
    assert sum(status["tasks"].values()) == result["task_count"]


def test_brief_lists_only_ready_unblocked_tasks(tmp_path):
    # The live board may legitimately have no READY task after prior agents finish.
    brief = build_agent_brief("codex", _lab_copy(tmp_path))
    assert "BRD-999" in brief
    assert "lab claim" in brief


def test_claim_is_exclusive_and_atomic(tmp_path):
    lab = _lab_copy(tmp_path)
    claimed = claim_task("BRD-999", "codex", lab)
    assert claimed["status"] == "ACTIVE"
    assert claimed["owner"] == "codex"
    with pytest.raises(ValueError, match="READY"):
        claim_task("BRD-999", "claude", lab)
    assert not list((lab / ".locks").glob("*.lock"))


def test_handoff_requires_independent_review_and_hashed_artifact(tmp_path):
    lab = _lab_copy(tmp_path)
    claim_task("BRD-999", "codex", lab)
    handoff = submit_handoff(
        "BRD-999", "codex", "orchestrator",
        "Đã đối chiếu contract và lập capability matrix có thể kiểm toán.",
        "IDEA", [], ["README.md"], lab_dir=lab,
    )
    assert len(handoff["artifacts"][0]["sha256"]) == 64
    assert json.loads((lab / "tasks" / "BRD-999.json").read_text(encoding="utf-8"))["status"] == "REVIEW"
    with pytest.raises(ValueError, match="không được tự review"):
        review_handoff(
            "BRD-999", "codex", "APPROVE",
            [{"gate": "G0", "status": "PASS", "evidence": "independent check"}],
            "Tự duyệt là không hợp lệ.", lab,
        )
    review = review_handoff(
        "BRD-999", "claude", "APPROVE",
        [{"gate": "G0", "status": "PASS", "evidence": "Recomputed capability matrix"}],
        "Đã kiểm tra độc lập và chấp nhận artifact.", lab,
    )
    assert review["decision"] == "APPROVE"
    assert validate_lab(lab)["valid"] is True


def test_claim_level_cannot_skip_physics_gates(tmp_path):
    lab = _lab_copy(tmp_path)
    path = lab / "tasks" / "BRD-999.json"
    task = json.loads(path.read_text(encoding="utf-8"))
    task["claim_ceiling"] = "SCREENED"
    path.write_text(json.dumps(task, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    claim_task("BRD-999", "codex", lab)
    with pytest.raises(ValueError, match="thiếu gate"):
        submit_handoff(
            "BRD-999", "codex", "structural_analyst",
            "Kết luận sàng lọc nhưng chưa hoàn tất chuỗi physics gates.",
            "SCREENED", ["G0"], ["README.md"], lab_dir=lab,
        )


def test_research_records_export_to_obsidian_and_are_idempotent(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()

    first = export_research_to_obsidian(vault)
    second = export_research_to_obsidian(vault)

    root = vault / "DYLIGHT Bridge Evolution" / "Research Lab"
    expected_tasks = validate_lab()["task_count"]
    assert first["tasks_exported"] == expected_tasks
    assert len(first["written"]) >= expected_tasks + 1
    assert second["written"] == []
    assert len(second["unchanged"]) == len(first["written"])
    assert (root / "00 - Research Lab Dashboard.md").is_file()
    task = (root / "Tasks" / "BRD-005.md").read_text(encoding="utf-8")
    assert "Evidence matrix" in task
    assert "dylight_canonical_sha256" in task
    assert "Runtime hiện tại chỉ đạt SCREENED" in task


def test_handoff_artifacts_are_mirrored_but_canonical_remains_source(tmp_path):
    lab = _lab_copy(tmp_path)
    vault = tmp_path / "vault"
    vault.mkdir()
    claim_task("BRD-999", "codex", lab)
    submit_handoff(
        "BRD-999", "codex", "orchestrator",
        "Đã lưu phát minh, phép tính và kết quả âm thành artifact có hash.",
        "IDEA", [], ["README.md"], lab_dir=lab,
    )

    result = export_research_to_obsidian(vault, lab_dir=lab)

    assert result["handoffs_exported"] >= 1
    notes = list((vault / "DYLIGHT Bridge Evolution" / "Research Lab" / "Handoffs").glob("BRD-999.*.md"))
    assert len(notes) == 1
    note = notes[0].read_text(encoding="utf-8")
    assert "README.md" in note
    assert "SHA-256" in note
    assert "Artifact/JSON trong project" not in note


def test_user_edited_research_note_becomes_conflict(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    export_research_to_obsidian(vault)
    note = vault / "DYLIGHT Bridge Evolution" / "Research Lab" / "Tasks" / "BRD-005.md"
    edited = note.read_text(encoding="utf-8") + "\nGhi chú riêng.\n"
    note.write_text(edited, encoding="utf-8")

    result = export_research_to_obsidian(vault)

    assert result["conflicts"] == ["Tasks/BRD-005.md"]
    assert note.read_text(encoding="utf-8") == edited
