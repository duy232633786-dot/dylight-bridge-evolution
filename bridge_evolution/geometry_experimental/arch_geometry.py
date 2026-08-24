"""Hình học thuần toán cho họ vòm chạy trên (deck arch) — SANDBOX THỰC NGHIỆM.

===========================================================================
GIỚI HẠN HIỆU LỰC — ĐỌC TRƯỚC KHI DÙNG
===========================================================================
Module này CHỈ dựng HÌNH HỌC: trục vòm, toạ độ chân/đỉnh, vị trí và chiều cao
cột khoang vòm, cao độ mặt cầu, vị trí ngang của các sườn vòm.

Nó KHÔNG tính nội lực, KHÔNG tính ứng suất, KHÔNG tính chuyển vị, KHÔNG tính
ổn định, KHÔNG tính bất kỳ đại lượng hiệu năng nào — và điều đó là CỐ Ý, không
phải thiếu sót tạm thời:

  * Runtime DYLIGHT hiện chỉ có L0 + L1 line-girder cho hệ n dầm Super-T song
    song nhịp giản đơn (RCM-2.0.0, claim_ceiling = SCREENED).
  * SOLVER_MIDAS_CIVIL, SOLVER_OPENSEESPY, GRILLAGE_3D và
    STAGED_PRESTRESS_EFFECTS đều ở trạng thái ABSENT.
  * Không có solver nào trong repo chạm được tới vòm. Bất kỳ con số hiệu năng
    nào mà hệ sinh ra cho họ kết cấu này sẽ nằm NGOÀI phạm vi hiệu lực của
    chính nó, dù nhìn có vẻ hợp lệ.

Mức claim của mọi kết quả trả về: **F0 IDEA** (multiagent/PHYSICS_GATES.md).
Toạ độ trả về là TOẠ ĐỘ, không phải kết luận kỹ thuật. Không được diễn giải
kết quả của module này thành "khả thi" hay "thi công được".

Một cảnh báo bản chất, không phải chi tiết (BRD-004 / INC-004): một cây vòm
khẩu độ lớn KHÔNG phải một kết cấu, nó là một CHUỖI kết cấu. Hình học mà module
này dựng là hình học của trạng thái HOÀN THIỆN (S7_SERVICE). Trong đúc/lắp hẫng,
mỗi nửa vòm là một CONSOL — dấu nội lực ngược hẳn, và tiết diện chịu lực còn
thay đổi giữa chừng (ống thép rỗng -> ống nhồi bê tông). Hình dạng hoàn thiện
KHÔNG mô tả được các trạng thái đó.

===========================================================================
QUY ƯỚC TOẠ ĐỘ
===========================================================================
  * x: dọc cầu, mét, gốc tại chân vòm TRÁI, dương về chân vòm PHẢI.
  * y: cao độ, mét, gốc tại cao độ chân vòm, dương hướng LÊN.
  * z: ngang cầu, mét, gốc tại tim mặt cầu, dương về bên phải theo chiều tăng x.
  * Đỉnh vòm ở x = span_m / 2, y = rise_m.
  * Đơn vị của module: MÉT (grammar dùng mm cho một số biến; đổi đơn vị là việc
    của người gọi, module này không tự đoán đơn vị).
"""

from __future__ import annotations

import hashlib
import json
import math
import re

#: Các dạng trục vòm được hỗ trợ.
AXIS_TYPES = ("PARABOLA_2ND_ORDER", "CATENARY")

#: Mức claim cố định của mọi kết quả module này trả về.
CLAIM_LEVEL = "IDEA"

#: Định danh generator cho lineage. Cặp (GENERATOR_ID, GENERATOR_VERSION) tham
#: gia geometry_hash: đổi phiên bản là ĐỔI hash, vì cùng bộ tham số qua hai
#: phiên bản thuật toán dựng hình khác nhau là hai case khác nhau về tái lập.
GENERATOR_ID = "arch_geometry"
GENERATOR_VERSION = "0.1.0-experimental"

#: Số ký tự hex đầu của geometry_hash dùng làm case id — khớp quy ước
#: CASE_ID_HASH_HEX = 16 của make_case_id trong bridge_evolution/state.py
#: (đây là quy ước ĐỊNH DẠNG, không phải ngưỡng kỹ thuật).
_CASE_ID_HASH_HEX = 16

#: Dạng hợp lệ của một geometry_hash: đúng 64 ký tự hex THƯỜNG (SHA-256 hex).
_HEX64_RE = re.compile(r"\A[0-9a-f]{64}\Z")

#: Tham số bắt buộc phải có mặt khi gọi geometry_hash(params).
_HASH_PARAM_REQUIRED = ("span_m", "rise_m", "deck_level_m", "bay_count")

#: Giá trị mặc định của các tham số còn lại — PHẢI khớp từng giá trị với default
#: trong chữ ký arch_geometry(), để geometry_hash(params) và lineage do
#: arch_geometry() tự tính luôn cho cùng một kết quả.
_HASH_PARAM_DEFAULTS = {
    "axis_type": "PARABOLA_2ND_ORDER",
    "deck_width_m": None,
    "rib_count": 2,
    "rib_edge_inset_m": 0.0,
    "point_count": 101,
    "construction_stage_id": "S7_SERVICE",
}

#: Dung sai và số vòng lặp tối đa khi giải tham số dây xích.
_CATENARY_TOL = 1e-12
_CATENARY_MAX_ITER = 200


class ArchGeometryError(ValueError):
    """Tham số hình học phi vật lý hoặc không dựng được biên.

    Fail-closed: module KHÔNG bịa giá trị mặc định và KHÔNG "sửa nhẹ" tham số
    của người gọi. Sai thì báo sai.
    """


# ---------------------------------------------------------------------------
# Kiểm tra tham số
# ---------------------------------------------------------------------------

def _as_positive_float(value, name: str) -> float:
    # Fail-closed: chỉ nhận int/float thật. KHÔNG tự ép kiểu chuỗi ("200" -> 200.0)
    # vì chuỗi lọt vào đây thường là dấu hiệu sai đơn vị hoặc dữ liệu chưa parse.
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ArchGeometryError(f"{name} phải là số thực, nhận được {value!r}")
    out = float(value)
    if not math.isfinite(out):
        raise ArchGeometryError(f"{name} phải hữu hạn, nhận được {out!r}")
    if out <= 0.0:
        raise ArchGeometryError(f"{name} phải dương, nhận được {out!r}")
    return out


def validate_arch_params(
    span_m,
    rise_m,
    axis_type: str = "PARABOLA_2ND_ORDER",
    springing_left_y_m: float = 0.0,
    springing_right_y_m: float = 0.0,
) -> tuple[float, float]:
    """Kiểm tra bộ tham số cơ bản của trục vòm; trả về ``(span_m, rise_m)``.

    Raise :class:`ArchGeometryError` khi:
      * khẩu độ hoặc đường tên không dương / không hữu hạn;
      * đường tên >= khẩu độ (L/f <= 1) — không phải vòm chạy trên nữa;
      * dạng trục không nằm trong :data:`AXIS_TYPES`;
      * hai chân vòm ở CAO ĐỘ KHÁC NHAU (xem giải thích trong thông báo lỗi).
    """
    span = _as_positive_float(span_m, "span_m")
    rise = _as_positive_float(rise_m, "rise_m")

    if axis_type not in AXIS_TYPES:
        raise ArchGeometryError(
            f"axis_type khong ho tro: {axis_type!r}; chi chap nhan {AXIS_TYPES}"
        )

    if rise >= span:
        raise ArchGeometryError(
            f"rise_m ({rise}) >= span_m ({span}): ty so L/f <= 1, khong con la "
            "vom chay tren. Kiem lai don vi va gia tri."
        )

    try:
        y_left = float(springing_left_y_m)
        y_right = float(springing_right_y_m)
    except (TypeError, ValueError) as exc:
        raise ArchGeometryError("cao do hai chan vom phai la so thuc") from exc

    if abs(y_left - y_right) > 1e-9:
        raise ArchGeometryError(
            "Hai chan vom o CAO DO KHAC NHAU (vom lech). Module nay KHONG dung "
            "hinh cho truong hop do, va co y khong lam vay: truc vom lech KHONG "
            "phai la mot parabol/day xich doi xung bi nghieng di, no phai duoc "
            "dan xuat lai tu duong ap luc cua tinh tai. Chot cao do hai chan "
            "trong design basis roi mo rong module bang mot ham rieng."
        )

    return span, rise


def _validate_point_count(value) -> int:
    """Kiểm tra ``point_count``: số nguyên LẺ >= 3 (đỉnh vòm phải là điểm mẫu)."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ArchGeometryError("point_count phải là số nguyên")
    if value < 3:
        raise ArchGeometryError(f"point_count phải >= 3, nhận được {value}")
    if value % 2 == 0:
        raise ArchGeometryError(
            f"point_count phải LẺ để đỉnh vòm là điểm mẫu, nhận được {value}"
        )
    return value


def _validate_deck_level(deck_level_m, rise: float) -> float:
    """Kiểm tra ``deck_level_m``: số thực hữu hạn, không thấp hơn đỉnh vòm."""
    try:
        deck = float(deck_level_m)
    except (TypeError, ValueError) as exc:
        raise ArchGeometryError("deck_level_m phải là số thực") from exc
    if not math.isfinite(deck):
        raise ArchGeometryError("deck_level_m phải hữu hạn")
    if deck < rise:
        raise ArchGeometryError(
            f"deck_level_m ({deck}) < rise_m ({rise}): mat cau nam DUOI dinh vom "
            "nen day khong con la vom chay tren. Doi deck_level_m hoac doi ho "
            "ket cau (vom chay duoi / vom co thanh cang)."
        )
    return deck


def _validate_count(value, name: str, minimum: int, even_required: bool) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ArchGeometryError(f"{name} phải là số nguyên, nhận được {value!r}")
    if value < minimum:
        raise ArchGeometryError(f"{name} phải >= {minimum}, nhận được {value}")
    if even_required and value % 2 != 0:
        raise ArchGeometryError(
            f"{name} phải CHẴN để đỉnh vòm là một điểm mẫu / một tuyến cột đối "
            f"xứng, nhận được {value}"
        )
    return value


# ---------------------------------------------------------------------------
# Trục vòm
# ---------------------------------------------------------------------------

def parabola_ordinate(x_m: float, span_m: float, rise_m: float) -> float:
    """Tung độ trục vòm parabol bậc 2 qua (0,0), (span/2, rise), (span, 0).

    y(x) = 4·f·x·(L − x) / L²
    """
    return 4.0 * rise_m * x_m * (span_m - x_m) / (span_m * span_m)


def catenary_parameter(span_m: float, rise_m: float) -> float:
    """Tham số ``a`` của dây xích lộn ngược qua (0,0), (L/2, f), (L, 0).

    Trục dây xích: y(x) = f − a·(cosh(u/a) − 1) với u = x − L/2.
    Điều kiện y(0) = y(L) = 0 cho phương trình một ẩn:

        g(a) = a·(cosh(s/a) − 1) − f = 0,   s = L/2

    g giảm đơn điệu theo a (a→0⁺: g→+∞; a→∞: g→−f), nên giải bằng chia đôi.
    Cận dưới lấy từ xấp xỉ parabol a₀ = s²/(2f), tại đó g(a₀) > 0 vì khai triển
    cosh còn các số hạng bậc cao dương.
    """
    s = span_m / 2.0

    def g(a: float) -> float:
        return a * (math.cosh(s / a) - 1.0) - rise_m

    lo = s * s / (2.0 * rise_m)
    if g(lo) <= 0.0:  # phòng xa cho sai số làm tròn ở tỉ lệ cực đoan
        lo *= 0.5
        guard = 0
        while g(lo) <= 0.0:
            lo *= 0.5
            guard += 1
            if guard > _CATENARY_MAX_ITER:
                raise ArchGeometryError(
                    "Khong khoanh duoc nghiem tham so day xich; kiem lai span_m/rise_m."
                )

    hi = lo * 2.0
    guard = 0
    while g(hi) > 0.0:
        hi *= 2.0
        guard += 1
        if guard > _CATENARY_MAX_ITER:
            raise ArchGeometryError(
                "Khong khoanh duoc nghiem tham so day xich; kiem lai span_m/rise_m."
            )

    for _ in range(_CATENARY_MAX_ITER):
        mid = 0.5 * (lo + hi)
        val = g(mid)
        if abs(val) <= _CATENARY_TOL * max(1.0, rise_m):
            return mid
        if val > 0.0:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def catenary_ordinate(x_m: float, span_m: float, rise_m: float, a_m: float) -> float:
    """Tung độ trục dây xích lộn ngược tại ``x_m`` với tham số ``a_m``."""
    u = x_m - span_m / 2.0
    return rise_m - a_m * (math.cosh(u / a_m) - 1.0)


def axis_ordinate(
    x_m: float,
    span_m: float,
    rise_m: float,
    axis_type: str = "PARABOLA_2ND_ORDER",
    a_m: float | None = None,
) -> float:
    """Tung độ trục vòm tại ``x_m`` theo dạng trục đã chọn."""
    if axis_type == "PARABOLA_2ND_ORDER":
        return parabola_ordinate(x_m, span_m, rise_m)
    if axis_type == "CATENARY":
        if a_m is None:
            a_m = catenary_parameter(span_m, rise_m)
        return catenary_ordinate(x_m, span_m, rise_m, a_m)
    raise ArchGeometryError(f"axis_type khong ho tro: {axis_type!r}")


def arch_axis_polyline(
    span_m,
    rise_m,
    axis_type: str = "PARABOLA_2ND_ORDER",
    point_count: int = 101,
) -> list[dict]:
    """Đa tuyến rời rạc hoá trục vòm.

    ``point_count`` phải LẺ và >= 3 để đỉnh vòm luôn là một điểm mẫu.
    Trả về list các dict ``{"x_m": ..., "y_m": ...}`` theo x tăng dần.
    """
    span, rise = validate_arch_params(span_m, rise_m, axis_type)
    _validate_point_count(point_count)

    a_m = catenary_parameter(span, rise) if axis_type == "CATENARY" else None
    n = point_count - 1
    points = []
    for i in range(point_count):
        x = span * i / n
        y = axis_ordinate(x, span, rise, axis_type, a_m)
        points.append({"x_m": x, "y_m": y})
    # Ép đúng điều kiện biên, khử sai số làm tròn tích luỹ.
    points[0]["y_m"] = 0.0
    points[-1]["y_m"] = 0.0
    points[-1]["x_m"] = span
    return points


def polyline_length_m(points: list[dict]) -> float:
    """Chiều dài đa tuyến (xấp xỉ chiều dài cung trục vòm)."""
    if len(points) < 2:
        raise ArchGeometryError("Cần ít nhất 2 điểm để tính chiều dài đa tuyến")
    total = 0.0
    for p, q in zip(points, points[1:]):
        total += math.hypot(q["x_m"] - p["x_m"], q["y_m"] - p["y_m"])
    return total


# ---------------------------------------------------------------------------
# Khoang vòm, mặt cầu, sườn vòm
# ---------------------------------------------------------------------------

def spandrel_column_lines(
    span_m,
    rise_m,
    deck_level_m,
    bay_count: int,
    axis_type: str = "PARABOLA_2ND_ORDER",
) -> list[dict]:
    """Các tuyến cột khoang vòm: vị trí x, cao độ lưng vòm, cao độ mặt cầu, chiều cao.

    ``bay_count`` là SỐ KHOANG trên toàn khẩu độ (phải chẵn, >= 2), nên có
    ``bay_count + 1`` tuyến; hai tuyến ở i = 0 và i = bay_count trùng chân vòm và
    có chiều cao bằng ``deck_level_m`` — chúng KHÔNG phải cột mà là phần chuyển
    tiếp về mố, nên được đánh dấu ``at_springing = True``.

    Cột càng gần chân vòm càng NGẮN; độ cứng ngang của cột tăng theo bậc ~1/h³,
    nên cột ngắn hút lực ngang không tương xứng. Đó là lý do vùng gần chân vòm
    trong thực tế thường là TƯỜNG KHOANG VÒM ĐẶC chứ không phải cột kéo dài.
    Module này chỉ trả về chiều cao; việc quyết định đổi sang tường là quyết
    định thiết kế, không phải phép tính.
    """
    span, rise = validate_arch_params(span_m, rise_m, axis_type)
    bays = _validate_count(bay_count, "bay_count", 2, even_required=True)
    deck = _validate_deck_level(deck_level_m, rise)

    a_m = catenary_parameter(span, rise) if axis_type == "CATENARY" else None
    lines = []
    for i in range(bays + 1):
        x = span * i / bays
        y_arch = axis_ordinate(x, span, rise, axis_type, a_m)
        if i == 0 or i == bays:
            y_arch = 0.0
        lines.append(
            {
                "index": i,
                "x_m": x,
                "y_arch_m": y_arch,
                "y_deck_m": deck,
                "height_m": deck - y_arch,
                "at_springing": i == 0 or i == bays,
            }
        )
    return lines


def rib_transverse_offsets_m(
    deck_width_m,
    rib_count: int,
    edge_inset_m: float = 0.0,
) -> list[float]:
    """Toạ độ z của các sườn vòm so với tim mặt cầu.

    ``rib_count = 1`` -> một sườn ở tim; ``rib_count = 2`` -> hai sườn đối xứng,
    lùi vào ``edge_inset_m`` tính từ mép mặt cầu.

    Đây là ẩn số cấp hệ thống (INC-006), không phải chi tiết: một sườn thì mặt
    cầu chịu XOẮN khi hoạt tải lệch một làn và toàn bộ mô men xoắn phải chạy
    xuống một sườn duy nhất; hai sườn thì bắt buộc có hệ giằng ngang LIÊN TỤC
    suốt chiều dài vòm và bài toán ổn định ngoài mặt phẳng trở thành bài toán
    ổn định của một hệ hai sườn có giằng.
    """
    width = _as_positive_float(deck_width_m, "deck_width_m")
    if isinstance(rib_count, bool) or not isinstance(rib_count, int):
        raise ArchGeometryError("rib_count phải là số nguyên")
    if rib_count not in (1, 2):
        raise ArchGeometryError(
            f"rib_count chỉ nhận 1 hoặc 2 (INC-006), nhận được {rib_count}"
        )
    try:
        inset = float(edge_inset_m)
    except (TypeError, ValueError) as exc:
        raise ArchGeometryError("edge_inset_m phải là số thực") from exc
    if inset < 0.0:
        raise ArchGeometryError("edge_inset_m không được âm")
    if rib_count == 1:
        return [0.0]
    offset = width / 2.0 - inset
    if offset <= 0.0:
        raise ArchGeometryError(
            f"edge_inset_m ({inset}) >= nua be rong mat cau ({width / 2.0}): "
            "hai suon vom trung nhau hoac lat nguoc."
        )
    return [-offset, offset]


# ---------------------------------------------------------------------------
# Lineage: geometry hash tái lập được (BRD-004, tiêu chí nghiệm thu #2)
# ---------------------------------------------------------------------------

def _canonical_json(obj) -> str:
    """JSON chính tắc — khớp từng byte với ``canonical_json`` của state.py.

    Cùng quy ước ``sort_keys=True, separators=(",", ":"), ensure_ascii=False``
    như production (bridge_evolution/state.py) để hai hệ hash đọc được nhau.
    """
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _normalized_hash_inputs(
    span_m,
    rise_m,
    deck_level_m,
    bay_count,
    axis_type,
    deck_width_m,
    rib_count,
    rib_edge_inset_m,
    point_count,
    construction_stage_id,
) -> dict:
    """Kiểm tra rồi CHUẨN HOÁ bộ tham số đầu vào về kiểu chính tắc để hash.

    Chuẩn hoá: số thực -> ``float``, số nguyên -> ``int``, enum/chuỗi -> ``str``,
    tuỳ chọn vắng mặt -> ``None``. Nhờ đó ``2`` và ``2.0`` cho ``span_m`` băm ra
    cùng giá trị, còn kiểu sai thì raise thay vì bị ép ngầm.

    Fail-closed và CHẶT hơn đường dựng hình cũ ở hai điểm (có chủ đích, vì mọi
    tham số dưới đây đều tham gia geometry_hash nên không được mang kiểu tuỳ
    tiện): ``rib_count``/``rib_edge_inset_m`` luôn bị kiểm tra kể cả khi
    ``deck_width_m`` là None, và ``construction_stage_id`` phải là chuỗi không
    rỗng (INC-004: một phương án là hình dạng CỘNG giai đoạn).
    """
    span, rise = validate_arch_params(span_m, rise_m, axis_type)
    n_points = _validate_point_count(point_count)
    bays = _validate_count(bay_count, "bay_count", 2, even_required=True)
    deck = _validate_deck_level(deck_level_m, rise)

    if isinstance(rib_count, bool) or not isinstance(rib_count, int):
        raise ArchGeometryError("rib_count phải là số nguyên")
    if rib_count not in (1, 2):
        raise ArchGeometryError(
            f"rib_count chỉ nhận 1 hoặc 2 (INC-006), nhận được {rib_count}"
        )
    try:
        inset = float(rib_edge_inset_m)
    except (TypeError, ValueError) as exc:
        raise ArchGeometryError("rib_edge_inset_m phải là số thực") from exc
    if not math.isfinite(inset) or inset < 0.0:
        raise ArchGeometryError(
            f"rib_edge_inset_m phải hữu hạn và không âm, nhận được {inset!r}"
        )

    width: float | None = None
    if deck_width_m is not None:
        # Dùng đúng validator của đường dựng hình để hai đường không lệch nhau.
        rib_transverse_offsets_m(deck_width_m, rib_count, inset)
        width = float(deck_width_m)

    if not isinstance(construction_stage_id, str) or not construction_stage_id.strip():
        raise ArchGeometryError(
            "construction_stage_id phải là chuỗi không rỗng, nhận được "
            f"{construction_stage_id!r}"
        )

    return {
        "span_m": span,
        "rise_m": rise,
        "deck_level_m": deck,
        "bay_count": bays,
        "axis_type": str(axis_type),
        "deck_width_m": width,
        "rib_count": int(rib_count),
        "rib_edge_inset_m": inset,
        "point_count": n_points,
        "construction_stage_id": construction_stage_id,
    }


def _hash_of_normalized(hash_inputs: dict) -> str:
    """SHA-256 hex của payload lineage đã chuẩn hoá (không tự kiểm tra lại)."""
    payload = {
        "generator_id": GENERATOR_ID,
        "generator_version": GENERATOR_VERSION,
        "params": hash_inputs,
    }
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def geometry_hash(params: dict) -> str:
    """Hash tái lập được của MỘT phương án hình học, tính trên THAM SỐ ĐẦU VÀO.

    Trả về SHA-256 hex (64 ký tự thường) của canonical JSON — cùng quy ước
    ``sort_keys=True, separators=(",", ":"), ensure_ascii=False`` như
    ``input_hash`` production (bridge_evolution/state.py) — của dict::

        {"generator_id": GENERATOR_ID,
         "generator_version": GENERATOR_VERSION,
         "params": <tham số đã validate + chuẩn hoá kiểu>}

    VÌ SAO hash trên tham số đầu vào chứ không trên ``axis_points``: đa tuyến
    là DẪN XUẤT — toạ độ của nó mang sai số làm tròn float tích luỹ, phụ thuộc
    thứ tự phép cộng và có thể đổi theo phiên bản Python/nền tảng, trong khi
    bộ tham số đã chuẩn hoá là biểu diễn chính tắc, ổn định từng byte. Đổi
    thuật toán dựng hình mà giữ nguyên tham số thì phải nâng
    ``GENERATOR_VERSION``, và hash đổi theo — đó là lý do phiên bản nằm trong
    payload.

    ``params`` bắt buộc có ``span_m, rise_m, deck_level_m, bay_count``; các
    khoá còn lại nhận default ĐÚNG BẰNG default của :func:`arch_geometry`
    (``axis_type, deck_width_m, rib_count, rib_edge_inset_m, point_count,
    construction_stage_id``). Khoá lạ hoặc thiếu khoá bắt buộc -> raise
    :class:`ArchGeometryError` (fail-closed, không đoán). Metadata lineage
    (``parent_geometry_hash``, ``generation_action``) KHÔNG tham gia hash —
    giống production loại ``provenance`` khỏi ``input_hash``: hai lần sinh ra
    cùng một hình từ hai nhánh tiến hoá khác nhau vẫn là cùng một hình.

    Hash này là ĐỊNH DANH hình học mức F0 IDEA, không phải kết luận kỹ thuật.
    """
    if not isinstance(params, dict):
        raise ArchGeometryError(
            f"params phải là dict, nhận được {type(params).__name__}"
        )
    known = set(_HASH_PARAM_REQUIRED) | set(_HASH_PARAM_DEFAULTS)
    unknown = sorted(set(params) - known)
    if unknown:
        raise ArchGeometryError(
            f"Khoá lạ không thuộc bộ tham số hình học: {unknown}"
        )
    missing = sorted(k for k in _HASH_PARAM_REQUIRED if k not in params)
    if missing:
        raise ArchGeometryError(f"Thiếu tham số bắt buộc để hash: {missing}")
    merged = {**_HASH_PARAM_DEFAULTS, **params}
    return _hash_of_normalized(_normalized_hash_inputs(**merged))


def geometry_case_id(geometry_hash: str) -> str:
    """Case id ngắn ``"ARCH-" + 16 hex đầu`` của một geometry_hash hợp lệ.

    Cùng quy ước với ``make_case_id`` production (``"BT-" + 16 hex đầu``,
    CASE_ID_HASH_HEX = 16 trong bridge_evolution/state.py); tiền tố ARCH- để
    không lẫn với case Super-T. Full SHA-256 trong khối lineage vẫn là định
    danh chuẩn. Đầu vào không phải chuỗi 64 hex thường -> raise
    :class:`ArchGeometryError`.
    """
    if not isinstance(geometry_hash, str) or not _HEX64_RE.match(geometry_hash):
        raise ArchGeometryError(
            "geometry_hash phải là chuỗi 64 ký tự hex thường (SHA-256 hex), "
            f"nhận được {geometry_hash!r}"
        )
    return "ARCH-" + geometry_hash[:_CASE_ID_HASH_HEX]


def _validate_lineage_fields(
    parent_geometry_hash: str | None, generation_action: str
) -> tuple[str | None, str]:
    """Kiểm tra metadata lineage; sai dạng -> raise, không tự sửa."""
    if parent_geometry_hash is not None and (
        not isinstance(parent_geometry_hash, str)
        or not _HEX64_RE.match(parent_geometry_hash)
    ):
        raise ArchGeometryError(
            "parent_geometry_hash phải là None hoặc chuỗi 64 ký tự hex thường, "
            f"nhận được {parent_geometry_hash!r}"
        )
    if not isinstance(generation_action, str) or not generation_action.strip():
        raise ArchGeometryError(
            f"generation_action phải là chuỗi không rỗng, nhận được "
            f"{generation_action!r}"
        )
    return parent_geometry_hash, generation_action


# ---------------------------------------------------------------------------
# Hàm gọi chính
# ---------------------------------------------------------------------------

def arch_geometry(
    span_m,
    rise_m,
    deck_level_m,
    bay_count: int,
    axis_type: str = "PARABOLA_2ND_ORDER",
    deck_width_m=None,
    rib_count: int = 2,
    rib_edge_inset_m: float = 0.0,
    point_count: int = 101,
    construction_stage_id: str = "S7_SERVICE",
    *,
    parent_geometry_hash: str | None = None,
    generation_action: str = "INITIAL",
) -> dict:
    """Dựng toàn bộ hình học vòm chạy trên từ tham số.

    CHỈ HÌNH HỌC. Không trường nào trong dict trả về là đại lượng nội lực, ứng
    suất, chuyển vị hay hiệu năng — xem docstring đầu module.

    ``construction_stage_id`` được mang theo và trả lại nguyên vẹn, KHÔNG dùng
    để tính gì cả. Nó có mặt vì grammar bắt buộc phải mang trường giai đoạn ngay
    từ định nghĩa (BRD-004 / INC-004): một phương án của họ này không phải một
    hình dạng, nó là một hình dạng CỘNG một giai đoạn. Hình học dựng ở đây là
    hình học hoàn thiện; các giai đoạn hẫng có sơ đồ và tiết diện khác hẳn.

    Lineage (BRD-004, tiêu chí #2): kết quả mang khối ``"lineage"`` gồm
    ``geometry_hash`` (xem :func:`geometry_hash` — hash trên tham số đầu vào đã
    chuẩn hoá, KHÔNG trên đa tuyến), ``parent_geometry_hash`` (None cho phương
    án gốc; nếu khác None phải là chuỗi 64 hex thường), ``generation_action``
    (chuỗi không rỗng, mặc định ``"INITIAL"``), cặp generator id/version và
    ``hash_inputs`` — đúng bộ tham số đã băm, để bên kiểm tra tái lập hash mà
    không cần gọi lại module này. Hai trường lineage chỉ là METADATA phả hệ,
    không tham gia hash và không đổi hình học.
    """
    _validate_lineage_fields(parent_geometry_hash, generation_action)
    hash_inputs = _normalized_hash_inputs(
        span_m=span_m,
        rise_m=rise_m,
        deck_level_m=deck_level_m,
        bay_count=bay_count,
        axis_type=axis_type,
        deck_width_m=deck_width_m,
        rib_count=rib_count,
        rib_edge_inset_m=rib_edge_inset_m,
        point_count=point_count,
        construction_stage_id=construction_stage_id,
    )

    span, rise = validate_arch_params(span_m, rise_m, axis_type)
    axis = arch_axis_polyline(span, rise, axis_type, point_count)
    columns = spandrel_column_lines(span, rise, deck_level_m, bay_count, axis_type)
    interior = [c for c in columns if not c["at_springing"]]

    ribs = None
    if deck_width_m is not None:
        ribs = rib_transverse_offsets_m(deck_width_m, rib_count, rib_edge_inset_m)

    a_m = catenary_parameter(span, rise) if axis_type == "CATENARY" else None

    return {
        "claim_level": CLAIM_LEVEL,
        "computes_internal_forces": False,
        "runtime_can_evaluate_this_family": False,
        "units": "m",
        "axis_type": axis_type,
        "construction_stage_id": construction_stage_id,
        "span_m": span,
        "rise_m": rise,
        "span_rise_ratio_L_over_f": span / rise,
        "catenary_parameter_a_m": a_m,
        "springing_left": {"x_m": 0.0, "y_m": 0.0},
        "springing_right": {"x_m": span, "y_m": 0.0},
        "crown": {"x_m": span / 2.0, "y_m": rise},
        "axis_points": axis,
        "axis_arc_length_m": polyline_length_m(axis),
        "bay_count": columns[-1]["index"],
        "bay_length_m": span / columns[-1]["index"],
        "deck_level_m": columns[0]["y_deck_m"],
        "spandrel_column_lines": columns,
        "interior_column_count": len(interior),
        "min_interior_column_height_m": min(c["height_m"] for c in interior),
        "max_interior_column_height_m": max(c["height_m"] for c in interior),
        "deck_width_m": None if deck_width_m is None else float(deck_width_m),
        "rib_count": None if ribs is None else rib_count,
        "rib_transverse_offsets_m": ribs,
        "lineage": {
            "geometry_hash": _hash_of_normalized(hash_inputs),
            "parent_geometry_hash": parent_geometry_hash,
            "generation_action": generation_action,
            "generator_id": GENERATOR_ID,
            "generator_version": GENERATOR_VERSION,
            "hash_inputs": hash_inputs,
        },
        "notes_vi": [
            "Toa do, khong phai ket luan ky thuat. Muc claim F0 IDEA.",
            "Chieu cao cot khoang vom giam don dieu ve hai chan; vung gan chan "
            "vom nen la tuong khoang vom dac chu khong phai cot ngan.",
            "Hinh hoc nay la hinh hoc TRANG THAI HOAN THIEN; giai doan duc/lap "
            "hang co so do va tiet dien khac han.",
        ],
    }
