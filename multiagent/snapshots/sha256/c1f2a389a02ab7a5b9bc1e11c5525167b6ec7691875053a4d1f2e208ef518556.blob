"""Nạp catalogs và grammar (nguồn dữ liệu duy nhất cho mọi module)."""
import json
import re
from functools import lru_cache

from . import CATALOGS_DIR, GRAMMAR_DIR


class GrammarIdError(ValueError):
    """``grammar_id`` không hợp lệ — chặn TRƯỚC khi chạm hệ thống tệp.

    Đây không phải hàng rào bảo mật (không có đầu vào từ người ngoài). Rủi ro
    thật là TRUY VẾT: ``bridge_grammar/experimental/`` chứa các họ kết cấu mà
    runtime KHÔNG có solver (vòm), ở mức claim IDEA. Trước đây
    ``load_grammar("experimental/arch_deck_v1")`` nạp được, và
    ``gene_order()``/``gene_domains()`` chạy trơn trên nó — đường sinh số chỉ
    dừng ở ``BudgetedEvaluator`` bằng một ``KeyError`` tình cờ. Một con số phát
    ra từ họ vòm rồi bị đọc như thể có hiệu lực là hỏng đúng thứ mà thang
    fidelity sinh ra để bảo vệ.
    """


# Tên grammar production: chữ/số, '_' và '-'. Cố ý KHÔNG cho '/', '\\', '.',
# ':' — tức chặn luôn '..', tên có đuôi và đường dẫn tuyệt đối.
_GRAMMAR_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")


def _validated_grammar_path(grammar_id: str):
    """Đường dẫn grammar đã kiểm, hoặc ``GrammarIdError`` nói rõ lý do."""
    if not isinstance(grammar_id, str) or not grammar_id:
        raise GrammarIdError(
            f"grammar_id phải là chuỗi không rỗng, nhận được {grammar_id!r}")
    if not _GRAMMAR_ID_PATTERN.fullmatch(grammar_id):
        raise GrammarIdError(
            f"grammar_id {grammar_id!r} không hợp lệ: chỉ chấp nhận chữ, số, '_' và '-'. "
            "Dấu phân cách đường dẫn ('/', '\\\\'), '..' và đường dẫn tuyệt đối bị chặn "
            "để grammar sandbox trong bridge_grammar/experimental/ không lọt vào đường "
            "sinh số production. Sandbox chỉ được nạp qua đường dẫn tường minh trong "
            "test, không qua load_grammar()."
        )
    path = (GRAMMAR_DIR / f"{grammar_id}.json").resolve()
    # Phòng thủ tầng hai: dù pattern có bị nới trong tương lai, tệp vẫn phải nằm
    # TRỰC TIẾP trong GRAMMAR_DIR, không phải thư mục con.
    if path.parent != GRAMMAR_DIR.resolve():
        raise GrammarIdError(
            f"grammar_id {grammar_id!r} phân giải ra ngoài thư mục grammar production: {path}")
    return path


@lru_cache(maxsize=1)
def load_catalogs() -> dict:
    with open(CATALOGS_DIR / "catalogs.json", encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=None)
def load_grammar(grammar_id: str = "super_t_simple_v1") -> dict:
    with open(_validated_grammar_path(grammar_id), encoding="utf-8") as f:
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
