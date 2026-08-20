"""So sánh Random Search và NSGA-II theo cùng ngân sách solver thật.

Mỗi lần chạy tạo thư mục mới; không ghi đè hoặc trộn với kết quả cũ. Lịch sử
JSONL lưu gene, SHA-256 đầy đủ, config, version và seed để replay/audit.
"""
import argparse
import csv
from datetime import datetime, timezone
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from bridge_evolution import __version__                              # noqa: E402
from bridge_evolution.optimization import nsga2, random_search        # noqa: E402
from bridge_evolution.pareto import hypervolume_2d, hypervolume_mc    # noqa: E402

# Console Windows có thể vẫn dùng cp1252 dù file/report là UTF-8.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

# Khai báo TRƯỚC thí nghiệm, không suy ra từ front của bất kỳ thuật toán nào.
# Thứ tự: relative_cost, material_mass_t, embodied_carbon_kgCO2e.
HV_IDEAL_3D = (0.0, 0.0, 0.0)
HV_REFERENCE_3D = (5_000.0, 1_200.0, 250_000.0)
HV_MC_SAMPLES = 40_000
HV_MC_SEED = 1_729


def summarize(run: dict) -> dict:
    """Chỉ số tách rõ proposal, L0 và solver; feasible rate có điều kiện solver."""
    hist = run["history"]
    solver_hist = [r for r in hist if r.get("solver_call_index") is not None]
    feas = [r for r in solver_hist if r["feasible"]]
    costs = [r["objectives"][0] for r in feas]
    by_status: dict[str, int] = {}
    for r in hist:
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1
    counters = run["counters"]
    solver_calls = counters["solver_calls"]
    return {
        "algorithm": run["algorithm"],
        "proposals": counters["proposals"],
        "l0_checks": counters["l0_checks"],
        "l0_rejected": counters["l0_rejected"],
        "cache_hits": counters["cache_hits"],
        "solver_calls": solver_calls,
        "status_counts": by_status,
        "feasible_count": len(feas),
        "solver_conditional_feasible_rate": round(len(feas) / max(1, solver_calls), 4),
        "first_feasible_solver_call": next(
            (r["solver_call_index"] for r in solver_hist if r["feasible"]), None),
        "best_cost": min(costs) if costs else None,
        "median_feasible_cost": round(statistics.median(costs), 2) if costs else None,
        "archive_size": len(run["archive"].entries),
    }


def _assert_hv_domain(points: list[tuple]) -> None:
    outside = [p for p in points if not all(
        HV_IDEAL_3D[i] <= p[i] < HV_REFERENCE_3D[i] for i in range(3))]
    if outside:
        raise ValueError(
            "Có objective ngoài miền hypervolume khai báo trước; phải sửa protocol "
            f"trước khi chạy, không được suy ref từ kết quả: {outside[:3]}"
        )


def add_hypervolume(run: dict, summary: dict) -> None:
    pts3 = [tuple(e["objectives"]) for e in run["archive"].entries]
    _assert_hv_domain(pts3)
    pts2 = [(p[0], p[2]) for p in pts3]
    ref2 = (HV_REFERENCE_3D[0], HV_REFERENCE_3D[2])
    summary["hypervolume_2d_cost_carbon"] = round(hypervolume_2d(pts2, ref2), 2)
    summary["hypervolume_3d_mc"] = round(hypervolume_mc(
        pts3, HV_REFERENCE_3D, HV_IDEAL_3D,
        n_samples=HV_MC_SAMPLES, seed=HV_MC_SEED), 2)


def _create_output_dir(budget: int, seed: int, requested: str | None) -> Path:
    if requested:
        out = Path(requested).expanduser().resolve()
        # exist_ok=False là chủ ý: không bao giờ để file stale sống sót trong run mới.
        out.mkdir(parents=True, exist_ok=False)
        return out
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    out = ROOT / "experiments" / "results" / f"baseline_b{budget}_s{seed}_{stamp}"
    out.mkdir(parents=True, exist_ok=False)
    return out


def _enriched(record: dict, run: dict) -> dict:
    return {"algorithm": run["algorithm"], "run_config": run["config"], **record}


def _write_jsonl(path: Path, records: list[dict], run: dict) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as f:
        for record in records:
            f.write(json.dumps(_enriched(record, run), ensure_ascii=False,
                               sort_keys=True, separators=(",", ":")))
            f.write("\n")


def _write_history_csv(path: Path, run: dict) -> None:
    with path.open("x", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["record_index", "proposal_index", "solver_call_index", "case_id",
                    "input_hash_sha256", "seed", "software_version", "status",
                    "solver_status", "feasible", "cv", "cost", "mass_t", "carbon",
                    "max_utilization", "gene_json", "run_config_json"])
        for r in run["history"]:
            obj = r["objectives"] or (None, None, None)
            w.writerow([r["record_index"], r["proposal_index"], r["solver_call_index"],
                        r["case_id"], r["input_hash"], r["seed"], r["software_version"],
                        r["status"], r["solver_status"], r["feasible"], round(r["cv"], 6),
                        *obj, r["max_utilization"],
                        json.dumps(r["gene"], ensure_ascii=False, sort_keys=True),
                        json.dumps(run["config"], ensure_ascii=False, sort_keys=True)])


def _write_run_artifacts(out: Path, run: dict) -> None:
    name = run["algorithm"]
    _write_history_csv(out / f"history_{name}.csv", run)
    _write_jsonl(out / f"history_{name}.jsonl", run["history"], run)
    _write_jsonl(out / f"proposals_{name}.jsonl", run["proposal_history"], run)
    with (out / f"pareto_{name}.json").open("x", encoding="utf-8") as f:
        json.dump([{
            "case_id": e["case_id"],
            "objectives": dict(zip(
                ("relative_cost", "material_mass_t", "embodied_carbon_kgCO2e"),
                e["objectives"])),
            "gene": e["payload"].get("gene"),
        } for e in run["archive"].entries], f, indent=2, ensure_ascii=False)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--budget", type=int, default=600,
                    help="số lần solver.status != NOT_RUN cho mỗi thuật toán")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--pop", type=int, default=40)
    ap.add_argument("--output-dir", type=str,
                    help="thư mục mới (lệnh từ chối nếu đã tồn tại)")
    args = ap.parse_args()

    print(f"[1/2] Random Search  (solver budget={args.budget}, seed={args.seed}) ...")
    rs = random_search(args.budget, args.seed)
    print(f"[2/2] NSGA-II        (solver budget={args.budget}, seed={args.seed}, "
          f"pop={args.pop}) ...")
    ga = nsga2(args.budget, args.seed, pop_size=args.pop)
    runs = (rs, ga)

    summaries = [summarize(run) for run in runs]
    for run, summary in zip(runs, summaries):
        add_hypervolume(run, summary)

    out = _create_output_dir(args.budget, args.seed, args.output_dir)
    for run in runs:
        _write_run_artifacts(out, run)

    manifest = {
        "experiment": "baseline_random_search_vs_nsga2",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "software_version": __version__,
        "budget_definition": "solver.status != NOT_RUN",
        "hypervolume_protocol": {
            "objective_order": ["relative_cost", "material_mass_t",
                                "embodied_carbon_kgCO2e"],
            "ideal_3d": HV_IDEAL_3D,
            "reference_3d": HV_REFERENCE_3D,
            "mc_samples": HV_MC_SAMPLES,
            "mc_seed": HV_MC_SEED,
        },
        "runs": [{"algorithm": r["algorithm"], "seed": r["seed"],
                  "config": r["config"], "counters": r["counters"],
                  "termination": r["termination"]} for r in runs],
    }
    with (out / "run_manifest.json").open("x", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False, sort_keys=True)

    lines = ["# Baseline — Random Search vs NSGA-II", "",
             f"Ngân sách: **{args.budget} solver calls** / thuật toán · seed {args.seed}"
             f" · pop NSGA-II {args.pop}", "",
             "Budget chỉ tăng khi `solver.status != NOT_RUN`; L0 reject và cache hit "
             "được báo riêng.", "",
             f"HV reference khai báo trước: `{HV_REFERENCE_3D}` · ideal `{HV_IDEAL_3D}`"
             f" · MC seed {HV_MC_SEED}", "",
             "| Chỉ số | Random Search | NSGA-II |", "|---|---:|---:|"]
    keys = ["proposals", "l0_rejected", "cache_hits", "solver_calls",
            "feasible_count", "solver_conditional_feasible_rate",
            "first_feasible_solver_call", "best_cost", "median_feasible_cost",
            "archive_size", "hypervolume_2d_cost_carbon", "hypervolume_3d_mc"]
    labels = {
        "proposals": "Proposal", "l0_rejected": "Bị L0 loại", "cache_hits": "Cache hit",
        "solver_calls": "Solver calls thực", "feasible_count": "Khả thi sau solver",
        "solver_conditional_feasible_rate": "P(khả thi | solver chạy)",
        "first_feasible_solver_call": "Solver call tới khả thi đầu tiên",
        "best_cost": "Chi phí tốt nhất", "median_feasible_cost": "Chi phí trung vị khả thi",
        "archive_size": "Kích thước Pareto front",
        "hypervolume_2d_cost_carbon": "HV 2D (cost×carbon)",
        "hypervolume_3d_mc": "HV 3D (MC, fixed seed)",
    }
    for key in keys:
        lines.append(f"| {labels[key]} | {summaries[0].get(key)} | {summaries[1].get(key)} |")
    lines += ["", "## Phân loại kết quả duy nhất", "",
              f"- Random Search: `{summaries[0]['status_counts']}`",
              f"- NSGA-II: `{summaries[1]['status_counts']}`"]
    (out / "report.md").write_text("\n".join(lines), encoding="utf-8")

    print("\n".join(lines))
    print(f"\nĐã lưu run mới, không trộn kết quả cũ: {out}")


if __name__ == "__main__":
    main()
