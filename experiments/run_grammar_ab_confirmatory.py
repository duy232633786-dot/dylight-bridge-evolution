"""Confirmatory A/B experiment for grammar v1 vs v2 with 20 seeds and 4th arm.

Task: BRD-013 (thiết kế thí nghiệm) — phân tích thống kê được sửa trong BRD-015.
Implements the 4-arm confirmatory trial defined in:
experiments/preregistration/grammar_ab_confirmatory.json

Nguyên tắc chi phối (multiagent/PHYSICS_GATES.md): thiếu dữ liệu là STOP, không
phải một phán quyết mềm. Khi không đủ dữ liệu để phát biểu theo pre-registration,
runner ghi summary có ``status = "STOPPED"`` + ``stop_reason``, KHÔNG ghi khóa
``verdict``, in cảnh báo ra stderr và trả exit code khác 0.
"""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import random
import re
import statistics
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from bridge_evolution import __version__
from bridge_evolution.objectives import OBJECTIVE_KEYS
from bridge_evolution.optimization import nsga2, random_search
from bridge_evolution.optimization.common import (
    BudgetedEvaluator,
    gene_domains,
    gene_order,
)
from bridge_evolution.optimization.nsga2 import (
    _crowding,
    _fast_nondominated_sort,
)
from bridge_evolution.pareto import ParetoArchive

try:  # scipy là bắt buộc cho phép kiểm đã khóa trong pre-registration.
    from scipy.stats import wilcoxon as _scipy_wilcoxon
    _WILCOXON_IMPORT_ERROR: Exception | None = None
except Exception as _exc:  # pragma: no cover - chỉ chạy khi thiếu scipy
    _scipy_wilcoxon = None
    _WILCOXON_IMPORT_ERROR = _exc

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

DEFAULT_PREREG = ROOT / "experiments" / "preregistration" / "grammar_ab_confirmatory.json"

#: Exit code khi thí nghiệm bị DỪNG (fail-closed, không có phán quyết).
STOP_EXIT_CODE = 3

#: Phép kiểm đã khóa trong pre-registration; runner tuân nó, không phải ngược lại.
REQUIRED_STATISTICAL_TEST = "paired_wilcoxon_and_bootstrap_ci"
#: 'pratt' giữ các chênh lệch bằng 0 trong xếp hạng (không âm thầm bỏ cặp).
WILCOXON_ZERO_METHOD = "pratt"
#: Hai phía: không giả định sẵn chiều cải thiện; chiều do trung vị + ngưỡng quyết định.
WILCOXON_ALTERNATIVE = "two-sided"

_NUMBER_RE = re.compile(r"[-+]?\d+(?:\.\d+)?")

RUN_CSV_FIELDS = [
    "arm_id", "algorithm", "seed", "solver_calls", "l0_rejected", "feasible_count",
    "best_cost", "median_cost", "archive_size", "solver_records", "solver_failed",
    "crash_rate", "invalidated", "invalidation_reason",
]


class ExperimentStopped(RuntimeError):
    """Thí nghiệm không thể phát biểu kết luận theo pre-registration ⇒ DỪNG.

    Không bao giờ được nuốt thành một verdict mềm: 'KHÔNG ĐẠT' nghĩa là ĐÃ KIỂM
    và BÁC BỎ, còn đây là CHƯA KIỂM ĐƯỢC.
    """


def _restricted_domains(grammar_id: str, restriction: dict) -> dict[str, list]:
    base = gene_domains(grammar_id)
    out = dict(base)
    for k, v in restriction.items():
        if k in out:
            allowed = set(v)
            filtered = [x for x in out[k] if x in allowed]
            if not filtered:
                raise ValueError(f"Miền bị lọc rỗng cho {k}: {v}")
            out[k] = filtered
    return out


def _restricted_random_search(
    budget: int,
    seed: int,
    grammar_id: str,
    domains: dict,
) -> dict:
    rng = random.Random(seed)
    order = list(domains)
    ev = BudgetedEvaluator(budget, generation_action="RANDOM_SEARCH", seed=seed,
                           grammar_id=grammar_id)
    archive = ParetoArchive()
    max_proposals = max(10_000, budget * 1000)

    while not ev.exhausted and ev.n_proposals < max_proposals:
        gene = {name: rng.choice(domains[name]) for name in order}
        rec = ev.evaluate_gene(gene)
        if rec and rec["feasible"]:
            archive.add(rec["case_id"], rec["objectives"], {"gene": rec["gene"]})

    config = {**ev.config, "algorithm": "random_search", "max_proposals": max_proposals}
    return {
        "algorithm": "random_search", "seed": seed, "grammar_id": grammar_id,
        "config": config, "counters": ev.counters, "history": ev.history,
        "proposal_history": ev.proposal_history, "archive": archive,
        "termination": "budget_exhausted" if ev.exhausted else "proposal_guard"
    }


def _restricted_nsga2(
    budget: int,
    seed: int,
    grammar_id: str,
    domains: dict,
    pop_size: int = 40,
    p_crossover: float = 0.9,
) -> dict:
    rng = random.Random(seed)
    order = list(domains)
    sizes = [len(domains[k]) for k in order]
    n_var = len(order)
    p_mut = 1.0 / n_var

    ev = BudgetedEvaluator(budget, generation_action="NSGA2", seed=seed,
                           grammar_id=grammar_id)
    archive = ParetoArchive()
    max_proposals = max(10_000, budget * 1000)

    def decode(idx_vec):
        return {k: domains[k][i] for k, i in zip(order, idx_vec)}

    def evaluate(idx_vec):
        rec = ev.evaluate_gene(decode(idx_vec))
        if rec is None:
            return None
        if rec["feasible"]:
            archive.add(rec["case_id"], rec["objectives"], {"gene": rec["gene"]})
        return {**rec, "x": list(idx_vec)}

    def mutate(x):
        y = list(x)
        for j in range(n_var):
            if rng.random() < p_mut:
                if rng.random() < 0.5:
                    y[j] = min(sizes[j] - 1, max(0, y[j] + rng.choice((-1, 1))))
                else:
                    y[j] = rng.randrange(sizes[j])
        return y

    def crossover(a, b):
        if rng.random() > p_crossover:
            return list(a), list(b)
        c1, c2 = list(a), list(b)
        for j in range(n_var):
            if rng.random() < 0.5:
                c1[j], c2[j] = c2[j], c1[j]
        return c1, c2

    pop = []
    seen = set()
    while (len(pop) < pop_size and not ev.exhausted and ev.n_proposals < max_proposals):
        x = [rng.randrange(s) for s in sizes]
        if tuple(x) in seen:
            continue
        seen.add(tuple(x))
        ind = evaluate(x)
        if ind:
            pop.append(ind)

    while not ev.exhausted and pop and ev.n_proposals < max_proposals:
        fronts = _fast_nondominated_sort(pop)
        rank = {}
        crowd = {}
        for fi, front in enumerate(fronts):
            cd = _crowding(pop, front)
            for i in front:
                rank[i], crowd[i] = fi, cd[i]

        def tournament():
            i, j = rng.randrange(len(pop)), rng.randrange(len(pop))
            if rank[i] != rank[j]:
                return pop[i] if rank[i] < rank[j] else pop[j]
            return pop[i] if crowd[i] >= crowd[j] else pop[j]

        offspring = []
        while (len(offspring) < pop_size and not ev.exhausted and ev.n_proposals < max_proposals):
            c1, c2 = crossover(tournament()["x"], tournament()["x"])
            for c in (mutate(c1), mutate(c2)):
                ind = evaluate(c)
                if ind:
                    offspring.append(ind)
                if (len(offspring) >= pop_size or ev.exhausted or ev.n_proposals >= max_proposals):
                    break

        union = pop + offspring
        fronts = _fast_nondominated_sort(union)
        new_pop = []
        for front in fronts:
            cd = _crowding(union, front)
            if len(new_pop) + len(front) <= pop_size:
                new_pop.extend(union[i] for i in front)
            else:
                rest = sorted(front, key=lambda i: cd[i], reverse=True)
                new_pop.extend(union[i] for i in rest[:pop_size - len(new_pop)])
                break
        pop = new_pop

    config = {**ev.config, "algorithm": "nsga2", "pop_size": pop_size, "p_crossover": p_crossover}
    return {
        "algorithm": "nsga2", "seed": seed, "grammar_id": grammar_id,
        "config": config, "counters": ev.counters, "history": ev.history,
        "proposal_history": ev.proposal_history, "archive": archive,
        "termination": "budget_exhausted" if ev.exhausted else "proposal_guard"
    }


def summarize_history(history: list[dict]) -> dict:
    """Rút gọn một history của BudgetedEvaluator thành các thống kê của một run.

    Tách riêng để test có thể so khớp ĐỘC LẬP trên CÙNG MỘT history mà
    ``run_single_arm`` đã dùng (xem test_summarizer_agrees_with_independent_count).
    """
    # BudgetedEvaluator._record_result luu objectives la TUPLE theo dung thu tu
    # OBJECTIVE_KEYS = (relative_cost, material_mass_t, embodied_carbon_kgCO2e),
    # KHONG phai dict. Ban truoc viet item["objectives"]["relative_cost"] va gate
    # bang '"relative_cost" in item["objectives"]' — dieu kien do kiem chuoi co
    # nam trong mot tuple cac so hay khong, nen LUON False: moi run bao
    # feasible_count = 0, best_cost = None, va phan quyet duoc sinh ra tu
    # n_paired_seeds = 0. Cung lop loi voi pymoo_adapter da va o BRD-009.
    cost_index = OBJECTIVE_KEYS.index("relative_cost")
    feasible_costs = [
        float(item["objectives"][cost_index])
        for item in history
        if item.get("feasible") and item.get("objectives") is not None
    ]

    # Mẫu số crash rate = số record ĐÃ THỰC SỰ mở solver (solver_call_index != None);
    # record bị L0 loại không mở solver nên không thuộc mẫu số.
    solver_records = [item for item in history if item.get("solver_call_index") is not None]
    solver_failed = [item for item in solver_records if item.get("status") == "SOLVER_FAILED"]

    return {
        "feasible_count": len(feasible_costs),
        "best_cost": min(feasible_costs) if feasible_costs else None,
        "median_cost": statistics.median(feasible_costs) if feasible_costs else None,
        "solver_records": len(solver_records),
        "solver_failed": len(solver_failed),
        "crash_rate": (len(solver_failed) / len(solver_records)) if solver_records else 0.0,
    }


def run_single_arm(
    arm: dict,
    algorithm: str,
    seed: int,
    budget: int,
    *,
    return_history: bool = False,
) -> dict:
    """Chạy một (arm, algorithm, seed) và tóm tắt kết quả.

    ``return_history=True`` trả kèm khóa ``history`` — chính history của lần chạy
    này — để test kiểm chứng hành vi tóm tắt mà không phải chạy một tối ưu khác.
    """
    grammar_id = arm["grammar_id"]
    restriction = arm.get("domain_restriction", {})
    search_path = arm.get("search_path", "reference_api")

    if search_path == "local_restricted_domain_path" or restriction:
        domains = _restricted_domains(grammar_id, restriction)
        if algorithm == "random_search":
            res = _restricted_random_search(budget, seed, grammar_id, domains)
        else:
            res = _restricted_nsga2(budget, seed, grammar_id, domains)
    else:
        if algorithm == "random_search":
            res = random_search(budget, seed=seed, grammar_id=grammar_id)
        else:
            res = nsga2(budget, seed=seed, grammar_id=grammar_id)

    history = res.get("history", [])
    stats = summarize_history(history)
    counters = res.get("counters", {})

    out = {
        "arm_id": arm["arm_id"],
        "algorithm": algorithm,
        "seed": seed,
        "solver_calls": counters.get("solver_calls", 0),
        "l0_rejected": counters.get("l0_rejected", 0),
        "feasible_count": stats["feasible_count"],
        "best_cost": stats["best_cost"],
        "median_cost": stats["median_cost"],
        "solver_records": stats["solver_records"],
        "solver_failed": stats["solver_failed"],
        "crash_rate": stats["crash_rate"],
        "archive_size": len(res["archive"].entries) if hasattr(res.get("archive"), "entries") else len(res.get("archive", [])),
    }
    if return_history:
        out["history"] = history
    return out


def bootstrap_ci(
    diffs: list[float],
    n_resamples: int = 10000,
    alpha: float = 0.05,
    seed: int = 42,
) -> tuple[float, float, float]:
    """Bootstrap CI của TRUNG BÌNH — thống kê PHỤ (primary là trung vị + Wilcoxon)."""
    if not diffs:
        return 0.0, 0.0, 0.0
    rng = random.Random(seed)
    n = len(diffs)
    means = []
    for _ in range(n_resamples):
        sample = [rng.choice(diffs) for _ in range(n)]
        means.append(statistics.mean(sample))
    means.sort()
    low_idx = int(n_resamples * (alpha / 2))
    high_idx = int(n_resamples * (1 - alpha / 2))
    return statistics.mean(diffs), means[low_idx], means[high_idx]


def _invalidation_threshold(prereg: dict, condition_id: str) -> tuple[float, dict]:
    """Đọc ngưỡng số của một invalidation condition thẳng từ pre-registration."""
    conditions = prereg.get("invalidation_conditions", [])
    cond = next((c for c in conditions if c.get("condition_id") == condition_id), None)
    if cond is None:
        raise ExperimentStopped(
            f"pre-registration thiếu invalidation condition {condition_id}")
    numbers = _NUMBER_RE.findall(str(cond.get("threshold", "")))
    if not numbers:
        raise ExperimentStopped(
            f"không đọc được ngưỡng số của {condition_id}: {cond.get('threshold')!r}")
    return float(numbers[-1]), cond


def registered_seeds(prereg: dict) -> list[int]:
    """Tập seed ĐÃ ĐĂNG KÝ, lấy đúng từ seed_start..seed_end của pre-registration."""
    budget = prereg["budget"]
    seeds = list(range(int(budget["seed_start"]), int(budget["seed_end"]) + 1))
    n_registered = int(budget.get("n_seeds", len(seeds)))
    if n_registered != len(seeds):
        raise ExperimentStopped(
            f"pre-registration tự mâu thuẫn: n_seeds={n_registered} nhưng "
            f"seed_start..seed_end cho {len(seeds)} seed")
    return seeds


def check_seed_compliance(seeds: list[int], prereg: dict) -> dict:
    """So khớp TẬP SEED CHÍNH XÁC (không chỉ số lượng) với pre-registration."""
    expected = registered_seeds(prereg)
    executed = list(seeds)
    missing = sorted(set(expected) - set(executed))
    unexpected = sorted(set(executed) - set(expected))
    duplicated = sorted({s for s in executed if executed.count(s) > 1})
    match = not missing and not unexpected and not duplicated

    detail = ""
    if not match:
        parts = []
        if missing:
            parts.append(f"thiếu seed {missing}")
        if unexpected:
            parts.append(f"seed lạ {unexpected}")
        if duplicated:
            parts.append(f"seed lặp {duplicated}")
        detail = "; ".join(parts)

    return {
        "seeds_registered": len(expected),
        "seeds_executed": len(executed),
        "seed_set_registered": expected,
        "seed_set_executed": executed,
        "seed_set_exact_match": match,
        "seed_set_mismatch_detail": detail,
        "seed_compliance": ("khop giao thuc" if match else
                            "CHAY LECH GIAO THUC — tap seed thuc chay khac tap seed da dang ky"),
    }


def check_protocol_compliance(results: list[dict], seeds: list[int], prereg: dict) -> dict:
    """Enforce toàn bộ invalidation condition TRƯỚC khi tính bất kỳ thống kê nào.

    Trả về dict compliance; ``violations`` khác rỗng nghĩa là phải DỪNG.
    """
    compliance = dict(check_seed_compliance(seeds, prereg))
    violations: list[dict] = []

    if not compliance["seed_set_exact_match"]:
        violations.append({
            "condition_id": "SEED_SET_MISMATCH",
            "action": "STOP",
            "detail": ("tap seed thuc chay khac tap seed da dang ky: "
                       + compliance["seed_set_mismatch_detail"]),
        })

    required_calls_f, budget_cond = _invalidation_threshold(prereg, "UNEQUAL_SOLVER_BUDGET")
    required_calls = int(required_calls_f)
    declared_calls = int(prereg["budget"]["solver_calls_per_run"])
    if required_calls != declared_calls:
        raise ExperimentStopped(
            f"pre-registration tự mâu thuẫn: budget.solver_calls_per_run={declared_calls} "
            f"nhưng UNEQUAL_SOLVER_BUDGET nói {required_calls}")

    crash_threshold, crash_cond = _invalidation_threshold(prereg, "SOLVER_CRASH_RATE")

    invalidated: list[dict] = []
    over_crash: list[dict] = []
    solver_records_total = 0
    solver_failed_total = 0

    for run in results:
        run_id = {"arm_id": run.get("arm_id"), "algorithm": run.get("algorithm"),
                  "seed": run.get("seed")}
        calls = int(run.get("solver_calls", 0))
        if calls != required_calls:
            reason = f"solver_calls={calls} != {required_calls}"
            run["invalidated"] = True
            run["invalidation_reason"] = reason
            invalidated.append({**run_id, "solver_calls": calls,
                                "condition_id": budget_cond.get("condition_id"),
                                "action": budget_cond.get("action"),
                                "detail": reason})
        else:
            run.setdefault("invalidated", False)
            run.setdefault("invalidation_reason", None)

        n_records = int(run.get("solver_records", 0))
        n_failed = int(run.get("solver_failed", 0))
        solver_records_total += n_records
        solver_failed_total += n_failed
        rate = (n_failed / n_records) if n_records else 0.0
        run["crash_rate"] = rate
        if rate > crash_threshold:
            over_crash.append({**run_id, "crash_rate": round(rate, 4)})

    experiment_crash_rate = (solver_failed_total / solver_records_total
                             if solver_records_total else 0.0)

    if invalidated:
        violations.append({
            "condition_id": budget_cond.get("condition_id", "UNEQUAL_SOLVER_BUDGET"),
            "action": budget_cond.get("action", "INVALIDATE_RUN"),
            "detail": (f"{len(invalidated)} run co solver_calls != {required_calls} "
                       f"nen bi loai khoi phan tich ⇒ thieu cap de ghep"),
        })

    if over_crash or experiment_crash_rate > crash_threshold:
        violations.append({
            "condition_id": crash_cond.get("condition_id", "SOLVER_CRASH_RATE"),
            "action": crash_cond.get("action", "INVALIDATE_EXPERIMENT"),
            "detail": (f"crash_rate toan thi nghiem = {experiment_crash_rate:.4f}, "
                       f"{len(over_crash)} run vuot nguong {crash_threshold}"),
        })

    compliance.update({
        "solver_calls_required": required_calls,
        "n_runs_total": len(results),
        "n_invalidated_runs": len(invalidated),
        "invalidated_runs": invalidated,
        "crash_rate_threshold": crash_threshold,
        "solver_records_total": solver_records_total,
        "solver_failed_total": solver_failed_total,
        "crash_rate_experiment": round(experiment_crash_rate, 6),
        "runs_over_crash_threshold": over_crash,
        "violations": violations,
    })
    return compliance


def paired_improvement_pct(results: list[dict], baseline_arm: str, treatment_arm: str,
                           algorithm: str = "nsga2") -> tuple[list[int], list[float]]:
    """Chênh lệch ghép cặp theo % cải thiện của treatment so với baseline.

    Dương nghĩa là treatment (v2) rẻ hơn baseline (A4). Run bị invalidated bị loại.
    """
    def _index(arm_id: str) -> dict[int, float]:
        return {r["seed"]: r["best_cost"] for r in results
                if r.get("arm_id") == arm_id and r.get("algorithm") == algorithm
                and r.get("best_cost") is not None and not r.get("invalidated", False)}

    base = _index(baseline_arm)
    treat = _index(treatment_arm)
    common = sorted(set(base) & set(treat))
    diffs = []
    for s in common:
        c_base = float(base[s])
        c_treat = float(treat[s])
        if c_base == 0.0:
            raise ExperimentStopped(
                f"best_cost cua {baseline_arm} bang 0 tai seed {s} — khong the chuan hoa %")
        diffs.append(((c_base - c_treat) / c_base) * 100.0)
    return common, diffs


def evaluate_primary_endpoint(
    diffs: list[float],
    prereg: dict,
    *,
    n_resamples: int = 10000,
    bootstrap_seed: int = 42,
) -> dict:
    """Phép kiểm chính ĐÃ ĐĂNG KÝ: paired Wilcoxon (chính) + bootstrap CI (phụ).

    H1 chỉ được chấp nhận khi ``p < alpha`` VÀ ``median >= threshold`` (2.0%).
    Hàm thuần: không đọc file, không ghi file — test gọi trực tiếp được.
    Mọi tình huống không kiểm được đều raise ``ExperimentStopped``.
    """
    endpoint = prereg["primary_endpoint"]
    test_name = endpoint.get("statistical_test")
    if test_name != REQUIRED_STATISTICAL_TEST:
        raise ExperimentStopped(
            f"pre-registration khoa phep kiem {test_name!r}, runner chi hien thuc "
            f"{REQUIRED_STATISTICAL_TEST!r}")

    confidence = float(endpoint["confidence_level"])
    alpha = round(1.0 - confidence, 10)
    threshold_pct = float(endpoint["threshold_relative"]) * 100.0

    if not diffs:
        raise ExperimentStopped("khong co cap seed nao de kiem dinh")
    if _scipy_wilcoxon is None:
        raise ExperimentStopped(
            f"thieu scipy.stats.wilcoxon nen khong chay duoc phep kiem da dang ky "
            f"({_WILCOXON_IMPORT_ERROR})")
    if all(d == 0.0 for d in diffs):
        raise ExperimentStopped(
            "moi chenh lech ghep cap bang 0 — Wilcoxon suy bien, khong kiem dinh duoc")

    try:
        stat, p_value = _scipy_wilcoxon(
            diffs, zero_method=WILCOXON_ZERO_METHOD, alternative=WILCOXON_ALTERNATIVE)
    except Exception as exc:  # không nuốt lỗi: chuyển thẳng sang STOP
        raise ExperimentStopped(f"scipy.stats.wilcoxon that bai: {exc}") from exc

    p_value = float(p_value)
    stat = float(stat)
    if math.isnan(p_value):
        raise ExperimentStopped("Wilcoxon tra p_value = NaN — khong kiem dinh duoc")

    median_pct = float(statistics.median(diffs))
    mean_pct, ci_low, ci_high = bootstrap_ci(
        diffs, n_resamples=n_resamples, alpha=alpha, seed=bootstrap_seed)

    h1_supported = bool(p_value < alpha and median_pct >= threshold_pct)
    if h1_supported:
        verdict = (f"ĐẠT (H1 được chấp nhận: p = {p_value:.4g} < {alpha} và trung vị "
                   f"cải thiện {median_pct:.2f}% >= {threshold_pct:.1f}%)")
    else:
        verdict = (f"KHÔNG ĐẠT (H0 giữ vững: p = {p_value:.4g}, trung vị cải thiện "
                   f"{median_pct:.2f}%, cần p < {alpha} VÀ trung vị >= {threshold_pct:.1f}%)")

    return {
        "n_paired_seeds": len(diffs),
        "primary_statistic": "median_improvement_pct",
        "statistical_test": REQUIRED_STATISTICAL_TEST,
        "alpha": alpha,
        "confidence_level": confidence,
        "threshold_median_pct": threshold_pct,
        "median_improvement_pct": round(median_pct, 4),
        "wilcoxon": {
            "statistic": stat,
            "p_value": p_value,
            "zero_method": WILCOXON_ZERO_METHOD,
            "alternative": WILCOXON_ALTERNATIVE,
            "note": ("zero_method='pratt' giữ chênh lệch 0 trong xếp hạng; "
                     "alternative='two-sided' không giả định sẵn chiều cải thiện"),
        },
        "secondary_bootstrap": {
            "role": "THONG KE PHU — khong dung de ra phan quyet",
            "statistic": "mean_improvement_pct",
            "mean_improvement_pct": round(mean_pct, 4),
            "bootstrap_ci_95_pct": [round(ci_low, 4), round(ci_high, 4)],
            "n_resamples": n_resamples,
        },
        "decision_rule": "H1 <=> (p_value < alpha) AND (median_improvement_pct >= threshold)",
        "h1_supported": h1_supported,
        "verdict": verdict,
    }


def _write_outputs(output_dir: Path, summary: dict, results: list[dict]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    with (output_dir / "summary.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=RUN_CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for r in results:
            writer.writerow(r)


def execute_confirmatory_experiment(
    prereg_path: Path = DEFAULT_PREREG,
    seeds: list[int] | None = None,
    output_dir: Path | None = None,
) -> dict:
    """Chạy thí nghiệm confirmatory và ghi summary.

    Trả về summary dict với ``status`` là ``"COMPLETED"`` (có ``verdict``) hoặc
    ``"STOPPED"`` (KHÔNG có ``verdict``, có ``stop_reason``). Người gọi phải đọc
    ``status``; ``main()`` biến STOP thành exit code khác 0.
    """
    prereg_path = Path(prereg_path)
    prereg_bytes = prereg_path.read_bytes()
    prereg = json.loads(prereg_bytes.decode("utf-8"))
    created_at = datetime.now(timezone.utc).isoformat()

    if output_dir is None:
        output_dir = ROOT / "experiments" / "results" / f"confirmatory_ab_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    output_dir = Path(output_dir)

    results: list[dict] = []
    compliance: dict | None = None
    endpoint_result: dict | None = None
    common_seeds_a2_a4: list[int] = []
    stop_reason: str | None = None

    try:
        arms = prereg["arms"]
        algorithms = prereg["algorithms"]
        budget = int(prereg["budget"]["solver_calls_per_run"])
        registered = registered_seeds(prereg)
        if seeds is None:
            seeds = list(registered)
        seeds = list(seeds)

        # Kiểm tra tập seed TRƯỚC khi đốt ngân sách solver: một lần chạy lệch
        # giao thức không thể dùng để phát biểu gì, nên không cần chạy.
        seed_check = check_seed_compliance(seeds, prereg)
        if not seed_check["seed_set_exact_match"]:
            compliance = {**seed_check, "violations": [{
                "condition_id": "SEED_SET_MISMATCH", "action": "STOP",
                "detail": seed_check["seed_set_mismatch_detail"]}]}
            raise ExperimentStopped(
                f"tap seed thuc chay khac tap seed da dang ky "
                f"({seed_check['seeds_executed']}/{seed_check['seeds_registered']}): "
                f"{seed_check['seed_set_mismatch_detail']}")

        print("=== Starting Confirmatory A/B Trial (Task BRD-013) ===")
        print(f"Arms: {[a['arm_id'] for a in arms]}")
        print(f"Algorithms: {algorithms} | Seeds: {len(seeds)} (Range {seeds[0]}..{seeds[-1]})")
        print(f"Budget per run: {budget} solver calls\n")

        for arm in arms:
            for algo in algorithms:
                for seed in seeds:
                    res = run_single_arm(arm, algo, seed, budget)
                    results.append(res)
                    print(f"[{arm['arm_id']}] algo={algo} seed={seed:02d} -> "
                          f"best_cost={res['best_cost']} (calls={res['solver_calls']})")

        # --- Gate giao thức: chạy TRƯỚC mọi phép thống kê ---
        compliance = check_protocol_compliance(results, seeds, prereg)
        if compliance["violations"]:
            detail = "; ".join(v["detail"] for v in compliance["violations"])
            raise ExperimentStopped(f"vi pham dieu kien invalidation: {detail}")

        # --- Ghép cặp A2 (v2 shape only) vs A4 (v1 restricted {5,6}) trên NSGA2 ---
        baseline_arm = prereg.get("baseline_arms", {}).get(
            "controlled_baseline", "A4_v1_restricted_girders")
        treatment_arm = "A2_v2_shape_only"
        common_seeds_a2_a4, diffs_a2_a4_pct = paired_improvement_pct(
            results, baseline_arm, treatment_arm, algorithm="nsga2")

        n_registered = len(registered)
        if len(common_seeds_a2_a4) < n_registered:
            raise ExperimentStopped(
                f"chi ghep cap duoc {len(common_seeds_a2_a4)}/{n_registered} seed da dang ky "
                f"(mot trong hai arm khong tim ra phuong an kha thi o cac seed con lai) — "
                f"khong du du lieu de phat bieu theo pre-registration")

        endpoint_result = evaluate_primary_endpoint(diffs_a2_a4_pct, prereg)

    except ExperimentStopped as exc:
        stop_reason = str(exc)

    for r in results:
        r.setdefault("invalidated", False)
        r.setdefault("invalidation_reason", None)

    summary = {
        "schema_version": "1.1",
        "task_id": "BRD-013",
        "analysis_revision": "BRD-015",
        "created_at_utc": created_at,
        "software_version": __version__,
        "preregistration_sha256": hashlib.sha256(prereg_bytes).hexdigest(),
        "n_runs_total": len(results),
        "seeds_registered": (compliance or {}).get("seeds_registered"),
        "seeds_executed": (compliance or {}).get("seeds_executed"),
        "seed_compliance": (compliance or {}).get("seed_compliance"),
        "n_paired_seeds": len(common_seeds_a2_a4),
        "protocol_compliance": compliance,
    }

    if stop_reason is None and endpoint_result is not None:
        summary["status"] = "COMPLETED"
        summary["verdict"] = endpoint_result["verdict"]
        summary["comparison_A2_vs_A4_nsga2"] = endpoint_result
    else:
        # FAIL-CLOSED: khong ghi khoa verdict, khong ghi bat ky chuoi nao trong
        # nhu mot phan quyet. Thieu du lieu la DUNG, khong phai ket luan.
        summary["status"] = "STOPPED"
        summary["stop_reason"] = stop_reason or "khong tao duoc ket qua diem cuoi chinh"

    summary["runs"] = results
    _write_outputs(output_dir, summary, results)

    if summary["status"] == "STOPPED":
        print("", file=sys.stderr)
        print("=" * 50, file=sys.stderr)
        print("THI NGHIEM BI DUNG (STOP) — khong phat bieu phan quyet.", file=sys.stderr)
        print(f"Ly do: {summary['stop_reason']}", file=sys.stderr)
        print(f"Summary (de kiem toan) da ghi tai: {output_dir}", file=sys.stderr)
        print("=" * 50, file=sys.stderr)
        return summary

    ep = endpoint_result
    sec = ep["secondary_bootstrap"]
    print("\n==================================================")
    print("Confirmatory Trial Complete!")
    print(f"Verdict: {ep['verdict']}")
    print(f"[PRIMARY] median improvement = {ep['median_improvement_pct']:.2f}% | "
          f"Wilcoxon p = {ep['wilcoxon']['p_value']:.4g} "
          f"(zero_method={WILCOXON_ZERO_METHOD}, alternative={WILCOXON_ALTERNATIVE})")
    print(f"[SECONDARY] mean improvement = {sec['mean_improvement_pct']:.2f}% "
          f"(95% CI: {sec['bootstrap_ci_95_pct']})")
    print(f"Results saved to: {output_dir}")
    print("==================================================")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run confirmatory grammar A/B trial")
    parser.add_argument("--seeds", type=int, default=None,
                        help="So seed chay tu seed_start (mac dinh: dung tap seed da dang ky)")
    parser.add_argument("--prereg", type=Path, default=DEFAULT_PREREG,
                        help="Duong dan file pre-registration")
    parser.add_argument("--output-dir", type=Path, default=None,
                        help="Thu muc ghi summary.json / summary.csv")
    args = parser.parse_args(argv)

    seed_list: list[int] | None = None
    if args.seeds is not None:
        prereg = json.loads(Path(args.prereg).read_text(encoding="utf-8"))
        start = int(prereg["budget"]["seed_start"])
        seed_list = list(range(start, start + args.seeds))

    summary = execute_confirmatory_experiment(
        prereg_path=args.prereg, seeds=seed_list, output_dir=args.output_dir)
    return 0 if summary.get("status") == "COMPLETED" else STOP_EXIT_CODE


if __name__ == "__main__":
    sys.exit(main())
