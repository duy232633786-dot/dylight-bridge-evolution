"""Tests for L2 3D V&V and multi-method independent check (Task BRD-003)."""

from __future__ import annotations

import json
from pathlib import Path
import pytest
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parent.parent


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture
def schema() -> dict:
    return _load_json(ROOT / "contracts" / "physical_validation_record.schema.json")


@pytest.fixture
def protocol() -> dict:
    return _load_json(ROOT / "experiments" / "validation" / "l2_protocol.json")


def test_physical_validation_schema_validates_correct_records(schema, protocol):
    validator = Draft202012Validator(schema)
    records = protocol.get("verified_records", [])
    assert len(records) >= 1
    for rec in records:
        errors = list(validator.iter_errors(rec))
        assert not errors, f"Record {rec.get('validation_id')} failed schema: {errors}"


def test_stratified_sampling_tier_coverage(protocol):
    tiers = [t["tier"] for t in protocol["sampling_strategy"]["tiers"]]
    assert "OPTIMUM" in tiers
    assert "INTERIOR_CONTROL" in tiers
    assert "FAILING_BOUNDARY" in tiers


def test_mesh_convergence_and_equilibrium_fail_closed(schema, protocol):
    validator = Draft202012Validator(schema)
    valid_record = protocol["verified_records"][0]

    # Test excessive mesh convergence error
    bad_mesh = dict(valid_record)
    bad_mesh["l2_fe_model"] = dict(valid_record["l2_fe_model"])
    bad_mesh["l2_fe_model"]["mesh_convergence_error_pct"] = -5.0  # Invalid negative
    assert list(validator.iter_errors(bad_mesh))

    # Test missing equilibrium residual
    bad_eq = dict(valid_record)
    bad_eq["l2_fe_model"] = dict(valid_record["l2_fe_model"])
    del bad_eq["l2_fe_model"]["equilibrium_residual_kN"]
    assert list(validator.iter_errors(bad_eq))


def test_independent_check_requires_blind_and_tolerance_enforcement(protocol):
    tol = protocol["pre_registered_tolerances"]["independent_check_max_discrepancy_pct"]
    for rec in protocol.get("verified_records", []):
        check = rec["independent_check"]
        assert check["is_blind"] is True, "Independent calculation must be blind"
        assert check["discrepancy_pct"] <= tol, f"Discrepancy exceeds pre-registered tolerance {tol}%"
        assert check["verified_pass"] is True
