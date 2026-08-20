"""Đối chiếu các Pareto archive của một benchmark với exhaustive oracle."""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

from bridge_evolution.pareto import hypervolume_2d, hypervolume_mc  # noqa: E402
from experiments.run_baseline import (                            # noqa: E402
    HV_IDEAL_3D, HV_MC_SAMPLES, HV_MC_SEED, HV_REFERENCE_3D,
)

OBJECTIVE_KEYS = (
    "relative_cost", "material_mass_t", "embodied_carbon_kgCO2e")


def _load_front(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"Front phải là JSON array: {path}")
    return data


def _point(item: dict) -> tuple[float, ...]:
    return tuple(float(item["objectives"][key]) for key in OBJECTIVE_KEYS)


def _normalized(point: tuple[float, ...]) -> tuple[float, ...]:
    return tuple(
        (point[i] - HV_IDEAL_3D[i]) /
        (HV_REFERENCE_3D[i] - HV_IDEAL_3D[i])
        for i in range(len(point))
    )


def igd_plus(reference: list[tuple], approximation: list[tuple]) -> float | None:
    """IGD+ chuẩn hóa cho bài toán minimize; 0 nghĩa là phủ oracle."""
    if not reference or not approximation:
        return None
    ref_n = [_normalized(p) for p in reference]
    app_n = [_normalized(p) for p in approximation]
    distances = []
    for ref in ref_n:
        distances.append(min(math.sqrt(sum(
            max(app[i] - ref[i], 0.0) ** 2 for i in range(len(ref))))
            for app in app_n))
    return sum(distances) / len(distances)


def additive_epsilon(reference: list[tuple], approximation: list[tuple]) -> float | None:
    """Unary additive epsilon chuẩn hóa; nhỏ hơn là tốt hơn, 0 phủ oracle."""
    if not reference or not approximation:
        return None
    ref_n = [_normalized(p) for p in reference]
    app_n = [_normalized(p) for p in approximation]
    eps = max(min(max(app[i] - ref[i] for i in range(len(ref))) for app in app_n)
              for ref in ref_n)
    return max(0.0, eps)


def compare(reference_items: list[dict], approximation_items: list[dict]) -> dict:
    reference, approximation = ([_point(x) for x in items]
                                for items in (reference_items, approximation_items))
    ref_ids = {x["case_id"] for x in reference_items}
    app_ids = {x["case_id"] for x in approximation_items}
    hv_ref_2d = hypervolume_2d(
        [(p[0], p[2]) for p in reference],
        (HV_REFERENCE_3D[0], HV_REFERENCE_3D[2]))
    hv_app_2d = hypervolume_2d(
        [(p[0], p[2]) for p in approximation],
        (HV_REFERENCE_3D[0], HV_REFERENCE_3D[2]))
    hv_ref_3d = hypervolume_mc(
        reference, HV_REFERENCE_3D, HV_IDEAL_3D,
        n_samples=HV_MC_SAMPLES, seed=HV_MC_SEED)
    hv_app_3d = hypervolume_mc(
        approximation, HV_REFERENCE_3D, HV_IDEAL_3D,
        n_samples=HV_MC_SAMPLES, seed=HV_MC_SEED)
    oracle_best = min((p[0] for p in reference), default=None)
    app_best = min((p[0] for p in approximation), default=None)
    return {
        "archive_size": len(approximation_items),
        "oracle_points_found": len(ref_ids & app_ids),
        "oracle_size": len(ref_ids),
        "oracle_recall": len(ref_ids & app_ids) / len(ref_ids) if ref_ids else None,
        "exact_oracle_front": app_ids == ref_ids,
        "extra_nondominated_points": len(app_ids - ref_ids),
        "best_cost": app_best,
        "best_cost_gap_pct": (
            100.0 * (app_best - oracle_best) / oracle_best
            if app_best is not None and oracle_best else None),
        "hv_2d_ratio": hv_app_2d / hv_ref_2d if hv_ref_2d else None,
        "hv_3d_ratio": hv_app_3d / hv_ref_3d if hv_ref_3d else None,
        "igd_plus_normalized": igd_plus(reference, approximation),
        "epsilon_additive_normalized": additive_epsilon(reference, approximation),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--oracle-dir", required=True)
    parser.add_argument("--run-dir", required=True)
    args = parser.parse_args()
    oracle_dir = Path(args.oracle_dir).expanduser().resolve()
    run_dir = Path(args.run_dir).expanduser().resolve()
    oracle = _load_front(oracle_dir / "pareto_oracle.json")
    front_files = sorted(run_dir.glob("pareto_*.json"))
    if not front_files:
        raise FileNotFoundError(f"Không có pareto_*.json trong {run_dir}")

    rows = []
    for path in front_files:
        metrics = compare(oracle, _load_front(path))
        rows.append({"run": path.stem.removeprefix("pareto_"), **metrics})

    csv_path = run_dir / "oracle_comparison.csv"
    md_path = run_dir / "oracle_comparison.md"
    if csv_path.exists() or md_path.exists():
        raise FileExistsError("Oracle comparison đã tồn tại; không ghi đè")
    with csv_path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    headers = list(rows[0])
    lines = ["# Đối chiếu exhaustive oracle", "",
             f"Oracle: `{oracle_dir.name}` · {len(oracle)} Pareto points", "",
             "| " + " | ".join(headers) + " |",
             "|" + "---|" * len(headers)]
    for row in rows:
        cells = []
        for key in headers:
            value = row[key]
            cells.append(f"{value:.6g}" if isinstance(value, float) else str(value))
        lines.append("| " + " | ".join(cells) + " |")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
