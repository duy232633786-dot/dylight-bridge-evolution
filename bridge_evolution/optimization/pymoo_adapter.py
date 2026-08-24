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

from pymoo.core.termination import Termination

from ..objectives import OBJECTIVE_KEYS
from ..pareto import ParetoArchive
from .common import DEFAULT_GRAMMAR_ID, BudgetedEvaluator, gene_domains, gene_order

#: Điểm phạt khi không có objective thật (hết ngân sách / bị L0 loại / solver lỗi).
PENALTY = 1e6


class BridgePymooProblem(ElementwiseProblem):
    """Lớp bài toán tối ưu hóa đa mục tiêu cầu tương thích chuẩn pymoo.

    Mục tiêu (Minimize 3 objectives) — thứ tự BẮT BUỘC theo
    ``bridge_evolution.objectives.OBJECTIVE_KEYS`` để mọi công cụ hạ nguồn
    (hypervolume, đối chiếu oracle, báo cáo) dùng chung một quy ước:
    - F[0]: relative_cost
    - F[1]: material_mass_t
    - F[2]: embodied_carbon_kgCO2e

    Ràng buộc (1 constraint G[0] <= 0):
    - G[0]: Điểm vi phạm ràng buộc cứng (hard_violation_score). G[0] == 0 là PASS.
    """

    def __init__(
        self,
        evaluator: BudgetedEvaluator,
        grammar_id: str = DEFAULT_GRAMMAR_ID,
        **kwargs: Any,
    ) -> None:
        self.evaluator = evaluator
        self.grammar_id = grammar_id
        self.domains = gene_domains(grammar_id)
        # Biến lấy theo grammar chứ không theo hằng 8 biến v1: grammar v2 có
        # n_var = 14 (8 biến v1 + 6 biến hình dạng mặt cắt).
        self.var_names = gene_order(grammar_id)

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
            out["F"] = [PENALTY] * len(OBJECTIVE_KEYS)
            out["G"] = [100.0]
            return

        # Trích xuất mục tiêu THẬT. BudgetedEvaluator lưu record["objectives"] là
        # TUPLE theo đúng thứ tự OBJECTIVE_KEYS, và chỉ bản ghi đã chạy solver mới
        # có giá trị (None với L0-reject / schema-invalid). Bản trước gate theo
        # res["status"] in ("FEASIBLE", "INFEASIBLE") — hai giá trị KHÔNG TỒN TẠI
        # trong enum status của contract — nên nhánh này là nhánh chết và F luôn
        # bằng PENALTY: pymoo tối ưu một hàm hằng số và báo cáo 1e6 như thể đó là
        # chi phí đã tính (review lõi BRD-009, mức CRITICAL).
        objs = res.get("objectives")
        if objs is not None:
            f_values = [float(v) for v in objs]
        else:
            f_values = [PENALTY] * len(OBJECTIVE_KEYS)

        # Tính điểm vi phạm ràng buộc cứng (G <= 0 là hợp lệ)
        if res.get("feasible") is True:
            g1 = 0.0
        else:
            # Tính tổng margin vi phạm các quy tắc HARD
            violations = res.get("violations", [])
            hard_v = [v for v in violations if v.get("severity") == "HARD"]
            if hard_v:
                g1 = sum(max(0.01, float(v.get("margin", 1.0))) for v in hard_v)
            else:
                g1 = 10.0

        out["F"] = f_values
        out["G"] = [g1]


def l0_valid_initial_population(problem: "BridgePymooProblem", pop_size: int,
                                seed: int, max_draws: int = 20_000) -> np.ndarray:
    """Quần thể khởi tạo ưu tiên cá thể QUA ĐƯỢC L0 — miễn phí ngân sách solver.

    Lý do: với ``IntegerRandomSampling`` thuần, xác suất một cá thể ngẫu nhiên
    qua L0 chỉ ~5% (grammar v1) và ~0.4% (v2). Khi quần thể khởi tạo KHÔNG có
    cá thể hợp lệ nào, mọi cá thể cùng nhận F = PENALTY nên áp lực chọn lọc gần
    như biến mất và NSGA-II có thể không bao giờ thoát ra: đã tái hiện với
    pop_size=20, seed=42 — 0/308 ứng viên qua L0 và 0 lần gọi solver trên ngân
    sách 200.

    ``check_geometry`` là cấp L0 nên việc sàng này KHÔNG tiêu ngân sách solver và
    không phải lợi thế không công bằng — nó chính là safety shield mà mọi thuật
    toán khác trong repo đều dùng ở bước đề xuất.
    """
    rng = np.random.default_rng(seed)
    sizes = [len(d) for d in problem.domain_lists]
    rows: list[list[int]] = []
    seen: set[tuple[int, ...]] = set()
    draws = 0
    while len(rows) < pop_size and draws < max_draws:
        draws += 1
        cand = [int(rng.integers(0, size)) for size in sizes]
        key = tuple(cand)
        if key in seen:
            continue
        screened = problem.evaluator.prescreen_gene(problem.vector_to_gene(cand))
        if screened["outcome"] in ("READY", "CACHE_HIT"):
            seen.add(key)
            rows.append(cand)
    # Không đủ cá thể hợp lệ thì bù ngẫu nhiên: thà quần thể yếu còn hơn treo.
    while len(rows) < pop_size:
        rows.append([int(rng.integers(0, size)) for size in sizes])
    return np.array(rows, dtype=int)


class SolverBudgetTermination(Termination):
    """Dừng theo NGÂN SÁCH SOLVER THẬT, không theo số thế hệ.

    ``("n_gen", n)`` tính như thể mỗi lần pymoo gọi ``_evaluate`` là một lần gọi
    solver. Thực tế L0-reject và cache hit vẫn chiếm một slot đánh giá của pymoo
    nhưng KHÔNG tiêu ngân sách, nên pymoo dừng khi mới tiêu một phần ngân sách —
    arm pymoo tiêu ít hơn hẳn các arm khác và mọi so sánh "cùng solver budget"
    trở nên vô hiệu (review lõi BRD-009, mức MAJOR).
    """

    def __init__(self, evaluator: BudgetedEvaluator, max_gen: int,
                 stall_gens: int = 25) -> None:
        super().__init__()
        self.evaluator = evaluator
        self.max_gen = max(1, int(max_gen))
        self.stall_gens = max(1, int(stall_gens))
        self._calls_at_last_progress = evaluator.n_solver_calls
        self._stalled = 0
        self.reason = "running"

    def _update(self, algorithm: Any) -> float:
        if self.evaluator.budget <= 0:
            self.reason = "budget_exhausted"
            return 1.0

        calls = self.evaluator.n_solver_calls
        if calls > self._calls_at_last_progress:
            self._calls_at_last_progress = calls
            self._stalled = 0
        else:
            self._stalled += 1

        by_budget = calls / self.evaluator.budget
        if by_budget >= 1.0:
            self.reason = "budget_exhausted"
            return 1.0
        # Đình trệ: quần thể hội tụ nên mọi ứng viên đều trùng cache hoặc bị L0
        # loại; ngân sách KHÔNG THỂ tiêu hết. Dừng và nói thật lý do thay vì
        # quay vòng vô ích.
        if self._stalled >= self.stall_gens:
            self.reason = "stalled_no_new_solver_calls"
            return 1.0
        if (algorithm.n_gen or 0) >= self.max_gen:
            self.reason = "generation_guard"
            return 1.0
        return float(min(0.999, by_budget))


def run_pymoo_optimization(
    budget: int = 600,
    pop_size: int = 40,
    seed: int = 42,
    grammar_id: str = DEFAULT_GRAMMAR_ID,
) -> dict[str, Any]:
    """Chạy tối ưu hóa đa mục tiêu với NSGA-II qua pymoo trên cùng ngân sách solver."""
    evaluator = BudgetedEvaluator(
        budget=budget,
        generation_action="PYMOO_NSGA2",
        seed=seed,
        grammar_id=grammar_id,
    )
    problem = BridgePymooProblem(evaluator=evaluator, grammar_id=grammar_id)

    # Trần thế hệ chỉ là VAN AN TOÀN chống lặp vô hạn khi ngân sách không thể
    # tiêu hết (ví dụ grammar v2: gần như mọi ứng viên bị L0 loại, hoặc pymoo
    # sinh trùng lặp liên tục). Điều kiện dừng THẬT là ngân sách solver.
    max_gen = max(50, budget * 50 // max(1, pop_size) + 100)
    termination = SolverBudgetTermination(evaluator, max_gen=max_gen)

    algorithm = NSGA2(
        pop_size=pop_size,
        sampling=l0_valid_initial_population(problem, pop_size, seed),
        crossover=SBX(prob=0.9, eta=15, repair=RoundingRepair(), vtype=int),
        mutation=PM(prob=0.2, eta=20, repair=RoundingRepair(), vtype=int),
        eliminate_duplicates=True,
    )

    res = minimize(
        problem,
        algorithm,
        termination,
        seed=seed,
        verbose=False,
        # BẮT BUỘC: pymoo mặc định deep-copy termination, khiến bản sao trỏ vào
        # một BudgetedEvaluator KHÁC — bộ đếm ngân sách không bao giờ nhúc nhích
        # và điều kiện dừng theo ngân sách trở nên vô hiệu (đã tái hiện: budget
        # 200 chỉ tiêu 0 lần gọi solver rồi dừng vì cờ đình trệ giả).
        copy_termination=False,
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
                    "objectives": dict(zip(
                        OBJECTIVE_KEYS, (float(v) for v in f_vals))),
                })

    # Archive dựng từ BẢN GHI THẬT của evaluator, không từ F nội bộ của pymoo:
    # đây mới là thứ so sánh được với các thuật toán khác và với oracle.
    archive = ParetoArchive()
    for record in evaluator.history:
        if record["feasible"] and record["objectives"] is not None:
            archive.add(record["case_id"], record["objectives"],
                        {"gene": record["gene"]})

    config = {**evaluator.config, "algorithm": "pymoo_NSGA2",
              "pop_size": pop_size, "max_gen": max_gen}
    return {
        "algorithm": "pymoo_NSGA2",
        "seed": seed,
        "grammar_id": grammar_id,
        "config": config,
        "counters": evaluator.counters,
        "history": evaluator.history,
        "proposal_history": evaluator.proposal_history,
        "archive": archive,
        "termination": ("budget_exhausted" if evaluator.exhausted
                        else termination.reason),
        "pareto_solutions_count": len(pareto_solutions),
        "pareto_solutions": pareto_solutions,
        "evaluator": evaluator,
    }
