"""Kiểm chứng cổng năng lực family Revit — BRD-036 Pha 2.

Thư viện ``bridge_evolution.revit_family`` chỉ có MỘT lời hứa:
**không thể sinh ra C# mà ta đã ĐO là hỏng.** File này kiểm đúng lời hứa đó,
theo năm lớp:

  1. BẢNG   — hai bảng dữ liệu khớp ``docs/revit_family_capability.md``
              (RFC-1.1.0) từng ô, kể cả cái bẫy ``Mass.isAdaptive = False``.
  2. CỔNG   — ``require_operation`` RAISE đúng loại lỗi cho từng cặp
              (phép × thế giới): đã đo hỏng -> ``UnsupportedInWorldError``,
              chưa đo -> ``NotMeasuredError``.
  3. THÔNG ĐIỆP — lỗi phải nói được VÌ SAO và trỏ về tài liệu nguồn. Một cổng
              chặn mà không giải thích thì người ta sẽ vòng qua nó.
  4. SỐ     — hoán vị trục cầu -> Revit và hệ số feet, đúng từng chữ số.
  5. MÃ C#  — bốn bất biến đã đo được kiểm TRÊN CHÍNH chuỗi sinh ra, không
              phải bằng lời khẳng định trong docstring.

Không test nào ở đây cần Revit chạy. Test duy nhất chạm đĩa (template có thật
không) tự bỏ qua khi không ở trên máy đã đo.
"""
import math
import os
import re

import pytest

from bridge_evolution.revit_family import (
    ALLOWED_CLAIM_LEVELS,
    CAPABILITY_DOC,
    CLAIM_LEVEL_PARAM,
    CLAIM_STATEMENT_PARAM,
    FT,
    NOT_MEASURED_OPERATIONS,
    OPERATION_ALIASES,
    OPERATIONS,
    TEMPLATE_ALIASES,
    TEMPLATE_ROOT,
    TEMPLATES,
    ClaimCeilingError,
    CSharpBuilder,
    CSharpEmitError,
    CSharpStructureError,
    FamilyWorld,
    ForbiddenCSharpError,
    MeasuredStatus,
    NonAsciiCSharpError,
    NotMeasuredError,
    RevitFamilyCapabilityError,
    UnknownOperationError,
    UnknownTemplateError,
    UnsupportedInWorldError,
    capability_table,
    claim_parameters_cs,
    cs_string,
    family_scaffold,
    guarded_family_scaffold,
    m_to_ft,
    operation_spec,
    operation_status,
    operations_ok_in,
    require_operation,
    require_operations,
    template_exists,
    template_path,
    template_spec,
    templates_in_world,
    world_of,
    xyz,
)

SKETCH_KEYS = (
    "generic_model",
    "structural_framing",
    "structural_column",
    "structural_foundation",
    "generic_model_line_based",
    "generic_model_face_based",
)
ADAPTIVE_KEYS = ("adaptive", "pattern_based", "curtain_panel_pattern_based")
MASSING_KEYS = ("mass",)
TWO_D_KEYS = ("profile_hosted", "detail_item")

#: RFC-1.1.0 §1 — ánh xạ template -> thế giới, chép tay từ tài liệu.
RFC_WORLD_MAP = {
    **{k: FamilyWorld.SKETCH for k in SKETCH_KEYS},
    **{k: FamilyWorld.ADAPTIVE for k in ADAPTIVE_KEYS},
    **{k: FamilyWorld.MASSING for k in MASSING_KEYS},
    **{k: FamilyWorld.TWO_D for k in TWO_D_KEYS},
}

#: RFC-1.1.0 §1 — category ĐO ĐƯỢC sau khi mở template.
RFC_CATEGORY = {
    "generic_model": "Generic Models",
    "structural_framing": "Structural Framing",
    "structural_column": "Structural Columns",
    "structural_foundation": "Structural Foundations",
    "generic_model_line_based": "Generic Models",
    "generic_model_face_based": "Generic Models",
    "adaptive": "Generic Models",
    "pattern_based": "Curtain Panels",
    "curtain_panel_pattern_based": "Curtain Panels",
    "mass": "Mass",
    "profile_hosted": "Profiles",
    "detail_item": "Detail Items",
}

ALL_KEYS = tuple(RFC_WORLD_MAP)


def _lenh(code: str) -> str:
    """Chỉ giữ phần LỆNH của một chuỗi C#: bỏ mọi chú thích ``//``.

    Dùng cho MỌI kiểm tra về THỨ TỰ THI HÀNH và SỐ LẦN GỌI. Mã sinh ra cố ý
    mang nhiều chú thích dẫn số đo và dẫn giả định overload — chúng nhắc tên
    API, nên một kiểm tra chạy trên chuỗi thô sẽ đếm cả lời cảnh báo lẫn lệnh
    thật. Đó đúng là cái làm hỏng bài kiểm [A3] ở vòng phản biện trước: một
    dòng chú thích chứa chữ "Regenerate" thoả mãn ``assert "Regenerate" in
    code`` trong khi thứ tự thi hành vẫn sai.
    """
    return "\n".join(dong.split("//")[0] for dong in code.splitlines())


# =========================================================================
# 1. BẢNG — khớp RFC-1.1.0 từng ô
# =========================================================================

def test_dung_12_template_da_do():
    assert set(TEMPLATES) == set(ALL_KEYS)
    assert len(TEMPLATES) == 12


@pytest.mark.parametrize("key", ALL_KEYS)
def test_the_gioi_va_category_khop_rfc(key):
    assert world_of(key) is RFC_WORLD_MAP[key]
    assert template_spec(key).category == RFC_CATEGORY[key]


@pytest.mark.parametrize("key", ALL_KEYS)
def test_duong_dan_template_dung_khuon_windows(key):
    path = template_path(key)
    assert path.startswith(TEMPLATE_ROOT + "\\")
    assert path.lower().endswith(".rft")
    assert "/" not in path, "đường dẫn Revit phải dùng '\\'"


def test_mass_la_bay_isadaptive_false_nhung_van_thuoc_the_gioi_massing():
    """Cái bẫy đắt nhất của RFC-1.1.0 §1: cờ adaptive KHÔNG đoán được thế giới."""
    mass = template_spec("mass")
    assert mass.is_adaptive_family is False
    assert mass.world is FamilyWorld.MASSING
    # và Mass vẫn dựng được form + điểm, y như thế giới ADAPTIVE
    require_operation("NewReferencePoint", "mass")
    require_operation("NewLoftForm", "mass")
    require_operation("NewExtrusionForm", "mass")


@pytest.mark.parametrize("key", ALL_KEYS)
def test_co_adaptive_khop_rfc(key):
    expect_true = key in ("adaptive", "pattern_based", "curtain_panel_pattern_based")
    assert template_spec(key).is_adaptive_family is expect_true


def test_templates_in_world_phan_hoach_du_12():
    gom = []
    for world in FamilyWorld:
        gom.extend(templates_in_world(world))
    assert sorted(gom) == sorted(ALL_KEYS)
    assert set(templates_in_world(FamilyWorld.SKETCH)) == set(SKETCH_KEYS)
    assert set(templates_in_world(FamilyWorld.ADAPTIVE)) == set(ADAPTIVE_KEYS)
    assert set(templates_in_world(FamilyWorld.TWO_D)) == set(TWO_D_KEYS)


@pytest.mark.skipif(not os.path.isdir(TEMPLATE_ROOT),
                    reason="không ở trên máy đã đo (không có thư mục template Revit 2026)")
@pytest.mark.parametrize("key", ALL_KEYS)
def test_12_template_co_that_tren_dia(key):
    """Trên máy đã đo thì 12/12 phải có thật — bảng không được chứa đường dẫn ma."""
    assert template_exists(key), template_path(key)
    assert template_path(key, must_exist=True)


def test_moi_phep_ghi_du_bon_the_gioi():
    """Không để trạng thái mặc định ngầm: thiếu một ô là thiếu một phép đo."""
    for name, op in OPERATIONS.items():
        assert set(op.by_world) == set(FamilyWorld), name


def test_measured_fail_luon_kem_loi_nguyen_van():
    for name, op in OPERATIONS.items():
        if MeasuredStatus.MEASURED_FAIL in op.by_world.values():
            assert op.revit_error.strip(), name


def test_not_measured_luon_kem_ly_do():
    for name, op in OPERATIONS.items():
        if MeasuredStatus.NOT_MEASURED in op.by_world.values():
            assert op.not_measured_reason.strip(), name


def test_bi_danh_phep_va_template_deu_tro_toi_khoa_that():
    for alias, target in OPERATION_ALIASES.items():
        assert target in OPERATIONS
        assert operation_spec(alias) is OPERATIONS[target]
    for alias, target in TEMPLATE_ALIASES.items():
        assert target in TEMPLATES
        assert template_spec(alias) is TEMPLATES[target]


def test_capability_table_la_du_lieu_thuan():
    rows = capability_table()
    assert len(rows) == len(OPERATIONS)
    row = {r["operation"]: r for r in rows}["NewExtrusion"]
    assert row["status_by_world"]["SKETCH"] == "MEASURED_OK"
    assert row["status_by_world"]["ADAPTIVE"] == "MEASURED_FAIL"
    assert row["status_by_world"]["2D"] == "MEASURED_FAIL"


# =========================================================================
# 2. CỔNG — require_operation raise đúng loại
# =========================================================================

def test_require_operation_tra_none_khong_tra_bool():
    """RAISE chứ không trả bool: giá trị trả về có thể bị quên kiểm, exception thì không."""
    assert require_operation("NewExtrusion", "generic_model") is None


@pytest.mark.parametrize("key", SKETCH_KEYS)
def test_newextrusion_chay_duoc_trong_moi_template_sketch(key):
    require_operation("NewExtrusion", key)


@pytest.mark.parametrize("key", ADAPTIVE_KEYS + MASSING_KEYS + TWO_D_KEYS)
def test_newextrusion_bi_chan_ngoai_the_gioi_sketch(key):
    with pytest.raises(UnsupportedInWorldError):
        require_operation("NewExtrusion", key)


@pytest.mark.parametrize("key", SKETCH_KEYS + TWO_D_KEYS)
def test_newreferencepoint_bi_chan_trong_sketch_va_2d(key):
    with pytest.raises(UnsupportedInWorldError):
        require_operation("NewReferencePoint", key)


@pytest.mark.parametrize("key", ADAPTIVE_KEYS + MASSING_KEYS)
def test_newreferencepoint_chay_duoc_trong_adaptive_va_massing(key):
    require_operation("NewReferencePoint", key)


@pytest.mark.parametrize("op", ["NewLoftForm", "NewExtrusionForm"])
@pytest.mark.parametrize("key", SKETCH_KEYS + TWO_D_KEYS)
def test_form_bi_chan_ngoai_the_gioi_diem(op, key):
    with pytest.raises(UnsupportedInWorldError):
        require_operation(op, key)


@pytest.mark.parametrize("op", ["NewBlend", "NewSweep", "NewSweptBlend",
                                "NewRevolution", "NewModelCurve",
                                "ChangeToReferenceLine", "NewReferencePlane",
                                "NewModelText", "InclinedWorkPlane",
                                "LoadFamily", "AddParameter", "SaveAs"])
def test_bo_cong_cu_sketch_chay_duoc_trong_sketch(op):
    require_operation(op, "generic_model")


@pytest.mark.parametrize("op", sorted(NOT_MEASURED_OPERATIONS))
@pytest.mark.parametrize("key", ["generic_model", "adaptive", "mass", "detail_item"])
def test_phep_chua_do_bi_chan_o_moi_the_gioi(op, key):
    with pytest.raises(NotMeasuredError):
        require_operation(op, key)


def test_danh_sach_chua_do_dung_bang_muc_5_cua_rfc():
    """Mục '5. CHƯA ĐO' + NewSweptBlendForm (§3/§4) — không thiếu, không thừa.

    ``HostedPointOnCurve`` nằm đây vì §3 đo được HÀNH VI của điểm hosted
    ([A3], [A5]) nhưng KHÔNG ghi lại TÊN API tạo ra nó — đúng cái bẫy [A2].
    """
    assert NOT_MEASURED_OPERATIONS == frozenset({
        "NewSweptBlendForm",
        "NewRevolveForm",
        "NonPlanarProfileForm",
        "CreateAdaptiveComponentInstance",
        "SetInstancePlacementPointElementRefIds",
        "GetPlacementPoints",
        "HostedPointOnCurve",
        "NewOpening",
        "NewModelGroup",
        "AdaptiveComponent4Point",
    })


def test_newsweptblendform_la_chua_do_chu_khong_phai_absent():
    """RFC-1.1.0 §4: đã thử và hỏng NHƯNG chưa loại trừ lỗi người gọi."""
    with pytest.raises(NotMeasuredError) as exc:
        require_operation("NewSweptBlendForm", "adaptive")
    msg = str(exc.value)
    assert "Cannot create swept blend form" in msg
    assert "chưa loại trừ lỗi người gọi" in msg.lower() or "CHƯA loại trừ" in msg


def test_addparameter_chua_do_trong_adaptive():
    """Phát hiện của Pha 2: dấu claim BẮT BUỘC chưa đo được trong family adaptive."""
    require_operation("AddParameter", "generic_model")
    with pytest.raises(NotMeasuredError):
        require_operation("AddParameter", "adaptive")


def test_moi_loi_cong_deu_la_valueerror():
    for exc_type in (UnsupportedInWorldError, NotMeasuredError,
                     UnknownTemplateError, UnknownOperationError,
                     RevitFamilyCapabilityError):
        assert issubclass(exc_type, ValueError)


def test_template_va_phep_la_thi_raise_khong_doan_mo():
    with pytest.raises(UnknownTemplateError):
        require_operation("NewExtrusion", "metric generic model")
    with pytest.raises(UnknownOperationError):
        require_operation("NewMagicSolid", "generic_model")
    with pytest.raises(UnknownTemplateError):
        template_spec(None)


def test_require_operations_chan_danh_sach_rong():
    require_operations(["NewExtrusion", "AddParameter"], "generic_model")
    with pytest.raises(RevitFamilyCapabilityError):
        require_operations([], "generic_model")
    with pytest.raises(UnsupportedInWorldError):
        require_operations(["NewReferencePoint", "NewExtrusion"], "adaptive")


def test_operation_status_khong_raise_theo_trang_thai():
    assert operation_status("NewExtrusion", "adaptive") is MeasuredStatus.MEASURED_FAIL
    assert operation_status("NewLoftForm", "adaptive") is MeasuredStatus.MEASURED_OK
    assert operation_status("NewRevolveForm", "mass") is MeasuredStatus.NOT_MEASURED


def test_operations_ok_in_khop_voi_require_operation():
    for key in ALL_KEYS:
        oks = operations_ok_in(key)
        for name in OPERATIONS:
            if name in oks:
                require_operation(name, key)
            else:
                with pytest.raises((UnsupportedInWorldError, NotMeasuredError)):
                    require_operation(name, key)


def test_the_gioi_2d_khong_dung_khoi_duoc():
    for key in TWO_D_KEYS:
        assert "NewExtrusion" not in operations_ok_in(key)
        assert "NewLoftForm" not in operations_ok_in(key)


# =========================================================================
# 3. THÔNG ĐIỆP — cổng phải giải thích, nếu không người ta sẽ vòng qua
# =========================================================================

def test_loi_sai_the_gioi_dan_loi_revit_nguyen_van():
    with pytest.raises(UnsupportedInWorldError) as exc:
        require_operation("NewExtrusion", "adaptive")
    msg = str(exc.value)
    assert "not permitted in this type of family" in msg
    assert "MEASURED_FAIL" in msg
    assert "SKETCH" in msg
    assert "generic_model" in msg, "phải gợi ý template thay thế"


def test_loi_newreferencepoint_trong_sketch_dan_ten_ngoai_le():
    with pytest.raises(UnsupportedInWorldError) as exc:
        require_operation("NewReferencePoint", "structural_column")
    assert "FamilyContextException" in str(exc.value)


@pytest.mark.parametrize("op", sorted(NOT_MEASURED_OPERATIONS))
def test_loi_chua_do_noi_ro_chua_do_va_tro_ve_tai_lieu(op):
    with pytest.raises(NotMeasuredError) as exc:
        require_operation(op, "adaptive")
    msg = str(exc.value)
    assert "CHƯA ĐO" in msg
    assert "KHÔNG BIẾT" in msg
    assert "Không phải 'không tồn tại'" in msg
    assert CAPABILITY_DOC in msg


def test_loi_template_la_liet_ke_khoa_hop_le():
    with pytest.raises(UnknownTemplateError) as exc:
        template_spec("khong_co_template_nay")
    msg = str(exc.value)
    for key in ALL_KEYS:
        assert key in msg


@pytest.mark.parametrize("op,dau", [
    ("NewSweptBlend", "[S1]"),
    ("NewBlend", "[B1]"),
    ("NewRevolution", "[R1]"),
    ("IsAdaptiveComponentFamily", "[A1]"),
    ("GetPlacementPoints", "[A2]"),
])
def test_rang_buoc_bat_buoc_duoc_ma_hoa_thanh_du_lieu(op, dau):
    spec = operation_spec(op)
    blob = " ".join(spec.constraints) + " " + spec.not_measured_reason
    assert dau in blob, f"{op} thiếu ràng buộc {dau}"


def test_s1_noi_ro_phai_di_qua_modelcurve_reference():
    text = " ".join(operation_spec("NewSweptBlend").constraints)
    assert "Reference" in text and "Curve" in text
    assert "GeometryCurve.Reference" in text
    assert "Arc" in text, "phải ghi lại là path CONG ĐƯỢC (một đốt vòm = một phép)"


def test_b1_va_r1_noi_ro_cai_gi_lam_hong():
    assert "CAO ĐỘ KHÁC NHAU" in " ".join(operation_spec("NewBlend").constraints)
    assert "trục" in " ".join(operation_spec("NewRevolution").constraints).lower()


# =========================================================================
# 4. SỐ — hoán vị trục và hệ số feet
# =========================================================================

def test_hang_doi_feet():
    assert FT == 3.280839895013
    assert m_to_ft(1.0) == FT
    assert m_to_ft(0.0) == 0.0
    assert math.isclose(m_to_ft(2.5), 2.5 * FT, rel_tol=0, abs_tol=0)


def test_xyz_hoan_vi_dung_va_doi_feet():
    """(x, y, z)_cầu -> new XYZ(x_ft, z_ft, y_ft): Revit lấy Z làm cao độ."""
    got = xyz(1, 2, 3)
    assert got == "new XYZ(3.280839895, 9.842519685, 6.56167979)"
    nums = [float(v) for v in re.findall(r"-?\d+\.\d+", got)]
    # in ra 9 chữ số thập phân: sai lệch <= 1e-9 ft ~ 0.3 nm
    assert math.isclose(nums[0], 1 * FT, rel_tol=0, abs_tol=1e-9)
    assert math.isclose(nums[1], 3 * FT, rel_tol=0, abs_tol=1e-9), "số giữa là NGANG cầu (z)"
    assert math.isclose(nums[2], 2 * FT, rel_tol=0, abs_tol=1e-9), "số cuối là CAO ĐỘ (y)"


def test_xyz_khong_doi_xung_nen_hoan_vi_sai_la_lo_ngay():
    assert xyz(1, 2, 3) != xyz(1, 3, 2)
    assert xyz(0, 0, 0) == "new XYZ(0.0, 0.0, 0.0)"


def test_xyz_chan_nan_va_inf():
    for bad in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(ValueError):
            xyz(bad, 0, 0)
        with pytest.raises(ValueError):
            m_to_ft(bad)


def test_so_khong_bao_gio_ra_ky_hieu_mu():
    """C# không đọc được '1e-07' như Python in ra — literal phải là thập phân."""
    for value in (1e-7, 1e-9, 123456.789, -0.0001):
        text = xyz(value, value, value)
        assert "e" not in text.lower().replace("new xyz", "")


def test_cs_string_verbatim_va_nhan_doi_nhay():
    assert cs_string(r"C:\a b\c.rft") == '@"C:\\a b\\c.rft"'
    assert cs_string('say "hi"') == '@"say ""hi"""'
    with pytest.raises(ValueError):
        cs_string("hai\ndong")
    with pytest.raises(NonAsciiCSharpError):
        cs_string("có dấu")


# =========================================================================
# 5. MÃ C# — bốn bất biến, kiểm trên chính chuỗi sinh ra
# =========================================================================

def test_builder_thut_le_va_dong_ngoac():
    b = CSharpBuilder()
    b.line("int n = 0;")
    with b.block("if (n == 0)"):
        b.line("n = 1;")
    code = b.build()
    assert code == "int n = 0;\nif (n == 0)\n{\n    n = 1;\n}\n"


def test_builder_chan_transaction_tren_document_cua_host():
    b = CSharpBuilder()
    with pytest.raises(ForbiddenCSharpError) as exc:
        b.line('using (Transaction t = new Transaction(document, "x"))')
    assert "InvalidOperationException" in str(exc.value)


def test_builder_chan_guid_ngau_nhien():
    with pytest.raises(ForbiddenCSharpError):
        CSharpBuilder().line("ds.ApplicationDataId = Guid.NewGuid().ToString();")


def test_builder_chan_dong_document_cua_host():
    with pytest.raises(ForbiddenCSharpError):
        CSharpBuilder().line("document.Close(false);")


def test_builder_chan_ky_tu_co_dau():
    with pytest.raises(NonAsciiCSharpError):
        CSharpBuilder().line("// dựng khối")


def test_builder_chan_nhieu_dong_trong_mot_lan_goi():
    with pytest.raises(ValueError):
        CSharpBuilder().line("a;\nb;")


def test_builder_chan_ngoac_lech():
    b = CSharpBuilder()
    b.line("{")
    with pytest.raises(CSharpStructureError):
        b.build()


def test_ngoac_trong_chuoi_hang_khong_bi_dem():
    b = CSharpBuilder()
    b.line('string s = "{ khong phai ngoac }";')
    assert b.build().strip().endswith(';')


# ------------------------------------------------------------------ scaffold

TPL = template_path("generic_model")
OUT = r"C:\Temp\dylight_test.rfa"
#: Dấu claim là BẮT BUỘC với mọi chuỗi phát ra ``fd.SaveAs(...)`` — kể cả khi
#: gọi thẳng ``family_scaffold`` (hạ tầng trần, không gác thế giới). Nên thân
#: mã dùng chung của mục này phải mang dấu claim, y như đời thật.
CLAIM_BODY = claim_parameters_cs(template_key="generic_model")
BODY = ["// dung hinh o day", "double h = 1.0;"] + CLAIM_BODY


def test_scaffold_mo_transaction_tren_fd_khong_phai_document():
    """Bất biến 1 — self-check (f) của hợp đồng BRD-036."""
    code = family_scaffold(TPL, OUT, BODY)
    assert "new Transaction(fd" in code
    assert "new Transaction(document" not in code
    assert not re.search(r"new\s+Transaction\s*\(\s*document\b", code)


def test_scaffold_regenerate_nam_trong_transaction():
    """Bất biến 3 — Regenerate sau Commit thì Revit ném InvalidOperationException."""
    code = family_scaffold(TPL, OUT, BODY)
    i_regen = code.index("fd.Regenerate();")
    i_commit = code.index("tx.Commit();")
    i_saveas = code.index("fd.SaveAs(")
    assert i_regen < i_commit < i_saveas


def test_scaffold_co_du_khuon_da_kiem_chung():
    code = family_scaffold(TPL, OUT, BODY, "DYLIGHT test")
    for moc in ("app.NewFamilyDocument(tplPath)",
                "SaveAsOptions",
                "so.OverwriteExistingFile = true;",
                "fd.Close(false);",
                "catch (Exception ex)",
                "System.IO.File.Exists(tplPath)",
                "System.IO.FileInfo(outRfa)"):
        assert moc in code, moc
    assert code.count("fd.Close(false);") >= 2, "phải đóng cả ở nhánh catch"
    for line in BODY:
        assert line in code


def test_scaffold_la_ascii_thuan():
    """Bất biến 4 — mã đi qua MCP và console cp1252 trên máy này."""
    code = family_scaffold(TPL, OUT, BODY)
    code.encode("ascii")


def test_scaffold_xac_dinh_lai_duoc():
    assert family_scaffold(TPL, OUT, BODY) == family_scaffold(TPL, OUT, BODY)


def test_scaffold_chan_than_ma_rong():
    with pytest.raises(CSharpStructureError):
        family_scaffold(TPL, OUT, [])


def test_scaffold_chan_duoi_file_sai():
    with pytest.raises(ValueError):
        family_scaffold(TPL, r"C:\Temp\x.rvt", BODY)
    with pytest.raises(ValueError):
        family_scaffold(r"C:\Temp\x.rvt", OUT, BODY)


def test_scaffold_chan_than_ma_gianh_transaction():
    for xau in ("tx.Commit();", "tx.Start();", "fd.SaveAs(p, o);",
                "fd.Regenerate();"):
        with pytest.raises(ForbiddenCSharpError):
            family_scaffold(TPL, OUT, ["double h = 1.0;", xau])


def test_scaffold_chan_ca_giai_doan_pre_regen_gianh_transaction():
    """``pre_regen_lines`` là thân mã, nên chịu ĐÚNG bộ cấm của thân mã."""
    for xau in ("tx.Commit();", "fd.Regenerate();", "fd.SaveAs(p, o);"):
        with pytest.raises(ForbiddenCSharpError):
            family_scaffold(TPL, OUT, BODY, pre_regen_lines=["int q = 1;", xau])


def test_scaffold_tu_choi_ghi_rfa_khong_mang_dau_claim():
    """Điều khoản 4 BRD-036 — kiểm ở chỗ DUY NHẤT phát ``fd.SaveAs(...)``.

    Trước bản sửa này, ``family_scaffold`` là đường vòng đi quanh dấu claim:
    nó không gác thế giới, không gác claim, mà vẫn ghi ra một ``.rfa`` hoàn
    chỉnh. Một file ``.rfa`` không dấu claim trông y hệt hồ sơ kỹ thuật thật.
    """
    with pytest.raises(CSharpStructureError) as exc:
        family_scaffold(TPL, OUT, ["// dung hinh o day", "double h = 1.0;"])
    msg = str(exc.value)
    assert CLAIM_LEVEL_PARAM in msg
    assert "AddParameter" in msg


def test_scaffold_khong_nhan_dau_claim_gia_bang_chu_thich():
    """Chú thích nhắc tên tham số KHÔNG phải là đã dán dấu claim."""
    with pytest.raises(CSharpStructureError):
        family_scaffold(TPL, OUT, [f"// {CLAIM_LEVEL_PARAM} se dan sau"])


def test_scaffold_chan_than_ma_mo_transaction_tren_host():
    with pytest.raises(ForbiddenCSharpError):
        family_scaffold(TPL, OUT, ['var t = new Transaction(document, "x");'])


def test_scaffold_chan_doc_he_toa_do_truoc_regenerate():
    """[A3] — cái bẫy IM LẶNG, chặn ngay trên chuỗi vừa sinh.

    Trước bản sửa này, ghép bộ xương + mặt phẳng tiết diện vào CÙNG một thân mã
    cho ra một chuỗi đọc ``GetCoordinateSystem()`` trước ``fd.Regenerate();``.
    RFC-1.1.0 §3 [A3] đo được rằng lúc đó nó trả MA TRẬN ĐƠN VỊ — và spine dọc
    trục X trùng đúng ma trận đơn vị nên không test nào lộ ra.
    """
    with pytest.raises(CSharpStructureError) as exc:
        family_scaffold(TPL, OUT,
                        ["Transform tf = ptA.GetCoordinateSystem();"] + BODY)
    assert "[A3]" in str(exc.value)


def test_scaffold_pre_regen_dat_regenerate_TRUOC_phan_doc_he_toa_do():
    """Lối ĐÚNG: dựng điểm ở giai đoạn 1, đọc hệ toạ độ ở giai đoạn 2."""
    lenh = _lenh(family_scaffold(
        TPL, OUT,
        ["Transform tf = ptA.GetCoordinateSystem();"] + BODY,
        pre_regen_lines=["ReferencePoint ptA = fc.NewReferencePoint(XYZ.Zero);"]))
    assert lenh.index("fd.Regenerate();") < lenh.index("GetCoordinateSystem")
    assert lenh.count("fd.Regenerate();") == 2, \
        "một Regenerate giữa chừng cho [A3], một trước Commit cho bất biến 3"
    i_regen2 = lenh.rindex("fd.Regenerate();")
    assert lenh.index("GetCoordinateSystem") < i_regen2 < lenh.index("tx.Commit();")


def test_scaffold_chu_thich_canh_bao_khong_thoa_man_duoc_kiem_tra_A3():
    """Một dòng chú thích nhắc 'Regenerate' KHÔNG phải là đã Regenerate."""
    with pytest.raises(CSharpStructureError):
        family_scaffold(TPL, OUT,
                        ["// PHAI Regenerate() truoc khi doc he toa do",
                         "Transform tf = ptA.GetCoordinateSystem();"] + BODY)


def test_scaffold_ngoac_can_bang():
    code = family_scaffold(TPL, OUT, BODY)
    clean = re.sub(r'"(?:[^"]|"")*"', "", code)
    clean = "\n".join(l.split("//")[0] for l in clean.splitlines())
    assert clean.count("{") == clean.count("}")


# ------------------------------------------------------------------ claim

def test_claim_parameters_doc_duoc_trong_revit():
    lines = claim_parameters_cs()
    blob = "\n".join(lines)
    assert CLAIM_LEVEL_PARAM in blob
    assert CLAIM_STATEMENT_PARAM in blob
    assert "F0_IDEA" in blob
    assert "fm.AddParameter" in blob
    assert "fm.Set(" in blob
    blob.encode("ascii")


def test_claim_khong_nang_duoc_muc():
    assert ALLOWED_CLAIM_LEVELS == frozenset({"F0_IDEA"})
    for muc in ("F1_SCREENED", "SCREENED", "ENGINEERING_CANDIDATE", "F0-IDEA", ""):
        with pytest.raises(ClaimCeilingError):
            claim_parameters_cs(muc, "bat ky")


def test_claim_chan_cau_rong():
    with pytest.raises(ValueError):
        claim_parameters_cs("F0_IDEA", "   ")


def test_claim_nhan_doi_dau_nhay_khong_vo_chuoi_c_sharp():
    blob = "\n".join(claim_parameters_cs("F0_IDEA", 'muc "F0"'))
    assert '@"muc ""F0"""' in blob


def test_claim_co_cong_chan_theo_template():
    claim_parameters_cs(template_key="generic_model")
    with pytest.raises(NotMeasuredError):
        claim_parameters_cs(template_key="adaptive")


# ------------------------------------------------------------------ guarded

def test_guarded_sinh_duoc_family_sketch_kem_dau_claim():
    code = guarded_family_scaffold(
        "structural_foundation", OUT,
        ["NewExtrusion", "AddParameter"],
        ["// NewExtrusion o day"],
        "DYLIGHT mong F0 IDEA")
    assert "Metric Structural Foundation.rft" in code
    assert CLAIM_LEVEL_PARAM in code
    assert "new Transaction(fd" in code
    code.encode("ascii")


def test_guarded_chan_phep_sai_the_gioi_truoc_khi_phat_dong_nao():
    with pytest.raises(UnsupportedInWorldError):
        guarded_family_scaffold("adaptive", OUT, ["NewExtrusion"], ["// x"])


def test_guarded_chan_phep_chua_do():
    with pytest.raises(NotMeasuredError):
        guarded_family_scaffold("adaptive", OUT, ["NewSweptBlendForm"], ["// x"])


def test_guarded_chan_danh_sach_phep_rong():
    with pytest.raises(RevitFamilyCapabilityError):
        guarded_family_scaffold("generic_model", OUT, [], ["// x"])


def test_guarded_hien_chan_ca_the_gioi_adaptive_vi_addparameter_chua_do():
    """Chặn THẬT, không phải thiếu sót: dấu claim bắt buộc mà AddParameter
    trong adaptive chưa ai đo. Mở khoá bằng cách ĐO, không bằng cách nới cổng."""
    with pytest.raises(NotMeasuredError) as exc:
        guarded_family_scaffold("adaptive", OUT,
                                ["NewReferencePoint", "NewLoftForm"],
                                ["// loft form o day"])
    assert "AddParameter" in str(exc.value)


# =========================================================================
# 6. NHÓM SKETCH — sketch_family.py
#
# Năm cấu kiện, năm ràng buộc đã đo. Lớp kiểm ở đây có một câu hỏi duy nhất:
# **có xin được một đoạn C# mà RFC-1.1.0 đã đo là hỏng không?** Câu trả lời
# phải là không, ở mọi ngả.
# =========================================================================

from bridge_evolution.revit_family import (  # noqa: E402
    PLANE_TOL_COS,
    REVIT_SHORT_CURVE_TOL_M,
    SAG_TOL_M,
    BlendElevationError,
    BoxSpec,
    CollinearArcError,
    DegenerateGeometryError,
    RevolveAxisError,
    SketchFamilyError,
    VoidDoesNotCutError,
    arch_rib_segment,
    prismatic_member,
    revolved_member,
    tapered_pier_shaft,
    void_cut,
)

RFA = r"D:\tmp\arch_massing\FAM_Test.rfa"

#: Một đốt vòm CONG hợp lệ — dùng lại ở nhiều test.
ARCH_OK = dict(
    start_m=(0.0, 0.0, 0.0), mid_m=(20.0, 6.0, 0.0), end_m=(40.0, 0.0, 0.0),
    width_start_m=1.2, height_start_m=2.0,
    width_end_m=1.2, height_end_m=1.2,
)
SHAFT_OK = dict(
    base_center_m=(0.0, 0.0, 0.0), top_center_m=(0.0, 12.0, 0.0),
    base_long_m=3.0, base_trans_m=5.0, top_long_m=2.0, top_trans_m=4.0,
)
REV_OK = dict(
    profile_m=[(0.6, 0.0, 0.0), (1.4, 0.0, 0.0), (1.0, 3.0, 0.0), (0.6, 3.0, 0.0)],
    axis_start_m=(0.0, 0.0, 0.0), axis_end_m=(0.0, 3.0, 0.0),
)


def _brace(name="Giang"):
    return BoxSpec(start_m=(0.0, 0.0, 0.0), end_m=(6.0, 8.0, 0.0),
                   width_m=0.4, height_m=0.6, name=name)


def _footing(name="BeMong"):
    return BoxSpec(start_m=(0.0, 0.0, 0.0), end_m=(0.0, 2.5, 0.0),
                   width_m=10.0, height_m=8.0, name=name)


def _pile_hole(name="LoCoc"):
    return BoxSpec(start_m=(0.0, -0.25, 0.0), end_m=(0.0, 2.75, 0.0),
                   width_m=1.2, height_m=1.2, name=name)


ALL_FIVE = (
    lambda key: arch_rib_segment(key, RFA, **ARCH_OK),
    lambda key: tapered_pier_shaft(key, RFA, **SHAFT_OK),
    lambda key: revolved_member(key, RFA, **REV_OK),
    lambda key: prismatic_member(key, RFA, _brace()),
    lambda key: void_cut(key, RFA, _footing(), _pile_hole(),
                         acknowledge_no_cut=True),
)


# -- 6.1 năm hàm sinh được mã hợp lệ trong thế giới SKETCH ----------------

@pytest.mark.parametrize("make", ALL_FIVE)
def test_nam_ham_sinh_duoc_ma_trong_the_gioi_sketch(make):
    code = make("generic_model")
    code.encode("ascii")                       # bất biến 4 của csharp.py
    assert "new Transaction(fd" in code
    assert "new Transaction(document" not in code
    assert CLAIM_LEVEL_PARAM in code           # dấu claim là bắt buộc
    assert "F0_IDEA" in code


@pytest.mark.parametrize("make", ALL_FIVE)
def test_moi_ham_deu_xoa_hinh_hoc_ship_san_cua_template(make):
    """[S3] template ship sẵn hình học — không xoá thì mọi con số đếm bị nhiễm."""
    code = make("generic_model")
    assert "OfClass(typeof(GenericForm))" in code
    assert "fd.Delete(tplForms)" in code


@pytest.mark.parametrize("make", ALL_FIVE)
def test_ma_sinh_ra_xac_dinh_lai_duoc(make):
    assert make("generic_model") == make("generic_model")


@pytest.mark.parametrize("make", ALL_FIVE)
@pytest.mark.parametrize("key", ADAPTIVE_KEYS + MASSING_KEYS + TWO_D_KEYS)
def test_khong_ham_nao_sinh_duoc_ma_ngoai_the_gioi_sketch(make, key):
    """Cổng đứng TRƯỚC hình học: không một ký tự C# nào ra khỏi đây."""
    with pytest.raises(RevitFamilyCapabilityError):
        make(key)


@pytest.mark.parametrize("make", ALL_FIVE)
def test_sketch_template_la_thi_raise_chu_khong_doan(make):
    with pytest.raises(UnknownTemplateError):
        make("metric_generic_model_super_adaptive")


# -- 6.2 [S1] NewSweptBlend nhận Reference, KHÔNG nhận Curve ---------------

def test_s1_luon_di_qua_modelcurve_reference():
    lenh = _lenh(arch_rib_segment("structural_framing", RFA, **ARCH_OK))
    assert lenh.index("NewModelCurve(") < lenh.index("NewSweptBlend(")
    assert "Reference refRibPath = mcRibPath.GeometryCurve.Reference;" in lenh
    assert "NewSweptBlend(true, refRibPath, profRibA, profRibB)" in lenh


def test_s1_khong_bao_gio_truyen_curve_thang_vao_sweptblend():
    """Lỗi biên dịch đã đo: cannot convert from 'Curve' to 'Reference'."""
    lenh = _lenh(arch_rib_segment("structural_framing", RFA, **ARCH_OK))
    call = [ln for ln in lenh.splitlines() if "NewSweptBlend(" in ln][0]
    assert "crvRibPath" not in call          # biến kiểu Curve KHÔNG được lọt vào
    assert "refRibPath" in call


def test_s1_path_cong_duoc_nen_mot_dot_vom_la_mot_phep():
    """RFC-1.1.0 §2: path CONG được (đã đo với Arc) -> không chia đoạn."""
    lenh = _lenh(arch_rib_segment("structural_framing", RFA, **ARCH_OK))
    assert lenh.count("NewSweptBlend(") == 1, "một đốt vòm = MỘT phép"
    assert "Arc.Create(pRibA, pRibB, pRibM)" in lenh


def test_ba_diem_thang_hang_bi_chan_vi_arc_create_se_nem():
    with pytest.raises(CollinearArcError) as exc:
        arch_rib_segment("structural_framing", RFA,
                         start_m=(0.0, 0.0, 0.0), mid_m=(20.0, 0.0, 0.0),
                         end_m=(40.0, 0.0, 0.0),
                         width_start_m=1.2, height_start_m=2.0,
                         width_end_m=1.2, height_end_m=1.2)
    msg = str(exc.value)
    assert "THẲNG HÀNG" in msg
    assert "Arc.Create" in msg
    assert "allow_straight=True" in msg


def test_thang_hang_co_opt_in_thi_ha_xuong_line_khong_phat_arc():
    code = arch_rib_segment("structural_framing", RFA,
                            start_m=(0.0, 0.0, 0.0), mid_m=(20.0, 0.0, 0.0),
                            end_m=(40.0, 0.0, 0.0),
                            width_start_m=1.2, height_start_m=2.0,
                            width_end_m=1.2, height_end_m=1.2,
                            allow_straight=True)
    assert "Arc.Create(" not in code
    assert "Line.CreateBound(pRibA, pRibB)" in code
    assert "GeometryCurve.Reference" in code      # [S1] vẫn giữ nguyên


def test_khong_co_mid_thi_dot_thang_va_khong_can_opt_in():
    code = arch_rib_segment("structural_framing", RFA,
                            start_m=(0.0, 0.0, 0.0), end_m=(40.0, 0.0, 0.0),
                            width_start_m=1.2, height_start_m=2.0,
                            width_end_m=1.2, height_end_m=1.2)
    assert "Arc.Create(" not in code


def test_sagitta_ngay_tren_nguong_thi_dung_arc():
    """Ranh giới thẳng/cong nằm ở dung sai đường ngắn của Revit (1/256 ft)."""
    sag = SAG_TOL_M * 10.0
    code = arch_rib_segment("structural_framing", RFA,
                            start_m=(0.0, 0.0, 0.0), mid_m=(20.0, sag, 0.0),
                            end_m=(40.0, 0.0, 0.0),
                            width_start_m=1.2, height_start_m=2.0,
                            width_end_m=1.2, height_end_m=1.2)
    assert "Arc.Create(" in code


def test_diem_giua_ngoai_day_cung_cho_ra_cung_LON_chu_khong_im_lang_doi_ben():
    """``Arc.Create`` lấy cung CHỨA điểm thứ ba — kể cả khi đó là cung lớn.

    Điểm giữa ở ngoài dây cung là hợp lệ (cung > 180 độ), và bộ sinh phải theo
    đúng cung đó chứ không lặng lẽ lấy cung nhỏ ở phía bên kia: tiếp tuyến hai
    đầu — tức hướng đặt tiết diện — của hai cung ngược nhau.
    """
    lon = arch_rib_segment("structural_framing", RFA,
                           start_m=(0.0, 0.0, 0.0), mid_m=(-20.0, 6.0, 0.0),
                           end_m=(40.0, 0.0, 0.0),
                           width_start_m=1.2, height_start_m=2.0,
                           width_end_m=1.2, height_end_m=1.2)
    goc = float(re.search(r"goc quet ([0-9.]+) do", lon).group(1))
    assert goc > 180.0
    nho = arch_rib_segment("structural_framing", RFA, **ARCH_OK)
    assert float(re.search(r"goc quet ([0-9.]+) do", nho).group(1)) < 180.0
    assert lon != nho


# -- 6.3 [B1] NewBlend đòi hai profile khác cao độ -------------------------

def test_b1_hai_profile_cung_cao_do_thi_raise():
    with pytest.raises(BlendElevationError) as exc:
        tapered_pier_shaft("structural_column", RFA,
                           base_center_m=(0.0, 4.0, 0.0),
                           top_center_m=(0.0, 4.0, 0.0),
                           base_long_m=3.0, base_trans_m=5.0,
                           top_long_m=2.0, top_trans_m=4.0)
    msg = str(exc.value)
    assert "[B1]" in msg
    assert "CAO ĐỘ KHÁC NHAU" in msg
    assert "y" in msg                       # nói rõ hệ trục cầu


def test_b1_chenh_cao_do_duoi_dung_sai_van_bi_chan():
    with pytest.raises(BlendElevationError):
        tapered_pier_shaft("structural_column", RFA,
                           base_center_m=(0.0, 0.0, 0.0),
                           top_center_m=(0.0, REVIT_SHORT_CURVE_TOL_M / 2, 0.0),
                           base_long_m=3.0, base_trans_m=5.0,
                           top_long_m=2.0, top_trans_m=4.0)


def test_tru_lon_nguoc_bi_chan_vi_revit_khong_bao_gi_ca():
    with pytest.raises(DegenerateGeometryError):
        tapered_pier_shaft("structural_column", RFA,
                           base_center_m=(0.0, 12.0, 0.0),
                           top_center_m=(0.0, 0.0, 0.0),
                           base_long_m=3.0, base_trans_m=5.0,
                           top_long_m=2.0, top_trans_m=4.0)


def test_b1_hai_profile_thuc_su_khac_cao_do_trong_ma_sinh_ra():
    code = tapered_pier_shaft("structural_column", RFA, **SHAFT_OK)
    base_z = {ln.rsplit(",", 1)[1] for ln in code.splitlines()
              if ln.strip().startswith("XYZ ShaftBaseP")}
    top_z = {ln.rsplit(",", 1)[1] for ln in code.splitlines()
             if ln.strip().startswith("XYZ ShaftTopP")}
    assert len(base_z) == 1 and len(top_z) == 1
    assert base_z != top_z                 # đúng cái [B1] đòi


def test_b1_thu_tu_doi_so_newblend_la_top_truoc_base_sau():
    code = tapered_pier_shaft("structural_column", RFA, **SHAFT_OK)
    assert "NewBlend(true, ShaftTopLoop, ShaftBaseLoop, spShaft)" in code


# -- 6.4 [R1] NewRevolution đòi trục nằm trong mặt phẳng phác thảo ---------

def test_r1_truc_vuong_goc_mat_phang_thi_raise():
    with pytest.raises(RevolveAxisError) as exc:
        revolved_member("generic_model", RFA,
                        profile_m=REV_OK["profile_m"],
                        axis_start_m=(0.0, 0.0, 0.0),
                        axis_end_m=(0.0, 0.0, 3.0))
    msg = str(exc.value)
    assert "[R1]" in msg
    assert "NẰM TRONG mặt phẳng phác thảo" in msg
    assert "tích vô hướng" in msg


def test_r1_truc_song_song_nhung_o_ngoai_mat_phang_van_bi_chan():
    """Chỉ kiểm tích vô hướng là chưa đủ: song song vẫn có thể ở ngoài."""
    with pytest.raises(RevolveAxisError) as exc:
        revolved_member("generic_model", RFA,
                        profile_m=REV_OK["profile_m"],
                        axis_start_m=(0.0, 0.0, 5.0),
                        axis_end_m=(0.0, 3.0, 5.0))
    assert "KHÔNG NẰM TRONG" in str(exc.value)


def test_r1_lech_duoi_dung_sai_thi_van_cho_qua():
    lech = PLANE_TOL_COS / 10.0
    code = revolved_member("generic_model", RFA,
                           profile_m=REV_OK["profile_m"],
                           axis_start_m=(0.0, 0.0, 0.0),
                           axis_end_m=(0.0, 3.0, 3.0 * lech))
    assert "NewRevolution(" in code


def test_profile_khong_phang_bi_chan():
    with pytest.raises(DegenerateGeometryError) as exc:
        revolved_member("generic_model", RFA,
                        profile_m=[(0.6, 0.0, 0.0), (1.4, 0.0, 0.0),
                                   (1.0, 3.0, 0.5), (0.6, 3.0, 0.0)],
                        axis_start_m=(0.0, 0.0, 0.0), axis_end_m=(0.0, 3.0, 0.0))
    assert "KHÔNG PHẲNG" in str(exc.value)


def test_profile_cat_qua_truc_bi_chan():
    with pytest.raises(DegenerateGeometryError) as exc:
        revolved_member("generic_model", RFA,
                        profile_m=[(-1.0, 0.0, 0.0), (1.4, 0.0, 0.0),
                                   (1.0, 3.0, 0.0), (-1.0, 3.0, 0.0)],
                        axis_start_m=(0.0, 0.0, 0.0), axis_end_m=(0.0, 3.0, 0.0))
    assert "CẮT QUA trục" in str(exc.value)


def test_profile_it_hon_ba_dinh_bi_chan():
    with pytest.raises(DegenerateGeometryError):
        revolved_member("generic_model", RFA,
                        profile_m=[(0.6, 0.0, 0.0), (1.4, 0.0, 0.0)],
                        axis_start_m=(0.0, 0.0, 0.0), axis_end_m=(0.0, 3.0, 0.0))


def test_dinh_dau_lap_o_cuoi_duoc_bo_chu_khong_thanh_canh_dai_0():
    pts = list(REV_OK["profile_m"]) + [REV_OK["profile_m"][0]]
    code = revolved_member("generic_model", RFA, profile_m=pts,
                           axis_start_m=(0.0, 0.0, 0.0),
                           axis_end_m=(0.0, 3.0, 0.0))
    assert code.count("XYZ RevP") == 4


@pytest.mark.parametrize("goc_cuoi", [0.0, -1.0, 2.0 * math.pi + 0.5])
def test_goc_quet_ngoai_khoang_hop_le_bi_chan(goc_cuoi):
    with pytest.raises(DegenerateGeometryError):
        revolved_member("generic_model", RFA, end_angle_rad=goc_cuoi, **REV_OK)


# -- 6.5 [S2] void trong SKETCH KHÔNG cắt ---------------------------------

def test_s2_void_cut_raise_mac_dinh():
    with pytest.raises(VoidDoesNotCutError) as exc:
        void_cut("structural_foundation", RFA, _footing(), _pile_hole())
    msg = str(exc.value)
    assert "[S2]" in msg
    assert "KHÔNG CẮT" in msg
    assert "CanElementCutElement = False" in msg
    assert "CHƯA ĐO" in msg


def test_s2_thong_diep_noi_ra_the_tich_ky_vong_va_the_tich_thuc_te():
    """Con số là thứ duy nhất bắt được cái hỏng IM LẶNG này.

    Và nó phải là ĐÚNG con số RFC-1.1.0 §2 [S2] ghi: *"nếu cắt phải còn
    196.400"*, tức ``200 - 1.2*1.2*2.5``. Void 1.2x1.2x3.0 xuyên qua bệ dày
    2.5 m nên 0.5 m void nằm NGOÀI bệ và không khoét gì. Trừ nguyên thể tích
    void ra 195.68 — con số đó chỉ dẫn người mở lại .rfa kết luận NGƯỢC: họ đo
    được 196.4 (cắt THÀNH CÔNG) mà bảng lại bảo đó không phải giá trị kỳ vọng.
    """
    with pytest.raises(VoidDoesNotCutError) as exc:
        void_cut("structural_foundation", RFA, _footing(), _pile_hole())
    msg = str(exc.value)
    assert "200.0000" in msg               # thể tích thực tế = khối đặc
    assert "196.4000" in msg               # thể tích kỳ vọng nếu cắt được
    assert "3.6000" in msg                 # phần void NẰM TRONG bệ
    assert "195.68" not in msg, "hiệu hai thể tích là công thức SAI"
    # con số này phải khớp cả với dữ liệu cổng năng lực, không được lệch nhau
    assert "196.400" in " ".join(operation_spec("SolidSolidCut").constraints)


def test_s2_the_tich_ky_vong_dung_PHAN_GIAO_chu_khong_phai_hieu_hai_the_tich():
    """Void nằm TRỌN trong khối đặc thì hai công thức mới trùng nhau.

    Ca này là ca phân biệt: void 1.0 x 1.0 x 1.0 đặt hẳn bên trong bệ, phần
    giao = cả khối void, nên kỳ vọng = 200 - 1.0 = 199.0 theo CẢ HAI công
    thức. Ca xuyên qua ở test trên mới tách được chúng.
    """
    trong = BoxSpec(start_m=(0.0, 0.5, 0.0), end_m=(0.0, 1.5, 0.0),
                    width_m=1.0, height_m=1.0, name="LoTrong")
    with pytest.raises(VoidDoesNotCutError) as exc:
        void_cut("structural_foundation", RFA, _footing(), trong)
    msg = str(exc.value)
    assert "199.0000" in msg
    assert "0.0000 m3 nằm ngoài" in msg


def test_s2_xac_nhan_roi_thi_ma_van_mang_canh_bao_va_hai_con_so():
    code = void_cut("structural_foundation", RFA, _footing(), _pile_hole(),
                    acknowledge_no_cut=True)
    assert "VOID TRONG FAMILY SKETCH KHONG TU CAT" in code
    assert "CanElementCutElement = False" in code
    assert "200.0000 m3" in code
    assert "200.0000 - 3.6000 = 196.4000 m3" in code
    assert "PHAI mo lai .rfa va DO THE TICH" in code


def test_s2_void_phat_ra_issolid_false_con_khoi_dac_la_true():
    code = void_cut("structural_foundation", RFA, _footing(), _pile_hole(),
                    acknowledge_no_cut=True)
    assert "NewExtrusion(true, caaBeMong" in code
    assert "NewExtrusion(false, caaLoCoc" in code


def test_hai_khoi_trung_ten_bi_chan_vi_bien_c_sharp_trung():
    with pytest.raises(DegenerateGeometryError) as exc:
        void_cut("structural_foundation", RFA, _footing("A"), _pile_hole("A"),
                 acknowledge_no_cut=True)
    assert "tiền tố BIẾN C#" in str(exc.value)


def test_the_tich_giao_hai_hop_dung_ca_hop_NGHIENG():
    """Phần giao tính bằng hình học thật, không phải bằng ca trùng trục chính.

    Hộp nghiêng (0.6, 0.8, 0) dài 5.0, tiết diện 1.0 x 1.0, cắt bệ ở khoảng
    ``0 <= y <= 2.5``: đáp số giải tích là 3.03125 m3 (diện tích phần dải
    ``-2 <= 0.8a + 0.6b <= 0.5`` trên hình chữ nhật 5 x 1).
    """
    from bridge_evolution.revit_family.sketch_family import _box_overlap_m3
    be = _footing()
    assert math.isclose(_box_overlap_m3(be, _pile_hole()), 3.6, abs_tol=1e-9)
    xien = BoxSpec(start_m=(0.0, 0.0, 0.0), end_m=(3.0, 4.0, 0.0),
                   width_m=1.0, height_m=1.0, name="Xien")
    assert math.isclose(_box_overlap_m3(be, xien), 3.03125, abs_tol=1e-9)
    xa = BoxSpec(start_m=(50.0, 0.0, 0.0), end_m=(50.0, 2.5, 0.0),
                 width_m=1.0, height_m=1.0, name="Xa")
    assert _box_overlap_m3(be, xa) == 0.0, "hai khối rời nhau thì không khoét gì"
    trong = BoxSpec(start_m=(0.0, 0.5, 0.0), end_m=(0.0, 1.5, 0.0),
                    width_m=1.0, height_m=2.0, name="Trong")
    assert math.isclose(_box_overlap_m3(be, trong), trong.volume_m3, abs_tol=1e-9)


# -- 6.6 khai báo overload giả định ---------------------------------------

def test_moi_overload_gia_dinh_cua_sketch_deu_hien_trong_ma_c_sharp():
    """Cùng kỷ luật với ``adaptive_family.DECLARED_OVERLOADS``.

    RFC-1.1.0 ghi KẾT QUẢ, hiếm khi ghi CHỮ KÝ. Chữ ký dùng ở đây là giả định,
    và người đọc bên Revit phải phân biệt được đâu là số đo, đâu là suy đoán.
    """
    from bridge_evolution.revit_family import SKETCH_DECLARED_OVERLOADS
    goi = "\n".join(make("generic_model") for make in ALL_FIVE)
    for op_name, mo_ta in SKETCH_DECLARED_OVERLOADS:
        assert len(mo_ta) > 40, f"{op_name}: mô tả giả định quá sơ sài"
        assert f"{op_name}(" in goi, f"{op_name} không còn được phát ra"
        assert f"GIA DINH OVERLOAD: {op_name}(" in goi, op_name


def test_ten_trong_bang_overload_sketch_deu_tro_toi_phep_that_neu_co_gac():
    from bridge_evolution.revit_family import SKETCH_DECLARED_OVERLOADS
    for op_name, _ in SKETCH_DECLARED_OVERLOADS:
        if op_name in OPERATIONS:
            assert operation_spec(op_name).name == op_name
        else:
            # NewCurveLoopsProfile là API Creation, không phải phép ĐƯỢC GÁC —
            # nó vẫn phải được khai báo là giả định, nhưng không có ô trong bảng
            assert op_name == "NewCurveLoopsProfile", op_name


# -- 6.7 work plane nghiêng phải xin thêm phép -----------------------------

def test_giang_cheo_xin_them_phep_inclined_work_plane():
    brace = _brace()
    assert brace.needs_inclined_work_plane is True
    code = prismatic_member("structural_framing", RFA, brace)
    assert "NGHIENG" in code


def test_thanh_trung_truc_chinh_khong_can_xin_them():
    thang = BoxSpec(start_m=(0.0, 0.0, 0.0), end_m=(10.0, 0.0, 0.0),
                    width_m=0.4, height_m=0.6, name="Dam")
    assert thang.needs_inclined_work_plane is False
    code = prismatic_member("generic_model", RFA, thang)
    assert "trung mot truc chinh" in code


def test_vom_ngoai_mat_phang_chinh_cung_phai_xin_phep_inclined():
    """Danh sách phép phải mô tả ĐÚNG cái mã C# làm.

    ``arch_rib_segment`` phát ra một ``Plane.CreateByNormalAndOrigin`` với pháp
    tuyến bất kỳ, y như ``prismatic_member`` — nên nó cũng phải xin
    ``InclinedWorkPlane`` khi mặt phẳng đó nghiêng. Vòm nằm trong mặt phẳng
    z = 0 thì pháp tuyến trùng trục chính và KHÔNG cần xin.
    """
    phang = arch_rib_segment("generic_model", RFA, **ARCH_OK)
    assert "mat phang phac thao cua path: trung mot truc chinh" in phang

    cheo = arch_rib_segment(
        "structural_framing", RFA,
        start_m=(0.0, 0.0, 0.0), mid_m=(10.0, 4.0, 5.0), end_m=(20.0, 0.0, 10.0),
        width_start_m=1.0, height_start_m=1.5,
        width_end_m=1.0, height_end_m=1.2)
    assert "mat phang phac thao cua path: NGHIENG" in cheo


def test_tron_xoay_profile_dat_cheo_cung_phai_xin_phep_inclined():
    nghieng = revolved_member(
        "generic_model", RFA,
        profile_m=[(0.6, 0.0, 0.6), (1.4, 0.0, 1.4), (1.0, 3.0, 1.0),
                   (0.6, 3.0, 0.6)],
        axis_start_m=(0.0, 0.0, 0.0), axis_end_m=(0.0, 3.0, 0.0))
    assert "mat phang phac thao: NGHIENG" in nghieng
    thang = revolved_member("generic_model", RFA, **REV_OK)
    assert "mat phang phac thao: trung mot truc chinh" in thang


def test_cot_thang_dung_van_dung_duoc_he_truc_tiet_dien():
    cot = BoxSpec(start_m=(0.0, 0.0, 0.0), end_m=(0.0, 10.0, 0.0),
                  width_m=1.0, height_m=1.5, name="Cot")
    assert cot.needs_inclined_work_plane is False
    assert prismatic_member("structural_column", RFA, cot)


def test_up_hint_song_song_truc_bi_chan_ngay_luc_dung_spec():
    with pytest.raises(DegenerateGeometryError) as exc:
        BoxSpec(start_m=(0.0, 0.0, 0.0), end_m=(0.0, 10.0, 0.0),
                width_m=1.0, height_m=1.5, up_hint_m=(0.0, 1.0, 0.0))
    assert "song song" in str(exc.value)


# -- 6.7 BoxSpec kiểm ngay lúc dựng ---------------------------------------

@pytest.mark.parametrize("sua", [
    dict(width_m=0.0),
    dict(height_m=-1.0),
    dict(width_m=REVIT_SHORT_CURVE_TOL_M / 2),
    dict(width_m=float("nan")),
    dict(height_m=float("inf")),
    dict(end_m=(0.0, 0.0, 0.0)),
    dict(start_m=(0.0, 0.0)),
    dict(start_m=(0.0, 0.0, "x")),
    dict(name="2Xau"),
    dict(name="co dau"),
])
def test_boxspec_chan_ngay_luc_dung(sua):
    base = dict(start_m=(0.0, 0.0, 0.0), end_m=(6.0, 0.0, 0.0),
                width_m=0.4, height_m=0.6, name="Ok")
    base.update(sua)
    with pytest.raises(DegenerateGeometryError):
        BoxSpec(**base)


def test_boxspec_the_tich_va_chieu_dai_dung():
    box = BoxSpec(start_m=(0.0, 0.0, 0.0), end_m=(0.0, 2.5, 0.0),
                  width_m=10.0, height_m=8.0, name="Be")
    assert box.length_m == pytest.approx(2.5)
    assert box.volume_m3 == pytest.approx(200.0)


def test_prismatic_tu_choi_thu_khong_phai_boxspec():
    with pytest.raises(DegenerateGeometryError):
        prismatic_member("generic_model", RFA,
                         {"start_m": (0, 0, 0), "end_m": (1, 0, 0)})


# -- 6.8 mọi lỗi của nhóm SKETCH đều là ValueError -------------------------

@pytest.mark.parametrize("err", [
    SketchFamilyError, DegenerateGeometryError, CollinearArcError,
    BlendElevationError, RevolveAxisError, VoidDoesNotCutError,
])
def test_moi_loi_sketch_deu_la_valueerror_va_cung_goc_voi_cong(err):
    assert issubclass(err, RevitFamilyCapabilityError)
    assert issubclass(err, ValueError)


# -- 6.9 mọi hàm nhúng dấu claim, không hàm nào nâng mức ------------------

@pytest.mark.parametrize("make", ALL_FIVE)
def test_khong_ham_nao_phat_muc_claim_khac_f0_idea(make):
    code = make("generic_model")
    assert 'fm.Set(pClaimLevel, @"F0_IDEA");' in code
    assert CLAIM_STATEMENT_PARAM in code
    for level in ("SCREENED", "NUMERICALLY_VERIFIED", "ENGINEERING_CANDIDATE"):
        assert level not in code


@pytest.mark.parametrize("make", ALL_FIVE)
def test_khong_ham_nao_dung_return_trong_than_ma(make):
    """``return`` giữa using(Transaction) bỏ qua catch -> bỏ ngỏ family document.

    Ba câu ``return`` của khuôn đều nằm NGOÀI thân mã; thân mã chỉ được ``throw``.
    """
    code = make("generic_model")
    body = code[code.index("--- than ma do nguoi goi truyen vao ---"):
                code.index("--- het than ma ---")]
    assert "return" not in body
    assert "throw new InvalidOperationException(" in body


# =========================================================================
# THẾ GIỚI ADAPTIVE / MASSING — bridge_evolution/revit_family/adaptive_family.py
#
# Ba lớp, theo đúng thứ tự đắt giá:
#   A. CHẶN   — [A3] mặt phẳng XY, [A4] loft không flex, [A5] chưa hoà giải.
#   B. PHÁT   — cái gì CÓ đo thì phát được mã thật, và mã đó đúng nguyên tắc
#               "hình do ĐIỂM điều khiển".
#   C. PROBE  — FLEX TEST phải đo CẢ thể tích, không chỉ spine ([A4]).
# =========================================================================

import json as _json

from bridge_evolution.revit_family import (
    DECLARED_OVERLOADS,
    FLEX_PRESERVING_FORM_OP,
    MASSING_LOFT_OPS,
    MEMBER_OPS,
    SPINE_OPS,
    STATIC_FORM_OP,
    VOID_OPS,
    AdaptiveTwoPointSpec,
    adaptive_flex_probe,
    adaptive_four_point_panel,
    adaptive_section_plane_body,
    adaptive_two_point_member,
    adaptive_two_point_spine_body,
    adaptive_void,
    blocking_operations,
    massing_loft_surface,
)
from bridge_evolution.revit_family.adaptive_family import (
    _rect_profile_lines,
    _swept_blend_form_lines,
    _void_form_lines,
)

#: Dầm chủ 39 m của dự án thật — tiết diện thuôn 2.2 m xuống 1.6 m.
DAM = AdaptiveTwoPointSpec(
    point_a_m=(0.0, 0.0, 0.0),
    point_b_m=(39.0, 0.35, 0.0),
    width_start_m=1.0, height_start_m=2.2,
    width_end_m=1.0, height_end_m=1.6,
    name="DAM_CHU_N1",
)
OUT_RFA = r"C:\Temp\dylight_dam.rfa"


# ------------------------------------------------- A. CHẶN

def test_a3_mat_phang_xy_la_bay_da_do_la_hong():
    """[A3] Hợp đồng Pha 2 ghi 'dùng GetCoordinatePlaneReferenceXY()'. Sai."""
    with pytest.raises(UnsupportedInWorldError) as exc:
        require_operation("AdaptivePointCoordinatePlaneXY", "adaptive")
    msg = str(exc.value)
    assert "Cannot create loft form" in msg, "phải dẫn lỗi Revit nguyên văn"
    assert "song song" in msg.lower(), "phải nói VÌ SAO: profile song song path"
    # còn lối đúng thì đi qua được
    require_operation("AdaptivePointCoordinatePlaneYZ", "adaptive")


def test_a4_loft_form_khong_flex_la_ket_qua_am_duoc_ma_hoa():
    """[A4] Phép đo đắt nhất: form dựng ĐƯỢC nhưng thể tích ĐỨNG YÊN."""
    # tạo form thì đo được là chạy
    require_operation("NewLoftForm", "adaptive")
    # nhưng đòi nó FLEX thì đã đo là hỏng
    with pytest.raises(UnsupportedInWorldError) as exc:
        require_operation("NewLoftFormFlex", "adaptive")
    msg = str(exc.value)
    assert "54.533" in msg, "phải dẫn số đo, không chỉ nói 'không flex'"
    assert "1.0000" in msg, "tỷ lệ thể tích 1.0000 là bằng chứng"
    assert "IM LẶNG" in msg, "hỏng im lặng nguy hiểm hơn hỏng có ngoại lệ"


def test_a5_la_loi_duy_nhat_giu_tham_so_va_hien_dang_chan():
    """[A5] có path -> giữ flex. Nhưng §3 tự mâu thuẫn nên bảng CHẶN."""
    spec = operation_spec(FLEX_PRESERVING_FORM_OP)
    blob = " ".join(spec.constraints) + " " + spec.not_measured_reason
    assert "2.4104" in blob, "phải ghi tỷ lệ đo được của lần chạy ĐẠT"
    assert "MÂU THUẪN" in blob, "mâu thuẫn nội bộ §3 phải nằm trong dữ liệu"
    with pytest.raises(NotMeasuredError):
        require_operation(FLEX_PRESERVING_FORM_OP, "adaptive")


def test_cau_kien_adaptive_hien_bi_chan_va_noi_ro_chan_o_dau():
    with pytest.raises(NotMeasuredError):
        adaptive_two_point_member(DAM, OUT_RFA)
    chan = dict(blocking_operations(MEMBER_OPS, "adaptive"))
    assert chan == {
        "NewModelCurve": MeasuredStatus.NOT_MEASURED,
        FLEX_PRESERVING_FORM_OP: MeasuredStatus.NOT_MEASURED,
    }, "danh sách chặn phải đủ, không phải gỡ từng cái một"


def test_cau_kien_adaptive_khong_bao_gio_lui_ve_loft_form():
    """Lùi im lặng về NewLoftForm là đúng cái [A4] cấm — khối cứng đội lốt."""
    assert STATIC_FORM_OP not in MEMBER_OPS
    assert FLEX_PRESERVING_FORM_OP in MEMBER_OPS


def test_void_chan_o_solidsolidcut_vi_s2_hong_im_lang():
    with pytest.raises(NotMeasuredError):
        adaptive_void(DAM, OUT_RFA)
    assert "SolidSolidCut" in VOID_OPS
    msg = " ".join(operation_spec("SolidSolidCut").constraints)
    assert "200.000" in msg and "196.400" in msg, "[S2] phải dẫn hai thể tích"


def test_void_khai_dung_nhung_phep_ma_than_ma_that_su_dung():
    """Khai ít hơn thực dùng là cổng chặn nói dối.

    Thân mã void dựng profile bằng ``NewModelCurve`` trên mặt phẳng tiết diện
    YZ, y hệt cấu kiện — nên hai phép đó phải nằm trong ``VOID_OPS``.
    """
    for phep in ("NewModelCurve", "AdaptivePointCoordinatePlaneYZ",
                 "NewLoftForm", "SolidSolidCut"):
        assert phep in VOID_OPS, phep
    assert dict(blocking_operations(VOID_OPS, "adaptive")) == {
        "NewModelCurve": MeasuredStatus.NOT_MEASURED,
        "SolidSolidCut": MeasuredStatus.NOT_MEASURED,
    }


def test_s2_void_trong_sketch_da_do_la_khong_cat():
    with pytest.raises(UnsupportedInWorldError) as exc:
        require_operation("SolidSolidCut", "generic_model")
    assert "CutNotAppropriateForElements" in str(exc.value)


def test_massing_chan_vi_curvebypoints_va_saveas_chua_do():
    with pytest.raises(NotMeasuredError):
        massing_loft_surface([[(0, 0, 0), (1, 0, 0)],
                              [(0, 0, 5), (1, 0, 5)]], OUT_RFA)
    assert dict(blocking_operations(MASSING_LOFT_OPS, "mass")) == {
        "NewCurveByPoints": MeasuredStatus.NOT_MEASURED,
        "SaveAs": MeasuredStatus.NOT_MEASURED,
    }


def test_massing_chan_hinh_hoc_truoc_khi_cham_cong():
    """Profile suy biến phải chết ở validation, KHÔNG phải ở cổng năng lực.

    Kiểu lỗi ở đây là load-bearing. ``massing_loft_surface`` đang bị cổng chặn
    hoàn toàn, nên ``pytest.raises(ValueError)`` được thoả mãn bởi
    ``NotMeasuredError`` với MỌI đầu vào — kể cả khi xoá sạch phần kiểm hình
    học. Đòi đúng ``CSharpEmitError`` (nhánh validation) thì đột biến đó mới
    làm test đỏ.
    """
    with pytest.raises(CSharpEmitError) as exc:
        massing_loft_surface([[(0, 0, 0), (1, 0, 0)]], OUT_RFA)
    assert "TỐI THIỂU 2 profile" in str(exc.value)
    with pytest.raises(CSharpEmitError) as exc:
        massing_loft_surface([[(0, 0, 0)], [(0, 0, 5)]], OUT_RFA)
    assert "cần ít nhất 2" in str(exc.value)
    # và NotMeasuredError KHÔNG phải CSharpEmitError — hai nhánh phân biệt được
    assert not issubclass(NotMeasuredError, CSharpEmitError)


def test_adaptive_4_diem_luon_chan_va_dan_ca_meo():
    with pytest.raises(NotMeasuredError) as exc:
        adaptive_four_point_panel()
    assert "MÉO" in str(exc.value), "phải dẫn tiền lệ panel 4 điểm bị méo"


def test_hosted_point_chan_vi_khong_ai_ghi_ten_api():
    """[A2] lặp lại: đoán tên API là cách hỏng đã gặp một lần."""
    with pytest.raises(NotMeasuredError) as exc:
        require_operation("HostedPointOnCurve", "adaptive")
    msg = str(exc.value)
    assert "TÊN API" in msg
    assert "NewPointOnEdge" in msg, "phải gọi đích danh cái tên dễ bị đoán"


@pytest.mark.parametrize("key", SKETCH_KEYS + TWO_D_KEYS)
def test_bo_xuong_adaptive_bi_chan_ngoai_the_gioi_diem(key):
    with pytest.raises(UnsupportedInWorldError):
        adaptive_two_point_spine_body(DAM, template_key=key)


# ------------------------------------------------- B. PHÁT

def test_bo_xuong_2_diem_phat_duoc_va_dung_nguyen_tac_diem():
    code = "\n".join(adaptive_two_point_spine_body(DAM))
    assert "NewReferencePoint" in code
    lenh = "\n".join(l for l in code.splitlines()
                     if not l.strip().startswith("//"))
    assert lenh.count("MakeAdaptivePoint") == 2, "PHẢI adaptive hoá CẢ HAI điểm"
    assert lenh.count("NewReferencePoint") == 2
    assert "AdaptivePointType.PlacementPoint" in code
    assert "NewCurveByPoints" in code
    code.encode("ascii")


def test_bo_xuong_khong_lam_thay_viec_cua_scaffold():
    code = "\n".join(adaptive_two_point_spine_body(DAM))
    for cam in ("fd.SaveAs", "fd.Close", "tx.Commit", "fd.Regenerate"):
        assert cam not in code, f"thân mã không được giành {cam} của scaffold"


def test_mat_phang_tiet_dien_la_yz_khong_phai_xy():
    """[A3] — cái sửa quan trọng nhất so với hợp đồng Pha 2."""
    code = "\n".join(adaptive_section_plane_body("ptA", "plA",
                                                 regenerated_before=True))
    assert "GetCoordinatePlaneReferenceYZ()" in code
    assert "GetCoordinatePlaneReferenceXY" not in code
    assert "SketchPlane.Create(fd," in code
    assert "GetCoordinateSystem()" in code
    assert "Regenerate" in code, "phải cảnh báo hệ toạ độ chỉ đúng SAU Regenerate"
    code.encode("ascii")


def test_mat_phang_tiet_dien_tu_choi_phat_khi_chua_regenerate():
    """[A3] chặn thứ hai: KHÔNG chứng minh được đã Regenerate thì không phát mã.

    Chú thích cảnh báo trong thân mã không cứu được ai — nó thoả mãn
    ``assert "Regenerate" in code`` mà không thoả mãn thứ tự THI HÀNH.
    """
    with pytest.raises(RevitFamilyCapabilityError):
        # cổng thế giới vẫn chặn trước, kiểm ở template SKETCH
        adaptive_section_plane_body("ptA", "plA", template_key="generic_model")
    with pytest.raises(ValueError) as exc:
        adaptive_section_plane_body("ptA", "plA")
    msg = str(exc.value)
    assert "[A3]" in msg
    assert "MA TRẬN ĐƠN VỊ" in msg
    assert "pre_regen_lines" in msg


def test_A3_thu_tu_thi_hanh_duoc_kiem_tren_ma_da_ghep_qua_scaffold():
    """Kiểm THỨ TỰ THẬT, không phải sự có mặt của chữ 'Regenerate'.

    Đây là ca hỏng cụ thể: spine chéo (0.6, 0.8, 0) — dầm chủ trên cầu cong.
    [A3] đo SAU Regenerate BasisY = (-0.800, 0.600, 0.000); TRƯỚC Regenerate
    là (0, 1, 0). Đọc sớm thì profile lệch ~53 độ mà không ngoại lệ nào báo.
    """
    cheo = AdaptiveTwoPointSpec(
        point_a_m=(0.0, 0.0, 0.0), point_b_m=(6.0, 0.0, 8.0),
        width_start_m=1.0, height_start_m=2.0,
        width_end_m=1.0, height_end_m=2.0, name="DAM_CHEO")
    code = family_scaffold(
        template_path("adaptive"), OUT_RFA,
        adaptive_section_plane_body("ptA", "plA", regenerated_before=True)
        + claim_parameters_cs(),
        pre_regen_lines=adaptive_two_point_spine_body(cheo))
    # BỎ CHÚ THÍCH trước khi so thứ tự: thân mã adaptive NHẮC tên
    # GetCoordinateSystem trong chú thích cảnh báo, và một lời cảnh báo không
    # được phép làm thoả mãn một kiểm tra thứ tự thi hành.
    assert "GetCoordinateSystem()" in code.split("fd.Regenerate();")[0], \
        "chú thích cảnh báo đứng trước Regenerate — đúng cái che mất cái bẫy"
    lenh = _lenh(code)
    assert lenh.index("fd.Regenerate();") < lenh.index("GetCoordinateSystem()")


def test_profile_bam_transform_cua_diem_khong_phai_toa_do_tuyet_doi():
    """Đặt profile bằng toạ độ tuyệt đối = dựng đúng lần đầu rồi không flex."""
    code = "\n".join(_rect_profile_lines("profA", "plA", 1.0, 2.2))
    assert "plATf.Origin" in code
    assert "plATf.BasisY" in code and "plATf.BasisZ" in code
    assert "plATf.BasisX" not in code, "[A3] BasisX là TIẾP TUYẾN, không thuộc tiết diện"
    assert code.count("NewModelCurve") == 4, "profile chữ nhật = 4 cạnh"
    assert code.count("GeometryCurve.Reference") == 4


def test_profile_doi_feet_dung_nua_kich_thuoc():
    code = "\n".join(_rect_profile_lines("p", "pl", 1.0, 2.2))
    nua_rong = 0.5 * FT
    nua_cao = 1.1 * FT
    assert f"{nua_rong:.9f}".rstrip("0") in code
    assert f"{nua_cao:.9f}".rstrip("0") in code


def test_khoi_a5_truyen_SPINE_lam_path():
    """Mấu chốt [A5]: có PATH thì form bị ràng buộc vào spine -> flex giữ được."""
    code = "\n".join(_swept_blend_form_lines(DAM))
    assert "pathRa.Append(spine.GeometryCurve.Reference);" in code
    assert "NewSweptBlendForm(true, pathRa, profRaa)" in code
    lenh = [l for l in code.splitlines() if not l.strip().startswith("//")]
    assert not any("NewLoftForm" in l for l in lenh), \
        "lối [A5] không được lẫn NewLoftForm trong phần LỆNH"
    code.encode("ascii")


def test_duong_void_dang_chan_van_phai_BIEN_DICH_DUOC():
    """Một đường dựng "viết sẵn cho ngày cổng mở" mà không biên dịch được thì
    không sẵn gì cả — ngày đó vẫn phải viết lại dưới áp lực.

    Trước bản sửa: thân mã void tham chiếu ``voidProfiles`` KHÔNG khai báo ở
    đâu, và một dòng chú thích chứa ký tự ngoài ASCII. Cả hai chỉ lộ ra khi
    cổng mở, vì ``require_operations`` raise trước.
    """
    code = "\n".join(_void_form_lines(DAM))
    code.encode("ascii")                       # bất biến 4
    khai_bao = code.index("ReferenceArrayArray voidProfiles")
    dung = code.index("NewLoftForm(false, voidProfiles)")
    assert khai_bao < dung, "biến phải khai báo TRƯỚC khi dùng"
    for bien in ("ReferenceArray voidA", "ReferenceArray voidB"):
        assert bien in code, f"{bien} phải được khai báo trong chính thân mã"
    assert "voidProfiles.Append(voidA);" in code
    assert "voidProfiles.Append(voidB);" in code
    assert "GIA DINH OVERLOAD" in code


def test_than_ma_void_chi_muon_bien_do_GIAI_DOAN_1_khai_bao():
    """Hợp đồng giữa hai giai đoạn: void mượn ``fc``/``ptA``/``ptB`` của spine.

    Biến mượn phải có chỗ khai báo THẬT ở giai đoạn 1, nếu không thì mã ghép
    lại vẫn không biên dịch được — đúng cái lỗi đã có ở ``voidProfiles``.
    """
    spine = "\n".join(adaptive_two_point_spine_body(DAM))
    void = "\n".join(_void_form_lines(DAM))
    for khai_bao in ("FamilyItemFactory fc = fd.FamilyCreate;",
                     "ReferencePoint ptA = ", "ReferencePoint ptB = "):
        assert khai_bao in spine, khai_bao
    for muon in ("fc.", "ptA.", "ptB."):
        assert muon in void, f"{muon} là biến giai đoạn 1, phải mượn được"


def test_overload_gia_dinh_deu_duoc_khai_bao_va_tro_toi_phep_that():
    """Giả định phải có TÊN và có CHỖ, không nằm im trong đầu người viết."""
    for op_name, mo_ta in DECLARED_OVERLOADS:
        assert operation_spec(op_name) is not None
        assert len(mo_ta) > 40, f"{op_name}: mô tả giả định quá sơ sài"


def test_dau_gia_dinh_overload_hien_trong_ma_c_sharp():
    """Người đọc bên Revit phải thấy chỗ nào là giả định, chỗ nào là đo được."""
    code = "\n".join(adaptive_two_point_spine_body(DAM))
    assert "GIA DINH OVERLOAD" in code


# ------------------------------------------------- C. FLEX PROBE

def _sinh_probe(**kw):
    return adaptive_flex_probe(r"C:\Temp\dam.rfa",
                               move_point_to_m=(25.0, 8.0, 0.0), **kw)


def test_flex_probe_do_CA_the_tich_LAN_spine():
    """Bài học [A4]: probe chỉ đo spine sẽ báo ĐẠT cho một family HỎNG."""
    code = _sinh_probe()
    assert "GenericForm" in code and "sd.Volume" in code, "phải đo THỂ TÍCH"
    assert "CurveByPoints" in code and "GeometryCurve.Length" in code, "phải đo SPINE"
    assert "bool chayTheo = spineFlex && volFlex;" in code, \
        "CHAY_THEO phải đòi CẢ HAI cùng đổi — spine flex một mình là ca hỏng đã gặp"


def test_flex_probe_doi_diem_roi_regenerate_TRONG_transaction():
    code = _sinh_probe()
    i_move = code.index("moved.Position =")
    i_regen = code.index("fdoc.Regenerate();")
    i_roll = code.index("ptx.RollBack();")
    assert i_move < i_regen < i_roll
    assert "ptx.Start();" in code
    assert code.index("ptx.Start();") < i_move


def test_flex_probe_khong_pha_file_tren_dia():
    code = _sinh_probe()
    assert "ptx.RollBack();" in code
    assert "ptx.Commit()" not in code, "probe là dụng cụ ĐO, không phải bước dựng"
    assert "fdoc.Save" not in code


def test_flex_probe_khong_dung_toi_document_cua_host():
    code = _sinh_probe()
    assert not re.search(r"new\s+Transaction\s*\(\s*document\b", code)
    assert not re.search(r"\bdocument\s*\.\s*Close\s*\(", code)
    assert "var app = document.Application;" in code, "chỉ ĐỌC host"


def test_flex_probe_in_so_bang_invariantculture():
    """Máy này chạy locale Việt: ToString('F6') mặc định cho dấu PHẨY -> JSON hỏng."""
    code = _sinh_probe()
    assert "CultureInfo.InvariantCulture" in code
    assert code.count('.ToString(@"F6", ci)') == 6


def test_flex_probe_la_ascii_va_ngoac_can_bang():
    code = _sinh_probe()
    code.encode("ascii")
    sach = re.sub(r'@?"(?:[^"]|"")*"', "", code)
    sach = "\n".join(l.split("//")[0] for l in sach.splitlines())
    assert sach.count("{") == sach.count("}")


def _mo_phong_json(code: str, gia_tri: dict) -> str:
    """Chạy tay phép nối chuỗi C# của probe để lấy ra chuỗi JSON THẬT.

    Không phải trình biên dịch C#: nó chỉ thay từng biểu thức C# đã biết bằng
    giá trị mẫu rồi ghép các chuỗi verbatim lại. Đủ để chứng minh chuỗi sinh ra
    là JSON hợp lệ — kể cả phần thoát dấu backslash của đường dẫn Windows.
    """
    # rindex: dòng ĐẦU là khai báo `string outJson = "";`, không phải biểu thức
    dau = code.rindex("outJson =")
    cuoi = code.index(";", dau)
    bieu_thuc = code[dau + len("outJson ="):cuoi]
    # 1. số: <expr>.ToString(@"F6", ci)
    bieu_thuc = re.sub(r'([A-Za-z0-9_\[\]]+)\.ToString\(@"F6", ci\)',
                       lambda m: '@"%.6f"' % gia_tri[m.group(1)], bieu_thuc)
    # 2. bool: (<expr> ? @"true" : @"false")
    bieu_thuc = re.sub(r'\(([A-Za-z0-9_]+) \? @"true" : @"false"\)',
                       lambda m: '@"%s"' % str(gia_tri[m.group(1)]).lower(),
                       bieu_thuc)
    # 3. đường dẫn có thoát dấu backslash
    bieu_thuc = bieu_thuc.replace('rfaPath.Replace(@"\\", @"\\\\")',
                                  '@"' + gia_tri["rfaPath"].replace("\\", "\\\\") + '"')
    # 4. số nguyên trần (point_index) — C# nối int vào string được, JSON cũng nhận
    bieu_thuc = re.sub(r"\+ (\d+) \+", r'+ @"\1" +', bieu_thuc)
    # 5. ghép các chuỗi verbatim còn lại
    manh = re.findall(r'@"((?:[^"]|"")*)"', bieu_thuc)
    con_lai = re.sub(r'@"(?:[^"]|"")*"', "", bieu_thuc).replace("+", "").strip()
    assert not con_lai, "còn biểu thức C# chưa mô phỏng: %r" % con_lai
    return "".join(m.replace('""', '"') for m in manh)


def test_json_probe_sinh_ra_la_json_hop_le_va_du_truong():
    """Chứng minh trên CHÍNH chuỗi sinh ra, không phải bằng lời trong docstring."""
    code = _sinh_probe()
    ket_qua = _mo_phong_json(code, {
        "rfaPath": r"C:\Temp\dam.rfa",
        "spineM[0]": 10.0, "spineM[1]": 24.104,
        "volM3[0]": 54.533, "volM3[1]": 54.533,      # <- đúng ca [A4]
        "rSpine": 2.4104, "rVol": 1.0,
        "spineFlex": True, "volFlex": False,
        "coKhoi": True, "chayTheo": False,
    })
    data = _json.loads(ket_qua)
    assert data["schema"] == "dylight.flex_probe/1"
    assert data["rfa"] == r"C:\Temp\dam.rfa", "đường dẫn Windows phải thoát đúng"
    assert data["spine_truoc_m"] == 10.0
    assert data["the_tich_truoc_m3"] == data["the_tich_sau_m3"]
    # đây là bài kiểm quyết định: spine flex nhưng khối đứng yên -> KHÔNG ĐẠT
    assert data["spine_co_flex"] is True
    assert data["the_tich_co_flex"] is False
    assert data["CHAY_THEO"] is False, \
        "[A4] spine flex một mình KHÔNG được tính là ĐẠT"


def test_json_probe_bao_DAT_khi_ca_hai_cung_flex():
    code = _sinh_probe()
    data = _json.loads(_mo_phong_json(code, {
        "rfaPath": r"C:\Temp\dam.rfa",
        "spineM[0]": 10.0, "spineM[1]": 24.104,
        "volM3[0]": 54.533, "volM3[1]": 131.447,     # <- đúng ca [A5]
        "rSpine": 2.4104, "rVol": 2.4104,
        "spineFlex": True, "volFlex": True,
        "coKhoi": True, "chayTheo": True,
    }))
    assert data["CHAY_THEO"] is True
    assert data["ty_le_spine"] == data["ty_le_the_tich"] == 2.4104


def test_flex_probe_chan_tham_so_rac():
    with pytest.raises(ValueError):
        adaptive_flex_probe(r"C:\Temp\x.rvt", move_point_to_m=(1, 2, 3))
    with pytest.raises(ValueError):
        adaptive_flex_probe(r"C:\Temp\x.rfa", move_point_to_m=(1, 2))
    with pytest.raises(ValueError):
        adaptive_flex_probe(r"C:\Temp\x.rfa", move_point_to_m=(1, 2, 3),
                            point_index=-1)
    with pytest.raises(ValueError):
        adaptive_flex_probe(r"C:\Temp\x.rfa",
                            move_point_to_m=(float("nan"), 0, 0))


# ------------------------------------------------- đặc tả cấu kiện

def test_spec_chan_hai_diem_trung_nhau():
    with pytest.raises(ValueError) as exc:
        AdaptiveTwoPointSpec((1, 2, 3), (1, 2, 3), 1, 1, 1, 1)
    assert "trùng nhau" in str(exc.value)


@pytest.mark.parametrize("xau", [
    {"width_start_m": 0.0}, {"height_end_m": -1.0},
    {"width_end_m": float("inf")},
])
def test_spec_chan_tiet_dien_suy_bien(xau):
    kw = dict(point_a_m=(0, 0, 0), point_b_m=(10, 0, 0), width_start_m=1.0,
              height_start_m=1.0, width_end_m=1.0, height_end_m=1.0)
    kw.update(xau)
    with pytest.raises(ValueError):
        AdaptiveTwoPointSpec(**kw)


def test_spec_chan_ten_khong_phai_dinh_danh():
    for ten in ("dam chu", "dầm", "", "1dam-x"):
        with pytest.raises(ValueError):
            AdaptiveTwoPointSpec((0, 0, 0), (10, 0, 0), 1, 1, 1, 1, ten)


def test_spec_span_dung_pythagore():
    s = AdaptiveTwoPointSpec((0, 0, 0), (25, 0, 8), 1, 1, 1, 1)
    assert math.isclose(s.span_m, math.hypot(25, 8), rel_tol=1e-12)


def test_toa_do_theo_he_cau_x_doc_y_cao_z_ngang():
    """Điểm B ở y=0.35 (cao độ) phải ra số CUỐI của XYZ Revit."""
    code = "\n".join(adaptive_two_point_spine_body(DAM))
    dong_b = [l for l in code.splitlines() if "ptB = " in l][0]
    so = [float(v) for v in re.findall(r"-?\d+\.\d+", dong_b)]
    assert math.isclose(so[0], 39.0 * FT, abs_tol=1e-6), "số đầu = dọc cầu"
    assert math.isclose(so[1], 0.0, abs_tol=1e-9), "số giữa = NGANG cầu (z)"
    assert math.isclose(so[2], 0.35 * FT, abs_tol=1e-6), "số cuối = CAO ĐỘ (y)"


def test_blocking_operations_khong_raise_theo_trang_thai():
    assert blocking_operations(SPINE_OPS, "adaptive") == ()
    assert blocking_operations(["NewExtrusion"], "adaptive") == (
        ("NewExtrusion", MeasuredStatus.MEASURED_FAIL),)
    with pytest.raises(UnknownOperationError):
        blocking_operations(["KhongCoPhepNay"], "adaptive")


# =========================================================================
# 8. QUÉT TOÀN BỘ CORPUS — bất biến C# áp cho MỌI chuỗi gói này phát ra
#
# Bảy mục trên kiểm từng nhóm một. Mục này kiểm CẢ GÓI trong một lượt: dựng
# MỌI chuỗi C# mà ``bridge_evolution.revit_family`` phát được hôm nay rồi soi
# cùng một bộ bất biến. Lý do phải có lớp quét ngang: một bộ sinh mới thêm
# vào gói có thể lọt qua mọi test theo-nhóm ở trên mà vẫn phát ra
# ``new Transaction(document`` hoặc quên dấu claim.
#
# Danh sách corpus không được phép mục ruỗng theo thời gian, nên
# ``test_moi_ham_cong_khai_deu_duoc_phan_loai`` bắt MỌI hàm công khai của gói
# phải nằm trong đúng một trong bốn rổ: PHÁT CHƯƠNG TRÌNH, PHÁT MẢNH THÂN MÃ,
# KHÔNG PHÁT MÃ, hoặc ĐANG CHẶN. Thêm hàm mà không xếp rổ là test đỏ — đó
# chính là chỗ ép người sau phải quyết định.
# =========================================================================

import inspect  # noqa: E402

import bridge_evolution.revit_family as rf  # noqa: E402

#: Năm bộ sinh SKETCH, kèm tên đọc được (khớp THỨ TỰ của ``ALL_FIVE``).
NAM_HAM_SKETCH = (
    "arch_rib_segment",
    "tapered_pier_shaft",
    "revolved_member",
    "prismatic_member",
    "void_cut",
)


def _corpus_family():
    """MỌI chương trình C# ghi ra một file ``.rfa`` mà gói này phát được.

    Quét CHÉO: năm bộ sinh x cả SÁU template SKETCH, chứ không chỉ
    ``generic_model``. Một bất biến chỉ đúng trên một template thì không phải
    bất biến.
    """
    ra = [(f"{ten}[{key}]", make(key))
          for key in SKETCH_KEYS
          for ten, make in zip(NAM_HAM_SKETCH, ALL_FIVE)]
    ra.append((
        "guarded_family_scaffold[generic_model]",
        guarded_family_scaffold("generic_model", RFA, ["NewExtrusion"],
                                ["// than ma toi thieu"])))
    ra.append((
        "family_scaffold[generic_model]",
        family_scaffold(template_path("generic_model"), RFA,
                        claim_parameters_cs(template_key="generic_model"))))
    return tuple(ra)


def _corpus_khac():
    """Chương trình C# hoàn chỉnh KHÔNG sinh family — hiện chỉ có FLEX PROBE."""
    return (
        ("adaptive_flex_probe",
         adaptive_flex_probe(r"C:\Temp\dylight_dam.rfa",
                             move_point_to_m=(60.0, 1.0, 0.0))),
    )


def _corpus_manh():
    """Các MẢNH thân mã (``list[str]``) — chưa phải chương trình, vẫn phải sạch."""
    return (
        ("adaptive_two_point_spine_body",
         "\n".join(adaptive_two_point_spine_body(DAM))),
        ("adaptive_section_plane_body",
         "\n".join(adaptive_section_plane_body("ptA", "spA",
                                               regenerated_before=True))),
        ("claim_parameters_cs",
         "\n".join(claim_parameters_cs(template_key="generic_model"))),
    )


CORPUS_FAMILY = _corpus_family()
CORPUS_KHAC = _corpus_khac()
CORPUS_MANH = _corpus_manh()
CORPUS_TAT_CA = CORPUS_FAMILY + CORPUS_KHAC + CORPUS_MANH


def test_corpus_quet_du_ca_ba_ro_khong_rong():
    """Chốt số: 6 template x 5 bộ sinh + 2 khuôn = 32 chương trình family."""
    assert len(CORPUS_FAMILY) == len(SKETCH_KEYS) * len(ALL_FIVE) + 2 == 32
    assert CORPUS_KHAC and CORPUS_MANH


# -- 8.1 host giữ transaction trên `document` ----------------------------

@pytest.mark.parametrize("nhan,code", CORPUS_TAT_CA)
def test_khong_chuoi_nao_mo_transaction_tren_document_cua_host(nhan, code):
    """Bất biến 1 — mở thêm transaction trên `document` là InvalidOperationException.

    Đã đo ở BRD-017; chính vì nó mà MCP chạy chế độ rollback-only.
    """
    assert "new Transaction(document" not in code, nhan
    assert not re.search(r"new\s+Transaction\s*\(\s*document\b", code), nhan
    assert not re.search(r"\bdocument\s*\.\s*Close\s*\(", code), nhan


# -- 8.2 Regenerate TRONG transaction, TRƯỚC Commit ----------------------

@pytest.mark.parametrize("nhan,code", CORPUS_FAMILY)
def test_regenerate_luon_co_va_luon_truoc_commit(nhan, code):
    """Bất biến 3 — Regenerate() sau Commit() thì Revit ném InvalidOperationException."""
    assert "Regenerate" in code, nhan
    i_regen = code.index("fd.Regenerate();")
    i_commit = code.index("tx.Commit();")
    i_saveas = code.index("fd.SaveAs(")
    assert i_regen < i_commit < i_saveas, (
        f"{nhan}: Regenerate@{i_regen} phải TRƯỚC Commit@{i_commit}, "
        f"và Commit phải trước SaveAs@{i_saveas}")


@pytest.mark.parametrize("nhan,code", CORPUS_KHAC)
def test_probe_cung_regenerate_trong_transaction(nhan, code):
    """Probe không Commit (nó RollBack) — nhưng Regenerate vẫn phải nằm trong tx."""
    assert "Regenerate" in code, nhan
    assert "tx.Commit();" not in code, f"{nhan}: probe KHÔNG được Commit"
    assert code.index("fdoc.Regenerate();") < code.index("ptx.RollBack();"), nhan


# -- 8.3 định danh phải TIỀN ĐỊNH ----------------------------------------

@pytest.mark.parametrize("nhan,code", CORPUS_TAT_CA)
def test_khong_chuoi_nao_dung_guid_ngau_nhien(nhan, code):
    """Bất biến 2 — hai lần chạy phải so được với nhau thì mới lần ngược được."""
    assert "Guid.NewGuid" not in code, nhan
    assert not re.search(r"Guid\s*\.\s*NewGuid\s*\(", code), nhan


@pytest.mark.parametrize("nhan,code", CORPUS_FAMILY)
def test_moi_chuong_trinh_family_sinh_lai_ra_dung_chuoi_cu(nhan, code):
    """Không Guid ngẫu nhiên thì phải xác định lại được — kiểm bằng chính corpus."""
    assert dict(_corpus_family())[nhan] == code


# -- 8.4 dấu claim đọc được NGAY TRONG REVIT -----------------------------

@pytest.mark.parametrize("nhan,code", CORPUS_FAMILY)
def test_moi_family_deu_mang_dau_claim_f0_idea(nhan, code):
    assert CLAIM_LEVEL_PARAM in code, nhan
    assert CLAIM_STATEMENT_PARAM in code, nhan
    assert "F0_IDEA" in code, nhan


@pytest.mark.parametrize("nhan,code", CORPUS_FAMILY)
def test_khong_family_nao_tu_nang_muc_claim(nhan, code):
    """Trần claim BRD-036 là IDEA. Family đẹp và tham số hoá KHÔNG nâng mức claim."""
    for cao_hon in ("SCREENED", "NUMERICALLY_VERIFIED", "LAB_VALIDATED",
                    "PILOT_VALIDATED", "ENGINEERING_CANDIDATE"):
        assert cao_hon not in code, f"{nhan} phát mức claim '{cao_hon}'"


# -- 8.5 ASCII thuần + thân mã không dùng `return` -----------------------

@pytest.mark.parametrize("nhan,code", CORPUS_TAT_CA)
def test_moi_chuoi_deu_ascii_thuan(nhan, code):
    """Mã đi qua MCP và console cp1252 — một ký tự có dấu là một lần hỏng khó đọc."""
    code.encode("ascii")


@pytest.mark.parametrize("nhan,code", CORPUS_FAMILY)
def test_than_ma_khong_bao_gio_dung_return(nhan, code):
    """`return` giữa ``using (Transaction)`` bỏ qua catch -> bỏ ngỏ family document.

    Chỉ ``throw`` mới rơi đúng vào khối catch có ``fd.Close(false)``.
    """
    than = code[code.index("--- than ma do nguoi goi truyen vao ---"):
                code.index("--- het than ma ---")]
    assert "return" not in than, nhan


@pytest.mark.parametrize("nhan,code", CORPUS_FAMILY)
def test_moi_family_deu_dong_family_document_o_ca_hai_nhanh(nhan, code):
    assert code.count("fd.Close(false);") >= 2, (
        f"{nhan}: phải Close ở nhánh thành công VÀ trong khối catch")


# -- 8.6 probe được miễn dấu claim, và nói rõ VÌ SAO ---------------------

@pytest.mark.parametrize("nhan,code", CORPUS_KHAC)
def test_probe_khong_dan_dau_claim_vi_no_khong_sinh_family(nhan, code):
    """Miễn trừ CÓ LÝ DO, không phải bỏ sót.

    FLEX PROBE chỉ MỞ một ``.rfa`` có sẵn, đo, rồi RollBack. Nó không tạo ra
    family nào nên không có gì để dán nhãn; dán nhãn claim ở đây còn nguy hiểm
    hơn vì sẽ ghi đè nhãn của family gốc.
    """
    assert CLAIM_LEVEL_PARAM not in code, nhan
    assert "fd.SaveAs(" not in code and "fdoc.SaveAs(" not in code, nhan
    assert "RollBack" in code, nhan


# -- 8.7 ba cặp phép x template mà RFC-1.1.0 đo LÀ HỎNG ------------------

@pytest.mark.parametrize("op,key,dau_hieu", [
    ("NewExtrusion", "adaptive", "not permitted in this type of family"),
    ("NewReferencePoint", "generic_model", "FamilyContextException"),
    ("NewLoftForm", "generic_model", "Form"),
])
def test_ba_cap_da_do_la_hong_deu_raise_kem_loi_revit(op, key, dau_hieu):
    """Đúng ba cặp hợp đồng Pha 2 gọi đích danh, kiểm thẳng chứ không qua vòng khác."""
    with pytest.raises(UnsupportedInWorldError) as exc:
        require_operation(op, key)
    text = str(exc.value)
    assert "MEASURED_FAIL" in text
    assert dau_hieu in text
    assert CAPABILITY_DOC in text


def test_hai_the_gioi_3d_loai_tru_nhau_theo_ca_hai_chieu():
    """SKETCH và ADAPTIVE không giao nhau: mỗi bên chặn đúng bộ công cụ bên kia."""
    assert operation_status("NewExtrusion", "generic_model") is MeasuredStatus.MEASURED_OK
    assert operation_status("NewExtrusion", "adaptive") is MeasuredStatus.MEASURED_FAIL
    assert operation_status("NewReferencePoint", "adaptive") is MeasuredStatus.MEASURED_OK
    assert operation_status("NewReferencePoint", "generic_model") is MeasuredStatus.MEASURED_FAIL


# -- 8.8 bốn bộ sinh adaptive PHẢI còn chặn ------------------------------

BO_SINH_DANG_CHAN = (
    ("adaptive_two_point_member", lambda: adaptive_two_point_member(DAM, OUT_RFA)),
    ("adaptive_void", lambda: adaptive_void(DAM, OUT_RFA)),
    ("massing_loft_surface",
     lambda: massing_loft_surface([[(0, 0, 0), (1, 0, 0)],
                                   [(0, 0, 5), (1, 0, 5)]], OUT_RFA)),
    ("adaptive_four_point_panel", lambda: adaptive_four_point_panel()),
)


@pytest.mark.parametrize("ten,goi", BO_SINH_DANG_CHAN)
def test_bon_bo_sinh_adaptive_van_dang_chan(ten, goi):
    """Chặn là TRẠNG THÁI ĐƯỢC KIỂM, không phải một câu trong tài liệu.

    Ngày nào có người nới cổng mà chưa đo, test này đỏ TRƯỚC khi mã kịp chạy
    vào Revit.
    """
    with pytest.raises(RevitFamilyCapabilityError):
        goi()


# -- 8.9 biên của gói: __all__ và phân loại hàm công khai ----------------

def _bon_module():
    from bridge_evolution.revit_family import adaptive_family, csharp
    from bridge_evolution.revit_family import sketch_family, worlds
    return (worlds, csharp, sketch_family, adaptive_family)


def test_all_cua_goi_dung_bang_hop_bon_module_con():
    """Không thừa (rò rỉ nội bộ), không thiếu (bộ sinh mới quên phơi ra)."""
    hop = set()
    for mod in _bon_module():
        assert hasattr(mod, "__all__"), f"{mod.__name__} thiếu __all__"
        hop |= set(mod.__all__)
    assert set(rf.__all__) == hop


def test_all_khong_trung_lap_va_moi_ten_deu_resolve():
    assert len(rf.__all__) == len(set(rf.__all__)) == 80
    thieu = [ten for ten in rf.__all__ if not hasattr(rf, ten)]
    assert thieu == []


def test_khong_ro_ri_ten_private_ra_bien_goi():
    assert [t for t in rf.__all__ if t.startswith("_")] == []


#: Hàm công khai KHÔNG phát mã C# — tra cứu, cổng, đổi đơn vị, hạ tầng chuỗi.
HAM_KHONG_PHAT_MA = frozenset({
    "template_spec", "operation_spec", "world_of", "template_path",
    "template_exists", "operation_status", "require_operation",
    "require_operations", "templates_in_world", "operations_ok_in",
    "capability_table", "blocking_operations", "m_to_ft", "xyz", "cs_string",
})
#: Hàm phát ra CHƯƠNG TRÌNH C# hoàn chỉnh (phải có mặt trong corpus quét ngang).
HAM_PHAT_CHUONG_TRINH = frozenset({
    "family_scaffold", "guarded_family_scaffold", "arch_rib_segment",
    "tapered_pier_shaft", "revolved_member", "prismatic_member", "void_cut",
    "adaptive_flex_probe",
})
#: Hàm phát ra MẢNH thân mã (``list[str]``).
HAM_PHAT_MANH = frozenset({
    "claim_parameters_cs", "adaptive_two_point_spine_body",
    "adaptive_section_plane_body",
})
#: Hàm hiện RAISE theo thiết kế — chưa đo thì chưa phát mã.
HAM_DANG_CHAN = frozenset({
    "adaptive_two_point_member", "adaptive_void", "massing_loft_surface",
    "adaptive_four_point_panel",
})


def test_moi_ham_cong_khai_deu_duoc_phan_loai():
    """Thêm một bộ sinh mà quên xếp rổ -> test này đỏ.

    Đây là cái chốt giữ cho corpus quét ngang không mục ruỗng: bốn tập trên
    phải phủ ĐÚNG BẰNG tập hàm công khai, không thừa không thiếu.
    """
    cong_khai = {ten for ten in rf.__all__
                 if inspect.isfunction(getattr(rf, ten))}
    phan_loai = (HAM_KHONG_PHAT_MA | HAM_PHAT_CHUONG_TRINH
                 | HAM_PHAT_MANH | HAM_DANG_CHAN)
    assert cong_khai == phan_loai, (
        f"chưa xếp rổ: {sorted(cong_khai - phan_loai)}; "
        f"xếp rổ nhưng không còn công khai: {sorted(phan_loai - cong_khai)}")


def test_bon_ro_phan_loai_roi_nhau():
    ro = (HAM_KHONG_PHAT_MA, HAM_PHAT_CHUONG_TRINH, HAM_PHAT_MANH,
          HAM_DANG_CHAN)
    tong = sum(len(r) for r in ro)
    assert len(set().union(*ro)) == tong


def test_moi_ham_phat_chuong_trinh_deu_co_mat_trong_corpus():
    """Phân loại là một chuyện; CÓ BỊ QUÉT hay không là chuyện khác."""
    da_quet = {nhan.split("[")[0] for nhan, _ in CORPUS_FAMILY + CORPUS_KHAC}
    assert HAM_PHAT_CHUONG_TRINH <= da_quet
    da_quet_manh = {nhan for nhan, _ in CORPUS_MANH}
    assert HAM_PHAT_MANH <= da_quet_manh
