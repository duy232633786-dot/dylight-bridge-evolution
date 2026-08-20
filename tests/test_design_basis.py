"""Kiểm thử hợp đồng schema Design Basis và Site-Hazard Profile."""
import json
from pathlib import Path
import jsonschema
import pytest

from bridge_evolution import CONTRACTS_DIR


def _load_schema(name: str) -> dict:
    with open(CONTRACTS_DIR / name, encoding="utf-8") as f:
        return json.load(f)


def test_design_basis_schema_valid():
    schema = _load_schema("design_basis.schema.json")
    valid_db = {
        "schema_version": "1.0",
        "project_id": "VN-BRIDGE-2026-01",
        "bridge_name": "Cầu Vượt Sông Hồng Tham Số",
        "governing_standard": {
            "code": "TCVN_11823",
            "version": "2017",
            "jurisdiction": "Vietnam",
        },
        "design_life_years": 100,
        "exposure_class": "INLAND_MILD",
        "units": {
            "length": "m",
            "force": "kN",
            "stress": "MPa",
            "mass": "tonne",
            "temperature": "celsius",
        },
        "geometry_constraints": {
            "span_length_m": 38.3,
            "deck_width_m": 12.0,
            "vertical_clearance_m": 5.5,
            "skew_angle_deg": 0.0,
        },
        "load_requirements": {
            "live_load_model": "TCVN_HL93",
            "impact_percentage": 33.0,
            "pedestrian_load_kPa": 3.0,
        },
        "materials_policy": {
          "allowed_concrete_grades": ["C40", "C45", "C50"],
          "allowed_prestress_types": ["PS-15.2-1860"],
          "max_aggregate_size_mm": 20.0,
        },
    }

    validator = jsonschema.Draft202012Validator(schema)
    errors = list(validator.iter_errors(valid_db))
    assert errors == []


def test_site_hazard_profile_schema_valid():
    schema = _load_schema("site_hazard_profile.schema.json")
    valid_site = {
        "schema_version": "1.0",
        "site_id": "SITE-HANOI-01",
        "geographic_location": {
            "latitude": 21.0285,
            "longitude": 105.8542,
            "terrain_category": "B_SUBURBAN",
        },
        "seismic_hazard": {
            "pga_g": 0.12,
            "site_class": "D_STIFF_SOIL",
            "seismic_performance_zone": 2,
        },
        "wind_hazard": {
            "basic_wind_speed_m_s": 40.0,
            "gust_effect_factor": 1.15,
            "aerodynamic_risk_level": "LOW",
        },
        "hydrology_scour": {
            "design_flood_frequency_years": 100,
            "estimated_scour_depth_m": 2.5,
            "tidal_range_m": 0.0,
        },
        "geotechnical_category": "DEEP_ALLUVIAL",
    }

    validator = jsonschema.Draft202012Validator(schema)
    errors = list(validator.iter_errors(valid_site))
    assert errors == []
