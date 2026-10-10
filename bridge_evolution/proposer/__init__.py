"""Lớp đề xuất AI có hợp đồng (BRD-053).

Bộ não AI (LLM local qua HTTP, vendor CLI, hoặc heuristic đối chứng) chỉ được
ĐỀ XUẤT thay đổi gene trong miền grammar. Mọi phán quyết khả thi/claim đều do
``design_study.assess_candidate`` cấp; lớp này ghi lineage có hash và
pre-registration khóa trước vòng 1.
"""
from .contract import (
    ProposerError,
    apply_changes,
    build_request,
    canonical_json,
    gene_in_domain,
    load_basis,
    load_schema,
    sha256_json,
    summarize_assessment,
    validate_report,
    validate_request,
    validate_response,
)
from .adapters import (
    AdapterResult,
    HeuristicProposer,
    OpenAICompatibleProposer,
    VendorCLIProposer,
    make_adapter,
)
from .loop import run_proposal_session, seed_gene_for_family

__all__ = [
    "AdapterResult",
    "HeuristicProposer",
    "OpenAICompatibleProposer",
    "ProposerError",
    "VendorCLIProposer",
    "apply_changes",
    "build_request",
    "canonical_json",
    "gene_in_domain",
    "load_basis",
    "load_schema",
    "make_adapter",
    "run_proposal_session",
    "seed_gene_for_family",
    "sha256_json",
    "summarize_assessment",
    "validate_report",
    "validate_request",
    "validate_response",
]
