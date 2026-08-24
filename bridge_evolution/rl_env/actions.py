"""Không gian hành động rời rạc cho RL: ±1 bước lưới trên từng biến gene + SUBMIT.

actions[i] = (tên hành động, tên biến trong gene_order | None, delta).
Mỗi biến có cặp DEC (-1) / INC (+1) theo ĐÚNG thứ tự ``gene_order(grammar_id)``;
SUBMIT luôn nằm CUỐI danh sách. Số hành động = 2 × số biến + 1:
  * grammar v1 (8 biến)  → 17 hành động, SUBMIT ở index 16;
  * grammar v2 (14 biến) → 29 hành động, SUBMIT ở index 28.

``ACTIONS``/``N_ACTIONS``/``SUBMIT_INDEX``/``VAR_INDEX`` cấp module là bản ĐÓNG
BĂNG của grammar v1 (backward compat cho mọi consumer cũ). Code chạy đa grammar
phải dùng ``build_actions(grammar_id)`` + ``submit_index(actions)`` +
``var_index(order)``.
"""
from functools import lru_cache

from ..optimization.common import DEFAULT_GRAMMAR_ID, GENE_ORDER, gene_order


def _actions_from_order(order) -> list[tuple[str, str | None, int]]:
    """Sinh cặp DEC/INC theo thứ tự biến rồi thêm SUBMIT ở CUỐI."""
    actions: list[tuple[str, str | None, int]] = []
    for var in order:
        actions.append((f"DEC_{var}", var, -1))
        actions.append((f"INC_{var}", var, +1))
    actions.append(("SUBMIT", None, 0))
    return actions


@lru_cache(maxsize=None)
def _actions_cached(grammar_id: str) -> tuple[tuple[str, str | None, int], ...]:
    """Bản tuple bất biến để cache (danh sách hành động không đổi trong phiên)."""
    return tuple(_actions_from_order(gene_order(grammar_id)))


def build_actions(grammar_id: str = DEFAULT_GRAMMAR_ID) -> list[tuple[str, str | None, int]]:
    """Danh sách hành động của một grammar (list mới mỗi lần gọi, an toàn để sửa)."""
    return list(_actions_cached(grammar_id))


def submit_index(actions) -> int:
    """Vị trí SUBMIT — theo quy ước luôn là phần tử CUỐI của danh sách."""
    return len(actions) - 1


def var_index(order) -> dict[str, int]:
    """{tên biến: vị trí trong vector chỉ số} cho một ``gene_order`` bất kỳ."""
    return {name: j for j, name in enumerate(order)}


# --- Bản v1 đóng băng: dựng thẳng từ hằng GENE_ORDER, không phụ thuộc file I/O.
ACTIONS: list[tuple[str, str | None, int]] = _actions_from_order(GENE_ORDER)

N_ACTIONS = len(ACTIONS)          # 17
SUBMIT_INDEX = N_ACTIONS - 1      # 16

# Tra cứu nhanh: tên biến -> vị trí trong GENE_ORDER (dùng cho shield/env)
VAR_INDEX = var_index(GENE_ORDER)
