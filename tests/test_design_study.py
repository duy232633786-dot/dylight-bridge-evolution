"""BRD-038 — tìm kiếm mạnh hơn nhưng fail-closed ngoài miền mô hình."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import pytest

import bridge_evolution.design_study as design_study_module
import bridge_evolution.evaluate as evaluate_module
from bridge_evolution import __version__
from bridge_evolution.design_study import (
    ApplicabilityRegistryError,
    assess_candidate,
    check_model_applicability,
    load_applicability_registry,
    robust_pareto,
    stratified_genes,
    stratified_multifamily,
)
from bridge_evolution.fe_adapter import SOLVER_VERSION as BUILTIN_L1_SOLVER_VERSION
from bridge_evolution.geometry import check_geometry
from bridge_evolution.state import input_hash, make_case_id, state_from_gene


REPO_ROOT = Path(__file__).resolve().parents[1]
_TEST_SOURCE_PATH = Path(__file__).resolve()


def _gene(family: str) -> dict:
    genes = {
        "i_girder_parametric_v1": {
            "girder_catalog_id": "I-PARAM",
            "girder_count": 5,
            "girder_spacing_mm": 2400,
            "deck_slab_thickness_mm": 200,
            "girder_concrete_id": "C50",
            "deck_concrete_id": "C35",
            "diaphragm_layout_id": "DG-5",
            "prestress_layout_id": "PT-42",
            "girder_depth_mm": 1800,
            "top_flange_width_mm": 1000,
            "top_flange_thickness_mm": 180,
            "web_thickness_mm": 200,
            "bottom_flange_width_mm": 650,
            "bottom_flange_thickness_mm": 300,
        },
        "box_girder_parametric_v1": {
            "girder_catalog_id": "BOX-PARAM",
            "girder_count": 1,
            "girder_spacing_mm": 12000,
            "deck_slab_thickness_mm": 250,
            "girder_concrete_id": "C50",
            "deck_concrete_id": "C35",
            "diaphragm_layout_id": "DG-5",
            "prestress_layout_id": "PT-42",
            "box_web_height_mm": 2400,
            "box_bottom_width_mm": 6500,
            "box_bottom_slab_mm": 250,
            "box_web_thickness_mm": 450,
        },
        "composite_i_girder_parametric_v1": {
            "girder_catalog_id": "CI-PARAM",
            "girder_count": 5,
            "girder_spacing_mm": 2400,
            "deck_slab_thickness_mm": 250,
            "girder_concrete_id": "C40",
            "deck_concrete_id": "C35",
            "diaphragm_layout_id": "DG-5",
            "prestress_layout_id": "PT-34",
            "steel_depth_mm": 2000,
            "steel_top_flange_width_mm": 500,
            "steel_top_flange_thickness_mm": 30,
            "steel_web_thickness_mm": 20,
            "steel_bottom_flange_width_mm": 700,
            "steel_bottom_flange_thickness_mm": 50,
        },
    }
    return dict(genes[family])


def _state(family: str) -> dict:
    return state_from_gene(_gene(family), grammar_id=family)


def _source_ref(locator: str) -> str:
    digest = hashlib.sha256(_TEST_SOURCE_PATH.read_bytes()).hexdigest()
    return (
        f"tests/test_design_study.py#sha256={digest}&locator={locator}"
    )


def _known(value, locator: str):
    return {
        "status": "KNOWN",
        "value": value,
        "source_ref": _source_ref(locator),
    }


def _complete_site() -> dict:
    return {
        "site_id": "TEST-SITE",
        "site_status": "SPECIFIED",
        "site_status_note": "Hồ sơ tổng hợp dùng để kiểm thử contract.",
        "schema_version": "1.2",
        "coordinate_reference_system": {
            "horizontal_crs": _known("EPSG:3405", "crs/horizontal"),
            "vertical_datum": _known("HONDAU", "crs/vertical"),
        },
        "hydrology_scour": {
            "design_flood_frequency_years": _known(100, "hydro/frequency"),
            "design_water_level_m": _known(8.0, "hydro/water-level"),
            "estimated_scour_depth_m": _known(2.0, "hydro/scour"),
            "tidal_range_m": _known(0.5, "hydro/tidal-range"),
            "navigation_clearance": _known("NOT_REQUIRED", "hydro/navigation"),
        },
        "seismic_hazard": {
            "pga_g": _known(0.12, "seismic/pga"),
            "site_class": _known("D_STIFF_SOIL", "seismic/site-class"),
            "seismic_performance_zone": _known(2, "seismic/zone"),
        },
        "wind_hazard": {
            "basic_wind_speed_m_s": _known(45.0, "wind/basic-speed"),
            "gust_effect_factor": _known(1.1, "wind/gust-factor"),
            "aerodynamic_risk_level": _known("LOW", "wind/aero-risk"),
        },
        "geographic_location": {
            "latitude": _known(21.0, "location/latitude"),
            "longitude": _known(105.8, "location/longitude"),
            "terrain_category": _known("B_SUBURBAN", "location/terrain"),
        },
        "geotechnical_category": _known("DEEP_ALLUVIAL", "geo/category"),
        "geotechnical_investigation": {
            "investigation_status": "COMPLETE",
            "report_ref": _source_ref("geo/investigation-report"),
        },
        "corrosion_exposure": _known("COASTAL_SPRAY", "durability/exposure"),
        "g0_gate": {
            "gate": "G0",
            "status": "PASSED",
            "assessed_by": "test engineer",
            "blocking_items": [],
        },
        "document_provenance": {
            "task_id": "TEST",
            "prepared_by": "test fixture",
            "review_status": "ENGINEER_APPROVED",
            "claim_ceiling": "SCREENED",
        },
    }


def _verified_registry(tmp_path: Path, monkeypatch, *families: str) -> dict:
    registry = json.loads(json.dumps(load_applicability_registry()))
    selected = families or ("i_girder_parametric_v1",)
    for family in selected:
        registry["families"][family]["domain_evidence"]["status"] = "VERIFIED"
        registry["families"][family]["domain_evidence"]["note"] = (
            "Test-only verified fixture; không phải design-basis của dự án."
        )
    path = tmp_path / "verified-model-applicability.json"
    path.write_text(
        json.dumps(registry, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    monkeypatch.setattr(design_study_module, "_DEFAULT_REGISTRY", path)
    monkeypatch.setattr(design_study_module, "_APPROVED_REGISTRY_SHA256", digest)
    return registry


def _valid_evaluation(state: dict, *, utilization: float = 0.8) -> dict:
    return {
        "case_id": make_case_id(state),
        "status": "SUCCESS",
        "feasible": True,
        "solver": {
            "status": "CONVERGED",
            "name": "BUILTIN_L1",
            "runtime_ms": 1.0,
        },
        "violations": [],
        "objectives": {
            "relative_cost": 100.0,
            "material_mass_t": 200.0,
            "embodied_carbon_kgCO2e": 300.0,
        },
        "responses": {"max_utilization": utilization},
        "provenance": {
            "input_hash": input_hash(state),
            "ruleset_version": "test-rules/1.0",
            "solver_version": f"{BUILTIN_L1_SOLVER_VERSION} (pkg {__version__})",
            "catalogs_version": "test-catalogs/1.0",
        },
    }


def test_registry_is_schema_valid_and_semantically_ordered(tmp_path):
    registry = load_applicability_registry()
    assert registry["claim_ceiling"] == "SCREENED"
    assert set(registry["families"]) >= {
        "super_t_parametric_v2", "i_girder_parametric_v1",
        "box_girder_parametric_v1", "composite_i_girder_parametric_v1",
    }

    bad = json.loads(json.dumps(registry))
    bad["families"]["i_girder_parametric_v1"]["domain"]["span_m"] = {
        "min": 80, "max": 10,
    }
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(ApplicabilityRegistryError, match="span_m min > max"):
        load_applicability_registry(path)


def test_stratified_sampling_is_deterministic_balanced_and_multifamily_round_robin():
    a = stratified_genes("i_girder_parametric_v1", 12, seed=41)
    b = stratified_genes("i_girder_parametric_v1", 12, seed=41)
    c = stratified_genes("i_girder_parametric_v1", 12, seed=42)
    assert a == b
    assert a != c
    assert len(a) == 12
    registry = load_applicability_registry()
    assert a[0] == registry["families"]["i_girder_parametric_v1"]["anchor_gene"]
    assert len({row["girder_depth_mm"] for row in a}) >= 11
    # Miền 3 giá trị phải được phủ gần cân bằng, kể cả anchor bắt buộc.
    counts = {n: sum(row["girder_count"] == n for row in a) for n in (4, 5, 6)}
    assert max(counts.values()) - min(counts.values()) <= 1

    families = ["i_girder_parametric_v1", "box_girder_parametric_v1"]
    proposals = stratified_multifamily(families, 3, seed=7)
    assert [p["family"] for p in proposals] == families * 3
    assert [p["sample_index"] for p in proposals] == [0, 0, 1, 1, 2, 2]


def test_box_l1_is_blocked_before_evaluator_and_l0_is_allowed():
    calls = []

    def evaluator(state):
        calls.append(state)
        raise AssertionError("evaluator không được gọi")

    state = _state("box_girder_parametric_v1")
    blocked = assess_candidate(
        state, study_level="L1_STRUCTURAL", site_profile=_complete_site(),
        evaluator=evaluator,
    )
    assert blocked["status"] == "BLOCKED"
    assert {b["code"] for b in blocked["blockers"]} >= {"APP-LEVEL-001", "APP-SOLVER-001"}
    assert calls == []

    l0 = assess_candidate(state, study_level="L0_GEOMETRY", evaluator=evaluator)
    assert l0["status"] == "L0_SCREENED"
    assert l0["claim_level"] == "IDEA"
    assert calls == []


def test_composite_geometry_can_be_studied_but_builtin_l1_never_runs():
    calls = []

    def evaluator(state):
        calls.append(state)
        raise AssertionError("evaluator không được gọi")

    state = _state("composite_i_girder_parametric_v1")
    l0 = assess_candidate(state, study_level="L0_GEOMETRY", evaluator=evaluator)
    assert l0["status"] == "L0_SCREENED"
    assert {item["code"] for item in l0["deferred_blockers"]} == {
        "SOLVER-COMPOSITE-001",
    }
    l1 = assess_candidate(
        state, study_level="L1_STRUCTURAL", site_profile=_complete_site(),
        evaluator=evaluator,
    )
    assert l1["status"] == "BLOCKED"
    assert any(b["code"] == "SOLVER-COMPOSITE-001" for b in l1["blockers"])
    assert calls == []


def test_skew_span_and_distribution_domain_fail_closed():
    state = _state("i_girder_parametric_v1")
    violations, geom = check_geometry(state)
    assert not [v for v in violations if v["severity"] == "HARD"]

    skewed = json.loads(json.dumps(state))
    skewed["project_inputs"]["skew_deg"] = 10
    blockers = check_model_applicability(
        skewed, geom, study_level="L1_STRUCTURAL", site_profile=_complete_site())
    assert "APP-SKEW-001" in {b["code"] for b in blockers}

    long_span = json.loads(json.dumps(state))
    long_span["project_inputs"]["span_length_m"] = 90
    blockers = check_model_applicability(
        long_span, geom, study_level="L1_STRUCTURAL", site_profile=_complete_site())
    assert "APP-SPAN-001" in {b["code"] for b in blockers}

    outside = json.loads(json.dumps(geom))
    outside["spacing_m"] = 6.0
    blockers = check_model_applicability(
        state, outside, study_level="L1_STRUCTURAL", site_profile=_complete_site())
    assert any(b["code"] == "APP-DF-001" and b["field"] == "distribution/spacing_mm"
               for b in blockers)

    nan_skew = json.loads(json.dumps(state))
    nan_skew["project_inputs"]["skew_deg"] = float("nan")
    blockers = check_model_applicability(
        nan_skew, geom, study_level="L1_STRUCTURAL", site_profile=_complete_site())
    assert "APP-SKEW-001" in {b["code"] for b in blockers}

    for field in ("girder_count", "spacing_m", "slab_thickness_m"):
        nan_geom = json.loads(json.dumps(geom))
        nan_geom[field] = float("nan")
        blockers = check_model_applicability(
            state, nan_geom, study_level="L1_STRUCTURAL",
            site_profile=_complete_site(),
        )
        assert any(
            b["code"] == "APP-DF-001"
            and math.isnan(float(b["value"]))
            for b in blockers
        )

    nan_stiffness = json.loads(json.dumps(geom))
    nan_stiffness["section"]["I_m4"] = float("nan")
    blockers = check_model_applicability(
        state, nan_stiffness, study_level="L1_STRUCTURAL",
        site_profile=_complete_site(),
    )
    assert any(
        b["code"] == "APP-DF-001"
        and b["field"] == "distribution/kg_mm4"
        and math.isnan(float(b["value"]))
        for b in blockers
    )


def test_l0_applicability_block_preserves_deferred_solver_diagnostic(
    tmp_path, monkeypatch,
):
    registry = json.loads(json.dumps(load_applicability_registry()))
    family = "composite_i_girder_parametric_v1"
    registry["families"][family]["domain"]["span_m"] = {
        "min": 10.0, "max": 20.0,
    }
    path = tmp_path / "l0-blocked-registry.json"
    path.write_text(
        json.dumps(registry, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(design_study_module, "_DEFAULT_REGISTRY", path)
    monkeypatch.setattr(
        design_study_module, "_APPROVED_REGISTRY_SHA256",
        hashlib.sha256(path.read_bytes()).hexdigest(),
    )

    result = assess_candidate(
        _state(family), study_level="L0_GEOMETRY",
    )
    assert result["status"] == "BLOCKED"
    assert "APP-SPAN-001" in {item["code"] for item in result["blockers"]}
    assert {item["code"] for item in result["deferred_blockers"]} == {
        "SOLVER-COMPOSITE-001",
    }


def test_missing_site_blocks_before_evaluator_but_complete_site_can_promote(
    tmp_path, monkeypatch,
):
    state = _state("i_girder_parametric_v1")
    calls = []

    def evaluator(candidate):
        calls.append(candidate)
        return _valid_evaluation(candidate)

    monkeypatch.setattr(evaluate_module, "evaluate_candidate", evaluator)

    missing = assess_candidate(state, site_profile=None)
    assert missing["status"] == "BLOCKED"
    assert "SITE-001" in {b["code"] for b in missing["blockers"]}
    assert calls == []

    _verified_registry(tmp_path, monkeypatch)
    passed = assess_candidate(state, site_profile=_complete_site())
    assert passed["status"] == "SCREENED"
    assert passed["claim_level"] == "SCREENED"
    assert len(calls) == 1
    assert set(passed["authority_schema_sha256"]) == {
        "model_applicability", "evaluation_result", "site_hazard_profile",
    }
    assert all(
        len(digest) == 64
        for digest in passed["authority_schema_sha256"].values()
    )


def test_site_known_labels_do_not_pass_without_real_sources_and_engineer_gate():
    state = _state("i_girder_parametric_v1")
    _, geom = check_geometry(state)

    missing_source = _complete_site()
    missing_source["wind_hazard"]["basic_wind_speed_m_s"]["source_ref"] = \
        "research/nonexistent-wind-report.pdf#sha256=" + "0" * 64 + \
        "&locator=wind/basic-speed"
    blockers = check_model_applicability(
        state, geom, study_level="L1_STRUCTURAL", site_profile=missing_source)
    assert "SITE-SOURCE-001" in {b["code"] for b in blockers}

    unreviewed = _complete_site()
    unreviewed["document_provenance"]["review_status"] = "AGENT_REVIEWED"
    unreviewed["g0_gate"] = {
        "gate": "G0",
        "status": "BLOCKED",
        "assessed_by": "agent",
        "blocking_items": ["Chưa có kiểm tra độc lập"],
    }
    blockers = check_model_applicability(
        state, geom, study_level="L1_STRUCTURAL", site_profile=unreviewed)
    assert {"SITE-G0-001", "SITE-REVIEW-001"} <= {b["code"] for b in blockers}


def test_default_numeric_domain_evidence_blocks_l1_before_evaluator():
    calls = []
    result = assess_candidate(
        _state("i_girder_parametric_v1"),
        site_profile=_complete_site(),
        evaluator=lambda state: calls.append(state),
    )
    assert result["status"] == "BLOCKED"
    assert "APP-EVIDENCE-001" in {item["code"] for item in result["blockers"]}
    assert calls == []


def test_tampered_default_registry_is_refused_even_when_schema_valid(
    tmp_path, monkeypatch,
):
    registry = json.loads(json.dumps(load_applicability_registry()))
    registry["families"]["i_girder_parametric_v1"]["domain"]["span_m"]["max"] = 999
    path = tmp_path / "tampered.json"
    path.write_text(json.dumps(registry), encoding="utf-8")
    monkeypatch.setattr(design_study_module, "_DEFAULT_REGISTRY", path)

    with pytest.raises(ApplicabilityRegistryError, match="drift khỏi snapshot"):
        assess_candidate(
            _state("i_girder_parametric_v1"),
            site_profile=_complete_site(),
            evaluator=lambda state: _valid_evaluation(state),
        )


def test_fake_or_mismatched_evaluator_cannot_issue_screened(tmp_path, monkeypatch):
    _verified_registry(tmp_path, monkeypatch)
    state = _state("i_girder_parametric_v1")

    fake = assess_candidate(
        state,
        site_profile=_complete_site(),
        evaluator=lambda candidate: {"status": "SUCCESS", "feasible": True},
    )
    assert fake["status"] == "BLOCKED"
    assert {item["code"] for item in fake["blockers"]} == {
        "EVALUATOR-CONTRACT-001",
    }

    thin = _valid_evaluation(state)
    thin.pop("objectives")
    thin.pop("responses")
    schema_valid_but_empty = assess_candidate(
        state,
        site_profile=_complete_site(),
        evaluator=lambda candidate: thin,
    )
    assert schema_valid_but_empty["status"] == "BLOCKED"
    assert "thiếu objectives" in schema_valid_but_empty["blockers"][0]["message"]

    wrong = _valid_evaluation(state)
    wrong["case_id"] = "BT-0000000000000000"
    wrong["provenance"]["input_hash"] = "0" * 64
    mismatched = assess_candidate(
        state,
        site_profile=_complete_site(),
        evaluator=lambda candidate: wrong,
    )
    assert mismatched["status"] == "BLOCKED"
    assert "case_id" in mismatched["blockers"][0]["message"]
    assert "input_hash" in mismatched["blockers"][0]["message"]

    valid_but_untrusted = assess_candidate(
        state,
        site_profile=_complete_site(),
        evaluator=lambda candidate: _valid_evaluation(candidate),
    )
    assert valid_but_untrusted["status"] == "BLOCKED"
    assert {item["code"] for item in valid_but_untrusted["blockers"]} == {
        "EVALUATOR-AUTHORITY-001",
    }

    forged_solver = _valid_evaluation(state)
    forged_solver["solver"]["name"] = "MIDAS_CIVIL"
    forged_solver["provenance"]["solver_version"] = "forged/9.9"
    monkeypatch.setattr(
        evaluate_module, "evaluate_candidate", lambda candidate: forged_solver,
    )
    solver_mismatch = assess_candidate(state, site_profile=_complete_site())
    assert solver_mismatch["status"] == "BLOCKED"
    message = solver_mismatch["blockers"][0]["message"]
    assert "solver/name" in message
    assert "solver_version" in message


def test_authority_schema_drift_blocks_before_evaluator(tmp_path, monkeypatch):
    drifted = tmp_path / "evaluation_result.schema.json"
    drifted.write_bytes(
        (REPO_ROOT / "contracts" / "evaluation_result.schema.json").read_bytes()
        + b"\n"
    )
    pins = dict(design_study_module._AUTHORITY_SCHEMA_PINS)
    _path, expected, code = pins["evaluation_result"]
    pins["evaluation_result"] = (drifted, expected, code)
    monkeypatch.setattr(design_study_module, "_AUTHORITY_SCHEMA_PINS", pins)

    result = assess_candidate(_state("i_girder_parametric_v1"))
    assert result["status"] == "BLOCKED"
    assert result["blockers"][0]["code"] == "EVALUATOR-CONTRACT-000"
    assert "đã drift" in result["blockers"][0]["message"]


def test_default_evaluator_preserves_soft_findings_as_advisories(tmp_path, monkeypatch):
    _verified_registry(tmp_path, monkeypatch)
    state = _state("i_girder_parametric_v1")
    evaluation = _valid_evaluation(state)
    evaluation["violations"] = [{
        "rule_id": "SERV-ADVISORY-001",
        "severity": "SOFT",
        "message": "Theo dõi thêm trong bước sau",
        "margin": -0.1,
    }]
    monkeypatch.setattr(
        evaluate_module, "evaluate_candidate", lambda candidate: evaluation,
    )

    result = assess_candidate(state, site_profile=_complete_site())
    assert result["status"] == "SCREENED"
    assert result["blockers"] == []
    assert result["advisories"] == [{
        "code": "SERV-ADVISORY-001",
        "severity": "SOFT",
        "message": "Theo dõi thêm trong bước sau",
        "margin": -0.1,
    }]


@pytest.mark.parametrize(
    ("mutate", "expected_path"),
    [
        (lambda evaluation: evaluation["solver"].__setitem__(
            "runtime_ms", float("inf")), "$/solver/runtime_ms"),
        (lambda evaluation: evaluation.__setitem__("violations", [{
            "rule_id": "SERV-NAN-001",
            "severity": "SOFT",
            "message": "Không được lọt NaN vào advisory",
            "margin": float("nan"),
        }]), "$/violations/0/margin"),
    ],
)
def test_default_evaluator_rejects_nonfinite_json_numbers(
    tmp_path, monkeypatch, mutate, expected_path,
):
    _verified_registry(tmp_path, monkeypatch)
    state = _state("i_girder_parametric_v1")
    evaluation = _valid_evaluation(state)
    mutate(evaluation)
    monkeypatch.setattr(
        evaluate_module, "evaluate_candidate", lambda candidate: evaluation,
    )

    result = assess_candidate(state, site_profile=_complete_site())
    assert result["status"] == "BLOCKED"
    assert result["claim_level"] == "IDEA"
    assert result["blockers"][0]["code"] == "EVALUATOR-CONTRACT-001"
    assert expected_path in result["blockers"][0]["message"]
    assert result["evaluation"] is None
    json.dumps(result, allow_nan=False)


def test_default_evaluator_does_not_echo_cyclic_invalid_result(
    tmp_path, monkeypatch,
):
    _verified_registry(tmp_path, monkeypatch)
    state = _state("i_girder_parametric_v1")
    evaluation = _valid_evaluation(state)
    evaluation["cycle"] = evaluation
    monkeypatch.setattr(
        evaluate_module, "evaluate_candidate", lambda candidate: evaluation,
    )

    result = assess_candidate(state, site_profile=_complete_site())
    assert result["status"] == "BLOCKED"
    assert result["evaluation"] is None
    assert "chu trình" in result["blockers"][0]["message"]
    json.dumps(result, allow_nan=False)


def test_real_default_evaluator_matches_pinned_solver_identity(tmp_path, monkeypatch):
    _verified_registry(tmp_path, monkeypatch)
    state = _state("i_girder_parametric_v1")

    result = assess_candidate(state, site_profile=_complete_site())
    assert result["status"] in {"SCREENED", "REJECTED"}
    assert result["evaluation"] is not None
    assert result["evaluation"]["solver"]["name"] == "BUILTIN_L1"
    assert result["evaluation"]["provenance"]["solver_version"] == (
        f"{BUILTIN_L1_SOLVER_VERSION} (pkg {__version__})"
    )
    assert not {
        "EVALUATOR-CONTRACT-000", "EVALUATOR-CONTRACT-001",
        "EVALUATOR-AUTHORITY-001",
    } & {item["code"] for item in result["blockers"]}


def test_non_json_serializable_state_returns_uniform_rejection():
    result = assess_candidate({"family": {"not", "json"}})
    assert result["status"] == "REJECTED"
    assert result["claim_level"] == "IDEA"
    assert result["case_id"] is None
    assert result["family"] is None
    assert result["blockers"][0]["code"] == "SCHEMA-001"
    json.dumps(result)


def test_canonical_unspecified_site_blocks_the_real_project_before_evaluator():
    site_path = Path(__file__).resolve().parents[1] / "docs" / "design_basis" / "SITE-UNSPECIFIED.json"
    site = json.loads(site_path.read_text(encoding="utf-8"))
    calls = []

    def evaluator(candidate):
        calls.append(candidate)
        raise AssertionError("site G0 BLOCKED không được mở evaluator")

    result = assess_candidate(
        _state("i_girder_parametric_v1"), site_profile=site, evaluator=evaluator)
    assert result["status"] == "BLOCKED"
    codes = {b["code"] for b in result["blockers"]}
    assert {"SITE-STATUS-001", "SITE-G0-001", "SITE-REVIEW-001", "SITE-001"} <= codes
    assert calls == []


def test_malformed_site_fails_closed_without_crashing_or_calling_evaluator():
    calls = []
    result = assess_candidate(
        _state("i_girder_parametric_v1"),
        site_profile={"site_id": "BROKEN"},
        evaluator=lambda state: calls.append(state),
    )
    assert result["status"] == "BLOCKED"
    assert "SITE-SCHEMA-001" in {b["code"] for b in result["blockers"]}
    assert calls == []


def _sample(cost, mass, carbon, utilization):
    identity = f"{cost}|{mass}|{carbon}|{utilization}"
    seed = int(hashlib.sha256(identity.encode("utf-8")).hexdigest()[:12], 16)
    perturbation = {
        "seed": seed,
        "variables": {
            "cost_factor": float(cost),
            "mass_factor": float(mass),
            "carbon_factor": float(carbon),
            "utilization_factor": float(utilization),
        },
    }
    digest = hashlib.sha256(json.dumps(
        perturbation, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")).hexdigest()
    return {
        "sample_id": "S-" + digest[:16],
        "seed": seed,
        "perturbation": perturbation,
        "input_digest": digest,
        "objectives": {
            "relative_cost": cost,
            "material_mass_t": mass,
            "embodied_carbon_kgCO2e": carbon,
        },
        "max_utilization": utilization,
    }


def test_robust_pareto_uses_ucb_worst_case_and_blocks_weak_evidence():
    studies = [
        {"case_id": "A", "status": "SCREENED", "samples": [
            _sample(100, 100, 100, 0.80),
            _sample(102, 101, 103, 0.85),
            _sample(98, 99, 97, 0.90),
        ]},
        {"case_id": "B", "status": "SCREENED", "samples": [
            _sample(110, 88, 90, 0.82),
            _sample(112, 90, 92, 0.84),
            _sample(108, 92, 88, 0.86),
        ]},
        {"case_id": "C", "status": "SCREENED", "samples": [
            _sample(130, 130, 130, 0.70),
            _sample(132, 132, 132, 0.72),
            _sample(128, 128, 128, 0.74),
        ]},
        {"case_id": "D", "status": "SCREENED", "samples": [
            _sample(80, 80, 80, 0.60),
        ]},
        {"case_id": "E", "status": "SCREENED", "samples": [
            _sample(70, 70, 70, 0.90),
            _sample(72, 72, 72, 1.02),
            _sample(68, 68, 68, 0.95),
        ]},
    ]
    result = robust_pareto(studies, min_samples=3)
    assert {item["case_id"] for item in result["front"]} == {"A", "B"}
    assert {item["case_id"] for item in result["eligible"]} == {"A", "B", "C"}
    assert {item["code"] for item in result["blocked"]} == {
        "ROBUST-SAMPLES-001", "ROBUST-UTIL-001",
    }
    a = next(item for item in result["eligible"] if item["case_id"] == "A")
    assert a["robust_objectives"]["relative_cost"] > 100.0
    assert a["worst_case_utilization"] == 0.90
    assert len(a["source_digest"]) == 64
    assert result["policy"]["objective_method"] == "ONE_SIDED_VARIABILITY_ENVELOPE"


def test_robust_pareto_refuses_replayed_uncertainty_samples():
    replay = _sample(100, 100, 100, 0.8)
    candidate = {
        "case_id": "REPLAY",
        "status": "SCREENED",
        "samples": [replay, dict(replay), dict(replay)],
    }
    result = robust_pareto([candidate], min_samples=3)
    assert result["eligible"] == []
    assert result["front"] == []
    assert {item["code"] for item in result["blocked"]} == {
        "ROBUST-INDEPENDENCE-001",
    }


def test_robust_pareto_refuses_digest_forgery_and_downgraded_policy():
    forged = [_sample(100 + index, 100 + index, 100 + index, 0.8)
              for index in range(3)]
    forged[1]["input_digest"] = "0" * 64
    result = robust_pareto([{
        "case_id": "FORGED", "status": "SCREENED", "samples": forged,
    }])
    assert {item["code"] for item in result["blocked"]} == {
        "ROBUST-INDEPENDENCE-001",
    }

    valid = [{
        "case_id": "VALID",
        "status": "SCREENED",
        "samples": [
            _sample(100, 100, 100, 0.8),
            _sample(101, 101, 101, 0.8),
            _sample(102, 102, 102, 0.8),
        ],
    }]
    with pytest.raises(ValueError, match="min_samples phải >= 3"):
        robust_pareto(valid, min_samples=2)
    with pytest.raises(ValueError, match="confidence_z.*>= 1.0"):
        robust_pareto(valid, confidence_z=0.999)


def test_zero_variance_requires_explicit_deterministic_justification():
    samples = [
        _sample(100 + index, 200 + index, 300 + index, 0.8)
        for index in range(3)
    ]
    for sample in samples:
        sample["objectives"] = {
            "relative_cost": 100.0,
            "material_mass_t": 200.0,
            "embodied_carbon_kgCO2e": 300.0,
        }
    candidate = {"case_id": "ZERO", "status": "SCREENED", "samples": samples}
    blocked = robust_pareto([candidate])
    assert {item["code"] for item in blocked["blocked"]} == {
        "ROBUST-INDEPENDENCE-002",
    }

    candidate["deterministic_justification"] = (
        "Đáp ứng được chứng minh bất biến giải tích với các perturbation đã khai."
    )
    justified = robust_pareto([candidate])
    assert [item["case_id"] for item in justified["eligible"]] == ["ZERO"]
    assert justified["blocked"] == []


def test_robust_pareto_rejects_duplicate_case_ids():
    candidate = {"case_id": "X", "status": "SCREENED", "samples": [
        _sample(1, 1, 1, 0.5), _sample(1, 1, 1, 0.5), _sample(1, 1, 1, 0.5),
    ]}
    with pytest.raises(ValueError, match="Trùng case_id"):
        robust_pareto([candidate, candidate])


def test_robust_pareto_rejects_malformed_policy_and_candidate_types():
    with pytest.raises(ValueError, match="min_samples phải >= 3"):
        robust_pareto([], min_samples=3.5)
    with pytest.raises(ValueError, match="confidence_z phải hữu hạn"):
        robust_pareto([], confidence_z="1.645")
    with pytest.raises(ValueError, match="candidate robust phải là object"):
        robust_pareto([None])
