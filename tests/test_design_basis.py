"""Kiểm thử hợp đồng schema Design Basis và Site-Hazard Profile.

Ngoài kiểm thử schema thuần túy, file này biến hai tài liệu G0 trong
``docs/design_basis/`` thành RÀNG BUỘC THẬT:

* mọi giá trị ``KNOWN`` trong design basis phải khớp đúng những gì runtime
  (``bridge_grammar/*.json`` + ``catalogs/catalogs.json``) thực sự dùng;
* mọi ô trống phải nói rõ cái gì sẽ lấp nó (``resolution_path``) hoặc vì sao nó
  không áp dụng (``not_applicable_reason``);
* hồ sơ vị trí phải ở trạng thái RỖNG CÓ CHỦ ĐÍCH — không được điền bừa một
  tọa độ, một vùng động đất hay một vận tốc gió nào cho "đủ".
"""
import copy
import json
import sys
from pathlib import Path

import jsonschema
import pytest

from bridge_evolution import CATALOGS_DIR, CONTRACTS_DIR, GRAMMAR_DIR
from bridge_evolution.evaluate import (
    COMPONENT_AUDIT_REGISTRY,
    build_component_audit,
    evaluate_candidate,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
DESIGN_BASIS_DIR = REPO_ROOT / "docs" / "design_basis"
DESIGN_BASIS_INSTANCE = DESIGN_BASIS_DIR / "DB-SUPERT-38M.json"
SITE_PROFILE_INSTANCE = DESIGN_BASIS_DIR / "SITE-UNSPECIFIED.json"

EVIDENCE_STATUSES = {"KNOWN", "UNKNOWN", "NOT_APPLICABLE"}

#: Các khối trong site profile chứa dữ liệu vị trí/hazard — repo KHÔNG có dữ
#: liệu nào thuộc nhóm này, nên không trường nào trong đây được phép ``KNOWN``.
SITE_HAZARD_BLOCKS = (
    "coordinate_reference_system",
    "geographic_location",
    "seismic_hazard",
    "wind_hazard",
    "hydrology_scour",
    "geotechnical_category",
    "corrosion_exposure",
    "thermal_environment",
    "obstacle_crossed",
)


def _load_schema(name: str) -> dict:
    with open(CONTRACTS_DIR / name, encoding="utf-8") as f:
        return json.load(f)


def _load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _design_basis() -> dict:
    return _load_json(DESIGN_BASIS_INSTANCE)


def _site_profile() -> dict:
    return _load_json(SITE_PROFILE_INSTANCE)


def _catalogs() -> dict:
    return _load_json(Path(CATALOGS_DIR) / "catalogs.json")


def _grammar_files() -> list[Path]:
    files = sorted(Path(GRAMMAR_DIR).glob("*.json"))
    assert files, "Không tìm thấy grammar nào trong bridge_grammar/"
    return files


def _is_evidence_field(node) -> bool:
    return isinstance(node, dict) and node.get("status") in EVIDENCE_STATUSES


def _iter_evidence(node, path: str = "$"):
    """Duyệt toàn bộ cây JSON, sinh ra (đường dẫn, evidence_field)."""
    if _is_evidence_field(node):
        yield path, node
        return
    if isinstance(node, dict):
        for key, child in node.items():
            yield from _iter_evidence(child, f"{path}.{key}")
    elif isinstance(node, list):
        for idx, child in enumerate(node):
            yield from _iter_evidence(child, f"{path}[{idx}]")


def _known(container: dict, *keys: str):
    """Lấy value của một trường KNOWN; đỏ nếu trường đó không phải KNOWN."""
    node = container
    for key in keys:
        assert key in node, f"Thiếu trường {'.'.join(keys)} trong design basis"
        node = node[key]
    assert _is_evidence_field(node), f"{'.'.join(keys)} không phải evidence_field"
    assert node["status"] == "KNOWN", (
        f"{'.'.join(keys)} phải là KNOWN nhưng đang là {node['status']}"
    )
    return node["value"]


def _errors(schema: dict, instance: dict) -> list:
    return list(jsonschema.Draft202012Validator(schema).iter_errors(instance))


# ---------------------------------------------------------------------------
# Kiểm thử schema gốc (giữ nguyên — hồ sơ 1.0 vẫn phải hợp lệ)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Instance thật của dự án
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "schema_name,instance_path",
    [
        ("design_basis.schema.json", DESIGN_BASIS_INSTANCE),
        ("site_hazard_profile.schema.json", SITE_PROFILE_INSTANCE),
    ],
)
def test_instances_validate_against_schema(schema_name, instance_path):
    assert instance_path.is_file(), f"Thiếu instance {instance_path}"
    errors = _errors(_load_schema(schema_name), _load_json(instance_path))
    assert errors == [], "\n".join(f"{list(e.path)}: {e.message}" for e in errors)


def test_every_unknown_has_resolution_path():
    """Mọi ô trống phải nói rõ cái gì sẽ lấp nó — không được trống câm lặng."""
    for doc in (_design_basis(), _site_profile()):
        for path, field in _iter_evidence(doc):
            if field["status"] != "UNKNOWN":
                continue
            resolution = field.get("resolution_path", "")
            assert resolution.strip(), f"{path}: UNKNOWN mà không có resolution_path"
            assert len(resolution.strip()) >= 20, (
                f"{path}: resolution_path quá sơ sài, phải nêu cụ thể việc gì giải quyết nó"
            )
            assert "value" not in field, f"{path}: UNKNOWN thì không được kèm value"


def test_every_not_applicable_has_reason():
    for doc in (_design_basis(), _site_profile()):
        for path, field in _iter_evidence(doc):
            if field["status"] != "NOT_APPLICABLE":
                continue
            reason = field.get("not_applicable_reason", "")
            assert reason.strip(), f"{path}: NOT_APPLICABLE mà không nêu lý do"
            assert len(reason.strip()) >= 20, f"{path}: lý do NOT_APPLICABLE quá sơ sài"
            assert "value" not in field, f"{path}: NOT_APPLICABLE thì không được kèm value"


def test_every_known_field_cites_a_real_file():
    """KNOWN phải có nguồn, và nguồn phải là file CÓ THẬT trong repo."""
    seen_known = 0
    for doc in (_design_basis(), _site_profile()):
        for path, field in _iter_evidence(doc):
            if field["status"] != "KNOWN":
                continue
            seen_known += 1
            refs = field.get("source_ref")
            assert refs, f"{path}: KNOWN mà không có source_ref"
            if isinstance(refs, str):
                refs = [refs]
            for ref in refs:
                rel = ref.split("#", 1)[0].strip()
                assert (REPO_ROOT / rel).exists(), (
                    f"{path}: source_ref trỏ tới file không tồn tại: {rel}"
                )
    assert seen_known > 0, "Design basis không có trường KNOWN nào — nghi ngờ sai đường dẫn"


def test_design_basis_matches_runtime():
    """Giá trị KNOWN phải khớp đúng những gì runtime thực sự dùng.

    Nếu ai đó đổi ``bridge_grammar/*.json`` hoặc ``catalogs/catalogs.json`` mà
    quên đổi ``docs/design_basis/DB-SUPERT-38M.json`` thì test này PHẢI đỏ.
    """
    db = _design_basis()
    catalogs = _catalogs()
    grammars = {}
    for path in _grammar_files():
        data = _load_json(path)
        grammars[data["grammar_id"]] = (path, data)

    geom = db["geometry_constraints"]
    span = _known(geom, "span_length_m")
    width = _known(geom, "deck_width_m")
    skew = _known(geom, "skew_angle_deg")
    alignment = _known(geom, "alignment_type")

    # 1. Hình học dự án — phải khớp project_inputs của MỌI grammar.
    for grammar_id, (path, data) in grammars.items():
        inputs = data["project_inputs"]
        assert span == pytest.approx(inputs["span_length_m"]), (
            f"span_length_m lệch với {path.name}"
        )
        assert width == pytest.approx(inputs["deck_width_m"]), (
            f"deck_width_m lệch với {path.name}"
        )
        assert skew == pytest.approx(float(inputs["skew_deg"])), (
            f"skew_angle_deg lệch với {path.name}"
        )
        assert alignment == inputs["alignment_type"], (
            f"alignment_type lệch với {path.name}"
        )

    # 2. Ràng buộc runtime — load profile / rule profile / grammar phải phủ hết.
    binding_block = db["runtime_binding"]
    assert binding_block["catalogs_version"] == catalogs["catalogs_version"], (
        "catalogs_version trong design basis không khớp catalogs/catalogs.json"
    )
    bindings = {b["grammar_id"]: b for b in binding_block["grammar_bindings"]}
    assert set(bindings) == set(grammars), (
        "runtime_binding phải phủ đúng tập grammar trong bridge_grammar/: "
        f"design basis={sorted(bindings)} vs repo={sorted(grammars)}"
    )
    for grammar_id, binding in bindings.items():
        path, data = grammars[grammar_id]
        fixed = data["fixed"]
        assert binding["grammar_ref"].endswith(path.name)
        assert (REPO_ROOT / binding["grammar_ref"]).exists()
        assert binding.get("grammar_version") == data["grammar_version"]
        assert binding["load_profile_id"] == fixed["load_profile_id"]
        assert binding["rule_profile_id"] == fixed["rule_profile_id"]
        assert binding.get("prestressing_steel_id") == fixed["prestressing_steel_id"]
        assert binding.get("fidelity") == fixed["fidelity"]
        assert binding.get("solver") == fixed["solver"]
        assert binding["load_profile_id"] in catalogs["load_profiles"]
        assert binding["rule_profile_id"] in catalogs["rule_profiles"]
        assert binding["fidelity"] in binding_block["fidelity_available"]

    # 3. Tải trọng — phải khớp LOAD-PROFILE-01 thật.
    load_profile_ids = {b["load_profile_id"] for b in bindings.values()}
    assert len(load_profile_ids) == 1, "Nhiều load profile — design basis phải khai rõ từng cái"
    lp = catalogs["load_profiles"][load_profile_ids.pop()]
    loads = db["load_requirements"]
    assert _known(loads, "impact_percentage") == pytest.approx(lp["impact_factor"] * 100.0)
    assert _known(loads, "lane_load_kN_per_m") == pytest.approx(lp["lane_load_kN_per_m"])
    assert _known(loads, "design_lane_width_m") == pytest.approx(lp["design_lane_width_m"])
    assert _known(loads, "wearing_surface_thickness_m") == pytest.approx(
        lp["wearing_surface_thickness_m"]
    )
    assert _known(loads, "wearing_surface_unit_weight_kN_m3") == pytest.approx(
        lp["wearing_surface_unit_weight_kN_m3"]
    )
    assert _known(loads, "barrier_line_load_kN_per_m") == pytest.approx(
        lp["barrier_line_load_kN_per_m"]
    )
    assert _known(loads, "barrier_count") == lp["barrier_count"]
    assert _known(loads, "misc_smeared_dead_load_kN_per_m_per_girder") == pytest.approx(
        lp["misc_smeared_dead_load_kN_per_m_per_girder"]
    )
    assert _known(loads, "multiple_presence_factors") == lp["multiple_presence"]
    assert "HL-93" in lp["description"] or "HL93" in lp["description"]
    assert _known(loads, "live_load_model") in {"HL-93", "TCVN_HL93"}

    # 4. Tổ hợp tải — hệ số phải khớp rule profile thật của MỌI arm.
    combos = {c["name"]: c["factors"] for c in _known(db["load_combinations"], "combinations")}
    deflection = _known(db["load_combinations"], "deflection_limit")
    for binding in bindings.values():
        rp = catalogs["rule_profiles"][binding["rule_profile_id"]]
        assert combos["STRENGTH_I"] == rp["strength1"], (
            f"Hệ số Cường độ I lệch với {binding['rule_profile_id']}"
        )
        assert combos["SERVICE_III"] == rp["service3"], (
            f"Hệ số Sử dụng III lệch với {binding['rule_profile_id']}"
        )
        assert deflection == rp["deflection_limit_span_ratio"], (
            f"Giới hạn võng lệch với {binding['rule_profile_id']}"
        )

    # 5. Vật liệu — miền bê tông và trần cấp bê tông phải khớp grammar + catalogs.
    materials = db["materials_policy"]
    allowed_grades = _known(materials, "allowed_concrete_grades")
    runtime_grades = set()
    for _path, data in grammars.values():
        for var in ("girder_concrete_id", "deck_concrete_id"):
            runtime_grades.update(data["design_variables"][var]["domain"])
    assert set(allowed_grades) == runtime_grades, (
        "allowed_concrete_grades phải bằng đúng hợp miền bê tông của các grammar: "
        f"design basis={sorted(allowed_grades)} vs grammar={sorted(runtime_grades)}"
    )
    for grade in allowed_grades:
        assert grade in catalogs["concretes"], f"Cấp {grade} không có trong catalogs.concretes"

    ceiling = _known(materials, "max_concrete_grade_MPa")
    catalog_ceiling = max(c["fc_MPa"] for c in catalogs["concretes"].values())
    assert ceiling == pytest.approx(catalog_ceiling), (
        "Trần cấp bê tông trong design basis phải bằng f'c lớn nhất của catalogs.concretes"
    )
    for grade in allowed_grades:
        assert catalogs["concretes"][grade]["fc_MPa"] <= ceiling

    prestress = _known(materials, "allowed_prestress_types")
    runtime_prestress = {data["fixed"]["prestressing_steel_id"] for _p, data in grammars.values()}
    assert set(prestress) == runtime_prestress
    for pid in prestress:
        assert pid in catalogs["prestressing_steels"]


def test_runtime_drift_makes_the_guard_red(tmp_path, monkeypatch):
    """Meta-test: đổi grammar/catalog mà quên đổi design basis thì guard PHẢI đỏ.

    Không đụng vào file thật — dựng bản sao đã bị "trôi" trong tmp_path rồi trỏ
    ``GRAMMAR_DIR`` / ``CATALOGS_DIR`` vào đó.
    """
    module = sys.modules[__name__]
    grammar_copies = {p.name: _load_json(p) for p in _grammar_files()}
    catalogs_copy = _catalogs()

    # 1. Nhịp trong grammar bị đổi.
    drifted_grammar = tmp_path / "grammar_drift"
    drifted_grammar.mkdir()
    first = sorted(grammar_copies)[0]
    grammar_copies[first]["project_inputs"]["span_length_m"] = 40.0
    for name, data in grammar_copies.items():
        (drifted_grammar / name).write_text(
            json.dumps(data, ensure_ascii=False), encoding="utf-8"
        )
    monkeypatch.setattr(module, "GRAMMAR_DIR", drifted_grammar)
    with pytest.raises(AssertionError):
        test_design_basis_matches_runtime()
    monkeypatch.undo()

    # 2. Hệ số xung kích trong catalog bị đổi.
    drifted_catalogs = tmp_path / "catalog_drift"
    drifted_catalogs.mkdir()
    catalogs_copy["load_profiles"]["LOAD-PROFILE-01"]["impact_factor"] = 0.25
    (drifted_catalogs / "catalogs.json").write_text(
        json.dumps(catalogs_copy, ensure_ascii=False), encoding="utf-8"
    )
    monkeypatch.setattr(module, "CATALOGS_DIR", drifted_catalogs)
    with pytest.raises(AssertionError):
        test_design_basis_matches_runtime()


def test_blocked_materials_cover_unverified_register():
    """UHPC và CFRP phải nằm trong danh sách chặn, có trỏ về sổ claim chưa kiểm chứng."""
    blocked = _known(_design_basis()["materials_policy"], "blocked_materials")
    ids = {item["material_id"] for item in blocked}
    assert {"UHPC", "CFRP_TENDON"} <= ids, f"Thiếu vật liệu bị chặn: {sorted(ids)}"
    for item in blocked:
        rel = item["register_ref"].split("#", 1)[0].strip()
        assert (REPO_ROOT / rel).exists(), f"register_ref không có thật: {rel}"
        assert len(item["reason"].strip()) >= 20


def test_governing_standard_versions_not_mixed():
    """Không được trộn phiên bản tiêu chuẩn trong cùng một design basis."""
    std = _design_basis()["governing_standard"]
    version = std["version"]
    for part in std.get("parts", []):
        assert part.endswith(f":{version}"), (
            f"Phần tiêu chuẩn '{part}' không cùng phiên bản {version}"
        )


def test_design_basis_and_site_profile_cross_reference():
    db = _design_basis()
    site = _site_profile()
    assert (REPO_ROOT / db["site_hazard_profile_ref"]).resolve() == SITE_PROFILE_INSTANCE
    assert (REPO_ROOT / site["applicable_design_basis_ref"]).resolve() == DESIGN_BASIS_INSTANCE


# ---------------------------------------------------------------------------
# Chống bịa dữ liệu vị trí
# ---------------------------------------------------------------------------


def test_site_profile_is_explicitly_unspecified():
    """Hồ sơ vị trí phải RỖNG CÓ CHỦ ĐÍCH — không tọa độ, không vùng động đất, không gió."""
    site = _site_profile()
    assert site["site_id"] == "SITE-UNSPECIFIED"
    assert site["site_status"] == "UNSPECIFIED_PLACEHOLDER"
    assert len(site["site_status_note"].strip()) >= 100, (
        "site_status_note phải nói rõ đây là hồ sơ rỗng có chủ đích, không phải vị trí thật"
    )

    must_be_empty = [
        ("geographic_location", "latitude"),
        ("geographic_location", "longitude"),
        ("geographic_location", "terrain_category"),
        ("geographic_location", "administrative_area"),
        ("seismic_hazard", "pga_g"),
        ("seismic_hazard", "site_class"),
        ("seismic_hazard", "seismic_performance_zone"),
        ("wind_hazard", "basic_wind_speed_m_s"),
        ("wind_hazard", "gust_effect_factor"),
        ("wind_hazard", "aerodynamic_risk_level"),
        ("hydrology_scour", "design_flood_frequency_years"),
        ("hydrology_scour", "estimated_scour_depth_m"),
        ("hydrology_scour", "tidal_range_m"),
    ]
    for block, key in must_be_empty:
        field = site[block][key]
        assert field["status"] == "UNKNOWN", (
            f"{block}.{key} phải UNKNOWN — repo không có dữ liệu vị trí nào"
        )
        assert "value" not in field, f"{block}.{key} đã bị điền giá trị — nghi ngờ bịa dữ liệu"

    for key in ("geotechnical_category", "corrosion_exposure"):
        assert site[key]["status"] == "UNKNOWN"
        assert "value" not in site[key]


def test_no_fabricated_site_data():
    """Không trường hazard nào trong hồ sơ vị trí được mang trạng thái KNOWN."""
    site = _site_profile()
    offenders = []
    for block in SITE_HAZARD_BLOCKS:
        assert block in site, f"Thiếu khối {block} trong site profile"
        for path, field in _iter_evidence(site[block], f"${block}"):
            if field["status"] == "KNOWN":
                offenders.append(path)
    assert offenders == [], (
        "Repo KHÔNG có dữ liệu địa chất/thủy văn/gió/động đất/ăn mòn nào, nên các trường "
        f"sau không được phép KNOWN: {offenders}"
    )


def test_g0_gate_blocked_while_unknowns_remain():
    """Còn UNKNOWN thì G0 phải BLOCKED — đây là cái chặn agent nhảy vào tối ưu."""
    for doc, name in ((_design_basis(), "design basis"), (_site_profile(), "site profile")):
        unknowns = [p for p, f in _iter_evidence(doc) if f["status"] == "UNKNOWN"]
        gate = doc["g0_gate"]
        assert gate["gate"] == "G0"
        if unknowns:
            assert gate["status"] == "BLOCKED", (
                f"{name} còn {len(unknowns)} trường UNKNOWN nhưng G0 lại không BLOCKED"
            )
            assert gate["blocking_items"], f"{name}: G0 BLOCKED mà không liệt kê lý do"
            assert gate.get("blocked_claims"), (
                f"{name}: phải liệt kê rõ những claim bị chặn khi G0 chưa đạt"
            )


def test_site_profile_blocks_site_dependent_claims():
    """Danh sách claim bị chặn phải nêu đủ các nhóm phụ thuộc vị trí."""
    blocked_text = " ".join(_site_profile()["g0_gate"]["blocked_claims"]).lower()
    for keyword in ("động đất", "gió", "xói", "tuổi thọ", "móng"):
        assert keyword in blocked_text, f"Chưa chặn rõ claim liên quan: {keyword}"


# ---------------------------------------------------------------------------
# Schema phải TỰ CHẶN, không chỉ dựa vào thiện chí của người điền
# ---------------------------------------------------------------------------


def test_schema_rejects_unknown_without_resolution_path():
    schema = _load_schema("design_basis.schema.json")
    db = _design_basis()
    assert _errors(schema, db) == []
    db["exposure_class"].pop("resolution_path")
    assert _errors(schema, db), "Schema phải chặn UNKNOWN không có resolution_path"


def test_schema_rejects_not_applicable_without_reason():
    schema = _load_schema("design_basis.schema.json")
    db = _design_basis()
    field = db["load_requirements"]["pedestrian_load_kPa"]
    assert field["status"] == "NOT_APPLICABLE"
    field.pop("not_applicable_reason")
    assert _errors(schema, db), "Schema phải chặn NOT_APPLICABLE không có lý do"


def test_schema_rejects_value_on_non_known_field():
    schema = _load_schema("design_basis.schema.json")
    db = _design_basis()
    db["exposure_class"]["value"] = "INLAND_MILD"
    assert _errors(schema, db), "Schema phải chặn việc gán value cho trường UNKNOWN"


def test_schema_rejects_known_without_source_ref():
    schema = _load_schema("design_basis.schema.json")
    db = _design_basis()
    db["geometry_constraints"]["span_length_m"].pop("source_ref")
    assert _errors(schema, db), "Schema phải chặn KNOWN không có nguồn"


def test_schema_requires_g0_blocks_for_version_1_1():
    """Hồ sơ 1.1 thiếu đầu vào G0 phải bị schema từ chối."""
    schema = _load_schema("design_basis.schema.json")
    for missing in ("coordinate_system", "load_combinations", "runtime_binding",
                    "site_hazard_profile_ref", "g0_gate"):
        db = _design_basis()
        db.pop(missing)
        assert _errors(schema, db), f"Schema phải chặn design basis 1.1 thiếu {missing}"


def test_schema_forces_evidence_form_in_version_1_1():
    """Ở 1.1 không được quay lại kiểu điền số trần không khai trạng thái."""
    schema = _load_schema("design_basis.schema.json")
    db = _design_basis()
    db["geometry_constraints"] = {
        "span_length_m": 38.3,
        "deck_width_m": 12.0,
        "vertical_clearance_m": 5.5,
        "skew_angle_deg": 0.0,
    }
    assert _errors(schema, db), "1.1 phải bắt buộc dạng evidence_field, không nhận số trần"


def test_schema_rejects_known_hazard_on_unspecified_site():
    """Hàng rào chống bịa: site rỗng mà khai KNOWN hazard là sai schema."""
    schema = _load_schema("site_hazard_profile.schema.json")
    base = _site_profile()
    assert _errors(schema, base) == []

    fabricated = copy.deepcopy(base)
    fabricated["seismic_hazard"]["pga_g"] = {
        "status": "KNOWN",
        "value": 0.12,
        "source_ref": "docs/01_research_contract.md",
    }
    assert _errors(schema, fabricated), (
        "Schema phải chặn việc khai KNOWN cho hazard khi site_status = UNSPECIFIED_PLACEHOLDER"
    )

    fabricated2 = copy.deepcopy(base)
    fabricated2["geographic_location"]["latitude"] = {
        "status": "KNOWN",
        "value": 21.0285,
        "source_ref": "docs/01_research_contract.md",
    }
    assert _errors(schema, fabricated2), "Schema phải chặn việc điền tọa độ vào hồ sơ rỗng"


def test_schema_rejects_g0_passed_with_blocking_items():
    schema = _load_schema("site_hazard_profile.schema.json")
    site = _site_profile()
    site["g0_gate"]["status"] = "PASSED"
    assert _errors(schema, site), (
        "Không được tuyên bố G0 PASSED trong khi vẫn còn blocking_items"
    )


# ---------------------------------------------------------------------------
# Component audit đa cấu kiện — chỉ điều phối evidence, không thay verifier
# ---------------------------------------------------------------------------


_AUDIT_CASE_ID = "BT-0123456789abcdef"


def _audit_evidence(tag: str = "sample") -> dict:
    return {
        "source_ref": f"tests/synthetic-component-evidence/{tag}.json",
        "sha256": "a" * 64,
        "fidelity": "ENGINEER_REVIEW",
        "producer": "pytest-fixture",
    }


def _complete_component(kind: str, component_id: str = "C1",
                        *, fail_check: str | None = None,
                        include_advisory: bool = True) -> dict:
    checks = []
    for check_id, severity in COMPONENT_AUDIT_REGISTRY[kind]["required_checks"].items():
        if severity == "SOFT" and not include_advisory:
            continue
        checks.append({
            "check_id": check_id,
            "status": "FAIL" if check_id == fail_check else "PASS",
            "severity": severity,
            "evidence": _audit_evidence(f"{kind}-{check_id}"),
            "message": "Synthetic envelope test; không phải bằng chứng thiết kế.",
            "utilization": 1.05 if check_id == fail_check else 0.75,
        })
    return {"component_id": component_id, "kind": kind, "checks": checks}


def _build_audit(manifest: dict, state: dict | None = None) -> dict:
    state = {} if state is None else state
    result = {
        "case_id": _AUDIT_CASE_ID,
        "provenance": {"input_hash": "b" * 64},
    }
    return build_component_audit(state, result, manifest)


def test_component_registry_covers_whole_bridge_system():
    required_families = {
        "DECK_SLAB", "LONGITUDINAL_GIRDER", "CROSS_BEAM_DIAPHRAGM",
        "PIER_COLUMN", "PIER_CAP", "ABUTMENT", "RETAINING_WING_WALL",
        "FOUNDATION_FOOTING", "FOUNDATION_PILE", "BEARING",
        "EXPANSION_JOINT", "PRESTRESSING_SYSTEM", "CABLE_SYSTEM",
        "ARCH_RIB", "TRUSS_MEMBER", "CONNECTION", "APPROACH_SLAB",
        "PARAPET_BARRIER", "WATERPROOFING_DRAINAGE", "TEMPORARY_WORKS",
    }
    assert required_families <= set(COMPONENT_AUDIT_REGISTRY)


def test_every_registered_component_can_enter_audit_envelope():
    components = [
        _complete_component(kind, f"C{index:02d}")
        for index, kind in enumerate(sorted(COMPONENT_AUDIT_REGISTRY), start=1)
    ]
    audit = _build_audit({"candidate_id": _AUDIT_CASE_ID, "components": components})
    assert audit["status"] == "SCREENED"
    assert audit["blocking_reasons"] == []
    assert {item["kind"] for item in audit["components"]} == set(COMPONENT_AUDIT_REGISTRY)


def test_hard_fail_rejects_component_audit_and_creates_unverified_repair():
    hard_check = next(
        check_id for check_id, severity
        in COMPONENT_AUDIT_REGISTRY["CONNECTION"]["required_checks"].items()
        if severity == "HARD"
    )
    audit = _build_audit({
        "components": [_complete_component("CONNECTION", "CONN-1",
                                           fail_check=hard_check)],
    })
    assert audit["status"] == "REJECTED"
    repair = next(p for p in audit["proposals"] if p["check_id"] == hard_check)
    assert repair["kind"] == "REPAIR"
    assert repair["requires_reanalysis"] is True
    assert repair["claim"] == "UNVERIFIED_PROPOSAL"
    assert "feasible" not in repair


def test_missing_or_unproven_hard_checks_fail_closed():
    audit = _build_audit({
        "components": [{
            "component_id": "BRG-1",
            "kind": "BEARING",
            "checks": [{
                "check_id": "REACTION_CAPACITY",
                "status": "PASS",
                "severity": "HARD",
                "message": "Caller nói đạt nhưng không đưa evidence.",
            }],
        }],
    })
    assert audit["status"] == "BLOCKED"
    by_id = {check["check_id"]: check for check in audit["components"][0]["checks"]}
    assert by_id["REACTION_CAPACITY"]["status"] == "NOT_EVALUATED"
    codes = {reason["code"] for reason in audit["blocking_reasons"]}
    assert "INVALID_HARD_CHECK_EVIDENCE" in codes
    assert "MISSING_HARD_CHECK_EVIDENCE" in codes


def test_unknown_component_kind_is_visible_and_blocked():
    audit = _build_audit({
        "components": [{"component_id": "X-1", "kind": "ALIEN_PART", "checks": []}],
    })
    assert audit["status"] == "BLOCKED"
    assert audit["components"][0]["registry_supported"] is False
    assert audit["components"][0]["checks"][0]["status"] == "NOT_EVALUATED"
    assert any(r["code"] == "UNKNOWN_COMPONENT_KIND"
               for r in audit["blocking_reasons"])


def test_component_audit_lineage_and_hash_are_deterministic():
    state = {"provenance": {"parent_candidate_id": "BT-parent-001"}}
    component_a = _complete_component("DECK_SLAB", "DECK-1")
    component_b = _complete_component("PIER_COLUMN", "PIER-1")
    manifest = {
        "candidate_id": _AUDIT_CASE_ID,
        "parent_candidate_id": "BT-parent-001",
        "components": [component_a, component_b],
    }
    first = _build_audit(copy.deepcopy(manifest), state)
    reordered = copy.deepcopy(manifest)
    reordered["components"].reverse()
    second = _build_audit(reordered, state)
    assert first["parent_candidate_id"] == "BT-parent-001"
    assert first["audit_hash"] == second["audit_hash"]
    assert len(first["audit_hash"]) == 64

    mismatched = copy.deepcopy(manifest)
    mismatched["parent_candidate_id"] = "BT-other-parent"
    mismatch_audit = _build_audit(mismatched, state)
    assert mismatch_audit["status"] == "BLOCKED"
    assert any(r["code"] == "PARENT_LINEAGE_MISMATCH"
               for r in mismatch_audit["blocking_reasons"])


def test_durability_stays_advisory_when_hard_checks_have_evidence():
    audit = _build_audit({
        "components": [_complete_component(
            "DECK_SLAB", "DECK-1", include_advisory=False,
        )],
    })
    assert audit["status"] == "SCREENED"
    durability = next(
        check for check in audit["components"][0]["checks"]
        if check["check_id"] == "DURABILITY"
    )
    assert durability["severity"] == "SOFT"
    assert durability["status"] == "NOT_EVALUATED"


def test_component_audit_validates_against_evaluation_result_schema():
    audit = _build_audit({
        "components": [_complete_component("FOUNDATION_PILE", "PILE-1")],
    })
    result = {
        "case_id": _AUDIT_CASE_ID,
        "status": "SUCCESS",
        "feasible": False,
        "solver": {"status": "NOT_RUN", "name": "BUILTIN_L1"},
        "violations": [],
        "provenance": {
            "input_hash": "b" * 64,
            "ruleset_version": "test-rules",
            "solver_version": "test-solver",
            "catalogs_version": "test-catalogs",
        },
        "component_audit": audit,
    }
    assert _errors(_load_schema("evaluation_result.schema.json"), result) == []


def test_component_audit_never_changes_existing_evaluation_verdict():
    state = _load_json(REPO_ROOT / "gold_cases" / "cases" / "GC-01_standard_pass.json")
    baseline = evaluate_candidate(copy.deepcopy(state))
    audited = evaluate_candidate(copy.deepcopy(state), component_manifest={
        "components": [{"component_id": "X-1", "kind": "UNKNOWN_PART", "checks": []}],
    })
    assert audited["status"] == baseline["status"]
    assert audited["feasible"] == baseline["feasible"]
    assert audited["component_audit"]["status"] == "BLOCKED"
    assert audited["component_audit"]["alters_evaluation_verdict"] is False
    assert "component_audit" not in baseline
