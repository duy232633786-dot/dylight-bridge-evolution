"""Sinh mã C# cho thế giới ADAPTIVE / MASSING — nơi ĐIỂM điều khiển hình.

===========================================================================
KẾT LUẬN NGẮN: HÔM NAY MODULE NÀY **KHÔNG DỰNG ĐƯỢC** DẦM CHỦ ADAPTIVE
===========================================================================
Không phải vì chưa viết. Vì cổng chặn nói KHÔNG, và cổng chặn đang đúng.

Đây là môi trường CHÍNH của dự án thật (dầm chủ, gờ lan can, lan can thép đều
là adaptive 2 điểm). Nhưng RFC-1.1.0 §3 — sau đợt bổ sung [A3]/[A4]/[A5] —
nói ba điều làm thay đổi hẳn thiết kế của module này:

**[A4] KẾT QUẢ ÂM, ĐẮT NHẤT.** ``NewLoftForm`` dựng ra form đẹp trong family
adaptive, và form đó **KHÔNG chạy theo điểm thích ứng**::

    spine 10.000 -> 24.104 m     (spine CÓ flex)
    form  54.533 -> 54.533 m3    (tỷ lệ 1.0000 — ĐỨNG YÊN)

Đúng thứ mà hợp đồng nhiệm vụ gọi là *"khối cứng đội lốt family — tệ hơn
DirectShape vì trông như tham số mà không phải"*. Cho nên module này **từ chối
phát** đường ``NewLoftForm`` cho cấu kiện: đó là phép ``NewLoftFormFlex``,
``MEASURED_FAIL``. Muốn khối tĩnh thì đã có ``tmp/rvt_loader_csharp.py``
(DirectShape) — nó trung thực hơn, vì không giả vờ là tham số.

**[A5] LỐI ĐÚNG, NHƯNG §3 TỰ MÂU THUẪN.** ``NewSweptBlendForm`` — phép **CÓ
PATH** — giữ được liên kết: thể tích 54.533 -> 131.447 m³, tỷ lệ 2.4104 khớp
đúng tỷ lệ chiều dài. Nhưng **bảng** §3 vẫn ghi hàng ``NewSweptBlendForm =
FAIL``. Hai chỗ trong cùng một mục nói ngược nhau, nên
:data:`~bridge_evolution.revit_family.worlds.OPERATIONS` giữ ``NOT_MEASURED``
và :func:`adaptive_two_point_member` **raise**.

**[A3] BẪY MẶT PHẲNG.** Hợp đồng nhiệm vụ Pha 2 ghi *"dùng
``GetCoordinatePlaneReferenceXY()``"*. RFC-1.1.0 §3 [A3] — viết SAU hợp đồng —
đo được rằng như thế là **SAI**: tiếp tuyến của đường nằm ở ``BasisX``, nên mặt
phẳng XY **CHỨA** path, profile đặt lên đó song song path và ``NewLoftForm``
ném ``InvalidOperationException: "Cannot create loft form."``. Mặt phẳng tiết
diện là **YZ**. Module này theo số đo, không theo hợp đồng, và mã hoá cái bẫy
thành phép ``AdaptivePointCoordinatePlaneXY`` (``MEASURED_FAIL``).

VÌ SAO VẪN VIẾT MODULE MÀ BIẾT LÀ NÓ RAISE
-------------------------------------------
Hợp đồng cho phép: *"viết nhưng gọi ``require_operation`` để nó raise
``NotMeasuredError`` — ghi rõ lựa chọn trong docstring"*. Giá trị nằm ở chỗ:
khi ai đó đo xong và mở ô trong bảng, đường dựng đã sẵn ở đây, **đúng lối
[A5]**, không phải viết lại dưới áp lực.

Và không phải mọi thứ đều chặn. Ba thứ **phát được mã C# THẬT ngay hôm nay**:

* :func:`adaptive_two_point_spine_body` — bộ xương 2 điểm thích ứng + spine.
  Đây là phần đã đo là **CÓ FLEX** (§3 FLEX TEST, sai lệch 3.55E-15).
* :func:`adaptive_section_plane_body` — mặt phẳng tiết diện YZ theo [A3]. Đòi
  ``regenerated_before=True``: cùng [A3] đo được ``GetCoordinateSystem()``
  trước ``Regenerate()`` trả **ma trận đơn vị**, nên đọc sớm là hỏng IM LẶNG.
  Chỗ đặt ``Regenerate()`` giữa chừng là ``pre_regen_lines`` của
  :func:`~bridge_evolution.revit_family.csharp.family_scaffold`.
* :func:`adaptive_flex_probe` — bài đo quyết định, chạy trên ``.rfa`` đã lưu.

RANH GIỚI: THÂN MÃ ≠ FAMILY
---------------------------
Hàm ``*_body`` trả **danh sách dòng C#**, không phải family. Thân mã không tự
lưu được ``.rfa`` nên không thể bị nhầm là sản phẩm giao. Family hoàn chỉnh đi
qua :func:`~bridge_evolution.revit_family.csharp.guarded_family_scaffold`, và
đường đó còn một chặn nữa: dấu claim bắt buộc dùng ``FamilyManager.AddParameter``
mà RFC-1.1.0 §5 ghi **CHƯA ĐO trong family adaptive/mass**. Nên hiện tại
**không** family adaptive nào ra được file — kể cả bộ xương.

OVERLOAD API: GIẢ ĐỊNH ĐƯỢC KHAI BÁO
-------------------------------------
RFC-1.1.0 ghi **kết quả** (chạy được / hỏng / id đối tượng), hiếm khi ghi
**chữ ký hàm**. Module này theo đúng tiền lệ của
:func:`~bridge_evolution.revit_family.csharp.claim_parameters_cs`: cổng chặn
quyết định *được dùng phép nào*, còn overload cụ thể là **giả định khai báo
tường minh**, đánh dấu ``GIA DINH OVERLOAD`` ngay trong mã C# phát ra để người
đọc bên Revit thấy được. Danh sách giả định: :data:`DECLARED_OVERLOADS`.

Ngoại lệ **không** giả định: cách TẠO điểm hosted trên đường. [A5] có dùng
``hostA``/``hostB`` nhưng không cho thấy chỗ khởi tạo, và [A2] đã dạy đúng bài
này một lần (``GetPlacementPoints`` nghe rất hợp lý và KHÔNG TỒN TẠI). Nên đó
là phép ``HostedPointOnCurve``, ``NOT_MEASURED``, và module này đặt profile lên
mặt phẳng của **chính điểm thích ứng** thay vì đoán một tên API.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from .csharp import (
    FT,
    CSharpBuilder,
    CSharpEmitError,
    _num,  # bộ in double xác định DUY NHẤT của gói — viết lại là viết quy tắc song song
    cs_string,
    guarded_family_scaffold,
    m_to_ft,
    xyz,
)
from .worlds import (
    MeasuredStatus,
    NotMeasuredError,
    operation_status,
    require_operation,
    require_operations,
)

__all__ = [
    "AdaptiveTwoPointSpec",
    "SPINE_OPS",
    "SECTION_PLANE_OPS",
    "MEMBER_OPS",
    "VOID_OPS",
    "MASSING_LOFT_OPS",
    "FLEX_PROBE_OPS",
    "FLEX_PRESERVING_FORM_OP",
    "STATIC_FORM_OP",
    "DECLARED_OVERLOADS",
    "blocking_operations",
    "adaptive_two_point_spine_body",
    "adaptive_section_plane_body",
    "adaptive_two_point_member",
    "adaptive_flex_probe",
    "massing_loft_surface",
    "adaptive_void",
    "adaptive_four_point_panel",
]


# ---------------------------------------------------------------------------
# Hai lối dựng khối trong thế giới adaptive — chỉ MỘT lối giữ được tham số
# ---------------------------------------------------------------------------

#: Phép dựng khối **CÓ PATH**. RFC-1.1.0 §3 [A5]: giữ liên kết, FLEX ĐẠT.
FLEX_PRESERVING_FORM_OP = "NewSweptBlendForm"

#: Phép dựng khối **KHÔNG PATH**. §3 [A4]: tạo được form, nhưng form ĐỨNG YÊN.
STATIC_FORM_OP = "NewLoftForm"

#: Bộ xương 2 điểm — phần ĐÃ ĐO LÀ CÓ FLEX (§3 FLEX TEST, sai lệch 3.55E-15).
SPINE_OPS: tuple[str, ...] = (
    "NewReferencePoint",
    "MakeAdaptivePoint",
    "NewCurveByPoints",
)

#: Mặt phẳng tiết diện theo [A3] — YZ, KHÔNG phải XY.
SECTION_PLANE_OPS: tuple[str, ...] = ("AdaptivePointCoordinatePlaneYZ",)

#: Cấu kiện adaptive HOÀN CHỈNH. Ba phép cuối hiện đang CHẶN — xem docstring module.
MEMBER_OPS: tuple[str, ...] = (
    SPINE_OPS
    + SECTION_PLANE_OPS
    + ("NewModelCurve", FLEX_PRESERVING_FORM_OP, "IsAdaptiveComponentFamily")
)

#: Khoét lỗ. ``SolidSolidCut`` là chặn thật — xem [S2] về void hỏng IM LẶNG.
#:
#: Danh sách này phải mô tả ĐÚNG những gì mã C# phát ra dùng: thân mã void
#: dựng profile bằng ``NewModelCurve`` trên mặt phẳng tiết diện YZ, y hệt
#: :data:`MEMBER_OPS`. Khai ít hơn thực dùng là cổng chặn nói dối.
VOID_OPS: tuple[str, ...] = (
    SPINE_OPS
    + SECTION_PLANE_OPS
    + ("NewModelCurve", STATIC_FORM_OP, "SolidSolidCut")
)

#: Mặt trơn thế giới MASSING.
MASSING_LOFT_OPS: tuple[str, ...] = (
    "NewReferencePoint",
    "NewCurveByPoints",
    "NewLoftForm",
    "SaveAs",
)

#: Bài đo quyết định. ``FlexTest`` MEASURED_OK trong ADAPTIVE.
FLEX_PROBE_OPS: tuple[str, ...] = ("FlexTest", "NewReferencePoint")

#: Overload API mà RFC-1.1.0 KHÔNG ghi lại — giả định khai báo tường minh.
#:
#: Cùng nguyên tắc với :func:`~bridge_evolution.revit_family.csharp.claim_parameters_cs`:
#: cổng chặn quyết định *dùng phép nào*, overload là giả định có tên có chỗ.
DECLARED_OVERLOADS: tuple[tuple[str, str], ...] = (
    ("MakeAdaptivePoint",
     "AdaptiveComponentFamilyUtils.MakeAdaptivePoint(Document, ElementId, "
     "AdaptivePointType.PlacementPoint) — §3 ghi 'MakeAdaptivePoint "
     "(PlacementPoint) OK, 2 diem' nhung khong ghi chu ky"),
    ("NewCurveByPoints",
     "FamilyItemFactory.NewCurveByPoints(ReferencePointArray) — §3 ghi "
     "'dai 10.0000 m' nhung khong ghi chu ky"),
    ("AdaptivePointCoordinatePlaneYZ",
     "ReferencePoint.GetCoordinatePlaneReferenceYZ() khong tham so, tra "
     "Reference dung cho SketchPlane.Create(Document, Reference) — [A3] goi "
     "dich danh ten ham nhung khong ghi chu ky"),
    ("NewSweptBlendForm",
     "FamilyItemFactory.NewSweptBlendForm(bool, ReferenceArray, "
     "ReferenceArrayArray) — doan ma [A5] cho thay dung ba doi so nay"),
    ("FlexTest",
     "ReferencePoint.Position setter + Document.Regenerate() — §3 ghi ket qua "
     "do, khong ghi cach doi vi tri diem"),
    ("NewLoftForm",
     "FamilyItemFactory.NewLoftForm(bool isSolid, ReferenceArrayArray) — §3 "
     "ghi 'id=7706' cho ca bien the void nhung khong ghi chu ky; cung overload "
     "dung cho massing_loft_surface va adaptive_void"),
)

_CLAIM_BLOCKER_HINT = (
    "Ghi chú: kể cả khi phép dựng hình được mở, đường ra file .rfa còn một "
    "chặn nữa — dấu claim bắt buộc dùng FamilyManager.AddParameter, mà "
    "RFC-1.1.0 §5 ghi CHƯA ĐO trong family adaptive/mass."
)


# ---------------------------------------------------------------------------
# Đặc tả cấu kiện 2 điểm
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AdaptiveTwoPointSpec:
    """Cấu kiện adaptive 2 điểm, tiết diện chữ nhật THUÔN.

    Toạ độ theo hệ CẦU của repo: ``(x dọc cầu, y CAO ĐỘ, z NGANG cầu)``, đơn vị
    **mét**. Phép hoán vị sang trục Revit do
    :func:`~bridge_evolution.revit_family.csharp.xyz` lo.

    Hai điểm là **điểm thích ứng**: chúng là giao diện tham số của cấu kiện.
    Kích thước tiết diện ở hai đầu khác nhau thì được khối thuôn — đúng hình
    dầm chủ và gờ lan can của dự án thật.

    Attributes:
        point_a_m: điểm thích ứng 1 ``(x, y, z)`` mét.
        point_b_m: điểm thích ứng 2 ``(x, y, z)`` mét.
        width_start_m: bề rộng tiết diện (NGANG cầu) tại điểm 1.
        height_start_m: chiều cao tiết diện tại điểm 1.
        width_end_m: bề rộng tiết diện tại điểm 2.
        height_end_m: chiều cao tiết diện tại điểm 2.
        name: tên dùng cho biến C# và tên transaction. ASCII, kiểu định danh.
    """

    point_a_m: tuple[float, float, float]
    point_b_m: tuple[float, float, float]
    width_start_m: float
    height_start_m: float
    width_end_m: float
    height_end_m: float
    name: str = "DYLIGHT_AdaptiveMember"

    def __post_init__(self) -> None:
        a = _check_point(self.point_a_m, "point_a_m")
        b = _check_point(self.point_b_m, "point_b_m")
        span = sum((ai - bi) ** 2 for ai, bi in zip(a, b)) ** 0.5
        if span < 1e-6:
            raise CSharpEmitError(
                f"Hai điểm thích ứng trùng nhau (cách {span:.3e} m). Spine dài 0 "
                f"thì NewCurveByPoints không có gì để dựng, và FLEX TEST mất "
                f"mẫu số — tỷ lệ chiều dài chia cho 0."
            )
        for field_name in ("width_start_m", "height_start_m",
                           "width_end_m", "height_end_m"):
            _check_positive(getattr(self, field_name), field_name)
        if not isinstance(self.name, str) or not self.name.strip():
            raise CSharpEmitError("name rỗng.")
        if not self.name.replace("_", "").isalnum() or not self.name.isascii():
            raise CSharpEmitError(
                f"name {self.name!r} phải là ASCII kiểu định danh (chữ, số, '_') "
                f"— nó đi thẳng vào tên biến C# và tên transaction."
            )

    @property
    def span_m(self) -> float:
        """Khoảng cách thẳng giữa hai điểm thích ứng, mét."""
        return sum((a - b) ** 2
                   for a, b in zip(self.point_a_m, self.point_b_m)) ** 0.5


def _check_point(value: object, what: str) -> tuple[float, float, float]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise CSharpEmitError(f"{what} phải là bộ ba số, nhận {type(value).__name__}")
    if len(value) != 3:
        raise CSharpEmitError(f"{what} phải có đúng 3 thành phần, nhận {len(value)}")
    return tuple(m_to_ft(v) / FT for v in value)  # type: ignore[return-value]


def _check_positive(value: float, what: str) -> float:
    number = m_to_ft(value) / FT  # mượn chặn nan/inf của m_to_ft
    if number <= 0.0:
        raise CSharpEmitError(
            f"{what} = {value!r} phải DƯƠNG. Tiết diện rộng 0 hoặc âm cho ra "
            f"profile suy biến; Revit hoặc ném lỗi ở chỗ khác, hoặc dựng ra "
            f"khối rác trông vẫn bình thường."
        )
    return number


# ---------------------------------------------------------------------------
# Tra cứu chặn — xem HẾT blocker một lần, không phải gỡ từng cái một
# ---------------------------------------------------------------------------

def blocking_operations(operations: Iterable[str],
                        template_key: str) -> tuple[tuple[str, MeasuredStatus], ...]:
    """Mọi phép trong ``operations`` KHÔNG phải ``MEASURED_OK`` với template này.

    :func:`~bridge_evolution.revit_family.worlds.require_operations` raise ở
    phép hỏng ĐẦU TIÊN — đúng cho cổng chặn, nhưng khi chẩn đoán thì người ta
    gỡ được một cái rồi lại đâm vào cái kế tiếp. Hàm này trả **toàn bộ** danh
    sách chặn cùng lúc, và **không raise theo trạng thái**.

    Returns:
        Bộ ``(tên phép, trạng thái)`` theo đúng thứ tự ``operations``, chỉ gồm
        phép bị chặn. Rỗng nghĩa là đi qua được cổng.
    """
    out: list[tuple[str, MeasuredStatus]] = []
    for name in operations:
        status = operation_status(name, template_key)
        if status is not MeasuredStatus.MEASURED_OK:
            out.append((name, status))
    return tuple(out)


# ---------------------------------------------------------------------------
# THÂN MÃ 1 — bộ xương 2 điểm thích ứng (PHÁT ĐƯỢC HÔM NAY)
# ---------------------------------------------------------------------------

def adaptive_two_point_spine_body(spec: AdaptiveTwoPointSpec, *,
                                  template_key: str = "adaptive") -> list[str]:
    """Thân mã C#: hai điểm thích ứng + spine nối chúng.

    Đây là phần adaptive **đã đo là CÓ FLEX**: RFC-1.1.0 §3 FLEX TEST dời điểm
    2 tới ``(25, 8, 0)`` và spine đi từ 10.0000 m lên 26.2488 m, đúng
    ``sqrt(25² + 8²)``, sai lệch ``3.55E-15``.

    Ba phép đều ``MEASURED_OK`` trong ADAPTIVE nên hàm này **phát mã thật**.
    Nó KHÔNG dựng khối — muốn khối thì xem :func:`adaptive_two_point_member`,
    và đọc lý do nó chặn.

    Thứ tự phát ra bám nguyên tắc "hình do ĐIỂM điều khiển":

    1. ``NewReferencePoint`` hai lần;
    2. ``MakeAdaptivePoint`` cho **cả hai** — chưa gọi bước này thì chúng chỉ
       là điểm tham chiếu thường, không phải giao diện tham số của family;
    3. ``NewCurveByPoints`` nối hai điểm.

    Args:
        spec: đặc tả cấu kiện.
        template_key: template trong bảng đã đo (mặc định ``"adaptive"``).

    Returns:
        Danh sách dòng C# ASCII, chạy TRONG transaction của family document
        ``fd``.

    Raises:
        UnsupportedInWorldError: template không thuộc thế giới điểm.
        NotMeasuredError: một phép chưa đo trong thế giới đó.
    """
    require_operations(SPINE_OPS, template_key)

    b = CSharpBuilder()
    b.comment("=" * 66)
    b.comment(f"SPINE ADAPTIVE 2 DIEM - {spec.name}")
    b.comment("Hinh do DIEM dieu khien. Hai diem nay LA giao dien tham so.")
    b.comment("[A3] He toa do cua ReferencePoint CHI DUNG SAU Regenerate() -")
    b.comment("     doc GetCoordinateSystem() truoc do tra ma tran don vi.")
    b.comment("=" * 66)
    b.line("FamilyItemFactory fc = fd.FamilyCreate;")
    b.line(f"ReferencePoint ptA = fc.NewReferencePoint({xyz(*spec.point_a_m)});")
    b.line(f"ReferencePoint ptB = fc.NewReferencePoint({xyz(*spec.point_b_m)});")
    b.blank()
    b.comment("GIA DINH OVERLOAD: MakeAdaptivePoint(Document, ElementId, AdaptivePointType)")
    b.comment("Khong lam buoc nay thi chung chi la diem tham chieu thuong.")
    b.line("AdaptiveComponentFamilyUtils.MakeAdaptivePoint(")
    b.line("    fd, ptA.Id, AdaptivePointType.PlacementPoint);")
    b.line("AdaptiveComponentFamilyUtils.MakeAdaptivePoint(")
    b.line("    fd, ptB.Id, AdaptivePointType.PlacementPoint);")
    b.blank()
    b.comment("GIA DINH OVERLOAD: NewCurveByPoints(ReferencePointArray)")
    b.line("ReferencePointArray rpa = new ReferencePointArray();")
    b.line("rpa.Append(ptA);")
    b.line("rpa.Append(ptB);")
    b.line("CurveByPoints spine = fc.NewCurveByPoints(rpa);")
    b.comment(f"span ky vong = {spec.span_m:.6f} m (kiem lai bang FLEX PROBE)")
    return b.build().rstrip("\n").split("\n")


# ---------------------------------------------------------------------------
# THÂN MÃ 2 — mặt phẳng tiết diện theo [A3] (PHÁT ĐƯỢC HÔM NAY)
# ---------------------------------------------------------------------------

def adaptive_section_plane_body(point_var: str, plane_var: str, *,
                                template_key: str = "adaptive",
                                regenerated_before: bool = False) -> list[str]:
    """Thân mã C#: mặt phẳng TIẾT DIỆN của một điểm — **YZ**, không phải XY.

    Đây là chỗ hợp đồng nhiệm vụ Pha 2 nói sai và RFC-1.1.0 §3 [A3] sửa lại.
    Hợp đồng ghi *"dùng ``GetCoordinatePlaneReferenceXY()``"*; [A3] đo được:

    * tiếp tuyến của đường nằm ở ``BasisX`` (spine hướng ``(0.6, 0.8, 0)`` cho
      ``BasisX=(0.600, 0.800, 0.000)``);
    * nên mặt phẳng ``XY`` **CHỨA** path — profile đặt lên đó SONG SONG path và
      ``NewLoftForm`` ném ``InvalidOperationException: "Cannot create loft form."``;
    * mặt phẳng tiết diện đúng là **``YZ``**, căng bởi ``BasisY`` và ``BasisZ``.

    Cái bẫy đã được mã hoá thành dữ liệu: xin phép
    ``AdaptivePointCoordinatePlaneXY`` thì cổng raise ``UnsupportedInWorldError``
    kèm đúng câu lỗi trên. Hàm này chỉ phát lối YZ.

    Mã phát ra lấy cả ``Transform`` của điểm, vì profile cần **gốc + hai trục**
    thì mới xoay theo khi điểm dời — đặt profile bằng toạ độ tuyệt đối là dựng
    đúng lần đầu rồi không flex.

    ``regenerated_before`` — CHẶN THỨ HAI CỦA [A3], VÀ NÓ FAIL-CLOSED
    ----------------------------------------------------------------
    Cùng §3 [A3] còn đo một điều nữa: ``GetCoordinateSystem()`` gọi **TRƯỚC**
    ``Regenerate()`` trả về **ma trận đơn vị**. Với spine dọc trục X thì ma
    trận đơn vị trùng đúng đáp số nên không ai thấy gì sai; với spine chéo
    (dầm chủ trên cầu cong/xiên) profile bị đặt lệch khỏi mặt phẳng tiết diện
    thật — hỏng IM LẶNG.

    Nên hàm này **từ chối phát mã** cho tới khi người gọi chứng minh đã có một
    ``Regenerate()`` chạy trước đó. Cách duy nhất đặt được cờ ấy cho đúng là
    đưa phần dựng điểm/đường vào ``pre_regen_lines`` của
    :func:`~bridge_evolution.revit_family.csharp.family_scaffold` — khuôn đó
    phát ``fd.Regenerate();`` giữa transaction rồi mới tới thân mã này, và tự
    kiểm lại thứ tự trên chuỗi vừa sinh.

    Args:
        point_var: tên biến C# của ``ReferencePoint`` (ví dụ ``"ptA"``).
        plane_var: tiền tố đặt tên cho các biến sinh ra.
        template_key: template trong bảng đã đo.
        regenerated_before: khai báo rằng thân mã này chạy SAU một
            ``Regenerate()``. ``False`` -> raise, không phát mã.

    Returns:
        Danh sách dòng C# ASCII. Sinh ra ba biến: ``<plane_var>Ref``
        (``Reference``), ``<plane_var>Sp`` (``SketchPlane``), ``<plane_var>Tf``
        (``Transform``).

    Raises:
        CSharpEmitError: ``regenerated_before=False`` — xem [A3] ở trên.
    """
    require_operations(SECTION_PLANE_OPS, template_key)
    if not regenerated_before:
        raise CSharpEmitError(
            "[A3] Thân mã này ĐỌC ReferencePoint.GetCoordinateSystem(), mà "
            "RFC-1.1.0 §3 [A3] đo được: gọi TRƯỚC Regenerate() thì nó trả về "
            "MA TRẬN ĐƠN VỊ — sai kiểu IM LẶNG.\n"
            "  Ca spine dọc trục X trùng đúng ma trận đơn vị nên không lộ; "
            "spine chéo (0.6, 0.8, 0) thì [A3] đo BasisY = (-0.800, 0.600, "
            "0.000) SAU Regenerate và (0, 1, 0) TRƯỚC — profile lệch ~53 độ "
            "khỏi mặt phẳng tiết diện thật.\n"
            "  Không có cờ nào bỏ qua phép đo này. Cách đúng: đưa phần dựng "
            "điểm/đường vào pre_regen_lines của family_scaffold rồi gọi lại "
            "với regenerated_before=True.")
    ident = _check_identifier(point_var, "point_var")
    prefix = _check_identifier(plane_var, "plane_var")

    b = CSharpBuilder()
    b.comment("-" * 66)
    b.comment(f"MAT PHANG TIET DIEN cua {ident} - [A3]: YZ, KHONG phai XY.")
    b.comment("Tiep tuyen nam o BasisX => XY CHUA path => profile song song path")
    b.comment('=> NewLoftForm nem "Cannot create loft form." Mat cat dung la YZ.')
    b.comment("GIA DINH OVERLOAD: GetCoordinatePlaneReferenceYZ() khong tham so;")
    b.comment("                   SketchPlane.Create(Document, Reference).")
    b.comment("-" * 66)
    b.line(f"Reference {prefix}Ref = {ident}.GetCoordinatePlaneReferenceYZ();")
    b.line(f"SketchPlane {prefix}Sp = SketchPlane.Create(fd, {prefix}Ref);")
    b.comment("[A3] Transform nay CHI DUNG SAU Regenerate() - khuon da phat mot")
    b.comment("Regenerate() GIUA transaction TRUOC doan nay (pre_regen_lines).")
    b.comment("Goc + hai truc trong mat phang tiet dien la BasisY va BasisZ")
    b.comment("(BasisX la TIEP TUYEN cua path, khong thuoc tiet dien).")
    b.line(f"Transform {prefix}Tf = {ident}.GetCoordinateSystem();")
    return b.build().rstrip("\n").split("\n")


def _check_identifier(value: str, what: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CSharpEmitError(f"{what} rỗng.")
    text = value.strip()
    if not text.isascii() or not text.replace("_", "").isalnum() or text[0].isdigit():
        raise CSharpEmitError(
            f"{what} = {text!r} phải là định danh C# hợp lệ (ASCII, chữ/số/'_', "
            f"không bắt đầu bằng chữ số) — nó đi thẳng vào tên biến."
        )
    return text


# ---------------------------------------------------------------------------
# Khối [A5] — CÓ PATH. Riêng tư và KHÔNG tự gác: cổng nằm ở hàm công khai.
# ---------------------------------------------------------------------------

def _swept_blend_form_lines(spec: AdaptiveTwoPointSpec) -> list[str]:
    """Dòng C# dựng khối theo lối [A5] — ``NewSweptBlendForm`` có PATH.

    **Riêng tư và cố ý KHÔNG gọi cổng chặn.** Cổng đặt ở biên công khai
    (:func:`adaptive_two_point_member`); một hàm riêng tư tự gác thêm lần nữa
    chỉ làm thông điệp lỗi nhân đôi. Đổi lại, test gọi thẳng hàm này để soi
    được hình dạng mã C# của lối [A5] mà **không** phải nới cổng — đó là cách
    duy nhất giữ cho đường dựng này không thành mã chết chưa ai đọc.

    Vì sao lối này chứ không phải ``NewLoftForm``: [A5] truyền **spine làm
    path**, nên form bị ràng buộc vào spine — mà spine do điểm thích ứng điều
    khiển. ``NewLoftForm`` không có path nên loft xong là đứt liên kết ([A4],
    tỷ lệ thể tích 1.0000).
    """
    b = CSharpBuilder()
    b.comment("=" * 66)
    b.comment("KHOI [A5] - NewSweptBlendForm, phep CO PATH.")
    b.comment("MAU CHOT: pathRa mang spine => form bi rang buoc vao spine, ma")
    b.comment("spine do diem thich ung dieu khien => FLEX giu duoc.")
    b.comment("Doi lai NewLoftForm (khong path) thi form dung yen: [A4] do duoc")
    b.comment("54.533 -> 54.533 m3, ty le 1.0000, trong khi spine van flex.")
    b.comment("GIA DINH OVERLOAD: NewSweptBlendForm(bool, ReferenceArray,")
    b.comment("                   ReferenceArrayArray)")
    b.comment("=" * 66)
    b.line("ReferenceArray pathRa = new ReferenceArray();")
    b.line("pathRa.Append(spine.GeometryCurve.Reference);")
    b.blank()
    b.line("ReferenceArrayArray profRaa = new ReferenceArrayArray();")
    b.line("profRaa.Append(profA);")
    b.line("profRaa.Append(profB);")
    b.blank()
    b.line("Form memberForm = fc.NewSweptBlendForm(true, pathRa, profRaa);")
    b.comment(f"tiet dien thuon: {spec.width_start_m:.4f} x {spec.height_start_m:.4f}"
              f" -> {spec.width_end_m:.4f} x {spec.height_end_m:.4f} m")
    return b.build().rstrip("\n").split("\n")


def _rect_profile_lines(prefix: str, plane_prefix: str,
                        width_m: float, height_m: float) -> list[str]:
    """Dòng C#: profile chữ nhật trên mặt phẳng tiết diện của một điểm.

    **Riêng tư, không tự gác** (xem :func:`_swept_blend_form_lines`).

    Profile dựng từ ``Transform`` của ĐIỂM — gốc ``Origin`` cộng ``BasisY`` và
    ``BasisZ`` — chứ không phải từ toạ độ tuyệt đối. Đó là điều kiện để tiết
    diện XOAY THEO khi điểm dời; đặt bằng toạ độ tuyệt đối thì hình đúng lần
    đầu rồi đứng yên.
    """
    hw = _num(m_to_ft(width_m) / 2.0)
    hh = _num(m_to_ft(height_m) / 2.0)
    b = CSharpBuilder()
    b.comment(f"profile chu nhat {prefix}: dung tu Transform CUA DIEM, khong phai")
    b.comment("toa do tuyet doi - co vay tiet dien moi xoay theo khi diem doi.")
    b.line(f"XYZ {prefix}O = {plane_prefix}Tf.Origin;")
    b.line(f"XYZ {prefix}U = {plane_prefix}Tf.BasisY.Multiply({hw});")
    b.line(f"XYZ {prefix}V = {plane_prefix}Tf.BasisZ.Multiply({hh});")
    for idx, (su, sv) in enumerate(((-1, -1), (1, -1), (1, 1), (-1, 1))):
        u = f"{prefix}U" if su > 0 else f"{prefix}U.Negate()"
        v = f"{prefix}V" if sv > 0 else f"{prefix}V.Negate()"
        b.line(f"XYZ {prefix}C{idx} = {prefix}O.Add({u}).Add({v});")
    b.line(f"ReferenceArray {prefix} = new ReferenceArray();")
    for idx in range(4):
        nxt = (idx + 1) % 4
        b.line(f"ModelCurve {prefix}M{idx} = fc.NewModelCurve(")
        b.line(f"    Line.CreateBound({prefix}C{idx}, {prefix}C{nxt}), {plane_prefix}Sp);")
        b.line(f"{prefix}.Append({prefix}M{idx}.GeometryCurve.Reference);")
    return b.build().rstrip("\n").split("\n")


# ---------------------------------------------------------------------------
# CẤU KIỆN HOÀN CHỈNH — hiện đang CHẶN, và đó là câu trả lời đúng
# ---------------------------------------------------------------------------

def adaptive_two_point_member(spec: AdaptiveTwoPointSpec, out_rfa: str, *,
                              template_key: str = "adaptive") -> str:
    """Family adaptive 2 điểm, tiết diện thuôn — **hiện raise, cố ý**.

    Đây là cấu kiện thật của dự án: dầm chủ, gờ lan can, lan can thép. Đường
    dựng viết sẵn theo lối **[A5]** (``NewSweptBlendForm`` có path), không phải
    lối ``NewLoftForm`` mà hợp đồng Pha 2 đề xuất — vì [A4] đo được rằng lối
    ``NewLoftForm`` cho ra khối **đứng yên**.

    LỰA CHỌN ĐÃ GHI RÕ (hợp đồng cho phép hai cách; đây là cách thứ hai)
    -------------------------------------------------------------------
    Hàm này **được viết**, và nó **gọi cổng chặn để raise**. Không có cờ nào
    bỏ qua cổng. Lý do: hợp đồng nhiệm vụ ghi *"family adaptive dựng ra hình
    đúng NHƯNG không chạy theo điểm thì nó chỉ là khối cứng đội lốt family —
    tệ hơn DirectShape"*. Phát ra một family như thế còn tệ hơn không phát gì.

    Các phép đang chặn với ``template_key="adaptive"`` (xem
    :func:`blocking_operations` để lấy đủ danh sách một lần):

    * ``NewModelCurve`` — ``NOT_MEASURED``: §2 chỉ đo trên ``Metric Generic
      Model``, chưa chạy trong thế giới adaptive lần nào. Profile cần model
      curve, nên đây là chặn thật chứ không phải hình thức.
    * ``NewSweptBlendForm`` — ``NOT_MEASURED``: §3 tự mâu thuẫn (bảng ghi FAIL,
      [A5] ghi FLEX ĐẠT). Chặn về phía an toàn cho tới khi hoà giải.

    Muốn khối tĩnh ngay hôm nay thì dùng đường DirectShape đã có
    (``tmp/rvt_loader_csharp.py``): nó trung thực hơn vì không giả vờ tham số.

    HAI GIAI ĐOẠN, VÌ [A3]
    ----------------------
    Thân mã chia làm hai và khuôn phát một ``fd.Regenerate();`` **giữa** chúng:

    1. ``pre_regen_lines`` = bộ xương (điểm thích ứng + spine);
    2. ``body_lines`` = mặt phẳng tiết diện + profile + khối.

    Nếu gộp làm một thì ``GetCoordinateSystem()`` bị đọc TRƯỚC ``Regenerate()``
    và §3 [A3] đo được rằng nó trả **ma trận đơn vị** — profile đặt lệch mà
    không có ngoại lệ nào báo.

    Args:
        spec: đặc tả cấu kiện.
        out_rfa: đường dẫn tuyệt đối ``.rfa`` sẽ ghi ra.
        template_key: template trong bảng đã đo.

    Returns:
        Chuỗi C# — **khi nào** cổng mở.

    Raises:
        NotMeasuredError: hiện tại luôn raise với template adaptive.
        UnsupportedInWorldError: nếu đưa template ngoài thế giới điểm.
    """
    if not isinstance(spec, AdaptiveTwoPointSpec):
        raise CSharpEmitError(
            f"spec phải là AdaptiveTwoPointSpec, nhận {type(spec).__name__}")
    require_operations(MEMBER_OPS, template_key)  # <- cổng: hiện raise ở đây

    # GIAI ĐOẠN 1 — điểm và đường. Chưa đọc hệ toạ độ của điểm ở đây: [A3].
    stage1 = adaptive_two_point_spine_body(spec, template_key=template_key)

    # GIAI ĐOẠN 2 — chạy SAU fd.Regenerate() do khuôn phát ra, nên
    # GetCoordinateSystem() mới trả đúng hệ toạ độ của điểm.
    body: list[str] = []
    body += adaptive_section_plane_body("ptA", "plA", template_key=template_key,
                                        regenerated_before=True)
    body += _rect_profile_lines("profA", "plA",
                                spec.width_start_m, spec.height_start_m)
    body.append("")
    body += adaptive_section_plane_body("ptB", "plB", template_key=template_key,
                                        regenerated_before=True)
    body += _rect_profile_lines("profB", "plB",
                                spec.width_end_m, spec.height_end_m)
    body.append("")
    body += _swept_blend_form_lines(spec)
    body.append("")
    body.append("// [A1] IsAdaptiveComponentFamily nhan Family, KHONG nhan Document.")
    body.append("bool isAdaptive =")
    body.append("    AdaptiveComponentFamilyUtils.IsAdaptiveComponentFamily(fd.OwnerFamily);")
    return guarded_family_scaffold(template_key, out_rfa, MEMBER_OPS, body,
                                   f"DYLIGHT {spec.name} F0 IDEA",
                                   pre_regen_lines=stage1)


def adaptive_void(spec: AdaptiveTwoPointSpec, out_rfa: str, *,
                  template_key: str = "adaptive") -> str:
    """Khối VOID adaptive (``NewLoftForm`` với ``isSolid=false``) — **raise**.

    Tạo *đối tượng* void trong family adaptive là ``MEASURED_OK`` (§3, id=7706).
    Nhưng làm cho nó **KHOÉT** thì chưa ai đo, và §2 **[S2]** cho thấy đó là
    một chặn thật chứ không phải khắt khe vô cớ::

        form solid=1  void=1                 <- void CO ton tai
        the tich     = 200.000 m3            <- DUNG BANG 10x8x2.5, tuc KHONG cat
        CanElementCutElement = False   reason = CutNotAppropriateForElements

    Void tạo ra bình thường, hiện trong danh sách phần tử, và **không khoét gì
    cả**. Hỏng kiểu im lặng — chỉ đo thể tích mới lộ. Vì thế
    :data:`VOID_OPS` gồm ``SolidSolidCut``, và phép đó ``NOT_MEASURED`` ngoài
    thế giới SKETCH (nơi nó ``MEASURED_FAIL``).

    Chính thông báo lỗi của [S2] có nhắc ``adaptive component family`` như nơi
    cut hợp lệ — nhưng gợi ý trong một câu lỗi **không phải phép đo**.

    ĐƯỜNG DỰNG VIẾT SẴN, BIÊN DỊCH ĐƯỢC
    -----------------------------------
    Hàm raise, nhưng thân mã bên dưới là thân mã THẬT: hai profile chữ nhật
    dựng trên mặt phẳng tiết diện của chính hai điểm thích ứng, gom vào một
    ``ReferenceArrayArray``, rồi ``NewLoftForm(false, ...)``. Một đường dựng
    "sẵn ở đây" mà tham chiếu biến chưa khai báo thì ngày cổng mở vẫn phải
    viết lại — tức là không sẵn gì cả.
    """
    if not isinstance(spec, AdaptiveTwoPointSpec):
        raise CSharpEmitError(
            f"spec phải là AdaptiveTwoPointSpec, nhận {type(spec).__name__}")
    require_operations(VOID_OPS, template_key)  # <- cổng: hiện raise

    stage1 = adaptive_two_point_spine_body(spec, template_key=template_key)
    body = _void_form_lines(spec, template_key=template_key)
    return guarded_family_scaffold(template_key, out_rfa, VOID_OPS, body,
                                   f"DYLIGHT {spec.name} VOID F0 IDEA",
                                   pre_regen_lines=stage1)


def _void_form_lines(spec: AdaptiveTwoPointSpec, *,
                     template_key: str = "adaptive") -> list[str]:
    """Giai đoạn 2 của đường VOID — profile + ``NewLoftForm(false, ...)``.

    **Riêng tư và cố ý KHÔNG gọi cổng chặn của void**, cùng lý do với
    :func:`_swept_blend_form_lines`: cổng đặt ở biên công khai
    (:func:`adaptive_void`), còn hàm này để test soi được hình dạng mã C# mà
    không phải nới cổng. Đó là cách duy nhất giữ cho một đường dựng ĐANG BỊ
    CHẶN không mục thành mã chết — ví dụ tham chiếu một biến chưa khai báo,
    thứ chỉ lộ ra vào đúng ngày ai đó mở cổng.
    """
    body: list[str] = []
    body.append("// VOID: NewLoftForm(false, ...) - muc 3 id=7706 tao duoc.")
    body.append("// [S2] PHAI doi chieu THE TICH sau khi tao void; dem phan tu")
    body.append("//      thi thay du solid + void ngay ca khi KHONG he cat.")
    body.append("")
    body += adaptive_section_plane_body("ptA", "plVA", template_key=template_key,
                                        regenerated_before=True)
    body += _rect_profile_lines("voidA", "plVA",
                                spec.width_start_m, spec.height_start_m)
    body.append("")
    body += adaptive_section_plane_body("ptB", "plVB", template_key=template_key,
                                        regenerated_before=True)
    body += _rect_profile_lines("voidB", "plVB",
                                spec.width_end_m, spec.height_end_m)
    body.append("")
    body.append("// GIA DINH OVERLOAD: NewLoftForm(bool, ReferenceArrayArray)")
    body.append("ReferenceArrayArray voidProfiles = new ReferenceArrayArray();")
    body.append("voidProfiles.Append(voidA);")
    body.append("voidProfiles.Append(voidB);")
    body.append("Form voidForm = fc.NewLoftForm(false, voidProfiles);")
    return body


def massing_loft_surface(profiles_m: Sequence[Sequence[tuple[float, float, float]]],
                         out_rfa: str, *, template_key: str = "mass") -> str:
    """Mặt trơn thế giới MASSING (``Metric Mass``, ``NewLoftForm`` nhiều profile)
    — **raise**.

    Dùng cho mặt cầu cong / vênh siêu cao, theo ánh xạ §6. Thế giới MASSING có
    ``IsAdaptiveComponentFamily = False`` mà vẫn dựng được điểm + form — đó là
    cái bẫy §1, và :func:`~bridge_evolution.revit_family.worlds.world_of` xử lý
    nó bằng template chứ không bằng cờ.

    Chặn hiện tại với ``template_key="mass"``:

    * ``NewCurveByPoints`` — ``NOT_MEASURED``: §3 chỉ đo trên template adaptive.
    * ``SaveAs`` — ``NOT_MEASURED``: §5 ghi rõ mới lưu ``.rfa`` từ SKETCH và
      ADAPTIVE; *"rất có thể chạy được vì SaveAs là API mức Document, nhưng
      SUY RA không phải ĐO"*.

    Ở đây [A4] ÍT nguy hiểm hơn: mặt massing là hình học nền, không ai đọc nó
    như cấu kiện tham số. Nhưng ``NewLoftForm`` vẫn cho khối tĩnh — đừng gọi
    kết quả là family tham số.

    Args:
        profiles_m: dãy profile, mỗi profile là dãy điểm ``(x, y, z)`` mét.
            Cần **tối thiểu 2** profile thì mới loft được.
        out_rfa: đường dẫn ``.rfa``.
        template_key: mặc định ``"mass"``.
    """
    profiles = [list(p) for p in profiles_m]
    if len(profiles) < 2:
        raise CSharpEmitError(
            f"NewLoftForm cần TỐI THIỂU 2 profile, nhận {len(profiles)}. Một "
            f"profile thì không có gì để loft qua."
        )
    for i, prof in enumerate(profiles):
        if len(prof) < 2:
            raise CSharpEmitError(
                f"profile[{i}] chỉ có {len(prof)} điểm — cần ít nhất 2.")
        for pt in prof:
            _check_point(pt, f"profile[{i}]")
    require_operations(MASSING_LOFT_OPS, template_key)  # <- cổng: hiện raise

    b = CSharpBuilder()
    b.comment("MASSING - mat tron qua nhieu profile. The gioi MASSING co")
    b.comment("IsAdaptiveComponentFamily = False ma van dung duoc diem + form.")
    b.line("FamilyItemFactory fc = fd.FamilyCreate;")
    b.line("ReferenceArrayArray massRaa = new ReferenceArrayArray();")
    for i, prof in enumerate(profiles):
        b.blank()
        b.line("ReferencePointArray mp%d = new ReferencePointArray();" % i)
        for j, pt in enumerate(prof):
            b.line(f"mp{i}.Append(fc.NewReferencePoint({xyz(*pt)}));")
        b.line(f"CurveByPoints mc{i} = fc.NewCurveByPoints(mp{i});")
        b.line(f"ReferenceArray mr{i} = new ReferenceArray();")
        b.line(f"mr{i}.Append(mc{i}.GeometryCurve.Reference);")
        b.line(f"massRaa.Append(mr{i});")
    b.blank()
    b.comment("GIA DINH OVERLOAD: NewLoftForm(bool, ReferenceArrayArray)")
    b.line("Form massForm = fc.NewLoftForm(true, massRaa);")
    body = b.build().rstrip("\n").split("\n")
    return guarded_family_scaffold(template_key, out_rfa, MASSING_LOFT_OPS, body,
                                   "DYLIGHT massing surface F0 IDEA")


def adaptive_four_point_panel(*_args: object, **_kwargs: object) -> str:
    """Family adaptive **4 điểm** — luôn raise :class:`NotMeasuredError`.

    Viết ra để cái chặn có **địa chỉ**: người đi tìm "panel 4 điểm" gặp hàm
    này và đọc được lý do, thay vì không tìm thấy gì rồi tự dựng lấy.

    RFC-1.1.0 §5: skill dựng cầu của chủ dự án ghi lại panel adaptive 4 điểm
    đặt tự động bị **MÉO**, đã phải lùi về DirectShape cho dầm ngang. Ranh giới
    chưa rõ. Kết quả [A5] chỉ áp cho **2 điểm** — §3 nói thẳng điều đó.
    """
    require_operation("AdaptiveComponent4Point", "adaptive")
    raise NotMeasuredError(  # pragma: no cover - cổng ở trên luôn raise trước
        "AdaptiveComponent4Point phải chặn ở require_operation.")


# ---------------------------------------------------------------------------
# FLEX PROBE — bài đo quyết định (PHÁT ĐƯỢC HÔM NAY)
# ---------------------------------------------------------------------------

def adaptive_flex_probe(rfa_path: str, *,
                        move_point_to_m: tuple[float, float, float],
                        point_index: int = 1,
                        tolerance: float = 1e-6) -> str:
    """Sinh C# CHẠY FLEX TEST trên một ``.rfa`` đã lưu — **phát mã thật**.

    Mở file, đo **thể tích khối** và **chiều dài spine**, dời một điểm thích
    ứng, ``Regenerate()``, đo lại, trả JSON có cả hai lần đo và cờ ``CHAY_THEO``.

    VÌ SAO PHẢI ĐO CẢ THỂ TÍCH, KHÔNG CHỈ SPINE
    -------------------------------------------
    Đây là bài học [A4], và nó là lý do tồn tại của hàm này. Trong ca [A4]:

    ====================  ==========  ==========  =========
    đại lượng             trước       sau         tỷ lệ
    ====================  ==========  ==========  =========
    chiều dài spine       10.000 m    24.104 m    2.4104
    thể tích form         54.533 m³   54.533 m³   **1.0000**
    ====================  ==========  ==========  =========

    Một probe chỉ đo spine sẽ báo **ĐẠT** cho family đó — trong khi khối hoàn
    toàn đứng yên. Nên cờ ``CHAY_THEO`` ở đây đòi **cả hai** cùng đổi::

        CHAY_THEO = spine_co_doi AND the_tich_co_doi

    KHÔNG PHÁ FILE
    --------------
    Transaction kết thúc bằng ``RollBack()``, nên ``.rfa`` trên đĩa **không đổi**
    sau khi đo. Probe là dụng cụ đo, không phải bước dựng.

    Ngoài ra mã phát ra dùng ``CultureInfo.InvariantCulture`` khi in số: máy này
    chạy locale Việt, ``ToString("F6")`` mặc định cho ra dấu **phẩy** thập phân
    và JSON hỏng ngay.

    Args:
        rfa_path: đường dẫn tuyệt đối ``.rfa`` (phải có thật lúc chạy bên Revit).
        move_point_to_m: vị trí mới ``(x, y, z)`` mét, hệ CẦU, cho điểm được dời.
        point_index: chỉ số điểm thích ứng cần dời, tính theo ``ElementId`` tăng
            dần, gốc 0. Mặc định ``1`` = điểm thứ hai.
        tolerance: ngưỡng coi tỷ lệ là "có đổi" (mặc định ``1e-6``).

    Returns:
        Chuỗi C# ASCII, đẩy thẳng qua ``send_code_to_revit``.

    Raises:
        NotMeasuredError / UnsupportedInWorldError: nếu ``FlexTest`` chưa đo.
        CSharpEmitError: tham số không hợp lệ.
    """
    require_operations(FLEX_PROBE_OPS, "adaptive")

    if not isinstance(rfa_path, str) or not rfa_path.strip().lower().endswith(".rfa"):
        raise CSharpEmitError(
            f"rfa_path phải trỏ tới file '.rfa', nhận: {rfa_path!r}")
    target = _check_point(move_point_to_m, "move_point_to_m")
    if not isinstance(point_index, int) or isinstance(point_index, bool) \
            or point_index < 0:
        raise CSharpEmitError(
            f"point_index phải là số nguyên >= 0, nhận {point_index!r}")
    tol = m_to_ft(tolerance) / FT
    if tol <= 0.0:
        raise CSharpEmitError(f"tolerance phải DƯƠNG, nhận {tolerance!r}")

    ft3 = _num(FT * FT * FT)
    b = CSharpBuilder()
    b.line("// " + "=" * 70)
    b.comment("DYLIGHT BRD-036 - FLEX PROBE tren mot .rfa da luu")
    b.comment("[A4] SPINE FLEX KHONG KEO THEO FORM FLEX. Do duoc mot ca:")
    b.comment("     spine 10.000 -> 24.104 m NHUNG the tich 54.533 -> 54.533 m3.")
    b.comment("     Probe chi do spine se bao DAT cho mot family HONG.")
    b.comment("     => CHAY_THEO doi CA HAI dai luong cung doi.")
    b.comment("Transaction ket thuc bang RollBack: file tren dia KHONG doi.")
    b.line("// " + "=" * 70)
    b.line(f"string rfaPath = {cs_string(rfa_path.strip())};")
    b.blank()
    with b.block("if (!System.IO.File.Exists(rfaPath))"):
        b.line('return "LOI: khong thay file " + rfaPath;')
    b.blank()
    b.comment("Chi DOC document cua host de lay Application.")
    b.line("var app = document.Application;")
    b.line("Document fdoc = app.OpenDocumentFile(rfaPath);")
    with b.block("if (fdoc == null)"):
        b.line('return "LOI: OpenDocumentFile tra ve null cho " + rfaPath;')
    b.blank()
    b.line('string outJson = "";')
    with b.block("try"):
        b.line("var ptList = new FilteredElementCollector(fdoc)")
        b.line("    .OfClass(typeof(ReferencePoint))")
        b.line("    .Cast<ReferencePoint>()")
        b.line("    .OrderBy(p => p.Id.Value)")
        b.line("    .ToList();")
        with b.block(f"if (ptList.Count <= {point_index})"):
            b.line("fdoc.Close(false);")
            b.line('return "LOI: chi co " + ptList.Count + " ReferencePoint, '
                   f'can chi so {point_index}";')
        b.line(f"ReferencePoint moved = ptList[{point_index}];")
        b.blank()
        b.line("double[] volM3 = new double[2];")
        b.line("double[] spineM = new double[2];")
        b.blank()
        with b.block('using (Transaction ptx = new Transaction(fdoc, "DYLIGHT flex probe"))'):
            b.line("ptx.Start();")
            with b.block("for (int pass = 0; pass < 2; pass++)"):
                with b.block("if (pass == 1)"):
                    b.comment("--- DOI DIEM THICH UNG roi Regenerate TRONG transaction ---")
                    b.line(f"moved.Position = {xyz(*target)};")
                    b.line("fdoc.Regenerate();")
                b.blank()
                b.comment("THE TICH: cong moi Solid cua moi GenericForm.")
                b.line("double vFt3 = 0.0;")
                b.line("var forms = new FilteredElementCollector(fdoc)")
                b.line("    .OfClass(typeof(GenericForm))")
                b.line("    .Cast<GenericForm>()")
                b.line("    .ToList();")
                with b.block("foreach (GenericForm gf in forms)"):
                    b.line("GeometryElement ge = gf.get_Geometry(new Options());")
                    b.line("if (ge == null) { continue; }")
                    with b.block("foreach (GeometryObject go in ge)"):
                        b.line("Solid sd = go as Solid;")
                        b.line("if (sd != null) { vFt3 += sd.Volume; }")
                b.line(f"volM3[pass] = vFt3 / {ft3};")
                b.blank()
                b.comment("CHIEU DAI SPINE: cong moi CurveByPoints.")
                b.line("double lFt = 0.0;")
                b.line("var spines = new FilteredElementCollector(fdoc)")
                b.line("    .OfClass(typeof(CurveByPoints))")
                b.line("    .Cast<CurveByPoints>()")
                b.line("    .ToList();")
                with b.block("foreach (CurveByPoints cb in spines)"):
                    b.line("if (cb.GeometryCurve != null)")
                    b.line("{ lFt += cb.GeometryCurve.Length; }")
                b.line(f"spineM[pass] = lFt / {_num(FT)};")
            b.blank()
            b.comment("ROLLBACK: probe la dung cu DO, khong phai buoc dung.")
            b.line("ptx.RollBack();")
        b.blank()
        b.line("double rSpine = spineM[0] > 1e-12 ? spineM[1] / spineM[0] : 0.0;")
        b.line("double rVol   = volM3[0]  > 1e-12 ? volM3[1]  / volM3[0]  : 0.0;")
        b.line(f"bool spineFlex = System.Math.Abs(rSpine - 1.0) > {_num(tol)};")
        b.line(f"bool volFlex   = System.Math.Abs(rVol   - 1.0) > {_num(tol)};")
        b.comment("[A4]: doi CA HAI. Spine flex mot minh la ca HONG da gap.")
        b.line("bool chayTheo = spineFlex && volFlex;")
        b.line("bool coKhoi = volM3[0] > 1e-12;")
        b.blank()
        b.line("var ci = System.Globalization.CultureInfo.InvariantCulture;")
        b.comment("InvariantCulture BAT BUOC: locale Viet in dau PHAY thap phan")
        b.comment("va JSON hong ngay tai do.")
        b.line("outJson =")
        b.line(f'    {cs_string("{")}')
        b.line(f'    + {cs_string(chr(34) + "schema" + chr(34) + ": " + chr(34) + "dylight.flex_probe/1" + chr(34) + ", ")}')
        b.line(f'    + {cs_string(chr(34) + "rfa" + chr(34) + ": " + chr(34))} '
               f'+ rfaPath.Replace({cs_string(chr(92))}, {cs_string(chr(92) * 2)}) '
               f'+ {cs_string(chr(34) + ", ")}')
        b.line(f'    + {cs_string(chr(34) + "point_index" + chr(34) + ": ")} '
               f'+ {point_index}'
               f' + {cs_string(", ")}')
        _json_num(b, "spine_truoc_m", "spineM[0]")
        _json_num(b, "spine_sau_m", "spineM[1]")
        _json_num(b, "the_tich_truoc_m3", "volM3[0]")
        _json_num(b, "the_tich_sau_m3", "volM3[1]")
        _json_num(b, "ty_le_spine", "rSpine")
        _json_num(b, "ty_le_the_tich", "rVol")
        _json_bool(b, "spine_co_flex", "spineFlex")
        _json_bool(b, "the_tich_co_flex", "volFlex")
        _json_bool(b, "co_khoi", "coKhoi")
        b.line(f'    + {cs_string(chr(34) + "CHAY_THEO" + chr(34) + ": ")}'
               f' + (chayTheo ? {cs_string("true")} : {cs_string("false")})')
        b.line(f'    + {cs_string("}")};')
        b.blank()
        b.line("fdoc.Close(false);")
    with b.block("catch (Exception ex)"):
        b.line("try { fdoc.Close(false); } catch { }")
        b.line('return "LOI: " + ex.GetType().Name + ": " + ex.Message;')
    b.blank()
    b.line("return outJson;")
    return b.build()


def _json_num(b: CSharpBuilder, key: str, expr: str) -> None:
    """Một cặp ``"key": <số>`` trong chuỗi JSON C#, in bằng InvariantCulture."""
    b.line(f'    + {cs_string(chr(34) + key + chr(34) + ": ")}'
           f' + {expr}.ToString({cs_string("F6")}, ci)'
           f' + {cs_string(", ")}')


def _json_bool(b: CSharpBuilder, key: str, expr: str) -> None:
    """Một cặp ``"key": true|false`` trong chuỗi JSON C#."""
    b.line(f'    + {cs_string(chr(34) + key + chr(34) + ": ")}'
           f' + ({expr} ? {cs_string("true")} : {cs_string("false")})'
           f' + {cs_string(", ")}')
