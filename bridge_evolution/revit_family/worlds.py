"""Mô hình HAI THẾ GIỚI dựng hình của Revit — mã hoá RFC-1.1.0 thành DỮ LIỆU.

===========================================================================
GIÁ TRỊ CỐT LÕI: **không thể sinh ra C# mà ta đã ĐO là hỏng**
===========================================================================
Module này KHÔNG dựng hình. Nó là cái CỔNG. Mọi bộ sinh mã trong gói
``bridge_evolution.revit_family`` phải đi qua :func:`require_operation`
TRƯỚC khi phát một dòng C# nào.

Ba trạng thái, ba cách xử:

===============  ==================================================
Trạng thái       :func:`require_operation` làm gì
===============  ==================================================
MEASURED_OK      trả ``None`` (đi tiếp)
MEASURED_FAIL    raise :class:`UnsupportedInWorldError` — ĐÃ ĐO LÀ HỎNG
NOT_MEASURED     raise :class:`NotMeasuredError` — CHƯA ĐO ≠ không có
===============  ==================================================

**CHƯA ĐO không phải là ABSENT.** Ở đợt đo RFC-1.1.0, ``NewBlend`` và
``NewRevolution`` đều trả 0 đối tượng ở lần chạy đầu; nếu ghi ABSENT lúc đó
thì ma trận đã SAI — cả hai chạy được, lỗi nằm ở tham số người gọi truyền
vào. Vì vậy ở đây CHƯA ĐO nghĩa là **không biết**, và không biết thì chặn.

NGUỒN SỰ THẬT DUY NHẤT
----------------------
``docs/revit_family_capability.md`` (RFC-1.1.0), đo trên **Revit 2026** máy
này ngày 2026-08-26 qua ``send_code_to_revit``. Mọi ô trong hai bảng dưới đây
đều trỏ ngược về một mục của tài liệu đó qua trường ``evidence``. Không ô nào
đọc từ tài liệu API của Autodesk.

BỐN THẾ GIỚI — TEMPLATE QUYẾT ĐỊNH, KHÔNG SỬA ĐƯỢC SAU
------------------------------------------------------
* ``SKETCH``   — ``FamilyItemFactory``: Extrusion/Blend/Sweep/SweptBlend/
  Revolution. ``NewReferencePoint`` ném ``FamilyContextException``.
* ``ADAPTIVE`` — điểm thích ứng + ``Form``. ``NewExtrusion`` ném
  ``InvalidOperationException`` *"not permitted in this type of family"*.
* ``MASSING``  — cùng bộ công cụ với ADAPTIVE (điểm + form) **nhưng**
  ``IsAdaptiveComponentFamily = False``.
* ``TWO_D``    — không dựng khối được.

Bẫy: **``IsAdaptiveComponentFamily`` KHÔNG dùng để đoán thế giới.** Mass trả
``False`` mà vẫn dựng form được. Phải nhìn TEMPLATE.

MỘT MÂU THUẪN NỘI BỘ CỦA RFC-1.1.0 §3 — ĐANG ĐỂ NGỎ, CHẶN VỀ PHÍA AN TOÀN
--------------------------------------------------------------------------
Bảng §3 có hàng ``NewSweptBlendForm | FAIL (chưa loại trừ lỗi người gọi)``.
Nhưng cũng trong §3, mục **[A5]** ghi lại một lần chạy ``NewSweptBlendForm``
**ĐẠT FLEX TEST** (thể tích 54.533 -> 131.447 m³, tỷ lệ 2.4104 khớp đúng tỷ lệ
chiều dài). Hai chỗ trong CÙNG một mục nói ngược nhau.

Bảng dưới đây giữ ``NewSweptBlendForm = NOT_MEASURED`` — tức **chặn**. Lý do:
nới cổng là hành động một chiều (mở ra rồi thì mã sinh ra chạy vào Revit thật),
còn chặn nhầm thì chỉ tốn một lần đo lại. Muốn mở phải hoà giải §3 rồi cập nhật
CẢ tài liệu LẪN bảng này trong cùng một lần.

**Hệ quả trực tiếp:** [A5] là lối dựng khối adaptive **DUY NHẤT** mà tài liệu
ghi là giữ được liên kết tham số, nên
:func:`~bridge_evolution.revit_family.adaptive_family.adaptive_two_point_member`
hiện **raise** :class:`NotMeasuredError`. Đó là cổng chặn hoạt động đúng, không
phải thiếu sót.

VÌ SAO LÀ BẢNG DỮ LIỆU CHỨ KHÔNG PHẢI ``if/else``
--------------------------------------------------
Rải ``if world == ...`` khắp các bộ sinh mã thì mỗi lần đo thêm một phép phải
sửa nhiều chỗ, và không ai kiểm được bảng năng lực có khớp tài liệu không.
Ở đây năng lực là DỮ LIỆU: :data:`TEMPLATES` và :data:`OPERATIONS`. Test đối
chiếu thẳng bảng với tài liệu; bộ sinh mã chỉ gọi một hàm.

Trạng thái được ghi **theo từng thế giới** (``by_world``), không phải một
trường duy nhất cho cả phép — vì RFC-1.1.0 đo theo template, và cùng một phép
có thể MEASURED_OK ở thế giới này, MEASURED_FAIL ở thế giới kia và NOT_MEASURED
ở thế giới thứ ba. Gộp lại thành một cờ là làm mất chính thông tin đắt nhất.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Iterable, Mapping

__all__ = [
    "RFC_VERSION",
    "CAPABILITY_DOC",
    "TEMPLATE_ROOT",
    "FamilyWorld",
    "MeasuredStatus",
    "TemplateSpec",
    "OperationSpec",
    "TEMPLATES",
    "TEMPLATE_ALIASES",
    "OPERATIONS",
    "OPERATION_ALIASES",
    "NOT_MEASURED_OPERATIONS",
    "RevitFamilyCapabilityError",
    "UnknownTemplateError",
    "UnknownOperationError",
    "UnsupportedInWorldError",
    "NotMeasuredError",
    "template_spec",
    "operation_spec",
    "world_of",
    "template_path",
    "template_exists",
    "operation_status",
    "require_operation",
    "require_operations",
    "templates_in_world",
    "operations_ok_in",
    "capability_table",
]

#: Phiên bản ma trận năng lực mà bảng dưới đây mã hoá.
RFC_VERSION = "RFC-1.1.0"

#: Đường dẫn tương đối (trong repo) tới nguồn sự thật.
CAPABILITY_DOC = "docs/revit_family_capability.md"

#: Thư mục template hệ mét của Revit 2026 trên máy này — đã liệt kê được 12/12.
TEMPLATE_ROOT = r"C:\ProgramData\Autodesk\RVT 2026\Family Templates\English"


class FamilyWorld(Enum):
    """Bốn thế giới dựng hình. Template quyết định, hai thế giới 3D loại trừ nhau."""

    SKETCH = "SKETCH"
    ADAPTIVE = "ADAPTIVE"
    MASSING = "MASSING"
    TWO_D = "2D"

    def __str__(self) -> str:  # pragma: no cover - tiện đọc thông điệp lỗi
        return self.value


class MeasuredStatus(Enum):
    """Trạng thái ĐO ĐƯỢC của một phép trong một thế giới.

    ``MEASURED_FAIL`` là *đã chạy và Revit ném lỗi, đã loại trừ lỗi người gọi*.
    ``NOT_MEASURED`` là *chưa biết* — kể cả khi đã thử một lần và hỏng, nếu
    chưa loại trừ lỗi người gọi thì vẫn là ``NOT_MEASURED`` (RFC-1.1.0 §4).
    """

    MEASURED_OK = "MEASURED_OK"
    MEASURED_FAIL = "MEASURED_FAIL"
    NOT_MEASURED = "NOT_MEASURED"


# ---------------------------------------------------------------------------
# Lỗi — tất cả đều là ValueError, fail-closed
# ---------------------------------------------------------------------------

class RevitFamilyCapabilityError(ValueError):
    """Gốc của mọi lỗi cổng năng lực family Revit.

    MRO: ``RevitFamilyCapabilityError -> ValueError``.
    """


class UnknownTemplateError(RevitFamilyCapabilityError):
    """Xin một template không có trong bảng đã đo."""


class UnknownOperationError(RevitFamilyCapabilityError):
    """Xin một phép không có trong bảng đã đo."""


class UnsupportedInWorldError(RevitFamilyCapabilityError):
    """Xin một phép ĐÃ ĐO LÀ HỎNG trong thế giới của template này."""


class NotMeasuredError(RevitFamilyCapabilityError):
    """Xin một phép CHƯA ĐO — không biết thì không sinh mã."""


# ---------------------------------------------------------------------------
# Bảng TEMPLATES — đúng 12 template của RFC-1.1.0 §1, mở được 12/12
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TemplateSpec:
    """Một template ``.rft`` đã mở thử được trên Revit 2026 máy này."""

    key: str
    rft: str
    """Đường dẫn TƯƠNG ĐỐI so với :data:`TEMPLATE_ROOT`, dùng dấu ``\\``."""
    world: FamilyWorld
    category: str
    """Category Revit ĐO ĐƯỢC sau khi mở template (không phải suy đoán)."""
    is_adaptive_family: bool
    """``IsAdaptiveComponentFamily`` ĐO ĐƯỢC. KHÔNG dùng để đoán thế giới."""
    evidence: str

    @property
    def path(self) -> str:
        """Đường dẫn tuyệt đối Windows tới file ``.rft``."""
        return TEMPLATE_ROOT + "\\" + self.rft


def _t(key: str, rft: str, world: FamilyWorld, category: str,
       is_adaptive: bool) -> TemplateSpec:
    return TemplateSpec(
        key=key, rft=rft, world=world, category=category,
        is_adaptive_family=is_adaptive,
        evidence=f"{CAPABILITY_DOC} §1 ({RFC_VERSION}) — hàng '{rft}'",
    )


_S = FamilyWorld.SKETCH
_A = FamilyWorld.ADAPTIVE
_M = FamilyWorld.MASSING
_D = FamilyWorld.TWO_D

#: 12 template đã đo. Khoá là tên NGẮN dùng khắp gói này.
TEMPLATES: Mapping[str, TemplateSpec] = MappingProxyType({
    # --- thế giới SKETCH (FamilyItemFactory) -------------------------------
    "generic_model": _t(
        "generic_model", "Metric Generic Model.rft", _S, "Generic Models", False),
    "structural_framing": _t(
        "structural_framing", "Metric Structural Framing - Beams and Braces.rft",
        _S, "Structural Framing", False),
    "structural_column": _t(
        "structural_column", "Metric Structural Column.rft",
        _S, "Structural Columns", False),
    "structural_foundation": _t(
        "structural_foundation", "Metric Structural Foundation.rft",
        _S, "Structural Foundations", False),
    "generic_model_line_based": _t(
        "generic_model_line_based", "Metric Generic Model line based.rft",
        _S, "Generic Models", False),
    "generic_model_face_based": _t(
        "generic_model_face_based", "Metric Generic Model face based.rft",
        _S, "Generic Models", False),
    # --- thế giới ADAPTIVE (điểm thích ứng + Form) -------------------------
    "adaptive": _t(
        "adaptive", "Metric Generic Model Adaptive.rft",
        _A, "Generic Models", True),
    "pattern_based": _t(
        "pattern_based", "Metric Generic Model Pattern Based.rft",
        _A, "Curtain Panels", True),
    "curtain_panel_pattern_based": _t(
        "curtain_panel_pattern_based", "Metric Curtain Panel Pattern Based.rft",
        _A, "Curtain Panels", True),
    # --- thế giới MASSING (điểm + Form, nhưng isAdaptive = False) ----------
    "mass": _t(
        "mass", "Conceptual Mass\\Metric Mass.rft", _M, "Mass", False),
    # --- thế giới 2D (không dựng khối được) --------------------------------
    "profile_hosted": _t(
        "profile_hosted", "Metric Profile-Hosted.rft", _D, "Profiles", False),
    "detail_item": _t(
        "detail_item", "Metric Detail Item.rft", _D, "Detail Items", False),
})

#: Bí danh tường minh (KHÔNG đoán mờ) cho tên dài trong RFC-1.1.0 §1.
TEMPLATE_ALIASES: Mapping[str, str] = MappingProxyType({
    "generic_model_adaptive": "adaptive",
    "metric_generic_model_adaptive": "adaptive",
    "generic_model_pattern_based": "pattern_based",
    "metric_mass": "mass",
    "conceptual_mass": "mass",
    "structural_framing_beams_and_braces": "structural_framing",
})


# ---------------------------------------------------------------------------
# Bảng OPERATIONS — trạng thái THEO TỪNG THẾ GIỚI
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class OperationSpec:
    """Một phép dựng hình, kèm trạng thái đo được ở CẢ BỐN thế giới."""

    name: str
    api: str
    by_world: Mapping[FamilyWorld, MeasuredStatus]
    evidence: str
    constraints: tuple[str, ...] = ()
    """Ràng buộc BẮT BUỘC đã đo, ví dụ ``[S1]``, ``[B1]``, ``[R1]``."""
    revit_error: str = ""
    """Thông báo lỗi NGUYÊN VĂN của Revit khi ``MEASURED_FAIL``."""
    not_measured_reason: str = ""
    """Vì sao chưa đo — bắt buộc nếu có thế giới nào ``NOT_MEASURED``."""
    aliases: tuple[str, ...] = field(default=(), repr=False)

    def status(self, world: FamilyWorld) -> MeasuredStatus:
        """Trạng thái đo được của phép này trong ``world``."""
        return self.by_world[world]

    @property
    def ok_worlds(self) -> tuple[FamilyWorld, ...]:
        """Các thế giới ĐÃ ĐO LÀ CHẠY ĐƯỢC."""
        return tuple(w for w in FamilyWorld
                     if self.by_world[w] is MeasuredStatus.MEASURED_OK)


_OK = MeasuredStatus.MEASURED_OK
_FAIL = MeasuredStatus.MEASURED_FAIL
_NM = MeasuredStatus.NOT_MEASURED


def _op(name: str, api: str, s: MeasuredStatus, a: MeasuredStatus,
        m: MeasuredStatus, d: MeasuredStatus, evidence: str, *,
        constraints: tuple[str, ...] = (), revit_error: str = "",
        not_measured_reason: str = "",
        aliases: tuple[str, ...] = ()) -> OperationSpec:
    return OperationSpec(
        name=name, api=api,
        by_world=MappingProxyType({_S: s, _A: a, _M: m, _D: d}),
        evidence=evidence, constraints=constraints, revit_error=revit_error,
        not_measured_reason=not_measured_reason, aliases=aliases,
    )


_E1 = f"{CAPABILITY_DOC} §1 ({RFC_VERSION}) — bảng template × phép"
_E2 = f"{CAPABILITY_DOC} §2 ({RFC_VERSION}) — thế giới SKETCH"
_E3 = f"{CAPABILITY_DOC} §3 ({RFC_VERSION}) — thế giới MASSING/ADAPTIVE"
_E4 = f"{CAPABILITY_DOC} §4 ({RFC_VERSION}) — ghi chú phương pháp"
_E5 = f"{CAPABILITY_DOC} §5 ({RFC_VERSION}) — mục CHƯA ĐO"

#: Lý do dùng lại cho cả nhóm FamilyItemFactory ngoài thế giới SKETCH.
_NM_SKETCH_TOOL = (
    "RFC-1.1.0 §1 chỉ đo ĐÍCH DANH NewExtrusion ngoài thế giới SKETCH. Kết luận "
    "§0 ('hai thế giới loại trừ nhau') rất có thể đúng cho cả nhóm "
    "FamilyItemFactory, nhưng SUY RA không phải ĐO — nên ghi CHƯA ĐO."
)
_NM_SKETCH_AUX = (
    "Phép này chỉ đo trên template 'Metric Generic Model' (§2). Ngoài thế giới "
    "SKETCH chưa chạy lần nào."
)
_NM_ADAPTIVE_TOOL = (
    "Phép này chỉ đo trên template 'Metric Generic Model Adaptive' (§3). "
    "Chưa chạy trên template khác."
)

OPERATIONS: Mapping[str, OperationSpec] = MappingProxyType({op.name: op for op in (
    # ================= thế giới SKETCH — FamilyItemFactory =================
    _op("NewExtrusion", "FamilyItemFactory.NewExtrusion",
        _OK, _FAIL, _FAIL, _FAIL, _E1,
        constraints=("Biến thể void (isSolid=false) TẠO ĐƯỢC đối tượng "
                     "(§2: GenericForm VOID = 1) — nhưng ĐỌC TIẾP [S2].",
                     "[S2] VOID trong thế giới SKETCH **KHÔNG KHOÉT** khối và "
                     "hỏng IM LẶNG: NewExtrusion(false, ...) trả về đối tượng "
                     "bình thường, void có mặt trong file, nhưng thể tích khối "
                     "KHÔNG đổi. Muốn khoét thật xem phép SolidSolidCut.",),
        revit_error=('ADAPTIVE: InvalidOperationException "not permitted in this '
                     'type of family"; 2D: ArgumentException'),
        aliases=("NewExtrusionVoid",)),
    _op("NewBlend", "FamilyItemFactory.NewBlend",
        _OK, _NM, _NM, _NM, _E2,
        constraints=("[B1] NewBlend ĐÒI hai profile ở CAO ĐỘ KHÁC NHAU. "
                     "Cả hai ở z=0 -> hỏng.",),
        not_measured_reason=_NM_SKETCH_TOOL),
    _op("NewSweep", "FamilyItemFactory.NewSweep",
        _OK, _NM, _NM, _NM, _E2,
        constraints=("Path NHIỀU ĐOẠN đã đo chạy được (§2: path 2 đoạn).",),
        not_measured_reason=_NM_SKETCH_TOOL),
    _op("NewSweptBlend", "FamilyItemFactory.NewSweptBlend",
        _OK, _NM, _NM, _NM, _E2,
        constraints=(
            "[S1] NewSweptBlend nhận Reference, KHÔNG nhận Curve. Lỗi biên dịch "
            'nguyên văn: "Argument 2: cannot convert from '
            "'Autodesk.Revit.DB.Curve' to 'Autodesk.Revit.DB.Reference'\". "
            "=> PHẢI phát ModelCurve trước rồi truyền mc.GeometryCurve.Reference.",
            "Path CONG ĐƯỢC (đã đo với Arc): một đốt vòm cong tiết diện thuôn = "
            "MỘT phép, không phải chia đoạn.",
        ),
        not_measured_reason=_NM_SKETCH_TOOL),
    _op("NewRevolution", "FamilyItemFactory.NewRevolution",
        _OK, _NM, _NM, _NM, _E2,
        constraints=("[R1] NewRevolution ĐÒI trục NẰM TRONG mặt phẳng phác "
                     "thảo. Trục vuông góc -> hỏng.",),
        not_measured_reason=_NM_SKETCH_TOOL),
    _op("NewModelCurve", "FamilyItemFactory.NewModelCurve",
        _OK, _NM, _NM, _NM, _E2,
        constraints=("Là bước BẮT BUỘC trước NewSweptBlend — xem [S1].",),
        not_measured_reason=_NM_SKETCH_AUX),
    _op("ChangeToReferenceLine", "ModelCurve.ChangeToReferenceLine",
        _OK, _NM, _NM, _NM, _E2,
        constraints=("Sau khi đổi, ElementType vẫn báo 'ModelLine' (đã đo).",),
        not_measured_reason=_NM_SKETCH_AUX),
    _op("NewReferencePlane", "FamilyItemFactory.NewReferencePlane",
        _OK, _NM, _NM, _NM, _E2,
        constraints=("Cần một View để tạo. Đặt tên được (đã đo).",),
        not_measured_reason=_NM_SKETCH_AUX),
    _op("NewModelText", "FamilyItemFactory.NewModelText",
        _OK, _NM, _NM, _NM, _E2,
        not_measured_reason=_NM_SKETCH_AUX),
    _op("InclinedWorkPlane", "SketchPlane.Create + Extrusion trên mặt nghiêng",
        _OK, _NM, _NM, _NM, _E2,
        constraints=("Đã chứng minh với pháp tuyến (0.6, 0, 0.8).",),
        not_measured_reason=_NM_SKETCH_AUX,
        aliases=("SketchPlaneInclined",)),
    _op("LoadFamily", "Document.LoadFamily (family lồng trong family)",
        _OK, _NM, _NM, _NM, _E2,
        constraints=("Đã đo loaded=True — dùng cho cụm lặp (khoang vòm).",),
        not_measured_reason=_NM_SKETCH_AUX),
    _op("AddParameter", "FamilyManager.AddParameter + FamilyManager.Set",
        _OK, _NM, _NM, _NM, _E2,
        constraints=("Đã đo: tham số DYLIGHT_ChieuCao còn nguyên sau khi lưu.",),
        not_measured_reason=(
            "AddParameter chỉ đo trên 'Metric Generic Model' (§2). RFC-1.1.0 §3 "
            "KHÔNG có hàng nào cho AddParameter trong family adaptive/mass. "
            "HỆ QUẢ NẶNG: dấu claim BẮT BUỘC (DYLIGHT_ClaimLevel) do đó CHƯA "
            "dán được vào family adaptive — phải đo trước. Xem 'câu hỏi mở' "
            "của BRD-036 Pha 2."),
        aliases=("FamilyManager.AddParameter",)),
    _op("SaveAs", "Document.SaveAs (.rfa) + Document.Close(false)",
        _OK, _OK, _NM, _NM, _E2,
        constraints=("Bằng chứng: _probe_family.rfa 475.136 B (SKETCH) và "
                     "_probe_adaptive_forms.rfa 499.712 B (ADAPTIVE).",),
        not_measured_reason=(
            "Chưa lưu .rfa từ template Mass hay template 2D lần nào. Rất có thể "
            "chạy được vì SaveAs là API mức Document, nhưng SUY RA không phải ĐO."
        )),

    # ============ thế giới ADAPTIVE / MASSING — điểm + Form ================
    _op("NewReferencePoint", "FamilyItemFactory.NewReferencePoint",
        _FAIL, _OK, _OK, _FAIL, _E1,
        revit_error="SKETCH và 2D: FamilyContextException",
        constraints=("Đã đo id=7586, 7587 trên template adaptive.",
                     "[A3] Hệ toạ độ của điểm CHỈ ĐÚNG SAU Regenerate(). Đọc "
                     "GetCoordinateSystem() trước Regenerate trả ma trận đơn "
                     "vị — sai kiểu im lặng.",)),
    _op("SolidSolidCut",
        "SolidSolidCutUtils.AddCutBetweenSolids (void KHOÉT được solid)",
        _FAIL, _NM, _NM, _NM, _E2,
        revit_error=(
            "SKETCH: CanElementCutElement = False, reason = "
            "CutNotAppropriateForElements; AddCutBetweenSolids ném "
            'ArgumentException: "The element must be in a project document or '
            "in a conceptual model, pattern based curtain panel, or adaptive "
            'component family."'),
        constraints=(
            "[S2] Đo trên FAM_BeMong.rfa: khối 10.0 x 8.0 x 2.5 m cộng một void "
            "1.2 x 1.2 x 3.0 m xuyên qua -> thể tích 200.000 m3, ĐÚNG BẰNG "
            "10x8x2.5, tức KHÔNG cắt (nếu cắt phải còn 196.400).",
            "[S2] Quy tắc: sau khi tạo void PHẢI đối chiếu THỂ TÍCH với giá trị "
            "kỳ vọng đã trừ phần khoét. Đếm phần tử thì thấy đủ solid + void — "
            "chỉ đo thể tích mới lộ ra.",
            "Chính thông báo lỗi nhắc tới 'adaptive component family' như nơi "
            "cut HỢP LỆ — nhưng gợi ý trong một thông báo lỗi KHÔNG PHẢI phép "
            "đo, nên các thế giới kia vẫn NOT_MEASURED."),
        not_measured_reason=(
            "Ngoài SKETCH chưa chạy AddCutBetweenSolids lần nào. Thông báo lỗi "
            "§2 [S2] gợi ý cut hợp lệ trong conceptual model / pattern based "
            "curtain panel / adaptive component family, nhưng GỢI Ý KHÔNG PHẢI "
            "ĐO — cùng nguyên tắc §4.")),
    _op("MakeAdaptivePoint", "AdaptiveComponentFamilyUtils.MakeAdaptivePoint",
        _NM, _OK, _NM, _NM, _E3,
        constraints=("Đã đo 2 điểm PlacementPoint.",),
        not_measured_reason=(
            "Chỉ đo trên 'Metric Generic Model Adaptive'. Mass có "
            "IsAdaptiveComponentFamily = False nên điểm thích ứng ở đó là dấu "
            "hỏi thật sự, chưa chạy.")),
    _op("NewCurveByPoints", "FamilyItemFactory.NewCurveByPoints",
        _NM, _OK, _NM, _NM, _E3,
        constraints=("Đã đo dài 10.0000 m; là đường dùng cho FLEX TEST.",),
        not_measured_reason=_NM_ADAPTIVE_TOOL),
    _op("NewLoftForm", "FamilyItemFactory.NewLoftForm",
        _FAIL, _OK, _OK, _FAIL, _E1,
        revit_error="SKETCH và 2D: cột 'Form' của bảng §1 đo được ❌",
        constraints=("Biến thể VOID (isSolid=false) cũng ĐÃ ĐO LÀ CHẠY ĐƯỢC "
                     "trong ADAPTIVE (§3: id=7706).",
                     "MASSING: bằng chứng là cột 'Form' ✅ của hàng "
                     "'Conceptual Mass\\Metric Mass' trong §1; các id cụ thể ở "
                     "§3 lấy trên template adaptive.",
                     "[A4] Ô này chỉ nói TẠO form được. Form tạo ra KHÔNG chạy "
                     "theo điểm thích ứng — xem phép NewLoftFormFlex "
                     "(MEASURED_FAIL, tỷ lệ thể tích 1.0000). Dùng NewLoftForm "
                     "rồi gọi kết quả là 'family tham số' là nói sai.")),
    _op("NewExtrusionForm", "FamilyItemFactory.NewExtrusionForm",
        _FAIL, _OK, _OK, _FAIL, _E1,
        revit_error="SKETCH và 2D: cột 'Form' của bảng §1 đo được ❌",
        constraints=("ADAPTIVE: đã đo id=7645.",
                     "MASSING: bằng chứng là cột 'Form' ✅ của hàng Mass ở §1.")),
    _op("IsAdaptiveComponentFamily",
        "AdaptiveComponentFamilyUtils.IsAdaptiveComponentFamily",
        _NM, _OK, _NM, _NM, _E3,
        constraints=("[A1] Hàm nhận Family, KHÔNG nhận Document -> phải truyền "
                     "fd.OwnerFamily.",
                     "CẢNH BÁO: cờ này KHÔNG dùng để đoán thế giới. Mass trả "
                     "False mà vẫn dựng form được."),
        not_measured_reason=_NM_ADAPTIVE_TOOL),

    # --- mặt phẳng tiết diện của điểm: XY là BẪY, YZ mới đúng ([A3]) --------
    _op("AdaptivePointCoordinatePlaneYZ",
        "ReferencePoint.GetCoordinatePlaneReferenceYZ",
        _NM, _OK, _NM, _NM, _E3,
        constraints=(
            "[A3] TIẾP TUYẾN của đường nằm ở BasisX, nên mặt phẳng TIẾT DIỆN là "
            "YZ. Đo trên spine hướng (0.6, 0.8, 0): BasisX=(0.600,0.800,0.000), "
            "BasisY=(-0.800,0.600,0.000), BasisZ=(0.000,0.000,1.000).",
            "[A3] Hệ toạ độ CHỈ ĐÚNG SAU Regenerate(). TRƯỚC Regenerate nó trả "
            "ma trận đơn vị (BasisZ=(0,0,1)) — đọc lúc đó là đọc SAI, và sai "
            "kiểu im lặng: vẫn ra một mặt phẳng hợp lệ, chỉ là mặt phẳng khác.",
        ),
        not_measured_reason=_NM_ADAPTIVE_TOOL),
    _op("AdaptivePointCoordinatePlaneXY",
        "ReferencePoint.GetCoordinatePlaneReferenceXY",
        _NM, _FAIL, _NM, _NM, _E3,
        revit_error=(
            "ADAPTIVE: mặt phẳng XY CHỨA đường dẫn, nên profile đặt trên nó SONG "
            "SONG path và NewLoftForm ném InvalidOperationException: "
            '"Cannot create loft form."'),
        constraints=(
            "[A3] Đây là cái bẫy đặt tên: 'XY' nghe như 'mặt phẳng của điểm', "
            "nhưng nó CHỨA path. Mặt phẳng tiết diện là YZ — xem "
            "AdaptivePointCoordinatePlaneYZ.",),
        not_measured_reason=_NM_ADAPTIVE_TOOL),

    # --- [A4] KẾT QUẢ ÂM: loft tạo được nhưng KHÔNG flex -------------------
    _op("NewLoftFormFlex",
        "NewLoftForm + FLEX TEST (form có CHẠY THEO điểm thích ứng không)",
        _NM, _FAIL, _NM, _NM, _E3,
        revit_error=(
            "ADAPTIVE: KHÔNG ném ngoại lệ — HỎNG IM LẶNG. Đo được: spine "
            "10.000 -> 24.104 m (spine CÓ flex) nhưng thể tích form 54.533 -> "
            "54.533 m3 (tỷ lệ 1.0000, ĐỨNG YÊN); hostB trả null NGAY TỪ TRƯỚC "
            "khi flex — các ReferencePoint hosted bị NUỐT vào form lúc tạo."),
        constraints=(
            "[A4] NewLoftForm KHÔNG có path, nên nó chỉ loft hình học tại thời "
            "điểm tạo rồi ĐỨT liên kết ngược về điểm thích ứng.",
            "[A4] Bỏ điểm hosted trung gian và đặt profile trên mặt phẳng của "
            "CHÍNH điểm thích ứng cũng KHÔNG cứu được: form dựng OK, FLEX vẫn "
            "hỏng, tỷ lệ thể tích 1.0000.",
            "[A4] Quy tắc rút ra: trong thế giới adaptive, muốn hình FLEX thì "
            "phải dùng phép dựng CÓ PATH. Phép không path cho ra khối tĩnh — "
            "hình đúng, tham số GIẢ.",
            "Vì sao tách khỏi NewLoftForm: TẠO form là MEASURED_OK, còn FLEX là "
            "MEASURED_FAIL. Gộp hai điều đó vào một ô là làm mất đúng thông tin "
            "đắt nhất của cả đợt đo.",
        ),
        not_measured_reason=_NM_ADAPTIVE_TOOL),

    # --- FLEX TEST: phép đo quyết định, và cái bẫy của nó -------------------
    _op("FlexTest", "dời điểm thích ứng -> Regenerate() -> đo lại",
        _NM, _OK, _NM, _NM, _E3,
        constraints=(
            "Đã đo trên spine: dài 10.0000 -> 26.2488 m, kỳ vọng "
            "sqrt(25^2+8^2) = 26.2488, sai lệch 3.55E-15, CHẠY THEO = True.",
            "[A4] CẢNH BÁO NẶNG: spine flex KHÔNG kéo theo form flex. Probe "
            "PHẢI đo THỂ TÍCH KHỐI chứ không chỉ chiều dài spine — [A4] chính "
            "là ca spine flex đúng mà thể tích đứng yên. Probe chỉ đo spine sẽ "
            "báo ĐẠT cho một family hỏng.",
        ),
        not_measured_reason=_NM_ADAPTIVE_TOOL),

    # ===================== CHƯA ĐO — chặn tuyệt đối ========================
    _op("NewSweptBlendForm", "FamilyItemFactory.NewSweptBlendForm",
        _NM, _NM, _NM, _NM, _E4,
        constraints=(
            "[A5] RFC-1.1.0 §3 ghi lại một lần chạy ĐẠT FLEX TEST: truyền spine "
            "làm PATH (pathRa.Append(spine.GeometryCurve.Reference)) cộng hai "
            "profile trên mặt phẳng YZ theo [A3]; thể tích 54.533 -> 131.447 m3, "
            "tỷ lệ 2.4104 KHỚP CHÍNH XÁC tỷ lệ chiều dài 10.000 -> 24.104.",
            "[A5] Nếu hoà giải được mâu thuẫn §3 thì ĐÂY là lối dựng khối "
            "adaptive DUY NHẤT tài liệu ghi là giữ liên kết tham số — đối lập "
            "với NewLoftFormFlex ([A4], tỷ lệ 1.0000).",
            "[A5] chỉ áp cho adaptive 2 ĐIỂM. Ca 4 điểm xem "
            "AdaptiveComponent4Point.",
        ),
        not_measured_reason=(
            'ĐÃ THỬ trong ADAPTIVE và Revit ném InvalidOperationException '
            '"Cannot create swept blend form." NHƯNG CHƯA loại trừ lỗi người '
            "gọi (nhiều khả năng profile chưa đặt đúng vị trí dọc path), nên "
            "RFC-1.1.0 §3 KHÔNG ghi ABSENT — xem nguyên tắc ở §4.\n"
            "  MÂU THUẪN NỘI BỘ CHƯA HOÀ GIẢI: bảng §3 ghi hàng này là FAIL, "
            "nhưng mục [A5] CÙNG §3 ghi một lần chạy ĐẠT FLEX TEST (54.533 -> "
            "131.447 m3, tỷ lệ 2.4104 khớp tỷ lệ chiều dài). Hai chỗ nói ngược "
            "nhau thì bảng này CHẶN, vì nới cổng là hành động một chiều còn "
            "chặn nhầm chỉ tốn một lần đo lại.\n"
            "  MỞ KHOÁ BẰNG CÁCH: chạy lại probe [A5], hoà giải hàng §3 với mục "
            "[A5] trong cùng một lần sửa tài liệu, rồi mới đổi ô này.")),
    _op("HostedPointOnCurve",
        "tạo ReferencePoint HOSTED trên một đường (tên API CHƯA GHI LẠI)",
        _NM, _NM, _NM, _NM, _E3,
        not_measured_reason=(
            "RFC-1.1.0 §3 đo được HÀNH VI của điểm hosted ([A3]: tiếp tuyến ở "
            "BasisX, hệ toạ độ chỉ đúng sau Regenerate; [A5]: hostA/hostB dùng "
            "trong lần chạy đạt flex) nhưng KHÔNG GHI LẠI TÊN API đã dùng để "
            "TẠO ra nó — đoạn mã [A5] chỉ tham chiếu hostA/hostB, không cho "
            "thấy chỗ khởi tạo.\n"
            "  [A2] là bài học đúng cho đúng ca này: "
            "AdaptiveComponentFamilyUtils.GetPlacementPoints nghe rất hợp lý và "
            "KHÔNG TỒN TẠI. Đoán 'NewPointOnEdge' hay bất kỳ tên nào khác là "
            "lặp lại đúng lỗi đó.\n"
            "  MỞ KHOÁ BẰNG CÁCH: chạy probe tạo điểm hosted trên một "
            "CurveByPoints, ghi TÊN API NGUYÊN VĂN vào §3, rồi mới thêm ô này.")),
    _op("NewRevolveForm", "FamilyItemFactory.NewRevolveForm",
        _NM, _NM, _NM, _NM, _E5,
        not_measured_reason="Chưa chạy lần nào (§5)."),
    _op("NonPlanarProfileForm", "profile KHÔNG PHẲNG trong form adaptive",
        _NM, _NM, _NM, _NM, _E5,
        not_measured_reason=(
            "Nghi vấn (ii) của BRD-036 — form adaptive có nhận profile không "
            "phẳng / mặt phẳng nghiêng theo điểm hay không: CHƯA TRẢ LỜI (§5).")),
    _op("CreateAdaptiveComponentInstance",
        "AdaptiveComponentInstanceUtils.CreateAdaptiveComponentInstance",
        _NM, _NM, _NM, _NM, _E5,
        not_measured_reason="Bước LẮP, thuộc Pha 3. Chưa chạy (§5)."),
    _op("SetInstancePlacementPointElementRefIds",
        "AdaptiveComponentInstanceUtils.SetInstancePlacementPointElementRefIds",
        _NM, _NM, _NM, _NM, _E5,
        not_measured_reason="Bước LẮP, thuộc Pha 3. Chưa chạy (§5)."),
    _op("GetPlacementPoints", "AdaptiveComponentFamilyUtils.GetPlacementPoints",
        _NM, _NM, _NM, _NM, _E3,
        not_measured_reason=(
            "[A2] Tên này KHÔNG tồn tại trên AdaptiveComponentFamilyUtils. Tên "
            "ĐÚNG là gì thì CHƯA ĐO — không được đoán.")),
    _op("NewOpening", "Document.NewOpening / công cụ Opening",
        _NM, _NM, _NM, _NM, _E5,
        not_measured_reason="Có trong ribbon, chưa đo (§5).",
        aliases=("Opening",)),
    _op("NewModelGroup", "Document.Create.NewGroup / Model Group",
        _NM, _NM, _NM, _NM, _E5,
        not_measured_reason="Có trong ribbon, chưa đo (§5).",
        aliases=("ModelGroup",)),
    _op("AdaptiveComponent4Point", "family adaptive 4 ĐIỂM",
        _NM, _NM, _NM, _NM, _E5,
        not_measured_reason=(
            "Skill dựng cầu của chủ dự án ghi lại: panel adaptive 4 điểm đặt tự "
            "động bị MÉO nên đã phải lùi về DirectShape cho dầm ngang. Ranh "
            "giới CHƯA RÕ — phải đo trước khi dùng (§5). Adaptive 2 ĐIỂM thì "
            "khác: đã có tiền lệ chạy thật trên dự án của chủ dự án.")),
)})

#: Bí danh tường minh cho tên phép (gộp từ ``OperationSpec.aliases``).
OPERATION_ALIASES: Mapping[str, str] = MappingProxyType({
    alias: op.name for op in OPERATIONS.values() for alias in op.aliases
})

#: Các phép CHƯA ĐO ở MỌI thế giới — luôn raise :class:`NotMeasuredError`.
NOT_MEASURED_OPERATIONS: frozenset[str] = frozenset(
    op.name for op in OPERATIONS.values()
    if all(st is MeasuredStatus.NOT_MEASURED for st in op.by_world.values())
)


# ---------------------------------------------------------------------------
# Tự kiểm bảng lúc import — bảng sai thì gói không nạp được
# ---------------------------------------------------------------------------

def _validate_tables() -> None:
    """Kiểm bất biến của hai bảng. Sai là lỗi lập trình, không phải lỗi người dùng."""
    if len(TEMPLATES) != 12:
        raise RuntimeError(
            f"TEMPLATES phải có đúng 12 template của {RFC_VERSION} §1, "
            f"đang có {len(TEMPLATES)}")
    for key, spec in TEMPLATES.items():
        if spec.key != key:
            raise RuntimeError(f"TEMPLATES['{key}'].key = '{spec.key}'")
        if not spec.rft.endswith(".rft"):
            raise RuntimeError(f"template '{key}' không trỏ tới file .rft")
        if "/" in spec.rft:
            raise RuntimeError(
                f"template '{key}': đường dẫn Revit phải dùng '\\', không dùng '/'")
    for alias, target in TEMPLATE_ALIASES.items():
        if target not in TEMPLATES:
            raise RuntimeError(f"bí danh template '{alias}' trỏ tới '{target}' không có")
        if alias in TEMPLATES:
            raise RuntimeError(f"bí danh template '{alias}' trùng khoá thật")

    worlds = set(FamilyWorld)
    for name, op in OPERATIONS.items():
        if op.name != name:
            raise RuntimeError(f"OPERATIONS['{name}'].name = '{op.name}'")
        if set(op.by_world) != worlds:
            missing = worlds - set(op.by_world)
            raise RuntimeError(
                f"phép '{name}' thiếu trạng thái cho thế giới {missing} — "
                "bảng phải ghi ĐỦ bốn thế giới, không để mặc định ngầm")
        has_fail = any(st is MeasuredStatus.MEASURED_FAIL
                       for st in op.by_world.values())
        if has_fail and not op.revit_error:
            raise RuntimeError(
                f"phép '{name}' có MEASURED_FAIL nhưng thiếu revit_error "
                "(bằng chứng nguyên văn là bắt buộc)")
        has_nm = any(st is MeasuredStatus.NOT_MEASURED
                     for st in op.by_world.values())
        if has_nm and not op.not_measured_reason:
            raise RuntimeError(
                f"phép '{name}' có NOT_MEASURED nhưng thiếu not_measured_reason")
        if not op.evidence:
            raise RuntimeError(f"phép '{name}' thiếu evidence")
    for alias, target in OPERATION_ALIASES.items():
        if alias in OPERATIONS:
            raise RuntimeError(f"bí danh phép '{alias}' trùng khoá thật")
        if target not in OPERATIONS:
            raise RuntimeError(f"bí danh phép '{alias}' trỏ tới '{target}' không có")


_validate_tables()


# ---------------------------------------------------------------------------
# API tra cứu
# ---------------------------------------------------------------------------

def template_spec(template_key: str) -> TemplateSpec:
    """Trả :class:`TemplateSpec`; raise :class:`UnknownTemplateError` nếu lạ."""
    if not isinstance(template_key, str):
        raise UnknownTemplateError(
            f"template_key phải là str, nhận {type(template_key).__name__}")
    key = TEMPLATE_ALIASES.get(template_key, template_key)
    try:
        return TEMPLATES[key]
    except KeyError:
        raise UnknownTemplateError(
            f"Template '{template_key}' KHÔNG có trong bảng đã đo "
            f"({RFC_VERSION} §1, 12 template).\n"
            f"  Hợp lệ: {', '.join(sorted(TEMPLATES))}\n"
            f"  Bí danh: {', '.join(sorted(TEMPLATE_ALIASES))}\n"
            f"  Muốn thêm template khác thì phải MỞ THỬ trên Revit rồi ghi vào "
            f"{CAPABILITY_DOC} trước — không thêm bằng suy đoán."
        ) from None


def operation_spec(operation: str) -> OperationSpec:
    """Trả :class:`OperationSpec`; raise :class:`UnknownOperationError` nếu lạ."""
    if not isinstance(operation, str):
        raise UnknownOperationError(
            f"operation phải là str, nhận {type(operation).__name__}")
    name = OPERATION_ALIASES.get(operation, operation)
    try:
        return OPERATIONS[name]
    except KeyError:
        raise UnknownOperationError(
            f"Phép '{operation}' KHÔNG có trong bảng năng lực {RFC_VERSION}.\n"
            f"  KHÔNG có trong bảng nghĩa là CHƯA AI ĐO nó trên Revit 2026 máy "
            f"này — không phải là nó không tồn tại.\n"
            f"  Đã đo: {', '.join(sorted(OPERATIONS))}\n"
            f"  Muốn dùng: chạy probe thật, rồi ghi vào {CAPABILITY_DOC} và "
            f"bảng OPERATIONS."
        ) from None


def world_of(template_key: str) -> FamilyWorld:
    """Thế giới dựng hình của một template.

    Đây là hàm quyết định TẤT CẢ: chọn template là chọn cả bộ công cụ.
    KHÔNG suy ra thế giới từ ``IsAdaptiveComponentFamily`` (Mass = False mà
    vẫn thuộc thế giới massing).
    """
    return template_spec(template_key).world


def template_path(template_key: str, *, must_exist: bool = False) -> str:
    """Đường dẫn tuyệt đối tới ``.rft``.

    ``must_exist=True`` kiểm file có thật trên đĩa (chỉ dùng được trên máy có
    Revit); thiếu file thì raise :class:`UnknownTemplateError` chứ không trả
    đường dẫn ma.
    """
    spec = template_spec(template_key)
    path = spec.path
    if must_exist and not os.path.isfile(path):
        raise UnknownTemplateError(
            f"Template '{spec.key}' có trong bảng đã đo nhưng KHÔNG thấy file "
            f"trên đĩa:\n  {path}\n"
            f"  Máy này không phải máy đã đo, hoặc Revit 2026 chưa cài đúng chỗ."
        )
    return path


def template_exists(template_key: str) -> bool:
    """File ``.rft`` có thật trên đĩa máy này không (không raise)."""
    return os.path.isfile(template_spec(template_key).path)


def operation_status(operation: str, template_key: str) -> MeasuredStatus:
    """Trạng thái đo được của ``operation`` với template này. KHÔNG raise theo trạng thái."""
    return operation_spec(operation).status(world_of(template_key))


def require_operation(operation: str, template_key: str) -> None:
    """CỔNG CHẶN — raise nếu phép này không được phép với template này.

    Trả ``None`` khi và chỉ khi cặp (phép, thế giới) là ``MEASURED_OK``.
    Hàm này **raise chứ không trả bool**: một giá trị trả về có thể bị quên
    kiểm, một exception thì không.

    Raises:
        UnknownTemplateError: template không có trong bảng đã đo.
        UnknownOperationError: phép không có trong bảng đã đo.
        UnsupportedInWorldError: ĐÃ ĐO LÀ HỎNG trong thế giới này.
        NotMeasuredError: CHƯA ĐO trong thế giới này.
    """
    op = operation_spec(operation)
    tpl = template_spec(template_key)
    status = op.status(tpl.world)
    if status is MeasuredStatus.MEASURED_OK:
        return None

    head = (f"Phép '{op.name}' ({op.api})\n"
            f"  template  : '{tpl.key}' — {tpl.rft}\n"
            f"  thế giới  : {tpl.world}\n")

    if status is MeasuredStatus.MEASURED_FAIL:
        ok = op.ok_worlds
        alt = tuple(k for k, s in TEMPLATES.items() if s.world in ok)
        raise UnsupportedInWorldError(
            head +
            f"  trạng thái: MEASURED_FAIL — ĐÃ ĐO LÀ HỎNG trên Revit 2026 máy này.\n"
            f"  lỗi Revit : {op.revit_error}\n"
            f"  chạy được ở thế giới: "
            f"{', '.join(str(w) for w in ok) if ok else '(không thế giới nào)'}\n"
            f"  đổi template sang: "
            f"{', '.join(sorted(alt)) if alt else '(không có template thay thế)'}\n"
            f"  bằng chứng: {op.evidence}"
        )

    raise NotMeasuredError(
        head +
        f"  trạng thái: NOT_MEASURED — CHƯA ĐO.\n"
        f"  CHƯA ĐO nghĩa là KHÔNG BIẾT. Không phải 'không tồn tại', cũng "
        f"không phải 'dùng được'.\n"
        f"  vì sao    : {op.not_measured_reason}\n"
        f"  muốn dùng : chạy probe THẬT trên Revit 2026 máy này, rồi cập nhật "
        f"mục '5. CHƯA ĐO' trong {CAPABILITY_DOC} và bảng OPERATIONS của "
        f"bridge_evolution/revit_family/worlds.py.\n"
        f"  bằng chứng hiện có: {op.evidence}"
    )


def require_operations(operations: Iterable[str], template_key: str) -> None:
    """Gác một loạt phép cùng lúc — raise ở phép ĐẦU TIÊN không hợp lệ."""
    seen = False
    for op in operations:
        seen = True
        require_operation(op, template_key)
    if not seen:
        raise RevitFamilyCapabilityError(
            "Danh sách phép RỖNG. Phải khai báo mình định dùng phép nào thì "
            "cổng mới gác được — bộ sinh mã không được đoán hộ."
        )


def templates_in_world(world: FamilyWorld) -> tuple[str, ...]:
    """Các khoá template thuộc một thế giới, đã sắp xếp."""
    if not isinstance(world, FamilyWorld):
        raise RevitFamilyCapabilityError(
            f"world phải là FamilyWorld, nhận {type(world).__name__}")
    return tuple(sorted(k for k, s in TEMPLATES.items() if s.world is world))


def operations_ok_in(template_key: str) -> tuple[str, ...]:
    """Các phép ĐÃ ĐO LÀ CHẠY ĐƯỢC với template này, đã sắp xếp."""
    world = world_of(template_key)
    return tuple(sorted(
        name for name, op in OPERATIONS.items()
        if op.status(world) is MeasuredStatus.MEASURED_OK))


def capability_table() -> tuple[dict[str, object], ...]:
    """Bảng năng lực dạng dữ liệu thuần — để test đối chiếu và để xuất báo cáo."""
    rows: list[dict[str, object]] = []
    for name in sorted(OPERATIONS):
        op = OPERATIONS[name]
        rows.append({
            "operation": name,
            "api": op.api,
            "status_by_world": {str(w): op.status(w).value for w in FamilyWorld},
            "constraints": list(op.constraints),
            "evidence": op.evidence,
        })
    return tuple(rows)
