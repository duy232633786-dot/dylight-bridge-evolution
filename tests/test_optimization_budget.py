"""Hồi quy fairness/reproducibility cho optimization budget."""
from bridge_evolution.optimization import nsga2, random_search
from bridge_evolution.optimization.common import BudgetedEvaluator


VALID_GENE = {
    "girder_catalog_id": "ST-1750",
    "girder_count": 6,
    "girder_spacing_mm": 2200,
    "deck_slab_thickness_mm": 200,
    "girder_concrete_id": "C45",
    "deck_concrete_id": "C35",
    "diaphragm_layout_id": "DG-5",
    "prestress_layout_id": "PT-46",
}


def test_budget_counts_only_actual_solver_and_tracks_every_outcome():
    ev = BudgetedEvaluator(1, generation_action="TEST", seed=314)

    invalid = dict(VALID_GENE, girder_count=5)
    l0 = ev.evaluate_gene(invalid)
    assert l0["status"] == "GEOMETRY_INVALID"
    assert l0["solver_status"] == "NOT_RUN"
    assert l0["solver_call_index"] is None
    assert ev.n_solver_calls == 0

    # Cùng hash trả cache, không bị tính lại thành L0 reject hay solver call.
    assert ev.evaluate_gene(invalid) is l0
    assert ev.n_cache_hits == 1
    assert ev.n_l0_rejected == 1

    solved = ev.evaluate_gene(VALID_GENE)
    assert solved["solver_status"] != "NOT_RUN"
    assert solved["solver_call_index"] == 1
    assert ev.exhausted
    assert len(solved["input_hash"]) == 64
    assert solved["provenance"]["random_seed"] == 314
    assert solved["design_state"]["provenance"]["random_seed"] == 314

    # Gene L0-valid mới sau khi hết budget bị chặn trước solver.
    blocked = ev.evaluate_gene(dict(VALID_GENE, girder_concrete_id="C50"))
    assert blocked is None
    assert ev.counters == {
        "proposals": 4,
        "l0_checks": 2,
        "l0_passed": 1,
        "l0_rejected": 1,
        "cache_hits": 1,
        "solver_calls": 1,
        "budget_blocked": 1,
        "unique_results": 2,
    }
    assert [p["outcome"] for p in ev.proposal_history] == [
        "L0_REJECTED", "CACHE_HIT", "SOLVER_EVALUATED", "BUDGET_EXHAUSTED",
    ]


def test_random_search_and_nsga2_receive_same_actual_solver_budget():
    runs = (random_search(budget=5, seed=21),
            nsga2(budget=5, seed=21, pop_size=8))
    for run in runs:
        assert run["counters"]["solver_calls"] == 5
        solver_records = [r for r in run["history"]
                          if r["solver_call_index"] is not None]
        assert len(solver_records) == 5
        assert all(r["solver_status"] != "NOT_RUN" for r in solver_records)
        assert run["counters"]["proposals"] >= 5
        assert run["counters"]["l0_rejected"] > 0
        assert run["config"]["seed"] == 21


def test_seeded_history_is_deterministic_without_runtime_or_timestamp():
    a = random_search(budget=8, seed=9)
    b = random_search(budget=8, seed=9)
    assert a["counters"] == b["counters"]
    assert a["history"] == b["history"]
    assert a["proposal_history"] == b["proposal_history"]
    assert all("timestamp_utc" not in r["provenance"] for r in a["history"])
