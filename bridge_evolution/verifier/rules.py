"""Independent Verifier — PASS/FAIL theo rule profile khai trong chính state.

Nguyên tắc: verifier KHÔNG tin solver "tự nhận đạt" — nó nhận số liệu phản ứng
thô rồi tự áp tiêu chuẩn. Verifier cũng chạy lại toàn bộ kiểm tra hình học L0
(double-check độc lập với đường sinh phương án).

Nhãn truy vết ruleset phải SUY TỪ ``state["constraints"]["rule_profile_id"]``.
Một hằng cố định sẽ khiến mọi kết quả chạy dưới BRIDGE-RULESET-V2 (grammar tham
số hóa, có thêm FAB-001..FAB-007) tự khai nhầm là chạy dưới V1 — phép tính vẫn
đúng nhưng artifact nói dối về điều kiện sinh ra nó (BRD-010).
"""
import math

from ..catalogs import load_catalogs
from ..geometry import check_geometry

#: Profile mặc định khi state không khai (chỉ dùng cho hằng tương thích ngược).
DEFAULT_RULE_PROFILE_ID = "BRIDGE-RULESET-V1"

#: Nhãn dùng khi không phân giải được profile — KHÔNG bịa về V1.
UNRESOLVED_RULESET_VERSION = "UNRESOLVED"


def ruleset_label(rule_profile_id: str) -> str:
    """``<rule_profile_id>/<ruleset_version của chính profile đó>``."""
    profile = load_catalogs()["rule_profiles"].get(rule_profile_id)
    if not isinstance(profile, dict):
        return f"{rule_profile_id}/{UNRESOLVED_RULESET_VERSION}"
    return f"{rule_profile_id}/{profile.get('ruleset_version', UNRESOLVED_RULESET_VERSION)}"


def ruleset_version_for(state) -> str:
    """Nhãn truy vết của MỘT state cụ thể; không raise với state hỏng."""
    try:
        rule_profile_id = state["constraints"]["rule_profile_id"]
    except (TypeError, KeyError, IndexError):
        return UNRESOLVED_RULESET_VERSION
    if not isinstance(rule_profile_id, str):
        return UNRESOLVED_RULESET_VERSION
    return ruleset_label(rule_profile_id)


#: Hằng tương thích ngược = nhãn của profile mặc định, suy từ catalog nên không
#: bao giờ lệch khỏi dữ liệu thật. Đường provenance dùng ``ruleset_version_for``.
RULESET_VERSION = ruleset_label(DEFAULT_RULE_PROFILE_ID)


def verify_candidate(state: dict, geom: dict, analysis: dict) -> tuple[list[dict], dict]:
    """Trả về (violations, responses). responses = số liệu phục vụ báo cáo/RL observation."""
    cat = load_catalogs()
    rules = cat["rule_profiles"][state["constraints"]["rule_profile_id"]]
    conc_g = cat["concretes"][state["materials"]["girder_concrete_id"]]

    violations, _ = check_geometry(state)  # kiểm tra lại hình học — độc lập
    utils = {}

    def check(rule_id, severity, demand, capacity, message):
        util = demand / capacity if capacity > 0 else math.inf
        utils[rule_id] = util
        if util > 1.0 + 1e-9:
            violations.append({
                "rule_id": rule_id, "severity": severity,
                "message": message, "margin": round(util - 1.0, 4),
            })

    c1, c3 = rules["strength1"], rules["service3"]
    M, V = analysis["moments_kNm"], analysis["shears_kN"]

    # MODEL-001 — công thức sức kháng uốn L1 chỉ hợp lệ khi toàn bộ khối
    # ứng suất chữ nhật nằm trong bản. Kiểm lại từ chiều sâu thô thay vì chỉ
    # tin cờ boolean do solver trả về; fail-closed nếu cờ không phải True.
    capacity = analysis["capacity"]
    a_mm = capacity["compression_block_depth_mm"]
    slab_mm = capacity["slab_thickness_mm"]
    block_util = a_mm / slab_mm if slab_mm > 0 else math.inf
    utils["MODEL-001"] = block_util
    block_outside = slab_mm <= 0 or a_mm > slab_mm + 1e-6
    if capacity.get("stress_block_in_slab") is not True or block_outside:
        margin = max(block_util - 1.0, 0.0001) if math.isfinite(block_util) else 1.0
        violations.append({
            "rule_id": "MODEL-001", "severity": "HARD",
            "message": (f"Khối ứng suất nén a={a_mm:.1f} mm vượt chiều dày bản "
                        f"ts={slab_mm:.1f} mm; công thức Mn của L1 nằm ngoài miền áp dụng"),
            "margin": round(margin, 4),
        })

    # STR-001 — uốn, Cường độ I
    Mu = c1["DC"] * M["stage1"] + c1["DW"] * M["dw"] + c1["LL"] * M["ll_im"]
    phiMn = rules["phi_flexure"] * analysis["capacity"]["Mn_kNm"]
    check("STR-001", "HARD", Mu, phiMn,
          f"Uốn CĐ-I: Mu={Mu:.0f} kNm > φMn={phiMn:.0f} kNm")

    # STR-002 — cắt, Cường độ I (mô hình đơn giản hóa L1)
    Vu = c1["DC"] * V["stage1"] + c1["DW"] * V["dw"] + c1["LL"] * V["ll_im"]
    phiVn = rules["phi_shear"] * analysis["capacity"]["Vn_kN"]
    check("STR-002", "HARD", Vu, phiVn,
          f"Cắt CĐ-I: Vu={Vu:.0f} kN > φVn={phiVn:.0f} kN")

    # SERV-001 — ứng suất kéo thớ dưới, Sử dụng III (nén +, kéo −)
    ps = analysis["prestress"]
    M_service2 = c3["DW"] * M["dw"] + c3["LL"] * M["ll_im"]
    sigma_bottom_kPa = (ps["sigma_pe_kPa"] - c3["DC"] * ps["sigma_stage1_kPa"]
                        - M_service2 / analysis["composite"]["Sb_comp"])
    tension_MPa = max(0.0, -sigma_bottom_kPa / 1000.0)
    tension_limit = rules["service_tension_limit_coef_sqrt_fc"] * math.sqrt(conc_g["fc_MPa"])
    check("SERV-001", "HARD", tension_MPa, tension_limit,
          f"Kéo thớ dưới SD-III: {tension_MPa:.2f} MPa > giới hạn {tension_limit:.2f} MPa")

    # SERV-002 — võng hoạt tải
    d_ll = analysis["deflection_m"]["ll"]
    d_limit = geom["span_m"] / rules["deflection_limit_span_ratio"]
    check("SERV-002", "HARD", d_ll, d_limit,
          f"Võng hoạt tải {d_ll * 1000:.1f} mm > L/{rules['deflection_limit_span_ratio']}"
          f" = {d_limit * 1000:.1f} mm")

    # SERV-003 — tần số dao động cơ bản (SOFT)
    f1 = analysis["first_frequency_Hz"]
    f_min = rules["min_first_frequency_Hz"]
    if f1 < f_min:
        utils["SERV-003"] = f_min / f1
        violations.append({
            "rule_id": "SERV-003", "severity": "SOFT",
            "message": f"Tần số f1={f1:.2f} Hz < khuyến nghị {f_min} Hz",
            "margin": round(f_min / f1 - 1.0, 4),
        })

    hard_utils = {k: v for k, v in utils.items()
                  if k.startswith(("MODEL", "STR", "SERV-001", "SERV-002"))}
    responses = {
        "Mu_strength1_kNm": round(Mu, 1),
        "phiMn_kNm": round(phiMn, 1),
        "Vu_strength1_kN": round(Vu, 1),
        "phiVn_kN": round(phiVn, 1),
        "bottom_stress_service3_MPa": round(sigma_bottom_kPa / 1000.0, 3),
        "tension_limit_MPa": round(tension_limit, 3),
        "max_ll_deflection_mm": round(d_ll * 1000.0, 2),
        "deflection_limit_mm": round(d_limit * 1000.0, 2),
        "first_frequency_Hz": round(f1, 3),
        "max_utilization": round(max(hard_utils.values()), 4),
        "distribution_factor_moment": round(analysis["distribution"]["g_moment"], 4),
        "distribution_factor_shear": round(analysis["distribution"]["g_shear"], 4),
    }
    return violations, responses
