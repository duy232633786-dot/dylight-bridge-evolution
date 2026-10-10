"""BRD-059 — toán tử NSGA-II ``repaired`` so với ``legacy``.

Legacy phải tái lập từng byte (thí nghiệm grammar A/B đã pre-register dựa vào
nó). Repaired phải: quần thể chỉ gồm cá thể qua L0, không trùng gene, immigrant
không phá front 0 khi còn đuôi để thay, và đột biến luôn đổi gene được chọn.
"""
import hashlib
import importlib
import json
import random

import pytest

from bridge_evolution.optimization import nsga2
from bridge_evolution.optimization.common import gene_sizes

nsga2_module = importlib.import_module("bridge_evolution.optimization.nsga2")

GRAMMAR_V2 = "super_t_parametric_v2"


def _fingerprint(run: dict) -> str:
    payload = {
        "h": run["history"],
        "p": run["proposal_history"],
        "a": [e["objectives"] for e in run["archive"].entries],
        "g": run["generations"],
        "c": run["counters"],
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def _population_snapshots(monkeypatch, **kwargs):
    """Chụp mọi quần thể được đưa vào non-dominated sort (pop và union)."""
    snapshots = []
    original = nsga2_module._fast_nondominated_sort

    def spy(pop):
        snapshots.append(list(pop))
        return original(pop)

    monkeypatch.setattr(nsga2_module, "_fast_nondominated_sort", spy)
    run = nsga2(**kwargs)
    return run, snapshots


def test_legacy_is_default_and_byte_identical_to_pre_brd059_history():
    # Dấu vân tay chụp từ nsga2.py TRƯỚC khi sửa (BRD-059). Đổi số này là đổi
    # lịch sử của thí nghiệm đã pre-register — test phải đỏ.
    assert _fingerprint(nsga2(budget=60, seed=11, pop_size=12)) == (
        "eb64ffeab4289064a17ceb4b7c6b49e05903e232699591c62aed863bdd9d084f")
    explicit = nsga2(budget=60, seed=11, pop_size=12, operators="legacy")
    assert "operators" not in explicit["config"]
    assert "operator_diagnostics" not in explicit


def test_unknown_operator_is_rejected():
    with pytest.raises(ValueError, match="operators"):
        nsga2(budget=5, seed=1, operators="magic")


def test_repaired_is_reproducible_for_same_seed():
    a = nsga2(budget=60, seed=7, pop_size=12, operators="repaired")
    b = nsga2(budget=60, seed=7, pop_size=12, operators="repaired")
    assert _fingerprint(a) == _fingerprint(b)
    assert a["operator_diagnostics"] == b["operator_diagnostics"]
    assert a["config"]["operators"] == "repaired"


def test_repaired_population_has_no_l0_rejects_and_no_duplicates(monkeypatch):
    run, snapshots = _population_snapshots(
        monkeypatch, budget=150, seed=42, pop_size=20, operators="repaired")
    assert snapshots, "phải có ít nhất một thế hệ"
    for pop in snapshots:
        assert all(ind["solver_status"] != "NOT_RUN" for ind in pop)
        genes = [tuple(ind["x"]) for ind in pop]
        assert len(set(genes)) == len(genes)
    diag = run["operator_diagnostics"]
    assert diag["final_population_l0_rejected"] == 0
    assert diag["final_population_unique_genes"] == 20


def test_legacy_population_still_shows_the_measured_defects(monkeypatch):
    # Kết quả âm được giữ: legacy có L0-reject trong quần thể khởi tạo và sụp
    # đa dạng. Test này ghi lại lý do tồn tại của biến thể repaired.
    _run, snapshots = _population_snapshots(
        monkeypatch, budget=150, seed=42, pop_size=20)
    first = snapshots[0]
    assert sum(ind["solver_status"] == "NOT_RUN" for ind in first) > len(first) // 2
    assert any(len({tuple(i["x"]) for i in pop}) < len(pop) for pop in snapshots)


def test_repaired_respects_solver_budget():
    for budget in (0, 1, 5, 40):
        run = nsga2(budget=budget, seed=3, pop_size=8, operators="repaired")
        assert run["counters"]["solver_calls"] <= budget


def test_repaired_runs_on_grammar_v2():
    run = nsga2(budget=40, seed=3, pop_size=8, grammar_id=GRAMMAR_V2,
                operators="repaired")
    assert run["counters"]["solver_calls"] == 40
    assert run["operator_diagnostics"]["final_population_l0_rejected"] == 0


@pytest.mark.parametrize("seed", range(20))
def test_repaired_mutation_changes_every_selected_gene(seed):
    sizes = gene_sizes()
    rng = random.Random(seed)
    x = [rng.randrange(s) for s in sizes]
    # Đặt vài gene ở biên để kiểm phản xạ ±1.
    x[0], x[1] = 0, sizes[1] - 1
    y = nsga2_module._mutate_vector(x, sizes, 1.0, random.Random(seed), True)
    for j, size in enumerate(sizes):
        assert 0 <= y[j] < size
        if size > 1:
            assert y[j] != x[j], f"gene {j} được chọn nhưng không đổi"


def test_legacy_mutation_can_leave_selected_gene_unchanged():
    sizes = gene_sizes()
    unchanged = 0
    for seed in range(200):
        x = [0] * len(sizes)
        y = nsga2_module._mutate_vector(x, sizes, 1.0, random.Random(seed), False)
        unchanged += sum(a == b for a, b in zip(x, y))
    assert unchanged > 0


def test_repaired_long_run_keeps_population_clean(monkeypatch):
    # Seed 42, budget 600 là run mà legacy kết thúc với 9/40 cá thể L0-reject
    # do immigrant không lọc L0. Repaired phải giữ quần thể sạch tới cuối.
    run, snapshots = _population_snapshots(
        monkeypatch, budget=600, seed=42, pop_size=40, operators="repaired")
    assert run["counters"]["solver_calls"] == 600
    last = snapshots[-1]
    assert all(ind["solver_status"] != "NOT_RUN" for ind in last)
    assert run["operator_diagnostics"]["final_population_l0_rejected"] == 0
