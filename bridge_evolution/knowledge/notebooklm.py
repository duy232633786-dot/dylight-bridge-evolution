"""Xuất snapshot NotebookLM chỉ-đọc thành thư viện tham khảo Obsidian."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

from .obsidian import (_atomic_write, _managed_root, _safe_target,
                       _yaml_value, resolve_obsidian_vault)

SNAPSHOT_PATH = Path(__file__).with_name("notebooklm_bridge_snapshot.json")
DEFAULT_FOLDER = "NotebookLM"
MANIFEST_NAME = ".dylight-notebooklm-manifest.json"
IMPORTER_VERSION = "notebooklm-snapshot-import/1"
_UUID = re.compile(r"^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _table(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def load_notebooklm_snapshot(path: str | Path | None = None) -> dict:
    source = Path(path) if path is not None else SNAPSHOT_PATH
    try:
        data = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Snapshot NotebookLM không đọc được: {source}") from exc
    if not isinstance(data, dict) or data.get("snapshot_schema_version") != 1:
        raise ValueError("Snapshot NotebookLM sai schema_version")
    notebooks = data.get("notebooks")
    if not isinstance(notebooks, list):
        raise ValueError("Snapshot NotebookLM thiếu notebooks")
    seen: set[str] = set()
    for notebook in notebooks:
        if not isinstance(notebook, dict):
            raise ValueError("Notebook entry phải là object")
        notebook_id = notebook.get("notebook_id")
        if not isinstance(notebook_id, str) or not _UUID.fullmatch(notebook_id):
            raise ValueError("NotebookLM notebook_id không hợp lệ")
        if notebook_id in seen:
            raise ValueError(f"Trùng notebook_id: {notebook_id}")
        seen.add(notebook_id)
        expected_url = f"https://notebook.google.com/notebook/{notebook_id}"
        if notebook.get("url") != expected_url:
            raise ValueError(f"NotebookLM URL không khớp ID: {notebook_id}")
        if not isinstance(notebook.get("title"), str) or not notebook["title"].strip():
            raise ValueError(f"NotebookLM thiếu title: {notebook_id}")
        counts = [notebook.get(key) for key in (
            "declared_source_count", "observed_source_items", "non_item_source_count")]
        if any(not isinstance(value, int) or value < 0 for value in counts):
            raise ValueError(f"NotebookLM source count sai: {notebook_id}")
        if counts[1] + counts[2] != counts[0]:
            raise ValueError(f"NotebookLM source count không cân bằng: {notebook_id}")
        inventory = notebook.get("source_inventory")
        if not isinstance(inventory, list):
            raise ValueError(f"NotebookLM source_inventory sai: {notebook_id}")
        observed = 0
        for item in inventory:
            if (not isinstance(item, dict) or not isinstance(item.get("name"), str)
                    or not item["name"].strip() or not isinstance(item.get("count"), int)
                    or item["count"] < 1):
                raise ValueError(f"NotebookLM source item sai: {notebook_id}")
            observed += item["count"]
        if observed != counts[1]:
            raise ValueError(f"NotebookLM source inventory không đủ: {notebook_id}")
        if not isinstance(notebook.get("summary"), str):
            raise ValueError(f"NotebookLM summary sai: {notebook_id}")
        prompts = notebook.get("conversation_prompts")
        if not isinstance(prompts, list) or not all(isinstance(x, str) for x in prompts):
            raise ValueError(f"NotebookLM prompts sai: {notebook_id}")
    return data


def _brain_links(managed_folder: str, title: str) -> list[str]:
    links = [
        f"[[{managed_folder}/00 - Brain 2 Dashboard|Brain 2 Dashboard]]",
        f"[[{managed_folder}/Rules/00 - Rules Index|Rules Index]]",
        f"[[{managed_folder}/Variables/00 - Variables Index|Variables Index]]",
        f"[[{managed_folder}/Standards/TCVN 11823-2017/00 - TCVN 11823-2017|TCVN 11823:2017]]",
    ]
    lower = title.casefold()
    if any(term in lower for term in ("bê tông", "btct", "concrete", "tcvn 11823-5")):
        links.append(
            f"[[{managed_folder}/Standards/TCVN 11823-2017/Parts/"
            "TCVN 11823-5-2017 - Kết cấu bê tông|TCVN 11823-5:2017]]")
    if any(term in lower for term in ("thép", "steel", "i-beam")):
        links.append(
            f"[[{managed_folder}/Standards/TCVN 11823-2017/Parts/"
            "TCVN 11823-6-2017 - Kết cấu thép|TCVN 11823-6:2017]]")
    return links


def _render_notebook(notebook: dict, managed_folder: str,
                     captured_date: str) -> str:
    tags = ["dylight/notebooklm", "dylight/reference", "dylight/bridge"]
    if notebook["public"]:
        tags.append("dylight/notebooklm/public")
    lines = [
        "---",
        f"dylight_kind: {_yaml_value('notebooklm-reference')}",
        "dylight_schema_version: 1",
        f"notebooklm_id: {_yaml_value(notebook['notebook_id'])}",
        f"notebooklm_url: {_yaml_value(notebook['url'])}",
        f"notebooklm_updated_label: {_yaml_value(notebook['updated'])}",
        f"notebooklm_captured_date: {_yaml_value(captured_date)}",
        f"declared_source_count: {notebook['declared_source_count']}",
        f"observed_source_items: {notebook['observed_source_items']}",
        f"public_notebook: {_yaml_value(notebook['public'])}",
        f"tags: {_yaml_value(tags)}",
        f"cssclasses: {_yaml_value(['dylight-note', 'dylight-notebooklm'])}",
        "---", "",
        f"# {notebook['title']}", "",
        "> [!WARNING] Snapshot NotebookLM — nội dung AI chưa kiểm chứng",
        "> Danh mục nguồn và summary được đọc từ giao diện NotebookLM. Summary/chat"
        " không phải bằng chứng kỹ thuật, không tự trở thành rule và không đi vào verifier.",
        "",
        f"[Mở notebook gốc]({notebook['url']})", "",
        "## Liên kết Brain 2", "",
        " · ".join(_brain_links(managed_folder, notebook["title"])), "",
        "## Metadata", "",
        f"- Cập nhật trên NotebookLM: **{notebook['updated']}**",
        f"- Nguồn NotebookLM khai báo: **{notebook['declared_source_count']}**",
        f"- Source item đọc được: **{notebook['observed_source_items']}**",
        f"- Nguồn phi-item (ví dụ Gemini conversation): **{notebook['non_item_source_count']}**",
        f"- Public/shared card: **{'Có' if notebook['public'] else 'Không'}**", "",
        "## NotebookLM summary", "",
        "> [!CAUTION] AI-generated / UNVERIFIED",
        notebook["summary"] or "*(NotebookLM chưa hiển thị summary tại thời điểm chụp.)*", "",
        "## Source inventory", "",
        "| Tên nguồn hiển thị | Số bản ghi |", "|---|---:|",
    ]
    lines.extend(
        f"| {_table(item['name'])} | {item['count']} |"
        for item in notebook["source_inventory"])
    if notebook["non_item_source_count"]:
        lines.append(
            f"| *(nguồn phi-item/nhóm hội thoại không có filename)* |"
            f" {notebook['non_item_source_count']} |")
    lines.extend(["", "## Conversation prompts đã quan sát", ""])
    if notebook["conversation_prompts"]:
        lines.extend(f"- {_table(prompt)}" for prompt in notebook["conversation_prompts"])
    else:
        lines.append("*(Không tải được prompt nào trong snapshot này.)*")
    lines.extend(["", "## Provenance", "",
                  f"- Snapshot date: `{captured_date}`",
                  f"- Importer: `{IMPORTER_VERSION}`", ""])
    return "\n".join(lines)


def _render_index(snapshot: dict, managed_folder: str) -> str:
    notebooks = snapshot["notebooks"]
    total_sources = sum(item["declared_source_count"] for item in notebooks)
    lines = [
        "---",
        f"dylight_kind: {_yaml_value('notebooklm-library')}",
        "dylight_schema_version: 1",
        f"notebook_count: {len(notebooks)}",
        f"declared_source_count: {total_sources}",
        f"captured_date: {_yaml_value(snapshot['captured_date'])}",
        f"tags: {_yaml_value(['dylight/notebooklm', 'dylight/index'])}",
        f"cssclasses: {_yaml_value(['dylight-note', 'dylight-notebooklm', 'dylight-notebooklm-index'])}",
        "---", "", "# NotebookLM — Thư viện cầu và Bridge BIM", "",
        "> [!IMPORTANT] Phạm vi snapshot",
        "> Chỉ gồm notebook có tiêu đề liên quan bridge/cầu/dầm/formtraveler/I-Beam;"
        " notebook cá nhân ngoài dự án không được nhập.", "",
        f"- Notebook: **{len(notebooks)}**",
        f"- Nguồn khai báo: **{total_sources}**",
        f"- Ngày chụp: **{snapshot['captured_date']}**", "",
        f"[[{managed_folder}/00 - Brain 2 Dashboard|← Brain 2 Dashboard]]", "",
        "## Danh mục", "",
        "| Notebook | Nguồn | Updated | Public |", "|---|---:|---|---|",
    ]
    for notebook in notebooks:
        link = f"{managed_folder}/{DEFAULT_FOLDER}/{notebook['notebook_id']}"
        lines.append(
            f"| [[{link}|{_table(notebook['title'])}]] |"
            f" {notebook['declared_source_count']} | {_table(notebook['updated'])} |"
            f" {'Có' if notebook['public'] else 'Không'} |")
    lines.extend(["", "> [!WARNING] Ranh giới sử dụng",
                  "> Mọi summary và chat là dữ liệu tham khảo chưa kiểm chứng."
                  " Muốn biến thành rule phải truy nguồn gốc, dẫn điều khoản, test và duyệt kỹ sư.", ""])
    return "\n".join(lines)


def _load_manifest(path: Path, root: Path) -> dict:
    if not path.exists():
        return {"schema_version": 1, "files": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("NotebookLM manifest không đọc được") from exc
    if data.get("schema_version") != 1 or not isinstance(data.get("files"), dict):
        raise ValueError("NotebookLM manifest sai schema")
    for relative, digest in data["files"].items():
        _safe_target(root, relative)
        if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
            raise ValueError("NotebookLM manifest có hash sai")
    return data


def import_notebooklm_snapshot(
        vault_dir: str | Path | None = None, *,
        snapshot_path: str | Path | None = None,
        managed_folder: str = "DYLIGHT Bridge Evolution",
        collection_folder: str = DEFAULT_FOLDER,
        dry_run: bool = False) -> dict:
    snapshot = load_notebooklm_snapshot(snapshot_path)
    vault = resolve_obsidian_vault(vault_dir)
    managed_root = _managed_root(vault, managed_folder)
    root = _safe_target(managed_root, collection_folder)
    manifest_path = _safe_target(root, MANIFEST_NAME)
    old = (_load_manifest(manifest_path, root) if manifest_path.exists()
           else {"schema_version": 1, "files": {}})
    old_files = old["files"]
    outputs = {
        "00 - NotebookLM Bridge Library.md": (
            _render_index(snapshot, managed_folder) + "\n").encode("utf-8")
    }
    for notebook in snapshot["notebooks"]:
        outputs[f"{notebook['notebook_id']}.md"] = (
            _render_notebook(notebook, managed_folder, snapshot["captured_date"])
            + "\n").encode("utf-8")
    hashes = {name: _sha256(data) for name, data in outputs.items()}
    planned, unchanged, conflicts = [], [], []
    for relative, digest in sorted(hashes.items()):
        target = _safe_target(root, relative)
        current = _sha256(target.read_bytes()) if target.is_file() else None
        if current == digest:
            unchanged.append(relative)
        elif current is not None and old_files.get(relative) != current:
            conflicts.append(relative)
        else:
            planned.append(relative)
    stale = sorted(set(old_files) - set(outputs))
    written: list[str] = []
    manifest = {
        "schema_version": 1,
        "importer_version": IMPORTER_VERSION,
        "snapshot_sha256": _sha256(
            (Path(snapshot_path) if snapshot_path else SNAPSHOT_PATH).read_bytes()),
        "files": dict(sorted(hashes.items())),
    }
    manifest_bytes = (json.dumps(
        manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    manifest_changed = (not manifest_path.is_file()
                        or manifest_path.read_bytes() != manifest_bytes)
    if not conflicts and not dry_run:
        for relative in planned:
            _atomic_write(_safe_target(root, relative), outputs[relative])
            written.append(relative)
        if manifest_changed:
            _atomic_write(manifest_path, manifest_bytes)
    return {
        "vault": str(vault),
        "notebooks": len(snapshot["notebooks"]),
        "declared_sources": sum(
            item["declared_source_count"] for item in snapshot["notebooks"]),
        "planned_writes": planned,
        "written": written,
        "unchanged": unchanged,
        "conflicts": conflicts,
        "stale_not_deleted": stale,
        "manifest_changed": manifest_changed,
        "dry_run": dry_run,
    }


__all__ = ["import_notebooklm_snapshot", "load_notebooklm_snapshot"]
