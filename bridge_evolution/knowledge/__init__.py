"""Não thứ 2 — lớp tri thức kỹ thuật dạng thẻ có cấu trúc.

Thẻ tri thức chỉ GỢI Ý — PASS/FAIL luôn thuộc verifier; mọi con số trong thẻ
phải đối chiếu catalogs/ruleset trước khi dùng.
"""
from .store import load_cards, query_knowledge, validate_card
from .obsidian import (discover_obsidian_vaults, export_obsidian_vault,
                       load_card_audit, resolve_obsidian_vault)
from .reference_docs import import_tcvn_collection
from .notebooklm import import_notebooklm_snapshot, load_notebooklm_snapshot
from .theme import configure_obsidian_colors

__all__ = [
    "discover_obsidian_vaults",
    "configure_obsidian_colors",
    "export_obsidian_vault",
    "import_tcvn_collection",
    "import_notebooklm_snapshot",
    "load_card_audit",
    "load_cards",
    "load_notebooklm_snapshot",
    "query_knowledge",
    "resolve_obsidian_vault",
    "validate_card",
]
