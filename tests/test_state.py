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


# ---------------------------------------------------------------------------
# BRD-029 — mở khoá hợp đồng đa loại cầu mà KHÔNG đụng tới lịch sử
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent

FAMILY_SHAPE_KEYS = {
    "super_t_parametric_v2": ["girder_depth_mm", "top_flange_width_mm",
                              "top_flange_thickness_mm", "web_thickness_mm",
                              "bottom_bulb_width_mm", "bottom_bulb_height_mm"],
    "i_girder_parametric_v1": ["girder_depth_mm", "top_flange_width_mm",
                               "top_flange_thickness_mm", "web_thickness_mm",
                               "bottom_flange_width_mm", "bottom_flange_thickness_mm"],
    "box_girder_parametric_v1": ["box_web_height_mm", "box_web_thickness_mm",
                                 "box_bottom_width_mm", "box_bottom_slab_mm"],
    "composite_i_girder_parametric_v1": ["steel_depth_mm", "steel_top_flange_width_mm",
                                         "steel_top_flange_thickness_mm", "steel_web_thickness_mm",
                                         "steel_bottom_flange_width_mm",
                                         "steel_bottom_flange_thickness_mm"],
}

# Chốt trước khi nới hợp đồng. Nới enum/if-then KHÔNG được đổi một byte nào của
# canonical_json, vì input_hash và case_id của toàn bộ artifact lịch sử phụ thuộc nó.
# 16 hex dau cua input_hash (chinh la phan than cua case_id).
GOLD_INPUT_HASH_BEFORE_BRD029 = {
    "GC-01_standard_pass.json": "b6d4a1bc884997a7",
    "GC-02_geometry_invalid.json": "3e587e290b95415c",
    "GC-03_capacity_fail.json": "1ab4abe763b0e9a1",
    "GC-04_slab_too_thin.json": "1f3001767dbe0e45",
    "GC-05_solver_failure.json": "a2b7bb69a653c723",
    "GC-06_cheap_but_fails.json": "7b8e109e20a6c66c",
    "GC-07_pass_but_expensive.json": "8eeccbaba62c78e6",
}


def test_family_enum_covers_four_families_and_stays_an_enum():
    """Enum là hàng rào có chủ ý duy nhất chặn họ sandbox — không được đổi sang type:string."""
    schema = json.loads(
        (ROOT / "contracts" / "bridge_design_state.schema.json").read_text(encoding="utf-8"))
    fam = schema["properties"]["family"]
    assert "enum" in fam, "family phải giữ dạng enum"
    assert set(fam["enum"]) == {"super_t_simple_v1", "super_t_parametric_v2"} | set(
        FAMILY_SHAPE_KEYS) - {"super_t_parametric_v2"}
    assert "arch_deck_cfst_skeleton_v1" not in fam["enum"]


def test_opening_the_contract_did_not_move_any_historical_hash():
    """Bằng SỐ, không bằng lập luận: hash của cả 7 gold case phải y nguyên."""
    for name, expected in GOLD_INPUT_HASH_BEFORE_BRD029.items():
        state = json.loads(
            (ROOT / "gold_cases" / "cases" / name).read_text(encoding="utf-8"))
        assert input_hash(state)[:16] == expected, name
        assert make_case_id(state) == f"BT-{expected}", name


def test_each_family_is_locked_to_exactly_one_project_scope():
    """Nới hợp đồng KHÔNG có nghĩa là thả lỏng phạm vi bài toán."""
    base = json.loads(
        (ROOT / "gold_cases" / "cases" / "GC-01_standard_pass.json").read_text(encoding="utf-8"))
    loosened = json.loads(json.dumps(base))
    loosened["project_inputs"]["span_length_m"] = 45.0
    assert validate_design_state(loosened), "span ngoài phạm vi phải bị từ chối"

    skewed = json.loads(json.dumps(base))
    skewed["project_inputs"]["skew_deg"] = 15
    assert validate_design_state(skewed), "cầu chéo chưa có mô hình — phải bị từ chối"


def test_a_family_cannot_borrow_another_familys_shape_keys():
    base = json.loads(
        (ROOT / "gold_cases" / "cases" / "GC-01_standard_pass.json").read_text(encoding="utf-8"))
    borrowed = json.loads(json.dumps(base))
    borrowed["design_variables"]["box_web_height_mm"] = 2400
    assert validate_design_state(borrowed), "biến hình dạng của họ khác phải bị từ chối"


def test_durability_package_is_shipped():
    """Engine tuổi thọ mồ côi thì không vào wheel — bug đóng gói, không phải bug logic."""
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert '"bridge_evolution.durability"' in text
