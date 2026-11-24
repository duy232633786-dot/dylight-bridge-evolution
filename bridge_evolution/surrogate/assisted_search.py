"""Surrogate-assisted search: sàng lọc học máy TRƯỚC khi tiêu ngân sách solver.

Hai lợi thế hợp lệ của thuật toán (không vi phạm trung thực ngân sách):
1. Prefilter L0 bằng check_geometry là MIỄN PHÍ — không mở solver, không tốn
   budget; gene fail L0 bị loại trước khi cân nhắc đánh giá thật.
2. Surrogate (FeasibilitySurrogate) chỉ XẾP HẠNG ứng viên trong pool; nhãn
   feasible duy nhất vẫn đến từ BudgetedEvaluator.evaluate_gene — không model
   nào được tự kết luận khả thi.

Surrogate được fit trên tập ĐỒNG PHÂN PHỐI với pool (chỉ record đã chạy solver —
xem ``FeasibilitySurrogate.fit``). Mỗi lần fit ghi lại số liệu vào khối
``surrogate_diagnostics`` của result để lần sau ĐO được, không phải đoán.

Thuật toán chạy trên MỌI grammar: thứ tự rút số ngẫu nhiên và tập biến đột biến
đều lấy từ ``gene_order(grammar_id)``. Với v1 dãy đó đúng bằng ``GENE_ORDER`` cũ
nên cùng seed vẫn cho cùng một lịch sử.
"""
import random

from ..optimization.common import (
    DEFAULT_GRAMMAR_ID, BudgetedEvaluator, gene_domains, gene_order,
)
from ..pareto import ParetoArchive
from .model import MIN_FIT_SAMPLES, FeasibilitySurrogate


def surrogate_assisted_search(budget: int, seed: int, warmup: int = 120,
                              pool_size: int = 300, batch_size: int = 24,
                              retrain_every: int = 48,
                              grammar_id: str = DEFAULT_GRAMMAR_ID,
                              ranking: str = "none",
                              feasibility_gate: float = 0.5) -> dict:
    """Tìm kiếm có surrogate hỗ trợ. Trả về result dict chuẩn của mọi thuật toán.

    Pha 1 (warmup): đánh giá thật min(warmup, budget//3) gene ngẫu nhiên đã qua
    prefilter L0, rồi fit surrogate trên toàn bộ lịch sử.
    Pha 2 (vòng lặp): sinh pool = 50% ngẫu nhiên + 50% đột biến từ archive,
    loại gene L0-fail và gene đã có trong cache (đều miễn phí), xếp hạng theo
    ``ranking`` rồi đánh giá thật top batch_size; retrain surrogate sau mỗi
    retrain_every lần gọi solver mới.

    ``ranking`` — KẾT QUẢ ĐO, KHÔNG PHẢI SỞ THÍCH (budget 150, seed 42/43/44,
    best_relative_cost; ``none`` là mặc định vì đo được là tốt nhất/đơn giản nhất):

    ======== ============================== ==============================
    ranking  v1 (2072.94 = tối ưu vét cạn)  v2
    ======== ============================== ==============================
    reward   2092.24 / 2105.11 / 2089.48    2176.09 / 2042.79 / 2209.62
    none     2072.94 / 2072.94 / 2072.94    2123.81 / 2042.79 / 2160.16
    gate     2072.94 / 2105.11 / 2089.48    2142.73 / 2041.38 / 2145.68
    ======== ============================== ==============================

    - ``reward`` (bản cũ): cộng P(khả thi) vào điểm. THUA 5/6 so với ``none``.
      Nguyên nhân có ý nghĩa kỹ thuật: phương án tối ưu nằm ĐÚNG TRÊN BIÊN khả
      thi — nơi P(khả thi) thấp nhất — nên tối đa hóa P(khả thi) kéo tìm kiếm
      RỜI KHỎI chỗ cần đến. Surrogate làm tốt đúng việc nó được huấn luyện, và
      đó chính là lý do nó gây hại khi dùng làm điểm thưởng.
    - ``none``: bỏ hẳn đóng góp xếp hạng của surrogate. Chạm tối ưu vét cạn của
      v1 ở CẢ BA seed.
    - ``gate``: dùng surrogate làm cổng lọc rồi xếp theo chi phí. Xấp xỉ ``none``
      (3–2–1), chưa đủ bằng chứng để làm mặc định.

    CẢNH BÁO: 3 seed mỗi grammar là QUÁ ÍT để kết luận chắc; đây là tín hiệu định
    hướng, không phải kết quả đã được kiểm chứng. Cần nghiên cứu nhiều seed có
    pre-registration riêng trước khi tuyên bố cách xếp hạng nào thắng.
    """
    rng = random.Random(seed)
    # Thứ tự rút số PHẢI theo gene_order để cùng seed ⇒ cùng lịch sử; với v1 đây
    # đúng dãy GENE_ORDER cũ nên kết quả cũ không đổi một byte.
    order = gene_order(grammar_id)
    domains = gene_domains(grammar_id)
    ev = BudgetedEvaluator(budget, generation_action="SURROGATE_SEARCH", seed=seed,
                           grammar_id=grammar_id)
    archive = ParetoArchive()
    model = FeasibilitySurrogate(seed, grammar_id=grammar_id)

    def random_gene() -> dict:
        return {name: rng.choice(domains[name]) for name in order}

    def submit(screened: dict) -> dict | None:
        """Đánh giá THẬT qua BudgetedEvaluator; record feasible → archive."""
        rec = ev.evaluate_prescreened(screened)
        if rec and rec["feasible"]:
            archive.add(rec["case_id"], rec["objectives"], {"gene": rec["gene"]})
        return rec

    def mutate(parent: dict) -> dict:
        """Đột biến 1–2 biến: bước ±1 trên lưới domain hoặc reset ngẫu nhiên."""
        child = dict(parent)
        for name in rng.sample(order, rng.randint(1, 2)):
            dom = domains[name]
            i = dom.index(child[name]) if child[name] in dom else rng.randrange(len(dom))
            if rng.random() < 0.5:
                i = min(len(dom) - 1, max(0, i + rng.choice((-1, 1))))
            else:
                i = rng.randrange(len(dom))
            child[name] = dom[i]
        return child

    fit_log: list[dict] = []

    def refit() -> None:
        """Fit lại surrogate và ghi số liệu tập fit vào nhật ký chẩn đoán."""
        model.fit(ev.history)
        fit_log.append(dict(model.diagnostics,
                            solver_calls_at_fit=ev.n_solver_calls))

    # --- Pha 1: warmup ngẫu nhiên (có prefilter L0 miễn phí)
    n_warm = min(warmup, budget // 3)
    attempts = 0
    while ev.n_solver_calls < n_warm and attempts < 500 * max(1, n_warm):
        attempts += 1
        gene = random_gene()
        screened = ev.prescreen_gene(gene)
        if screened["outcome"] != "READY":
            continue
        if submit(screened) is None:
            break
    refit()
    calls_at_fit = ev.n_solver_calls

    # --- Pha 2: vòng lặp surrogate xếp hạng → đánh giá thật top batch.
    # Guard thoát sớm tính theo TỔNG số lần sinh ứng viên thất bại liên tiếp
    # (empty_rounds × pool_size) để không phụ thuộc pool_size — với pool nhỏ,
    # ngưỡng cố định 50 vòng có thể bỏ phí ngân sách (finding review P4).
    empty_rounds = 0
    while not ev.exhausted and empty_rounds * max(pool_size, 1) < 15000:
        # Nguồn cha mẹ cho nửa pool đột biến: archive → best feasible → (rỗng)
        parents = [e["payload"]["gene"] for e in archive.entries
                   if "gene" in e["payload"]]
        if not parents:
            feas = [r for r in ev.history if r["feasible"]]
            if feas:
                parents = [min(feas, key=lambda r: r["objectives"][0])["gene"]]

        candidates, seen = [], set()
        for k in range(pool_size):
            if parents and k % 2 == 1:      # 50% đột biến (khi có cha mẹ)
                gene = mutate(rng.choice(parents))
            else:                           # 50% ngẫu nhiên (khám phá)
                gene = random_gene()
            screened = ev.prescreen_gene(gene)
            if screened["outcome"] != "READY":
                continue
            h = screened["input_hash"]
            if h in seen:
                continue
            seen.add(h)
            candidates.append((gene, screened))

        if not candidates:
            empty_rounds += 1
            continue
        empty_rounds = 0

        # Điểm xếp hạng = P(feasible) − 0.3 × (cost_exact / 3000);
        # cost_exact tính giải tích từ hình học (compute_objectives, miễn phí)
        proba = model.predict_feasible_proba([c[0] for c in candidates])
        cheap_cost = [screened["cheap_objectives"][0] for _, screened in candidates]

        if ranking == "reward":
            # Bản CŨ: cộng thẳng P(khả thi) vào điểm. ĐO ĐƯỢC là TỆ HƠN cả bản bỏ
            # surrogate — giữ lại chỉ để tái lập kết quả âm, không dùng mặc định.
            scores = [float(proba[i]) - 0.3 * (cheap_cost[i] / 3000.0)
                      for i in range(len(candidates))]
            order_by_score = sorted(range(len(candidates)),
                                    key=lambda i: (-scores[i], i))
        elif ranking == "none":
            # Ablation: bỏ hẳn đóng góp của surrogate, xếp theo chi phí rẻ (giải tích).
            order_by_score = sorted(range(len(candidates)),
                                    key=lambda i: (cheap_cost[i], i))
        elif ranking == "gate":
            # Surrogate làm CỔNG LỌC, không làm điểm thưởng: loại ứng viên có
            # P(khả thi) dưới ngưỡng, rồi trong số còn lại xếp theo chi phí rẻ.
            # Lý do: phương án tối ưu nằm ĐÚNG TRÊN BIÊN khả thi — nơi P(khả thi)
            # thấp nhất — nên tối đa hóa P(khả thi) kéo tìm kiếm RỜI KHỎI chỗ cần
            # đến. Cổng lọc giữ được tác dụng loại phương án chắc chắn hỏng mà
            # không bẻ hướng tối ưu.
            passed = [i for i in range(len(candidates))
                      if float(proba[i]) >= feasibility_gate]
            if not passed:  # cổng quá chặt ở vòng này: không được bỏ trống batch
                passed = list(range(len(candidates)))
            order_by_score = sorted(passed, key=lambda i: (cheap_cost[i], i))
        else:
            raise ValueError(f"ranking không hợp lệ: {ranking!r}")

        for i in order_by_score[:batch_size]:
            if submit(candidates[i][1]) is None:
                break  # hết ngân sách

        if ev.n_solver_calls - calls_at_fit >= retrain_every:
            refit()
            calls_at_fit = ev.n_solver_calls

    config = {**ev.config, "algorithm": "surrogate_assisted", "warmup": warmup,
              "pool_size": pool_size, "batch_size": batch_size,
              "retrain_every": retrain_every,
              "ranking": ranking, "feasibility_gate": feasibility_gate,
              "surrogate_fit_set": "solver_run_records_only"}
    # Chẩn đoán tập fit: đo được surrogate học trên bao nhiêu mẫu và tỷ lệ lớp
    # ra sao, thay vì phải đoán khi đọc kết quả sau này.
    surrogate_diagnostics = {
        "n_fits": len(fit_log),
        "min_fit_samples": MIN_FIT_SAMPLES,
        "constant_mode_fits": sum(1 for f in fit_log
                                  if f["classifier_mode"] == "constant"),
        "last_fit": dict(fit_log[-1]) if fit_log else None,
        "fit_log": fit_log,
    }
    return {"algorithm": "surrogate_assisted", "seed": seed, "grammar_id": grammar_id,
            "config": config,
            "counters": ev.counters, "history": ev.history,
            "proposal_history": ev.proposal_history, "archive": archive,
            "surrogate_diagnostics": surrogate_diagnostics,
            "termination": "budget_exhausted" if ev.exhausted else "candidate_pool_exhausted"}
