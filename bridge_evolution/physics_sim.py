"""TCVN 11823:2017 L1 Natural & Physical Simulation Engine (P0).

Module này mở rộng lớp sàng lọc L1 hiện có bằng các hiệu ứng tự nhiên và thử tải
vật lý trung thực cho cầu dầm nhịp giản đơn tại Việt Nam:
  1. 5 kịch bản môi trường/tải trọng Việt Nam (V0..V4).
  2. Gió ngang WS/WL (áp lực gió thiết kế P_D, tải gió ngang và thành phần lật).
  3. Nhiệt độ đều TU (biến dạng dài ΔL) & Gradient nhiệt TG (ứng suất tự cân bằng
     CHỈ áp dụng cho nhịp giản đơn — ``SIMPLY_SUPPORTED_ONLY``).
  4. Cấp phơi nhiễm môi trường (INLAND_MODERATE / COASTAL_HUMID / MARINE_SEVERE)
     siết ứng suất kéo cho phép và chiều dày lớp bảo vệ tối thiểu.
  5. Động đất EQ mức sàng lọc L1: CHỈ tính chiều dài gối đỡ tối thiểu N_min
     (TCVN 11823-4:4.7.4.4) và lực chốt chống xô bảo thủ F_key — TUYỆT ĐỐI KHÔNG
     dùng chu kỳ uốn thẳng đứng T1 để tra phổ phản ứng ngang Csm.
  6. Kiểm tra nén thớ trên SERV-004 (0.45·f'c dài hạn, 0.60·f'c toàn phần).
  7. Bao nội lực/ứng suất/võng 21 trạm dọc nhịp, Rating Factor (RF), Safety Factor
     (SF), và Quét biên dự trữ theo Trạng thái Giới hạn (λ = 0.5..2.5).
  8. Đối chứng L1 vs. MIDAS Civil L2 kèm bảng LaTeX booktabs và CSV.

Trần tuyên bố (claim ceiling): ``SCREENED_HYPOTHETICAL`` — kết quả L1 dùng để
sàng lọc và so sánh tương đối; mọi kết luận thiết kế cuối cùng phải kiểm chứng L2.
"""
from __future__ import annotations

import csv
import io
import math
from copy import deepcopy
from typing import Any

from .catalogs import load_catalogs
from .fe_adapter.line_girder import GRAVITY, SolverError, analyze as line_girder_analyze
from .geometry import BOX_SECTION_ID, derive_geometry
from .section import SectionGeometryError
from .state import new_state, state_from_gene

CLAIM_LEVEL = "SCREENED_HYPOTHETICAL"

# ---------------------------------------------------------------------------
# 1. Vietnam Environmental & Multi-Hazard Presets (TCVN 11823-3 / TCVN 9386)
# ---------------------------------------------------------------------------
SIM_PRESETS: tuple[dict[str, Any], ...] = (
    {
        "id": "V0_INLAND",
        "name": "V0 — Đồng bằng Nội địa (Chuẩn TCVN)",
        "description": (
            "Kịch bản danh định nội địa Việt Nam: gió cấp trung bình, khí hậu nhiệt đới "
            "ôn hòa, động đất thấp, hoạt tải HL-93 tiêu chuẩn."
        ),
        "wind_vb_ms": 38.0,
        "terrain_cat": "II",
        "bridge_height_m": 10.0,
        "temp_min_c": 10.0,
        "temp_max_c": 42.0,
        "tg_t1_c": 23.0,
        "tg_t2_c": 6.0,
        "pga_g": 0.08,
        "exposure_class": "INLAND_MODERATE",
        "ll_multiplier": 1.0,
        "im_factor": 0.33,
    },
    {
        "id": "V1_COASTAL_TYPHOON",
        "name": "V1 — Ven biển Miền Trung (Bão & Xâm thực)",
        "description": (
            "Cầu ven biển chịu gió bão mạnh (vùng trống trải loại I), biên nhiệt cao và "
            "môi trường ẩm mặn siết ứng suất kéo thớ dưới."
        ),
        "wind_vb_ms": 50.0,
        "terrain_cat": "I",
        "bridge_height_m": 15.0,
        "temp_min_c": 12.0,
        "temp_max_c": 45.0,
        "tg_t1_c": 25.0,
        "tg_t2_c": 7.0,
        "pga_g": 0.10,
        "exposure_class": "COASTAL_HUMID",
        "ll_multiplier": 1.0,
        "im_factor": 0.33,
    },
    {
        "id": "V2_NORTHWEST_SEISMIC",
        "name": "V2 — Tây Bắc (Động đất & Biên độ nhiệt)",
        "description": (
            "Khu vực miền núi Tây Bắc với gia tốc nền PGA cao (0.25g), cầu vượt thung lũng "
            "cao và biên độ nhiệt ngày-đêm lớn."
        ),
        "wind_vb_ms": 35.0,
        "terrain_cat": "III",
        "bridge_height_m": 18.0,
        "temp_min_c": 2.0,
        "temp_max_c": 40.0,
        "tg_t1_c": 23.0,
        "tg_t2_c": 6.0,
        "pga_g": 0.25,
        "exposure_class": "INLAND_MODERATE",
        "ll_multiplier": 1.0,
        "im_factor": 0.33,
    },
    {
        "id": "V3_PORT_OVERLOAD",
        "name": "V3 — Cảng biển (Quá tải Container & Biển nặng)",
        "description": (
            "Tuyến kết nối cảng biển với xe quá tải (+35% hoạt tải, xung kích 0.38) và "
            "môi trường biển khắc nghiệt (không cho phép ứng suất kéo thớ dưới)."
        ),
        "wind_vb_ms": 45.0,
        "terrain_cat": "I",
        "bridge_height_m": 12.0,
        "temp_min_c": 14.0,
        "temp_max_c": 44.0,
        "tg_t1_c": 25.0,
        "tg_t2_c": 7.0,
        "pga_g": 0.10,
        "exposure_class": "MARINE_SEVERE",
        "ll_multiplier": 1.35,
        "im_factor": 0.38,
    },
    {
        "id": "V4_EXTREME_MULTIHAZARD",
        "name": "V4 — Đa tai biến Cực đoan (Bão + Động đất + Quá tải)",
        "description": (
            "Kịch bản thử tải khắc nghiệt kết hợp siêu bão (55 m/s), động đất mạnh (0.28g), "
            "nhiệt độ cực đại, xâm thực biển nặng và hoạt tải tăng 30%."
        ),
        "wind_vb_ms": 55.0,
        "terrain_cat": "I",
        "bridge_height_m": 20.0,
        "temp_min_c": 4.0,
        "temp_max_c": 48.0,
        "tg_t1_c": 27.0,
        "tg_t2_c": 8.0,
        "pga_g": 0.28,
        "exposure_class": "MARINE_SEVERE",
        "ll_multiplier": 1.30,
        "im_factor": 0.40,
    },
)

_PRESETS_BY_ID: dict[str, dict[str, Any]] = {p["id"]: p for p in SIM_PRESETS}

# Exposure class limits per TCVN 11823-5 Table 5.9.4.2.2-1 & durability cover
EXPOSURE_RULES: dict[str, dict[str, Any]] = {
    "INLAND_MODERATE": {
        "tension_coef_sqrt_fc": 0.50,
        "cover_req_mm": 50.0,
        "label": "Nội địa trung bình (0.50·√f'c, lớp bảo vệ ≥ 50 mm)",
    },
    "COASTAL_HUMID": {
        "tension_coef_sqrt_fc": 0.25,
        "cover_req_mm": 60.0,
        "label": "Ven biển ẩm mặn (0.25·√f'c, lớp bảo vệ ≥ 60 mm)",
    },
    "MARINE_SEVERE": {
        "tension_coef_sqrt_fc": 0.0,
        "cover_req_mm": 75.0,
        "label": "Môi trường biển khắc nghiệt (0.0 MPa — không kéo, lớp bảo vệ ≥ 75 mm)",
    },
}

# Terrain roughness parameters (TCVN 11823-3:3.8.1.1 / AASHTO LRFD)
_TERRAIN_PARAMS: dict[str, dict[str, float]] = {
    "I": {"z0_m": 0.01, "alpha_exp": 0.12, "k_base": 1.08},
    "II": {"z0_m": 0.07, "alpha_exp": 0.16, "k_base": 1.00},
    "III": {"z0_m": 0.30, "alpha_exp": 0.22, "k_base": 0.88},
    "IV": {"z0_m": 1.00, "alpha_exp": 0.30, "k_base": 0.76},
}

_ALPHA_CONCRETE_PER_C = 1.08e-5  # 1/°C (TCVN 11823-5:5.4.2.2)
_REF_TEMP_C = 20.0
_BARRIER_HEIGHT_M = 1.0
_WIND_CD_GIRDER = 1.6
_WIND_GUST_G = 1.15
_AIR_DENSITY_KG_M3 = 1.225
_N_STATIONS = 21
_SWEEP_LAMBDAS: tuple[float, ...] = tuple(round(0.5 + 0.1 * i, 1) for i in range(21))

HONESTY_NOTE = (
    "SCREENED_HYPOTHETICAL (TCVN 11823:2017 L1): "
    "(1) Gradient nhiệt TG chỉ áp dụng cho nhịp giản đơn (SIMPLY_SUPPORTED_ONLY — không có mô-men siêu tĩnh); "
    "(2) Động đất EQ ở L1 chỉ sàng lọc chiều dài gối tối thiểu N_min và lực chốt F_key — tuyệt đối không dùng chu kỳ uốn đứng T1 cho phổ ngang Csm; "
    "(3) Quét hệ số λ là Biên dự trữ theo Trạng thái Giới hạn đàn hồi tuyến tính, không phải phân tích đẩy dần phi tuyến (Pushover); "
    "(4) Dầm hộp đơn ô ở L1 bỏ qua xoắn St. Venant, vênh mặt cắt và shear lag — bắt buộc kiểm chứng MIDAS Civil L2."
)


def list_sim_presets() -> dict[str, Any]:
    """Return the 5 standardized Vietnam environmental & load presets."""
    return {
        "claim_level": CLAIM_LEVEL,
        "presets": [dict(p) for p in SIM_PRESETS],
    }


def _safe_float(val: Any, default: float) -> float:
    if isinstance(val, bool) or val is None:
        return default
    try:
        out = float(val)
        return out if math.isfinite(out) else default
    except (TypeError, ValueError):
        return default


def resolve_scenario(scenario: dict[str, Any] | str | None) -> dict[str, Any]:
    """Normalize a scenario dict or preset ID into a complete, validated scenario dict."""
    base = dict(_PRESETS_BY_ID["V0_INLAND"])
    if isinstance(scenario, str):
        if scenario in _PRESETS_BY_ID:
            base = dict(_PRESETS_BY_ID[scenario])
        return base
    if not isinstance(scenario, dict):
        return base

    preset_id = scenario.get("preset_id") or scenario.get("id")
    if isinstance(preset_id, str) and preset_id in _PRESETS_BY_ID:
        base = dict(_PRESETS_BY_ID[preset_id])

    for key in (
        "wind_vb_ms",
        "bridge_height_m",
        "temp_min_c",
        "temp_max_c",
        "tg_t1_c",
        "tg_t2_c",
        "pga_g",
        "ll_multiplier",
        "im_factor",
    ):
        if key in scenario and scenario[key] is not None:
            base[key] = _safe_float(scenario[key], base[key])

    if "terrain_cat" in scenario and str(scenario["terrain_cat"]).upper() in _TERRAIN_PARAMS:
        base["terrain_cat"] = str(scenario["terrain_cat"]).upper()
    if "exposure_class" in scenario and str(scenario["exposure_class"]).upper() in EXPOSURE_RULES:
        base["exposure_class"] = str(scenario["exposure_class"]).upper()
    if isinstance(scenario.get("name"), str) and scenario["name"].strip():
        base["name"] = scenario["name"].strip()
    if isinstance(scenario.get("description"), str) and scenario["description"].strip():
        base["description"] = scenario["description"].strip()

    # Physical bounds clamping
    base["wind_vb_ms"] = max(0.0, min(90.0, base["wind_vb_ms"]))
    base["bridge_height_m"] = max(2.0, min(150.0, base["bridge_height_m"]))
    base["pga_g"] = max(0.0, min(1.0, base["pga_g"]))
    base["ll_multiplier"] = max(0.1, min(5.0, base["ll_multiplier"]))
    base["im_factor"] = max(0.0, min(1.0, base["im_factor"]))
    if base["temp_max_c"] < base["temp_min_c"]:
        base["temp_max_c"], base["temp_min_c"] = base["temp_min_c"], base["temp_max_c"]
    return base


# ---------------------------------------------------------------------------
# 2. Flexible State Extraction & L1 Model Resolution
# ---------------------------------------------------------------------------
def _default_super_t_state() -> dict[str, Any]:
    return new_state(
        {
            "girder_catalog_id": "ST-1750",
            "girder_count": 5,
            "girder_spacing_mm": 2400,
            "deck_slab_thickness_mm": 200,
            "diaphragm_layout_id": "DG-5",
            "prestress_layout_id": "PT-42",
        },
        girder_concrete_id="C50",
        deck_concrete_id="C35",
        grammar_id="super_t_simple_v1",
    )


def _infer_grammar_id(dv: dict[str, Any], explicit_family: str | None = None) -> str:
    if explicit_family in (
        "super_t_simple_v1",
        "super_t_parametric_v2",
        "box_girder_parametric_v1",
        "i_girder_parametric_v1",
    ):
        return explicit_family
    marker = dv.get("girder_catalog_id")
    if marker == "BOX-PARAM" or "box_web_height_mm" in dv:
        return "box_girder_parametric_v1"
    if marker == "ST-PARAM" or "girder_depth_mm" in dv:
        return "super_t_parametric_v2"
    return "super_t_simple_v1"


def _coerce_to_full_state(raw: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    """Coerce a full BridgeDesignState, design_loop report, or simplified dict into a full state.

    Returns (state, extra_metadata). Never raises on partial/simplified inputs.
    """
    extra: dict[str, Any] = {}
    if not isinstance(raw, dict):
        return _default_super_t_state(), {"coerced_from": "default_fallback"}

    # Unwrap report / wrapper payloads (including design_loop report["final"])
    candidate = raw
    for wrapper_key in ("final", "final_state", "design_state", "state", "candidate_state"):
        if isinstance(raw.get(wrapper_key), dict):
            candidate = raw[wrapper_key]
            break

    explicit_family = (
        candidate.get("family")
        or candidate.get("grammar_id")
        or raw.get("grammar_id")
        or raw.get("family")
    )

    # Preserve caller-supplied summary fields for reference/fallback
    for meta_key in ("objectives", "max_utilization", "rule_utilizations", "responses", "case_id"):
        if meta_key in raw:
            extra[meta_key] = raw[meta_key]
        elif meta_key in candidate:
            extra[meta_key] = candidate[meta_key]

    # Case A: Looks like a full BridgeDesignState
    if (
        isinstance(candidate.get("design_variables"), dict)
        and isinstance(candidate.get("materials"), dict)
        and isinstance(candidate.get("project_inputs"), dict)
    ):
        st = deepcopy(candidate)
        st.setdefault("family", _infer_grammar_id(st["design_variables"], explicit_family))
        st.setdefault(
            "analysis",
            {
                "fidelity": "L1_LINE_GIRDER",
                "solver": "BUILTIN_L1",
                "load_profile_id": "LOAD-PROFILE-01",
            },
        )
        st.setdefault("constraints", {"rule_profile_id": "BRIDGE-RULESET-V2"})
        extra["coerced_from"] = "full_state"
        return st, extra

    # Case B: Simplified dict with `gene` or `design_variables`
    raw_dv = candidate.get("gene") if isinstance(candidate.get("gene"), dict) else candidate.get("design_variables")
    if isinstance(raw_dv, dict) and raw_dv:
        dv = dict(raw_dv)
        mats = candidate.get("materials") if isinstance(candidate.get("materials"), dict) else {}
        girder_conc = dv.pop("girder_concrete_id", mats.get("girder_concrete_id", "C50"))
        deck_conc = dv.pop("deck_concrete_id", mats.get("deck_concrete_id", "C35"))
        family = _infer_grammar_id(dv, explicit_family)

        # Fill missing required keys with safe defaults for the inferred family
        if family == "box_girder_parametric_v1":
            dv.setdefault("girder_catalog_id", "BOX-PARAM")
            dv.setdefault("girder_count", 1)
            dv.setdefault("girder_spacing_mm", 12000)
            dv.setdefault("deck_slab_thickness_mm", 250)
            dv.setdefault("diaphragm_layout_id", "DG-5")
            dv.setdefault("prestress_layout_id", "PT-54")
            dv.setdefault("box_web_height_mm", 2400)
            dv.setdefault("box_bottom_width_mm", 6500)
            dv.setdefault("box_bottom_slab_mm", 250)
            dv.setdefault("box_web_thickness_mm", 450)
        elif family == "super_t_parametric_v2":
            dv.setdefault("girder_catalog_id", "ST-PARAM")
            dv.setdefault("girder_count", 5)
            dv.setdefault("girder_spacing_mm", 2400)
            dv.setdefault("deck_slab_thickness_mm", 200)
            dv.setdefault("diaphragm_layout_id", "DG-5")
            dv.setdefault("prestress_layout_id", "PT-42")
            dv.setdefault("girder_depth_mm", 1750)
            dv.setdefault("top_flange_width_mm", 2050)
            dv.setdefault("top_flange_thickness_mm", 120)
            dv.setdefault("web_thickness_mm", 110)
            dv.setdefault("bottom_bulb_width_mm", 350)
            dv.setdefault("bottom_bulb_height_mm", 300)
        else:
            dv.setdefault("girder_catalog_id", "ST-1750")
            dv.setdefault("girder_count", 5)
            dv.setdefault("girder_spacing_mm", 2400)
            dv.setdefault("deck_slab_thickness_mm", 200)
            dv.setdefault("diaphragm_layout_id", "DG-5")
            dv.setdefault("prestress_layout_id", "PT-42")

        st = new_state(
            dv,
            girder_concrete_id=str(girder_conc),
            deck_concrete_id=str(deck_conc),
            grammar_id=family,
        )
        # Allow optional span/width overrides on simplified dicts
        if isinstance(candidate.get("project_inputs"), dict):
            for k in ("span_length_m", "deck_width_m", "skew_deg"):
                if k in candidate["project_inputs"]:
                    st["project_inputs"][k] = _safe_float(
                        candidate["project_inputs"][k], st["project_inputs"].get(k, 0.0)
                    )
        if "span_length_m" in candidate:
            st["project_inputs"]["span_length_m"] = _safe_float(candidate["span_length_m"], 38.3)
        if "deck_width_m" in candidate:
            st["project_inputs"]["deck_width_m"] = _safe_float(candidate["deck_width_m"], 12.0)

        extra["coerced_from"] = "simplified_gene"
        return st, extra

    # Case C: Bare simplified dict (only objectives / max_utilization / etc.)
    extra["coerced_from"] = "bare_fallback"
    return _default_super_t_state(), extra


def _resolve_l1_model(raw_state: Any) -> dict[str, Any]:
    """Run L1 geometry + line_girder analysis with safe fallback for simplified dicts."""
    cat = load_catalogs()
    state, extra = _coerce_to_full_state(raw_state)
    fallback_used = False

    try:
        geom = derive_geometry(state)
        analysis = line_girder_analyze(state, geom)
    except (KeyError, ValueError, TypeError, SolverError, SectionGeometryError):
        fallback_used = True
        state = _default_super_t_state()
        geom = derive_geometry(state)
        analysis = line_girder_analyze(state, geom)

    dv = state["design_variables"]
    mats = state["materials"]
    conc_g = cat["concretes"].get(mats["girder_concrete_id"], cat["concretes"]["C50"])
    conc_d = cat["concretes"].get(mats["deck_concrete_id"], cat["concretes"]["C35"])
    pt = cat["prestress_layouts"].get(dv["prestress_layout_id"], cat["prestress_layouts"]["PT-42"])
    rules = cat["rule_profiles"].get(
        state["constraints"].get("rule_profile_id", "BRIDGE-RULESET-V2"),
        cat["rule_profiles"]["BRIDGE-RULESET-V2"],
    )
    lp = cat["load_profiles"].get(
        state["analysis"].get("load_profile_id", "LOAD-PROFILE-01"),
        cat["load_profiles"]["LOAD-PROFILE-01"],
    )

    is_box = dv.get("girder_catalog_id") == BOX_SECTION_ID
    # For single-cell box girder (girder_count == 1), ensure total bridge live load is captured
    # if line_girder returned a multi-girder type-k DF < n_lanes * mp.
    if is_box and geom["girder_count"] == 1:
        n_lanes = analysis["distribution"]["n_lanes"]
        mp = lp["multiple_presence"][str(min(n_lanes, 4))]
        box_df = n_lanes * mp
        if analysis["distribution"]["g_moment"] < box_df - 1e-6:
            scale_m = box_df / max(analysis["distribution"]["g_moment"], 1e-6)
            scale_v = box_df / max(analysis["distribution"]["g_shear"], 1e-6)
            analysis = deepcopy(analysis)
            analysis["distribution"]["g_moment"] = box_df
            analysis["distribution"]["g_shear"] = box_df
            analysis["moments_kNm"]["ll_im"] *= scale_m
            analysis["shears_kN"]["ll_im"] *= scale_v

    return {
        "state": state,
        "geom": geom,
        "analysis": analysis,
        "conc_g": conc_g,
        "conc_d": conc_d,
        "pt": pt,
        "rules": rules,
        "lp": lp,
        "is_box": is_box,
        "fallback_used": fallback_used,
        "extra": extra,
    }


# ---------------------------------------------------------------------------
# 3. TCVN 11823:2017 L1 Physical Environmental Effects
# ---------------------------------------------------------------------------
def compute_wind_effects(geom: dict[str, Any], scenario: dict[str, Any]) -> dict[str, Any]:
    """Compute TCVN 11823-3:3.8.1 wind pressure P_D, lateral WS/WL, and overturning increment."""
    sec = geom["section"]
    h_struct = sec["depth_m"] + geom["slab_thickness_m"]
    h_exposed = h_struct + _BARRIER_HEIGHT_M

    terrain = _TERRAIN_PARAMS.get(scenario["terrain_cat"], _TERRAIN_PARAMS["II"])
    z_m = max(10.0, float(scenario["bridge_height_m"]))
    vb = float(scenario["wind_vb_ms"])

    # Height & terrain adjustment relative to 10 m open-country reference
    k_z = terrain["k_base"] * ((z_m / 10.0) ** terrain["alpha_exp"])
    v_dz_ms = vb * k_z

    # Design wind pressure P_D (kPa) = 0.5 * rho * V_DZ^2 * C_D * G / 1000
    p_d_kpa = 0.5 * _AIR_DENSITY_KG_M3 * (v_dz_ms ** 2) * _WIND_CD_GIRDER * _WIND_GUST_G / 1000.0

    # Lateral wind on structure WS and wind on live load WL (TCVN 11823-3:3.8.1.3)
    w_ws_kn_m = p_d_kpa * h_exposed
    w_wl_kn_m = 1.46 * ((v_dz_ms / 44.7) ** 2) if v_dz_ms > 0 else 0.0

    # Overturning moment per meter about girder bearing level -> vertical load on exterior girder
    n = max(1, int(geom["girder_count"]))
    spacing = float(geom["spacing_m"])
    m_ot_knm_m = w_ws_kn_m * (h_exposed / 2.0) + w_wl_kn_m * (h_struct + 1.8)

    if n >= 2 and spacing > 0:
        # Girder transverse offsets from bridge centerline
        offsets = [((i - (n - 1) / 2.0) * spacing) for i in range(n)]
        sum_x2 = sum(x * x for x in offsets)
        x_ext = max(abs(x) for x in offsets)
        w_vert_ext_kn_m = m_ot_knm_m * x_ext / sum_x2 if sum_x2 > 0 else 0.0
        overturning_note = "Phân bố mô-men lật gió sang dầm biên theo giả thiết bản mặt cầu cứng ngang (L1)."
    else:
        w_vert_ext_kn_m = 0.0
        overturning_note = (
            "Dầm hộp 1 ô (n=1): mô-men lật gió gây xoắn toàn hộp, không quy đổi thành lực thẳng đứng "
            "cục bộ ở L1 — bắt buộc kiểm chứng xoắn trong MIDAS L2."
        )

    return {
        "terrain_cat": scenario["terrain_cat"],
        "bridge_height_m": round(z_m, 2),
        "wind_vb_ms": round(vb, 2),
        "k_z": round(k_z, 4),
        "v_dz_ms": round(v_dz_ms, 2),
        "P_D_kPa": round(p_d_kpa, 3),
        "exposed_depth_m": round(h_exposed, 3),
        "w_WS_kN_per_m": round(w_ws_kn_m, 3),
        "w_WL_kN_per_m": round(w_wl_kn_m, 3),
        "M_overturning_kNm_per_m": round(m_ot_knm_m, 3),
        "w_overturning_ext_girder_kN_per_m": round(w_vert_ext_kn_m, 3),
        "note": overturning_note,
    }


def compute_thermal_effects(
    geom: dict[str, Any],
    analysis: dict[str, Any],
    conc_g: dict[str, Any],
    conc_d: dict[str, Any],
    scenario: dict[str, Any],
) -> dict[str, Any]:
    """Compute TU (uniform expansion ΔL) and TG (self-equilibrating fiber stress, SIMPLY_SUPPORTED_ONLY)."""
    L = float(geom["span_m"])
    t_min = float(scenario["temp_min_c"])
    t_max = float(scenario["temp_max_c"])
    t_range = t_max - t_min
    delta_l_mm = _ALPHA_CONCRETE_PER_C * t_range * L * 1000.0
    delta_l_expand_mm = _ALPHA_CONCRETE_PER_C * max(0.0, t_max - _REF_TEMP_C) * L * 1000.0
    delta_l_contract_mm = _ALPHA_CONCRETE_PER_C * max(0.0, _REF_TEMP_C - t_min) * L * 1000.0

    # TG self-equilibrating stress by numerical fiber integration (100 slices)
    sec = geom["section"]
    comp = analysis["composite"]
    h_g = float(sec["depth_m"])
    ts = float(geom["slab_thickness_m"])
    h_tot = h_g + ts
    e_g_mpa = float(conc_g["E_GPa"]) * 1000.0
    e_d_mpa = float(conc_d["E_GPa"]) * 1000.0
    t1 = float(scenario["tg_t1_c"])
    t2 = float(scenario["tg_t2_c"])

    # Equivalent slice widths reproducing A_girder, A_slab, and composite section
    beff = float(comp["beff_m"])
    n_mod = float(comp["n_mod"])
    b_g_avg = float(sec["area_m2"]) / max(h_g, 1e-6)
    yb_c = float(comp["yb_c"])
    a_c = float(comp["A_c"])
    i_c = float(comp["I_c"])

    def _temp_at_depth_below_top(d_m: float) -> float:
        # TCVN 11823-3:3.12.3 positive vertical temperature gradient
        if d_m <= 0.10:
            return t1 + (t2 - t1) * (d_m / 0.10)
        if d_m <= 0.40:
            return t2 * (1.0 - (d_m - 0.10) / 0.30)
        return 0.0

    n_slices = 100
    dy = h_tot / n_slices
    p_th = 0.0  # MN (using MPa * m^2)
    m_th = 0.0  # MN*m
    for k in range(n_slices):
        y = (k + 0.5) * dy
        d_below_top = h_tot - y
        temp_c = _temp_at_depth_below_top(d_below_top)
        if y <= h_g:
            b_eff_slice = b_g_avg
            e_slice = e_g_mpa
        else:
            b_eff_slice = beff * n_mod
            e_slice = e_g_mpa  # transformed to girder modulus (E_d * b = E_g * b * n_mod)
        # Restrained thermal compressive stress (MPa)
        sigma_r = e_slice * _ALPHA_CONCRETE_PER_C * temp_c
        d_force = sigma_r * b_eff_slice * dy
        p_th += d_force
        m_th += d_force * (y - yb_c)

    # Self-equilibrating stress: sigma_TG(y) = sigma_restrained(y) - P_th/A_c - M_th*(y - yb_c)/I_c
    # Positive = compression, Negative = tension
    sigma_tg_deck_top_mpa = (
        e_d_mpa * _ALPHA_CONCRETE_PER_C * _temp_at_depth_below_top(0.0)
        - n_mod * (p_th / a_c + m_th * (h_tot - yb_c) / i_c)
    )
    sigma_tg_girder_top_mpa = (
        e_g_mpa * _ALPHA_CONCRETE_PER_C * _temp_at_depth_below_top(ts)
        - (p_th / a_c + m_th * (h_g - yb_c) / i_c)
    )
    sigma_tg_bot_mpa = (
        e_g_mpa * _ALPHA_CONCRETE_PER_C * _temp_at_depth_below_top(h_tot)
        - (p_th / a_c + m_th * (0.0 - yb_c) / i_c)
    )

    return {
        "scope": "SIMPLY_SUPPORTED_ONLY",
        "temp_min_c": round(t_min, 1),
        "temp_max_c": round(t_max, 1),
        "temp_range_c": round(t_range, 1),
        "delta_L_mm": round(delta_l_mm, 2),
        "delta_L_expand_mm": round(delta_l_expand_mm, 2),
        "delta_L_contract_mm": round(delta_l_contract_mm, 2),
        "tg_t1_c": round(t1, 1),
        "tg_t2_c": round(t2, 1),
        "sigma_tg_deck_top_MPa": round(sigma_tg_deck_top_mpa, 3),
        "sigma_tg_girder_top_MPa": round(sigma_tg_girder_top_mpa, 3),
        "sigma_tg_bot_MPa": round(sigma_tg_bot_mpa, 3),
        "note": (
            "SIMPLY_SUPPORTED_ONLY: Ứng suất tự cân bằng TG chỉ hợp lệ cho nhịp giản đơn "
            "(không có mô-men siêu tĩnh do gối kềm nhiệt như cầu liên tục/đúc hẫng)."
        ),
    }


def compute_seismic_l1_screening(
    geom: dict[str, Any],
    analysis: dict[str, Any],
    scenario: dict[str, Any],
    skew_deg: float = 0.0,
) -> dict[str, Any]:
    """TCVN 11823-4:4.7.4.4 L1 seismic screening ONLY: N_min_mm and conservative shear key F_key_kN.

    SCIENTIFIC HONESTY RULE: NEVER use vertical flexural period T1 for horizontal Csm!
    """
    L_m = float(geom["span_m"])
    H_m = float(scenario["bridge_height_m"])
    pga_g = float(scenario["pga_g"])
    n_girders = max(1, int(geom["girder_count"]))

    # TCVN 11823-4 Eq. 4.7.4.4-1 (metric: L and H in meters -> mm)
    # N = (200 + 1.67 * L_m + 6.66 * H_m) * (1 + 0.000125 * S^2)
    zone_mult = 1.5 if pga_g >= 0.15 else 1.0
    n_min_mm = (200.0 + 1.67 * L_m + 6.66 * H_m) * (1.0 + 0.000125 * (skew_deg ** 2)) * zone_mult

    # Conservative shear key force at one abutment/pier line: F_key = As_eff * (W_total / 2)
    dl = analysis["dead_loads_kN_per_m"]
    w_total_bridge_kn_per_m = (dl["stage1_total"] + dl["wearing_surface_and_barriers"]) * n_girders
    w_dead_span_kn = w_total_bridge_kn_per_m * L_m
    as_eff = max(0.10, pga_g * 1.2)  # conservative site amplification factor F_pga=1.2 for L1
    f_key_kn = as_eff * (w_dead_span_kn / 2.0)

    return {
        "screening_level": "L1_GEOMETRIC_AND_CONSERVATIVE_KEY_ONLY",
        "pga_g": round(pga_g, 3),
        "seismic_zone_multiplier": zone_mult,
        "N_min_mm": round(n_min_mm, 1),
        "W_dead_span_kN": round(w_dead_span_kn, 1),
        "As_conservative_g": round(as_eff, 3),
        "F_key_kN": round(f_key_kn, 1),
        "uses_vertical_T1_for_Csm": False,
        "note": (
            "Sàng lọc L1 thuần hình học (N_min theo TCVN 11823-4:4.7.4.4) và lực chốt chống xô "
            "bảo thủ (As·W_dead/2). KHÔNG dùng chu kỳ uốn thẳng đứng T1 để tra phổ ngang Csm; "
            "phân tích phổ phản ứng SPFC bắt buộc thực hiện trong MIDAS Civil L2 với độ cứng gối/trụ."
        ),
    }


def compute_exposure_limits(conc_g: dict[str, Any], scenario: dict[str, Any]) -> dict[str, Any]:
    """Exposure class tension limit & minimum concrete cover."""
    exp_id = str(scenario["exposure_class"]).upper()
    rule = EXPOSURE_RULES.get(exp_id, EXPOSURE_RULES["INLAND_MODERATE"])
    fc_mpa = float(conc_g["fc_MPa"])
    ft_limit_mpa = rule["tension_coef_sqrt_fc"] * math.sqrt(fc_mpa)
    return {
        "exposure_class": exp_id,
        "tension_coef_sqrt_fc": rule["tension_coef_sqrt_fc"],
        "tension_limit_MPa": round(ft_limit_mpa, 3),
        "cover_req_mm": rule["cover_req_mm"],
        "label": rule["label"],
    }


# ---------------------------------------------------------------------------
# 4. Single-Design Evaluation under Scenario + 21-Station Envelopes + RF/SF
# ---------------------------------------------------------------------------
def _evaluate_design_under_scenario(
    model: dict[str, Any],
    scenario: dict[str, Any],
) -> dict[str, Any]:
    state = model["state"]
    geom = model["geom"]
    analysis = model["analysis"]
    conc_g = model["conc_g"]
    conc_d = model["conc_d"]
    rules = model["rules"]
    lp = model["lp"]

    L = float(geom["span_m"])
    sec = geom["section"]
    comp = analysis["composite"]
    ps = analysis["prestress"]
    cap = analysis["capacity"]

    wind = compute_wind_effects(geom, scenario)
    thermal = compute_thermal_effects(geom, analysis, conc_g, conc_d, scenario)
    seismic = compute_seismic_l1_screening(
        geom, analysis, scenario, skew_deg=_safe_float(state["project_inputs"].get("skew_deg"), 0.0)
    )
    exposure = compute_exposure_limits(conc_g, scenario)

    # Effective live-load scaling for scenario (ll_multiplier & im_factor adjustment)
    base_im = float(lp.get("impact_factor", 0.33))
    im_ratio = (1.0 + float(scenario["im_factor"])) / (1.0 + base_im)
    ll_scale = float(scenario["ll_multiplier"]) * im_ratio

    M_dc = float(analysis["moments_kNm"]["stage1"])
    M_dw = float(analysis["moments_kNm"]["dw"])
    M_ll = float(analysis["moments_kNm"]["ll_im"]) * ll_scale
    M_ws_vert = float(wind["w_overturning_ext_girder_kN_per_m"]) * (L ** 2) / 8.0

    V_dc = float(analysis["shears_kN"]["stage1"])
    V_dw = float(analysis["shears_kN"]["dw"])
    V_ll = float(analysis["shears_kN"]["ll_im"]) * ll_scale
    V_ws_vert = float(wind["w_overturning_ext_girder_kN_per_m"]) * L / 2.0

    d_ll_mm = float(analysis["deflection_m"]["ll"]) * ll_scale * 1000.0
    d_limit_mm = (L / float(rules["deflection_limit_span_ratio"])) * 1000.0

    # Section moduli for top and bottom fibers
    h_g = float(sec["depth_m"])
    ts = float(geom["slab_thickness_m"])
    yb_g = float(sec["y_bottom_m"])
    yt_g = max(h_g - yb_g, 1e-6)
    st_girder = float(sec["I_m4"]) / yt_g
    sb_girder = float(comp["Sb_girder"])

    yb_c = float(comp["yb_c"])
    yt_g_comp = max(h_g - yb_c, 1e-6)
    yt_d_comp = max(h_g + ts - yb_c, 1e-6)
    st_girder_comp = float(comp["I_c"]) / yt_g_comp
    st_deck_comp = float(comp["I_c"]) / yt_d_comp
    sb_comp = float(comp["Sb_comp"])
    n_mod = float(comp["n_mod"])

    # Prestress stresses (kPa, compression +)
    Pe = float(ps["Pe_kN"])
    e_g = float(ps["e_m"])
    sigma_pe_bot_kpa = float(ps["sigma_pe_kPa"])
    sigma_pe_top_kpa = Pe / float(sec["area_m2"]) - Pe * e_g / st_girder

    # Strength I & Strength III/V checks (TCVN 11823-3)
    c1 = rules["strength1"]
    c3 = rules["service3"]
    phi_mn = float(rules["phi_flexure"]) * float(cap["Mn_kNm"])
    phi_vn = float(rules["phi_shear"]) * float(cap["Vn_kN"])

    Mu_str1 = c1["DC"] * M_dc + c1["DW"] * M_dw + c1["LL"] * M_ll
    Mu_str5 = c1["DC"] * M_dc + c1["DW"] * M_dw + 1.35 * M_ll + 1.0 * M_ws_vert
    Mu_str3 = c1["DC"] * M_dc + c1["DW"] * M_dw + 1.0 * M_ws_vert
    Mu_gov = max(Mu_str1, Mu_str5, Mu_str3)

    Vu_str1 = c1["DC"] * V_dc + c1["DW"] * V_dw + c1["LL"] * V_ll
    Vu_str5 = c1["DC"] * V_dc + c1["DW"] * V_dw + 1.35 * V_ll + 1.0 * V_ws_vert
    Vu_gov = max(Vu_str1, Vu_str5)

    dc_str1 = Mu_gov / phi_mn if phi_mn > 0 else math.inf
    dc_str2 = Vu_gov / phi_vn if phi_vn > 0 else math.inf

    # SERV-001: Bottom fiber tension under Service III + 0.5*TG (TCVN 11823-3:3.4.1)
    # Positive = compression, Negative = tension
    sigma_tg_bot_mpa = float(thermal["sigma_tg_bot_MPa"])
    sigma_bot_serv3_mpa = (
        sigma_pe_bot_kpa
        - c3["DC"] * (M_dc / sb_girder)
        - (c3["DW"] * M_dw + c3["LL"] * M_ll + 0.3 * M_ws_vert) / sb_comp
    ) / 1000.0 + 0.5 * sigma_tg_bot_mpa
    tension_bot_mpa = max(0.0, -sigma_bot_serv3_mpa)
    ft_lim_mpa = float(exposure["tension_limit_MPa"])
    if ft_lim_mpa > 1e-9:
        dc_serv1 = tension_bot_mpa / ft_lim_mpa
    else:
        # MARINE_SEVERE: 0.0 MPa tension allowed -> any tension > 0 fails (D/C > 1.0)
        dc_serv1 = 0.0 if tension_bot_mpa <= 1e-6 else (1.0 + tension_bot_mpa / max(1.0, 0.25 * math.sqrt(conc_g["fc_MPa"])))

    # SERV-002: Live-load deflection
    dc_serv2 = d_ll_mm / d_limit_mm if d_limit_mm > 0 else math.inf

    # SERV-004: Top fiber compression check (0.45*fc sustained, 0.60*fc total — TCVN 11823-5:5.9.4.2.1)
    fc_g = float(conc_g["fc_MPa"])
    fc_d = float(conc_d["fc_MPa"])
    sigma_top_g_sustained_mpa = (
        sigma_pe_top_kpa + M_dc / st_girder + M_dw / st_girder_comp
    ) / 1000.0
    sigma_top_g_total_mpa = (
        sigma_top_g_sustained_mpa
        + (M_ll + 0.3 * M_ws_vert) / (st_girder_comp * 1000.0)
        + 0.5 * float(thermal["sigma_tg_girder_top_MPa"])
    )
    sigma_top_d_sustained_mpa = (n_mod * M_dw / st_deck_comp) / 1000.0
    sigma_top_d_total_mpa = (
        n_mod * (M_dw + M_ll + 0.3 * M_ws_vert) / (st_deck_comp * 1000.0)
        + 0.5 * float(thermal["sigma_tg_deck_top_MPa"])
    )

    lim_sust_g = 0.45 * fc_g
    lim_tot_g = 0.60 * fc_g
    lim_sust_d = 0.45 * fc_d
    lim_tot_d = 0.60 * fc_d

    dc_serv4_sust = max(
        max(0.0, sigma_top_g_sustained_mpa) / lim_sust_g,
        max(0.0, sigma_top_d_sustained_mpa) / lim_sust_d,
    )
    dc_serv4_tot = max(
        max(0.0, sigma_top_g_total_mpa) / lim_tot_g,
        max(0.0, sigma_top_d_total_mpa) / lim_tot_d,
    )
    dc_serv4 = max(dc_serv4_sust, dc_serv4_tot)

    # Rating Factor (RF) & Global Safety Factor (SF)
    rf_str1 = (phi_mn - c1["DC"] * M_dc - c1["DW"] * M_dw) / max(c1["LL"] * M_ll, 1e-6)
    avail_stress_mpa = (
        (sigma_pe_bot_kpa - c3["DC"] * (M_dc / sb_girder) - c3["DW"] * (M_dw / sb_comp)) / 1000.0
        + 0.5 * sigma_tg_bot_mpa
        + ft_lim_mpa
    )
    ll_stress_serv3_mpa = (c3["LL"] * M_ll / sb_comp) / 1000.0
    rf_serv3 = avail_stress_mpa / max(ll_stress_serv3_mpa, 1e-6)
    rating_factor = min(rf_str1, rf_serv3)
    safety_factor = phi_mn / max(Mu_gov, 1e-6)

    # Analytical limit-state reserve multipliers (λ)
    lam_str1_m = max(0.0, (phi_mn - c1["DC"] * M_dc - c1["DW"] * M_dw) / max(c1["LL"] * M_ll, 1e-6))
    lam_str1_v = max(0.0, (phi_vn - c1["DC"] * V_dc - c1["DW"] * V_dw) / max(c1["LL"] * V_ll, 1e-6))
    lambda_str1 = min(lam_str1_m, lam_str1_v)
    lambda_crack = max(0.0, avail_stress_mpa / max(ll_stress_serv3_mpa, 1e-6))
    lambda_deflect = d_limit_mm / max(d_ll_mm, 1e-6)

    # 21-station longitudinal envelopes (x_m = 0 .. L)
    stations: list[dict[str, float]] = []
    transfer_len_m = 1.5
    for idx in range(_N_STATIONS):
        xi = idx / (_N_STATIONS - 1)
        x_m = xi * L
        # Moment envelope shape: 4*xi*(1-xi) (exact at supports & midspan)
        m_shape = 4.0 * xi * (1.0 - xi)
        # Shear envelope: dead load |1 - 2*xi|, live load max(xi, 1 - xi)
        v_dead_shape = abs(1.0 - 2.0 * xi)
        v_ll_shape = max(xi, 1.0 - xi)
        # Deflection shape (Euler-Bernoulli): 16/5 * xi * (1 - 2*xi^2 + xi^3)
        d_shape = 3.2 * xi * (1.0 - 2.0 * (xi ** 2) + (xi ** 3))
        # Prestress transfer length taper at girder ends
        ps_taper = min(1.0, x_m / transfer_len_m, (L - x_m) / transfer_len_m)

        m_dc_x = M_dc * m_shape
        m_dw_x = M_dw * m_shape
        m_ll_x = M_ll * m_shape
        m_ws_x = M_ws_vert * m_shape
        m_env_x = c1["DC"] * m_dc_x + c1["DW"] * m_dw_x + c1["LL"] * m_ll_x

        v_env_x = c1["DC"] * V_dc * v_dead_shape + c1["DW"] * V_dw * v_dead_shape + c1["LL"] * V_ll * v_ll_shape
        defl_x_mm = d_ll_mm * d_shape

        sig_top_x = (
            ps_taper * sigma_pe_top_kpa
            + m_dc_x / st_girder
            + (m_dw_x + m_ll_x + 0.3 * m_ws_x) / st_girder_comp
        ) / 1000.0 + 0.5 * float(thermal["sigma_tg_girder_top_MPa"])

        sig_bot_x = (
            ps_taper * sigma_pe_bot_kpa
            - c3["DC"] * (m_dc_x / sb_girder)
            - (c3["DW"] * m_dw_x + c3["LL"] * m_ll_x + 0.3 * m_ws_x) / sb_comp
        ) / 1000.0 + 0.5 * sigma_tg_bot_mpa

        stations.append(
            {
                "x_m": round(x_m, 3),
                "M_kNm": round(m_env_x, 1),
                "V_kN": round(v_env_x, 1),
                "deflection_mm": round(defl_x_mm, 2),
                "sigma_top_MPa": round(sig_top_x, 3),
                "sigma_bot_MPa": round(sig_bot_x, 3),
            }
        )

    rule_utils = {
        "STR-001": round(dc_str1, 4),
        "STR-002": round(dc_str2, 4),
        "SERV-001": round(dc_serv1, 4),
        "SERV-002": round(dc_serv2, 4),
        "SERV-004": round(dc_serv4, 4),
    }
    max_dc = max(rule_utils.values())

    # Helper closure for λ sweep
    def _eval_at_lambda(lam: float) -> tuple[float, float]:
        m_ll_l = lam * M_ll
        v_ll_l = lam * V_ll
        d_ll_l = lam * d_ll_mm
        dc1 = max(
            c1["DC"] * M_dc + c1["DW"] * M_dw + c1["LL"] * m_ll_l,
            c1["DC"] * M_dc + c1["DW"] * M_dw + 1.35 * m_ll_l + 1.0 * M_ws_vert,
        ) / max(phi_mn, 1e-6)
        dc2 = (c1["DC"] * V_dc + c1["DW"] * V_dw + c1["LL"] * v_ll_l) / max(phi_vn, 1e-6)
        sig_b = (
            sigma_pe_bot_kpa
            - c3["DC"] * (M_dc / sb_girder)
            - (c3["DW"] * M_dw + c3["LL"] * m_ll_l + 0.3 * M_ws_vert) / sb_comp
        ) / 1000.0 + 0.5 * sigma_tg_bot_mpa
        tens = max(0.0, -sig_b)
        if ft_lim_mpa > 1e-9:
            dcs1 = tens / ft_lim_mpa
        else:
            dcs1 = 0.0 if tens <= 1e-6 else (1.0 + tens / max(1.0, 0.25 * math.sqrt(fc_g)))
        dcs2 = d_ll_l / max(d_limit_mm, 1e-6)
        sig_tg = sigma_top_g_sustained_mpa + (m_ll_l + 0.3 * M_ws_vert) / (st_girder_comp * 1000.0) + 0.5 * float(thermal["sigma_tg_girder_top_MPa"])
        sig_td = n_mod * (M_dw + m_ll_l + 0.3 * M_ws_vert) / (st_deck_comp * 1000.0) + 0.5 * float(thermal["sigma_tg_deck_top_MPa"])
        dcs4 = max(dc_serv4_sust, max(0.0, sig_tg) / lim_tot_g, max(0.0, sig_td) / lim_tot_d)
        return round(max(dc1, dc2, dcs1, dcs2, dcs4), 4), round(d_ll_l, 2)

    box_warning = (
        "L1 1D Flexure/Shear Screening Only — Xoắn St. Venant, vênh mặt cắt và shear lag "
        "(TCVN 11823-4:4.6.2.6) BẮT BUỘC kiểm chứng trong MIDAS Civil L2."
        if model["is_box"]
        else None
    )

    return {
        "result": {
            "family": state["family"],
            "girder_catalog_id": state["design_variables"].get("girder_catalog_id"),
            "span_m": round(L, 2),
            "girder_count": geom["girder_count"],
            "model_source": "SIMPLIFIED_FALLBACK" if model["fallback_used"] else "FULL_L1_SOLVER",
            "box_torsion_warning": box_warning,
            "stations": stations,
            "rating_factor": round(rating_factor, 3),
            "rating_factor_str1": round(rf_str1, 3),
            "rating_factor_serv3": round(rf_serv3, 3),
            "safety_factor": round(safety_factor, 3),
            "lambda_crack": round(lambda_crack, 3),
            "lambda_deflect": round(lambda_deflect, 3),
            "lambda_str1": round(lambda_str1, 3),
            "max_dc": round(max_dc, 4),
            "feasible_l1_scenario": max_dc <= 1.0 + 1e-9,
            "rule_utilizations": rule_utils,
            "serv004": {
                "sigma_top_girder_sustained_MPa": round(sigma_top_g_sustained_mpa, 3),
                "limit_girder_sustained_MPa": round(lim_sust_g, 3),
                "sigma_top_girder_total_MPa": round(sigma_top_g_total_mpa, 3),
                "limit_girder_total_MPa": round(lim_tot_g, 3),
                "sigma_top_deck_sustained_MPa": round(sigma_top_d_sustained_mpa, 3),
                "limit_deck_sustained_MPa": round(lim_sust_d, 3),
                "sigma_top_deck_total_MPa": round(sigma_top_d_total_mpa, 3),
                "limit_deck_total_MPa": round(lim_tot_d, 3),
                "dc_sustained": round(dc_serv4_sust, 4),
                "dc_total": round(dc_serv4_tot, 4),
                "dc": round(dc_serv4, 4),
            },
            "key_responses": {
                "Mu_governing_kNm": round(Mu_gov, 1),
                "phiMn_kNm": round(phi_mn, 1),
                "Vu_governing_kN": round(Vu_gov, 1),
                "phiVn_kN": round(phi_vn, 1),
                "sigma_bot_serv3_MPa": round(sigma_bot_serv3_mpa, 3),
                "tension_limit_MPa": round(ft_lim_mpa, 3),
                "deflection_ll_mm": round(d_ll_mm, 2),
                "deflection_limit_mm": round(d_limit_mm, 2),
                "first_frequency_Hz": round(float(analysis["first_frequency_Hz"]), 3),
            },
            "env_effects": {
                "wind": wind,
                "thermal": thermal,
                "exposure": exposure,
                "seismic_l1": seismic,
            },
        },
        "eval_at_lambda": _eval_at_lambda,
    }


def run_stress_test(
    baseline_state: dict[str, Any],
    ai_state: dict[str, Any],
    scenario: dict[str, Any] | str | None = None,
) -> dict[str, Any]:
    """Run an honest TCVN 11823:2017 L1 stress-test duel between Human Baseline and AI design."""
    scen = resolve_scenario(scenario)
    base_model = _resolve_l1_model(baseline_state)
    ai_model = _resolve_l1_model(ai_state)

    base_eval = _evaluate_design_under_scenario(base_model, scen)
    ai_eval = _evaluate_design_under_scenario(ai_model, scen)

    base_res = base_eval["result"]
    ai_res = ai_eval["result"]

    # Limit-State Reserve Sweep: λ = 0.5 .. 2.5 (step 0.1, 21 points)
    sweep: list[dict[str, float]] = []
    for lam in _SWEEP_LAMBDAS:
        dc_b, defl_b = base_eval["eval_at_lambda"](lam)
        dc_a, defl_a = ai_eval["eval_at_lambda"](lam)
        sweep.append(
            {
                "lam": lam,
                "dc_base": dc_b,
                "dc_ai": dc_a,
                "defl_base_mm": defl_b,
                "defl_ai_mm": defl_a,
            }
        )

    rf_delta = round(ai_res["rating_factor"] - base_res["rating_factor"], 3)
    sf_delta = round(ai_res["safety_factor"] - base_res["safety_factor"], 3)
    winner_rf = "ai" if rf_delta > 1e-6 else ("baseline" if rf_delta < -1e-6 else "tie")

    l2_required = [
        "Phổ phản ứng động đất ngang SPFC (độ cứng gối đàn hồi + trụ + địa chất nền)",
        "Tổ hợp tải trọng không gian 3D (grillage / FEM) và dầm biên",
        "Mất mát DƯL theo giai đoạn thi công, co ngót và từ biến dài hạn",
    ]
    if base_model["is_box"] or ai_model["is_box"]:
        l2_required.insert(0, "Xoắn St. Venant, vênh mặt cắt (warping), méo mặt cắt và shear lag cho dầm hộp")

    return {
        "claim_level": CLAIM_LEVEL,
        "honesty_note": HONESTY_NOTE,
        "scenario_applied": scen,
        "env_effects": {
            "baseline": base_res["env_effects"],
            "ai": ai_res["env_effects"],
            # Top-level quick reference (from AI design or shared bridge-level values)
            "wind": ai_res["env_effects"]["wind"],
            "thermal": ai_res["env_effects"]["thermal"],
            "exposure": ai_res["env_effects"]["exposure"],
            "seismic_l1": ai_res["env_effects"]["seismic_l1"],
        },
        "baseline": base_res,
        "ai": ai_res,
        "sweep": sweep,
        "summary": {
            "sweep_label": "Biên dự trữ theo Trạng thái Giới hạn (Limit-State Reserve Sweep, không phải Pushover phi tuyến)",
            "winner_rf": winner_rf,
            "rf_base": base_res["rating_factor"],
            "rf_ai": ai_res["rating_factor"],
            "rf_delta": rf_delta,
            "sf_base": base_res["safety_factor"],
            "sf_ai": ai_res["safety_factor"],
            "sf_delta": sf_delta,
            "max_dc_base": base_res["max_dc"],
            "max_dc_ai": ai_res["max_dc"],
            "lambda_crack_base": base_res["lambda_crack"],
            "lambda_crack_ai": ai_res["lambda_crack"],
            "lambda_deflect_base": base_res["lambda_deflect"],
            "lambda_deflect_ai": ai_res["lambda_deflect"],
            "lambda_str1_base": base_res["lambda_str1"],
            "lambda_str1_ai": ai_res["lambda_str1"],
            "all_pass_base": base_res["feasible_l1_scenario"],
            "all_pass_ai": ai_res["feasible_l1_scenario"],
            "l2_required_checks": l2_required,
        },
    }


# ---------------------------------------------------------------------------
# 5. L1 vs. MIDAS Civil L2 Validation Comparator + LaTeX / CSV Generator
# ---------------------------------------------------------------------------
_L2_METRIC_SPECS: tuple[tuple[str, str, str], ...] = (
    ("m_max_kNm", "Mô-men uốn lớn nhất $M_{\\max}$", "kN$\\cdot$m"),
    ("sigma_bot_MPa", "Ứng suất thớ dưới $\\sigma_{\\text{bot}}$", "MPa"),
    ("deflection_mm", "Độ võng hoạt tải $\\delta_{\\text{LL}}$", "mm"),
    ("volume_m3", "Thể tích bê tông $V_c$", "m$^3$"),
    ("max_dc", "Tỷ số kiểm tra cực đại $(D/C)_{\\max}$", "--"),
)


def _opt_num(d: Any, key: str) -> float | None:
    if not isinstance(d, dict) or key not in d or d[key] is None or isinstance(d[key], bool):
        return None
    try:
        val = float(d[key])
        return val if math.isfinite(val) else None
    except (TypeError, ValueError):
        return None


def _pct_delta(num: float | None, ref: float | None) -> float | None:
    if num is None or ref is None or abs(ref) < 1e-9:
        return None
    return round(((num - ref) / abs(ref)) * 100.0, 2)


def _fmt_num(val: float | None, signed: bool = False) -> str:
    if val is None:
        return "--"
    return f"{val:+.2f}" if signed else f"{val:.2f}"


def compare_l2_validation(payload: dict[str, Any]) -> dict[str, Any]:
    """Compare L1 screening vs. MIDAS Civil L2 results for Human Baseline and AI designs.

    Accepts ``{l1_baseline, l1_ai, l2_baseline, l2_ai}`` with optional numeric fields:
    ``m_max_kNm``, ``sigma_bot_MPa``, ``deflection_mm``, ``volume_m3``, ``max_dc``.
    """
    payload = payload if isinstance(payload, dict) else {}
    l1_b = payload.get("l1_baseline") or {}
    l1_a = payload.get("l1_ai") or {}
    l2_b = payload.get("l2_baseline") or {}
    l2_a = payload.get("l2_ai") or {}

    metrics: list[dict[str, Any]] = []
    l1_l2_errors: list[float] = []
    has_l2_data = False

    for key, latex_label, unit_latex in _L2_METRIC_SPECS:
        v_l1_b = _opt_num(l1_b, key)
        v_l1_a = _opt_num(l1_a, key)
        v_l2_b = _opt_num(l2_b, key)
        v_l2_a = _opt_num(l2_a, key)

        if v_l2_b is not None or v_l2_a is not None:
            has_l2_data = True

        err_b = _pct_delta(v_l1_b, v_l2_b)
        err_a = _pct_delta(v_l1_a, v_l2_a)
        delta_l1 = _pct_delta(v_l1_a, v_l1_b)
        delta_l2 = _pct_delta(v_l2_a, v_l2_b)

        if err_b is not None:
            l1_l2_errors.append(abs(err_b))
        if err_a is not None:
            l1_l2_errors.append(abs(err_a))

        metrics.append(
            {
                "metric": key,
                "label": latex_label,
                "unit": unit_latex,
                "l1_baseline": v_l1_b,
                "l1_ai": v_l1_a,
                "l2_baseline": v_l2_b,
                "l2_ai": v_l2_a,
                "l1_vs_l2_err_baseline_pct": err_b,
                "l1_vs_l2_err_ai_pct": err_a,
                "human_vs_ai_l1_delta_pct": delta_l1,
                "human_vs_ai_l2_delta_pct": delta_l2,
            }
        )

    max_err = round(max(l1_l2_errors), 2) if l1_l2_errors else None
    within_5pct = (max_err <= 5.0) if max_err is not None else None

    # Build booktabs LaTeX table
    latex_lines = [
        r"\begin{table}[htbp]",
        r"\centering",
        r"\caption{Đối chứng kết quả phân tích L1 và MIDAS Civil L2 giữa Phương án Gốc (Human) và AI}",
        r"\label{tab:l1_l2_validation}",
        r"\begin{tabular}{lccccccc}",
        r"\toprule",
        r"Chỉ tiêu & Đơn vị & L1 Base & L2 Base & Sai số Base (\%) & L1 AI & L2 AI & $\Delta$ AI/Base L2 (\%) \\",
        r"\midrule",
    ]
    for row in metrics:
        latex_lines.append(
            f"{row['label']} & {row['unit']} & "
            f"{_fmt_num(row['l1_baseline'])} & {_fmt_num(row['l2_baseline'])} & "
            f"{_fmt_num(row['l1_vs_l2_err_baseline_pct'], signed=True)} & "
            f"{_fmt_num(row['l1_ai'])} & {_fmt_num(row['l2_ai'])} & "
            f"{_fmt_num(row['human_vs_ai_l2_delta_pct'], signed=True)} \\\\"
        )
    latex_lines.extend(
        [
            r"\bottomrule",
            r"\end{tabular}",
            r"\end{table}",
        ]
    )
    latex_table = "\n".join(latex_lines)

    # Build CSV text
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(
        [
            "metric",
            "l1_baseline",
            "l2_baseline",
            "l1_vs_l2_err_baseline_pct",
            "l1_ai",
            "l2_ai",
            "l1_vs_l2_err_ai_pct",
            "human_vs_ai_l1_delta_pct",
            "human_vs_ai_l2_delta_pct",
        ]
    )
    for row in metrics:
        writer.writerow(
            [
                row["metric"],
                "" if row["l1_baseline"] is None else row["l1_baseline"],
                "" if row["l2_baseline"] is None else row["l2_baseline"],
                "" if row["l1_vs_l2_err_baseline_pct"] is None else row["l1_vs_l2_err_baseline_pct"],
                "" if row["l1_ai"] is None else row["l1_ai"],
                "" if row["l2_ai"] is None else row["l2_ai"],
                "" if row["l1_vs_l2_err_ai_pct"] is None else row["l1_vs_l2_err_ai_pct"],
                "" if row["human_vs_ai_l1_delta_pct"] is None else row["human_vs_ai_l1_delta_pct"],
                "" if row["human_vs_ai_l2_delta_pct"] is None else row["human_vs_ai_l2_delta_pct"],
            ]
        )

    return {
        "claim_level": "L2_CROSS_CHECKED" if has_l2_data else "L2_COMPARISON_PENDING",
        "has_l2_data": has_l2_data,
        "max_l1_l2_error_pct": max_err,
        "within_5pct_target": within_5pct,
        "metrics": metrics,
        "latex_table": latex_table,
        "csv_text": buf.getvalue(),
    }
