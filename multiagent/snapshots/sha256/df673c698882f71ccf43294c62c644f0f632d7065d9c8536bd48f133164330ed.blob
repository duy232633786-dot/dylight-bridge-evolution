"""Xâm thực clorua — Fick 2 với D giảm theo tuổi (BRD-026).

Mô hình DuraCrete/fib Bulletin 34 (không phần tử hữu hạn — dạng đóng):

    C(x, t) = Cs · [1 − erf( x / (2·√(D_app(t)·t)) )]

    D_app(t) = D_ref · (t_ref / t)^m      khi t ≤ t_c (giai đoạn giảm theo tuổi)
    D_app(t) = D_ref · (t_ref / t_c)^m    khi t > t_c (ổn định)

Nguồn:
  * Nghiệm Fick bán vô hạn với biên C=Cs hằng số — Crank 1975, chuẩn trong
    DuraCrete (Brite/EuRam 1998) và fib Bulletin 34 §5.
  * D_app giảm theo tuổi với mũ m: DuraCrete khuyến nghị m ≈ 0.30 (PC thường)
    đến 0.45 (tro bay/silica); t_c ≈ 25–30 năm. Chọn mặc định m=0.30, t_c=25
    — bảo thủ cho bê tông PC.
  * Cs theo mức phơi (% khối lượng chất kết dính): splash 3.0–5.0, tidal
    2.0–3.0, khí quyển ven biển 0.5–1.0 (fib Bulletin 34 bảng 5.2-2 dạng
    định lượng; chọn trị giữa dải làm mặc định sàng lọc).
  * C_crit ≈ 0.4–1.0 % khối kết dính (thép thường, có oxy); mặc định 0.6.

t_initiate = thời điểm C(cover, t) = C_crit — giải bằng chia đôi vì D phụ
thuộc t (không có dạng đóng). Hàm C theo t đơn điệu tăng về Cs nên chia đôi
chắc chắn hội tụ.
"""
from __future__ import annotations

import math

__all__ = ["chloride_concentration", "chloride_initiation_years",
           "CHLORIDE_SURFACE_CONCENTRATIONS"]

#: Cs mặc định (% khối chất kết dính) theo mức phơi — fib Bulletin 34 bảng
#: 5.2-2 (dải), chọn trị giữa làm mặc định sàng lọc.
CHLORIDE_SURFACE_CONCENTRATIONS = {
    "splash": 4.0,
    "tidal": 2.5,
    "atmospheric_marine": 0.75,
    "deicing_salt": 1.0,   # vùng rắc muối chống băng, xịt xa xe chạy
}

_M_DEFAULT = 0.30          # DuraCrete: PC thường 0.30, pozzolan 0.40–0.45
_T_C_YEARS = 25.0          # mốc D ổn định
_D_REF_M2_S = 12.0e-12     # D_ref ở t_ref=28 ngày, bê tông PC chất lượng cầu
_T_REF_DAYS = 28.0


def _d_app(d_ref_m2s: float, m: float, t_years: float) -> float:
    if t_years * 365.25 <= _T_REF_DAYS:
        return d_ref_m2s
    ratio = min(t_years, _T_C_YEARS) / (_T_REF_DAYS / 365.25)
    return d_ref_m2s * (1.0 / ratio) ** m


def chloride_concentration(
    depth_mm: float,
    t_years: float,
    cs_percent: float,
    d_ref_m2s: float = _D_REF_M2_S,
    m: float = _M_DEFAULT,
) -> float:
    """Nồng độ clorua [% khối kết dính] tại độ sâu depth_mm sau t_years năm.

    Đơn điệu tăng theo t (tiệm cận Cs) và giảm theo depth — tính chất được
    test khóa lại. t_years <= 0 trả 0.
    """
    if depth_mm < 0:
        raise ValueError("depth_mm không âm")
    if t_years <= 0:
        return 0.0
    d = _d_app(d_ref_m2s, m, t_years)
    # đổi: depth mm → m; t năm → giây
    x_m = depth_mm / 1000.0
    t_s = t_years * 365.25 * 86400.0
    arg = x_m / (2.0 * math.sqrt(d * t_s))
    return cs_percent * (1.0 - math.erf(arg))


def chloride_initiation_years(
    cover_mm: float,
    cs_percent: float,
    ccrit_percent: float = 0.6,
    d_ref_m2s: float = _D_REF_M2_S,
    m: float = _M_DEFAULT,
) -> float:
    """Số năm đến khi C(cover, t) = C_crit — chia đôi trên [1e-3, 500] năm.

    C theo t đơn điệu tăng (chứng minh: đạo hàm d(C)/dt > 0 vì cả D_app·t
    tăng theo t khi m ≥ 0) nên chia đôi hội tụ chắc chắn. Trả None-đại-diện
    500 năm nếu ngay cả 500 năm chưa tới ngưỡng (vùng rất an toàn).
    """
    if cover_mm <= 0:
        raise ValueError("cover_mm phải dương")
    if not (0 < ccrit_percent < cs_percent):
        raise ValueError("cần 0 < C_crit < Cs để có điểm khởi phát hữu hạn")

    def excess(t: float) -> float:
        return chloride_concentration(cover_mm, t, cs_percent, d_ref_m2s, m) - ccrit_percent

    if excess(500.0) < 0:
        return 500.0
    lo, hi = 1e-3, 500.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if excess(mid) < 0:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)
