import hashlib
import json
from pathlib import Path
import shutil

import pytest

from bridge_evolution import REPO_ROOT
from bridge_evolution.collaboration import (
    build_agent_brief,
    claim_task,
    lab_status,
    record_provenance_correction,
    review_handoff,
    review_provenance_correction,
    submit_handoff,
    validate_lab,
    export_research_to_obsidian,
)
from bridge_evolution.collaboration import lab as lab_module


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


def _minimal_correction_project(tmp_path: Path, monkeypatch) -> tuple[Path, Path]:
    project = tmp_path / "project"
    lab = project / "multiagent"
    for directory in (
        "tasks", "handoffs", "reviews", "incidents", "corrections",
        "correction_reviews", "snapshots/sha256", ".locks",
    ):
        (lab / directory).mkdir(parents=True, exist_ok=True)
    shutil.copy2(REPO_ROOT / "multiagent" / "lab.json", lab / "lab.json")
    task = {
        "schema_version": "1.0", "task_id": "BRD-999",
        "title": "Fixture provenance correction độc lập",
        "research_question": "Drift sau review có được sửa mà không viết lại lịch sử không?",
        "workstream": "integration", "priority": "P0", "status": "READY",
        "owner": None, "reviewer": None, "dependencies": [],
        "required_gates": ["G0"], "claim_ceiling": "IDEA",
        "write_scope": ["artifact.txt"],
        "acceptance_criteria": ["Snapshot và correction review khóa provenance"],
        "required_artifacts": ["artifact.txt"],
        "safety_notes": ["Không sửa handoff/review lịch sử"],
        "review_notes": [],
    }
    (lab / "tasks" / "BRD-999.json").write_text(
        json.dumps(task, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (project / "artifact.txt").write_bytes(b"recorded bytes\n")
    monkeypatch.setattr(lab_module, "REPO_ROOT", project)
    return project, lab


def test_drift_requires_exact_snapshot_incident_correction_and_independent_review(
    tmp_path, monkeypatch
):
    project, lab = _minimal_correction_project(tmp_path, monkeypatch)
    claim_task("BRD-999", "codex", lab)
    submit_handoff(
        "BRD-999", "codex", "orchestrator",
        "Ghi handoff ban đầu để kiểm tra provenance bất biến.",
        "IDEA", [], ["artifact.txt"], lab_dir=lab,
    )
    review_handoff(
        "BRD-999", "claude", "APPROVE",
        [{"gate": "G0", "status": "PASS", "evidence": "Kiểm tra fixture độc lập"}],
        "Chấp nhận fixture trước khi xuất hiện drift.", lab,
    )
    handoff_path = lab / "handoffs" / "BRD-999.codex.r001.json"
    review_path = lab / "reviews" / "BRD-999.claude.r001.json"
    immutable_handoff = handoff_path.read_bytes()
    immutable_review = review_path.read_bytes()
    snapshot_source = tmp_path / "recorded-artifact.bin"
    snapshot_source.write_bytes((project / "artifact.txt").read_bytes())
    first_corrected_bytes = b"post-handoff bugfix\n"
    (project / "artifact.txt").write_bytes(first_corrected_bytes)

    result = validate_lab(lab)
    assert result["valid"] is False
    assert any("chưa có snapshot/incident/correction review" in item for item in result["errors"])

    correction = record_provenance_correction(
        "BRD-999", "repair_bot",
        "multiagent/handoffs/BRD-999.codex.r001.json", "artifact.txt",
        snapshot_source, "Bugfix được áp dụng sau khi handoff r001 đã được duyệt.",
        "Giữ r001 và ghi nhận hash hiện tại bằng correction handoff bất biến.",
        [["python", "-m", "pytest", "tests/test_collaboration.py", "-q"]],
        lab_dir=lab,
    )
    assert correction["review_required"] is True
    assert validate_lab(lab)["valid"] is False
    with pytest.raises(ValueError, match="không được tự review"):
        review_provenance_correction(
            correction["correction"]["correction_id"], "repair_bot", "APPROVE",
            ["Snapshot và current hash khớp"], "Tự review bị cấm.", lab,
        )
    with pytest.raises(ValueError, match="Original handoff agent"):
        review_provenance_correction(
            correction["correction"]["correction_id"], "codex", "APPROVE",
            ["Snapshot và current hash khớp"], "Original owner review bị cấm.", lab,
        )

    review_provenance_correction(
        correction["correction"]["correction_id"], "opencode", "APPROVE",
        [
            "Snapshot bytes khớp recorded SHA-256",
            "Incident liên kết đúng handoff và artifact",
            "Current artifact hash khớp correction handoff",
        ],
        "Đã kiểm tra độc lập và chấp nhận provenance correction.", lab,
    )
    assert validate_lab(lab)["valid"] is True
    assert handoff_path.read_bytes() == immutable_handoff
    assert review_path.read_bytes() == immutable_review

    first_corrected_snapshot = tmp_path / "first-corrected-artifact.bin"
    first_corrected_snapshot.write_bytes(first_corrected_bytes)
    (project / "artifact.txt").write_bytes(b"second unreviewed drift\n")
    assert validate_lab(lab)["valid"] is False

    second = record_provenance_correction(
        "BRD-999", "repair_bot",
        "multiagent/handoffs/BRD-999.codex.r001.json", "artifact.txt",
        first_corrected_snapshot,
        "Artifact drift lần hai sau correction đầu tiên đã được duyệt.",
        "Nối correction thứ hai vào đúng current hash của correction thứ nhất.",
        [["python", "-m", "pytest", "tests/test_collaboration.py", "-q"]],
        lab_dir=lab,
    )
    assert (
        second["correction"]["supersedes_correction_sha256"]
        == correction["correction_sha256"]
    )
    assert (
        second["correction"]["corrected_artifact"]["previous_sha256"]
        == hashlib.sha256(first_corrected_bytes).hexdigest()
    )
    assert validate_lab(lab)["valid"] is False
    review_provenance_correction(
        second["correction"]["correction_id"], "claude", "APPROVE",
        [
            "Intermediate snapshot khớp current hash correction thứ nhất",
            "Supersedes linkage không đứt old/new hash",
            "Current artifact khớp correction thứ hai",
        ],
        "Đã kiểm tra độc lập correction chain hai bước.", lab,
    )
    assert validate_lab(lab)["valid"] is True
    intermediate = (
        lab / "snapshots" / "sha256"
        / f"{hashlib.sha256(first_corrected_bytes).hexdigest()}.blob"
    )
    intermediate.unlink()
    assert validate_lab(lab)["valid"] is False
    intermediate.write_bytes(first_corrected_bytes)
    assert validate_lab(lab)["valid"] is True


def test_wrong_snapshot_bytes_cannot_authorize_drift(tmp_path, monkeypatch):
    project, lab = _minimal_correction_project(tmp_path, monkeypatch)
    claim_task("BRD-999", "codex", lab)
    submit_handoff(
        "BRD-999", "codex", "orchestrator",
        "Ghi handoff fixture để từ chối snapshot không đúng bytes.",
        "IDEA", [], ["artifact.txt"], lab_dir=lab,
    )
    review_handoff(
        "BRD-999", "claude", "APPROVE",
        [{"gate": "G0", "status": "PASS", "evidence": "Fixture ban đầu hợp lệ"}],
        "Duyệt fixture ban đầu.", lab,
    )
    (project / "artifact.txt").write_bytes(b"post-review drift\n")
    wrong = tmp_path / "wrong.bin"
    wrong.write_bytes(b"not the recorded bytes\n")

    with pytest.raises(ValueError, match="snapshot bytes không khớp"):
        record_provenance_correction(
            "BRD-999", "repair_bot",
            "multiagent/handoffs/BRD-999.codex.r001.json", "artifact.txt", wrong,
            "Drift fixture cần bị từ chối nếu snapshot sai.",
            "Không được tạo correction từ snapshot không đúng recorded hash.",
            [["python", "-m", "pytest", "tests/test_collaboration.py", "-q"]],
            lab_dir=lab,
        )


def test_revise_snapshots_historical_bytes_but_latest_handoff_stays_strict(
    tmp_path, monkeypatch
):
    project, lab = _minimal_correction_project(tmp_path, monkeypatch)
    claim_task("BRD-999", "codex", lab)
    submit_handoff(
        "BRD-999", "codex", "orchestrator",
        "Revision r001 sẽ được snapshot trước khi trả về ACTIVE.",
        "IDEA", [], ["artifact.txt"], lab_dir=lab,
    )
    review_handoff(
        "BRD-999", "claude", "REVISE",
        [{"gate": "G0", "status": "FAIL", "evidence": "Cần sửa artifact"}],
        "REVISE để kiểm tra vòng lặp lịch sử bất biến.", lab,
    )
    recorded = b"recorded bytes\n"
    recorded_sha256 = hashlib.sha256(recorded).hexdigest()
    snapshot = lab / "snapshots" / "sha256" / f"{recorded_sha256}.blob"
    assert snapshot.read_bytes() == recorded

    revised = b"revision two bytes\n"
    (project / "artifact.txt").write_bytes(revised)
    assert validate_lab(lab)["valid"] is True

    submit_handoff(
        "BRD-999", "codex", "orchestrator",
        "Revision r002 phải tiếp tục khớp artifact live trong lúc REVIEW.",
        "IDEA", [], ["artifact.txt"], lab_dir=lab,
    )
    assert validate_lab(lab)["valid"] is True
    (project / "artifact.txt").write_bytes(b"unreviewed drift after r002\n")
    result = validate_lab(lab)
    assert result["valid"] is False
    assert any("BRD-999.codex.r002.json" in item for item in result["errors"])

    (project / "artifact.txt").write_bytes(revised)
    review_handoff(
        "BRD-999", "opencode", "APPROVE",
        [{"gate": "G0", "status": "PASS", "evidence": "r002 live hash khớp"}],
        "APPROVE revision hiện hành sau khi kiểm tra độc lập.", lab,
    )
    assert validate_lab(lab)["valid"] is True


def test_revise_snapshot_must_exist_and_match_exact_bytes(tmp_path, monkeypatch):
    project, lab = _minimal_correction_project(tmp_path, monkeypatch)
    claim_task("BRD-999", "codex", lab)
    submit_handoff(
        "BRD-999", "codex", "orchestrator",
        "Tạo r001 để kiểm tra snapshot missing và snapshot giả.",
        "IDEA", [], ["artifact.txt"], lab_dir=lab,
    )
    review_handoff(
        "BRD-999", "claude", "REVISE",
        [{"gate": "G0", "status": "FAIL", "evidence": "Cần revision"}],
        "Tạo historical revision có snapshot.", lab,
    )
    recorded = b"recorded bytes\n"
    recorded_sha256 = hashlib.sha256(recorded).hexdigest()
    snapshot = lab / "snapshots" / "sha256" / f"{recorded_sha256}.blob"
    (project / "artifact.txt").write_bytes(b"revised live bytes\n")
    assert validate_lab(lab)["valid"] is True

    snapshot.unlink()
    assert validate_lab(lab)["valid"] is False
    snapshot.write_bytes(b"fake historical bytes\n")
    assert validate_lab(lab)["valid"] is False
    snapshot.write_bytes(recorded)
    assert validate_lab(lab)["valid"] is True


def test_approved_handoff_cannot_use_bare_snapshot_to_hide_drift(tmp_path, monkeypatch):
    project, lab = _minimal_correction_project(tmp_path, monkeypatch)
    claim_task("BRD-999", "codex", lab)
    submit_handoff(
        "BRD-999", "codex", "orchestrator",
        "APPROVE hiện hành không được lách bằng bare snapshot.",
        "IDEA", [], ["artifact.txt"], lab_dir=lab,
    )
    original = (project / "artifact.txt").read_bytes()
    original_sha256 = hashlib.sha256(original).hexdigest()
    snapshot = lab / "snapshots" / "sha256" / f"{original_sha256}.blob"
    snapshot.write_bytes(original)
    (project / "artifact.txt").write_bytes(b"drift before approve\n")
    with pytest.raises(ValueError, match="handoff đã drift"):
        review_handoff(
            "BRD-999", "claude", "APPROVE",
            [{"gate": "G0", "status": "PASS", "evidence": "Không hợp lệ"}],
            "Không được duyệt artifact đã drift.", lab,
        )

    (project / "artifact.txt").write_bytes(original)
    review_handoff(
        "BRD-999", "claude", "APPROVE",
        [{"gate": "G0", "status": "PASS", "evidence": "Live hash khớp"}],
        "Duyệt artifact còn nguyên vẹn.", lab,
    )
    (project / "artifact.txt").write_bytes(b"drift after approve\n")
    assert validate_lab(lab)["valid"] is False


def test_submit_handoff_blocks_claim_exceeding_project_claim_ceiling(tmp_path):
    lab = _lab_copy(tmp_path)
    path = lab / "tasks" / "BRD-999.json"
    task = json.loads(path.read_text(encoding="utf-8"))
    task["claim_ceiling"] = "NUMERICALLY_VERIFIED"
    task["required_gates"] = ["G0", "G1", "G2", "G3", "G4"]
    path.write_text(json.dumps(task, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    claim_task("BRD-999", "codex", lab)
    with pytest.raises(ValueError, match="vượt trần cấp dự án"):
        submit_handoff(
            "BRD-999", "codex", "structural_analyst",
            "Tự nâng trần lên NUMERICALLY_VERIFIED khi dự án chỉ đạt SCREENED.",
            "NUMERICALLY_VERIFIED", ["G0", "G1", "G2", "G3", "G4"], ["README.md"],
            lab_dir=lab,
        )


def test_validate_lab_catches_handoff_exceeding_project_ceiling(tmp_path):
    lab = _lab_copy(tmp_path)
    handoff_path = lab / "handoffs" / "BRD-999.codex.r001.json"
    handoff = {
        "schema_version": "1.0",
        "task_id": "BRD-999",
        "agent_id": "codex",
        "role": "structural_analyst",
        "summary": "Handoff khai khống trần claim.",
        "claim_level": "NUMERICALLY_VERIFIED",
        "gates_completed": ["G0", "G1", "G2", "G3", "G4"],
        "artifacts": [{"path": "README.md", "sha256": hashlib.sha256((REPO_ROOT / "README.md").read_bytes()).hexdigest(), "kind": "report"}],
        "assumptions": [],
        "unresolved_risks": [],
        "next_action": "Independent review",
    }
    handoff_path.write_text(json.dumps(handoff, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    validation = validate_lab(lab)
    assert validation["valid"] is False
    assert any("vượt trần cấp dự án (SCREENED)" in err for err in validation["errors"])

