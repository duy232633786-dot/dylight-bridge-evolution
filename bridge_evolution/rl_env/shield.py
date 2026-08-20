"""Safety shield L0: mask hành động dẫn tới thiết kế vô lý TRƯỚC khi tốn budget.

check_geometry là kiểm tra giải tích RẺ (không mở solver, không tính vào ngân
sách) nên được gọi tự do — đây chính là action mask hợp lệ về mặt khoa học:
shield chỉ chặn vi phạm hình học HARD, KHÔNG bao giờ tự kết luận khả thi
(feasibility chỉ đến từ record.feasible của đánh giá thật).
"""
from functools import lru_cache

import numpy as np

from ..geometry import check_geometry
from ..optimization.common import GENE_ORDER, gene_domains
from ..state import state_from_gene
from .actions import ACTIONS, SUBMIT_INDEX, VAR_INDEX


@lru_cache(maxsize=1)
def _domains() -> dict:
    """Miền giá trị grammar (cache — bất biến trong suốt phiên chạy)."""
    return gene_domains()


def decode_gene(idx_vec) -> dict:
    """Đổi vector chỉ số (theo thứ tự GENE_ORDER) thành gene dict."""
    d = _domains()
    return {name: d[name][i] for name, i in zip(GENE_ORDER, idx_vec)}


def gene_l0_valid(gene: dict) -> bool:
    """True nếu gene qua kiểm tra hình học L0 (không có violation HARD)."""
    violations, _ = check_geometry(state_from_gene(gene))
    return not any(v["severity"] == "HARD" for v in violations)


def valid_action_mask(idx_vec, sizes, l0_precheck: bool = True) -> np.ndarray:
    """Mask bool (len 17): True = hành động được phép từ trạng thái idx_vec.

    - DEC/INC đưa chỉ số ra ngoài [0, size-1] → False.
    - l0_precheck: gene sau đột biến có violation HARD hình học L0 → False.
    - SUBMIT luôn True — kể cả khi mọi hành động biến đổi bị mask, agent
      vẫn còn lối thoát hợp lệ (không bao giờ bị kẹt).
    """
    mask = np.zeros(len(ACTIONS), dtype=bool)
    mask[SUBMIT_INDEX] = True
    for a, (_name, var, delta) in enumerate(ACTIONS):
        if var is None:  # SUBMIT đã xử lý ở trên
            continue
        j = VAR_INDEX[var]
        new_idx = idx_vec[j] + delta
        if not 0 <= new_idx <= sizes[j] - 1:
            continue
        if l0_precheck:
            mutated = list(idx_vec)
            mutated[j] = new_idx
            if not gene_l0_valid(decode_gene(mutated)):
                continue
        mask[a] = True
    return mask
