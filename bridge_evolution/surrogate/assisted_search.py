"""Surrogate-assisted search: sàng lọc học máy TRƯỚC khi tiêu ngân sách solver.

Hai lợi thế hợp lệ của thuật toán (không vi phạm trung thực ngân sách):
1. Prefilter L0 bằng check_geometry là MIỄN PHÍ — không mở solver, không tốn
   budget; gene fail L0 bị loại trước khi cân nhắc đánh giá thật.
2. Surrogate (FeasibilitySurrogate) chỉ XẾP HẠNG ứng viên trong pool; nhãn
   feasible duy nhất vẫn đến từ BudgetedEvaluator.evaluate_gene — không model
   nào được tự kết luận khả thi.
"""
import random

from ..optimization.common import BudgetedEvaluator, gene_domains, GENE_ORDER
from ..pareto import ParetoArchive
from .model import FeasibilitySurrogate


def surrogate_assisted_search(budget: int, seed: int, warmup: int = 120,
                              pool_size: int = 300, batch_size: int = 24,
                              retrain_every: int = 48) -> dict:
    """Tìm kiếm có surrogate hỗ trợ. Trả về result dict chuẩn của mọi thuật toán.

    Pha 1 (warmup): đánh giá thật min(warmup, budget//3) gene ngẫu nhiên đã qua
    prefilter L0, rồi fit surrogate trên toàn bộ lịch sử.
    Pha 2 (vòng lặp): sinh pool = 50% ngẫu nhiên + 50% đột biến từ archive,
    loại gene L0-fail và gene đã có trong cache (đều miễn phí), chấm điểm
    = P(feasible) − 0.3 × (cost_exact/3000) rồi đánh giá thật top batch_size;
    retrain surrogate sau mỗi retrain_every lần gọi solver mới.
    """
    rng = random.Random(seed)
    domains = gene_domains()
    ev = BudgetedEvaluator(budget, generation_action="SURROGATE_SEARCH", seed=seed)
    archive = ParetoArchive()
    model = FeasibilitySurrogate(seed)

    def random_gene() -> dict:
        return {name: rng.choice(vals) for name, vals in domains.items()}

    def submit(screened: dict) -> dict | None:
        """Đánh giá THẬT qua BudgetedEvaluator; record feasible → archive."""
        rec = ev.evaluate_prescreened(screened)
        if rec and rec["feasible"]:
            archive.add(rec["case_id"], rec["objectives"], {"gene": rec["gene"]})
        return rec

    def mutate(parent: dict) -> dict:
        """Đột biến 1–2 biến: bước ±1 trên lưới domain hoặc reset ngẫu nhiên."""
        child = dict(parent)
        for name in rng.sample(GENE_ORDER, rng.randint(1, 2)):
            dom = domains[name]
            i = dom.index(child[name]) if child[name] in dom else rng.randrange(len(dom))
            if rng.random() < 0.5:
                i = min(len(dom) - 1, max(0, i + rng.choice((-1, 1))))
            else:
                i = rng.randrange(len(dom))
            child[name] = dom[i]
        return child

    # --- Pha 1: warmup ngẫu nhiên (có prefilter L0 miễn phí)
    n_warm = min(warmup, budget // 3)
    attempts = 0
    while ev.n_solver_calls < n_warm and attempts < 500 * max(1, n_warm):
        attempts += 1
        gene = random_gene()
        screened = ev.prescreen_gene(gene)
        if screened["outcome"] != "READY":
            continue
        if submit(screened) is None:
            break
    model.fit(ev.history)
    calls_at_fit = ev.n_solver_calls

    # --- Pha 2: vòng lặp surrogate xếp hạng → đánh giá thật top batch.
    # Guard thoát sớm tính theo TỔNG số lần sinh ứng viên thất bại liên tiếp
    # (empty_rounds × pool_size) để không phụ thuộc pool_size — với pool nhỏ,
    # ngưỡng cố định 50 vòng có thể bỏ phí ngân sách (finding review P4).
    empty_rounds = 0
    while not ev.exhausted and empty_rounds * max(pool_size, 1) < 15000:
        # Nguồn cha mẹ cho nửa pool đột biến: archive → best feasible → (rỗng)
        parents = [e["payload"]["gene"] for e in archive.entries
                   if "gene" in e["payload"]]
        if not parents:
            feas = [r for r in ev.history if r["feasible"]]
            if feas:
                parents = [min(feas, key=lambda r: r["objectives"][0])["gene"]]

        candidates, seen = [], set()
        for k in range(pool_size):
            if parents and k % 2 == 1:      # 50% đột biến (khi có cha mẹ)
                gene = mutate(rng.choice(parents))
            else:                           # 50% ngẫu nhiên (khám phá)
                gene = random_gene()
            screened = ev.prescreen_gene(gene)
            if screened["outcome"] != "READY":
                continue
            h = screened["input_hash"]
            if h in seen:
                continue
            seen.add(h)
            candidates.append((gene, screened))

        if not candidates:
            empty_rounds += 1
            continue
        empty_rounds = 0

        # Điểm xếp hạng = P(feasible) − 0.3 × (cost_exact / 3000);
        # cost_exact tính giải tích từ hình học (compute_objectives, miễn phí)
        proba = model.predict_feasible_proba([c[0] for c in candidates])
        scores = [float(proba[i])
                  - 0.3 * (screened["cheap_objectives"][0] / 3000.0)
                  for i, (_, screened) in enumerate(candidates)]
        order = sorted(range(len(candidates)), key=lambda i: (-scores[i], i))

        for i in order[:batch_size]:
            if submit(candidates[i][1]) is None:
                break  # hết ngân sách

        if ev.n_solver_calls - calls_at_fit >= retrain_every:
            model.fit(ev.history)
            calls_at_fit = ev.n_solver_calls

    config = {**ev.config, "algorithm": "surrogate_assisted", "warmup": warmup,
              "pool_size": pool_size, "batch_size": batch_size,
              "retrain_every": retrain_every,
              "ranking": "P(feasible)-0.3*(cheap_cost/3000)"}
    return {"algorithm": "surrogate_assisted", "seed": seed, "config": config,
            "counters": ev.counters, "history": ev.history,
            "proposal_history": ev.proposal_history, "archive": archive,
            "termination": "budget_exhausted" if ev.exhausted else "candidate_pool_exhausted"}
