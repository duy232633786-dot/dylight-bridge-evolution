from __future__ import annotations

import hashlib
import json
from copy import deepcopy

import pytest

import bridge_evolution.arch_action_f1 as arch_action
import bridge_evolution.creative_frame_adapter as adapter
import bridge_evolution.creative_shape as creative
import bridge_evolution.frame_f1 as frame_f1
from bridge_evolution.arch_action_f1 import (
    ArchActionF1Error,
    load_arch_action_basis,
    run_arch_action_study,
    validate_arch_action_study,
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


def _genome(topology: str) -> dict:
    return {
        "topology": topology,
        "span_m": 145.0,
        "rise_ratio": 0.20,
        "panel_count": 12,
        "rib_count": 2,
        "rib_depth_m": 2.0,
        "deck_clearance_m": 6.5,
        "shape_coefficients": [0.0, 0.0, 0.0],
    }


@pytest.fixture
def study_environment(tmp_path, monkeypatch) -> dict:
    monkeypatch.setattr(creative, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(adapter, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(frame_f1, "REPO_ROOT", tmp_path)
    technical_bytes = b'{"purpose":"arch-action-creative-test"}'
    structural_bytes = b'{"purpose":"arch-action-structural-test"}'
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
        "profile_id": "CFP-ARCH-ACTION-TEST",
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


def _parent(environment: dict, topology: str) -> dict:
    candidate = creative.evaluate_genome(
        _genome(topology), environment["technical_profile"]
    )
    parent = adapter.analyze_creative_candidate(
        candidate,
        technical_profile=environment["technical_profile"],
        structural_profile=_structural_profile(environment, candidate),
    )
    assert parent["status"] == "CONVERGED"
    return parent


def _rehash_candidate(candidate: dict) -> None:
    candidate["geometry_sha256"] = _sha256({
        "axis_points": candidate["axis_points"],
        "graph": candidate["graph"],
    })
    payload = deepcopy(candidate)
    payload.pop("candidate_sha256", None)
    candidate["candidate_sha256"] = _sha256(payload)


def _rehash_parent(parent: dict) -> None:
    payload = deepcopy(parent)
    payload.pop("analysis_sha256", None)
    parent["analysis_sha256"] = _sha256(payload)


def _rehash_frame_result(result: dict) -> None:
    payload = deepcopy(result)
    payload.pop("result_sha256", None)
    result["result_sha256"] = _sha256(payload)


def _rehash_study(study: dict) -> None:
    payload = deepcopy(study)
    payload.pop("study_sha256", None)
    study["study_sha256"] = _sha256(payload)


def _horizontal_reaction_magnitude(frame_result: dict) -> float:
    case = frame_result["load_case_results"][0]
    return 0.5 * sum(abs(item["fx_kN"]) for item in case["reactions"])


def test_deck_arch_exposes_balanced_foundation_thrust(study_environment):
    parent = _parent(study_environment, "DECK_ARCH")
    study = run_arch_action_study(parent)
    diagnostic = study["diagnostics"][0]

    assert study["status"] == "ACTION_DIAGNOSTIC_COMPLETE"
    assert study["support_policy_id"] == "DECK_ARCH_BOTH_FEET_PINNED_TRANSLATION"
    assert study["study_model"]["supports"] == [
        {"node_id": "A0", "ux": True, "uy": True, "rz": False},
        {"node_id": "A12", "ux": True, "uy": True, "rz": False},
    ]
    assert diagnostic["action_status"] == "FOUNDATION_THRUST_DETECTED"
    assert diagnostic["horizontal_thrust_magnitude_kN"] > 1.0
    assert diagnostic["left_reaction"]["fx_kN"] == pytest.approx(
        -diagnostic["right_reaction"]["fx_kN"], rel=1e-10, abs=1e-8
    )
    assert diagnostic["arch_rib_axial_envelope"]["max_compression_kN"] > 1.0
    assert diagnostic["horizontal_equilibrium_residual_relative"] < 1e-10
    assert diagnostic["vertical_equilibrium_residual_relative"] < 1e-10
    assert _horizontal_reaction_magnitude(parent["frame_result"]) == pytest.approx(
        0.0, abs=1e-8
    )
    validate_arch_action_study(study)


@pytest.mark.parametrize("topology", ["THROUGH_ARCH", "NETWORK_ARCH"])
def test_tied_arch_exposes_internal_tie_action_and_releases_external_horizontal_reaction(
    study_environment, topology,
):
    parent = _parent(study_environment, topology)
    study = run_arch_action_study(parent)
    diagnostic = study["diagnostics"][0]

    assert study["status"] == "ACTION_DIAGNOSTIC_COMPLETE"
    assert study["support_policy_id"] == "TIED_ARCH_LEFT_PIN_RIGHT_VERTICAL_ROLLER"
    assert study["study_model"]["supports"] == parent["frame_model"]["supports"]
    assert diagnostic["action_status"] == "INTERNAL_TIE_ACTION_DETECTED"
    assert diagnostic["horizontal_thrust_magnitude_kN"] == pytest.approx(0.0, abs=1e-8)
    assert diagnostic["arch_rib_axial_envelope"]["max_compression_kN"] > 1.0
    assert diagnostic["deck_axial_envelope"]["max_tension_kN"] > 1.0
    assert diagnostic["reason_codes"] == []
    validate_arch_action_study(study)


@pytest.mark.parametrize("topology", ["DECK_ARCH", "THROUGH_ARCH", "NETWORK_ARCH"])
def test_study_changes_only_model_id_and_supports(study_environment, topology):
    parent = _parent(study_environment, topology)
    study = run_arch_action_study(parent)
    expected = deepcopy(parent["frame_model"])
    observed = deepcopy(study["study_model"])
    del expected["model_id"], expected["supports"]
    del observed["model_id"], observed["supports"]
    assert observed == expected


@pytest.mark.parametrize("topology", ["DECK_ARCH", "THROUGH_ARCH", "NETWORK_ARCH"])
def test_axial_sign_and_reaction_metrics_are_independently_reproducible(
    study_environment, topology,
):
    study = run_arch_action_study(_parent(study_environment, topology))
    diagnostic = study["diagnostics"][0]
    result_case = study["study_result"]["load_case_results"][0]
    edges = {
        edge["id"]: edge
        for edge in study["parent_analysis"]["candidate"]["graph"]["edges"]
    }
    for kind, field in (
        ("ARCH_RIB", "arch_rib_axial_envelope"),
        ("DECK", "deck_axial_envelope"),
    ):
        values = [
            0.5 * (force["axial_j_kN"] - force["axial_i_kN"])
            for force in result_case["element_end_forces"]
            if edges[force["element_id"]]["kind"] == kind
        ]
        envelope = diagnostic[field]
        assert envelope["min_signed_axial_kN"] == pytest.approx(min(values))
        assert envelope["max_signed_axial_kN"] == pytest.approx(max(values))
        assert envelope["max_compression_kN"] == pytest.approx(max(0.0, -min(values)))
        assert envelope["max_tension_kN"] == pytest.approx(max(0.0, max(values)))
    total_load = -sum(
        item["fy_kN"]
        for item in study["study_model"]["load_cases"][0]["nodal_loads"]
    )
    total_vertical_reaction = sum(
        item["fy_kN"] for item in result_case["reactions"]
    )
    assert total_vertical_reaction == pytest.approx(total_load, rel=1e-10)


def test_study_is_deterministic_and_manifest_preserves_full_lineage(study_environment):
    parent = _parent(study_environment, "DECK_ARCH")
    first = run_arch_action_study(parent)
    second = run_arch_action_study(parent)
    assert first == second
    manifest = first["manifest"]
    assert manifest["parent_analysis_sha256"] == parent["analysis_sha256"]
    assert manifest["candidate_sha256"] == parent["manifest"]["candidate_sha256"]
    assert manifest["geometry_sha256"] == parent["manifest"]["geometry_sha256"]
    assert manifest["candidate_profile_sha256"] == parent["manifest"]["candidate_profile_sha256"]
    assert manifest["structural_profile_sha256"] == parent["manifest"]["structural_profile_sha256"]
    assert manifest["study_model_sha256"] == first["study_result"]["model_sha256"]
    assert manifest["study_result_sha256"] == first["study_result"]["result_sha256"]
    assert manifest["study_source_sha256"] == _sha256(first["study_source_digests"])


def test_special_asymmetric_shapes_keep_a_continuous_expected_force_path(study_environment):
    coefficient_sets = (
        [0.08, -0.08, 0.06],
        [-0.08, 0.08, -0.06],
        [0.06, 0.06, -0.06],
    )
    for topology in ("DECK_ARCH", "THROUGH_ARCH", "NETWORK_ARCH"):
        for coefficients in coefficient_sets:
            genome = _genome(topology)
            genome["shape_coefficients"] = coefficients
            candidate = creative.evaluate_genome(
                genome, study_environment["technical_profile"]
            )
            assert candidate["screening_status"] == "L0_PASSED"
            parent = adapter.analyze_creative_candidate(
                candidate,
                technical_profile=study_environment["technical_profile"],
                structural_profile=_structural_profile(study_environment, candidate),
            )
            assert parent["status"] == "CONVERGED"
            study = run_arch_action_study(parent)
            assert study["status"] == "ACTION_DIAGNOSTIC_COMPLETE"
            assert study["diagnostics"][0]["reason_codes"] == []


@pytest.mark.parametrize("tamper", ["candidate", "manifest", "parent_model"])
def test_resealed_parent_tamper_is_blocked_before_model_derivation(
    study_environment, monkeypatch, tamper,
):
    parent = _parent(study_environment, "NETWORK_ARCH")
    mutated = deepcopy(parent)
    if tamper == "candidate":
        mutated["candidate"]["graph"]["nodes"][1]["y_m"] += 0.25
        _rehash_candidate(mutated["candidate"])
    elif tamper == "manifest":
        mutated["manifest"]["geometry_sha256"] = "0" * 64
    else:
        mutated["frame_model"]["supports"][1]["ux"] = True
    _rehash_parent(mutated)
    called = False

    def forbidden_derivation(_parent, _basis):
        nonlocal called
        called = True
        raise AssertionError("study model must not be derived")

    monkeypatch.setattr(arch_action, "_derive_model", forbidden_derivation)
    with pytest.raises(ArchActionF1Error, match="Parent BRD-041"):
        run_arch_action_study(mutated)
    assert not called


def test_parent_source_drift_is_blocked_before_model_derivation(
    study_environment, monkeypatch,
):
    parent = _parent(study_environment, "DECK_ARCH")
    (study_environment["root"] / "structural.json").write_bytes(b"drift")
    called = False

    def forbidden_derivation(_parent, _basis):
        nonlocal called
        called = True
        raise AssertionError("study model must not be derived")

    monkeypatch.setattr(arch_action, "_derive_model", forbidden_derivation)
    with pytest.raises(ArchActionF1Error, match="Parent BRD-041"):
        run_arch_action_study(parent)
    assert not called


@pytest.mark.parametrize(
    "tamper",
    [
        "manifest",
        "model_support",
        "result_reaction",
        "diagnostic_thrust",
        "topology",
        "basis_lineage",
        "source_digest",
        "limitation",
    ],
)
def test_resealed_outer_hash_cannot_hide_study_tamper(
    study_environment, tamper,
):
    study = run_arch_action_study(_parent(study_environment, "DECK_ARCH"))
    if tamper == "manifest":
        study["manifest"]["study_model_sha256"] = "0" * 64
    elif tamper == "model_support":
        study["study_model"]["supports"][1]["ux"] = False
    elif tamper == "result_reaction":
        study["study_result"]["load_case_results"][0]["reactions"][0]["fx_kN"] += 10.0
        _rehash_frame_result(study["study_result"])
    elif tamper == "diagnostic_thrust":
        study["diagnostics"][0]["horizontal_thrust_magnitude_kN"] = 0.0
    elif tamper == "topology":
        study["topology"] = "THROUGH_ARCH"
    elif tamper == "basis_lineage":
        study["upstream_basis_hashes"]["frame_basis_sha256"] = "0" * 64
    elif tamper == "source_digest":
        study["study_source_digests"][0]["sha256"] = "0" * 64
    else:
        study["limitations"].pop()
    _rehash_study(study)
    with pytest.raises(ArchActionF1Error):
        validate_arch_action_study(study)


@pytest.mark.parametrize("forbidden", ["feasible", "verified", "design_pass", "capacity_pass"])
def test_schema_rejects_design_or_capacity_verdict_backdoors(
    study_environment, forbidden,
):
    study = run_arch_action_study(_parent(study_environment, "THROUGH_ARCH"))
    study[forbidden] = True
    _rehash_study(study)
    with pytest.raises(ArchActionF1Error, match="sai schema"):
        validate_arch_action_study(study)


def test_classifier_cannot_hide_missing_deck_arch_thrust(study_environment):
    parent = _parent(study_environment, "DECK_ARCH")
    basis = load_arch_action_basis()
    model, policy_id = arch_action._derive_model(parent, basis)
    result = frame_f1.analyze_frame_model(model)
    for reaction in result["load_case_results"][0]["reactions"]:
        reaction["fx_kN"] = 0.0
    diagnostics, status = arch_action._diagnostics(parent, model, result, basis, policy_id)
    assert status == "EXPECTED_ACTION_NOT_DETECTED"
    assert diagnostics[0]["action_status"] == "EXPECTED_ACTION_NOT_DETECTED"
    assert "FOUNDATION_HORIZONTAL_THRUST_NOT_DETECTED" in diagnostics[0]["reason_codes"]


def test_classifier_cannot_hide_missing_tie_tension(study_environment):
    parent = _parent(study_environment, "NETWORK_ARCH")
    basis = load_arch_action_basis()
    model, policy_id = arch_action._derive_model(parent, basis)
    result = frame_f1.analyze_frame_model(model)
    edge_kind = {
        edge["id"]: edge["kind"] for edge in parent["candidate"]["graph"]["edges"]
    }
    changed_one = False
    for force in result["load_case_results"][0]["element_end_forces"]:
        if edge_kind[force["element_id"]] == "DECK":
            if not changed_one:
                force["axial_i_kN"] = 1.0
                force["axial_j_kN"] = -1.0
                changed_one = True
    diagnostics, status = arch_action._diagnostics(parent, model, result, basis, policy_id)
    assert status == "EXPECTED_ACTION_NOT_DETECTED"
    assert "DECK_TIE_NOT_IN_TENSION_THROUGHOUT" in diagnostics[0]["reason_codes"]


def test_classifier_requires_compression_throughout_the_arch_rib(study_environment):
    parent = _parent(study_environment, "DECK_ARCH")
    basis = load_arch_action_basis()
    model, policy_id = arch_action._derive_model(parent, basis)
    result = frame_f1.analyze_frame_model(model)
    edge_kind = {
        edge["id"]: edge["kind"] for edge in parent["candidate"]["graph"]["edges"]
    }
    for force in result["load_case_results"][0]["element_end_forces"]:
        if edge_kind[force["element_id"]] == "ARCH_RIB":
            force["axial_i_kN"] = -1.0
            force["axial_j_kN"] = 1.0
            break
    diagnostics, status = arch_action._diagnostics(parent, model, result, basis, policy_id)
    assert status == "EXPECTED_ACTION_NOT_DETECTED"
    assert "ARCH_RIB_NOT_IN_COMPRESSION_THROUGHOUT" in diagnostics[0]["reason_codes"]


def test_nonconverged_derived_case_is_explicitly_not_evaluable(study_environment):
    parent = _parent(study_environment, "THROUGH_ARCH")
    basis = load_arch_action_basis()
    model, policy_id = arch_action._derive_model(parent, basis)
    result = frame_f1.analyze_frame_model(model)
    result["status"] = "MODEL_LIMIT_EXCEEDED"
    result["load_case_results"][0]["status"] = "MODEL_LIMIT_EXCEEDED"
    diagnostics, status = arch_action._diagnostics(parent, model, result, basis, policy_id)
    assert status == "NOT_EVALUABLE"
    assert diagnostics[0]["action_status"] == "NOT_EVALUABLE"
    assert diagnostics[0]["horizontal_thrust_magnitude_kN"] is None


@pytest.mark.parametrize("tamper", ["support", "expected_action", "source_hash"])
def test_basis_is_fail_closed(study_environment, tmp_path, monkeypatch, tamper):
    basis = json.loads(arch_action._BASIS_PATH.read_text(encoding="utf-8"))
    if tamper == "support":
        basis["support_policy_by_topology"]["DECK_ARCH"]["right"]["ux"] = False
    elif tamper == "expected_action":
        basis["expected_action_by_topology"]["DECK_ARCH"] = "INTERNAL_TIE_ACTION"
    else:
        basis["study_source_sha256"] = "0" * 64
    path = tmp_path / f"basis-{tamper}.json"
    path.write_text(json.dumps(basis), encoding="utf-8")
    monkeypatch.setattr(arch_action, "_BASIS_PATH", path)
    with pytest.raises(ArchActionF1Error):
        load_arch_action_basis()
