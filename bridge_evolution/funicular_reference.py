"""Tham chiếu đường áp lực funicular độc lập với kernel độ cứng F1.

Module này dùng cân bằng tĩnh học của vòm parabol hai khớp dưới tải đứng đều
theo phương ngang. Nó đo độ lệch hình học và so bậc độ lớn với diagnostic
BRD-042; không tính sức kháng, utilization hay phát hành verdict thiết kế.
"""
from __future__ import annotations

import hashlib
import json
import math
from copy import deepcopy
from pathlib import Path

import jsonschema

from . import CONTRACTS_DIR, REPO_ROOT
from . import arch_action_f1


REFERENCE_ID = "FUNICULAR_STATIC_REFERENCE"
REFERENCE_VERSION = "funicular-reference/0.1.0"
CLAIM_LEVEL = "IDEA"
DESIGN_VERDICT_AUTHORITY = "NONE"
TECHNICAL_SCOPE = "STATIC_FUNICULAR_REFERENCE_ONLY_NO_CAPACITY_OR_DESIGN_VERDICT"

_SCHEMA_PATH = CONTRACTS_DIR / "funicular_reference_study.schema.json"
_BASIS_PATH = REPO_ROOT / "docs" / "design_basis" / "funicular_reference_basis.json"
_SOURCE_PATHS = (
    ("bridge_evolution/funicular_reference.py", Path(__file__).resolve()),
    ("bridge_evolution/arch_action_f1.py", Path(arch_action_f1.__file__).resolve()),
)
_TOPOLOGIES = ("DECK_ARCH", "THROUGH_ARCH", "NETWORK_ARCH")
_LOAD_DOMAIN = {
    "load_case_count": 1,
    "direction": "GLOBAL_NEGATIVE_Y",
    "distribution": "UNIFORM_OVER_HORIZONTAL_SPAN_FROM_TRIBUTARY_LENGTHS",
    "support_elevation": "EQUAL",
    "arch_axis_x": "STRICTLY_INCREASING",
}
_FORMULAE = {
    "equivalent_uniform_load": "w=W/L",
    "horizontal_thrust": "H_ref=w*L^2/(8*f)",
    "funicular_axis": "y_ref=4*f*x*(L-x)/L^2",
    "reference_shear": "V_ref=w*(L/2-x)",
    "reference_compression": "C_ref=sqrt(H_ref^2+V_ref^2)",
    "bending_proxy": "M_proxy=w*x*(L-x)/2-H_ref*y_actual",
}
_EXPECTED_ACTION_STATUS = {
    "DECK_ARCH": "FOUNDATION_THRUST_DETECTED",
    "THROUGH_ARCH": "INTERNAL_TIE_ACTION_DETECTED",
    "NETWORK_ARCH": "INTERNAL_TIE_ACTION_DETECTED",
}
_MEASURED_ACTION = {
    "DECK_ARCH": "FOUNDATION_THRUST_MAGNITUDE",
    "THROUGH_ARCH": "DECK_TIE_TENSION_ENVELOPE",
    "NETWORK_ARCH": "DECK_TIE_TENSION_ENVELOPE",
}


class FunicularReferenceError(ValueError):
    """Parent, basis hoặc output vi phạm hợp đồng tham chiếu funicular."""


def _canonical(value: object) -> str:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise FunicularReferenceError(f"Dữ liệu không thể canonical JSON: {exc}") from exc


def _sha256_json(value: object) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _read_json(path: Path, label: str) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FunicularReferenceError(f"Không đọc được {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise FunicularReferenceError(f"{label} phải là JSON object")
    return value


def _schema_errors(instance: dict) -> list[str]:
    schema = _read_json(_SCHEMA_PATH, _SCHEMA_PATH.name)
    jsonschema.Draft202012Validator.check_schema(schema)
    errors = sorted(
        jsonschema.Draft202012Validator(schema).iter_errors(instance),
        key=lambda error: list(error.absolute_path),
    )
    return [
        f"{'/'.join(str(part) for part in error.absolute_path) or '<root>'}: "
        f"{error.message}"
        for error in errors
    ]


def _source_digests() -> list[dict]:
    digests = []
    for label, path in _SOURCE_PATHS:
        if not path.is_file():
            raise FunicularReferenceError(f"Không tìm thấy source reference: {label}")
        digests.append({"path": label, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    return digests


def _source_sha256() -> str:
    return _sha256_json(_source_digests())


def _finite_positive(value: object) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and math.isfinite(float(value))
        and float(value) > 0.0
    )


def load_funicular_basis() -> dict:
    """Đọc basis và khóa mọi giả thiết có thể đổi ý nghĩa phép tham chiếu."""
    basis = _read_json(_BASIS_PATH, "funicular reference basis")
    if basis.get("schema_version") != "1.0":
        raise FunicularReferenceError("schema_version của funicular basis phải là 1.0")
    if basis.get("basis_id") != "FUNICULAR-REFERENCE-1.0.0":
        raise FunicularReferenceError("basis_id không khớp runtime")
    if basis.get("reference_version") != REFERENCE_VERSION:
        raise FunicularReferenceError("reference_version không khớp runtime")
    if basis.get("upstream_version") != arch_action_f1.STUDY_VERSION:
        raise FunicularReferenceError("upstream_version không khớp BRD-042 runtime")
    if basis.get("claim_ceiling") != CLAIM_LEVEL:
        raise FunicularReferenceError("Basis không được nâng claim khỏi IDEA")
    if basis.get("design_verdict_authority") != DESIGN_VERDICT_AUTHORITY:
        raise FunicularReferenceError("Basis phải khai design_verdict_authority=NONE")
    if basis.get("applicable_topologies") != list(_TOPOLOGIES):
        raise FunicularReferenceError("applicable_topologies không khớp runtime")
    if basis.get("load_domain") != _LOAD_DOMAIN:
        raise FunicularReferenceError("load_domain không khớp runtime")
    if basis.get("formulae") != _FORMULAE:
        raise FunicularReferenceError("formulae không khớp runtime")

    tolerances = basis.get("numerical_tolerances")
    required_tolerances = {
        "geometry_relative",
        "load_relative",
        "canonical_funicular_relative",
    }
    if not isinstance(tolerances, dict) or set(tolerances) != required_tolerances:
        raise FunicularReferenceError("numerical_tolerances thiếu hoặc thừa khóa")
    if any(
        not _finite_positive(value) or float(value) > 1e-6
        for value in tolerances.values()
    ):
        raise FunicularReferenceError("Mọi numerical tolerance phải ở (0, 1e-6]")

    order_band = basis.get("order_of_magnitude_band")
    if not isinstance(order_band, dict) or set(order_band) != {
        "minimum_ratio", "maximum_ratio", "interpretation"
    }:
        raise FunicularReferenceError("order_of_magnitude_band thiếu hoặc thừa khóa")
    minimum = order_band.get("minimum_ratio")
    maximum = order_band.get("maximum_ratio")
    if not _finite_positive(minimum) or not _finite_positive(maximum):
        raise FunicularReferenceError("Order band phải hữu hạn và dương")
    if not float(minimum) < 1.0 < float(maximum):
        raise FunicularReferenceError("Order band phải bao quanh tỷ số 1")
    if not math.isclose(float(minimum) * float(maximum), 1.0, rel_tol=1e-12, abs_tol=1e-12):
        raise FunicularReferenceError("Order band phải đối xứng theo thang log")
    if order_band.get("interpretation") != "HEURISTIC_MODEL_ERROR_DETECTION_NOT_CODE_LIMIT":
        raise FunicularReferenceError("Order band không được diễn giải như giới hạn tiêu chuẩn")

    for field in ("explicit_assumptions", "explicit_limitations", "promotion_requirements"):
        values = basis.get(field)
        if not isinstance(values, list) or not values or not all(
            isinstance(item, str) and item.strip() for item in values
        ):
            raise FunicularReferenceError(f"Basis phải có {field} không rỗng")
    expected_sources = [label for label, _path in _SOURCE_PATHS]
    if basis.get("reference_source_files") != expected_sources:
        raise FunicularReferenceError("reference_source_files không khớp runtime")
    observed = _source_sha256()
    if basis.get("reference_source_sha256") != observed:
        raise FunicularReferenceError(
            "reference_source_sha256 không khớp bytes runtime: "
            f"expected={basis.get('reference_source_sha256')}, observed={observed}"
        )
    return basis


def _validated_parent(parent_study: dict) -> None:
    try:
        arch_action_f1.validate_arch_action_study(parent_study)
    except arch_action_f1.ArchActionF1Error as exc:
        raise FunicularReferenceError(f"Parent BRD-042 không hợp lệ: {exc}") from exc
    if parent_study["status"] != "ACTION_DIAGNOSTIC_COMPLETE":
        raise FunicularReferenceError(
            "Chỉ parent BRD-042 ACTION_DIAGNOSTIC_COMPLETE mới vào tham chiếu funicular"
        )
    if parent_study["claim_level"] != CLAIM_LEVEL:
        raise FunicularReferenceError("Parent phải giữ claim_level=IDEA")
    if parent_study["design_verdict_authority"] != DESIGN_VERDICT_AUTHORITY:
        raise FunicularReferenceError("Parent phải giữ design_verdict_authority=NONE")
    topology = parent_study["topology"]
    expected = _EXPECTED_ACTION_STATUS.get(topology)
    if expected is None:
        raise FunicularReferenceError(f"Topology ngoài miền funicular: {topology}")
    if any(item["action_status"] != expected for item in parent_study["diagnostics"]):
        raise FunicularReferenceError("Parent chưa phát hiện đầy đủ cơ chế kỳ vọng ở mọi load case")


def _support_nodes(parent_study: dict) -> tuple[dict, dict]:
    nodes = [
        node for node in parent_study["parent_analysis"]["candidate"]["graph"]["nodes"]
        if node.get("support") is True
    ]
    ordered = sorted(nodes, key=lambda item: (float(item["x_m"]), item["id"]))
    if len(ordered) != 2:
        raise FunicularReferenceError("Candidate phải có đúng hai chân vòm")
    left, right = ordered
    if not float(left["x_m"]) < float(right["x_m"]):
        raise FunicularReferenceError("Hai chân vòm phải có thứ tự trái-phải")
    return left, right


def _axis_points(parent_study: dict, left: dict, right: dict, tolerance: float) -> list[dict]:
    raw = parent_study["parent_analysis"]["candidate"]["axis_points"]
    if len(raw) < 3:
        raise FunicularReferenceError("Trục vòm phải có ít nhất ba điểm")
    points = [
        {"index": int(point["index"]), "x_m": float(point["x_m"]), "y_m": float(point["y_m"])}
        for point in raw
    ]
    if any(not all(math.isfinite(value) for value in (point["x_m"], point["y_m"])) for point in points):
        raise FunicularReferenceError("Trục vòm chứa tọa độ không hữu hạn")
    if not all(a["x_m"] < b["x_m"] for a, b in zip(points, points[1:])):
        raise FunicularReferenceError("Hoành độ trục vòm phải tăng nghiêm ngặt")
    span = float(right["x_m"]) - float(left["x_m"])
    scale = max(1.0, span)
    if abs(float(left["y_m"]) - float(right["y_m"])) > tolerance * scale:
        raise FunicularReferenceError("Hai chân vòm không cùng cao độ")
    if abs(points[0]["x_m"] - float(left["x_m"])) > tolerance * scale:
        raise FunicularReferenceError("Điểm đầu trục không trùng chân trái")
    if abs(points[-1]["x_m"] - float(right["x_m"])) > tolerance * scale:
        raise FunicularReferenceError("Điểm cuối trục không trùng chân phải")
    support_y = 0.5 * (float(left["y_m"]) + float(right["y_m"]))
    if abs(points[0]["y_m"] - support_y) > tolerance * scale:
        raise FunicularReferenceError("Cao độ đầu trục không trùng đường gối")
    if abs(points[-1]["y_m"] - support_y) > tolerance * scale:
        raise FunicularReferenceError("Cao độ cuối trục không trùng đường gối")
    if max(point["y_m"] - support_y for point in points) <= tolerance * scale:
        raise FunicularReferenceError("Rise trục vòm bằng 0 hoặc quá nhỏ")
    return points


def _load_input(parent_study: dict, span: float, tolerance: float) -> dict:
    analysis = parent_study["parent_analysis"]
    model = parent_study["study_model"]
    load_cases = model["load_cases"]
    if len(load_cases) != _LOAD_DOMAIN["load_case_count"]:
        raise FunicularReferenceError("Tham chiếu chỉ hỗ trợ đúng một load case")
    load_case = load_cases[0]
    profile_load = analysis["structural_profile"]["deck_line_load"]
    if profile_load["direction"] != _LOAD_DOMAIN["direction"]:
        raise FunicularReferenceError("Chỉ hỗ trợ tải GLOBAL_NEGATIVE_Y")
    conservation = analysis["load_conservation"]
    q = float(conservation["line_load_kN_m"])
    deck_length = float(conservation["deck_length_m"])
    if not _finite_positive(q) or not _finite_positive(deck_length):
        raise FunicularReferenceError("Tải đường và chiều dài mặt cầu phải dương hữu hạn")
    scale = max(1.0, span, deck_length)
    if abs(deck_length - span) > tolerance * scale:
        raise FunicularReferenceError("Mặt cầu không tương đương tải đều theo phương ngang trên nhịp")
    tributary = {
        item["node_id"]: float(item["tributary_length_m"])
        for item in conservation["tributary_length_by_node_m"]
    }
    loads = load_case["nodal_loads"]
    if {item["node_id"] for item in loads} != set(tributary):
        raise FunicularReferenceError("Tập nút tải không khớp tributary lengths")
    load_scale = max(1.0, q * span)
    for load in loads:
        if abs(float(load["fx_kN"])) > tolerance * load_scale:
            raise FunicularReferenceError("Tải ngang nằm ngoài miền funicular")
        if abs(float(load["mz_kNm"])) > tolerance * load_scale * max(1.0, span):
            raise FunicularReferenceError("Mômen nút nằm ngoài miền funicular")
        expected_fy = -q * tributary[load["node_id"]]
        if abs(float(load["fy_kN"]) - expected_fy) > tolerance * load_scale:
            raise FunicularReferenceError("Tải nút không còn phân bố đều theo tributary lengths")
    total_vertical = -sum(float(load["fy_kN"]) for load in loads)
    if not _finite_positive(total_vertical):
        raise FunicularReferenceError("Tổng tải đứng phải dương hữu hạn")
    if abs(total_vertical - q * span) > tolerance * load_scale:
        raise FunicularReferenceError("Tổng tải đứng không khớp w*L")
    return {
        "load_case_id": load_case["id"],
        "load_model": "EQUIVALENT_UNIFORM_VERTICAL_LOAD_OVER_HORIZONTAL_SPAN",
        "load_direction": _LOAD_DOMAIN["direction"],
        "total_vertical_load_kN": total_vertical,
        "equivalent_uniform_load_kN_m": total_vertical / span,
        "deck_length_m": deck_length,
    }


def _derive_reference_input(parent_study: dict, basis: dict) -> dict:
    tolerance = float(basis["numerical_tolerances"]["geometry_relative"])
    left, right = _support_nodes(parent_study)
    span = float(right["x_m"]) - float(left["x_m"])
    if not _finite_positive(span):
        raise FunicularReferenceError("Nhịp phải dương hữu hạn")
    points = _axis_points(parent_study, left, right, tolerance)
    support_y = 0.5 * (float(left["y_m"]) + float(right["y_m"]))
    rise = max(point["y_m"] - support_y for point in points)
    if not _finite_positive(rise):
        raise FunicularReferenceError("Rise phải dương hữu hạn")
    load = _load_input(
        parent_study,
        span,
        float(basis["numerical_tolerances"]["load_relative"]),
    )
    return {
        **load,
        "span_m": span,
        "rise_m": rise,
        "support_elevation_m": support_y,
        "arch_axis": points,
    }


def _f1_comparison(parent_study: dict, diagnostic: dict, h_ref: float, basis: dict) -> dict:
    topology = parent_study["topology"]
    measured_action = _MEASURED_ACTION[topology]
    if topology == "DECK_ARCH":
        measured_min = float(diagnostic["horizontal_thrust_magnitude_kN"])
        measured_max = measured_min
    else:
        envelope = diagnostic["deck_axial_envelope"]
        measured_min = float(envelope["min_signed_axial_kN"])
        measured_max = float(envelope["max_signed_axial_kN"])
    if not _finite_positive(measured_min) or not _finite_positive(measured_max):
        raise FunicularReferenceError("Cơ chế parent không cung cấp lực dương để so tham chiếu")
    if measured_min > measured_max:
        raise FunicularReferenceError("Envelope lực đo được bị đảo min/max")
    ratio_min = measured_min / h_ref
    ratio_max = measured_max / h_ref
    order_band = basis["order_of_magnitude_band"]
    lower = float(order_band["minimum_ratio"])
    upper = float(order_band["maximum_ratio"])
    within = ratio_min >= lower and ratio_max <= upper
    return {
        "measured_action": measured_action,
        "reference_force_kN": h_ref,
        "measured_force_min_kN": measured_min,
        "measured_force_max_kN": measured_max,
        "measured_to_reference_ratio_min": ratio_min,
        "measured_to_reference_ratio_max": ratio_max,
        "order_band_minimum_ratio": lower,
        "order_band_maximum_ratio": upper,
        "agreement_status": (
            "AGREEMENT_WITHIN_ORDER_BAND" if within
            else "AGREEMENT_OUTSIDE_ORDER_BAND"
        ),
        "reason_codes": [] if within else ["MEASURED_FORCE_OUTSIDE_HEURISTIC_ORDER_BAND"],
    }


def _derive_reference_result(parent_study: dict, reference_input: dict, basis: dict) -> dict:
    span = float(reference_input["span_m"])
    rise = float(reference_input["rise_m"])
    support_y = float(reference_input["support_elevation_m"])
    total_load = float(reference_input["total_vertical_load_kN"])
    w = total_load / span
    h_ref = w * span * span / (8.0 * rise)
    if not _finite_positive(h_ref):
        raise FunicularReferenceError("Không tính được horizontal thrust tham chiếu")
    simple_beam_max = w * span * span / 8.0
    samples = []
    deviations = []
    bending_values = []
    for point in reference_input["arch_axis"]:
        x_rel = float(point["x_m"]) - float(reference_input["arch_axis"][0]["x_m"])
        y_actual = float(point["y_m"]) - support_y
        y_ref = 4.0 * rise * x_rel * (span - x_rel) / (span * span)
        deviation = y_actual - y_ref
        simple_moment = w * x_rel * (span - x_rel) / 2.0
        bending_proxy = simple_moment - h_ref * y_actual
        shear = w * (span / 2.0 - x_rel)
        compression = math.hypot(h_ref, shear)
        samples.append({
            "index": int(point["index"]),
            "x_from_left_m": x_rel,
            "actual_ordinate_m": y_actual,
            "reference_ordinate_m": y_ref,
            "axis_deviation_m": deviation,
            "simple_beam_moment_kNm": simple_moment,
            "bending_proxy_kNm": bending_proxy,
            "reference_shear_kN": shear,
            "reference_compression_kN": compression,
        })
        deviations.append(deviation)
        bending_values.append(bending_proxy)
    rms_deviation = math.sqrt(sum(value * value for value in deviations) / len(deviations))
    max_deviation = max(abs(value) for value in deviations)
    max_bending = max(abs(value) for value in bending_values)
    rms_ratio = rms_deviation / rise
    max_deviation_ratio = max_deviation / rise
    max_bending_ratio = max_bending / simple_beam_max
    canonical_tolerance = float(
        basis["numerical_tolerances"]["canonical_funicular_relative"]
    )
    diagnostics = {item["load_case_id"]: item for item in parent_study["diagnostics"]}
    diagnostic = diagnostics.get(reference_input["load_case_id"])
    if diagnostic is None:
        raise FunicularReferenceError("Không tìm thấy diagnostic BRD-042 cho load case")
    comparison = _f1_comparison(parent_study, diagnostic, h_ref, basis)
    return {
        "load_case_id": reference_input["load_case_id"],
        "reference_model": "TWO_HINGED_PARABOLIC_FUNICULAR_UNDER_HORIZONTAL_UDL",
        "horizontal_thrust_reference_kN": h_ref,
        "simple_beam_max_moment_kNm": simple_beam_max,
        "axis_rms_deviation_m": rms_deviation,
        "axis_max_abs_deviation_m": max_deviation,
        "axis_rms_deviation_ratio": rms_ratio,
        "axis_max_abs_deviation_ratio": max_deviation_ratio,
        "bending_proxy_max_abs_kNm": max_bending,
        "bending_proxy_max_abs_ratio": max_bending_ratio,
        "canonical_funicular_within_tolerance": (
            max(rms_ratio, max_deviation_ratio, max_bending_ratio) <= canonical_tolerance
        ),
        "samples": samples,
        "f1_comparison": comparison,
    }


def _identity(parent_study: dict, basis_sha256: str) -> dict:
    return {
        "reference_id": REFERENCE_ID,
        "reference_version": REFERENCE_VERSION,
        "parent_study_sha256": parent_study["study_sha256"],
        "basis_sha256": basis_sha256,
    }


def _manifest(
    parent_study: dict,
    reference_input: dict,
    reference_result: dict,
    basis_sha256: str,
    source_sha256: str,
) -> dict:
    parent_manifest = parent_study["manifest"]
    return {
        "parent_study_id": parent_study["study_id"],
        "parent_study_sha256": parent_study["study_sha256"],
        "parent_analysis_id": parent_manifest["parent_analysis_id"],
        "parent_analysis_sha256": parent_manifest["parent_analysis_sha256"],
        "candidate_id": parent_manifest["candidate_id"],
        "candidate_sha256": parent_manifest["candidate_sha256"],
        "geometry_sha256": parent_manifest["geometry_sha256"],
        "candidate_profile_sha256": parent_manifest["candidate_profile_sha256"],
        "structural_profile_sha256": parent_manifest["structural_profile_sha256"],
        "parent_study_model_sha256": parent_manifest["study_model_sha256"],
        "parent_study_result_sha256": parent_manifest["study_result_sha256"],
        "arch_action_basis_sha256": parent_manifest["study_basis_sha256"],
        "funicular_basis_sha256": basis_sha256,
        "funicular_source_sha256": source_sha256,
        "reference_input_sha256": _sha256_json(reference_input),
        "reference_result_sha256": _sha256_json(reference_result),
    }


def run_funicular_reference(parent_study: dict) -> dict:
    """Tính tham chiếu tĩnh học độc lập và trả output diagnostic ở mức IDEA."""
    _validated_parent(parent_study)
    basis = load_funicular_basis()
    basis_sha256 = hashlib.sha256(_BASIS_PATH.read_bytes()).hexdigest()
    source_digests = _source_digests()
    source_sha256 = _sha256_json(source_digests)
    reference_input = _derive_reference_input(parent_study, basis)
    reference_result = _derive_reference_result(parent_study, reference_input, basis)
    output = {
        "schema_version": "1.0",
        "reference_id": (
            "FR-" + _sha256_json(_identity(parent_study, basis_sha256))[:16]
        ),
        "reference": {"id": REFERENCE_ID, "version": REFERENCE_VERSION},
        "reference_source_sha256": source_sha256,
        "reference_source_digests": source_digests,
        "claim_level": CLAIM_LEVEL,
        "design_verdict_authority": DESIGN_VERDICT_AUTHORITY,
        "technical_scope": TECHNICAL_SCOPE,
        "status": "REFERENCE_COMPLETE",
        "topology": parent_study["topology"],
        "parent_study": deepcopy(parent_study),
        "reference_input": reference_input,
        "reference_result": reference_result,
        "manifest": _manifest(
            parent_study,
            reference_input,
            reference_result,
            basis_sha256,
            source_sha256,
        ),
        "upstream_basis_hashes": {
            **deepcopy(parent_study["upstream_basis_hashes"]),
            "arch_action_basis_sha256": parent_study["manifest"]["study_basis_sha256"],
        },
        "limitations": list(basis["explicit_limitations"]),
    }
    output["reference_sha256"] = _sha256_json(output)
    validate_funicular_reference(output)
    return output


def validate_funicular_reference(output: dict) -> None:
    """Tái dẫn xuất parent -> input -> tĩnh học -> manifest và kiểm mọi hash."""
    if not isinstance(output, dict):
        raise FunicularReferenceError("Funicular reference output phải là object")
    _canonical(output)
    errors = _schema_errors(output)
    if errors:
        raise FunicularReferenceError("Funicular reference sai schema: " + "; ".join(errors[:30]))
    payload = deepcopy(output)
    claimed_sha256 = payload.pop("reference_sha256")
    actual_sha256 = _sha256_json(payload)
    if claimed_sha256 != actual_sha256:
        raise FunicularReferenceError(
            f"reference_sha256 không khớp: expected={actual_sha256}, actual={claimed_sha256}"
        )
    if output["reference"] != {"id": REFERENCE_ID, "version": REFERENCE_VERSION}:
        raise FunicularReferenceError("Reference identity/version không khớp runtime")
    if output["claim_level"] != CLAIM_LEVEL:
        raise FunicularReferenceError("Output không được nâng claim khỏi IDEA")
    if output["design_verdict_authority"] != DESIGN_VERDICT_AUTHORITY:
        raise FunicularReferenceError("Output phải giữ design_verdict_authority=NONE")
    if output["technical_scope"] != TECHNICAL_SCOPE:
        raise FunicularReferenceError("technical_scope không khớp runtime")
    if output["status"] != "REFERENCE_COMPLETE":
        raise FunicularReferenceError("Output hợp lệ phải có status REFERENCE_COMPLETE")

    basis = load_funicular_basis()
    basis_sha256 = hashlib.sha256(_BASIS_PATH.read_bytes()).hexdigest()
    expected_digests = _source_digests()
    expected_source_sha256 = _sha256_json(expected_digests)
    if output["reference_source_digests"] != expected_digests:
        raise FunicularReferenceError("reference_source_digests không khớp bytes runtime")
    if output["reference_source_sha256"] != expected_source_sha256:
        raise FunicularReferenceError("reference_source_sha256 không khớp source digests")

    parent_study = output["parent_study"]
    _validated_parent(parent_study)
    expected_input = _derive_reference_input(parent_study, basis)
    if output["reference_input"] != expected_input:
        raise FunicularReferenceError("reference_input không tái lập được từ parent/basis")
    expected_result = _derive_reference_result(parent_study, expected_input, basis)
    if output["reference_result"] != expected_result:
        raise FunicularReferenceError("reference_result không tái lập được bằng tĩnh học độc lập")
    if output["topology"] != parent_study["topology"]:
        raise FunicularReferenceError("Topology output không khớp parent")
    expected_manifest = _manifest(
        parent_study,
        expected_input,
        expected_result,
        basis_sha256,
        expected_source_sha256,
    )
    if output["manifest"] != expected_manifest:
        raise FunicularReferenceError("Manifest funicular không khớp lineage/hash tái lập")
    expected_upstream = {
        **deepcopy(parent_study["upstream_basis_hashes"]),
        "arch_action_basis_sha256": parent_study["manifest"]["study_basis_sha256"],
    }
    if output["upstream_basis_hashes"] != expected_upstream:
        raise FunicularReferenceError("upstream_basis_hashes không khớp parent")
    if output["limitations"] != list(basis["explicit_limitations"]):
        raise FunicularReferenceError("Limitations không khớp basis")
    expected_id = "FR-" + _sha256_json(_identity(parent_study, basis_sha256))[:16]
    if output["reference_id"] != expected_id:
        raise FunicularReferenceError("reference_id không khớp identity canonical")
