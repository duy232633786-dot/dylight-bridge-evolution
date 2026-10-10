"""Hàng đợi đồng bộ hai chiều Codex/Obsidian <-> NotebookLM.

Module này quản lý contract và provenance cục bộ. Transport tới giao diện
NotebookLM được thực hiện bởi browser worker riêng; không giả lập API không tồn tại.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Iterable
from uuid import uuid4

from .obsidian import (_atomic_write, _managed_root, _safe_target,
                       _yaml_value, resolve_obsidian_vault)

SCHEMA_VERSION = 1
DEFAULT_STORE = Path("knowledge") / "notebooklm_sync"
DEFAULT_PROJECT = "do-an-cau-vuot-song"
DEFAULT_PROJECT_FOLDER = "Do an cau vuot song"
_UUID = re.compile(r"^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$")
_MESSAGE_ID = re.compile(r"^NBS-[0-9]{8}T[0-9]{6}Z-[0-9a-f]{12}$")
_DIRECTIONS = {"codex_to_notebooklm", "notebooklm_to_codex"}
_STATUSES = {"PENDING", "DELIVERED", "CAPTURED", "ACKNOWLEDGED", "FAILED"}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z")


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _validate_notebook_id(notebook_id: str) -> None:
    if not _UUID.fullmatch(notebook_id):
        raise ValueError("notebook_id phải là UUID hợp lệ")


def _store_root(store_dir: str | Path | None) -> Path:
    root = Path(store_dir) if store_dir is not None else DEFAULT_STORE
    root = root.resolve(strict=False)
    root.mkdir(parents=True, exist_ok=True)
    return root


def _message_path(root: Path, direction: str, message_id: str) -> Path:
    if direction not in _DIRECTIONS or not _MESSAGE_ID.fullmatch(message_id):
        raise ValueError("direction hoặc message_id không hợp lệ")
    folder = "outbox" if direction == "codex_to_notebooklm" else "inbox"
    target = (root / folder / f"{message_id}.json").resolve(strict=False)
    if root not in target.parents:
        raise ValueError("đường dẫn message thoát khỏi sync store")
    return target


def _validate_message(data: dict) -> dict:
    required = {
        "schema_version", "message_id", "direction", "notebook_id",
        "project", "created_at", "updated_at", "status", "content",
        "content_sha256", "origin", "source_refs", "remote_ref", "error",
    }
    if not isinstance(data, dict) or set(data) != required:
        raise ValueError("message sai schema")
    if data["schema_version"] != SCHEMA_VERSION:
        raise ValueError("message sai schema_version")
    if not isinstance(data["message_id"], str) or not _MESSAGE_ID.fullmatch(
            data["message_id"]):
        raise ValueError("message_id không hợp lệ")
    if data["direction"] not in _DIRECTIONS or data["status"] not in _STATUSES:
        raise ValueError("direction/status không hợp lệ")
    _validate_notebook_id(data["notebook_id"])
    for key in ("project", "created_at", "updated_at", "content", "origin"):
        if not isinstance(data[key], str) or not data[key].strip():
            raise ValueError(f"{key} không hợp lệ")
    if not isinstance(data["source_refs"], list) or not all(
            isinstance(item, str) for item in data["source_refs"]):
        raise ValueError("source_refs không hợp lệ")
    if data["remote_ref"] is not None and not isinstance(data["remote_ref"], str):
        raise ValueError("remote_ref không hợp lệ")
    if data["error"] is not None and not isinstance(data["error"], str):
        raise ValueError("error không hợp lệ")
    if data["content_sha256"] != _digest(data["content"]):
        raise ValueError("content_sha256 không khớp")
    return data


def _write_message(root: Path, data: dict, *, create_only: bool = False) -> Path:
    _validate_message(data)
    target = _message_path(root, data["direction"], data["message_id"])
    if create_only and target.exists():
        raise FileExistsError(f"message đã tồn tại: {data['message_id']}")
    payload = (json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True)
               + "\n").encode("utf-8")
    _atomic_write(target, payload)
    return target


def enqueue_codex_message(notebook_id: str, content: str, *,
                          project: str = DEFAULT_PROJECT,
                          origin: str = "codex-chat",
                          source_refs: Iterable[str] = (),
                          store_dir: str | Path | None = None) -> dict:
    """Đưa một lượt Codex/Obsidian vào outbox chờ browser worker gửi."""
    _validate_notebook_id(notebook_id)
    if not isinstance(content, str) or not content.strip():
        raise ValueError("content không được rỗng")
    created = _now()
    compact = created.replace("-", "").replace(":", "")
    message_id = f"NBS-{compact}-{uuid4().hex[:12]}"
    data = {
        "schema_version": SCHEMA_VERSION,
        "message_id": message_id,
        "direction": "codex_to_notebooklm",
        "notebook_id": notebook_id,
        "project": project,
        "created_at": created,
        "updated_at": created,
        "status": "PENDING",
        "content": content.strip(),
        "content_sha256": _digest(content.strip()),
        "origin": origin,
        "source_refs": list(source_refs),
        "remote_ref": None,
        "error": None,
    }
    root = _store_root(store_dir)
    path = _write_message(root, data, create_only=True)
    return {**data, "path": str(path)}


def ingest_notebooklm_capture(capture_path: str | Path, *,
                              store_dir: str | Path | None = None) -> dict:
    """Nhập capture do browser worker tạo vào inbox, có kiểm hash/chống trùng."""
    source = Path(capture_path)
    try:
        raw = json.loads(source.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"capture không đọc được: {source}") from exc
    if not isinstance(raw, dict):
        raise ValueError("capture phải là JSON object")
    notebook_id = raw.get("notebook_id")
    content = raw.get("content")
    _validate_notebook_id(notebook_id if isinstance(notebook_id, str) else "")
    if not isinstance(content, str) or not content.strip():
        raise ValueError("capture thiếu content")
    remote_ref = raw.get("remote_ref")
    if remote_ref is not None and not isinstance(remote_ref, str):
        raise ValueError("capture remote_ref không hợp lệ")
    project = raw.get("project", DEFAULT_PROJECT)
    if not isinstance(project, str) or not project.strip():
        raise ValueError("capture project không hợp lệ")
    root = _store_root(store_dir)
    content = content.strip()
    for existing in load_messages(root, direction="notebooklm_to_codex"):
        if (existing["notebook_id"] == notebook_id
                and existing["content_sha256"] == _digest(content)
                and existing["remote_ref"] == remote_ref):
            return {**existing, "duplicate": True}
    created = _now()
    compact = created.replace("-", "").replace(":", "")
    data = {
        "schema_version": SCHEMA_VERSION,
        "message_id": f"NBS-{compact}-{uuid4().hex[:12]}",
        "direction": "notebooklm_to_codex",
        "notebook_id": notebook_id,
        "project": project,
        "created_at": created,
        "updated_at": created,
        "status": "CAPTURED",
        "content": content,
        "content_sha256": _digest(content),
        "origin": "notebooklm-browser-capture",
        "source_refs": list(raw.get("source_refs", [])),
        "remote_ref": remote_ref,
        "error": None,
    }
    path = _write_message(root, data, create_only=True)
    return {**data, "path": str(path), "duplicate": False}


def load_messages(store_dir: str | Path | None = None, *,
                  direction: str | None = None) -> list[dict]:
    root = _store_root(store_dir)
    directions = [direction] if direction else sorted(_DIRECTIONS)
    messages: list[dict] = []
    for item_direction in directions:
        if item_direction not in _DIRECTIONS:
            raise ValueError("direction không hợp lệ")
        folder = "outbox" if item_direction == "codex_to_notebooklm" else "inbox"
        for path in sorted((root / folder).glob("NBS-*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                raise ValueError(f"message không đọc được: {path}") from exc
            messages.append(_validate_message(data))
    return sorted(messages, key=lambda item: (item["created_at"], item["message_id"]))


def update_message_status(message_id: str, status: str, *,
                          remote_ref: str | None = None,
                          error: str | None = None,
                          store_dir: str | Path | None = None) -> dict:
    if status not in _STATUSES:
        raise ValueError("status không hợp lệ")
    root = _store_root(store_dir)
    matches = list(root.glob(f"*/{message_id}.json"))
    if len(matches) != 1:
        raise FileNotFoundError(f"không tìm thấy duy nhất message: {message_id}")
    data = _validate_message(json.loads(matches[0].read_text(encoding="utf-8")))
    allowed = {
        "PENDING": {"DELIVERED", "FAILED"},
        "FAILED": {"PENDING"},
        "CAPTURED": {"ACKNOWLEDGED", "FAILED"},
        "DELIVERED": set(),
        "ACKNOWLEDGED": set(),
    }
    if status != data["status"] and status not in allowed[data["status"]]:
        raise ValueError(f"chuyển trạng thái không hợp lệ: {data['status']} -> {status}")
    data["status"] = status
    data["updated_at"] = _now()
    data["remote_ref"] = remote_ref if remote_ref is not None else data["remote_ref"]
    data["error"] = error
    _write_message(root, data)
    return data


def sync_status(store_dir: str | Path | None = None) -> dict:
    messages = load_messages(store_dir)
    counts: dict[str, int] = {status: 0 for status in sorted(_STATUSES)}
    for message in messages:
        counts[message["status"]] += 1
    return {
        "store": str(_store_root(store_dir)),
        "total": len(messages),
        "counts": counts,
        "browser_transport_required": True,
        "transport_status": "NOT_CONFIGURED",
    }


def _render_sync_dashboard(messages: list[dict], managed_folder: str,
                           project: str) -> str:
    rows = [
        "---",
        f"dylight_kind: {_yaml_value('notebooklm-two-way-sync')}",
        "dylight_schema_version: 1",
        f"project: {_yaml_value(project)}",
        f"tags: {_yaml_value(['dylight/notebooklm', 'dylight/sync'])}",
        "---", "", "# NotebookLM - Đồng bộ hai chiều", "",
        "> [!warning] Trạng thái transport",
        "> Hàng đợi hai chiều đã hoạt động cục bộ. Việc gửi/thu với NotebookLM",
        "> chỉ hoàn tất khi browser worker đã xác nhận `DELIVERED` hoặc `CAPTURED`.",
        "", f"[[{managed_folder}/NotebookLM/00 - NotebookLM Bridge Library|Thư viện NotebookLM]]",
        "", "## Nhật ký", "",
        "| Thời gian | Chiều | Notebook | Trạng thái | Nội dung |", "|---|---|---|---|---|",
    ]
    for item in reversed(messages):
        snippet = item["content"].replace("|", "\\|").replace("\n", " ")[:120]
        rows.append(
            f"| {item['created_at']} | {item['direction']} | {item['notebook_id']} |"
            f" {item['status']} | {snippet} |")
    rows.extend(["", "## Quy tắc", "",
                 "- `PENDING`: chờ gửi sang NotebookLM.",
                 "- `DELIVERED`: worker đã xác nhận gửi.",
                 "- `CAPTURED`: nội dung NotebookLM đã được thu về.",
                 "- `ACKNOWLEDGED`: Codex/người dùng đã xử lý capture.",
                 "- Summary/chat vẫn là `UNVERIFIED` cho đến khi đối chiếu nguồn.", ""])
    return "\n".join(rows)


def export_sync_dashboard(vault_dir: str | Path | None = None, *,
                          store_dir: str | Path | None = None,
                          managed_folder: str = "DYLIGHT Bridge Evolution",
                          project: str = DEFAULT_PROJECT,
                          dry_run: bool = False) -> dict:
    vault = resolve_obsidian_vault(vault_dir)
    managed = _managed_root(vault, managed_folder)
    project_folder = DEFAULT_PROJECT_FOLDER if project == DEFAULT_PROJECT else project
    relative = f"Projects/{project_folder}/02 - NotebookLM Two-Way Sync.md"
    target = _safe_target(managed, relative)
    payload = (_render_sync_dashboard(load_messages(store_dir), managed_folder, project)
               + "\n").encode("utf-8")
    changed = not target.is_file() or target.read_bytes() != payload
    if changed and not dry_run:
        _atomic_write(target, payload)
    return {"vault": str(vault), "path": str(target), "changed": changed,
            "dry_run": dry_run}


__all__ = [
    "enqueue_codex_message", "export_sync_dashboard",
    "ingest_notebooklm_capture", "load_messages", "sync_status",
    "update_message_status",
]
