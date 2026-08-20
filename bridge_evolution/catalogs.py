"""Nạp catalogs và grammar (nguồn dữ liệu duy nhất cho mọi module)."""
import json
from functools import lru_cache

from . import CATALOGS_DIR, GRAMMAR_DIR


@lru_cache(maxsize=1)
def load_catalogs() -> dict:
    with open(CATALOGS_DIR / "catalogs.json", encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=None)
def load_grammar(grammar_id: str = "super_t_simple_v1") -> dict:
    with open(GRAMMAR_DIR / f"{grammar_id}.json", encoding="utf-8") as f:
        return json.load(f)


def grid_domain(spec: dict) -> list:
    """Miền giá trị của một biến grammar dưới dạng list (dùng cho EA/RL action space)."""
    if spec["type"] in ("catalog", "int"):
        return list(spec["domain"])
    if spec["type"] == "grid":
        return list(range(spec["min"], spec["max"] + 1, spec["step"]))
    raise ValueError(f"Loại biến grammar không hỗ trợ: {spec['type']}")


def all_domains(grammar: dict) -> dict:
    """{tên biến: [giá trị hợp lệ, ...]} — action mask cấp 0 cho mọi thuật toán."""
    return {name: grid_domain(spec) for name, spec in grammar["design_variables"].items()}
