"""Kiểm chứng section builders đa loại cầu (BRD-025 — bridge_evolution/section_types.py).

Bốn lớp kiểm tra:
  1. TOÁN HỌC — I/hộp/thép đối chiếu công thức giải tích đóng (A, y, I).
  2. HÌNH HỌC — đơn điệu theo tham số, tự chối tham số phi vật lý.
  3. FAB — mỗi rule có case kích hoạt + case sạch.
  4. PIPELINE — grammar mới chạy trọn state → L0 → (I/BOX: solver L1;
     CI: bị gate SOLVER-COMPOSITE-001) và Super-T v1/v2 KHÔNG đổi hành vi.
"""
import math

import pytest

from bridge_evolution.catalogs import load_catalogs
from bridge_evolution.geometry import check_geometry
from bridge_evolution.section import SectionGeometryError
from bridge_evolution.section_types import (
    composite_i_girder_section_from_params,
    composite_solver_gate,
    fabrication_violations_box_girder,
    fabrication_violations_composite_i,
    fabrication_violations_i_girder,
    box_girder_section_from_params,
    i_girder_section_from_params,
)
from bridge_evolution.state import state_from_gene

CONTRACT_KEYS = {"depth_m", "area_m2", "I_m4", "y_bottom_m",
                 "top_flange_width_m", "web_width_total_m"}

# ---------------------------------------------------------------- I-girder
I_ANCHOR = {
    "girder_depth_mm": 1800,
    "top_flange_width_mm": 1000,
    "top_flange_thickness_mm": 180,
    "web_thickness_mm": 200,
    "bottom_flange_width_mm": 650,
    "bottom_flange_thickness_mm": 300,
}


def test_i_girder_matches_closed_form():
    sec = i_girder_section_from_params(I_ANCHOR)
    H, bf, tf = 1.8, 1.0, 0.18
    tw, bfb, tfb = 0.2, 0.65, 0.30
    a_flange_t = bf * tf
    a_web = tw * (H - tf - tfb)
    a_flange_b = bfb * tfb
    area = a_flange_t + a_web + a_flange_b
    yb = (a_flange_b * tfb / 2 + a_web * (tfb + (H - tf - tfb) / 2)
          + a_flange_t * (H - tf / 2)) / area
    assert sec["area_m2"] == pytest.approx(area, rel=1e-9)
    assert sec["y_bottom_m"] == pytest.approx(yb, rel=1e-9)
    i_flange_b = bfb * tfb ** 3 / 12 + a_flange_b * (yb - tfb / 2) ** 2
    i_web = tw * (H - tf - tfb) ** 3 / 12 + a_web * (tfb + (H - tf - tfb) / 2 - yb) ** 2
    i_flange_t = bf * tf ** 3 / 12 + a_flange_t * (H - tf / 2 - yb) ** 2
    assert sec["I_m4"] == pytest.approx(i_flange_b + i_web + i_flange_t, rel=1e-9)
    assert CONTRACT_KEYS <= set(sec.keys())
    assert sec["web_width_total_m"] == pytest.approx(0.2)


def test_i_girder_monotonic_in_depth():
    i_prev = 0.0
    for h in range(1400, 2201, 100):
        sec = i_girder_section_from_params({**I_ANCHOR, "girder_depth_mm": h})
        assert sec["I_m4"] > i_prev
        i_prev = sec["I_m4"]


@pytest.mark.parametrize("override", [
    {"top_flange_width_mm": 800, "bottom_flange_width_mm": 900},  # bf < bfb
    {"bottom_flange_width_mm": 100},     # bfb < tw
    {"girder_depth_mm": 300},            # tf + tfb >= H
])
def test_i_girder_rejects_invalid(override):
    with pytest.raises(SectionGeometryError):
        i_girder_section_from_params({**I_ANCHOR, **override})


def test_i_girder_fab_rules_fire_and_clean():
    ctx = {"span_m": 35.0, "strand_count": 44}
    assert fabrication_violations_i_girder(I_ANCHOR, ctx) == []

    thin_web = {**I_ANCHOR, "web_thickness_mm": 100}
    ids = {v["rule_id"] for v in fabrication_violations_i_girder(thin_web, ctx)}
    assert "FAB-001" in ids

    no_room = {**I_ANCHOR, "bottom_flange_width_mm": 500,
               "bottom_flange_thickness_mm": 200}
    ids = {v["rule_id"] for v in fabrication_violations_i_girder(no_room, ctx)}
    assert "FAB-003" in ids

    heavy = dict(I_ANCHOR)
    ctx_heavy = {"span_m": 35.0, "strand_count": 44,
                 "fab_limits": {"lift_capacity_t": 10.0}}
    ids = {v["rule_id"] for v in fabrication_violations_i_girder(heavy, ctx_heavy)}
    assert "FAB-004" in ids

    ids = {v["rule_id"] for v in fabrication_violations_i_girder(
        I_ANCHOR, {"span_m": 60.0, "strand_count": 44})}
    assert "FAB-007" in ids  # L/H = 33 > 26 (SOFT)


# ---------------------------------------------------------------- Box girder
BOX_ANCHOR = {
    "box_web_height_mm": 2400,
    "box_bottom_width_mm": 6500,
    "box_bottom_slab_mm": 250,
    "box_web_thickness_mm": 450,
}


def test_box_u_section_matches_closed_form():
    sec = box_girder_section_from_params(BOX_ANCHOR)
    H, Bb, tsb, tw = 2.4, 6.5, 0.25, 0.45
    xi = Bb / 2 - tw
    a_slab = Bb * tsb
    a_webs = 2 * tw * (H - tsb)
    area = a_slab + a_webs
    yb = (a_slab * tsb / 2 + a_webs * (tsb + (H - tsb) / 2)) / area
    assert sec["area_m2"] == pytest.approx(area, rel=1e-9)
    assert sec["y_bottom_m"] == pytest.approx(yb, rel=1e-9)
    i_slab = Bb * tsb ** 3 / 12 + a_slab * (yb - tsb / 2) ** 2
    i_web_one = tw * (H - tsb) ** 3 / 12
    d_web = tsb + (H - tsb) / 2 - yb
    assert sec["I_m4"] == pytest.approx(i_slab + 2 * (i_web_one + tw * (H - tsb) * d_web ** 2),
                                        rel=1e-9)
    assert sec["web_width_total_m"] == pytest.approx(0.9)


def test_box_rejects_invalid():
    with pytest.raises(SectionGeometryError):
        box_girder_section_from_params({**BOX_ANCHOR, "box_bottom_slab_mm": 2500})
    with pytest.raises(SectionGeometryError):
        box_girder_section_from_params({**BOX_ANCHOR, "box_bottom_width_mm": 800})


def test_box_fab_rules_fire_and_clean():
    ctx = {"span_m": 45.0, "strand_count": 40, "deck_slab_thickness_mm": 250}
    assert fabrication_violations_box_girder(BOX_ANCHOR, ctx) == []

    ids = {v["rule_id"] for v in fabrication_violations_box_girder(
        {**BOX_ANCHOR, "box_web_thickness_mm": 300}, ctx)}
    assert "FAB-001" in ids

    ids = {v["rule_id"] for v in fabrication_violations_box_girder(
        BOX_ANCHOR, {**ctx, "deck_slab_thickness_mm": 180})}
    assert "FAB-002" in ids

    ids = {v["rule_id"] for v in fabrication_violations_box_girder(
        {**BOX_ANCHOR, "box_bottom_slab_mm": 180},
        {**ctx, "strand_count": 200})}
    assert "FAB-003" in ids


# ---------------------------------------------------------------- Composite
STEEL_ANCHOR = {
    "steel_depth_mm": 2000,
    "steel_top_flange_width_mm": 500,
    "steel_top_flange_thickness_mm": 30,
    "steel_web_thickness_mm": 20,
    "steel_bottom_flange_width_mm": 700,
    "steel_bottom_flange_thickness_mm": 50,
}


def test_composite_steel_i_matches_closed_form():
    sec = composite_i_girder_section_from_params(STEEL_ANCHOR)
    hs, bft, tft = 2.0, 0.5, 0.03
    tw, bfb, tfb = 0.02, 0.7, 0.05
    area = bft * tft + tw * (hs - tft - tfb) + bfb * tfb
    yb = (bfb * tfb * tfb / 2 + tw * (hs - tft - tfb) * (tfb + (hs - tft - tfb) / 2)
          + bft * tft * (hs - tft / 2)) / area
    assert sec["area_m2"] == pytest.approx(area, rel=1e-9)
    assert sec["y_bottom_m"] == pytest.approx(yb, rel=1e-9)
    assert sec["source"] == "PARAMETRIC_COMPOSITE"
    assert sec["material_kind"] == "STEEL"


def test_composite_fab_and_gate():
    ctx = {"span_m": 40.0}
    assert fabrication_violations_composite_i(STEEL_ANCHOR, ctx) == []
    ids = {v["rule_id"] for v in fabrication_violations_composite_i(
        {**STEEL_ANCHOR, "steel_web_thickness_mm": 12}, ctx)}
    assert "FAB-001" in ids
    ids = {v["rule_id"] for v in fabrication_violations_composite_i(
        {**STEEL_ANCHOR, "steel_top_flange_thickness_mm": 25,
         "steel_top_flange_width_mm": 750}, ctx)}
    assert "FAB-002" in ids
    gate = composite_solver_gate()
    assert gate["rule_id"] == "SOLVER-COMPOSITE-001"
    assert gate["severity"] == "HARD"


# ---------------------------------------------------------------- Pipeline
def _gene(grammar_id: str, **overrides) -> dict:
    """Gene hợp lệ tối thiểu cho từng grammar (đủ mọi khóa design_variables)."""
    base = {
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
            "girder_count": 4,
            "girder_spacing_mm": 2500,
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
    }[grammar_id]
    base.update(overrides)
    return base


def _l0_ids(grammar_id: str, **overrides) -> set:
    state = state_from_gene(_gene(grammar_id, **overrides), grammar_id=grammar_id)
    violations, _ = check_geometry(state)
    return {v["rule_id"] for v in violations}, state, violations


def test_pipeline_i_girder_l0_clean():
    ids, state, _ = _l0_ids("i_girder_parametric_v1")
    assert ids == set(), f"I-girder anchor phải sạch L0, còn: {ids}"
    assert state["design_variables"]["girder_catalog_id"] == "I-PARAM"


def test_pipeline_box_l0_clean_no_deck_geom_rules():
    ids, _, _ = _l0_ids("box_girder_parametric_v1")
    # Hộp: GEOM-001/002/003 không áp dụng; anchor sạch FAB hộp.
    assert "GEOM-001" not in ids
    assert "GEOM-003" not in ids
    assert ids == set(), f"Box anchor phải sạch L0, còn: {ids}"


def test_pipeline_composite_gated_before_solver():
    ids, _, violations = _l0_ids("composite_i_girder_parametric_v1")
    assert "SOLVER-COMPOSITE-001" in ids
    hard = [v for v in violations if v["severity"] == "HARD"]
    assert any(v["rule_id"] == "SOLVER-COMPOSITE-001" for v in hard)


def test_pipeline_i_girder_invalid_shape_is_fab000_not_crash():
    # bf=800 (trên lưới) < bfb=900 (trên lưới) — biên không dựng được → FAB-000
    ids, _, _ = _l0_ids("i_girder_parametric_v1",
                        top_flange_width_mm=800, bottom_flange_width_mm=900)
    assert "FAB-000" in ids


def test_super_t_behavior_unchanged():
    """Super-T v2 vẫn chạy đúng đường cũ (dispatch mới không phá hành vi)."""
    gene = {
        "girder_catalog_id": "ST-PARAM",
        "girder_count": 5,
        "girder_spacing_mm": 2400,
        "deck_slab_thickness_mm": 200,
        "girder_concrete_id": "C50",
        "deck_concrete_id": "C35",
        "diaphragm_layout_id": "DG-5",
        "prestress_layout_id": "PT-42",
        "girder_depth_mm": 1750,
        "top_flange_width_mm": 2050,
        "top_flange_thickness_mm": 120,
        "web_thickness_mm": 110,
        "bottom_bulb_width_mm": 350,
        "bottom_bulb_height_mm": 350,
    }
    state = state_from_gene(gene, grammar_id="super_t_parametric_v2")
    violations, geom = check_geometry(state)
    assert geom["section_source"] == "PARAMETRIC"
    assert {v["rule_id"] for v in violations} == set(), \
        f"Super-T anchor phải sạch như trước thay đổi: {violations}"
