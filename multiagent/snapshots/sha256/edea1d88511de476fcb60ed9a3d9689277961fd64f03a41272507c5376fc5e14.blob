"""Contract trung tâm: evaluate_candidate(BridgeDesignState) -> EvaluationResult.

Pipeline: schema → L0 hình học → solver vật lý → independent verifier
          → objectives → provenance/artifacts.
L0 chặn HARD violation TRƯỚC khi mở solver (tiết kiệm ngân sách mô phỏng và
đóng vai trò safety shield cho EA/RL).
"""
import hashlib
import json
import math
import re
from copy import deepcopy
from datetime import datetime, timezone

from . import __version__, ARTIFACTS_DIR
from .catalogs import load_catalogs, load_grammar
from .fe_adapter import run_analysis, SolverError, SOLVER_VERSION
from .geometry import check_geometry
from .objectives import compute_objectives
from .state import (validate_design_state, validate_evaluation_result,
                    input_hash, make_case_id)
from .verifier import verify_candidate, RULESET_VERSION, ruleset_version_for


COMPONENT_AUDIT_REGISTRY_VERSION = "component-audit/1.0.0"


def _component_entry(label: str, hard: tuple[str, ...],
                     advisory: tuple[str, ...] = ()) -> dict:
    """Khai bộ evidence cần có; không hiện thực công thức sức kháng."""
    return {
        "label": label,
        "required_checks": {
            **{check_id: "HARD" for check_id in hard},
            **{check_id: "SOFT" for check_id in advisory},
        },
    }


# Registry bao phủ hệ kết cấu chính, phụ trợ và trạng thái thi công của cầu.
# Những check ngoài L1 được giữ ở đây để runtime trả NOT_EVALUATED minh bạch,
# không bị bỏ quên hoặc bị LLM tự suy diễn.
COMPONENT_AUDIT_REGISTRY = {
    "DECK_SLAB": _component_entry(
        "Bản mặt cầu",
        ("FLEXURE_STRENGTH", "SHEAR_PUNCHING", "SERVICE_CRACKING", "FATIGUE"),
        ("DURABILITY",),
    ),
    "LONGITUDINAL_GIRDER": _component_entry(
        "Dầm chủ",
        ("FLEXURE_STRENGTH", "SHEAR_TORSION", "SERVICE_STRESS", "DEFLECTION",
         "FATIGUE", "STABILITY"),
        ("DURABILITY",),
    ),
    "CROSS_BEAM_DIAPHRAGM": _component_entry(
        "Dầm ngang hoặc vách ngăn",
        ("FLEXURE_SHEAR", "CONNECTION", "FATIGUE"),
        ("DURABILITY",),
    ),
    "PIER_COLUMN": _component_entry(
        "Thân trụ",
        ("AXIAL_FLEXURE", "SHEAR", "SECOND_ORDER", "DUCTILITY",
         "FOUNDATION_INTERFACE"),
        ("DURABILITY",),
    ),
    "PIER_CAP": _component_entry(
        "Xà mũ trụ",
        ("FLEXURE", "SHEAR", "STRUT_TIE", "BEARING_ZONE"),
        ("DURABILITY",),
    ),
    "ABUTMENT": _component_entry(
        "Mố cầu",
        ("STABILITY", "STRUCTURAL_STRENGTH", "SOIL_STRUCTURE", "SEISMIC"),
        ("DURABILITY",),
    ),
    "RETAINING_WING_WALL": _component_entry(
        "Tường cánh hoặc tường chắn",
        ("SLIDING", "OVERTURNING", "BEARING_PRESSURE", "STRUCTURAL_STRENGTH"),
        ("DRAINAGE", "DURABILITY"),
    ),
    "FOUNDATION_FOOTING": _component_entry(
        "Bệ hoặc móng nông",
        ("BEARING_CAPACITY", "SLIDING", "OVERTURNING", "SETTLEMENT",
         "PUNCHING_SHEAR", "SCOUR"),
        ("DURABILITY",),
    ),
    "FOUNDATION_PILE": _component_entry(
        "Cọc và nhóm cọc",
        ("AXIAL_CAPACITY", "LATERAL_CAPACITY", "GROUP_EFFECT", "SETTLEMENT",
         "STRUCTURAL_STRENGTH", "SCOUR"),
        ("DURABILITY",),
    ),
    "BEARING": _component_entry(
        "Gối cầu",
        ("REACTION_CAPACITY", "ROTATION", "TRANSLATION", "STABILITY", "FATIGUE"),
        ("REPLACEABILITY", "DURABILITY"),
    ),
    "EXPANSION_JOINT": _component_entry(
        "Khe co giãn",
        ("MOVEMENT_RANGE", "FATIGUE", "ANCHORAGE"),
        ("DRAINAGE", "MAINTAINABILITY", "DURABILITY"),
    ),
    "PRESTRESSING_SYSTEM": _component_entry(
        "Hệ dự ứng lực",
        ("JACKING_STRESS", "TRANSFER_STRESS", "LOSSES", "ULTIMATE_STRENGTH",
         "ANCHORAGE_ZONE"),
        ("GROUTING_DURABILITY",),
    ),
    "CABLE_SYSTEM": _component_entry(
        "Cáp chủ, dây văng hoặc dây treo",
        ("CABLE_STRENGTH", "FATIGUE", "VIBRATION", "ANCHORAGE"),
        ("REPLACEABILITY", "CORROSION_PROTECTION"),
    ),
    "ARCH_RIB": _component_entry(
        "Sườn vòm",
        ("COMBINED_STRENGTH", "GLOBAL_BUCKLING", "LOCAL_BUCKLING", "FATIGUE"),
        ("DURABILITY",),
    ),
    "TRUSS_MEMBER": _component_entry(
        "Thanh giàn",
        ("AXIAL_STRENGTH", "BUCKLING", "FATIGUE", "CONNECTION"),
        ("DURABILITY",),
    ),
    "CONNECTION": _component_entry(
        "Liên kết",
        ("STRENGTH", "SLIP", "FATIGUE", "DUCTILITY"),
        ("DURABILITY",),
    ),
    "APPROACH_SLAB": _component_entry(
        "Bản quá độ",
        ("FLEXURE", "SETTLEMENT_TRANSITION"),
        ("DRAINAGE", "DURABILITY"),
    ),
    "PARAPET_BARRIER": _component_entry(
        "Lan can hoặc dải phân cách",
        ("VEHICLE_IMPACT", "PEDESTRIAN_SAFETY", "ANCHORAGE"),
        ("DURABILITY",),
    ),
    "WATERPROOFING_DRAINAGE": _component_entry(
        "Chống thấm và thoát nước",
        ("WATER_TIGHTNESS", "DRAINAGE_CAPACITY", "DISCHARGE_PATH"),
        ("MAINTAINABILITY",),
    ),
    "TEMPORARY_WORKS": _component_entry(
        "Kết cấu và trạng thái thi công tạm",
        ("STABILITY", "STRENGTH", "CONSTRUCTION_STAGE", "ERECTION_SEQUENCE",
         "REMOVAL_SEQUENCE"),
    ),
}


_COMPONENT_REPAIR_ACTIONS = {
    "DECK_SLAB": "Rà soát chiều dày, cốt thép và sơ đồ truyền lực của bản mặt cầu",
    "LONGITUDINAL_GIRDER": "Rà soát tiết diện, vật liệu, cốt thép/DƯL và sơ đồ nhịp dầm chủ",
    "CROSS_BEAM_DIAPHRAGM": "Rà soát tiết diện, khoảng cách và liên kết dầm ngang/vách ngăn",
    "PIER_COLUMN": "Rà soát tiết diện, cốt thép, chiều dài tính toán và liên kết thân trụ",
    "PIER_CAP": "Rà soát kích thước, cốt thép và mô hình vùng gián đoạn của xà mũ",
    "ABUTMENT": "Rà soát hình học, đất đắp, liên kết và điều kiện nền của mố",
    "RETAINING_WING_WALL": "Rà soát hình học, cốt thép, tải đất và thoát nước tường",
    "FOUNDATION_FOOTING": "Rà soát kích thước bệ, cao độ, tải truyền và mô hình nền",
    "FOUNDATION_PILE": "Rà soát loại, số lượng, chiều dài, nhóm cọc và tương tác đất-cọc",
    "BEARING": "Rà soát loại gối, kích thước, phương chuyển vị và phản lực thiết kế",
    "EXPANSION_JOINT": "Rà soát loại khe, hành trình, neo giữ và chi tiết thoát nước",
    "PRESTRESSING_SYSTEM": "Rà soát bố trí cáp DƯL, trình tự căng và vùng neo",
    "CABLE_SYSTEM": "Rà soát tiết diện, lực căng, neo, giảm chấn và bảo vệ cáp",
    "ARCH_RIB": "Rà soát tiết diện, giằng, đường lực và ổn định sườn vòm",
    "TRUSS_MEMBER": "Rà soát tiết diện, chiều dài tính toán và liên kết nút giàn",
    "CONNECTION": "Rà soát đường truyền lực, cấu tạo và độ cứng liên kết",
    "APPROACH_SLAB": "Rà soát hình học, cốt thép và xử lý chuyển tiếp bản quá độ",
    "PARAPET_BARRIER": "Rà soát cấp va xe, hình học và neo lan can/dải chắn",
    "WATERPROOFING_DRAINAGE": "Rà soát lớp chống thấm, khẩu độ thu và đường xả nước",
    "TEMPORARY_WORKS": "Rà soát hệ chống đỡ, trình tự lắp/tháo và tải thi công",
}


_CHECK_STATUSES = {"PASS", "FAIL", "NOT_EVALUATED", "NOT_APPLICABLE"}
_CHECK_SEVERITIES = {"HARD", "SOFT"}
_EVIDENCE_FIDELITIES = {
    "L0", "L1", "L2", "L3", "EXTERNAL_SOLVER", "PHYSICAL", "ENGINEER_REVIEW",
}
_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")


def _canonical_sha256(payload) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _token(value, fallback: str) -> str:
    if not isinstance(value, str) or not value.strip():
        return fallback
    normalized = re.sub(r"[^A-Z0-9_]+", "_", value.strip().upper()).strip("_")
    return (normalized or fallback)[:96]


def _blocking_reason(code: str, message: str, *, component_id=None,
                     check_id=None) -> dict:
    return {
        "code": code,
        "component_id": component_id,
        "check_id": check_id,
        "message": message,
    }


def _normalise_evidence(raw) -> tuple[dict | None, str | None]:
    if not isinstance(raw, dict):
        return None, "thiếu object evidence"
    source_ref = raw.get("source_ref")
    digest = raw.get("sha256")
    fidelity = raw.get("fidelity")
    producer = raw.get("producer")
    problems = []
    if not isinstance(source_ref, str) or not source_ref.strip():
        problems.append("source_ref rỗng")
    if not isinstance(digest, str) or not _SHA256_RE.fullmatch(digest):
        problems.append("sha256 không phải 64 ký tự hex")
    if fidelity not in _EVIDENCE_FIDELITIES:
        problems.append("fidelity không được hỗ trợ")
    if not isinstance(producer, str) or not producer.strip():
        problems.append("producer rỗng")
    generated_at = raw.get("generated_at_utc")
    if generated_at is not None and (not isinstance(generated_at, str)
                                     or not generated_at.strip()):
        problems.append("generated_at_utc không hợp lệ")
    if problems:
        return None, "; ".join(problems)
    evidence = {
        "source_ref": source_ref.strip(),
        "sha256": digest.lower(),
        "fidelity": fidelity,
        "producer": producer.strip(),
    }
    if generated_at is not None:
        evidence["generated_at_utc"] = generated_at.strip()
    return evidence, None


def _not_evaluated_check(check_id: str, severity: str, message: str) -> dict:
    return {
        "check_id": check_id,
        "status": "NOT_EVALUATED",
        "severity": severity,
        "evidence": None,
        "message": message,
        "rationale": None,
        "utilization": None,
    }


def _normalise_check(raw: dict, component_id: str, check_id: str,
                     expected_severity: str | None,
                     blockers: list[dict]) -> dict:
    status = raw.get("status")
    severity = raw.get("severity", expected_severity or "HARD")
    downgrade_reasons = []

    if status not in _CHECK_STATUSES:
        status = "NOT_EVALUATED"
        downgrade_reasons.append("status không hợp lệ")
    if severity not in _CHECK_SEVERITIES:
        severity = expected_severity or "HARD"
        status = "NOT_EVALUATED"
        downgrade_reasons.append("severity không hợp lệ")
    if expected_severity is not None and severity != expected_severity:
        severity = expected_severity
        status = "NOT_EVALUATED"
        downgrade_reasons.append("không được thay severity của required check")

    evidence, evidence_problem = _normalise_evidence(raw.get("evidence"))
    rationale = raw.get("rationale")
    rationale = rationale.strip() if isinstance(rationale, str) and rationale.strip() else None
    if status in {"PASS", "FAIL"} and evidence_problem:
        status = "NOT_EVALUATED"
        downgrade_reasons.append(evidence_problem)
    if status == "NOT_APPLICABLE" and (evidence_problem or rationale is None):
        status = "NOT_EVALUATED"
        downgrade_reasons.append(evidence_problem or "NOT_APPLICABLE phải có rationale")

    utilization = raw.get("utilization")
    if utilization is not None:
        valid_number = (isinstance(utilization, (int, float))
                        and not isinstance(utilization, bool)
                        and math.isfinite(utilization) and utilization >= 0)
        if not valid_number:
            utilization = None
            if status in {"PASS", "FAIL"}:
                status = "NOT_EVALUATED"
                downgrade_reasons.append("utilization không phải số hữu hạn không âm")
    if status == "PASS" and utilization is not None and utilization > 1.0:
        status = "NOT_EVALUATED"
        downgrade_reasons.append("PASS mâu thuẫn với utilization > 1")

    if downgrade_reasons and severity == "HARD":
        blockers.append(_blocking_reason(
            "INVALID_HARD_CHECK_EVIDENCE",
            "; ".join(dict.fromkeys(downgrade_reasons)),
            component_id=component_id,
            check_id=check_id,
        ))

    message = raw.get("message")
    if not isinstance(message, str) or not message.strip():
        message = f"Kết quả do caller cung cấp cho {check_id}."
    else:
        message = message.strip()
    if downgrade_reasons:
        message += " Hạ về NOT_EVALUATED: " \
            + "; ".join(dict.fromkeys(downgrade_reasons)) + "."

    return {
        "check_id": check_id,
        "status": status,
        "severity": severity,
        "evidence": evidence if status != "NOT_EVALUATED" else None,
        "message": message,
        "rationale": rationale,
        "utilization": utilization,
    }


def _proposal_for(candidate_id: str, component: dict, check: dict,
                  ordinal: int) -> dict:
    component_id = component["component_id"]
    check_id = check["check_id"]
    if check["status"] == "NOT_EVALUATED":
        proposal_kind = "EVIDENCE_REQUEST"
        action = (f"Bổ sung và kiểm chứng bằng chứng cho {check_id} của "
                  f"{component_id}; chưa đổi hình học khi chưa biết nguyên nhân.")
        expected_direction = (
            "Đóng khoảng trống bằng chứng; chưa dự báo thay đổi sức kháng hoặc nội lực."
        )
        tradeoffs = ["thời gian mô hình hóa", "chi phí kiểm tra", "độ tin cậy dữ liệu"]
    else:
        proposal_kind = "REPAIR"
        action = _COMPONENT_REPAIR_ACTIONS.get(
            component["kind"], "Rà soát cấu tạo, mô hình và tham số thiết kế cấu kiện",
        ) + f"; xử lý check {check_id}."
        expected_direction = (
            "Nhằm giảm mức sử dụng hoặc loại nguyên nhân FAIL; hiệu quả chưa được xác minh."
        )
        tradeoffs = ["khối lượng", "chi phí", "thi công", "tác động sang cấu kiện liên quan"]

    seed = (f"{candidate_id}|{component_id}|{component['kind']}|{check_id}|"
            f"{check['status']}|{ordinal}")
    return {
        "proposal_id": "RP-" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12],
        "component_id": component_id,
        "check_id": check_id,
        "kind": proposal_kind,
        "action": action,
        "expected_direction": expected_direction,
        "tradeoffs": tradeoffs,
        "required_evidence": [
            f"Bằng chứng mới cho {component_id}/{check_id} có SHA-256 và provenance",
            "Kết quả phân tích lại bằng solver/phương pháp phù hợp với check",
            "Đánh giá lại bởi independent verifier hoặc kỹ sư có thẩm quyền",
        ],
        "requires_reanalysis": True,
        "claim": "UNVERIFIED_PROPOSAL",
    }


def build_component_audit(state: dict, result: dict,
                          component_manifest) -> dict:
    """Chuẩn hóa audit đa cấu kiện fail-closed, không tự tính cơ học.

    Hàm không sửa ``result.status`` hay ``result.feasible``. PASS/FAIL chỉ được
    chuyển tiếp khi caller cung cấp evidence có provenance; hard check thiếu
    evidence bị hạ về NOT_EVALUATED và làm audit BLOCKED.
    """
    candidate_id = result["case_id"]
    result_provenance = result.get("provenance")
    candidate_digest = (result_provenance or {}).get("input_hash") \
        if isinstance(result_provenance, dict) else None
    if not isinstance(candidate_digest, str) or not _SHA256_RE.fullmatch(candidate_digest):
        candidate_digest = input_hash(state)

    state_provenance = state.get("provenance") if isinstance(state, dict) else None
    state_parent = (state_provenance or {}).get("parent_candidate_id") \
        if isinstance(state_provenance, dict) else None
    blockers = []
    components = []

    if not isinstance(component_manifest, dict):
        manifest = {}
        blockers.append(_blocking_reason(
            "INVALID_COMPONENT_MANIFEST", "component_manifest phải là object JSON.",
        ))
    else:
        manifest = component_manifest

    declared_candidate = manifest.get("candidate_id")
    if declared_candidate is not None and declared_candidate != candidate_id:
        blockers.append(_blocking_reason(
            "CANDIDATE_LINEAGE_MISMATCH",
            f"manifest khai candidate_id={declared_candidate!r}, chờ {candidate_id!r}.",
        ))

    manifest_parent = manifest.get("parent_candidate_id", state_parent)
    if manifest_parent is not None and (not isinstance(manifest_parent, str)
                                        or not manifest_parent.strip()):
        blockers.append(_blocking_reason(
            "INVALID_PARENT_LINEAGE",
            "parent_candidate_id phải là chuỗi khác rỗng hoặc null.",
        ))
        manifest_parent = None
    elif isinstance(manifest_parent, str):
        manifest_parent = manifest_parent.strip()
    if (state_parent is not None and manifest.get("parent_candidate_id") is not None
            and manifest_parent != state_parent):
        blockers.append(_blocking_reason(
            "PARENT_LINEAGE_MISMATCH",
            f"manifest parent={manifest_parent!r} khác state parent={state_parent!r}.",
        ))

    raw_components = manifest.get("components")
    if not isinstance(raw_components, list) or not raw_components:
        blockers.append(_blocking_reason(
            "EMPTY_COMPONENT_MANIFEST", "Manifest phải có mảng components khác rỗng.",
        ))
        raw_components = []

    seen_component_ids = set()
    for index, raw_component in enumerate(raw_components, start=1):
        if not isinstance(raw_component, dict):
            component_id = f"INVALID_COMPONENT_{index:03d}"
            blockers.append(_blocking_reason(
                "INVALID_COMPONENT_ENTRY", "Mỗi component phải là object JSON.",
                component_id=component_id,
            ))
            components.append({
                "component_id": component_id,
                "kind": "UNKNOWN",
                "registry_supported": False,
                "checks": [_not_evaluated_check(
                    "COMPONENT_KIND_SUPPORTED", "HARD",
                    "Không thể xác định loại cấu kiện từ entry không hợp lệ.",
                )],
            })
            continue

        raw_component_id = raw_component.get("component_id")
        if not isinstance(raw_component_id, str) or not raw_component_id.strip():
            component_id = f"INVALID_COMPONENT_{index:03d}"
            blockers.append(_blocking_reason(
                "INVALID_COMPONENT_ID", "component_id phải là chuỗi khác rỗng.",
                component_id=component_id,
            ))
        else:
            component_id = raw_component_id.strip()[:128]
        if component_id in seen_component_ids:
            blockers.append(_blocking_reason(
                "DUPLICATE_COMPONENT_ID",
                f"component_id {component_id!r} xuất hiện nhiều lần.",
                component_id=component_id,
            ))
        seen_component_ids.add(component_id)

        kind = _token(raw_component.get("kind"), "UNKNOWN")
        registry_entry = COMPONENT_AUDIT_REGISTRY.get(kind)
        if registry_entry is None:
            blockers.append(_blocking_reason(
                "UNKNOWN_COMPONENT_KIND",
                f"Loại {kind!r} chưa có trong registry {COMPONENT_AUDIT_REGISTRY_VERSION}.",
                component_id=component_id,
                check_id="COMPONENT_KIND_SUPPORTED",
            ))
            components.append({
                "component_id": component_id,
                "kind": kind,
                "registry_supported": False,
                "checks": [_not_evaluated_check(
                    "COMPONENT_KIND_SUPPORTED", "HARD",
                    "Không có bộ hard check được kiểm soát cho loại cấu kiện này.",
                )],
            })
            continue

        raw_checks = raw_component.get("checks")
        if not isinstance(raw_checks, list):
            blockers.append(_blocking_reason(
                "INVALID_CHECK_LIST", "checks phải là một mảng JSON.",
                component_id=component_id,
            ))
            raw_checks = []

        supplied_checks = {}
        for check_index, raw_check in enumerate(raw_checks, start=1):
            if not isinstance(raw_check, dict):
                blockers.append(_blocking_reason(
                    "INVALID_CHECK_ENTRY", f"Check thứ {check_index} không phải object JSON.",
                    component_id=component_id,
                ))
                continue
            check_id = _token(raw_check.get("check_id"), f"INVALID_CHECK_{check_index:03d}")
            if check_id in supplied_checks:
                blockers.append(_blocking_reason(
                    "DUPLICATE_CHECK_ID",
                    f"check_id {check_id!r} xuất hiện nhiều lần trong cùng cấu kiện.",
                    component_id=component_id,
                    check_id=check_id,
                ))
                continue
            supplied_checks[check_id] = raw_check

        normalized_checks = []
        for check_id, severity in sorted(registry_entry["required_checks"].items()):
            raw_check = supplied_checks.pop(check_id, None)
            if raw_check is None:
                normalized_checks.append(_not_evaluated_check(
                    check_id, severity, f"Thiếu bằng chứng bắt buộc cho {kind}/{check_id}.",
                ))
                if severity == "HARD":
                    blockers.append(_blocking_reason(
                        "MISSING_HARD_CHECK_EVIDENCE",
                        f"Thiếu hard check {kind}/{check_id}.",
                        component_id=component_id,
                        check_id=check_id,
                    ))
                continue
            normalized_checks.append(_normalise_check(
                raw_check, component_id, check_id, severity, blockers,
            ))

        # Check chuyên dự án được phép mở rộng nhưng vẫn phải có evidence.
        for check_id, raw_check in sorted(supplied_checks.items()):
            normalized_checks.append(_normalise_check(
                raw_check, component_id, check_id, None, blockers,
            ))

        components.append({
            "component_id": component_id,
            "kind": kind,
            "registry_supported": True,
            "checks": sorted(normalized_checks, key=lambda item: item["check_id"]),
        })

    components.sort(key=lambda item: (item["component_id"], item["kind"]))
    blockers.sort(key=lambda item: (
        item["component_id"] or "", item["check_id"] or "", item["code"], item["message"],
    ))
    hard_checks = [check for component in components for check in component["checks"]
                   if check["severity"] == "HARD"]
    if any(check["status"] == "FAIL" for check in hard_checks):
        audit_status = "REJECTED"
    elif blockers or any(check["status"] == "NOT_EVALUATED" for check in hard_checks):
        audit_status = "BLOCKED"
    else:
        audit_status = "SCREENED"

    proposals = []
    ordinal = 0
    for component in components:
        for check in component["checks"]:
            if check["status"] not in {"FAIL", "NOT_EVALUATED"}:
                continue
            ordinal += 1
            proposals.append(_proposal_for(candidate_id, component, check, ordinal))
    proposals.sort(key=lambda item: item["proposal_id"])

    audit = {
        "registry_version": COMPONENT_AUDIT_REGISTRY_VERSION,
        "candidate_id": candidate_id,
        "candidate_input_hash": candidate_digest.lower(),
        "parent_candidate_id": manifest_parent,
        "status": audit_status,
        "verdict_authority": "INDEPENDENT_VERIFIER",
        "alters_evaluation_verdict": False,
        "components": components,
        "blocking_reasons": blockers,
        "proposals": proposals,
        # Ghép chuỗi để bộ inventory rule không hiểu nhầm tên thuật toán băm
        # thành rule_id dạng XXX-NNN.
        "hash_algorithm": "SHA" + "-256",
    }
    audit["audit_hash"] = _canonical_sha256(audit)
    return audit


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
        "ruleset_version": ruleset_version_for(state),
        "solver_version": _solver_provenance_version(requested_solver),
        "catalogs_version": cat["catalogs_version"],
        "grammar_version": grammar_version,
        "random_seed": (state_provenance or {}).get("random_seed")
        if isinstance(state_provenance, dict) else None,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def evaluate_candidate(state: dict, save_artifacts: bool = False,
                       component_manifest: dict | None = None) -> dict:
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
        return _finish(result, state, save_artifacts,
                       component_manifest=component_manifest)

    # 2. L0 — hình học/cấu tạo (id catalog lạ → coi như schema-level)
    try:
        geo_violations, geom = check_geometry(state)
    except KeyError as e:
        result["status"] = "SCHEMA_INVALID"
        result["violations"] = [{"rule_id": "SCHEMA-002", "severity": "HARD",
                                 "message": f"Id không tồn tại trong catalog: {e}", "margin": 1.0}]
        return _finish(result, state, save_artifacts,
                       component_manifest=component_manifest)

    if any(v["severity"] == "HARD" for v in geo_violations):
        result["status"] = "GEOMETRY_INVALID"
        result["violations"] = geo_violations
        return _finish(result, state, save_artifacts,
                       component_manifest=component_manifest)

    # 3. Solver vật lý
    try:
        analysis = run_analysis(state, geom)
    except SolverError as e:
        result["status"] = "SOLVER_FAILED"
        result["solver"] = {"status": "NOT_CONVERGED", "name": requested_solver}
        result["violations"] = [{"rule_id": "SOLVER-001", "severity": "HARD",
                                 "message": str(e), "margin": 1.0}]
        return _finish(result, state, save_artifacts,
                       component_manifest=component_manifest)
    result["solver"] = {k: analysis["solver"][k] for k in ("status", "name", "runtime_ms")}

    # 4. Independent verifier
    violations, responses = verify_candidate(state, geom, analysis)
    result["violations"] = violations
    result["responses"] = responses
    result["feasible"] = not any(v["severity"] == "HARD" for v in violations)

    # 5. Objectives (tính cả khi infeasible — phục vụ phân tích trade-off)
    result["objectives"] = compute_objectives(state, geom)

    return _finish(result, state, save_artifacts, analysis,
                   component_manifest=component_manifest)


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


def _finish(result: dict, state, save: bool, analysis: dict | None = None,
            component_manifest: dict | None = None) -> dict:
    if component_manifest is not None:
        result["component_audit"] = build_component_audit(
            state, result, component_manifest,
        )

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
