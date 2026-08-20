"""Kiểm chứng lõi vật lý L1 bằng các bài toán có nghiệm giải tích chính xác."""
import json
from pathlib import Path

import pytest

from bridge_evolution.catalogs import load_catalogs
from bridge_evolution.fe_adapter.line_girder import (_moving_load_max, analyze,
                                                     composite_section, GRAVITY,
                                                     SolverError)
from bridge_evolution.geometry import derive_geometry
from bridge_evolution.objectives import diaphragm_concrete_volume_m3


CASES = Path(__file__).resolve().parent.parent / "gold_cases" / "cases"


def _standard_state():
    with open(CASES / "GC-01_standard_pass.json", encoding="utf-8") as f:
        return json.load(f)


def test_single_point_load_gives_PL_over_4():
    M, V = _moving_load_max(20.0, ((0.0, 100.0),))
    assert abs(M - 100.0 * 20.0 / 4.0) < 0.5   # PL/4 = 500
    assert abs(V - 100.0) < 1e-6


def test_two_equal_loads_analytical_max():
    # 2 tải P=100 cách nhau a=5 trên L=20: Mmax = P(L - a/2)^2 / (2L) = 765.625 kNm
    M, _ = _moving_load_max(20.0, ((0.0, 100.0), (5.0, 100.0)))
    assert abs(M - 765.625) < 1.0


def test_moment_monotonic_with_span():
    axles = ((0.0, 35.0), (4.3, 145.0), (8.6, 145.0))
    M30, _ = _moving_load_max(30.0, axles)
    M40, _ = _moving_load_max(40.0, axles)
    assert M40 > M30 > 0


def test_composite_stiffer_than_girder_alone():
    sec = {"depth_m": 1.75, "area_m2": 0.649, "I_m4": 0.226, "y_bottom_m": 0.795,
           "top_flange_width_m": 2.06, "web_width_total_m": 0.20}
    comp = composite_section(sec, 31.5, 27.8, 2.2, 0.2, 38.3)
    assert comp["I_c"] > sec["I_m4"]
    assert comp["yb_c"] > sec["y_bottom_m"]   # trục trung hòa dịch lên khi thêm bản


def test_singular_section_raises_solver_error():
    sec = {"depth_m": 1.75, "area_m2": 0.649, "I_m4": 0.0, "y_bottom_m": 0.795,
           "top_flange_width_m": 2.06, "web_width_total_m": 0.20}
    with pytest.raises(SolverError):
        composite_section(sec, 31.5, 27.8, 2.2, 0.2, 38.3)


def test_diaphragm_self_weight_is_in_stage1_and_matches_objective_volume():
    state = _standard_state()
    geom = derive_geometry(state)
    result = analyze(state, geom)
    cat = load_catalogs()
    dia_geo = cat["diaphragm_layouts"]["_geometry"]
    conc_dia = cat["concretes"][dia_geo["concrete_id"]]

    volume = diaphragm_concrete_volume_m3(state, geom, cat)
    expected_w = (volume * conc_dia["density_kg_m3"] * GRAVITY / 1000.0
                  / (geom["span_m"] * geom["girder_count"]))
    loads = result["dead_loads_kN_per_m"]

    assert loads["diaphragm_smeared"] == pytest.approx(expected_w)
    assert loads["stage1_total"] == pytest.approx(
        loads["girder"] + loads["deck"] + loads["diaphragm_smeared"] + loads["misc"])
    assert result["moments_kNm"]["stage1"] == pytest.approx(
        loads["stage1_total"] * geom["span_m"] ** 2 / 8.0)


def test_compression_block_depth_and_slab_depth_are_reported_consistently():
    state = _standard_state()
    capacity = analyze(state, derive_geometry(state))["capacity"]

    assert capacity["compression_block_depth_mm"] > 0
    assert capacity["slab_thickness_mm"] == state["design_variables"]["deck_slab_thickness_mm"]
    assert capacity["stress_block_in_slab"] == (
        capacity["compression_block_depth_mm"] <= capacity["slab_thickness_mm"] + 1e-6)
