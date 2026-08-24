"""Test MODULE P4 — surrogate sàng lọc học máy (model + assisted search)."""
import random

import numpy as np

from bridge_evolution.optimization.common import BudgetedEvaluator, gene_domains
from bridge_evolution.optimization.common import GENE_ORDER, gene_order
from bridge_evolution.surrogate import FeasibilitySurrogate, surrogate_assisted_search
from bridge_evolution.surrogate.model import (
    MIN_FIT_SAMPLES, _l0_hard_rejected, is_solver_run_record,
)


def _best_cost(history):
    """Min cost trong các record feasible, hoặc None nếu chưa có record feasible."""
    costs = [r["objectives"][0] for r in history if r["feasible"]]
    return min(costs) if costs else None


def test_fit_and_accuracy():
    # 30 solver calls thật + toàn bộ L0 rejects (seeded) → fit.
    rng = random.Random(0)
    domains = gene_domains()
    ev = BudgetedEvaluator(30, seed=0)
    while not ev.exhausted:
        ev.evaluate_gene({name: rng.choice(vals) for name, vals in domains.items()})
    assert ev.counters["solver_calls"] == 30

    surrogate = FeasibilitySurrogate(seed=0)
    surrogate.fit(ev.history)

    genes = [r["gene"] for r in ev.history]
    labels = [bool(r["feasible"]) for r in ev.history]
    preds = surrogate.predict_feasible_proba(genes) >= 0.5
    accuracy = sum(int(p == l) for p, l in zip(preds, labels)) / len(labels)
    assert accuracy > 0.75

    # predict_utilization luôn trả đúng độ dài, giá trị hữu hạn
    utils = surrogate.predict_utilization(genes)
    assert len(utils) == len(genes)


def test_assisted_search_runs():
    result = surrogate_assisted_search(budget=100, seed=7)

    assert result["algorithm"] == "surrogate_assisted"
    assert result["seed"] == 7
    # history gồm cả L0 reject; chỉ counter solver mới bị chặn bởi budget.
    assert result["counters"]["solver_calls"] == 100
    assert len(result["history"]) >= result["counters"]["solver_calls"]
    assert result["counters"]["proposals"] >= len(result["history"])
    assert result["counters"]["l0_rejected"] > 0

    # Mọi entry trong archive phải tương ứng một record feasible THẬT trong history
    by_case = {r["case_id"]: r for r in result["history"]}
    assert result["archive"].entries, "budget=100 phải tìm được ít nhất 1 phương án khả thi"
    for entry in result["archive"].entries:
        assert len(entry["objectives"]) == 3
        rec = by_case[entry["case_id"]]
        assert rec["feasible"] is True
        assert tuple(rec["objectives"]) == tuple(entry["objectives"])


def test_deterministic():
    r1 = surrogate_assisted_search(budget=60, seed=11)
    r2 = surrogate_assisted_search(budget=60, seed=11)
    assert _best_cost(r1["history"]) == _best_cost(r2["history"])
    assert r1["counters"] == r2["counters"]
    assert r1["history"] == r2["history"]
    assert r1["proposal_history"] == r2["proposal_history"]


# ====================================================================
# MODULE P4b — surrogate đa grammar: v2 (14 biến) được quét thật, v1 đóng băng.
#
# Đặc trưng của surrogate trước đây hard-code danh sách biến v1, nên 6 biến hình
# dạng của super_t_parametric_v2 không hề đi vào model và mutate() chỉ đảo 8 biến
# cũ. Các test dưới khóa: (1) đặc trưng phải nhạy với CẢ 6 biến hình dạng;
# (2) archive v2 chỉ chứa record feasible THẬT; (3) không vượt ngân sách và tái
# lập được; (4) đường v1 vẫn ra đúng gene 8 biến.
# ====================================================================
GRAMMAR_V1 = "super_t_simple_v1"
GRAMMAR_V2 = "super_t_parametric_v2"

#: 6 biến hình dạng mà v2 thêm vào so với v1 (AI tự thiết kế mặt cắt).
SHAPE_VARS = (
    "girder_depth_mm", "top_flange_width_mm", "top_flange_thickness_mm",
    "web_thickness_mm", "bottom_bulb_width_mm", "bottom_bulb_height_mm",
)

#: Ngân sách các ca v2 — CHỐT TRƯỚC, không suy từ kết quả.
V2_BUDGET = 80
V2_SEED = 5

V2_GENE = {
    "girder_catalog_id": "ST-PARAM", "girder_count": 6,
    "girder_spacing_mm": 2200, "deck_slab_thickness_mm": 200,
    "girder_concrete_id": "C45", "deck_concrete_id": "C35",
    "diaphragm_layout_id": "DG-5", "prestress_layout_id": "PT-42",
    "girder_depth_mm": 1750, "top_flange_width_mm": 2050,
    "top_flange_thickness_mm": 120, "web_thickness_mm": 110,
    "bottom_bulb_width_mm": 350, "bottom_bulb_height_mm": 350,
}

V1_GENE = {
    "girder_catalog_id": "ST-1750", "girder_count": 6,
    "girder_spacing_mm": 2200, "deck_slab_thickness_mm": 200,
    "girder_concrete_id": "C45", "deck_concrete_id": "C35",
    "diaphragm_layout_id": "DG-5", "prestress_layout_id": "PT-46",
}


def test_surrogate_v2_features_track_shape_vars():
    """Đặc trưng v2 phải suy từ gene_domains(v2): đổi biến hình dạng ⇒ đổi vector."""
    model = FeasibilitySurrogate(seed=0, grammar_id=GRAMMAR_V2)
    domains = gene_domains(GRAMMAR_V2)
    x0 = model._features(V2_GENE)
    assert np.all(np.isfinite(x0))

    for name in SHAPE_VARS:
        dom = domains[name]
        other = dom[-1] if V2_GENE[name] != dom[-1] else dom[0]
        x1 = model._features(dict(V2_GENE, **{name: other}))
        assert len(x1) == len(x0)
        assert not np.array_equal(x0, x1), f"bien {name} khong vao dac trung surrogate"

    # v1 giữ nguyên bố cục cũ (ít cột hơn) và vẫn dựng được đặc trưng hữu hạn.
    v1 = FeasibilitySurrogate(seed=0)
    x_v1 = v1._features(V1_GENE)
    assert len(x_v1) < len(x0)
    assert np.all(np.isfinite(x_v1))


def test_surrogate_v2_handles_impossible_shape():
    """Bộ tham số phi vật lý không được làm nổ surrogate — nhóm hình học điền 0."""
    model = FeasibilitySurrogate(seed=0, grammar_id=GRAMMAR_V2)
    # tf >= H: cánh trên dày hơn cả tiết diện -> SectionGeometryError ở L0.
    broken = dict(V2_GENE, girder_depth_mm=1500, top_flange_thickness_mm=170,
                  bottom_bulb_width_mm=450, web_thickness_mm=90)
    x = model._features(broken)
    assert len(x) == len(model._features(V2_GENE))
    assert np.all(np.isfinite(x))
    # Model chỉ XẾP HẠNG: proba luôn nằm trong [0, 1], kể cả khi chưa fit.
    proba = model.predict_feasible_proba([broken, V2_GENE])
    assert len(proba) == 2
    assert np.all((proba >= 0.0) & (proba <= 1.0))


def test_assisted_search_v2_runs_and_reproduces():
    """v2: mọi entry archive ứng record feasible thật, không vượt budget, tái lập."""
    r1 = surrogate_assisted_search(budget=V2_BUDGET, seed=V2_SEED,
                                   grammar_id=GRAMMAR_V2)
    assert r1["algorithm"] == "surrogate_assisted"
    assert r1["config"]["grammar_id"] == GRAMMAR_V2
    assert r1["counters"]["solver_calls"] <= V2_BUDGET
    assert r1["counters"]["l0_rejected"] > 0     # FAB-*/GEOM-* chặn miễn phí ở L0

    solver_records = [r for r in r1["history"] if r["solver_call_index"] is not None]
    assert r1["counters"]["solver_calls"] == len(solver_records)

    for rec in r1["history"]:
        assert list(rec["gene"]) == gene_order(GRAMMAR_V2)
        state = rec["design_state"]
        assert state["family"] == GRAMMAR_V2
        assert state["design_variables"]["girder_catalog_id"] == "ST-PARAM"
        for name in SHAPE_VARS:
            assert state["design_variables"][name] == rec["gene"][name]

    # Không gian hình dạng thật sự được quét (nếu hỏng thì là kết quả ÂM, không nới).
    for name in SHAPE_VARS:
        assert len({rec["gene"][name] for rec in r1["history"]}) > 1

    # Archive: nhãn feasible CHỈ đến từ đánh giá thật.
    by_case = {r["case_id"]: r for r in r1["history"]}
    assert r1["archive"].entries, "budget=80 phai tim duoc it nhat 1 phuong an kha thi"
    for entry in r1["archive"].entries:
        rec = by_case[entry["case_id"]]
        assert rec["feasible"] is True
        assert rec["solver_call_index"] is not None
        assert rec["cv"] == 0.0
        assert tuple(rec["objectives"]) == tuple(entry["objectives"])

    r2 = surrogate_assisted_search(budget=V2_BUDGET, seed=V2_SEED,
                                   grammar_id=GRAMMAR_V2)
    assert r1["counters"] == r2["counters"]
    assert r1["history"] == r2["history"]
    assert r1["proposal_history"] == r2["proposal_history"]


def test_assisted_search_v1_gene_unchanged():
    """Mở đường v2 không được làm gene v1 mọc thêm biến hình dạng."""
    r = surrogate_assisted_search(budget=30, seed=11)
    assert r["config"]["grammar_id"] == GRAMMAR_V1
    for rec in r["history"]:
        assert list(rec["gene"]) == GENE_ORDER
        assert rec["design_state"]["family"] == GRAMMAR_V1
        assert not set(SHAPE_VARS) & set(rec["gene"])


# ====================================================================
# MODULE P4c — TẬP FIT của surrogate (finding review S1)
#
# Reviewer đo: 98.9% (v2) / 91.1% (v1) record trong ev.history là L0_REJECTED,
# tức loại gene KHÔNG BAO GIỜ có mặt trong pool ứng viên vì pool đã prefilter L0.
# Fit trên đó là học lại đúng thứ prefilter đã loại miễn phí — lệch phân phối và
# gây hại. Các test dưới khóa: (1) fit CHỈ ăn record đã chạy solver; (2) chẩn
# đoán được ghi ra và khớp số; (3) ít mẫu / một lớp ⇒ chế độ hằng số, không nổ;
# (4) gene L0-fail nhận P = 0 theo LUẬT chứ không phải do model đoán.
# ====================================================================
def _fake_history(n_l0: int, n_solver: int, n_feasible: int, seed: int = 0,
                  grammar_id: str = GRAMMAR_V1) -> list[dict]:
    """History giả: n_l0 record L0_REJECTED + n_solver record ĐÃ chạy solver."""
    rng = random.Random(seed)
    domains = gene_domains(grammar_id)
    order = gene_order(grammar_id)

    def gene():
        return {name: rng.choice(domains[name]) for name in order}

    records = [{"gene": gene(), "feasible": False, "max_utilization": None,
                "solver_call_index": None, "solver_status": "NOT_RUN",
                "status": "L0_REJECTED"} for _ in range(n_l0)]
    records += [{"gene": gene(), "feasible": i < n_feasible,
                 "max_utilization": 0.5 + 0.01 * i,
                 "solver_call_index": i + 1, "solver_status": "SUCCESS",
                 "status": "SUCCESS"} for i in range(n_solver)]
    return records


def test_is_solver_run_record_reads_both_signals():
    """Cả solver_call_index lẫn solver_status đều đủ để nhận diện record đã chạy."""
    assert not is_solver_run_record(
        {"solver_call_index": None, "solver_status": "NOT_RUN"})
    assert not is_solver_run_record({})                     # thiếu khóa ⇒ chưa chạy
    assert is_solver_run_record({"solver_call_index": 7})
    assert is_solver_run_record(
        {"solver_call_index": None, "solver_status": "SUCCESS"})


def test_fit_uses_only_solver_run_records():
    """Số mẫu fit phải ĐÚNG bằng số record solver-run, phần L0 bị loại hết."""
    records = _fake_history(n_l0=400, n_solver=40, n_feasible=18)
    model = FeasibilitySurrogate(seed=0)
    model.fit(records)

    d = model.diagnostics
    assert d["records_seen"] == 440
    assert d["fit_samples"] == 40 == sum(is_solver_run_record(r) for r in records)
    assert d["records_dropped_not_solver_run"] == 400
    assert d["n_feasible"] == 18 and d["n_infeasible"] == 22
    assert d["feasible_rate"] == 18 / 40 and d["infeasible_rate"] == 22 / 40
    assert d["classifier_mode"] == "random_forest"
    assert d["utilization_samples"] == 40 and d["utilization_mode"] == "random_forest"
    assert d["n_fits"] == 1

    # Thêm 5000 record L0_REJECTED nữa KHÔNG được làm đổi tập fit.
    model2 = FeasibilitySurrogate(seed=0)
    model2.fit(records + _fake_history(5000, 0, 0, seed=1))
    assert model2.diagnostics["fit_samples"] == 40
    assert np.array_equal(model.predict_feasible_proba([V1_GENE]),
                          model2.predict_feasible_proba([V1_GENE]))


def test_fit_constant_mode_when_too_few_samples():
    """< MIN_FIT_SAMPLES mẫu ⇒ chế độ hằng số, KHÔNG raise và không đoán bừa."""
    records = _fake_history(n_l0=300, n_solver=6, n_feasible=3)
    model = FeasibilitySurrogate(seed=0)
    model.fit(records)              # không được raise

    d = model.diagnostics
    assert d["fit_samples"] == 6 < MIN_FIT_SAMPLES == d["min_fit_samples"]
    assert d["classifier_mode"] == "constant"
    assert d["utilization_mode"] == "constant"
    assert d["const_proba"] == 3 / 6

    genes = [V1_GENE, dict(V1_GENE, deck_slab_thickness_mm=220),
             dict(V1_GENE, prestress_layout_id="PT-42")]
    proba = model.predict_feasible_proba(genes)
    l0_ok = [p for g, p in zip(genes, proba)
             if not _l0_hard_rejected(GRAMMAR_V1, tuple(sorted(g.items())))]
    assert len(l0_ok) >= 2
    assert set(l0_ok) == {3 / 6}    # hằng số ⇒ không tác động vào xếp hạng pool
    assert list(model.predict_utilization(genes)) == [1.0] * len(genes)


def test_fit_constant_mode_when_single_label_class():
    """Chỉ còn một lớp nhãn ⇒ hằng số bằng đúng tỷ lệ lớp, không train."""
    for n_feasible, expected in ((0, 0.0), (20, 1.0)):
        model = FeasibilitySurrogate(seed=0)
        model.fit(_fake_history(n_l0=100, n_solver=20, n_feasible=n_feasible))
        d = model.diagnostics
        assert d["fit_samples"] == 20
        assert d["classifier_mode"] == "constant"
        assert d["const_proba"] == expected
        assert model.predict_feasible_proba([V1_GENE])[0] == expected

    # History rỗng / toàn L0: không có mẫu nào ⇒ giữ 0.5 trung tính.
    model = FeasibilitySurrogate(seed=0)
    model.fit([])
    assert model.diagnostics["fit_samples"] == 0
    assert model.diagnostics["const_proba"] == 0.5
    model.fit(_fake_history(n_l0=50, n_solver=0, n_feasible=0))
    assert model.diagnostics["fit_samples"] == 0
    assert model.diagnostics["records_dropped_not_solver_run"] == 50
    assert model.predict_feasible_proba([V1_GENE])[0] == 0.5


def test_l0_rejected_gene_scored_zero_by_rule():
    """Gene vi phạm HARD L0 nhận P = 0 theo LUẬT giải tích, không do model đoán."""
    broken = dict(V2_GENE, girder_depth_mm=1500, top_flange_thickness_mm=170,
                  bottom_bulb_width_mm=450, web_thickness_mm=90)
    assert _l0_hard_rejected(GRAMMAR_V2, tuple(sorted(broken.items())))
    assert not _l0_hard_rejected(GRAMMAR_V2, tuple(sorted(V2_GENE.items())))

    model = FeasibilitySurrogate(seed=0, grammar_id=GRAMMAR_V2)
    proba = model.predict_feasible_proba([broken, V2_GENE])
    assert proba[0] == 0.0      # luật L0
    assert proba[1] == 0.5      # chưa fit ⇒ hằng số trung tính


def test_surrogate_diagnostics_reported_and_consistent():
    """Kết quả tìm kiếm phải kèm surrogate_diagnostics và số liệu phải khớp."""
    r = surrogate_assisted_search(budget=60, seed=11)
    assert r["config"]["surrogate_fit_set"] == "solver_run_records_only"

    diag = r["surrogate_diagnostics"]
    assert diag["n_fits"] == len(diag["fit_log"]) >= 1
    assert diag["min_fit_samples"] == MIN_FIT_SAMPLES
    assert diag["last_fit"] == diag["fit_log"][-1]

    solver_run = [rec for rec in r["history"] if rec["solver_call_index"] is not None]
    assert len(solver_run) == r["counters"]["solver_calls"]
    for fit in diag["fit_log"]:
        # Mỗi lần fit: số mẫu = số solver call ĐÃ tiêu tại đúng thời điểm đó.
        assert fit["fit_samples"] == fit["solver_calls_at_fit"]
        assert fit["fit_samples"] <= len(solver_run)
        assert (fit["records_dropped_not_solver_run"]
                == fit["records_seen"] - fit["fit_samples"])
        assert fit["n_feasible"] + fit["n_infeasible"] == fit["fit_samples"]
        assert fit["records_seen"] > fit["fit_samples"]   # L0 reject bị loại thật
        assert fit["classifier_mode"] in ("constant", "random_forest")

    # Tái lập: cùng seed ⇒ cùng chẩn đoán (chẩn đoán không được chứa thời gian).
    r2 = surrogate_assisted_search(budget=60, seed=11)
    assert r2["surrogate_diagnostics"] == diag


# ====================================================================
# Khóa kết quả ĐO của ba cách xếp hạng (BRD-009).
# ====================================================================
def test_ranking_default_is_measured_best_not_reward():
    """Mặc định KHÔNG được quay lại 'reward' — bản đo được là tệ nhất (thua 5/6).

    Nguyên nhân: phương án tối ưu nằm đúng trên biên khả thi, nơi P(khả thi)
    thấp nhất, nên xếp hạng theo P(khả thi) kéo tìm kiếm rời khỏi vùng tối ưu.
    """
    import inspect

    from bridge_evolution.surrogate import surrogate_assisted_search

    default = inspect.signature(surrogate_assisted_search).parameters["ranking"].default
    assert default == "none", (
        "mặc định phải là cách xếp hạng có bằng chứng đo tốt nhất; đổi mặc định "
        "phải kèm số liệu mới trong docstring")


def test_all_ranking_modes_run_and_respect_budget():
    from bridge_evolution.surrogate import surrogate_assisted_search

    for ranking in ("none", "gate", "reward"):
        run = surrogate_assisted_search(budget=40, seed=42, ranking=ranking)
        assert run["counters"]["solver_calls"] <= 40
        assert run["config"]["ranking"] == ranking
        for entry in run["archive"].entries:
            assert entry["objectives"] is not None


def test_invalid_ranking_is_rejected():
    import pytest

    from bridge_evolution.surrogate import surrogate_assisted_search

    with pytest.raises(ValueError, match="ranking"):
        surrogate_assisted_search(budget=40, seed=42, ranking="khong-ton-tai")
