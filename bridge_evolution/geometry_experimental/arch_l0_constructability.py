"""Sàng lọc L0 chế tạo / vận chuyển / cẩu lắp / tiếp cận kiểm tra cho ĐỐT VÒM.

===========================================================================
GIỚI HẠN HIỆU LỰC — ĐỌC TRƯỚC KHI DÙNG (BRD-004, sandbox thực nghiệm)
===========================================================================
Module này CHỈ làm SỐ HỌC HÌNH HỌC mức L0 trên output của
:mod:`bridge_evolution.geometry_experimental.arch_geometry`:

  * chia chiều dài cung trục vòm cho số đốt để ước lượng chiều dài đốt;
  * nhân diện tích × chiều dài × khối lượng riêng để ước lượng khối lượng đốt;
  * so vài hiệu số cao độ / khoảng cách ngang với ngưỡng do NGƯỜI GỌI cung cấp.

Nó KHÔNG tính nội lực, KHÔNG tính ứng suất, KHÔNG tính ổn định, KHÔNG tính
chuyển vị, KHÔNG mô phỏng trình tự lắp. Runtime DYLIGHT không có solver nào
cho họ vòm (RCM-2.0.0: SOLVER_MIDAS_CIVIL, SOLVER_OPENSEESPY, GRILLAGE_3D,
STAGED_PRESTRESS_EFFECTS đều ABSENT) và module này không giả vờ có.

Mức claim của mọi kết quả: **F0 IDEA**. PASS ở đây chỉ có nghĩa "vài con số
hình học không mâu thuẫn với ngưỡng mà người gọi tự chịu trách nhiệm cung
cấp"; nó KHÔNG phải kết luận kỹ thuật về phương án và không nói gì về các
trạng thái lắp hẫng (dấu nội lực ngược, tiết diện thay đổi giữa chừng — xem
docstring của ``arch_geometry``).

NGUYÊN TẮC FAIL-CLOSED
  * KHÔNG hard-code ngưỡng nào trong code (chỉ có hằng toán học). Mọi ngưỡng
    đến từ ``logistics_profile``, mỗi ngưỡng là dict
    ``{"value": số | None, "provenance": str}``.
  * Thiếu ngưỡng (thiếu khoá, hoặc ``value = None``) → check đó trả trạng thái
    ``UNKNOWN_INPUT_MISSING`` và KHÔNG được đếm là PASS. ``all_known_pass``
    chỉ True khi không có FAIL VÀ không có UNKNOWN (thiếu dữ liệu không bao
    giờ được hiểu ngầm là đạt).
  * Ngưỡng CÓ giá trị nhưng phi vật lý (không phải số hữu hạn dương, hoặc
    thiếu provenance) → raise :class:`ArchGeometryError` — dữ liệu hỏng phải
    nổ ngay, không âm thầm bỏ qua, không tự sửa.

ĐƠN VỊ: mét cho chiều dài, m² cho diện tích, kg/m³ cho khối lượng riêng,
TẤN cho khối lượng ước tính. Module không tự đổi đơn vị hộ người gọi.
"""

from __future__ import annotations

import math

from .arch_geometry import ArchGeometryError, CLAIM_LEVEL

#: Nhãn cấp sàng lọc — chỉ hình học, không mở solver nào.
SCREENING_LEVEL = "L0_GEOMETRY_ONLY"

#: Ba trạng thái duy nhất của một check. Không có "WARN": ở mức IDEA một
#: nghi ngờ chưa đủ dữ liệu là UNKNOWN, không phải một PASS kèm chú thích.
STATUS_PASS = "PASS"
STATUS_FAIL = "FAIL"
STATUS_UNKNOWN = "UNKNOWN_INPUT_MISSING"

#: Các khoá geometry bắt buộc (đúng schema output của ``arch_geometry``).
REQUIRED_GEOMETRY_KEYS = (
    "axis_arc_length_m",
    "rise_m",
    "deck_level_m",
    "min_interior_column_height_m",
    "rib_count",
    "rib_transverse_offsets_m",
)

#: Các khoá ngưỡng mà logistics_profile CÓ THỂ cung cấp. Thiếu khoá nào thì
#: check tương ứng trả UNKNOWN_INPUT_MISSING chứ không dùng giá trị mặc định.
KNOWN_THRESHOLD_KEYS = (
    "max_transport_segment_length_m",
    "max_lift_piece_mass_t",
    "min_inspection_walkway_clearance_m",
    "min_spandrel_column_height_for_inspection_m",
    "min_rib_clear_gap_m",
    "max_cantilever_half_arch_segments",
)

__all__ = [
    "screen_constructability_l0",
    "SCREENING_LEVEL",
    "STATUS_PASS",
    "STATUS_FAIL",
    "STATUS_UNKNOWN",
    "REQUIRED_GEOMETRY_KEYS",
    "KNOWN_THRESHOLD_KEYS",
]


# ---------------------------------------------------------------------------
# Kiểm tra đầu vào (fail-closed)
# ---------------------------------------------------------------------------

def _finite_positive(value: object, name: str) -> float:
    """Số hữu hạn DƯƠNG; không ép kiểu chuỗi, không nhận bool."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ArchGeometryError(f"{name} phải là số thực, nhận được {value!r}")
    out = float(value)
    if not math.isfinite(out):
        raise ArchGeometryError(f"{name} phải hữu hạn, nhận được {out!r}")
    if out <= 0.0:
        raise ArchGeometryError(f"{name} phải dương, nhận được {out!r}")
    return out


def _finite_nonnegative(value: object, name: str) -> float:
    """Số hữu hạn KHÔNG ÂM (chiều cao cột có thể bằng 0 khi deck trùng đỉnh vòm)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ArchGeometryError(f"{name} phải là số thực, nhận được {value!r}")
    out = float(value)
    if not math.isfinite(out):
        raise ArchGeometryError(f"{name} phải hữu hạn, nhận được {out!r}")
    if out < 0.0:
        raise ArchGeometryError(f"{name} không được âm, nhận được {out!r}")
    return out


def _validate_geometry(geometry: object) -> dict:
    """Geometry phải là dict mang đủ khoá của ``arch_geometry`` — thiếu là raise."""
    if not isinstance(geometry, dict):
        raise ArchGeometryError(
            f"geometry phải là dict output của arch_geometry, nhận được {type(geometry).__name__}"
        )
    missing = [k for k in REQUIRED_GEOMETRY_KEYS if k not in geometry]
    if missing:
        raise ArchGeometryError(
            f"geometry thiếu khoá bắt buộc: {missing} — truyền nguyên dict do "
            "arch_geometry() trả về, không tự lắp dict tay."
        )
    _finite_positive(geometry["axis_arc_length_m"], "geometry['axis_arc_length_m']")
    _finite_positive(geometry["rise_m"], "geometry['rise_m']")
    _finite_positive(geometry["deck_level_m"], "geometry['deck_level_m']")
    _finite_nonnegative(
        geometry["min_interior_column_height_m"],
        "geometry['min_interior_column_height_m']",
    )
    rib_count = geometry["rib_count"]
    if rib_count is not None and (isinstance(rib_count, bool) or not isinstance(rib_count, int)):
        raise ArchGeometryError(
            f"geometry['rib_count'] phải là int hoặc None, nhận được {rib_count!r}"
        )
    return geometry


def _validate_segmentation(segmentation: object) -> dict:
    """Hợp thức hoá khối segmentation; trả về dict đã kiểm.

    Bắt buộc: ``segment_count_per_rib`` (int >= 2) và ``provenance`` khác rỗng.
    Số đốt LẺ KHÔNG raise ở đây — nó là một FAIL của check hợp long
    (ARCH-L0-03), vì đó là kết quả sàng lọc chứ không phải dữ liệu hỏng.
    Tuỳ chọn (None nếu chưa có): ``rib_section_area_m2``,
    ``rib_material_density_kg_m3``, ``rib_width_m`` — nếu CÓ giá trị thì phải
    là số hữu hạn dương.
    """
    if not isinstance(segmentation, dict):
        raise ArchGeometryError(
            f"segmentation phải là dict, nhận được {type(segmentation).__name__}"
        )
    if "segment_count_per_rib" not in segmentation:
        raise ArchGeometryError("segmentation thiếu khoá 'segment_count_per_rib'")
    count = segmentation["segment_count_per_rib"]
    if isinstance(count, bool) or not isinstance(count, int):
        raise ArchGeometryError(
            f"segment_count_per_rib phải là số nguyên, nhận được {count!r}"
        )
    if count < 2:
        raise ArchGeometryError(
            f"segment_count_per_rib phải >= 2 (một vòm không thể ít hơn 2 đốt "
            f"khi lắp từ hai phía), nhận được {count}"
        )
    prov = segmentation.get("provenance")
    if not prov:
        raise ArchGeometryError(
            "segmentation phải mang trường 'provenance' khác rỗng: phương án "
            "chia đốt là một quyết định của người gọi, không phải của module này."
        )
    out = {"segment_count_per_rib": count, "provenance": prov}
    for key in ("rib_section_area_m2", "rib_material_density_kg_m3", "rib_width_m"):
        value = segmentation.get(key)
        out[key] = None if value is None else _finite_positive(value, f"segmentation['{key}']")
    return out


def _threshold(
    profile: dict, key: str
) -> tuple[float | None, str | None, str | None]:
    """Đọc một ngưỡng từ logistics_profile.

    Trả về ``(value, provenance, missing_vi)``:
      * thiếu khoá hoặc value = None → ``(None, ..., lý_do_thiếu)`` — người gọi
        nhận UNKNOWN_INPUT_MISSING, module KHÔNG bịa giá trị mặc định;
      * value là số → phải hữu hạn dương và provenance phải là chuỗi khác rỗng,
        sai thì raise :class:`ArchGeometryError`.
    """
    if key not in profile:
        return None, None, f"logistics_profile thiếu khoá '{key}'"
    entry = profile[key]
    if not isinstance(entry, dict) or "value" not in entry:
        raise ArchGeometryError(
            f"logistics_profile['{key}'] phải là dict dạng "
            f"{{'value': ..., 'provenance': ...}}, nhận được {entry!r}"
        )
    value = entry["value"]
    if value is None:
        return None, None, (
            f"logistics_profile['{key}'].value = None — người gọi chưa chốt ngưỡng"
        )
    prov = entry.get("provenance")
    if not isinstance(prov, str) or not prov.strip():
        raise ArchGeometryError(
            f"logistics_profile['{key}'] có value nhưng provenance rỗng hoặc "
            "không phải chuỗi — mọi ngưỡng phải khai xuất xứ (hàng rào BRD-004)."
        )
    return _finite_positive(value, f"logistics_profile['{key}'].value"), prov, None


# ---------------------------------------------------------------------------
# Bản ghi check
# ---------------------------------------------------------------------------

def _check_record(
    check_id: str,
    title_vi: str,
    status: str,
    value: float | int | None,
    value_unit: str | None,
    limit: float | int | str | None,
    limit_unit: str | None,
    limit_provenance: str | None,
    message_vi: str,
    extra: dict | None = None,
) -> dict:
    """Một bản ghi check theo phong cách bản ghi vi phạm của production
    (rule_id/severity/message) nhưng cho L0 hình học họ vòm: dùng
    ``value``/``limit`` trung tính, không dùng các cặp từ mang nghĩa phân tích."""
    record: dict = {
        "check_id": check_id,
        "title_vi": title_vi,
        "status": status,
        "value": value,
        "value_unit": value_unit,
        "limit": limit,
        "limit_unit": limit_unit,
        "limit_provenance": limit_provenance,
        "message_vi": message_vi,
    }
    if extra:
        record.update(extra)
    return record


# ---------------------------------------------------------------------------
# Hàm public chính
# ---------------------------------------------------------------------------

def screen_constructability_l0(
    geometry: dict,
    logistics_profile: dict,
    segmentation: dict,
) -> dict:
    """Sàng lọc L0 (chỉ hình học) về chia đốt, vận chuyển, cẩu, tiếp cận kiểm tra.

    Tham số
    -------
    geometry:
        Dict do :func:`arch_geometry.arch_geometry` trả về (nguyên vẹn).
    logistics_profile:
        Dict ngưỡng của NGƯỜI GỌI; mỗi ngưỡng là
        ``{"value": số | None, "provenance": str}``. Các khoá được hiểu:
        xem :data:`KNOWN_THRESHOLD_KEYS`. Thiếu khoá / value None → check
        tương ứng trả ``UNKNOWN_INPUT_MISSING``. Module KHÔNG có ngưỡng mặc định.
    segmentation:
        ``{"segment_count_per_rib": int >= 2, "rib_section_area_m2": float|None,
        "rib_material_density_kg_m3": float|None, "rib_width_m": float|None,
        "provenance": ...}``. Số đốt nên CHẴN để hai nửa vòm lắp hẫng đối xứng
        và hợp long tại đỉnh; số LẺ không raise mà bị check ARCH-L0-03 đánh FAIL.

    Trả về
    ------
    Dict gồm ``claim_level="IDEA"``, ``screening_level``, danh sách ``checks``
    (mỗi bản ghi có check_id/title_vi/status/value/limit/limit_provenance/
    message_vi), ``status_counts`` và ba cờ ``any_fail`` / ``any_unknown`` /
    ``all_known_pass``. QUY ƯỚC FAIL-CLOSED: ``all_known_pass`` chỉ True khi
    KHÔNG có FAIL và KHÔNG có UNKNOWN — một check thiếu dữ liệu làm cả bộ
    sàng lọc mất quyền tuyên bố "đã sàng xong".

    Mọi phép tính trong đây là số học hình học; không phép nào là nội lực,
    ứng suất hay ổn định, và PASS không nâng mức claim lên trên IDEA.
    """
    geom = _validate_geometry(geometry)
    seg = _validate_segmentation(segmentation)
    if not isinstance(logistics_profile, dict):
        raise ArchGeometryError(
            f"logistics_profile phải là dict, nhận được {type(logistics_profile).__name__}"
        )

    count = seg["segment_count_per_rib"]
    arc_m = float(geom["axis_arc_length_m"])
    segment_length_m = arc_m / count

    checks: list[dict] = []

    # -- ARCH-L0-01 · FAB/TRANSPORT: chiều dài đốt so với ngưỡng vận chuyển --
    fab_note = (
        "Xấp xỉ L0: chiều dài đốt lấy bằng chiều dài cung TRUNG BÌNH "
        "(axis_arc_length_m / segment_count_per_rib). Đốt thật dài khác nhau "
        "theo độ cong — đốt gần chân vòm cong gắt hơn — nên ngưỡng của người "
        "gọi phải chừa dung sai cho điều đó."
    )
    limit, prov, missing = _threshold(logistics_profile, "max_transport_segment_length_m")
    if missing is not None:
        status, msg = STATUS_UNKNOWN, f"Không so được: {missing}. {fab_note}"
    elif segment_length_m <= limit:
        status = STATUS_PASS
        msg = (
            f"Chiều dài đốt trung bình {segment_length_m:.2f} m nằm trong ngưỡng "
            f"vận chuyển {limit} m do người gọi cung cấp. {fab_note}"
        )
    else:
        status = STATUS_FAIL
        msg = (
            f"Chiều dài đốt trung bình {segment_length_m:.2f} m vượt ngưỡng vận "
            f"chuyển {limit} m do người gọi cung cấp — tăng số đốt hoặc đổi "
            f"phương án vận chuyển. {fab_note}"
        )
    checks.append(_check_record(
        "ARCH-L0-01", "Chế tạo/vận chuyển: chiều dài đốt vòm", status,
        segment_length_m, "m", limit, "m", prov, msg,
    ))

    # -- ARCH-L0-02 · LIFT: khối lượng ước tính mỗi đốt so với ngưỡng cẩu -----
    lift_note = (
        "Ước tính SỐ HỌC L0: diện tích tiết diện × chiều dài đốt trung bình × "
        "khối lượng riêng ÷ 1000 (tấn). KHÔNG phải kết quả solver, chưa kể mối "
        "nối/vách/phụ kiện; với CFST, diện tích và khối lượng riêng phải ứng "
        "đúng GIAI ĐOẠN cẩu (ống rỗng khi lắp, bê tông nhồi sau)."
    )
    area = seg["rib_section_area_m2"]
    density = seg["rib_material_density_kg_m3"]
    limit, prov, missing = _threshold(logistics_profile, "max_lift_piece_mass_t")
    estimate_t: float | None = None
    missing_inputs = [
        name for name, val in (
            ("segmentation['rib_section_area_m2']", area),
            ("segmentation['rib_material_density_kg_m3']", density),
        ) if val is None
    ]
    if missing_inputs:
        status = STATUS_UNKNOWN
        msg = (
            f"Không ước tính được khối lượng đốt: thiếu {', '.join(missing_inputs)}. "
            f"{lift_note}"
        )
    else:
        estimate_t = area * segment_length_m * density / 1000.0
        if missing is not None:
            status, msg = STATUS_UNKNOWN, (
                f"Ước tính được {estimate_t:.1f} t/đốt nhưng không so được: "
                f"{missing}. {lift_note}"
            )
        elif estimate_t <= limit:
            status = STATUS_PASS
            msg = (
                f"Ước tính {estimate_t:.1f} t/đốt nằm trong ngưỡng cẩu {limit} t "
                f"do người gọi cung cấp. {lift_note}"
            )
        else:
            status = STATUS_FAIL
            msg = (
                f"Ước tính {estimate_t:.1f} t/đốt vượt ngưỡng cẩu {limit} t do "
                f"người gọi cung cấp — chia đốt nhỏ hơn hoặc đổi thiết bị. {lift_note}"
            )
    checks.append(_check_record(
        "ARCH-L0-02", "Cẩu lắp: khối lượng ước tính mỗi đốt (số học L0)", status,
        estimate_t, "t", limit, "t", prov, msg,
        extra={"segment_mass_t_estimate_l0": estimate_t},
    ))

    # -- ARCH-L0-03 · ERECTION: số đốt chẵn để hợp long đối xứng tại đỉnh -----
    even_prov = (
        "Ràng buộc TOPO của sơ đồ lắp hẫng đối xứng hai nửa vòm với tuyến hợp "
        "long tại đỉnh (BRD-004/INC-004) — không phải ngưỡng số của người gọi."
    )
    if count % 2 == 0:
        status = STATUS_PASS
        msg = (
            f"segment_count_per_rib = {count} chẵn: mỗi nửa vòm {count // 2} đốt, "
            "đỉnh vòm là mặt hợp long đối xứng."
        )
    else:
        status = STATUS_FAIL
        msg = (
            f"segment_count_per_rib = {count} LẺ: hai nửa vòm không đối xứng qua "
            "đỉnh nên không có mặt hợp long đối xứng tại đỉnh — dùng số đốt chẵn."
        )
    checks.append(_check_record(
        "ARCH-L0-03", "Lắp dựng: số đốt chẵn (hợp long tại đỉnh)", status,
        count, "đốt", "số chẵn (chia hết cho 2)", None, even_prov, msg,
    ))

    # -- ARCH-L0-04 · ERECTION: số đốt mỗi nửa vòm khi lắp hẫng ---------------
    half_count = count / 2.0
    cant_note = (
        "Đếm hình học thuần tuý: số đốt mỗi nửa vòm = segment_count_per_rib / 2. "
        "KHÔNG kiểm được nội lực hay ổn định của consol lắp hẫng — runtime "
        "không có solver cho vòm; ngưỡng số đốt là kinh nghiệm người gọi tự chịu."
    )
    limit, prov, missing = _threshold(logistics_profile, "max_cantilever_half_arch_segments")
    if missing is not None:
        status, msg = STATUS_UNKNOWN, f"Không so được: {missing}. {cant_note}"
    elif half_count <= limit:
        status = STATUS_PASS
        msg = (
            f"{half_count:g} đốt mỗi nửa vòm nằm trong giới hạn {limit:g} đốt do "
            f"người gọi cung cấp. {cant_note}"
        )
    else:
        status = STATUS_FAIL
        msg = (
            f"{half_count:g} đốt mỗi nửa vòm vượt giới hạn {limit:g} đốt do người "
            f"gọi cung cấp — giảm số đốt, tăng chiều dài đốt (kiểm lại ARCH-L0-01) "
            f"hoặc đổi sơ đồ lắp. {cant_note}"
        )
    checks.append(_check_record(
        "ARCH-L0-04", "Lắp dựng: số đốt mỗi nửa vòm khi lắp hẫng", status,
        half_count, "đốt/nửa vòm", limit, "đốt", prov, msg,
    ))

    # -- ARCH-L0-05 · INSPECTION: khe hở đứng đỉnh vòm ↔ đáy mặt cầu ----------
    clearance_m = float(geom["deck_level_m"]) - float(geom["rise_m"])
    insp_note = (
        "Xấp xỉ L0: khe hở tính giữa cao độ TRỤC vòm tại đỉnh và cao độ mặt cầu "
        "danh nghĩa; chưa trừ nửa chiều cao tiết diện sườn lẫn chiều dày hệ mặt "
        "cầu — người gọi phải phản ánh các bề dày đó trong ngưỡng của mình."
    )
    limit, prov, missing = _threshold(
        logistics_profile, "min_inspection_walkway_clearance_m"
    )
    if missing is not None:
        status, msg = STATUS_UNKNOWN, f"Không so được: {missing}. {insp_note}"
    elif clearance_m >= limit:
        status = STATUS_PASS
        msg = (
            f"Khe hở đỉnh vòm–mặt cầu {clearance_m:.2f} m đạt ngưỡng lối kiểm tra "
            f"{limit} m do người gọi cung cấp. {insp_note}"
        )
    else:
        status = STATUS_FAIL
        msg = (
            f"Khe hở đỉnh vòm–mặt cầu {clearance_m:.2f} m nhỏ hơn ngưỡng lối kiểm "
            f"tra {limit} m do người gọi cung cấp — nâng deck_level_m, hạ rise_m "
            f"hoặc chấp nhận phương án tiếp cận khác (quyết định thiết kế). {insp_note}"
        )
    checks.append(_check_record(
        "ARCH-L0-05", "Kiểm tra: khe hở đứng đỉnh vòm tới đáy mặt cầu", status,
        clearance_m, "m", limit, "m", prov, msg,
    ))

    # -- ARCH-L0-06 · INSPECTION: chiều cao cột khoang vòm thấp nhất ----------
    min_col_m = float(geom["min_interior_column_height_m"])
    limit, prov, missing = _threshold(
        logistics_profile, "min_spandrel_column_height_for_inspection_m"
    )
    if missing is not None:
        status, msg = STATUS_UNKNOWN, f"Không so được: {missing}."
    elif min_col_m >= limit:
        status = STATUS_PASS
        msg = (
            f"Cột khoang vòm thấp nhất {min_col_m:.2f} m đạt ngưỡng tiếp cận "
            f"kiểm tra {limit} m do người gọi cung cấp."
        )
    else:
        status = STATUS_FAIL
        msg = (
            f"Cột khoang vòm thấp nhất {min_col_m:.2f} m nhỏ hơn ngưỡng tiếp cận "
            f"kiểm tra {limit} m do người gọi cung cấp. Gợi ý khớp notes_vi của "
            "arch_geometry: vùng gần chân vòm nên là TƯỜNG KHOANG VÒM ĐẶC thay "
            "cho cột quá ngắn (cột ngắn còn hút lực ngang không tương xứng) — "
            "đây là quyết định thiết kế, không phải phép tính."
        )
    checks.append(_check_record(
        "ARCH-L0-06", "Kiểm tra: chiều cao cột khoang vòm thấp nhất", status,
        min_col_m, "m", limit, "m", prov, msg,
    ))

    # -- ARCH-L0-07 · INSPECTION: khe ngang thông thuỷ giữa hai sườn vòm ------
    rib_count = geom["rib_count"]
    if rib_count is None:
        checks.append(_check_record(
            "ARCH-L0-07", "Kiểm tra: khe ngang thông thuỷ giữa các sườn vòm",
            STATUS_UNKNOWN, None, "m", None, "m", None,
            "Geometry không mang thông tin sườn (rib_count = None — arch_geometry "
            "được gọi không có deck_width_m) nên không dựng được khe ngang. "
            "Gọi lại arch_geometry với deck_width_m và rib_count.",
        ))
    elif rib_count >= 2:
        offsets = geom["rib_transverse_offsets_m"]
        if (not isinstance(offsets, list) or len(offsets) != rib_count
                or not all(isinstance(z, (int, float)) and not isinstance(z, bool)
                           and math.isfinite(float(z)) for z in offsets)):
            raise ArchGeometryError(
                f"geometry['rib_transverse_offsets_m'] phải là list {rib_count} "
                f"số hữu hạn, nhận được {offsets!r}"
            )
        ordered = sorted(float(z) for z in offsets)
        centre_gap_m = min(b - a for a, b in zip(ordered, ordered[1:]))
        rib_width = seg["rib_width_m"]
        limit, prov, missing = _threshold(logistics_profile, "min_rib_clear_gap_m")
        clear_gap_m: float | None = None
        if rib_width is None:
            status = STATUS_UNKNOWN
            msg = (
                f"Khoảng cách TIM–TIM hai sườn kề nhau là {centre_gap_m:.2f} m "
                "nhưng thiếu segmentation['rib_width_m'] nên không trừ được bề "
                "rộng sườn — khe thông thuỷ chưa xác định."
            )
        else:
            clear_gap_m = centre_gap_m - rib_width
            if missing is not None:
                status, msg = STATUS_UNKNOWN, (
                    f"Khe thông thuỷ ước tính {clear_gap_m:.2f} m nhưng không so "
                    f"được: {missing}."
                )
            elif clear_gap_m >= limit:
                status = STATUS_PASS
                msg = (
                    f"Khe ngang thông thuỷ giữa hai sườn {clear_gap_m:.2f} m đạt "
                    f"ngưỡng tiếp cận {limit} m do người gọi cung cấp."
                )
            else:
                status = STATUS_FAIL
                extra_overlap = (
                    " (khe <= 0: hai sườn chồng lên nhau — cấu hình phi vật lý)"
                    if clear_gap_m <= 0.0 else ""
                )
                msg = (
                    f"Khe ngang thông thuỷ giữa hai sườn {clear_gap_m:.2f} m nhỏ "
                    f"hơn ngưỡng tiếp cận {limit} m do người gọi cung cấp"
                    f"{extra_overlap} — nới khoảng cách sườn (giảm rib_edge_inset_m "
                    f"hoặc tăng deck_width_m) hoặc thu hẹp tiết diện sườn."
                )
        checks.append(_check_record(
            "ARCH-L0-07", "Kiểm tra: khe ngang thông thuỷ giữa các sườn vòm",
            status, clear_gap_m, "m", limit, "m", prov, msg,
        ))
    # rib_count == 1: một sườn duy nhất, không tồn tại khe giữa hai sườn —
    # check không áp dụng nên KHÔNG phát sinh bản ghi (không phải PASS ngầm).

    # -- Tổng hợp -------------------------------------------------------------
    status_counts = {STATUS_PASS: 0, STATUS_FAIL: 0, STATUS_UNKNOWN: 0}
    for record in checks:
        status_counts[record["status"]] += 1
    any_fail = status_counts[STATUS_FAIL] > 0
    any_unknown = status_counts[STATUS_UNKNOWN] > 0
    all_known_pass = (not any_fail) and (not any_unknown) and bool(checks)

    lineage = geom.get("lineage")
    geometry_hash = lineage.get("geometry_hash") if isinstance(lineage, dict) else None

    return {
        "claim_level": CLAIM_LEVEL,
        "screening_level": SCREENING_LEVEL,
        "runtime_can_evaluate_this_family": False,
        "statement_vi": (
            "PASS ở sàng lọc L0 này KHÔNG làm họ kết cấu dùng được: đây chỉ là "
            "số học hình học mức F0 IDEA. Mọi ngưỡng do người gọi cung cấp kèm "
            "provenance và người gọi tự chịu trách nhiệm về chúng. Không kiểm "
            "ổn định, không kiểm nội lực, không mô phỏng trình tự lắp. "
            "all_known_pass chỉ True khi không có FAIL và không có UNKNOWN "
            "(fail-closed: thiếu dữ liệu không bao giờ được hiểu là đạt)."
        ),
        "geometry_hash": geometry_hash,
        "construction_stage_id": geom.get("construction_stage_id"),
        "segment_count_per_rib": count,
        "segmentation_provenance": seg["provenance"],
        "checks": checks,
        "status_counts": status_counts,
        "any_fail": any_fail,
        "any_unknown": any_unknown,
        "all_known_pass": all_known_pass,
    }
