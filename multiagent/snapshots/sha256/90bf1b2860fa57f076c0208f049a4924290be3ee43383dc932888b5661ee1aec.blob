"""Tổng hợp tuổi thọ khai thác (BRD-026).

Tuổi thọ cấu kiện bê tông cốt thép theo mô hình hai giai đoạn chuẩn:

    t_service = t_initiation + t_propagation

  * t_initiation: carbonat/clorua chạm cốt thép (carbonation.py / chloride.py)
  * t_propagation: từ khi ăn mòn khởi phát đến khi đạt giới hạn sử dụng
    (nứt bong, mất tiết diện tới hạn). Sàng lọc: hằng số theo mức phơi —
    carbonat lan chậm (bê tông đậm đặc, ăn mòn đồng đều): 8 năm mặc định;
    clorua lan nhanh (ăn mòn cục bộ pitting): 4 năm. Trị số dẫn nguồn dải
    công bố 2–15 năm (fib Bulletin 34 §6; DuraCrete §3.4) — phải hiệu chỉnh
    theo quan trắc thật khi có (G6).

Còn lại (remaining life) = t_service − tuổi hiện tại, có thể hiệu chỉnh theo
condition state kiểm tra thực (1 tốt → hệ số 1.0; 4 xấu → nhân hệ số <1 vì
khấu hao thực nhanh hơn mô hình).
"""
from __future__ import annotations

import math

from .carbonation import carbonation_initiation_years
from .chloride import chloride_initiation_years

__all__ = ["propagation_years", "service_life_years", "remaining_service_life",
           "CONDITION_STATE_FACTORS"]

#: Số năm lan truyền mặc định (sàng lọc, dẫn nguồn dải fib Bulletin 34 §6).
PROPAGATION_DEFAULTS = {"carbonation": 8.0, "chloride": 4.0}

#: Hệ số hiệu chỉnh remaining life theo condition state AASHTO element
#: inspection (1 tốt … 4 xấu). Trị sàng lọc do lab tự định mức, ghi rõ là
#: HIỆU CHỈNH KINH NGHIỆM — không phải chuẩn chính thức.
CONDITION_STATE_FACTORS = {1: 1.0, 2: 0.9, 3: 0.7, 4: 0.5}


def propagation_years(mechanism: str = "carbonation") -> float:
    """Số năm lan truyền mặc định; mechanism lạ raise ValueError."""
    if mechanism not in PROPAGATION_DEFAULTS:
        raise ValueError(f"mechanism lạ: {mechanism!r}; cho phép: "
                         f"{sorted(PROPAGATION_DEFAULTS)}")
    return PROPAGATION_DEFAULTS[mechanism]


def service_life_years(
    cover_mm: float,
    mechanism: str = "carbonation",
    fck_MPa: float = 30.0,
    rh_percent: float = 70.0,
    exposure: str = "outdoor_sheltered",
    cs_percent: float = 4.0,
    ccrit_percent: float = 0.6,
    measured: dict | None = None,
) -> float:
    """Tuổi thọ khai thác ước lượng (năm) = initiation + propagation.

    mechanism="carbonation": dùng (cover, fck, rh, exposure).
    mechanism="chloride": dùng (cover, cs, ccrit).

    ``measured``: dict từ ``exposure_data.load_exposure_data()["measured"]`` —
    giá trị đo được ghi đè trị sàng lọc (G6). ``measured_k`` áp cho
    carbonation; các khóa clorua áp cho chloride.
    """
    if mechanism == "carbonation":
        measured_k = measured.get("carbonation_k_mm_sqrt_year") if measured else None
        t_init = carbonation_initiation_years(
            cover_mm, fck_MPa, rh_percent, exposure, measured_k=measured_k)
    elif mechanism == "chloride":
        params = {"cover_mm": cover_mm, "cs_percent": cs_percent,
                  "ccrit_percent": ccrit_percent}
        if measured:
            chl = measured.get("chloride") or {}
            for key in ("cs_percent", "ccrit_percent"):
                if key in chl:
                    params[key] = float(chl[key])
            if "d_ref_m2s" in chl:
                params["d_ref_m2s"] = float(chl["d_ref_m2s"])
            if "m" in chl:
                params["m"] = float(chl["m"])
        t_init = chloride_initiation_years(**params)
    else:
        raise ValueError(f"mechanism lạ: {mechanism!r}")
    return t_init + propagation_years(mechanism)


def remaining_service_life(
    current_age_years: float,
    cover_mm: float,
    mechanism: str = "carbonation",
    condition_state: int = 1,
    measured: dict | None = None,
    **kwargs,
) -> dict:
    """Tuổi thọ còn lại (năm) + nhãn advisory. KHÔNG PASS/FAIL.

    condition_state (AASHTO 1-4) hiệu chỉnh mô hình theo quan sát thực:
    state xấu hơn → hệ số < 1 trên tuổi thọ lý thuyết. Kết quả luôn kèm
    ``advisory = True``, ghi chú mức tin cậy và ``data_provenance``.
    """
    if current_age_years < 0:
        raise ValueError("current_age_years không âm")
    if condition_state not in CONDITION_STATE_FACTORS:
        raise ValueError(f"condition_state phải trong {sorted(CONDITION_STATE_FACTORS)}")

    provenance = "SCREENING_DEFAULT"
    if measured:
        provenance = "MEASURED"
        if "rh_percent" in measured:
            kwargs["rh_percent"] = float(measured["rh_percent"])
    theoretical = service_life_years(cover_mm, mechanism, measured=measured, **kwargs)
    factor = CONDITION_STATE_FACTORS[condition_state]
    adjusted = theoretical * factor
    remaining = max(0.0, adjusted - current_age_years)
    return {
        "mechanism": mechanism,
        "theoretical_life_years": round(theoretical, 1),
        "condition_state": condition_state,
        "condition_factor": factor,
        "adjusted_life_years": round(adjusted, 1),
        "current_age_years": round(float(current_age_years), 1),
        "remaining_life_years": round(remaining, 1),
        "data_provenance": provenance,
        "advisory": True,
        "note": "Ước lượng sàng lọc từ mô hình khấu hao — không thay thế "
                "kiểm định hiện trường; hiệu chỉnh theo đo đạc G6 khi có.",
    }
