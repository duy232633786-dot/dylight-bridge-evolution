"""Hợp đồng dữ liệu giữa bộ não AI và phòng lab (BRD-053).

Ba đối tượng trong ``contracts/ai_proposal.schema.json``:

* ``ProposalRequest`` — những gì bộ não được nhìn: miền grammar đầy đủ, gene
  hiện tại, đánh giá đã tóm tắt, lịch sử (kể cả kết quả âm), thẻ tri thức có
  nhãn tin cậy, ngân sách và luật chơi.
* ``ProposalResponse`` — những gì bộ não được trả: danh sách ``changes`` + giả
  thuyết. ``additionalProperties=false`` nên mọi khóa phán quyết tự thêm
  (verdict/pass/feasible…) làm cả câu trả lời bị loại.
* ``ProposalSessionReport`` — lineage một phiên; mọi status/claim trong đó do
  ``design_study.assess_candidate`` cấp.

Module này KHÔNG gọi solver; nó chỉ kiểm hợp đồng, áp thay đổi trong miền và
tóm tắt đánh giá thành phản hồi có cấu trúc.
"""
from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path

from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACTS_DIR = REPO_ROOT / "contracts"
SCHEMA_PATH = CONTRACTS_DIR / "ai_proposal.schema.json"
BASIS_PATH = REPO_ROOT / "docs" / "design_basis" / "ai_proposer_basis.json"
SCHEMA_VERSION = "1.0"

#: Những khóa mang nghĩa phán quyết mà bộ não KHÔNG được phát. Schema đã chặn
#: bằng additionalProperties=false; danh sách này chỉ để báo lỗi dễ hiểu hơn.
FORBIDDEN_VERDICT_KEYS = frozenset({
    "verdict", "pass", "passed", "fail", "failed", "feasible", "ok", "approved",
    "claim_level", "status", "utilization", "capacity", "phiMn_kNm", "phiVn_kN",
})


class ProposerError(ValueError):
    """Lỗi hợp đồng/cấu hình của lớp đề xuất (không phải lỗi vật lý)."""


# --------------------------------------------------------------------------- hash
def canonical_json(value: object) -> str:
    """JSON chuẩn hoá (sort_keys, không khoảng trắng, cấm NaN) để băm tái lập."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_json(value: object) -> str:
    return sha256_text(canonical_json(value))


def sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# --------------------------------------------------------------------------- schema/basis
@lru_cache(maxsize=1)
def load_schema() -> dict:
    with open(SCHEMA_PATH, encoding="utf-8") as stream:
        schema = json.load(stream)
    Draft202012Validator.check_schema(schema)
    return schema


@lru_cache(maxsize=1)
def load_basis() -> dict:
    with open(BASIS_PATH, encoding="utf-8") as stream:
        basis = json.load(stream)
    required = ("basis_id", "authority", "context_policy", "termination", "adapters",
                "heuristic_policy", "prompt", "safety_invariants")
    missing = [key for key in required if key not in basis]
    if missing:
        raise ProposerError(f"ai_proposer_basis.json thiếu khoá {missing}")
    return basis


def _validator_for(definition: str) -> Draft202012Validator:
    schema = load_schema()
    # Schema con riêng: chỉ $defs + $ref, để root (session report) không can thiệp.
    sub = {"$schema": schema["$schema"], "$defs": schema["$defs"],
           "$ref": f"#/$defs/{definition}"}
    return Draft202012Validator(sub)


def _errors(definition: str, instance: object) -> list[str]:
    errors = sorted(_validator_for(definition).iter_errors(instance), key=lambda e: list(e.path))
    out = []
    for error in errors[:20]:
        where = "/".join(str(p) for p in error.path) or "<root>"
        out.append(f"{where}: {error.message}")
    return out


def validate_request(request: object) -> list[str]:
    return _errors("ProposalRequest", request)


def validate_response(response: object, expected_request_id: str | None = None) -> list[str]:
    """Kiểm ProposalResponse; thêm thông báo dễ hiểu khi bộ não phát khoá phán quyết."""
    errors = _errors("ProposalResponse", response)
    if isinstance(response, dict):
        leaked = sorted(FORBIDDEN_VERDICT_KEYS & set(response))
        for proposal in response.get("proposals", []) if isinstance(response.get("proposals"), list) else []:
            if isinstance(proposal, dict):
                leaked += sorted(FORBIDDEN_VERDICT_KEYS & set(proposal))
        if leaked:
            errors.insert(0, "bộ não tự phát khoá phán quyết bị cấm: " + ", ".join(dict.fromkeys(leaked)))
        if expected_request_id is not None and response.get("request_id") != expected_request_id:
            errors.insert(0, "request_id không khớp request đã gửi")
    return errors


def validate_report(report: object) -> list[str]:
    return _errors("ProposalSessionReport", report)


# --------------------------------------------------------------------------- domain
def _domain_kind(domain: list) -> str:
    if domain and all(isinstance(v, int) and not isinstance(v, bool) for v in domain):
        return "int"
    if domain and all(isinstance(v, str) for v in domain):
        return "str"
    raise ProposerError("Miền grammar phải thuần số nguyên hoặc thuần chuỗi")


def check_value(name: str, value: object, domain: list) -> str | None:
    """Trả None nếu ``value`` nằm đúng miền với đúng kiểu; ngược lại trả lý do."""
    kind = _domain_kind(domain)
    if isinstance(value, bool):
        return f"{name}: bool không phải giá trị grammar"
    if kind == "int":
        if not isinstance(value, int):
            return f"{name}: cần số nguyên trong miền, nhận {type(value).__name__} {value!r}"
    elif not isinstance(value, str):
        return f"{name}: cần chuỗi catalog trong miền, nhận {type(value).__name__} {value!r}"
    if value not in domain:
        return f"{name}: {value!r} ngoài miền grammar ({len(domain)} giá trị)"
    return None


def gene_in_domain(gene: dict, domains: dict) -> list[str]:
    """Danh sách lỗi nếu gene thiếu biến, thừa biến hoặc có giá trị ngoài miền."""
    if not isinstance(gene, dict):
        return ["gene phải là dict"]
    errors = [f"thiếu biến {name}" for name in domains if name not in gene]
    errors += [f"biến lạ {name}" for name in gene if name not in domains]
    for name, domain in domains.items():
        if name in gene:
            problem = check_value(name, gene[name], domain)
            if problem:
                errors.append(problem)
    return errors


def apply_changes(base_gene: dict, changes: object, domains: dict) -> tuple[dict | None, list[str]]:
    """Áp ``changes`` lên ``base_gene``; chỉ chấp nhận biến có trong miền, đúng kiểu, đúng giá trị.

    Trả ``(gene_mới, [])`` khi hợp lệ, ``(None, [lý do…])`` khi không. Không ném
    lỗi cho input xấu của bộ não — đó là kết quả cần ghi, không phải sự cố.
    """
    if not isinstance(changes, dict) or not changes:
        return None, ["changes phải là dict không rỗng"]
    errors: list[str] = []
    for name, value in changes.items():
        if name not in domains:
            errors.append(f"{name}: không phải biến của grammar")
            continue
        problem = check_value(name, value, domains[name])
        if problem:
            errors.append(problem)
    if errors:
        return None, errors
    gene = dict(base_gene)
    gene.update(changes)
    if gene == base_gene:
        return None, ["changes không đổi gene hiện tại"]
    return gene, []


# --------------------------------------------------------------------------- summaries
def _finding(item: dict) -> dict:
    code = item.get("code") or item.get("rule_id") or "UNKNOWN"
    margin = item.get("margin")
    return {
        "code": str(code),
        "severity": str(item.get("severity", "HARD")),
        "message": str(item.get("message", ""))[:400],
        "margin": float(margin) if isinstance(margin, (int, float)) and not isinstance(margin, bool) else None,
    }


def _clean_number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if value != value or value in (float("inf"), float("-inf")):
        return None
    return float(value)


FEEDBACK_AUTHORITY = ("evaluate_candidate BUILTIN_L1 + INDEPENDENT_VERIFIER — phản hồi vật lý "
                      "(violations/utilization/objectives) cho bộ não, KHÔNG phải claim")
#: Mã blocker của cổng claim không liên quan tới gene (site, bằng chứng miền, contract)
#: — không dùng để truy vấn thẻ tri thức sửa gene.
NON_GENE_CODE_PREFIXES = ("SITE-", "APP-", "EVALUATOR-", "SCHEMA-", "AUTHORITY-")


def summarize_assessment(assessment: dict, objective_key: str, *, feedback: dict | None = None,
                         max_blockers: int = 12, max_advisories: int = 8) -> dict:
    """Rút gọn thành phản hồi có cấu trúc cho bộ não — hai tầng tách bạch.

    * Tầng CLAIM: ``status``/``claim_level``/``blockers`` nguyên văn từ
      ``assess_candidate`` (cổng applicability + site + evidence). Hôm nay cổng này
      chặn L1 của Super-T bằng APP-EVIDENCE-001/SITE-001, nên claim vẫn IDEA.
    * Tầng PHẢN HỒI: ``feedback_status``/``verifier_feasible``/``feedback_violations``/
      ``responses``/``objectives`` từ ``evaluate_candidate`` (BUILTIN_L1 + verifier) —
      là cái bộ não cần để học, nhưng không phải claim. ``feedback`` được ưu tiên
      nếu caller truyền; nếu không, dùng ``assessment["evaluation"]`` khi có.
    ``objective_value`` = None khi mức nghiên cứu không có objective (L0) hoặc
    evaluator không chạy.
    """
    evaluation = feedback if isinstance(feedback, dict) else (
        assessment.get("evaluation") if isinstance(assessment, dict) else None)
    responses: dict = {}
    objectives: dict = {}
    if isinstance(evaluation, dict):
        for key, value in (evaluation.get("responses") or {}).items():
            number = _clean_number(value)
            responses[str(key)] = number if number is not None else (value if isinstance(value, str) else None)
        for key, value in (evaluation.get("objectives") or {}).items():
            objectives[str(key)] = _clean_number(value)
    blockers = [_finding(b) for b in (assessment.get("blockers") or []) if isinstance(b, dict)]
    advisories = [_finding(a) for a in (assessment.get("advisories") or []) if isinstance(a, dict)]
    feedback_violations = [_finding(v) for v in ((evaluation or {}).get("violations") or [])
                           if isinstance(v, dict)] if isinstance(evaluation, dict) else []
    claim = assessment.get("claim_level") if assessment.get("claim_level") in ("IDEA", "SCREENED") else "IDEA"
    summary = {
        "status": str(assessment.get("status", "UNKNOWN")),
        "claim_level": claim,
        "study_level": assessment.get("study_level", "L1_STRUCTURAL"),
        "blockers": blockers[:max_blockers],
        "advisories": advisories[:max_advisories],
        "feedback_status": str(evaluation.get("status")) if isinstance(evaluation, dict) else None,
        "verifier_feasible": (evaluation.get("feasible") is True) if isinstance(evaluation, dict) else None,
        "feedback_violations": feedback_violations[:max_blockers],
        "feedback_authority": FEEDBACK_AUTHORITY if isinstance(evaluation, dict) else "NONE_AT_THIS_STUDY_LEVEL",
        "responses": responses,
        "objectives": objectives,
        "objective_value": objectives.get(objective_key),
        "max_utilization": responses.get("max_utilization") if isinstance(responses.get("max_utilization"), float) else None,
        "case_id": assessment.get("case_id"),
    }
    return summary


def failed_rule_ids(summary: dict) -> list[str]:
    """Mã rule liên quan tới gene (ưu tiên verifier), bỏ mã cổng claim không liên quan gene."""
    codes = [v["code"] for v in summary.get("feedback_violations", [])]
    codes += [b["code"] for b in summary.get("blockers", [])
              if not b["code"].startswith(NON_GENE_CODE_PREFIXES)]
    return list(dict.fromkeys(codes))


# --------------------------------------------------------------------------- request
def design_space_from_domains(grammar: dict, domains: dict) -> dict:
    space = {}
    for name, domain in domains.items():
        spec = grammar["design_variables"][name]
        space[name] = {"type": spec["type"], "domain": list(domain)}
    return space


def build_request(*, session_id: str, round_index: int, mode: str, family: str,
                  grammar: dict, domains: dict, study_level: str, objective_key: str,
                  direction: str, objective_available: bool, current_gene: dict,
                  current_summary: dict, history: list[dict], cards: list[dict],
                  rounds_remaining: int, evaluations_remaining: int,
                  max_proposals: int) -> dict:
    """Dựng ProposalRequest; ``request_id`` là SHA-256 của nội dung (trừ chính nó)."""
    basis = load_basis()
    body = {
        "schema_version": SCHEMA_VERSION,
        "session_id": session_id,
        "round": round_index,
        "mode": mode,
        "family": family,
        "grammar_version": str(grammar.get("grammar_version", "n/a")),
        "study_level": study_level,
        "objective": {"key": objective_key, "direction": direction,
                      "available_at_study_level": objective_available},
        "design_space": design_space_from_domains(grammar, domains),
        "current_gene": dict(current_gene),
        "current_assessment": current_summary,
        "history": history,
        "knowledge_cards": cards,
        "budget": {"rounds_remaining": rounds_remaining,
                   "evaluations_remaining": evaluations_remaining,
                   "max_proposals_this_round": max_proposals},
        "rules_for_the_proposer": list(basis["safety_invariants"]),
        "response_format": {
            "schema": "contracts/ai_proposal.schema.json#/$defs/ProposalResponse",
            "example": {
                "schema_version": SCHEMA_VERSION,
                "request_id": "<chép lại request_id>",
                "proposals": [{
                    "changes": {"<biến grammar>": "<giá trị trong domain>"},
                    "hypothesis": "rule nào sẽ cải thiện và vì sao",
                    "expected_effects": [{"rule_id": "SERV-001", "direction": "decrease"}],
                    "cites": ["KC-001"],
                    "confidence": 0.5,
                }],
                "notes": "tuỳ chọn",
            },
            "forbidden": "mọi khoá ngoài schema, đặc biệt verdict/pass/fail/feasible",
        },
    }
    request_id = sha256_json(body)
    return {"request_id": request_id, **body}


def source_digests() -> list[dict]:
    here = Path(__file__).resolve().parent
    paths = [
        ("bridge_evolution/proposer/contract.py", here / "contract.py"),
        ("bridge_evolution/proposer/adapters.py", here / "adapters.py"),
        ("bridge_evolution/proposer/loop.py", here / "loop.py"),
        ("contracts/ai_proposal.schema.json", SCHEMA_PATH),
        ("docs/design_basis/ai_proposer_basis.json", BASIS_PATH),
    ]
    return [{"path": rel, "sha256": sha256_file(path)} for rel, path in paths if path.is_file()]
