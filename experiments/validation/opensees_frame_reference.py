"""Đối chứng OpenSees độc lập cho mô hình khung/giàn phẳng BRD-044.

Worker OpenSees chỉ dùng thư viện chuẩn + ``openseespy`` và chạy ở tiến trình
Python riêng. Worker không import bất kỳ solver hay pipeline DYLIGHT nào. Phần
host sau đó mới chạy lại ``frame_f1`` và so theo ID toàn bộ response bằng dung
sai abs+rel đã khóa trong design basis.

Đây là code-verification ở mức IDEA, không phải L2 và không có thẩm quyền kết
luận thiết kế.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.metadata
import json
import math
import os
import platform
import subprocess
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPO_ROOT / "contracts" / "opensees_frame_reference.schema.json"
BASIS_PATH = REPO_ROOT / "docs" / "design_basis" / "opensees_frame_reference_basis.json"
DEFAULT_ARTIFACT_PATH = (
    REPO_ROOT / "experiments" / "validation" / "opensees_brd044_benchmarks.json"
)

REFERENCE_ID = "OPENSEES_FRAME_2D_REFERENCE"
REFERENCE_VERSION = "opensees-frame-reference/0.1.0"
CLAIM_LEVEL = "IDEA"
DESIGN_VERDICT_AUTHORITY = "NONE"
TECHNICAL_SCOPE = (
    "CROSS_IMPLEMENTATION_LINEAR_2D_CODE_VERIFICATION_NO_L2_OR_DESIGN_VERDICT"
)
UNITS = {
    "length": "m",
    "force": "kN",
    "moment": "kN_m",
    "elastic_modulus": "GPa",
    "area": "m2",
    "inertia": "m4",
}
SOURCE_FILES = (
    "experiments/validation/opensees_frame_reference.py",
    "bridge_evolution/creative_shape.py",
    "bridge_evolution/frame_f1.py",
    "bridge_evolution/creative_frame_adapter.py",
    "bridge_evolution/arch_action_f1.py",
    "bridge_evolution/funicular_reference.py",
)
FORBIDDEN_WORKER_MODULES = (
    "bridge_evolution.frame_f1",
    "bridge_evolution.creative_shape",
    "bridge_evolution.creative_frame_adapter",
    "bridge_evolution.arch_action_f1",
    "bridge_evolution.funicular_reference",
)
EDGE_KINDS = (
    "ARCH_RIB",
    "DECK",
    "SPANDREL",
    "END_POST",
    "HANGER",
    "NETWORK_HANGER",
)


class OpenSeesReferenceError(ValueError):
    """Contract, provenance hoặc phép đối chứng BRD-044 không hợp lệ."""


class WorkerInputError(ValueError):
    """Input worker không đạt kiểm tra độc lập tối thiểu."""


def canonical_json(value: object) -> str:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise OpenSeesReferenceError(f"Dữ liệu không thể canonical JSON: {exc}") from exc


def sha256_json(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _file_sha256(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise OpenSeesReferenceError(f"Không đọc được file provenance {path}: {exc}") from exc


def _read_json(path: Path, label: str) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise OpenSeesReferenceError(f"Không đọc được {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise OpenSeesReferenceError(f"{label} phải là JSON object")
    return value


def source_digests() -> list[dict]:
    result = []
    for rel in SOURCE_FILES:
        path = REPO_ROOT / rel
        if not path.is_file():
            raise OpenSeesReferenceError(f"Không tìm thấy source BRD-044/upstream: {rel}")
        result.append({"path": rel, "sha256": _file_sha256(path)})
    return result


def source_sha256() -> str:
    return sha256_json(source_digests())


def _finite_number(value: object) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and math.isfinite(float(value))
    )


def load_basis() -> dict:
    basis = _read_json(BASIS_PATH, "OpenSees reference basis")
    if basis.get("schema_version") != "1.0":
        raise OpenSeesReferenceError("schema_version basis không khớp")
    if basis.get("reference") != {"id": REFERENCE_ID, "version": REFERENCE_VERSION}:
        raise OpenSeesReferenceError("Reference identity/version trong basis không khớp")
    if basis.get("claim_ceiling") != CLAIM_LEVEL:
        raise OpenSeesReferenceError("Basis không được nâng claim khỏi IDEA")
    if basis.get("design_verdict_authority") != DESIGN_VERDICT_AUTHORITY:
        raise OpenSeesReferenceError("Basis phải giữ design_verdict_authority=NONE")
    if basis.get("technical_scope") != TECHNICAL_SCOPE:
        raise OpenSeesReferenceError("technical_scope basis không khớp runtime")
    if basis.get("units") != UNITS:
        raise OpenSeesReferenceError("Hệ đơn vị basis không khớp runtime")
    if basis.get("reference_source_files") != list(SOURCE_FILES):
        raise OpenSeesReferenceError("reference_source_files không khớp runtime")
    observed_source_sha = source_sha256()
    if basis.get("reference_source_sha256") != observed_source_sha:
        raise OpenSeesReferenceError(
            "reference_source_sha256 không khớp bytes runtime: "
            f"expected={basis.get('reference_source_sha256')}, observed={observed_source_sha}"
        )
    expected_tolerances = {
        "displacement_absolute_m",
        "displacement_relative",
        "rotation_absolute_rad",
        "rotation_relative",
        "force_absolute_kN",
        "force_relative",
        "moment_absolute_kNm",
        "moment_relative",
        "equilibrium_force_absolute_kN",
        "equilibrium_force_relative",
        "equilibrium_moment_absolute_kNm",
        "equilibrium_moment_relative",
    }
    tolerances = basis.get("comparison_tolerances")
    if not isinstance(tolerances, dict) or set(tolerances) != expected_tolerances:
        raise OpenSeesReferenceError("comparison_tolerances thiếu hoặc thừa khóa")
    if any(not _finite_number(value) or float(value) <= 0.0 for value in tolerances.values()):
        raise OpenSeesReferenceError("Mọi comparison tolerance phải hữu hạn và > 0")
    minimum_length = basis.get("minimum_element_length_m")
    if not _finite_number(minimum_length) or float(minimum_length) <= 0.0:
        raise OpenSeesReferenceError("minimum_element_length_m phải hữu hạn và > 0")
    limitations = basis.get("explicit_limitations")
    if not isinstance(limitations, list) or not limitations or not all(
        isinstance(item, str) and item.strip() for item in limitations
    ):
        raise OpenSeesReferenceError("Basis phải có explicit_limitations không rỗng")
    sources = basis.get("official_method_sources")
    if not isinstance(sources, list) or len(sources) < 4 or not all(
        isinstance(item, dict)
        and set(item) == {"title", "url"}
        and isinstance(item["title"], str)
        and item["title"].strip()
        and isinstance(item["url"], str)
        and item["url"].startswith("https://opensees.github.io/")
        for item in sources
    ):
        raise OpenSeesReferenceError("Nguồn phương pháp OpenSees trong basis không hợp lệ")
    return basis


def _manual_worker_validate_model(model: object, minimum_length_m: float) -> dict:
    """Kiểm độc lập trong worker, không gọi schema hay code DYLIGHT."""
    if not isinstance(model, dict):
        raise WorkerInputError("Model phải là JSON object")
    try:
        json.dumps(model, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise WorkerInputError(f"Model không phải JSON hữu hạn: {exc}") from exc
    required = {
        "schema_version", "model_id", "analysis_type", "units", "nodes",
        "materials", "sections", "elements", "supports", "load_cases",
    }
    if set(model) != required:
        raise WorkerInputError("Model worker thiếu hoặc thừa top-level key")
    if model["schema_version"] != "1.0":
        raise WorkerInputError("schema_version model không khớp")
    if model["analysis_type"] != "LINEAR_ELASTIC_2D_SMALL_DISPLACEMENT":
        raise WorkerInputError("Worker chỉ nhận LINEAR_ELASTIC_2D_SMALL_DISPLACEMENT")
    if model["units"] != UNITS:
        raise WorkerInputError("Worker chỉ nhận hệ đơn vị m-kN-kN_m-GPa-m2-m4")

    def unique(items: object, label: str) -> dict[str, dict]:
        if not isinstance(items, list) or not items:
            raise WorkerInputError(f"{label} phải là mảng không rỗng")
        result: dict[str, dict] = {}
        for item in items:
            if not isinstance(item, dict) or not isinstance(item.get("id"), str) or not item["id"]:
                raise WorkerInputError(f"{label} có item/id không hợp lệ")
            if item["id"] in result:
                raise WorkerInputError(f"{label} trùng id: {item['id']}")
            result[item["id"]] = item
        return result

    nodes = unique(model["nodes"], "nodes")
    materials = unique(model["materials"], "materials")
    sections = unique(model["sections"], "sections")
    elements = unique(model["elements"], "elements")
    load_cases = unique(model["load_cases"], "load_cases")
    del load_cases

    for node in nodes.values():
        if set(node) != {"id", "x_m", "y_m"} or not all(
            _finite_number(node[key]) for key in ("x_m", "y_m")
        ):
            raise WorkerInputError(f"Node {node.get('id')} sai cấu trúc/toạ độ")
    for material in materials.values():
        if set(material) != {"id", "elastic_modulus_GPa", "source_ref"}:
            raise WorkerInputError(f"Material {material.get('id')} sai cấu trúc")
        if not _finite_number(material["elastic_modulus_GPa"]) or float(
            material["elastic_modulus_GPa"]
        ) <= 0.0:
            raise WorkerInputError(f"Material {material['id']} có E không hợp lệ")
    for section in sections.values():
        if set(section) != {"id", "area_m2", "inertia_m4", "source_ref"}:
            raise WorkerInputError(f"Section {section.get('id')} sai cấu trúc")
        if any(
            not _finite_number(section[key]) or float(section[key]) <= 0.0
            for key in ("area_m2", "inertia_m4")
        ):
            raise WorkerInputError(f"Section {section['id']} có A/I không hợp lệ")
    adjacency = {node_id: set() for node_id in nodes}
    for element in elements.values():
        expected = {"id", "kind", "node_i", "node_j", "material_id", "section_id"}
        if set(element) != expected or element["kind"] not in {"FRAME_2D", "TRUSS_2D"}:
            raise WorkerInputError(f"Element {element.get('id')} sai cấu trúc/kind")
        if element["node_i"] not in nodes or element["node_j"] not in nodes:
            raise WorkerInputError(f"Element {element['id']} tham chiếu node mồ côi")
        if element["material_id"] not in materials or element["section_id"] not in sections:
            raise WorkerInputError(f"Element {element['id']} tham chiếu material/section mồ côi")
        ni, nj = nodes[element["node_i"]], nodes[element["node_j"]]
        length = math.hypot(float(nj["x_m"]) - float(ni["x_m"]),
                            float(nj["y_m"]) - float(ni["y_m"]))
        if length <= minimum_length_m:
            raise WorkerInputError(f"Element {element['id']} zero-length hoặc quá ngắn")
        adjacency[element["node_i"]].add(element["node_j"])
        adjacency[element["node_j"]].add(element["node_i"])

    frame_nodes = {
        endpoint
        for element in elements.values() if element["kind"] == "FRAME_2D"
        for endpoint in (element["node_i"], element["node_j"])
    }
    supports = model["supports"]
    if not isinstance(supports, list) or not supports:
        raise WorkerInputError("supports phải là mảng không rỗng")
    support_nodes: set[str] = set()
    for support in supports:
        if not isinstance(support, dict) or set(support) != {"node_id", "ux", "uy", "rz"}:
            raise WorkerInputError("Support sai cấu trúc")
        node_id = support["node_id"]
        if node_id not in nodes or node_id in support_nodes:
            raise WorkerInputError(f"Support node mồ côi hoặc lặp: {node_id}")
        if not all(isinstance(support[key], bool) for key in ("ux", "uy", "rz")):
            raise WorkerInputError(f"Support {node_id} phải dùng boolean")
        if not any(support[key] for key in ("ux", "uy", "rz")):
            raise WorkerInputError(f"Support {node_id} không khóa DOF nào")
        support_nodes.add(node_id)

    reached = set(support_nodes)
    frontier = list(support_nodes)
    while frontier:
        current = frontier.pop()
        for neighbour in adjacency[current] - reached:
            reached.add(neighbour)
            frontier.append(neighbour)
    for case in model["load_cases"]:
        if not isinstance(case, dict) or set(case) != {
            "id", "combination_status", "source_ref", "nodal_loads"
        }:
            raise WorkerInputError("Load case sai cấu trúc")
        loads = case["nodal_loads"]
        if not isinstance(loads, list) or not loads:
            raise WorkerInputError(f"Load case {case['id']} không có tải")
        seen: set[str] = set()
        nonzero = False
        for load in loads:
            if not isinstance(load, dict) or set(load) != {
                "node_id", "fx_kN", "fy_kN", "mz_kNm"
            }:
                raise WorkerInputError(f"Load case {case['id']} có nodal load sai cấu trúc")
            node_id = load["node_id"]
            if node_id not in nodes or node_id in seen:
                raise WorkerInputError(f"Load node mồ côi hoặc lặp: {node_id}")
            seen.add(node_id)
            values = [load[key] for key in ("fx_kN", "fy_kN", "mz_kNm")]
            if not all(_finite_number(value) for value in values):
                raise WorkerInputError(f"Load tại {node_id} không hữu hạn")
            if node_id not in frame_nodes and abs(float(load["mz_kNm"])) > 0.0:
                raise WorkerInputError(
                    f"Load moment tại nút thuần TRUSS_2D {node_id} nằm ngoài formulation"
                )
            nonzero = nonzero or any(abs(float(value)) > 0.0 for value in values)
        if not nonzero:
            raise WorkerInputError(f"Load case {case['id']} không có tải khác 0")
        missing = sorted(seen - reached)
        if missing:
            raise WorkerInputError(f"Nút tải không có đường tới gối: {missing}")
    return model


def _raw_result_hash(payload: dict) -> str:
    value = deepcopy(payload)
    value.pop("raw_result_sha256", None)
    return sha256_json(value)


def _structured_failure(model: dict, status: str, issue: str) -> dict:
    try:
        model_sha = sha256_json(model)
    except OpenSeesReferenceError:
        model_sha = hashlib.sha256(
            repr(model).encode("utf-8", errors="backslashreplace")
        ).hexdigest()
    model_id = model.get("model_id", "UNKNOWN")
    if not isinstance(model_id, str) or not model_id:
        model_id = "UNKNOWN"
    result = {
        "schema_version": "1.0",
        "status": status,
        "model_id": model_id,
        "model_payload_sha256": model_sha,
        "engine": None,
        "load_case_results": [],
        "issues": [issue],
    }
    result["raw_result_sha256"] = _raw_result_hash(result)
    return result


def _engine_identity(ops: Any) -> dict:
    binary_module = importlib.import_module("openseespywin.opensees")
    binary_path = Path(binary_module.__file__).resolve()
    executable = Path(sys.executable).resolve()
    return {
        "name": "OpenSees",
        "engine_version": str(ops.version()),
        "package_name": "openseespywin",
        "package_version": importlib.metadata.version("openseespywin"),
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "python_executable_sha256": hashlib.sha256(executable.read_bytes()).hexdigest(),
        "binary_file_name": binary_path.name,
        "binary_sha256": hashlib.sha256(binary_path.read_bytes()).hexdigest(),
        "worker_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }


def _solve_one_case(ops: Any, model: dict, load_case: dict) -> dict:
    nodes = {item["id"]: item for item in model["nodes"]}
    materials = {item["id"]: item for item in model["materials"]}
    sections = {item["id"]: item for item in model["sections"]}
    node_tags = {item["id"]: index + 1 for index, item in enumerate(model["nodes"])}
    material_tags = {
        item["id"]: index + 1 for index, item in enumerate(model["materials"])
    }
    element_tags = {
        item["id"]: index + 1 for index, item in enumerate(model["elements"])
    }
    frame_nodes = {
        node_id
        for element in model["elements"] if element["kind"] == "FRAME_2D"
        for node_id in (element["node_i"], element["node_j"])
    }
    support_map = {item["node_id"]: item for item in model["supports"]}

    try:
        ops.wipe()
        ops.model("basic", "-ndm", 2, "-ndf", 3)
        for node in model["nodes"]:
            ops.node(node_tags[node["id"]], float(node["x_m"]), float(node["y_m"]))
        for material in model["materials"]:
            modulus_kN_m2 = float(material["elastic_modulus_GPa"]) * 1_000_000.0
            ops.uniaxialMaterial("Elastic", material_tags[material["id"]], modulus_kN_m2)
        for element in model["elements"]:
            tag = element_tags[element["id"]]
            ni, nj = node_tags[element["node_i"]], node_tags[element["node_j"]]
            material = materials[element["material_id"]]
            section = sections[element["section_id"]]
            modulus_kN_m2 = float(material["elastic_modulus_GPa"]) * 1_000_000.0
            if element["kind"] == "FRAME_2D":
                ops.geomTransf("Linear", tag)
                ops.element(
                    "elasticBeamColumn",
                    tag,
                    ni,
                    nj,
                    float(section["area_m2"]),
                    modulus_kN_m2,
                    float(section["inertia_m4"]),
                    tag,
                )
            else:
                ops.element(
                    "Truss",
                    tag,
                    ni,
                    nj,
                    float(section["area_m2"]),
                    material_tags[element["material_id"]],
                )
        for node in model["nodes"]:
            node_id = node["id"]
            support = support_map.get(node_id)
            ux = int(bool(support and support["ux"]))
            uy = int(bool(support and support["uy"]))
            rz = int(bool(support and support["rz"]) or node_id not in frame_nodes)
            ops.fix(node_tags[node_id], ux, uy, rz)

        ops.timeSeries("Linear", 1)
        ops.pattern("Plain", 1, 1)
        for load in load_case["nodal_loads"]:
            ops.load(
                node_tags[load["node_id"]],
                float(load["fx_kN"]),
                float(load["fy_kN"]),
                float(load["mz_kNm"]),
            )
        ops.system("BandGeneral")
        ops.numberer("RCM")
        ops.constraints("Plain")
        ops.integrator("LoadControl", 1.0)
        ops.algorithm("Linear")
        ops.analysis("Static")
        return_code = int(ops.analyze(1))
        if return_code != 0:
            return {
                "load_case_id": load_case["id"],
                "status": "SOLVER_FAILED",
                "analyze_return_code": return_code,
                "nodal_displacements": [],
                "reactions": [],
                "element_end_forces": [],
                "max_translation_m": None,
                "max_rotation_rad": None,
                "issues": [f"OpenSees analyze trả mã {return_code}"],
            }
        ops.reactions()
        displacements = []
        for node in model["nodes"]:
            values = list(ops.nodeDisp(node_tags[node["id"]]))
            if len(values) != 3 or not all(_finite_number(value) for value in values):
                raise WorkerInputError(f"OpenSees trả displacement sai tại {node['id']}")
            displacements.append({
                "node_id": node["id"],
                "ux_m": float(values[0]),
                "uy_m": float(values[1]),
                "rz_rad": float(values[2]),
            })
        reactions = []
        for support in model["supports"]:
            values = list(ops.nodeReaction(node_tags[support["node_id"]]))
            if len(values) != 3 or not all(_finite_number(value) for value in values):
                raise WorkerInputError(
                    f"OpenSees trả reaction sai tại {support['node_id']}"
                )
            reactions.append({
                "node_id": support["node_id"],
                "fx_kN": float(values[0]),
                "fy_kN": float(values[1]),
                "mz_kNm": float(values[2]),
            })
        element_forces = []
        for element in model["elements"]:
            values = list(ops.eleResponse(element_tags[element["id"]], "localForce"))
            if len(values) != 6 or not all(_finite_number(value) for value in values):
                raise WorkerInputError(
                    f"OpenSees trả localForce sai tại {element['id']}: {values}"
                )
            element_forces.append({
                "element_id": element["id"],
                "axial_i_kN": float(values[0]),
                "shear_i_kN": float(values[1]),
                "moment_i_kNm": float(values[2]),
                "axial_j_kN": float(values[3]),
                "shear_j_kN": float(values[4]),
                "moment_j_kNm": float(values[5]),
            })
        max_translation = max(
            math.hypot(item["ux_m"], item["uy_m"]) for item in displacements
        )
        max_rotation = max(abs(item["rz_rad"]) for item in displacements)
        return {
            "load_case_id": load_case["id"],
            "status": "CONVERGED",
            "analyze_return_code": return_code,
            "nodal_displacements": displacements,
            "reactions": reactions,
            "element_end_forces": element_forces,
            "max_translation_m": max_translation,
            "max_rotation_rad": max_rotation,
            "issues": [],
        }
    except Exception as exc:  # worker phải trả lỗi có cấu trúc
        return {
            "load_case_id": load_case["id"],
            "status": "SOLVER_FAILED",
            "analyze_return_code": None,
            "nodal_displacements": [],
            "reactions": [],
            "element_end_forces": [],
            "max_translation_m": None,
            "max_rotation_rad": None,
            "issues": [f"{type(exc).__name__}: {exc}"],
        }
    finally:
        try:
            ops.wipe()
        except Exception:
            pass


def worker_solve(model: object, site_packages: str | None = None) -> dict:
    """Entry point độc lập; không được gọi bất kỳ module DYLIGHT nào."""
    if site_packages:
        path = str(Path(site_packages).resolve())
        if path not in sys.path:
            sys.path.insert(0, path)
    minimum_length = 1e-9
    try:
        checked = _manual_worker_validate_model(model, minimum_length)
    except Exception as exc:
        if isinstance(model, dict):
            return _structured_failure(model, "SOLVER_FAILED", f"{type(exc).__name__}: {exc}")
        fallback = {"model_id": "UNKNOWN", "invalid_input": repr(model)}
        return _structured_failure(fallback, "SOLVER_FAILED", f"{type(exc).__name__}: {exc}")
    try:
        ops = importlib.import_module("openseespy.opensees")
        engine = _engine_identity(ops)
    except Exception as exc:
        return _structured_failure(
            checked, "BACKEND_UNAVAILABLE", f"{type(exc).__name__}: {exc}"
        )
    load_results = [_solve_one_case(ops, checked, case) for case in checked["load_cases"]]
    issues = [issue for case in load_results for issue in case["issues"]]
    status = "CONVERGED" if all(
        case["status"] == "CONVERGED" for case in load_results
    ) else "SOLVER_FAILED"
    result = {
        "schema_version": "1.0",
        "status": status,
        "model_id": checked["model_id"],
        "model_payload_sha256": sha256_json(checked),
        "engine": engine,
        "load_case_results": load_results,
        "issues": issues,
    }
    result["raw_result_sha256"] = _raw_result_hash(result)
    return result


def _host_validate_model(model: dict) -> None:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from bridge_evolution.frame_f1 import FrameF1Error, validate_frame_model

    try:
        validate_frame_model(model)
    except FrameF1Error as exc:
        raise OpenSeesReferenceError(f"Model F1 host không hợp lệ: {exc}") from exc


def run_opensees_model(
    model: dict,
    *,
    python_executable: str | Path,
    site_packages: str | Path | None = None,
    timeout_seconds: float = 30.0,
) -> dict:
    """Chạy worker tách tiến trình; không fallback khi backend thiếu/hỏng."""
    _host_validate_model(model)
    load_basis()
    executable = Path(python_executable)
    if not executable.is_file():
        return _structured_failure(
            model, "BACKEND_UNAVAILABLE", "Không tìm thấy Python worker đã chỉ định"
        )
    command = [str(executable), str(Path(__file__).resolve()), "worker"]
    if site_packages is not None:
        site_path = Path(site_packages)
        if not site_path.is_dir():
            return _structured_failure(
                model, "BACKEND_UNAVAILABLE", "Không tìm thấy site-packages đã chỉ định"
            )
        command.extend(["--site-packages", str(site_path)])
    environment = dict(os.environ)
    environment["PYTHONNOUSERSITE"] = "1"
    environment.pop("PYTHONPATH", None)
    try:
        process = subprocess.run(
            command,
            input=canonical_json(model),
            text=True,
            encoding="utf-8",
            errors="strict",
            capture_output=True,
            cwd=REPO_ROOT,
            env=environment,
            timeout=float(timeout_seconds),
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return _structured_failure(model, "BACKEND_UNAVAILABLE", f"{type(exc).__name__}: {exc}")
    if process.returncode != 0:
        issue = process.stderr.strip() or process.stdout.strip() or "worker không có chẩn đoán"
        return _structured_failure(
            model,
            "SOLVER_FAILED",
            f"Worker process return code {process.returncode}: {issue[:2000]}",
        )
    try:
        result = json.loads(process.stdout)
    except json.JSONDecodeError as exc:
        return _structured_failure(
            model,
            "SOLVER_FAILED",
            f"Worker stdout không phải JSON duy nhất: {exc}",
        )
    try:
        validate_raw_result(result, model=model)
    except OpenSeesReferenceError as exc:
        return _structured_failure(model, "SOLVER_FAILED", f"Worker result invalid: {exc}")
    if result["status"] == "CONVERGED":
        executable_sha = _file_sha256(executable)
        if result["engine"]["python_executable_sha256"] != executable_sha:
            return _structured_failure(
                model, "SOLVER_FAILED", "Worker khai sai python_executable_sha256"
            )
        expected_worker_sha = _file_sha256(Path(__file__))
        if result["engine"]["worker_source_sha256"] != expected_worker_sha:
            return _structured_failure(
                model, "SOLVER_FAILED", "Worker source bytes không khớp host"
            )
    return result


def validate_raw_result(result: object, *, model: dict) -> None:
    if not isinstance(result, dict):
        raise OpenSeesReferenceError("Raw OpenSees result phải là object")
    required = {
        "schema_version", "status", "model_id", "model_payload_sha256", "engine",
        "load_case_results", "issues", "raw_result_sha256",
    }
    if set(result) != required:
        raise OpenSeesReferenceError("Raw result thiếu hoặc thừa key")
    if result["schema_version"] != "1.0":
        raise OpenSeesReferenceError("Raw result schema_version không khớp")
    if result["status"] not in {"CONVERGED", "SOLVER_FAILED", "BACKEND_UNAVAILABLE"}:
        raise OpenSeesReferenceError("Raw result status không hợp lệ")
    if result["model_id"] != model["model_id"]:
        raise OpenSeesReferenceError("Raw result model_id không khớp")
    if result["model_payload_sha256"] != sha256_json(model):
        raise OpenSeesReferenceError("Raw result không bind đúng model payload")
    if result["raw_result_sha256"] != _raw_result_hash(result):
        raise OpenSeesReferenceError("raw_result_sha256 không khớp")
    if not isinstance(result["issues"], list) or not all(
        isinstance(item, str) and item for item in result["issues"]
    ):
        raise OpenSeesReferenceError("Raw result issues không hợp lệ")
    if result["status"] == "BACKEND_UNAVAILABLE":
        if result["engine"] is not None or result["load_case_results"]:
            raise OpenSeesReferenceError("BACKEND_UNAVAILABLE không được mang engine/case")
        if not result["issues"]:
            raise OpenSeesReferenceError("BACKEND_UNAVAILABLE phải có issue")
        return
    if result["status"] == "SOLVER_FAILED" and result["engine"] is None:
        if result["load_case_results"] or not result["issues"]:
            raise OpenSeesReferenceError("Process-level SOLVER_FAILED sai cấu trúc")
        return
    engine = result["engine"]
    expected_engine_keys = {
        "name", "engine_version", "package_name", "package_version",
        "python_version", "python_implementation", "python_executable_sha256",
        "binary_file_name", "binary_sha256", "worker_source_sha256",
    }
    if not isinstance(engine, dict) or set(engine) != expected_engine_keys:
        raise OpenSeesReferenceError("Engine provenance thiếu hoặc thừa key")
    if engine["name"] != "OpenSees" or engine["package_name"] != "openseespywin":
        raise OpenSeesReferenceError("Engine identity không phải OpenSees/openseespywin")
    for field in ("python_executable_sha256", "binary_sha256", "worker_source_sha256"):
        value = engine[field]
        if not isinstance(value, str) or len(value) != 64 or any(
            char not in "0123456789abcdef" for char in value
        ):
            raise OpenSeesReferenceError(f"Engine {field} không phải SHA-256")
    for field in (
        "engine_version", "package_version", "python_version",
        "python_implementation", "binary_file_name",
    ):
        if not isinstance(engine[field], str) or not engine[field]:
            raise OpenSeesReferenceError(f"Engine {field} phải là string không rỗng")
    if not isinstance(result["load_case_results"], list):
        raise OpenSeesReferenceError("load_case_results phải là array")
    expected_ids = [item["id"] for item in model["load_cases"]]
    actual_ids = [item.get("load_case_id") for item in result["load_case_results"]]
    if actual_ids != expected_ids:
        raise OpenSeesReferenceError("Raw load case IDs/order không khớp model")
    if result["status"] == "CONVERGED" and result["issues"]:
        raise OpenSeesReferenceError("Raw CONVERGED không được có issues")
    if result["status"] == "SOLVER_FAILED" and not result["issues"]:
        raise OpenSeesReferenceError("Raw SOLVER_FAILED phải có issue")
    node_ids = {item["id"] for item in model["nodes"]}
    support_ids = {item["node_id"] for item in model["supports"]}
    element_ids = {item["id"] for item in model["elements"]}
    for case in result["load_case_results"]:
        if set(case) != {
            "load_case_id", "status", "analyze_return_code", "nodal_displacements",
            "reactions", "element_end_forces", "max_translation_m", "max_rotation_rad",
            "issues",
        }:
            raise OpenSeesReferenceError("Raw load case thiếu hoặc thừa key")
        if case.get("status") == "SOLVER_FAILED":
            if result["status"] != "SOLVER_FAILED":
                raise OpenSeesReferenceError("Raw CONVERGED chứa load case SOLVER_FAILED")
            if not case.get("issues"):
                raise OpenSeesReferenceError("Load case SOLVER_FAILED phải có issue")
            if any(case.get(key) for key in (
                "nodal_displacements", "reactions", "element_end_forces"
            )):
                raise OpenSeesReferenceError("Load case SOLVER_FAILED không được có response")
            if case.get("max_translation_m") is not None or case.get("max_rotation_rad") is not None:
                raise OpenSeesReferenceError("Load case SOLVER_FAILED không được có max response")
            continue
        if case.get("status") != "CONVERGED" or case.get("analyze_return_code") != 0:
            raise OpenSeesReferenceError("Load case status/return code không hợp lệ")
        if case.get("issues") != []:
            raise OpenSeesReferenceError("Load case CONVERGED không được có issue")
        if {item["node_id"] for item in case["nodal_displacements"]} != node_ids:
            raise OpenSeesReferenceError("Raw displacement node set không khớp model")
        if {item["node_id"] for item in case["reactions"]} != support_ids:
            raise OpenSeesReferenceError("Raw reaction node set không khớp supports")
        if {item["element_id"] for item in case["element_end_forces"]} != element_ids:
            raise OpenSeesReferenceError("Raw element force set không khớp model")
        numeric_groups = (
            (case["nodal_displacements"], ("ux_m", "uy_m", "rz_rad")),
            (case["reactions"], ("fx_kN", "fy_kN", "mz_kNm")),
            (case["element_end_forces"], (
                "axial_i_kN", "shear_i_kN", "moment_i_kNm",
                "axial_j_kN", "shear_j_kN", "moment_j_kNm",
            )),
        )
        for items, fields in numeric_groups:
            for item in items:
                id_key = "element_id" if "element_id" in item else "node_id"
                if set(item) != {id_key, *fields}:
                    raise OpenSeesReferenceError("Raw response thiếu hoặc thừa key")
                if not all(_finite_number(item[field]) for field in fields):
                    raise OpenSeesReferenceError("Raw result chứa response không hữu hạn")
        if not _finite_number(case["max_translation_m"]) or not _finite_number(
            case["max_rotation_rad"]
        ):
            raise OpenSeesReferenceError("Raw max response không hữu hạn")
        derived_translation = max(
            math.hypot(float(item["ux_m"]), float(item["uy_m"]))
            for item in case["nodal_displacements"]
        )
        derived_rotation = max(
            abs(float(item["rz_rad"])) for item in case["nodal_displacements"]
        )
        if not math.isclose(
            float(case["max_translation_m"]), derived_translation,
            rel_tol=1e-12, abs_tol=1e-15,
        ):
            raise OpenSeesReferenceError("Raw max_translation_m không tái lập từ nodes")
        if not math.isclose(
            float(case["max_rotation_rad"]), derived_rotation,
            rel_tol=1e-12, abs_tol=1e-15,
        ):
            raise OpenSeesReferenceError("Raw max_rotation_rad không tái lập từ nodes")
    if result["status"] == "SOLVER_FAILED" and all(
        case.get("status") == "CONVERGED" for case in result["load_case_results"]
    ):
        raise OpenSeesReferenceError("Raw SOLVER_FAILED không có case thất bại")


def _index_exact(items: list[dict], key: str, expected: set[str], label: str) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for item in items:
        item_id = item[key]
        if item_id in result:
            raise OpenSeesReferenceError(f"{label} trùng {key}: {item_id}")
        result[item_id] = item
    if set(result) != expected:
        raise OpenSeesReferenceError(
            f"{label} ID set không khớp: expected={sorted(expected)}, actual={sorted(result)}"
        )
    return result


def _normalized_error(a: float, b: float, absolute: float, relative: float) -> tuple[float, float]:
    error = abs(float(a) - float(b))
    denominator = float(absolute) + float(relative) * max(abs(float(a)), abs(float(b)))
    return error, error / denominator


def _equilibrium(model: dict, raw_case: dict, tolerances: dict) -> dict:
    nodes = {item["id"]: item for item in model["nodes"]}
    load_case = next(item for item in model["load_cases"] if item["id"] == raw_case["load_case_id"])
    fx = fy = mz = 0.0
    force_scale = 0.0
    moment_scale = 0.0
    for load in sorted(load_case["nodal_loads"], key=lambda item: item["node_id"]):
        node = nodes[load["node_id"]]
        lfx, lfy, lmz = (float(load["fx_kN"]), float(load["fy_kN"]), float(load["mz_kNm"]))
        term = float(node["x_m"]) * lfy - float(node["y_m"]) * lfx + lmz
        fx += lfx
        fy += lfy
        mz += term
        force_scale += abs(lfx) + abs(lfy)
        moment_scale += abs(term)
    for reaction in sorted(raw_case["reactions"], key=lambda item: item["node_id"]):
        node = nodes[reaction["node_id"]]
        rfx, rfy, rmz = (
            float(reaction["fx_kN"]),
            float(reaction["fy_kN"]),
            float(reaction["mz_kNm"]),
        )
        term = float(node["x_m"]) * rfy - float(node["y_m"]) * rfx + rmz
        fx += rfx
        fy += rfy
        mz += term
        force_scale += abs(rfx) + abs(rfy)
        moment_scale += abs(term)
    force_denominator = (
        float(tolerances["equilibrium_force_absolute_kN"])
        + float(tolerances["equilibrium_force_relative"]) * max(1.0, force_scale)
    )
    moment_denominator = (
        float(tolerances["equilibrium_moment_absolute_kNm"])
        + float(tolerances["equilibrium_moment_relative"]) * max(1.0, moment_scale)
    )
    fx_norm = abs(fx) / force_denominator
    fy_norm = abs(fy) / force_denominator
    mz_norm = abs(mz) / moment_denominator
    return {
        "load_case_id": raw_case["load_case_id"],
        "fx_residual_kN": fx,
        "fy_residual_kN": fy,
        "mz_residual_kNm": mz,
        "force_scale_kN": force_scale,
        "moment_scale_kNm": moment_scale,
        "fx_normalized": fx_norm,
        "fy_normalized": fy_norm,
        "mz_normalized": mz_norm,
        "max_normalized": max(fx_norm, fy_norm, mz_norm),
    }


def compare_to_frame_f1(model: dict, raw_result: dict) -> tuple[dict, dict]:
    """Tự chạy lại F1 rồi so theo ID; không tin F1 result do caller truyền."""
    _host_validate_model(model)
    validate_raw_result(raw_result, model=model)
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from bridge_evolution.frame_f1 import analyze_frame_model

    f1_result = analyze_frame_model(model)
    basis = load_basis()
    tolerances = basis["comparison_tolerances"]
    if raw_result["status"] != "CONVERGED" or f1_result["status"] != "CONVERGED":
        comparison = {
            "status": "NOT_EVALUABLE",
            "compared_value_count": 0,
            "outside_tolerance_count": 0,
            "max_normalized_error": None,
            "worst_response": None,
            "response_differences": [],
            "equilibrium": [],
            "reason_codes": ["ONE_OR_BOTH_SOLVERS_NOT_CONVERGED"],
        }
        return f1_result, comparison

    f1_cases = _index_exact(
        f1_result["load_case_results"], "load_case_id",
        {item["id"] for item in model["load_cases"]}, "F1 load cases",
    )
    raw_cases = _index_exact(
        raw_result["load_case_results"], "load_case_id", set(f1_cases), "OpenSees load cases",
    )
    differences: list[dict] = []

    def add(
        load_case_id: str,
        group: str,
        item_id: str,
        field: str,
        f1_value: float,
        os_value: float,
        absolute_key: str,
        relative_key: str,
    ) -> None:
        absolute = float(tolerances[absolute_key])
        relative = float(tolerances[relative_key])
        abs_error, normalized = _normalized_error(f1_value, os_value, absolute, relative)
        differences.append({
            "load_case_id": load_case_id,
            "response_group": group,
            "item_id": item_id,
            "field": field,
            "frame_f1_value": float(f1_value),
            "opensees_value": float(os_value),
            "absolute_error": abs_error,
            "absolute_tolerance": absolute,
            "relative_tolerance": relative,
            "normalized_error": normalized,
            "comparison_state": "WITHIN_TOLERANCE" if normalized <= 1.0 else "OUTSIDE_TOLERANCE",
        })

    for load_case_id in sorted(f1_cases):
        f1_case, raw_case = f1_cases[load_case_id], raw_cases[load_case_id]
        if f1_case["status"] != "CONVERGED" or raw_case["status"] != "CONVERGED":
            raise OpenSeesReferenceError("Suite CONVERGED chứa case không CONVERGED")
        node_ids = {item["id"] for item in model["nodes"]}
        support_ids = {item["node_id"] for item in model["supports"]}
        element_ids = {item["id"] for item in model["elements"]}
        f1_nodes = _index_exact(f1_case["nodal_displacements"], "node_id", node_ids, "F1 nodes")
        raw_nodes = _index_exact(raw_case["nodal_displacements"], "node_id", node_ids, "OS nodes")
        for node_id in sorted(node_ids):
            for field in ("ux_m", "uy_m"):
                add(load_case_id, "NODAL_DISPLACEMENT", node_id, field,
                    f1_nodes[node_id][field], raw_nodes[node_id][field],
                    "displacement_absolute_m", "displacement_relative")
            add(load_case_id, "NODAL_ROTATION", node_id, "rz_rad",
                f1_nodes[node_id]["rz_rad"], raw_nodes[node_id]["rz_rad"],
                "rotation_absolute_rad", "rotation_relative")
        f1_reactions = _index_exact(f1_case["reactions"], "node_id", support_ids, "F1 reactions")
        raw_reactions = _index_exact(raw_case["reactions"], "node_id", support_ids, "OS reactions")
        for node_id in sorted(support_ids):
            for field in ("fx_kN", "fy_kN"):
                add(load_case_id, "SUPPORT_REACTION", node_id, field,
                    f1_reactions[node_id][field], raw_reactions[node_id][field],
                    "force_absolute_kN", "force_relative")
            add(load_case_id, "SUPPORT_MOMENT", node_id, "mz_kNm",
                f1_reactions[node_id]["mz_kNm"], raw_reactions[node_id]["mz_kNm"],
                "moment_absolute_kNm", "moment_relative")
        f1_forces = _index_exact(
            f1_case["element_end_forces"], "element_id", element_ids, "F1 element forces"
        )
        raw_forces = _index_exact(
            raw_case["element_end_forces"], "element_id", element_ids, "OS element forces"
        )
        for element_id in sorted(element_ids):
            for field in ("axial_i_kN", "shear_i_kN", "axial_j_kN", "shear_j_kN"):
                add(load_case_id, "ELEMENT_END_FORCE", element_id, field,
                    f1_forces[element_id][field], raw_forces[element_id][field],
                    "force_absolute_kN", "force_relative")
            for field in ("moment_i_kNm", "moment_j_kNm"):
                add(load_case_id, "ELEMENT_END_MOMENT", element_id, field,
                    f1_forces[element_id][field], raw_forces[element_id][field],
                    "moment_absolute_kNm", "moment_relative")

    equilibrium = [_equilibrium(model, raw_cases[item["id"]], tolerances)
                   for item in model["load_cases"]]
    outside = [item for item in differences if item["comparison_state"] == "OUTSIDE_TOLERANCE"]
    max_normalized = max(item["normalized_error"] for item in differences)
    worst = max(differences, key=lambda item: item["normalized_error"])
    equilibrium_bad = [item for item in equilibrium if item["max_normalized"] > 1.0]
    reason_codes = []
    if outside:
        reason_codes.append("RESPONSE_DIFFERENCE_OUTSIDE_PREREGISTERED_TOLERANCE")
    if equilibrium_bad:
        reason_codes.append("OPENSEES_GLOBAL_EQUILIBRIUM_RESIDUAL_OUTSIDE_TOLERANCE")
    comparison = {
        "status": (
            "AGREEMENT_WITHIN_PREREGISTERED_TOLERANCE"
            if not reason_codes else "DISCREPANCY_REQUIRES_RECONCILIATION"
        ),
        "compared_value_count": len(differences),
        "outside_tolerance_count": len(outside),
        "max_normalized_error": max_normalized,
        "worst_response": deepcopy(worst),
        "response_differences": differences,
        "equilibrium": equilibrium,
        "reason_codes": reason_codes,
    }
    return f1_result, comparison


def _analytical_models(basis: dict) -> list[dict]:
    data = basis["benchmark_inputs"]["analytical"]
    source_ref = "docs/design_basis/opensees_frame_reference_basis.json"
    material = {
        "id": "MAT1",
        "elastic_modulus_GPa": float(data["elastic_modulus_GPa"]),
        "source_ref": source_ref,
    }
    section = {
        "id": "SEC1",
        "area_m2": float(data["area_m2"]),
        "inertia_m4": float(data["inertia_m4"]),
        "source_ref": source_ref,
    }

    def model(model_id: str, nodes: list[dict], elements: list[dict],
              supports: list[dict], loads: list[dict]) -> dict:
        return {
            "schema_version": "1.0",
            "model_id": model_id,
            "analysis_type": "LINEAR_ELASTIC_2D_SMALL_DISPLACEMENT",
            "units": deepcopy(UNITS),
            "nodes": nodes,
            "materials": [deepcopy(material)],
            "sections": [deepcopy(section)],
            "elements": elements,
            "supports": supports,
            "load_cases": [{
                "id": "LC1",
                "combination_status": "RESEARCH_BENCHMARK",
                "source_ref": source_ref,
                "nodal_loads": loads,
            }],
        }

    axial = data["axial_bar"]
    length = float(axial["length_m"])
    axial_model = model(
        "F1M-BRD044-axial",
        [{"id": "N1", "x_m": 0.0, "y_m": 0.0},
         {"id": "N2", "x_m": length, "y_m": 0.0}],
        [{"id": "E1", "kind": "TRUSS_2D", "node_i": "N1", "node_j": "N2",
          "material_id": "MAT1", "section_id": "SEC1"}],
        [{"node_id": "N1", "ux": True, "uy": True, "rz": True},
         {"node_id": "N2", "ux": False, "uy": True, "rz": False}],
        [{"node_id": "N2", "fx_kN": float(axial["force_kN"]),
          "fy_kN": 0.0, "mz_kNm": 0.0}],
    )
    cantilever = data["cantilever"]
    length = float(cantilever["length_m"])
    cantilever_model = model(
        "F1M-BRD044-cantilever",
        [{"id": "N1", "x_m": 0.0, "y_m": 0.0},
         {"id": "N2", "x_m": length, "y_m": 0.0}],
        [{"id": "E1", "kind": "FRAME_2D", "node_i": "N1", "node_j": "N2",
          "material_id": "MAT1", "section_id": "SEC1"}],
        [{"node_id": "N1", "ux": True, "uy": True, "rz": True}],
        [{"node_id": "N2", "fx_kN": 0.0,
          "fy_kN": float(cantilever["tip_force_kN"]), "mz_kNm": 0.0}],
    )
    beam = data["simple_beam"]
    span = float(beam["span_m"])
    beam_model = model(
        "F1M-BRD044-simple-beam",
        [{"id": "A", "x_m": 0.0, "y_m": 0.0},
         {"id": "M", "x_m": span / 2.0, "y_m": 0.0},
         {"id": "B", "x_m": span, "y_m": 0.0}],
        [{"id": "E1", "kind": "FRAME_2D", "node_i": "A", "node_j": "M",
          "material_id": "MAT1", "section_id": "SEC1"},
         {"id": "E2", "kind": "FRAME_2D", "node_i": "M", "node_j": "B",
          "material_id": "MAT1", "section_id": "SEC1"}],
        [{"node_id": "A", "ux": True, "uy": True, "rz": False},
         {"node_id": "B", "ux": False, "uy": True, "rz": False}],
        [{"node_id": "M", "fx_kN": 0.0,
          "fy_kN": float(beam["midspan_force_kN"]), "mz_kNm": 0.0}],
    )
    return [
        {"case_id": "BRD044-ANALYTICAL-AXIAL", "case_kind": "ANALYTICAL",
         "model": axial_model, "lineage": _empty_lineage("AXIAL_BAR")},
        {"case_id": "BRD044-ANALYTICAL-CANTILEVER", "case_kind": "ANALYTICAL",
         "model": cantilever_model, "lineage": _empty_lineage("CANTILEVER")},
        {"case_id": "BRD044-ANALYTICAL-SIMPLE-BEAM", "case_kind": "ANALYTICAL",
         "model": beam_model, "lineage": _empty_lineage("SIMPLE_BEAM")},
    ]


def _empty_lineage(benchmark_name: str) -> dict:
    return {
        "benchmark_name": benchmark_name,
        "topology": None,
        "candidate_sha256": None,
        "analysis_sha256": None,
        "arch_action_study_sha256": None,
        "funicular_reference_sha256": None,
    }


def _creative_specs(basis: dict) -> list[dict]:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from bridge_evolution import arch_action_f1, creative_frame_adapter, creative_shape
    from bridge_evolution import funicular_reference

    data = basis["benchmark_inputs"]["creative"]
    source_ref = "docs/design_basis/opensees_frame_reference_basis.json"
    source_hash = _file_sha256(BASIS_PATH)

    def sourced(key: str, value: float) -> dict:
        return {
            "value": float(value),
            "source_ref": source_ref,
            "expected_source_sha256": source_hash,
            "clause_id": f"BRD-044-BENCH-{key.upper()}",
        }

    technical_profile = {
        key: sourced(key, value)
        for key, value in data["technical_thresholds"].items()
    }
    result = []
    for topology in data["topologies"]:
        genome = {"topology": topology, **deepcopy(data["genome"])}
        candidate = creative_shape.evaluate_genome(genome, technical_profile)

        def material() -> dict:
            return {
                "elastic_modulus_GPa": float(data["elastic_modulus_GPa"]),
                "source_ref": source_ref,
                "expected_source_sha256": source_hash,
                "clause_id": "BRD-044-BENCH-E",
            }

        def section() -> dict:
            return {
                "area_m2": float(data["section_area_m2"]),
                "inertia_m4": float(data["section_inertia_m4"]),
                "source_ref": source_ref,
                "expected_source_sha256": source_hash,
                "clause_id": "BRD-044-BENCH-A-I",
            }

        structural_profile = {
            "schema_version": "1.0",
            "profile_id": f"CFP-BRD044-{topology}",
            "candidate_id": candidate["candidate_id"],
            "candidate_profile_sha256": candidate["profile_sha256"],
            "support_policy": data["support_policy"],
            "edge_properties": {
                kind: {"material": material(), "section": section()}
                for kind in EDGE_KINDS
            },
            "deck_line_load": {
                "q_kN_m": float(data["deck_line_load_kN_m"]),
                "direction": "GLOBAL_NEGATIVE_Y",
                "source_ref": source_ref,
                "expected_source_sha256": source_hash,
                "clause_id": "BRD-044-BENCH-DECK-UDL",
            },
        }
        analysis = creative_frame_adapter.analyze_creative_candidate(
            candidate,
            technical_profile=technical_profile,
            structural_profile=structural_profile,
        )
        study = arch_action_f1.run_arch_action_study(analysis)
        funicular = funicular_reference.run_funicular_reference(study)
        if study["status"] != "ACTION_DIAGNOSTIC_COMPLETE":
            raise OpenSeesReferenceError(
                f"Creative benchmark {topology} không ACTION_DIAGNOSTIC_COMPLETE"
            )
        result.append({
            "case_id": f"BRD044-CREATIVE-{topology}",
            "case_kind": "CREATIVE_PIPELINE",
            "model": deepcopy(study["study_model"]),
            "lineage": {
                "benchmark_name": "CREATIVE_ARCH_ACTION_MODEL",
                "topology": topology,
                "candidate_sha256": candidate["candidate_sha256"],
                "analysis_sha256": analysis["analysis_sha256"],
                "arch_action_study_sha256": study["study_sha256"],
                "funicular_reference_sha256": funicular["reference_sha256"],
            },
        })
    return result


def expected_case_specs() -> list[dict]:
    basis = load_basis()
    return _analytical_models(basis) + _creative_specs(basis)


def _case_hash(case: dict) -> str:
    payload = deepcopy(case)
    payload.pop("case_sha256", None)
    return sha256_json(payload)


def _suite_hash(suite: dict) -> str:
    payload = deepcopy(suite)
    payload.pop("suite_sha256", None)
    return sha256_json(payload)


def generate_benchmark_suite(
    *,
    python_executable: str | Path,
    site_packages: str | Path | None = None,
) -> dict:
    basis = load_basis()
    basis_sha = _file_sha256(BASIS_PATH)
    digests = source_digests()
    source_sha = sha256_json(digests)
    cases = []
    for spec in expected_case_specs():
        model = deepcopy(spec["model"])
        raw = run_opensees_model(
            model,
            python_executable=python_executable,
            site_packages=site_packages,
        )
        f1_result, comparison = compare_to_frame_f1(model, raw)
        case = {
            "case_id": spec["case_id"],
            "case_kind": spec["case_kind"],
            "lineage": deepcopy(spec["lineage"]),
            "model": model,
            "model_payload_sha256": sha256_json(model),
            "frame_f1_result": f1_result,
            "opensees_result": raw,
            "comparison": comparison,
        }
        case["case_sha256"] = _case_hash(case)
        cases.append(case)
    statuses = {case["opensees_result"]["status"] for case in cases}
    comparisons = {case["comparison"]["status"] for case in cases}
    if statuses != {"CONVERGED"}:
        suite_status = "BACKEND_OR_SOLVER_FAILURE"
    elif comparisons != {"AGREEMENT_WITHIN_PREREGISTERED_TOLERANCE"}:
        suite_status = "RECONCILIATION_REQUIRED"
    else:
        suite_status = "BENCHMARK_SUITE_COMPLETE"
    engines = [case["opensees_result"]["engine"] for case in cases]
    backend_identity = engines[0] if engines and all(item == engines[0] for item in engines) else None
    suite = {
        "schema_version": "1.0",
        "suite_id": "OSR-" + sha256_json({
            "basis_sha256": basis_sha,
            "source_sha256": source_sha,
            "case_sha256": [case["case_sha256"] for case in cases],
        })[:16],
        "reference": {"id": REFERENCE_ID, "version": REFERENCE_VERSION},
        "claim_level": CLAIM_LEVEL,
        "design_verdict_authority": DESIGN_VERDICT_AUTHORITY,
        "technical_scope": TECHNICAL_SCOPE,
        "status": suite_status,
        "basis_sha256": basis_sha,
        "reference_source_sha256": source_sha,
        "reference_source_digests": digests,
        "backend_identity": backend_identity,
        "comparison_tolerances": deepcopy(basis["comparison_tolerances"]),
        "cases": cases,
        "limitations": list(basis["explicit_limitations"]),
    }
    suite["suite_sha256"] = _suite_hash(suite)
    _schema_validate(suite)
    validate_benchmark_suite(suite)
    return suite


def _schema_validate(suite: dict) -> None:
    try:
        import jsonschema
    except ImportError as exc:
        raise OpenSeesReferenceError("Host thiếu jsonschema để kiểm artifact") from exc
    schema = _read_json(SCHEMA_PATH, "OpenSees reference schema")
    jsonschema.Draft202012Validator.check_schema(schema)
    errors = sorted(
        jsonschema.Draft202012Validator(schema).iter_errors(suite),
        key=lambda error: list(error.absolute_path),
    )
    if errors:
        details = [
            f"{'/'.join(str(part) for part in error.absolute_path) or '<root>'}: {error.message}"
            for error in errors[:40]
        ]
        raise OpenSeesReferenceError("Artifact sai schema: " + "; ".join(details))


def validate_benchmark_suite(
    suite: dict,
    *,
    rerun_backend: bool = False,
    python_executable: str | Path | None = None,
    site_packages: str | Path | None = None,
) -> None:
    if not isinstance(suite, dict):
        raise OpenSeesReferenceError("Benchmark suite phải là object")
    canonical_json(suite)
    _schema_validate(suite)
    if suite["suite_sha256"] != _suite_hash(suite):
        raise OpenSeesReferenceError("suite_sha256 không khớp")
    basis = load_basis()
    basis_sha = _file_sha256(BASIS_PATH)
    if suite["reference"] != {"id": REFERENCE_ID, "version": REFERENCE_VERSION}:
        raise OpenSeesReferenceError("Reference identity/version artifact không khớp")
    if suite["claim_level"] != CLAIM_LEVEL:
        raise OpenSeesReferenceError("Artifact không được nâng claim khỏi IDEA")
    if suite["design_verdict_authority"] != DESIGN_VERDICT_AUTHORITY:
        raise OpenSeesReferenceError("Artifact phải giữ design_verdict_authority=NONE")
    if suite["technical_scope"] != TECHNICAL_SCOPE:
        raise OpenSeesReferenceError("Artifact technical_scope không khớp")
    if suite["basis_sha256"] != basis_sha:
        raise OpenSeesReferenceError("Artifact basis_sha256 không khớp bytes runtime")
    digests = source_digests()
    source_sha = sha256_json(digests)
    if suite["reference_source_digests"] != digests:
        raise OpenSeesReferenceError("Artifact source digests không khớp runtime")
    if suite["reference_source_sha256"] != source_sha:
        raise OpenSeesReferenceError("Artifact source sha không khớp digests")
    if suite["comparison_tolerances"] != basis["comparison_tolerances"]:
        raise OpenSeesReferenceError("Artifact tolerance drift khỏi preregistered basis")
    if suite["limitations"] != basis["explicit_limitations"]:
        raise OpenSeesReferenceError("Artifact limitations drift khỏi basis")

    specs = expected_case_specs()
    expected_ids = [item["case_id"] for item in specs]
    actual_ids = [item["case_id"] for item in suite["cases"]]
    if actual_ids != expected_ids:
        raise OpenSeesReferenceError("Benchmark case IDs/order không khớp basis")
    engines = []
    for spec, case in zip(specs, suite["cases"]):
        if case["case_kind"] != spec["case_kind"]:
            raise OpenSeesReferenceError(f"{case['case_id']}: case_kind không khớp")
        if case["lineage"] != spec["lineage"]:
            raise OpenSeesReferenceError(f"{case['case_id']}: lineage không tái lập được")
        if case["model"] != spec["model"]:
            raise OpenSeesReferenceError(f"{case['case_id']}: model không tái lập được")
        if case["model_payload_sha256"] != sha256_json(case["model"]):
            raise OpenSeesReferenceError(f"{case['case_id']}: model payload hash sai")
        validate_raw_result(case["opensees_result"], model=case["model"])
        expected_f1, expected_comparison = compare_to_frame_f1(
            case["model"], case["opensees_result"]
        )
        if case["frame_f1_result"] != expected_f1:
            raise OpenSeesReferenceError(f"{case['case_id']}: F1 result không tái lập")
        if case["comparison"] != expected_comparison:
            raise OpenSeesReferenceError(f"{case['case_id']}: comparison không tái lập")
        if case["case_sha256"] != _case_hash(case):
            raise OpenSeesReferenceError(f"{case['case_id']}: case_sha256 không khớp")
        engines.append(case["opensees_result"]["engine"])
        if rerun_backend:
            if python_executable is None:
                raise OpenSeesReferenceError("rerun_backend cần python_executable")
            rerun = run_opensees_model(
                case["model"],
                python_executable=python_executable,
                site_packages=site_packages,
            )
            if rerun != case["opensees_result"]:
                raise OpenSeesReferenceError(
                    f"{case['case_id']}: backend rerun không byte-deterministic"
                )
    backend = engines[0] if engines and all(item == engines[0] for item in engines) else None
    if suite["backend_identity"] != backend:
        raise OpenSeesReferenceError("backend_identity không khớp các case")
    statuses = {case["opensees_result"]["status"] for case in suite["cases"]}
    comparisons = {case["comparison"]["status"] for case in suite["cases"]}
    if statuses != {"CONVERGED"}:
        expected_status = "BACKEND_OR_SOLVER_FAILURE"
    elif comparisons != {"AGREEMENT_WITHIN_PREREGISTERED_TOLERANCE"}:
        expected_status = "RECONCILIATION_REQUIRED"
    else:
        expected_status = "BENCHMARK_SUITE_COMPLETE"
    if suite["status"] != expected_status:
        raise OpenSeesReferenceError("Suite status không tái lập từ case status")
    expected_id = "OSR-" + sha256_json({
        "basis_sha256": basis_sha,
        "source_sha256": source_sha,
        "case_sha256": [case["case_sha256"] for case in suite["cases"]],
    })[:16]
    if suite["suite_id"] != expected_id:
        raise OpenSeesReferenceError("suite_id không khớp identity canonical")


def validate_artifact_against_handoff(
    artifact_path: str | Path,
    handoff_path: str | Path,
    *,
    rerun_backend: bool = False,
    python_executable: str | Path | None = None,
    site_packages: str | Path | None = None,
) -> None:
    """Kiểm bytes artifact theo hash đã neo trong handoff rồi mới kiểm ngữ nghĩa.

    Hash tự chứa bên trong JSON chỉ phát hiện hỏng vô ý; người có quyền sửa file
    có thể tính lại toàn bộ hash nội bộ. Handoff đã submit và review độc lập là
    trust anchor bên ngoài cần thiết để chặn kiểu reseal đó.
    """
    artifact = Path(artifact_path).resolve()
    handoff = Path(handoff_path).resolve()
    try:
        artifact_rel = str(artifact.relative_to(REPO_ROOT.resolve())).replace("\\", "/")
        handoff.relative_to(REPO_ROOT.resolve())
    except ValueError as exc:
        raise OpenSeesReferenceError("Artifact và handoff phải nằm trong repo") from exc
    handoff_data = _read_json(handoff, "BRD-044 handoff")
    if handoff_data.get("task_id") != "BRD-044":
        raise OpenSeesReferenceError("Handoff trust anchor không thuộc BRD-044")
    matches = [
        item for item in handoff_data.get("artifacts", [])
        if isinstance(item, dict) and item.get("path", "").replace("\\", "/") == artifact_rel
    ]
    if len(matches) != 1:
        raise OpenSeesReferenceError("Handoff phải neo đúng một artifact benchmark BRD-044")
    observed = _file_sha256(artifact)
    if matches[0].get("sha256") != observed:
        raise OpenSeesReferenceError(
            "Artifact bytes drift khỏi handoff trust anchor: "
            f"expected={matches[0].get('sha256')}, observed={observed}"
        )
    suite = _read_json(artifact, "benchmark artifact")
    validate_benchmark_suite(
        suite,
        rerun_backend=rerun_backend,
        python_executable=python_executable,
        site_packages=site_packages,
    )


def _worker_cli(args: argparse.Namespace) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="strict")
    try:
        value = json.loads(sys.stdin.read())
    except json.JSONDecodeError as exc:
        value = {"model_id": "UNKNOWN", "invalid_json": str(exc)}
    result = worker_solve(value, site_packages=args.site_packages)
    sys.stdout.write(canonical_json(result))
    return 0


def _generate_cli(args: argparse.Namespace) -> int:
    suite = generate_benchmark_suite(
        python_executable=args.python_executable,
        site_packages=args.site_packages,
    )
    output = Path(args.output).resolve()
    try:
        output.relative_to(REPO_ROOT.resolve())
    except ValueError as exc:
        raise OpenSeesReferenceError("Output artifact phải nằm trong repo") from exc
    output.write_text(json.dumps(suite, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": suite["status"],
        "suite_id": suite["suite_id"],
        "suite_sha256": suite["suite_sha256"],
        "case_count": len(suite["cases"]),
        "output": str(output.relative_to(REPO_ROOT)).replace("\\", "/"),
    }, ensure_ascii=False, indent=2))
    return 0


def _validate_cli(args: argparse.Namespace) -> int:
    suite = _read_json(Path(args.artifact), "benchmark artifact")
    if args.handoff:
        validate_artifact_against_handoff(
            args.artifact,
            args.handoff,
            rerun_backend=args.rerun_backend,
            python_executable=args.python_executable,
            site_packages=args.site_packages,
        )
    else:
        validate_benchmark_suite(
            suite,
            rerun_backend=args.rerun_backend,
            python_executable=args.python_executable,
            site_packages=args.site_packages,
        )
    print(json.dumps({
        "status": suite["status"],
        "suite_id": suite["suite_id"],
        "suite_sha256": suite["suite_sha256"],
        "case_count": len(suite["cases"]),
        "rerun_backend": bool(args.rerun_backend),
    }, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    worker = sub.add_parser("worker")
    worker.add_argument("--site-packages")
    worker.set_defaults(handler=_worker_cli)
    generate = sub.add_parser("generate")
    generate.add_argument("--python-executable", required=True)
    generate.add_argument("--site-packages")
    generate.add_argument("--output", default=str(DEFAULT_ARTIFACT_PATH))
    generate.set_defaults(handler=_generate_cli)
    validate = sub.add_parser("validate")
    validate.add_argument("artifact", nargs="?", default=str(DEFAULT_ARTIFACT_PATH))
    validate.add_argument("--rerun-backend", action="store_true")
    validate.add_argument("--python-executable")
    validate.add_argument("--site-packages")
    validate.add_argument("--handoff")
    validate.set_defaults(handler=_validate_cli)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args.handler(args))
    except OpenSeesReferenceError as exc:
        print(f"BRD-044 STOP: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
