"""Baseline 1 — Random Search: lấy mẫu đều trên grammar (mốc so sánh bắt buộc)."""
import random

from ..pareto import ParetoArchive
from .common import DEFAULT_GRAMMAR_ID, BudgetedEvaluator, gene_domains, gene_order


def random_search(budget: int, seed: int,
                  grammar_id: str = DEFAULT_GRAMMAR_ID) -> dict:
    rng = random.Random(seed)
    # Thứ tự rút số PHẢI theo gene_order: cùng seed ⇒ cùng lịch sử. Với v1 đây
    # đúng dãy GENE_ORDER cũ nên kết quả cũ không đổi một byte.
    order = gene_order(grammar_id)
    domains = gene_domains(grammar_id)
    ev = BudgetedEvaluator(budget, generation_action="RANDOM_SEARCH", seed=seed,
                           grammar_id=grammar_id)
    archive = ParetoArchive()
    # Guard chỉ có tác dụng nếu budget lớn hơn số gene L0-valid duy nhất.
    max_proposals = max(10_000, budget * 1000)

    while not ev.exhausted and ev.n_proposals < max_proposals:
        gene = {name: rng.choice(domains[name]) for name in order}
        rec = ev.evaluate_gene(gene)
        if rec and rec["feasible"]:
            archive.add(rec["case_id"], rec["objectives"], {"gene": rec["gene"]})

    config = {**ev.config, "algorithm": "random_search",
              "max_proposals": max_proposals}
    return {"algorithm": "random_search", "seed": seed, "grammar_id": grammar_id,
            "config": config,
            "counters": ev.counters, "history": ev.history,
            "proposal_history": ev.proposal_history, "archive": archive,
            "termination": "budget_exhausted" if ev.exhausted else "proposal_guard"}
