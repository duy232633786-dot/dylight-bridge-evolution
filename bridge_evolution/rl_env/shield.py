"""Safety shield L0: mask hành động dẫn tới thiết kế vô lý TRƯỚC khi tốn budget.

check_geometry là kiểm tra giải tích RẺ (không mở solver, không tính vào ngân
sách) nên được gọi tự do — đây chính là action mask hợp lệ về mặt khoa học:
shield chỉ chặn vi phạm hình học HARD (gồm cả nhóm chế tạo FAB-* của grammar
tham số hóa v2), KHÔNG bao giờ tự kết luận khả thi (feasibility chỉ đến từ
record.feasible của đánh giá thật).

Mọi hàm nhận ``grammar_id`` với mặc định v1 để chữ ký cũ chạy y nguyên.
"""
from functools import lru_cache

import numpy as np

from ..geometry import check_geometry
from ..optimization.common import DEFAULT_GRAMMAR_ID, gene_domains, gene_order
from ..state import state_from_gene
from .actions import build_actions, var_index


@lru_cache(maxsize=None)
def _domains(grammar_id: str = DEFAULT_GRAMMAR_ID) -> dict:
    """Miền giá trị grammar (cache — bất biến trong suốt phiên chạy)."""
    return gene_domains(grammar_id)


@lru_cache(maxsize=None)
def _order(grammar_id: str = DEFAULT_GRAMMAR_ID) -> tuple[str, ...]:
    """Thứ tự biến của grammar (cache; tuple để hashable trong lru_cache)."""
    return tuple(gene_order(grammar_id))


def decode_gene(idx_vec, grammar_id: str = DEFAULT_GRAMMAR_ID) -> dict:
    """Đổi vector chỉ số (theo thứ tự gene_order của grammar) thành gene dict."""
    d = _domains(grammar_id)
    return {name: d[name][i] for name, i in zip(_order(grammar_id), idx_vec)}


def gene_l0_valid(gene: dict, grammar_id: str = DEFAULT_GRAMMAR_ID) -> bool:
    """True nếu gene qua kiểm tra hình học L0 (không có violation HARD).

    Fail-closed: gene không dựng nổi state/hình học (id lạ, thiếu khóa) coi như
    KHÔNG hợp lệ — shield thà chặn oan còn hơn để một hành động hỏng đi tới
    solver. Với grammar v1 nhánh này không bao giờ kích hoạt nên hành vi cũ
    không đổi.
    """
    try:
        violations, _ = check_geometry(state_from_gene(gene, grammar_id=grammar_id))
    except (KeyError, TypeError, ValueError):
        return False
    return not any(v["severity"] == "HARD" for v in violations)


def valid_action_mask(idx_vec, sizes, l0_precheck: bool = True,
                      grammar_id: str = DEFAULT_GRAMMAR_ID) -> np.ndarray:
    """Mask bool (len = 2·n_var + 1): True = hành động được phép từ idx_vec.

    - DEC/INC đưa chỉ số ra ngoài [0, size-1] → False.
    - l0_precheck: gene sau đột biến có violation HARD hình học L0 → False.
      Với grammar v2, nhóm này bao gồm FAB-000…FAB-006 (chế tạo/vận chuyển/
      cẩu lắp/bố trí cáp) nên shield chặn được cả hành động phi chế tạo.
    - SUBMIT luôn True — kể cả khi mọi hành động biến đổi bị mask, agent
      vẫn còn lối thoát hợp lệ (không bao giờ bị kẹt).
    """
    actions = build_actions(grammar_id)
    var_pos = var_index(_order(grammar_id))
    mask = np.zeros(len(actions), dtype=bool)
    mask[len(actions) - 1] = True  # SUBMIT ở CUỐI danh sách
    for a, (_name, var, delta) in enumerate(actions):
        if var is None:  # SUBMIT đã xử lý ở trên
            continue
        j = var_pos[var]
        new_idx = idx_vec[j] + delta
        if not 0 <= new_idx <= sizes[j] - 1:
            continue
        if l0_precheck:
            mutated = list(idx_vec)
            mutated[j] = new_idx
            if not gene_l0_valid(decode_gene(mutated, grammar_id), grammar_id):
                continue
        mask[a] = True
    return mask
