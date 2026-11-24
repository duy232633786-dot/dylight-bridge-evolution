"""Unit tests for P0 TCVN 11823:2017 L1 Physics Simulation & MIDAS Load Exporter."""
from __future__ import annotations

import csv
import io
import math
import re

import pytest

from bridge_evolution.midas_loads import INTERCHANGE_SCHEMA, build_interchange_bundle
from bridge_evolution.physics_sim import (
    CLAIM_LEVEL,
    compare_l2_validation,
    list_sim_presets,
    run_stress_test,
)
from bridge_evolution.state import new_state


def _sample_baseline_state() -> dict:
    return new_state(
        {
            "girder_catalog_id": "ST-1750",
            "girder_count": 5,
            "girder_spacing_mm": 2400,
            "deck_slab_thickness_mm": 200,
            "diaphragm_layout_id": "DG-5",
            "prestress_layout_id": "PT-42",
        },
        girder_concrete_id="C50",
        deck_concrete_id="C35",
        grammar_id="super_t_simple_v1",
    )


def _sample_ai_parametric_state() -> dict:
    return new_state(
        {
            "girder_catalog_id": "ST-PARAM",
            "girder_count": 5,
            "girder_spacing_mm": 2400,
            "deck_slab_thickness_mm": 200,
            "diaphragm_layout_id": "DG-5",
            "prestress_layout_id": "PT-46",
            "girder_depth_mm": 1850,
            "top_flange_width_mm": 2050,
            "top_flange_thickness_mm": 120,
            "web_thickness_mm": 110,
            "bottom_bulb_width_mm": 350,
            "bottom_bulb_height_mm": 300,
        },
        girder_concrete_id="C55",
        deck_concrete_id="C35",
        grammar_id="super_t_parametric_v2",
    )


def _sample_box_state() -> dict:
    return new_state(
        {
            "girder_catalog_id": "BOX-PARAM",
            "girder_count": 1,
            "girder_spacing_mm": 12000,
            "deck_slab_thickness_mm": 250,
            "diaphragm_layout_id": "DG-5",
            "prestress_layout_id": "PT-54",
            "box_web_height_mm": 2400,
            "box_bottom_width_mm": 6500,
            "box_bottom_slab_mm": 250,
            "box_web_thickness_mm": 450,
        },
        girder_concrete_id="C50",
        deck_concrete_id="C35",
        grammar_id="box_girder_parametric_v1",
    )


# ---------------------------------------------------------------------------
# 1. Presets
# ---------------------------------------------------------------------------
def test_list_sim_presets_contract():
    res = list_sim_presets()
    assert res["claim_level"] == "SCREENED_HYPOTHETICAL"
    presets = res["presets"]
    assert len(presets) == 5

    expected_ids = {
        "V0_INLAND",
        "V1_COASTAL_TYPHOON",
        "V2_NORTHWEST_SEISMIC",
        "V3_PORT_OVERLOAD",
        "V4_EXTREME_MULTIHAZARD",
    }
    assert {p["id"] for p in presets} == expected_ids

    required_keys = {
        "id",
        "name",
        "description",
        "wind_vb_ms",
        "terrain_cat",
        "bridge_height_m",
        "temp_min_c",
        "temp_max_c",
        "tg_t1_c",
        "tg_t2_c",
        "pga_g",
        "exposure_class",
        "ll_multiplier",
        "im_factor",
    }
    for p in presets:
        assert required_keys.issubset(p.keys())
        assert p["temp_max_c"] > p["temp_min_c"]
        assert p["wind_vb_ms"] > 0
        assert p["ll_multiplier"] >= 1.0


# ---------------------------------------------------------------------------
# 2. Stress Test Duel — Full States, Scientific Honesty & Envelopes
# ---------------------------------------------------------------------------
def test_run_stress_test_full_states_and_honesty_rules():
    base = _sample_baseline_state()
    ai = _sample_ai_parametric_state()
    out = run_stress_test(base, ai, {"id": "V1_COASTAL_TYPHOON"})

    assert out["claim_level"] == CLAIM_LEVEL
    assert "SIMPLY_SUPPORTED_ONLY" in out["honesty_note"]
    assert out["scenario_applied"]["id"] == "V1_COASTAL_TYPHOON"

    for side in ("baseline", "ai"):
        data = out[side]
        assert data["model_source"] == "FULL_L1_SOLVER"
        assert len(data["stations"]) == 21
        # Boundary conditions at supports & midspan
        assert data["stations"][0]["x_m"] == 0.0
        assert math.isclose(data["stations"][-1]["x_m"], 38.3, abs_tol=1e-2)
        assert data["stations"][0]["M_kNm"] == 0.0
        assert data["stations"][-1]["M_kNm"] == 0.0
        assert data["stations"][0]["deflection_mm"] == 0.0
        assert data["stations"][-1]["deflection_mm"] == 0.0
        assert data["stations"][10]["M_kNm"] > 0.0
        assert data["stations"][10]["deflection_mm"] > 0.0

        # Required station keys
        for st in data["stations"]:
            assert {"x_m", "M_kNm", "V_kN", "deflection_mm", "sigma_top_MPa", "sigma_bot_MPa"} <= set(st.keys())

        # Thermal TG explicitly tagged SIMPLY_SUPPORTED_ONLY
        th = data["env_effects"]["thermal"]
        assert th["scope"] == "SIMPLY_SUPPORTED_ONLY"
        assert th["delta_L_mm"] > 0.0

        # Seismic L1 screening ONLY (NEVER uses vertical T1 for horizontal Csm)
        eq = data["env_effects"]["seismic_l1"]
        assert eq["uses_vertical_T1_for_Csm"] is False
        assert eq["N_min_mm"] > 200.0
        assert eq["F_key_kN"] > 0.0

        # SERV-004 top fiber compression check
        assert "SERV-004" in data["rule_utilizations"]
        s4 = data["serv004"]
        assert s4["limit_girder_sustained_MPa"] > 0
        assert s4["limit_girder_total_MPa"] > s4["limit_girder_sustained_MPa"]

        # RF, SF, and reserve multipliers
        assert math.isfinite(data["rating_factor"])
        assert data["safety_factor"] > 0.0
        assert data["lambda_str1"] >= 0.0
        assert data["lambda_deflect"] > 0.0

    # Sweep: 21 points from 0.5 to 2.5 step 0.1
    sweep = out["sweep"]
    assert len(sweep) == 21
    assert sweep[0]["lam"] == 0.5
    assert sweep[-1]["lam"] == 2.5
    # Deflection & D/C must be non-decreasing with lambda
    for a, b in zip(sweep, sweep[1:]):
        assert b["defl_base_mm"] >= a["defl_base_mm"]
        assert b["defl_ai_mm"] >= a["defl_ai_mm"]
        assert b["dc_base"] >= a["dc_base"] - 1e-9
        assert b["dc_ai"] >= a["dc_ai"] - 1e-9


def test_exposure_class_tightening_and_wind_scaling():
    base = _sample_baseline_state()
    ai = _sample_ai_parametric_state()

    res_inland = run_stress_test(base, ai, {"exposure_class": "INLAND_MODERATE", "wind_vb_ms": 35.0})
    res_coastal = run_stress_test(base, ai, {"exposure_class": "COASTAL_HUMID", "wind_vb_ms": 50.0})
    res_marine = run_stress_test(base, ai, {"exposure_class": "MARINE_SEVERE", "wind_vb_ms": 55.0})

    exp_in = res_inland["baseline"]["env_effects"]["exposure"]
    exp_co = res_coastal["baseline"]["env_effects"]["exposure"]
    exp_ma = res_marine["baseline"]["env_effects"]["exposure"]

    assert exp_in["cover_req_mm"] == 50.0
    assert exp_co["cover_req_mm"] == 60.0
    assert exp_ma["cover_req_mm"] == 75.0
    assert exp_in["tension_limit_MPa"] > exp_co["tension_limit_MPa"] > exp_ma["tension_limit_MPa"] == 0.0

    w_in = res_inland["baseline"]["env_effects"]["wind"]
    w_co = res_coastal["baseline"]["env_effects"]["wind"]
    assert w_co["P_D_kPa"] > w_in["P_D_kPa"]
    assert w_co["w_WS_kN_per_m"] > w_in["w_WS_kN_per_m"]
    assert w_co["w_overturning_ext_girder_kN_per_m"] > w_in["w_overturning_ext_girder_kN_per_m"]


def test_run_stress_test_handles_simplified_dicts_and_box_warning():
    # Simplified gene dict + bare objectives dict — must NEVER crash
    simplified_base = {
        "gene": {
            "girder_catalog_id": "ST-1750",
            "girder_count": 5,
            "girder_spacing_mm": 2400,
            "deck_slab_thickness_mm": 200,
            "girder_concrete_id": "C50",
            "deck_concrete_id": "C35",
            "diaphragm_layout_id": "DG-5",
            "prestress_layout_id": "PT-42",
        },
        "objectives": {"relative_cost": 1500.0},
        "max_utilization": 0.92,
    }
    bare_ai = {
        "objectives": {"relative_cost": 1350.0},
        "max_utilization": 0.85,
        "rule_utilizations": {"STR-001": 0.85},
    }
    out = run_stress_test(simplified_base, bare_ai, "V0_INLAND")
    assert out["claim_level"] == CLAIM_LEVEL
    assert len(out["baseline"]["stations"]) == 21
    assert len(out["ai"]["stations"]) == 21
    assert len(out["sweep"]) == 21

    # Box girder warning must be emitted for BOX-PARAM
    box_out = run_stress_test(_sample_baseline_state(), _sample_box_state(), "V4_EXTREME_MULTIHAZARD")
    assert box_out["ai"]["box_torsion_warning"] is not None
    assert "MIDAS" in box_out["ai"]["box_torsion_warning"]


# ---------------------------------------------------------------------------
# 3. L1 vs. L2 Validation Comparator
# ---------------------------------------------------------------------------
def test_compare_l2_validation_computations_and_exports():
    payload = {
        "l1_baseline": {
            "m_max_kNm": 6200.0,
            "sigma_bot_MPa": -1.50,
            "deflection_mm": 24.0,
            "volume_m3": 195.0,
            "max_dc": 0.94,
        },
        "l2_baseline": {
            "m_max_kNm": 6050.0,
            "sigma_bot_MPa": -1.45,
            "deflection_mm": 23.2,
            "volume_m3": 195.0,
            "max_dc": 0.91,
        },
        "l1_ai": {
            "m_max_kNm": 6100.0,
            "sigma_bot_MPa": -0.80,
            "deflection_mm": 21.0,
            "volume_m3": 172.0,
            "max_dc": 0.86,
        },
        "l2_ai": {
            "m_max_kNm": 5980.0,
            "sigma_bot_MPa": -0.78,
            "deflection_mm": 20.5,
            "volume_m3": 172.0,
            "max_dc": 0.84,
        },
    }
    res = compare_l2_validation(payload)
    assert res["claim_level"] == "L2_CROSS_CHECKED"
    assert res["has_l2_data"] is True
    assert res["within_5pct_target"] is True
    assert res["max_l1_l2_error_pct"] is not None and res["max_l1_l2_error_pct"] < 5.0

    # Check LaTeX booktabs structure
    latex = res["latex_table"]
    assert r"\toprule" in latex
    assert r"\midrule" in latex
    assert r"\bottomrule" in latex
    assert r"\begin{table}" in latex

    # Check CSV text
    rows = list(csv.reader(io.StringIO(res["csv_text"])))
    assert rows[0][0] == "metric"
    assert len(rows) == 6  # header + 5 metrics

    # Partial/empty L2 payload must degrade gracefully
    pending = compare_l2_validation({"l1_baseline": {"m_max_kNm": 6000.0}})
    assert pending["claim_level"] == "L2_COMPARISON_PENDING"
    assert pending["max_l1_l2_error_pct"] is None


# ---------------------------------------------------------------------------
# 4. Bridge Interchange v1 + MIDAS .mct + Dynamo CSV
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("key_name", ["report_or_state", "state", "report"])
def test_build_interchange_bundle_all_input_aliases(key_name: str):
    st = _sample_ai_parametric_state()
    bundle = build_interchange_bundle(
        {
            key_name: st if key_name != "report" else {"final_state": st},
            "scenario": {"id": "V4_EXTREME_MULTIHAZARD"},
            "label": "AI_SuperT_V4",
        }
    )

    interchange = bundle["bridge_interchange_v1"]
    assert interchange["schema"] == INTERCHANGE_SCHEMA == "bridge_interchange/1.0"
    assert re.fullmatch(r"[0-9a-f]{64}", interchange["sha256"])
    assert bundle["sha256"] == interchange["sha256"]
    assert interchange["geometry"]["span_m"] == 38.3
    assert interchange["materials"]["girder_concrete_id"] == "C55"
    assert interchange["scenario"]["id"] == "V4_EXTREME_MULTIHAZARD"

    # Verify all required MIDAS .mct blocks and load combinations
    mct = bundle["mct_text"]
    for token in (
        "*STLDCASE",
        "*SELFWEIGHT",
        "*BEAMLOAD",
        "*TEMPER",
        "*BSTEMP",
        "*SPFC",
        "*LOADCOMB",
        "STR_I",
        "STR_III",
        "STR_V",
        "SERV_I",
        "SERV_III",
        "EXT_I",
    ):
        assert token in mct, f"Missing required MIDAS MCT token: {token}"

    # Verify Dynamo CSV has header + 21 stations
    csv_rows = list(csv.reader(io.StringIO(bundle["dynamo_csv"])))
    assert len(csv_rows) == 22
    assert csv_rows[0][0] == "station_idx"
    assert csv_rows[1][1] == "0.0"
    assert float(csv_rows[-1][1]) == pytest.approx(38.3, abs=1e-3)


def test_build_interchange_unwraps_design_loop_report_final():
    """design_loop reports store the optimized candidate under report['final'] with report['grammar_id']."""
    loop_report = {
        "grammar_id": "super_t_parametric_v2",
        "final": {
            "gene": {
                "girder_catalog_id": "ST-PARAM",
                "girder_count": 5,
                "girder_spacing_mm": 2400,
                "deck_slab_thickness_mm": 200,
                "girder_concrete_id": "C60",
                "deck_concrete_id": "C35",
                "diaphragm_layout_id": "DG-5",
                "prestress_layout_id": "PT-46",
                "girder_depth_mm": 1900,
                "top_flange_width_mm": 2050,
                "top_flange_thickness_mm": 120,
                "web_thickness_mm": 110,
                "bottom_bulb_width_mm": 350,
                "bottom_bulb_height_mm": 300,
            }
        },
    }
    bundle = build_interchange_bundle({"report": loop_report, "scenario": "V1_COASTAL_TYPHOON", "label": "LoopFinal"})
    inter = bundle["bridge_interchange_v1"]
    assert inter["family"] == "super_t_parametric_v2"
    assert inter["materials"]["girder_concrete_id"] == "C60"
    assert inter["geometry"]["section"]["depth_m"] == pytest.approx(1.9, abs=1e-3)
