"""Không gian hành động rời rạc cho RL: ±1 bước lưới trên từng biến gene + SUBMIT.

ACTIONS[i] = (tên hành động, tên biến trong GENE_ORDER | None, delta).
Mỗi biến có cặp DEC (-1) / INC (+1) theo đúng thứ tự GENE_ORDER (8 biến → 16
hành động biến đổi); SUBMIT luôn nằm CUỐI danh sách (index 16).
"""
from ..optimization.common import GENE_ORDER

ACTIONS: list[tuple[str, str | None, int]] = []
for _var in GENE_ORDER:
    ACTIONS.append((f"DEC_{_var}", _var, -1))
    ACTIONS.append((f"INC_{_var}", _var, +1))
ACTIONS.append(("SUBMIT", None, 0))

N_ACTIONS = len(ACTIONS)          # 17
SUBMIT_INDEX = N_ACTIONS - 1      # 16

# Tra cứu nhanh: tên biến -> vị trí trong GENE_ORDER (dùng cho shield/env)
VAR_INDEX = {name: j for j, name in enumerate(GENE_ORDER)}
