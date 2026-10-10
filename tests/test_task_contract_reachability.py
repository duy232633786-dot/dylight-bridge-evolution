import json
from pathlib import Path

from jsonschema import Draft202012Validator
import pytest

from bridge_evolution import CONTRACTS_DIR
from bridge_evolution.collaboration import lab as lab_module
from bridge_evolution.collaboration.lab import claim_task, review_handoff, submit_handoff


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _task(*, runtime_scope: dict | None, task_id: str = "BRD-999") -> dict:
    value = {
        "schema_version": "1.0",
        "task_id": task_id,
        "title": "Kiểm tra khả năng đạt cổng trước khi claim",
        "research_question": "Runtime hiện tại có đủ năng lực để hoàn thành G2 không?",
        "workstream": "structural_physics",
        "priority": "P0",
        "status": "READY",
        "owner": None,
        "reviewer": None,
        "dependencies": [],
        "required_gates": ["G2"],
        "claim_ceiling": "SCREENED",
        "write_scope": ["research/probe.md"],
        "acceptance_criteria": ["Dừng trước claim nếu solver cần thiết đang ABSENT"],
        "required_artifacts": ["research/probe.md"],
        "safety_notes": ["Không suy diễn năng lực solver từ tên file hoặc marker"],
        "review_notes": [],
        "human_gate": False,
    }
    if runtime_scope is not None:
        value["runtime_scope"] = runtime_scope
    return value


def _scope(
    runtime_domain: str = "experimental_arch_frame",
    *families: str,
) -> dict:
    return {
        "structural_families": list(families or ("arch_deck_v1",)),
        "runtime_domain": runtime_domain,
    }


def _lab(tmp_path: Path, task: dict) -> Path:
    root = tmp_path / "multiagent"
    for name in (
        "tasks", "handoffs", "reviews", "amendments",
        "task_contract_snapshots/sha256", "incidents", "corrections",
        "correction_reviews", "snapshots/sha256", "runs", "intake", ".locks",
    ):
        (root / name).mkdir(parents=True, exist_ok=True)
    _write_json(
        root / "lab.json",
        {
            "schema_version": "1.0",
            "lab_id": "test-lab",
            "current_project_claim_ceiling": "SCREENED",
        },
    )
    _write_json(root / "tasks" / f"{task['task_id']}.json", task)
    return root


def _matrix(tmp_path: Path, states: dict[str, str]) -> Path:
    path = tmp_path / "runtime_capability_matrix.json"
    _write_json(
        path,
        {
            "schema_version": 1,
            "matrix_id": "RCM-TEST",
            "package_version": "0.0.0-test",
            "claim_ceiling": "IDEA",
            "claim_ceiling_evidence": {"path": "test", "pointer": "/"},
            "doc_mirror": "docs/runtime_capability_matrix.md",
            "runtime_rule_inventory": ["GEO-001"],
            "capabilities": [
                {
                    "id": capability_id,
                    "title": capability_id,
                    "state": state,
                    "evidence": ["test fixture"],
                    "limits": "Test fixture; not runtime evidence.",
                    "probes": [{
                        "kind": "declared_not_machine_provable",
                        "rationale": "Synthetic capability used only by isolated claim tests.",
                    }],
                }
                for capability_id, state in states.items()
            ],
            "known_card_reference_exceptions": [],
            "declared_counts": [{
                "id": "test_count",
                "description": "Synthetic count",
                "source": "load_cards",
                "doc_claims": [],
            }],
            "fabrication_rule_probes": [{
                "rule_id": "FAB-001", "params": {}, "context": {},
            }],
            "l0_pipeline_probe": {
                "grammar_id": "test_grammar",
                "design_variables": {},
                "girder_concrete_id": "test_concrete",
                "deck_concrete_id": "test_concrete",
                "expect_section_source": "test",
                "expect_rule_ids": ["GEO-001"],
            },
        },
    )
    return path


def test_claim_blocks_unreachable_gate_before_mutating_task(tmp_path, monkeypatch):
    task = _task(runtime_scope=_scope())
    root = _lab(tmp_path, task)
    task_path = root / "tasks" / "BRD-999.json"
    bytes_before = task_path.read_bytes()
    monkeypatch.setattr(
        lab_module,
        "RUNTIME_CAPABILITY_MATRIX_PATH",
        _matrix(
            tmp_path,
            {"SOLVER_MIDAS_CIVIL": "ABSENT", "SOLVER_OPENSEESPY": "ABSENT"},
        ),
    )

    with pytest.raises(
        ValueError,
        match=r"G2.*SOLVER_MIDAS_CIVIL=ABSENT.*SOLVER_OPENSEESPY=ABSENT",
    ):
        claim_task("BRD-999", "codex", root)

    assert task_path.read_bytes() == bytes_before


def test_any_requirement_allows_claim_when_one_capability_is_present(tmp_path, monkeypatch):
    root = _lab(
        tmp_path,
        _task(runtime_scope=_scope()),
    )
    monkeypatch.setattr(
        lab_module,
        "RUNTIME_CAPABILITY_MATRIX_PATH",
        _matrix(
            tmp_path,
            {
                "L0_LAYOUT_RULES": "PRESENT",
                "L0_FABRICATION_RULES": "PRESENT",
                "SOLVER_MIDAS_CIVIL": "ABSENT",
                "SOLVER_OPENSEESPY": "PRESENT",
            },
        ),
    )

    claimed = claim_task("BRD-999", "codex", root)

    assert claimed["status"] == "ACTIVE"
    assert claimed["owner"] == "codex"


def test_partial_capability_never_satisfies_claim_gate(tmp_path, monkeypatch):
    root = _lab(tmp_path, _task(runtime_scope=_scope()))
    monkeypatch.setattr(
        lab_module,
        "RUNTIME_CAPABILITY_MATRIX_PATH",
        _matrix(
            tmp_path,
            {"SOLVER_MIDAS_CIVIL": "PARTIAL", "SOLVER_OPENSEESPY": "ABSENT"},
        ),
    )

    with pytest.raises(ValueError, match=r"SOLVER_MIDAS_CIVIL=PARTIAL"):
        claim_task("BRD-999", "codex", root)


def test_all_requirement_blocks_when_one_capability_is_absent(tmp_path, monkeypatch):
    root = _lab(
        tmp_path,
        _task(runtime_scope=_scope("production_line_girder_l1", "super_t_simple_v1")),
    )
    monkeypatch.setattr(
        lab_module,
        "RUNTIME_CAPABILITY_MATRIX_PATH",
        _matrix(
            tmp_path,
            {
                "L1_LINE_GIRDER_SOLVER": "PRESENT",
                "INDEPENDENT_VERIFIER": "PRESENT",
                "EVALUATION_CONTRACT": "ABSENT",
            },
        ),
    )

    with pytest.raises(ValueError, match=r"G2.*EVALUATION_CONTRACT=ABSENT"):
        claim_task("BRD-999", "codex", root)


def test_family_cannot_borrow_an_unrelated_runtime_domain(tmp_path, monkeypatch):
    root = _lab(
        tmp_path,
        _task(runtime_scope=_scope("production_line_girder_l1", "arch_deck_v1")),
    )
    monkeypatch.setattr(
        lab_module,
        "RUNTIME_CAPABILITY_MATRIX_PATH",
        _matrix(tmp_path, {"L1_LINE_GIRDER_SOLVER": "PRESENT"}),
    )

    with pytest.raises(ValueError, match=r"không áp dụng cho family arch_deck_v1"):
        claim_task("BRD-999", "codex", root)


def test_scoped_task_cannot_omit_policy_for_a_required_machine_gate(tmp_path, monkeypatch):
    task = _task(runtime_scope=_scope())
    task["required_gates"] = ["G3"]
    root = _lab(tmp_path, task)
    monkeypatch.setattr(
        lab_module,
        "RUNTIME_CAPABILITY_MATRIX_PATH",
        _matrix(tmp_path, {"SOLVER_OPENSEESPY": "PRESENT"}),
    )

    with pytest.raises(ValueError, match=r"không có capability policy cho gate G3"):
        claim_task("BRD-999", "codex", root)


def test_screened_ceiling_cannot_hide_machine_gates_with_empty_required_gates(
    tmp_path, monkeypatch,
):
    task = _task(runtime_scope=_scope())
    task["required_gates"] = []
    task["claim_ceiling"] = "SCREENED"
    root = _lab(tmp_path, task)
    monkeypatch.setattr(
        lab_module,
        "RUNTIME_CAPABILITY_MATRIX_PATH",
        _matrix(
            tmp_path,
            {
                "L0_LAYOUT_RULES": "PRESENT",
                "L0_FABRICATION_RULES": "PARTIAL",
                "SOLVER_MIDAS_CIVIL": "ABSENT",
                "SOLVER_OPENSEESPY": "ABSENT",
            },
        ),
    )

    with pytest.raises(ValueError, match=r"G1.*L0_FABRICATION_RULES=PARTIAL"):
        claim_task("BRD-999", "codex", root)


def test_frozen_legacy_task_without_runtime_scope_warns_but_remains_claimable(tmp_path, monkeypatch):
    root = _lab(tmp_path, _task(runtime_scope=None, task_id="BRD-004"))
    monkeypatch.setattr(
        lab_module,
        "RUNTIME_CAPABILITY_MATRIX_PATH",
        _matrix(tmp_path, {"SOLVER_OPENSEESPY": "ABSENT"}),
    )

    with pytest.warns(RuntimeWarning, match="không khai runtime_scope"):
        claimed = claim_task("BRD-004", "codex", root)

    assert claimed["status"] == "ACTIVE"


def test_new_task_cannot_claim_without_runtime_scope(tmp_path, monkeypatch):
    root = _lab(tmp_path, _task(runtime_scope=None))
    monkeypatch.setattr(
        lab_module,
        "RUNTIME_CAPABILITY_MATRIX_PATH",
        _matrix(tmp_path, {"SOLVER_OPENSEESPY": "PRESENT"}),
    )

    with pytest.raises(ValueError, match=r"task mới đòi machine gate.*không khai runtime_scope"):
        claim_task("BRD-999", "codex", root)


@pytest.mark.parametrize("task_id", ["BRD-000", "RND-647720ea-99"])
def test_unallocated_id_cannot_impersonate_a_legacy_task(tmp_path, monkeypatch, task_id):
    root = _lab(tmp_path, _task(runtime_scope=None, task_id=task_id))
    monkeypatch.setattr(
        lab_module,
        "RUNTIME_CAPABILITY_MATRIX_PATH",
        _matrix(tmp_path, {"SOLVER_OPENSEESPY": "PRESENT"}),
    )

    with pytest.raises(ValueError, match=r"task mới đòi machine gate.*runtime_scope"):
        claim_task(task_id, "codex", root)


def test_claim_refuses_schema_invalid_task_before_reachability(tmp_path, monkeypatch):
    task = _task(runtime_scope=_scope("production_line_girder_l1", "super_t_simple_v1"))
    task["runtime_scope"]["structural_families"] = []
    root = _lab(tmp_path, task)
    monkeypatch.setattr(
        lab_module,
        "RUNTIME_CAPABILITY_MATRIX_PATH",
        _matrix(
            tmp_path,
            {
                "L1_LINE_GIRDER_SOLVER": "PRESENT",
                "INDEPENDENT_VERIFIER": "PRESENT",
                "EVALUATION_CONTRACT": "PRESENT",
            },
        ),
    )

    with pytest.raises(ValueError, match=r"không đúng schema.*should be non-empty"):
        claim_task("BRD-999", "codex", root)


def test_claim_refuses_schema_invalid_capability_matrix(tmp_path, monkeypatch):
    root = _lab(tmp_path, _task(runtime_scope=_scope()))
    malformed = _matrix(
        tmp_path,
        {"SOLVER_MIDAS_CIVIL": "ABSENT", "SOLVER_OPENSEESPY": "PRESENT"},
    )
    value = json.loads(malformed.read_text(encoding="utf-8"))
    del value["package_version"]
    _write_json(malformed, value)
    monkeypatch.setattr(lab_module, "RUNTIME_CAPABILITY_MATRIX_PATH", malformed)

    with pytest.raises(ValueError, match=r"matrix không đúng schema.*package_version"):
        claim_task("BRD-999", "codex", root)


def test_claim_refuses_non_object_capability_matrix_without_crashing(tmp_path, monkeypatch):
    root = _lab(tmp_path, _task(runtime_scope=_scope()))
    malformed = tmp_path / "runtime_capability_matrix.json"
    malformed.write_text("[]\n", encoding="utf-8")
    monkeypatch.setattr(lab_module, "RUNTIME_CAPABILITY_MATRIX_PATH", malformed)

    with pytest.raises(ValueError, match=r"matrix không đúng schema.*object"):
        claim_task("BRD-999", "codex", root)


def test_claim_refuses_missing_matrix_schema_without_raw_traceback(tmp_path, monkeypatch):
    root = _lab(tmp_path, _task(runtime_scope=_scope()))
    monkeypatch.setattr(
        lab_module,
        "RUNTIME_CAPABILITY_MATRIX_PATH",
        _matrix(
            tmp_path,
            {
                "L0_LAYOUT_RULES": "PRESENT",
                "L0_FABRICATION_RULES": "PRESENT",
                "SOLVER_MIDAS_CIVIL": "ABSENT",
                "SOLVER_OPENSEESPY": "PRESENT",
            },
        ),
    )

    original_schema = lab_module._schema

    def missing_schema(name):
        if name == "runtime_capability_matrix.schema.json":
            raise FileNotFoundError("matrix schema missing")
        return original_schema(name)

    monkeypatch.setattr(lab_module, "_schema", missing_schema)
    with pytest.raises(ValueError, match=r"không đọc được.*matrix/schema"):
        claim_task("BRD-999", "codex", root)


def test_runtime_policy_references_only_declared_capabilities():
    matrix = json.loads(
        lab_module.RUNTIME_CAPABILITY_MATRIX_PATH.read_text(encoding="utf-8")
    )
    declared = {entry["id"] for entry in matrix["capabilities"]}
    referenced = {
        capability_id
        for policy in lab_module.RUNTIME_SCOPE_POLICIES.values()
        for requirements in policy["gates"].values()
        for _mode, capability_ids in requirements
        for capability_id in capability_ids
    }
    assert referenced <= declared


def test_runtime_scope_is_amendable_instead_of_requiring_allowlist_growth():
    assert "runtime_scope" in lab_module.TASK_AMENDABLE_FIELDS


def test_runtime_scope_schema_is_optional_and_strict():
    schema = json.loads(
        (CONTRACTS_DIR / "research_task.schema.json").read_text(encoding="utf-8")
    )
    validator = Draft202012Validator(schema)

    assert list(validator.iter_errors(_task(runtime_scope=None))) == []
    assert list(validator.iter_errors(_task(runtime_scope=_scope()))) == []

    malformed = _task(runtime_scope=_scope())
    malformed["runtime_scope"]["invented_escape_hatch"] = True
    errors = list(validator.iter_errors(malformed))
    assert errors
    assert any("Additional properties" in error.message for error in errors)


def test_existing_reject_then_candidate_lineage_preserves_f0_work(tmp_path):
    blocked_task = _task(runtime_scope=None, task_id="BRD-999")
    blocked_task.update(
        {
            "status": "ACTIVE",
            "owner": "claude",
            "write_scope": ["README.md"],
            "required_artifacts": ["README.md"],
        }
    )
    root = _lab(tmp_path, blocked_task)

    first = submit_handoff(
        "BRD-999",
        "claude",
        "form_inventor",
        "Giữ nguyên artifact F0 nhưng dừng task SCREENED vì G2 không thể đạt.",
        "IDEA",
        [],
        ["README.md"],
        unresolved_risks=["Runtime chưa có solver cho họ kết cấu đã khai."],
        lab_dir=root,
    )
    rejected = review_handoff(
        "BRD-999",
        "opencode",
        "REJECT",
        [{"gate": "G2", "status": "FAIL", "evidence": "Required solver is ABSENT."}],
        "Đóng hợp đồng không thể đạt; không hạ gate và không xóa artifact F0.",
        root,
    )
    assert rejected["decision"] == "REJECT"

    successor = _task(runtime_scope=_scope(), task_id="BRD-998")
    successor.update(
        {
            "required_gates": [],
            "claim_ceiling": "IDEA",
            "write_scope": ["README.md"],
            "required_artifacts": ["README.md"],
            "review_notes": [
                "Candidate lineage của BRD-999; tái sử dụng artifact SHA-256 "
                + first["artifacts"][0]["sha256"]
            ],
        }
    )
    _write_json(root / "tasks" / "BRD-998.json", successor)

    claimed = claim_task("BRD-998", "codex", root)
    assert claimed["status"] == "ACTIVE"
    assert json.loads(
        (root / "tasks" / "BRD-999.json").read_text(encoding="utf-8")
    )["status"] == "REJECTED"
