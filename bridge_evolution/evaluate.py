"""Contract trung tâm: evaluate_candidate(BridgeDesignState) -> EvaluationResult.

Pipeline: schema → L0 hình học → solver vật lý → independent verifier
          → objectives → provenance/artifacts.
L0 chặn HARD violation TRƯỚC khi mở solver (tiết kiệm ngân sách mô phỏng và
đóng vai trò safety shield cho EA/RL).
"""
import json
from copy import deepcopy
from datetime import datetime, timezone

from . import __version__, ARTIFACTS_DIR
from .catalogs import load_catalogs, load_grammar
from .fe_adapter import run_analysis, SolverError, SOLVER_VERSION
from .geometry import check_geometry
from .objectives import compute_objectives
from .state import (validate_design_state, validate_evaluation_result,
                    input_hash, make_case_id)
from .verifier import verify_candidate, RULESET_VERSION


def _requested_solver(state) -> str:
    """Tên solver trong request, kể cả khi state sai schema."""
    if not isinstance(state, dict):
        return "UNSPECIFIED"
    analysis = state.get("analysis")
    if not isinstance(analysis, dict):
        return "UNSPECIFIED"
    solver = analysis.get("solver")
    return solver if isinstance(solver, str) and solver else "UNSPECIFIED"


def _solver_provenance_version(requested_solver: str) -> str:
    if requested_solver == "BUILTIN_L1":
        return SOLVER_VERSION + f" (pkg {__version__})"
    return f"{requested_solver}/adapter-requested (pkg {__version__})"


def _provenance(state) -> dict:
    cat = load_catalogs()
    grammar_version = "n/a"
    try:
        family = state.get("family", "") if isinstance(state, dict) else ""
        grammar_version = load_grammar(family).get("grammar_version", "n/a")
    except Exception:
        pass
    state_provenance = state.get("provenance") if isinstance(state, dict) else None
    requested_solver = _requested_solver(state)
    return {
        "input_hash": input_hash(state),
        "ruleset_version": RULESET_VERSION,
        "solver_version": _solver_provenance_version(requested_solver),
        "catalogs_version": cat["catalogs_version"],
        "grammar_version": grammar_version,
        "random_seed": (state_provenance or {}).get("random_seed")
        if isinstance(state_provenance, dict) else None,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def evaluate_candidate(state: dict, save_artifacts: bool = False) -> dict:
    # case_id do caller gửi lên chỉ là metadata legacy. Mọi output và
    # filesystem path đều bắt nguồn từ hash nội dung tin cậy.
    case_id = make_case_id(state)
    requested_solver = _requested_solver(state)
    result = {
        "case_id": case_id,
        "status": "SUCCESS",
        "feasible": False,
        "solver": {"status": "NOT_RUN", "name": requested_solver},
        "violations": [],
        "provenance": _provenance(state),
    }

    # 1. Schema
    schema_errors = validate_design_state(state)
    if schema_errors:
        result["status"] = "SCHEMA_INVALID"
        result["violations"] = [{"rule_id": "SCHEMA-001", "severity": "HARD",
                                 "message": e, "margin": 1.0} for e in schema_errors]
        return _finish(result, state, save_artifacts)

    # 2. L0 — hình học/cấu tạo (id catalog lạ → coi như schema-level)
    try:
        geo_violations, geom = check_geometry(state)
    except KeyError as e:
        result["status"] = "SCHEMA_INVALID"
        result["violations"] = [{"rule_id": "SCHEMA-002", "severity": "HARD",
                                 "message": f"Id không tồn tại trong catalog: {e}", "margin": 1.0}]
        return _finish(result, state, save_artifacts)

    if any(v["severity"] == "HARD" for v in geo_violations):
        result["status"] = "GEOMETRY_INVALID"
        result["violations"] = geo_violations
        return _finish(result, state, save_artifacts)

    # 3. Solver vật lý
    try:
        analysis = run_analysis(state, geom)
    except SolverError as e:
        result["status"] = "SOLVER_FAILED"
        result["solver"] = {"status": "NOT_CONVERGED", "name": requested_solver}
        result["violations"] = [{"rule_id": "SOLVER-001", "severity": "HARD",
                                 "message": str(e), "margin": 1.0}]
        return _finish(result, state, save_artifacts)
    result["solver"] = {k: analysis["solver"][k] for k in ("status", "name", "runtime_ms")}

    # 4. Independent verifier
    violations, responses = verify_candidate(state, geom, analysis)
    result["violations"] = violations
    result["responses"] = responses
    result["feasible"] = not any(v["severity"] == "HARD" for v in violations)

    # 5. Objectives (tính cả khi infeasible — phục vụ phân tích trade-off)
    result["objectives"] = compute_objectives(state, geom)

    return _finish(result, state, save_artifacts, analysis)


def hard_violation_score(result: dict) -> float:
    """Tổng mức vi phạm HARD chuẩn hóa — dùng cho constraint-domination (Deb) và reward RL."""
    return sum(v["margin"] for v in result["violations"] if v["severity"] == "HARD")


def _safe_artifact_dir(case_id: str):
    """Resolve và chứng minh thư mục case nằm trong artifacts root."""
    root = ARTIFACTS_DIR.resolve()
    out = (root / case_id).resolve()
    try:
        relative = out.relative_to(root)
    except ValueError as exc:
        raise ValueError("Artifact path thoát khỏi ARTIFACTS_DIR") from exc
    if not relative.parts:
        raise ValueError("Artifact case directory không được trùng ARTIFACTS_DIR")
    return root, out


def _finish(result: dict, state, save: bool, analysis: dict | None = None) -> dict:
    payloads = None
    if save:
        root, out = _safe_artifact_dir(result["case_id"])
        artifact_state = deepcopy(state)
        if isinstance(artifact_state, dict):
            artifact_state["case_id"] = result["case_id"]

        payloads = {
            "design_state": artifact_state,
            "verification_report": result,
        }
        if analysis is not None:
            payloads["analysis_result"] = analysis

        # Gắn manifest TRƯỚC validation và trước khi serialize report;
        # verification_report.json nhờ đó tự mô tả đủ bộ artifact.
        result["artifacts"] = {
            name: (out / f"{name}.json").relative_to(root.parent).as_posix()
            for name in payloads
        }

    errors = validate_evaluation_result(result)
    assert not errors, f"EvaluationResult vi phạm contract: {errors}"

    if payloads is not None:
        # _safe_artifact_dir đã resolve cả junction/symlink tồn tại. Chỉ
        # tạo thư mục sau khi result hoàn chỉnh đã qua contract.
        out.mkdir(parents=True, exist_ok=True)
        for name, payload in payloads.items():
            p = out / f"{name}.json"
            p.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str),
                         encoding="utf-8")
    return result
