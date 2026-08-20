"""Mục tiêu tối ưu (minimize): chi phí tương đối, khối lượng vật liệu, carbon.

An toàn KHÔNG nằm ở đây — mọi điều kiện cường độ/sử dụng/cấu tạo là hard
constraint trong verifier, không được đánh đổi lấy chi phí.
"""
from .catalogs import load_catalogs


def diaphragm_concrete_volume_m3(state: dict, geom: dict, cat: dict | None = None) -> float:
    """Thể tích toàn bộ dầm ngang, dùng chung cho tải trọng và mục tiêu.

    Giữ phép tính tại một nơi để tự trọng mà solver đưa vào DC luôn khớp với
    lượng bê tông được tính vào khối lượng/chi phí/carbon.
    """
    cat = cat or load_catalogs()
    dv = state["design_variables"]
    cm = cat["cost_model"]
    dia = cat["diaphragm_layouts"][dv["diaphragm_layout_id"]]
    dia_geo = cat["diaphragm_layouts"]["_geometry"]
    sec = geom["section"]
    n, S = geom["girder_count"], geom["spacing_m"]
    bay_width = max(0.3, S - cm["diaphragm_bay_clear_width_offset_m"])
    return (dia["rows"] * (n - 1) * bay_width
            * dia_geo["depth_ratio_of_girder"] * sec["depth_m"]
            * dia_geo["thickness_m"])


def compute_objectives(state: dict, geom: dict) -> dict:
    cat = load_catalogs()
    cm = cat["cost_model"]
    dv, mats = state["design_variables"], state["materials"]
    sec = geom["section"]
    L, ts, n, B = (geom["span_m"], geom["slab_thickness_m"],
                   geom["girder_count"], geom["deck_width_m"])

    conc_g = cat["concretes"][mats["girder_concrete_id"]]
    conc_d = cat["concretes"][mats["deck_concrete_id"]]
    ps = cat["prestressing_steels"][mats["prestressing_steel_id"]]
    pt = cat["prestress_layouts"][dv["prestress_layout_id"]]
    dia_geo = cat["diaphragm_layouts"]["_geometry"]
    conc_dia = cat["concretes"][dia_geo["concrete_id"]]

    # ---- khối lượng bê tông (m³)
    vol_girders = n * sec["area_m2"] * L
    vol_deck = B * ts * L
    vol_dia = diaphragm_concrete_volume_m3(state, geom, cat)

    # ---- cáp DƯL (tấn)
    strand_len = L + cm["strand_extra_length_m"]
    strand_mass_t = n * pt["strand_count"] * strand_len * ps["unit_mass_kg_per_m"] / 1000.0

    mass_t = (vol_girders * conc_g["density_kg_m3"]
              + vol_deck * conc_d["density_kg_m3"]
              + vol_dia * conc_dia["density_kg_m3"]) / 1000.0 + strand_mass_t

    cost = (vol_girders * conc_g["unit_cost_per_m3"]
            + vol_deck * conc_d["unit_cost_per_m3"]
            + vol_dia * conc_dia["unit_cost_per_m3"]
            + strand_mass_t * ps["unit_cost_per_tonne"]
            + n * cm["fixed_cost_per_girder"])

    carbon = (vol_girders * conc_g["carbon_kgCO2e_per_m3"]
              + vol_deck * conc_d["carbon_kgCO2e_per_m3"]
              + vol_dia * conc_dia["carbon_kgCO2e_per_m3"]
              + strand_mass_t * ps["carbon_kgCO2e_per_tonne"])

    return {
        "relative_cost": round(cost, 2),
        "material_mass_t": round(mass_t, 2),
        "embodied_carbon_kgCO2e": round(carbon, 1),
    }


OBJECTIVE_KEYS = ("relative_cost", "material_mass_t", "embodied_carbon_kgCO2e")


def objectives_tuple(obj: dict) -> tuple:
    return tuple(obj[k] for k in OBJECTIVE_KEYS)
