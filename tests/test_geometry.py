import json
from pathlib import Path

from bridge_evolution.geometry import check_geometry

CASES = Path(__file__).resolve().parent.parent / "gold_cases" / "cases"


def load(name):
    with open(CASES / name, encoding="utf-8") as f:
        return json.load(f)


def rule_ids(violations):
    return {v["rule_id"] for v in violations}


def test_standard_case_clean():
    v, geom = check_geometry(load("GC-01_standard_pass.json"))
    assert v == []
    assert abs(geom["overhang_m"] - 0.5) < 1e-9


def test_zero_overhang_fails_geom001():
    v, _ = check_geometry(load("GC-02_geometry_invalid.json"))
    assert "GEOM-001" in rule_ids(v)


def test_thin_slab_fails_geom003():
    v, _ = check_geometry(load("GC-04_slab_too_thin.json"))
    assert "GEOM-003" in rule_ids(v)


def test_end_only_diaphragm_fails_cons001():
    state = load("GC-01_standard_pass.json")
    state["design_variables"]["diaphragm_layout_id"] = "DG-END-ONLY"
    v, _ = check_geometry(state)
    assert "CONS-001" in rule_ids(v)


def test_off_grid_spacing_fails_cons002():
    state = load("GC-01_standard_pass.json")
    state["design_variables"]["girder_spacing_mm"] = 2225  # không chia hết bước 50
    v, _ = check_geometry(state)
    assert "CONS-002" in rule_ids(v)
