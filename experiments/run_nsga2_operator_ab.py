"""BRD-059 — A/B toán tử NSGA-II: ``legacy`` vs ``repaired``, cùng ngân sách solver.

Pre-registration (khóa trong code, ghi vào summary trước khi xem kết quả):
- Arm: operators ∈ {legacy, repaired}; mọi tham số khác giữ mặc định nsga2.
- Grammar: super_t_simple_v1 (có oracle vét cạn 2072,94) và super_t_parametric_v2.
- Ngân sách: 150 và 600 solver call; seed 100..119 (20 seed, không trùng seed
  42/43/44 đã dùng để phát hiện lỗi — tránh đánh giá trên chính dữ liệu gợi ý).
- Metric chính: best_relative_cost (thấp hơn là tốt hơn). Phụ: số seed chạm
  oracle v1, số gene duy nhất trong quần thể cuối, tỷ lệ cache hit/proposal.
- Quy tắc kết luận: repaired chỉ được gọi là "tốt hơn" ở một ô (grammar,
  budget) khi thắng legacy ở ≥ 14/20 seed theo cặp (dấu hiệu, p ≈ 0,058 một
  phía) VÀ trung vị best_cost không tệ hơn. Ngược lại báo "không khác biệt có
  căn cứ" hoặc kết quả âm. Hòa (chênh < 1e-9) không tính thắng/thua.

Claim ceiling: SCREENED (L0 + L1 line-girder sơ bộ).
"""
import argparse
import json
import statistics
import sys
from datetime import datetime, timezone
from math import comb
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from bridge_evolution import __version__                  # noqa: E402
from bridge_evolution.optimization import nsga2           # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

PREREGISTRATION = {
    "arms": ["legacy", "repaired"],
    "grammars": ["super_t_simple_v1", "super_t_parametric_v2"],
    "budgets": [150, 600],
    "seeds": list(range(100, 120)),
    "primary_metric": "best_relative_cost",
    "v1_exhaustive_oracle_best_cost": 2072.94,
    "decision_rule": ("repaired tốt hơn ở ô (grammar, budget) chỉ khi thắng theo "
                      "cặp ở >= 14/20 seed và trung vị best_cost không tệ hơn"),
    "win_threshold": 14,
    "tie_tolerance": 1e-9,
}


def _one_run(grammar: str, budget: int, seed: int, operators: str) -> dict:
    run = nsga2(budget=budget, seed=seed, grammar_id=grammar, operators=operators)
    feasible = [r for r in run["history"] if r["feasible"]]
    best = min((r["objectives"][0] for r in feasible), default=None)
    counters = run["counters"]
    diag = run.get("operator_diagnostics", {})
    return {
        "grammar": grammar, "budget": budget, "seed": seed, "operators": operators,
        "best_cost": best,
        "feasible_count": len(feasible),
        "solver_calls": counters["solver_calls"],
        "proposals": counters["proposals"],
        "cache_hits": counters["cache_hits"],
        "cache_hit_ratio": counters["cache_hits"] / max(1, counters["proposals"]),
        "generations": run["generations"],
        "archive_size": len(run["archive"].entries),
        "termination": run["termination"],
        "final_population_unique_genes": diag.get("final_population_unique_genes"),
    }


def _sign_test_p(wins: int, losses: int) -> float | None:
    """P một phía của kiểm định dấu (bỏ hòa)."""
    n = wins + losses
    if n == 0:
        return None
    return sum(comb(n, k) for k in range(wins, n + 1)) / 2 ** n


def summarize_cell(rows: list[dict]) -> dict:
    by = {(r["operators"], r["seed"]): r for r in rows}
    seeds = sorted({r["seed"] for r in rows})
    wins = losses = ties = 0
    for s in seeds:
        a, b = by[("legacy", s)]["best_cost"], by[("repaired", s)]["best_cost"]
        if a is None and b is None:
            ties += 1
        elif a is None:
            wins += 1
        elif b is None:
            losses += 1
        elif abs(a - b) < PREREGISTRATION["tie_tolerance"]:
            ties += 1
        elif b < a:
            wins += 1
        else:
            losses += 1
    arms = {}
    for arm in PREREGISTRATION["arms"]:
        arm_rows = [by[(arm, s)] for s in seeds]
        costs = [r["best_cost"] for r in arm_rows if r["best_cost"] is not None]
        oracle = PREREGISTRATION["v1_exhaustive_oracle_best_cost"]
        arms[arm] = {
            "median_best_cost": statistics.median(costs) if costs else None,
            "mean_best_cost": statistics.fmean(costs) if costs else None,
            "worst_best_cost": max(costs) if costs else None,
            "runs_without_feasible": sum(r["best_cost"] is None for r in arm_rows),
            "seeds_hitting_v1_oracle": sum(
                1 for c in costs if abs(c - oracle) < 0.005)
            if rows[0]["grammar"] == "super_t_simple_v1" else None,
            "median_cache_hit_ratio": statistics.median(
                r["cache_hit_ratio"] for r in arm_rows),
            "median_feasible_count": statistics.median(
                r["feasible_count"] for r in arm_rows),
        }
    med_l, med_r = arms["legacy"]["median_best_cost"], arms["repaired"]["median_best_cost"]
    better = (wins >= PREREGISTRATION["win_threshold"]
              and med_l is not None and med_r is not None and med_r <= med_l)
    worse = (losses >= PREREGISTRATION["win_threshold"]
             and med_l is not None and med_r is not None and med_r >= med_l)
    verdict = ("REPAIRED_BETTER" if better else
               "REPAIRED_WORSE" if worse else "NO_SUPPORTED_DIFFERENCE")
    return {"paired_wins_repaired": wins, "paired_losses_repaired": losses,
            "paired_ties": ties, "sign_test_p_one_sided": _sign_test_p(wins, losses),
            "arms": arms, "verdict": verdict}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=str(ROOT / "experiments" / "results"
                                         / "nsga2_operator_ab"))
    args = ap.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    rows = []
    for grammar in PREREGISTRATION["grammars"]:
        for budget in PREREGISTRATION["budgets"]:
            for seed in PREREGISTRATION["seeds"]:
                for arm in PREREGISTRATION["arms"]:
                    rows.append(_one_run(grammar, budget, seed, arm))
            print(f"xong {grammar} budget={budget}", flush=True)

    cells = {}
    for grammar in PREREGISTRATION["grammars"]:
        for budget in PREREGISTRATION["budgets"]:
            cell_rows = [r for r in rows if r["grammar"] == grammar
                         and r["budget"] == budget]
            cells[f"{grammar}|{budget}"] = summarize_cell(cell_rows)

    summary = {
        "experiment": "BRD-059 nsga2 operator A/B",
        "software_version": __version__,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "claim_ceiling": "SCREENED",
        "preregistration": PREREGISTRATION,
        "cells": cells,
    }
    with open(out / "runs.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
    (out / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    print(json.dumps(cells, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
