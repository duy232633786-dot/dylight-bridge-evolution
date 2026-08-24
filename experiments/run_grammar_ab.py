"""Thí nghiệm A/B grammar: tiết diện định hình (v1) vs AI tự thiết kế hình dạng (v2).

Câu hỏi, arm, ngân sách, metric, hypervolume protocol và tiêu chí bác bỏ đều nằm
trong ``experiments/preregistration/grammar_ab_v1_vs_v2.json`` và được KHÓA TRƯỚC
khi chạy. Script này ĐỌC file đó làm nguồn sự thật duy nhất cho định nghĩa arm —
không có arm nào được định nghĩa cứng trong code — rồi nhúng nguyên văn vào
manifest. Thiếu file pre-registration thì thí nghiệm KHÔNG được chạy.

Ngân sách giữ đúng một nghĩa của ``BudgetedEvaluator``: số lần
``solver.status != NOT_RUN``. Proposal bị L0 loại, cache hit và proposal bị chặn
vì hết ngân sách đều không tiêu ngân sách và được báo riêng.

Về arm A2 (cô lập hiệu ứng hình dạng): API tham chiếu ``random_search``/``nsga2``
chỉ nhận ``grammar_id``, không nhận miền đã lọc. Lọc ứng viên Ở TẦNG ĐỀ XUẤT là
SAI ngân sách nên bị cấm. Vì vậy A2 đi qua một đường tìm kiếm riêng trong chính
file này (``_restricted_random_search`` / ``_restricted_nsga2``) dùng trực tiếp
``BudgetedEvaluator`` với miền đã lọc — miền hẹp được truyền xuống bộ sinh gene
nên ứng viên ngoài miền không bao giờ được sinh ra. Hai hàm đó là bản sao trung
thành của thuật toán tham chiếu (dùng lại nguyên hàm chọn lọc của ``nsga2``);
``tests/test_grammar_ab_experiment.py`` khóa điều kiện tương đương: với miền
KHÔNG bị lọc, đường riêng phải cho lịch sử trùng khớp API tham chiếu.

Claim ceiling: SCREENED. Số liệu ở đây là L0 + L1 line-girder sơ bộ, KHÔNG phải
thiết kế và không được gọi là build-ready.
"""
import argparse
import csv
import hashlib
import json
import random
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from bridge_evolution import __version__                              # noqa: E402
from bridge_evolution.optimization import nsga2, random_search        # noqa: E402
from bridge_evolution.optimization.common import (                    # noqa: E402
    BudgetedEvaluator, gene_domains, gene_order,
)
# Dùng lại NGUYÊN hàm chọn lọc của thuật toán tham chiếu để đường tìm kiếm riêng
# của A2 không khác A1/A3 ở phần logic tiến hóa (chỉ khác ở miền biến).
from bridge_evolution.optimization.nsga2 import (                     # noqa: E402
    _crowding, _fast_nondominated_sort,
)
from bridge_evolution.pareto import ParetoArchive                     # noqa: E402
from experiments.run_baseline import (                                # noqa: E402
    HV_IDEAL_3D, HV_MC_SAMPLES, HV_MC_SEED, HV_REFERENCE_3D,
    _write_history_csv, _write_jsonl, add_hypervolume, summarize,
)

# Console Windows có thể vẫn dùng cp1252 dù file/report là UTF-8.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

#: Pre-registration mặc định; đổi bằng --preregistration khi cần bản version khác.
DEFAULT_PREREG = ROOT / "experiments" / "preregistration" / "grammar_ab_v1_vs_v2.json"

#: Khóa bắt buộc phải có trong pre-registration — thiếu là dừng, không chạy.
REQUIRED_PREREG_KEYS = (
    "research_question", "arms", "confounds", "algorithms", "budget_per_run",
    "budget_definition", "seeds", "metrics", "hypervolume_protocol",
    "decision_rule", "falsification_criterion", "invalidation_conditions",
    "claim_ceiling",
)

#: Metric đã đăng ký, đúng thứ tự dùng trong summary.csv và summary.md.
METRIC_KEYS = [
    "best_relative_cost", "median_feasible_cost", "solver_conditional_feasible_rate",
    "first_feasible_solver_call", "hypervolume_2d_cost_carbon", "hypervolume_3d_mc",
    "archive_size", "best_material_mass_t", "best_embodied_carbon",
]
#: Bộ đếm ngân sách — báo riêng để không ai nhầm proposal với solver call.
#: ``l0_checks`` có mặt vì sàng L0 là MIỄN PHÍ (không tiêu ngân sách) nên số lần
#: sàng là một confound thật giữa các arm; giấu nó đi là giấu bất đối xứng.
COUNTER_KEYS = ["proposals", "l0_checks", "l0_rejected", "cache_hits",
                "solver_calls", "feasible_count"]
#: Hệ số tương quan giữa các mục tiêu, dùng cho cảnh báo suy biến.
CORR_KEYS = ["corr_cost_mass", "corr_cost_carbon", "corr_mass_carbon"]

#: Ba trạng thái phán quyết. VERDICT_VOID là trạng thái thứ ba bắt buộc: một so
#: sánh bị điều kiện vô hiệu (hoặc chạy lệch giao thức) chạm vào thì KHÔNG kết
#: luận theo hướng nào — không ĐẠT mà cũng không được ghi là kết quả âm.
VERDICT_PASS = "ĐẠT"
VERDICT_FAIL = "KHÔNG ĐẠT — KẾT QUẢ ÂM"
VERDICT_VOID = "VÔ HIỆU"

#: Nhãn dán toàn báo cáo khi cấu hình chạy lệch run matrix đã đăng ký.
DEVIATION_LABEL = "CHẠY LỆCH GIAO THỨC — KHÔNG DÙNG ĐỂ KẾT LUẬN"
COMPLIANCE_LABEL = "khớp giao thức"

#: Điều kiện vô hiệu mà runner THẬT SỰ đánh giá được cho từng run. Pre-registration
#: khai báo auto_evaluated_in_runner cho từng điều kiện; hai tập phải khớp, nếu
#: không thì hoặc file nói dối, hoặc code thiếu — cả hai đều phải DỪNG.
IMPLEMENTED_INVALIDATION_CONDITIONS = frozenset({
    "DEGENERATE_FRONT", "NO_FEASIBLE", "FEASIBLE_RATE_TOO_LOW",
    "OBJECTIVES_COLLINEAR", "UNEQUAL_SOLVER_BUDGET",
})

METRIC_LABELS = {
    "best_relative_cost": "Chi phí tương đối tốt nhất",
    "median_feasible_cost": "Chi phí trung vị khả thi",
    # Dấu | phải escape: nhãn nằm trong ô của bảng Markdown.
    "solver_conditional_feasible_rate": r"P(khả thi \| solver chạy)",
    "first_feasible_solver_call": "Solver call tới khả thi đầu tiên",
    "hypervolume_2d_cost_carbon": "HV 2D (cost×carbon)",
    "hypervolume_3d_mc": "HV 3D (MC, seed cố định)",
    "archive_size": "Kích thước Pareto front",
    "best_material_mass_t": "Khối lượng vật liệu nhỏ nhất (t)",
    "best_embodied_carbon": "Carbon hàm chứa nhỏ nhất (kgCO2e)",
}

ALGO_IDS = ("rs", "nsga2")


# ------------------------------------------------------------ pre-registration
def load_preregistration(path: Path) -> dict:
    """Nạp và kiểm tra pre-registration; thiếu/không hợp lệ là DỪNG thí nghiệm.

    Không có pre-registration thì không có câu hỏi, ngân sách và tiêu chí bác bỏ
    khóa trước, nên kết quả không phải bằng chứng — chạy tiếp là vi phạm
    MARP-1.0 §Quy tắc nghiên cứu 1.
    """
    if not path.is_file():
        raise FileNotFoundError(
            f"Không tìm thấy pre-registration: {path}. Thí nghiệm bị DỪNG — "
            "không được chạy A/B khi câu hỏi, ngân sách và tiêu chí bác bỏ "
            "chưa được khóa trước."
        )
    with path.open(encoding="utf-8") as f:
        prereg = json.load(f)

    missing = [k for k in REQUIRED_PREREG_KEYS if k not in prereg]
    if missing:
        raise ValueError(
            f"Pre-registration thiếu khóa bắt buộc {missing}; DỪNG thí nghiệm.")

    hv = prereg["hypervolume_protocol"]
    # Hằng HV phải khớp NGUYÊN VĂN bản đã khóa trong run_baseline. Nếu lệch thì
    # hoặc pre-registration sai, hoặc ai đó đã sửa protocol sau khi thấy kết quả.
    locked = {
        "ideal_3d": list(HV_IDEAL_3D),
        "reference_3d": list(HV_REFERENCE_3D),
        "mc_samples": HV_MC_SAMPLES,
        "mc_seed": HV_MC_SEED,
    }
    for key, expected in locked.items():
        actual = hv.get(key)
        if isinstance(expected, list):
            actual = list(actual) if actual is not None else None
        if actual != expected:
            raise ValueError(
                f"hypervolume_protocol/{key} = {actual!r} lệch hằng đã khóa trong "
                f"experiments/run_baseline.py ({expected!r}). DỪNG: reference point "
                "không được suy hay sửa theo kết quả."
            )

    _check_invalidation_conditions(prereg)
    return prereg


def _check_invalidation_conditions(prereg: dict) -> None:
    """Điều kiện vô hiệu phải khai báo đúng cái nào runner tự đánh giá được.

    Điều kiện tự nhận ``auto_evaluated_in_runner`` nhưng runner không hiện thực
    là một lời hứa suông trong báo cáo; ngược lại, runner đánh giá một điều kiện
    mà file không khai báo thì ngưỡng đang bị hard-code. Cả hai đều DỪNG.
    """
    conditions = prereg["invalidation_conditions"]["conditions"]
    declared_auto = set()
    for cond in conditions:
        cid = cond["condition_id"]
        if "auto_evaluated_in_runner" not in cond:
            raise ValueError(
                f"invalidation condition {cid} thiếu 'auto_evaluated_in_runner'; "
                "DỪNG: không được im lặng về việc điều kiện có được đánh giá hay không.")
        if cond["auto_evaluated_in_runner"]:
            declared_auto.add(cid)
        elif not cond.get("evaluation_note"):
            raise ValueError(
                f"invalidation condition {cid} không được đánh giá tự động nhưng "
                "thiếu 'evaluation_note' giải thích ai/khi nào kiểm nó. DỪNG.")

    if declared_auto != set(IMPLEMENTED_INVALIDATION_CONDITIONS):
        missing = sorted(declared_auto - IMPLEMENTED_INVALIDATION_CONDITIONS)
        extra = sorted(IMPLEMENTED_INVALIDATION_CONDITIONS - declared_auto)
        raise ValueError(
            "Khai báo auto_evaluated_in_runner lệch với hiện thực: điều kiện khai "
            f"báo tự động nhưng runner KHÔNG hiện thực {missing}; điều kiện runner "
            f"có hiện thực nhưng file không khai báo {extra}. DỪNG.")


def arms_by_id(prereg: dict) -> dict:
    arms = {}
    for arm in prereg["arms"]:
        arm_id = arm["arm_id"]
        if arm_id in arms:
            raise ValueError(f"arm_id trùng trong pre-registration: {arm_id}")
        arms[arm_id] = arm
    return arms


# ------------------------------------------------------- miền biến bị hạn chế
def restricted_domains(grammar_id: str, restriction: dict) -> dict:
    """Miền grammar sau khi cắt theo ``restriction``, GIỮ thứ tự khai báo grammar.

    ``restriction`` là {tên biến: [giá trị cho phép]}. Miền trả về vẫn đi theo
    ``gene_order(grammar_id)`` nên thứ tự rút số ngẫu nhiên không đổi; chỉ số
    lựa chọn của biến bị cắt là ít đi. Giá trị lạ (không có trong grammar) hoặc
    miền rỗng là lỗi cấu hình — dừng ngay, không im lặng bỏ qua.
    """
    full = gene_domains(grammar_id)
    unknown = [name for name in restriction if name not in full]
    if unknown:
        raise ValueError(
            f"domain_restriction nhắc biến không có trong grammar {grammar_id}: {unknown}")

    out = {}
    for name in gene_order(grammar_id):
        values = full[name]
        if name in restriction:
            allowed = list(restriction[name])
            outside = [v for v in allowed if v not in values]
            if outside:
                raise ValueError(
                    f"domain_restriction/{name}: giá trị {outside} không thuộc miền "
                    f"grammar {grammar_id}; không được mở rộng miền, chỉ được cắt.")
            # Lọc theo THỨ TỰ của grammar, không theo thứ tự người viết liệt kê,
            # để cùng restriction luôn cho cùng chỉ số → cùng seed, cùng lịch sử.
            values = [v for v in values if v in allowed]
            if not values:
                raise ValueError(f"domain_restriction/{name} làm miền rỗng.")
        out[name] = values
    return out


# ------------------------------- đường tìm kiếm riêng cho arm có miền bị cắt
# Hai hàm dưới đây là bản sao trung thành của bridge_evolution.optimization
# .random_search / .nsga2, chỉ khác một điểm: miền biến được TRUYỀN VÀO thay vì
# đọc từ grammar. Thứ tự rút số ngẫu nhiên, generation_action, guard proposal và
# cách tiêu ngân sách giữ y nguyên để A2 so sánh được với A1/A3.
def _restricted_random_search(budget: int, seed: int, grammar_id: str,
                              domains: dict) -> dict:
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

    config = {**ev.config, "algorithm": "random_search",
              "max_proposals": max_proposals}
    return {"algorithm": "random_search", "seed": seed, "grammar_id": grammar_id,
            "config": config,
            "counters": ev.counters, "history": ev.history,
            "proposal_history": ev.proposal_history, "archive": archive,
            "termination": "budget_exhausted" if ev.exhausted else "proposal_guard"}


def _restricted_nsga2(budget: int, seed: int, grammar_id: str, domains: dict,
                      pop_size: int = 40, p_crossover: float = 0.9) -> dict:
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
                if rng.random() < 0.5:  # bước ±1 trên lưới (local move)
                    y[j] = min(sizes[j] - 1, max(0, y[j] + rng.choice((-1, 1))))
                else:                   # reset ngẫu nhiên (exploration)
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

    # --- khởi tạo
    pop = []
    seen = set()
    while (len(pop) < pop_size and not ev.exhausted
           and ev.n_proposals < max_proposals):
        x = [rng.randrange(s) for s in sizes]
        if tuple(x) in seen:
            continue
        seen.add(tuple(x))
        ind = evaluate(x)
        if ind:
            pop.append(ind)
    generations = 0

    # --- vòng tiến hóa
    while not ev.exhausted and pop and ev.n_proposals < max_proposals:
        calls_before_gen = ev.n_solver_calls
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
        while (len(offspring) < pop_size and not ev.exhausted
               and ev.n_proposals < max_proposals):
            c1, c2 = crossover(tournament()["x"], tournament()["x"])
            for c in (mutate(c1), mutate(c2)):
                ind = evaluate(c)
                if ind:
                    offspring.append(ind)
                if (len(offspring) >= pop_size or ev.exhausted
                        or ev.n_proposals >= max_proposals):
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
        generations += 1

        # Chống kẹt ngân sách: quần thể hội tụ → toàn cache hit, không tiêu solver
        # call. Bơm cá thể ngẫu nhiên để tiếp tục khám phá (giống bản tham chiếu).
        if (ev.n_solver_calls == calls_before_gen and not ev.exhausted
                and ev.n_proposals < max_proposals):
            n_inject = max(1, pop_size // 4)
            for _ in range(n_inject):
                ind = evaluate([rng.randrange(s) for s in sizes])
                if ind:
                    pop[rng.randrange(len(pop))] = ind
                if ev.exhausted:
                    break

    config = {**ev.config, "algorithm": "nsga2", "pop_size": pop_size,
              "p_crossover": p_crossover, "p_mutation": p_mut,
              "max_proposals": max_proposals}
    return {"algorithm": "nsga2", "seed": seed, "grammar_id": grammar_id,
            "pop_size": pop_size,
            "generations": generations, "config": config, "counters": ev.counters,
            "history": ev.history, "proposal_history": ev.proposal_history,
            "archive": archive,
            "termination": "budget_exhausted" if ev.exhausted else "proposal_guard"}


def run_arm(arm: dict, algo_id: str, budget: int, seed: int, pop: int) -> dict:
    """Chạy một (arm, thuật toán, seed) và trả về run kèm ``search_path`` thực tế.

    Arm không có ``domain_restriction`` đi thẳng qua API tham chiếu. Arm có miền
    bị cắt đi qua đường riêng trong file này. ``search_path`` mà pre-registration
    khai báo được đối chiếu với đường thực sự chạy — lệch là DỪNG, vì manifest
    khi đó sẽ mô tả sai cách thí nghiệm được thực hiện.
    """
    grammar_id = arm["grammar_id"]
    restriction = arm.get("domain_restriction") or {}

    if restriction:
        domains = restricted_domains(grammar_id, restriction)
        if algo_id == "rs":
            run = _restricted_random_search(budget, seed, grammar_id, domains)
        else:
            run = _restricted_nsga2(budget, seed, grammar_id, domains, pop_size=pop)
        search_path = "local_restricted_domain_path"
        run["config"] = {**run["config"], "domain_restriction": restriction,
                         "restricted_domain_sizes":
                             {k: len(v) for k, v in domains.items()}}
    else:
        if algo_id == "rs":
            run = random_search(budget, seed, grammar_id=grammar_id)
        else:
            run = nsga2(budget, seed, pop_size=pop, grammar_id=grammar_id)
        search_path = "reference_api"
        run["config"] = {**run["config"], "domain_restriction": {}}

    declared = arm.get("search_path")
    if declared is not None and declared != search_path:
        raise ValueError(
            f"arm {arm['arm_id']}: pre-registration khai báo search_path="
            f"{declared!r} nhưng thực tế chạy {search_path!r}. DỪNG.")

    run["arm_id"] = arm["arm_id"]
    run["algo_id"] = algo_id
    run["search_path"] = search_path
    run["config"] = {**run["config"], "arm_id": arm["arm_id"],
                     "search_path": search_path}
    return run


# --------------------------------------------------------------------- metrics
#: Số mẫu tối thiểu để tương quan Pearson có nghĩa. Với ĐÚNG 2 điểm, mọi cặp
#: (x, y) luôn nằm trên một đường thẳng nên |r| = 1 theo định nghĩa — dùng con số
#: đó để bật cờ OBJECTIVES_COLLINEAR là bật cờ GIẢ. Ngưỡng thật đọc từ
#: pre-registration (threshold.min_sample_size); hằng này chỉ là mặc định phòng hờ.
MIN_CORRELATION_SAMPLES = 3


def _pearson(xs: list[float], ys: list[float],
             min_samples: int = MIN_CORRELATION_SAMPLES) -> float | None:
    """Hệ số tương quan Pearson; None khi không xác định.

    None có hai nguyên nhân và cả hai đều KHÔNG được coi là suy biến: không đủ
    mẫu (``len < min_samples``) hoặc một chuỗi là hằng số. Số mẫu thực được báo
    riêng trong ``corr_sample_size`` để người đọc phân biệt được hai trường hợp.
    """
    if len(xs) < max(2, min_samples):
        return None
    try:
        return round(statistics.correlation(xs, ys), 6)
    except statistics.StatisticsError:
        return None


def summarize_run(run: dict, min_corr_samples: int = MIN_CORRELATION_SAMPLES) -> dict:
    """Metric đã đăng ký cho một run, gồm cả hypervolume theo protocol khóa trước."""
    summary = summarize(run)
    # add_hypervolume gọi _assert_hv_domain: objective ngoài miền khai báo ⇒ DỪNG.
    add_hypervolume(run, summary)

    feas = [r for r in run["history"]
            if r["solver_call_index"] is not None and r["feasible"]]
    costs = [r["objectives"][0] for r in feas]
    masses = [r["objectives"][1] for r in feas]
    carbons = [r["objectives"][2] for r in feas]

    summary["best_relative_cost"] = min(costs) if costs else None
    summary["best_material_mass_t"] = min(masses) if masses else None
    summary["best_embodied_carbon"] = min(carbons) if carbons else None
    summary["corr_sample_size"] = len(feas)
    summary["corr_cost_mass"] = _pearson(costs, masses, min_corr_samples)
    summary["corr_cost_carbon"] = _pearson(costs, carbons, min_corr_samples)
    summary["corr_mass_carbon"] = _pearson(masses, carbons, min_corr_samples)
    summary["termination"] = run["termination"]
    return summary


def mean_std(values: list) -> str:
    """Trung bình ± độ lệch chuẩn, KÈM số run thật sự được dùng trên tổng số run.

    Bỏ lặng lẽ các run có metric None (thường là run không tìm được phương án
    khả thi nào) sẽ THIÊN VỊ đúng cái arm thất bại nặng nhất: nó chỉ còn được
    tính trên những seed may mắn. Vì vậy mọi ô đều ghi ``(n=dùng/tổng)`` và đánh
    dấu ⚠ khi có run bị bỏ.
    """
    total = len(values)
    vals = [v for v in values if v is not None]
    if not vals:
        return f"n/a (n=0/{total}) ⚠ thiếu {total} run"
    mean = statistics.mean(vals)
    std = statistics.stdev(vals) if len(vals) >= 2 else 0.0
    cell = f"{mean:.6g} ± {std:.6g} (n={len(vals)}/{total})"
    if len(vals) < total:
        cell += f" ⚠ thiếu {total - len(vals)} run"
    return cell


# ------------------------------------------------------------------- artifacts
def _create_output_dir(requested: str | None) -> Path:
    if requested:
        out = Path(requested).expanduser().resolve()
        # exist_ok=False là chủ ý: không bao giờ để file stale sống sót trong run mới.
        out.mkdir(parents=True, exist_ok=False)
        return out
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    out = ROOT / "experiments" / "results" / f"grammar_ab_{stamp}"
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


def run_key(run: dict) -> str:
    return f"{run['arm_id']}_{run['algo_id']}_s{run['seed']}"


def _write_run_artifacts(out: Path, run: dict) -> None:
    key = run_key(run)
    _write_history_csv(out / f"history_{key}.csv", run)
    _write_jsonl(out / f"history_{key}.jsonl", run["history"], run)
    _write_jsonl(out / f"proposals_{key}.jsonl", run["proposal_history"], run)
    _write_pareto(out / f"pareto_{key}.json", run)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# --------------------------------------- đối chiếu cấu hình chạy với giao thức
def _protocol_compliance(prereg: dict, *, budget: int, seeds: list[int],
                         algo_names: list[str], arms: list[str], pop: int) -> dict:
    """So cấu hình chạy THỰC TẾ với run matrix đã đăng ký.

    Chạy một tập con (bớt seed, bớt thuật toán, bớt arm, đổi ngân sách) rồi vẫn
    xuất phán quyết là cách dễ nhất để "chọn" kết quả có lợi sau khi đã thấy số
    liệu. Vì vậy mọi lệch được liệt kê tường minh và toàn bộ báo cáo bị dán nhãn
    lệch; smoke test ngân sách nhỏ vẫn chạy được, chỉ là không được kết luận.
    """
    registered = {
        "budget_per_run": prereg["budget_per_run"],
        "seeds": sorted(prereg["seeds"]),
        "algorithms": sorted(a["algorithm_id"] for a in prereg["algorithms"]),
        "arms": sorted(a["arm_id"] for a in prereg["arms"]),
    }
    actual = {
        "budget_per_run": budget,
        "seeds": sorted(seeds),
        "algorithms": sorted(algo_names),
        "arms": sorted(arms),
    }
    registered_pop = next((a.get("pop_size") for a in prereg["algorithms"]
                           if a["algorithm_id"] == "nsga2"), None)
    if registered_pop is not None and "nsga2" in algo_names:
        registered["nsga2_pop_size"] = registered_pop
        actual["nsga2_pop_size"] = pop

    deviations = [{"field": field, "registered": registered[field],
                   "actual": actual[field]}
                  for field in registered if registered[field] != actual[field]]
    return {
        "run_matrix_declared": prereg.get("run_matrix"),
        "registered": registered,
        "actual": actual,
        "matches": not deviations,
        "deviations": deviations,
        "label": COMPLIANCE_LABEL if not deviations else DEVIATION_LABEL,
    }


# ------------------------------------------- đánh giá theo tiêu chí đã đăng ký
def _condition_index(prereg: dict) -> dict:
    return {c["condition_id"]: c
            for c in prereg["invalidation_conditions"]["conditions"]}


def _threshold(conditions: dict, condition_id: str, key: str):
    """Ngưỡng đọc TỪ pre-registration; thiếu là DỪNG, không rơi về hằng trong code."""
    try:
        return conditions[condition_id]["threshold"][key]
    except KeyError:
        raise ValueError(
            f"Pre-registration thiếu ngưỡng invalidation_conditions/{condition_id}"
            f"/threshold/{key}. DỪNG: ngưỡng không được hard-code trong runner."
        ) from None


def _invalidation_flags(items: list[dict], prereg: dict) -> list[dict]:
    """Điều kiện làm SO SÁNH VÔ HIỆU, ngưỡng đọc từ invalidation_conditions.

    Trả về list dict (không phải chuỗi) để manifest.json và summary.md dùng CHUNG
    một nguồn: cùng ``condition_id``, cùng ``run_key``, cùng câu lý do.
    """
    conds = _condition_index(prereg)
    max_archive = _threshold(conds, "DEGENERATE_FRONT", "archive_size_at_most")
    max_infeasible = _threshold(conds, "NO_FEASIBLE", "feasible_count_at_most")
    min_rate = _threshold(conds, "FEASIBLE_RATE_TOO_LOW",
                          "solver_conditional_feasible_rate_below")
    abs_r = _threshold(conds, "OBJECTIVES_COLLINEAR", "abs_pearson_at_least")

    flags: list[dict] = []

    def add(item: dict, condition_id: str, message: str) -> None:
        run = item["run"]
        flags.append({"condition_id": condition_id, "run_key": run_key(run),
                      "arm_id": run["arm_id"], "algorithm": run["algo_id"],
                      "seed": run["seed"],
                      "message": f"{condition_id} — {run_key(run)}: {message}"})

    for item in items:
        s, run = item["summary"], item["run"]
        if s["feasible_count"] <= max_infeasible:
            add(item, "NO_FEASIBLE", "không có phương án khả thi nào "
                f"(feasible_count = {s['feasible_count']} ≤ {max_infeasible}).")
        if s["archive_size"] <= max_archive:
            add(item, "DEGENERATE_FRONT",
                f"Pareto front chỉ còn {s['archive_size']} điểm "
                f"(≤{max_archive}), không được diễn giải Pareto.")
        if s["solver_conditional_feasible_rate"] < min_rate:
            add(item, "FEASIBLE_RATE_TOO_LOW",
                f"P(khả thi|solver) = {s['solver_conditional_feasible_rate']} "
                f"< {min_rate}.")
        for corr_key in CORR_KEYS:
            value = s.get(corr_key)
            if value is not None and abs(value) >= abs_r:
                add(item, "OBJECTIVES_COLLINEAR",
                    f"{corr_key} = {value} (|r| ≥ {abs_r}) trên "
                    f"{s['corr_sample_size']} mẫu khả thi, mục tiêu suy biến.")
        granted = run["config"]["budget_solver_calls"]
        if s["solver_calls"] != granted:
            add(item, "UNEQUAL_SOLVER_BUDGET",
                f"solver_calls thực tế {s['solver_calls']} ≠ ngân sách đã cấp "
                f"{granted} (termination = {run['termination']}). Run này KHÔNG "
                "tiêu cùng ngân sách solver với các run khác nên không so sánh được.")
    return flags


def _invalidation_condition_status(prereg: dict, flags: list[dict]) -> list[dict]:
    """Trạng thái CỦA TỪNG điều kiện đã đăng ký, kể cả điều kiện không tự đánh giá.

    Điều kiện chưa hiện thực được phải hiện ra là "chưa được đánh giá tự động";
    im lặng bỏ qua sẽ khiến người đọc tưởng cả 7 điều kiện đều đã được kiểm.
    """
    fired: dict[str, list[str]] = {}
    for flag in flags:
        fired.setdefault(flag["condition_id"], []).append(flag["run_key"])

    rows = []
    for cond in prereg["invalidation_conditions"]["conditions"]:
        cid = cond["condition_id"]
        keys = sorted(set(fired.get(cid, [])))
        if not cond["auto_evaluated_in_runner"]:
            status = "CHƯA ĐƯỢC ĐÁNH GIÁ TỰ ĐỘNG"
        elif keys:
            status = f"KÍCH HOẠT ({len(keys)} run)"
        else:
            status = "không kích hoạt"
        rows.append({
            "condition_id": cid,
            "status": status,
            "auto_evaluated_in_runner": cond["auto_evaluated_in_runner"],
            "rule": cond["rule"],
            "threshold": cond.get("threshold"),
            "evaluation_note": cond.get("evaluation_note"),
            "run_keys": keys,
        })
    return rows


def _evaluate_decision_rule(items: list[dict], prereg: dict, baseline_arm: str,
                            flags: list[dict], compliance: dict) -> dict:
    """Áp tiêu chí bác bỏ đã đăng ký; không được nới ngưỡng sau khi thấy số liệu.

    Ba trạng thái, không phải hai. Một cặp (arm, thuật toán, seed) mà điều kiện
    vô hiệu kích hoạt — ở run của arm HOẶC ở run đối chứng của chính cặp đó —
    mang trạng thái VÔ HIỆU. Arm còn cặp vô hiệu, hoặc chạy lệch run matrix, thì
    phán quyết là VÔ HIỆU: không ĐẠT, và cũng không được ghi nhận là kết quả âm.
    """
    rule = prereg["decision_rule"]
    threshold = rule["improvement_threshold_relative"]
    index = {(i["run"]["arm_id"], i["run"]["algo_id"], i["run"]["seed"]): i
             for i in items}
    by_run_key: dict[str, list[str]] = {}
    for flag in flags:
        by_run_key.setdefault(flag["run_key"], []).append(flag["message"])
    arms_present = sorted({i["run"]["arm_id"] for i in items})
    verdicts = {}

    for arm_id in arms_present:
        if arm_id == baseline_arm:
            continue
        pairs, all_pass, evaluable = [], True, 0
        for item in items:
            if item["run"]["arm_id"] != arm_id:
                continue
            algo_id, seed = item["run"]["algo_id"], item["run"]["seed"]
            base = index.get((baseline_arm, algo_id, seed))
            void_reasons = list(by_run_key.get(run_key(item["run"]), []))
            if base is not None:
                void_reasons += by_run_key.get(run_key(base["run"]), [])
            if base is None:
                pairs.append({"algo": algo_id, "seed": seed, "status": "NO_BASELINE",
                              "void_reasons": void_reasons, "passed": False})
                all_pass = False
                continue
            b, a = base["summary"], item["summary"]
            if b["best_relative_cost"] is None or a["best_relative_cost"] is None:
                pairs.append({"algo": algo_id, "seed": seed, "status": "NO_FEASIBLE",
                              "void_reasons": void_reasons, "passed": False})
                all_pass = False
                continue
            evaluable += 1
            improvement = ((b["best_relative_cost"] - a["best_relative_cost"])
                           / b["best_relative_cost"])
            cost_ok = improvement >= threshold
            hv_ok = (a["hypervolume_2d_cost_carbon"]
                     >= b["hypervolume_2d_cost_carbon"])
            passed = cost_ok and hv_ok
            all_pass = all_pass and passed
            pairs.append({
                "algo": algo_id, "seed": seed,
                "status": VERDICT_VOID if void_reasons else "OK",
                "void_reasons": void_reasons,
                "improvement": round(improvement, 6),
                "cost_ok": cost_ok, "hv_ok": hv_ok, "passed": passed,
                "baseline_best_cost": b["best_relative_cost"],
                "arm_best_cost": a["best_relative_cost"],
                "baseline_hv2d": b["hypervolume_2d_cost_carbon"],
                "arm_hv2d": a["hypervolume_2d_cost_carbon"],
            })

        void_pairs = [p for p in pairs if p["void_reasons"]]
        # Phán quyết "nếu bỏ qua vô hiệu" chỉ để người đọc thấy số liệu thô;
        # nó KHÔNG BAO GIỜ được dùng làm kết luận khi verdict là VÔ HIỆU.
        raw = (VERDICT_PASS if (all_pass and evaluable and len(pairs) == evaluable)
               else VERDICT_FAIL)
        blockers = []
        if void_pairs:
            blockers.append(
                f"{len(void_pairs)}/{len(pairs)} cặp (thuật toán, seed) dính điều "
                "kiện vô hiệu đã đăng ký")
        if not compliance["matches"]:
            blockers.append(DEVIATION_LABEL)
        verdict = VERDICT_VOID if blockers else raw
        verdicts[arm_id] = {
            "pairs": pairs,
            "evaluable_pairs": evaluable,
            "void_pair_count": len(void_pairs),
            "void_reasons": sorted({r for p in void_pairs for r in p["void_reasons"]}),
            "blockers": blockers,
            "verdict": verdict,
            "verdict_ignoring_invalidation": raw,
        }
    return {"baseline_arm": baseline_arm, "threshold": threshold,
            "verdict_states": [VERDICT_PASS, VERDICT_FAIL, VERDICT_VOID],
            "protocol_compliance_label": compliance["label"],
            "arms": verdicts}


# ------------------------------------------------------------------------ main
def main(argv: list[str] | None = None) -> Path:
    ap = argparse.ArgumentParser(
        description="A/B grammar v1 (tiết diện định hình) vs v2 (AI tự thiết kế hình dạng)")
    ap.add_argument("--budget", type=int, default=600,
                    help="số lần solver.status != NOT_RUN cho mỗi (arm, thuật toán, seed)")
    ap.add_argument("--seeds", type=str, default="42,43,44")
    ap.add_argument("--algos", type=str, default="rs,nsga2")
    ap.add_argument("--arms", type=str, default="A1,A2,A3",
                    help="tiền tố arm_id trong pre-registration, vd A1,A2,A3")
    ap.add_argument("--pop", type=int, default=40)
    ap.add_argument("--preregistration", type=str, default=str(DEFAULT_PREREG),
                    help="đường dẫn pre-registration đã khóa trước (bắt buộc tồn tại)")
    ap.add_argument("--output-dir", type=str,
                    help="thư mục mới (lệnh từ chối nếu đã tồn tại)")
    args = ap.parse_args(argv)

    # Pre-registration được kiểm TRƯỚC khi tạo bất kỳ artifact nào: thiếu nó thì
    # không có thí nghiệm, và cũng không được để lại thư mục kết quả rỗng.
    prereg_path = Path(args.preregistration).expanduser()
    prereg = load_preregistration(prereg_path)
    all_arms = arms_by_id(prereg)

    seeds = [int(s) for s in args.seeds.split(",") if s.strip()]
    algo_names = [a.strip() for a in args.algos.split(",") if a.strip()]
    arm_prefixes = [a.strip() for a in args.arms.split(",") if a.strip()]
    if not seeds:
        raise ValueError("Cần ít nhất một seed")
    bad_algos = [a for a in algo_names if a not in ALGO_IDS]
    if bad_algos or not algo_names:
        raise ValueError(f"Thuật toán không hợp lệ: {bad_algos or algo_names}; "
                         f"chỉ nhận {list(ALGO_IDS)}")

    selected = []
    for prefix in arm_prefixes:
        matched = [aid for aid in all_arms if aid == prefix or aid.startswith(prefix + "_")]
        if len(matched) != 1:
            raise ValueError(
                f"--arms '{prefix}' khớp {matched or 'không arm nào'} trong "
                f"pre-registration (cần đúng 1). Arm có sẵn: {list(all_arms)}")
        if matched[0] not in selected:
            selected.append(matched[0])

    baseline_arm = prereg.get("baseline_arm", selected[0])

    # Đối chiếu cấu hình chạy với run matrix đã đăng ký TRƯỚC khi chạy, và nói
    # ngay: một run lệch giao thức vẫn được phép chạy (smoke test), nhưng người
    # chạy phải biết từ đầu rằng nó không dùng để kết luận được.
    compliance = _protocol_compliance(
        prereg, budget=args.budget, seeds=seeds, algo_names=algo_names,
        arms=selected, pop=args.pop)
    if not compliance["matches"]:
        print(f"*** {DEVIATION_LABEL} ***")
        for dev in compliance["deviations"]:
            print(f"    - {dev['field']}: đã đăng ký {dev['registered']!r}, "
                  f"thực tế {dev['actual']!r}")

    min_corr_samples = _threshold(_condition_index(prereg), "OBJECTIVES_COLLINEAR",
                                  "min_sample_size")

    items = []
    total = len(selected) * len(algo_names) * len(seeds)
    for arm_id in selected:
        for algo_id in algo_names:
            for seed in seeds:
                print(f"[{len(items) + 1}/{total}] {arm_id:<18} {algo_id:<6} "
                      f"seed={seed} solver_budget={args.budget} ...")
                run = run_arm(all_arms[arm_id], algo_id, args.budget, seed, args.pop)
                items.append({"run": run,
                              "summary": summarize_run(run, min_corr_samples)})

    out = _create_output_dir(args.output_dir)
    for item in items:
        _write_run_artifacts(out, item["run"])

    # ---- summary.csv (1 dòng / run, hoàn toàn xác định để so sánh 2 lần chạy)
    header = (["arm_id", "algorithm", "seed", "grammar_id", "search_path",
               "budget_solver_calls"] + COUNTER_KEYS + METRIC_KEYS + CORR_KEYS)
    with (out / "summary.csv").open("x", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        for item in items:
            run, s = item["run"], item["summary"]
            w.writerow([run["arm_id"], run["algo_id"], run["seed"],
                        run["grammar_id"], run["search_path"], args.budget]
                       + [s[k] for k in COUNTER_KEYS]
                       + [s[k] for k in METRIC_KEYS]
                       + [s[k] for k in CORR_KEYS])

    flags = _invalidation_flags(items, prereg)
    decision = _evaluate_decision_rule(items, prereg, baseline_arm, flags,
                                       compliance)
    condition_status = _invalidation_condition_status(prereg, flags)
    prereg_sha = _sha256(prereg_path)
    prereg_is_default = (prereg_path.resolve() == DEFAULT_PREREG.resolve())
    lines = _report_lines(args, prereg, prereg_path, selected, algo_names, seeds,
                          items, decision, flags, all_arms,
                          compliance=compliance, condition_status=condition_status,
                          prereg_sha=prereg_sha,
                          prereg_is_default=prereg_is_default)
    (out / "summary.md").write_text("\n".join(lines), encoding="utf-8")

    # ---- manifest (viết SAU cùng để hash phủ mọi artifact kết quả)
    manifest = {
        "experiment": "grammar_ab_v1_vs_v2",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "software_version": __version__,
        "claim_ceiling": prereg["claim_ceiling"],
        "budget_definition": "solver.status != NOT_RUN",
        "preregistration_path": str(prereg_path),
        "preregistration_sha256": prereg_sha,
        "preregistration_version": prereg.get("preregistration_version"),
        "preregistration_is_default_file": prereg_is_default,
        "preregistration_default_path": str(DEFAULT_PREREG),
        "preregistration": prereg,
        "requested": {
            "budget_per_run": args.budget, "seeds": seeds,
            "algorithms": algo_names, "arms": selected, "nsga2_pop": args.pop,
            "baseline_arm": baseline_arm,
        },
        "arms": [{
            "arm_id": arm_id,
            "grammar_id": all_arms[arm_id]["grammar_id"],
            "domain_restriction": all_arms[arm_id].get("domain_restriction") or {},
            "search_path": next(i["run"]["search_path"] for i in items
                                if i["run"]["arm_id"] == arm_id),
        } for arm_id in selected],
        "domain_restriction_note":
            "Miền bị cắt được truyền xuống bộ sinh gene TRƯỚC khi đề xuất ứng viên. "
            "Arm có search_path='local_restricted_domain_path' KHÔNG chạy qua API "
            "random_search/nsga2 mà qua bản sao trong experiments/run_grammar_ab.py, "
            "vì API tham chiếu chưa nhận miền đã lọc; lọc ở tầng đề xuất bị cấm do "
            "làm sai ngân sách solver.",
        "hypervolume_protocol": {
            "objective_order": ["relative_cost", "material_mass_t",
                                "embodied_carbon_kgCO2e"],
            "ideal_3d": HV_IDEAL_3D,
            "reference_3d": HV_REFERENCE_3D,
            "mc_samples": HV_MC_SAMPLES,
            "mc_seed": HV_MC_SEED,
            "locked_before_experiment": True,
        },
        "protocol_compliance": compliance,
        "decision_rule_evaluation": decision,
        "decision_rule_used": prereg["decision_rule"],
        "invalidation_flags": flags,
        "invalidation_condition_status": condition_status,
        "correlation_min_sample_size": min_corr_samples,
        "runs_without_any_feasible": sorted(
            run_key(i["run"]) for i in items if i["summary"]["feasible_count"] == 0),
        "runs": [{
            "arm_id": i["run"]["arm_id"], "algorithm": i["run"]["algo_id"],
            "seed": i["run"]["seed"], "run_key": run_key(i["run"]),
            "grammar_id": i["run"]["grammar_id"],
            "search_path": i["run"]["search_path"],
            "config": i["run"]["config"], "counters": i["run"]["counters"],
            "termination": i["run"]["termination"],
            "metrics": {k: i["summary"][k] for k in METRIC_KEYS + CORR_KEYS},
        } for i in items],
        "artifact_sha256": {p.name: _sha256(p)
                            for p in sorted(out.iterdir()) if p.is_file()},
    }
    with (out / "manifest.json").open("x", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False, sort_keys=True)

    print()
    print("\n".join(lines))
    print(f"\nĐã lưu run mới, không trộn kết quả cũ: {out}")
    return out


def _report_lines(args, prereg: dict, prereg_path: Path, selected: list[str],
                  algo_names: list[str], seeds: list[int], items: list[dict],
                  decision: dict, flags: list[dict], all_arms: dict, *,
                  compliance: dict, condition_status: list[dict], prereg_sha: str,
                  prereg_is_default: bool) -> list[str]:
    """summary.md — bảng mean±std theo arm, phán quyết bác bỏ và cảnh báo suy biến."""
    lines = [
        "# A/B grammar — tiết diện định hình (v1) vs AI tự thiết kế hình dạng (v2)",
        "",
        f"**Claim ceiling: {prereg['claim_ceiling']}.** Số liệu là L0 + L1 line-girder "
        "sơ bộ, KHÔNG phải thiết kế và không phải build-ready.",
        "",
    ]

    # ---- M2: nhãn tuân thủ giao thức, đặt ngay đầu báo cáo
    if compliance["matches"]:
        lines += [f"**Tuân thủ run matrix đã đăng ký: {COMPLIANCE_LABEL}.**", ""]
    else:
        lines += [
            f"> # ⚠ {compliance['label']}",
            ">",
            "> Cấu hình chạy thực tế LỆCH khỏi run matrix đã đăng ký. Phán quyết "
            f"`{VERDICT_PASS}` bị CẤM trong toàn bộ báo cáo này; mọi con số dưới "
            "đây chỉ là dữ liệu vận hành, không phải bằng chứng cho hay chống lại "
            "giả thuyết.",
            ">",
            f"> Run matrix đã đăng ký: {compliance['run_matrix_declared']}",
            ">",
            "> | Trường | Đã đăng ký | Thực tế chạy |",
            "> |---|---|---|",
        ]
        for dev in compliance["deviations"]:
            lines.append(f"> | `{dev['field']}` | `{dev['registered']}` | "
                         f"`{dev['actual']}` |")
        lines.append("")

    lines += [
        f"Pre-registration khóa trước: `{prereg_path}` "
        f"(v{prereg.get('preregistration_version', '?')})",
        "",
        f"SHA-256 pre-registration đã dùng: `{prereg_sha}`",
        "",
    ]
    if not prereg_is_default:
        lines += [
            f"> ⚠ **KHÔNG dùng pre-registration mặc định.** File mặc định là "
            f"`{DEFAULT_PREREG}`, nhưng lần chạy này dùng `{prereg_path}` "
            "(tham số `--preregistration`). Ngưỡng quyết định và điều kiện vô hiệu "
            "ở dưới đến từ FILE ĐƯỢC TRỎ TỚI, không phải từ file mặc định — phải "
            "đối chiếu hash ở trên trước khi tin bất kỳ phán quyết nào.",
            "",
        ]
    if prereg.get("amendments"):
        lines += ["**Sửa đổi pre-registration đã ghi nhận:**", ""]
        for am in prereg["amendments"]:
            after = ("SAU KHI ĐÃ THẤY KẾT QUẢ"
                     if am.get("made_after_seeing_results") else "trước khi chạy")
            lines.append(f"- v{am.get('version')} ({am.get('date_utc')}) — {after}: "
                         f"{am.get('reason')}")
        lines.append("")

    lines += [
        f"> {prereg['research_question']}",
        "",
        f"Ngân sách: **{args.budget} solver calls** / (arm × thuật toán × seed) · "
        f"seeds {seeds} · thuật toán {algo_names} · pop NSGA-II {args.pop}",
        "",
        f"Định nghĩa ngân sách: `{prereg['budget_definition']}`",
        "",
        f"HV khóa trước: ref `{HV_REFERENCE_3D}` · ideal `{HV_IDEAL_3D}` · "
        f"MC samples {HV_MC_SAMPLES} · MC seed {HV_MC_SEED}",
        "",
        "## Arm",
        "",
        "| Arm | Grammar | Miền bị cắt | Đường tìm kiếm |",
        "|---|---|---|---|",
    ]
    for arm_id in selected:
        arm = all_arms[arm_id]
        restriction = arm.get("domain_restriction") or {}
        path = next(i["run"]["search_path"] for i in items
                    if i["run"]["arm_id"] == arm_id)
        lines.append(f"| `{arm_id}` | `{arm['grammar_id']}` | "
                     f"`{json.dumps(restriction, ensure_ascii=False, sort_keys=True)}` | "
                     f"`{path}` |")

    lines += ["", "## Metric theo arm (mean ± std trên mọi thuật toán × seed)", "",
              "Mỗi ô ghi `(n=số run được dùng/tổng số run)`. Run không có metric "
              "(thường vì KHÔNG tìm được phương án khả thi nào) bị loại khỏi trung "
              "bình và được đánh dấu `⚠`; đọc trung bình có `⚠` như một con số đã "
              "được lọc theo hướng có lợi cho arm đó.", "",
              "| Chỉ số | " + " | ".join(f"`{a}`" for a in selected) + " |",
              "|---|" + "---:|" * len(selected)]
    for key in METRIC_KEYS:
        cells = []
        for arm_id in selected:
            values = [i["summary"][key] for i in items
                      if i["run"]["arm_id"] == arm_id]
            cells.append(mean_std(values))
        lines.append(f"| {METRIC_LABELS[key]} | " + " | ".join(cells) + " |")

    # Hàng đếm riêng: bao nhiêu run hoàn toàn không có phương án khả thi nào.
    infeasible_cells = []
    for arm_id in selected:
        arm_items = [i for i in items if i["run"]["arm_id"] == arm_id]
        n_zero = sum(1 for i in arm_items if i["summary"]["feasible_count"] == 0)
        mark = " ⚠" if n_zero else ""
        infeasible_cells.append(f"{n_zero}/{len(arm_items)}{mark}")
    lines.append("| **Run KHÔNG có phương án khả thi nào** | "
                 + " | ".join(infeasible_cells) + " |")

    zero_keys = sorted(run_key(i["run"]) for i in items
                       if i["summary"]["feasible_count"] == 0)
    lines.append("")
    if zero_keys:
        lines.append("Run không có phương án khả thi nào: "
                     + ", ".join(f"`{k}`" for k in zero_keys))
    else:
        lines.append("Mọi run đều có ít nhất một phương án khả thi.")

    detail_keys = ["solver_calls", "termination", "proposals", "l0_checks",
                   "l0_rejected", "cache_hits", "feasible_count"]
    lines += ["", "## Chi tiết từng run", "",
              "`solver_calls` là ngân sách THỰC SỰ tiêu; `termination` cho biết run "
              "dừng vì hết ngân sách hay vì chạm `proposal_guard`. Hai cột này phải "
              "được đọc TRƯỚC mọi so sánh: hai run khác solver_calls thì không cùng "
              "ngân sách nên không so sánh được. `l0_checks` là số lần sàng L0 MIỄN "
              "PHÍ (không tiêu ngân sách) — chênh lệch lớn giữa các arm là confound "
              "đã đăng ký, không phải nhiễu.", "",
              "| Arm | Thuật toán | Seed | Ngân sách cấp | "
              + " | ".join(detail_keys) + " | " + " | ".join(METRIC_KEYS) + " |",
              "|---|---|---:|---:|" + "---:|" * (len(detail_keys) + len(METRIC_KEYS))]
    for item in items:
        run, s = item["run"], item["summary"]
        granted = run["config"]["budget_solver_calls"]
        mark = "" if s["solver_calls"] == granted else " ⚠"
        lines.append(f"| {run['arm_id']} | {run['algo_id']} | {run['seed']} | "
                     f"{granted}{mark} | "
                     + " | ".join(str(s[k]) for k in detail_keys) + " | "
                     + " | ".join(str(s[k]) for k in METRIC_KEYS) + " |")

    # ---- phán quyết theo tiêu chí đã đăng ký
    rule = prereg["decision_rule"]
    lines += ["", "## Đánh giá theo tiêu chí bác bỏ đã đăng ký", "",
              "Ba trạng thái phán quyết: "
              f"`{VERDICT_PASS}` · `{VERDICT_FAIL}` · `{VERDICT_VOID}`. "
              f"`{VERDICT_VOID}` nghĩa là KHÔNG kết luận theo hướng nào — nó không "
              "phải kết quả âm, và tuyệt đối không được đọc thành kết quả dương.",
              "",
              "**Nội dung tiêu chí đã dùng (trích nguyên văn từ file "
              f"pre-registration có SHA-256 `{prereg_sha}`):**", "",
              f"- `primary_metric` = `{rule['primary_metric']}`",
              f"- `improvement_threshold_relative` = `{rule['improvement_threshold_relative']}`",
              f"- `secondary_guard`: {rule['secondary_guard']}",
              f"- `rule`: {rule['rule']}",
              f"- `on_failure`: {rule['on_failure']}",
              f"- `attribution_rule`: {rule['attribution_rule']}",
              "",
              f"Arm đối chứng: `{decision['baseline_arm']}` · ngưỡng cải thiện "
              f"`{decision['threshold']:.1%}` · tuân thủ giao thức: "
              f"**{compliance['label']}**", ""]
    if not decision["arms"]:
        lines.append("Không có arm nào để so với đối chứng trong lần chạy này.")
    for arm_id, verdict in decision["arms"].items():
        lines += [f"### `{arm_id}` → **{verdict['verdict']}**", ""]
        if verdict["blockers"]:
            lines += ["**Lý do phán quyết là VÔ HIỆU:**"]
            lines += [f"- {b}" for b in verdict["blockers"]]
            lines += [""]
            if verdict["void_reasons"]:
                lines += ["Điều kiện vô hiệu đã kích hoạt trên các cặp của arm này "
                          "(gồm cả điều kiện kích hoạt ở run đối chứng của cùng cặp):"]
                lines += [f"- {r}" for r in verdict["void_reasons"]]
                lines += [""]
            lines += [
                "Phán quyết theo quy tắc NẾU BỎ QUA vô hiệu: "
                f"`{verdict['verdict_ignoring_invalidation']}` — con số này chỉ để "
                "kiểm toán, KHÔNG phải kết luận và không được trích dẫn tách khỏi "
                "nhãn VÔ HIỆU.", ""]
        lines += ["| Thuật toán | Seed | best_cost đối chứng | best_cost arm | "
                  "Cải thiện | Cost đạt | HV không giảm | Kết luận cặp |",
                  "|---|---:|---:|---:|---:|:---:|:---:|:---:|"]
        for pair in verdict["pairs"]:
            if pair["status"] in ("NO_BASELINE", "NO_FEASIBLE"):
                lines.append(f"| {pair['algo']} | {pair['seed']} | — | — | — | — | — |"
                             f" {pair['status']} |")
                continue
            cell = (VERDICT_VOID if pair["status"] == VERDICT_VOID
                    else ("ĐẠT" if pair["passed"] else "KHÔNG"))
            lines.append(
                f"| {pair['algo']} | {pair['seed']} | {pair['baseline_best_cost']} | "
                f"{pair['arm_best_cost']} | {pair['improvement']:.2%} | "
                f"{'ĐẠT' if pair['cost_ok'] else 'KHÔNG'} | "
                f"{'ĐẠT' if pair['hv_ok'] else 'KHÔNG'} | {cell} |")
        lines.append("")
        for pair in verdict["pairs"]:
            for reason in pair["void_reasons"]:
                lines.append(f"- `{pair['algo']}` seed {pair['seed']} → "
                             f"{VERDICT_VOID}: {reason}")
        if any(p["void_reasons"] for p in verdict["pairs"]):
            lines.append("")
        if verdict["verdict"] == VERDICT_FAIL:
            lines += [
                "**KẾT QUẢ ÂM được ghi nhận.** Theo pre-registration, không đạt "
                "đồng thời hai điều kiện trên MỌI cặp (thuật toán, seed) thì không "
                "được phát biểu rằng grammar này tốt hơn đối chứng. Không được đổi "
                "ngưỡng, bỏ seed hay chọn thuật toán có lợi sau khi đã thấy số liệu.",
                ""]
        elif verdict["verdict"] == VERDICT_VOID:
            lines += [
                "**KHÔNG KẾT LUẬN.** Theo `invalidation_conditions` đã khóa trước, "
                "so sánh này vô hiệu: không được nói grammar v2 tốt hơn, và cũng "
                "không được ghi nhận đây là kết quả âm hợp lệ. Phải xử lý nguyên "
                "nhân vô hiệu rồi chạy lại đúng run matrix.", ""]
    lines += [f"Quy tắc quy kết: {rule['attribution_rule']}", ""]

    # ---- cảnh báo suy biến
    conds = _condition_index(prereg)
    abs_r = conds["OBJECTIVES_COLLINEAR"]["threshold"]["abs_pearson_at_least"]
    min_n = conds["OBJECTIVES_COLLINEAR"]["threshold"]["min_sample_size"]
    lines += ["## Cảnh báo suy biến", "",
              "Hệ số tương quan Pearson giữa các mục tiêu, tính trên record khả thi "
              f"của từng run (|r| ≥ {abs_r} ⇒ mục tiêu suy biến, hypervolume và "
              "Pareto front mất ý nghĩa đa mục tiêu). Cần tối thiểu "
              f"**{min_n} mẫu khả thi**; dưới ngưỡng đó ghi `không đủ mẫu` và "
              "KHÔNG bật cờ suy biến — với đúng 2 điểm thì |r| luôn bằng 1 theo "
              "định nghĩa nên cờ sẽ bật giả.", "",
              "| Arm | Thuật toán | Seed | Pareto front | Mẫu khả thi | "
              "r(cost,mass) | r(cost,carbon) | r(mass,carbon) |",
              "|---|---|---:|---:|---:|---:|---:|---:|"]
    for item in items:
        run, s = item["run"], item["summary"]
        n_corr = s["corr_sample_size"]
        cells = []
        for corr_key in CORR_KEYS:
            value = s[corr_key]
            if value is not None:
                cells.append(str(value))
            elif n_corr < min_n:
                cells.append(f"không đủ mẫu (n={n_corr}<{min_n})")
            else:
                cells.append("không xác định (chuỗi hằng)")
        lines.append(f"| {run['arm_id']} | {run['algo_id']} | {run['seed']} | "
                     f"{s['archive_size']} | {n_corr} | " + " | ".join(cells) + " |")
    lines.append("")
    if flags:
        lines.append("**Điều kiện làm so sánh VÔ HIỆU đã kích hoạt:**")
        lines += [f"- {flag['message']}" for flag in flags]
        lines += ["", "So sánh giữa các arm ở trên KHÔNG được diễn giải như bằng "
                  "chứng cho tới khi các điều kiện này được xử lý."]
    else:
        lines.append("Không có điều kiện vô hiệu nào bị kích hoạt trong lần chạy này.")

    # ---- trạng thái CỦA TỪNG điều kiện đã đăng ký, kể cả điều kiện chưa tự đánh giá
    lines += ["", "### Trạng thái từng điều kiện vô hiệu đã đăng ký", "",
              "Bảng này liệt kê TẤT CẢ điều kiện trong pre-registration, kể cả điều "
              "kiện runner CHƯA đánh giá tự động được — im lặng về chúng sẽ khiến "
              "người đọc tưởng cả bộ điều kiện đã được kiểm.", "",
              "| Điều kiện | Ngưỡng (từ pre-registration) | Trạng thái | Ghi chú |",
              "|---|---|---|---|"]
    for row in condition_status:
        threshold = (json.dumps(row["threshold"], ensure_ascii=False, sort_keys=True)
                     if row["threshold"] is not None else "—")
        note = row["evaluation_note"] or (", ".join(f"`{k}`" for k in row["run_keys"])
                                          if row["run_keys"] else "—")
        lines.append(f"| `{row['condition_id']}` | `{threshold}` | "
                     f"{row['status']} | {note} |")
    not_auto = [r["condition_id"] for r in condition_status
                if not r["auto_evaluated_in_runner"]]
    lines.append("")
    if not_auto:
        lines.append("**Chưa được đánh giá tự động trong lần chạy này: "
                     + ", ".join(f"`{c}`" for c in not_auto)
                     + ".** Báo cáo này KHÔNG chứng minh các điều kiện đó không xảy ra.")
    else:
        lines.append("Mọi điều kiện đã đăng ký đều được runner đánh giá tự động.")

    # ---- confound
    lines += ["", "## Confound đã đăng ký (không bóc tách được ở thí nghiệm này)", ""]
    lines += [f"- {c}" for c in prereg["confounds"]["not_separable_in_this_experiment"]]

    # Sàng L0 KHÔNG tiêu ngân sách, nên bất đối xứng số lần sàng là một khác biệt
    # thật giữa các arm ở "cùng ngân sách solver". In ngay số đo của chính run này.
    lines += ["", "### Sàng L0 miễn phí trong CHÍNH lần chạy này", "",
              "L0 không tiêu ngân sách solver, nên số lần sàng là công tìm kiếm "
              "được cấp thêm MIỄN PHÍ. Ở cùng số solver call, arm sàng nhiều hơn "
              "được xem nhiều ứng viên hơn.", "",
              "| Arm | Thuật toán | l0_checks | l0_rejected | Tỷ lệ qua L0 |",
              "|---|---|---:|---:|---:|"]
    for arm_id in selected:
        for algo_id in algo_names:
            group = [i for i in items if i["run"]["arm_id"] == arm_id
                     and i["run"]["algo_id"] == algo_id]
            if not group:
                continue
            checks = sum(i["summary"]["l0_checks"] for i in group)
            rejected = sum(i["summary"]["l0_rejected"] for i in group)
            rate = f"{(checks - rejected) / checks:.4%}" if checks else "n/a"
            lines.append(f"| {arm_id} | {algo_id} | {checks} | {rejected} | {rate} |")

    lines += ["", f"_{prereg['claim_ceiling_note']}_", "",
              f"_Tuân thủ run matrix đã đăng ký: **{compliance['label']}**._"]
    return lines


if __name__ == "__main__":
    main()
