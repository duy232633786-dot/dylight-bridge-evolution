from __future__ import annotations

from copy import deepcopy

import pytest

import bridge_evolution.frame_f1 as frame_f1
from bridge_evolution.frame_f1 import (
    FrameF1Error,
    analyze_frame_model,
    load_frame_basis,
    validate_frame_model,
    validate_frame_result,
)


UNITS = {
    "length": "m",
    "force": "kN",
    "moment": "kN_m",
    "elastic_modulus": "GPa",
    "area": "m2",
    "inertia": "m4",
}


@pytest.fixture
def evidence(tmp_path, monkeypatch) -> str:
    monkeypatch.setattr(frame_f1, "REPO_ROOT", tmp_path)
    (tmp_path / "evidence.json").write_text(
        '{"purpose":"test-only benchmark provenance"}', encoding="utf-8")
    return "evidence.json"


def model(*, nodes, elements, supports, loads, evidence: str,
          model_id: str = "F1M-benchmark", load_case_id: str = "LC1") -> dict:
    return {
        "schema_version": "1.0",
        "model_id": model_id,
        "analysis_type": "LINEAR_ELASTIC_2D_SMALL_DISPLACEMENT",
        "units": deepcopy(UNITS),
        "nodes": nodes,
        "materials": [{
            "id": "MAT1", "elastic_modulus_GPa": 200.0, "source_ref": evidence,
        }],
        "sections": [{
            "id": "SEC1", "area_m2": 0.02, "inertia_m4": 0.002,
            "source_ref": evidence,
        }],
        "elements": [
            {
                "id": item[0], "kind": item[1], "node_i": item[2], "node_j": item[3],
                "material_id": "MAT1", "section_id": "SEC1",
            }
            for item in elements
        ],
        "supports": supports,
        "load_cases": [{
            "id": load_case_id,
            "combination_status": "RESEARCH_BENCHMARK",
            "source_ref": evidence,
            "nodal_loads": loads,
        }],
    }


def axial_bar(evidence: str) -> dict:
    return model(
        nodes=[{"id": "N1", "x_m": 0.0, "y_m": 0.0},
               {"id": "N2", "x_m": 2.0, "y_m": 0.0}],
        elements=[("E1", "TRUSS_2D", "N1", "N2")],
        supports=[{"node_id": "N1", "ux": True, "uy": True, "rz": True},
                  {"node_id": "N2", "ux": False, "uy": True, "rz": False}],
        loads=[{"node_id": "N2", "fx_kN": 100.0, "fy_kN": 0.0, "mz_kNm": 0.0}],
        evidence=evidence,
        model_id="F1M-axial",
    )


def cantilever(evidence: str) -> dict:
    return model(
        nodes=[{"id": "N1", "x_m": 0.0, "y_m": 0.0},
               {"id": "N2", "x_m": 3.0, "y_m": 0.0}],
        elements=[("E1", "FRAME_2D", "N1", "N2")],
        supports=[{"node_id": "N1", "ux": True, "uy": True, "rz": True}],
        loads=[{"node_id": "N2", "fx_kN": 0.0, "fy_kN": -10.0, "mz_kNm": 0.0}],
        evidence=evidence,
        model_id="F1M-cantilever",
    )


def simple_beam(evidence: str) -> dict:
    return model(
        nodes=[{"id": "A", "x_m": 0.0, "y_m": 0.0},
               {"id": "M", "x_m": 5.0, "y_m": 0.0},
               {"id": "B", "x_m": 10.0, "y_m": 0.0}],
        elements=[("E1", "FRAME_2D", "A", "M"),
                  ("E2", "FRAME_2D", "M", "B")],
        supports=[{"node_id": "A", "ux": True, "uy": True, "rz": False},
                  {"node_id": "B", "ux": False, "uy": True, "rz": False}],
        loads=[{"node_id": "M", "fx_kN": 0.0, "fy_kN": -20.0, "mz_kNm": 0.0}],
        evidence=evidence,
        model_id="F1M-simple-beam",
    )


def shallow_v_truss(evidence: str, offset_m: float) -> dict:
    return model(
        nodes=[{"id": "N1", "x_m": 0.0, "y_m": 0.0},
               {"id": "N2", "x_m": 5.0, "y_m": offset_m},
               {"id": "N3", "x_m": 10.0, "y_m": 0.0}],
        elements=[("E1", "TRUSS_2D", "N1", "N2"),
                  ("E2", "TRUSS_2D", "N2", "N3")],
        supports=[{"node_id": "N1", "ux": True, "uy": True, "rz": True},
                  {"node_id": "N3", "ux": True, "uy": True, "rz": True}],
        loads=[{"node_id": "N2", "fx_kN": 0.0, "fy_kN": -10.0, "mz_kNm": 0.0}],
        evidence=evidence,
        model_id=f"F1M-v-truss-{offset_m:g}",
    )


def by_id(items: list[dict], key: str) -> dict[str, dict]:
    return {item[key]: item for item in items}


def test_basis_is_explicitly_f1_and_has_no_design_authority():
    basis = load_frame_basis()
    assert basis["claim_ceiling"] == "IDEA"
    assert basis["design_verdict_authority"] == "NONE"
    assert any("P-Delta" in item for item in basis["explicit_limitations"])
    assert all(item["url"].startswith("https://opensees.github.io/")
               for item in basis["official_method_sources"])
    assert basis["solver_source_sha256"] == frame_f1._solver_source_sha256()
    limitations = " ".join(basis["explicit_limitations"])
    assert "characteristic model length" in limitations
    assert "not a bridge-code serviceability limit" in limitations
    assert basis["numerical_guards"]["max_translation_to_characteristic_length"] == 0.05


def test_axial_bar_matches_closed_form_and_ignores_unloaded_rotation_dofs(evidence):
    result = analyze_frame_model(axial_bar(evidence))
    case = result["load_case_results"][0]
    displacement = by_id(case["nodal_displacements"], "node_id")
    reaction = by_id(case["reactions"], "node_id")
    expected = 100.0 * 2.0 / (200.0e6 * 0.02)
    assert result["status"] == "CONVERGED"
    assert displacement["N2"]["ux_m"] == pytest.approx(expected, rel=1e-12)
    assert reaction["N1"]["fx_kN"] == pytest.approx(-100.0, abs=1e-10)
    assert case["diagnostics"]["active_dof_count"] == 4
    assert len(case["diagnostics"]["excluded_dofs"]) == 2


def test_cantilever_tip_load_matches_euler_bernoulli_solution(evidence):
    result = analyze_frame_model(cantilever(evidence))
    case = result["load_case_results"][0]
    displacement = by_id(case["nodal_displacements"], "node_id")["N2"]
    E, I, P, length = 200.0e6, 0.002, 10.0, 3.0
    assert displacement["uy_m"] == pytest.approx(-P * length ** 3 / (3.0 * E * I), rel=1e-12)
    assert displacement["rz_rad"] == pytest.approx(-P * length ** 2 / (2.0 * E * I), rel=1e-12)
    assert all(check["status"] == "PASS" for check in case["checks"])


def test_inclined_frame_transformation_preserves_pure_axial_response(evidence):
    value = model(
        nodes=[{"id": "N1", "x_m": 0.0, "y_m": 0.0},
               {"id": "N2", "x_m": 3.0, "y_m": 4.0}],
        elements=[("E1", "FRAME_2D", "N1", "N2")],
        supports=[{"node_id": "N1", "ux": True, "uy": True, "rz": True}],
        loads=[{"node_id": "N2", "fx_kN": 60.0, "fy_kN": 80.0, "mz_kNm": 0.0}],
        evidence=evidence,
        model_id="F1M-inclined-axial",
    )
    case = analyze_frame_model(value)["load_case_results"][0]
    tip = by_id(case["nodal_displacements"], "node_id")["N2"]
    axial_displacement = 100.0 * 5.0 / (200.0e6 * 0.02)
    assert tip["ux_m"] == pytest.approx(0.6 * axial_displacement, rel=1e-11)
    assert tip["uy_m"] == pytest.approx(0.8 * axial_displacement, rel=1e-11)
    assert tip["rz_rad"] == pytest.approx(0.0, abs=1e-14)


def test_cantilever_tip_moment_uses_moment_units_and_equilibrates(evidence):
    value = cantilever(evidence)
    value["model_id"] = "F1M-cantilever-moment"
    value["load_cases"][0]["nodal_loads"] = [
        {"node_id": "N2", "fx_kN": 0.0, "fy_kN": 0.0, "mz_kNm": 30.0}
    ]
    case = analyze_frame_model(value)["load_case_results"][0]
    tip = by_id(case["nodal_displacements"], "node_id")["N2"]
    E, I, moment, length = 200.0e6, 0.002, 30.0, 3.0
    assert tip["uy_m"] == pytest.approx(moment * length ** 2 / (2.0 * E * I), rel=1e-12)
    assert tip["rz_rad"] == pytest.approx(moment * length / (E * I), rel=1e-12)
    assert case["diagnostics"]["moment_equilibrium_relative"] <= 1e-8


def test_simply_supported_beam_matches_midspan_deflection_reactions_and_moment(evidence):
    result = analyze_frame_model(simple_beam(evidence))
    case = result["load_case_results"][0]
    displacement = by_id(case["nodal_displacements"], "node_id")
    reaction = by_id(case["reactions"], "node_id")
    E, I, P, length = 200.0e6, 0.002, 20.0, 10.0
    assert displacement["M"]["uy_m"] == pytest.approx(-P * length ** 3 / (48.0 * E * I), rel=1e-11)
    assert reaction["A"]["fy_kN"] == pytest.approx(P / 2.0, abs=1e-9)
    assert reaction["B"]["fy_kN"] == pytest.approx(P / 2.0, abs=1e-9)
    max_moment = max(
        abs(force[key]) for force in case["element_end_forces"]
        for key in ("moment_i_kNm", "moment_j_kNm")
    )
    assert max_moment == pytest.approx(P * length / 4.0, rel=1e-11)


def test_every_converged_case_passes_equilibrium_and_energy_checks(evidence):
    for input_model in (axial_bar(evidence), cantilever(evidence), simple_beam(evidence)):
        case = analyze_frame_model(input_model)["load_case_results"][0]
        assert case["status"] == "CONVERGED"
        diagnostics = case["diagnostics"]
        assert diagnostics["free_residual_relative"] <= 1e-8
        assert diagnostics["force_equilibrium_relative"] <= 1e-8
        assert diagnostics["moment_equilibrium_relative"] <= 1e-8
        assert diagnostics["energy_identity_relative"] <= 1e-8


def test_loaded_inactive_truss_dof_is_reported_as_unstable_not_solved(evidence):
    unstable = model(
        nodes=[{"id": "A", "x_m": 0.0, "y_m": 0.0},
               {"id": "M", "x_m": 5.0, "y_m": 0.0},
               {"id": "B", "x_m": 10.0, "y_m": 0.0}],
        elements=[("E1", "TRUSS_2D", "A", "M"), ("E2", "TRUSS_2D", "M", "B")],
        supports=[{"node_id": "A", "ux": True, "uy": True, "rz": True},
                  {"node_id": "B", "ux": False, "uy": True, "rz": False}],
        loads=[{"node_id": "M", "fx_kN": 0.0, "fy_kN": -10.0, "mz_kNm": 0.0}],
        evidence=evidence,
        model_id="F1M-mechanism",
    )
    result = analyze_frame_model(unstable)
    case = result["load_case_results"][0]
    assert result["status"] == "UNSTABLE_MODEL"
    assert case["nodal_displacements"] == []
    assert "cơ cấu" in case["issues"][0] or "suy biến" in case["issues"][0]


def test_unloaded_global_truss_mechanism_is_not_silently_dropped(evidence):
    value = model(
        nodes=[{"id": "N1", "x_m": 0.0, "y_m": 0.0},
               {"id": "N2", "x_m": 10.0, "y_m": 0.0}],
        elements=[("E1", "TRUSS_2D", "N1", "N2")],
        supports=[{"node_id": "N1", "ux": True, "uy": False, "rz": False}],
        loads=[{"node_id": "N2", "fx_kN": 50.0, "fy_kN": 0.0, "mz_kNm": 0.0}],
        evidence=evidence,
        model_id="F1M-global-mechanism",
    )
    result = analyze_frame_model(value)
    assert result["status"] == "UNSTABLE_MODEL"
    assert result["load_case_results"][0]["checks"][0]["status"] == "FAIL"


def test_unloaded_local_translational_mechanism_is_not_silently_dropped(evidence):
    value = model(
        nodes=[{"id": "N1", "x_m": 0.0, "y_m": 0.0},
               {"id": "N2", "x_m": 5.0, "y_m": 0.0},
               {"id": "N3", "x_m": 10.0, "y_m": 0.0}],
        elements=[("E1", "TRUSS_2D", "N1", "N2"),
                  ("E2", "TRUSS_2D", "N2", "N3")],
        supports=[{"node_id": "N1", "ux": True, "uy": True, "rz": True},
                  {"node_id": "N3", "ux": False, "uy": True, "rz": True}],
        loads=[{"node_id": "N3", "fx_kN": 50.0, "fy_kN": 0.0, "mz_kNm": 0.0}],
        evidence=evidence,
        model_id="F1M-local-mechanism",
    )
    assert analyze_frame_model(value)["status"] == "UNSTABLE_MODEL"


def test_unit_scaled_condition_number_is_invariant_under_geometric_similarity(evidence):
    base = cantilever(evidence)
    first = analyze_frame_model(base)["load_case_results"][0]["diagnostics"]["condition_number"]
    for scale in (0.01, 100.0):
        scaled = deepcopy(base)
        scaled["model_id"] = f"F1M-cantilever-scaled-{scale:g}"
        for node in scaled["nodes"]:
            node["x_m"] *= scale
            node["y_m"] *= scale
        scaled["sections"][0]["area_m2"] *= scale ** 2
        scaled["sections"][0]["inertia_m4"] *= scale ** 4
        for load in scaled["load_cases"][0]["nodal_loads"]:
            load["fx_kN"] *= scale ** 2
            load["fy_kN"] *= scale ** 2
            load["mz_kNm"] *= scale ** 3
        second = analyze_frame_model(scaled)["load_case_results"][0]["diagnostics"]["condition_number"]
        assert second == pytest.approx(first, rel=1e-10)


def test_unit_scaling_exposes_shallow_v_truss_softness_and_small_displacement_limit(evidence):
    offsets = [0.5, 0.05, 0.005]
    cases = [
        analyze_frame_model(shallow_v_truss(evidence, offset))["load_case_results"][0]
        for offset in offsets
    ]
    conditions = [case["diagnostics"]["condition_number"] for case in cases]
    assert conditions[0] < conditions[1] < conditions[2]
    assert conditions[1] / conditions[0] > 50.0
    assert conditions[2] / conditions[1] > 50.0
    assert cases[0]["status"] == "CONVERGED"
    assert cases[1]["status"] == "CONVERGED"
    assert cases[2]["status"] == "MODEL_LIMIT_EXCEEDED"
    small_displacement = next(
        check for check in cases[2]["checks"]
        if check["check_id"] == "F1-SMALL-DISPLACEMENT"
    )
    assert small_displacement["status"] == "FAIL"
    assert cases[2]["diagnostics"]["max_translation_to_characteristic_length"] > 0.05
    assert cases[2]["max_translation_m"] > (
        0.05 * cases[2]["diagnostics"]["characteristic_length_m"])


def test_extreme_shallow_v_truss_never_reports_all_pass_converged(evidence):
    result = analyze_frame_model(shallow_v_truss(evidence, 5e-6))
    case = result["load_case_results"][0]
    assert result["status"] != "CONVERGED"
    assert case["status"] != "CONVERGED"
    assert not all(check["status"] == "PASS" for check in case["checks"])


def test_result_anchors_solver_source_bytes(evidence):
    result = analyze_frame_model(axial_bar(evidence))
    assert result["solver_sha256"] == frame_f1._solver_source_sha256()
    assert result["solver_source_digests"] == frame_f1._solver_source_digests()


def test_solver_source_hash_changes_when_any_local_kernel_source_drifts(tmp_path, monkeypatch):
    first = tmp_path / "frame_f1.py"
    second = tmp_path / "__init__.py"
    first.write_bytes(b"solver-v1")
    second.write_bytes(b"init-v1")
    monkeypatch.setattr(frame_f1, "_SOLVER_SOURCE_PATHS", (("frame", first), ("init", second)))
    before = frame_f1._solver_source_sha256()
    second.write_bytes(b"init-v2")
    assert frame_f1._solver_source_sha256() != before


@pytest.mark.parametrize(
    "mutation",
    [
        lambda value: value["nodes"].append(deepcopy(value["nodes"][0])),
        lambda value: value["nodes"][1].__setitem__("x_m", 0.0),
        lambda value: value["nodes"][1].__setitem__("x_m", float("nan")),
        lambda value: value["elements"][0].__setitem__("node_j", "ORPHAN"),
    ],
)
def test_invalid_geometry_and_references_are_blocked_before_solve(evidence, mutation):
    value = axial_bar(evidence)
    mutation(value)
    with pytest.raises(FrameF1Error):
        analyze_frame_model(value)


def test_zero_length_is_blocked_even_with_distinct_node_ids(evidence):
    value = axial_bar(evidence)
    value["nodes"][1]["x_m"] = value["nodes"][0]["x_m"]
    value["nodes"][1]["y_m"] = value["nodes"][0]["y_m"]
    with pytest.raises(FrameF1Error, match="zero-length"):
        validate_frame_model(value)


def test_missing_or_outside_source_is_blocked(evidence):
    for source_ref in ("missing.json", "../outside.json"):
        value = axial_bar(evidence)
        value["materials"][0]["source_ref"] = source_ref
        with pytest.raises(FrameF1Error, match="source_ref"):
            analyze_frame_model(value)


def test_disconnected_loaded_component_is_blocked(evidence):
    value = axial_bar(evidence)
    value["nodes"].append({"id": "N3", "x_m": 5.0, "y_m": 1.0})
    value["nodes"].append({"id": "N4", "x_m": 6.0, "y_m": 1.0})
    value["elements"].append({
        "id": "E2", "kind": "TRUSS_2D", "node_i": "N3", "node_j": "N4",
        "material_id": "MAT1", "section_id": "SEC1",
    })
    value["load_cases"][0]["nodal_loads"] = [
        {"node_id": "N3", "fx_kN": 1.0, "fy_kN": 0.0, "mz_kNm": 0.0}
    ]
    with pytest.raises(FrameF1Error, match="không có đường tới gối"):
        analyze_frame_model(value)


def test_source_byte_drift_changes_model_fingerprint(evidence, tmp_path):
    before = analyze_frame_model(axial_bar(evidence))
    (tmp_path / "evidence.json").write_text('{"purpose":"test-only","revision":2}', encoding="utf-8")
    after = analyze_frame_model(axial_bar(evidence))
    assert before["model_sha256"] != after["model_sha256"]
    assert before["source_digests"] != after["source_digests"]


def test_same_model_is_deterministic_and_result_hash_detects_tamper(evidence):
    first = analyze_frame_model(simple_beam(evidence))
    second = analyze_frame_model(simple_beam(evidence))
    assert first == second
    tampered = deepcopy(first)
    tampered["load_case_results"][0]["max_translation_m"] *= 2.0
    with pytest.raises(FrameF1Error, match="result_sha256 không khớp"):
        validate_frame_result(tampered)


def test_result_schema_rejects_design_verdict_backdoors(evidence):
    result = analyze_frame_model(axial_bar(evidence))
    assert result["claim_level"] == "IDEA"
    assert result["design_verdict_authority"] == "NONE"
    for forbidden in ("feasible", "verified", "design_pass"):
        mutated = deepcopy(result)
        mutated[forbidden] = True
        with pytest.raises(FrameF1Error, match="sai schema"):
            validate_frame_result(mutated)
