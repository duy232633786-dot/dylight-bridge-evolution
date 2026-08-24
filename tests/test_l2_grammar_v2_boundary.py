"""Tests for L2 Midas boundary comparison on grammar v2 sections (Task BRD-014)."""

from __future__ import annotations

import json
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / "experiments" / "validation" / "grammar_v2_fab_boundary"


def _load(name: str) -> dict:
    return json.loads((BASE / name).read_text(encoding="utf-8"))


@pytest.fixture
def prereg() -> dict:
    return _load("pre_registration.json")


@pytest.fixture
def model_card() -> dict:
    return _load("model_card.json")


@pytest.fixture
def indep_check() -> dict:
    return _load("independent_check.json")


def test_preregistration_and_model_card_integrity(prereg, model_card):
    assert prereg["schema_version"] == "1.0"
    assert prereg["task_id"] == "BRD-014"
    assert prereg["fidelity_target"] == "NUMERICALLY_VERIFIED"
    assert "mesh_convergence_error_max_pct" in prereg["pre_registered_tolerances"]

    assert model_card["schema_version"] == "1.0"
    assert model_card["task_id"] == "BRD-014"
    assert model_card["mesh_convergence_study"]["convergence_status"] == "CONVERGED"
    assert model_card["equilibrium_audit"]["equilibrium_status"] == "PASS"


def test_stratified_samples_include_fab_boundary_and_failing_cases(prereg, indep_check):
    strata_ids = [s["stratum_id"] for s in prereg["sampling_plan"]["strata"]]
    assert "FAB_BOUNDARY_OPTIMUM" in strata_ids
    assert "INTERIOR_CONTROL" in strata_ids
    assert "FAILING_BOUNDARY" in strata_ids

    verified_strata = [r["stratum_id"] for r in indep_check["strata_verification_results"]]
    assert set(strata_ids) == set(verified_strata)


def test_mesh_convergence_and_equilibrium_criteria(prereg, model_card):
    max_mesh_err = prereg["pre_registered_tolerances"]["mesh_convergence_error_max_pct"]
    max_resid = prereg["pre_registered_tolerances"]["equilibrium_reaction_residual_max_kN"]

    observed_mesh_err = model_card["mesh_convergence_study"]["convergence_relative_error_pct"]
    observed_resid = model_card["equilibrium_audit"]["residual_kN"]

    assert observed_mesh_err <= max_mesh_err, f"Mesh error {observed_mesh_err}% exceeds {max_mesh_err}%"
    assert observed_resid <= max_resid, f"Residual {observed_resid} kN exceeds {max_resid} kN"


def test_independent_check_is_blind_and_within_tolerance(prereg, indep_check):
    assert indep_check["checker_metadata"]["is_blind"] is True
    tol = prereg["pre_registered_tolerances"]["independent_check_discrepancy_max_pct"]

    for res in indep_check["strata_verification_results"]:
        check = res["independent_check_result"]
        assert check["verified_pass"] is True
        assert check["discrepancy_vs_l2_pct"] <= tol, f"Check discrepancy {check['discrepancy_vs_l2_pct']}% exceeds {tol}%"


def test_reports_discrepancy_and_failure_modes_for_all_tiers(indep_check):
    results = indep_check["strata_verification_results"]
    assert len(results) >= 3

    for res in results:
        assert "failure_mode" in res and len(res["failure_mode"]) >= 5
        assert "l1_vs_l2_discrepancy_pct" in res
        assert res["l1_vs_l2_discrepancy_pct"] >= 0.0

    synthesis = indep_check["synthesis_and_uncertainty"]
    assert "mean_l1_l2_discrepancy_pct" in synthesis
    assert "max_l1_l2_discrepancy_pct" in synthesis
    assert "conclusion" in synthesis
