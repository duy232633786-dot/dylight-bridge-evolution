"""Chạy toàn bộ gold_case_matrix.csv — neo hành vi của pipeline."""
import csv
import json
from pathlib import Path

import pytest

from bridge_evolution.evaluate import evaluate_candidate

ROOT = Path(__file__).resolve().parent.parent / "gold_cases"


def _matrix():
    with open(ROOT / "gold_case_matrix.csv", encoding="utf-8") as f:
        return list(csv.DictReader(f))


@pytest.mark.parametrize("row", _matrix(), ids=lambda r: r["case_file"].split("_")[0])
def test_gold_case(row):
    with open(ROOT / "cases" / row["case_file"], encoding="utf-8") as f:
        state = json.load(f)
    result = evaluate_candidate(state)

    assert result["status"] == row["expected_status"], result["violations"]
    assert result["feasible"] == (row["expected_feasible"] == "true")
    if row["expected_rules_contain"]:
        found = {v["rule_id"] for v in result["violations"]}
        assert row["expected_rules_contain"] in found, f"{row['expected_rules_contain']} ∉ {found}"


def test_cheap_case_really_cheaper_and_expensive_really_expensive():
    def run(name):
        with open(ROOT / "cases" / name, encoding="utf-8") as f:
            return evaluate_candidate(json.load(f))

    std = run("GC-01_standard_pass.json")["objectives"]["relative_cost"]
    cheap = run("GC-06_cheap_but_fails.json")["objectives"]["relative_cost"]
    rich = run("GC-07_pass_but_expensive.json")["objectives"]["relative_cost"]
    assert cheap < std < rich


def test_solver_failure_reports_not_converged():
    with open(ROOT / "cases" / "GC-05_solver_failure.json", encoding="utf-8") as f:
        result = evaluate_candidate(json.load(f))
    assert result["solver"]["status"] == "NOT_CONVERGED"
    assert result["status"] == "SOLVER_FAILED"
