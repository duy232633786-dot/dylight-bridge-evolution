"""Baseline 1 — Random Search: lấy mẫu đều trên grammar (mốc so sánh bắt buộc)."""
import random

from ..pareto import ParetoArchive
from .common import BudgetedEvaluator, gene_domains


def random_search(budget: int, seed: int) -> dict:
    rng = random.Random(seed)
    domains = gene_domains()
    ev = BudgetedEvaluator(budget, generation_action="RANDOM_SEARCH", seed=seed)
    archive = ParetoArchive()
    # Guard chỉ có tác dụng nếu budget lớn hơn số gene L0-valid duy nhất.
    max_proposals = max(10_000, budget * 1000)

    while not ev.exhausted and ev.n_proposals < max_proposals:
        gene = {name: rng.choice(vals) for name, vals in domains.items()}
        rec = ev.evaluate_gene(gene)
        if rec and rec["feasible"]:
            archive.add(rec["case_id"], rec["objectives"], {"gene": rec["gene"]})

    config = {**ev.config, "algorithm": "random_search",
              "max_proposals": max_proposals}
    return {"algorithm": "random_search", "seed": seed, "config": config,
            "counters": ev.counters, "history": ev.history,
            "proposal_history": ev.proposal_history, "archive": archive,
            "termination": "budget_exhausted" if ev.exhausted else "proposal_guard"}
