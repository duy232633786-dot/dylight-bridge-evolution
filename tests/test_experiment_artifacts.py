import json

import pytest

from bridge_evolution.optimization import random_search
from experiments import run_baseline


def test_summary_uses_solver_conditional_feasible_rate():
    run = random_search(budget=4, seed=4)
    summary = run_baseline.summarize(run)
    assert summary["solver_calls"] == 4
    assert summary["proposals"] == run["counters"]["proposals"]
    assert summary["l0_rejected"] == run["counters"]["l0_rejected"]
    assert summary["solver_conditional_feasible_rate"] == round(
        summary["feasible_count"] / 4, 4)


def test_history_artifacts_are_full_and_output_dir_cannot_be_reused(tmp_path):
    requested = tmp_path / "fresh-run"
    out = run_baseline._create_output_dir(3, 12, str(requested))
    run = random_search(budget=3, seed=12)
    run_baseline._write_run_artifacts(out, run)

    first = json.loads((out / "history_random_search.jsonl")
                       .read_text(encoding="utf-8").splitlines()[0])
    assert len(first["input_hash"]) == 64
    assert first["gene"]
    assert first["seed"] == 12
    assert first["software_version"]
    assert first["run_config"]["budget_solver_calls"] == 3
    assert (out / "proposals_random_search.jsonl").is_file()

    with pytest.raises(FileExistsError):
        run_baseline._create_output_dir(3, 12, str(requested))


def test_hypervolume_protocol_is_predeclared_and_deterministic():
    a = random_search(budget=3, seed=2)
    summary1 = run_baseline.summarize(a)
    summary2 = run_baseline.summarize(a)
    run_baseline.add_hypervolume(a, summary1)
    run_baseline.add_hypervolume(a, summary2)
    assert run_baseline.HV_REFERENCE_3D == (5000.0, 1200.0, 250000.0)
    assert summary1["hypervolume_2d_cost_carbon"] == summary2["hypervolume_2d_cost_carbon"]
    assert summary1["hypervolume_3d_mc"] == summary2["hypervolume_3d_mc"]
