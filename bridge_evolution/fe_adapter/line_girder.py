"""L1 — Line-girder analysis cho dầm Super-T giản đơn liên hợp bản BTCT.

Đơn vị nội bộ: kN, m, kPa (chuyển sang MPa ở lớp báo cáo).
Mô hình:
  - Hoạt tải HL-93: truck/tandem quét vị trí chính xác trên dầm giản đơn + lane load.
  - Phân bố ngang: công thức type-k TCVN 11823-4 / AASHTO 4.6.2.2 (dầm trong).
  - Mặt cắt liên hợp: bản quy đổi theo tỷ số mô đun Ed/Eg, beff = min(S, L/4).
  - Võng hoạt tải: truck quy đổi lực tập trung giữa nhịp (Peq = 4M/L) — thiên lớn nhẹ.
  - Tần số: f1 = (π/2L²)·√(EI_c/m̄), dầm giản đơn.

GIỚI HẠN L1 (chuyển L2/L3): chưa xét mất mát DƯL theo giai đoạn, co ngót–từ biến,
ứng suất lúc truyền lực, dầm biên, xoắn/ngang. Mất mát tổng giả định trong catalog.
"""
import math
from functools import lru_cache

from ..catalogs import load_catalogs
from ..objectives import diaphragm_concrete_volume_m3

GRAVITY = 9.81  # m/s²


class SolverError(Exception):
    """Mô hình suy biến / không hội tụ — candidate bị loại, không phải đường thoát phạt."""


# ---------------------------------------------------------------- moving load
@lru_cache(maxsize=64)
def _moving_load_max(L: float, axles: tuple, step: float = 0.05) -> tuple[float, float]:
    """(Mmax, Vmax) một làn xe trên dầm giản đơn — quét vị trí, mô men lấy dưới trục."""
    total_len = max(off for off, _ in axles)
    best_M = best_V = 0.0
    for direction in (axles, tuple((total_len - off, P) for off, P in axles)):
        x0 = -total_len
        while x0 <= L + 1e-9:
            on_span = [(x0 + off, P) for off, P in direction if -1e-9 <= x0 + off <= L + 1e-9]
            if on_span:
                RA = sum(P * (L - x) / L for x, P in on_span)
                RB = sum(P for _, P in on_span) - RA
                best_V = max(best_V, RA, RB)
                for xa, _ in on_span:
                    M = RA * xa - sum(P * (xa - x) for x, P in on_span if x < xa - 1e-12)
                    best_M = max(best_M, M)
            x0 += step
    return best_M, best_V


@lru_cache(maxsize=16)
def lane_effects(load_profile_id: str, L: float) -> dict:
    """Hiệu ứng hoạt tải MỘT LÀN (chưa nhân DF): phụ thuộc duy nhất (profile, L) nên cache."""
    lp = load_catalogs()["load_profiles"][load_profile_id]
    M_tr, V_tr = _moving_load_max(L, tuple(tuple(a) for a in lp["truck_axles"]))
    M_td, V_td = _moving_load_max(L, tuple(tuple(a) for a in lp["tandem_axles"]))
    im = 1.0 + lp["impact_factor"]
    w_lane = lp["lane_load_kN_per_m"]
    M_veh, V_veh = max(M_tr, M_td), max(V_tr, V_td)
    return {
        "M_lane_total": M_veh * im + w_lane * L**2 / 8.0,
        "V_lane_total": V_veh * im + w_lane * L / 2.0,
        "M_truck_im": M_tr * im,          # dùng riêng cho tổ hợp võng
        "w_lane": w_lane,
    }


# ---------------------------------------------------------------- sections
def composite_section(sec: dict, Eg_GPa: float, Ed_GPa: float,
                      spacing: float, ts: float, span: float) -> dict:
    if sec["I_m4"] <= 0 or sec["area_m2"] <= 0 or Eg_GPa <= 0:
        raise SolverError("Tiết diện/vật liệu suy biến (I≤0 hoặc A≤0 hoặc E≤0) — độ cứng kỳ dị")
    h, A, I, yb = sec["depth_m"], sec["area_m2"], sec["I_m4"], sec["y_bottom_m"]
    n_mod = Ed_GPa / Eg_GPa                      # quy đổi bản về vật liệu dầm
    beff = min(spacing, span / 4.0)
    b_tr = beff * n_mod
    A_sl = b_tr * ts
    y_sl = h + ts / 2.0
    A_c = A + A_sl
    yb_c = (A * yb + A_sl * y_sl) / A_c
    I_c = (I + A * (yb_c - yb) ** 2
           + b_tr * ts**3 / 12.0 + A_sl * (y_sl - yb_c) ** 2)
    return {
        "n_mod": n_mod, "beff_m": beff,
        "A_c": A_c, "yb_c": yb_c, "I_c": I_c,
        "Sb_girder": I / yb,                     # thớ dưới, giai đoạn 1 (chưa liên hợp)
        "Sb_comp": I_c / yb_c,                   # thớ dưới, giai đoạn 2 (liên hợp)
    }


def _kg_term(sec: dict, Eg: float, Ed: float, ts: float) -> float:
    """Kg = n(I + A·eg²), mm⁴ — tham số độ cứng dọc cho công thức DF."""
    eg = (sec["depth_m"] - sec["y_bottom_m"]) + ts / 2.0
    n_g = Eg / Ed
    return n_g * (sec["I_m4"] + sec["area_m2"] * eg**2) * 1e12  # m⁴ → mm⁴


def distribution_factors(sec: dict, Eg: float, Ed: float, spacing: float, ts: float,
                         span: float, deck_width: float, lp: dict) -> dict:
    """DF dầm trong theo TCVN 11823-4 (type k). Đơn vị công thức: mm."""
    S, L, t = spacing * 1000, span * 1000, ts * 1000
    Kg = _kg_term(sec, Eg, Ed, ts)
    stiff = (Kg / (L * t**3)) ** 0.1
    g_m1 = 0.06 + (S / 4300) ** 0.4 * (S / L) ** 0.3 * stiff
    g_m2 = 0.075 + (S / 2900) ** 0.6 * (S / L) ** 0.2 * stiff
    g_v1 = 0.36 + S / 7600
    g_v2 = 0.2 + S / 3600 - (S / 10700) ** 2
    n_lanes = max(1, int((deck_width - 1.0) / lp["design_lane_width_m"]))  # trừ 2 gờ lan can
    mp = lp["multiple_presence"][str(min(n_lanes, 4))]
    return {
        "g_moment": max(g_m1, g_m2),
        "g_shear": max(g_v1, g_v2),
        "g_deflection": mp * n_lanes / max(1, lp["_girder_count"]),
        "n_lanes": n_lanes,
    }


# ---------------------------------------------------------------- main entry
def analyze(state: dict, geom: dict) -> dict:
    cat = load_catalogs()
    dv, mats = state["design_variables"], state["materials"]
    sec = geom["section"]
    L, S, ts, n = geom["span_m"], geom["spacing_m"], geom["slab_thickness_m"], geom["girder_count"]

    conc_g = cat["concretes"][mats["girder_concrete_id"]]
    conc_d = cat["concretes"][mats["deck_concrete_id"]]
    ps = cat["prestressing_steels"][mats["prestressing_steel_id"]]
    pt = cat["prestress_layouts"][dv["prestress_layout_id"]]
    dia_geo = cat["diaphragm_layouts"]["_geometry"]
    conc_dia = cat["concretes"][dia_geo["concrete_id"]]
    lp = dict(cat["load_profiles"][state["analysis"]["load_profile_id"]])
    lp["_girder_count"] = n

    comp = composite_section(sec, conc_g["E_GPa"], conc_d["E_GPa"], S, ts, L)

    # ---- tĩnh tải / dầm trong (kN/m)
    gamma_g = conc_g["density_kg_m3"] * GRAVITY / 1000.0
    gamma_d = conc_d["density_kg_m3"] * GRAVITY / 1000.0
    gamma_dia = conc_dia["density_kg_m3"] * GRAVITY / 1000.0
    vol_dia = diaphragm_concrete_volume_m3(state, geom, cat)
    # Quy đổi tổng tự trọng dầm ngang thành tải đều trên n dầm. Tổng tải
    # w_dia*L*n bằng đúng vol_dia*gamma_dia dùng trong mục tiêu vật liệu.
    w_dia = vol_dia * gamma_dia / (L * n)
    w_girder = sec["area_m2"] * gamma_g
    w_deck = S * ts * gamma_d
    w_misc = lp["misc_smeared_dead_load_kN_per_m_per_girder"]
    w_stage1 = w_girder + w_deck + w_dia + w_misc
    w_dw = (lp["wearing_surface_thickness_m"] * lp["wearing_surface_unit_weight_kN_m3"]
            * geom["deck_width_m"]
            + lp["barrier_count"] * lp["barrier_line_load_kN_per_m"]) / n

    M_stage1, V_stage1 = w_stage1 * L**2 / 8.0, w_stage1 * L / 2.0
    M_dw, V_dw = w_dw * L**2 / 8.0, w_dw * L / 2.0

    # ---- hoạt tải
    lane = lane_effects(state["analysis"]["load_profile_id"], L)
    df = distribution_factors(sec, conc_g["E_GPa"], conc_d["E_GPa"], S, ts, L,
                              geom["deck_width_m"], lp)
    M_ll, V_ll = df["g_moment"] * lane["M_lane_total"], df["g_shear"] * lane["V_lane_total"]

    # ---- dự ứng lực (mất mát tổng gộp — giới hạn L1)
    Aps_m2 = pt["strand_count"] * ps["strand_area_mm2"] * 1e-6
    fpe_kPa = ps["jacking_ratio"] * ps["fpu_MPa"] * (1 - ps["assumed_total_loss_ratio"]) * 1e3
    Pe = Aps_m2 * fpe_kPa
    e_g = sec["y_bottom_m"] - pt["centroid_from_bottom_m"]
    dp = sec["depth_m"] + ts - pt["centroid_from_bottom_m"]

    # ---- sức kháng uốn (khối ứng suất chữ nhật trong bản, cáp dính bám)
    fc_deck = conc_d["fc_MPa"]
    beta1 = max(0.65, 0.85 - 0.05 * (fc_deck - 28.0) / 7.0)
    k = ps["k_bond_factor"]
    Aps_mm2, dp_mm, b_mm = Aps_m2 * 1e6, dp * 1000, comp["beff_m"] * 1000
    c_mm = (Aps_mm2 * ps["fpu_MPa"]) / (
        0.85 * fc_deck * beta1 * b_mm + k * Aps_mm2 * ps["fpu_MPa"] / dp_mm)
    a_mm = beta1 * c_mm
    fps_MPa = ps["fpu_MPa"] * (1 - k * c_mm / dp_mm)
    Mn = Aps_mm2 * fps_MPa * (dp_mm - a_mm / 2.0) * 1e-6  # N·mm → kN·m
    stress_block_in_slab = a_mm <= ts * 1000 + 1e-6

    # ---- sức kháng cắt (đơn giản hóa L1: β=2, cốt đai giả định 4 nhánh D10@125)
    dv_shear = max(0.9 * dp, 0.72 * (sec["depth_m"] + ts))
    bv = sec["web_width_total_m"]
    Vc = 0.083 * 2.0 * math.sqrt(conc_g["fc_MPa"]) * bv * dv_shear * 1000  # kN
    Av_m2, fy_kPa, s_m = 4 * 78.5e-6, 420e3, 0.125
    Vs = Av_m2 * fy_kPa * dv_shear / s_m
    Vn = min(Vc + Vs, 0.25 * conc_g["fc_MPa"] * 1e3 * bv * dv_shear)

    # ---- ứng suất thớ dưới (Sử dụng III tính ở verifier; đây là các thành phần)
    sigma_pe = Pe / sec["area_m2"] + Pe * e_g / comp["Sb_girder"]      # kPa, nén +
    sigma_stage1 = M_stage1 / comp["Sb_girder"]                       # kéo do tải g/đoạn 1

    # ---- võng hoạt tải & tần số
    EI_c = conc_g["E_GPa"] * 1e6 * comp["I_c"]                        # kN·m²
    Peq = 4.0 * lane["M_truck_im"] / L
    d_truck = Peq * L**3 / (48.0 * EI_c)
    d_lane = 5.0 * lane["w_lane"] * L**4 / (384.0 * EI_c)
    d_ll = df["g_deflection"] * max(d_truck, 0.25 * d_truck + d_lane)

    mass_per_m = (w_stage1 + w_dw) / GRAVITY                          # t/m
    f1 = (math.pi / (2.0 * L**2)) * math.sqrt(EI_c / mass_per_m)

    return {
        "solver": {"name": "BUILTIN_L1", "status": "CONVERGED"},
        "composite": comp,
        "distribution": df,
        "moments_kNm": {"stage1": M_stage1, "dw": M_dw, "ll_im": M_ll},
        "shears_kN": {"stage1": V_stage1, "dw": V_dw, "ll_im": V_ll},
        "prestress": {"Pe_kN": Pe, "e_m": e_g, "dp_m": dp,
                      "sigma_pe_kPa": sigma_pe, "sigma_stage1_kPa": sigma_stage1},
        "capacity": {"Mn_kNm": Mn, "Vn_kN": Vn, "fps_MPa": fps_MPa,
                     "compression_block_depth_mm": a_mm,
                     "slab_thickness_mm": ts * 1000.0,
                     "stress_block_in_slab": stress_block_in_slab},
        "dead_loads_kN_per_m": {
            "girder": w_girder,
            "deck": w_deck,
            "diaphragm_smeared": w_dia,
            "misc": w_misc,
            "stage1_total": w_stage1,
            "wearing_surface_and_barriers": w_dw,
        },
        "deflection_m": {"ll": d_ll},
        "first_frequency_Hz": f1,
    }
