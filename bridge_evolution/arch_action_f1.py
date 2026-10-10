"""Chẩn đoán tác dụng vòm theo topology trên kernel F1 đã được khóa provenance.

Module này không kiểm tra sức kháng. Nó chỉ dẫn xuất một mô hình điều kiện biên
từ output BRD-041, chạy lại F1 và báo liệu đường truyền lực kỳ vọng có xuất hiện
trong lý tưởng hóa đàn hồi tuyến tính 2D hay không.
"""
from __future__ import annotations

import hashlib
import json
import math
from copy import deepcopy
from pathlib import Path

import jsonschema

from . import CONTRACTS_DIR, REPO_ROOT
from . import creative_frame_adapter, creative_shape, frame_f1


STUDY_ID = "TOPOLOGY_ARCH_ACTION_F1"
STUDY_VERSION = "arch-action-f1/0.1.0"
CLAIM_LEVEL = "IDEA"
DESIGN_VERDICT_AUTHORITY = "NONE"
TECHNICAL_SCOPE = "F1_ARCH_ACTION_DIAGNOSTIC_ONLY_NO_CAPACITY_OR_DESIGN_VERDICT"

_SCHEMA_PATH = CONTRACTS_DIR / "arch_action_f1_study.schema.json"
_BASIS_PATH = REPO_ROOT / "docs" / "design_basis" / "arch_action_f1_basis.json"
_SOURCE_PATHS = (
    ("bridge_evolution/arch_action_f1.py", Path(__file__).resolve()),
    (
        "bridge_evolution/creative_frame_adapter.py",
        Path(creative_frame_adapter.__file__).resolve(),
    ),
    ("bridge_evolution/creative_shape.py", Path(creative_shape.__file__).resolve()),
    ("bridge_evolution/frame_f1.py", Path(frame_f1.__file__).resolve()),
)
_SUPPORT_POLICIES = {
    "DECK_ARCH": {
        "id": "DECK_ARCH_BOTH_FEET_PINNED_TRANSLATION",
        "left": {"ux": True, "uy": True, "rz": False},
        "right": {"ux": True, "uy": True, "rz": False},
    },
    "THROUGH_ARCH": {
        "id": "TIED_ARCH_LEFT_PIN_RIGHT_VERTICAL_ROLLER",
        "left": {"ux": True, "uy": True, "rz": False},
        "right": {"ux": False, "uy": True, "rz": False},
    },
    "NETWORK_ARCH": {
        "id": "TIED_ARCH_LEFT_PIN_RIGHT_VERTICAL_ROLLER",
        "left": {"ux": True, "uy": True, "rz": False},
        "right": {"ux": False, "uy": True, "rz": False},
    },
}
_EXPECTED_ACTION = {
    "DECK_ARCH": "FOUNDATION_THRUST",
    "THROUGH_ARCH": "INTERNAL_TIE_ACTION",
    "NETWORK_ARCH": "INTERNAL_TIE_ACTION",
}


class ArchActionF1Error(ValueError):
    """Parent, basis hoặc study vi phạm contract chẩn đoán tác dụng vòm."""


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
        raise ArchActionF1Error(f"Dữ liệu không thể canonical JSON: {exc}") from exc


def _sha256_json(value: object) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _read_json(path: Path, label: str) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ArchActionF1Error(f"Không đọc được {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise ArchActionF1Error(f"{label} phải là JSON object")
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
            raise ArchActionF1Error(f"Không tìm thấy source study: {label}")
        digests.append({"path": label, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    return digests


def _source_sha256() -> str:
    return _sha256_json(_source_digests())


def load_arch_action_basis() -> dict:
    basis = _read_json(_BASIS_PATH, "arch action F1 basis")
    if basis.get("schema_version") != "1.0":
        raise ArchActionF1Error("schema_version của arch-action basis phải là 1.0")
    if basis.get("basis_id") != "ARCH-ACTION-F1-1.0.0":
        raise ArchActionF1Error("basis_id không khớp runtime")
    if basis.get("study_version") != STUDY_VERSION:
        raise ArchActionF1Error("study_version không khớp runtime")
    expected_versions = {
        "creative_frame_adapter": creative_frame_adapter.ADAPTER_VERSION,
        "creative_generator": creative_shape.GENERATOR_VERSION,
        "frame_solver": frame_f1.SOLVER_VERSION,
    }
    if basis.get("upstream_versions") != expected_versions:
        raise ArchActionF1Error("upstream_versions không khớp runtime")
    if basis.get("claim_ceiling") != CLAIM_LEVEL:
        raise ArchActionF1Error("Basis không được nâng claim khỏi IDEA")
    if basis.get("design_verdict_authority") != DESIGN_VERDICT_AUTHORITY:
        raise ArchActionF1Error("Basis phải khai design_verdict_authority=NONE")
    if basis.get("support_policy_by_topology") != _SUPPORT_POLICIES:
        raise ArchActionF1Error("support_policy_by_topology không khớp runtime")
    if basis.get("expected_action_by_topology") != _EXPECTED_ACTION:
        raise ArchActionF1Error("expected_action_by_topology không khớp runtime")
    tolerances = basis.get("diagnostic_tolerances")
    required_tolerances = {
        "action_force_relative",
        "equilibrium_relative",
        "element_end_antisymmetry_relative",
    }
    if not isinstance(tolerances, dict) or set(tolerances) != required_tolerances:
        raise ArchActionF1Error("diagnostic_tolerances thiếu hoặc thừa khóa")
    if any(
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or not 0.0 < float(value) <= 1e-6
        for value in tolerances.values()
    ):
        raise ArchActionF1Error("Mọi diagnostic tolerance phải hữu hạn trong (0, 1e-6]")
    for field in ("explicit_assumptions", "explicit_limitations", "promotion_requirements"):
        values = basis.get(field)
        if not isinstance(values, list) or not values or not all(
            isinstance(item, str) and item.strip() for item in values
        ):
            raise ArchActionF1Error(f"Basis phải có {field} không rỗng")
    expected_sources = [label for label, _path in _SOURCE_PATHS]
    if basis.get("study_source_files") != expected_sources:
        raise ArchActionF1Error("study_source_files không khớp runtime")
    observed = _source_sha256()
    if basis.get("study_source_sha256") != observed:
        raise ArchActionF1Error(
            "study_source_sha256 không khớp bytes runtime: "
            f"expected={basis.get('study_source_sha256')}, observed={observed}"
        )
    return basis


def _validated_parent(parent_analysis: dict) -> None:
    try:
        creative_frame_adapter.validate_creative_frame_analysis(parent_analysis)
    except creative_frame_adapter.CreativeFrameAdapterError as exc:
        raise ArchActionF1Error(f"Parent BRD-041 không hợp lệ: {exc}") from exc
    if parent_analysis["status"] != "CONVERGED":
        raise ArchActionF1Error("Chỉ parent BRD-041 status CONVERGED mới được nghiên cứu tác dụng vòm")
    if parent_analysis["claim_level"] != CLAIM_LEVEL:
        raise ArchActionF1Error("Parent phải giữ claim_level=IDEA")
    if parent_analysis["design_verdict_authority"] != DESIGN_VERDICT_AUTHORITY:
        raise ArchActionF1Error("Parent phải giữ design_verdict_authority=NONE")


def _support_nodes(parent_analysis: dict) -> list[dict]:
    nodes = [
        node for node in parent_analysis["candidate"]["graph"]["nodes"]
        if node.get("support") is True
    ]
    ordered = sorted(nodes, key=lambda node: (float(node["x_m"]), node["id"]))
    if len(ordered) != 2 or not float(ordered[0]["x_m"]) < float(ordered[1]["x_m"]):
        raise ArchActionF1Error("Parent không có đúng hai chân vòm trái-phải")
    return ordered


def _derive_model(parent_analysis: dict, basis: dict) -> tuple[dict, str]:
    topology = parent_analysis["candidate"]["genome"]["topology"]
    policy = basis["support_policy_by_topology"].get(topology)
    if policy is None:
        raise ArchActionF1Error(f"Topology không có support policy: {topology}")
    left, right = _support_nodes(parent_analysis)
    model = deepcopy(parent_analysis["frame_model"])
    model["model_id"] = (
        f"F1M-AA-{parent_analysis['candidate']['candidate_id'][3:]}-"
        f"{_sha256_json({'parent': parent_analysis['analysis_sha256'], 'policy': policy['id']})[:8]}"
    )
    model["supports"] = [
        {"node_id": left["id"], **deepcopy(policy["left"])},
        {"node_id": right["id"], **deepcopy(policy["right"])},
    ]
    return model, policy["id"]


def _signed_axial_envelope(
    element_kind: str,
    graph_edges: dict[str, dict],
    element_forces: list[dict],
    force_scale: float,
) -> dict:
    signed_values = []
    end_residuals = []
    for force in element_forces:
        edge = graph_edges.get(force["element_id"])
        if edge is None:
            raise ArchActionF1Error(f"F1 trả nội lực cho element lạ: {force['element_id']}")
        if edge["kind"] != element_kind:
            continue
        axial_i = float(force["axial_i_kN"])
        axial_j = float(force["axial_j_kN"])
        signed_values.append(0.5 * (axial_j - axial_i))
        end_residuals.append(abs(axial_i + axial_j) / force_scale)
    if not signed_values:
        raise ArchActionF1Error(f"Không có element kind {element_kind} để chẩn đoán")
    minimum = min(signed_values)
    maximum = max(signed_values)
    return {
        "element_kind": element_kind,
        "element_count": len(signed_values),
        "sign_convention": "POSITIVE_TENSION_NEGATIVE_COMPRESSION",
        "min_signed_axial_kN": minimum,
        "max_signed_axial_kN": maximum,
        "max_compression_kN": max(0.0, -minimum),
        "max_tension_kN": max(0.0, maximum),
        "max_end_antisymmetry_relative": max(end_residuals, default=0.0),
    }


def _not_evaluable_case(
    topology: str,
    policy_id: str,
    load_case: dict,
    case_result: dict,
) -> dict:
    applied_fx = sum(float(load["fx_kN"]) for load in load_case["nodal_loads"])
    applied_fy = sum(float(load["fy_kN"]) for load in load_case["nodal_loads"])
    return {
        "load_case_id": load_case["id"],
        "f1_status": case_result["status"],
        "action_status": "NOT_EVALUABLE",
        "expected_action": _EXPECTED_ACTION[topology],
        "support_policy_id": policy_id,
        "force_scale_kN": max(1.0, abs(applied_fx), abs(applied_fy)),
        "applied_fx_kN": applied_fx,
        "applied_fy_kN": applied_fy,
        "left_reaction": None,
        "right_reaction": None,
        "horizontal_thrust_magnitude_kN": None,
        "horizontal_equilibrium_residual_relative": None,
        "vertical_equilibrium_residual_relative": None,
        "arch_rib_axial_envelope": None,
        "deck_axial_envelope": None,
        "reason_codes": [f"F1_STATUS_{case_result['status']}"],
    }


def _case_diagnostic(
    topology: str,
    policy_id: str,
    load_case: dict,
    case_result: dict,
    graph_edges: dict[str, dict],
    basis: dict,
    support_node_ids: tuple[str, str],
) -> dict:
    if case_result["status"] != "CONVERGED":
        return _not_evaluable_case(topology, policy_id, load_case, case_result)
    reactions = {item["node_id"]: item for item in case_result["reactions"]}
    if set(reactions) != set(support_node_ids):
        raise ArchActionF1Error("Study F1 phải trả đúng hai phản lực chân vòm")
    left, right = (reactions[node_id] for node_id in support_node_ids)
    applied_fx = sum(float(load["fx_kN"]) for load in load_case["nodal_loads"])
    applied_fy = sum(float(load["fy_kN"]) for load in load_case["nodal_loads"])
    force_scale = max(1.0, abs(applied_fx), abs(applied_fy))
    horizontal_residual = abs(
        float(left["fx_kN"]) + float(right["fx_kN"]) + applied_fx
    ) / force_scale
    vertical_residual = abs(
        float(left["fy_kN"]) + float(right["fy_kN"]) + applied_fy
    ) / force_scale
    thrust = 0.5 * (abs(float(left["fx_kN"])) + abs(float(right["fx_kN"])))
    arch_envelope = _signed_axial_envelope(
        "ARCH_RIB", graph_edges, case_result["element_end_forces"], force_scale
    )
    deck_envelope = _signed_axial_envelope(
        "DECK", graph_edges, case_result["element_end_forces"], force_scale
    )
    tolerances = basis["diagnostic_tolerances"]
    action_limit = float(tolerances["action_force_relative"]) * force_scale
    equilibrium_limit = float(tolerances["equilibrium_relative"])
    end_force_limit = float(tolerances["element_end_antisymmetry_relative"])
    reasons = []
    if horizontal_residual > equilibrium_limit:
        reasons.append("HORIZONTAL_EQUILIBRIUM_OUTSIDE_TOLERANCE")
    if vertical_residual > equilibrium_limit:
        reasons.append("VERTICAL_EQUILIBRIUM_OUTSIDE_TOLERANCE")
    if arch_envelope["max_end_antisymmetry_relative"] > end_force_limit:
        reasons.append("ARCH_RIB_END_FORCE_ANTISYMMETRY_OUTSIDE_TOLERANCE")
    if deck_envelope["max_end_antisymmetry_relative"] > end_force_limit:
        reasons.append("DECK_END_FORCE_ANTISYMMETRY_OUTSIDE_TOLERANCE")
    if arch_envelope["max_signed_axial_kN"] >= -action_limit:
        reasons.append("ARCH_RIB_NOT_IN_COMPRESSION_THROUGHOUT")
    if topology == "DECK_ARCH":
        if thrust <= action_limit:
            reasons.append("FOUNDATION_HORIZONTAL_THRUST_NOT_DETECTED")
        if not (
            float(left["fx_kN"]) > action_limit
            and float(right["fx_kN"]) < -action_limit
        ):
            reasons.append("FOUNDATION_REACTIONS_NOT_DIRECTED_INWARD")
        detected_status = "FOUNDATION_THRUST_DETECTED"
    else:
        if thrust > action_limit:
            reasons.append("EXTERNAL_HORIZONTAL_REACTION_NOT_RELEASED")
        if deck_envelope["min_signed_axial_kN"] <= action_limit:
            reasons.append("DECK_TIE_NOT_IN_TENSION_THROUGHOUT")
        detected_status = "INTERNAL_TIE_ACTION_DETECTED"
    action_status = detected_status if not reasons else "EXPECTED_ACTION_NOT_DETECTED"
    return {
        "load_case_id": load_case["id"],
        "f1_status": case_result["status"],
        "action_status": action_status,
        "expected_action": _EXPECTED_ACTION[topology],
        "support_policy_id": policy_id,
        "force_scale_kN": force_scale,
        "applied_fx_kN": applied_fx,
        "applied_fy_kN": applied_fy,
        "left_reaction": deepcopy(left),
        "right_reaction": deepcopy(right),
        "horizontal_thrust_magnitude_kN": thrust,
        "horizontal_equilibrium_residual_relative": horizontal_residual,
        "vertical_equilibrium_residual_relative": vertical_residual,
        "arch_rib_axial_envelope": arch_envelope,
        "deck_axial_envelope": deck_envelope,
        "reason_codes": reasons,
    }


def _diagnostics(parent_analysis: dict, model: dict, result: dict, basis: dict,
                 policy_id: str) -> tuple[list[dict], str]:
    topology = parent_analysis["candidate"]["genome"]["topology"]
    result_by_id = {case["load_case_id"]: case for case in result["load_case_results"]}
    graph_edges = {
        edge["id"]: edge for edge in parent_analysis["candidate"]["graph"]["edges"]
    }
    support_node_ids = (
        model["supports"][0]["node_id"],
        model["supports"][1]["node_id"],
    )
    diagnostics = []
    for load_case in model["load_cases"]:
        case_result = result_by_id.get(load_case["id"])
        if case_result is None:
            raise ArchActionF1Error(f"Thiếu F1 result cho load case {load_case['id']}")
        diagnostics.append(_case_diagnostic(
            topology, policy_id, load_case, case_result, graph_edges, basis,
            support_node_ids,
        ))
    statuses = {item["action_status"] for item in diagnostics}
    if "NOT_EVALUABLE" in statuses:
        status = "NOT_EVALUABLE"
    elif "EXPECTED_ACTION_NOT_DETECTED" in statuses:
        status = "EXPECTED_ACTION_NOT_DETECTED"
    else:
        status = "ACTION_DIAGNOSTIC_COMPLETE"
    return diagnostics, status


def _identity(parent_analysis: dict, policy_id: str, basis_sha256: str) -> dict:
    return {
        "study_id": STUDY_ID,
        "study_version": STUDY_VERSION,
        "parent_analysis_sha256": parent_analysis["analysis_sha256"],
        "support_policy_id": policy_id,
        "basis_sha256": basis_sha256,
    }


def _manifest(parent_analysis: dict, result: dict, basis_sha256: str,
              source_sha256: str) -> dict:
    parent_manifest = parent_analysis["manifest"]
    return {
        "parent_analysis_id": parent_analysis["analysis_id"],
        "parent_analysis_sha256": parent_analysis["analysis_sha256"],
        "candidate_id": parent_manifest["candidate_id"],
        "candidate_sha256": parent_manifest["candidate_sha256"],
        "geometry_sha256": parent_manifest["geometry_sha256"],
        "candidate_profile_sha256": parent_manifest["candidate_profile_sha256"],
        "structural_profile_sha256": parent_manifest["structural_profile_sha256"],
        "study_model_sha256": result["model_sha256"],
        "study_result_sha256": result["result_sha256"],
        "study_basis_sha256": basis_sha256,
        "study_source_sha256": source_sha256,
    }


def run_arch_action_study(parent_analysis: dict) -> dict:
    """Dẫn xuất support theo topology, chạy F1 và trả diagnostic không-capacity."""
    _validated_parent(parent_analysis)
    basis = load_arch_action_basis()
    basis_sha256 = hashlib.sha256(_BASIS_PATH.read_bytes()).hexdigest()
    source_digests = _source_digests()
    source_sha256 = _sha256_json(source_digests)
    model, policy_id = _derive_model(parent_analysis, basis)
    try:
        result = frame_f1.analyze_frame_model(model)
    except frame_f1.FrameF1Error as exc:
        raise ArchActionF1Error(f"Study model F1 không hợp lệ: {exc}") from exc
    diagnostics, status = _diagnostics(parent_analysis, model, result, basis, policy_id)
    study = {
        "schema_version": "1.0",
        "study_id": (
            "AA-" + _sha256_json(_identity(parent_analysis, policy_id, basis_sha256))[:16]
        ),
        "study": {"id": STUDY_ID, "version": STUDY_VERSION},
        "study_source_sha256": source_sha256,
        "study_source_digests": source_digests,
        "claim_level": CLAIM_LEVEL,
        "design_verdict_authority": DESIGN_VERDICT_AUTHORITY,
        "technical_scope": TECHNICAL_SCOPE,
        "status": status,
        "topology": parent_analysis["candidate"]["genome"]["topology"],
        "support_policy_id": policy_id,
        "parent_analysis": deepcopy(parent_analysis),
        "study_model": model,
        "study_result": result,
        "diagnostics": diagnostics,
        "manifest": _manifest(parent_analysis, result, basis_sha256, source_sha256),
        "upstream_basis_hashes": deepcopy(parent_analysis["basis_hashes"]),
        "limitations": list(basis["explicit_limitations"]),
    }
    study["study_sha256"] = _sha256_json(study)
    validate_arch_action_study(study)
    return study


def validate_arch_action_study(study: dict) -> None:
    """Tái lập parent -> support model -> F1 -> diagnostics và kiểm toàn bộ hash."""
    if not isinstance(study, dict):
        raise ArchActionF1Error("Arch-action study phải là object")
    _canonical(study)
    errors = _schema_errors(study)
    if errors:
        raise ArchActionF1Error("Arch-action study sai schema: " + "; ".join(errors[:24]))
    payload = deepcopy(study)
    claimed_sha256 = payload.pop("study_sha256")
    actual_sha256 = _sha256_json(payload)
    if claimed_sha256 != actual_sha256:
        raise ArchActionF1Error(
            f"study_sha256 không khớp: expected={actual_sha256}, actual={claimed_sha256}"
        )
    if study["study"] != {"id": STUDY_ID, "version": STUDY_VERSION}:
        raise ArchActionF1Error("Study identity/version không khớp runtime")
    basis = load_arch_action_basis()
    basis_sha256 = hashlib.sha256(_BASIS_PATH.read_bytes()).hexdigest()
    expected_source_digests = _source_digests()
    expected_source_sha256 = _sha256_json(expected_source_digests)
    if study["study_source_digests"] != expected_source_digests:
        raise ArchActionF1Error("study_source_digests không khớp bytes runtime")
    if study["study_source_sha256"] != expected_source_sha256:
        raise ArchActionF1Error("study_source_sha256 không khớp source digests")
    parent_analysis = study["parent_analysis"]
    _validated_parent(parent_analysis)
    expected_model, expected_policy_id = _derive_model(parent_analysis, basis)
    if study["study_model"] != expected_model:
        raise ArchActionF1Error("study_model không phải dẫn xuất canonical từ parent và basis")
    try:
        expected_result = frame_f1.analyze_frame_model(expected_model)
        frame_f1.validate_frame_result(study["study_result"])
    except frame_f1.FrameF1Error as exc:
        raise ArchActionF1Error(f"study_result F1 không hợp lệ: {exc}") from exc
    if study["study_result"] != expected_result:
        raise ArchActionF1Error("study_result không tái lập được từ study_model")
    expected_diagnostics, expected_status = _diagnostics(
        parent_analysis, expected_model, expected_result, basis, expected_policy_id
    )
    if study["diagnostics"] != expected_diagnostics:
        raise ArchActionF1Error("diagnostics không tái lập được từ model/result/basis")
    if study["status"] != expected_status:
        raise ArchActionF1Error("Study status không khớp diagnostics")
    topology = parent_analysis["candidate"]["genome"]["topology"]
    if study["topology"] != topology:
        raise ArchActionF1Error("Topology study không khớp parent")
    if study["support_policy_id"] != expected_policy_id:
        raise ArchActionF1Error("support_policy_id không khớp topology")
    expected_manifest = _manifest(
        parent_analysis, expected_result, basis_sha256, expected_source_sha256
    )
    if study["manifest"] != expected_manifest:
        raise ArchActionF1Error("Manifest study không khớp lineage/hash tái lập")
    if study["upstream_basis_hashes"] != parent_analysis["basis_hashes"]:
        raise ArchActionF1Error("upstream_basis_hashes không khớp parent")
    if study["limitations"] != list(basis["explicit_limitations"]):
        raise ArchActionF1Error("Limitations study không khớp basis")
    expected_study_id = (
        "AA-" + _sha256_json(
            _identity(parent_analysis, expected_policy_id, basis_sha256)
        )[:16]
    )
    if study["study_id"] != expected_study_id:
        raise ArchActionF1Error("study_id không khớp identity canonical")
