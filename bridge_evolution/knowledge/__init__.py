"""Não thứ 2 — lớp tri thức kỹ thuật dạng thẻ có cấu trúc.

Thẻ tri thức chỉ GỢI Ý — PASS/FAIL luôn thuộc verifier; mọi con số trong thẻ
phải đối chiếu catalogs/ruleset trước khi dùng.
"""
from .store import load_cards, query_knowledge, validate_card
from .obsidian import (discover_obsidian_vaults, export_obsidian_vault,
                       load_card_audit, resolve_obsidian_vault)
from .reference_docs import import_tcvn_collection
from .local_library import import_local_library, plan_import
from .notebooklm import import_notebooklm_snapshot, load_notebooklm_snapshot
from .notebooklm_sync import (
    enqueue_codex_message, export_sync_dashboard, ingest_notebooklm_capture,
    load_messages as load_notebooklm_sync_messages, sync_status as notebooklm_sync_status,
    update_message_status as update_notebooklm_sync_status,
)
from .theme import configure_obsidian_colors

__all__ = [
    "discover_obsidian_vaults",
    "configure_obsidian_colors",
    "export_obsidian_vault",
    "import_local_library",
    "import_tcvn_collection",
    "import_notebooklm_snapshot",
    "load_card_audit",
    "load_cards",
    "load_notebooklm_snapshot",
    "enqueue_codex_message",
    "export_sync_dashboard",
    "ingest_notebooklm_capture",
    "load_notebooklm_sync_messages",
    "notebooklm_sync_status",
    "update_notebooklm_sync_status",
    "plan_import",
    "query_knowledge",
    "resolve_obsidian_vault",
    "validate_card",
]
