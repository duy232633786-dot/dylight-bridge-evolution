"""Kiểm chứng section calculator tham số hóa (bridge_evolution/section.py).

Ba lớp kiểm tra:
  1. TOÁN HỌC — định lý Green phải khớp công thức giải tích tới sai số máy.
  2. HÌNH HỌC — biên dựng ra phải đơn, đúng chiều, đơn điệu theo tham số, và
     từ chối tham số phi vật lý.
  3. CHẾ TẠO — mỗi rule FAB-00x đều có case kích hoạt và case sạch.
"""
import math

import pytest

from bridge_evolution.catalogs import load_catalogs
from bridge_evolution.section import (
    FAB_DEFAULTS,
    FLANGE_OVERHANG_MM,
    SectionGeometryError,
    build_section_polygon,
    fabrication_violations,
    polygon_properties,
    section_from_params,
)

# Bộ tham số neo, tái tạo GẦN ĐÚNG ST-1750 (xem test_anchor_against_catalog_ST1750).
ANCHOR = {
    "girder_depth_mm": 1750,
    "top_flange_width_mm": 2060,
    "top_flange_thickness_mm": 120,
    "web_thickness_mm": 110,
    "bottom_bulb_width_mm": 260,
    "bottom_bulb_height_mm": 400,
}

# Bộ tham số SẠCH mọi rule chế tạo — mốc so sánh cho test_fabrication_rules_fire.
FAB_BASE = {
    "girder_depth_mm": 1750,
    "top_flange_width_mm": 2060,
    "top_flange_thickness_mm": 120,
    "web_thickness_mm": 110,
    "bottom_bulb_width_mm": 400,
    "bottom_bulb_height_mm": 250,
}
FAB_CONTEXT = {"span_m": 38.3, "strand_count": 34, "girder_concrete_fc_MPa": 45}


def with_params(**overrides) -> dict:
    p = dict(FAB_BASE)
    p.update(overrides)
    return p


def with_context(**overrides) -> dict:
    c = dict(FAB_CONTEXT)
    c.update(overrides)
    return c


def rule_ids(violations) -> set:
    return {v["rule_id"] for v in violations}


def by_id(violations, rule_id) -> dict:
    return next(v for v in violations if v["rule_id"] == rule_id)


# ------------------------------------------------------------------ 1. toán học
def test_green_theorem_on_rectangle():
    """Chữ nhật b×h: A=b·h, ȳ=h/2, I=b·h³/12 — sai số phải ở mức máy."""
    b, h = 2.0, 3.0
    rect = [(0.0, 0.0), (b, 0.0), (b, h), (0.0, h)]  # ngược chiều kim đồng hồ
    props = polygon_properties(rect)

    assert abs(props["area_m2"] - b * h) < 1e-9
    assert abs(props["centroid_y_m"] - h / 2.0) < 1e-9
    assert abs(props["I_m4"] - b * h**3 / 12.0) < 1e-9
    assert abs(props["perimeter_m"] - 2.0 * (b + h)) < 1e-9


def test_green_theorem_on_composite():
    """Chữ T ghép từ 2 chữ nhật — so với công thức tổ hợp (trục song song) tính tay."""
    stem_b, stem_h = 0.20, 1.00      # sườn đứng, y ∈ [0, 1.0]
    fl_b, fl_t = 1.00, 0.20          # cánh ngang, y ∈ [1.0, 1.2]
    tee = [
        (-stem_b / 2, 0.0), (stem_b / 2, 0.0), (stem_b / 2, stem_h),
        (fl_b / 2, stem_h), (fl_b / 2, stem_h + fl_t),
        (-fl_b / 2, stem_h + fl_t), (-fl_b / 2, stem_h), (-stem_b / 2, stem_h),
    ]

    a_stem, y_stem = stem_b * stem_h, stem_h / 2.0
    a_fl, y_fl = fl_b * fl_t, stem_h + fl_t / 2.0
    area = a_stem + a_fl
    centroid = (a_stem * y_stem + a_fl * y_fl) / area
    inertia = (stem_b * stem_h**3 / 12.0 + a_stem * (y_stem - centroid) ** 2
               + fl_b * fl_t**3 / 12.0 + a_fl * (y_fl - centroid) ** 2)

    props = polygon_properties(tee)
    assert abs(props["area_m2"] - area) / area < 1e-9
    assert abs(props["centroid_y_m"] - centroid) / centroid < 1e-9
    assert abs(props["I_m4"] - inertia) / inertia < 1e-9


def test_polygon_properties_rejects_degenerate_input():
    with pytest.raises(SectionGeometryError):
        polygon_properties([(0.0, 0.0), (1.0, 0.0)])
    with pytest.raises(SectionGeometryError):
        polygon_properties([(0.0, 0.0), (1.0, 0.0), (2.0, 0.0)])  # thẳng hàng, A≈0


# ------------------------------------------------------------------ 2. hình học
def test_polygon_orientation_and_closure():
    """Đa giác đơn: Green cho diện tích DƯƠNG (ngược chiều kim đồng hồ), đủ đỉnh."""
    ring = build_section_polygon(ANCHOR)

    assert len(ring) >= 8
    assert polygon_properties(ring)["area_m2"] > 0.0

    # Vòng đóng ngầm: đỉnh đầu không lặp ở cuối, không có cạnh dài 0.
    assert ring[0] != ring[-1]
    for (x0, y0), (x1, y1) in zip(ring, ring[1:] + ring[:1]):
        assert math.hypot(x1 - x0, y1 - y0) > 0.0

    # Đối xứng qua tim: tập đỉnh phải bất biến khi lật x → -x.
    mirrored = {(round(-x, 9), round(y, 9)) for x, y in ring}
    assert mirrored == {(round(x, 9), round(y, 9)) for x, y in ring}

    # Hở đáy: không có đỉnh nào tại tim ở cao độ đáy (không có bản đáy).
    assert all(not (abs(x) < 1e-9 and abs(y) < 1e-9) for x, y in ring)


def test_polygon_matches_hand_component_sum():
    """Diện tích Green = cánh trên + 2 sườn + 2 bầu (kiểm tra cách dựng biên)."""
    p = ANCHOR
    H, bf = p["girder_depth_mm"], p["top_flange_width_mm"]
    tf, tw = p["top_flange_thickness_mm"], p["web_thickness_mm"]
    bb, hb = p["bottom_bulb_width_mm"], p["bottom_bulb_height_mm"]
    hand_mm2 = bf * tf + 2 * tw * (H - tf - hb) + 2 * bb * hb

    area = polygon_properties(build_section_polygon(p))["area_m2"]
    assert abs(area - hand_mm2 * 1e-6) < 1e-9


def test_section_from_params_contract_keys():
    """Trả về ĐÚNG bộ khóa catalog girder_sections đang dùng + phần mở rộng."""
    sec = section_from_params(ANCHOR)
    assert set(sec) == {
        "depth_m", "area_m2", "I_m4", "y_bottom_m", "top_flange_width_m",
        "web_width_total_m", "perimeter_m", "source",
    }
    catalog_keys = set(load_catalogs()["girder_sections"]["ST-1750"])
    assert catalog_keys <= set(sec)

    assert sec["source"] == "PARAMETRIC"
    assert abs(sec["depth_m"] - 1.750) < 1e-12
    assert abs(sec["top_flange_width_m"] - 2.060) < 1e-12
    assert abs(sec["web_width_total_m"] - 2 * 110 / 1000.0) < 1e-12
    assert 0.0 < sec["y_bottom_m"] < sec["depth_m"]
    assert sec["perimeter_m"] > 0.0


def test_anchor_against_catalog_ST1750():
    """NEO BẬC-ĐỘ-LỚN với ST-1750, KHÔNG phải kiểm chứng chính xác.

    Catalog hiện là PLACEHOLDER (catalogs.json ghi rõ điều này), còn mô hình ở
    section.py là biên gần đúng: bỏ vút, bỏ bo góc, sườn dày đều theo phương
    ngang. Vì vậy chỉ yêu cầu cùng bậc độ lớn — sai số tương đối < 35% cho từng
    đại lượng — đủ để phát hiện sai đơn vị, sai định lý Green hay sai cách dựng
    biên, mà không khóa cứng vào các con số placeholder.

    Lưu ý về bộ tham số: bb ở đây là bề rộng MỘT bầu đo từ mép ngoài sườn vào
    trong. Do mô hình ràng buộc "bầu bulge vào trong đúng bằng lượng sườn vát ra
    ngoài", với bf=2060 mm thì bb bị chặn ≈ 420 mm; bề rộng đáy dầm thực tế là
    2·x_bulb_out, không phải 2·bb.
    """
    cat = load_catalogs()["girder_sections"]["ST-1750"]
    sec = section_from_params(ANCHOR)

    for key in ("area_m2", "I_m4", "y_bottom_m"):
        rel = abs(sec[key] - cat[key]) / cat[key]
        assert rel < 0.35, f"{key}: {sec[key]:.4f} lệch {rel:.1%} so với catalog {cat[key]}"

    assert sec["depth_m"] == cat["depth_m"]
    assert sec["top_flange_width_m"] == cat["top_flange_width_m"]


def test_monotonic_depth():
    """Tăng H (giữ nguyên biến khác) ⇒ I_m4 tăng đơn điệu ngặt."""
    inertias = []
    for depth in range(1500, 2101, 50):
        params = dict(ANCHOR, girder_depth_mm=depth)
        inertias.append(section_from_params(params)["I_m4"])

    assert all(b > a for a, b in zip(inertias, inertias[1:])), inertias


def test_flange_overhang_constant_drives_web_position():
    """Mép ngoài sườn tại đáy cánh = bf/2 - FLANGE_OVERHANG_MM (hằng số module)."""
    ring = build_section_polygon(ANCHOR)
    y_web_top = (ANCHOR["girder_depth_mm"] - ANCHOR["top_flange_thickness_mm"]) / 1000.0
    xs = [x for x, y in ring if abs(y - y_web_top) < 1e-12 and x > 0]
    expected = (ANCHOR["top_flange_width_mm"] / 2.0 - FLANGE_OVERHANG_MM) / 1000.0
    assert any(abs(x - expected) < 1e-12 for x in xs)


def test_degenerate_bulb_keeps_polygon_simple():
    """bb == tw: bầu suy biến thành chân sườn — biên vẫn đơn, không cạnh dài 0."""
    params = dict(ANCHOR, bottom_bulb_width_mm=ANCHOR["web_thickness_mm"])
    ring = build_section_polygon(params)
    assert len(ring) >= 8
    assert polygon_properties(ring)["area_m2"] > 0.0
    for (x0, y0), (x1, y1) in zip(ring, ring[1:] + ring[:1]):
        assert math.hypot(x1 - x0, y1 - y0) > 0.0


@pytest.mark.parametrize("overrides, reason", [
    ({"girder_depth_mm": 0}, "chiều cao ≤ 0"),
    ({"web_thickness_mm": -110}, "sườn dày âm"),
    ({"bottom_bulb_height_mm": 0}, "bầu cao 0"),
    ({"top_flange_thickness_mm": 1750}, "cánh dày ≥ H"),
    ({"top_flange_thickness_mm": 1400, "bottom_bulb_height_mm": 400}, "hb ≥ H - tf"),
    ({"top_flange_width_mm": 500}, "cánh hẹp hơn sườn ⇒ hai sườn giao nhau"),
    ({"bottom_bulb_width_mm": 50}, "bầu hẹp hơn sườn"),
    ({"bottom_bulb_width_mm": 700}, "bầu chồng lấn qua tim"),
    ({"girder_depth_mm": "1750"}, "tham số không phải số"),
    ({"web_thickness_mm": True}, "bool không phải kích thước"),
    ({"top_flange_width_mm": float("nan")}, "giá trị không hữu hạn"),
])
def test_invalid_params_raise(overrides, reason):
    params = dict(ANCHOR)
    params.update(overrides)
    with pytest.raises(SectionGeometryError):
        build_section_polygon(params)
    with pytest.raises(SectionGeometryError):
        section_from_params(params)


def test_missing_param_key_raises():
    params = dict(ANCHOR)
    del params["bottom_bulb_height_mm"]
    with pytest.raises(SectionGeometryError):
        build_section_polygon(params)


# ------------------------------------------------------------------ 3. chế tạo
def test_fab_base_is_clean():
    """Mốc so sánh: bộ tham số nền không vi phạm bất kỳ rule chế tạo nào."""
    assert fabrication_violations(FAB_BASE, FAB_CONTEXT) == []


# (rule_id, severity, ghi đè tham số, ghi đè context)
FAB_CASES = [
    ("FAB-001", "HARD", {"web_thickness_mm": 80}, {}),
    ("FAB-002", "HARD", {"top_flange_thickness_mm": 70}, {}),
    ("FAB-003", "HARD", {}, {"strand_count": 54}),
    ("FAB-004", "HARD", {"top_flange_thickness_mm": 250}, {}),
    ("FAB-005", "HARD", {"girder_depth_mm": 2400},
     {"fab_limits": {"lift_capacity_t": 200.0}}),
    ("FAB-006", "HARD", {"bottom_bulb_width_mm": 110}, {}),
    ("FAB-007", "SOFT", {"girder_depth_mm": 1200}, {}),
]


@pytest.mark.parametrize("rule_id, severity, param_over, ctx_over", FAB_CASES)
def test_fabrication_rules_fire(rule_id, severity, param_over, ctx_over):
    """Mỗi rule có 1 case KÍCH HOẠT (margin > 0) và 1 case SẠCH (FAB_BASE)."""
    dirty = fabrication_violations(with_params(**param_over), with_context(**ctx_over))
    assert rule_id in rule_ids(dirty)

    v = by_id(dirty, rule_id)
    assert set(v) == {"rule_id", "severity", "message", "margin"}
    assert v["severity"] == severity
    assert v["margin"] > 0.0
    assert isinstance(v["message"], str) and v["message"]

    # case sạch: chính rule đó KHÔNG kích hoạt trên bộ tham số nền
    assert rule_id not in rule_ids(fabrication_violations(FAB_BASE, FAB_CONTEXT))


def test_fab007_fires_on_both_ends_and_is_soft():
    """FAB-007 là SOFT và bắt cả hai đầu dải [17, 26]."""
    slender = fabrication_violations(with_params(girder_depth_mm=1200), FAB_CONTEXT)
    assert by_id(slender, "FAB-007")["severity"] == "SOFT"

    stocky = fabrication_violations(
        with_params(girder_depth_mm=2400),
        with_context(fab_limits={"lift_capacity_t": 200.0, "transport_height_mm": 3000.0}),
    )
    assert by_id(stocky, "FAB-007")["severity"] == "SOFT"
    assert rule_ids(stocky) == {"FAB-007"}


def test_fab006_vertical_web_is_violation():
    """Sườn thẳng đứng hoàn toàn (bb == tw) ⇒ không rút được ván khuôn."""
    v = by_id(fabrication_violations(with_params(bottom_bulb_width_mm=110), FAB_CONTEXT),
              "FAB-006")
    assert v["margin"] >= 1.0  # draft = 0 ⇒ margin = (min - 0)/min = 1


def test_fab_limits_override_beats_defaults():
    """Ngưỡng lấy từ context['fab_limits']; khóa thiếu rơi về FAB_DEFAULTS."""
    assert fabrication_violations(FAB_BASE, FAB_CONTEXT) == []

    strict = fabrication_violations(
        FAB_BASE, with_context(fab_limits={"lift_capacity_t": 50.0}))
    assert "FAB-004" in rule_ids(strict)

    loose = fabrication_violations(
        with_params(web_thickness_mm=80),
        with_context(fab_limits={"web_thickness_min_mm": 70.0}))
    assert "FAB-001" not in rule_ids(loose)

    # Ghi đè một khóa không làm mất các default còn lại.
    assert FAB_DEFAULTS["web_thickness_min_mm"] == 100.0


def test_fab_missing_context_keys():
    """Context thiếu khóa ⇒ không crash, chỉ BỎ QUA rule cần khóa đó."""
    # Không có context: chỉ còn các rule thuần tham số.
    assert fabrication_violations(FAB_BASE) == []
    assert fabrication_violations(FAB_BASE, {}) == []
    assert fabrication_violations(FAB_BASE, None) == []

    # Thiếu strand_count ⇒ FAB-003 bị bỏ qua dù bầu quá nhỏ để chứa cáp.
    tiny_bulb = with_params(bottom_bulb_width_mm=150, bottom_bulb_height_mm=150)
    assert "FAB-003" not in rule_ids(fabrication_violations(tiny_bulb, {"span_m": 38.3}))
    assert "FAB-003" in rule_ids(
        fabrication_violations(tiny_bulb, {"span_m": 38.3, "strand_count": 34}))

    # Thiếu span_m ⇒ FAB-004 và FAB-007 bị bỏ qua, các rule khác vẫn chạy.
    heavy_short = with_params(top_flange_thickness_mm=250, girder_depth_mm=1200)
    no_span = rule_ids(fabrication_violations(heavy_short, {"strand_count": 34}))
    assert "FAB-004" not in no_span and "FAB-007" not in no_span

    with_span = rule_ids(fabrication_violations(
        heavy_short, {"strand_count": 34, "span_m": 38.3}))
    assert {"FAB-004", "FAB-007"} <= with_span

    # Khóa lạ trong context không gây lỗi.
    assert fabrication_violations(FAB_BASE, {"unknown_key": 1, "fab_limits": {}}) == []


def test_fabrication_rejects_unbuildable_params():
    """Fail-closed: không kết luận 'chế tạo được' cho biên không dựng nổi."""
    with pytest.raises(SectionGeometryError):
        fabrication_violations(with_params(bottom_bulb_width_mm=700), FAB_CONTEXT)
