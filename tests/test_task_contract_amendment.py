import hashlib
import json
from pathlib import Path
import shutil

import pytest

from bridge_evolution import REPO_ROOT
from bridge_evolution.cli import main as cli_main
from bridge_evolution.collaboration import (
    amend_task_contract,
    export_research_to_obsidian,
    validate_lab,
)
from bridge_evolution.collaboration.lab import _amendment_sha256


def _task(task_id: str = "BRD-999") -> dict:
    return {
        "schema_version": "1.0",
        "task_id": task_id,
        "title": "Sàng lọc kết cấu thử nghiệm",
        "research_question": "Mô hình hiện tại có đủ bằng chứng để claim SCREENED không?",
        "workstream": "structural_physics",
        "priority": "P0",
        "status": "READY",
        "owner": None,
        "reviewer": None,
        "dependencies": [],
        "required_gates": ["G0", "G1", "G2"],
        "claim_ceiling": "SCREENED",
        "write_scope": ["research/screen.md"],
        "acceptance_criteria": ["Hoàn tất physics screening theo G0 đến G2"],
        "required_artifacts": ["research/screen.md"],
        "safety_notes": ["Dừng nếu design basis hoặc solver evidence còn thiếu"],
        "review_notes": [],
        "human_gate": False,
    }


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _minimal_lab(tmp_path: Path, task_id: str = "BRD-999") -> Path:
    lab = tmp_path / "multiagent"
    for directory in (
        "tasks", "handoffs", "reviews", "amendments",
        "task_contract_snapshots/sha256", "incidents", "corrections",
        "correction_reviews", "snapshots/sha256", "runs", "intake", ".locks",
    ):
        (lab / directory).mkdir(parents=True, exist_ok=True)
    shutil.copy2(REPO_ROOT / "multiagent" / "lab.json", lab / "lab.json")
    _write_json(lab / "tasks" / f"{task_id}.json", _task(task_id))
    return lab


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_rescope_screened_g0_g2_to_idea_without_gates_has_hash_chain(tmp_path):
    lab = _minimal_lab(tmp_path)
    task_path = lab / "tasks" / "BRD-999.json"
    original_bytes = task_path.read_bytes()
    pre_hash = hashlib.sha256(original_bytes).hexdigest()
    changes = {
        "claim_ceiling": "IDEA",
        "required_gates": [],
        "title": "Ghi nhận giới hạn F0 và dừng physics screening",
        "research_question": (
            "Thiếu G0/L2 nào buộc task chỉ lập pre-registration F0 và dừng claim?"
        ),
        "acceptance_criteria": [
            "Nêu rõ G0 còn PENDING và không phát hành kết luận SCREENED",
            "Lưu tiêu chí bác bỏ cùng phép thử L2 cần thực hiện tiếp theo",
        ],
        "human_gate": True,
    }

    first = amend_task_contract(
        "BRD-999", changes,
        reason="Design basis G0 chưa khóa nên task phải fail-closed ở F0.",
        authorized_by="project_owner",
        expected_pre_task_sha256=pre_hash,
        lab_dir=lab,
    )

    record = first["amendment"]
    assert record["pre_task_sha256"] == pre_hash
    assert record["post_task_sha256"] == _sha(task_path)
    assert record["amendment_sha256"] == _amendment_sha256(record)
    assert record["previous_amendment_sha256"] is None
    assert {
        item["field"]: (item["before"], item["after"])
        for item in record["changes"]
    }["claim_ceiling"] == ("SCREENED", "IDEA")
    snapshot = lab / "task_contract_snapshots" / "sha256" / f"{pre_hash}.json"
    assert snapshot.read_bytes() == original_bytes

    second_pre = _sha(task_path)
    second = amend_task_contract(
        "BRD-999",
        {"safety_notes": ["Chỉ F0; mọi physics claim dừng tới khi có G0 và L2 độc lập"]},
        reason="Bổ sung STOP rule rõ ràng sau lần re-scope đầu tiên.",
        authorized_by="project_owner",
        expected_pre_task_sha256=second_pre,
        lab_dir=lab,
    )
    assert second["amendment"]["previous_amendment_sha256"] == record["amendment_sha256"]
    assert validate_lab(lab) == {"valid": True, "errors": [], "task_count": 1}


def test_amendment_rejects_stale_pre_hash_without_mutation(tmp_path):
    lab = _minimal_lab(tmp_path)
    task_path = lab / "tasks" / "BRD-999.json"
    stale_hash = _sha(task_path)
    task = json.loads(task_path.read_text(encoding="utf-8"))
    task["title"] = "Một caller khác đã thay bytes trước khi amendment"
    _write_json(task_path, task)
    bytes_before_call = task_path.read_bytes()

    with pytest.raises(ValueError, match="Stale pre-task hash"):
        amend_task_contract(
            "BRD-999", {"claim_ceiling": "IDEA"},
            reason="Caller này đang dùng task hash đã cũ.",
            authorized_by="project_owner",
            expected_pre_task_sha256=stale_hash,
            lab_dir=lab,
        )

    assert task_path.read_bytes() == bytes_before_call
    assert list((lab / "amendments").glob("*.json")) == []
    assert list((lab / "task_contract_snapshots").rglob("*.json")) == []


def test_amendment_rejects_active_task_even_with_current_hash(tmp_path):
    lab = _minimal_lab(tmp_path)
    task_path = lab / "tasks" / "BRD-999.json"
    task = json.loads(task_path.read_text(encoding="utf-8"))
    task["status"] = "ACTIVE"
    task["owner"] = "codex"
    _write_json(task_path, task)
    bytes_before_call = task_path.read_bytes()

    with pytest.raises(ValueError, match="Không được amendment task ACTIVE"):
        amend_task_contract(
            "BRD-999", {"claim_ceiling": "IDEA"},
            reason="Không được rewrite contract khi worker đang chạy.",
            authorized_by="project_owner",
            expected_pre_task_sha256=_sha(task_path),
            lab_dir=lab,
        )

    assert task_path.read_bytes() == bytes_before_call
    assert list((lab / "amendments").glob("*.json")) == []


def test_run_task_requires_brief_requester_and_logs_amendment_event(tmp_path):
    task_id = "RND-cafebabe-01"
    lab = _minimal_lab(tmp_path, task_id)
    brief_id = "RND-20260821-cafebabe"
    run_id = "RUN-20260821-cafebabe"
    for number in range(2, 5):
        sibling_id = f"RND-cafebabe-{number:02d}"
        sibling = _task(sibling_id)
        sibling["claim_ceiling"] = "IDEA"
        sibling["required_gates"] = []
        sibling["source_brief_id"] = brief_id
        _write_json(lab / "tasks" / f"{sibling_id}.json", sibling)
    primary_path = lab / "tasks" / f"{task_id}.json"
    primary = json.loads(primary_path.read_text(encoding="utf-8"))
    primary["source_brief_id"] = brief_id
    _write_json(primary_path, primary)
    brief = {
        "schema_version": "1.0", "brief_id": brief_id,
        "created_at": "2026-08-21T00:00:00Z",
        "topic": "Kiểm thử amendment task contract trong orchestration run",
        "objectives": ["Giữ audit trail bất biến cho mọi lần re-scope"],
        "constraints": ["Không sửa task đang active"],
        "requested_by": "project_owner", "autonomy_mode": "DIGITAL_AUTO",
        "claim_ceiling": "SCREENED",
        "budget": {
            "max_tasks": 4, "max_parallel": 1, "max_retries": 1,
            "task_timeout_seconds": 600, "wall_time_seconds": 3600,
        },
        "human_gates": ["TECHNICAL_RELEASE"],
        "knowledge_sink": "OBSIDIAN_AND_CANONICAL_JSON",
    }
    _write_json(lab / "intake" / f"{brief_id}.json", brief)
    run = {
        "schema_version": "1.0", "run_id": run_id, "brief_id": brief_id,
        "created_at": "2026-08-21T00:00:00Z",
        "updated_at": "2026-08-21T00:00:00Z", "status": "PLANNED",
        "planner": "test/1.0",
        "task_ids": [f"RND-cafebabe-{number:02d}" for number in range(1, 5)],
        "provider_policy": "STRICT_MULTI_VENDOR",
        "attempts": {f"RND-cafebabe-{number:02d}": 0 for number in range(1, 5)},
        "recovery_grants": {f"RND-cafebabe-{number:02d}": 0 for number in range(1, 5)},
        "events": [{
            "at": "2026-08-21T00:00:00Z", "kind": "PLAN_CREATED",
            "message": "Fixture plan created",
        }],
        "human_gate": None, "knowledge_sync": "SYNCED",
    }
    run_path = lab / "runs" / run_id / "run.json"
    _write_json(run_path, run)

    with pytest.raises(PermissionError, match="brief requester"):
        amend_task_contract(
            task_id, {"claim_ceiling": "IDEA", "required_gates": []},
            reason="Unauthorized actor phải bị chặn trước mọi mutation.",
            authorized_by="codex",
            expected_pre_task_sha256=_sha(primary_path), lab_dir=lab,
        )
    result = amend_task_contract(
        task_id, {"claim_ceiling": "IDEA", "required_gates": []},
        reason="G0 chưa khóa nên hạ task về F0 an toàn.",
        authorized_by="project_owner",
        expected_pre_task_sha256=_sha(primary_path), lab_dir=lab,
    )

    saved_run = json.loads(run_path.read_text(encoding="utf-8"))
    event = saved_run["events"][-1]
    assert saved_run["knowledge_sync"] == "PENDING"
    assert event["kind"] == "TASK_CONTRACT_AMENDED"
    assert result["amendment"]["amendment_id"] in event["message"]
    assert result["amendment_sha256"] in event["message"]
    assert validate_lab(lab)["valid"] is True
    vault = tmp_path / "run-vault"
    vault.mkdir()
    export_research_to_obsidian(vault, lab_dir=lab)
    run_note = (
        vault / "DYLIGHT Bridge Evolution" / "Research Lab" / "Runs"
        / f"{run_id}.md"
    ).read_text(encoding="utf-8")
    assert "Research Lab/Amendments/RND-cafebabe-01.amendment.r001" in run_note


def test_amend_task_cli_accepts_json_change_map(tmp_path, monkeypatch, capsys):
    lab = _minimal_lab(tmp_path)
    task_path = lab / "tasks" / "BRD-999.json"
    changes_path = tmp_path / "changes.json"
    _write_json(changes_path, {"claim_ceiling": "IDEA", "required_gates": []})
    monkeypatch.setenv("DYLIGHT_MULTIAGENT_DIR", str(lab))

    exit_code = cli_main([
        "lab", "amend-task", "BRD-999",
        "--changes", str(changes_path),
        "--reason", "CLI re-scope phải tạo cùng canonical audit record.",
        "--authorized-by", "project_owner",
        "--pre-task-sha256", _sha(task_path),
    ])

    assert exit_code == 0
    output = json.loads(capsys.readouterr().out)
    assert output["amendment"]["task_id"] == "BRD-999"
    assert validate_lab(lab)["valid"] is True


def test_obsidian_mirrors_amendment_with_links_manifest_and_conflict_safety(tmp_path):
    lab = _minimal_lab(tmp_path)
    task_path = lab / "tasks" / "BRD-999.json"
    result = amend_task_contract(
        "BRD-999", {"claim_ceiling": "IDEA", "required_gates": []},
        reason="G0 chưa khóa nên mirror phải giữ re-scope F0 lâu dài.",
        authorized_by="project_owner",
        expected_pre_task_sha256=_sha(task_path), lab_dir=lab,
    )
    vault = tmp_path / "vault"
    vault.mkdir()
    unrelated = vault / "Ghi chú của người dùng.md"
    unrelated.write_text("Không được chạm vào.\n", encoding="utf-8")

    first = export_research_to_obsidian(vault, lab_dir=lab)
    relative = "Amendments/BRD-999.amendment.r001.md"
    research = vault / "DYLIGHT Bridge Evolution" / "Research Lab"
    note_path = research / relative
    note = note_path.read_text(encoding="utf-8")
    assert first["amendments_exported"] == 1
    assert relative in first["written"]
    assert result["amendment"]["pre_task_sha256"] in note
    assert result["amendment"]["post_task_sha256"] in note
    assert result["amendment_sha256"] in note
    assert result["amendment"]["snapshot"]["path"] in note
    assert result["amendment"]["reason"] in note
    assert result["amendment"]["authorized_by"] in note
    assert result["amendment"]["created_at"] in note
    assert '"field": "claim_ceiling"' in note
    task_note = (research / "Tasks" / "BRD-999.md").read_text(encoding="utf-8")
    dashboard = (research / "00 - Research Lab Dashboard.md").read_text(encoding="utf-8")
    assert "Research Lab/Amendments/BRD-999.amendment.r001" in task_note
    assert "Research Lab/Amendments|task contract amendments" in dashboard
    assert "Research Lab/Amendments/BRD-999.amendment.r001" in dashboard
    assert unrelated.read_text(encoding="utf-8") == "Không được chạm vào.\n"
    assert not (research / "task_contract_snapshots").exists()
    manifest = json.loads(
        (research / ".dylight-research-manifest.json").read_text(encoding="utf-8")
    )
    assert relative in manifest["files"]

    second = export_research_to_obsidian(vault, lab_dir=lab)
    assert second["written"] == []
    assert relative in second["unchanged"]
    assert second["manifest_changed"] is False

    edited = note + "\nGhi chú thủ công phải được giữ lại.\n"
    note_path.write_text(edited, encoding="utf-8")
    conflict = export_research_to_obsidian(vault, lab_dir=lab)
    assert conflict["conflicts"] == [relative]
    assert note_path.read_text(encoding="utf-8") == edited
