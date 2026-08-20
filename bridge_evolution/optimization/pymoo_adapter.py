"""Adapter kết nối DYLIGHT Bridge Evolution với framework pymoo.

Hỗ trợ tối ưu hóa đa mục tiêu với NSGA-II / NSGA-III / MOEA/D,
đồng bộ chuẩn mực xử lý ràng buộc cứng (Constraint Violation g(x) <= 0)
và ngân sách gọi solver (BudgetedEvaluator).
"""
from __future__ import annotations

from typing import Any

import numpy as np
from pymoo.algorithms.moo.nsga2 import NSGA2
from pymoo.core.problem import ElementwiseProblem
from pymoo.operators.crossover.sbx import SBX
from pymoo.operators.mutation.pm import PM
from pymoo.operators.repair.rounding import RoundingRepair
from pymoo.operators.sampling.rnd import IntegerRandomSampling
from pymoo.optimize import minimize

from .common import BudgetedEvaluator, GENE_ORDER, gene_domains


class BridgePymooProblem(ElementwiseProblem):
    """Lớp bài toán tối ưu hóa đa mục tiêu cầu tương thích chuẩn pymoo.

    Mục tiêu (Minimize 3 objectives):
    - F[0]: Chi phí tương đối (relative_cost)
    - F[1]: Phát thải carbon (embodied_carbon - kgCO2e)
    - F[2]: Khối lượng vật liệu (material_mass - tấn)

    Ràng buộc (1 constraint G[0] <= 0):
    - G[0]: Điểm vi phạm ràng buộc cứng (hard_violation_score). G[0] == 0 là PASS.
    """

    def __init__(
        self,
        evaluator: BudgetedEvaluator,
        grammar_id: str = "super_t_simple_v1",
        **kwargs: Any,
    ) -> None:
        self.evaluator = evaluator
        self.grammar_id = grammar_id
        self.domains = gene_domains(grammar_id)
        self.var_names = list(GENE_ORDER)

        # Số lựa chọn rời rạc cho từng biến
        self.domain_lists = [list(self.domains[name]) for name in self.var_names]
        n_vars = len(self.var_names)

        xl = np.zeros(n_vars, dtype=int)
        xu = np.array([len(d) - 1 for d in self.domain_lists], dtype=int)

        super().__init__(
            n_var=n_vars,
            n_obj=3,
            n_ieq_constr=1,
            xl=xl,
            xu=xu,
            vtype=int,
            **kwargs,
        )

    def vector_to_gene(self, x: np.ndarray) -> dict[str, Any]:
        """Chuyển đổi vector chỉ số nguyên sang dict gene biến thiết kế."""
        gene = {}
        for i, name in enumerate(self.var_names):
            idx = int(np.clip(round(float(x[i])), 0, len(self.domain_lists[i]) - 1))
            gene[name] = self.domain_lists[i][idx]
        return gene

    def _evaluate(self, x: np.ndarray, out: dict[str, Any], *args: Any, **kwargs: Any) -> None:
        gene = self.vector_to_gene(x)
        res = self.evaluator.evaluate_gene(gene)

        if res is None:
            # Ngân sách đã hết hoặc bị chặn
            out["F"] = [1e6, 1e6, 1e6]
            out["G"] = [100.0]
            return

        # Trích xuất 3 mục tiêu
        objs = res.get("objectives")
        if objs and res.get("status") in ("FEASIBLE", "INFEASIBLE"):
            f1 = float(objs["relative_cost"])
            f2 = float(objs["embodied_carbon"])
            f3 = float(objs["material_mass"])
        else:
            # Điểm phạt lớn khi phương án bị chặn hoặc lỗi
            f1, f2, f3 = 1e6, 1e6, 1e6

        # Tính điểm vi phạm ràng buộc cứng (G <= 0 là hợp lệ)
        # Trong DYLIGHT, nếu status == FEASIBLE -> G = 0; nếu INFEASIBLE/REJECT -> G > 0
        if res.get("status") == "FEASIBLE" or res.get("feasible") is True:
            g1 = 0.0
        else:
            # Tính tổng margin vi phạm các quy tắc HARD
            violations = res.get("violations", [])
            hard_v = [v for v in violations if v.get("severity") == "HARD"]
            if hard_v:
                g1 = sum(max(0.01, float(v.get("margin", 1.0))) for v in hard_v)
            else:
                g1 = 10.0

        out["F"] = [f1, f2, f3]
        out["G"] = [g1]


def run_pymoo_optimization(
    budget: int = 600,
    pop_size: int = 40,
    seed: int = 42,
    grammar_id: str = "super_t_simple_v1",
) -> dict[str, Any]:
    """Chạy tối ưu hóa đa mục tiêu với NSGA-II qua pymoo trên cùng ngân sách solver."""
    evaluator = BudgetedEvaluator(
        budget=budget,
        generation_action="PYMOO_NSGA2",
        seed=seed,
        grammar_id=grammar_id,
    )
    problem = BridgePymooProblem(evaluator=evaluator, grammar_id=grammar_id)

    # Ước lượng số thế hệ dựa trên pop_size và budget
    n_gen = max(5, budget // pop_size + 2)

    algorithm = NSGA2(
        pop_size=pop_size,
        sampling=IntegerRandomSampling(),
        crossover=SBX(prob=0.9, eta=15, repair=RoundingRepair(), vtype=int),
        mutation=PM(prob=0.2, eta=20, repair=RoundingRepair(), vtype=int),
        eliminate_duplicates=True,
    )

    res = minimize(
        problem,
        algorithm,
        ("n_gen", n_gen),
        seed=seed,
        verbose=False,
    )

    # Lọc các nghiệm khả thi (G <= 0) từ kết quả Pareto
    pareto_solutions = []
    if res.X is not None and len(res.X) > 0:
        for idx in range(len(res.X)):
            g_val = res.G[idx][0] if res.G is not None else 0.0
            if g_val <= 1e-6:
                gene = problem.vector_to_gene(res.X[idx])
                f_vals = res.F[idx]
                pareto_solutions.append({
                    "gene": gene,
                    "objectives": {
                        "relative_cost": float(f_vals[0]),
                        "embodied_carbon": float(f_vals[1]),
                        "material_mass": float(f_vals[2]),
                    },
                })

    return {
        "algorithm": "pymoo_NSGA2",
        "seed": seed,
        "counters": evaluator.counters,
        "pareto_solutions_count": len(pareto_solutions),
        "pareto_solutions": pareto_solutions,
        "evaluator": evaluator,
    }
