"""Lát cắt B1 của SAGE-EvoBridge, tái dùng kernel frame_f1 hiện hữu.

Chỉ kiểm ràng buộc benchmark dầm chữ nhật, không cấp kết luận tiêu chuẩn.
Không phải generator A/B, optimizer mới, hay verified engineering memory.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, fields
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version as package_version
import json
import math
from pathlib import Path
import platform
import uuid

from . import REPO_ROOT
from .frame_f1 import (
    ANALYSIS_FIDELITY, FrameF1Error, SOLVER_VERSION, analyze_frame_model,
    load_frame_basis, validate_frame_model, validate_frame_result,
)

BASIS_REF = "docs/sage_evobridge/BENCHMARK_BASIS.md"
VERSION = "evobridge-b1/0.1.0"
FAILURE_GROUPS = (
    "INPUT_DATA_ERROR", "GEOMETRY_CONNECTIVITY_ERROR", "MODEL_MAPPING_ERROR",
    "NUMERICAL_ANALYSIS_ERROR", "STRUCTURAL_LIMIT_STATE_VIOLATION",
    "RULE_SCOPE_DATA_GAP", "CONSTRUCTABILITY_VIOLATION",
)


def canonical(value: object) -> str:
    """Chuẩn hóa JSON và từ chối NaN/Infinity thay vì biến thành số 0."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False)


def digest(value: object) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def _positive(value: object, label: str) -> None:
    if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
        raise ValueError(f"{label} must be a finite positive number")


@dataclass(frozen=True)
class BeamContract:
    """Khóa đầu bài; operator chỉ có quyền đổi height_m trong miền đã khai."""
    schema_version: str
    project_id: str
    task_id: str
    units: str
    span_m: float
    width_m: float
    elastic_modulus_GPa: float
    unit_weight_kN_m3: float
    external_midpoint_load_kN: float
    height_min_m: float
    height_max_m: float
    deflection_limit_m: float
    stress_limit_MPa: float
    volume_limit_m3: float
    solver_budget: int
    max_actions: int
    required_checks: tuple[str, ...]
    fidelity: str = ANALYSIS_FIDELITY
    support_scheme: str = "PIN_ROLLER"
    mesh_elements: int = 8
    reference_relative_tolerance: float = 1e-7

    def __post_init__(self) -> None:
        if self.schema_version != "1.0" or self.units != "m-kN-GPa":
            raise ValueError("Unsupported schema or units; expected 1.0 and m-kN-GPa")
        for label in ("project_id", "task_id"):
            if not isinstance(getattr(self, label), str) or not getattr(self, label).strip():
                raise ValueError(f"Missing {label}")
        for label in ("span_m", "width_m", "elastic_modulus_GPa", "unit_weight_kN_m3",
                      "external_midpoint_load_kN", "height_min_m", "height_max_m",
                      "deflection_limit_m", "stress_limit_MPa", "volume_limit_m3"):
            _positive(getattr(self, label), label)
        if self.height_min_m > self.height_max_m:
            raise ValueError("Reversed height bounds")
        if self.support_scheme != "PIN_ROLLER":
            raise ValueError("Only PIN_ROLLER is implemented; no support substitution")
        if type(self.mesh_elements) is not int or not 2 <= self.mesh_elements <= 64 or self.mesh_elements % 2:
            raise ValueError("mesh_elements must be even, between 2 and 64")
        for label in ("solver_budget", "max_actions"):
            if type(getattr(self, label)) is not int or not 1 <= getattr(self, label) <= 100:
                raise ValueError(f"{label} must be an integer between 1 and 100")
        if self.reference_relative_tolerance != 1e-7:
            raise ValueError("Reference tolerance is preregistered at 1e-7")
        if not isinstance(self.fidelity, str) or not self.fidelity:
            raise ValueError("Missing fidelity")
        if not isinstance(self.required_checks, tuple) or not self.required_checks:
            raise ValueError("required_checks must be a nonempty tuple")
        if any(not isinstance(x, str) or not x for x in self.required_checks):
            raise ValueError("Invalid required check identifier")
        if len(set(self.required_checks)) != len(self.required_checks):
            raise ValueError("Duplicate required checks")
        if not {"DEFLECTION", "STRESS", "VOLUME"} <= set(self.required_checks):
            raise ValueError("Cannot remove mandatory benchmark checks")

    @classmethod
    def from_mapping(cls, value: dict) -> "BeamContract":
        """Nạp dữ liệu có kiểu; không nhận chỉ dẫn/field vượt contract."""
        if not isinstance(value, dict) or set(value) - {f.name for f in fields(cls)}:
            raise ValueError("Contract must be an object with known fields only")
        data = dict(value)
        if not isinstance(data.get("required_checks"), list):
            raise ValueError("required_checks must be a JSON list")
        data["required_checks"] = tuple(data["required_checks"])
        return cls(**data)


def compile_beam(contract: BeamContract, height_m: float) -> dict:
    """Biên dịch genome chữ nhật sang schema native của frame_f1, SI rõ ràng."""
    _positive(height_m, "height_m")
    if not contract.height_min_m <= height_m <= contract.height_max_m:
        raise ValueError("height_m outside immutable contract bounds")
    n = contract.mesh_elements
    dx = contract.span_m / n
    # Tự trọng là tải phụ thuộc hình học: lumped theo chiều dài tributary từng nút.
    q = contract.width_m * height_m * contract.unit_weight_kN_m3
    loads = []
    for i in range(n + 1):
        weight = q * dx * (0.5 if i in (0, n) else 1.0)
        imposed = contract.external_midpoint_load_kN if i == n // 2 else 0.0
        loads.append({"node_id": f"N{i}", "fx_kN": 0.0,
                      "fy_kN": -(weight + imposed), "mz_kNm": 0.0})
    return {
        "schema_version": "1.0",
        "model_id": "F1M-" + digest({"contract": asdict(contract), "height_m": height_m})[:24],
        "analysis_type": "LINEAR_ELASTIC_2D_SMALL_DISPLACEMENT",
        "units": {"length": "m", "force": "kN", "moment": "kN_m",
                  "elastic_modulus": "GPa", "area": "m2", "inertia": "m4"},
        "nodes": [{"id": f"N{i}", "x_m": i * dx, "y_m": 0.0} for i in range(n + 1)],
        "materials": [{"id": "M1", "elastic_modulus_GPa": contract.elastic_modulus_GPa,
                       "source_ref": BASIS_REF}],
        "sections": [{"id": "S1", "area_m2": contract.width_m * height_m,
                      "inertia_m4": contract.width_m * height_m**3 / 12, "source_ref": BASIS_REF}],
        "elements": [{"id": f"E{i}", "kind": "FRAME_2D", "node_i": f"N{i}",
                      "node_j": f"N{i+1}", "material_id": "M1", "section_id": "S1"}
                     for i in range(n)],
        "supports": [{"node_id": "N0", "ux": True, "uy": True, "rz": False},
                     {"node_id": f"N{n}", "ux": False, "uy": True, "rz": False}],
        "load_cases": [{"id": "BENCHMARK_SERVICE", "combination_status": "RESEARCH_BENCHMARK",
                        "source_ref": BASIS_REF, "nodal_loads": loads}],
    }


def reference_response(contract: BeamContract, height_m: float) -> dict:
    """Nghiệm đóng độc lập: superposition Green của tải điểm, không đọc FE model."""
    length, width = contract.span_m, contract.width_m
    ei = contract.elastic_modulus_GPa * 1e6 * width * height_m**3 / 12
    x = length / 2
    count = contract.mesh_elements
    tributary = length / count
    q = width * height_m * contract.unit_weight_kN_m3
    displacement = 0.0
    left_moment = 0.0
    for j in range(count + 1):
        a = length * j / count
        p = q * tributary * (0.5 if j in (0, count) else 1.0)
        if j == count // 2:
            p += contract.external_midpoint_load_kN
        b = length - a
        if x <= a:
            displacement += p * b * x * (length**2 - b**2 - x**2) / (6 * length * ei)
        else:
            displacement += p * a * (length - x) * (length**2 - a**2 - (length-x)**2) / (6 * length * ei)
        if a < x:
            left_moment += p * (x - a)
    reaction = (contract.external_midpoint_load_kN + q * length) / 2
    return {"deflection_m": displacement, "reaction_kN": reaction,
            "moment_kNm": reaction * x - left_moment,
            "self_weight_kN": q * length}


def audit_compiled_model(c: BeamContract, h: float, model: dict) -> None:
    """Đối soát semantics từ contract; EI đúng không che được E/I mapping sai."""
    n = c.mesh_elements
    if (len(model["materials"]) != 1 or len(model["sections"]) != 1
            or model["materials"][0]["elastic_modulus_GPa"] != c.elastic_modulus_GPa
            or not math.isclose(model["sections"][0]["area_m2"], c.width_m*h, rel_tol=1e-12)
            or not math.isclose(model["sections"][0]["inertia_m4"], c.width_m*h*h*h/12, rel_tol=1e-12)):
        raise FrameF1Error("Contract material/section mapping discrepancy")
    if len(model["nodes"]) != n+1 or len(model["elements"]) != n:
        raise FrameF1Error("Contract topology mapping discrepancy")
    for i, node in enumerate(model["nodes"]):
        if node["id"] != f"N{i}" or node["y_m"] != 0 or not math.isclose(node["x_m"], c.span_m*i/n, abs_tol=1e-12):
            raise FrameF1Error("Contract coordinate mapping discrepancy")
    for i, element in enumerate(model["elements"]):
        if element != {"id": f"E{i}", "kind": "FRAME_2D", "node_i": f"N{i}",
                       "node_j": f"N{i+1}", "material_id": "M1", "section_id": "S1"}:
            raise FrameF1Error("Contract connectivity mapping discrepancy")
    if model["supports"] != [{"node_id": "N0", "ux": True, "uy": True, "rz": False},
                              {"node_id": f"N{n}", "ux": False, "uy": True, "rz": False}]:
        raise FrameF1Error("Contract support mapping discrepancy")
    if len(model["load_cases"]) != 1 or model["load_cases"][0]["id"] != "BENCHMARK_SERVICE":
        raise FrameF1Error("Contract load case mapping discrepancy")
    loads = model["load_cases"][0]["nodal_loads"]
    if len(loads) != n+1:
        raise FrameF1Error("Contract load count discrepancy")
    total_weight = c.unit_weight_kN_m3*c.width_m*h*c.span_m
    for i, load in enumerate(loads):
        expected = total_weight/n*(.5 if i in (0,n) else 1.)
        expected += c.external_midpoint_load_kN if i == n//2 else 0.
        if (load["node_id"] != f"N{i}" or load["fx_kN"] != 0 or load["mz_kNm"] != 0
                or not math.isclose(-load["fy_kN"], expected, rel_tol=1e-12)):
            raise FrameF1Error("Contract external load/self weight mapping discrepancy")


def _failure(group: str, message: str, **evidence: object) -> dict:
    return {"category": group, "message": message, "evidence": evidence}


def evaluate_beam(contract: BeamContract, height_m: float) -> dict:
    """Kiểm mapping, model, nghiệm đối chứng trước mọi verdict benchmark."""
    evaluation = {
        "schema_version": "1.0", "contract_sha256": digest(asdict(contract)),
        "height_m": height_m, "execution_status": "NOT_RUN", "analysis_validity": "NOT_CHECKED",
        "compliance_status": "INCONCLUSIVE", "benchmark_status": "INCONCLUSIVE",
        "evidence_level": "NONE", "approval_status": "NOT_REVIEWED",
        "claim_level": "IDEA", "design_verdict_authority": "NONE",
        "solver_calls": 0, "failures": [], "checks": [], "model": None, "raw_result": None,
    }
    unsupported = set(contract.required_checks) - {"DEFLECTION", "STRESS", "VOLUME"}
    if contract.fidelity != ANALYSIS_FIDELITY or unsupported:
        evaluation["execution_status"] = "BLOCKED"
        evaluation["failures"].append(_failure("RULE_SCOPE_DATA_GAP", "Unsupported required fidelity/check",
                                               fidelity=contract.fidelity, checks=sorted(unsupported)))
        return evaluation
    try:
        model = compile_beam(contract, height_m)
        sources = validate_frame_model(model)
        evaluation["model"] = model
        evaluation["model_sha256"] = digest({"model": model, "source_digests": sources})
        audit_compiled_model(contract, height_m, model)
    except FrameF1Error as exc:
        evaluation["execution_status"] = "REJECTED"
        evaluation["analysis_validity"] = "INVALID"
        evaluation["failures"].append(_failure("MODEL_MAPPING_ERROR", str(exc)))
        return evaluation
    except (ValueError, TypeError) as exc:
        evaluation["execution_status"] = "REJECTED"
        evaluation["failures"].append(_failure("INPUT_DATA_ERROR", str(exc)))
        return evaluation
    evaluation["solver_calls"] = 1
    try:
        raw = analyze_frame_model(model)
        # Giữ output hỏng dưới dạng text riêng, không serialize NaN thành số hợp lệ.
        try:
            canonical(raw)
            evaluation["raw_result"] = raw
        except (ValueError, TypeError):
            evaluation["raw_output_invalid_repr"] = repr(raw)
            raise FrameF1Error("Solver output contains nonfinite or non-JSON values")
        validate_frame_result(raw)
        if raw["model_sha256"] != evaluation["model_sha256"] or raw["model_id"] != model["model_id"]:
            evaluation["execution_status"] = "COMPLETED"
            evaluation["analysis_validity"] = "INVALID"
            evaluation["failures"].append(_failure("MODEL_MAPPING_ERROR", "Stale or mismatched solver model"))
            return evaluation
        basis = load_frame_basis()
        current_sources = [{"path": p, "sha256": hashlib.sha256((REPO_ROOT/p).read_bytes()).hexdigest()}
                           for p in basis["solver_source_files"]]
        if (raw["source_digests"] != sources or raw["solver_source_digests"] != current_sources
                or raw["solver_sha256"] != digest(current_sources)
                or raw["basis_sha256"] != hashlib.sha256((REPO_ROOT/"docs/design_basis/frame_f1_basis.json").read_bytes()).hexdigest()):
            raise FrameF1Error("Solver/source/basis provenance does not match current runtime")
        evaluation["execution_status"] = "COMPLETED"
        case = raw["load_case_results"][0]
        if (len(raw["load_case_results"]) != 1 or case["load_case_id"] != "BENCHMARK_SERVICE"
                or raw["status"] != "CONVERGED" or case["status"] != "CONVERGED"
                or raw["issues"] or case["issues"] or not case["checks"]
                or any(c["status"] != "PASS" for c in case["checks"])):
            raise FrameF1Error("Solver nonconvergence, unresolved warning or model quality failure")
        guards = basis["numerical_guards"]
        quality = {
            "F1-STABILITY": ("condition_number", guards["max_scaled_condition_number"]),
            "F1-CONDITION": ("condition_number", guards["max_scaled_condition_number"]),
            "F1-SMALL-DISPLACEMENT": ("max_translation_to_characteristic_length", guards["max_translation_to_characteristic_length"]),
            "F1-FREE-RESIDUAL": ("free_residual_relative", guards["equilibrium_relative_tolerance"]),
            "F1-FORCE-EQUILIBRIUM": ("force_equilibrium_relative", guards["equilibrium_relative_tolerance"]),
            "F1-MOMENT-EQUILIBRIUM": ("moment_equilibrium_relative", guards["equilibrium_relative_tolerance"]),
            "F1-ENERGY-IDENTITY": ("energy_identity_relative", guards["energy_relative_tolerance"]),
        }
        checks = {check["check_id"]: check for check in case["checks"]}
        if set(checks) != set(quality) or len(case["checks"]) != len(quality):
            raise FrameF1Error("Incomplete or duplicate model quality checks")
        for check_id, (channel, limit) in quality.items():
            observed = case["diagnostics"][channel]
            if (type(observed) not in (int,float) or not 0 <= observed <= limit
                    or checks[check_id]["value"] != observed or checks[check_id]["limit"] != limit):
                raise FrameF1Error("Model quality values/limits are inconsistent")
        if case["diagnostics"]["rank"] != case["diagnostics"]["free_active_dof_count"]:
            raise FrameF1Error("Incomplete stiffness matrix rank")
        expected_nodes = {node["id"] for node in model["nodes"]}
        displacements = {v["node_id"]: v for v in case["nodal_displacements"]}
        reactions = {v["node_id"]: v for v in case["reactions"]}
        forces = {v["element_id"]: v for v in case["element_end_forces"]}
        if (set(displacements) != expected_nodes or len(displacements) != len(case["nodal_displacements"])
                or set(reactions) != {"N0", f"N{contract.mesh_elements}"} or len(case["reactions"]) != 2
                or set(forces) != {e["id"] for e in model["elements"]}
                or len(forces) != len(case["element_end_forces"])):
            raise FrameF1Error("Missing or duplicate result mappings")
        displacement_tolerance = max(1e-12, contract.span_m*1e-10)
        if (abs(displacements["N0"]["uy_m"]) > displacement_tolerance
                or abs(displacements[f"N{contract.mesh_elements}"]["uy_m"]) > displacement_tolerance
                or any(abs(v["ux_m"]) > displacement_tolerance for v in displacements.values())
                or any(abs(v["fx_kN"]) > 1e-8 or abs(v["mz_kNm"]) > 1e-8 for v in reactions.values())):
            raise FrameF1Error("Boundary response contradicts pinned roller model")
        midpoint = displacements[f"N{contract.mesh_elements//2}"]
        deflection = -midpoint["uy_m"]
        moment = max(abs(f[key]) for f in forces.values() for key in ("moment_i_kNm", "moment_j_kNm"))
        reference = reference_response(contract, height_m)
        errors = {"deflection": abs(deflection-reference["deflection_m"])/max(reference["deflection_m"], 1e-12),
                  "moment": abs(moment-reference["moment_kNm"])/max(reference["moment_kNm"], 1e-12)}
        for node, values in reactions.items():
            errors[f"reaction_{node}"] = abs(values["fy_kN"]-reference["reaction_kN"])/max(reference["reaction_kN"], 1e-12)
        evaluation["independent_reference"] = {"method": "CLOSED_FORM_POINT_LOAD_SUPERPOSITION",
                                                "values": reference, "relative_errors": errors,
                                                "tolerance": contract.reference_relative_tolerance}
        if any(error > contract.reference_relative_tolerance for error in errors.values()):
            evaluation["analysis_validity"] = "DISCREPANCY"
            evaluation["failures"].append(_failure("MODEL_MAPPING_ERROR", "Independent reference discrepancy",
                                                   relative_errors=errors))
            return evaluation
        evaluation["analysis_validity"] = "VALID_FOR_BENCHMARK"
        evaluation["evidence_level"] = "COMPUTED_AND_CLOSED_FORM_CHECKED"
        values = {"DEFLECTION": (deflection, contract.deflection_limit_m, "m"),
                  "STRESS": (moment/(contract.width_m*height_m**2/6)/1000, contract.stress_limit_MPa, "MPa"),
                  "VOLUME": (contract.span_m*contract.width_m*height_m, contract.volume_limit_m3, "m3")}
        for name, (value, limit, unit) in values.items():
            check = {"check_id": name, "value": value, "limit": limit, "unit": unit,
                     "utilization": value/limit, "status": "PASS" if value <= limit else "FAIL",
                     "threshold_kind": "BENCHMARK_CONSTRAINT", "source_ref": BASIS_REF,
                     "contract_sha256": evaluation["contract_sha256"]}
            evaluation["checks"].append(check)
            if check["status"] == "FAIL":
                group = "CONSTRUCTABILITY_VIOLATION" if name == "VOLUME" else "STRUCTURAL_LIMIT_STATE_VIOLATION"
                evaluation["failures"].append(_failure(group, f"{name}: benchmark limit exceeded",
                    object_id="BEAM", location="MIDSPAN" if name != "VOLUME" else "WHOLE_MEMBER",
                    load_case="BENCHMARK_SERVICE", model_quality=evaluation["analysis_validity"], **check))
        evaluation["benchmark_status"] = "FAIL" if evaluation["failures"] else "PASS"
    except (FrameF1Error, ValueError, TypeError, KeyError, IndexError, ArithmeticError, RuntimeError, OSError) as exc:
        evaluation["execution_status"] = "ERROR"
        evaluation["analysis_validity"] = "INVALID"
        evaluation["failures"].append(_failure("NUMERICAL_ANALYSIS_ERROR", str(exc)))
    return evaluation


def run_interventions(contract: BeamContract, initial_height_m: float, heights: list[float]) -> dict:
    """Chạy operator chiều cao có biên; giữ mọi kết quả, kể cả phản ví dụ."""
    _positive(initial_height_m, "initial_height_m")
    if len(heights) > contract.max_actions:
        raise ValueError("Action list exceeds immutable max_actions")
    for h in heights:
        _positive(h, "intervention height")
    fixed_hash = digest(asdict(contract))
    report = {"schema_version": "1.0", "version": VERSION, "run_id": str(uuid.uuid4()),
              "timestamp_utc": datetime.now(timezone.utc).isoformat(), "contract": asdict(contract),
              "contract_sha256": fixed_hash, "claim_level": "IDEA", "approval_status": "NOT_REVIEWED",
              "compliance_status": "INCONCLUSIVE", "branch": "B1_EVALUATOR_BENCHMARK",
              "seed": None, "policy": "USER_ORDERED_HEIGHT_PROBES_NO_LEARNING",
              "solver_calls": 0, "cache_hits": 0, "cache_policy": "DISABLED_ALL_PROBES_COUNTED",
              "evaluations": [], "interventions": [],
              "feasible_benchmark_candidates": [], "status": "RUNNING"}
    reference = evaluate_beam(contract, initial_height_m)
    report["evaluations"].append(reference)
    report["solver_calls"] += reference["solver_calls"]
    reference["evaluation_id"] = "E0"
    if reference["benchmark_status"] == "PASS":
        report["feasible_benchmark_candidates"].append("E0")
        report["status"] = "BENCHMARK_FEASIBLE"
    elif reference["analysis_validity"] != "VALID_FOR_BENCHMARK":
        report["status"] = "INCONCLUSIVE"
    else:
        before = {c["check_id"]: c for c in reference["checks"]}
        if before["DEFLECTION"]["status"] != "FAIL":
            report["status"] = "BLOCKED_NO_APPLICABLE_OPERATOR"
        else:
            for height in heights:
                if report["solver_calls"] >= contract.solver_budget:
                    break
                if digest(asdict(contract)) != fixed_hash:
                    raise ValueError("Immutable contract changed")
                child = evaluate_beam(contract, height)
                child["evaluation_id"] = f"E{len(report['evaluations'])}"
                child["parent_id"] = "E0"
                report["evaluations"].append(child)
                report["solver_calls"] += child["solver_calls"]
                valid = child["analysis_validity"] == "VALID_FOR_BENCHMARK"
                after = {c["check_id"]: c for c in child["checks"]}
                delta = after["DEFLECTION"]["value"] - before["DEFLECTION"]["value"] if valid else None
                collateral = [k for k in before if before[k]["status"] == "PASS" and after[k]["status"] == "FAIL"] if valid else []
                conclusion = "INCONCLUSIVE"
                if valid and not math.isclose(delta, 0.0, abs_tol=1e-12):
                    conclusion = "SUPPORTED_IN_MODEL" if delta < 0 else "CONTRADICTED"
                report["interventions"].append({
                    "operator_id": "SET_RECTANGULAR_HEIGHT/1.0", "reference_id": "E0",
                    "child_id": child["evaluation_id"], "contract_sha256": fixed_hash,
                    "hypothesis": "This permitted height change reduces midpoint deflection in this linear model",
                    "predicted_direction": "DECREASE", "conclusion": conclusion,
                    "height_delta_m": height-initial_height_m, "deflection_delta_m": delta,
                    "violation_delta": {k: max(0,after[k]["utilization"]-1)-max(0,before[k]["utilization"]-1) for k in before} if valid else None,
                    "collateral_failures": collateral,
                    "reference_model_sha256": reference.get("model_sha256"),
                    "child_model_sha256": child.get("model_sha256"),
                    "reference_result_sha256": (reference.get("raw_result") or {}).get("result_sha256"),
                    "child_result_sha256": (child.get("raw_result") or {}).get("result_sha256"),
                    "dependency_updates": ["area", "inertia", "self_weight", "model", "all_checks"],
                    "memory_eligibility": "REVIEW_REQUIRED" if valid else "INELIGIBLE",
                    "accepted": child["benchmark_status"] == "PASS" and not collateral,
                    "causal_claim": "NO_UNIQUE_CAUSE_IDENTIFIED",
                })
                if child["benchmark_status"] == "PASS" and not collateral:
                    report["feasible_benchmark_candidates"].append(child["evaluation_id"])
                    report["status"] = "BENCHMARK_FEASIBLE"
                    break
            if report["status"] == "RUNNING":
                report["status"] = "NO_FEASIBLE_DESIGN_FOUND_WITHIN_BUDGET"
                report["stop_reason"] = "SOLVER_BUDGET_EXHAUSTED" if report["solver_calls"] >= contract.solver_budget else "ACTION_LIST_EXHAUSTED"
    report["report_sha256"] = digest(report)
    return report


def verify_evidence(directory: Path) -> dict:
    """Kiểm integrity mọi artifact; không nâng integrity thành approval vật lý."""
    root = directory.resolve()
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    claimed = manifest.pop("manifest_sha256")
    if digest(manifest) != claimed:
        raise ValueError("Manifest integrity failure")
    names = [entry["path"] for entry in manifest["files"]]
    if len(names) != len(set(names)):
        raise ValueError("Duplicate manifest artifact paths")
    for entry in manifest["files"]:
        target = (root / entry["path"]).resolve()
        if not target.is_relative_to(root) or target.is_symlink() or not target.is_file():
            raise ValueError("Artifact path escapes evidence package or is missing")
        if hashlib.sha256(target.read_bytes()).hexdigest() != entry["sha256"]:
            raise ValueError(f"Artifact integrity failure: {entry['path']}")
    report = json.loads((root / "trajectory.json").read_text(encoding="utf-8"))
    report_sha = report.pop("report_sha256")
    if digest(report) != report_sha:
        raise ValueError("Trajectory integrity failure")
    expected = {"trajectory.json", "contract.json", "environment.json"}
    if manifest["run_id"] != report["run_id"]:
        raise ValueError("Run identity integrity failure")
    saved_contract = json.loads((root / "contract.json").read_text(encoding="utf-8"))
    if saved_contract != report["contract"] or digest(saved_contract) != report["contract_sha256"]:
        raise ValueError("Contract cross-link integrity failure")
    identifiers = [item["evaluation_id"] for item in report["evaluations"]]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("Duplicate evaluation identities")
    for item in report["evaluations"]:
        for suffix, key in (("_model.json", "model"), ("_solver_raw.json", "raw_result")):
            name = item["evaluation_id"] + suffix
            expected.add(name)
            target = (root/name).resolve()
            if not target.is_relative_to(root) or name not in names:
                raise ValueError("Missing or unsafe evaluation artifact")
            if json.loads(target.read_text(encoding="utf-8")) != item[key]:
                raise ValueError("Evaluation cross-link integrity failure")
        if item["contract_sha256"] != report["contract_sha256"]:
            raise ValueError("Evaluation contract integrity failure")
    if set(names) != expected:
        raise ValueError("Evidence package inventory integrity failure")
    return {"status": "INTEGRITY_VERIFIED", "file_count": len(manifest["files"]),
            "engineering_approval": False}


def write_evidence(directory: Path, report: dict) -> None:
    """Ghi gói mới độc quyền, không ghi đè raw history hay báo cáo cũ."""
    directory.mkdir(parents=True, exist_ok=False)
    records = []

    def save(name: str, value: object) -> None:
        data = (canonical(value) + "\n").encode("utf-8")
        with (directory / name).open("xb") as handle:
            handle.write(data)
        records.append({"path": name, "sha256": hashlib.sha256(data).hexdigest()})

    save("trajectory.json", report)
    save("contract.json", report["contract"])
    for item in report["evaluations"]:
        save(item["evaluation_id"] + "_model.json", item["model"])
        save(item["evaluation_id"] + "_solver_raw.json", item.get("raw_result"))
    sources = ["bridge_evolution/evobridge.py", "bridge_evolution/frame_f1.py",
               "bridge_evolution/__init__.py", "contracts/frame_f1_model.schema.json",
               "contracts/frame_f1_result.schema.json", "docs/design_basis/frame_f1_basis.json", BASIS_REF]
    save("environment.json", {"python": platform.python_version(), "platform": platform.platform(),
                              "solver_version": SOLVER_VERSION,
                              "dependencies": {p: package_version(p) for p in ("numpy", "jsonschema")},
                              "sources": [{"path": p, "sha256": hashlib.sha256((REPO_ROOT/p).read_bytes()).hexdigest()} for p in sources]})
    manifest = {"schema_version": "1.0", "run_id": report["run_id"], "files": records}
    manifest["manifest_sha256"] = digest(manifest)
    (directory / "manifest.json").write_text(canonical(manifest) + "\n", encoding="utf-8")
    verify_evidence(directory)


def main(argv: list[str] | None = None) -> int:
    """CLI local dùng kernel hiện có, không mở CAD/solver ngoài hoặc gọi LLM."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path)
    parser.add_argument("--initial-height", type=float)
    parser.add_argument("--heights", nargs="*", type=float, default=[])
    parser.add_argument("--out", type=Path)
    parser.add_argument("--verify", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.verify:
            print(canonical(verify_evidence(args.verify)))
            return 0
        if args.contract is None or args.initial_height is None or args.out is None:
            parser.error("--contract, --initial-height and --out are required")
        if args.out.exists():
            raise ValueError("Output already exists; choose a new run directory")
        contract = BeamContract.from_mapping(json.loads(args.contract.read_text(encoding="utf-8")))
        report = run_interventions(contract, args.initial_height, args.heights)
        write_evidence(args.out, report)
        print(canonical({"status": report["status"], "solver_calls": report["solver_calls"],
                         "evidence": str(args.out.resolve()), "claim_level": "IDEA"}))
        return 0 if report["status"] == "BENCHMARK_FEASIBLE" else 2
    except (ValueError, TypeError, OSError) as exc:
        print(canonical({"status": "ERROR", "error": str(exc)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
