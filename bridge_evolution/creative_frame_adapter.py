"""Adapter fail-closed từ candidate hình thái F0 sang kernel khung/giàn F1.

Adapter chỉ bảo toàn và chuyển đổi dữ liệu đã được người gọi khai báo. Nó không
tự sinh vật liệu, tiết diện, tự trọng, tổ hợp tải hay sức kháng. Kết quả F1 hội
tụ chỉ có nghĩa hệ đàn hồi tuyến tính 2D đã giải được; không phải verdict thiết
kế cầu. Mọi output giữ ``claim_level=IDEA`` và
``design_verdict_authority=NONE``.
"""
from __future__ import annotations

import hashlib
import json
import math
from copy import deepcopy
from pathlib import Path, PurePosixPath

import jsonschema

from . import CONTRACTS_DIR, REPO_ROOT
from . import creative_shape, frame_f1


ADAPTER_ID = "CREATIVE_ARCH_TO_FRAME_F1"
ADAPTER_VERSION = "creative-frame-adapter/0.1.0"
CLAIM_LEVEL = "IDEA"
DESIGN_VERDICT_AUTHORITY = "NONE"
TECHNICAL_SCOPE = "F0_CANDIDATE_TO_F1_LINEAR_MODEL_NO_DESIGN_VERDICT"

_PROFILE_SCHEMA = CONTRACTS_DIR / "creative_frame_profile.schema.json"
_ANALYSIS_SCHEMA = CONTRACTS_DIR / "creative_frame_analysis.schema.json"
_BASIS_PATH = REPO_ROOT / "docs" / "design_basis" / "creative_frame_adapter_basis.json"
_EDGE_KINDS = (
    "ARCH_RIB",
    "DECK",
    "SPANDREL",
    "END_POST",
    "HANGER",
    "NETWORK_HANGER",
)
_FRAME_EDGE_KINDS = {"ARCH_RIB", "DECK", "SPANDREL", "END_POST"}
_TRUSS_EDGE_KINDS = {"HANGER", "NETWORK_HANGER"}
_SUPPORT_POLICY = "LEFT_PIN_RIGHT_VERTICAL_ROLLER"
_ADAPTER_SOURCE_PATHS = (
    ("bridge_evolution/creative_frame_adapter.py", Path(__file__).resolve()),
    ("bridge_evolution/creative_shape.py", Path(creative_shape.__file__).resolve()),
    ("bridge_evolution/frame_f1.py", Path(frame_f1.__file__).resolve()),
)


class CreativeFrameAdapterError(ValueError):
    """Candidate, profile hoặc analysis vi phạm contract adapter."""


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
        raise CreativeFrameAdapterError(f"Dữ liệu không thể canonical JSON: {exc}") from exc


def _sha256_json(value: object) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _read_json(path: Path, label: str) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CreativeFrameAdapterError(f"Không đọc được {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise CreativeFrameAdapterError(f"{label} phải là JSON object")
    return value


def _schema_errors(instance: dict, schema_path: Path) -> list[str]:
    schema = _read_json(schema_path, schema_path.name)
    jsonschema.Draft202012Validator.check_schema(schema)
    errors = sorted(
        jsonschema.Draft202012Validator(schema).iter_errors(instance),
        key=lambda error: list(error.absolute_path),
    )
    return [
        f"{'/'.join(str(part) for part in error.absolute_path) or '<root>'}: {error.message}"
        for error in errors
    ]


def _adapter_source_digests() -> list[dict]:
    digests = []
    for label, path in _ADAPTER_SOURCE_PATHS:
        if not path.is_file():
            raise CreativeFrameAdapterError(f"Không tìm thấy source adapter: {label}")
        digests.append({"path": label, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    return digests


def _adapter_source_sha256() -> str:
    return _sha256_json(_adapter_source_digests())


def load_adapter_basis() -> dict:
    basis = _read_json(_BASIS_PATH, "creative frame adapter basis")
    if basis.get("schema_version") != "1.0":
        raise CreativeFrameAdapterError("schema_version của adapter basis phải là 1.0")
    if basis.get("basis_id") != "CREATIVE-FRAME-ADAPTER-1.0.0":
        raise CreativeFrameAdapterError("basis_id của adapter không khớp runtime")
    if basis.get("adapter_version") != ADAPTER_VERSION:
        raise CreativeFrameAdapterError("adapter_version trong basis không khớp runtime")
    if basis.get("creative_generator_version") != creative_shape.GENERATOR_VERSION:
        raise CreativeFrameAdapterError("creative_generator_version trong basis không khớp runtime")
    if basis.get("frame_solver_version") != frame_f1.SOLVER_VERSION:
        raise CreativeFrameAdapterError("frame_solver_version trong basis không khớp runtime")
    if basis.get("claim_ceiling") != CLAIM_LEVEL:
        raise CreativeFrameAdapterError("Basis không được nâng claim khỏi IDEA")
    if basis.get("design_verdict_authority") != DESIGN_VERDICT_AUTHORITY:
        raise CreativeFrameAdapterError("Basis phải khai design_verdict_authority=NONE")
    expected_support_policy = {
        "id": _SUPPORT_POLICY,
        "left": {"ux": True, "uy": True, "rz": False},
        "right": {"ux": False, "uy": True, "rz": False},
    }
    if basis.get("support_policy") != expected_support_policy:
        raise CreativeFrameAdapterError("Basis chỉ được khai support policy đã hỗ trợ")
    expected_mapping = {
        kind: "FRAME_2D" if kind in _FRAME_EDGE_KINDS else "TRUSS_2D"
        for kind in _EDGE_KINDS
    }
    if basis.get("edge_kind_mapping") != expected_mapping:
        raise CreativeFrameAdapterError("edge_kind_mapping trong basis không khớp runtime")
    load_transfer = basis.get("load_transfer")
    if not isinstance(load_transfer, dict) or set(load_transfer) != {
        "method", "direction", "relative_tolerance",
    }:
        raise CreativeFrameAdapterError("load_transfer trong basis thiếu hoặc thừa khóa")
    if load_transfer.get("method") != "HALF_ADJACENT_DECK_EDGE_LENGTH_TO_EACH_END_NODE":
        raise CreativeFrameAdapterError("Basis khai load-transfer method không được hỗ trợ")
    if load_transfer.get("direction") != "GLOBAL_NEGATIVE_Y":
        raise CreativeFrameAdapterError("Basis chỉ hỗ trợ tải theo GLOBAL_NEGATIVE_Y")
    tolerance = load_transfer.get("relative_tolerance")
    if (
        isinstance(tolerance, bool)
        or not isinstance(tolerance, (int, float))
        or not math.isfinite(tolerance)
        or not 0.0 < float(tolerance) <= 1e-6
    ):
        raise CreativeFrameAdapterError("load transfer tolerance phải hữu hạn trong (0, 1e-6]")
    minimum_length = basis.get("minimum_element_length_m")
    if (
        isinstance(minimum_length, bool)
        or not isinstance(minimum_length, (int, float))
        or not math.isfinite(minimum_length)
        or not 0.0 < float(minimum_length) <= 1e-3
    ):
        raise CreativeFrameAdapterError(
            "minimum_element_length_m phải hữu hạn trong (0, 1e-3]")
    limitations = basis.get("explicit_limitations")
    if not isinstance(limitations, list) or not limitations or not all(
        isinstance(item, str) and item.strip() for item in limitations
    ):
        raise CreativeFrameAdapterError("Basis phải có explicit_limitations không rỗng")
    for field in ("explicit_assumptions", "promotion_requirements"):
        values = basis.get(field)
        if not isinstance(values, list) or not values or not all(
            isinstance(item, str) and item.strip() for item in values
        ):
            raise CreativeFrameAdapterError(f"Basis phải có {field} không rỗng")
    expected_sources = [label for label, _path in _ADAPTER_SOURCE_PATHS]
    if basis.get("adapter_source_files") != expected_sources:
        raise CreativeFrameAdapterError("adapter_source_files trong basis không khớp runtime")
    observed = _adapter_source_sha256()
    if basis.get("adapter_source_sha256") != observed:
        raise CreativeFrameAdapterError(
            "adapter_source_sha256 trong basis không khớp bytes runtime: "
            f"expected={basis.get('adapter_source_sha256')}, observed={observed}")
    return basis


def _source_path(source_ref: object) -> Path | None:
    if not isinstance(source_ref, str) or not source_ref.strip() or "#" in source_ref:
        return None
    if "\\" in source_ref:
        return None
    posix = PurePosixPath(source_ref)
    if (
        posix.is_absolute()
        or not posix.parts
        or any(part in {"", ".", ".."} for part in posix.parts)
        or posix.as_posix() != source_ref
    ):
        return None
    resolved = (REPO_ROOT / Path(*posix.parts)).resolve(strict=False)
    try:
        resolved.relative_to(REPO_ROOT.resolve())
    except ValueError:
        return None
    return resolved if resolved.is_file() else None


def _source_digest(source_ref: str, expected_sha256: str, label: str) -> dict:
    path = _source_path(source_ref)
    if path is None:
        raise CreativeFrameAdapterError(
            f"{label}.source_ref không tồn tại, không POSIX hoặc vượt biên repo: {source_ref}")
    observed = hashlib.sha256(path.read_bytes()).hexdigest()
    if observed != expected_sha256:
        raise CreativeFrameAdapterError(
            f"{label} source drift: expected={expected_sha256}, observed={observed}")
    return {"source_ref": source_ref, "sha256": observed}


def validate_structural_profile(profile: dict, candidate: dict) -> list[dict]:
    """Kiểm schema, binding candidate và hash bytes của mọi nguồn đã khai."""
    if not isinstance(profile, dict):
        raise CreativeFrameAdapterError("Structural profile phải là object")
    _canonical(profile)
    errors = _schema_errors(profile, _PROFILE_SCHEMA)
    if errors:
        raise CreativeFrameAdapterError("Structural profile sai schema: " + "; ".join(errors[:16]))
    if profile["candidate_id"] != candidate.get("candidate_id"):
        raise CreativeFrameAdapterError("Structural profile không bind đúng candidate_id")
    if profile["candidate_profile_sha256"] != candidate.get("profile_sha256"):
        raise CreativeFrameAdapterError("Structural profile không bind đúng candidate profile hash")
    if profile["support_policy"] != _SUPPORT_POLICY:
        raise CreativeFrameAdapterError("Support policy không được basis hỗ trợ")

    observed_by_ref: dict[str, str] = {}
    records: list[tuple[str, dict]] = []
    for edge_kind in _EDGE_KINDS:
        properties = profile["edge_properties"][edge_kind]
        records.append((f"edge_properties.{edge_kind}.material", properties["material"]))
        records.append((f"edge_properties.{edge_kind}.section", properties["section"]))
    records.append(("deck_line_load", profile["deck_line_load"]))
    for label, record in records:
        digest = _source_digest(
            record["source_ref"], record["expected_source_sha256"], label)
        prior = observed_by_ref.setdefault(digest["source_ref"], digest["sha256"])
        if prior != digest["sha256"]:
            raise CreativeFrameAdapterError(f"Một source_ref có nhiều digest: {digest['source_ref']}")
    return [
        {"source_ref": source_ref, "sha256": observed_by_ref[source_ref]}
        for source_ref in sorted(observed_by_ref)
    ]


def _structural_profile_sha256(profile: dict, source_digests: list[dict]) -> str:
    return _sha256_json({"profile": profile, "source_digests": source_digests})


def _node_distance(node_i: dict, node_j: dict) -> float:
    return math.hypot(
        float(node_j["x_m"]) - float(node_i["x_m"]),
        float(node_j["y_m"]) - float(node_i["y_m"]),
    )


def _build_frame_model(
    candidate: dict,
    structural_profile: dict,
    structural_profile_sha256: str,
    basis: dict,
) -> tuple[dict, dict]:
    graph = candidate["graph"]
    topology = candidate["genome"]["topology"]
    nodes = {node["id"]: node for node in graph["nodes"]}
    coordinates = [(float(node["x_m"]), float(node["y_m"])) for node in graph["nodes"]]
    if len(set(coordinates)) != len(coordinates):
        raise CreativeFrameAdapterError("Graph có nút đồng tọa độ ngoài representation đã hợp nhất")

    support_nodes = sorted(
        (node for node in graph["nodes"] if node.get("support") is True),
        key=lambda node: (float(node["x_m"]), node["id"]),
    )
    if len(support_nodes) != 2 or support_nodes[0]["id"] == support_nodes[1]["id"]:
        raise CreativeFrameAdapterError("Adapter yêu cầu đúng hai chân vòm phân biệt")
    if not float(support_nodes[0]["x_m"]) < float(support_nodes[1]["x_m"]):
        raise CreativeFrameAdapterError("Hai chân vòm phải có thứ tự trái-phải rõ ràng")
    if topology in {"THROUGH_ARCH", "NETWORK_ARCH"}:
        if any(node["kind"] != "ARCH_DECK" for node in support_nodes):
            raise CreativeFrameAdapterError("Tied arch phải dùng nút chân vòm ARCH_DECK đã hợp nhất")
        if any(edge["kind"] == "END_POST" for edge in graph["edges"]):
            raise CreativeFrameAdapterError("Tied arch đã hợp nhất không được còn END_POST")

    used_kinds = {edge.get("kind") for edge in graph["edges"]}
    unknown_kinds = sorted(repr(kind) for kind in used_kinds - set(_EDGE_KINDS))
    if unknown_kinds:
        raise CreativeFrameAdapterError(f"Edge kind không được ánh xạ: {unknown_kinds}")
    min_length = float(basis["minimum_element_length_m"])
    for edge in graph["edges"]:
        if edge["from"] not in nodes or edge["to"] not in nodes:
            raise CreativeFrameAdapterError(f"Edge {edge.get('id')} tham chiếu node mồ côi")
        if _node_distance(nodes[edge["from"]], nodes[edge["to"]]) <= min_length:
            raise CreativeFrameAdapterError(f"Edge {edge['id']} zero-length hoặc quá ngắn")

    materials = []
    sections = []
    for edge_kind in _EDGE_KINDS:
        if edge_kind not in used_kinds:
            continue
        properties = structural_profile["edge_properties"][edge_kind]
        materials.append({
            "id": f"MAT_{edge_kind}",
            "elastic_modulus_GPa": float(properties["material"]["elastic_modulus_GPa"]),
            "source_ref": properties["material"]["source_ref"],
        })
        sections.append({
            "id": f"SEC_{edge_kind}",
            "area_m2": float(properties["section"]["area_m2"]),
            "inertia_m4": float(properties["section"]["inertia_m4"]),
            "source_ref": properties["section"]["source_ref"],
        })

    elements = []
    for edge in graph["edges"]:
        edge_kind = edge["kind"]
        elements.append({
            "id": edge["id"],
            "kind": "FRAME_2D" if edge_kind in _FRAME_EDGE_KINDS else "TRUSS_2D",
            "node_i": edge["from"],
            "node_j": edge["to"],
            "material_id": f"MAT_{edge_kind}",
            "section_id": f"SEC_{edge_kind}",
        })

    supports = [
        {"node_id": support_nodes[0]["id"], "ux": True, "uy": True, "rz": False},
        {"node_id": support_nodes[1]["id"], "ux": False, "uy": True, "rz": False},
    ]

    tributary_lengths: dict[str, float] = {}
    deck_length = 0.0
    deck_edges = [edge for edge in graph["edges"] if edge["kind"] == "DECK"]
    if not deck_edges:
        raise CreativeFrameAdapterError("Graph không có DECK edge để quy đổi tải đường")
    for edge in deck_edges:
        length = _node_distance(nodes[edge["from"]], nodes[edge["to"]])
        deck_length += length
        tributary_lengths[edge["from"]] = tributary_lengths.get(edge["from"], 0.0) + length / 2.0
        tributary_lengths[edge["to"]] = tributary_lengths.get(edge["to"], 0.0) + length / 2.0
    line_load = float(structural_profile["deck_line_load"]["q_kN_m"])
    nodal_loads = [
        {
            "node_id": node["id"],
            "fx_kN": 0.0,
            "fy_kN": -line_load * tributary_lengths[node["id"]],
            "mz_kNm": 0.0,
        }
        for node in graph["nodes"] if node["id"] in tributary_lengths
    ]
    expected_total = line_load * deck_length
    actual_total = -sum(load["fy_kN"] for load in nodal_loads)
    relative_error = abs(actual_total - expected_total) / max(1.0, abs(expected_total))
    tolerance = float(basis["load_transfer"]["relative_tolerance"])
    if relative_error > tolerance:
        raise CreativeFrameAdapterError(
            "Quy đổi tải đường không bảo toàn tổng tải: "
            f"expected={expected_total}, actual={actual_total}, relative_error={relative_error}")
    load_conservation = {
        "status": "PASS",
        "line_load_kN_m": line_load,
        "deck_length_m": deck_length,
        "expected_total_vertical_load_kN": expected_total,
        "actual_total_vertical_load_kN": actual_total,
        "relative_error": relative_error,
        "relative_tolerance": tolerance,
        "tributary_length_by_node_m": [
            {"node_id": node["id"], "tributary_length_m": tributary_lengths[node["id"]]}
            for node in graph["nodes"] if node["id"] in tributary_lengths
        ],
    }

    model = {
        "schema_version": "1.0",
        "model_id": f"F1M-CFA-{candidate['candidate_id'][3:]}-{structural_profile_sha256[:8]}",
        "analysis_type": "LINEAR_ELASTIC_2D_SMALL_DISPLACEMENT",
        "units": {
            "length": "m",
            "force": "kN",
            "moment": "kN_m",
            "elastic_modulus": "GPa",
            "area": "m2",
            "inertia": "m4",
        },
        "nodes": [
            {"id": node["id"], "x_m": float(node["x_m"]), "y_m": float(node["y_m"])}
            for node in graph["nodes"]
        ],
        "materials": materials,
        "sections": sections,
        "elements": elements,
        "supports": supports,
        "load_cases": [{
            "id": "LC_DECK_UDL",
            "combination_status": "USER_SUPPLIED_UNFACTORED",
            "source_ref": structural_profile["deck_line_load"]["source_ref"],
            "nodal_loads": nodal_loads,
        }],
    }
    return model, load_conservation


def _require_screened_candidate(candidate: dict, technical_profile: dict) -> None:
    try:
        creative_shape.validate_candidate(candidate, technical_profile=technical_profile)
    except creative_shape.CreativeShapeError as exc:
        raise CreativeFrameAdapterError(f"Candidate không tái lập/không hợp lệ: {exc}") from exc
    if candidate["screening_status"] != "L0_PASSED" or candidate["all_known_pass"] is not True:
        raise CreativeFrameAdapterError("Chỉ candidate L0_PASSED và all_known_pass mới được vào F1")


def _analysis_identity(candidate: dict, structural_profile_sha256: str) -> dict:
    return {
        "adapter_id": ADAPTER_ID,
        "adapter_version": ADAPTER_VERSION,
        "candidate_sha256": candidate["candidate_sha256"],
        "structural_profile_sha256": structural_profile_sha256,
    }


def analyze_creative_candidate(
    candidate: dict,
    *,
    technical_profile: dict,
    structural_profile: dict,
) -> dict:
    """Tái lập candidate, dựng model F1, chạy solver và trả manifest có hash."""
    _require_screened_candidate(candidate, technical_profile)
    basis = load_adapter_basis()
    source_digests = validate_structural_profile(structural_profile, candidate)
    structural_sha256 = _structural_profile_sha256(structural_profile, source_digests)
    model, load_conservation = _build_frame_model(
        candidate, structural_profile, structural_sha256, basis)
    try:
        frame_result = frame_f1.analyze_frame_model(model)
    except frame_f1.FrameF1Error as exc:
        raise CreativeFrameAdapterError(f"Mô hình F1 do adapter tạo không hợp lệ: {exc}") from exc
    adapter_source_digests = _adapter_source_digests()
    analysis = {
        "schema_version": "1.0",
        "analysis_id": f"CFA-{_sha256_json(_analysis_identity(candidate, structural_sha256))[:16]}",
        "adapter": {"id": ADAPTER_ID, "version": ADAPTER_VERSION},
        "adapter_source_sha256": _sha256_json(adapter_source_digests),
        "adapter_source_digests": adapter_source_digests,
        "claim_level": CLAIM_LEVEL,
        "design_verdict_authority": DESIGN_VERDICT_AUTHORITY,
        "technical_scope": TECHNICAL_SCOPE,
        "status": frame_result["status"],
        "candidate": deepcopy(candidate),
        "creative_technical_profile": deepcopy(technical_profile),
        "structural_profile": deepcopy(structural_profile),
        "frame_model": model,
        "frame_result": frame_result,
        "manifest": {
            "candidate_id": candidate["candidate_id"],
            "candidate_sha256": candidate["candidate_sha256"],
            "geometry_sha256": candidate["geometry_sha256"],
            "candidate_profile_sha256": candidate["profile_sha256"],
            "structural_profile_sha256": structural_sha256,
            "model_sha256": frame_result["model_sha256"],
            "frame_result_sha256": frame_result["result_sha256"],
        },
        "basis_hashes": {
            "creative_domain_sha256": candidate["domain_sha256"],
            "adapter_basis_sha256": hashlib.sha256(_BASIS_PATH.read_bytes()).hexdigest(),
            "frame_basis_sha256": frame_result["basis_sha256"],
        },
        "source_digests": source_digests,
        "load_conservation": load_conservation,
        "limitations": list(basis["explicit_limitations"]),
    }
    analysis["analysis_sha256"] = _sha256_json(analysis)
    validate_creative_frame_analysis(analysis)
    return analysis


def validate_creative_frame_analysis(analysis: dict) -> None:
    """Tái lập toàn tuyến candidate -> model -> result và kiểm mọi manifest/hash."""
    if not isinstance(analysis, dict):
        raise CreativeFrameAdapterError("Creative frame analysis phải là object")
    _canonical(analysis)
    errors = _schema_errors(analysis, _ANALYSIS_SCHEMA)
    if errors:
        raise CreativeFrameAdapterError("Creative frame analysis sai schema: " + "; ".join(errors[:20]))
    payload = deepcopy(analysis)
    claimed_sha256 = payload.pop("analysis_sha256")
    actual_sha256 = _sha256_json(payload)
    if claimed_sha256 != actual_sha256:
        raise CreativeFrameAdapterError(
            f"analysis_sha256 không khớp: expected={actual_sha256}, actual={claimed_sha256}")

    basis = load_adapter_basis()
    if analysis["adapter"] != {"id": ADAPTER_ID, "version": ADAPTER_VERSION}:
        raise CreativeFrameAdapterError("Adapter identity/version không khớp runtime")
    expected_adapter_digests = _adapter_source_digests()
    if analysis["adapter_source_digests"] != expected_adapter_digests:
        raise CreativeFrameAdapterError("adapter_source_digests không khớp bytes runtime")
    if analysis["adapter_source_sha256"] != _sha256_json(expected_adapter_digests):
        raise CreativeFrameAdapterError("adapter_source_sha256 không khớp source digests")

    candidate = analysis["candidate"]
    technical_profile = analysis["creative_technical_profile"]
    structural_profile = analysis["structural_profile"]
    _require_screened_candidate(candidate, technical_profile)
    source_digests = validate_structural_profile(structural_profile, candidate)
    structural_sha256 = _structural_profile_sha256(structural_profile, source_digests)
    expected_model, expected_load_conservation = _build_frame_model(
        candidate, structural_profile, structural_sha256, basis)
    if analysis["frame_model"] != expected_model:
        raise CreativeFrameAdapterError("frame_model không tái lập được từ candidate/profile/basis")
    if analysis["load_conservation"] != expected_load_conservation:
        raise CreativeFrameAdapterError("load_conservation không khớp phép quy đổi tributary")
    try:
        expected_frame_result = frame_f1.analyze_frame_model(expected_model)
        frame_f1.validate_frame_result(analysis["frame_result"])
    except frame_f1.FrameF1Error as exc:
        raise CreativeFrameAdapterError(f"frame_result không hợp lệ: {exc}") from exc
    if analysis["frame_result"] != expected_frame_result:
        raise CreativeFrameAdapterError("frame_result không tái lập được từ frame_model")

    expected_manifest = {
        "candidate_id": candidate["candidate_id"],
        "candidate_sha256": candidate["candidate_sha256"],
        "geometry_sha256": candidate["geometry_sha256"],
        "candidate_profile_sha256": candidate["profile_sha256"],
        "structural_profile_sha256": structural_sha256,
        "model_sha256": expected_frame_result["model_sha256"],
        "frame_result_sha256": expected_frame_result["result_sha256"],
    }
    if analysis["manifest"] != expected_manifest:
        raise CreativeFrameAdapterError("Manifest analysis không khớp dữ liệu tái lập")
    expected_basis_hashes = {
        "creative_domain_sha256": candidate["domain_sha256"],
        "adapter_basis_sha256": hashlib.sha256(_BASIS_PATH.read_bytes()).hexdigest(),
        "frame_basis_sha256": expected_frame_result["basis_sha256"],
    }
    if analysis["basis_hashes"] != expected_basis_hashes:
        raise CreativeFrameAdapterError("basis_hashes không khớp bytes và upstream result")
    if analysis["source_digests"] != source_digests:
        raise CreativeFrameAdapterError("source_digests không khớp structural profile")
    if analysis["status"] != expected_frame_result["status"]:
        raise CreativeFrameAdapterError("Status adapter không được khác status F1")
    if analysis["limitations"] != list(basis["explicit_limitations"]):
        raise CreativeFrameAdapterError("Limitations analysis không khớp basis")
    expected_analysis_id = (
        f"CFA-{_sha256_json(_analysis_identity(candidate, structural_sha256))[:16]}"
    )
    if analysis["analysis_id"] != expected_analysis_id:
        raise CreativeFrameAdapterError("analysis_id không khớp identity canonical")
