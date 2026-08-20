"""Test tầng chẩn đoán: vi phạm HARD → nước sửa trong miền grammar, không gọi solver."""
import copy
import json
from pathlib import Path

import pytest

from bridge_evolution.analysis import suggest_repairs
from bridge_evolution.evaluate import evaluate_candidate
from bridge_evolution.geometry import check_geometry
from bridge_evolution.optimization.common import gene_domains

CASES = Path(__file__).resolve().parent.parent / "gold_cases" / "cases"


def _load(name: str) -> dict:
    with open(CASES / name, encoding="utf-8") as f:
        return json.load(f)


def _state_and_result(name: str) -> tuple[dict, dict]:
    state = _load(name)
    return state, evaluate_candidate(state)


def test_serv001_repair():
    # GC-06: rẻ nhưng trượt SERV-001 (PT-38 thiếu nén trước)
    state, result = _state_and_result("GC-06_cheap_but_fails.json")
    repairs = suggest_repairs(state, result)
    assert repairs, "SERV-001 phải sinh ít nhất một nước sửa"
    first = repairs[0]
    assert first["variable"] == "prestress_layout_id"
    assert first["current"] == "PT-38"
    assert first["proposed"] == "PT-42"      # +1 bậc trên miền PT
    assert first["rule_id"] == "SERV-001"
    assert first["card_id"] == "KC-001"      # thẻ tri thức khớp mạnh nhất


def test_geom001_repair_is_valid():
    # GC-02: 6 dầm × 2400 mm → cánh hẫng = 0 → GEOM-001
    state, result = _state_and_result("GC-02_geometry_invalid.json")
    repairs = suggest_repairs(state, result)
    spacing = [r for r in repairs if r["variable"] == "girder_spacing_mm"]
    assert spacing, "GEOM-001 phải đề xuất quét girder_spacing_mm"
    # Quét giảm dần từ 2400: 2350/2300/2250 vẫn vi phạm, 2200 là giá trị đầu sạch
    assert spacing[0]["proposed"] == 2200

    fixed = copy.deepcopy(state)
    fixed["design_variables"]["girder_spacing_mm"] = spacing[0]["proposed"]
    violations, _ = check_geometry(fixed)
    assert violations == [], f"Nước sửa GEOM phải làm hình học sạch: {violations}"


def test_no_solver_calls(monkeypatch):
    # Đánh giá thật MỘT lần trước khi gài bẫy — suggest_repairs không được gọi solver
    state, result = _state_and_result("GC-06_cheap_but_fails.json")

    import bridge_evolution.evaluate as evaluate_mod
    import bridge_evolution.fe_adapter as fe_mod

    def boom(*args, **kwargs):
        raise AssertionError("suggest_repairs không được gọi solver/evaluate_candidate")

    monkeypatch.setattr(evaluate_mod, "evaluate_candidate", boom)
    monkeypatch.setattr(evaluate_mod, "run_analysis", boom)
    monkeypatch.setattr(fe_mod, "run_analysis", boom)

    repairs = suggest_repairs(state, result)
    assert repairs  # vẫn chẩn đoán được mà không đụng solver


@pytest.mark.parametrize("case_file", [
    "GC-02_geometry_invalid.json",   # GEOM-001
    "GC-03_capacity_fail.json",      # STR-001 + STR-002 + SERV-001
    "GC-04_slab_too_thin.json",      # GEOM-003
    "GC-05_solver_failure.json",     # SOLVER-001 (không sửa thiết kế)
    "GC-06_cheap_but_fails.json",    # SERV-001
])
def test_proposals_in_domain(case_file):
    state, result = _state_and_result(case_file)
    repairs = suggest_repairs(state, result)
    domains = gene_domains()
    for r in repairs:
        if r["rule_id"] == "SOLVER-001":
            # Lỗi dữ liệu catalog: chỉ báo người duyệt, không đề xuất biến nào
            assert r["variable"] is None and r["proposed"] is None
            assert r["rationale"]
        else:
            assert r["variable"] in domains
            assert r["proposed"] in domains[r["variable"]], \
                f"{r['variable']}={r['proposed']} ngoài miền grammar"


def test_schema_invalid_state_has_no_repairs_and_does_not_crash():
    state = _load("GC-01_standard_pass.json")
    del state["design_variables"]
    result = evaluate_candidate(state)
    assert result["status"] == "SCHEMA_INVALID"
    assert suggest_repairs(state, result) == []


def test_cli_diagnose_schema_invalid_does_not_crash(monkeypatch, capsys):
    from bridge_evolution import cli

    state = _load("GC-01_standard_pass.json")
    state["materials"]["girder_concrete_id"] = "C-KHONG-TON-TAI"
    monkeypatch.setattr(cli, "_load_state", lambda _path: state)

    assert cli.main(["diagnose", "unused.json"]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "SCHEMA_INVALID"
    assert payload["suggested_repairs"] == []
