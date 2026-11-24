"""Single-Source-of-Truth Bridge Interchange & MIDAS Civil .mct Load Exporter (P0).

Sinh đồng bộ 3 artifact từ cùng một phương án thiết kế và kịch bản môi trường:
  1. ``bridge_interchange_v1`` (JSON, ``schema: "bridge_interchange/1.0"``, kèm SHA-256)
  2. ``mct_text`` — kịch bản tải trọng và tổ hợp MIDAS Civil đầy đủ:
     ``*STLDCASE``, ``*SELFWEIGHT``, ``*BEAMLOAD``, ``*TEMPER``, ``*BSTEMP``,
     ``*SPFC``, ``*LOADCOMB`` (``STR_I``, ``STR_III``, ``STR_V``, ``SERV_I``,
     ``SERV_III``, ``EXT_I``).
  3. ``dynamo_csv`` — bảng tọa độ & đặc trưng 21 trạm dọc nhịp cho Revit/Dynamo.

Lưu ý trung thực khoa học:
  - Phổ phản ứng ``*SPFC`` xuất kèm để kỹ sư nạp vào mô hình L2 (MIDAS Civil)
    nơi có đủ độ cứng gối đàn hồi, trụ và địa chất nền. L1 không dùng T1 đứng
    để tính Csm ngang.
  - Khối MCT tải trọng tuân theo cú pháp bảng chuẩn MIDAS Civil (đơn vị kN, m, C).
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from typing import Any

from .physics_sim import (
    CLAIM_LEVEL,
    _resolve_l1_model,
    compute_exposure_limits,
    compute_seismic_l1_screening,
    compute_thermal_effects,
    compute_wind_effects,
    resolve_scenario,
)

INTERCHANGE_SCHEMA = "bridge_interchange/1.0"
_SAFE_LABEL_RE = re.compile(r"[^A-Za-z0-9_\-]+")
_REF_TEMP_C = 20.0
_N_STATIONS = 21


def _sanitize_label(raw: Any) -> str:
    if not isinstance(raw, str) or not raw.strip():
        return "BRIDGE_DESIGN"
    cleaned = _SAFE_LABEL_RE.sub("_", raw.strip()).strip("_")
    return (cleaned or "BRIDGE_DESIGN")[:48]


def _canonical_sha256(obj: dict[str, Any]) -> str:
    encoded = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _tcvn_spfc_points(pga_g: float) -> list[tuple[float, float]]:
    """Generate TCVN 11823-3 / TCVN 9386 horizontal design spectrum (T_s, Sa_g) for MIDAS *SPFC.

    Uses standard Soil Class II / Type 1 spectral shape (S=1.2, Tb=0.15s, Tc=0.50s, Td=2.0s)
    scaled by PGA (g) for L2 modal analysis in MIDAS Civil.
    """
    ag = max(0.02, float(pga_g))
    s_soil = 1.2
    tb, tc, td = 0.15, 0.50, 2.00
    eta = 1.0  # 5% damping
    periods = (0.0, 0.05, 0.10, 0.15, 0.30, 0.50, 0.75, 1.00, 1.50, 2.00, 3.00, 4.00)
    pts: list[tuple[float, float]] = []
    for t in periods:
        if t < tb:
            sa = ag * s_soil * (1.0 + (t / tb) * (2.5 * eta - 1.0))
        elif t <= tc:
            sa = ag * s_soil * 2.5 * eta
        elif t <= td:
            sa = ag * s_soil * 2.5 * eta * (tc / t)
        else:
            sa = ag * s_soil * 2.5 * eta * (tc * td / (t * t))
        pts.append((round(t, 3), round(sa, 4)))
    return pts


def _build_mct_text(
    *,
    label: str,
    sha256_hex: str,
    geom: dict[str, Any],
    analysis: dict[str, Any],
    conc_g: dict[str, Any],
    scenario: dict[str, Any],
    wind: dict[str, Any],
    thermal: dict[str, Any],
    seismic: dict[str, Any],
    exposure: dict[str, Any],
) -> str:
    """Build complete MIDAS Civil .mct load, thermal, spectrum, and load combination script."""
    L = float(geom["span_m"])
    n_elem = _N_STATIONS - 1  # 20 beam elements along 21 nodes (1..21)
    elem_range = f"1to{n_elem}"

    dl = analysis["dead_loads_kN_per_m"]
    w_dc_super = round(dl["deck"] + dl["diaphragm_smeared"] + dl["misc"], 3)
    w_dw = round(dl["wearing_surface_and_barriers"], 3)
    w_ws_lat = round(wind["w_WS_kN_per_m"], 3)
    w_wl_lat = round(wind["w_WL_kN_per_m"], 3)
    w_ws_vert = round(wind["w_overturning_ext_girder_kN_per_m"], 3)

    dt_pos = round(max(1.0, float(scenario["temp_max_c"]) - _REF_TEMP_C), 2)
    dt_neg = round(min(-1.0, float(scenario["temp_min_c"]) - _REF_TEMP_C), 2)
    t1 = round(float(scenario["tg_t1_c"]), 2)
    t2 = round(float(scenario["tg_t2_c"]), 2)
    # Negative gradient per TCVN 11823-3:3.12.3 (-0.30 * positive gradient for plain concrete deck)
    t1_neg = round(-0.30 * t1, 2)
    t2_neg = round(-0.30 * t2, 2)

    h_tot = round(geom["section"]["depth_m"] + geom["slab_thickness_m"], 3)
    b_top = round(geom["section"]["top_flange_width_m"], 3)
    spfc_pts = _tcvn_spfc_points(float(scenario["pga_g"]))

    lines: list[str] = [
        "; ============================================================================",
        f"; DYLIGHT Bridge Evolution — MIDAS Civil Load & Combination Script (.mct)",
        f"; Schema       : {INTERCHANGE_SCHEMA}",
        f"; Label        : {label}",
        f"; SHA-256      : {sha256_hex}",
        f"; Claim Level  : {CLAIM_LEVEL}",
        f"; Scenario     : {scenario.get('id', 'CUSTOM')} ({scenario.get('name', '')})",
        f"; Span / Width : L = {L:.2f} m, B = {geom['deck_width_m']:.2f} m, n = {geom['girder_count']}",
        f"; Exposure     : {exposure['exposure_class']} (ft_lim = {exposure['tension_limit_MPa']} MPa, cover >= {exposure['cover_req_mm']} mm)",
        f"; EQ L1 Screen : N_min = {seismic['N_min_mm']} mm, F_key = {seismic['F_key_kN']} kN (SPFC below is for L2 modal analysis)",
        "; ============================================================================",
        "*UNIT    ; Force, Length, Heat, Temp",
        "   KN, M, KJ, C",
        "",
        "*STLDCASE    ; Static Load Cases",
        "; LCNAME, LCTYPE, DESC",
        "   DC, D, Dead load of structural components (girder + deck + diaphragm)",
        "   DW, DW, Dead load of wearing surface and barriers",
        "   LL, L, HL-93 vehicular live load (apply via Moving Load Tracer in L2)",
        "   WS, W, Wind load on structure (TCVN 11823-3:3.8.1)",
        "   WL, WL, Wind on live load (TCVN 11823-3:3.8.1.3)",
        "   TU_POS, T, Uniform temperature rise (+DeltaT)",
        "   TU_NEG, T, Uniform temperature fall (-DeltaT)",
        "   TG_POS, T, Positive vertical temperature gradient (TCVN 11823-3:3.12.3)",
        "   TG_NEG, T, Negative vertical temperature gradient (-0.30 x positive)",
        "   PS, PS, Prestressing tendon primary/secondary effects",
        "",
        "*USE-STLD, DC",
        "*SELFWEIGHT    ; Self Weight (girder self-weight via section * gamma_c)",
        "; X, Y, Z, GROUP",
        "   0, 0, -1, ",
        "",
        "*BEAMLOAD    ; Superimposed Stage-1 DC (deck slab + diaphragm + misc) [kN/m]",
        "; ELEM_LIST, CMD, TYPE, DIR, bPROJ, bECCEN, ECCDIR, I-END, J-END, bJ, D1, P1, D2, P2, D3, P3, D4, P4, GROUP",
        f"   {elem_range}, BEAM, UNILOAD, GZ, NO, NO, aDir[1], , , , 0, {-w_dc_super:.3f}, 1, {-w_dc_super:.3f}, 0, 0, 0, 0, ",
        "",
        "*USE-STLD, DW",
        "*BEAMLOAD    ; Wearing Surface + Barriers DW [kN/m]",
        f"   {elem_range}, BEAM, UNILOAD, GZ, NO, NO, aDir[1], , , , 0, {-w_dw:.3f}, 1, {-w_dw:.3f}, 0, 0, 0, 0, ",
        "",
        "*USE-STLD, WS",
        "*BEAMLOAD    ; Lateral Wind on Structure WS (GY) & Exterior Girder Overturning (GZ) [kN/m]",
        f"   {elem_range}, BEAM, UNILOAD, GY, NO, NO, aDir[1], , , , 0, {w_ws_lat:.3f}, 1, {w_ws_lat:.3f}, 0, 0, 0, 0, ",
    ]
    if abs(w_ws_vert) > 1e-6:
        lines.append(
            f"   {elem_range}, BEAM, UNILOAD, GZ, NO, NO, aDir[1], , , , 0, {-w_ws_vert:.3f}, 1, {-w_ws_vert:.3f}, 0, 0, 0, 0, "
        )

    lines.extend(
        [
            "",
            "*USE-STLD, WL",
            "*BEAMLOAD    ; Lateral Wind on Live Load WL (GY) [kN/m]",
            f"   {elem_range}, BEAM, UNILOAD, GY, NO, NO, aDir[1], , , , 0, {w_wl_lat:.3f}, 1, {w_wl_lat:.3f}, 0, 0, 0, 0, ",
            "",
            "*USE-STLD, TU_POS",
            "*TEMPER    ; Uniform Temperature Rise (+DeltaT from T_ref=20C)",
            "; ELEM_LIST, TEMPER, GROUP",
            f"   {elem_range}, {dt_pos:.2f}, ",
            "",
            "*USE-STLD, TU_NEG",
            "*TEMPER    ; Uniform Temperature Fall (-DeltaT from T_ref=20C)",
            f"   {elem_range}, {dt_neg:.2f}, ",
            "",
            "*USE-STLD, TG_POS",
            "*BSTEMP    ; Positive Beam Section Temperature Gradient (TCVN 11823-3:3.12.3)",
            "; ELEM_LIST, DIR, REF, B, H1, T1, H2, T2, GROUP",
            f"   {elem_range}, LZ, TOP, {b_top:.3f}, 0.000, {t1:.2f}, 0.100, {t2:.2f}, ",
            f"   {elem_range}, LZ, TOP, {b_top:.3f}, 0.100, {t2:.2f}, 0.400, 0.00, ",
            "",
            "*USE-STLD, TG_NEG",
            "*BSTEMP    ; Negative Beam Section Temperature Gradient (-0.30 x Positive)",
            f"   {elem_range}, LZ, TOP, {b_top:.3f}, 0.000, {t1_neg:.2f}, 0.100, {t2_neg:.2f}, ",
            f"   {elem_range}, LZ, TOP, {b_top:.3f}, 0.100, {t2_neg:.2f}, 0.400, 0.00, ",
            "",
            "*SPFC    ; Horizontal Response Spectrum (TCVN 11823-3 / TCVN 9386) — FOR L2 MODAL ANALYSIS",
            f"; PGA = {scenario['pga_g']:.3f} g, Soil Class II (S=1.2, Tb=0.15s, Tc=0.50s, Td=2.00s, damping=5%)",
            "; NAME, TYPE, SCALE, GRAV, DAMP, DESC",
            f"   NAME=TCVN_SPFC_{label[:16]}, ACC, 1.0, 9.81, 0.05, TCVN 11823 L2 Horizontal Spectrum (PGA={scenario['pga_g']:.3f}g)",
            "; PERIOD(sec), VALUE(g)",
        ]
    )
    for t_s, sa_g in spfc_pts:
        lines.append(f"   {t_s:.3f}, {sa_g:.4f}")

    ll_mult = round(float(scenario["ll_multiplier"]), 3)
    f_ll_str1 = round(1.75 * ll_mult, 3)
    f_ll_str5 = round(1.35 * ll_mult, 3)
    f_ll_serv1 = round(1.00 * ll_mult, 3)
    f_ll_serv3 = round(0.80 * ll_mult, 3)
    f_ll_ext1 = round(0.50 * ll_mult, 3)

    lines.extend(
        [
            "",
            "*LOADCOMB    ; TCVN 11823-3:2017 Table 3.4.1-1 Load Combinations",
            "; NAME=NAME, KIND, ACTIVE, bES, iTYPE, DESC",
            ";   ANAL, LCNAME, FACTOR, ...",
            f"   NAME=STR_I, GEN, ACTIVE, 0, 0, Strength I (TCVN 11823-3, LL_mult={ll_mult})",
            f"   ST, DC, 1.25, ST, DW, 1.50, ST, LL, {f_ll_str1:.3f}, ST, PS, 1.00, ST, TU_POS, 0.50",
            "   NAME=STR_III, GEN, ACTIVE, 0, 0, Strength III (High Wind WS, no LL)",
            "   ST, DC, 1.25, ST, DW, 1.50, ST, WS, 1.40, ST, PS, 1.00, ST, TU_POS, 0.50",
            f"   NAME=STR_V, GEN, ACTIVE, 0, 0, Strength V (Normal Wind WS+WL with LL)",
            f"   ST, DC, 1.25, ST, DW, 1.50, ST, LL, {f_ll_str5:.3f}, ST, WS, 0.40, ST, WL, 1.00, ST, PS, 1.00",
            f"   NAME=SERV_I, GEN, ACTIVE, 0, 0, Service I (Compression & Deflection)",
            f"   ST, DC, 1.00, ST, DW, 1.00, ST, LL, {f_ll_serv1:.3f}, ST, WS, 0.30, ST, WL, 1.00, ST, PS, 1.00, ST, TU_POS, 1.00, ST, TG_POS, 0.50",
            f"   NAME=SERV_III, GEN, ACTIVE, 0, 0, Service III (PSC Bottom Tension Check)",
            f"   ST, DC, 1.00, ST, DW, 1.00, ST, LL, {f_ll_serv3:.3f}, ST, WS, 0.30, ST, PS, 1.00, ST, TU_POS, 1.00, ST, TG_POS, 0.50",
            f"   NAME=EXT_I, GEN, ACTIVE, 0, 0, Extreme Event I (Seismic EQ — attach L2 RS case in MIDAS)",
            f"   ST, DC, 1.25, ST, DW, 1.50, ST, LL, {f_ll_ext1:.3f}, ST, PS, 1.00",
            f"; NOTE: Total composite depth H_tot = {h_tot:.3f} m, fc_girder = {conc_g['fc_MPa']} MPa.",
            "; END OF MCT SCRIPT",
        ]
    )
    return "\n".join(lines) + "\n"


def _build_dynamo_csv(
    geom: dict[str, Any],
    analysis: dict[str, Any],
    pt: dict[str, Any],
    wind: dict[str, Any],
) -> tuple[str, list[dict[str, float]]]:
    """Generate 21-station CSV table for Revit/Dynamo parametric bridge geometry."""
    L = float(geom["span_m"])
    sec = geom["section"]
    dl = analysis["dead_loads_kN_per_m"]
    w_dc = round(dl["stage1_total"], 3)
    w_dw = round(dl["wearing_surface_and_barriers"], 3)
    w_ws = round(wind["w_WS_kN_per_m"], 3)
    strands = int(pt["strand_count"])

    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(
        [
            "station_idx",
            "x_m",
            "y_m",
            "z_m",
            "girder_depth_m",
            "top_flange_width_m",
            "slab_thickness_m",
            "deck_width_m",
            "girder_count",
            "spacing_m",
            "section_area_m2",
            "I_m4",
            "prestress_strands",
            "w_dc_kN_m",
            "w_dw_kN_m",
            "w_ws_kN_m",
        ]
    )

    stations_json: list[dict[str, float]] = []
    for idx in range(_N_STATIONS):
        xi = idx / (_N_STATIONS - 1)
        x_m = round(xi * L, 4)
        row = [
            idx,
            x_m,
            0.0,
            0.0,
            round(float(sec["depth_m"]), 4),
            round(float(sec["top_flange_width_m"]), 4),
            round(float(geom["slab_thickness_m"]), 4),
            round(float(geom["deck_width_m"]), 4),
            int(geom["girder_count"]),
            round(float(geom["spacing_m"]), 4),
            round(float(sec["area_m2"]), 5),
            round(float(sec["I_m4"]), 6),
            strands,
            w_dc,
            w_dw,
            w_ws,
        ]
        writer.writerow(row)
        stations_json.append(
            {
                "station_idx": idx,
                "x_m": x_m,
                "y_m": 0.0,
                "z_m": 0.0,
                "girder_depth_m": round(float(sec["depth_m"]), 4),
                "slab_thickness_m": round(float(geom["slab_thickness_m"]), 4),
            }
        )

    return buf.getvalue(), stations_json


def build_interchange_bundle(payload: dict[str, Any]) -> dict[str, Any]:
    """Build Single-Source-of-Truth bridge_interchange_v1 JSON, MIDAS .mct, and Dynamo .csv.

    Accepts ``{report_or_state, scenario, label}`` (and aliases ``state`` / ``report``).
    """
    payload = payload if isinstance(payload, dict) else {}
    raw_source = (
        payload.get("report_or_state")
        if payload.get("report_or_state") is not None
        else (
            payload.get("state")
            if payload.get("state") is not None
            else (
                payload.get("report")
                if payload.get("report") is not None
                else payload
            )
        )
    )
    label = _sanitize_label(payload.get("label") or payload.get("name") or "BRIDGE_DESIGN")
    scenario = resolve_scenario(payload.get("scenario"))

    model = _resolve_l1_model(raw_source)
    state = model["state"]
    geom = model["geom"]
    analysis = model["analysis"]
    conc_g = model["conc_g"]
    conc_d = model["conc_d"]
    pt = model["pt"]

    wind = compute_wind_effects(geom, scenario)
    thermal = compute_thermal_effects(geom, analysis, conc_g, conc_d, scenario)
    seismic = compute_seismic_l1_screening(
        geom,
        analysis,
        scenario,
        skew_deg=float(state["project_inputs"].get("skew_deg", 0.0) or 0.0),
    )
    exposure = compute_exposure_limits(conc_g, scenario)
    dynamo_csv, stations_json = _build_dynamo_csv(geom, analysis, pt, wind)

    sec = geom["section"]
    interchange_core: dict[str, Any] = {
        "schema": INTERCHANGE_SCHEMA,
        "label": label,
        "claim_level": CLAIM_LEVEL,
        "family": state["family"],
        "geometry": {
            "span_m": round(float(geom["span_m"]), 3),
            "deck_width_m": round(float(geom["deck_width_m"]), 3),
            "girder_count": int(geom["girder_count"]),
            "spacing_m": round(float(geom["spacing_m"]), 4),
            "slab_thickness_m": round(float(geom["slab_thickness_m"]), 4),
            "overhang_m": round(float(geom["overhang_m"]), 4),
            "section": {
                "depth_m": round(float(sec["depth_m"]), 4),
                "area_m2": round(float(sec["area_m2"]), 5),
                "I_m4": round(float(sec["I_m4"]), 6),
                "y_bottom_m": round(float(sec["y_bottom_m"]), 4),
                "top_flange_width_m": round(float(sec["top_flange_width_m"]), 4),
                "web_width_total_m": round(float(sec["web_width_total_m"]), 4),
            },
            "design_variables": dict(state["design_variables"]),
        },
        "materials": {
            "girder_concrete_id": state["materials"]["girder_concrete_id"],
            "girder_concrete": {
                "fc_MPa": conc_g["fc_MPa"],
                "E_GPa": conc_g["E_GPa"],
                "density_kg_m3": conc_g["density_kg_m3"],
            },
            "deck_concrete_id": state["materials"]["deck_concrete_id"],
            "deck_concrete": {
                "fc_MPa": conc_d["fc_MPa"],
                "E_GPa": conc_d["E_GPa"],
                "density_kg_m3": conc_d["density_kg_m3"],
            },
            "prestressing_steel_id": state["materials"]["prestressing_steel_id"],
            "prestress_layout_id": state["design_variables"]["prestress_layout_id"],
            "strand_count": pt["strand_count"],
            "strand_centroid_from_bottom_m": pt["centroid_from_bottom_m"],
        },
        "scenario": scenario,
        "loads_summary": {
            "dead_loads_kN_per_m": {
                k: round(float(v), 3) for k, v in analysis["dead_loads_kN_per_m"].items()
            },
            "wind": wind,
            "thermal": thermal,
            "exposure": exposure,
            "seismic_l1": seismic,
        },
        "stations": stations_json,
    }

    digest = _canonical_sha256(interchange_core)
    bridge_interchange_v1 = {
        "schema": INTERCHANGE_SCHEMA,
        "sha256": digest,
        **{k: v for k, v in interchange_core.items() if k != "schema"},
    }

    mct_text = _build_mct_text(
        label=label,
        sha256_hex=digest,
        geom=geom,
        analysis=analysis,
        conc_g=conc_g,
        scenario=scenario,
        wind=wind,
        thermal=thermal,
        seismic=seismic,
        exposure=exposure,
    )

    return {
        "schema": INTERCHANGE_SCHEMA,
        "sha256": digest,
        "label": label,
        "claim_level": CLAIM_LEVEL,
        "bridge_interchange_v1": bridge_interchange_v1,
        "mct_text": mct_text,
        "dynamo_csv": dynamo_csv,
        "filenames": {
            "interchange_json": f"{label}_bridge_interchange_v1.json",
            "midas_mct": f"{label}_midas_loads.mct",
            "dynamo_csv": f"{label}_dynamo_stations.csv",
        },
    }
