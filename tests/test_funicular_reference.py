from __future__ import annotations

import ast
import hashlib
import json
import math
from copy import deepcopy
from pathlib import Path

import pytest

import bridge_evolution.arch_action_f1 as arch_action
import bridge_evolution.creative_frame_adapter as adapter
import bridge_evolution.creative_shape as creative
import bridge_evolution.frame_f1 as frame_f1
import bridge_evolution.funicular_reference as funicular
from bridge_evolution.funicular_reference import (
    FunicularReferenceError,
    load_funicular_basis,
    run_funicular_reference,
    validate_funicular_reference,
)


EDGE_KINDS = (
    "ARCH_RIB",
    "DECK",
    "SPANDREL",
    "END_POST",
    "HANGER",
    "NETWORK_HANGER",
)


def _sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _genome(topology: str, coefficients: list[float] | None = None) -> dict:
    return {
        "topology": topology,
        "span_m": 145.0,
        "rise_ratio": 0.20,
        "panel_count": 12,
        "rib_count": 2,
        "rib_depth_m": 2.0,
        "deck_clearance_m": 6.5,
        "shape_coefficients": coefficients or [0.0, 0.0, 0.0],
    }


@pytest.fixture
def reference_environment(tmp_path, monkeypatch) -> dict:
    monkeypatch.setattr(creative, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(adapter, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(frame_f1, "REPO_ROOT", tmp_path)
    technical_bytes = b'{"purpose":"funicular-creative-test"}'
    structural_bytes = b'{"purpose":"funicular-structural-test"}'
    (tmp_path / "technical.json").write_bytes(technical_bytes)
    (tmp_path / "structural.json").write_bytes(structural_bytes)
    technical_sha = hashlib.sha256(technical_bytes).hexdigest()
    structural_sha = hashlib.sha256(structural_bytes).hexdigest()

    def threshold(value: float) -> dict:
        return {
            "value": value,
            "source_ref": "technical.json",
            "expected_source_sha256": technical_sha,
            "clause_id": "TEST-ONLY-F0",
        }

    return {
        "root": tmp_path,
        "structural_sha": structural_sha,
        "technical_profile": {
            "max_abs_slope": threshold(4.0),
            "min_curvature_radius_m": threshold(1.0),
            "max_member_length_m": threshold(200.0),
            "max_member_slenderness": threshold(500.0),
            "deck_member_depth_m": threshold(2.0),
            "spandrel_member_depth_m": threshold(1.0),
            "end_post_member_depth_m": threshold(1.0),
            "hanger_member_depth_m": threshold(0.5),
            "min_deck_arch_separation_m": threshold(0.5),
            "min_through_arch_clearance_m": threshold(0.5),
            "distributed_load_kN_m": threshold(25.0),
            "rib_area_m2": threshold(5.0),
            "allowable_compression_MPa": threshold(100.0),
        },
    }


def _structural_profile(environment: dict, candidate: dict) -> dict:
    digest = environment["structural_sha"]

    def material() -> dict:
        return {
            "elastic_modulus_GPa": 200.0,
            "source_ref": "structural.json",
            "expected_source_sha256": digest,
            "clause_id": "TEST-ONLY-E",
        }

    def section() -> dict:
        return {
            "area_m2": 5.0,
            "inertia_m4": 100.0,
            "source_ref": "structural.json",
            "expected_source_sha256": digest,
            "clause_id": "TEST-ONLY-A-I",
        }

    return {
        "schema_version": "1.0",
        "profile_id": "CFP-FUNICULAR-TEST",
        "candidate_id": candidate["candidate_id"],
        "candidate_profile_sha256": candidate["profile_sha256"],
        "support_policy": "LEFT_PIN_RIGHT_VERTICAL_ROLLER",
        "edge_properties": {
            kind: {"material": material(), "section": section()}
            for kind in EDGE_KINDS
        },
        "deck_line_load": {
            "q_kN_m": 25.0,
            "direction": "GLOBAL_NEGATIVE_Y",
            "source_ref": "structural.json",
            "expected_source_sha256": digest,
            "clause_id": "TEST-ONLY-Q",
        },
    }


def _parent_study(
    environment: dict,
    topology: str,
    coefficients: list[float] | None = None,
) -> dict:
    candidate = creative.evaluate_genome(
        _genome(topology, coefficients), environment["technical_profile"]
    )
    assert candidate["screening_status"] == "L0_PASSED"
    parent = adapter.analyze_creative_candidate(
        candidate,
        technical_profile=environment["technical_profile"],
        structural_profile=_structural_profile(environment, candidate),
    )
    assert parent["status"] == "CONVERGED"
    study = arch_action.run_arch_action_study(parent)
    assert study["status"] == "ACTION_DIAGNOSTIC_COMPLETE"
    return study


def _rehash_arch_study(study: dict) -> None:
    payload = deepcopy(study)
    payload.pop("study_sha256", None)
    study["study_sha256"] = _sha256(payload)


def _rehash_reference(output: dict) -> None:
    payload = deepcopy(output)
    payload.pop("reference_sha256", None)
    output["reference_sha256"] = _sha256(payload)


def test_canonical_parabola_has_zero_funicular_deviation_and_exact_closed_form(
    reference_environment,
):
    output = run_funicular_reference(_parent_study(reference_environment, "DECK_ARCH"))
    result = output["reference_result"]
    expected_h = 25.0 * 145.0**2 / (8.0 * 29.0)

    assert output["status"] == "REFERENCE_COMPLETE"
    assert result["horizontal_thrust_reference_kN"] == pytest.approx(expected_h)
    assert result["simple_beam_max_moment_kNm"] == pytest.approx(expected_h * 29.0)
    assert result["axis_rms_deviation_m"] == pytest.approx(0.0, abs=1e-12)
    assert result["axis_max_abs_deviation_m"] == pytest.approx(0.0, abs=1e-12)
    assert result["bending_proxy_max_abs_kNm"] == pytest.approx(0.0, abs=1e-9)
    assert result["canonical_funicular_within_tolerance"] is True
    validate_funicular_reference(output)


@pytest.mark.parametrize("topology", ["DECK_ARCH", "THROUGH_ARCH", "NETWORK_ARCH"])
def test_all_topologies_report_expected_measured_action_and_order_band(
    reference_environment, topology,
):
    output = run_funicular_reference(_parent_study(reference_environment, topology))
    comparison = output["reference_result"]["f1_comparison"]

    assert output["topology"] == topology
    assert comparison["agreement_status"] == "AGREEMENT_WITHIN_ORDER_BAND"
    assert comparison["reason_codes"] == []
    if topology == "DECK_ARCH":
        assert comparison["measured_action"] == "FOUNDATION_THRUST_MAGNITUDE"
        assert comparison["measured_force_min_kN"] == comparison["measured_force_max_kN"]
    else:
        assert comparison["measured_action"] == "DECK_TIE_TENSION_ENVELOPE"
        assert comparison["measured_force_min_kN"] > 0.0
        assert comparison["measured_force_max_kN"] >= comparison["measured_force_min_kN"]


def test_reference_shear_and_compression_follow_equilibrium_identities(reference_environment):
    output = run_funicular_reference(_parent_study(reference_environment, "THROUGH_ARCH"))
    result = output["reference_result"]
    samples = result["samples"]
    h_ref = result["horizontal_thrust_reference_kN"]
    total = output["reference_input"]["total_vertical_load_kN"]

    assert samples[0]["reference_shear_kN"] == pytest.approx(total / 2.0)
    assert samples[-1]["reference_shear_kN"] == pytest.approx(-total / 2.0)
    for sample in samples:
        expected = math.hypot(h_ref, sample["reference_shear_kN"])
        assert sample["reference_compression_kN"] == pytest.approx(expected)


@pytest.mark.parametrize("topology", ["DECK_ARCH", "THROUGH_ARCH", "NETWORK_ARCH"])
def test_asymmetric_axis_is_not_laundered_into_canonical_funicular(
    reference_environment, topology,
):
    output = run_funicular_reference(
        _parent_study(reference_environment, topology, [0.08, -0.08, 0.06])
    )
    result = output["reference_result"]

    assert result["canonical_funicular_within_tolerance"] is False
    assert result["axis_rms_deviation_ratio"] > 1e-4
    assert result["axis_max_abs_deviation_ratio"] > 1e-4
    assert result["bending_proxy_max_abs_ratio"] > 1e-4
    assert any(abs(sample["axis_deviation_m"]) > 1e-3 for sample in result["samples"])


def test_statics_kernel_has_no_direct_frame_solver_import_or_call():
    source = Path(funicular.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.extend(alias.name for alias in node.names)
    assert "frame_f1" not in imported
    assert "frame_f1." not in source
    derive_source = ast.get_source_segment(source, next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_derive_reference_result"
    ))
    assert derive_source is not None
    assert "study_result" not in derive_source
    assert "element_end_forces" not in derive_source


def test_reference_equations_do_not_change_when_measured_f1_force_changes(
    reference_environment,
):
    parent = _parent_study(reference_environment, "DECK_ARCH")
    basis = load_funicular_basis()
    reference_input = funicular._derive_reference_input(parent, basis)
    baseline = funicular._derive_reference_result(parent, reference_input, basis)
    mutated = deepcopy(parent)
    mutated["diagnostics"][0]["horizontal_thrust_magnitude_kN"] *= 2.0
    changed = funicular._derive_reference_result(mutated, reference_input, basis)

    for key in (
        "horizontal_thrust_reference_kN",
        "axis_rms_deviation_m",
        "axis_max_abs_deviation_m",
        "bending_proxy_max_abs_kNm",
        "samples",
    ):
        assert changed[key] == baseline[key]
    assert changed["f1_comparison"]["measured_force_min_kN"] == pytest.approx(
        2.0 * baseline["f1_comparison"]["measured_force_min_kN"]
    )


def test_reference_is_deterministic_and_manifest_preserves_lineage(reference_environment):
    parent = _parent_study(reference_environment, "NETWORK_ARCH")
    first = run_funicular_reference(parent)
    second = run_funicular_reference(parent)
    manifest = first["manifest"]

    assert first == second
    assert manifest["parent_study_id"] == parent["study_id"]
    assert manifest["parent_study_sha256"] == parent["study_sha256"]
    assert manifest["parent_analysis_sha256"] == parent["manifest"]["parent_analysis_sha256"]
    assert manifest["candidate_sha256"] == parent["manifest"]["candidate_sha256"]
    assert manifest["geometry_sha256"] == parent["manifest"]["geometry_sha256"]
    assert manifest["reference_input_sha256"] == _sha256(first["reference_input"])
    assert manifest["reference_result_sha256"] == _sha256(first["reference_result"])
    assert first["reference_source_sha256"] == _sha256(first["reference_source_digests"])


@pytest.mark.parametrize(
    "tamper, message",
    [
        ("horizontal_load", "Tải ngang"),
        ("nodal_distribution", "phân bố đều"),
        ("nodal_moment", "Mômen nút"),
        ("deck_length", "Mặt cầu"),
        ("load_case_count", "một load case"),
        ("load_direction", "GLOBAL_NEGATIVE_Y"),
    ],
)
def test_load_domain_is_fail_closed(reference_environment, tamper, message):
    parent = _parent_study(reference_environment, "DECK_ARCH")
    mutated = deepcopy(parent)
    if tamper == "horizontal_load":
        mutated["study_model"]["load_cases"][0]["nodal_loads"][0]["fx_kN"] = 1.0
    elif tamper == "nodal_distribution":
        mutated["study_model"]["load_cases"][0]["nodal_loads"][1]["fy_kN"] *= 1.1
    elif tamper == "nodal_moment":
        mutated["study_model"]["load_cases"][0]["nodal_loads"][0]["mz_kNm"] = 1.0
    elif tamper == "deck_length":
        mutated["parent_analysis"]["load_conservation"]["deck_length_m"] += 1.0
    elif tamper == "load_case_count":
        mutated["study_model"]["load_cases"].append(
            deepcopy(mutated["study_model"]["load_cases"][0])
        )
    else:
        mutated["parent_analysis"]["structural_profile"]["deck_line_load"]["direction"] = (
            "GLOBAL_POSITIVE_Y"
        )
    with pytest.raises(FunicularReferenceError, match=message):
        funicular._load_input(mutated, 145.0, 1e-12)


@pytest.mark.parametrize(
    "tamper, message",
    [
        ("flat", "Rise"),
        ("duplicate_x", "tăng nghiêm ngặt"),
        ("support_elevation", "không cùng cao độ"),
        ("left_endpoint", "chân trái"),
    ],
)
def test_geometry_domain_is_fail_closed(reference_environment, tamper, message):
    parent = _parent_study(reference_environment, "DECK_ARCH")
    mutated = deepcopy(parent)
    left, right = funicular._support_nodes(mutated)
    points = mutated["parent_analysis"]["candidate"]["axis_points"]
    if tamper == "flat":
        for point in points:
            point["y_m"] = 0.0
    elif tamper == "duplicate_x":
        points[2]["x_m"] = points[1]["x_m"]
    elif tamper == "support_elevation":
        right["y_m"] = 1.0
    else:
        points[0]["x_m"] += 1.0
    with pytest.raises(FunicularReferenceError, match=message):
        funicular._axis_points(mutated, left, right, 1e-12)


def test_zero_span_is_rejected_before_any_reference_formula(reference_environment):
    parent = _parent_study(reference_environment, "DECK_ARCH")
    support_nodes = [
        node
        for node in parent["parent_analysis"]["candidate"]["graph"]["nodes"]
        if node.get("support") is True
    ]
    support_nodes[1]["x_m"] = support_nodes[0]["x_m"]
    with pytest.raises(FunicularReferenceError, match="thứ tự trái-phải"):
        funicular._support_nodes(parent)


@pytest.mark.parametrize("tamper", ["status", "claim", "authority", "parent_geometry"])
def test_resealed_parent_tamper_is_blocked_before_reference_derivation(
    reference_environment, monkeypatch, tamper,
):
    parent = _parent_study(reference_environment, "THROUGH_ARCH")
    mutated = deepcopy(parent)
    if tamper == "status":
        mutated["status"] = "EXPECTED_ACTION_NOT_DETECTED"
    elif tamper == "claim":
        mutated["claim_level"] = "SCREENED"
    elif tamper == "authority":
        mutated["design_verdict_authority"] = "ADVISORY"
    else:
        mutated["parent_analysis"]["candidate"]["axis_points"][1]["y_m"] += 0.5
    _rehash_arch_study(mutated)
    called = False

    def forbidden(_parent, _basis):
        nonlocal called
        called = True
        raise AssertionError("reference input must not be derived")

    monkeypatch.setattr(funicular, "_derive_reference_input", forbidden)
    with pytest.raises(FunicularReferenceError, match="Parent BRD-042"):
        run_funicular_reference(mutated)
    assert not called


@pytest.mark.parametrize(
    "tamper",
    [
        "input_rise",
        "result_thrust",
        "result_deviation",
        "sample",
        "comparison",
        "manifest",
        "source_digest",
        "upstream_basis",
        "limitation",
        "topology",
        "parent_study",
    ],
)
def test_resealed_outer_hash_cannot_hide_output_tamper(reference_environment, tamper):
    output = run_funicular_reference(_parent_study(reference_environment, "DECK_ARCH"))
    if tamper == "input_rise":
        output["reference_input"]["rise_m"] += 1.0
    elif tamper == "result_thrust":
        output["reference_result"]["horizontal_thrust_reference_kN"] *= 2.0
    elif tamper == "result_deviation":
        output["reference_result"]["axis_rms_deviation_m"] = 0.5
    elif tamper == "sample":
        output["reference_result"]["samples"][2]["bending_proxy_kNm"] += 10.0
    elif tamper == "comparison":
        output["reference_result"]["f1_comparison"]["agreement_status"] = (
            "AGREEMENT_OUTSIDE_ORDER_BAND"
        )
    elif tamper == "manifest":
        output["manifest"]["reference_result_sha256"] = "0" * 64
    elif tamper == "source_digest":
        output["reference_source_digests"][0]["sha256"] = "0" * 64
    elif tamper == "upstream_basis":
        output["upstream_basis_hashes"]["frame_basis_sha256"] = "0" * 64
    elif tamper == "limitation":
        output["limitations"].pop()
    elif tamper == "topology":
        output["topology"] = "NETWORK_ARCH"
    else:
        output["parent_study"]["manifest"]["geometry_sha256"] = "0" * 64
    _rehash_reference(output)
    with pytest.raises(FunicularReferenceError):
        validate_funicular_reference(output)


@pytest.mark.parametrize(
    "location, forbidden",
    [
        ("root", "feasible"),
        ("root", "verified"),
        ("root", "design_pass"),
        ("root", "utilization"),
        ("result", "capacity_pass"),
        ("comparison", "safe"),
    ],
)
def test_schema_rejects_design_capacity_or_safety_backdoors(
    reference_environment, location, forbidden,
):
    output = run_funicular_reference(_parent_study(reference_environment, "NETWORK_ARCH"))
    if location == "root":
        output[forbidden] = True
    elif location == "result":
        output["reference_result"][forbidden] = True
    else:
        output["reference_result"]["f1_comparison"][forbidden] = True
    _rehash_reference(output)
    with pytest.raises(FunicularReferenceError, match="sai schema"):
        validate_funicular_reference(output)


def test_order_band_is_diagnostic_and_can_report_outside_without_design_verdict(
    reference_environment,
):
    parent = _parent_study(reference_environment, "DECK_ARCH")
    basis = load_funicular_basis()
    strict = deepcopy(basis)
    strict["order_of_magnitude_band"]["minimum_ratio"] = 0.95
    strict["order_of_magnitude_band"]["maximum_ratio"] = 1.0 / 0.95
    reference_input = funicular._derive_reference_input(parent, basis)
    h_ref = funicular._derive_reference_result(parent, reference_input, basis)[
        "horizontal_thrust_reference_kN"
    ]
    comparison = funicular._f1_comparison(parent, parent["diagnostics"][0], h_ref, strict)

    assert comparison["agreement_status"] == "AGREEMENT_OUTSIDE_ORDER_BAND"
    assert comparison["reason_codes"] == ["MEASURED_FORCE_OUTSIDE_HEURISTIC_ORDER_BAND"]
    assert "pass" not in " ".join(comparison).lower()
    assert "safe" not in " ".join(comparison).lower()


@pytest.mark.parametrize("tamper", ["formula", "load_domain", "order_band", "source_hash"])
def test_basis_is_fail_closed(tmp_path, monkeypatch, tamper):
    basis = json.loads(funicular._BASIS_PATH.read_text(encoding="utf-8"))
    if tamper == "formula":
        basis["formulae"]["horizontal_thrust"] = "H_ref=w*L^2/(4*f)"
    elif tamper == "load_domain":
        basis["load_domain"]["direction"] = "ANY"
    elif tamper == "order_band":
        basis["order_of_magnitude_band"]["minimum_ratio"] = 0.01
    else:
        basis["reference_source_sha256"] = "0" * 64
    path = tmp_path / f"basis-{tamper}.json"
    path.write_text(json.dumps(basis), encoding="utf-8")
    monkeypatch.setattr(funicular, "_BASIS_PATH", path)
    with pytest.raises(FunicularReferenceError):
        load_funicular_basis()


def test_runtime_source_drift_is_fail_closed(tmp_path, monkeypatch):
    drifted = tmp_path / "funicular_reference.py"
    drifted.write_bytes(Path(funicular.__file__).read_bytes() + b"\n# drift")
    monkeypatch.setattr(
        funicular,
        "_SOURCE_PATHS",
        (
            ("bridge_evolution/funicular_reference.py", drifted),
            ("bridge_evolution/arch_action_f1.py", Path(arch_action.__file__).resolve()),
        ),
    )
    with pytest.raises(FunicularReferenceError, match="reference_source_sha256"):
        load_funicular_basis()


def test_schema_closes_every_object_owned_by_funicular_module():
    schema = json.loads(funicular._SCHEMA_PATH.read_text(encoding="utf-8"))
    assert schema["additionalProperties"] is False
    for name in (
        "source_digest",
        "axis_point",
        "reference_input",
        "sample",
        "f1_comparison",
        "reference_result",
        "manifest",
        "upstream_basis_hashes",
    ):
        assert schema["$defs"][name]["additionalProperties"] is False
    assert schema["properties"]["claim_level"] == {"const": "IDEA"}
    assert schema["properties"]["design_verdict_authority"] == {"const": "NONE"}


def test_all_accepted_upstream_artifacts_remain_byte_identical_to_handoffs():
    handoffs = (
        "multiagent/handoffs/BRD-039.codex.r003.json",
        "multiagent/handoffs/BRD-040.codex.r003.json",
        "multiagent/handoffs/BRD-041.codex.r001.json",
        "multiagent/handoffs/BRD-042.codex.r001.json",
    )
    checked = 0
    for handoff_path in handoffs:
        handoff = json.loads((funicular.REPO_ROOT / handoff_path).read_text(encoding="utf-8"))
        for artifact in handoff["artifacts"]:
            observed = hashlib.sha256(
                (funicular.REPO_ROOT / artifact["path"]).read_bytes()
            ).hexdigest()
            assert observed == artifact["sha256"], artifact["path"]
            checked += 1
    assert checked == 18
