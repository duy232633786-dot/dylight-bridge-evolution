"""Baseline 2 — NSGA-II với constraint-domination (Deb 2002).

Cá thể infeasible xếp sau mọi cá thể feasible; giữa hai infeasible so bằng tổng
vi phạm HARD (cv). Gene = vector chỉ số vào miền grammar (action-mask tự nhiên:
không bao giờ sinh giá trị ngoài lưới).
"""
import math
import random

from ..pareto import ParetoArchive, dominates
from .common import BudgetedEvaluator, gene_domains, GENE_ORDER


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


def nsga2(budget: int, seed: int, pop_size: int = 40,
          p_crossover: float = 0.9) -> dict:
    rng = random.Random(seed)
    domains = gene_domains()
    sizes = [len(domains[k]) for k in GENE_ORDER]
    n_var = len(GENE_ORDER)
    p_mut = 1.0 / n_var

    ev = BudgetedEvaluator(budget, generation_action="NSGA2", seed=seed)
    archive = ParetoArchive()
    max_proposals = max(10_000, budget * 1000)

    def decode(idx_vec):
        return {k: domains[k][i] for k, i in zip(GENE_ORDER, idx_vec)}

    def evaluate(idx_vec):
        rec = ev.evaluate_gene(decode(idx_vec))
        if rec is None:
            return None
        if rec["feasible"]:
            archive.add(rec["case_id"], rec["objectives"], {"gene": rec["gene"]})
        return {**rec, "x": list(idx_vec)}

    def mutate(x):
        y = list(x)
        for j in range(n_var):
            if rng.random() < p_mut:
                if rng.random() < 0.5:  # bước ±1 trên lưới (local move)
                    y[j] = min(sizes[j] - 1, max(0, y[j] + rng.choice((-1, 1))))
                else:                   # reset ngẫu nhiên (exploration)
                    y[j] = rng.randrange(sizes[j])
        return y

    def crossover(a, b):
        if rng.random() > p_crossover:
            return list(a), list(b)
        c1, c2 = list(a), list(b)
        for j in range(n_var):
            if rng.random() < 0.5:
                c1[j], c2[j] = c2[j], c1[j]
        return c1, c2

    # --- khởi tạo
    pop = []
    seen = set()
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
        while (len(offspring) < pop_size and not ev.exhausted
               and ev.n_proposals < max_proposals):
            c1, c2 = crossover(tournament()["x"], tournament()["x"])
            for c in (mutate(c1), mutate(c2)):
                ind = evaluate(c)
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
        # Bơm cá thể ngẫu nhiên (random immigrants) thay 25% cuối để tiếp tục khám phá.
        if (ev.n_solver_calls == calls_before_gen and not ev.exhausted
                and ev.n_proposals < max_proposals):
            n_inject = max(1, pop_size // 4)
            for _ in range(n_inject):
                ind = evaluate([rng.randrange(s) for s in sizes])
                if ind:
                    pop[rng.randrange(len(pop))] = ind
                if ev.exhausted:
                    break

    config = {**ev.config, "algorithm": "nsga2", "pop_size": pop_size,
              "p_crossover": p_crossover, "p_mutation": p_mut,
              "max_proposals": max_proposals}
    return {"algorithm": "nsga2", "seed": seed, "pop_size": pop_size,
            "generations": generations, "config": config, "counters": ev.counters,
            "history": ev.history, "proposal_history": ev.proposal_history,
            "archive": archive,
            "termination": "budget_exhausted" if ev.exhausted else "proposal_guard"}
