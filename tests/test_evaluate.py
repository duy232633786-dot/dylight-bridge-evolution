import json
import re
from pathlib import Path

from bridge_evolution.evaluate import evaluate_candidate
from bridge_evolution.state import validate_evaluation_result

CASES = Path(__file__).resolve().parent.parent / "gold_cases" / "cases"


def load(name):
    with open(CASES / name, encoding="utf-8") as f:
        return json.load(f)


def strip_volatile(result):
    r = json.loads(json.dumps(result))
    r["provenance"].pop("timestamp_utc", None)
    r["solver"].pop("runtime_ms", None)
    return r


def test_result_matches_contract_schema():
    result = evaluate_candidate(load("GC-01_standard_pass.json"))
    assert validate_evaluation_result(result) == []


def test_rerun_reproducible():
    """Gate 'Re-run within numerical tolerance': cùng input → cùng số liệu."""
    a = evaluate_candidate(load("GC-01_standard_pass.json"))
    b = evaluate_candidate(load("GC-01_standard_pass.json"))
    assert strip_volatile(a) == strip_volatile(b)
    assert a["provenance"]["input_hash"] == b["provenance"]["input_hash"]


def test_schema_invalid_status():
    state = load("GC-01_standard_pass.json")
    state["design_variables"]["girder_count"] = "six"
    result = evaluate_candidate(state)
    assert result["status"] == "SCHEMA_INVALID" and not result["feasible"]


def test_unknown_catalog_id_is_schema_level():
    state = load("GC-01_standard_pass.json")
    state["design_variables"]["girder_catalog_id"] = "ST-KHONG-TON-TAI"
    result = evaluate_candidate(state)
    assert result["status"] == "SCHEMA_INVALID"


def test_provenance_complete():
    r = evaluate_candidate(load("GC-01_standard_pass.json"))
    p = r["provenance"]
    assert p["input_hash"] and p["ruleset_version"] and p["solver_version"]
    assert p["catalogs_version"] and p["grammar_version"]


def test_legacy_case_id_never_controls_output_id():
    state = load("GC-01_standard_pass.json")
    state["case_id"] = "BT-deadbeef"  # input legacy 8 hex vẫn được chấp nhận
    result = evaluate_candidate(state)
    assert result["status"] == "SUCCESS"
    assert re.fullmatch(r"BT-[0-9a-f]{16}", result["case_id"])
    assert result["case_id"] != state["case_id"]


def test_artifact_manifest_is_in_saved_report_and_validated(monkeypatch, tmp_path):
    import bridge_evolution.evaluate as evaluate_module

    artifact_root = tmp_path / "artifacts"
    monkeypatch.setattr(evaluate_module, "ARTIFACTS_DIR", artifact_root)
    result = evaluate_module.evaluate_candidate(
        load("GC-01_standard_pass.json"), save_artifacts=True
    )

    assert validate_evaluation_result(result) == []
    assert set(result["artifacts"]) == {
        "design_state", "verification_report", "analysis_result"
    }
    report_path = artifact_root / result["case_id"] / "verification_report.json"
    saved_report = json.loads(report_path.read_text(encoding="utf-8"))
    assert saved_report == result
    assert saved_report["artifacts"] == result["artifacts"]


def test_path_traversal_case_id_cannot_escape_artifact_root(monkeypatch, tmp_path):
    import bridge_evolution.evaluate as evaluate_module

    artifact_root = tmp_path / "artifacts"
    monkeypatch.setattr(evaluate_module, "ARTIFACTS_DIR", artifact_root)
    state = load("GC-01_standard_pass.json")
    state["case_id"] = "../../escape"

    result = evaluate_module.evaluate_candidate(state, save_artifacts=True)

    assert result["status"] == "SCHEMA_INVALID"
    assert re.fullmatch(r"BT-[0-9a-f]{16}", result["case_id"])
    assert (artifact_root / result["case_id"] / "verification_report.json").is_file()
    assert not (tmp_path / "escape").exists()
    saved_state = json.loads(
        (artifact_root / result["case_id"] / "design_state.json").read_text(encoding="utf-8")
    )
    assert saved_state["case_id"] == result["case_id"]


def test_solver_failure_names_and_versions_requested_solver():
    state = load("GC-01_standard_pass.json")
    state["analysis"].update(fidelity="L2_GRILLAGE", solver="MIDAS_CIVIL")
    result = evaluate_candidate(state)
    assert result["status"] == "SOLVER_FAILED"
    assert result["solver"]["name"] == "MIDAS_CIVIL"
    assert result["provenance"]["solver_version"].startswith("MIDAS_CIVIL/")


def test_incompatible_fidelity_solver_is_schema_invalid():
    state = load("GC-01_standard_pass.json")
    state["analysis"].update(fidelity="L3_NONLINEAR", solver="BUILTIN_L1")
    result = evaluate_candidate(state)
    assert result["status"] == "SCHEMA_INVALID"
    assert result["solver"]["status"] == "NOT_RUN"


def test_compression_block_outside_slab_is_hard_model_violation():
    """Một candidate từng được coi feasible phải bị chặn khi công thức Mn hết hiệu lực."""
    state = load("GC-01_standard_pass.json")
    state["design_variables"].update({
        "girder_catalog_id": "ST-1650",
        "girder_count": 5,
        "girder_spacing_mm": 2350,
        "deck_slab_thickness_mm": 180,
        "diaphragm_layout_id": "DG-5",
        "prestress_layout_id": "PT-54",
    })

    result = evaluate_candidate(state)
    model = next(v for v in result["violations"] if v["rule_id"] == "MODEL-001")

    assert result["status"] == "SUCCESS"
    assert result["feasible"] is False
    assert model["severity"] == "HARD"
    assert model["margin"] > 0
    assert "a=" in model["message"] and "ts=" in model["message"]
    assert result["responses"]["max_utilization"] > 1.0
