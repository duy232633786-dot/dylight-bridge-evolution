"""Cấu hình màu Brain 2 cho Obsidian CSS snippet và Graph View."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .obsidian import _atomic_write, resolve_obsidian_vault

SNIPPET_NAME = "dylight-brain2"
SNIPPET_FILE = f"{SNIPPET_NAME}.css"
THEME_MANIFEST = ".dylight-brain2-theme.json"

CSS = """/* DYLIGHT Brain 2 - managed by bridge_evolution. */
.dylight-note {
  --dylight-accent: #8b5cf6;
  --dylight-accent-soft: color-mix(in srgb, var(--dylight-accent) 14%, transparent);
}
.dylight-standard { --dylight-accent: #3b82f6; }
.dylight-rule { --dylight-accent: #8b5cf6; }
.dylight-variable { --dylight-accent: #14b8a6; }
.dylight-notebooklm { --dylight-accent: #06b6d4; }
.dylight-research { --dylight-accent: #6366f1; }
.dylight-dashboard { --dylight-accent: #8b5cf6; }
.dylight-claim-idea { --dylight-accent: #94a3b8; }
.dylight-claim-screened { --dylight-accent: #f59e0b; }
.dylight-claim-numerically_verified { --dylight-accent: #3b82f6; }
.dylight-claim-lab_validated { --dylight-accent: #8b5cf6; }
.dylight-claim-pilot_validated { --dylight-accent: #14b8a6; }
.dylight-claim-engineering_candidate { --dylight-accent: #22c55e; }
.dylight-review-reject { --dylight-accent: #ef4444; }
.dylight-review-revise { --dylight-accent: #f59e0b; }
.dylight-review-approve { --dylight-accent: #22c55e; }
.dylight-status-draft { --dylight-accent: #f59e0b; }
.dylight-status-engineer_approved { --dylight-accent: #22c55e; }
.dylight-status-rejected,
.dylight-risk-red { --dylight-accent: #ef4444; }
.dylight-risk-orange { --dylight-accent: #f59e0b; }
.dylight-risk-green { --dylight-accent: #22c55e; }

.markdown-preview-view.dylight-note .inline-title,
.markdown-source-view.dylight-note .inline-title {
  color: var(--dylight-accent);
}
.markdown-preview-view.dylight-note .metadata-container,
.markdown-source-view.dylight-note .metadata-container {
  border-left: 4px solid var(--dylight-accent);
  background: var(--dylight-accent-soft);
  border-radius: 8px;
  padding-left: 0.8rem;
}
.markdown-preview-view.dylight-note h2,
.markdown-source-view.dylight-note .HyperMD-header-2 {
  border-bottom: 1px solid var(--dylight-accent);
  padding-bottom: 0.2rem;
}
.dylight-chip {
  display: inline-block;
  color: #fff;
  border-radius: 999px;
  padding: 0.18rem 0.55rem;
  margin: 0.12rem 0.18rem 0.12rem 0;
  font-size: 0.82em;
  font-weight: 650;
}
.dylight-chip-red { background: #ef4444; }
.dylight-chip-orange { background: #f59e0b; color: #1f2937; }
.dylight-chip-green { background: #22c55e; }
.dylight-chip-blue { background: #3b82f6; }
.dylight-chip-purple { background: #8b5cf6; }
.dylight-chip-teal { background: #14b8a6; }

.internal-link[href*="/Standards/"] { color: #3b82f6; }
.internal-link[href*="/Rules/"] { color: #8b5cf6; }
.internal-link[href*="/Variables/"] { color: #14b8a6; }
.internal-link[href*="/NotebookLM/"] { color: #06b6d4; }
.internal-link[href*="/Research Lab/"] { color: #6366f1; }
"""

DYLIGHT_COLOR_GROUPS = [
    {"query": "tag:#dylight/risk/red", "color": {"a": 1, "rgb": 15680580}},
    {"query": "tag:#dylight/status/engineer_approved", "color": {"a": 1, "rgb": 2278750}},
    {"query": "tag:#dylight/risk/orange", "color": {"a": 1, "rgb": 16096779}},
    {"query": "tag:#dylight/status/draft", "color": {"a": 1, "rgb": 16096779}},
    {"query": "tag:#dylight/standard", "color": {"a": 1, "rgb": 3900150}},
    {"query": "tag:#dylight/notebooklm", "color": {"a": 1, "rgb": 440020}},
    {"query": "tag:#dylight/review/reject", "color": {"a": 1, "rgb": 15680580}},
    {"query": "tag:#dylight/review/revise OR tag:#dylight/claim/screened", "color": {"a": 1, "rgb": 16096779}},
    {"query": "tag:#dylight/claim/numerically_verified", "color": {"a": 1, "rgb": 3900150}},
    {"query": "tag:#dylight/claim/lab_validated", "color": {"a": 1, "rgb": 9133302}},
    {"query": "tag:#dylight/claim/pilot_validated", "color": {"a": 1, "rgb": 1357990}},
    {"query": "tag:#dylight/review/approve OR tag:#dylight/claim/engineering_candidate", "color": {"a": 1, "rgb": 2278750}},
    {"query": "tag:#dylight/research-task OR tag:#dylight/research-handoff", "color": {"a": 1, "rgb": 6514417}},
    {"query": "tag:#dylight/rule", "color": {"a": 1, "rgb": 9133302}},
    {"query": "tag:#dylight/variable", "color": {"a": 1, "rgb": 1357990}},
    {"query": "tag:#dylight/dashboard OR tag:#dylight/index", "color": {"a": 1, "rgb": 9133302}},
    {"query": "path:\"DYLIGHT Bridge Evolution/Standards\"", "color": {"a": 1, "rgb": 6583435}},
]


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_object(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cấu hình Obsidian không đọc được: {path.name}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"Cấu hình Obsidian phải là JSON object: {path.name}")
    return data


def _json_bytes(data: dict) -> bytes:
    return (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def configure_obsidian_colors(vault_dir: str | Path | None = None, *,
                              dry_run: bool = False) -> dict:
    """Bật CSS snippet và các color group DYLIGHT, giữ cấu hình khác của user."""
    vault = resolve_obsidian_vault(vault_dir)
    obsidian_dir = (vault / ".obsidian").resolve(strict=False)
    if not obsidian_dir.is_dir() or vault.resolve() not in obsidian_dir.parents:
        raise FileNotFoundError(f"Vault thiếu .obsidian: {vault}")
    if (obsidian_dir.is_symlink()
            or getattr(obsidian_dir, "is_junction", lambda: False)()):
        raise ValueError(".obsidian không được là symlink/junction")

    snippets_dir = obsidian_dir / "snippets"
    snippet_path = snippets_dir / SNIPPET_FILE
    manifest_path = snippets_dir / THEME_MANIFEST
    appearance_path = obsidian_dir / "appearance.json"
    graph_path = obsidian_dir / "graph.json"
    css_bytes = CSS.encode("utf-8")

    old_manifest = _read_object(manifest_path) if manifest_path.exists() else {}
    old_css_hash = old_manifest.get("css_sha256")
    current_css_hash = _sha256(snippet_path.read_bytes()) if snippet_path.is_file() else None
    desired_css_hash = _sha256(css_bytes)
    conflicts = []
    if (current_css_hash is not None and current_css_hash != desired_css_hash
            and current_css_hash != old_css_hash):
        conflicts.append(f"snippets/{SNIPPET_FILE}")

    appearance = _read_object(appearance_path)
    enabled = appearance.get("enabledCssSnippets", [])
    if enabled is None:
        enabled = []
    if not isinstance(enabled, list) or not all(isinstance(item, str) for item in enabled):
        raise ValueError("appearance.json có enabledCssSnippets sai kiểu")
    appearance["enabledCssSnippets"] = list(dict.fromkeys([*enabled, SNIPPET_NAME]))

    graph = _read_object(graph_path)
    existing_groups = graph.get("colorGroups", [])
    if not isinstance(existing_groups, list):
        raise ValueError("graph.json có colorGroups sai kiểu")
    preserved_groups = [
        group for group in existing_groups
        if not (isinstance(group, dict)
                and (str(group.get("query", "")).startswith("tag:#dylight/")
                     or str(group.get("query", "")).startswith(
                         'path:"DYLIGHT Bridge Evolution/Standards"')))
    ]
    graph.update({
        "showTags": True,
        "showAttachments": True,
        "hideUnresolved": False,
        "showOrphans": False,
        "collapse-color-groups": False,
        "colorGroups": [*DYLIGHT_COLOR_GROUPS, *preserved_groups],
    })

    desired = {
        f"snippets/{SNIPPET_FILE}": css_bytes,
        "appearance.json": _json_bytes(appearance),
        "graph.json": _json_bytes(graph),
    }
    current = {
        relative: (obsidian_dir / relative).read_bytes()
        if (obsidian_dir / relative).is_file() else None
        for relative in desired
    }
    semantic_json = {"appearance.json": appearance, "graph.json": graph}
    planned = []
    for relative, data in desired.items():
        path = obsidian_dir / relative
        if relative in semantic_json and path.is_file():
            # Obsidian có thể tự đổi CRLF/thứ tự key khi đóng/mở. Không rewrite
            # nếu object JSON vẫn đúng để tránh vòng lặp cấu hình giả.
            if _read_object(path) == semantic_json[relative]:
                continue
        if current[relative] != data:
            planned.append(relative)
    planned.sort()
    unchanged = sorted(set(desired) - set(planned))
    written = []
    manifest_changed = old_css_hash != desired_css_hash
    if not conflicts and not dry_run:
        for relative in planned:
            _atomic_write(obsidian_dir / relative, desired[relative])
            written.append(relative)
        manifest = {"schema_version": 1, "css_sha256": desired_css_hash}
        manifest_bytes = _json_bytes(manifest)
        manifest_changed = (not manifest_path.is_file()
                            or manifest_path.read_bytes() != manifest_bytes)
        if manifest_changed:
            _atomic_write(manifest_path, manifest_bytes)

    return {
        "vault": str(vault),
        "snippet": SNIPPET_NAME,
        "color_groups": len(DYLIGHT_COLOR_GROUPS),
        "planned_writes": planned,
        "written": written,
        "unchanged": unchanged,
        "conflicts": conflicts,
        "manifest_changed": manifest_changed,
        "dry_run": dry_run,
    }


__all__ = ["configure_obsidian_colors"]
