"""Tests for the confirmatory grammar A/B trial (BRD-013, phân tích sửa ở BRD-015)."""

from __future__ import annotations

import json
from pathlib import Path
import statistics

import pytest

import experiments.run_grammar_ab_confirmatory as runner
from experiments.run_grammar_ab_confirmatory import (
    DEFAULT_PREREG,
    STOP_EXIT_CODE,
    ExperimentStopped,
    bootstrap_ci,
    check_seed_compliance,
    evaluate_primary_endpoint,
    main,
    run_single_arm,
)

_ROOT = Path(__file__).resolve().parent.parent

A4_ARM = {
    "arm_id": "A4_v1_restricted_girders",
    "grammar_id": "super_t_simple_v1",
    "domain_restriction": {"girder_count": [5, 6]},
    "search_path": "local_restricted_domain_path",
}


def _prereg() -> dict:
    return json.loads(DEFAULT_PREREG.read_text(encoding="utf-8"))


def test_preregistration_file_exists_and_has_required_schema():
    assert DEFAULT_PREREG.is_file()
    data = json.loads(DEFAULT_PREREG.read_text(encoding="utf-8"))
    assert data["task_id"] == "BRD-013"
    assert data["locked_before_running"] is True
    assert len(data["arms"]) == 4
    arm_ids = [a["arm_id"] for a in data["arms"]]
    assert "A1_v1_catalog" in arm_ids
    assert "A4_v1_restricted_girders" in arm_ids
    assert "A2_v2_shape_only" in arm_ids
    assert "A3_v2_full" in arm_ids
    assert data["budget"]["solver_calls_per_run"] == 600
    assert data["budget"]["n_seeds"] >= 20
    # Phép kiểm và ngưỡng đã KHÓA — runner phải tuân, không được tự nới.
    assert data["primary_endpoint"]["statistical_test"] == "paired_wilcoxon_and_bootstrap_ci"
    assert data["primary_endpoint"]["threshold_relative"] == 0.02
    assert data["primary_endpoint"]["confidence_level"] == 0.95


def test_bootstrap_ci_calculation():
    # Test positive improvement
    diffs = [2.5, 3.0, 2.8, 3.2, 2.1, 2.9, 3.5, 2.4, 2.7, 3.1]
    mean, low, high = bootstrap_ci(diffs, n_resamples=500, seed=42)
    assert 2.0 < mean < 3.5
    assert low < mean < high


def test_single_arm_execution_strictly_respects_budget():
    # Test on tiny budget of 10 solver calls
    res = run_single_arm(A4_ARM, "random_search", seed=42, budget=10)
    assert res["solver_calls"] == 10
    assert res["arm_id"] == "A4_v1_restricted_girders"
    assert res["algorithm"] == "random_search"


# ====================================================================
# BRD-015 — chặn CẢ LỚP lỗi "coi objectives là dict".
#
# Lỗi gốc: BudgetedEvaluator lưu record["objectives"] là TUPLE theo thứ tự
# OBJECTIVE_KEYS, nhưng runner viết item["objectives"]["relative_cost"] và gate
# bằng '"relative_cost" in item["objectives"]'. Điều kiện đó kiểm một CHUỖI có
# nằm trong tuple các SỐ hay không nên LUÔN False ⇒ mọi run báo feasible_count
# = 0 ⇒ n_paired_seeds = 0 ⇒ phán quyết "KHÔNG ĐẠT" sinh ra từ dữ liệu rỗng.
# Cùng lớp lỗi với pymoo_adapter đã vá ở BRD-009.
# ====================================================================


def test_evaluator_stores_objectives_as_tuple_not_dict():
    """Neo contract: đọc objectives bằng khóa chuỗi phải hỏng ngay tại đây."""
    from bridge_evolution.objectives import OBJECTIVE_KEYS
    from bridge_evolution.optimization import nsga2

    run = nsga2(60, seed=42)
    feasible = [r for r in run["history"] if r["feasible"]]
    assert feasible, "cần ít nhất một phương án khả thi để test có nghĩa"

    objectives = feasible[0]["objectives"]
    assert isinstance(objectives, tuple), (
        f"objectives phải là tuple theo OBJECTIVE_KEYS, đang là {type(objectives).__name__}")
    assert len(objectives) == len(OBJECTIVE_KEYS)
    # Chính điều kiện đã gây ra lỗi: nó phải là False, và code KHÔNG được dựa vào nó.
    assert ("relative_cost" in objectives) is False


def test_runner_never_reads_objectives_as_dict():
    """Neo tĩnh riêng cho lớp lỗi trên (test hành vi nằm ở test kế tiếp)."""
    source = (_ROOT / "experiments" / "run_grammar_ab_confirmatory.py").read_text(encoding="utf-8")
    code_only = chr(10).join(line for line in source.splitlines()
                             if not line.lstrip().startswith("#"))
    assert '["objectives"]["relative_cost"]' not in code_only, (
        "runner lại đọc objectives như dict — đây đúng lỗi BRD-015")
    assert 'OBJECTIVE_KEYS.index("relative_cost")' in source, (
        "runner phải lấy chỉ số cột chi phí từ OBJECTIVE_KEYS")


def test_summarizer_agrees_with_independent_count():
    """HÀNH VI: feasible_count/best_cost của chính run_single_arm phải khớp phép
    tính độc lập trên CÙNG MỘT history mà chính lần chạy đó sinh ra."""
    from bridge_evolution.objectives import OBJECTIVE_KEYS

    res = run_single_arm(A4_ARM, "nsga2", seed=42, budget=40, return_history=True)
    history = res["history"]
    assert history, "run phải sinh history"

    index = OBJECTIVE_KEYS.index("relative_cost")
    expected_costs = [float(r["objectives"][index]) for r in history
                      if r["feasible"] and r["objectives"] is not None]
    assert expected_costs, "cần dữ liệu khả thi để test có nghĩa"

    assert res["feasible_count"] == len(expected_costs)
    assert res["best_cost"] == pytest.approx(min(expected_costs))
    assert res["median_cost"] == pytest.approx(statistics.median(expected_costs))

    solver_records = [r for r in history if r.get("solver_call_index") is not None]
    assert res["solver_records"] == len(solver_records)
    assert res["solver_failed"] == sum(
        1 for r in solver_records if r.get("status") == "SOLVER_FAILED")
    assert res["solver_calls"] == 40 == len(solver_records)


def test_exact_seed_set_is_enforced_not_just_the_count():
    """Đủ SỐ LƯỢNG seed nhưng sai TẬP seed vẫn là chạy lệch giao thức."""
    prereg = _prereg()
    ok = check_seed_compliance(list(range(42, 62)), prereg)
    assert ok["seed_set_exact_match"] is True
    assert ok["seeds_executed"] == 20

    shifted = check_seed_compliance(list(range(43, 63)), prereg)
    assert shifted["seeds_executed"] == 20, "cùng số lượng seed"
    assert shifted["seed_set_exact_match"] is False
    assert "42" in shifted["seed_set_mismatch_detail"]

    short = check_seed_compliance([42, 43], prereg)
    assert short["seed_set_exact_match"] is False


# ====================================================================
# Điểm cuối chính đã KHÓA: paired Wilcoxon (chính) + bootstrap CI (phụ).
# H1 <=> p < 0.05 VÀ trung vị cải thiện >= 2.0%.
# ====================================================================


def test_primary_endpoint_accepts_h1_on_large_consistent_improvement():
    diffs = [2.5, 3.0, 2.8, 3.2, 2.1, 2.9, 3.5, 2.4, 2.7, 3.1]
    out = evaluate_primary_endpoint(diffs, _prereg(), n_resamples=500)
    assert out["wilcoxon"]["p_value"] < 0.05
    assert out["median_improvement_pct"] >= 2.0
    assert out["h1_supported"] is True
    assert out["verdict"].startswith("ĐẠT")
    assert out["primary_statistic"] == "median_improvement_pct"
    assert out["statistical_test"] == "paired_wilcoxon_and_bootstrap_ci"
    assert out["wilcoxon"]["zero_method"] and out["wilcoxon"]["alternative"]
    # Bootstrap CI vẫn được ghi nhưng chỉ là thống kê PHỤ.
    assert "PHU" in out["secondary_bootstrap"]["role"]
    assert len(out["secondary_bootstrap"]["bootstrap_ci_95_pct"]) == 2


def test_primary_endpoint_rejects_h1_on_noise_around_zero():
    diffs = [0.4, -0.3, 0.2, -0.5, 0.1, -0.2, 0.3, -0.4, 0.05, -0.1]
    out = evaluate_primary_endpoint(diffs, _prereg(), n_resamples=500)
    assert out["wilcoxon"]["p_value"] >= 0.05
    assert out["h1_supported"] is False
    assert out["verdict"].startswith("KHÔNG ĐẠT")


def test_primary_endpoint_rejects_significant_but_below_locked_threshold():
    """p < 0.05 nhưng trung vị < 2% vẫn KHÔNG ĐẠT — ngưỡng đã khóa, không nới."""
    diffs = [1.0, 1.1, 0.9, 1.2, 1.05, 0.95, 1.15, 0.85, 1.0, 1.1]
    out = evaluate_primary_endpoint(diffs, _prereg(), n_resamples=500)
    assert out["wilcoxon"]["p_value"] < 0.05
    assert out["median_improvement_pct"] < 2.0
    assert out["h1_supported"] is False
    assert out["verdict"].startswith("KHÔNG ĐẠT")


def test_primary_endpoint_stops_on_degenerate_or_empty_input():
    prereg = _prereg()
    with pytest.raises(ExperimentStopped):
        evaluate_primary_endpoint([], prereg, n_resamples=100)
    with pytest.raises(ExperimentStopped):
        evaluate_primary_endpoint([0.0] * 10, prereg, n_resamples=100)


# ====================================================================
# FAIL-CLOSED: thiếu dữ liệu / vi phạm invalidation ⇒ STOP.
# Không verdict, exit code khác 0 (PHYSICS_GATES: "thiếu dữ liệu là STOP").
# ====================================================================


def _fake_run_factory(*, improvement_pct=3.0, solver_calls=600, crash_rate=0.0,
                      bad_run=None):
    """run_single_arm giả lập, nhanh, dùng cho test hành vi của gate giao thức."""
    def _fake(arm, algorithm, seed, budget, *, return_history=False):
        base = 2100.0 + (seed - 42) * 0.5
        if arm["arm_id"] == "A2_v2_shape_only":
            cost = base * (1.0 - (improvement_pct + (seed % 3) * 0.05) / 100.0)
        else:
            cost = base
        calls = solver_calls
        rate = crash_rate
        if bad_run and (arm["arm_id"], algorithm, seed) == bad_run[:3]:
            calls = bad_run[3]
            if len(bad_run) > 4:
                rate = bad_run[4]
        n_records = 600
        n_failed = int(round(rate * n_records))
        return {
            "arm_id": arm["arm_id"], "algorithm": algorithm, "seed": seed,
            "solver_calls": calls, "l0_rejected": 0, "feasible_count": 5,
            "best_cost": cost, "median_cost": cost, "archive_size": 3,
            "solver_records": n_records, "solver_failed": n_failed,
            "crash_rate": rate,
        }
    return _fake


def _read_summary(out_dir: Path) -> tuple[dict, str]:
    path = out_dir / "summary.json"
    assert path.is_file(), "summary phải được ghi để kiểm toán được"
    raw = path.read_text(encoding="utf-8")
    return json.loads(raw), raw


def _assert_stopped(out_dir: Path) -> dict:
    data, raw = _read_summary(out_dir)
    assert data["status"] == "STOPPED"
    assert data.get("stop_reason"), "phải nêu rõ lý do dừng"
    assert "verdict" not in data, "STOP không được gán phán quyết"
    assert "verdict" not in raw
    assert "ĐẠT" not in raw, "file dừng không được chứa chuỗi trông như phán quyết"
    return data


def test_missing_seeds_stop_fail_closed(tmp_path):
    """2 seed thay vì 20 ⇒ exit != 0, summary không có verdict."""
    out_dir = tmp_path / "stop_seeds"
    code = main(["--seeds", "2", "--output-dir", str(out_dir)])
    assert code != 0
    assert code == STOP_EXIT_CODE
    data = _assert_stopped(out_dir)
    assert data["seeds_registered"] == 20
    assert data["seeds_executed"] == 2
    assert data["seed_compliance"].startswith("CHAY LECH")
    assert data["n_paired_seeds"] == 0


def test_unequal_solver_budget_invalidates_run_and_stops(tmp_path, monkeypatch):
    """UNEQUAL_SOLVER_BUDGET: một run có solver_calls != 600 ⇒ loại ⇒ STOP."""
    monkeypatch.setattr(
        runner, "run_single_arm",
        _fake_run_factory(bad_run=("A2_v2_shape_only", "nsga2", 50, 599)))
    out_dir = tmp_path / "stop_budget"
    code = main(["--output-dir", str(out_dir)])
    assert code == STOP_EXIT_CODE
    data = _assert_stopped(out_dir)
    compliance = data["protocol_compliance"]
    assert compliance["n_invalidated_runs"] == 1
    bad = compliance["invalidated_runs"][0]
    assert bad["seed"] == 50 and bad["solver_calls"] == 599
    assert bad["condition_id"] == "UNEQUAL_SOLVER_BUDGET"
    assert any(v["condition_id"] == "UNEQUAL_SOLVER_BUDGET" for v in compliance["violations"])
    # Run bị loại phải được đánh dấu ngay trong bảng runs.
    marked = [r for r in data["runs"] if r["invalidated"]]
    assert len(marked) == 1 and marked[0]["seed"] == 50


def test_solver_crash_rate_invalidates_experiment_and_stops(tmp_path, monkeypatch):
    """SOLVER_CRASH_RATE > 0.05 ⇒ INVALIDATE_EXPERIMENT ⇒ STOP."""
    monkeypatch.setattr(runner, "run_single_arm", _fake_run_factory(crash_rate=0.10))
    out_dir = tmp_path / "stop_crash"
    code = main(["--output-dir", str(out_dir)])
    assert code == STOP_EXIT_CODE
    data = _assert_stopped(out_dir)
    compliance = data["protocol_compliance"]
    assert compliance["crash_rate_threshold"] == 0.05
    assert compliance["crash_rate_experiment"] > 0.05
    assert any(v["condition_id"] == "SOLVER_CRASH_RATE" for v in compliance["violations"])


def test_unpaired_seed_stops_instead_of_declaring_h0(tmp_path, monkeypatch):
    """Một arm không có nghiệm khả thi ở một seed ⇒ thiếu cặp ⇒ STOP, không 'KHÔNG ĐẠT'."""
    base_fake = _fake_run_factory()

    def _fake(arm, algorithm, seed, budget, *, return_history=False):
        out = base_fake(arm, algorithm, seed, budget)
        if arm["arm_id"] == "A2_v2_shape_only" and algorithm == "nsga2" and seed == 57:
            out["best_cost"] = None
            out["median_cost"] = None
            out["feasible_count"] = 0
        return out

    monkeypatch.setattr(runner, "run_single_arm", _fake)
    out_dir = tmp_path / "stop_unpaired"
    code = main(["--output-dir", str(out_dir)])
    assert code == STOP_EXIT_CODE
    data = _assert_stopped(out_dir)
    assert data["n_paired_seeds"] == 19
    assert "19" in data["stop_reason"]


def test_complete_run_states_verdict_and_exits_zero(tmp_path, monkeypatch):
    """Đủ 20 seed, đúng ngân sách, cải thiện lớn nhất quán ⇒ ĐẠT và exit 0."""
    monkeypatch.setattr(runner, "run_single_arm", _fake_run_factory(improvement_pct=3.0))
    out_dir = tmp_path / "ok"
    code = main(["--output-dir", str(out_dir)])
    assert code == 0
    data, _ = _read_summary(out_dir)
    assert data["status"] == "COMPLETED"
    assert data["n_paired_seeds"] == 20
    assert data["verdict"].startswith("ĐẠT")
    comparison = data["comparison_A2_vs_A4_nsga2"]
    assert comparison["wilcoxon"]["p_value"] < 0.05
    assert comparison["median_improvement_pct"] >= 2.0
    assert comparison["h1_supported"] is True
    assert data["protocol_compliance"]["violations"] == []
    assert (out_dir / "summary.csv").is_file()


def test_no_improvement_states_h0_not_stop(tmp_path, monkeypatch):
    """Dữ liệu đủ nhưng không cải thiện ⇒ KHÔNG ĐẠT (đã kiểm), vẫn exit 0."""
    monkeypatch.setattr(runner, "run_single_arm", _fake_run_factory(improvement_pct=0.0))
    out_dir = tmp_path / "h0"
    code = main(["--output-dir", str(out_dir)])
    assert code == 0
    data, _ = _read_summary(out_dir)
    assert data["status"] == "COMPLETED"
    assert data["verdict"].startswith("KHÔNG ĐẠT")
    assert data["comparison_A2_vs_A4_nsga2"]["h1_supported"] is False


def test_seed_compliance_is_recorded(tmp_path, monkeypatch):
    """Số seed thực chạy phải được ghi và đối chiếu với pre-registration."""
    prereg = _prereg()
    assert prereg["budget"]["n_seeds"] == 20

    monkeypatch.setattr(runner, "run_single_arm", _fake_run_factory())
    out_dir = tmp_path / "compliance"
    assert main(["--output-dir", str(out_dir)]) == 0
    data, _ = _read_summary(out_dir)
    for field in ("seeds_registered", "seeds_executed", "seed_compliance"):
        assert field in data, f"summary thiếu {field}"
    assert data["seeds_registered"] == 20
    assert data["seeds_executed"] == 20
    assert data["seed_compliance"] == "khop giao thuc"
    assert data["protocol_compliance"]["solver_calls_required"] == 600


def test_stale_broken_result_is_not_citable():
    """Kết quả cũ sinh từ pipeline hỏng phải nhận ra được, không được trích dẫn."""
    stale = _ROOT / "experiments" / "results" / "confirmatory_ab_20260821T081427Z" / "summary.json"
    if not stale.exists():
        pytest.skip("không còn thư mục kết quả cũ")
    data = json.loads(stale.read_text(encoding="utf-8"))
    # Dấu hiệu tự mâu thuẫn: archive khác rỗng nhưng feasible_count = 0.
    broken = [r for r in data["runs"] if r["archive_size"] > 0 and r["feasible_count"] == 0]
    assert broken, "nếu file này đã được chạy lại thì cập nhật/xóa test này"
    assert data["comparison_A2_vs_A4_nsga2"]["n_paired_seeds"] == 0
