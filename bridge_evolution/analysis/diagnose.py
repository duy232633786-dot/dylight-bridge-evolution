"""Chẩn đoán vi phạm → đề xuất nước sửa (repair moves) trong miền grammar.

Nguyên tắc:
- KHÔNG bao giờ gọi solver: chỉ dùng check_geometry (rẻ, L0), gene_domains
  và query_knowledge. Feasibility CHỈ đến từ đánh giá thật qua evaluate_candidate.
- Mọi đề xuất phải nằm trong miền grammar và khi áp thử vào bản sao state,
  check_geometry KHÔNG được sinh vi phạm HARD MỚI. Nước sửa cho nhóm GEOM phải
  gỡ HẾT các rule GEOM-*; vi phạm CONS tồn dư sẵn có được phép giữ lại (sẽ có
  đề xuất riêng cho nó) — người dùng gọi suggest_repairs lặp nhiều vòng cho
  tới khi hết vi phạm.
- Thẻ tri thức chỉ dùng để GẮN NHÃN nguồn gợi ý (card_id) — không quyết định
  PASS/FAIL.
"""
import copy

from ..geometry import check_geometry
from ..knowledge import load_cards, query_knowledge
from ..optimization.common import gene_domains
from ..state import validate_design_state

# Hai biến vật liệu nằm trong state["materials"], phần còn lại ở design_variables
_MATERIAL_VARS = ("girder_concrete_id", "deck_concrete_id")

# Bảng ánh xạ rule → chuỗi nước sửa dạng bậc thang (theo thứ tự ưu tiên).
# Mỗi mục: (tên biến, bước ±1 trên miền, lý do tiếng Việt).
_STEP_MOVES = {
    "SERV-001": [
        ("prestress_layout_id", +1,
         "tăng một bậc cáp DƯL để tăng lực nén trước, bù ứng suất kéo thớ dưới"),
        ("girder_catalog_id", +1,
         "dùng tiết diện dầm cao hơn để tăng mô đun chống uốn"),
        ("girder_concrete_id", +1,
         "nâng grade bê tông dầm để tăng giới hạn kéo cho phép (đòn bẩy cuối)"),
    ],
    "STR-001": [
        ("prestress_layout_id", +1,
         "tăng một bậc cáp DƯL để tăng sức kháng uốn φMn"),
        ("girder_catalog_id", +1,
         "dùng tiết diện dầm cao hơn để tăng cánh tay đòn nội lực"),
    ],
    "STR-002": [
        ("girder_count", +1,
         "thêm một dầm để giảm phần tải cắt mỗi dầm phải gánh"),
        ("girder_catalog_id", +1,
         "dùng tiết diện dầm cao hơn để tăng sức kháng cắt"),
        ("girder_spacing_mm", -1,
         "giảm một bậc khoảng cách dầm để giảm hệ số phân phối tải cắt"),
    ],
    "SERV-002": [
        ("girder_catalog_id", +1,
         "dùng tiết diện dầm cao hơn để tăng độ cứng, giảm võng hoạt tải"),
        ("girder_count", +1,
         "thêm một dầm để giảm tải mỗi dầm, giảm võng hoạt tải"),
    ],
}


def _get_var(state: dict, name: str):
    if name in _MATERIAL_VARS:
        return state["materials"][name]
    return state["design_variables"][name]


def _with_var(state: dict, name: str, value) -> dict:
    """Bản sao state với một biến được thay giá trị (không đụng state gốc)."""
    s = copy.deepcopy(state)
    if name in _MATERIAL_VARS:
        s["materials"][name] = value
    else:
        s["design_variables"][name] = value
    return s


def _hard_geo_rules(state: dict) -> set | None:
    """Tập rule_id vi phạm HARD của check_geometry; None nếu id lạ ngoài catalog."""
    try:
        violations, _ = check_geometry(state)
    except KeyError:
        return None
    return {v["rule_id"] for v in violations if v["severity"] == "HARD"}


def _step_value(domain: list, current, delta: int):
    """Giá trị cách current đúng delta bậc trên miền; None nếu ra ngoài miền."""
    try:
        idx = domain.index(current)
    except ValueError:
        return None
    j = idx + delta
    if 0 <= j < len(domain):
        return domain[j]
    return None


def _no_new_hard(state: dict, name: str, value, base_rules: set | None) -> bool:
    """Áp thử một nước sửa: không được sinh vi phạm HARD hình học MỚI."""
    if base_rules is None:
        return False
    new_rules = _hard_geo_rules(_with_var(state, name, value))
    return new_rules is not None and new_rules <= base_rules


def _geom_clean(state: dict, name: str, value, base_rules: set | None = None) -> bool:
    """Áp thử nước sửa GEOM: gỡ hết mọi rule GEOM-*, không sinh HARD mới.

    Vi phạm CONS tồn dư SẴN CÓ (⊆ base_rules) được phép giữ lại — nó độc lập
    với biến hình học đang sửa và sẽ có đề xuất riêng; đòi sạch tuyệt đối sẽ
    triệt tiêu oan nước sửa spacing khi GEOM-001 + CONS-001 vi phạm đồng thời
    (finding review analysis).
    """
    rules = _hard_geo_rules(_with_var(state, name, value))
    if rules is None or any(r.startswith("GEOM") for r in rules):
        return False
    return rules <= (base_rules or set())


def suggest_repairs(state: dict, result: dict, top_k: int = 5) -> list[dict]:
    """Đề xuất tối đa top_k nước sửa cho các vi phạm HARD trong result["violations"].

    Trả về list dict {"rule_id", "variable", "current", "proposed",
    "rationale" (tiếng Việt), "card_id" (str | None)} — gom theo từng vi phạm
    HARD (giữ thứ tự trong result), dedupe theo (variable, proposed).
    Hàm này KHÔNG gọi solver; mọi kiểm tra đều qua check_geometry (miễn phí).
    """
    # Repair moves chỉ có nghĩa với state đã đúng contract. Với input
    # schema-invalid, evaluate_candidate đã trả chẩn đoán SCHEMA-*; không
    # dereference các section còn thiếu hoặc ID lạ để tránh diagnose crash.
    if (not isinstance(state, dict) or not isinstance(result, dict)
            or result.get("status") == "SCHEMA_INVALID"
            or validate_design_state(state)):
        return []

    domains = gene_domains(state.get("family", "super_t_simple_v1"))
    cards = load_cards()
    base_rules = _hard_geo_rules(state)
    dv = state["design_variables"]

    suggestions: list[dict] = []
    seen: set = set()

    def card_for(rule_id: str, variable: str | None) -> str | None:
        hits = query_knowledge(failed_rules=[rule_id],
                               variables=[variable] if variable else [],
                               cards=cards)
        if hits and hits[0]["score"] >= 3:
            return hits[0]["card"]["card_id"]
        return None

    def push(rule_id: str, variable: str | None, proposed, rationale: str):
        key = (variable, proposed)
        if key in seen:
            return
        seen.add(key)
        suggestions.append({
            "rule_id": rule_id,
            "variable": variable,
            "current": _get_var(state, variable) if variable else None,
            "proposed": proposed,
            "rationale": rationale,
            "card_id": card_for(rule_id, variable),
        })

    for violation in result.get("violations", []):
        if violation.get("severity") != "HARD":
            continue
        rid = violation["rule_id"]

        if rid == "SOLVER-001":
            # Kỳ dị số học (I ≤ 0, E ≤ 0) = lỗi dữ liệu catalog — không được
            # "sửa thiết kế" để né lỗi (xem KC-007).
            push(rid, None, None,
                 "Lỗi dữ liệu catalog (solver kỳ dị số học) — không đề xuất sửa"
                 " thiết kế, cần người duyệt kiểm tra catalogs.json.")

        elif rid in _STEP_MOVES:
            for name, delta, why in _STEP_MOVES[rid]:
                current = _get_var(state, name)
                proposed = _step_value(domains[name], current, delta)
                if proposed is None:
                    continue  # đã kịch trần/kịch sàn miền grammar
                if not _no_new_hard(state, name, proposed, base_rules):
                    continue  # nước sửa sinh vi phạm hình học mới → loại
                push(rid, name, proposed,
                     f"Vi phạm {rid}: {why} ({current} → {proposed}).")

        elif rid in ("GEOM-001", "GEOM-002"):
            # Quét girder_spacing_mm theo TỪNG hướng từ giá trị hiện tại —
            # đề xuất GIÁ TRỊ ĐẦU TIÊN làm hình học sạch hoàn toàn.
            grid = domains["girder_spacing_mm"]
            cur_s = dv["girder_spacing_mm"]
            sweeps = [
                ([v for v in grid if v < cur_s][::-1], "quét giảm dần"),
                ([v for v in grid if v > cur_s], "quét tăng dần"),
            ]
            for values, direction in sweeps:
                for val in values:
                    if _geom_clean(state, "girder_spacing_mm", val, base_rules):
                        push(rid, "girder_spacing_mm", val,
                             f"Vi phạm {rid}: đặt girder_spacing_mm = {val}"
                             f" — giá trị đầu tiên ({direction}) làm bố trí"
                             " hết vi phạm hình học.")
                        break
            # girder_count ±1 (nếu còn trong miền và hình học sạch hoàn toàn)
            cur_n = dv["girder_count"]
            for delta in (-1, +1):
                n_new = cur_n + delta
                if n_new not in domains["girder_count"]:
                    continue
                if _geom_clean(state, "girder_count", n_new, base_rules):
                    push(rid, "girder_count", n_new,
                         f"Vi phạm {rid}: đổi girder_count {cur_n} → {n_new}"
                         " để bố trí lại cánh hẫng/khe cánh dầm hợp lệ.")

        elif rid == "GEOM-003":
            # Bản mỏng: quét deck_slab_thickness_mm tăng dần, giá trị đầu tiên
            # làm hình học hết vi phạm.
            cur_t = dv["deck_slab_thickness_mm"]
            for val in [v for v in domains["deck_slab_thickness_mm"] if v > cur_t]:
                if _geom_clean(state, "deck_slab_thickness_mm", val, base_rules):
                    push(rid, "deck_slab_thickness_mm", val,
                         f"Vi phạm {rid}: tăng chiều dày bản {cur_t} → {val} mm"
                         " để đạt chiều dày tối thiểu theo nhịp bản.")
                    break

        elif rid == "CONS-001":
            # Nhịp 38.3 m: chỉ DG-5 thỏa khoảng cách dầm ngang ≤ 10 m (xem KC-004)
            cur_d = dv["diaphragm_layout_id"]
            if "DG-5" in domains["diaphragm_layout_id"] and cur_d != "DG-5":
                rules_after = _hard_geo_rules(_with_var(state, "diaphragm_layout_id", "DG-5"))
                if (rules_after is not None and base_rules is not None
                        and "CONS-001" not in rules_after and rules_after <= base_rules):
                    push(rid, "diaphragm_layout_id", "DG-5",
                         f"Vi phạm {rid}: đổi bố trí dầm ngang {cur_d} → DG-5"
                         " (5 hàng tại L/4) để khoảng cách ≤ 10 m.")

        # Rule khác (SCHEMA-*, CONS-002, ...) — chưa có nước sửa tự động

        if len(suggestions) >= top_k:
            break

    return suggestions[:top_k]
