"""Kiểm thử mô-đun tối ưu hóa đa mục tiêu pymoo (pymoo_adapter.py)."""
import pytest

pytest.importorskip("pymoo")

from bridge_evolution.optimization.common import BudgetedEvaluator
from bridge_evolution.optimization.pymoo_adapter import BridgePymooProblem, run_pymoo_optimization


def test_bridge_pymoo_problem_setup():
    evaluator = BudgetedEvaluator(budget=10, seed=42)
    problem = BridgePymooProblem(evaluator=evaluator)

    assert problem.n_var == 8
    assert problem.n_obj == 3
    assert problem.n_ieq_constr == 1

    # Kiểm tra chuyển đổi vector sang gene
    x_zero = [0] * 8
    gene_0 = problem.vector_to_gene(x_zero)
    assert "girder_catalog_id" in gene_0
    assert "girder_count" in gene_0
    assert "deck_slab_thickness_mm" in gene_0


def test_run_pymoo_optimization_bounded_budget():
    budget = 15
    res = run_pymoo_optimization(budget=budget, pop_size=5, seed=42)

    assert res["algorithm"] == "pymoo_NSGA2"
    assert res["counters"]["solver_calls"] <= budget
    assert "pareto_solutions" in res
    assert "evaluator" in res
