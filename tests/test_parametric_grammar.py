"""Grammar v2 tham số hóa: tích hợp vào lõi mà KHÔNG đổi hành vi grammar v1.

Hai nhóm khẳng định:
  1. Neo hồi quy v1 — ``V1_FROZEN`` là EvaluationResult chụp TRƯỚC khi grammar v2
     được nối vào lõi. Mọi thứ ngoài ``timestamp_utc``/``runtime_ms`` phải khớp
     từng byte, kể cả ``input_hash`` và ``violations``. Ngoại lệ DUY NHẤT được
     phép là ``catalogs_version``: catalog lên 1.1.0 vì THÊM (không sửa) entry
     ST-PARAM, C55/C60 và BRIDGE-RULESET-V2; provenance phải nói thật về việc đó.
  2. Đường tham số hóa — tiết diện tính từ 6 biến hình dạng, và ràng buộc chế tạo
     FAB-* chặn ở L0 (solver KHÔNG được mở).
"""
import json
from copy import deepcopy
from pathlib import Path

import pytest

from bridge_evolution.evaluate import evaluate_candidate
from bridge_evolution.geometry import check_geometry, derive_geometry
from bridge_evolution.section import section_from_params
from bridge_evolution.state import new_state, validate_design_state

CASES = Path(__file__).resolve().parent.parent / "gold_cases" / "cases"

GRAMMAR_V2 = "super_t_parametric_v2"

#: Bộ tham số v2 tham chiếu: dựng được biên, sạch FAB, đủ chỗ cho PT-42.
PARAM_BASE = {
    "girder_catalog_id": "ST-PARAM",
    "girder_count": 5,
    "girder_spacing_mm": 2350,
    "deck_slab_thickness_mm": 200,
    "diaphragm_layout_id": "DG-5",
    "prestress_layout_id": "PT-42",
    "girder_depth_mm": 1750,
    "top_flange_width_mm": 2050,
    "top_flange_thickness_mm": 120,
    "web_thickness_mm": 110,
    "bottom_bulb_width_mm": 350,
    "bottom_bulb_height_mm": 350,
}

#: EvaluationResult của 3 gold case v1, chụp trước khi nối grammar v2 vào lõi.
V1_FROZEN = {
    "GC-01_standard_pass.json": {
        "case_id": "BT-b6d4a1bc884997a7",
        "status": "SUCCESS",
        "feasible": True,
        "solver": {"status": "CONVERGED", "name": "BUILTIN_L1"},
        "violations": [],
        "provenance": {
            "input_hash": "b6d4a1bc884997a7a48321659df9a226bbe804ca5290403afc9e4c162cccf844",
            "ruleset_version": "BRIDGE-RULESET-V1/1.1.0",
            "solver_version": "builtin-l1/0.2.0 (pkg 0.8.0)",
            "grammar_version": "1.0.0",
            "random_seed": 42,
        },
        "responses": {
            "Mu_strength1_kNm": 13796.7, "phiMn_kNm": 20155.9,
            "Vu_strength1_kN": 1616.8, "phiVn_kN": 1894.0,
            "bottom_stress_service3_MPa": 0.928, "tension_limit_MPa": 3.354,
            "max_ll_deflection_mm": 12.03, "deflection_limit_mm": 47.87,
            "first_frequency_Hz": 2.276, "max_utilization": 0.8841,
            "distribution_factor_moment": 0.6174, "distribution_factor_shear": 0.7688,
        },
        "objectives": {"relative_cost": 2585.58, "material_mass_t": 632.98,
                       "embodied_carbon_kgCO2e": 113844.0},
    },
    "GC-03_capacity_fail.json": {
        "case_id": "BT-1ab4abe763b0e9a1",
        "status": "SUCCESS",
        "feasible": False,
        "solver": {"status": "CONVERGED", "name": "BUILTIN_L1"},
        "violations": [
            {"rule_id": "STR-001", "severity": "HARD",
             "message": "Uốn CĐ-I: Mu=15572 kNm > φMn=14390 kNm", "margin": 0.0822},
            {"rule_id": "STR-002", "severity": "HARD",
             "message": "Cắt CĐ-I: Vu=1837 kN > φVn=1768 kN", "margin": 0.0392},
            {"rule_id": "SERV-001", "severity": "HARD",
             "message": "Kéo thớ dưới SD-III: 11.57 MPa > giới hạn 3.16 MPa", "margin": 2.6587},
        ],
        "provenance": {
            "input_hash": "1ab4abe763b0e9a13197d0d05d903cc264a43ced05be2c3224ca529cc972c405",
            "ruleset_version": "BRIDGE-RULESET-V1/1.1.0",
            "solver_version": "builtin-l1/0.2.0 (pkg 0.8.0)",
            "grammar_version": "1.0.0",
            "random_seed": 42,
        },
        "responses": {
            "Mu_strength1_kNm": 15572.0, "phiMn_kNm": 14389.9,
            "Vu_strength1_kN": 1836.9, "phiVn_kN": 1767.5,
            "bottom_stress_service3_MPa": -11.57, "tension_limit_MPa": 3.162,
            "max_ll_deflection_mm": 16.76, "deflection_limit_mm": 47.87,
            "first_frequency_Hz": 2.024, "max_utilization": 3.6587,
            "distribution_factor_moment": 0.7277, "distribution_factor_shear": 0.9093,
        },
        "objectives": {"relative_cost": 1979.59, "material_mass_t": 546.64,
                       "embodied_carbon_kgCO2e": 86799.2},
    },
    "GC-07_pass_but_expensive.json": {
        "case_id": "BT-8eeccbaba62c78e6",
        "status": "SUCCESS",
        "feasible": True,
        "solver": {"status": "CONVERGED", "name": "BUILTIN_L1"},
        "violations": [],
        "provenance": {
            "input_hash": "8eeccbaba62c78e6e9782b7169c64482b7e1944bb8c3e9e6d151a7b3c835a220",
            "ruleset_version": "BRIDGE-RULESET-V1/1.1.0",
            "solver_version": "builtin-l1/0.2.0 (pkg 0.8.0)",
            "grammar_version": "1.0.0",
            "random_seed": 42,
        },
        "responses": {
            "Mu_strength1_kNm": 14240.9, "phiMn_kNm": 25228.4,
            "Vu_strength1_kN": 1682.1, "phiVn_kN": 2058.1,
            "bottom_stress_service3_MPa": 5.373, "tension_limit_MPa": 3.536,
            "max_ll_deflection_mm": 9.15, "deflection_limit_mm": 47.87,
            "first_frequency_Hz": 2.494, "max_utilization": 0.8463,
            "distribution_factor_moment": 0.5856, "distribution_factor_shear": 0.7568,
        },
        "objectives": {"relative_cost": 2845.12, "material_mass_t": 712.28,
                       "embodied_carbon_kgCO2e": 132653.6},
    },
}


def load_case(name: str) -> dict:
    with open(CASES / name, encoding="utf-8") as f:
        return json.load(f)


def param_state(**overrides) -> dict:
    """State grammar v2 từ PARAM_BASE, ghi đè từng biến để dựng ca kiểm."""
    dv = dict(PARAM_BASE)
    dv.update(overrides)
    return new_state(dv, girder_concrete_id="C50", deck_concrete_id="C35",
                     grammar_id=GRAMMAR_V2, seed=42)


def rule_ids(violations) -> set:
    return {v["rule_id"] for v in violations}


# ------------------------------------------------------------------ v1 không đổi
@pytest.mark.parametrize("case_file", sorted(V1_FROZEN))
def test_v1_states_unchanged(case_file):
    result = deepcopy(evaluate_candidate(load_case(case_file)))
    # Chỉ hai trường phụ thuộc lần chạy được phép khác.
    assert result["provenance"].pop("timestamp_utc")
    result["solver"].pop("runtime_ms", None)
    # catalogs 1.1.0 THÊM entry cho v2; chính vì thêm thật nên version phải nhích.
    assert result["provenance"].pop("catalogs_version") == "1.1.0"
    assert result == V1_FROZEN[case_file]


def test_v1_section_stays_catalog_and_free_of_fab_rules():
    state = load_case("GC-01_standard_pass.json")
    violations, geom = check_geometry(state)
    assert geom["section_source"] == "CATALOG"
    assert geom["section"] is load_case and False or geom["section"]["depth_m"] == 1.75
    assert not any(v["rule_id"].startswith("FAB") for v in violations)


# ------------------------------------------------------------------ đường v2
def test_param_state_evaluates():
    state = param_state()
    assert validate_design_state(state) == []
    result = evaluate_candidate(state)
    assert result["status"] == "SUCCESS", result["violations"]
    assert result["solver"]["status"] == "CONVERGED"
    assert set(result["responses"]) >= {
        "Mu_strength1_kNm", "phiMn_kNm", "Vu_strength1_kN", "phiVn_kN",
        "bottom_stress_service3_MPa", "tension_limit_MPa",
        "max_ll_deflection_mm", "deflection_limit_mm",
        "first_frequency_Hz", "max_utilization",
    }
    assert set(result["objectives"]) == {
        "relative_cost", "material_mass_t", "embodied_carbon_kgCO2e"}


def test_param_section_matches_direct_computation():
    state = param_state()
    geom = derive_geometry(state)
    direct = section_from_params({k: PARAM_BASE[k] for k in (
        "girder_depth_mm", "top_flange_width_mm", "top_flange_thickness_mm",
        "web_thickness_mm", "bottom_bulb_width_mm", "bottom_bulb_height_mm")})

    assert geom["section_source"] == "PARAMETRIC"
    assert geom["section"]["source"] == "PARAMETRIC"
    # Không làm tròn ở bất kỳ đâu trên đường dẫn: phải khớp TUYỆT ĐỐI.
    assert geom["section"]["area_m2"] == direct["area_m2"]
    assert geom["section"]["I_m4"] == direct["I_m4"]
    assert geom["section"]["y_bottom_m"] == direct["y_bottom_m"]
    assert geom["flange_gap_m"] == pytest.approx(
        geom["spacing_m"] - PARAM_BASE["top_flange_width_mm"] / 1000.0)


def test_param_objectives_use_real_section_area():
    """Khối lượng/chi phí/carbon phải theo diện tích THẬT, không theo entry catalog."""
    thin = evaluate_candidate(param_state(top_flange_thickness_mm=100))
    thick = evaluate_candidate(param_state(top_flange_thickness_mm=130))
    assert thin["status"] == thick["status"] == "SUCCESS"
    assert thin["objectives"]["material_mass_t"] < thick["objectives"]["material_mass_t"]
    assert thin["objectives"]["relative_cost"] < thick["objectives"]["relative_cost"]


# ------------------------------------------------------------------ FAB ở L0
def test_fab_violation_blocks_at_L0():
    state = param_state(web_thickness_mm=90)  # đúng lưới grammar, dưới ngưỡng xưởng
    assert validate_design_state(state) == []

    violations, _ = check_geometry(state)
    fab001 = [v for v in violations if v["rule_id"] == "FAB-001"]
    assert fab001 and fab001[0]["severity"] == "HARD"
    assert fab001[0]["margin"] > 0

    result = evaluate_candidate(state)
    assert result["status"] == "GEOMETRY_INVALID"
    assert result["solver"]["status"] == "NOT_RUN"   # không tiêu ngân sách solver
    assert "FAB-001" in rule_ids(result["violations"])


@pytest.mark.parametrize("overrides,rule_id", [
    ({"bottom_bulb_height_mm": 150}, "FAB-003"),          # bầu không đủ chỗ 42 tao
    ({"girder_depth_mm": 2100, "top_flange_width_mm": 2300,
      "top_flange_thickness_mm": 170, "web_thickness_mm": 160,
      "bottom_bulb_width_mm": 450}, "FAB-004"),           # phiến vượt sức nâng cẩu
])
def test_fabrication_rules_are_hard_gates(overrides, rule_id):
    state = param_state(**overrides)
    assert validate_design_state(state) == []
    result = evaluate_candidate(state)
    assert result["status"] == "GEOMETRY_INVALID"
    assert result["solver"]["status"] == "NOT_RUN"
    hard = {v["rule_id"] for v in result["violations"] if v["severity"] == "HARD"}
    assert rule_id in hard


@pytest.mark.parametrize("overrides", [
    # Hai bầu chồng qua tim — tất cả giá trị ĐỀU đúng lưới grammar.
    {"top_flange_width_mm": 1900, "web_thickness_mm": 90, "bottom_bulb_width_mm": 450},
    # Cánh trên hẹp hơn 2× phần chìa 300 mm ⇒ không còn chỗ cho sườn.
    {"top_flange_width_mm": 500},
    # Cánh trên dày hơn cả chiều cao dầm.
    {"girder_depth_mm": 1500, "top_flange_thickness_mm": 1600},
])
def test_invalid_geometry_becomes_FAB000(overrides):
    state = param_state(**overrides)

    violations, geom = check_geometry(state)   # KHÔNG được raise
    assert "FAB-000" in rule_ids(violations)
    assert all(v["severity"] == "HARD" for v in violations if v["rule_id"] == "FAB-000")
    assert geom["section"] is None
    assert geom["section_source"] == "PARAMETRIC_INVALID"
    # Bố trí mặt cắt ngang vẫn kiểm được để agent nhận đủ tín hiệu trong một lần.
    assert geom["overhang_m"] == pytest.approx(1.3)

    result = evaluate_candidate(state)         # cũng KHÔNG được raise
    assert result["solver"]["status"] == "NOT_RUN"
    assert result["status"] in ("GEOMETRY_INVALID", "SCHEMA_INVALID")


# ------------------------------------------------------------------ contract v2
def test_v2_schema_valid():
    assert validate_design_state(param_state()) == []

    off_grid = param_state(girder_depth_mm=1525)   # 1525 không nằm trên bước 50
    errors = validate_design_state(off_grid)
    assert any("girder_depth_mm" in e and "ngoài miền grammar" in e for e in errors)

    violations, _ = check_geometry(off_grid)
    assert "CONS-002" in rule_ids(violations)


def test_v2_missing_shape_variable_is_contract_error():
    state = param_state()
    del state["design_variables"]["bottom_bulb_height_mm"]
    errors = validate_design_state(state)
    assert any("bottom_bulb_height_mm" in e for e in errors)
    # Và L0 vẫn phải trả violation thay vì nổ exception.
    assert "FAB-000" in rule_ids(check_geometry(state)[0])


def test_v1_state_stays_valid_without_shape_variables():
    """6 khóa hình dạng là TÙY CHỌN trong schema — state v1 không đổi gì."""
    state = load_case("GC-01_standard_pass.json")
    assert set(state["design_variables"]) & {"girder_depth_mm", "web_thickness_mm"} == set()
    assert validate_design_state(state) == []
