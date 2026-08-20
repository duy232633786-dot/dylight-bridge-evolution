r"""Section calculator tham số hóa cho dầm Super-T dạng máng hở (open trough).

Module THUẦN TOÁN: không đọc catalog, không gọi solver, không tiêu ngân sách
đánh giá. Mọi hàm ở đây rẻ như ``check_geometry``/``compute_objectives`` (cấp L0)
nên EA/RL được phép gọi hàng vạn lần trong một vòng tìm kiếm.

Vai trò: cho phép AI TỰ SINH hình dạng mặt cắt thay vì chỉ chọn trong catalog
định hình, đồng thời trả về đúng bộ khóa mà ``catalogs["girder_sections"][...]``
đang dùng để phần còn lại của pipeline (geometry/line_girder/objectives) không
phải biết tiết diện đến từ đâu.

--------------------------------------------------------------------------
MÔ HÌNH HÌNH HỌC (gần đúng, đối xứng qua trục đứng, đơn vị tham số: mm)
--------------------------------------------------------------------------
Tham số (đều là số dương; thực tế dùng số nguyên mm):
    girder_depth_mm            H   — chiều cao toàn tiết diện
    top_flange_width_mm        bf  — bề rộng cánh trên
    top_flange_thickness_mm    tf  — chiều dày cánh trên (lấy TRUNG BÌNH, coi đều)
    web_thickness_mm           tw  — chiều dày MỖI sườn (đo theo phương NGANG)
    bottom_bulb_width_mm       bb  — bề rộng MỖI bầu dưới
    bottom_bulb_height_mm      hb  — chiều cao MỖI bầu dưới

Gốc tọa độ: y = 0 tại ĐÁY dầm, x = 0 tại TIM dầm. Các mốc dựng biên:

  * Mép ngoài cánh trên:      x = ±bf/2,                     y ∈ [H - tf, H]
  * Mép ngoài sườn tại đáy cánh trên:
                              x = ±x_web_top = ±(bf/2 - FLANGE_OVERHANG_MM),
                              y = H - tf
  * Bầu dưới là HÌNH CHỮ NHẬT cao hb, rộng bb, mép NGOÀI của bầu TRÙNG mép ngoài
    sườn tại y = hb, tức mặt ngoài bầu và mặt ngoài chân sườn liền nhau, không có
    bậc. Vị trí mép ngoài bầu:
                              x = ±x_bulb_out = ±(x_web_top - (bb - tw))
  * Mép trong bầu:            x = ±x_bulb_in  = ±(x_bulb_out - bb)
  * Sườn nghiêng TUYẾN TÍNH từ mép ngoài bầu (y = hb) lên mép ngoài sườn
    (y = H - tf); mặt trong sườn song song, lệch vào trong đúng tw.
  * Tiết diện HỞ ĐÁY giữa hai sườn — KHÔNG có bản đáy.

Quy ước then chốt (chọn để mô hình khép kín chỉ với 6 tham số trên):
    Bầu dưới là phần CHÂN SƯỜN ĐƯỢC MỞ RỘNG. Lượng mở rộng Δ = bb - tw được đặt
    hoàn toàn về phía TRONG lòng máng, và mặt ngoài sườn được vát ra ngoài đúng
    bằng Δ khi đi từ y = hb lên y = H - tf. Nhờ vậy:
      - độ vát ván khuôn (draft) = Δ / (H - tf - hb) sinh ra TỪ THAM SỐ, không
        phải hằng số áp đặt;
      - khi bb = tw (không còn bầu) sườn THẲNG ĐỨNG hoàn toàn ⇒ không rút được
        ván khuôn ngoài ⇒ FAB-006 kích hoạt đúng như mong đợi.

Sơ đồ ASCII (nửa trái/phải đối xứng, không theo tỷ lệ):

        |<--------------------- bf --------------------->|
        +------------------------------------------------+   y = H
        |               cánh trên, dày tf                 |   (tf)
        +-----+------------------------------------+-----+   y = H - tf
    300 ->|   \                                    /   |<- 300   = FLANGE_OVERHANG_MM
              \          LÒNG MÁNG HỞ            /
               \      (không có bản đáy)       /            mặt ngoài sườn vát
                \                            /              ra ngoài đúng Δ = bb - tw
              +--+                        +--+              y = hb
              |  |                        |  |
           +--+--+                        +--+--+           (bầu bulge VÀO TRONG)
           |      bb     |          |     bb     |   hb
           +-------------+          +------------+          y = 0
           ^             ^          ^            ^
        -x_bulb_out  -x_bulb_in  +x_bulb_in  +x_bulb_out

Độ chính xác: đây là mô hình GẦN ĐÚNG (bỏ vút, bỏ bo góc, sườn coi như dày đều
theo phương ngang). Mục tiêu là NHẤT QUÁN và ĐƠN ĐIỆU theo tham số để thuật toán
tối ưu so sánh được các phương án, không phải thay thế bản vẽ chế tạo.
"""
from __future__ import annotations

import math

__all__ = [
    "SectionGeometryError",
    "FLANGE_OVERHANG_MM",
    "FAB_DEFAULTS",
    "PARAM_KEYS",
    "build_section_polygon",
    "polygon_properties",
    "section_from_params",
    "fabrication_violations",
]

#: Phần cánh trên chìa ra NGOÀI mép ngoài sườn ở MỖI bên (mm).
#: Đây là hằng số cấu tạo của họ Super-T dạng máng hở: cánh trên vươn ra hai bên
#: để đỡ ván khuôn bản mặt cầu giữa hai dầm liền kề. Giữ cố định để 6 tham số
#: hình học còn lại xác định trọn vẹn biên tiết diện.
FLANGE_OVERHANG_MM = 300.0

#: Thứ tự khóa tham số mặt cắt — dùng cho kiểm tra đầu vào và thông báo lỗi.
PARAM_KEYS = (
    "girder_depth_mm",
    "top_flange_width_mm",
    "top_flange_thickness_mm",
    "web_thickness_mm",
    "bottom_bulb_width_mm",
    "bottom_bulb_height_mm",
)

#: Ngưỡng chế tạo/vận chuyển/cẩu lắp mặc định. Caller ghi đè từng khóa qua
#: ``context["fab_limits"]``; khóa không ghi đè lấy giá trị ở đây.
FAB_DEFAULTS = {
    "web_thickness_min_mm": 100.0,        # FAB-001
    "top_flange_thickness_min_mm": 90.0,  # FAB-002
    "strand_grid_pitch_mm": 50.0,         # FAB-003
    "strand_cover_mm": 50.0,              # FAB-003
    "lift_capacity_t": 80.0,              # FAB-004
    "concrete_density_t_per_m3": 2.5,     # FAB-004
    "transport_height_mm": 2200.0,        # FAB-005
    "min_draft_ratio": 1.0 / 25.0,        # FAB-006
    "span_depth_ratio_min": 17.0,         # FAB-007
    "span_depth_ratio_max": 26.0,         # FAB-007
}

_EPS = 1e-12


class SectionGeometryError(ValueError):
    """Tham số mặt cắt phi vật lý — không dựng được biên nhất quán.

    Là lỗi ĐẦU VÀO, không phải lỗi nội bộ: caller (grammar/EA/RL) bắt và loại
    phương án ở cấp L0, không tiêu ngân sách solver.
    """


# --------------------------------------------------------------- tham số
def _number(params: dict, key: str) -> float:
    """Đọc một tham số mm, ép về float và chặn kiểu/giá trị phi vật lý."""
    if key not in params:
        raise SectionGeometryError(f"Thiếu tham số mặt cắt: {key}")
    value = params[key]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SectionGeometryError(f"{key} phải là số, nhận {value!r}")
    value = float(value)
    if not math.isfinite(value):
        raise SectionGeometryError(f"{key} không hữu hạn: {value!r}")
    if value <= 0.0:
        raise SectionGeometryError(f"{key}={value:g} mm phải > 0")
    return value


def _derived_mm(params: dict) -> dict:
    """Các mốc dựng biên (mm) sau khi đã kiểm tra tính khả thi hình học.

    Raise ``SectionGeometryError`` cho mọi bộ tham số không dựng được đa giác
    ĐƠN, đối xứng: kích thước ≤ 0, cánh trên hẹp hơn sườn, hai sườn giao nhau
    qua tim, bầu chồng lấn qua tim, bầu hẹp hơn sườn, hoặc bầu cao quá thân dầm.
    """
    H = _number(params, "girder_depth_mm")
    bf = _number(params, "top_flange_width_mm")
    tf = _number(params, "top_flange_thickness_mm")
    tw = _number(params, "web_thickness_mm")
    bb = _number(params, "bottom_bulb_width_mm")
    hb = _number(params, "bottom_bulb_height_mm")

    if tf >= H:
        raise SectionGeometryError(
            f"Cánh trên dày tf={tf:g} mm ≥ chiều cao dầm H={H:g} mm")
    y_web_top = H - tf
    web_height = y_web_top - hb
    if web_height <= 0.0:
        raise SectionGeometryError(
            f"Bầu dưới cao hb={hb:g} mm ≥ H - tf = {y_web_top:g} mm — không còn thân sườn")

    x_web_top = bf / 2.0 - FLANGE_OVERHANG_MM
    if x_web_top <= tw:
        raise SectionGeometryError(
            f"Cánh trên hẹp hơn sườn: bf/2 - {FLANGE_OVERHANG_MM:g} = {x_web_top:g} mm "
            f"≤ tw={tw:g} mm — hai sườn giao nhau qua tim")

    if bb < tw:
        raise SectionGeometryError(
            f"Bầu dưới hẹp hơn sườn: bb={bb:g} mm < tw={tw:g} mm")

    draft_dx = bb - tw                      # lượng sườn vát ra ngoài khi đi lên
    x_bulb_out = x_web_top - draft_dx
    x_bulb_in = x_bulb_out - bb
    if x_bulb_in <= 0.0:
        raise SectionGeometryError(
            f"Bầu dưới chồng lấn qua tim: mép trong bầu tại x={x_bulb_in:g} mm ≤ 0 "
            f"(bb={bb:g} mm quá lớn so với bf={bf:g} mm)")

    return {
        "H": H, "bf": bf, "tf": tf, "tw": tw, "bb": bb, "hb": hb,
        "x_flange": bf / 2.0,
        "x_web_top": x_web_top,
        "x_bulb_out": x_bulb_out,
        "x_bulb_in": x_bulb_in,
        "y_web_top": y_web_top,
        "web_height": web_height,
        "draft_dx": draft_dx,
        "draft_ratio": draft_dx / web_height,
    }


# --------------------------------------------------------------- đa giác
def build_section_polygon(params: dict) -> list[tuple[float, float]]:
    """Biên mặt cắt: đa giác ĐƠN, ngược chiều kim đồng hồ, đơn vị MÉT.

    Danh sách đỉnh KHÔNG lặp lại đỉnh đầu ở cuối — vòng được đóng NGẦM bằng cạnh
    nối đỉnh cuối về đỉnh đầu (quy ước chung của ``polygon_properties``).

    Trình tự duyệt (bắt đầu từ mép TRONG đáy bầu phải, đi ngược chiều kim đồng hồ,
    tức phần bê tông luôn nằm bên TRÁI hướng đi):
        đáy bầu phải → mặt ngoài bầu phải → mặt ngoài sườn phải (vát) →
        đáy cánh hẫng phải → mép cánh phải → mặt trên cánh → mép cánh trái →
        đáy cánh hẫng trái → mặt ngoài sườn trái (vát) → mặt ngoài bầu trái →
        đáy bầu trái → mặt trong bầu trái → mặt trên bầu trái →
        mặt trong sườn trái → trần lòng máng → mặt trong sườn phải →
        mặt trên bầu phải → (đóng ngầm) mặt trong bầu phải.

    Raise ``SectionGeometryError`` nếu tham số phi vật lý.
    """
    g = _derived_mm(params)
    H, tw, hb = g["H"], g["tw"], g["hb"]
    xf, xt, xo, xi = g["x_flange"], g["x_web_top"], g["x_bulb_out"], g["x_bulb_in"]
    yt = g["y_web_top"]

    ring_mm = [
        (xi, 0.0),              # 1  mép trong đáy bầu phải
        (xo, 0.0),              # 2  mép ngoài đáy bầu phải
        (xo, hb),               # 3  đỉnh mặt ngoài bầu phải
        (xt, yt),               # 4  mép ngoài sườn phải tại đáy cánh
        (xf, yt),               # 5  đáy mép cánh phải
        (xf, H),                # 6  đỉnh mép cánh phải
        (-xf, H),               # 7  đỉnh mép cánh trái
        (-xf, yt),              # 8  đáy mép cánh trái
        (-xt, yt),              # 9  mép ngoài sườn trái tại đáy cánh
        (-xo, hb),              # 10 đỉnh mặt ngoài bầu trái
        (-xo, 0.0),             # 11 mép ngoài đáy bầu trái
        (-xi, 0.0),             # 12 mép trong đáy bầu trái
        (-xi, hb),              # 13 đỉnh mặt trong bầu trái
        (-(xo - tw), hb),       # 14 chân mặt trong sườn trái
        (-(xt - tw), yt),       # 15 đỉnh mặt trong sườn trái
        ((xt - tw), yt),        # 16 đỉnh mặt trong sườn phải (trần lòng máng)
        ((xo - tw), hb),        # 17 chân mặt trong sườn phải
        (xi, hb),               # 18 đỉnh mặt trong bầu phải
    ]

    # Khi bb == tw (bầu suy biến thành chân sườn) một số đỉnh trùng nhau; bỏ đỉnh
    # lặp để đa giác luôn ĐƠN, không có cạnh dài 0.
    ring = []
    for x_mm, y_mm in ring_mm:
        point = (x_mm / 1000.0, y_mm / 1000.0)
        if ring and abs(point[0] - ring[-1][0]) < _EPS and abs(point[1] - ring[-1][1]) < _EPS:
            continue
        ring.append(point)
    if len(ring) > 1 and abs(ring[0][0] - ring[-1][0]) < _EPS \
            and abs(ring[0][1] - ring[-1][1]) < _EPS:
        ring.pop()
    return ring


def polygon_properties(points) -> dict:
    """Đặc trưng hình học của đa giác bằng ĐỊNH LÝ GREEN (đơn vị vào: mét).

    Với ``cross_i = x_i·y_{i+1} - x_{i+1}·y_i`` trên vòng đóng:
        A   = ½ Σ cross_i
        Q_x = ⅙ Σ (y_i + y_{i+1})·cross_i                    (mô men bậc nhất)
        I_0 = 1/12 Σ (y_i² + y_i·y_{i+1} + y_{i+1}²)·cross_i (mô men bậc hai quanh y=0)
        ȳ   = Q_x / A
        I   = I_0 - A·ȳ²                                     (trục NGANG qua trọng tâm)

    Vòng được đóng ngầm; nếu đỉnh cuối trùng đỉnh đầu thì đỉnh thừa được bỏ.
    Giá trị trả về mang DẤU theo chiều duyệt: đa giác ngược chiều kim đồng hồ
    (như ``build_section_polygon``) cho ``area_m2`` > 0.
    """
    pts = [(float(x), float(y)) for x, y in points]
    if len(pts) >= 2 and abs(pts[0][0] - pts[-1][0]) < _EPS \
            and abs(pts[0][1] - pts[-1][1]) < _EPS:
        pts = pts[:-1]
    if len(pts) < 3:
        raise SectionGeometryError("Đa giác cần tối thiểu 3 đỉnh phân biệt")

    twice_area = 0.0
    first_moment = 0.0
    second_moment = 0.0
    perimeter = 0.0
    n = len(pts)
    for i in range(n):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % n]
        cross = x0 * y1 - x1 * y0
        twice_area += cross
        first_moment += (y0 + y1) * cross
        second_moment += (y0 * y0 + y0 * y1 + y1 * y1) * cross
        perimeter += math.hypot(x1 - x0, y1 - y0)

    area = twice_area / 2.0
    if abs(area) < _EPS:
        raise SectionGeometryError("Đa giác suy biến: diện tích ≈ 0")
    centroid_y = first_moment / (6.0 * area)
    inertia_axis = second_moment / 12.0
    return {
        "area_m2": area,
        "centroid_y_m": centroid_y,
        "I_m4": inertia_axis - area * centroid_y * centroid_y,
        "perimeter_m": perimeter,
    }


def section_from_params(params: dict) -> dict:
    """Tiết diện tham số hóa dưới ĐÚNG contract của ``catalogs["girder_sections"]``.

    Trả về các khóa mà geometry/line_girder/objectives đang dùng
    (``depth_m``, ``area_m2``, ``I_m4``, ``y_bottom_m``, ``top_flange_width_m``,
    ``web_width_total_m``) cộng thêm ``perimeter_m`` (phục vụ ước lượng ván khuôn)
    và ``source = "PARAMETRIC"`` để phân biệt với entry catalog định hình.

    ``web_width_total_m`` = 2·tw/1000 — tổng bề rộng sườn chịu cắt của một phiến dầm.
    """
    g = _derived_mm(params)
    props = polygon_properties(build_section_polygon(params))
    return {
        "depth_m": g["H"] / 1000.0,
        "area_m2": props["area_m2"],
        "I_m4": props["I_m4"],
        "y_bottom_m": props["centroid_y_m"],
        "top_flange_width_m": g["bf"] / 1000.0,
        "web_width_total_m": 2.0 * g["tw"] / 1000.0,
        "perimeter_m": props["perimeter_m"],
        "source": "PARAMETRIC",
    }


# --------------------------------------------------------------- chế tạo
def _strand_capacity(bb: float, hb: float, pitch: float, cover: float) -> int:
    """Số tao cáp bố trí được trong CẢ HAI bầu dưới theo lưới ô vuông.

    Lưới ô ``pitch × pitch`` (mặc định 50×50 mm), lớp bảo vệ ``cover`` (mặc định
    50 mm) tính từ MỌI mặt biên của bầu, mỗi ô chứa đúng 1 tao:

        usable_w = bb - 2·cover
        usable_h = hb - 2·cover
        n_cols   = floor(usable_w / pitch)   (= 0 nếu usable_w < pitch)
        n_rows   = floor(usable_h / pitch)   (= 0 nếu usable_h < pitch)
        capacity = 2 · n_cols · n_rows       (2 bầu đối xứng)

    Diện tích bầu 2·bb·hb chỉ là chặn TRÊN; capacity ở trên là số ô THỰC bố trí
    được sau khi trừ lớp bảo vệ, nên luôn ≤ 2·bb·hb / pitch².
    """
    if pitch <= 0.0:
        return 0
    usable_w = bb - 2.0 * cover
    usable_h = hb - 2.0 * cover
    if usable_w < pitch or usable_h < pitch:
        return 0
    return 2 * int(usable_w // pitch) * int(usable_h // pitch)


def fabrication_violations(params: dict, context: dict | None = None) -> list[dict]:
    """Ràng buộc CHẾ TẠO – VẬN CHUYỂN – CẨU LẮP – BỐ TRÍ CÁP của mặt cắt.

    Trả về list violation đúng contract của repo
    ``{rule_id, severity, message, margin}`` với ``margin`` là mức vi phạm CHUẨN
    HÓA > 0 (luôn > 0 khi có tên trong list). Không vi phạm ⇒ list rỗng.
    Verifier là nơi duy nhất kết luận PASS/FAIL; hàm này chỉ cung cấp bằng chứng.

    ``context`` do caller cấp, ví dụ
    ``{"span_m": 38.3, "strand_count": 42, "girder_concrete_fc_MPa": 45,
       "fab_limits": {...}}``. Hàm CHỊU ĐƯỢC thiếu khóa: rule nào cần khóa không
    có thì BỎ QUA rule đó (FAB-003 cần ``strand_count``; FAB-004 và FAB-007 cần
    ``span_m``). Ngưỡng lấy từ ``context["fab_limits"]``, khóa thiếu lấy
    ``FAB_DEFAULTS``.

    Tham số phi vật lý vẫn raise ``SectionGeometryError`` (fail-closed): không
    thể kết luận "chế tạo được" cho một biên không dựng nổi.

    Danh mục rule (HARD trừ khi ghi khác):
      FAB-001  sườn quá mỏng ⇒ không đổ/đầm được bê tông, không đủ lớp bảo vệ.
      FAB-002  cánh trên quá mỏng ⇒ không đủ chiều dày cấu tạo/bảo vệ cốt thép.
      FAB-003  bầu dưới không đủ chỗ bố trí ``strand_count`` tao cáp.
      FAB-004  khối lượng một phiến dầm vượt sức nâng cẩu.
      FAB-005  chiều cao tiết diện vượt tĩnh không vận chuyển đường bộ.
      FAB-006  độ vát sườn quá nhỏ ⇒ không rút được ván khuôn ngoài.
      FAB-007  (SOFT) tỷ lệ nhịp/chiều cao ngoài dải cấu tạo thông thường.
    """
    context = context or {}
    g = _derived_mm(params)
    limits = dict(FAB_DEFAULTS)
    limits.update(context.get("fab_limits", {}) or {})

    violations: list[dict] = []

    def fail(rule_id: str, message: str, margin: float, severity: str = "HARD") -> None:
        violations.append({"rule_id": rule_id, "severity": severity,
                           "message": message, "margin": round(float(margin), 4)})

    # FAB-001 — chiều dày sườn tối thiểu
    tw_min = float(limits["web_thickness_min_mm"])
    if g["tw"] < tw_min - _EPS:
        fail("FAB-001",
             f"Sườn dày {g['tw']:.0f} mm < tối thiểu {tw_min:.0f} mm — không đổ/đầm "
             f"được bê tông và không đủ lớp bảo vệ cốt thép",
             (tw_min - g["tw"]) / tw_min)

    # FAB-002 — chiều dày cánh trên tối thiểu
    tf_min = float(limits["top_flange_thickness_min_mm"])
    if g["tf"] < tf_min - _EPS:
        fail("FAB-002",
             f"Cánh trên dày {g['tf']:.0f} mm < tối thiểu {tf_min:.0f} mm — không đủ "
             f"chiều dày cấu tạo cho cánh đỡ ván khuôn bản",
             (tf_min - g["tf"]) / tf_min)

    # FAB-003 — bố trí cáp trong bầu dưới (bỏ qua nếu caller không cấp strand_count)
    strand_count = context.get("strand_count")
    if strand_count is not None:
        need = int(strand_count)
        pitch = float(limits["strand_grid_pitch_mm"])
        cover = float(limits["strand_cover_mm"])
        capacity = _strand_capacity(g["bb"], g["hb"], pitch, cover)
        if capacity < need:
            denom = capacity if capacity > 0 else need
            fail("FAB-003",
                 f"Bầu dưới {g['bb']:.0f}×{g['hb']:.0f} mm chỉ bố trí được {capacity} tao "
                 f"theo lưới {pitch:.0f}×{pitch:.0f} mm (bảo vệ {cover:.0f} mm), "
                 f"cần {need} tao",
                 (need - capacity) / denom)

    # FAB-004 — khối lượng phiến dầm so với sức nâng cẩu (cần span_m)
    span_m = context.get("span_m")
    if span_m is not None:
        span_m = float(span_m)
        density = float(limits["concrete_density_t_per_m3"])
        lift_cap = float(limits["lift_capacity_t"])
        area_m2 = polygon_properties(build_section_polygon(params))["area_m2"]
        mass_t = area_m2 * span_m * density
        if lift_cap <= 0.0:
            fail("FAB-004", f"Sức nâng cẩu {lift_cap:g} t không hợp lệ", 1.0)
        elif mass_t > lift_cap + _EPS:
            fail("FAB-004",
                 f"Phiến dầm nặng {mass_t:.1f} t > sức nâng cẩu {lift_cap:.1f} t "
                 f"(A={area_m2:.3f} m² × L={span_m:.1f} m × {density:g} t/m³)",
                 (mass_t - lift_cap) / lift_cap)

    # FAB-005 — chiều cao vận chuyển
    h_max = float(limits["transport_height_mm"])
    if g["H"] > h_max + _EPS:
        fail("FAB-005",
             f"Chiều cao tiết diện {g['H']:.0f} mm > tĩnh không vận chuyển "
             f"{h_max:.0f} mm",
             (g["H"] - h_max) / h_max)

    # FAB-006 — độ vát sườn để rút ván khuôn ngoài
    draft_min = float(limits["min_draft_ratio"])
    draft = g["draft_ratio"]
    if draft < draft_min - _EPS:
        note = " (sườn thẳng đứng hoàn toàn)" if abs(draft) < _EPS else ""
        fail("FAB-006",
             f"Độ vát sườn {draft:.4f} = Δx {g['draft_dx']:.0f} mm / Δy "
             f"{g['web_height']:.0f} mm < tối thiểu {draft_min:.4f}{note} — "
             f"không rút được ván khuôn ngoài",
             (draft_min - draft) / draft_min)

    # FAB-007 (SOFT) — tỷ lệ nhịp/chiều cao (cần span_m)
    if span_m is not None:
        r_min = float(limits["span_depth_ratio_min"])
        r_max = float(limits["span_depth_ratio_max"])
        ratio = span_m / (g["H"] / 1000.0)
        if ratio < r_min - _EPS:
            fail("FAB-007",
                 f"Tỷ lệ nhịp/chiều cao {ratio:.2f} < {r_min:g} — dầm quá cao so với "
                 f"nhịp, bất thường về cấu tạo",
                 (r_min - ratio) / r_min, severity="SOFT")
        elif ratio > r_max + _EPS:
            fail("FAB-007",
                 f"Tỷ lệ nhịp/chiều cao {ratio:.2f} > {r_max:g} — dầm quá mảnh so với "
                 f"nhịp, bất thường về cấu tạo",
                 (ratio - r_max) / r_max, severity="SOFT")

    return violations
