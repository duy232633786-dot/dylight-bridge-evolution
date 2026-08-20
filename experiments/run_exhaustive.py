"""Quét toàn bộ grammar L1 để tạo oracle Pareto có thể audit.

Mặc định chỉ lưu lịch sử các gene qua L0; gene bị L0 loại được tổng hợp theo
rule để tránh tạo artifact hàng trăm MB. ``--limit`` chỉ dành cho smoke test và
manifest sẽ đánh dấu run chưa đầy đủ.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import itertools
import json
import math
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
import platform
import subprocess
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

from bridge_evolution import __version__                         # noqa: E402
from bridge_evolution.catalogs import load_catalogs, load_grammar  # noqa: E402
from bridge_evolution.evaluate import evaluate_candidate          # noqa: E402
from bridge_evolution.geometry import check_geometry               # noqa: E402
from bridge_evolution.objectives import objectives_tuple           # noqa: E402
from bridge_evolution.optimization.common import GENE_ORDER, gene_domains  # noqa: E402
from bridge_evolution.pareto import (                             # noqa: E402
    ParetoArchive, hypervolume_2d, hypervolume_mc,
)
from bridge_evolution.state import input_hash, state_from_gene     # noqa: E402
from bridge_evolution.fe_adapter import SOLVER_VERSION             # noqa: E402
from bridge_evolution.verifier import RULESET_VERSION              # noqa: E402
from experiments.run_baseline import (                             # noqa: E402
    HV_IDEAL_3D, HV_MC_SAMPLES, HV_MC_SEED, HV_REFERENCE_3D,
)


def _package_versions() -> dict[str, str]:
    result = {}
    for name in ("jsonschema", "numpy", "scikit-learn", "scipy"):
        try:
            result[name] = version(name)
        except PackageNotFoundError:
            result[name] = "not-installed"
    return result


def _source_revision() -> str:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
            text=True, check=False, timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return "unversioned"
    return proc.stdout.strip() if proc.returncode == 0 else "unversioned"


def _correlation(values: list[tuple], i: int, j: int) -> float | None:
    if len(values) < 2:
        return None
    xs, ys = [v[i] for v in values], [v[j] for v in values]
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    numerator = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    denominator = math.sqrt(
        sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys)
    )
    return numerator / denominator if denominator else None


def _output_dir(requested: str | None) -> Path:
    if requested:
        out = Path(requested).expanduser().resolve()
    else:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
        out = ROOT / "experiments" / "results" / f"exhaustive_{stamp}"
    out.mkdir(parents=True, exist_ok=False)
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", help="thư mục mới; từ chối ghi đè")
    parser.add_argument("--limit", type=int,
                        help="chỉ duyệt N gene đầu để smoke test; không phải oracle")
    args = parser.parse_args()
    if args.limit is not None and args.limit <= 0:
        raise ValueError("--limit phải > 0")

    domains = gene_domains()
    domain_size = math.prod(len(domains[name]) for name in GENE_ORDER)
    scan_limit = min(args.limit, domain_size) if args.limit is not None else domain_size
    out = _output_dir(args.output_dir)
    history_path = out / "solver_history.jsonl"

    archive = ParetoArchive()
    status_counts: Counter[str] = Counter()
    l0_rule_counts: Counter[str] = Counter()
    feasible_objectives: list[tuple] = []
    total = l0_valid = solver_calls = feasible = 0
    started = perf_counter()

    with history_path.open("x", encoding="utf-8", newline="\n") as history:
        product = itertools.product(*(domains[name] for name in GENE_ORDER))
        for values in itertools.islice(product, scan_limit):
            total += 1
            gene = dict(zip(GENE_ORDER, values))
            state = state_from_gene(
                gene, generation_action="EXHAUSTIVE_ORACLE", seed=0)
            violations, _geometry = check_geometry(state)
            if violations:
                l0_rule_counts.update(v["rule_id"] for v in violations)
                continue

            l0_valid += 1
            result = evaluate_candidate(state)
            status_counts[result["status"]] += 1
            if result.get("solver", {}).get("status") != "NOT_RUN":
                solver_calls += 1

            deterministic_result = json.loads(json.dumps(result))
            deterministic_result.get("provenance", {}).pop("timestamp_utc", None)
            deterministic_result.get("solver", {}).pop("runtime_ms", None)
            record = {
                "gene": gene,
                "input_hash": input_hash(state),
                "design_state": state,
                "result": deterministic_result,
            }
            history.write(json.dumps(record, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")) + "\n")

            if result["feasible"]:
                feasible += 1
                objective = objectives_tuple(result["objectives"])
                feasible_objectives.append(objective)
                archive.add(result["case_id"], objective, {"gene": gene})

            if total % 25_000 == 0:
                print(f"{total}/{scan_limit}: L0={l0_valid}, solver={solver_calls}, "
                      f"feasible={feasible}")

    elapsed = perf_counter() - started
    pareto = [{
        "case_id": entry["case_id"],
        "objectives": dict(zip(
            ("relative_cost", "material_mass_t", "embodied_carbon_kgCO2e"),
            entry["objectives"])),
        "gene": entry["payload"]["gene"],
    } for entry in archive.entries]
    (out / "pareto_oracle.json").write_text(
        json.dumps(pareto, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )

    catalog = load_catalogs()
    grammar = load_grammar()
    oracle_points = archive.front
    hv2 = hypervolume_2d(
        [(p[0], p[2]) for p in oracle_points],
        (HV_REFERENCE_3D[0], HV_REFERENCE_3D[2]),
    )
    hv3 = hypervolume_mc(
        oracle_points, HV_REFERENCE_3D, HV_IDEAL_3D,
        n_samples=HV_MC_SAMPLES, seed=HV_MC_SEED,
    )
    summary = {
        "complete_oracle": total == domain_size,
        "domain_size": domain_size,
        "scanned": total,
        "l0_valid": l0_valid,
        "l0_valid_rate": l0_valid / total if total else 0.0,
        "solver_calls": solver_calls,
        "feasible": feasible,
        "conditional_feasible_rate": feasible / solver_calls if solver_calls else 0.0,
        "pareto_size": len(pareto),
        "hypervolume_protocol": {
            "ideal_3d": HV_IDEAL_3D,
            "reference_3d": HV_REFERENCE_3D,
            "mc_samples": HV_MC_SAMPLES,
            "mc_seed": HV_MC_SEED,
            "oracle_hv_2d_cost_carbon": round(hv2, 2),
            "oracle_hv_3d_mc": round(hv3, 2),
        },
        "status_counts": dict(status_counts),
        "l0_rule_counts": dict(l0_rule_counts),
        "objective_correlations": {
            "cost_mass": _correlation(feasible_objectives, 0, 1),
            "cost_carbon": _correlation(feasible_objectives, 0, 2),
            "mass_carbon": _correlation(feasible_objectives, 1, 2),
        },
        "elapsed_seconds": round(elapsed, 3),
        "versions": {
            "software": __version__,
            "solver": SOLVER_VERSION,
            "ruleset": RULESET_VERSION,
            "catalogs": catalog["catalogs_version"],
            "grammar": grammar["grammar_version"],
            "source_revision": _source_revision(),
            "python": platform.python_version(),
            "platform": platform.platform(),
            "dependencies": _package_versions(),
        },
    }
    (out / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"Oracle artifacts: {out}")


if __name__ == "__main__":
    main()
