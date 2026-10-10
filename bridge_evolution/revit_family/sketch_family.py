"""Bộ sinh mã C# cho **thế giới SKETCH** — năm cấu kiện cầu, mọi ràng buộc đã đo.

===========================================================================
GIÁ TRỊ CỐT LÕI: **không thể sinh ra C# mà ta đã ĐO là hỏng**
===========================================================================
Module này KHÔNG lặp lại quy tắc của :mod:`~bridge_evolution.revit_family.worlds`
hay :mod:`~bridge_evolution.revit_family.csharp`; nó *dùng* chúng. Việc riêng
của nó là biến **ràng buộc hình học đã đo** thành phép kiểm chạy trong Python,
trước khi một ký tự C# nào được phát ra.

Năm hàm, năm ánh xạ lấy thẳng từ ``docs/revit_family_capability.md`` §6:

======================  ==================  ================================
Hàm                     Phép Revit          Ràng buộc mã hoá thành RAISE
======================  ==================  ================================
:func:`arch_rib_segment`   ``NewSweptBlend``   [S1] path phải là ``Reference``
                                               của một ``ModelCurve`` đã tồn
                                               tại; ba điểm thẳng hàng thì
                                               ``Arc.Create`` ném -> chặn
:func:`tapered_pier_shaft` ``NewBlend``        [B1] hai profile PHẢI khác cao độ
:func:`revolved_member`    ``NewRevolution``   [R1] trục PHẢI nằm trong mặt
                                               phẳng phác thảo
:func:`prismatic_member`   ``NewExtrusion``    work plane nghiêng phải xin
                                               thêm phép ``InclinedWorkPlane``
:func:`void_cut`           ``NewExtrusion``    [S2] void trong SKETCH **KHÔNG
                           (``isSolid=false``) TỰ CẮT** -> chặn mặc định
======================  ==================  ================================

BA RÀNG BUỘC ÍT AI NHỚ, ĐỀU ĐÃ ĐO
---------------------------------
* **[S1]** ``NewSweptBlend`` nhận ``Reference``, KHÔNG nhận ``Curve``. Lỗi biên
  dịch nguyên văn: *"Argument 2: cannot convert from 'Autodesk.Revit.DB.Curve'
  to 'Autodesk.Revit.DB.Reference'"*. Vì vậy :func:`arch_rib_segment` **luôn**
  phát ``NewModelCurve`` trước rồi truyền ``mc.GeometryCurve.Reference``. Tin
  vui đi kèm: path **cong được** (đã đo với ``Arc``), nên một đốt vòm cong tiết
  diện thuôn là MỘT phép, không phải chia đoạn.
* **[S2]** Void trong family SKETCH **không cắt khối đặc**, và nguy hiểm ở chỗ
  nó IM LẶNG: ``NewExtrusion(false, ...)`` trả về đối tượng bình thường, void
  có mặt trong file, chỉ đo thể tích mới lộ. Cách làm void cắt được thì CHƯA
  ĐO. :func:`void_cut` do đó **raise mặc định**.
* **[S3]** Template family **ship sẵn hình học** (``Metric Structural Framing``
  có sẵn một Extrusion 0.150 m³ không ai tạo). Mọi thân mã ở đây mở đầu bằng
  đoạn quét-và-xoá ``GenericForm`` có sẵn, nếu không thì con số đếm được sau
  này bị nhiễm khối rác của template.

HỆ TOẠ ĐỘ
---------
Vào bằng **mét**, hệ **cầu** ``(x dọc, y CAO ĐỘ, z ngang)`` — cùng quy ước với
:func:`~bridge_evolution.revit_family.csharp.xyz`, hàm lo phần đổi feet và hoán
vị sang trục Revit. Nói riêng: ``y`` là cao độ, nên ràng buộc [B1] *"hai profile
khác cao độ"* trong module này là điều kiện trên **``y``**, dù tài liệu gốc viết
theo ``z`` của Revit.

VÌ SAO KIỂM TRONG PYTHON CHỨ KHÔNG ĐỂ REVIT NÉM
-----------------------------------------------
Revit chạy trong tiến trình khác, qua MCP, mất hàng chục giây một vòng, và
thông báo lỗi của nó không nói được *ràng buộc nào* bị vi phạm. Ba điểm thẳng
hàng thì ``Arc.Create`` ném ở tận trong Revit; ở đây nó là một ``ValueError``
nói thẳng "sagitta 0.0000 m ≤ dung sai" và chỉ ra ``allow_straight=True``.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Sequence

from .csharp import (
    CLAIM_LEVEL_PARAM,
    DEFAULT_CLAIM_STATEMENT,
    FT,
    CSharpStructureError,
    guarded_family_scaffold,
    m_to_ft,
    xyz,
)
# Cùng gói, cố ý dùng bộ bỏ-chú-thích NỘI BỘ của csharp.py: "đâu là lệnh, đâu
# là chú thích" phải theo ĐÚNG MỘT quy tắc trong cả gói, y như quy tắc in số.
from .csharp import _strip_cs_literals_and_comments
# Cùng gói, cố ý dùng hàm in số NỘI BỘ của csharp.py: literal double trong C#
# phải theo ĐÚNG MỘT quy tắc. Viết một bộ định dạng thứ hai ở đây là dựng lên
# đúng cái "quy tắc song song" mà gói này tồn tại để tránh.
from .csharp import _num as _cs_num
from .worlds import (
    RevitFamilyCapabilityError,
    require_operations,
)

__all__ = [
    "REVIT_SHORT_CURVE_TOL_M",
    "SAG_TOL_M",
    "PLANE_TOL_M",
    "PLANE_TOL_COS",
    "SKETCH_DECLARED_OVERLOADS",
    "SketchFamilyError",
    "DegenerateGeometryError",
    "CollinearArcError",
    "BlendElevationError",
    "RevolveAxisError",
    "VoidDoesNotCutError",
    "BoxSpec",
    "arch_rib_segment",
    "tapered_pier_shaft",
    "revolved_member",
    "prismatic_member",
    "void_cut",
]

Vec3 = tuple[float, float, float]

# ---------------------------------------------------------------------------
# Dung sai
# ---------------------------------------------------------------------------

#: Dung sai "đường quá ngắn" CÔNG BỐ của Revit: 1/256 ft ~ 1.1906 mm.
#: ĐÂY KHÔNG PHẢI SỐ ĐO của đợt RFC-1.1.0 — nó là hằng số của Revit, dùng ở đây
#: làm ngưỡng **CHẶN**. Chặn nhầm một hình hợp lệ nhưng bé tí thì mất một vòng
#: sửa; để Revit ném "Curve is too short" thì mất một vòng MCP và một thông báo
#: lỗi không nói được ràng buộc nào vỡ.
REVIT_SHORT_CURVE_TOL_M = (1.0 / 256.0) / FT

#: Sagitta tối thiểu để ba điểm được coi là dựng được thành ``Arc``.
#: Dùng chung ngưỡng với đường ngắn: một cung có mũi tên bé hơn dung sai của
#: chính Revit thì bán kính của nó vô nghĩa.
SAG_TOL_M = REVIT_SHORT_CURVE_TOL_M

#: Dung sai khoảng cách khi kiểm "điểm nằm trong mặt phẳng" (1 micromet).
PLANE_TOL_M = 1.0e-6

#: Dung sai tích vô hướng khi kiểm "hướng vuông góc pháp tuyến" (~0.00006 độ).
PLANE_TOL_COS = 1.0e-6

#: Dưới ngưỡng này thì hai hướng coi như song song (sin của góc giữa chúng).
_PARALLEL_SIN_TOL = 1.0e-6

_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9]{0,23}$")

#: Overload API mà RFC-1.1.0 **KHÔNG ghi lại** — giả định khai báo tường minh.
#:
#: Cùng kỷ luật với
#: :data:`~bridge_evolution.revit_family.adaptive_family.DECLARED_OVERLOADS`:
#: tài liệu ghi *kết quả* (chạy được / hỏng / id đối tượng), hiếm khi ghi *chữ
#: ký hàm*. Cổng năng lực quyết định **được dùng phép nào**; chữ ký cụ thể là
#: **giả định**, và giả định phải có TÊN, có CHỖ, và hiện ra trong chính mã C#
#: phát ra (``// GIA DINH OVERLOAD: <tên>(...)``) để người đọc bên Revit phân
#: biệt được đâu là số đo, đâu là suy đoán. :func:`_self_check` bắt buộc điều
#: đó trên chuỗi vừa sinh.
SKETCH_DECLARED_OVERLOADS: tuple[tuple[str, str], ...] = (
    ("NewExtrusion",
     "FamilyItemFactory.NewExtrusion(bool isSolid, CurveArrArray, SketchPlane, "
     "double end) — RFC-1.1.0 §2 ghi OK va id doi tuong, khong ghi chu ky"),
    ("NewBlend",
     "FamilyItemFactory.NewBlend(bool isSolid, CurveArray top, CurveArray base, "
     "SketchPlane) — §2 chi ghi 'NewBlend | OK | id=2939'; THU TU doi so "
     "(TOP truoc, BASE sau) la phan gia dinh nang nhat o day"),
    ("NewRevolution",
     "FamilyItemFactory.NewRevolution(bool isSolid, CurveArrArray, SketchPlane, "
     "Line axis, double startAngle, double endAngle) — §2 ghi ket qua va rang "
     "buoc [R1], khong ghi chu ky"),
    ("NewSweptBlend",
     "FamilyItemFactory.NewSweptBlend(bool isSolid, Reference path, "
     "SweepProfile bottom, SweepProfile top) — §2 [S1] cho thay dung bon doi so "
     "nay va CAM truyen Curve o vi tri 2, nhung khong ghi profBottom/profTop "
     "duoc dung tu dau"),
    ("NewCurveLoopsProfile",
     "Application.Create.NewCurveLoopsProfile(CurveArrArray) tra SweepProfile — "
     "[S1] dung profBottom/profTop ma khong ghi cach tao chung; day la duong "
     "khong-deprecated cua Revit 2026"),
)


# ---------------------------------------------------------------------------
# Lỗi — đều là ValueError, cùng gốc với cổng năng lực
# ---------------------------------------------------------------------------

class SketchFamilyError(RevitFamilyCapabilityError):
    """Gốc của mọi lỗi dựng hình thế giới SKETCH.

    MRO: ``SketchFamilyError -> RevitFamilyCapabilityError -> ValueError``.
    Cùng gốc với cổng năng lực là cố ý: người gọi bắt một loại lỗi duy nhất
    cho cả "phép này sai thế giới" lẫn "hình học này vi phạm ràng buộc đã đo".
    """


class DegenerateGeometryError(SketchFamilyError):
    """Hình học suy biến: dài bằng 0, tiết diện âm, đa giác không phẳng, hướng song song."""


class CollinearArcError(SketchFamilyError):
    """Ba điểm THẲNG HÀNG — ``Arc.Create`` sẽ ném. Xem ``allow_straight``."""


class BlendElevationError(SketchFamilyError):
    """[B1] ``NewBlend`` đòi hai profile ở CAO ĐỘ KHÁC NHAU."""


class RevolveAxisError(SketchFamilyError):
    """[R1] ``NewRevolution`` đòi trục NẰM TRONG mặt phẳng phác thảo."""


class VoidDoesNotCutError(SketchFamilyError):
    """[S2] Void trong thế giới SKETCH ĐÃ ĐO LÀ KHÔNG CẮT khối đặc."""


# ---------------------------------------------------------------------------
# Vector thuần Python — không phụ thuộc thư viện ngoài
# ---------------------------------------------------------------------------

_UP_BRIDGE: Vec3 = (0.0, 1.0, 0.0)      # y = CAO ĐỘ (hệ cầu)
_LONG_BRIDGE: Vec3 = (1.0, 0.0, 0.0)    # x = DỌC cầu
_TRANS_BRIDGE: Vec3 = (0.0, 0.0, 1.0)   # z = NGANG cầu


def _point(value: Sequence[float], what: str) -> Vec3:
    """Ép một bộ ba số hữu hạn. Raise ngay nếu sai kiểu/độ dài/nan/inf."""
    if isinstance(value, (str, bytes)) or not hasattr(value, "__len__"):
        raise DegenerateGeometryError(
            f"{what} phải là bộ ba số (x, y, z) tính bằng MÉT theo hệ cầu "
            f"(x dọc, y CAO ĐỘ, z ngang), nhận {type(value).__name__}")
    if len(value) != 3:
        raise DegenerateGeometryError(
            f"{what} phải có đúng 3 thành phần, nhận {len(value)}")
    out = []
    for i, raw in enumerate(value):
        try:
            num = float(raw)
        except (TypeError, ValueError):
            raise DegenerateGeometryError(
                f"{what}[{i}] không phải số: {raw!r}") from None
        if not math.isfinite(num):
            raise DegenerateGeometryError(
                f"{what}[{i}] = {raw!r} không hữu hạn. Không bao giờ phát "
                f"'NaN'/'Infinity' vào mã C#.")
        out.append(num)
    return (out[0], out[1], out[2])


def _positive(value: float, what: str) -> float:
    """Ép một kích thước dương và lớn hơn dung sai đường ngắn của Revit."""
    try:
        num = float(value)
    except (TypeError, ValueError):
        raise DegenerateGeometryError(f"{what} không phải số: {value!r}") from None
    if not math.isfinite(num):
        raise DegenerateGeometryError(f"{what} = {value!r} không hữu hạn.")
    if num <= REVIT_SHORT_CURVE_TOL_M:
        raise DegenerateGeometryError(
            f"{what} = {num:.9f} m <= dung sai đường ngắn của Revit "
            f"({REVIT_SHORT_CURVE_TOL_M:.7f} m = 1/256 ft). Cạnh profile ngắn "
            f"hơn ngưỡng đó thì Revit từ chối đường cong — chặn ở đây để không "
            f"mất một vòng MCP.")
    return num


def _sub(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _add(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _scale(a: Vec3, k: float) -> Vec3:
    return (a[0] * k, a[1] * k, a[2] * k)


def _dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a: Vec3, b: Vec3) -> Vec3:
    return (a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _length(a: Vec3) -> float:
    return math.sqrt(_dot(a, a))


def _unit(a: Vec3, what: str) -> Vec3:
    """Chuẩn hoá một vector; raise nếu nó gần bằng 0."""
    norm = _length(a)
    if norm <= _PARALLEL_SIN_TOL:
        raise DegenerateGeometryError(
            f"{what} có độ dài {norm:.3e} — coi như vector 0, không xác định "
            f"được hướng.")
    return _scale(a, 1.0 / norm)


def _auto_up_hint(axis_unit: Vec3) -> Vec3:
    """Hướng "lên" tham chiếu mặc định để dựng hệ trục tiết diện.

    Mặc định là ``y`` (cao độ). Cấu kiện gần THẲNG ĐỨNG (trụ, cột) thì ``y``
    song song với trục nên vô dụng — lúc đó lấy ``x`` (dọc cầu). Ngưỡng 0.9
    (~26 độ) chọn rộng tay để không rơi vào vùng hệ trục xoay nhạy.
    """
    if abs(_dot(axis_unit, _UP_BRIDGE)) <= 0.9:
        return _UP_BRIDGE
    return _LONG_BRIDGE


def _frame(axis: Vec3, up_hint: Vec3 | None, what: str) -> tuple[Vec3, Vec3]:
    """Hệ trục TIẾT DIỆN ``(u, v)`` vuông góc ``axis``.

    ``u`` là hướng **rộng** (vuông góc cả trục lẫn ``up_hint``), ``v`` là hướng
    **cao** (``axis × u``). Với dầm nằm ngang và ``up_hint`` mặc định: ``u``
    ngang cầu, ``v`` thẳng đứng. Với cột thẳng đứng: ``u`` ngang cầu, ``v`` dọc
    cầu — vẫn xác định, chỉ khác ý nghĩa, và docstring của hàm gọi nói rõ.
    """
    n = _unit(axis, f"{what}: trục")
    ref = _unit(up_hint if up_hint is not None else _auto_up_hint(n),
                f"{what}: up_hint_m")
    c = _cross(ref, n)
    s = _length(c)
    if s <= _PARALLEL_SIN_TOL:
        raise DegenerateGeometryError(
            f"{what}: up_hint_m ({ref[0]:.4f}, {ref[1]:.4f}, {ref[2]:.4f}) song "
            f"song với trục ({n[0]:.4f}, {n[1]:.4f}, {n[2]:.4f}) — sin góc giữa "
            f"= {s:.3e}. Không dựng được hệ trục tiết diện. Truyền up_hint_m "
            f"khác (ví dụ (0, 0, 1) = ngang cầu).")
    u = _scale(c, 1.0 / s)
    return u, _cross(n, u)


def _is_axis_aligned(direction: Vec3) -> bool:
    """Hướng có trùng một trục chính của hệ cầu không (sai số ``PLANE_TOL_COS``)."""
    n = _unit(direction, "hướng")
    return any(abs(abs(_dot(n, axis)) - 1.0) <= PLANE_TOL_COS
               for axis in (_LONG_BRIDGE, _UP_BRIDGE, _TRANS_BRIDGE))


def _polygon_normal(points: Sequence[Vec3]) -> Vec3:
    """Pháp tuyến đa giác theo phương pháp Newell — bền với đa giác lồi lẫn lõm."""
    nx = ny = nz = 0.0
    count = len(points)
    for i in range(count):
        a = points[i]
        b = points[(i + 1) % count]
        nx += (a[1] - b[1]) * (a[2] + b[2])
        ny += (a[2] - b[2]) * (a[0] + b[0])
        nz += (a[0] - b[0]) * (a[1] + b[1])
    return (nx, ny, nz)


# ---------------------------------------------------------------------------
# Phát literal C#
# ---------------------------------------------------------------------------

def _dir_cs(direction: Vec3) -> str:
    """Vector HƯỚNG (không đơn vị) hệ cầu -> literal ``new XYZ`` hệ Revit.

    Đi vòng qua :func:`~bridge_evolution.revit_family.csharp.xyz` sau khi chia
    cho :data:`FT` là CỐ Ý: phép hoán vị trục ``(x, y, z)_cầu -> XYZ(x, z, y)``
    chỉ được viết ở MỘT chỗ trong gói này. Chia rồi nhân lại là sai số cỡ
    1e-16, còn chép lại phép hoán vị là sai số cỡ một cây cầu lật ngang.
    """
    ux, uy, uz = _unit(direction, "vector hướng")
    return xyz(ux / FT, uy / FT, uz / FT)


def _ft(value_m: float) -> str:
    """Số đo MÉT -> literal ``double`` C# tính bằng FEET."""
    return _cs_num(m_to_ft(value_m))


def _fmt_pt(p: Vec3) -> str:
    """Điểm hệ cầu -> chuỗi ASCII cho CHÚ THÍCH C# (mét, 4 chữ số)."""
    return f"({p[0]:.4f}, {p[1]:.4f}, {p[2]:.4f})"


def _purge_template_geometry_cs() -> list[str]:
    """[S3] Xoá hình học SHIP SẴN của template trước khi dựng."""
    return [
        "// --- [S3] template family SHIP SAN hinh hoc ---",
        "// Do tren FAM_DotVanhVom.rfa: template 'Metric Structural Framing -",
        "// Beams and Braces' co san mot Extrusion id=999 vol=0.150 m3 khong ai",
        "// tao. Khong xoa thi moi con so dem GenericForm ve sau deu bi nhiem",
        "// khoi rac cua template.",
        "var tplForms = new FilteredElementCollector(fd)"
        ".OfClass(typeof(GenericForm)).ToElementIds();",
        "if (tplForms.Count > 0) { fd.Delete(tplForms); }",
    ]


def _rect_loop_cs(tag: str, center: Vec3, u: Vec3, v: Vec3,
                  width_m: float, height_m: float) -> list[str]:
    """Một vòng kín HÌNH CHỮ NHẬT: 4 ``Line.CreateBound`` trong một ``CurveArray``.

    ``width_m`` đo dọc ``u``, ``height_m`` đo dọc ``v``, tâm tại ``center``.
    Thứ tự đỉnh ngược chiều kim đồng hồ nhìn từ phía ``u × v``.
    """
    hw = width_m * 0.5
    hh = height_m * 0.5
    corners = [
        _add(center, _add(_scale(u, hw), _scale(v, hh))),
        _add(center, _add(_scale(u, -hw), _scale(v, hh))),
        _add(center, _add(_scale(u, -hw), _scale(v, -hh))),
        _add(center, _add(_scale(u, hw), _scale(v, -hh))),
    ]
    lines = [
        f"// profile {tag}: {width_m:.4f} x {height_m:.4f} m, tam {_fmt_pt(center)} m",
    ]
    for i, corner in enumerate(corners):
        lines.append(f"XYZ {tag}P{i} = {xyz(*corner)};")
    lines.append(f"CurveArray {tag}Loop = new CurveArray();")
    for i in range(4):
        lines.append(
            f"{tag}Loop.Append(Line.CreateBound({tag}P{i}, {tag}P{(i + 1) % 4}));")
    return lines


def _throw_if_null_cs(var: str, what: str) -> str:
    """Một dòng C#: nil thì ``throw`` để ``catch`` của khuôn đóng family document.

    Cố ý KHÔNG dùng ``return``: ``return`` trong thân mã nằm giữa
    ``using (Transaction)`` nên nó bỏ qua khối ``catch`` và **bỏ ngỏ family
    document đang mở**. ``throw`` thì rơi đúng vào ``catch`` của
    :func:`~bridge_evolution.revit_family.csharp.family_scaffold`, chỗ có
    ``fd.Close(false)``.
    """
    return (f'if ({var} == null) {{ throw new InvalidOperationException('
            f'"{what} tra ve null"); }}')


# ---------------------------------------------------------------------------
# BoxSpec — khối lăng trụ tiết diện chữ nhật
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BoxSpec:
    """Một khối lăng trụ tiết diện chữ nhật, mô tả bằng trục + tiết diện.

    Mọi kiểm tra chạy NGAY trong ``__post_init__`` — điểm sớm nhất có thể.
    Một ``BoxSpec`` dựng được là một khối Revit nhận được (về mặt hình học);
    không có trạng thái "hợp lệ một nửa" đi tiếp xuống bộ phát mã.

    Attributes:
        start_m: điểm đầu trục ``(x, y, z)`` mét, hệ cầu (y = cao độ).
        end_m: điểm cuối trục.
        width_m: bề rộng tiết diện, đo dọc ``u`` (xem :func:`_frame`).
        height_m: bề cao tiết diện, đo dọc ``v``.
        up_hint_m: hướng "lên" tham chiếu; ``None`` = tự chọn.
        name: tên ASCII, dùng làm tiền tố BIẾN C# nên phải là định danh hợp lệ.
    """

    start_m: Vec3
    end_m: Vec3
    width_m: float
    height_m: float
    up_hint_m: Vec3 | None = None
    name: str = "Box"

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not _NAME_RE.match(self.name):
            raise DegenerateGeometryError(
                f"BoxSpec.name = {self.name!r} không hợp lệ. Tên này thành tiền "
                f"tố BIẾN C# nên phải khớp {_NAME_RE.pattern} (ASCII, bắt đầu "
                f"bằng chữ cái, tối đa 24 ký tự).")
        object.__setattr__(self, "start_m",
                           _point(self.start_m, f"BoxSpec({self.name}).start_m"))
        object.__setattr__(self, "end_m",
                           _point(self.end_m, f"BoxSpec({self.name}).end_m"))
        object.__setattr__(self, "width_m",
                           _positive(self.width_m, f"BoxSpec({self.name}).width_m"))
        object.__setattr__(self, "height_m",
                           _positive(self.height_m, f"BoxSpec({self.name}).height_m"))
        if self.up_hint_m is not None:
            object.__setattr__(
                self, "up_hint_m",
                _point(self.up_hint_m, f"BoxSpec({self.name}).up_hint_m"))
        if self.length_m <= REVIT_SHORT_CURVE_TOL_M:
            raise DegenerateGeometryError(
                f"BoxSpec({self.name}): trục dài {self.length_m:.9f} m <= dung "
                f"sai đường ngắn của Revit ({REVIT_SHORT_CURVE_TOL_M:.7f} m). "
                f"start_m {_fmt_pt(self.start_m)} và end_m "
                f"{_fmt_pt(self.end_m)} trùng nhau hoặc quá gần.")
        # ép dựng hệ trục tiết diện ngay: up_hint song song trục là lỗi lúc
        # DỰNG SPEC, không phải lúc phát mã.
        _ = self.frame

    @property
    def length_m(self) -> float:
        """Chiều dài trục, mét."""
        return _length(_sub(self.end_m, self.start_m))

    @property
    def axis_m(self) -> Vec3:
        """Hướng trục đã chuẩn hoá (cũng là pháp tuyến mặt phẳng phác thảo)."""
        return _unit(_sub(self.end_m, self.start_m), f"BoxSpec({self.name}): trục")

    @property
    def frame(self) -> tuple[Vec3, Vec3]:
        """Hệ trục tiết diện ``(u, v)``."""
        return _frame(_sub(self.end_m, self.start_m), self.up_hint_m,
                      f"BoxSpec({self.name})")

    @property
    def volume_m3(self) -> float:
        """Thể tích lăng trụ — dùng để đối chiếu sau khi mở lại ``.rfa``."""
        return self.width_m * self.height_m * self.length_m

    @property
    def needs_inclined_work_plane(self) -> bool:
        """Mặt phẳng phác thảo có NGHIÊNG so với ba trục chính không."""
        return not _is_axis_aligned(self.axis_m)


def _box_lines(box: BoxSpec, *, is_solid: bool) -> list[str]:
    """Thân mã C# dựng một :class:`BoxSpec` bằng ``NewExtrusion``."""
    u, v = box.frame
    tag = box.name
    kind = "khoi DAC" if is_solid else "khoi VOID"
    lines = [
        f"// --- {tag}: {kind} lang tru, NewExtrusion ---",
        f"// truc {_fmt_pt(box.start_m)} -> {_fmt_pt(box.end_m)} m, "
        f"dai {box.length_m:.4f} m",
        f"// tiet dien {box.width_m:.4f} (rong) x {box.height_m:.4f} (cao) m, "
        f"the tich {box.volume_m3:.4f} m3",
        f"// mat phang phac thao vuong goc truc; "
        f"{'NGHIENG' if box.needs_inclined_work_plane else 'trung mot truc chinh'}",
        f"Plane pl{tag} = Plane.CreateByNormalAndOrigin("
        f"{_dir_cs(box.axis_m)}, {xyz(*box.start_m)});",
        f"SketchPlane sp{tag} = SketchPlane.Create(fd, pl{tag});",
    ]
    lines += _rect_loop_cs(tag, box.start_m, u, v, box.width_m, box.height_m)
    lines += [
        f"CurveArrArray caa{tag} = new CurveArrArray();",
        f"caa{tag}.Append({tag}Loop);",
        "// GIA DINH OVERLOAD: NewExtrusion(bool isSolid, CurveArrArray, "
        "SketchPlane, double end)",
        f"Extrusion ext{tag} = fd.FamilyCreate.NewExtrusion("
        f"{'true' if is_solid else 'false'}, caa{tag}, sp{tag}, "
        f"{_ft(box.length_m)});",
        _throw_if_null_cs(f"ext{tag}", f"NewExtrusion ({tag})"),
    ]
    return lines


# ---------------------------------------------------------------------------
# Giao của hai khối hộp — con số DUY NHẤT bắt được cái hỏng IM LẶNG của [S2]
# ---------------------------------------------------------------------------
#
# VÌ SAO KHÔNG PHẢI ``host.volume_m3 - cut.volume_m3``
# ---------------------------------------------------
# Vì void thò ra ngoài khối đặc thì phần thò ra KHÔNG khoét gì cả. Ca đã đo
# trong RFC-1.1.0 §2 [S2]: bệ 10.0 x 8.0 x 2.5 m, void 1.2 x 1.2 x 3.0 m
# XUYÊN QUA (dài hơn bệ 0.5 m). Tài liệu ghi "nếu cắt phải còn 196.400" —
# tức ``200 - 1.2*1.2*2.5 = 196.4``, chỉ trừ phần void NẰM TRONG bệ. Công thức
# trừ nguyên thể tích void cho ra 195.68, một con số KHÔNG khớp phép đo. Mà
# đây đúng là con số người ta dùng để phân biệt "void đã cắt" với "void không
# cắt" sau khi mở lại ``.rfa`` — sai nó là chỉ dẫn người đọc kết luận ngược.


def _obb_half_spaces(box: "BoxSpec") -> list[tuple[Vec3, float]]:
    """Sáu nửa không gian ``n · x <= d`` bao đúng khối mà :func:`_box_lines` phát.

    Khối đó là: tiết diện chữ nhật TÂM tại ``start_m`` (rộng ``width_m`` dọc
    ``u``, cao ``height_m`` dọc ``v``) kéo dài ``length_m`` dọc trục — nên tâm
    khối nằm ở ``start_m + trục * length/2``.
    """
    u, v = box.frame
    n = box.axis_m
    center = _add(box.start_m, _scale(n, box.length_m * 0.5))
    out: list[tuple[Vec3, float]] = []
    for axis, half in ((u, box.width_m * 0.5),
                       (v, box.height_m * 0.5),
                       (n, box.length_m * 0.5)):
        offset = _dot(axis, center)
        out.append((axis, offset + half))
        out.append((_scale(axis, -1.0), half - offset))
    return out


def _plane_triple_point(h0: tuple[Vec3, float], h1: tuple[Vec3, float],
                        h2: tuple[Vec3, float]) -> Vec3 | None:
    """Giao điểm của ba mặt phẳng, hoặc ``None`` nếu chúng không cắt tại một điểm."""
    (n0, d0), (n1, d1), (n2, d2) = h0, h1, h2
    det = _dot(n0, _cross(n1, n2))
    if abs(det) <= 1.0e-9:
        return None                      # song song hoặc cùng chứa một đường
    num = _add(_add(_scale(_cross(n1, n2), d0), _scale(_cross(n2, n0), d1)),
               _scale(_cross(n0, n1), d2))
    return _scale(num, 1.0 / det)


def _centroid(points: Sequence[Vec3]) -> Vec3:
    k = 1.0 / float(len(points))
    return (sum(p[0] for p in points) * k,
            sum(p[1] for p in points) * k,
            sum(p[2] for p in points) * k)


def _half_space_volume_m3(half_spaces: Sequence[tuple[Vec3, float]]) -> float:
    """Thể tích khối lồi ``{x : n · x <= d}`` — 0.0 nếu rỗng hoặc dẹt.

    Cách làm, thuần stdlib và xác định lại được:

    1. đỉnh = giao của MỌI bộ ba mặt phẳng, giữ lại điểm thoả cả 12 ràng buộc;
    2. mặt = các đỉnh nằm trên cùng một mặt phẳng, sắp theo góc quanh tâm mặt;
    3. thể tích = tổng tứ diện (tâm khối, ba đỉnh của một tam giác trên mặt).

    Không cần thư viện ngoài, và đúng cho hộp NGHIÊNG chứ không riêng hộp trùng
    trục chính — hai ca đó cho ra hai con số khác nhau, nên chặn bằng "chỉ đúng
    khi trùng trục" là để dành một cái bẫy.
    """
    scale = max([1.0] + [abs(d) for _, d in half_spaces])
    tol = 1.0e-9 * scale

    verts: list[Vec3] = []
    count = len(half_spaces)
    for i in range(count):
        for j in range(i + 1, count):
            for k in range(j + 1, count):
                point = _plane_triple_point(half_spaces[i], half_spaces[j],
                                            half_spaces[k])
                if point is None:
                    continue
                if all(_dot(n, point) <= d + tol for n, d in half_spaces):
                    verts.append(point)
    uniq: list[Vec3] = []
    for point in verts:
        if not any(_length(_sub(point, seen)) <= 1.0e-7 for seen in uniq):
            uniq.append(point)
    if len(uniq) < 4:
        return 0.0

    apex = _centroid(uniq)
    volume = 0.0
    for n, d in half_spaces:
        face = [p for p in uniq if abs(_dot(n, p) - d) <= tol]
        if len(face) < 3:
            continue
        hub = _centroid(face)
        ref = (1.0, 0.0, 0.0) if abs(n[0]) < 0.9 else (0.0, 1.0, 0.0)
        e1 = _unit(_cross(n, ref), "hệ trục trong mặt")
        e2 = _cross(n, e1)
        face.sort(key=lambda p: math.atan2(_dot(_sub(p, hub), e2),
                                           _dot(_sub(p, hub), e1)))
        for t in range(1, len(face) - 1):
            volume += abs(_dot(_sub(face[0], apex),
                               _cross(_sub(face[t], apex),
                                      _sub(face[t + 1], apex)))) / 6.0
    return volume if volume > 1.0e-12 else 0.0


def _box_overlap_m3(host: "BoxSpec", cut: "BoxSpec") -> float:
    """Thể tích phần ``cut`` NẰM TRONG ``host``, mét khối.

    Đây là phần duy nhất bị khoét NẾU void cắt được. Phần void thò ra ngoài
    khối đặc không khoét gì — xem khối chú thích ở đầu mục này.
    """
    return _half_space_volume_m3(_obb_half_spaces(host) + _obb_half_spaces(cut))


# ---------------------------------------------------------------------------
# Cung tròn ba điểm
# ---------------------------------------------------------------------------

def _arc_sagitta(p_start: Vec3, p_end: Vec3, p_mid: Vec3) -> tuple[float, float]:
    """``(sagitta, dây cung)`` mét — khoảng cách từ điểm giữa tới dây cung."""
    chord = _sub(p_end, p_start)
    chord_len = _length(chord)
    if chord_len <= REVIT_SHORT_CURVE_TOL_M:
        raise DegenerateGeometryError(
            f"Dây cung dài {chord_len:.9f} m <= dung sai đường ngắn của Revit "
            f"({REVIT_SHORT_CURVE_TOL_M:.7f} m): hai đầu đốt trùng nhau.")
    sag = _length(_cross(_sub(p_mid, p_start), chord)) / chord_len
    return sag, chord_len


def _arc_frames(p_start: Vec3, p_end: Vec3,
                p_mid: Vec3) -> tuple[Vec3, Vec3, Vec3, float, float]:
    """``(pháp tuyến, tiếp tuyến đầu, tiếp tuyến cuối, bán kính, góc quét)``.

    Tất cả tính trong Python bằng hình học phẳng chuẩn — mã C# phát ra chỉ nhận
    literal, không phải làm phép vector nào. Ít mã C# hơn = ít chỗ hỏng ở phía
    không kiểm được bằng pytest hơn.
    """
    a = _sub(p_start, p_mid)
    b = _sub(p_end, p_mid)
    ab = _cross(a, b)
    denom = 2.0 * _dot(ab, ab)
    if denom <= 0.0:
        raise CollinearArcError(
            "Ba điểm suy biến: tích có hướng bằng 0, không có tâm cung.")
    num = _cross(_sub(_scale(b, _dot(a, a)), _scale(a, _dot(b, b))), ab)
    center = _add(p_mid, _scale(num, 1.0 / denom))

    normal = _unit(ab, "pháp tuyến mặt phẳng cung")
    r_start = _sub(p_start, center)
    radius = _length(r_start)
    if radius <= REVIT_SHORT_CURVE_TOL_M:
        raise DegenerateGeometryError(
            f"Bán kính cung {radius:.9f} m quá nhỏ.")
    e1 = _scale(r_start, 1.0 / radius)

    def _angles(nrm: Vec3) -> tuple[Vec3, float, float]:
        e2 = _cross(nrm, e1)
        def ang(p: Vec3) -> float:
            r = _sub(p, center)
            theta = math.atan2(_dot(r, e2), _dot(r, e1))
            return theta + 2.0 * math.pi if theta < 0.0 else theta
        return e2, ang(p_mid), ang(p_end)

    e2, th_mid, th_end = _angles(normal)
    if th_mid >= th_end:
        # điểm giữa nằm ở phía bên kia -> cung đi theo chiều ngược lại;
        # lật pháp tuyến để mọi thứ trở về "ngược chiều kim đồng hồ".
        normal = _scale(normal, -1.0)
        e2, th_mid, th_end = _angles(normal)
    if not (0.0 < th_mid < th_end < 2.0 * math.pi):
        raise DegenerateGeometryError(
            f"Điểm giữa không nằm giữa hai đầu trên cung: goc giữa={th_mid:.6f} "
            f"rad, góc cuối={th_end:.6f} rad. Điểm thứ ba phải là một điểm NẰM "
            f"TRÊN cung giữa hai đầu, không phải tâm hay điểm bất kỳ.")

    t_start = e2
    t_end = _add(_scale(e1, -math.sin(th_end)), _scale(e2, math.cos(th_end)))
    return normal, t_start, _unit(t_end, "tiếp tuyến cuối"), radius, th_end


# ---------------------------------------------------------------------------
# 1. Đốt vành vòm — NewSweptBlend, ràng buộc [S1]
# ---------------------------------------------------------------------------

def arch_rib_segment(
    template_key: str,
    out_rfa: str,
    *,
    start_m: Sequence[float],
    end_m: Sequence[float],
    mid_m: Sequence[float] | None = None,
    width_start_m: float,
    height_start_m: float,
    width_end_m: float,
    height_end_m: float,
    up_hint_m: Sequence[float] | None = None,
    allow_straight: bool = False,
    tx_name: str = "DYLIGHT arch rib segment F0 IDEA",
    claim_statement: str = DEFAULT_CLAIM_STATEMENT,
) -> str:
    """Một đốt VÀNH VÒM cong, tiết diện THUÔN — ``NewSweptBlend`` theo [S1].

    Path là một ``Arc`` ba điểm (hoặc ``Line`` khi không có ``mid_m``). RFC-1.1.0
    §2 đã đo: path **cong được**, nên một đốt vòm = **một** phép, không chia đoạn.

    [S1] được tuân thủ **bằng cấu trúc**, không bằng lời hứa: hàm luôn phát
    ``NewModelCurve`` trước, rồi truyền ``mc.GeometryCurve.Reference``. Không có
    nhánh nào trong hàm này truyền thẳng một ``Curve`` — mà nếu có, hàm tự kiểm
    trên chuỗi vừa sinh và raise.

    Args:
        template_key: khoá template (phải thuộc thế giới SKETCH).
        out_rfa: đường dẫn tuyệt đối ``.rfa`` sẽ ghi ra.
        start_m, end_m: hai đầu đốt, mét, hệ cầu ``(x dọc, y cao, z ngang)``.
        mid_m: một điểm NẰM TRÊN cung, giữa hai đầu. ``None`` = đốt THẲNG.
        width_start_m, height_start_m: tiết diện đầu A.
        width_end_m, height_end_m: tiết diện đầu B (khác đầu A = thuôn).
        up_hint_m: hướng "lên" tham chiếu cho tiết diện; ``None`` = tự chọn từ
            dây cung, dùng CHUNG cho cả hai đầu để tiết diện không bị xoắn 90 độ.
        allow_straight: cho phép hạ ``Arc`` xuống ``Line`` khi ba điểm thẳng hàng.
            Mặc định ``False``: xin một đốt CONG mà đưa vào ba điểm thẳng thì im
            lặng dựng ra thanh thẳng là nói dối, không phải là dễ tính.
        tx_name: tên transaction hiện trong undo stack của Revit.
        claim_statement: câu claim dán vào family.

    Returns:
        Chuỗi C# ASCII hoàn chỉnh, đẩy thẳng qua ``send_code_to_revit``.

    Raises:
        UnsupportedInWorldError: template ngoài thế giới SKETCH.
        NotMeasuredError: template chưa đo phép này.
        CollinearArcError: ``mid_m`` thẳng hàng với hai đầu và
            ``allow_straight=False``.
        DegenerateGeometryError: kích thước/hình học suy biến.
    """
    # CỔNG TRƯỚC — không một ký tự C# nào được sinh trước dòng này.
    operations = ["NewModelCurve", "NewSweptBlend"]
    require_operations(operations, template_key)

    p0 = _point(start_m, "arch_rib_segment.start_m")
    p1 = _point(end_m, "arch_rib_segment.end_m")
    w0 = _positive(width_start_m, "arch_rib_segment.width_start_m")
    h0 = _positive(height_start_m, "arch_rib_segment.height_start_m")
    w1 = _positive(width_end_m, "arch_rib_segment.width_end_m")
    h1 = _positive(height_end_m, "arch_rib_segment.height_end_m")
    hint = (_point(up_hint_m, "arch_rib_segment.up_hint_m")
            if up_hint_m is not None else None)

    chord = _sub(p1, p0)
    chord_len = _length(chord)
    if chord_len <= REVIT_SHORT_CURVE_TOL_M:
        raise DegenerateGeometryError(
            f"arch_rib_segment: hai đầu đốt cách nhau {chord_len:.9f} m <= dung "
            f"sai đường ngắn của Revit ({REVIT_SHORT_CURVE_TOL_M:.7f} m).")
    chord_dir = _scale(chord, 1.0 / chord_len)
    if hint is None:
        hint = _auto_up_hint(chord_dir)

    curved = False
    pm: Vec3 | None = None
    if mid_m is not None:
        pm = _point(mid_m, "arch_rib_segment.mid_m")
        sag, _ = _arc_sagitta(p0, p1, pm)
        if sag <= SAG_TOL_M:
            if not allow_straight:
                raise CollinearArcError(
                    f"Ba điểm THẲNG HÀNG: sagitta = {sag:.9f} m <= dung sai "
                    f"{SAG_TOL_M:.7f} m (= 1/256 ft).\n"
                    f"  start_m = {_fmt_pt(p0)} m\n"
                    f"  mid_m   = {_fmt_pt(pm)} m\n"
                    f"  end_m   = {_fmt_pt(p1)} m\n"
                    f"  Arc.Create trên ba điểm thẳng hàng sẽ NÉM trong Revit; "
                    f"chặn ở đây để không mất một vòng MCP.\n"
                    f"  Muốn một đốt THẲNG thì nói ra: bỏ mid_m, hoặc truyền "
                    f"allow_straight=True. Dựng lén một thanh thẳng cho người "
                    f"xin một đốt CONG là nói dối, không phải là dễ tính.")
            curved = False
        else:
            curved = True

    if curved and pm is not None:
        normal, t0, t1, radius, sweep = _arc_frames(p0, p1, pm)
        path_comment = (
            f"// path: Arc ba diem, ban kinh {radius:.4f} m, "
            f"goc quet {math.degrees(sweep):.4f} do")
        path_plane_normal = normal
        path_curve_cs = "Arc.Create(pRibA, pRibB, pRibM)"
    else:
        t0 = t1 = chord_dir
        # mặt phẳng phác thảo phải CHỨA đường thẳng: lấy pháp tuyến là hướng
        # "rộng" của tiết diện, tức mặt phẳng đứng chứa trục đốt.
        u_chord, _ = _frame(chord_dir, hint, "arch_rib_segment (đốt thẳng)")
        path_plane_normal = u_chord
        path_comment = f"// path: Line thang, dai {chord_len:.4f} m"
        path_curve_cs = "Line.CreateBound(pRibA, pRibB)"

    # Mặt phẳng phác thảo của PATH có nghiêng không? Nếu có thì phải xin thêm
    # phép — cùng khuôn với prismatic_member. Danh sách phép phải mô tả ĐÚNG
    # cái mã C# làm, không phải cái nó thường làm.
    inclined = not _is_axis_aligned(path_plane_normal)
    if inclined:
        operations.append("InclinedWorkPlane")
        require_operations(operations, template_key)

    u0, v0 = _frame(t0, hint, "arch_rib_segment (tiết diện đầu A)")
    u1, v1 = _frame(t1, hint, "arch_rib_segment (tiết diện đầu B)")

    body: list[str] = []
    body += _purge_template_geometry_cs()
    body.append("")
    body.append("// --- DOT VANH VOM: NewSweptBlend, rang buoc [S1] ---")
    body.append(f"// dau A {_fmt_pt(p0)} m, tiet dien {w0:.4f} x {h0:.4f} m")
    body.append(f"// dau B {_fmt_pt(p1)} m, tiet dien {w1:.4f} x {h1:.4f} m")
    body.append(path_comment)
    body.append(f"XYZ pRibA = {xyz(*p0)};")
    body.append(f"XYZ pRibB = {xyz(*p1)};")
    if curved:
        body.append(f"XYZ pRibM = {xyz(*pm)};")
    body.append(
        f"// mat phang phac thao cua path: "
        f"{'NGHIENG' if inclined else 'trung mot truc chinh'}")
    body.append(
        f"Plane plRibPath = Plane.CreateByNormalAndOrigin("
        f"{_dir_cs(path_plane_normal)}, pRibA);")
    body.append("SketchPlane spRibPath = SketchPlane.Create(fd, plRibPath);")
    body.append(f"Curve crvRibPath = {path_curve_cs};")
    body.append(
        "ModelCurve mcRibPath = fd.FamilyCreate.NewModelCurve("
        "crvRibPath, spRibPath);")
    body.append(_throw_if_null_cs("mcRibPath", "NewModelCurve (path vanh vom)"))
    body.append("")
    body.append("// [S1] NewSweptBlend nhan Reference, KHONG nhan Curve.")
    body.append("// Loi bien dich nguyen van neu truyen Curve:")
    body.append("//   Argument 2: cannot convert from 'Autodesk.Revit.DB.Curve'")
    body.append("//   to 'Autodesk.Revit.DB.Reference'")
    body.append("// => path PHAI di qua mot ModelCurve DA TON TAI trong family.")
    body.append("Reference refRibPath = mcRibPath.GeometryCurve.Reference;")
    body.append(_throw_if_null_cs("refRibPath", "GeometryCurve.Reference (path)"))
    body.append("")
    body += _rect_loop_cs("RibA", p0, u0, v0, w0, h0)
    body.append("CurveArrArray caaRibA = new CurveArrArray();")
    body.append("caaRibA.Append(RibALoop);")
    body.append("// GIA DINH OVERLOAD: NewCurveLoopsProfile(CurveArrArray)"
                " -> SweepProfile")
    body.append("//   [S1] dan profBottom/profTop nhung khong ghi cach tao chung.")
    body.append("SweepProfile profRibA = app.Create.NewCurveLoopsProfile(caaRibA);")
    body.append("")
    body += _rect_loop_cs("RibB", p1, u1, v1, w1, h1)
    body.append("CurveArrArray caaRibB = new CurveArrArray();")
    body.append("caaRibB.Append(RibBLoop);")
    body.append("SweepProfile profRibB = app.Create.NewCurveLoopsProfile(caaRibB);")
    body.append("")
    body.append("// GIA DINH OVERLOAD: NewSweptBlend(bool isSolid, Reference path,"
                " SweepProfile, SweepProfile)")
    body.append("SweptBlend sbRib = fd.FamilyCreate.NewSweptBlend("
                "true, refRibPath, profRibA, profRibB);")
    body.append(_throw_if_null_cs("sbRib", "NewSweptBlend (dot vanh vom)"))

    code = guarded_family_scaffold(
        template_key, out_rfa, operations, body, tx_name,
        claim_statement=claim_statement)
    _self_check(code, expect_arc=curved, expect_swept_blend=True)
    return code


# ---------------------------------------------------------------------------
# 2. Thân trụ thuôn — NewBlend, ràng buộc [B1]
# ---------------------------------------------------------------------------

def tapered_pier_shaft(
    template_key: str,
    out_rfa: str,
    *,
    base_center_m: Sequence[float],
    top_center_m: Sequence[float],
    base_long_m: float,
    base_trans_m: float,
    top_long_m: float,
    top_trans_m: float,
    tx_name: str = "DYLIGHT tapered pier shaft F0 IDEA",
    claim_statement: str = DEFAULT_CLAIM_STATEMENT,
) -> str:
    """Thân trụ THUÔN — ``NewBlend`` theo [B1].

    [B1] đã đo: ``NewBlend`` **đòi hai profile ở CAO ĐỘ KHÁC NHAU**; cả hai ở
    cùng cao độ thì hỏng. Trong hệ cầu của repo này cao độ là **``y``**, nên
    kiểm ở đây là ``base_center_m[1]`` phải khác ``top_center_m[1]``.

    Đỉnh trụ được phép LỆCH TÂM so với đáy (trụ xiên): ``NewBlend`` nối hai
    profile phẳng bất kỳ, chỉ cần chúng khác cao độ.

    Args:
        template_key: khoá template (thế giới SKETCH). RFC-1.1.0 §6 gợi ý
            ``structural_column``.
        out_rfa: đường dẫn tuyệt đối ``.rfa``.
        base_center_m: tâm mặt đáy ``(x, y, z)`` mét — ``y`` là CAO ĐỘ.
        top_center_m: tâm mặt đỉnh.
        base_long_m, base_trans_m: kích thước đáy dọc cầu / ngang cầu.
        top_long_m, top_trans_m: kích thước đỉnh (khác đáy = thuôn).

    Raises:
        BlendElevationError: hai profile cùng cao độ — vi phạm [B1].
        DegenerateGeometryError: đỉnh thấp hơn đáy, hoặc kích thước suy biến.
    """
    operations = ["NewBlend"]
    require_operations(operations, template_key)

    base = _point(base_center_m, "tapered_pier_shaft.base_center_m")
    top = _point(top_center_m, "tapered_pier_shaft.top_center_m")
    bl = _positive(base_long_m, "tapered_pier_shaft.base_long_m")
    bt = _positive(base_trans_m, "tapered_pier_shaft.base_trans_m")
    tl = _positive(top_long_m, "tapered_pier_shaft.top_long_m")
    tt = _positive(top_trans_m, "tapered_pier_shaft.top_trans_m")

    rise = top[1] - base[1]
    if abs(rise) < REVIT_SHORT_CURVE_TOL_M:
        raise BlendElevationError(
            f"[B1] NewBlend ĐÒI hai profile ở CAO ĐỘ KHÁC NHAU.\n"
            f"  base_center_m = {_fmt_pt(base)} m -> cao độ y = {base[1]:.6f} m\n"
            f"  top_center_m  = {_fmt_pt(top)} m -> cao độ y = {top[1]:.6f} m\n"
            f"  chênh cao độ  = {rise:.9f} m < dung sai "
            f"{REVIT_SHORT_CURVE_TOL_M:.7f} m (= 1/256 ft)\n"
            f"  RFC-1.1.0 §2 [B1]: cả hai profile ở cùng cao độ -> HỎNG. Đây là "
            f"số đo trên Revit 2026 máy này, không phải đọc tài liệu API.\n"
            f"  LƯU Ý HỆ TRỤC: hệ cầu của repo là (x dọc, y CAO ĐỘ, z ngang), "
            f"nên 'cao độ' ở đây là thành phần y — tài liệu gốc viết theo z vì "
            f"đó là trục cao độ của Revit.")
    if rise <= 0.0:
        raise DegenerateGeometryError(
            f"tapered_pier_shaft: đỉnh trụ ở cao độ {top[1]:.4f} m KHÔNG cao hơn "
            f"đáy {base[1]:.4f} m (chênh {rise:.4f} m). Một thân trụ lộn ngược "
            f"dựng ra vẫn là khối hợp lệ trong Revit nên sẽ KHÔNG có lỗi nào "
            f"báo — chặn ở đây. Đảo lại hai đối số nếu bạn cố ý.")

    # Mặt phẳng phác thảo NẰM NGANG tại cao độ đáy; hai profile là hai hình chữ
    # nhật trong mặt phẳng ngang, đặt ở hai cao độ khác nhau -> đúng [B1].
    u = _LONG_BRIDGE
    v = _TRANS_BRIDGE

    body: list[str] = []
    body += _purge_template_geometry_cs()
    body.append("")
    body.append("// --- THAN TRU THUON: NewBlend, rang buoc [B1] ---")
    body.append(f"// day  {_fmt_pt(base)} m, {bl:.4f} (doc) x {bt:.4f} (ngang) m")
    body.append(f"// dinh {_fmt_pt(top)} m, {tl:.4f} (doc) x {tt:.4f} (ngang) m")
    body.append(f"// chenh cao do = {rise:.4f} m (> 0 la bat buoc, xem [B1])")
    body.append(
        f"Plane plShaft = Plane.CreateByNormalAndOrigin("
        f"{_dir_cs(_UP_BRIDGE)}, {xyz(*base)});")
    body.append("SketchPlane spShaft = SketchPlane.Create(fd, plShaft);")
    body += _rect_loop_cs("ShaftBase", base, u, v, bl, bt)
    body += _rect_loop_cs("ShaftTop", top, u, v, tl, tt)
    body.append("// [B1] hai profile PHAI o CAO DO KHAC NHAU. Ca hai cung cao do")
    body.append("//      -> NewBlend hong (do tren Revit 2026 may nay).")
    body.append("// GIA DINH OVERLOAD: NewBlend(bool isSolid, CurveArray TOP,"
                " CurveArray BASE, SketchPlane)")
    body.append("//   muc 2 chi ghi 'NewBlend | OK | id=2939'. THU TU DOI SO")
    body.append("//   (TOP truoc, BASE sau) la GIA DINH, khong phai so do.")
    body.append("Blend blShaft = fd.FamilyCreate.NewBlend("
                "true, ShaftTopLoop, ShaftBaseLoop, spShaft);")
    body.append(_throw_if_null_cs("blShaft", "NewBlend (than tru thuon)"))

    code = guarded_family_scaffold(
        template_key, out_rfa, operations, body, tx_name,
        claim_statement=claim_statement)
    _self_check(code, expect_arc=False, expect_swept_blend=False)
    return code


# ---------------------------------------------------------------------------
# 3. Cấu kiện tròn xoay — NewRevolution, ràng buộc [R1]
# ---------------------------------------------------------------------------

def revolved_member(
    template_key: str,
    out_rfa: str,
    *,
    profile_m: Sequence[Sequence[float]],
    axis_start_m: Sequence[float],
    axis_end_m: Sequence[float],
    start_angle_rad: float = 0.0,
    end_angle_rad: float = 2.0 * math.pi,
    tx_name: str = "DYLIGHT revolved member F0 IDEA",
    claim_statement: str = DEFAULT_CLAIM_STATEMENT,
) -> str:
    """Cấu kiện TRÒN XOAY — ``NewRevolution`` theo [R1].

    [R1] đã đo: **trục phải NẰM TRONG mặt phẳng phác thảo**; trục vuông góc thì
    hỏng. Ở đây mặt phẳng phác thảo được suy ra từ CHÍNH đa giác profile (pháp
    tuyến Newell), rồi kiểm hai điều kiện:

    1. hướng trục vuông góc pháp tuyến (``|trục · n| <= PLANE_TOL_COS``);
    2. một điểm của trục nằm trong mặt phẳng (``|(a0 - p0) · n| <= PLANE_TOL_M``).

    Chỉ kiểm điều kiện 1 là chưa đủ: một trục song song mặt phẳng nhưng lệch ra
    ngoài vẫn thoả tích vô hướng mà không nằm trong mặt phẳng.

    Kiểm thêm (không phải [R1], mà là chặn cho Revit khỏi nổ): profile phải
    PHẲNG, không được CẮT QUA trục, và mọi cạnh phải dài hơn dung sai đường ngắn.

    Args:
        profile_m: đa giác KÍN, ``>= 3`` đỉnh ``(x, y, z)`` mét. Lặp lại đỉnh
            đầu ở cuối là được phép — hàm tự bỏ.
        axis_start_m, axis_end_m: hai điểm định nghĩa trục quay.
        start_angle_rad, end_angle_rad: góc quét, radian. Mặc định trọn vòng.

    Raises:
        RevolveAxisError: trục không nằm trong mặt phẳng phác thảo — [R1].
        DegenerateGeometryError: profile không phẳng / cắt trục / suy biến.
    """
    operations = ["NewRevolution"]
    require_operations(operations, template_key)

    if isinstance(profile_m, (str, bytes)) or not hasattr(profile_m, "__len__"):
        raise DegenerateGeometryError(
            "revolved_member.profile_m phải là dãy các bộ ba số.")
    pts = [_point(p, f"revolved_member.profile_m[{i}]")
           for i, p in enumerate(profile_m)]
    if len(pts) >= 2 and _length(_sub(pts[0], pts[-1])) <= REVIT_SHORT_CURVE_TOL_M:
        pts = pts[:-1]          # đỉnh đầu lặp ở cuối: bỏ, vòng tự khép
    if len(pts) < 3:
        raise DegenerateGeometryError(
            f"revolved_member.profile_m cần >= 3 đỉnh phân biệt, còn {len(pts)} "
            f"sau khi bỏ đỉnh lặp.")
    for i in range(len(pts)):
        seg = _length(_sub(pts[(i + 1) % len(pts)], pts[i]))
        if seg <= REVIT_SHORT_CURVE_TOL_M:
            raise DegenerateGeometryError(
                f"revolved_member: cạnh profile {i}->{(i + 1) % len(pts)} dài "
                f"{seg:.9f} m <= dung sai đường ngắn "
                f"({REVIT_SHORT_CURVE_TOL_M:.7f} m).")

    a0 = _point(axis_start_m, "revolved_member.axis_start_m")
    a1 = _point(axis_end_m, "revolved_member.axis_end_m")
    axis_len = _length(_sub(a1, a0))
    if axis_len <= REVIT_SHORT_CURVE_TOL_M:
        raise DegenerateGeometryError(
            f"revolved_member: trục dài {axis_len:.9f} m <= dung sai đường ngắn "
            f"({REVIT_SHORT_CURVE_TOL_M:.7f} m) — hai điểm trục trùng nhau.")
    axis_dir = _scale(_sub(a1, a0), 1.0 / axis_len)

    normal = _unit(_polygon_normal(pts),
                   "revolved_member: pháp tuyến profile (đa giác suy biến?)")
    origin = pts[0]
    for i, p in enumerate(pts):
        off = _dot(_sub(p, origin), normal)
        if abs(off) > PLANE_TOL_M:
            raise DegenerateGeometryError(
                f"revolved_member: profile KHÔNG PHẲNG — đỉnh {i} "
                f"{_fmt_pt(p)} m lệch {off:.9f} m khỏi mặt phẳng của đa giác "
                f"(dung sai {PLANE_TOL_M:.1e} m). NewRevolution dựng từ một "
                f"sketch 2D nên profile cong vênh là vô nghĩa.")

    # --- [R1] ------------------------------------------------------------
    cos_axis = _dot(axis_dir, normal)
    if abs(cos_axis) > PLANE_TOL_COS:
        raise RevolveAxisError(
            f"[R1] NewRevolution ĐÒI trục NẰM TRONG mặt phẳng phác thảo.\n"
            f"  trục       = {_fmt_pt(a0)} -> {_fmt_pt(a1)} m\n"
            f"  hướng trục = ({axis_dir[0]:.6f}, {axis_dir[1]:.6f}, "
            f"{axis_dir[2]:.6f})\n"
            f"  pháp tuyến mặt phẳng profile = ({normal[0]:.6f}, "
            f"{normal[1]:.6f}, {normal[2]:.6f})\n"
            f"  tích vô hướng = {cos_axis:.9f}, phải |.| <= "
            f"{PLANE_TOL_COS:.1e} (tức góc 90 độ)\n"
            f"  lệch khỏi 90 độ: {abs(math.degrees(math.asin(min(1.0, abs(cos_axis))))):.6f} độ\n"
            f"  RFC-1.1.0 §2 [R1]: trục VUÔNG GÓC mặt phẳng phác thảo -> HỎNG. "
            f"Trục quay phải nằm TRONG mặt phẳng chứa profile.")
    off_axis = _dot(_sub(a0, origin), normal)
    if abs(off_axis) > PLANE_TOL_M:
        raise RevolveAxisError(
            f"[R1] Trục SONG SONG mặt phẳng profile nhưng KHÔNG NẰM TRONG nó.\n"
            f"  điểm trục {_fmt_pt(a0)} m lệch {off_axis:.9f} m khỏi mặt phẳng "
            f"(dung sai {PLANE_TOL_M:.1e} m).\n"
            f"  Chỉ kiểm tích vô hướng là chưa đủ: song song vẫn có thể ở ngoài "
            f"mặt phẳng.")

    # --- profile không được cắt qua trục ---------------------------------
    perp = _cross(normal, axis_dir)          # đã đơn vị: hai vector đơn vị vuông góc
    dists = [_dot(_sub(p, a0), perp) for p in pts]
    max_abs = max(abs(d) for d in dists)
    if max_abs <= REVIT_SHORT_CURVE_TOL_M:
        raise DegenerateGeometryError(
            f"revolved_member: profile nằm ngay trên trục (bán kính lớn nhất "
            f"{max_abs:.9f} m) — vật thể xoay ra rỗng.")
    if min(dists) < -PLANE_TOL_M and max(dists) > PLANE_TOL_M:
        raise DegenerateGeometryError(
            f"revolved_member: profile CẮT QUA trục quay (khoảng cách có dấu từ "
            f"{min(dists):.6f} m tới {max(dists):.6f} m). Vật thể xoay sẽ tự "
            f"giao — Revit từ chối. Đặt toàn bộ profile về MỘT phía của trục.")

    for name, ang in (("start_angle_rad", start_angle_rad),
                      ("end_angle_rad", end_angle_rad)):
        if not isinstance(ang, (int, float)) or not math.isfinite(float(ang)):
            raise DegenerateGeometryError(
                f"revolved_member.{name} = {ang!r} không phải số hữu hạn.")
    sweep = float(end_angle_rad) - float(start_angle_rad)
    if sweep <= 1.0e-6 or sweep > 2.0 * math.pi + 1.0e-9:
        raise DegenerateGeometryError(
            f"revolved_member: góc quét = {sweep:.9f} rad. Phải nằm trong "
            f"(0, 2*pi]. Quét 0 thì không có khối; quét > 2*pi thì khối tự chồng.")

    # Mặt phẳng phác thảo ở đây là mặt phẳng CỦA CHÍNH PROFILE — profile đặt
    # chéo thì nó nghiêng, và phải xin thêm phép như prismatic_member.
    inclined = not _is_axis_aligned(normal)
    if inclined:
        operations.append("InclinedWorkPlane")
        require_operations(operations, template_key)

    body: list[str] = []
    body += _purge_template_geometry_cs()
    body.append("")
    body.append("// --- CAU KIEN TRON XOAY: NewRevolution, rang buoc [R1] ---")
    body.append(f"// profile {len(pts)} dinh, mat phang phap tuyen "
                f"({normal[0]:.6f}, {normal[1]:.6f}, {normal[2]:.6f}) he cau")
    body.append(f"// truc {_fmt_pt(a0)} -> {_fmt_pt(a1)} m, dai {axis_len:.4f} m")
    body.append(f"// ban kinh lon nhat {max_abs:.4f} m, "
                f"goc quet {math.degrees(sweep):.4f} do")
    body.append(f"// mat phang phac thao: "
                f"{'NGHIENG' if inclined else 'trung mot truc chinh'}")
    body.append(
        f"Plane plRev = Plane.CreateByNormalAndOrigin("
        f"{_dir_cs(normal)}, {xyz(*origin)});")
    body.append("SketchPlane spRev = SketchPlane.Create(fd, plRev);")
    for i, p in enumerate(pts):
        body.append(f"XYZ RevP{i} = {xyz(*p)};")
    body.append("CurveArray RevLoop = new CurveArray();")
    for i in range(len(pts)):
        body.append(f"RevLoop.Append(Line.CreateBound("
                    f"RevP{i}, RevP{(i + 1) % len(pts)}));")
    body.append("CurveArrArray caaRev = new CurveArrArray();")
    body.append("caaRev.Append(RevLoop);")
    body.append("// [R1] truc PHAI nam TRONG mat phang phac thao.")
    body.append("//      Truc vuong goc mat phang -> NewRevolution hong")
    body.append("//      (do tren Revit 2026 may nay, RFC-1.1.0 muc 2).")
    body.append(f"Line axRev = Line.CreateBound({xyz(*a0)}, {xyz(*a1)});")
    body.append("// GIA DINH OVERLOAD: NewRevolution(bool isSolid, CurveArrArray,"
                " SketchPlane, Line axis, double, double)")
    body.append(f"Revolution revMember = fd.FamilyCreate.NewRevolution("
                f"true, caaRev, spRev, axRev, "
                f"{_cs_num(float(start_angle_rad))}, "
                f"{_cs_num(float(end_angle_rad))});")
    body.append(_throw_if_null_cs("revMember", "NewRevolution (cau kien tron xoay)"))

    code = guarded_family_scaffold(
        template_key, out_rfa, operations, body, tx_name,
        claim_statement=claim_statement)
    _self_check(code, expect_arc=False, expect_swept_blend=False)
    return code


# ---------------------------------------------------------------------------
# 4. Thanh lăng trụ — NewExtrusion (+ work plane nghiêng)
# ---------------------------------------------------------------------------

def prismatic_member(
    template_key: str,
    out_rfa: str,
    box: BoxSpec,
    *,
    tx_name: str = "DYLIGHT prismatic member F0 IDEA",
    claim_statement: str = DEFAULT_CLAIM_STATEMENT,
) -> str:
    """Thanh LĂNG TRỤ tiết diện chữ nhật — ``NewExtrusion``.

    Mặt phẳng phác thảo vuông góc trục thanh. Nếu trục không trùng một trục
    chính của hệ cầu thì mặt phẳng đó **NGHIÊNG**, và hàm xin thêm phép
    ``InclinedWorkPlane`` ở cổng năng lực — RFC-1.1.0 §2 đã chứng minh work
    plane nghiêng chạy được trong thế giới SKETCH (pháp tuyến (0.6, 0, 0.8)),
    nhưng CHƯA đo ở thế giới nào khác, nên cổng vẫn phải hỏi.

    Với thanh nằm ngang, ``width_m`` đo ngang cầu và ``height_m`` đo thẳng đứng.
    Với **cột thẳng đứng** thì ``y`` song song trục nên hệ tiết diện tự xoay:
    ``width_m`` ngang cầu, ``height_m`` DỌC cầu. Muốn khác thì truyền
    ``up_hint_m`` vào :class:`BoxSpec`.
    """
    if not isinstance(box, BoxSpec):
        raise DegenerateGeometryError(
            f"prismatic_member: tham số `box` phải là BoxSpec, nhận "
            f"{type(box).__name__}. BoxSpec kiểm hình học ngay lúc dựng nên "
            f"không có 'spec hợp lệ một nửa' lọt xuống bộ phát mã.")
    operations = ["NewExtrusion"]
    if box.needs_inclined_work_plane:
        operations.append("InclinedWorkPlane")
    require_operations(operations, template_key)

    body = _purge_template_geometry_cs() + [""] + _box_lines(box, is_solid=True)
    code = guarded_family_scaffold(
        template_key, out_rfa, operations, body, tx_name,
        claim_statement=claim_statement)
    _self_check(code, expect_arc=False, expect_swept_blend=False)
    return code


# ---------------------------------------------------------------------------
# 5. Void — NewExtrusion(isSolid=false), ràng buộc [S2]
# ---------------------------------------------------------------------------

def void_cut(
    template_key: str,
    out_rfa: str,
    host: BoxSpec,
    cut: BoxSpec,
    *,
    acknowledge_no_cut: bool = False,
    tx_name: str = "DYLIGHT void cut F0 IDEA",
    claim_statement: str = DEFAULT_CLAIM_STATEMENT,
) -> str:
    """Khối đặc + khối VOID — ``NewExtrusion(isSolid=false)``, ràng buộc [S2].

    **ĐỌC TRƯỚC KHI DÙNG.** RFC-1.1.0 §2 [S2] đo trên ``FAM_BeMong.rfa``: void
    trong family SKETCH **KHÔNG cắt** khối đặc, và ``SolidSolidCutUtils`` TỪ
    CHỐI ở đó::

        the tich      = 200.000 m3   <- dung bang 10x8x2.5, tuc KHONG cat
        CanElementCutElement = False  reason = CutNotAppropriateForElements
        AddCutBetweenSolids  -> ArgumentException

    Nguy hiểm ở chỗ nó **im lặng**: ``NewExtrusion(false, ...)`` trả về đối
    tượng bình thường, void có mặt trong file, danh sách phần tử trông đủ. Chỉ
    **đo thể tích** mới lộ ra. Cách làm void cắt được trong thế giới SKETCH thì
    **CHƯA ĐO**.

    Vì vậy hàm này **raise mặc định**. ``acknowledge_no_cut=True`` là lời khai
    tường minh "tôi biết khối này KHÔNG bị khoét" — nó không mở khoá một năng
    lực nào cả, nó chỉ ghi lại rằng người gọi đã đọc [S2].

    CON SỐ ĐỐI CHIẾU LẤY TỪ PHẦN GIAO, KHÔNG PHẢI TỪ HIỆU HAI THỂ TÍCH
    ------------------------------------------------------------------
    "Thể tích kỳ vọng NẾU cắt được" = ``host`` trừ **phần void nằm TRONG
    host** (:func:`_box_overlap_m3`), vì phần void thò ra ngoài không khoét gì.
    Ca đã đo cho ra đúng ``200.0000 - 3.6000 = 196.4000`` như RFC-1.1.0 §2
    [S2] ghi; trừ nguyên thể tích void sẽ ra 195.68 và chỉ dẫn người đọc kết
    luận ngược khi họ mở lại ``.rfa`` và đo được 196.4.

    Args:
        host: khối ĐẶC.
        cut: khối VOID. Phải khác ``host.name`` (tên là tiền tố biến C#).
        acknowledge_no_cut: xác nhận đã đọc [S2].

    Raises:
        VoidDoesNotCutError: chưa xác nhận [S2].
        DegenerateGeometryError: hai khối trùng tên, hoặc spec sai kiểu.
    """
    for label, value in (("host", host), ("cut", cut)):
        if not isinstance(value, BoxSpec):
            raise DegenerateGeometryError(
                f"void_cut: tham số `{label}` phải là BoxSpec, nhận "
                f"{type(value).__name__}.")
    if host.name == cut.name:
        raise DegenerateGeometryError(
            f"void_cut: host và cut cùng tên '{host.name}'. Tên là tiền tố BIẾN "
            f"C#, trùng tên thì mã sinh ra khai báo lại biến và không biên dịch "
            f"được — chặn ở Python thay vì để Revit báo lỗi cú pháp.")
    # kẹp về [0, thể tích void]: sai số dấu phẩy động cỡ 1e-16 in ra thành
    # "-0.0000", và một dấu trừ vô nghĩa trong con số đối chiếu là một câu hỏi
    # thừa cho người đang đọc kết quả đo bên Revit.
    overlap_m3 = min(max(_box_overlap_m3(host, cut), 0.0), cut.volume_m3)
    expected_m3 = host.volume_m3 - overlap_m3
    outside_m3 = cut.volume_m3 - overlap_m3
    if not acknowledge_no_cut:
        raise VoidDoesNotCutError(
            f"[S2] Void trong thế giới SKETCH ĐÃ ĐO LÀ KHÔNG CẮT khối đặc.\n"
            f"  Đo trên FAM_BeMong.rfa (RFC-1.1.0 §2 [S2]): khối 10.0 x 8.0 x "
            f"2.5 m + void 1.2 x 1.2 x 3.0 m xuyên qua -> thể tích vẫn 200.000 "
            f"m3, ĐÚNG BẰNG khối đặc. CanElementCutElement = False, reason = "
            f"CutNotAppropriateForElements. AddCutBetweenSolids ném "
            f"ArgumentException.\n"
            f"  NGUY HIỂM VÌ NÓ IM LẶNG: NewExtrusion(false, ...) trả về đối "
            f"tượng bình thường và void CÓ trong file — chỉ đo thể tích mới lộ.\n"
            f"  Cách làm void cắt được trong family SKETCH: CHƯA ĐO.\n"
            f"  Nếu bạn CHỈ cần khối void tồn tại (để cắt ở nơi khác, hoặc để "
            f"đo tiếp) thì truyền acknowledge_no_cut=True. Nếu bạn cần một cái "
            f"LỖ THẬT thì đừng dùng thế giới SKETCH — hãy đo trước.\n"
            f"  Thể tích kỳ vọng NẾU cắt được: {host.volume_m3:.4f} - "
            f"{overlap_m3:.4f} = {expected_m3:.4f} m3.\n"
            f"  Chỉ trừ PHẦN VOID NẰM TRONG khối đặc: khối void "
            f"{cut.volume_m3:.4f} m3 nhưng {outside_m3:.4f} m3 nằm ngoài khối "
            f"đặc nên không khoét gì. (Ca đã đo: 200.0000 - 3.6000 = 196.4000, "
            f"đúng con số RFC-1.1.0 §2 [S2] ghi.)\n"
            f"  Thể tích THỰC TẾ sẽ đo được: {host.volume_m3:.4f} m3.")

    operations = ["NewExtrusion"]
    if host.needs_inclined_work_plane or cut.needs_inclined_work_plane:
        operations.append("InclinedWorkPlane")
    require_operations(operations, template_key)

    body: list[str] = []
    body += _purge_template_geometry_cs()
    body.append("")
    body += _box_lines(host, is_solid=True)
    body.append("")
    body.append("// " + "=" * 66)
    body.append("// [S2] CANH BAO DA DO: VOID TRONG FAMILY SKETCH KHONG TU CAT.")
    body.append("// FAM_BeMong.rfa: khoi 10.0x8.0x2.5 m + void 1.2x1.2x3.0 m")
    body.append("//   the tich = 200.000 m3 = DUNG BANG khoi dac -> KHONG cat")
    body.append("//   CanElementCutElement = False (CutNotAppropriateForElements)")
    body.append("//   AddCutBetweenSolids -> ArgumentException")
    body.append("// Khoi VOID duoi day CO trong file nhung KHONG khoet khoi dac.")
    body.append(f"// The tich ky vong NEU cat duoc: {host.volume_m3:.4f} - "
                f"{overlap_m3:.4f} = {expected_m3:.4f} m3")
    body.append(f"//   chi tru PHAN VOID NAM TRONG khoi dac; khoi void "
                f"{cut.volume_m3:.4f} m3, phan nam ngoai {outside_m3:.4f} m3")
    body.append("//   khong khoet gi. Ca da do: 200.0000 - 3.6000 = 196.4000.")
    body.append(f"// The tich THUC TE se do duoc  : {host.volume_m3:.4f} m3")
    body.append("// PHAI mo lai .rfa va DO THE TICH de doi chieu hai con so tren.")
    body.append("// " + "=" * 66)
    body.append("")
    body += _box_lines(cut, is_solid=False)

    code = guarded_family_scaffold(
        template_key, out_rfa, operations, body, tx_name,
        claim_statement=claim_statement)
    _self_check(code, expect_arc=False, expect_swept_blend=False)
    return code


# ---------------------------------------------------------------------------
# Tự kiểm TRÊN CHÍNH CHUỖI VỪA SINH
# ---------------------------------------------------------------------------

def _self_check(code: str, *, expect_arc: bool, expect_swept_blend: bool) -> None:
    """Kiểm bất biến trên chuỗi C# vừa sinh — không tin docstring của chính mình.

    Bổ sung cho ``csharp._self_check_scaffold`` (transaction / Regenerate /
    SaveAs / dấu claim) bằng bốn bất biến riêng của thế giới SKETCH: [S1],
    [S3], dấu claim, và **khai báo overload giả định**.
    """
    if CLAIM_LEVEL_PARAM not in code:
        raise CSharpStructureError(
            f"Mã sinh ra KHÔNG mang dấu claim ({CLAIM_LEVEL_PARAM}). Family "
            f"tham số hoá trông giống hồ sơ kỹ thuật thật hơn DirectShape nên "
            f"dấu claim là bắt buộc, không phải tuỳ chọn.")
    if "OfClass(typeof(GenericForm))" not in code:
        raise CSharpStructureError(
            "[S3] Mã sinh ra không quét-và-xoá hình học ship sẵn của template. "
            "Thiếu bước đó thì mọi con số đếm GenericForm về sau bị nhiễm.")

    # Mọi kiểm tra về THỨ TỰ và SỰ CÓ MẶT chạy trên bản đã bỏ chú thích và
    # chuỗi hằng: mã phát ra cố ý mang chú thích dẫn tên API (số đo [S1], giả
    # định overload), và một dòng chú thích không được phép làm thoả mãn một
    # bất biến về thi hành.
    clean = _strip_cs_literals_and_comments(code)

    has_swept_blend = "NewSweptBlend(" in clean
    if has_swept_blend != expect_swept_blend:
        raise CSharpStructureError(
            f"NewSweptBlend trong mã = {has_swept_blend}, kỳ vọng "
            f"{expect_swept_blend}.")
    if has_swept_blend:
        i_mc = clean.find("NewModelCurve(")
        i_sb = clean.find("NewSweptBlend(")
        if i_mc < 0 or i_mc > i_sb:
            raise CSharpStructureError(
                "[S1] NewSweptBlend nhận Reference, KHÔNG nhận Curve. Mã sinh "
                "ra phải phát NewModelCurve TRƯỚC rồi truyền "
                "mc.GeometryCurve.Reference.")
        if "GeometryCurve.Reference" not in clean:
            raise CSharpStructureError(
                "[S1] Không thấy 'GeometryCurve.Reference' — path của "
                "NewSweptBlend không đi qua một ModelCurve đã tồn tại.")

    has_arc = "Arc.Create(" in clean
    if has_arc != expect_arc:
        raise CSharpStructureError(
            f"Arc.Create trong mã = {has_arc}, kỳ vọng {expect_arc}. Ba điểm "
            f"thẳng hàng thì Arc.Create NÉM trong Revit — không được phát.")

    for op_name, gia_dinh in SKETCH_DECLARED_OVERLOADS:
        if f"{op_name}(" not in clean:      # chú thích không tính là lời gọi
            continue
        if f"GIA DINH OVERLOAD: {op_name}(" not in code:
            raise CSharpStructureError(
                f"Mã sinh ra gọi {op_name}(...) mà KHÔNG đánh dấu "
                f"'// GIA DINH OVERLOAD: {op_name}(...)'.\n"
                f"  RFC-1.1.0 ghi KẾT QUẢ của phép này, không ghi CHỮ KÝ. Chữ "
                f"ký dùng ở đây là giả định: {gia_dinh}\n"
                f"  Người đọc bên Revit phải phân biệt được đâu là số đo, đâu "
                f"là suy đoán — cùng kỷ luật với adaptive_family."
                f"DECLARED_OVERLOADS.")
