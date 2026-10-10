"""BRD-045: lớp hardening bất biến cho đối chứng OpenSees F1.

Module này không sửa BRD-044. Worker chạy ở tiến trình riêng, chỉ nạp module
BRD-044 theo đường dẫn file và OpenSeesPy; mọi module ``bridge_evolution`` trong
worker là lỗi fail-closed. Output chỉ là code-verification IDEA/NONE.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import hmac
import importlib
import importlib.metadata
import importlib.util
import json
import math
import os
from pathlib import Path
import platform
import secrets
import subprocess
import sys
import threading
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
BASE_MODULE_PATH = REPO_ROOT / "experiments" / "validation" / "opensees_frame_reference.py"
BASIS_PATH = REPO_ROOT / "docs" / "design_basis" / "opensees_frame_reference_v2_basis.json"
SCHEMA_PATH = REPO_ROOT / "contracts" / "opensees_frame_reference_v2.schema.json"
DEFAULT_SUITE_PATH = REPO_ROOT / "experiments" / "validation" / "opensees_brd045_benchmarks.json"
DEFAULT_NEGATIVE_PATH = REPO_ROOT / "experiments" / "validation" / "opensees_brd045_negative_result.json"

REFERENCE_ID = "OPENSEES_FRAME_2D_REFERENCE_HARDENED"
REFERENCE_VERSION = "opensees-frame-reference/0.2.0"
CLAIM_LEVEL = "IDEA"
DESIGN_VERDICT_AUTHORITY = "NONE"
TECHNICAL_SCOPE = "HARDENED_LINEAR_2D_CODE_VERIFICATION_NO_L2_OR_DESIGN_VERDICT"
SITE_PACKAGES_POLICY = "APPEND_AFTER_EXISTING_PATHS"
FORBIDDEN_RUNTIME_PREFIX = "bridge_evolution"
WORKER_NONCE_ENV = "DYLIGHT_BRD045_WORKER_NONCE"
ISOLATION_PROBE_ENV = "DYLIGHT_BRD045_TEST_ISOLATION_PROBE"
ISOLATION_PROBE_PATH = REPO_ROOT / FORBIDDEN_RUNTIME_PREFIX / "__init__.py"
WORKER_FAILURE_STATUSES = {
    "AUDIT_FAILED",
    "BACKEND_UNAVAILABLE",
    "HOST_VALIDATION_FAILED",
    "INVALID_INPUT",
    "ISOLATION_BREACH",
    "SOLVER_FAILED",
    "WORKER_CRASHED",
    "WORKER_ENVELOPE_INVALID",
    "WORKER_OUTPUT_INVALID",
    "WORKER_TIMEOUT",
}
FORBIDDEN_VERDICT_KEYS = {
    "adequate",
    "capacity",
    "compliant",
    "demand_capacity_ratio",
    "feasible",
    "design_pass",
    "rating",
    "safe",
    "utilization",
    "safety_factor",
    "verified",
    "verdict",
}

REQUIRED_OPENSEES_CALLABLES = (
    "algorithm",
    "analysis",
    "analyze",
    "constraints",
    "eleResponse",
    "element",
    "fix",
    "geomTransf",
    "getEleTags",
    "getFixedDOFs",
    "getFixedNodes",
    "getNodeTags",
    "integrator",
    "load",
    "model",
    "node",
    "nodeCoord",
    "nodeDisp",
    "nodeReaction",
    "numberer",
    "pattern",
    "reactions",
    "system",
    "timeSeries",
    "uniaxialMaterial",
    "version",
    "wipe",
)

UPSTREAM_BRD044_FILES = (
    "experiments/validation/opensees_frame_reference.py",
    "experiments/validation/opensees_brd044_benchmarks.json",
    "contracts/opensees_frame_reference.schema.json",
    "docs/design_basis/opensees_frame_reference_basis.json",
    "tests/test_opensees_frame_reference.py",
)
SOURCE_FILES = (
    "experiments/validation/opensees_frame_reference_v2.py",
    "experiments/validation/opensees_frame_reference.py",
    "bridge_evolution/creative_shape.py",
    "bridge_evolution/frame_f1.py",
    "bridge_evolution/creative_frame_adapter.py",
    "bridge_evolution/arch_action_f1.py",
    "bridge_evolution/funicular_reference.py",
)
TASK_SEALED_FILES = (
    "contracts/opensees_frame_reference_v2.schema.json",
    "tests/test_opensees_frame_reference_v2.py",
)

_BASE: Any | None = None


class HardenedReferenceError(ValueError):
    """Lỗi fail-closed của BRD-045."""


class NegativeEvidencePersistedError(HardenedReferenceError):
    """Dừng suite sau khi bằng chứng âm đã được ghi và tự kiểm hợp lệ."""

    def __init__(self, *, output_path: Path, record_id: str, failure_status: str) -> None:
        self.output_path = output_path
        self.record_id = record_id
        self.failure_status = failure_status
        super().__init__(
            "Worker không CONVERGED; negative evidence đã persist tại "
            f"{output_path} (record_id={record_id}, failure_status={failure_status})"
        )


def canonical_json(value: object) -> str:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise HardenedReferenceError(f"Payload không canonical JSON: {exc}") from exc


def sha256_json(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_json(path: Path, label: str) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HardenedReferenceError(f"Không đọc được {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise HardenedReferenceError(f"{label} phải là object")
    canonical_json(value)
    return value


def _base() -> Any:
    global _BASE
    if _BASE is None:
        spec = importlib.util.spec_from_file_location("_brd044_opensees_reference", BASE_MODULE_PATH)
        if spec is None or spec.loader is None:
            raise HardenedReferenceError("Không nạp được module BRD-044 bất biến")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _BASE = module
    return _BASE


def source_digests() -> list[dict]:
    return [{"path": item, "sha256": _file_sha256(REPO_ROOT / item)} for item in SOURCE_FILES]


def upstream_brd044_digests() -> list[dict]:
    return [
        {"path": item, "sha256": _file_sha256(REPO_ROOT / item)}
        for item in UPSTREAM_BRD044_FILES
    ]


def task_artifact_digests() -> list[dict]:
    return [
        {"path": item, "sha256": _file_sha256(REPO_ROOT / item)}
        for item in TASK_SEALED_FILES
    ]


def load_basis() -> dict:
    basis = _read_json(BASIS_PATH, "BRD-045 basis")
    _reject_forbidden_verdict_keys(basis, "<basis>")
    if basis.get("reference") != {"id": REFERENCE_ID, "version": REFERENCE_VERSION}:
        raise HardenedReferenceError("Reference identity/version trong basis không khớp")
    if basis.get("claim_ceiling") != CLAIM_LEVEL:
        raise HardenedReferenceError("Basis không được nâng claim khỏi IDEA")
    if basis.get("design_verdict_authority") != DESIGN_VERDICT_AUTHORITY:
        raise HardenedReferenceError("Basis phải giữ design_verdict_authority=NONE")
    if basis.get("technical_scope") != TECHNICAL_SCOPE:
        raise HardenedReferenceError("Basis technical_scope không khớp")
    if basis.get("upstream_brd044_artifacts") != upstream_brd044_digests():
        raise HardenedReferenceError("BRD-044 upstream artifact drift")
    if basis.get("task_artifact_digests") != task_artifact_digests():
        raise HardenedReferenceError("Schema/test BRD-045 drift khỏi basis")
    observed = source_digests()
    if basis.get("reference_source_files") != list(SOURCE_FILES):
        raise HardenedReferenceError("Danh sách source trong basis không khớp")
    if basis.get("reference_source_sha256") != sha256_json(observed):
        raise HardenedReferenceError("Source digest BRD-045 drift khỏi basis")
    return basis


def _finite(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _payload_capture(value: object) -> tuple[str, str, str]:
    try:
        text = canonical_json(value)
        kind = "CANONICAL_JSON"
    except HardenedReferenceError:
        text = repr(value)
        kind = "PYTHON_REPR"
    digest = hashlib.sha256(text.encode("utf-8", errors="backslashreplace")).hexdigest()
    return kind, text, digest


def _raw_hash(payload: dict) -> str:
    value = deepcopy(payload)
    value.pop("raw_result_sha256", None)
    return sha256_json(value)


def _envelope_hash(payload: dict) -> str:
    value = deepcopy(payload)
    value.pop("worker_envelope_sha256", None)
    return sha256_json(value)


def _record_hash(payload: dict, key: str) -> str:
    value = deepcopy(payload)
    value.pop(key, None)
    return sha256_json(value)


def _reject_forbidden_verdict_keys(value: object, path: str = "<root>") -> None:
    if isinstance(value, dict):
        found = sorted(FORBIDDEN_VERDICT_KEYS & set(value))
        if found:
            raise HardenedReferenceError(f"Forbidden design-verdict keys tại {path}: {found}")
        for key, item in value.items():
            _reject_forbidden_verdict_keys(item, f"{path}/{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _reject_forbidden_verdict_keys(item, f"{path}/{index}")


def _relative_to(path: Path, root: Path) -> str | None:
    try:
        return str(path.resolve().relative_to(root.resolve())).replace("\\", "/")
    except ValueError:
        return None


def _append_site_packages(site_packages: str | None) -> str | None:
    if site_packages is None:
        return None
    path = str(Path(site_packages).resolve())
    if path in sys.path:
        if sys.path.index(path) != len(sys.path) - 1:
            raise HardenedReferenceError("site-packages đã có precedence cao hơn chính sách append")
    else:
        sys.path.append(path)
    return path


def _engine_identity(
    ops: Any,
    site_packages: str | None,
) -> tuple[dict, dict, dict]:
    shim_name = str(getattr(ops, "__name__", ""))
    if shim_name != "openseespy.opensees":
        raise HardenedReferenceError(f"OpenSees shim module sai: {shim_name}")
    shim_file = getattr(ops, "__file__", None)
    if not shim_file:
        raise HardenedReferenceError("Không xác định được file của OpenSees shim")
    shim_path = Path(shim_file).resolve()
    owner_name = str(getattr(ops.version, "__module__", ""))
    if not owner_name:
        raise HardenedReferenceError("Không xác định được module sở hữu ops.version")
    owner_module = importlib.import_module(owner_name)
    binary_path = Path(owner_module.__file__).resolve()
    package_name = owner_name.split(".", 1)[0]
    shim_package_name = shim_name.split(".", 1)[0]
    site_root = Path(site_packages).resolve() if site_packages else None
    shim_relative = _relative_to(shim_path, site_root) if site_root else shim_path.name
    binary_relative = _relative_to(binary_path, site_root) if site_root else binary_path.name
    if site_root and (shim_relative is None or binary_relative is None):
        raise HardenedReferenceError("OpenSees shim/native không được nạp từ site-packages đã chỉ định")
    callable_bindings = []
    for name in REQUIRED_OPENSEES_CALLABLES:
        function = getattr(ops, name, None)
        native_function = getattr(owner_module, name, None)
        module_name = str(getattr(function, "__module__", ""))
        qualname = str(getattr(function, "__qualname__", ""))
        if not callable(function) or module_name != owner_name or function is not native_function:
            raise HardenedReferenceError(
                f"OpenSees callable {name} không bind trực tiếp vào binary đã pin"
            )
        callable_bindings.append({
            "name": name,
            "module": module_name,
            "qualname": qualname,
            "kind": type(function).__name__,
        })
    executable = Path(sys.executable).resolve()
    identity = {
        "name": "OpenSees",
        "engine_version": str(ops.version()),
        "package_name": package_name,
        "package_version": importlib.metadata.version(package_name),
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "python_executable_sha256": hashlib.sha256(executable.read_bytes()).hexdigest(),
        "binary_file_name": binary_path.name,
        "binary_sha256": hashlib.sha256(binary_path.read_bytes()).hexdigest(),
        "worker_source_sha256": _file_sha256(Path(__file__).resolve()),
    }
    module_contract = {
        "shim_module": shim_name,
        "shim_package_name": shim_package_name,
        "shim_package_version": importlib.metadata.version(shim_package_name),
        "shim_relative_path": str(shim_relative).replace("\\", "/"),
        "shim_sha256": _file_sha256(shim_path),
        "binary_owner_module": owner_name,
        "binary_relative_path": str(binary_relative).replace("\\", "/"),
        "callable_bindings": callable_bindings,
    }
    resolved_sys_path = [str(Path(item).resolve()) if item else "" for item in sys.path]
    runtime_path_audit = {
        "site_packages_path": str(site_root) if site_root else None,
        "site_packages_index": (
            resolved_sys_path.index(str(site_root)) if site_root and str(site_root) in resolved_sys_path
            else None
        ),
        "sys_path": resolved_sys_path,
        "sys_path_sha256": sha256_json(resolved_sys_path),
        "shim_file": str(shim_path),
        "binary_file": str(binary_path),
        "shim_under_site_packages": bool(site_root and shim_relative is not None),
        "binary_under_site_packages": bool(site_root and binary_relative is not None),
    }
    return identity, module_contract, runtime_path_audit


def _origin_record(module_name: str, origin: object) -> dict | None:
    if isinstance(origin, os.PathLike):
        origin = os.fspath(origin)
    if not isinstance(origin, str) or not origin:
        return None
    try:
        path = Path(origin).resolve()
    except (OSError, RuntimeError, ValueError):
        return None
    relative = _relative_to(path, REPO_ROOT / FORBIDDEN_RUNTIME_PREFIX)
    if relative is None:
        return None
    present = path.is_file()
    return {
        "module_name": module_name or "<anonymous>",
        "origin": f"{FORBIDDEN_RUNTIME_PREFIX}/{relative}",
        "origin_state": "PRESENT" if present else "MISSING_AT_AUDIT",
        "sha256": _file_sha256(path) if present else None,
    }


class _RuntimeOriginGuard:
    """Ghi mọi Python code thực thi từ bridge_evolution, kể cả alias rồi bị xóa."""

    def __init__(self) -> None:
        self._records: dict[tuple[str, str], dict] = {}
        self._previous_profile: Any = None
        self._previous_thread_profile: Any = None

    def _remember(self, module_name: str, origin: object) -> None:
        record = _origin_record(module_name, origin)
        if record is not None:
            key = (record["module_name"], record["origin"])
            previous = self._records.get(key)
            # Không để lần quét sau khi file bị xoá làm mất SHA đã quan sát khi
            # frame thực sự chạy. Ngược lại, PRESENT luôn nâng cấp bản ghi MISSING.
            if previous is None or record["origin_state"] == "PRESENT":
                self._records[key] = record

    def _scan_modules(self) -> None:
        for name, module in list(sys.modules.items()):
            if module is None:
                continue
            spec = getattr(module, "__spec__", None)
            origin = getattr(module, "__file__", None) or getattr(spec, "origin", None)
            self._remember(str(name), origin)

    def _profile(self, frame: Any, event: str, arg: Any) -> None:
        if event == "call":
            self._remember(str(frame.f_globals.get("__name__", "<exec>")), frame.f_code.co_filename)
        if self._previous_profile is not None:
            self._previous_profile(frame, event, arg)

    def start(self) -> None:
        self._scan_modules()
        self._previous_profile = sys.getprofile()
        self._previous_thread_profile = threading.getprofile()
        sys.setprofile(self._profile)
        threading.setprofile(self._profile)

    def stop(self) -> None:
        sys.setprofile(self._previous_profile)
        threading.setprofile(self._previous_thread_profile)
        self._scan_modules()

    @property
    def records(self) -> list[dict]:
        return [deepcopy(self._records[key]) for key in sorted(self._records)]


def _execute_isolation_probe() -> None:
    """Test seam nội bộ: chạy đúng ``bridge_evolution/__init__.py`` dưới alias.

    Hàm chỉ được kích bởi keyword private của ``run_opensees_model``; CLI sản
    xuất không expose công tắc này. Mục đích là kiểm end-to-end rằng worker thật
    vừa hội tụ vừa phát hiện/persist code có origin bị cấm.
    """
    path = ISOLATION_PROBE_PATH.resolve()
    if _relative_to(path, REPO_ROOT / FORBIDDEN_RUNTIME_PREFIX) is None or not path.is_file():
        raise HardenedReferenceError("Isolation probe path không hợp lệ")
    spec = importlib.util.spec_from_file_location("_brd045_isolation_probe_alias", path)
    if spec is None or spec.loader is None:
        raise HardenedReferenceError("Không tạo được isolation probe module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)


def _pure_truss_nodes(model: dict) -> set[str]:
    truss = {
        node
        for element in model["elements"]
        if element["kind"] == "TRUSS_2D"
        for node in (element["node_i"], element["node_j"])
    }
    frame = {
        node
        for element in model["elements"]
        if element["kind"] == "FRAME_2D"
        for node in (element["node_i"], element["node_j"])
    }
    return truss - frame


def _artificial_rotation_nodes(model: dict) -> set[str]:
    supports = {item["node_id"]: item for item in model["supports"]}
    return {
        node_id
        for node_id in _pure_truss_nodes(model)
        if not bool(supports.get(node_id, {}).get("rz", False))
    }


class _WipeProxy:
    """Giữ domain sau base solve để đọc phản lực DOF rz nhân tạo."""

    def __init__(self, ops: Any):
        self._ops = ops
        self._wipe_count = 0

    def wipe(self) -> None:
        self._wipe_count += 1
        if self._wipe_count == 1:
            self._ops.wipe()

    @property
    def total_wipe_calls(self) -> int:
        return self._wipe_count

    @property
    def forwarded_wipes(self) -> int:
        return min(self._wipe_count, 1)

    @property
    def suppressed_wipes(self) -> int:
        return max(self._wipe_count - 1, 0)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._ops, name)


def _domain_fingerprint(ops: Any, model: dict) -> dict:
    expected_node_tags = {item["id"]: index + 1 for index, item in enumerate(model["nodes"])}
    expected_element_tags = {
        item["id"]: index + 1 for index, item in enumerate(model["elements"])
    }
    actual_node_tags = sorted(int(value) for value in ops.getNodeTags())
    actual_element_tags = sorted(int(value) for value in ops.getEleTags())
    if actual_node_tags != sorted(expected_node_tags.values()):
        raise HardenedReferenceError("OpenSees node tags không khớp model")
    if actual_element_tags != sorted(expected_element_tags.values()):
        raise HardenedReferenceError("OpenSees element tags không khớp model")
    fixed_nodes = {int(value) for value in ops.getFixedNodes()}
    support_map = {item["node_id"]: item for item in model["supports"]}
    frame_nodes = {
        node_id
        for element in model["elements"] if element["kind"] == "FRAME_2D"
        for node_id in (element["node_i"], element["node_j"])
    }
    bindings = []
    for node in model["nodes"]:
        node_id = node["id"]
        tag = expected_node_tags[node_id]
        coordinates = list(ops.nodeCoord(tag))
        if len(coordinates) != 2 or not all(_finite(value) for value in coordinates):
            raise HardenedReferenceError(f"OpenSees nodeCoord sai tại {node_id}")
        if max(
            abs(float(coordinates[0]) - float(node["x_m"])),
            abs(float(coordinates[1]) - float(node["y_m"])),
        ) > 1e-12:
            raise HardenedReferenceError(f"OpenSees tag↔node coordinate sai tại {node_id}")
        support = support_map.get(node_id)
        expected_fixed_dofs = []
        if support and support["ux"]:
            expected_fixed_dofs.append(1)
        if support and support["uy"]:
            expected_fixed_dofs.append(2)
        if bool(support and support["rz"]) or node_id not in frame_nodes:
            expected_fixed_dofs.append(3)
        observed_fixed_dofs = (
            sorted(int(value) for value in ops.getFixedDOFs(tag)) if tag in fixed_nodes else []
        )
        if observed_fixed_dofs != expected_fixed_dofs:
            raise HardenedReferenceError(
                f"OpenSees fixed DOFs sai tại {node_id}: {observed_fixed_dofs}"
            )
        bindings.append({
            "node_id": node_id,
            "node_tag": tag,
            "x_m": float(coordinates[0]),
            "y_m": float(coordinates[1]),
            "fixed_dofs": observed_fixed_dofs,
        })
    element_bindings = [
        {"element_id": item["id"], "element_tag": expected_element_tags[item["id"]]}
        for item in model["elements"]
    ]
    payload = {
        "node_tags": actual_node_tags,
        "element_tags": actual_element_tags,
        "node_bindings": bindings,
        "element_bindings": element_bindings,
    }
    payload["fingerprint_sha256"] = sha256_json(payload)
    return payload


def _truss_local_force_audit(ops: Any, model: dict) -> list[dict]:
    element_tags = {item["id"]: index + 1 for index, item in enumerate(model["elements"])}
    audit = []
    for element in model["elements"]:
        if element["kind"] != "TRUSS_2D":
            continue
        vector = list(ops.eleResponse(element_tags[element["id"]], "localForce"))
        if not all(_finite(value) for value in vector):
            raise HardenedReferenceError(f"OpenSees localForce không hữu hạn tại {element['id']}")
        audit.append({
            "element_id": element["id"],
            "element_tag": element_tags[element["id"]],
            "component_count": len(vector),
            "raw_local_force": [float(value) for value in vector],
        })
    return audit


def _run_artificial_rotation_positive_control(
    base: Any,
    ops: Any,
    model: dict,
    node_id: str,
    applied_mz_kNm: float,
) -> dict:
    load_case = {
        "id": "BRD045-RZ-POSITIVE-CONTROL",
        "nodal_loads": [{
            "node_id": node_id,
            "fx_kN": 0.0,
            "fy_kN": 0.0,
            "mz_kNm": applied_mz_kNm,
        }],
    }
    proxy = _WipeProxy(ops)
    try:
        result = base._solve_one_case(proxy, model, load_case)
        if result["status"] != "CONVERGED":
            raise HardenedReferenceError(
                "Artificial-rz positive control không hội tụ: " + "; ".join(result["issues"])
            )
        if proxy.total_wipe_calls != 2:
            raise HardenedReferenceError("WipeProxy control không quan sát đúng hai lần wipe")
        fingerprint = _domain_fingerprint(ops, model)
        binding = _lookup(fingerprint["node_bindings"], "node_id", node_id)
        if 3 not in binding["fixed_dofs"]:
            raise HardenedReferenceError("Positive-control node không thực sự fix DOF rz")
        ops.reactions()
        values = list(ops.nodeReaction(binding["node_tag"]))
        if len(values) != 3 or not all(_finite(value) for value in values):
            raise HardenedReferenceError("Positive-control reaction sai cấu trúc")
        observed = float(values[2])
        return {
            "control_id": "ARTIFICIAL_RZ_NONZERO_REACTION",
            "node_id": node_id,
            "node_tag": int(binding["node_tag"]),
            "applied_mz_kNm": float(applied_mz_kNm),
            "observed_reaction_mz_kNm": observed,
            "equilibrium_residual_kNm": observed + float(applied_mz_kNm),
            "control_outcome": "EXPECTED_NONZERO_REACTION_OBSERVED",
            "domain_fingerprint_sha256": fingerprint["fingerprint_sha256"],
            "wipe_proxy": {
                "total_wipe_calls": proxy.total_wipe_calls,
                "forwarded_wipes": proxy.forwarded_wipes,
                "suppressed_wipes": proxy.suppressed_wipes,
            },
        }
    finally:
        try:
            ops.wipe()
        except Exception:
            pass


def _solve_case_with_audit(base: Any, ops: Any, model: dict, load_case: dict) -> tuple[dict, dict]:
    proxy = _WipeProxy(ops)
    result = base._solve_one_case(proxy, model, load_case)
    reactions: list[dict] = []
    constraints: list[dict] = []
    local_forces: list[dict] = []
    fingerprint: dict | None = None
    positive_control: dict | None = None
    audit_status = "NOT_AVAILABLE"
    audit_issues: list[str] = []
    try:
        if result["status"] == "CONVERGED":
            if proxy.total_wipe_calls != 2:
                raise HardenedReferenceError("WipeProxy không quan sát đúng hai lần wipe")
            fingerprint = _domain_fingerprint(ops, model)
            ops.reactions()
            bindings = {
                item["node_id"]: item for item in fingerprint["node_bindings"]
            }
            for node_id in sorted(_artificial_rotation_nodes(model)):
                binding = bindings[node_id]
                if 3 not in binding["fixed_dofs"]:
                    raise HardenedReferenceError(f"DOF rz nhân tạo chưa được fix tại {node_id}")
                values = list(ops.nodeReaction(binding["node_tag"]))
                if len(values) != 3 or not all(_finite(value) for value in values):
                    raise HardenedReferenceError(
                        f"OpenSees trả phản lực DOF nhân tạo sai tại {node_id}: {values}"
                    )
                reactions.append({"node_id": node_id, "mz_kNm": float(values[2])})
                constraints.append({
                    "node_id": node_id,
                    "node_tag": int(binding["node_tag"]),
                    "x_m": float(binding["x_m"]),
                    "y_m": float(binding["y_m"]),
                    "fixed_dofs": list(binding["fixed_dofs"]),
                })
            local_forces = _truss_local_force_audit(ops, model)
            audit_status = "COMPLETE"
    except Exception as exc:
        audit_status = "AUDIT_FAILED"
        audit_issues = [f"{type(exc).__name__}: {exc}"]
        result = {
            "load_case_id": load_case["id"],
            "status": "SOLVER_FAILED",
            "analyze_return_code": None,
            "nodal_displacements": [],
            "reactions": [],
            "element_end_forces": [],
            "max_translation_m": None,
            "max_rotation_rad": None,
            "issues": [f"AUDIT_FAILED: {type(exc).__name__}: {exc}"],
        }
        reactions = []
    finally:
        try:
            ops.wipe()
        except Exception:
            pass
    if audit_status == "COMPLETE" and constraints:
        try:
            positive_control = _run_artificial_rotation_positive_control(
                base,
                ops,
                model,
                constraints[0]["node_id"],
                float(load_basis()["artificial_rotation_positive_control_mz_kNm"]),
            )
        except Exception as exc:
            audit_status = "AUDIT_FAILED"
            audit_issues = [f"POSITIVE_CONTROL: {type(exc).__name__}: {exc}"]
            result = {
                "load_case_id": load_case["id"],
                "status": "SOLVER_FAILED",
                "analyze_return_code": None,
                "nodal_displacements": [],
                "reactions": [],
                "element_end_forces": [],
                "max_translation_m": None,
                "max_rotation_rad": None,
                "issues": [f"AUDIT_FAILED: {audit_issues[0]}"],
            }
    return result, {
        "load_case_id": load_case["id"],
        "audit_status": audit_status,
        "artificial_rotation_reactions": reactions,
        "artificial_rotation_constraints": constraints,
        "domain_fingerprint": fingerprint,
        "truss_local_force_responses": local_forces,
        "artificial_rotation_positive_control": positive_control,
        "wipe_proxy": {
            "total_wipe_calls": proxy.total_wipe_calls,
            "forwarded_wipes": proxy.forwarded_wipes,
            "suppressed_wipes": proxy.suppressed_wipes,
        },
        "issues": audit_issues,
    }


def _structured_raw_failure(
    model: object,
    raw_status: str,
    issue: str,
    *,
    engine: dict | None = None,
    load_case_results: list[dict] | None = None,
) -> dict:
    _, _, model_hash = _payload_capture(model)
    model_id = model.get("model_id", "UNKNOWN") if isinstance(model, dict) else "UNKNOWN"
    if not isinstance(model_id, str) or not model_id:
        model_id = "UNKNOWN"
    raw = {
        "schema_version": "1.0",
        "status": raw_status,
        "model_id": model_id,
        "model_payload_sha256": model_hash,
        "engine": deepcopy(engine),
        "load_case_results": deepcopy(load_case_results or []),
        "issues": [issue],
    }
    raw["raw_result_sha256"] = _raw_hash(raw)
    return raw


def _seal_envelope(
    raw: dict,
    failure_status: str | None,
    audit: dict,
    *,
    worker_nonce: str | None = None,
) -> dict:
    envelope = {
        "status": raw["status"],
        "failure_status": failure_status,
        "raw_result": raw,
        "hardening_audit": audit,
    }
    if worker_nonce is not None:
        envelope["worker_nonce"] = worker_nonce
    envelope["worker_envelope_sha256"] = _envelope_hash(envelope)
    return envelope


def _host_audit() -> dict:
    return {
        "origin": "HOST",
        "worker_attestation_verified": False,
        "worker_isolation_verified": None,
        "loaded_forbidden_modules": None,
        "loaded_forbidden_origins": None,
        "site_packages_policy": SITE_PACKAGES_POLICY,
        "runtime_path_audit": None,
        "engine_module_contract": None,
        "worker_v2_source_sha256": _file_sha256(Path(__file__).resolve()),
        "base_worker_source_sha256": _file_sha256(BASE_MODULE_PATH),
        "artificial_rotation_audits": [],
    }


def _failure_envelope(model: object, issue: str, failure_status: str) -> dict:
    if failure_status not in WORKER_FAILURE_STATUSES:
        raise HardenedReferenceError(f"failure_status không hỗ trợ: {failure_status}")
    raw_status = "BACKEND_UNAVAILABLE" if failure_status == "BACKEND_UNAVAILABLE" else "SOLVER_FAILED"
    raw = _structured_raw_failure(model, raw_status, issue)
    return _seal_envelope(raw, failure_status, _host_audit())


def _runtime_path_snapshot(site_packages: str | None) -> dict:
    resolved = [str(Path(item).resolve()) if item else "" for item in sys.path]
    site_root = str(Path(site_packages).resolve()) if site_packages else None
    return {
        "site_packages_path": site_root,
        "site_packages_index": resolved.index(site_root) if site_root in resolved else None,
        "sys_path": resolved,
        "sys_path_sha256": sha256_json(resolved),
        "shim_file": None,
        "binary_file": None,
        "shim_under_site_packages": False,
        "binary_under_site_packages": False,
    }


def worker_solve(
    model: object,
    site_packages: str | None = None,
    *,
    worker_nonce: str | None = None,
) -> dict:
    """Worker độc lập; output còn nonce chỉ được host hợp thức hóa sau subprocess."""
    guard = _RuntimeOriginGuard()
    checked: dict | None = None
    engine: dict | None = None
    module_contract: dict | None = None
    runtime_path_audit: dict | None = None
    rotation_audits: list[dict] = []
    raw: dict | None = None
    failure_status: str | None = None
    guard.start()
    try:
        if os.environ.get(ISOLATION_PROBE_ENV) == "1":
            _execute_isolation_probe()
        resolved_site = _append_site_packages(site_packages)
        runtime_path_audit = _runtime_path_snapshot(resolved_site)
        base = _base()
        try:
            checked = base._manual_worker_validate_model(
                model, float(load_basis()["minimum_element_length_m"])
            )
        except Exception as exc:
            failure_status = "INVALID_INPUT"
            raw = _structured_raw_failure(
                model, "SOLVER_FAILED", f"{type(exc).__name__}: {exc}"
            )
        if checked is not None:
            try:
                ops = importlib.import_module("openseespy.opensees")
                engine, module_contract, runtime_path_audit = _engine_identity(
                    ops, resolved_site
                )
            except Exception as exc:
                failure_status = "BACKEND_UNAVAILABLE"
                raw = _structured_raw_failure(
                    checked, "BACKEND_UNAVAILABLE", f"{type(exc).__name__}: {exc}"
                )
            if engine is not None:
                load_results: list[dict] = []
                for load_case in checked["load_cases"]:
                    result, audit = _solve_case_with_audit(base, ops, checked, load_case)
                    load_results.append(result)
                    rotation_audits.append(audit)
                issues = [issue for item in load_results for issue in item["issues"]]
                status = (
                    "CONVERGED"
                    if all(item["status"] == "CONVERGED" for item in load_results)
                    else "SOLVER_FAILED"
                )
                if status != "CONVERGED":
                    failure_status = (
                        "AUDIT_FAILED"
                        if any(issue.startswith("AUDIT_FAILED:") for issue in issues)
                        else "SOLVER_FAILED"
                    )
                raw = {
                    "schema_version": "1.0",
                    "status": status,
                    "model_id": checked["model_id"],
                    "model_payload_sha256": sha256_json(checked),
                    "engine": engine,
                    "load_case_results": load_results,
                    "issues": issues,
                }
                raw["raw_result_sha256"] = _raw_hash(raw)
    except Exception as exc:
        failure_status = "WORKER_CRASHED"
        raw = _structured_raw_failure(
            checked if checked is not None else model,
            "SOLVER_FAILED",
            f"WORKER_INTERNAL: {type(exc).__name__}: {exc}",
            engine=engine,
        )
    finally:
        guard.stop()

    if raw is None:
        failure_status = "WORKER_CRASHED"
        raw = _structured_raw_failure(model, "SOLVER_FAILED", "Worker không tạo raw result")
    forbidden_origins = guard.records
    if forbidden_origins:
        failure_status = "ISOLATION_BREACH"
        raw["status"] = "SOLVER_FAILED"
        raw["issues"] = list(raw["issues"]) + [
            "Worker đã thực thi code dưới bridge_evolution: "
            + canonical_json(forbidden_origins)
        ]
        raw["raw_result_sha256"] = _raw_hash(raw)
    if raw["status"] == "CONVERGED":
        failure_status = None
    audit = {
        "origin": "WORKER",
        "worker_attestation_verified": False,
        "worker_isolation_verified": not forbidden_origins,
        "loaded_forbidden_modules": sorted({
            item["module_name"] for item in forbidden_origins
        }),
        "loaded_forbidden_origins": forbidden_origins,
        "site_packages_policy": SITE_PACKAGES_POLICY,
        "runtime_path_audit": runtime_path_audit,
        "engine_module_contract": module_contract,
        "worker_v2_source_sha256": _file_sha256(Path(__file__).resolve()),
        "base_worker_source_sha256": _file_sha256(BASE_MODULE_PATH),
        "artificial_rotation_audits": rotation_audits,
    }
    return _seal_envelope(raw, failure_status, audit, worker_nonce=worker_nonce)


def _finalize_worker_response(envelope: object, expected_nonce: str) -> dict:
    if not isinstance(envelope, dict):
        raise HardenedReferenceError("Worker response phải là object")
    expected_keys = {
        "status",
        "failure_status",
        "raw_result",
        "hardening_audit",
        "worker_nonce",
        "worker_envelope_sha256",
    }
    if set(envelope) != expected_keys:
        raise HardenedReferenceError("Transient worker response có field lạ/thiếu")
    if envelope["worker_envelope_sha256"] != _envelope_hash(envelope):
        raise HardenedReferenceError("Transient worker hash không khớp")
    nonce = envelope.get("worker_nonce")
    if not isinstance(nonce, str) or not hmac.compare_digest(nonce, expected_nonce):
        raise HardenedReferenceError("Worker nonce không khớp challenge của host")
    audit = envelope.get("hardening_audit")
    if not isinstance(audit, dict) or audit.get("origin") != "WORKER":
        raise HardenedReferenceError("Transient response không có origin WORKER")
    if audit.get("worker_attestation_verified") is not False:
        raise HardenedReferenceError("Worker tự khai attestation trước host")
    finalized = deepcopy(envelope)
    finalized.pop("worker_nonce")
    finalized["hardening_audit"]["worker_attestation_verified"] = True
    finalized["worker_envelope_sha256"] = _envelope_hash(finalized)
    return finalized


def run_opensees_model(
    model: dict,
    *,
    python_executable: str | Path,
    site_packages: str | Path | None = None,
    timeout_seconds: float = 30.0,
    _test_isolation_probe: bool = False,
) -> dict:
    base = _base()
    try:
        base._host_validate_model(model)
    except Exception as exc:
        return _failure_envelope(
            model,
            f"HOST_VALIDATION: {type(exc).__name__}: {exc}",
            "HOST_VALIDATION_FAILED",
        )
    executable = Path(python_executable)
    if not executable.is_file():
        return _failure_envelope(model, "Không tìm thấy Python worker", "BACKEND_UNAVAILABLE")
    nonce = secrets.token_hex(32)
    command = [str(executable), "-P", str(Path(__file__).resolve()), "worker"]
    if site_packages is not None:
        site_path = Path(site_packages)
        if not site_path.is_dir():
            return _failure_envelope(
                model, "Không tìm thấy site-packages", "BACKEND_UNAVAILABLE"
            )
        command.extend(["--site-packages", str(site_path)])
    allowed_environment = (
        "COMSPEC",
        "PATH",
        "PATHEXT",
        "SYSTEMDRIVE",
        "SYSTEMROOT",
        "TEMP",
        "TMP",
        "WINDIR",
    )
    environment = {key: os.environ[key] for key in allowed_environment if key in os.environ}
    environment["PYTHONNOUSERSITE"] = "1"
    environment["PYTHONSAFEPATH"] = "1"
    environment[WORKER_NONCE_ENV] = nonce
    if _test_isolation_probe:
        environment[ISOLATION_PROBE_ENV] = "1"
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
    except subprocess.TimeoutExpired as exc:
        return _failure_envelope(
            model, f"WORKER_TIMEOUT: {exc}", "WORKER_TIMEOUT"
        )
    except Exception as exc:
        return _failure_envelope(
            model, f"WORKER_PROCESS: {type(exc).__name__}: {exc}", "WORKER_CRASHED"
        )
    if process.returncode != 0:
        issue = process.stderr.strip() or f"worker return code {process.returncode}"
        return _failure_envelope(model, issue, "WORKER_CRASHED")
    try:
        transient = json.loads(process.stdout)
    except json.JSONDecodeError as exc:
        return _failure_envelope(
            model, f"Worker stdout không phải JSON: {exc}", "WORKER_OUTPUT_INVALID"
        )
    try:
        envelope = _finalize_worker_response(transient, nonce)
        validate_worker_envelope(envelope, model=model, require_converged=False)
    except Exception as exc:
        return _failure_envelope(
            model,
            f"WORKER_ENVELOPE_INVALID: {type(exc).__name__}: {exc}",
            "WORKER_ENVELOPE_INVALID",
        )
    return envelope


def _mixed_error(observed: float, expected: float, absolute: float, relative: float) -> float:
    return abs(observed - expected) / (
        absolute + relative * max(abs(observed), abs(expected))
    )


def _expected_engine_identity(basis: dict) -> dict:
    return deepcopy(basis["expected_backend_identity"])


def _engine_contract_view(raw: dict, audit: dict) -> dict:
    engine = raw.get("engine") or {}
    module_contract = audit.get("engine_module_contract") or {}
    return {
        "name": engine.get("name"),
        "engine_version": engine.get("engine_version"),
        "package_name": engine.get("package_name"),
        "package_version": engine.get("package_version"),
        "python_version": engine.get("python_version"),
        "python_implementation": engine.get("python_implementation"),
        "python_executable_sha256": engine.get("python_executable_sha256"),
        "binary_owner_module": module_contract.get("binary_owner_module"),
        "binary_file_name": engine.get("binary_file_name"),
        "binary_sha256": engine.get("binary_sha256"),
        "shim_module": module_contract.get("shim_module"),
        "shim_package_name": module_contract.get("shim_package_name"),
        "shim_package_version": module_contract.get("shim_package_version"),
        "shim_relative_path": module_contract.get("shim_relative_path"),
        "shim_sha256": module_contract.get("shim_sha256"),
        "binary_relative_path": module_contract.get("binary_relative_path"),
        "callable_bindings": deepcopy(module_contract.get("callable_bindings")),
    }


def _validate_truss_forces(raw: dict, audit: dict, model: dict, basis: dict) -> None:
    truss_ids = {item["id"] for item in model["elements"] if item["kind"] == "TRUSS_2D"}
    force_abs = float(basis["truss_response_tolerances"]["force_absolute_kN"])
    force_rel = float(basis["truss_response_tolerances"]["force_relative"])
    moment_abs = float(basis["truss_response_tolerances"]["moment_absolute_kNm"])
    for load_case in raw["load_case_results"]:
        forces = {item["element_id"]: item for item in load_case["element_end_forces"]}
        rotation_audit = _lookup(
            audit["artificial_rotation_audits"], "load_case_id", load_case["load_case_id"]
        )
        observed_vectors = {
            item["element_id"]: item
            for item in rotation_audit["truss_local_force_responses"]
        }
        if set(observed_vectors) != truss_ids:
            raise HardenedReferenceError("Raw localForce audit thiếu/thừa TRUSS_2D")
        for element_id in sorted(truss_ids):
            item = forces[element_id]
            observed = observed_vectors[element_id]
            vector = observed["raw_local_force"]
            if observed["component_count"] != 6 or len(vector) != 6:
                raise HardenedReferenceError(f"{element_id}: raw localForce không đủ 6 thành phần")
            fields = (
                "axial_i_kN",
                "shear_i_kN",
                "moment_i_kNm",
                "axial_j_kN",
                "shear_j_kN",
                "moment_j_kNm",
            )
            for index, field in enumerate(fields):
                tolerance = moment_abs if "moment" in field else force_abs
                if abs(float(item[field]) - float(vector[index])) > tolerance:
                    raise HardenedReferenceError(
                        f"{element_id}: mapped {field} drift khỏi raw localForce"
                    )
            for index, field in ((1, "shear_i_kN"), (4, "shear_j_kN")):
                if abs(float(vector[index])) > force_abs:
                    raise HardenedReferenceError(f"{element_id}: {field} của TRUSS_2D khác 0")
            for index, field in ((2, "moment_i_kNm"), (5, "moment_j_kNm")):
                if abs(float(vector[index])) > moment_abs:
                    raise HardenedReferenceError(f"{element_id}: {field} của TRUSS_2D khác 0")
            if _mixed_error(
                float(vector[0]), -float(vector[3]), force_abs, force_rel
            ) > 1.0:
                raise HardenedReferenceError(f"{element_id}: axial_i không đối dấu axial_j")


def _validate_rotation_audits(audit: dict, model: dict, basis: dict) -> None:
    expected_nodes = sorted(_artificial_rotation_nodes(model))
    audits = audit["artificial_rotation_audits"]
    if [item.get("load_case_id") for item in audits] != [item["id"] for item in model["load_cases"]]:
        raise HardenedReferenceError("Artificial-rz audit thiếu/sai load case")
    tolerance = float(basis["artificial_rotation_reaction_absolute_kNm"])
    control_mz = float(basis["artificial_rotation_positive_control_mz_kNm"])
    for item in audits:
        if item.get("audit_status") != "COMPLETE" or item.get("issues") != []:
            raise HardenedReferenceError("Artificial-rz audit không COMPLETE")
        wipe = item.get("wipe_proxy")
        if wipe != {"total_wipe_calls": 2, "forwarded_wipes": 1, "suppressed_wipes": 1}:
            raise HardenedReferenceError("WipeProxy audit không khớp contract BRD-044")
        fingerprint = item.get("domain_fingerprint")
        if not isinstance(fingerprint, dict):
            raise HardenedReferenceError("Thiếu domain fingerprint")
        fingerprint_copy = deepcopy(fingerprint)
        fingerprint_sha = fingerprint_copy.pop("fingerprint_sha256", None)
        if fingerprint_sha != sha256_json(fingerprint_copy):
            raise HardenedReferenceError("Domain fingerprint hash sai")
        expected_node_tags = {
            node["id"]: index + 1 for index, node in enumerate(model["nodes"])
        }
        expected_element_tags = {
            element["id"]: index + 1 for index, element in enumerate(model["elements"])
        }
        if fingerprint["node_tags"] != sorted(expected_node_tags.values()):
            raise HardenedReferenceError("Domain fingerprint node tags sai")
        if fingerprint["element_tags"] != sorted(expected_element_tags.values()):
            raise HardenedReferenceError("Domain fingerprint element tags sai")
        bindings = {entry["node_id"]: entry for entry in fingerprint["node_bindings"]}
        if set(bindings) != set(expected_node_tags):
            raise HardenedReferenceError("Domain fingerprint node bindings sai")
        for node in model["nodes"]:
            binding = bindings[node["id"]]
            if binding["node_tag"] != expected_node_tags[node["id"]]:
                raise HardenedReferenceError("Domain fingerprint tag↔node sai")
            if max(
                abs(float(binding["x_m"]) - float(node["x_m"])),
                abs(float(binding["y_m"]) - float(node["y_m"])),
            ) > 1e-12:
                raise HardenedReferenceError("Domain fingerprint coordinate sai")
        reactions = item.get("artificial_rotation_reactions")
        constraints = item.get("artificial_rotation_constraints")
        if [entry.get("node_id") for entry in reactions] != expected_nodes:
            raise HardenedReferenceError("Artificial-rz node set không đầy đủ")
        if [entry.get("node_id") for entry in constraints] != expected_nodes:
            raise HardenedReferenceError("Artificial-rz constraint set không đầy đủ")
        for entry in constraints:
            binding = bindings[entry["node_id"]]
            if entry != {
                "node_id": entry["node_id"],
                "node_tag": binding["node_tag"],
                "x_m": binding["x_m"],
                "y_m": binding["y_m"],
                "fixed_dofs": binding["fixed_dofs"],
            } or 3 not in entry["fixed_dofs"]:
                raise HardenedReferenceError("Artificial-rz constraint evidence sai")
        for entry in reactions:
            value = entry.get("mz_kNm")
            if not _finite(value) or abs(float(value)) > tolerance:
                raise HardenedReferenceError(
                    f"Phản lực rz nhân tạo vượt tolerance tại {entry.get('node_id')}"
                )
        control = item.get("artificial_rotation_positive_control")
        if expected_nodes:
            if not isinstance(control, dict):
                raise HardenedReferenceError("Thiếu artificial-rz positive control")
            if control.get("node_id") != expected_nodes[0]:
                raise HardenedReferenceError("Positive-control node sai")
            if control.get("control_outcome") != "EXPECTED_NONZERO_REACTION_OBSERVED":
                raise HardenedReferenceError("Positive-control outcome sai")
            if float(control.get("applied_mz_kNm")) != control_mz:
                raise HardenedReferenceError("Positive-control load drift")
            observed = control.get("observed_reaction_mz_kNm")
            residual = control.get("equilibrium_residual_kNm")
            if not _finite(observed) or abs(float(observed)) <= tolerance:
                raise HardenedReferenceError("Positive control không tạo phản lực rz khác 0")
            if not _finite(residual) or abs(float(residual)) > tolerance:
                raise HardenedReferenceError("Positive-control moment không cân bằng")
            if control.get("domain_fingerprint_sha256") != fingerprint["fingerprint_sha256"]:
                raise HardenedReferenceError("Positive-control domain fingerprint drift")
        elif control is not None:
            raise HardenedReferenceError("Positive control không được xuất hiện khi không có rz nhân tạo")


def validate_worker_envelope(
    envelope: object,
    *,
    model: object,
    require_converged: bool,
    expected_model_payload_sha256: str | None = None,
) -> None:
    if not isinstance(envelope, dict):
        raise HardenedReferenceError("Worker envelope phải là object")
    canonical_json(envelope)
    expected_keys = {
        "status",
        "failure_status",
        "raw_result",
        "hardening_audit",
        "worker_envelope_sha256",
    }
    if set(envelope) != expected_keys:
        raise HardenedReferenceError("Worker envelope có field lạ/thiếu")
    if envelope["worker_envelope_sha256"] != _envelope_hash(envelope):
        raise HardenedReferenceError("worker_envelope_sha256 không khớp")
    raw = envelope["raw_result"]
    audit = envelope["hardening_audit"]
    if not isinstance(raw, dict) or not isinstance(audit, dict):
        raise HardenedReferenceError("raw_result/hardening_audit phải là object")
    if raw.get("raw_result_sha256") != _raw_hash(raw):
        raise HardenedReferenceError("raw_result_sha256 không khớp")
    expected_model_hash = expected_model_payload_sha256 or _payload_capture(model)[2]
    if raw.get("model_payload_sha256") != expected_model_hash:
        raise HardenedReferenceError("Worker model hash không khớp")
    if envelope["status"] != raw.get("status"):
        raise HardenedReferenceError("Envelope status không khớp raw result")
    failure_status = envelope.get("failure_status")
    if raw.get("status") == "CONVERGED":
        if failure_status is not None:
            raise HardenedReferenceError("CONVERGED không được có failure_status")
    elif failure_status not in WORKER_FAILURE_STATUSES:
        raise HardenedReferenceError("Worker failure thiếu/sai failure_status")
    if require_converged and raw.get("status") != "CONVERGED":
        raise HardenedReferenceError("Worker không CONVERGED")
    expected_audit_keys = {
        "origin",
        "worker_attestation_verified",
        "worker_isolation_verified",
        "loaded_forbidden_modules",
        "loaded_forbidden_origins",
        "site_packages_policy",
        "runtime_path_audit",
        "engine_module_contract",
        "worker_v2_source_sha256",
        "base_worker_source_sha256",
        "artificial_rotation_audits",
    }
    if set(audit) != expected_audit_keys:
        raise HardenedReferenceError("Hardening audit có field lạ/thiếu")
    if audit["site_packages_policy"] != SITE_PACKAGES_POLICY:
        raise HardenedReferenceError("site-packages precedence policy sai")
    if audit["worker_v2_source_sha256"] != _file_sha256(Path(__file__).resolve()):
        raise HardenedReferenceError("Worker v2 source hash sai")
    if audit["base_worker_source_sha256"] != _file_sha256(BASE_MODULE_PATH):
        raise HardenedReferenceError("Base BRD-044 source hash sai")
    origin = audit["origin"]
    if origin == "HOST":
        if raw.get("status") == "CONVERGED":
            raise HardenedReferenceError("HOST không được tạo CONVERGED envelope")
        if audit["worker_attestation_verified"] is not False:
            raise HardenedReferenceError("HOST không được tự khai worker attestation")
        for field in (
            "worker_isolation_verified",
            "loaded_forbidden_modules",
            "loaded_forbidden_origins",
            "runtime_path_audit",
            "engine_module_contract",
        ):
            if audit[field] is not None:
                raise HardenedReferenceError(f"HOST không được khai {field}")
        if audit["artificial_rotation_audits"]:
            raise HardenedReferenceError("HOST không được khai rotation audit")
    elif origin == "WORKER":
        if audit["worker_attestation_verified"] is not True:
            raise HardenedReferenceError("WORKER chưa được host xác minh nonce")
        forbidden = audit["loaded_forbidden_origins"]
        names = audit["loaded_forbidden_modules"]
        if not isinstance(forbidden, list) or not isinstance(names, list):
            raise HardenedReferenceError("WORKER isolation evidence sai kiểu")
        if any(
            not isinstance(item, dict)
            or not isinstance(item.get("module_name"), str)
            or not isinstance(item.get("origin"), str)
            for item in forbidden
        ):
            raise HardenedReferenceError("Forbidden origin record sai cấu trúc")
        expected_names = sorted({item["module_name"] for item in forbidden})
        if names != expected_names:
            raise HardenedReferenceError("Tên module và forbidden origin không khớp")
        for item in forbidden:
            state = item.get("origin_state")
            digest = item.get("sha256")
            if state == "PRESENT" and not isinstance(digest, str):
                raise HardenedReferenceError("Forbidden origin PRESENT thiếu SHA-256")
            if state == "MISSING_AT_AUDIT" and digest is not None:
                raise HardenedReferenceError("Forbidden origin MISSING không được tự khai SHA")
        if failure_status == "ISOLATION_BREACH":
            if audit["worker_isolation_verified"] is not False or not forbidden:
                raise HardenedReferenceError("ISOLATION_BREACH thiếu origin evidence")
        elif forbidden or names or audit["worker_isolation_verified"] is not True:
            raise HardenedReferenceError("Worker isolation không đạt")
        path_audit = audit["runtime_path_audit"]
        if not isinstance(path_audit, dict):
            raise HardenedReferenceError("WORKER thiếu runtime path audit")
        if path_audit["sys_path_sha256"] != sha256_json(path_audit["sys_path"]):
            raise HardenedReferenceError("Runtime sys.path hash sai")
        index = path_audit["site_packages_index"]
        path = path_audit["site_packages_path"]
        if path is not None:
            if index != len(path_audit["sys_path"]) - 1:
                raise HardenedReferenceError("site-packages không nằm cuối sys.path")
            if path_audit["sys_path"][index] != path:
                raise HardenedReferenceError("site-packages index/path không khớp")
    else:
        raise HardenedReferenceError("Hardening audit origin không hợp lệ")

    basis = load_basis()
    if raw.get("engine") is not None:
        if audit.get("engine_module_contract") is None:
            raise HardenedReferenceError("Engine tồn tại nhưng thiếu module contract")
        if _engine_contract_view(raw, audit) != _expected_engine_identity(basis):
            raise HardenedReferenceError("Backend identity drift khỏi basis")
        worker_digest = next(
            item["sha256"] for item in source_digests()
            if item["path"] == "experiments/validation/opensees_frame_reference_v2.py"
        )
        if raw["engine"]["worker_source_sha256"] != worker_digest:
            raise HardenedReferenceError("Engine worker hash không khớp source digest")
        path_audit = audit.get("runtime_path_audit") or {}
        if not path_audit.get("shim_under_site_packages") or not path_audit.get("binary_under_site_packages"):
            raise HardenedReferenceError("OpenSees shim/native không xuất phát từ site-packages pin")
    elif audit.get("engine_module_contract") is not None:
        raise HardenedReferenceError("Không có engine nhưng lại có module contract")

    if raw.get("status") != "CONVERGED":
        if failure_status == "BACKEND_UNAVAILABLE" and raw.get("engine") is not None:
            raise HardenedReferenceError("BACKEND_UNAVAILABLE không được mang engine")
        return
    if not isinstance(model, dict):
        raise HardenedReferenceError("CONVERGED model phải là object")
    _base().validate_raw_result(raw, model=model)
    _validate_rotation_audits(audit, model, basis)
    _validate_truss_forces(raw, audit, model, basis)


def _inclined_truss_spec(basis: dict) -> dict:
    data = basis["benchmark_inputs"]["inclined_two_bar_truss"]
    half_span = float(data["half_span_m"])
    height = float(data["height_m"])
    source_ref = "docs/design_basis/opensees_frame_reference_v2_basis.json"
    model = {
        "schema_version": "1.0",
        "model_id": "F1M-BRD045-inclined-two-bar",
        "analysis_type": "LINEAR_ELASTIC_2D_SMALL_DISPLACEMENT",
        "units": deepcopy(_base().UNITS),
        "nodes": [
            {"id": "N1", "x_m": 0.0, "y_m": 0.0},
            {"id": "N2", "x_m": 2.0 * half_span, "y_m": 0.0},
            {"id": "N3", "x_m": half_span, "y_m": height},
        ],
        "materials": [{
            "id": "MAT1",
            "elastic_modulus_GPa": float(data["elastic_modulus_GPa"]),
            "source_ref": source_ref,
        }],
        "sections": [{
            "id": "SEC1",
            "area_m2": float(data["area_m2"]),
            "inertia_m4": float(data["inertia_m4"]),
            "source_ref": source_ref,
        }],
        "elements": [
            {"id": "E1", "kind": "TRUSS_2D", "node_i": "N1", "node_j": "N3", "material_id": "MAT1", "section_id": "SEC1"},
            {"id": "E2", "kind": "TRUSS_2D", "node_i": "N2", "node_j": "N3", "material_id": "MAT1", "section_id": "SEC1"},
        ],
        "supports": [
            {"node_id": "N1", "ux": True, "uy": True, "rz": True},
            {"node_id": "N2", "ux": True, "uy": True, "rz": True},
        ],
        "load_cases": [{
            "id": "LC1",
            "combination_status": "RESEARCH_BENCHMARK",
            "source_ref": source_ref,
            "nodal_loads": [{
                "node_id": "N3",
                "fx_kN": 0.0,
                "fy_kN": float(data["apex_force_kN"]),
                "mz_kNm": 0.0,
            }],
        }],
    }
    return {
        "case_id": "BRD045-ANALYTICAL-INCLINED-TRUSS",
        "case_kind": "ANALYTICAL",
        "model": model,
        "lineage": {
            "benchmark_name": "INCLINED_TWO_BAR_TRUSS",
            "topology": None,
            "candidate_sha256": None,
            "analysis_sha256": None,
            "arch_action_study_sha256": None,
            "funicular_reference_sha256": None,
        },
    }


def expected_case_specs() -> list[dict]:
    return deepcopy(_base().expected_case_specs()) + [_inclined_truss_spec(load_basis())]


def _lookup(items: list[dict], key: str, value: str) -> dict:
    matches = [item for item in items if item.get(key) == value]
    if len(matches) != 1:
        raise HardenedReferenceError(f"Không tìm thấy duy nhất {key}={value}")
    return matches[0]


def _observed_response(raw: dict, expectation: dict) -> float:
    load_case = _lookup(raw["load_case_results"], "load_case_id", expectation["load_case_id"])
    kind = expectation["response_kind"]
    if kind == "NODE_DISPLACEMENT":
        item = _lookup(load_case["nodal_displacements"], "node_id", expectation["entity_id"])
        return float(item[expectation["component"]])
    if kind == "SUPPORT_REACTION":
        item = _lookup(load_case["reactions"], "node_id", expectation["entity_id"])
        return float(item[expectation["component"]])
    if kind == "ELEMENT_END_FORCE":
        item = _lookup(load_case["element_end_forces"], "element_id", expectation["entity_id"])
        return float(item[expectation["component"]])
    if kind == "MAX_ABS_ELEMENT_MOMENT":
        return max(
            abs(float(item[field]))
            for item in load_case["element_end_forces"]
            for field in ("moment_i_kNm", "moment_j_kNm")
        )
    raise HardenedReferenceError(f"response_kind không hỗ trợ: {kind}")


def evaluate_closed_form(case_id: str, raw: dict, basis: dict) -> dict | None:
    expectation_sets = basis["analytical_expectations"]
    if case_id not in expectation_sets:
        return None
    checks = []
    for expected in expectation_sets[case_id]["checks"]:
        observed = _observed_response(raw, expected)
        absolute = float(expected["absolute_tolerance"])
        relative = float(expected["relative_tolerance"])
        normalized = _mixed_error(observed, float(expected["expected_value"]), absolute, relative)
        checks.append({
            "response_kind": expected["response_kind"],
            "load_case_id": expected["load_case_id"],
            "entity_id": expected["entity_id"],
            "component": expected["component"],
            "expected_value": float(expected["expected_value"]),
            "observed_value": observed,
            "absolute_tolerance": absolute,
            "relative_tolerance": relative,
            "normalized_error": normalized,
            "comparison_state": "WITHIN_TOLERANCE" if normalized <= 1.0 else "OUTSIDE_TOLERANCE",
        })
    outside = [item for item in checks if item["comparison_state"] == "OUTSIDE_TOLERANCE"]
    return {
        "equation_id": expectation_sets[case_id]["equation_id"],
        "status": (
            "CLOSED_FORM_WITHIN_PREREGISTERED_TOLERANCE"
            if not outside else "CLOSED_FORM_DISCREPANCY"
        ),
        "checks": checks,
    }


def _case_hash(case: dict) -> str:
    return _record_hash(case, "case_sha256")


def _suite_hash(suite: dict) -> str:
    return _record_hash(suite, "suite_sha256")


def generate_benchmark_suite(
    *,
    python_executable: str | Path,
    site_packages: str | Path | None = None,
    negative_output: str | Path = DEFAULT_NEGATIVE_PATH,
    _test_isolation_probe: bool = False,
) -> dict:
    basis = load_basis()
    cases = []
    for spec in expected_case_specs():
        model = deepcopy(spec["model"])
        envelope = run_opensees_model(
            model,
            python_executable=python_executable,
            site_packages=site_packages,
            _test_isolation_probe=_test_isolation_probe,
        )
        if envelope["status"] != "CONVERGED":
            validate_worker_envelope(envelope, model=model, require_converged=False)
            negative = build_negative_result(model, envelope)
            output_path = Path(negative_output)
            _write_json(output_path, negative)
            # Đọc và validate lại bytes vừa ghi trước khi dừng để không báo
            # "đã persist" cho một file bị cắt cụt hoặc sai schema.
            persisted = _read_json(output_path.resolve(), "persisted negative evidence")
            validate_negative_result(persisted)
            raise NegativeEvidencePersistedError(
                output_path=output_path.resolve(),
                record_id=negative["record_id"],
                failure_status=negative["failure_status"],
            )
        validate_worker_envelope(envelope, model=model, require_converged=True)
        raw = envelope["raw_result"]
        f1_result, comparison = _base().compare_to_frame_f1(model, raw)
        analytical = evaluate_closed_form(spec["case_id"], raw, basis)
        case = {
            "case_id": spec["case_id"],
            "case_kind": spec["case_kind"],
            "lineage": deepcopy(spec["lineage"]),
            "model": model,
            "model_payload_sha256": sha256_json(model),
            "frame_f1_result": f1_result,
            "opensees_result": raw,
            "hardening_audit": deepcopy(envelope["hardening_audit"]),
            "worker_failure_status": envelope["failure_status"],
            "worker_envelope_sha256": envelope["worker_envelope_sha256"],
            "comparison": comparison,
            "analytical_check": analytical,
            "software_self_check_label": "SOFTWARE_CODE_VERIFICATION_ONLY_NOT_A_DESIGN_VERDICT",
        }
        case["case_sha256"] = _case_hash(case)
        cases.append(case)
    comparisons = {item["comparison"]["status"] for item in cases}
    analytical_states = {
        item["analytical_check"]["status"]
        for item in cases if item["analytical_check"] is not None
    }
    status = (
        "BENCHMARK_SUITE_COMPLETE"
        if comparisons == {"AGREEMENT_WITHIN_PREREGISTERED_TOLERANCE"}
        and analytical_states == {"CLOSED_FORM_WITHIN_PREREGISTERED_TOLERANCE"}
        else "RECONCILIATION_REQUIRED"
    )
    digests = source_digests()
    suite = {
        "schema_version": "2.0",
        "record_type": "BENCHMARK_SUITE",
        "suite_id": "OSR2-" + sha256_json({
            "basis": _file_sha256(BASIS_PATH),
            "source": sha256_json(digests),
            "cases": [item["case_sha256"] for item in cases],
        })[:16],
        "reference": {"id": REFERENCE_ID, "version": REFERENCE_VERSION},
        "claim_level": CLAIM_LEVEL,
        "design_verdict_authority": DESIGN_VERDICT_AUTHORITY,
        "technical_scope": TECHNICAL_SCOPE,
        "gates_completed": [],
        "status": status,
        "basis_sha256": _file_sha256(BASIS_PATH),
        "reference_source_sha256": sha256_json(digests),
        "reference_source_digests": digests,
        "task_artifact_digests": task_artifact_digests(),
        "upstream_brd044_artifacts": upstream_brd044_digests(),
        "expected_backend_identity": _expected_engine_identity(basis),
        "backend_identity": _engine_contract_view(
            cases[0]["opensees_result"], cases[0]["hardening_audit"]
        ),
        "comparison_tolerances": deepcopy(basis["comparison_tolerances"]),
        "cases": cases,
        "limitations": list(basis["explicit_limitations"]),
    }
    suite["suite_sha256"] = _suite_hash(suite)
    schema_validate(suite)
    validate_benchmark_suite(suite)
    return suite


def unstable_model() -> dict:
    source_ref = "docs/design_basis/opensees_frame_reference_v2_basis.json"
    return {
        "schema_version": "1.0",
        "model_id": "F1M-BRD045-unstable-negative",
        "analysis_type": "LINEAR_ELASTIC_2D_SMALL_DISPLACEMENT",
        "units": deepcopy(_base().UNITS),
        "nodes": [
            {"id": "N1", "x_m": 0.0, "y_m": 0.0},
            {"id": "N2", "x_m": 2.0, "y_m": 0.0},
        ],
        "materials": [{"id": "MAT1", "elastic_modulus_GPa": 200.0, "source_ref": source_ref}],
        "sections": [{"id": "SEC1", "area_m2": 0.02, "inertia_m4": 0.002, "source_ref": source_ref}],
        "elements": [{"id": "E1", "kind": "TRUSS_2D", "node_i": "N1", "node_j": "N2", "material_id": "MAT1", "section_id": "SEC1"}],
        "supports": [{"node_id": "N1", "ux": True, "uy": True, "rz": True}],
        "load_cases": [{
            "id": "LC1",
            "combination_status": "RESEARCH_BENCHMARK",
            "source_ref": source_ref,
            "nodal_loads": [{"node_id": "N2", "fx_kN": 0.0, "fy_kN": -1.0, "mz_kNm": 0.0}],
        }],
    }


def build_negative_result(model: object, envelope: dict) -> dict:
    if envelope["status"] not in {"SOLVER_FAILED", "BACKEND_UNAVAILABLE"}:
        raise HardenedReferenceError("Negative result yêu cầu worker failure thật")
    if envelope.get("failure_status") not in WORKER_FAILURE_STATUSES:
        raise HardenedReferenceError("Negative result thiếu failure_status có phân loại")
    basis = load_basis()
    digests = source_digests()
    capture_kind, capture_text, capture_hash = _payload_capture(model)
    valid_model: dict | None = None
    if isinstance(model, dict):
        try:
            _base()._host_validate_model(model)
            valid_model = deepcopy(model)
        except Exception:
            valid_model = None
    if envelope["raw_result"]["model_payload_sha256"] != capture_hash:
        raise HardenedReferenceError("Negative input capture hash không khớp worker")
    record = {
        "schema_version": "2.0",
        "record_type": "NEGATIVE_RESULT",
        "record_id": "OSR2-NEG-" + sha256_json({
            "input": capture_hash,
            "envelope": envelope["worker_envelope_sha256"],
        })[:16],
        "claim_level": CLAIM_LEVEL,
        "design_verdict_authority": DESIGN_VERDICT_AUTHORITY,
        "technical_scope": TECHNICAL_SCOPE,
        "gates_completed": [],
        "status": "NEGATIVE_RESULT_RECORDED",
        "failure_status": envelope["failure_status"],
        "basis_sha256": _file_sha256(BASIS_PATH),
        "reference_source_sha256": sha256_json(digests),
        "reference_source_digests": digests,
        "task_artifact_digests": task_artifact_digests(),
        "upstream_brd044_artifacts": upstream_brd044_digests(),
        "model": valid_model,
        "input_capture": {
            "capture_kind": capture_kind,
            "payload_text": capture_text,
            "payload_sha256": capture_hash,
        },
        "model_payload_sha256": capture_hash,
        "worker_envelope": deepcopy(envelope),
        "issues": list(envelope["raw_result"]["issues"]),
        "limitations": list(basis["explicit_limitations"]),
    }
    record["record_sha256"] = _record_hash(record, "record_sha256")
    schema_validate(record)
    validate_negative_result(record)
    return record


def generate_negative_result(
    *, python_executable: str | Path, site_packages: str | Path | None = None
) -> dict:
    model = unstable_model()
    envelope = run_opensees_model(
        model, python_executable=python_executable, site_packages=site_packages
    )
    return build_negative_result(model, envelope)


def _schema_registry(schema: dict) -> tuple[Any, Any]:
    try:
        import jsonschema
        from referencing import Registry, Resource
    except ImportError as exc:
        raise HardenedReferenceError("Host thiếu jsonschema/referencing") from exc
    registry = Registry()
    for path in (
        REPO_ROOT / "contracts" / "frame_f1_model.schema.json",
        REPO_ROOT / "contracts" / "frame_f1_result.schema.json",
        REPO_ROOT / "contracts" / "opensees_frame_reference.schema.json",
    ):
        item = _read_json(path, path.name)
        registry = registry.with_resource(item["$id"], Resource.from_contents(item))
    return jsonschema.Draft202012Validator(schema, registry=registry), jsonschema


def schema_validate(payload: dict) -> None:
    _reject_forbidden_verdict_keys(payload)
    schema = _read_json(SCHEMA_PATH, "BRD-045 schema")
    validator, jsonschema = _schema_registry(schema)
    jsonschema.Draft202012Validator.check_schema(schema)
    errors = sorted(validator.iter_errors(payload), key=lambda error: list(error.absolute_path))
    if errors:
        details = [
            f"{'/'.join(str(part) for part in error.absolute_path) or '<root>'}: {error.message}"
            for error in errors[:40]
        ]
        raise HardenedReferenceError("Artifact sai schema: " + "; ".join(details))


def _validate_common(payload: dict) -> dict:
    basis = load_basis()
    if payload["claim_level"] != CLAIM_LEVEL or payload["design_verdict_authority"] != DESIGN_VERDICT_AUTHORITY:
        raise HardenedReferenceError("Artifact nâng claim/verdict trái phép")
    if payload["technical_scope"] != TECHNICAL_SCOPE or payload["gates_completed"]:
        raise HardenedReferenceError("Artifact technical scope/gates sai")
    if payload["basis_sha256"] != _file_sha256(BASIS_PATH):
        raise HardenedReferenceError("Artifact basis hash drift")
    digests = source_digests()
    if payload["reference_source_digests"] != digests:
        raise HardenedReferenceError("Artifact source digests drift")
    if payload["reference_source_sha256"] != sha256_json(digests):
        raise HardenedReferenceError("Artifact source SHA sai")
    if payload["upstream_brd044_artifacts"] != upstream_brd044_digests():
        raise HardenedReferenceError("Artifact không neo đúng BRD-044")
    if payload["task_artifact_digests"] != task_artifact_digests():
        raise HardenedReferenceError("Artifact không neo đúng schema/test BRD-045")
    if payload["limitations"] != basis["explicit_limitations"]:
        raise HardenedReferenceError("Artifact limitations drift")
    return basis


def validate_benchmark_suite(
    suite: dict,
    *,
    rerun_backend: bool = False,
    python_executable: str | Path | None = None,
    site_packages: str | Path | None = None,
) -> None:
    canonical_json(suite)
    schema_validate(suite)
    if suite["record_type"] != "BENCHMARK_SUITE":
        raise HardenedReferenceError("Không phải benchmark suite")
    if suite["suite_sha256"] != _suite_hash(suite):
        raise HardenedReferenceError("suite_sha256 không khớp")
    basis = _validate_common(suite)
    if suite["reference"] != {"id": REFERENCE_ID, "version": REFERENCE_VERSION}:
        raise HardenedReferenceError("Reference identity/version sai")
    if suite["expected_backend_identity"] != _expected_engine_identity(basis):
        raise HardenedReferenceError("Expected backend identity drift khỏi basis")
    if suite["comparison_tolerances"] != basis["comparison_tolerances"]:
        raise HardenedReferenceError("Comparison tolerance drift")
    specs = expected_case_specs()
    if [item["case_id"] for item in suite["cases"]] != [item["case_id"] for item in specs]:
        raise HardenedReferenceError("Case IDs/order không tái lập")
    backend_views = []
    for spec, case in zip(specs, suite["cases"]):
        if case["case_kind"] != spec["case_kind"] or case["lineage"] != spec["lineage"]:
            raise HardenedReferenceError(f"{case['case_id']}: kind/lineage drift")
        if case["model"] != spec["model"] or case["model_payload_sha256"] != sha256_json(spec["model"]):
            raise HardenedReferenceError(f"{case['case_id']}: model drift")
        envelope = {
            "status": case["opensees_result"]["status"],
            "failure_status": case["worker_failure_status"],
            "raw_result": case["opensees_result"],
            "hardening_audit": case["hardening_audit"],
            "worker_envelope_sha256": case["worker_envelope_sha256"],
        }
        validate_worker_envelope(envelope, model=case["model"], require_converged=True)
        expected_f1, expected_comparison = _base().compare_to_frame_f1(
            case["model"], case["opensees_result"]
        )
        if case["frame_f1_result"] != expected_f1 or case["comparison"] != expected_comparison:
            raise HardenedReferenceError(f"{case['case_id']}: F1/comparison drift")
        expected_analytical = evaluate_closed_form(case["case_id"], case["opensees_result"], basis)
        if case["case_kind"] == "ANALYTICAL":
            if expected_analytical is None:
                raise HardenedReferenceError(f"{case['case_id']}: ANALYTICAL thiếu expectation trong basis")
        elif expected_analytical is not None:
            raise HardenedReferenceError(f"{case['case_id']}: creative case không được mượn expectation")
        if case["analytical_check"] != expected_analytical:
            raise HardenedReferenceError(f"{case['case_id']}: closed-form check drift")
        if case["software_self_check_label"] != "SOFTWARE_CODE_VERIFICATION_ONLY_NOT_A_DESIGN_VERDICT":
            raise HardenedReferenceError("Software self-check label sai")
        if case["case_sha256"] != _case_hash(case):
            raise HardenedReferenceError(f"{case['case_id']}: case hash sai")
        backend_views.append(_engine_contract_view(case["opensees_result"], case["hardening_audit"]))
        if rerun_backend:
            if python_executable is None:
                raise HardenedReferenceError("rerun_backend cần python_executable")
            rerun = run_opensees_model(
                case["model"], python_executable=python_executable, site_packages=site_packages
            )
            if rerun != envelope:
                raise HardenedReferenceError(f"{case['case_id']}: backend rerun không deterministic")
    if not backend_views or any(item != backend_views[0] for item in backend_views):
        raise HardenedReferenceError("Backend identity không đồng nhất")
    if suite["backend_identity"] != backend_views[0] or backend_views[0] != suite["expected_backend_identity"]:
        raise HardenedReferenceError("Backend identity không khớp contract")
    analytical_case_ids = {
        item["case_id"] for item in suite["cases"] if item["case_kind"] == "ANALYTICAL"
    }
    if analytical_case_ids != set(basis["analytical_expectations"]):
        raise HardenedReferenceError("Tập ANALYTICAL case không khớp basis")
    expected_status = (
        "BENCHMARK_SUITE_COMPLETE"
        if all(item["comparison"]["status"] == "AGREEMENT_WITHIN_PREREGISTERED_TOLERANCE" for item in suite["cases"])
        and all(
            item["analytical_check"] is None
            or item["analytical_check"]["status"]
            == "CLOSED_FORM_WITHIN_PREREGISTERED_TOLERANCE"
            for item in suite["cases"]
        )
        else "RECONCILIATION_REQUIRED"
    )
    if suite["status"] != expected_status:
        raise HardenedReferenceError("Suite status không tái lập")
    expected_id = "OSR2-" + sha256_json({
        "basis": _file_sha256(BASIS_PATH),
        "source": sha256_json(source_digests()),
        "cases": [item["case_sha256"] for item in suite["cases"]],
    })[:16]
    if suite["suite_id"] != expected_id:
        raise HardenedReferenceError("suite_id không khớp")


def validate_negative_result(
    record: dict,
    *,
    rerun_backend: bool = False,
    python_executable: str | Path | None = None,
    site_packages: str | Path | None = None,
) -> None:
    canonical_json(record)
    schema_validate(record)
    if record["record_type"] != "NEGATIVE_RESULT":
        raise HardenedReferenceError("Không phải negative result")
    if record["record_sha256"] != _record_hash(record, "record_sha256"):
        raise HardenedReferenceError("record_sha256 không khớp")
    _validate_common(record)
    if record["status"] != "NEGATIVE_RESULT_RECORDED":
        raise HardenedReferenceError("Negative status sai")
    capture = record["input_capture"]
    capture_hash = hashlib.sha256(
        capture["payload_text"].encode("utf-8", errors="backslashreplace")
    ).hexdigest()
    if capture["payload_sha256"] != capture_hash or record["model_payload_sha256"] != capture_hash:
        raise HardenedReferenceError("Negative input capture hash sai")
    if capture["capture_kind"] == "CANONICAL_JSON":
        try:
            captured_input = json.loads(capture["payload_text"])
        except json.JSONDecodeError as exc:
            raise HardenedReferenceError("Negative canonical input không parse được") from exc
        if canonical_json(captured_input) != capture["payload_text"]:
            raise HardenedReferenceError("Negative input không canonical")
    else:
        captured_input = None
    model = record["model"]
    if model is not None:
        if captured_input != model:
            raise HardenedReferenceError("Negative model không khớp input capture")
        _base()._host_validate_model(model)
    envelope = record["worker_envelope"]
    validation_model = captured_input if isinstance(captured_input, dict) else {}
    validate_worker_envelope(
        envelope,
        model=validation_model,
        require_converged=False,
        expected_model_payload_sha256=capture_hash,
    )
    if envelope["status"] not in {"SOLVER_FAILED", "BACKEND_UNAVAILABLE"}:
        raise HardenedReferenceError("Negative artifact không chứa failure")
    if record["failure_status"] != envelope["failure_status"]:
        raise HardenedReferenceError("Negative failure_status sai")
    if record["issues"] != envelope["raw_result"]["issues"] or not record["issues"]:
        raise HardenedReferenceError("Negative issues gốc bị mất")
    expected_id = "OSR2-NEG-" + sha256_json({
        "input": capture_hash,
        "envelope": envelope["worker_envelope_sha256"],
    })[:16]
    if record["record_id"] != expected_id:
        raise HardenedReferenceError("Negative record_id sai")
    if rerun_backend:
        if python_executable is None:
            raise HardenedReferenceError("rerun_backend cần python_executable")
        if not isinstance(captured_input, dict):
            raise HardenedReferenceError("Không thể rerun PYTHON_REPR input")
        rerun = run_opensees_model(
            captured_input, python_executable=python_executable, site_packages=site_packages
        )
        if rerun != envelope:
            raise HardenedReferenceError("Negative backend rerun không deterministic")


def validate_artifact_against_handoff(
    artifact_path: str | Path,
    handoff_path: str | Path,
    **kwargs: Any,
) -> None:
    artifact = Path(artifact_path).resolve()
    handoff = Path(handoff_path).resolve()
    try:
        artifact_rel = str(artifact.relative_to(REPO_ROOT.resolve())).replace("\\", "/")
        handoff.relative_to(REPO_ROOT.resolve())
    except ValueError as exc:
        raise HardenedReferenceError("Artifact/handoff phải nằm trong repo") from exc
    data = _read_json(handoff, "BRD-045 handoff")
    if data.get("task_id") != "BRD-045":
        raise HardenedReferenceError("Handoff không thuộc BRD-045")
    matches = [item for item in data.get("artifacts", []) if item.get("path", "").replace("\\", "/") == artifact_rel]
    if len(matches) != 1 or matches[0].get("sha256") != _file_sha256(artifact):
        raise HardenedReferenceError("Artifact bytes drift khỏi handoff")
    payload = _read_json(artifact, "BRD-045 artifact")
    if payload["record_type"] == "BENCHMARK_SUITE":
        validate_benchmark_suite(payload, **kwargs)
    else:
        validate_negative_result(payload, **kwargs)


def _write_json(path: Path, value: dict) -> None:
    resolved = path.resolve()
    try:
        resolved.relative_to(REPO_ROOT.resolve())
    except ValueError as exc:
        raise HardenedReferenceError("Output phải nằm trong repo") from exc
    resolved.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _worker_cli(args: argparse.Namespace) -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="strict")
    nonce = os.environ.get(WORKER_NONCE_ENV)
    try:
        model = json.loads(sys.stdin.read())
    except json.JSONDecodeError as exc:
        model = {"model_id": "UNKNOWN", "invalid_json": f"JSONDecodeError: {exc}"}
        print(canonical_json(worker_solve(model, args.site_packages, worker_nonce=nonce)))
        return 0
    print(canonical_json(worker_solve(model, args.site_packages, worker_nonce=nonce)))
    return 0


def _generate_cli(args: argparse.Namespace) -> int:
    value = generate_benchmark_suite(
        python_executable=args.python_executable,
        site_packages=args.site_packages,
        negative_output=args.negative_output,
    )
    _write_json(Path(args.output), value)
    print(json.dumps({"status": value["status"], "suite_id": value["suite_id"], "case_count": len(value["cases"]), "output": str(Path(args.output))}, ensure_ascii=False))
    return 0


def _negative_cli(args: argparse.Namespace) -> int:
    value = generate_negative_result(
        python_executable=args.python_executable, site_packages=args.site_packages
    )
    _write_json(Path(args.output), value)
    print(json.dumps({"status": value["status"], "record_id": value["record_id"], "failure_status": value["failure_status"], "output": str(Path(args.output))}, ensure_ascii=False))
    return 0


def _validate_cli(args: argparse.Namespace) -> int:
    value = _read_json(Path(args.artifact), "artifact")
    kwargs = {
        "rerun_backend": bool(args.rerun_backend),
        "python_executable": args.python_executable,
        "site_packages": args.site_packages,
    }
    if args.handoff:
        validate_artifact_against_handoff(args.artifact, args.handoff, **kwargs)
    elif value["record_type"] == "BENCHMARK_SUITE":
        validate_benchmark_suite(value, **kwargs)
    else:
        validate_negative_result(value, **kwargs)
    print(json.dumps({"status": value["status"], "record_type": value["record_type"], "rerun_backend": bool(args.rerun_backend)}, ensure_ascii=False))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    worker = sub.add_parser("worker")
    worker.add_argument("--site-packages")
    worker.set_defaults(handler=_worker_cli)
    for name, handler, default in (
        ("generate", _generate_cli, DEFAULT_SUITE_PATH),
        ("generate-negative", _negative_cli, DEFAULT_NEGATIVE_PATH),
    ):
        item = sub.add_parser(name)
        item.add_argument("--python-executable", required=True)
        item.add_argument("--site-packages")
        item.add_argument("--output", default=str(default))
        if name == "generate":
            item.add_argument(
                "--negative-output",
                default=str(DEFAULT_NEGATIVE_PATH),
                help="Nơi persist failure envelope trước khi generate dừng",
            )
        item.set_defaults(handler=handler)
    validate = sub.add_parser("validate")
    validate.add_argument("artifact")
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
    except HardenedReferenceError as exc:
        print(f"BRD-045 STOP: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
