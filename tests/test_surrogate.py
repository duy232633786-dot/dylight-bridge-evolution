"""Test MODULE P4 — surrogate sàng lọc học máy (model + assisted search)."""
import random

from bridge_evolution.optimization.common import BudgetedEvaluator, gene_domains
from bridge_evolution.surrogate import FeasibilitySurrogate, surrogate_assisted_search


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
