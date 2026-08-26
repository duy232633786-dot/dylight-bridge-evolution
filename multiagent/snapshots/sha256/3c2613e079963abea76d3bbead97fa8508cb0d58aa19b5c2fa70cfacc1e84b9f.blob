"""Kế hoạch kiểm tra-bảo trì từ tốc độ khấu hao (BRD-026).

Nguyên tắc sàng lọc (ADVISORY, không phải kế hoạch thi công):
  * Kiểm tra chi tiết ĐẦU TIÊN trước khi mô hình dự báo khấu hao chạm cốt
    thép — mặc định tại min(10 năm, 0.5·t_initiate): đủ sớm để bắt lệch mô
    hình, không dày quá tốn kém.
  * Chu kỳ lặp: co lại khi tiến gần mốc khởi phát —
        interval(t) = clamp(0.2 · (t_initiate − t), interval_min, interval_max)
    càng gần t_initiate chu kỳ càng ngắn.
  * LCC-lite chọn chu kỳ: tổng PV chi phí kiểm tra + rủi ro bỏ lỡ (chi phí
    sửa tăng khi phát hiện muộn, mô hình hóa tuyến tính theo chu kỳ). Hàm
    mục tiêu minh bạch để reviewer chấm được — không tối ưu hộ đen.

Mọi đầu ra kèm ``advisory: True``.
"""
from __future__ import annotations

__all__ = ["inspection_plan", "optimal_inspection_interval"]

_INTERVAL_MIN_YEARS = 2.0
_INTERVAL_MAX_YEARS = 10.0


def inspection_plan(
    t_initiate_years: float,
    design_life_years: float = 100.0,
    current_age_years: float = 0.0,
) -> dict:
    """Danh sách mốc kiểm tra đề xuất đến hết tuổi thọ thiết kế.

    Mốc đầu = min(10, 0.5·t_initiate); chu kỳ sau co theo khoảng cách tới
    t_initiate (công thức ở docstring module). Trả dict kèm advisory.
    """
    if t_initiate_years <= 0:
        raise ValueError("t_initiate_years phải dương")
    if design_life_years <= 0:
        raise ValueError("design_life_years phải dương")
    if current_age_years < 0:
        raise ValueError("current_age_years không âm")

    first = min(_INTERVAL_MAX_YEARS, 0.5 * t_initiate_years)
    schedule: list[float] = []
    t = first
    while t <= design_life_years + 1e-9:
        if t >= current_age_years - 1e-9:
            schedule.append(round(t, 1))
        remaining = t_initiate_years - t
        if remaining <= 0:
            # Đã qua mốc khởi phát: chu kỳ tối thiểu (giai đoạn lan truyền).
            interval = _INTERVAL_MIN_YEARS
        else:
            interval = min(_INTERVAL_MAX_YEARS,
                           max(_INTERVAL_MIN_YEARS, 0.2 * remaining))
        t += interval

    return {
        "first_inspection_year": round(first, 1),
        "t_initiate_years": round(t_initiate_years, 1),
        "inspection_years": schedule,
        "advisory": True,
        "note": "Kế hoạch đề xuất từ mô hình sàng lọc — điều chỉnh theo "
                "quy định quan trắc của chủ đầu tư/cơ quan quản lý.",
    }


def optimal_inspection_interval(
    t_initiate_years: float,
    cost_inspection: float,
    cost_late_detection: float,
    discount_rate: float = 0.03,
    design_life_years: float = 100.0,
) -> dict:
    """Chọn chu kỳ kiểm tra minimizing LCC-lite trên các candidate 2–10 năm.

    Mô hình chi phí (minh bạch, không hộ đen):
        PV = Σ [C_ins/(1+r)^t] + C_late · P_miss(t)
        P_miss(t) ước lượng tuyến tính: phần đời sau t_initiate, xác suất
        phát hiện muộn một chu kỳ ∝ interval/t_initiate (càng thưa càng
        dễ lỡ). Đây là xấp xỉ sàng lọc có khai báo, không phải mô hình rủi ro
        chính thống.
    """
    if t_initiate_years <= 0 or cost_inspection < 0 or cost_late_detection < 0:
        raise ValueError("đầu vào chi phí/t_initiate không hợp lệ")
    if not (0 <= discount_rate < 0.5):
        raise ValueError("discount_rate phải trong [0, 0.5)")

    best = None
    candidates = []
    interval = _INTERVAL_MIN_YEARS
    while interval <= _INTERVAL_MAX_YEARS + 1e-9:
        pv_cost = 0.0
        t = interval
        while t <= design_life_years + 1e-9:
            pv = cost_inspection / (1.0 + discount_rate) ** t
            if t > t_initiate_years:
                p_miss = min(1.0, interval / t_initiate_years)
                pv += cost_late_detection * p_miss / (1.0 + discount_rate) ** t
            pv_cost += pv
            t += interval
        candidates.append({"interval_years": round(interval, 1),
                           "pv_cost": round(pv_cost, 1)})
        if best is None or pv_cost < best["pv_cost"]:
            best = candidates[-1]
        interval += 1.0

    return {
        "optimal_interval_years": best["interval_years"],
        "min_pv_cost": best["pv_cost"],
        "candidates": candidates,
        "advisory": True,
        "note": "LCC-lite sàng lọc với giả thiết tuyến tính P_miss — chỉ dùng "
                "so sánh tương đối giữa các chu kỳ, không phải dự toán chi phí.",
    }
