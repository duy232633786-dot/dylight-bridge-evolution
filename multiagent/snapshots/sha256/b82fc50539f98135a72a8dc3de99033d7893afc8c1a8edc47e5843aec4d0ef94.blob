"""Mỏi — đường S-N và thiệt hại Miner (BRD-026).

Mô hình:
    log N = log A − m · log Δσ        (S-N lũy thừa, N chu kỳ tới phá)
    D = Σ n_i / N_i(Δσ_i)             (Miner 1945 — giả thiết tuyến tính)

Nguồn:
  * Dạng S-N và bảng detail category (log A = log(2·10^6 · Δσ_C^m / Δσ_C)
    …): EN 1993-1-9 §7.1 với m=3 giai đoạn 5·10^6 chu kỳ đầu và m=5 giai
    đoạn sau (chọn 1 đoạn m=3 cho sàng lọc — bảo thủ ở dải Δσ thấp hơn cắt
    CAFL); AASHTO LRFD §6.6 cùng họ đường thẳng log-log.
  * Detail category Δσ_C mặc định 71 MPa (mối nối gắn kèm — chi tiết bất
    lợi phổ biến cho dầm thép); caller truyền category của chi tiết thật.
  * Miner: D ≥ 1 coi là phá mỏi — giả thiết tuyến tính tích lũy, chuẩn
    sàng lọc; không mô hình hóa load order.

Tuổi thọ mỏi (năm) = số chu kỳ cho D=1 chia tổng chu kỳ/năm của quang phổ.
"""
from __future__ import annotations

__all__ = ["cycles_to_failure", "miner_damage", "fatigue_life_years"]


def cycles_to_failure(stress_range_MPa: float, detail_category_MPa: float = 71.0,
                      m: float = 3.0) -> float:
    """Số chu kỳ tới phá theo S-N một đoạn: N = 2e6 · (Δσ_C / Δσ)^m.

    EN 1993-1-9 chuẩn hóa đường S-N qua điểm (2·10^6, Δσ_C). Δσ ≤ 0 → vô cực
    (không có dao động thì không mỏi).
    """
    if stress_range_MPa <= 0:
        return float("inf")
    if detail_category_MPa <= 0 or m <= 0:
        raise ValueError("detail_category_MPa và m phải dương")
    return 2.0e6 * (detail_category_MPa / stress_range_MPa) ** m


def miner_damage(spectrum: list[tuple[float, float]],
                 detail_category_MPa: float = 71.0,
                 m: float = 3.0) -> float:
    """Thiệt hại Miner từ quang phổ [(số chu kỳ, khoảng ứng suất MPa), ...].

    D < 1: an toàn theo giả thiết Miner; D ≥ 1: phá mỏi tích lũy.
    """
    damage = 0.0
    for n_i, ds_i in spectrum:
        if n_i < 0:
            raise ValueError("số chu kỳ không âm")
        damage += n_i / cycles_to_failure(ds_i, detail_category_MPa, m)
    return damage


def fatigue_life_years(spectrum_per_year: list[tuple[float, float]],
                       detail_category_MPa: float = 71.0,
                       m: float = 3.0) -> float:
    """Tuổi thọ mỏi (năm) = 1 / D_một_năm.

    ``spectrum_per_year`` là quang phổ CHU KỲ MỖI NĂM. Trả float("inf") khi
    quang phổ rỗng hoặc D=0.
    """
    damage_per_year = miner_damage(spectrum_per_year, detail_category_MPa, m)
    if damage_per_year <= 0:
        return float("inf")
    return 1.0 / damage_per_year
