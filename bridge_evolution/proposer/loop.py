"""Vòng lặp đề xuất–đánh giá có pre-registration và lineage (BRD-053).

    seed ─► assess ─► [request → bộ não → changes] ─► apply trong miền ─► assess ─► ghi
                                  ▲                                            │
                                  └──────────── phản hồi có cấu trúc ◄─────────┘

Hai tầng authority, tách bạch trong mọi bản ghi:

* **Claim** — duy nhất từ ``design_study.assess_candidate`` (schema → L0 →
  applicability registry neo hash → site/evidence → BUILTIN_L1 → verifier).
  Hôm nay cổng này chặn L1 cho Super-T bằng ``APP-EVIDENCE-001`` (miền số mới
  PARTIAL) và ``SITE-001`` (chưa có hồ sơ site, G0) nên claim vẫn IDEA; lớp này
  không nới, không giả lập site.
* **Phản hồi vật lý** — từ ``evaluate_candidate`` (BUILTIN_L1 + INDEPENDENT
  VERIFIER): violations, utilization, objectives — cùng đường mà design_loop,
  rl_env và surrogate đang dùng. Đây là cái bộ não học từ, không phải claim.

``study_level`` chọn theo registry: họ chỉ cho L0_GEOMETRY (dầm hộp) thì không
bao giờ gọi evaluate_candidate; objective báo không có. Pre-registration khóa +
băm trước vòng 1; kết quả âm được giữ; báo cáo hợp lệ theo
``ProposalSessionReport`` và tái lập với adapter tất định.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone

from ..catalogs import all_domains, load_grammar
from ..design_study import assess_candidate, load_applicability_registry
from ..knowledge.store import load_cards, query_knowledge
from ..state import state_from_gene
from .contract import (
    FEEDBACK_AUTHORITY,
    ProposerError,
    SCHEMA_VERSION,
    apply_changes,
    build_request,
    failed_rule_ids,
    gene_in_domain,
    load_basis,
    sha256_json,
    source_digests,
    summarize_assessment,
    validate_report,
)

STUDY_L1 = "L1_STRUCTURAL"
STUDY_L0 = "L0_GEOMETRY"
CLAIM_CEILING = "SCREENED"
VERDICT_AUTHORITY = ("claim: design_study.assess_candidate (schema → L0 → applicability registry "
                     "→ site/evidence → BUILTIN_L1 → INDEPENDENT_VERIFIER); lớp đề xuất không có quyền")


def _registry() -> dict:
    registry = load_applicability_registry()
    if isinstance(registry, tuple):  # phòng khi API trả (registry, digest)
        registry = registry[0]
    return registry


def seed_gene_for_family(family: str) -> dict:
    """Gene neo của họ trong registry model_applicability (điểm xuất phát tái lập)."""
    spec = _registry().get("families", {}).get(family)
    if not spec or "anchor_gene" not in spec:
        raise ProposerError(f"Registry không có anchor_gene cho họ {family}")
    return dict(spec["anchor_gene"])


def study_level_for_family(family: str) -> str:
    spec = _registry().get("families", {}).get(family)
    if not spec:
        raise ProposerError(f"Registry model_applicability không có họ {family}")
    levels = spec.get("allowed_study_levels", [])
    return STUDY_L1 if STUDY_L1 in levels else STUDY_L0


def _assess(gene: dict, family: str, study_level: str, site_profile: dict | None) -> tuple[dict, dict | None]:
    """(assessment của cổng claim, feedback vật lý L1 hoặc None).

    Ở L1: nếu cổng claim đã chạy evaluator thì dùng lại; nếu cổng BLOCKED trước
    khi tới solver (site/evidence) thì gọi evaluate_candidate riêng để bộ não vẫn
    có phản hồi vật lý. Ở L0 không bao giờ gọi evaluate_candidate.
    """
    state = state_from_gene(gene, family)
    assessment = assess_candidate(state, study_level=study_level, site_profile=site_profile)
    feedback = None
    if study_level == STUDY_L1:
        feedback = assessment.get("evaluation")
        if feedback is None and assessment.get("status") == "BLOCKED":
            from ..evaluate import evaluate_candidate

            feedback = evaluate_candidate(state)
    return assessment, feedback


def _positive(summary: dict, objective_available: bool) -> bool:
    """'Kết quả dương' của một lượt: L1 = verifier khả thi; L0 = qua sàng L0."""
    if objective_available:
        return summary.get("verifier_feasible") is True
    return summary.get("status") == "L0_SCREENED"


def _card_briefs(summary: dict, gene: dict, family: str, cards: list[dict], top_k: int,
                 include_draft: bool, guidance_chars: int) -> list[dict]:
    hits = query_knowledge(failed_rules=failed_rule_ids(summary), variables=list(gene),
                           family=family, include_draft=include_draft, top_k=top_k, cards=cards)
    briefs = []
    for hit in hits:
        card = hit["card"]
        briefs.append({
            "card_id": card["card_id"], "title": card["title"],
            "guidance": card["guidance"][:guidance_chars], "status": card["status"],
            "applies_to": card["applies_to"], "score": float(hit["score"]),
            "trust": "UNVERIFIED_REFERENCE_ONLY",
        })
    return briefs


def _improvement(seed_value: float | None, value: float | None, direction: str) -> float | None:
    if seed_value is None or value is None or seed_value == 0:
        return None
    delta = (seed_value - value) if direction == "min" else (value - seed_value)
    return delta / abs(seed_value)


def _better(candidate: float | None, incumbent: float | None, direction: str) -> bool:
    if candidate is None:
        return False
    if incumbent is None:
        return True
    return candidate < incumbent if direction == "min" else candidate > incumbent


def _history_entry(round_index: int, changes: dict, summary: dict | None) -> dict:
    if summary is None:
        return {"round": round_index, "changes": changes, "in_domain": False, "status": "OUT_OF_DOMAIN",
                "claim_level": None, "verifier_feasible": None, "objective_value": None,
                "max_utilization": None, "blocker_codes": []}
    codes = [v["code"] for v in summary["feedback_violations"]] or [b["code"] for b in summary["blockers"]]
    return {"round": round_index, "changes": changes, "in_domain": True, "status": summary["status"],
            "claim_level": summary["claim_level"], "verifier_feasible": summary["verifier_feasible"],
            "objective_value": summary["objective_value"], "max_utilization": summary["max_utilization"],
            "blocker_codes": codes[:6]}


def run_proposal_session(seed_gene: dict, *, family: str, adapter, objective_key: str = "relative_cost",
                         direction: str = "min", rounds: int | None = None,
                         max_evaluations: int | None = None, proposals_per_round: int | None = None,
                         improvement_min_rel: float | None = None, seed: int = 0,
                         site_profile: dict | None = None, question: str | None = None) -> dict:
    """Chạy một phiên đề xuất và trả ``ProposalSessionReport`` đã validate."""
    basis = load_basis()
    term = basis["termination"]
    ctx = basis["context_policy"]
    rounds = int(term["default_rounds"] if rounds is None else rounds)
    max_evaluations = int(term["default_max_evaluations"] if max_evaluations is None else max_evaluations)
    proposals_per_round = int(term["default_proposals_per_round"] if proposals_per_round is None
                              else proposals_per_round)
    improvement_min_rel = float(term["default_improvement_min_rel"] if improvement_min_rel is None
                                else improvement_min_rel)
    if direction not in ("min", "max"):
        raise ProposerError("direction phải là 'min' hoặc 'max'")
    if not 1 <= rounds <= 50 or not 1 <= max_evaluations <= 500 or not 1 <= proposals_per_round <= 8:
        raise ProposerError("Ngân sách ngoài giới hạn: rounds 1–50, evaluations 1–500, proposals/round 1–8")
    if not hasattr(adapter, "propose") or not hasattr(adapter, "describe"):
        raise ProposerError("adapter phải có propose() và describe()")

    grammar = load_grammar(family)
    domains = all_domains(grammar)
    seed_errors = gene_in_domain(seed_gene, domains)
    if seed_errors:
        raise ProposerError("seed_gene ngoài miền grammar: " + "; ".join(seed_errors[:5]))
    study_level = study_level_for_family(family)
    objective_available = study_level == STUDY_L1
    summary_kw = {"max_blockers": int(ctx["max_blockers_in_summary"]),
                  "max_advisories": int(ctx["max_advisories_in_summary"])}

    seed_assessment, seed_feedback = _assess(seed_gene, family, study_level, site_profile)
    seed_summary = summarize_assessment(seed_assessment, objective_key, feedback=seed_feedback, **summary_kw)
    seed_sha = sha256_json(seed_gene)
    seed_positive = _positive(seed_summary, objective_available)
    adapter_meta = adapter.describe()
    session_id = sha256_json({"family": family, "seed_gene": seed_gene, "adapter": adapter_meta["adapter_id"],
                              "seed": seed, "rounds": rounds, "max_evaluations": max_evaluations,
                              "objective": objective_key, "direction": direction,
                              "improvement_min_rel": improvement_min_rel})[:16]
    prereg_t = basis["preregistration"]
    fmt = {"objective_key": objective_key, "improvement_min_rel": improvement_min_rel,
           "direction": direction, "budget_evaluations": max_evaluations, "budget_rounds": rounds}
    if not objective_available:
        success_template = prereg_t["success_criterion_template_l0_only"]
    elif seed_positive:
        success_template = prereg_t["success_criterion_template_feasible_seed"]
    else:
        success_template = prereg_t["success_criterion_template_infeasible_seed"]
    preregistration = {
        "question": question or (
            f"Bộ não {adapter_meta['adapter_id']} có đề xuất được thay đổi gene họ {family} "
            f"({study_level}) để "
            f"{('cải thiện ' + objective_key + ' mà vẫn verifier-khả thi') if seed_positive and objective_available else ('đưa seed đang ' + seed_summary['status'] + '/verifier ' + str(seed_summary['verifier_feasible']) + ' về khả thi')} "
            f"trong ngân sách {rounds} vòng / {max_evaluations} lượt đánh giá hay không?"),
        "family": family, "objective_key": objective_key, "direction": direction,
        "budget_rounds": rounds, "budget_evaluations": max_evaluations,
        "proposals_per_round": proposals_per_round, "improvement_min_rel": improvement_min_rel,
        "success_criterion": success_template.format(**fmt),
        "falsification_criterion": prereg_t["falsification_criterion_template"].format(**fmt),
        "claim_gate_note": prereg_t["claim_gate_note"],
        "seed": int(seed), "adapter_id": adapter_meta["adapter_id"], "seed_gene_sha256": seed_sha,
        "seed_status": seed_summary["status"], "seed_verifier_feasible": seed_summary["verifier_feasible"],
        "locked_before_round_1": True,
    }
    preregistration_sha = sha256_json(preregistration)

    cards = load_cards()
    assessed: dict[str, dict] = {seed_sha: seed_summary}
    history: list[dict] = []
    rounds_out: list[dict] = []
    best = None
    if seed_positive and objective_available:
        best = {"gene": dict(seed_gene), "gene_sha256": seed_sha, "status": seed_summary["status"],
                "claim_level": seed_summary["claim_level"], "verifier_feasible": True,
                "objective_value": seed_summary["objective_value"], "improvement_rel": 0.0, "found_in_round": 0}
    evaluations_used = 0
    negative = duplicates = out_of_domain = 0
    consecutive_failures = 0
    termination = "BUDGET_ROUNDS_EXHAUSTED"
    success = False

    for round_index in range(1, rounds + 1):
        started = time.perf_counter()
        base_gene = best["gene"] if best else dict(seed_gene)
        base_summary = assessed[sha256_json(base_gene)]
        if not objective_available:
            mode = "EXPLORE_L0"
        elif _positive(base_summary, True):
            mode = "TRIM"
        else:
            mode = "REPAIR"
        briefs = _card_briefs(base_summary, base_gene, family, cards, int(ctx["top_k_cards"]),
                              bool(ctx["include_draft_cards"]), int(ctx["guidance_max_chars"]))
        request = build_request(
            session_id=session_id, round_index=round_index, mode=mode, family=family, grammar=grammar,
            domains=domains, study_level=study_level, objective_key=objective_key, direction=direction,
            objective_available=objective_available, current_gene=base_gene, current_summary=base_summary,
            history=history[-int(ctx["history_window"]):], cards=briefs,
            rounds_remaining=rounds - round_index, evaluations_remaining=max_evaluations - evaluations_used,
            max_proposals=proposals_per_round)
        result = adapter.propose(request)
        record = {
            "round": round_index, "mode": mode, "base_gene_sha256": sha256_json(base_gene),
            "request_sha256": request["request_id"], "adapter_status": result.status,
            "adapter_error": result.error, "response_sha256": result.raw_sha256,
            "raw_excerpt": result.raw_excerpt, "proposals": [], "elapsed_s": 0.0,
        }
        if result.status != "OK":
            consecutive_failures += 1
            record["elapsed_s"] = round(time.perf_counter() - started, 6)
            rounds_out.append(record)
            if consecutive_failures >= int(term["adapter_failure_stop_after"]):
                termination = "ADAPTER_FAILED_REPEATEDLY"
                break
            continue
        consecutive_failures = 0
        budget_hit = False
        for index, proposal in enumerate(result.response["proposals"][:proposals_per_round]):
            changes = proposal["changes"]
            item = {
                "index": index, "changes": changes, "hypothesis": proposal["hypothesis"],
                "expected_effects": proposal.get("expected_effects", []), "cites": proposal.get("cites", []),
                "in_domain": False, "domain_errors": [], "outcome": "OUT_OF_DOMAIN", "gene": None,
                "gene_sha256": None, "assessment": None, "assessment_sha256": None, "improved": False,
            }
            gene, errors = apply_changes(base_gene, changes, domains)
            if gene is None:
                item["domain_errors"] = errors
                out_of_domain += 1
                history.append(_history_entry(round_index, changes, None))
                record["proposals"].append(item)
                continue
            item["in_domain"] = True
            gene_sha = sha256_json(gene)
            item["gene"], item["gene_sha256"] = gene, gene_sha
            if gene_sha in assessed:
                summary = assessed[gene_sha]
                item["outcome"] = "DUPLICATE"
                duplicates += 1
            elif evaluations_used >= max_evaluations:
                item["outcome"] = "BUDGET_EXHAUSTED"
                record["proposals"].append(item)
                budget_hit = True
                break
            else:
                assessment, feedback = _assess(gene, family, study_level, site_profile)
                summary = summarize_assessment(assessment, objective_key, feedback=feedback, **summary_kw)
                assessed[gene_sha] = summary
                evaluations_used += 1
                item["outcome"] = "ASSESSED"
                if not _positive(summary, objective_available):
                    negative += 1
            item["assessment"] = summary
            item["assessment_sha256"] = sha256_json(summary)
            history.append(_history_entry(round_index, changes, summary))
            if item["outcome"] == "ASSESSED" and _positive(summary, objective_available):
                if objective_available:
                    incumbent = best["objective_value"] if best else None
                    if best is None or _better(summary["objective_value"], incumbent, direction):
                        item["improved"] = True
                        best = {"gene": gene, "gene_sha256": gene_sha, "status": summary["status"],
                                "claim_level": summary["claim_level"], "verifier_feasible": True,
                                "objective_value": summary["objective_value"],
                                "improvement_rel": _improvement(seed_summary["objective_value"],
                                                                summary["objective_value"], direction),
                                "found_in_round": round_index}
                    if seed_positive:
                        imp = _improvement(seed_summary["objective_value"], summary["objective_value"], direction)
                        success = success or (imp is not None and imp >= improvement_min_rel)
                    else:
                        success = True
                elif not seed_positive:
                    # L0: seed chưa qua sàng, một đề xuất qua sàng L0 là kết quả dương duy nhất đo được.
                    item["improved"] = True
                    success = True
            record["proposals"].append(item)
        record["elapsed_s"] = round(time.perf_counter() - started, 6)
        rounds_out.append(record)
        if success:
            termination = "SUCCESS_CRITERION_MET"
            break
        if budget_hit or evaluations_used >= max_evaluations:
            termination = "BUDGET_EVALUATIONS_EXHAUSTED"
            break
        if not record["proposals"]:
            termination = "NO_NEW_PROPOSALS"
            break

    if success:
        hypothesis_supported: bool | None = True
    elif not objective_available and seed_positive:
        hypothesis_supported = None  # L0 không có objective: không có gì để 'cải thiện' đo được
    else:
        hypothesis_supported = False

    report = {
        "schema_version": SCHEMA_VERSION, "basis_id": basis["basis_id"], "session_id": session_id,
        "created_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "family": family, "grammar_version": str(grammar.get("grammar_version", "n/a")),
        "study_level": study_level, "objective_available": objective_available,
        "claim_ceiling": CLAIM_CEILING, "verdict_authority": VERDICT_AUTHORITY,
        "feedback_authority": FEEDBACK_AUTHORITY if objective_available else "NONE_AT_THIS_STUDY_LEVEL",
        "proposer_authority": "NONE",
        "adapter": adapter_meta, "preregistration": preregistration,
        "preregistration_sha256": preregistration_sha, "seed_gene": dict(seed_gene),
        "seed_assessment": seed_summary, "rounds": rounds_out, "best": best,
        "evaluations_used": evaluations_used, "assessed_count": len(assessed) - 1,
        "negative_results": negative, "duplicates": duplicates, "out_of_domain": out_of_domain,
        "termination_reason": termination, "hypothesis_supported": hypothesis_supported,
        "registry_sha256": seed_assessment.get("registry_sha256"), "source_digests": source_digests(),
    }
    errors = validate_report(report)
    if errors:
        raise ProposerError("Báo cáo phiên không hợp lệ theo schema: " + "; ".join(errors[:5]))
    return report
