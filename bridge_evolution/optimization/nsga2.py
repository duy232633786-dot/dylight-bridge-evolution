"""Baseline 2 — NSGA-II với constraint-domination (Deb 2002).

Cá thể infeasible xếp sau mọi cá thể feasible; giữa hai infeasible so bằng tổng
vi phạm HARD (cv). Gene = vector chỉ số vào miền grammar (action-mask tự nhiên:
không bao giờ sinh giá trị ngoài lưới).
"""
import math
import random

from ..pareto import ParetoArchive, dominates
from .common import DEFAULT_GRAMMAR_ID, BudgetedEvaluator, gene_domains, gene_order


def _c_dominates(a: dict, b: dict) -> bool:
    if a["cv"] == 0.0 and b["cv"] > 0.0:
        return True
    if a["cv"] > 0.0 and b["cv"] > 0.0:
        return a["cv"] < b["cv"]
    if a["cv"] == 0.0 and b["cv"] == 0.0:
        return dominates(a["objectives"], b["objectives"])
    return False


def _fast_nondominated_sort(pop: list[dict]) -> list[list[int]]:
    n = len(pop)
    S = [[] for _ in range(n)]
    counter = [0] * n
    fronts = [[]]
    for p in range(n):
        for q in range(n):
            if p == q:
                continue
            if _c_dominates(pop[p], pop[q]):
                S[p].append(q)
            elif _c_dominates(pop[q], pop[p]):
                counter[p] += 1
        if counter[p] == 0:
            fronts[0].append(p)
    i = 0
    while fronts[i]:
        nxt = []
        for p in fronts[i]:
            for q in S[p]:
                counter[q] -= 1
                if counter[q] == 0:
                    nxt.append(q)
        i += 1
        fronts.append(nxt)
    return fronts[:-1]


def _crowding(pop: list[dict], front: list[int]) -> dict[int, float]:
    dist = {i: 0.0 for i in front}
    feas = [i for i in front if pop[i]["objectives"] is not None]
    if len(feas) < 3:
        return {i: math.inf for i in front}
    n_obj = len(pop[feas[0]]["objectives"])
    for m in range(n_obj):
        order = sorted(feas, key=lambda i: pop[i]["objectives"][m])
        lo, hi = pop[order[0]]["objectives"][m], pop[order[-1]]["objectives"][m]
        dist[order[0]] = dist[order[-1]] = math.inf
        if hi - lo < 1e-12:
            continue
        for k in range(1, len(order) - 1):
            dist[order[k]] += (pop[order[k + 1]]["objectives"][m]
                               - pop[order[k - 1]]["objectives"][m]) / (hi - lo)
    return dist


#: Toán tử được hỗ trợ. ``legacy`` là bản gốc, đóng băng vì thí nghiệm grammar
#: A/B đã pre-register và ``experiments/run_grammar_ab._restricted_nsga2`` phải
#: cho lịch sử trùng khớp. ``repaired`` (BRD-059) sửa bốn lỗi đo được:
#:   1. quần thể khởi tạo/immigrant chỉ nhận cá thể qua L0 (legacy: 37–39/40
#:      cá thể ban đầu là L0-reject);
#:   2. khử trùng lặp gene (legacy: thế hệ ~50 chỉ còn 2 gene khác nhau/40);
#:   3. immigrant thay đúng phần đuôi quần thể đã xếp hạng (legacy thay chỉ số
#:      ngẫu nhiên, có thể xóa cá thể front 0, và không lọc L0);
#:   4. đột biến luôn đổi gene được chọn: reset chọn giá trị KHÁC giá trị cũ,
#:      bước ±1 phản xạ ở biên thay vì bị kẹp (legacy: 45,5% con giống cha).
#: L0-reject không tiêu solver call nên sửa 1 không đổi định nghĩa ngân sách.
OPERATORS = ("legacy", "repaired")


def _passes_l0(ind: dict | None) -> bool:
    """Record đã qua L0 và được solver đánh giá (kể cả lấy lại từ cache)."""
    return ind is not None and ind.get("solver_status") != "NOT_RUN"


def _mutate_vector(x: list[int], sizes: list[int], p_mut: float,
                   rng: random.Random, repaired: bool) -> list[int]:
    """Đột biến vector chỉ số; nửa bước ±1 (local), nửa reset (exploration).

    Legacy kẹp ±1 ở biên và reset có thể trúng lại giá trị cũ, nên gene "được
    chọn" nhiều khi không đổi. Repaired phản xạ ±1 ở biên và reset sang giá trị
    khác, nên mọi gene được chọn (miền > 1 giá trị) đều thật sự đổi. Thứ tự rút
    số của nhánh legacy giữ nguyên để lịch sử cũ tái lập từng byte.
    """
    y = list(x)
    for j in range(len(sizes)):
        if rng.random() < p_mut:
            if rng.random() < 0.5:  # bước ±1 trên lưới (local move)
                step = rng.choice((-1, 1))
                if not repaired:
                    y[j] = min(sizes[j] - 1, max(0, y[j] + step))
                elif sizes[j] > 1:
                    # Phản xạ ở biên: đang ở 0 mà bước −1 thì đi +1.
                    if not 0 <= y[j] + step < sizes[j]:
                        step = -step
                    y[j] += step
            elif not repaired:      # reset ngẫu nhiên (exploration)
                y[j] = rng.randrange(sizes[j])
            elif sizes[j] > 1:      # reset sang giá trị KHÁC giá trị cũ
                k = rng.randrange(sizes[j] - 1)
                y[j] = k if k < y[j] else k + 1
    return y


def nsga2(budget: int, seed: int, pop_size: int = 40,
          p_crossover: float = 0.9,
          grammar_id: str = DEFAULT_GRAMMAR_ID,
          operators: str = "legacy") -> dict:
    if operators not in OPERATORS:
        raise ValueError(f"operators phải thuộc {OPERATORS}, nhận {operators!r}")
    repaired = operators == "repaired"
    rng = random.Random(seed)
    # Chiều dài gene lấy từ grammar; p_mut = 1/n_var nên tự co giãn khi grammar
    # v2 thêm 6 biến hình dạng. Với v1, order == GENE_ORDER ⇒ hành vi không đổi.
    order = gene_order(grammar_id)
    domains = gene_domains(grammar_id)
    sizes = [len(domains[k]) for k in order]
    n_var = len(order)
    p_mut = 1.0 / n_var

    ev = BudgetedEvaluator(budget, generation_action="NSGA2", seed=seed,
                           grammar_id=grammar_id)
    archive = ParetoArchive()
    max_proposals = max(10_000, budget * 1000)
    # Mỗi thế hệ repaired được thử tối đa chừng này proposal để lấp offspring
    # không trùng; hết lượt thì chấp nhận lứa nhỏ hơn thay vì lặp vô hạn.
    max_attempts_per_generation = 50 * pop_size
    # Trần số lần rút ngẫu nhiên cho một immigrant (gene trùng không tăng
    # n_proposals nên cần guard riêng để không lặp vô hạn khi miền cạn).
    max_random_draws = 100_000

    def decode(idx_vec):
        return {k: domains[k][i] for k, i in zip(order, idx_vec)}

    def evaluate(idx_vec):
        rec = ev.evaluate_gene(decode(idx_vec))
        if rec is None:
            return None
        if rec["feasible"]:
            archive.add(rec["case_id"], rec["objectives"], {"gene": rec["gene"]})
        return {**rec, "x": list(idx_vec)}

    def mutate(x):
        return _mutate_vector(x, sizes, p_mut, rng, repaired)

    def crossover(a, b):
        if rng.random() > p_crossover:
            return list(a), list(b)
        c1, c2 = list(a), list(b)
        for j in range(n_var):
            if rng.random() < 0.5:
                c1[j], c2[j] = c2[j], c1[j]
        return c1, c2

    def budget_left():
        return not ev.exhausted and ev.n_proposals < max_proposals

    def random_l0_individual(taken: set):
        """Repaired: rút ngẫu nhiên tới khi gặp gene mới qua L0 (L0 miễn phí)."""
        draws = 0
        while budget_left() and draws < max_random_draws:
            draws += 1
            x = [rng.randrange(s) for s in sizes]
            if tuple(x) in taken:
                continue
            taken.add(tuple(x))
            ind = evaluate(x)
            if _passes_l0(ind):
                return ind
            if ind is None:
                return None
        return None

    # --- khởi tạo
    pop = []
    seen = set()
    if repaired:
        while len(pop) < pop_size and budget_left():
            ind = random_l0_individual(seen)
            if ind is None:
                break
            pop.append(ind)
    else:
        while (len(pop) < pop_size and not ev.exhausted
               and ev.n_proposals < max_proposals):
            x = [rng.randrange(s) for s in sizes]
            if tuple(x) in seen:
                continue
            seen.add(tuple(x))
            ind = evaluate(x)
            if ind:
                pop.append(ind)
    generations = 0
    duplicates_rejected = 0
    l0_rejected_offspring = 0

    # --- vòng tiến hóa
    while not ev.exhausted and pop and ev.n_proposals < max_proposals:
        calls_before_gen = ev.n_solver_calls
        fronts = _fast_nondominated_sort(pop)
        rank = {}
        crowd = {}
        for fi, front in enumerate(fronts):
            cd = _crowding(pop, front)
            for i in front:
                rank[i], crowd[i] = fi, cd[i]

        def tournament():
            i, j = rng.randrange(len(pop)), rng.randrange(len(pop))
            if rank[i] != rank[j]:
                return pop[i] if rank[i] < rank[j] else pop[j]
            return pop[i] if crowd[i] >= crowd[j] else pop[j]

        offspring = []
        taken = {tuple(ind["x"]) for ind in pop}
        attempts = 0
        while (len(offspring) < pop_size and not ev.exhausted
               and ev.n_proposals < max_proposals):
            if repaired:
                if attempts >= max_attempts_per_generation:
                    break
            c1, c2 = crossover(tournament()["x"], tournament()["x"])
            for c in (mutate(c1), mutate(c2)):
                if repaired:
                    attempts += 1
                    if tuple(c) in taken:
                        duplicates_rejected += 1
                        continue
                    taken.add(tuple(c))
                ind = evaluate(c)
                if repaired and ind is not None and not _passes_l0(ind):
                    l0_rejected_offspring += 1
                    continue
                if ind:
                    offspring.append(ind)
                if (len(offspring) >= pop_size or ev.exhausted
                        or ev.n_proposals >= max_proposals):
                    break

        union = pop + offspring
        fronts = _fast_nondominated_sort(union)
        new_pop = []
        for front in fronts:
            cd = _crowding(union, front)
            if len(new_pop) + len(front) <= pop_size:
                new_pop.extend(union[i] for i in front)
            else:
                rest = sorted(front, key=lambda i: cd[i], reverse=True)
                new_pop.extend(union[i] for i in rest[:pop_size - len(new_pop)])
                break
        pop = new_pop
        generations += 1

        # Chống kẹt ngân sách: quần thể hội tụ → toàn cache hit, không tiêu solver call.
        # Bơm cá thể ngẫu nhiên (random immigrants) để tiếp tục khám phá.
        if (ev.n_solver_calls == calls_before_gen and not ev.exhausted
                and ev.n_proposals < max_proposals):
            n_inject = max(1, pop_size // 4)
            if repaired:
                # new_pop xếp theo front rồi crowding giảm dần ⇒ đuôi là cá thể
                # kém nhất; chỉ thay đuôi, immigrant phải qua L0 và không trùng.
                taken = {tuple(ind["x"]) for ind in pop}
                for k in range(min(n_inject, len(pop))):
                    ind = random_l0_individual(taken)
                    if ind is None:
                        break
                    pop[len(pop) - 1 - k] = ind
            else:
                # Legacy (giữ nguyên để tái lập): thay chỉ số ngẫu nhiên.
                for _ in range(n_inject):
                    ind = evaluate([rng.randrange(s) for s in sizes])
                    if ind:
                        pop[rng.randrange(len(pop))] = ind
                    if ev.exhausted:
                        break

    config = {**ev.config, "algorithm": "nsga2", "pop_size": pop_size,
              "p_crossover": p_crossover, "p_mutation": p_mut,
              "max_proposals": max_proposals}
    result = {"algorithm": "nsga2", "seed": seed, "grammar_id": grammar_id,
              "pop_size": pop_size,
              "generations": generations, "config": config, "counters": ev.counters,
              "history": ev.history, "proposal_history": ev.proposal_history,
              "archive": archive,
              "termination": "budget_exhausted" if ev.exhausted else "proposal_guard"}
    if repaired:
        # Chỉ thêm khóa khi bật repaired để output legacy giữ nguyên từng byte.
        config["operators"] = operators
        config["max_attempts_per_generation"] = max_attempts_per_generation
        result["operator_diagnostics"] = {
            "duplicates_rejected": duplicates_rejected,
            "l0_rejected_offspring": l0_rejected_offspring,
            "final_population_unique_genes": len({tuple(i["x"]) for i in pop}),
            "final_population_l0_rejected": sum(1 for i in pop if not _passes_l0(i)),
        }
    return result
