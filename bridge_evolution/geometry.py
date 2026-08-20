"""L0 — kiểm tra hình học/bố trí. Loại phương án vô lý TRƯỚC khi mở solver.

Hai nguồn tiết diện cùng tồn tại và cùng một contract khóa:
  * CATALOG    — ``girder_catalog_id`` tra ``catalogs["girder_sections"]`` (grammar v1).
  * PARAMETRIC — ``girder_catalog_id == "ST-PARAM"``: đặc trưng tiết diện được TÍNH
    từ 6 biến hình dạng trong ``design_variables`` qua ``section.section_from_params``
    (grammar v2). Entry ST-PARAM trong catalog chỉ là MARKER, không chứa số liệu.

Phần còn lại của pipeline (fe_adapter/objectives/verifier) đọc ``geom["section"]``
nên không cần biết tiết diện đến từ đâu; ``geom["section_source"]`` cho biết.

Toàn bộ module vẫn ở cấp L0 (rẻ, không mở solver): ``section_from_params`` và
``fabrication_violations`` là thuần toán.
"""
from .catalogs import load_catalogs, load_grammar, all_domains
from .section import (PARAM_KEYS, SectionGeometryError, fabrication_violations,
                      section_from_params)

#: Marker catalog báo "tiết diện được tham số hóa, đừng tra bảng".
PARAMETRIC_SECTION_ID = "ST-PARAM"

#: Ánh xạ tên khóa trong ``rule_profiles[...]["fab_limits"]`` (tên CATALOG) sang
#: tên tham số của ``section.FAB_DEFAULTS``. Khóa lạ trong catalog bị bỏ qua để
#: một ghi chú/khóa mở rộng không lặng lẽ trở thành ngưỡng chế tạo.
_FAB_LIMIT_KEY_MAP = {
    "web_thickness_min_mm": "web_thickness_min_mm",
    "top_flange_thickness_min_mm": "top_flange_thickness_min_mm",
    "strand_cell_mm": "strand_grid_pitch_mm",
    "cover_mm": "strand_cover_mm",
    "lift_capacity_t": "lift_capacity_t",
    "concrete_density_t_per_m3": "concrete_density_t_per_m3",
    "transport_height_mm": "transport_height_mm",
    "min_draft_ratio": "min_draft_ratio",
    "span_depth_ratio_min": "span_depth_ratio_min",
    "span_depth_ratio_max": "span_depth_ratio_max",
}


def is_parametric_section(state: dict) -> bool:
    """State có dùng tiết diện tham số hóa hay không (rẻ, không dựng biên)."""
    return state["design_variables"].get("girder_catalog_id") == PARAMETRIC_SECTION_ID


def section_params(state: dict) -> dict:
    """6 tham số hình dạng lấy từ ``design_variables``.

    Khóa thiếu KHÔNG được bịa giá trị mặc định: dict trả về chỉ chứa khóa thật sự
    có trong state, để ``section_from_params`` báo đúng khóa nào thiếu bằng
    ``SectionGeometryError`` (fail-closed).
    """
    dv = state["design_variables"]
    return {name: dv[name] for name in PARAM_KEYS if name in dv}


def _deck_layout(state: dict) -> dict:
    """Phần hình học KHÔNG phụ thuộc tiết diện.

    Tách riêng để ``check_geometry`` vẫn kiểm được bố trí mặt cắt ngang ngay cả
    khi bộ tham số hình dạng phi vật lý (không dựng nổi biên).
    """
    dv = state["design_variables"]
    pi = state["project_inputs"]
    n = dv["girder_count"]
    S = dv["girder_spacing_mm"] / 1000.0
    B = pi["deck_width_m"]
    return {
        "span_m": pi["span_length_m"],
        "deck_width_m": B,
        "girder_count": n,
        "spacing_m": S,
        "slab_thickness_m": dv["deck_slab_thickness_mm"] / 1000.0,
        "overhang_m": (B - (n - 1) * S) / 2.0,
    }


def resolve_section(state: dict) -> tuple[dict, str]:
    """(đặc trưng tiết diện, nguồn) — ``"PARAMETRIC"`` hoặc ``"CATALOG"``.

    Raise ``SectionGeometryError`` khi tham số hình dạng phi vật lý và ``KeyError``
    khi id catalog không tồn tại (evaluate biến KeyError thành SCHEMA-002).
    """
    if is_parametric_section(state):
        return section_from_params(section_params(state)), "PARAMETRIC"
    cat = load_catalogs()
    return cat["girder_sections"][state["design_variables"]["girder_catalog_id"]], "CATALOG"


def derive_geometry(state: dict) -> dict:
    """Các đại lượng hình học dẫn xuất từ state (nguồn duy nhất cho solver + verifier)."""
    geom = _deck_layout(state)
    sec, source = resolve_section(state)
    geom["flange_gap_m"] = geom["spacing_m"] - sec["top_flange_width_m"]
    geom["section"] = sec
    geom["section_source"] = source
    return geom


def _fabrication_context(state: dict, geom: dict, cat: dict, rules: dict) -> dict:
    """Bối cảnh cho ``fabrication_violations``: nhịp, số tao cáp, ngưỡng xưởng.

    Khóa nào không tra được thì KHÔNG đưa vào context — section.py sẽ bỏ qua đúng
    rule cần khóa đó thay vì kiểm bằng một giá trị bịa.
    """
    dv = state["design_variables"]
    context: dict = {"span_m": geom["span_m"]}

    pt = cat["prestress_layouts"].get(dv["prestress_layout_id"])
    if isinstance(pt, dict) and "strand_count" in pt:
        context["strand_count"] = pt["strand_count"]

    conc = cat["concretes"].get(state["materials"]["girder_concrete_id"])
    if isinstance(conc, dict) and "fc_MPa" in conc:
        context["girder_concrete_fc_MPa"] = conc["fc_MPa"]

    profile_limits = rules.get("fab_limits") or {}
    limits = {param: profile_limits[cat_key]
              for cat_key, param in _FAB_LIMIT_KEY_MAP.items() if cat_key in profile_limits}
    if limits:
        context["fab_limits"] = limits
    return context


def check_geometry(state: dict) -> tuple[list[dict], dict]:
    """Trả về (violations L0, geometry).

    Mọi violation ở đây là HARD trừ FAB-007 (SOFT, tỷ lệ nhịp/chiều cao).
    KHÔNG bao giờ raise vì tham số hình dạng: bộ tham số phi vật lý trở thành
    violation HARD ``FAB-000`` để EA/RL loại phương án ở L0 mà không tốn ngân sách.
    """
    cat = load_catalogs()
    rules = cat["rule_profiles"][state["constraints"]["rule_profile_id"]]
    v = []

    def fail(rule_id, msg, margin):
        v.append({"rule_id": rule_id, "severity": "HARD", "message": msg,
                  "margin": round(float(margin), 4)})

    try:
        geom = derive_geometry(state)
    except SectionGeometryError as exc:
        # Biên không dựng được ⇒ không có tiết diện để kiểm GEOM-002 và không có
        # gì để đưa vào solver. Các kiểm tra bố trí còn lại vẫn chạy để agent
        # nhận đủ tín hiệu sửa trong một lần.
        geom = _deck_layout(state)
        geom["flange_gap_m"] = None
        geom["section"] = None
        geom["section_source"] = "PARAMETRIC_INVALID"
        fail("FAB-000", f"Tham số mặt cắt phi vật lý: {exc}", 1.0)

    # GEOM-001: bố trí nằm gọn trong bề rộng cầu, cánh hẫng trong giới hạn
    oh, S = geom["overhang_m"], geom["spacing_m"]
    oh_max = min(rules["overhang_max_m"], rules["overhang_max_spacing_ratio"] * S)
    if oh < rules["overhang_min_m"]:
        fail("GEOM-001", f"Cánh hẫng {oh:.3f} m < tối thiểu {rules['overhang_min_m']} m",
             (rules["overhang_min_m"] - oh) / rules["overhang_min_m"])
    elif oh > oh_max:
        fail("GEOM-001", f"Cánh hẫng {oh:.3f} m > tối đa {oh_max:.3f} m", (oh - oh_max) / oh_max)

    # GEOM-002: khe hở cánh dầm liền kề (bỏ qua khi chưa có tiết diện)
    gap = geom["flange_gap_m"]
    if gap is not None and gap < rules["flange_gap_min_m"]:
        fail("GEOM-002",
             f"Khe hở cánh dầm {gap * 1000:.0f} mm < {rules['flange_gap_min_m'] * 1000:.0f} mm",
             (rules["flange_gap_min_m"] - gap) / rules["flange_gap_min_m"])

    # GEOM-003: chiều dày bản tối thiểu (theo nhịp bản = khoảng cách dầm)
    ts_req = max(rules["slab_thickness_min_m"], (S * 1000 + 3000) / 30 / 1000)
    if geom["slab_thickness_m"] < ts_req - 1e-9:
        fail("GEOM-003",
             f"Bản dày {geom['slab_thickness_m'] * 1000:.0f} mm < yêu cầu {ts_req * 1000:.0f} mm",
             (ts_req - geom["slab_thickness_m"]) / ts_req)

    # CONS-001: số hàng dầm ngang theo nhịp
    dia = cat["diaphragm_layouts"][state["design_variables"]["diaphragm_layout_id"]]
    L = geom["span_m"]
    if L > 30.0:
        min_rows = rules["diaphragm_min_rows_span_over_30m"]
        max_gap = max((b - a) * L for a, b in zip(dia["positions_ratio"], dia["positions_ratio"][1:]))
        if dia["rows"] < min_rows:
            fail("CONS-001", f"{dia['rows']} hàng dầm ngang < tối thiểu {min_rows} (L={L} m)",
                 (min_rows - dia["rows"]) / min_rows)
        elif max_gap > rules["diaphragm_max_spacing_m"]:
            fail("CONS-001",
                 f"Khoảng cách dầm ngang {max_gap:.1f} m > {rules['diaphragm_max_spacing_m']} m",
                 (max_gap - rules["diaphragm_max_spacing_m"]) / rules["diaphragm_max_spacing_m"])

    # CONS-002: biến số học phải nằm đúng lưới grammar (chuẩn hóa mô-đun).
    # Biến kiểu catalog không kiểm ở đây: id lạ sẽ nổ KeyError → SCHEMA_INVALID ở evaluate;
    # entry test-only (ST-TEST-SINGULAR) được phép đi tới solver để test đường NOT_CONVERGED.
    grammar = load_grammar(state["family"])
    domains = all_domains(grammar)
    for name, spec in grammar["design_variables"].items():
        if spec["type"] in ("int", "grid"):
            value = state["design_variables"].get(name)
            if value not in domains[name]:
                fail("CONS-002", f"{name}={value} nằm ngoài lưới grammar", 1.0)

    # FAB-001…FAB-007: chế tạo / vận chuyển / cẩu lắp / bố trí cáp.
    # Chỉ áp cho tiết diện tham số hóa — tiết diện định hình đã được nhà sản xuất
    # bảo chứng nên grammar v1 không đổi hành vi.
    if geom["section_source"] == "PARAMETRIC":
        try:
            v.extend(fabrication_violations(
                section_params(state), _fabrication_context(state, geom, cat, rules)))
        except SectionGeometryError as exc:  # fail-closed, không thể lọt ra ngoài
            fail("FAB-000", f"Tham số mặt cắt phi vật lý: {exc}", 1.0)

    return v, geom
