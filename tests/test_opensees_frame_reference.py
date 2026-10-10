from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import os
import sys
from copy import deepcopy
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parent.parent
MODULE_PATH = ROOT / "experiments" / "validation" / "opensees_frame_reference.py"
ARTIFACT_PATH = ROOT / "experiments" / "validation" / "opensees_brd044_benchmarks.json"
BASIS_PATH = ROOT / "docs" / "design_basis" / "opensees_frame_reference_basis.json"
SCHEMA_PATH = ROOT / "contracts" / "opensees_frame_reference.schema.json"

SPEC = importlib.util.spec_from_file_location("brd044_opensees_reference", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
osref = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = osref
SPEC.loader.exec_module(osref)


EXPECTED_SOURCE_DIGESTS = {
    "experiments/validation/opensees_frame_reference.py":
        "fe65de3c259aafc027ae78ca58462cfa480116a6b77448c806b5739178d85915",
    "bridge_evolution/creative_shape.py":
        "f8e1b393ce0bd76b97b3af69053c8fe72d2902de7b6fab8d88e3879e26646e10",
    "bridge_evolution/frame_f1.py":
        "1ebbd5defb47b58eb5eb9171d28c52b1db721c10c2fbfefe083f86fba756720c",
    "bridge_evolution/creative_frame_adapter.py":
        "cb331daeeac877471632ca693b53fb1e65b08dd63e802af3c5b18745507b8507",
    "bridge_evolution/arch_action_f1.py":
        "9ef18b029ad021d1ccfd696c96cc4a9a295c552663e28a5332f925220b76bace",
    "bridge_evolution/funicular_reference.py":
        "0483ea7383e5ba5821c34d064b74f7927768c152000e242b789f95772f0342de",
}


@pytest.fixture(scope="module")
def suite() -> dict:
    return json.loads(ARTIFACT_PATH.read_text(encoding="utf-8"))


def _case(suite: dict, case_id: str) -> dict:
    return next(item for item in suite["cases"] if item["case_id"] == case_id)


def _by_id(items: list[dict], key: str) -> dict[str, dict]:
    return {item[key]: item for item in items}


def _backend_or_skip() -> tuple[Path, Path]:
    python_path = os.environ.get("DYLIGHT_OPENSEES_PYTHON")
    site_path = os.environ.get("DYLIGHT_OPENSEES_SITE_PACKAGES")
    if not python_path or not site_path:
        pytest.skip("Đặt DYLIGHT_OPENSEES_PYTHON và DYLIGHT_OPENSEES_SITE_PACKAGES để rerun")
    python = Path(python_path)
    site = Path(site_path)
    if not python.is_file() or not site.is_dir():
        pytest.skip("OpenSees backend paths không tồn tại trên host này")
    return python, site


def _reseal_suite(value: dict) -> None:
    for case in value["cases"]:
        case["case_sha256"] = osref._case_hash(case)
    value["suite_id"] = "OSR-" + osref.sha256_json({
        "basis_sha256": value["basis_sha256"],
        "source_sha256": value["reference_source_sha256"],
        "case_sha256": [case["case_sha256"] for case in value["cases"]],
    })[:16]
    value["suite_sha256"] = osref._suite_hash(value)


def test_canonical_artifact_is_semantically_reproducible(suite):
    osref.validate_benchmark_suite(suite)
    assert suite["status"] == "BENCHMARK_SUITE_COMPLETE"
    assert suite["claim_level"] == "IDEA"
    assert suite["design_verdict_authority"] == "NONE"
    assert len(suite["cases"]) == 6


def test_source_seal_covers_brd039_through_brd043_and_worker(suite):
    observed = {item["path"]: item["sha256"] for item in suite["reference_source_digests"]}
    assert observed == EXPECTED_SOURCE_DIGESTS
    assert suite["reference_source_sha256"] == osref.sha256_json(
        [{"path": path, "sha256": digest} for path, digest in EXPECTED_SOURCE_DIGESTS.items()]
    )


def test_backend_identity_is_real_opensees_binary(suite):
    engine = suite["backend_identity"]
    assert engine == {
        "binary_file_name": "opensees.pyd",
        "binary_sha256": "25ba42e1672526137d765d9c3631d1403e091f54f5afcdb9242f9243c63c3a96",
        "engine_version": "3.8.0",
        "name": "OpenSees",
        "package_name": "openseespywin",
        "package_version": "3.8.0.0",
        "python_executable_sha256": "d8e3f0adf246db00358c0c4ed349cf714898178f9558fb0e944f79f5c07f8eaa",
        "python_implementation": "CPython",
        "python_version": "3.12.13",
        "worker_source_sha256": EXPECTED_SOURCE_DIGESTS[
            "experiments/validation/opensees_frame_reference.py"
        ],
    }


def test_openSees_axial_bar_matches_closed_form_without_using_f1_result(suite):
    case = _case(suite, "BRD044-ANALYTICAL-AXIAL")
    raw = case["opensees_result"]["load_case_results"][0]
    displacement = _by_id(raw["nodal_displacements"], "node_id")
    reactions = _by_id(raw["reactions"], "node_id")
    forces = _by_id(raw["element_end_forces"], "element_id")
    expected = 100.0 * 2.0 / (200.0e6 * 0.02)
    assert displacement["N2"]["ux_m"] == pytest.approx(expected, rel=1e-12)
    assert reactions["N1"]["fx_kN"] == pytest.approx(-100.0, abs=1e-10)
    assert forces["E1"]["axial_i_kN"] == pytest.approx(-100.0, abs=1e-10)
    assert forces["E1"]["axial_j_kN"] == pytest.approx(100.0, abs=1e-10)


def test_openSees_cantilever_matches_euler_bernoulli_solution(suite):
    case = _case(suite, "BRD044-ANALYTICAL-CANTILEVER")
    raw = case["opensees_result"]["load_case_results"][0]
    displacement = _by_id(raw["nodal_displacements"], "node_id")["N2"]
    reaction = _by_id(raw["reactions"], "node_id")["N1"]
    E, inertia, load, length = 200.0e6, 0.002, 10.0, 3.0
    assert displacement["uy_m"] == pytest.approx(-load * length**3 / (3 * E * inertia), rel=1e-11)
    assert displacement["rz_rad"] == pytest.approx(-load * length**2 / (2 * E * inertia), rel=1e-11)
    assert reaction["fy_kN"] == pytest.approx(load, abs=1e-9)
    assert reaction["mz_kNm"] == pytest.approx(load * length, abs=1e-9)


def test_openSees_simple_beam_matches_closed_form_reactions_deflection_and_moment(suite):
    case = _case(suite, "BRD044-ANALYTICAL-SIMPLE-BEAM")
    raw = case["opensees_result"]["load_case_results"][0]
    displacement = _by_id(raw["nodal_displacements"], "node_id")
    reactions = _by_id(raw["reactions"], "node_id")
    E, inertia, load, length = 200.0e6, 0.002, 20.0, 10.0
    assert displacement["M"]["uy_m"] == pytest.approx(
        -load * length**3 / (48 * E * inertia), rel=1e-11
    )
    assert reactions["A"]["fy_kN"] == pytest.approx(load / 2, abs=1e-9)
    assert reactions["B"]["fy_kN"] == pytest.approx(load / 2, abs=1e-9)
    max_moment = max(
        abs(item[field]) for item in raw["element_end_forces"]
        for field in ("moment_i_kNm", "moment_j_kNm")
    )
    assert max_moment == pytest.approx(load * length / 4, rel=1e-11)


def test_three_creative_topologies_are_cross_solved_with_full_lineage(suite):
    creative = [case for case in suite["cases"] if case["case_kind"] == "CREATIVE_PIPELINE"]
    assert {case["lineage"]["topology"] for case in creative} == {
        "DECK_ARCH", "THROUGH_ARCH", "NETWORK_ARCH"
    }
    for case in creative:
        lineage = case["lineage"]
        assert all(lineage[key] is not None for key in (
            "candidate_sha256", "analysis_sha256", "arch_action_study_sha256",
            "funicular_reference_sha256",
        ))
        assert case["opensees_result"]["status"] == "CONVERGED"
        assert case["comparison"]["status"] == "AGREEMENT_WITHIN_PREREGISTERED_TOLERANCE"
        assert case["comparison"]["outside_tolerance_count"] == 0
        assert case["comparison"]["compared_value_count"] >= 280
        assert case["comparison"]["max_normalized_error"] < 0.001
        assert max(item["max_normalized"] for item in case["comparison"]["equilibrium"]) < 1e-5


def test_comparator_includes_zero_and_nonzero_values_in_every_response_family(suite):
    differences = [
        item for case in suite["cases"] for item in case["comparison"]["response_differences"]
    ]
    assert any(item["frame_f1_value"] == 0.0 for item in differences)
    assert any(item["frame_f1_value"] != 0.0 for item in differences)
    assert {item["response_group"] for item in differences} == {
        "NODAL_DISPLACEMENT", "NODAL_ROTATION", "SUPPORT_REACTION",
        "SUPPORT_MOMENT", "ELEMENT_END_FORCE", "ELEMENT_END_MOMENT",
    }


def test_worker_code_path_has_no_dylight_solver_imports():
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    worker_names = {"worker_solve", "_manual_worker_validate_model", "_solve_one_case", "_engine_identity"}
    snippets = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in worker_names:
            snippets.append(ast.get_source_segment(MODULE_PATH.read_text(encoding="utf-8"), node) or "")
    text = "\n".join(snippets)
    assert worker_names == {
        node.name for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in worker_names
    }
    assert all(name not in text for name in osref.FORBIDDEN_WORKER_MODULES)
    assert "analyze_frame_model" not in text


def test_backend_unavailable_is_explicit_and_never_falls_back(suite, tmp_path):
    model = deepcopy(suite["cases"][0]["model"])
    raw = osref.run_opensees_model(
        model,
        python_executable=tmp_path / "missing-python.exe",
        site_packages=tmp_path / "missing-site",
    )
    assert raw["status"] == "BACKEND_UNAVAILABLE"
    assert raw["engine"] is None
    assert raw["load_case_results"] == []
    f1, comparison = osref.compare_to_frame_f1(model, raw)
    assert f1["status"] == "CONVERGED"
    assert comparison["status"] == "NOT_EVALUABLE"
    assert comparison["reason_codes"] == ["ONE_OR_BOTH_SOLVERS_NOT_CONVERGED"]


@pytest.mark.parametrize(
    "mutation,match",
    [
        (lambda value: value["units"].__setitem__("force", "N"), "hệ đơn vị"),
        (lambda value: value["nodes"].append(deepcopy(value["nodes"][0])), "trùng id"),
        (lambda value: value["nodes"][1].__setitem__("x_m", value["nodes"][0]["x_m"]),
         "zero-length"),
        (lambda value: value["elements"][0].__setitem__("node_j", "ORPHAN"), "node mồ côi"),
        (lambda value: value["load_cases"][0]["nodal_loads"][0].__setitem__("fx_kN", float("nan")),
         "không phải JSON hữu hạn"),
        (lambda value: value["load_cases"][0]["nodal_loads"][0].__setitem__("mz_kNm", 1.0),
         "nút thuần TRUSS_2D"),
    ],
)
def test_worker_manual_validation_is_fail_closed_before_opensees(suite, mutation, match):
    model = deepcopy(suite["cases"][0]["model"])
    mutation(model)
    with pytest.raises(osref.WorkerInputError, match=match):
        osref._manual_worker_validate_model(model, 1e-9)


def test_direct_worker_nan_input_returns_structured_failure_without_importing_backend(suite):
    model = deepcopy(suite["cases"][0]["model"])
    model["nodes"][1]["x_m"] = float("nan")
    raw = osref.worker_solve(model, site_packages=None)
    assert raw["status"] == "SOLVER_FAILED"
    assert raw["engine"] is None
    assert raw["load_case_results"] == []
    assert raw["issues"]
    assert len(raw["model_payload_sha256"]) == 64


def test_id_permutation_does_not_change_comparison(suite):
    case = deepcopy(_case(suite, "BRD044-CREATIVE-NETWORK_ARCH"))
    raw = case["opensees_result"]
    raw["load_case_results"].reverse()
    for load_case in raw["load_case_results"]:
        load_case["nodal_displacements"].reverse()
        load_case["reactions"].reverse()
        load_case["element_end_forces"].reverse()
    raw["raw_result_sha256"] = osref._raw_result_hash(raw)
    _f1, comparison = osref.compare_to_frame_f1(case["model"], raw)
    assert comparison == case["comparison"]


def test_missing_response_id_is_rejected_not_silently_zipped(suite):
    case = deepcopy(_case(suite, "BRD044-ANALYTICAL-CANTILEVER"))
    raw = case["opensees_result"]
    raw["load_case_results"][0]["nodal_displacements"].pop()
    raw["raw_result_sha256"] = osref._raw_result_hash(raw)
    with pytest.raises(osref.OpenSeesReferenceError, match="node set"):
        osref.compare_to_frame_f1(case["model"], raw)


def test_mixed_absolute_relative_normalization_is_safe_at_zero():
    abs_error, normalized = osref._normalized_error(0.0, 5e-11, 1e-10, 1e-6)
    assert abs_error == pytest.approx(5e-11)
    assert normalized < 0.5
    _error, large = osref._normalized_error(0.0, 2e-10, 1e-10, 1e-6)
    assert large > 1.9


def test_plain_outer_tamper_is_rejected(suite):
    mutated = deepcopy(suite)
    mutated["status"] = "RECONCILIATION_REQUIRED"
    with pytest.raises(osref.OpenSeesReferenceError, match="suite_sha256"):
        osref.validate_benchmark_suite(mutated)


def test_resealed_model_tamper_is_rejected_by_pipeline_rederivation(suite):
    mutated = deepcopy(suite)
    case = mutated["cases"][0]
    case["model"]["nodes"][1]["x_m"] += 0.1
    case["model_payload_sha256"] = osref.sha256_json(case["model"])
    case["opensees_result"]["model_payload_sha256"] = case["model_payload_sha256"]
    case["opensees_result"]["raw_result_sha256"] = osref._raw_result_hash(
        case["opensees_result"]
    )
    _reseal_suite(mutated)
    with pytest.raises(osref.OpenSeesReferenceError, match="model không tái lập"):
        osref.validate_benchmark_suite(mutated)


def test_resealed_raw_response_tamper_is_rejected_by_comparison_rederivation(suite):
    mutated = deepcopy(suite)
    case = mutated["cases"][1]
    raw_case = case["opensees_result"]["load_case_results"][0]
    raw_case["nodal_displacements"][1]["uy_m"] *= 1.01
    raw_case["max_translation_m"] = max(
        (item["ux_m"] ** 2 + item["uy_m"] ** 2) ** 0.5
        for item in raw_case["nodal_displacements"]
    )
    case["opensees_result"]["raw_result_sha256"] = osref._raw_result_hash(
        case["opensees_result"]
    )
    _reseal_suite(mutated)
    with pytest.raises(osref.OpenSeesReferenceError, match="comparison không tái lập"):
        osref.validate_benchmark_suite(mutated)


def test_resealed_comparison_tamper_is_rejected(suite):
    mutated = deepcopy(suite)
    mutated["cases"][2]["comparison"]["max_normalized_error"] = 0.0
    _reseal_suite(mutated)
    with pytest.raises(osref.OpenSeesReferenceError, match="comparison không tái lập"):
        osref.validate_benchmark_suite(mutated)


def test_tolerance_tamper_is_rejected_even_with_outer_reseal(suite):
    mutated = deepcopy(suite)
    mutated["comparison_tolerances"]["force_relative"] *= 1000.0
    mutated["suite_sha256"] = osref._suite_hash(mutated)
    with pytest.raises(osref.OpenSeesReferenceError, match="tolerance drift"):
        osref.validate_benchmark_suite(mutated)


def test_source_digest_tamper_is_rejected_even_with_all_outer_ids_resealed(suite):
    mutated = deepcopy(suite)
    mutated["reference_source_digests"][0]["sha256"] = "0" * 64
    mutated["reference_source_sha256"] = osref.sha256_json(
        mutated["reference_source_digests"]
    )
    _reseal_suite(mutated)
    with pytest.raises(osref.OpenSeesReferenceError, match="source digests"):
        osref.validate_benchmark_suite(mutated)


def test_basis_source_hash_drift_is_fail_closed(tmp_path, monkeypatch):
    basis = json.loads(BASIS_PATH.read_text(encoding="utf-8"))
    basis["reference_source_sha256"] = "0" * 64
    path = tmp_path / "basis.json"
    path.write_text(json.dumps(basis), encoding="utf-8")
    monkeypatch.setattr(osref, "BASIS_PATH", path)
    with pytest.raises(osref.OpenSeesReferenceError, match="reference_source_sha256"):
        osref.load_basis()


def test_handoff_trust_anchor_rejects_fully_resealed_file_tamper(
    suite, tmp_path, monkeypatch,
):
    artifact = tmp_path / "artifact.json"
    original_bytes = ARTIFACT_PATH.read_bytes()
    artifact.write_bytes(original_bytes)
    expected_hash = hashlib.sha256(original_bytes).hexdigest()
    handoff = tmp_path / "handoff.json"
    handoff.write_text(json.dumps({
        "task_id": "BRD-044",
        "artifacts": [{"path": "artifact.json", "sha256": expected_hash, "kind": "data"}],
    }), encoding="utf-8")
    tampered = deepcopy(suite)
    case = tampered["cases"][0]
    raw_case = case["opensees_result"]["load_case_results"][0]
    raw_case["nodal_displacements"][1]["ux_m"] *= 1.5
    raw_case["max_translation_m"] = max(
        (item["ux_m"] ** 2 + item["uy_m"] ** 2) ** 0.5
        for item in raw_case["nodal_displacements"]
    )
    case["opensees_result"]["raw_result_sha256"] = osref._raw_result_hash(
        case["opensees_result"]
    )
    case["frame_f1_result"], case["comparison"] = osref.compare_to_frame_f1(
        case["model"], case["opensees_result"]
    )
    _reseal_suite(tampered)
    artifact.write_text(json.dumps(tampered), encoding="utf-8")
    monkeypatch.setattr(osref, "REPO_ROOT", tmp_path)
    with pytest.raises(osref.OpenSeesReferenceError, match="drift khỏi handoff"):
        osref.validate_artifact_against_handoff(artifact, handoff)


@pytest.mark.parametrize("forbidden", [
    "feasible", "verified", "design_pass", "utilization", "safety_factor",
])
def test_schema_and_validator_reject_design_verdict_backdoors(suite, forbidden):
    mutated = deepcopy(suite)
    mutated[forbidden] = True
    mutated["suite_sha256"] = osref._suite_hash(mutated)
    with pytest.raises(osref.OpenSeesReferenceError, match="sai schema"):
        osref.validate_benchmark_suite(mutated)


def test_artifact_and_schema_contain_no_forbidden_verdict_keys():
    artifact = json.loads(ARTIFACT_PATH.read_text(encoding="utf-8"))
    forbidden = {"feasible", "verified", "design_pass", "utilization", "safety_factor"}

    def keys(value):
        if isinstance(value, dict):
            yield from value
            for child in value.values():
                yield from keys(child)
        elif isinstance(value, list):
            for child in value:
                yield from keys(child)

    assert forbidden.isdisjoint(set(keys(artifact)))
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    assert schema["properties"]["claim_level"] == {"const": "IDEA"}
    assert schema["properties"]["design_verdict_authority"] == {"const": "NONE"}


def test_actual_backend_rerun_is_byte_deterministic(suite):
    python, site = _backend_or_skip()
    osref.validate_benchmark_suite(
        suite,
        rerun_backend=True,
        python_executable=python,
        site_packages=site,
    )


def test_actual_backend_reports_unstable_model_as_solver_failed(suite):
    python, site = _backend_or_skip()
    model = deepcopy(_case(suite, "BRD044-ANALYTICAL-AXIAL")["model"])
    model["model_id"] = "F1M-BRD044-global-mechanism"
    model["supports"] = [
        {"node_id": "N1", "ux": True, "uy": False, "rz": False}
    ]
    raw = osref.run_opensees_model(
        model,
        python_executable=python,
        site_packages=site,
    )
    assert raw["status"] == "SOLVER_FAILED"
    assert raw["issues"]
    assert raw["load_case_results"][0]["status"] == "SOLVER_FAILED"
    assert raw["load_case_results"][0]["analyze_return_code"] != 0
    _f1, comparison = osref.compare_to_frame_f1(model, raw)
    assert comparison["status"] == "NOT_EVALUABLE"
