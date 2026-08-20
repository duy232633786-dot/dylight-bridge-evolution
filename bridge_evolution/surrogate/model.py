"""Surrogate học máy dự đoán khả năng khả thi — CHỈ dùng để XẾP HẠNG ứng viên.

QUAN TRỌNG (quy tắc trung thực): surrogate KHÔNG BAO GIỜ được kết luận một
phương án là khả thi. Nhãn feasible duy nhất đến từ đánh giá thật qua
BudgetedEvaluator.evaluate_gene. Model ở đây chỉ là bộ lọc ưu tiên: dự đoán
P(feasible) và max_utilization để quyết định ứng viên nào ĐÁNG tiêu một lần
gọi solver thật trước các ứng viên khác.
"""
import numpy as np
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor

from ..geometry import derive_geometry
from ..optimization.common import gene_domains
from ..state import state_from_gene

# 4 biến catalog được one-hot theo ĐÚNG thứ tự domain trong grammar
_ONE_HOT_VARS = ["girder_catalog_id", "girder_concrete_id",
                 "deck_concrete_id", "diaphragm_layout_id"]
# 3 biến số học chuẩn hóa min-max về [0, 1]
_NUMERIC_VARS = ["girder_count", "girder_spacing_mm", "deck_slab_thickness_mm"]


class FeasibilitySurrogate:
    """Random Forest học từ record của BudgetedEvaluator (mọi status đều là dữ liệu).

    - Classifier: P(record.feasible) — nếu nhãn chỉ có 1 lớp thì rơi về chế độ
      hằng số (proba = tỷ lệ lớp feasible trong dữ liệu).
    - Regressor: max_utilization trên các record có kết quả solver; nếu < 10
      mẫu thì bỏ qua (predict trả 1.0 — trung tính, không thiên vị).
    """

    def __init__(self, seed: int):
        self.seed = seed
        self.domains = gene_domains()
        self._clf = None            # None = chế độ hằng số
        self._const_proba = 0.5     # dùng khi chưa fit hoặc nhãn 1 lớp
        self._reg = None            # None = chưa đủ mẫu utilization

    def _features(self, gene: dict) -> np.ndarray:
        """Vector đặc trưng: one-hot catalog + số học chuẩn hóa + hình học rẻ."""
        x = []
        # 1. One-hot 4 biến catalog (thứ tự theo domain grammar: 3+3+2+3)
        for name in _ONE_HOT_VARS:
            dom = self.domains[name]
            vec = [0.0] * len(dom)
            try:
                vec[dom.index(gene[name])] = 1.0
            except ValueError:
                pass  # giá trị ngoài grammar → vector 0 (không nổ)
            x.extend(vec)
        # 2. Biến số học chuẩn hóa [0,1] + chỉ số prestress layout chuẩn hóa
        for name in _NUMERIC_VARS:
            dom = self.domains[name]
            lo, hi = min(dom), max(dom)
            x.append((float(gene[name]) - lo) / (hi - lo))
        pt_dom = self.domains["prestress_layout_id"]
        try:
            x.append(pt_dom.index(gene["prestress_layout_id"]) / (len(pt_dom) - 1))
        except ValueError:
            x.append(0.0)
        # 3. Đặc trưng hình học rẻ (derive_geometry KHÔNG mở solver, miễn phí)
        try:
            geom = derive_geometry(state_from_gene(gene))
            s_mm = float(gene["girder_spacing_mm"])
            ts_req = max(0.175, (s_mm + 3000) / 30 / 1000)
            x.extend([geom["overhang_m"], geom["flange_gap_m"],
                      geom["slab_thickness_m"] - ts_req])
        except Exception:
            x.extend([0.0, 0.0, 0.0])  # gene lỗi hình học → điền 0 cho nhóm
        return np.array(x, dtype=float)

    def fit(self, records: list[dict]) -> None:
        """Huấn luyện trên record của BudgetedEvaluator (nhận mọi status)."""
        if not records:
            self._clf, self._const_proba, self._reg = None, 0.5, None
            return
        X = np.vstack([self._features(r["gene"]) for r in records])
        y = np.array([bool(r["feasible"]) for r in records])
        if len(set(y.tolist())) < 2:
            # Chỉ 1 lớp nhãn → không thể train classifier → chế độ hằng số
            self._clf = None
            self._const_proba = float(y.mean())
        else:
            self._clf = RandomForestClassifier(n_estimators=200,
                                               random_state=self.seed)
            self._clf.fit(X, y)
        # Regressor max_utilization: chỉ record đã qua solver mới có giá trị
        pairs = [(x, r["max_utilization"]) for x, r in zip(X, records)
                 if r["max_utilization"] is not None]
        if len(pairs) < 10:
            self._reg = None
        else:
            Xu = np.vstack([p[0] for p in pairs])
            yu = np.array([p[1] for p in pairs], dtype=float)
            self._reg = RandomForestRegressor(n_estimators=200,
                                              random_state=self.seed)
            self._reg.fit(Xu, yu)

    def predict_feasible_proba(self, genes: list[dict]) -> np.ndarray:
        """P(feasible) dự đoán cho từng gene — chỉ dùng để xếp hạng ứng viên."""
        if not genes:
            return np.zeros(0)
        if self._clf is None:
            return np.full(len(genes), self._const_proba)
        X = np.vstack([self._features(g) for g in genes])
        proba = self._clf.predict_proba(X)
        idx = list(self._clf.classes_).index(True)
        return proba[:, idx]

    def predict_utilization(self, genes: list[dict]) -> np.ndarray:
        """max_utilization dự đoán; trả 1.0 (trung tính) nếu chưa đủ mẫu train."""
        if not genes:
            return np.zeros(0)
        if self._reg is None:
            return np.ones(len(genes))
        X = np.vstack([self._features(g) for g in genes])
        return self._reg.predict(X)
