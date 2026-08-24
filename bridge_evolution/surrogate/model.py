"""Surrogate học máy dự đoán khả năng khả thi — CHỈ dùng để XẾP HẠNG ứng viên.

QUAN TRỌNG (quy tắc trung thực): surrogate KHÔNG BAO GIỜ được kết luận một
phương án là khả thi. Nhãn feasible duy nhất đến từ đánh giá thật qua
BudgetedEvaluator.evaluate_gene. Model ở đây chỉ là bộ lọc ưu tiên: dự đoán
P(feasible) và max_utilization để quyết định ứng viên nào ĐÁNG tiêu một lần
gọi solver thật trước các ứng viên khác.

Đặc trưng được SUY TỪ GRAMMAR (``gene_domains(grammar_id)``), không hard-code
danh sách biến, nên grammar tham số hóa v2 đưa được cả 6 biến hình dạng vào
model. Với grammar v1 thứ tự cột ra đúng bố cục cũ (one-hot 4 biến catalog →
3 biến số học → chỉ số PT chuẩn hóa → 3 đặc trưng hình học).

TẬP HUẤN LUYỆN (finding review S1): model CHỈ được fit trên record đã thực sự
tiêu một lần gọi solver. Xem docstring ``FeasibilitySurrogate.fit``.
"""
from functools import lru_cache

import numpy as np
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor

from ..catalogs import load_grammar
from ..geometry import check_geometry, derive_geometry
from ..optimization.common import DEFAULT_GRAMMAR_ID, gene_domains, gene_order
from ..state import state_from_gene

#: Biến kiểu catalog CÓ thứ tự tự nhiên ⇒ mã hóa bằng chỉ số chuẩn hóa [0,1]
#: thay vì one-hot (PT-34 < PT-38 < … là dãy tăng số tao cáp).
_ORDINAL_CATALOG_VARS = ("prestress_layout_id",)

#: Số mẫu TỐI THIỂU (đếm SAU khi lọc về tập đồng phân phối với pool ứng viên) để
#: được phép train. Dưới ngưỡng này model rơi về chế độ hằng số: thà không xếp
#: hạng còn hơn xếp hạng bằng một model học từ vài mẫu — đó là đoán bừa.
MIN_FIT_SAMPLES = 10


def is_solver_run_record(record: dict) -> bool:
    """True nếu record ĐÃ thực sự mở solver (tiêu đúng một đơn vị ngân sách).

    Hai tín hiệu của ``BudgetedEvaluator._record_result`` luôn đi cùng nhau
    (``solver_call_index`` chỉ được gán khi ``solver_status != "NOT_RUN"``); ở
    đây chấp nhận một trong hai để history dựng tay trong test cũng phân loại
    đúng.
    """
    if record.get("solver_call_index") is not None:
        return True
    return record.get("solver_status", "NOT_RUN") not in (None, "NOT_RUN")


@lru_cache(maxsize=200_000)
def _l0_hard_rejected(grammar_id: str, gene_items: tuple) -> bool:
    """True nếu gene có vi phạm HARD ở L0 — LUẬT giải tích, không phải dự đoán.

    ``check_geometry`` miễn phí (không mở solver) nên gọi tự do; gene không dựng
    nổi state/hình học được coi là bị bác bỏ (fail-closed, giống shield L0).
    """
    try:
        violations, _ = check_geometry(
            state_from_gene(dict(gene_items), grammar_id=grammar_id))
    except (KeyError, TypeError, ValueError):
        return True
    return any(v.get("severity") == "HARD" for v in violations)


def _feature_spec(grammar_id: str) -> tuple[list[str], list[str], list[str]]:
    """(biến one-hot, biến số học, biến catalog có thứ tự) theo ``gene_order``.

    Quy tắc suy từ grammar: ``type`` là ``int``/``grid`` ⇒ số học (chuẩn hóa
    min-max theo domain); ``catalog`` ⇒ one-hot, trừ nhóm ``_ORDINAL_CATALOG_VARS``.
    Với v1 quy tắc này tái tạo ĐÚNG bố cục cột cũ.
    """
    specs = load_grammar(grammar_id)["design_variables"]
    one_hot, numeric, ordinal = [], [], []
    for name in gene_order(grammar_id):
        if specs[name]["type"] in ("int", "grid"):
            numeric.append(name)
        elif name in _ORDINAL_CATALOG_VARS:
            ordinal.append(name)
        else:
            one_hot.append(name)
    return one_hot, numeric, ordinal


class FeasibilitySurrogate:
    """Random Forest học từ record ĐÃ CHẠY SOLVER của BudgetedEvaluator.

    - Classifier: P(record.feasible) — nếu quá ít mẫu hoặc nhãn chỉ có 1 lớp thì
      rơi về chế độ hằng số (proba = tỷ lệ lớp feasible trong tập fit).
    - Regressor: max_utilization trên các record có kết quả solver; nếu
      < ``MIN_FIT_SAMPLES`` mẫu thì bỏ qua (predict trả 1.0 — trung tính).
    - ``diagnostics``: số mẫu fit, tỷ lệ từng lớp, chế độ và số lần fit — để lần
      sau ĐO được chất lượng tập huấn luyện thay vì đoán.
    """

    def __init__(self, seed: int, grammar_id: str = DEFAULT_GRAMMAR_ID):
        self.seed = seed
        self.grammar_id = grammar_id
        self.domains = gene_domains(grammar_id)
        self._one_hot_vars, self._numeric_vars, self._ordinal_vars = \
            _feature_spec(grammar_id)
        self._clf = None            # None = chế độ hằng số
        self._const_proba = 0.5     # dùng khi chưa fit hoặc nhãn 1 lớp
        self._reg = None            # None = chưa đủ mẫu utilization
        self._n_fits = 0
        self.diagnostics = self._diagnostics(0, 0, 0, 0, "constant", 0, "constant")

    def _diagnostics(self, records_seen: int, fit_samples: int, n_feasible: int,
                     n_infeasible: int, classifier_mode: str,
                     utilization_samples: int, utilization_mode: str) -> dict:
        """Khối số liệu JSON-friendly về CHÍNH tập đã dùng để fit."""
        return {
            "n_fits": self._n_fits,
            "min_fit_samples": MIN_FIT_SAMPLES,
            "records_seen": records_seen,
            "records_dropped_not_solver_run": records_seen - fit_samples,
            "fit_samples": fit_samples,
            "n_feasible": n_feasible,
            "n_infeasible": n_infeasible,
            "feasible_rate": (n_feasible / fit_samples) if fit_samples else 0.0,
            "infeasible_rate": (n_infeasible / fit_samples) if fit_samples else 0.0,
            "classifier_mode": classifier_mode,
            "const_proba": self._const_proba,
            "utilization_samples": utilization_samples,
            "utilization_mode": utilization_mode,
        }

    def _features(self, gene: dict) -> np.ndarray:
        """Vector đặc trưng: one-hot catalog + số học chuẩn hóa + hình học rẻ."""
        x = []
        # 1. One-hot các biến catalog (thứ tự theo domain grammar)
        for name in self._one_hot_vars:
            dom = self.domains[name]
            vec = [0.0] * len(dom)
            try:
                vec[dom.index(gene[name])] = 1.0
            except (KeyError, ValueError):
                pass  # giá trị ngoài grammar / thiếu khóa → vector 0 (không nổ)
            x.extend(vec)
        # 2. Biến số học chuẩn hóa [0,1] theo min/max của domain
        for name in self._numeric_vars:
            dom = self.domains[name]
            lo, hi = min(dom), max(dom)
            try:
                x.append((float(gene[name]) - lo) / (hi - lo) if hi > lo else 0.0)
            except (KeyError, TypeError, ValueError):
                x.append(0.0)
        # 3. Biến catalog có thứ tự → chỉ số chuẩn hóa
        for name in self._ordinal_vars:
            dom = self.domains[name]
            try:
                x.append(dom.index(gene[name]) / (len(dom) - 1) if len(dom) > 1 else 0.0)
            except (KeyError, ValueError):
                x.append(0.0)
        # 4. Đặc trưng hình học rẻ (derive_geometry KHÔNG mở solver, miễn phí).
        #    Với v2, tiết diện được TÍNH từ 6 biến hình dạng; bộ tham số phi vật
        #    lý ném SectionGeometryError (ValueError) → điền 0 cho cả nhóm.
        try:
            geom = derive_geometry(state_from_gene(gene, grammar_id=self.grammar_id))
            s_mm = float(gene["girder_spacing_mm"])
            ts_req = max(0.175, (s_mm + 3000) / 30 / 1000)
            x.extend([geom["overhang_m"], geom["flange_gap_m"],
                      geom["slab_thickness_m"] - ts_req])
        except (KeyError, TypeError, ValueError):
            x.extend([0.0, 0.0, 0.0])  # gene lỗi hình học → điền 0 cho nhóm
        return np.array(x, dtype=float)

    def fit(self, records: list[dict]) -> None:
        """Huấn luyện CHỈ trên record ĐÃ CHẠY SOLVER (đồng phân phối với pool).

        Vì sao lọc (finding review S1): pool ứng viên của mọi thuật toán đã đi
        qua prefilter L0, nên gene L0-fail KHÔNG BAO GIỜ xuất hiện trong tập cần
        xếp hạng. Trên grammar v2, ~98.9% record trong ``ev.history`` là
        L0_REJECTED (solver NOT_RUN); fit trên đó là học đúng thứ mà prefilter
        đã loại miễn phí — vô dụng vì lệch phân phối, và có hại vì tín hiệu
        "hình học hỏng ⇒ infeasible" nhấn chìm tín hiệu "ứng suất/độ võng ⇒
        infeasible" là thứ duy nhất còn phân biệt được các ứng viên trong pool.
        Đo được: xếp hạng bằng model học trên toàn history TỆ HƠN cả ablation
        chọn ngẫu nhiên trong pool, ở cùng budget/seed/prefilter.

        Không tự bịa dữ liệu: nếu sau khi lọc còn < ``MIN_FIT_SAMPLES`` mẫu hoặc
        chỉ còn MỘT lớp nhãn thì chuyển sang chế độ hằng số (mọi ứng viên cùng
        điểm ⇒ surrogate không tác động vào xếp hạng) thay vì đoán bừa.
        """
        self._n_fits += 1
        fit_records = [r for r in records if is_solver_run_record(r)]
        n_seen, n_fit = len(records), len(fit_records)
        y = np.array([bool(r["feasible"]) for r in fit_records], dtype=bool)
        n_pos = int(y.sum()) if n_fit else 0
        n_neg = n_fit - n_pos

        X = (np.vstack([self._features(r["gene"]) for r in fit_records])
             if n_fit else None)
        if n_fit < MIN_FIT_SAMPLES or n_pos == 0 or n_neg == 0:
            # Quá ít mẫu hoặc 1 lớp nhãn → không train → chế độ hằng số.
            self._clf = None
            self._const_proba = float(n_pos / n_fit) if n_fit else 0.5
            clf_mode = "constant"
        else:
            self._clf = RandomForestClassifier(n_estimators=200,
                                               random_state=self.seed)
            self._clf.fit(X, y)
            clf_mode = "random_forest"

        # Regressor max_utilization: chỉ lấy trong CÙNG tập đã lọc.
        pairs = ([(x, r["max_utilization"]) for x, r in zip(X, fit_records)
                  if r.get("max_utilization") is not None] if n_fit else [])
        if len(pairs) < MIN_FIT_SAMPLES:
            self._reg = None
            reg_mode = "constant"
        else:
            Xu = np.vstack([p[0] for p in pairs])
            yu = np.array([p[1] for p in pairs], dtype=float)
            self._reg = RandomForestRegressor(n_estimators=200,
                                              random_state=self.seed)
            self._reg.fit(Xu, yu)
            reg_mode = "random_forest"

        self.diagnostics = self._diagnostics(n_seen, n_fit, n_pos, n_neg,
                                             clf_mode, len(pairs), reg_mode)

    def predict_feasible_proba(self, genes: list[dict]) -> np.ndarray:
        """P(feasible) dự đoán cho từng gene — chỉ dùng để xếp hạng ứng viên.

        Gene bị L0 bác bỏ nhận P = 0 theo LUẬT (vi phạm HARD hình học ⇒ chắc
        chắn không feasible), không phải theo model: đây là hệ quả giải tích
        miễn phí, giữ cho model nhất quán với prefilter mà không cần học lại nó.
        Trong vòng lặp tìm kiếm mọi ứng viên đều đã qua L0 nên nhánh này không
        đổi thứ tự xếp hạng của pool.
        """
        if not genes:
            return np.zeros(0)
        if self._clf is None:
            proba = np.full(len(genes), self._const_proba, dtype=float)
        else:
            X = np.vstack([self._features(g) for g in genes])
            idx = list(self._clf.classes_).index(True)
            proba = np.array(self._clf.predict_proba(X)[:, idx], dtype=float)
        for i, gene in enumerate(genes):
            if _l0_hard_rejected(self.grammar_id, tuple(sorted(gene.items()))):
                proba[i] = 0.0
        return proba

    def predict_utilization(self, genes: list[dict]) -> np.ndarray:
        """max_utilization dự đoán; trả 1.0 (trung tính) nếu chưa đủ mẫu train."""
        if not genes:
            return np.zeros(0)
        if self._reg is None:
            return np.ones(len(genes))
        X = np.vstack([self._features(g) for g in genes])
        return self._reg.predict(X)
