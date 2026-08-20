"""Thí nghiệm đa seed với ngân sách solver thật và artifact có thể audit.

Hypervolume dùng protocol cố định khai báo trước trong ``run_baseline``; tuyệt
đối không suy reference/ideal từ hợp front sau khi đã thấy kết quả.
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

from bridge_evolution import __version__                         # noqa: E402
from bridge_evolution.optimization import nsga2, random_search   # noqa: E402
from experiments.run_baseline import (                          # noqa: E402
    HV_IDEAL_3D, HV_MC_SAMPLES, HV_MC_SEED, HV_REFERENCE_3D,
    _write_jsonl, add_hypervolume, summarize,
)

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

METRIC_KEYS = [
    "proposals", "l0_rejected", "cache_hits", "solver_calls", "feasible_count",
    "solver_conditional_feasible_rate", "first_feasible_solver_call", "best_cost",
    "median_feasible_cost", "archive_size", "hypervolume_2d_cost_carbon",
    "hypervolume_3d_mc",
]
AGG_KEYS = ["solver_conditional_feasible_rate", "best_cost",
            "hypervolume_2d_cost_carbon", "hypervolume_3d_mc"]


def resolve_algos(names: list[str], pop: int) -> dict:
    """{tên ngắn: callable(budget, seed)}; module tùy chọn thiếu thì cảnh báo."""
    algos = {}
    for name in names:
        if name == "rs":
            algos["rs"] = lambda budget, seed: random_search(budget, seed)
        elif name == "nsga2":
            algos["nsga2"] = lambda budget, seed: nsga2(budget, seed, pop_size=pop)
        elif name == "surrogate":
            try:
                from bridge_evolution.surrogate import surrogate_assisted_search
            except ImportError as exc:
                print(f"[WARN] Bỏ qua 'surrogate' — module chưa sẵn sàng: {exc}")
                continue
            algos["surrogate"] = (
                lambda budget, seed: surrogate_assisted_search(budget, seed))
        elif name == "qlearning":
            try:
                from bridge_evolution.rl_env import train_qlearning
            except ImportError as exc:
                print(f"[WARN] Bỏ qua 'qlearning' — module chưa sẵn sàng: {exc}")
                continue
            algos["qlearning"] = lambda budget, seed: train_qlearning(budget, seed)
        else:
            print(f"[WARN] Thuật toán không nhận dạng: '{name}' — bỏ qua")
    return algos


def mean_std(values: list) -> str:
    vals = [v for v in values if v is not None]
    if not vals:
        return "n/a"
    mean = statistics.mean(vals)
    std = statistics.stdev(vals) if len(vals) >= 2 else 0.0
    return f"{mean:.4g} ± {std:.4g}"


def _create_output_dir(budget: int, requested: str | None) -> Path:
    if requested:
        out = Path(requested).expanduser().resolve()
        out.mkdir(parents=True, exist_ok=False)
        return out
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    out = ROOT / "experiments" / "results" / f"multiseed_b{budget}_{stamp}"
    out.mkdir(parents=True, exist_ok=False)
    return out


def _write_pareto(path: Path, run: dict) -> None:
    with path.open("x", encoding="utf-8") as f:
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
                    help="số solver calls thật cho mỗi algorithm × seed")
    ap.add_argument("--seeds", type=str, default="42,43,44")
    ap.add_argument("--algos", type=str, default="rs,nsga2,surrogate,qlearning")
    ap.add_argument("--pop", type=int, default=40)
    ap.add_argument("--output-dir", type=str,
                    help="thư mục mới (lệnh từ chối nếu đã tồn tại)")
    args = ap.parse_args()

    seeds = [int(s) for s in args.seeds.split(",") if s.strip()]
    algo_names = [a.strip() for a in args.algos.split(",") if a.strip()]
    if not seeds:
        raise ValueError("Cần ít nhất một seed")
    algos = resolve_algos(algo_names, args.pop)
    if not algos:
        raise ValueError("Không còn thuật toán hợp lệ để chạy")

    runs = []
    total = len(algos) * len(seeds)
    for algo_name, fn in algos.items():
        for seed in seeds:
            print(f"[{len(runs) + 1}/{total}] {algo_name:<10} seed={seed} "
                  f"solver_budget={args.budget} ...")
            run = fn(args.budget, seed)
            summary = summarize(run)
            add_hypervolume(run, summary)
            runs.append({"algo": algo_name, "seed": seed, "run": run,
                         "summary": summary})

    out = _create_output_dir(args.budget, args.output_dir)

    with (out / "summary.csv").open("x", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["algorithm", "seed"] + METRIC_KEYS)
        for item in runs:
            w.writerow([item["algo"], item["seed"]]
                       + [item["summary"][key] for key in METRIC_KEYS])

    for item in runs:
        key = f"{item['algo']}_s{item['seed']}"
        run = item["run"]
        _write_jsonl(out / f"history_{key}.jsonl", run["history"], run)
        _write_jsonl(out / f"proposals_{key}.jsonl", run["proposal_history"], run)
        _write_pareto(out / f"pareto_{key}.json", run)
        if "model_state" in run:
            with (out / f"model_{key}.json").open("x", encoding="utf-8") as f:
                json.dump({"algorithm": run["algorithm"], "seed": run["seed"],
                           "software_version": __version__, "config": run["config"],
                           "model_state": run["model_state"]},
                          f, indent=2, ensure_ascii=False, sort_keys=True)

    manifest = {
        "experiment": "multiseed_algorithm_comparison",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "software_version": __version__,
        "budget_definition": "solver.status != NOT_RUN",
        "requested": {"budget": args.budget, "seeds": seeds,
                      "algorithms": algo_names, "nsga2_pop": args.pop},
        "hypervolume_protocol": {
            "objective_order": ["relative_cost", "material_mass_t",
                                "embodied_carbon_kgCO2e"],
            "ideal_3d": HV_IDEAL_3D,
            "reference_3d": HV_REFERENCE_3D,
            "mc_samples": HV_MC_SAMPLES,
            "mc_seed": HV_MC_SEED,
        },
        "runs": [{"algorithm_key": item["algo"], "seed": item["seed"],
                  "config": item["run"]["config"],
                  "counters": item["run"]["counters"],
                  "termination": item["run"]["termination"]} for item in runs],
    }
    with (out / "run_manifest.json").open("x", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False, sort_keys=True)

    labels = {
        "solver_conditional_feasible_rate": "P(khả thi | solver chạy)",
        "best_cost": "Chi phí tốt nhất",
        "hypervolume_2d_cost_carbon": "HV 2D cost×carbon",
        "hypervolume_3d_mc": "HV 3D MC",
    }
    lines = ["# Thí nghiệm đa seed — cùng ngân sách solver thật", "",
             f"Ngân sách: **{args.budget} solver calls** / run · seeds: {seeds}"
             f" · pop NSGA-II: {args.pop}", "",
             "Budget chỉ tăng khi `solver.status != NOT_RUN`; proposal, L0 reject và "
             "cache hit được báo riêng.", "",
             f"HV protocol khai báo trước: ref `{HV_REFERENCE_3D}` · ideal `{HV_IDEAL_3D}`"
             f" · MC samples {HV_MC_SAMPLES} · MC seed {HV_MC_SEED}", "",
             "| Thuật toán | "
             + " | ".join(f"{labels[key]} (mean±std)" for key in AGG_KEYS) + " |",
             "|---|" + "---:|" * len(AGG_KEYS)]
    for algo_name in algos:
        rows = [item["summary"] for item in runs if item["algo"] == algo_name]
        cells = [mean_std([row[key] for row in rows]) for key in AGG_KEYS]
        lines.append(f"| {algo_name} | " + " | ".join(cells) + " |")

    lines += ["", "## Chi tiết từng run", "",
              "| Thuật toán | Seed | " + " | ".join(METRIC_KEYS) + " |",
              "|---|---:|" + "---:|" * len(METRIC_KEYS)]
    for item in runs:
        lines.append(f"| {item['algo']} | {item['seed']} | "
                     + " | ".join(str(item["summary"][key]) for key in METRIC_KEYS)
                     + " |")
    (out / "summary.md").write_text("\n".join(lines), encoding="utf-8")

    print()
    print("\n".join(lines))
    print(f"\nĐã lưu run mới, không trộn kết quả cũ: {out}")


if __name__ == "__main__":
    main()
