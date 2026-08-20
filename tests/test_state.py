import json
import re
from pathlib import Path

import pytest

from bridge_evolution.state import (validate_design_state, input_hash, make_case_id,
                                    new_state)

CASES = Path(__file__).resolve().parent.parent / "gold_cases" / "cases"


def load(name):
    with open(CASES / name, encoding="utf-8") as f:
        return json.load(f)


def test_gold_case_passes_schema():
    assert validate_design_state(load("GC-01_standard_pass.json")) == []


def test_schema_rejects_missing_field():
    state = load("GC-01_standard_pass.json")
    del state["design_variables"]["girder_count"]
    assert validate_design_state(state)


def test_schema_rejects_unknown_field():
    state = load("GC-01_standard_pass.json")
    state["design_variables"]["magic_flag"] = 1
    assert validate_design_state(state)


def test_hash_deterministic_and_ignores_provenance():
    a, b = load("GC-01_standard_pass.json"), load("GC-01_standard_pass.json")
    b["provenance"]["random_seed"] = 999
    assert input_hash(a) == input_hash(b)
    assert re.fullmatch(r"BT-[0-9a-f]{16}", make_case_id(a))


def test_hash_changes_with_design():
    a, b = load("GC-01_standard_pass.json"), load("GC-01_standard_pass.json")
    b["design_variables"]["girder_spacing_mm"] = 2150
    assert input_hash(a) != input_hash(b)


def test_new_state_valid():
    s = new_state(load("GC-01_standard_pass.json")["design_variables"],
                  girder_concrete_id="C45", deck_concrete_id="C35")
    assert validate_design_state(s) == []
    assert s["case_id"] == make_case_id(s)


@pytest.mark.parametrize("section,name,bad_value", [
    ("design_variables", "girder_catalog_id", "ST-KHONG-TON-TAI"),
    ("design_variables", "diaphragm_layout_id", "DG-KHONG-TON-TAI"),
    ("design_variables", "prestress_layout_id", "PT-KHONG-TON-TAI"),
    ("materials", "girder_concrete_id", "C-KHONG-TON-TAI"),
    ("materials", "deck_concrete_id", "C-KHONG-TON-TAI"),
    ("materials", "prestressing_steel_id", "PS-KHONG-TON-TAI"),
    ("analysis", "load_profile_id", "LOAD-KHONG-TON-TAI"),
    ("constraints", "rule_profile_id", "RULE-KHONG-TON-TAI"),
])
def test_unknown_catalog_references_are_validation_errors(section, name, bad_value):
    state = load("GC-01_standard_pass.json")
    state[section][name] = bad_value
    errors = validate_design_state(state)
    assert errors
    assert any(f"{section}/{name}" in error for error in errors)


def test_existing_catalog_value_outside_grammar_is_rejected():
    state = load("GC-01_standard_pass.json")
    state["materials"]["girder_concrete_id"] = "C35"  # có trong catalog, ngoài grammar
    assert any("ngoài miền grammar" in error for error in validate_design_state(state))


def test_project_scope_is_fixed_by_grammar():
    state = load("GC-01_standard_pass.json")
    state["project_inputs"]["span_length_m"] = 40.0
    assert validate_design_state(state)


@pytest.mark.parametrize("fidelity,solver,valid", [
    ("L1_LINE_GIRDER", "BUILTIN_L1", True),
    ("L2_GRILLAGE", "MIDAS_CIVIL", True),
    ("L2_GRILLAGE", "OPENSEESPY", True),
    ("L3_NONLINEAR", "MIDAS_CIVIL", True),
    ("L3_NONLINEAR", "BUILTIN_L1", False),
    ("L3_NONLINEAR", "OPENSEESPY", False),
])
def test_fidelity_solver_compatibility(fidelity, solver, valid):
    state = load("GC-01_standard_pass.json")
    state["analysis"].update(fidelity=fidelity, solver=solver)
    errors = validate_design_state(state)
    assert (not errors) is valid
