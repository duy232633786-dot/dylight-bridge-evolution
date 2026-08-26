"""Section builders cho các họ dầm NGOÀI Super-T (BRD-025).

Cùng contract khóa với ``section.section_from_params`` — mọi pipeline downstream
(geometry/fe_adapter/objectives/verifier) đọc đúng bộ khóa này:

    depth_m, area_m2, I_m4, y_bottom_m, top_flange_width_m,
    web_width_total_m (+ perimeter_m, source)

Ba họ mới, theo mức hỗ trợ THẬT của runtime:

=========================  ======  ===========================================
Họ                         Marker  Mức hỗ trợ
=========================  ======  ===========================================
I-girder BTCT DUL          I-PARAM L0 + L1 (cùng vật lý Super-T: dầm chiết
                                   úp, DUL, bản liên hợp qua solver)
Hộp đơn ô BTCT             BOX-PARAM L0 + L1 screening: section là MÁNG
                                   CHỮ U (đáy + 2 sườn đứng), bản trên nạp
                                   qua đường composite sẵn có của solver;
                                   bỏ qua uốn xoắn (L1 line-girder không
                                   mô hình xoắn — ghi rõ ở grammar)
Composite thép I + bản BT  CI-PARAM CHỈ L0: chặn HARD SOLVER-COMPOSITE-001
                                   trước solver vì mô hình sức kháng L1
                                   (khối nén bê tông + tao DUL dính bám)
                                   KHÔNG hợp lệ cho dầm thép. Không bao giờ
                                   sinh số liệu sức kháng giả
=========================  ======  ===========================================

Đơn vị tham số: mm (khớp grammar JSON). Đa giác: mét, ngược chiều kim đồng hồ,
concrete nằm bên TRÁI hướng đi — cùng quy ước ``section.build_section_polygon``.

NGUỒN NGƯỠNG FAB (sàng lọc, dẫn nguồn):
  * Toán học tiết diện: định lý Green cho đa giác (chuẩn số học; cùng thuật
    toán đã đối chứng trong section.polygon_properties).
  * I-girder DUL — dải L/H 17–26 và ngưỡng chế tạo dầm chiết úp: TCVN
    11823-1:2018 / AASHTO LRFD BDS §8.11 (precast beams, dải tỷ lệ thông
    dụng); dày sườn tối thiểu đổ xưởng 160 mm (AASHTO BDS §5.14.1.2 /
    TCVN 11823-1 mức cấu tạo đổ đầm trong xưởng).
  * Hộp đơn ô CIP — dải L/H 14–25, dày sườn ≥ 350 mm (cáp trong sườn),
    bản trên ≥ 220 mm, bản đáy ≥ 180 mm: TCVN 11823-1 / AASHTO BDS §8.14
    (cast-in-place box), mức cấu tạo phổ biến trong hồ sơ thiết kế cầu
    hộp đơn ô nhịp 30–70 m.
  * Composite thép — slenderness lớp 1: EN 1993-1-1 Table 5.2 (c/tw ≤ 72ε
    web trong tiết diện nén uốn; mức sàng lọc dùng hs/tw ≤ 110 cho dầm có
    gá ổn định, (bf/2)/tf ≤ 14·ε ≈ 11 với S355 — chọn 14 bảo thủ cho
    S235); dải L/H 20–30: AASHTO LRFD BDS §6.10 (I-section composite).
  Mọi ngưỡng là MỨC SÀNG LỌC có dẫn nguồn — không thay thế kiểm tra chi
  tiết theo mã thiết kế thật của dự án (G0 design basis).
"""
from __future__ import annotations

import math

from .section import SectionGeometryError, polygon_properties

__all__ = [
    "I_GIRDER_PARAM_KEYS",
    "BOX_GIRDER_PARAM_KEYS",
    "COMPOSITE_I_PARAM_KEYS",
    "SECTION_FAB_DEFAULTS",
    "i_girder_section_from_params",
    "box_girder_section_from_params",
    "composite_i_girder_section_from_params",
    "fabrication_violations_i_girder",
    "fabrication_violations_box_girder",
    "fabrication_violations_composite_i",
    "composite_solver_gate",
]

_EPS = 1e-12

I_GIRDER_PARAM_KEYS = (
    "girder_depth_mm",            # H    — chiều cao toàn tiết diện dầm
    "top_flange_width_mm",        # bf   — bề rộng cánh trên
    "top_flange_thickness_mm",    # tf   — dày cánh trên
    "web_thickness_mm",           # tw   — dày sườn (một sườn giữa)
    "bottom_flange_width_mm",     # bfb  — bề rộng cánh dưới
    "bottom_flange_thickness_mm", # tfb  — dày cánh dưới
)

BOX_GIRDER_PARAM_KEYS = (
    "box_web_height_mm",          # H    — cao từ ĐÁY hộp đến đỉnh sườn (chưa gồm bản trên)
    "box_bottom_width_mm",        # Bb   — bề rộng đáy hộp (mép ngoài)
    "box_bottom_slab_mm",         # tsb  — dày bản đáy
    "box_web_thickness_mm",       # tw   — dày MỖI sườn (2 sườn đứng)

)

COMPOSITE_I_PARAM_KEYS = (
    "steel_depth_mm",             # hs   — cao thép I
    "steel_top_flange_width_mm",  # bft
    "steel_top_flange_thickness_mm",  # tft
    "steel_web_thickness_mm",     # tw
    "steel_bottom_flange_width_mm",   # bfb
    "steel_bottom_flange_thickness_mm",  # tfb
)

#: Ngưỡng chế tạo riêng cho các họ mới. Cùng ngữ nghĩa khóa với
#: ``section.FAB_DEFAULTS`` để rule profile V2 ghi đè đồng nhất; thêm khóa
#: riêng của hộp (dày bản đáy) và thép (slenderness).
SECTION_FAB_DEFAULTS = {
    "web_thickness_min_mm": 160.0,          # FAB-001 (I DUL đổ xưởng)
    "box_web_thickness_min_mm": 350.0,      # FAB-001 (hộp CIP có cáp trong sườn)
    "top_flange_thickness_min_mm": 150.0,   # FAB-002 (I DUL)
    "box_top_slab_min_mm": 220.0,           # FAB-002 (bản trên hộp chịu bánh xe)
    "box_bottom_slab_min_mm": 180.0,        # FAB-002b
    "strand_grid_pitch_mm": 50.0,           # FAB-003
    "strand_cover_mm": 50.0,                # FAB-003
    "lift_capacity_t": 80.0,                # FAB-004
    "concrete_density_t_per_m3": 2.5,       # FAB-004
    "transport_height_mm": 2200.0,          # FAB-005 (chỉ I DUL chiết úp)
    "span_depth_ratio_min": 17.0,           # FAB-007
    "span_depth_ratio_max": 26.0,           # FAB-007
    "box_span_depth_ratio_min": 14.0,       # FAB-007 (hộp CIP hiệu quả hơn ở nhịp lớn)
    "box_span_depth_ratio_max": 25.0,
    "steel_web_slenderness_max": 110.0,     # FAB-001 (thép: hs/tw, lớp hầm bò lớp 1)
    "steel_flange_slenderness_max": 14.0,   # FAB-002 (thép: bf/2tf, lớp 1 nén)
    "composite_span_depth_ratio_min": 20.0, # FAB-007
    "composite_span_depth_ratio_max": 30.0,
}


def _positive(params: dict, key: str) -> float:
    value = params.get(key)
    if not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0:
        raise SectionGeometryError(f"{key} phải là số dương, nhận {value!r}")
    return float(value)


def _violation(rule_id: str, message: str, margin: float,
               severity: str = "HARD") -> dict:
    return {"rule_id": rule_id, "severity": severity,
            "message": message, "margin": round(float(margin), 4)}


def _strand_capacity(width_mm: float, height_mm: float,
                     pitch: float, cover: float) -> int:
    """Số tao bố trí được trong 1 vùng chữ nhật theo lưới ô vuông (2·cover lùi biên)."""
    usable_w = width_mm - 2.0 * cover
    usable_h = height_mm - 2.0 * cover
    if pitch <= 0 or usable_w < pitch or usable_h < pitch:
        return 0
    return int(usable_w // pitch) * int(usable_h // pitch)


# ===================================================================
# I-girder BTCT DUL
# ===================================================================
def _i_girder_ring(params: dict) -> list[tuple[float, float]]:
    H = _positive(params, "girder_depth_mm")
    bf = _positive(params, "top_flange_width_mm")
    tf = _positive(params, "top_flange_thickness_mm")
    tw = _positive(params, "web_thickness_mm")
    bfb = _positive(params, "bottom_flange_width_mm")
    tfb = _positive(params, "bottom_flange_thickness_mm")

    if tf + tfb >= H:
        raise SectionGeometryError(
            f"tf+tfb ({tf:.0f}) >= H ({H:.0f}) — không còn bề cao sườn")
    if bf <= tw or bfb <= tw:
        raise SectionGeometryError(
            f"Cánh phải rộng hơn sườn: bf={bf:.0f}, bfb={bfb:.0f}, tw={tw:.0f}")
    if bf <= bfb and bf - bfb < 2 * (tw/2 + 50):
        raise SectionGeometryError(
            "Cánh trên phải rộng hơn cánh dưới đủ bề rộng chuyển tiếp sườn")

    # CCW: đáy trái→phải, lên sườn phải, cánh trên phải→trái, xuống sườn trái.
    # Đơn vị mm, đổi sang m ở cuối.
    ring_mm = [
        (-bfb / 2, 0.0),        # đáy cánh dưới, trái → phải
        (bfb / 2, 0.0),
        (bfb / 2, tfb),         # đỉnh cánh dưới phải
        (tw / 2, tfb),          # vào sườn phải
        (tw / 2, H - tf),       # đỉnh sườn phải
        (bf / 2, H - tf),       # đáy cánh trên phải
        (bf / 2, H),            # đỉnh mép cánh phải
        (-bf / 2, H),           # mặt trên cánh, phải → trái
        (-bf / 2, H - tf),
        (-tw / 2, H - tf),
        (-tw / 2, tfb),
        (-bfb / 2, tfb),
    ]
    return [(x / 1000.0, y / 1000.0) for x, y in ring_mm]


def i_girder_section_from_params(params: dict) -> dict:
    """I BTCT DUL — contract đầy đủ; ``web_width_total_m`` = tw (một sườn)."""
    props = polygon_properties(_i_girder_ring(params))
    return {
        "depth_m": _positive(params, "girder_depth_mm") / 1000.0,
        "area_m2": props["area_m2"],
        "I_m4": props["I_m4"],
        "y_bottom_m": props["centroid_y_m"],
        "top_flange_width_m": _positive(params, "top_flange_width_mm") / 1000.0,
        "web_width_total_m": _positive(params, "web_thickness_mm") / 1000.0,
        "perimeter_m": props["perimeter_m"],
        "source": "PARAMETRIC",
    }


def fabrication_violations_i_girder(params: dict, context: dict | None = None) -> list[dict]:
    """FAB cho I DUL: sườn/cánh mỏng, chỗ cáp trong cánh dưới, cẩu, vận chuyển, L/H.

    Rule ID giữ ngữ nghĩa Super-T (FAB-001..007) để rule profile V2 điều khiển
    đồng nhất; ngưỡng lấy từ ``context["fab_limits"]`` (khóa thiếu lấy
    ``SECTION_FAB_DEFAULTS``). Rule cần khóa thiếu thì BỎ QUA (không bịa).
    """
    context = context or {}
    limits = dict(SECTION_FAB_DEFAULTS)
    limits.update(context.get("fab_limits", {}) or {})
    v: list[dict] = []

    H = _positive(params, "girder_depth_mm")
    tf = _positive(params, "top_flange_thickness_mm")
    tw = _positive(params, "web_thickness_mm")
    bfb = _positive(params, "bottom_flange_width_mm")
    tfb = _positive(params, "bottom_flange_thickness_mm")

    tw_min = float(limits["web_thickness_min_mm"])
    if tw < tw_min - _EPS:
        v.append(_violation("FAB-001",
                 f"Sườn dày {tw:.0f} mm < tối thiểu {tw_min:.0f} mm (I DUL đổ xưởng)",
                 (tw_min - tw) / tw_min))
    tf_min = float(limits["top_flange_thickness_min_mm"])
    if tf < tf_min - _EPS:
        v.append(_violation("FAB-002",
                 f"Cánh trên dày {tf:.0f} mm < tối thiểu {tf_min:.0f} mm",
                 (tf_min - tf) / tf_min))

    strand_count = context.get("strand_count")
    if strand_count is not None:
        cap = _strand_capacity(bfb, tfb,
                               float(limits["strand_grid_pitch_mm"]),
                               float(limits["strand_cover_mm"]))
        need = int(strand_count)
        if cap < need:
            v.append(_violation("FAB-003",
                     f"Cánh dưới bố trí được {cap} tao < cần {need} tao "
                     f"(lưới {limits['strand_grid_pitch_mm']:.0f} mm, cover "
                     f"{limits['strand_cover_mm']:.0f} mm)",
                     (need - cap) / max(need, 1)))

    span_m = context.get("span_m")
    if span_m is not None:
        height_mm = float(limits["transport_height_mm"])
        if H > height_mm + _EPS:
            v.append(_violation("FAB-005",
                     f"Cao tiết diện {H:.0f} mm vượt tĩnh không vận chuyển "
                     f"{height_mm:.0f} mm",
                     (H - height_mm) / height_mm))
        lift_t = float(limits["lift_capacity_t"])
        density = float(limits["concrete_density_t_per_m3"])
        # Khối lượng dùng area thật của tiết diện (m2) × dài × khối lượng riêng
        area = i_girder_section_from_params(params)["area_m2"]
        weight_t = area * density * float(span_m)
        if weight_t > lift_t + _EPS:
            v.append(_violation("FAB-004",
                     f"Khối lượng phiến {weight_t:.1f} t > sức cẩu {lift_t:.0f} t",
                     (weight_t - lift_t) / lift_t))
        ratio = span_m * 1000.0 / H
        lo, hi = float(limits["span_depth_ratio_min"]), float(limits["span_depth_ratio_max"])
        if ratio < lo - _EPS or ratio > hi + _EPS:
            v.append(_violation("FAB-007",
                     f"L/H = {ratio:.1f} ngoài dải cấu tạo [{lo:.0f}, {hi:.0f}]",
                     min(abs(ratio - lo), abs(ratio - hi)) / max(lo, 1.0),
                     severity="SOFT"))
    return v


# ===================================================================
# Hộp đơn ô BTCT — section là MÁNG CHỮ U (bản trên do solver liên hợp)
# ===================================================================
def _box_ring(params: dict) -> list[tuple[float, float]]:
    H = _positive(params, "box_web_height_mm")
    Bb = _positive(params, "box_bottom_width_mm")
    tsb = _positive(params, "box_bottom_slab_mm")
    tw = _positive(params, "box_web_thickness_mm")

    if tsb >= H:
        raise SectionGeometryError(
            f"Bản đáy dày {tsb:.0f} >= cao sườn {H:.0f} — máng U suy biến")
    if Bb <= 2 * tw + 100:
        raise SectionGeometryError(
            f"Đáy hộp {Bb:.0f} mm không đủ chỗ cho 2 sườn tw={tw:.0f}")

    xi, xo = Bb / 2 - tw, Bb / 2
    ring_mm = [
        (-xo, 0.0),       # đáy ngoài trái → phải
        (xo, 0.0),
        (xo, H),          # đỉnh sườn phải (mép ngoài)
        (xi, H),          # đỉnh sườn phải (mép trong)
        (xi, tsb),        # mặt trong sườn phải xuống bản đáy
        (-xi, tsb),       # mặt trên bản đáy, phải → trái
        (-xi, H),         # mép trong sườn trái
        (-xo, H),         # mép ngoài sườn trái
    ]
    return [(x / 1000.0, y / 1000.0) for x, y in ring_mm]


def box_girder_section_from_params(params: dict) -> dict:
    """Máng chữ U của hộp đơn ô — bản trên sẽ do solver liên hợp bổ sung.

    ``web_width_total_m`` = 2·tw (hai sườn chịu cắt). ``top_flange_width_m``
    trả bề rộng ĐÁY hộp: khóa này chỉ dùng cho GEOM-002 khe cánh dầm liền kề,
    mà hộp đơn ô có girder_count = 1 nên không bao giờ được đọc.
    """
    props = polygon_properties(_box_ring(params))
    return {
        "depth_m": _positive(params, "box_web_height_mm") / 1000.0,
        "area_m2": props["area_m2"],
        "I_m4": props["I_m4"],
        "y_bottom_m": props["centroid_y_m"],
        "top_flange_width_m": _positive(params, "box_bottom_width_mm") / 1000.0,
        "web_width_total_m": 2.0 * _positive(params, "box_web_thickness_mm") / 1000.0,
        "perimeter_m": props["perimeter_m"],
        "source": "PARAMETRIC",
    }


def fabrication_violations_box_girder(params: dict, context: dict | None = None) -> list[dict]:
    """FAB hộp CIP: sườn/bản tối thiểu, chỗ cáp trong đáy, L/H dải hộp."""
    context = context or {}
    limits = dict(SECTION_FAB_DEFAULTS)
    limits.update(context.get("fab_limits", {}) or {})
    v: list[dict] = []

    H = _positive(params, "box_web_height_mm")
    Bb = _positive(params, "box_bottom_width_mm")
    tsb = _positive(params, "box_bottom_slab_mm")
    tw = _positive(params, "box_web_thickness_mm")

    tw_min = float(limits["box_web_thickness_min_mm"])
    if tw < tw_min - _EPS:
        v.append(_violation("FAB-001",
                 f"Sườn hộp dày {tw:.0f} mm < tối thiểu {tw_min:.0f} mm "
                 "(cáp trong sườn cần chỗ đầm + cover)",
                 (tw_min - tw) / tw_min))

    ts_min = float(limits["box_top_slab_min_mm"])
    ts_deck = context.get("deck_slab_thickness_mm")
    if ts_deck is not None and float(ts_deck) < ts_min - _EPS:
        v.append(_violation("FAB-002",
                 f"Bản trên hộp dày {float(ts_deck):.0f} mm < tối thiểu cấu tạo "
                 f"{ts_min:.0f} mm (chịu bánh xe trực tiếp)",
                 (ts_min - float(ts_deck)) / ts_min))
    tsb_min = float(limits["box_bottom_slab_min_mm"])
    if tsb < tsb_min - _EPS:
        v.append(_violation("FAB-002",
                 f"Bản đáy dày {tsb:.0f} mm < tối thiểu {tsb_min:.0f} mm",
                 (tsb_min - tsb) / tsb_min))

    strand_count = context.get("strand_count")
    if strand_count is not None:
        cap = _strand_capacity(Bb - 2 * tw, tsb,
                               float(limits["strand_grid_pitch_mm"]),
                               float(limits["strand_cover_mm"]))
        need = int(strand_count)
        if cap < need:
            v.append(_violation("FAB-003",
                     f"Bản đáy bố trí được {cap} tao < cần {need} tao",
                     (need - cap) / max(need, 1)))

    span_m = context.get("span_m")
    if span_m is not None:
        ratio = span_m * 1000.0 / H
        lo = float(limits["box_span_depth_ratio_min"])
        hi = float(limits["box_span_depth_ratio_max"])
        if ratio < lo - _EPS or ratio > hi + _EPS:
            v.append(_violation("FAB-007",
                     f"L/H = {ratio:.1f} ngoài dải hộp CIP [{lo:.0f}, {hi:.0f}]",
                     min(abs(ratio - lo), abs(ratio - hi)) / max(lo, 1.0),
                     severity="SOFT"))
    return v


# ===================================================================
# Composite thép I + bản BT — CHỈ L0
# ===================================================================
def _steel_i_ring(params: dict) -> list[tuple[float, float]]:
    hs = _positive(params, "steel_depth_mm")
    bft = _positive(params, "steel_top_flange_width_mm")
    tft = _positive(params, "steel_top_flange_thickness_mm")
    tw = _positive(params, "steel_web_thickness_mm")
    bfb = _positive(params, "steel_bottom_flange_width_mm")
    tfb = _positive(params, "steel_bottom_flange_thickness_mm")

    if tft + tfb >= hs:
        raise SectionGeometryError(
            f"tft+tfb ({tft:.0f}+{tfb:.0f}) >= hs ({hs:.0f}) — thép I suy biến")
    if bft <= tw or bfb <= tw:
        raise SectionGeometryError(
            f"Cánh thép phải rộng hơn sườn: bft={bft:.0f}, bfb={bfb:.0f}, tw={tw:.0f}")

    ring_mm = [
        (-bfb / 2, 0.0),
        (bfb / 2, 0.0),
        (bfb / 2, tfb),
        (tw / 2, tfb),
        (tw / 2, hs - tft),
        (bft / 2, hs - tft),
        (bft / 2, hs),
        (-bft / 2, hs),
        (-bft / 2, hs - tft),
        (-tw / 2, hs - tft),
        (-tw / 2, tfb),
        (-bfb / 2, tfb),
    ]
    return [(x / 1000.0, y / 1000.0) for x, y in ring_mm]


def composite_i_girder_section_from_params(params: dict) -> dict:
    """Thép I riêng lẻ (chưa gồm bản) — chỉ dùng cho screening L0.

    ``source = "PARAMETRIC_COMPOSITE"`` để mọi bên downstream nhận biết đây
    KHÔNG phải tiết diện bê tông DUL: mô hình sức kháng L1 không áp dụng.
    """
    props = polygon_properties(_steel_i_ring(params))
    hs = _positive(params, "steel_depth_mm")
    return {
        "depth_m": hs / 1000.0,
        "area_m2": props["area_m2"],
        "I_m4": props["I_m4"],
        "y_bottom_m": props["centroid_y_m"],
        "top_flange_width_m": _positive(params, "steel_top_flange_width_mm") / 1000.0,
        "web_width_total_m": _positive(params, "steel_web_thickness_mm") / 1000.0,
        "perimeter_m": props["perimeter_m"],
        "source": "PARAMETRIC_COMPOSITE",
        "material_kind": "STEEL",
    }


def fabrication_violations_composite_i(params: dict, context: dict | None = None) -> list[dict]:
    """FAB thép I liên hợp: slenderness lớp 1 (web/cánh nén) + dải L/H.

    Ngưỡng slenderness tham chiếu mức tiết diện lớp 1 thông dụng cho dầm liên
    hợp (EN 1993-1-1 Table 5.2, thép S355: c/tf ≤ 14·ε với ε≈0.81 → ~11;
    lấy 14 cho S235 và ghi rõ đây là ngưỡng screening, không phải kiểm tra
    chảy vắt thật). Web: hs/tw ≤ 110 (dầm có buckling restraint thông thường).
    """
    context = context or {}
    limits = dict(SECTION_FAB_DEFAULTS)
    limits.update(context.get("fab_limits", {}) or {})
    v: list[dict] = []

    hs = _positive(params, "steel_depth_mm")
    bft = _positive(params, "steel_top_flange_width_mm")
    tft = _positive(params, "steel_top_flange_thickness_mm")
    tw = _positive(params, "steel_web_thickness_mm")

    web_slenderness = hs / tw
    web_max = float(limits["steel_web_slenderness_max"])
    if web_slenderness > web_max + _EPS:
        v.append(_violation("FAB-001",
                 f"Web slenderness hs/tw = {web_slenderness:.0f} > {web_max:.0f} "
                 "(ngưỡng screening lớp 1)",
                 (web_slenderness - web_max) / web_max))
    flange_slenderness = (bft / 2.0) / tft
    flange_max = float(limits["steel_flange_slenderness_max"])
    if flange_slenderness > flange_max + _EPS:
        v.append(_violation("FAB-002",
                 f"Cánh trên slenderness (bf/2)/tf = {flange_slenderness:.1f} > "
                 f"{flange_max:.1f} (ngưỡng screening lớp 1)",
                 (flange_slenderness - flange_max) / flange_max))

    span_m = context.get("span_m")
    if span_m is not None:
        ratio = span_m * 1000.0 / hs
        lo = float(limits["composite_span_depth_ratio_min"])
        hi = float(limits["composite_span_depth_ratio_max"])
        if ratio < lo - _EPS or ratio > hi + _EPS:
            v.append(_violation("FAB-007",
                     f"L/H = {ratio:.1f} ngoài dải composite [{lo:.0f}, {hi:.0f}]",
                     min(abs(ratio - lo), abs(ratio - hi)) / max(lo, 1.0),
                     severity="SOFT"))
    return v


def composite_solver_gate(context: dict | None = None) -> dict:
    """HARD gate: L1 line-girder KHÔNG hợp lệ cho composite thép-BT.

    Mô hình sức kháng L1 (khối nén bê tông MODEL-001, tao DUL dính bám, Vc bê
    tông trên web) chỉ đúng cho tiết diện BTCT. Chạy composite qua L1 sẽ sinh
    số liệu SAI có nhãn PASS/FAIL — vi phạm nguyên tắc bất biến số 1 của repo.
    Gate này chặn TRƯỚC solver; gỡ gate khi có solver composite thật (task riêng).
    """
    return _violation(
        "SOLVER-COMPOSITE-001",
        "Composite thép-BT chưa có solver sức kháng hợp lệ (L1 chỉ mô hình "
        "BTCT-DUL); chỉ screening L0 được phép — không mở solver",
        1.0)
