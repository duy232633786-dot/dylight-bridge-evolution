"""BRD-035: Multi-family contract — catalog markers + girder_count fencing."""
import json
from pathlib import Path

import pytest

from bridge_evolution.state import validate_design_state, new_state

ROOT = Path(__file__).resolve().parent.parent


def _base_state(family, design_variables, *, girder_concrete_id="C50",
                deck_concrete_id="C35"):
    from bridge_evolution.catalogs import load_grammar
    g = load_grammar(family)
    return {
        "family": family,
        "status": "CANDIDATE",
        "project_inputs": dict(g["project_inputs"]),
        "design_variables": dict(design_variables),
        "materials": {
            "girder_concrete_id": girder_concrete_id,
            "deck_concrete_id": deck_concrete_id,
            "prestressing_steel_id": g["fixed"]["prestressing_steel_id"],
        },
        "analysis": {
            "fidelity": g["fixed"]["fidelity"],
            "solver": g["fixed"]["solver"],
            "load_profile_id": g["fixed"]["load_profile_id"],
        },
        "constraints": {"rule_profile_id": g["fixed"]["rule_profile_id"]},
        "provenance": {"generation_action": "BRD035_TEST"},
    }


def _valid_design_vars(family):
    """Return minimal valid design_variables dict for each family."""
    common = {
        "girder_spacing_mm": 2450,
        "deck_slab_thickness_mm": 200,
        "diaphragm_layout_id": "DG-3",
        "prestress_layout_id": "PT-42",
    }
    if family == "super_t_parametric_v2":
        return {
            **common,
            "girder_catalog_id": "ST-PARAM", "girder_count": 5,
            "girder_depth_mm": 1750, "top_flange_width_mm": 2050,
            "top_flange_thickness_mm": 120, "web_thickness_mm": 110,
            "bottom_bulb_width_mm": 350, "bottom_bulb_height_mm": 300,
        }
    elif family == "i_girder_parametric_v1":
        return {
            **common,
            "girder_catalog_id": "I-PARAM", "girder_count": 5,
            "girder_depth_mm": 1800, "top_flange_width_mm": 1000,
            "top_flange_thickness_mm": 180, "web_thickness_mm": 200,
            "bottom_flange_width_mm": 650, "bottom_flange_thickness_mm": 300,
        }
    elif family == "box_girder_parametric_v1":
        return {
            **common,
            "girder_catalog_id": "BOX-PARAM", "girder_count": 1,
            "girder_spacing_mm": 12000, "deck_slab_thickness_mm": 250,
            "box_web_height_mm": 2400, "box_web_thickness_mm": 450,
            "box_bottom_width_mm": 6500, "box_bottom_slab_mm": 250,
        }
    elif family == "composite_i_girder_parametric_v1":
        return {
            **common,
            "prestress_layout_id": "PT-34",
            "girder_catalog_id": "CI-PARAM", "girder_count": 4,
            "steel_depth_mm": 2000, "steel_top_flange_width_mm": 500,
            "steel_top_flange_thickness_mm": 30, "steel_web_thickness_mm": 20,
            "steel_bottom_flange_width_mm": 700,
            "steel_bottom_flange_thickness_mm": 50,
        }
    raise ValueError(f"unknown family {family}")


ALL_PARAMETRIC_FAMILIES = [
    "super_t_parametric_v2",
    "i_girder_parametric_v1",
    "box_girder_parametric_v1",
    "composite_i_girder_parametric_v1",
]


class TestPositiveAllFamiliesBuild:
    @pytest.mark.parametrize("family", ALL_PARAMETRIC_FAMILIES)
    def test_valid_state_passes(self, family):
        dv = _valid_design_vars(family)
        gc = "C40" if family == "composite_i_girder_parametric_v1" else "C50"
        state = _base_state(family, dv, girder_concrete_id=gc)
        errors = validate_design_state(state)
        assert errors == [], f"{family} should be valid, got: {errors}"


class TestGirderCountOneRejectedForNonBox:
    @pytest.mark.parametrize("family", [
        "super_t_parametric_v2",
        "i_girder_parametric_v1",
        "composite_i_girder_parametric_v1",
    ])
    def test_girder_count_1_rejected(self, family):
        dv = _valid_design_vars(family)
        dv["girder_count"] = 1
        gc = "C40" if family == "composite_i_girder_parametric_v1" else "C50"
        state = _base_state(family, dv, girder_concrete_id=gc)
        errors = validate_design_state(state)
        assert errors, f"{family} must reject girder_count=1"
        assert any("girder_count" in e for e in errors)


class TestGirderCountZeroRejectedEveryFamily:
    @pytest.mark.parametrize("family", ALL_PARAMETRIC_FAMILIES)
    def test_girder_count_0_rejected(self, family):
        dv = _valid_design_vars(family)
        dv["girder_count"] = 0
        gc = "C40" if family == "composite_i_girder_parametric_v1" else "C50"
        state = _base_state(family, dv, girder_concrete_id=gc)
        errors = validate_design_state(state)
        assert errors, f"{family} must reject girder_count=0"
        assert any("girder_count" in e for e in errors)
