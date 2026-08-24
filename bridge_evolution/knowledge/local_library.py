"""Nhập thư viện tài liệu kỹ thuật cục bộ (ổ trong máy + USB) vào Obsidian.

File gốc được copy nguyên byte vào vùng ``Library`` của vault; Markdown chỉ chứa
metadata, thống kê và liên kết. Nội dung nhập vào là dữ liệu tham khảo
(REFERENCE_ONLY): nó không tạo rule, không đổi catalog và không được solver hay
verifier đọc.

Khử trùng lặp theo nội dung: mỗi nội dung duy nhất chỉ lưu một bản trong vault,
mọi đường dẫn nguồn trùng vẫn được ghi lại đầy đủ trong manifest và note.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import time
from typing import Callable, Iterable, Iterator

from .obsidian import _managed_root, _safe_target, _yaml_value, resolve_obsidian_vault

IMPORTER_VERSION = "local-library-import/1"
LIBRARY_MANIFEST = ".dylight-library-manifest.json"
MANIFEST_SCHEMA_VERSION = 1
DEFAULT_LIBRARY_FOLDER = "Library"

DOC_EXTENSIONS = {
    ".pdf", ".docx", ".doc", ".xlsx", ".xls", ".xlsm", ".pptx", ".ppt",
    ".txt", ".csv", ".rtf",
}
# ``.md`` nằm ngoài mặc định: Obsidian index mọi Markdown trong vault thành note,
# nên copy README của add-in vào đây sẽ làm ngập graph bằng ghi chú không liên quan.
MARKDOWN_EXTENSIONS = {".md"}
CAD_EXTENSIONS = {
    ".dwg", ".dxf", ".dwf", ".dgn", ".rvt", ".rfa", ".rte", ".rft",
    ".ifc", ".nwd", ".nwc", ".dyn", ".dyf",
}
CALC_EXTENSIONS = {".mcb", ".mgb", ".sdb", ".edb", ".s2k", ".anl"}
CODE_EXTENSIONS = {".lsp", ".vlx", ".dcl", ".py", ".cs", ".json", ".yml", ".yaml"}

SKIP_DIR_NAMES = {
    "system volume information", "$recycle.bin", "node_modules", ".git",
    ".venv", "venv", "__pycache__", "appdata", "windows", "program files",
    "program files (x86)", "programdata", ".cache", ".gradle", ".nuget",
    "site-packages", ".obsidian", ".pytest_cache", ".idea", ".vs",
}

MAX_FILE_BYTES = 2 * 1024 * 1024 * 1024
QUICK_HASH_WINDOW = 1024 * 1024
COPY_CHUNK = 4 * 1024 * 1024

BRIDGE_KEYWORDS = (
    "cầu", "cau ", "cau_", "bridge", "dầm", "girder", "super-t", "supert",
    "mố", "trụ", "pier", "abutment", "cọc", "pile", "bản mặt cầu", "deck",
    "dự ứng lực", "prestress", "nhịp", "xà mũ", "gối", "bearing",
)
PROJECT_KEYWORDS = (
    "hồ sơ", "ho so", "tkkt", "bvtc", "bptc", "kcpt", "thkl", "dự toán",
    "du toan", "thuyết minh", "thuyet minh", "bản vẽ", "ban ve", "khảo sát",
)
STANDARD_KEYWORDS = (
    "tcvn", "11823", "10304", "22tcn", "aashto", "tiêu chuẩn", "tieu chuan",
    "quy trình", "quy trinh", "quy chuẩn",
)
COURSE_KEYWORDS = (
    "khoá học", "khoa hoc", "bài giảng", "bai giang", "giáo trình",
    "giao trinh", "tutorial", "training", "đại học", "dai hoc",
    "tốt nghiệp", "tot nghiep", "đồ án", "do an",
)
BIM_KEYWORDS = ("family", "template", "library", "revit", "libraries", "lookup tables")
SCRIPT_KEYWORDS = ("dynamo", "lisp", "script", "addin", "add-in", "macro")
ROAD_KEYWORDS = (
    "đường", "duong", "civil 3d", "cv3d", "alignment", "trắc dọc",
    "san nền", "thủy lực", "thuy luc", "cống", "cong ",
)

TOPICS: dict[str, dict[str, str]] = {
    "bridge-projects": {
        "title": "Hồ sơ dự án cầu",
        "note": "Hồ sơ thiết kế cầu thực tế — nguồn kích thước và cấu tạo thật.",
    },
    "bridge-references": {
        "title": "Tài liệu và tiêu chuẩn cầu",
        "note": "Tiêu chuẩn, giáo trình và tài liệu kỹ thuật về cầu.",
    },
    "bim-library": {
        "title": "Thư viện BIM",
        "note": "Family, template và thư viện Revit.",
    },
    "automation": {
        "title": "Dynamo, LISP và add-in",
        "note": "Script tự động hoá cho Revit, AutoCAD và Civil 3D.",
    },
    "road-survey": {
        "title": "Đường và khảo sát",
        "note": "Hồ sơ đường, Civil 3D, thuỷ văn và khảo sát.",
    },
    "courses": {
        "title": "Học liệu",
        "note": "Khoá học, bài giảng và đồ án.",
    },
    "other": {
        "title": "Khác",
        "note": "Chưa phân loại theo chủ đề cầu/BIM.",
    },
}

_SLUG_UNSAFE = re.compile(r"[^0-9A-Za-zÀ-ỹ ._-]+")
_WS = re.compile(r"\s+")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _long_path(path: Path | str) -> str:
    """Windows giới hạn MAX_PATH; dùng tiền tố mở rộng cho đường dẫn dài."""
    text = str(path)
    if os.name != "nt" or text.startswith("\\\\?\\"):
        return text
    absolute = os.path.abspath(text)
    if len(absolute) < 240:
        return absolute
    if absolute.startswith("\\\\"):
        return "\\\\?\\UNC" + absolute[1:]
    return "\\\\?\\" + absolute


def _quick_key(path: Path, size: int) -> tuple[int, str]:
    """Khoá sàng lọc rẻ: kích thước + hash cửa sổ đầu/cuối file."""
    digest = hashlib.sha256()
    with open(_long_path(path), "rb") as stream:
        digest.update(stream.read(QUICK_HASH_WINDOW))
        if size > 2 * QUICK_HASH_WINDOW:
            stream.seek(-QUICK_HASH_WINDOW, os.SEEK_END)
            digest.update(stream.read(QUICK_HASH_WINDOW))
    return size, digest.hexdigest()


def _full_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with open(_long_path(path), "rb") as stream:
        while True:
            chunk = stream.read(COPY_CHUNK)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _slug(text: str, limit: int = 80) -> str:
    cleaned = _SLUG_UNSAFE.sub(" ", text)
    cleaned = _WS.sub(" ", cleaned).strip(" .")
    if not cleaned:
        cleaned = "untitled"
    return cleaned[:limit].strip(" .")


def _human_bytes(value: int) -> str:
    step = float(value)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if step < 1024 or unit == "TB":
            return f"{step:.0f} {unit}" if unit in ("B", "KB") else f"{step:.1f} {unit}"
        step /= 1024
    return f"{step:.1f} TB"


def _classify(path_text: str) -> str:
    lowered = path_text.lower()

    def has(words: Iterable[str]) -> bool:
        return any(word in lowered for word in words)

    bridge = has(BRIDGE_KEYWORDS)
    if bridge and has(PROJECT_KEYWORDS):
        return "bridge-projects"
    if has(STANDARD_KEYWORDS):
        return "bridge-references"
    if has(SCRIPT_KEYWORDS):
        return "automation"
    if has(BIM_KEYWORDS):
        return "bim-library"
    if has(COURSE_KEYWORDS):
        return "courses"
    if has(ROAD_KEYWORDS):
        return "road-survey"
    if bridge:
        return "bridge-references"
    return "other"


def _kind(extension: str) -> str:
    if extension in DOC_EXTENSIONS:
        return "document"
    if extension in CAD_EXTENSIONS:
        return "cad"
    if extension in CALC_EXTENSIONS:
        return "analysis"
    if extension in CODE_EXTENSIONS:
        return "code"
    return "other"


def _wanted_extensions(include_code: bool, include_markdown: bool) -> set[str]:
    extensions = set(DOC_EXTENSIONS) | set(CAD_EXTENSIONS) | set(CALC_EXTENSIONS)
    if include_code:
        extensions |= set(CODE_EXTENSIONS)
    if include_markdown:
        extensions |= set(MARKDOWN_EXTENSIONS)
    return extensions


def _is_within(candidate: Path, parent: Path) -> bool:
    try:
        candidate.relative_to(parent)
    except ValueError:
        return False
    return True


def scan_source(root: Path, *, include_code: bool = False,
                include_markdown: bool = False,
                exclude_roots: tuple[Path, ...] = (),
                max_depth: int = 12) -> Iterator[dict]:
    """Duyệt một gốc nguồn và trả metadata từng file ứng viên."""
    root = Path(root)
    extensions = _wanted_extensions(include_code, include_markdown)
    base_depth = len(root.parts)
    for dirpath, dirnames, filenames in os.walk(
            _long_path(root), topdown=True, onerror=lambda error: None):
        current = Path(dirpath)
        if any(_is_within(current, excluded) for excluded in exclude_roots):
            dirnames[:] = []
            continue
        if len(current.parts) - base_depth >= max_depth:
            dirnames[:] = []
        dirnames[:] = [name for name in dirnames
                       if name.lower() not in SKIP_DIR_NAMES
                       and not name.startswith("$")
                       and not any(_is_within(current / name, excluded)
                                   for excluded in exclude_roots)]
        for filename in filenames:
            extension = os.path.splitext(filename)[1].lower()
            if extension not in extensions:
                continue
            candidate = current / filename
            try:
                stat = candidate.stat()
            except OSError:
                continue
            if stat.st_size == 0 or stat.st_size > MAX_FILE_BYTES:
                continue
            yield {
                "path": str(candidate),
                "name": filename,
                "extension": extension,
                "size": stat.st_size,
                "mtime": int(stat.st_mtime),
                "source_root": str(root),
            }


def _tail_parts(entry: dict) -> tuple[str, ...]:
    parts = Path(entry["path"]).parts
    root_parts = len(Path(entry["source_root"]).parts)
    return parts[root_parts:]


def _collection_of(entry: dict, depth: int) -> str:
    tail = _tail_parts(entry)
    drive = (Path(entry["source_root"]).drive or "").rstrip(":") or "root"
    folders = tail[:-1]
    label = " / ".join(folders[:depth]) if folders else "(gốc ổ đĩa)"
    return f"{drive} — {label}"


def _relative_in_collection(entry: dict, depth: int) -> str:
    tail = _tail_parts(entry)
    folders = tail[:-1]
    remainder = folders[depth:]
    return "/".join([*remainder, entry["name"]])


def plan_import(sources: list[Path], *, include_code: bool = False,
                include_markdown: bool = False,
                exclude_roots: tuple[Path, ...] = (),
                collection_depth: int = 2,
                progress: Callable[[str], None] | None = None) -> dict:
    """Kiểm kê, phân loại và khử trùng lặp trước khi ghi bất kỳ file nào."""
    entries: list[dict] = []
    for source in sources:
        source = Path(source)
        if not source.exists():
            raise FileNotFoundError(f"Nguồn không tồn tại: {source}")
        count = 0
        for entry in scan_source(source, include_code=include_code,
                                 include_markdown=include_markdown,
                                 exclude_roots=exclude_roots):
            entries.append(entry)
            count += 1
            if progress and count % 5000 == 0:
                progress(f"  quét {source}: {count} file")
        if progress:
            progress(f"  quét {source}: {count} file")

    by_size: dict[int, list[dict]] = {}
    for entry in entries:
        by_size.setdefault(entry["size"], []).append(entry)

    duplicates: dict[str, list[dict]] = {}
    unique: list[dict] = []
    checked = 0
    for size, group in by_size.items():
        if len(group) == 1:
            unique.append(group[0])
            continue
        by_quick: dict[tuple[int, str], list[dict]] = {}
        for entry in group:
            try:
                key = _quick_key(Path(entry["path"]), size)
            except OSError:
                continue
            by_quick.setdefault(key, []).append(entry)
            checked += 1
            if progress and checked % 5000 == 0:
                progress(f"  sàng lọc trùng lặp: {checked} file")
        for quick_group in by_quick.values():
            if len(quick_group) == 1:
                unique.append(quick_group[0])
                continue
            by_hash: dict[str, list[dict]] = {}
            for entry in quick_group:
                try:
                    entry["sha256"] = _full_hash(Path(entry["path"]))
                except OSError:
                    continue
                by_hash.setdefault(entry["sha256"], []).append(entry)
            for digest, same in by_hash.items():
                same.sort(key=lambda item: (
                    0 if item["path"][:1].upper() == "G" else 1, len(item["path"])))
                unique.append(same[0])
                if len(same) > 1:
                    duplicates[digest] = [item["path"] for item in same[1:]]

    for entry in unique:
        entry["topic"] = _classify(entry["path"])
        entry["collection"] = _collection_of(entry, collection_depth)
        entry["kind"] = _kind(entry["extension"])
        entry["relative"] = _relative_in_collection(entry, collection_depth)

    collections: dict[str, dict] = {}
    used_slugs: dict[str, str] = {}
    for entry in sorted(unique, key=lambda item: item["collection"]):
        name = entry["collection"]
        bucket = collections.get(name)
        if bucket is None:
            slug = _slug(name)
            if slug in used_slugs and used_slugs[slug] != name:
                slug = f"{slug} ({_sha256_bytes(name.encode('utf-8'))[:6]})"
            used_slugs[slug] = name
            bucket = collections[name] = {
                "name": name, "slug": slug, "topics": {},
                "entries": [], "bytes": 0,
            }
        bucket["entries"].append(entry)
        bucket["bytes"] += entry["size"]
        bucket["topics"][entry["topic"]] = bucket["topics"].get(entry["topic"], 0) + 1

    for bucket in collections.values():
        bucket["topic"] = max(bucket["topics"].items(),
                              key=lambda item: (item[1], item[0]))[0]
        for entry in bucket["entries"]:
            entry["vault_relative"] = f"Files/{bucket['slug']}/{entry['relative']}"

    return {
        "sources": [str(Path(source)) for source in sources],
        "scanned": len(entries),
        "scanned_bytes": sum(entry["size"] for entry in entries),
        "unique": unique,
        "unique_bytes": sum(entry["size"] for entry in unique),
        "duplicates": duplicates,
        "duplicate_count": sum(len(items) for items in duplicates.values()),
        "collections": collections,
        "collection_depth": collection_depth,
        "include_code": include_code,
        "include_markdown": include_markdown,
    }


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name[:40]}.", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(_long_path(temporary), _long_path(path))
    finally:
        if temporary.exists():
            temporary.unlink()


def _atomic_copy(source: Path, target: Path) -> str:
    """Copy nguyên byte qua file tạm cùng thư mục và trả SHA-256 đã ghi."""
    target.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name[:40]}.", suffix=".tmp", dir=target.parent)
    temporary = Path(temporary_name)
    digest = hashlib.sha256()
    try:
        with os.fdopen(handle, "wb") as writer, \
                open(_long_path(source), "rb") as reader:
            while True:
                chunk = reader.read(COPY_CHUNK)
                if not chunk:
                    break
                digest.update(chunk)
                writer.write(chunk)
            writer.flush()
            os.fsync(writer.fileno())
        os.replace(_long_path(temporary), _long_path(target))
    finally:
        if temporary.exists():
            temporary.unlink()
    return digest.hexdigest()


def _load_manifest(path: Path) -> dict:
    if not path.exists():
        return {"schema_version": MANIFEST_SCHEMA_VERSION,
                "importer": IMPORTER_VERSION, "files": {}, "notes": {},
                "duplicates": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Manifest thư viện hỏng: {path}") from error
    if not isinstance(data, dict):
        raise ValueError(f"Manifest thư viện hỏng: {path}")
    data.setdefault("files", {})
    data.setdefault("notes", {})
    data.setdefault("duplicates", {})
    return data


MAX_NOTE_ROWS = 300
_KIND_ORDER = {"document": 0, "analysis": 1, "cad": 2, "code": 3, "other": 4}


def _md_escape(text: str) -> str:
    return text.replace("|", "\\|").replace("[", "(").replace("]", ")")


def _note_link(root_relative: str, label: str) -> str:
    return f"[{_md_escape(label)}]({root_relative.replace(' ', '%20')})"


def _render_collection_note(bucket: dict, managed_folder: str,
                            library_folder: str,
                            duplicates: dict[str, list[str]]) -> bytes:
    entries = bucket["entries"]
    slug = bucket["slug"]
    topic = bucket["topic"]
    by_kind: dict[str, int] = {}
    by_extension: dict[str, int] = {}
    for entry in entries:
        by_kind[entry["kind"]] = by_kind.get(entry["kind"], 0) + 1
        by_extension[entry["extension"]] = by_extension.get(entry["extension"], 0) + 1
    source_roots = sorted({entry["source_root"] for entry in entries})
    origins = sorted({str(Path(entry["path"]).parent) for entry in entries})

    lines: list[str] = []
    lines.append("---")
    lines.append('dylight_kind: "library-collection"')
    lines.append(f"dylight_schema_version: {MANIFEST_SCHEMA_VERSION}")
    lines.append(f"collection: {_yaml_value(bucket['name'])}")
    lines.append(f"topic: {_yaml_value(topic)}")
    lines.append(f"file_count: {len(entries)}")
    lines.append(f"total_bytes: {bucket['bytes']}")
    lines.append(f"importer: {_yaml_value(IMPORTER_VERSION)}")
    lines.append("evidence_status: REFERENCE_ONLY")
    lines.append("source_roots:")
    for item in source_roots:
        lines.append(f"  - {_yaml_value(item)}")
    lines.append('tags: ["dylight/library", ' + f'"dylight/library/{topic}"]')
    lines.append('cssclasses: ["dylight-note","dylight-library"]')
    lines.append("---")
    lines.append("")
    lines.append(f"# {bucket['name']}")
    lines.append("")
    lines.append("> [!INFO] Dữ liệu tham khảo")
    lines.append("> Bản sao nguyên byte của tài liệu cục bộ. Nội dung ở đây **không**"
                 " tạo rule, không đổi catalog và không được solver/verifier đọc."
                 " Muốn dùng một con số phải trích đúng nguồn, thêm test và được kỹ sư duyệt.")
    lines.append("")
    lines.append(f"- Chủ đề: **{TOPICS[topic]['title']}**")
    lines.append(f"- Số file: **{len(entries)}** · Dung lượng: **{_human_bytes(bucket['bytes'])}**")
    lines.append(f"- Thư mục file trong vault: `{library_folder}/Files/{slug}/`")
    lines.append(f"- Kiểm kê đầy đủ: `{library_folder}/Inventory/{slug}.csv`")
    lines.append("")
    lines.append("## Thành phần")
    lines.append("")
    lines.append("| Loại | Số file |")
    lines.append("| --- | ---: |")
    for kind, count in sorted(by_kind.items(), key=lambda item: -item[1]):
        lines.append(f"| {kind} | {count} |")
    lines.append("")
    lines.append("Định dạng: " + ", ".join(
        f"`{extension}` ×{count}" for extension, count
        in sorted(by_extension.items(), key=lambda item: -item[1])[:14]))
    lines.append("")
    lines.append("## Nguồn gốc")
    lines.append("")
    for item in origins[:40]:
        lines.append(f"- `{item}`")
    if len(origins) > 40:
        lines.append(f"- … và {len(origins) - 40} thư mục nguồn khác (xem CSV kiểm kê)")
    lines.append("")

    ranked = sorted(entries, key=lambda item: (
        _KIND_ORDER.get(item["kind"], 9), -item["size"]))
    shown = ranked[:MAX_NOTE_ROWS]
    lines.append("## File")
    lines.append("")
    if len(entries) > MAX_NOTE_ROWS:
        lines.append(f"Hiển thị {MAX_NOTE_ROWS}/{len(entries)} file (ưu tiên tài liệu,"
                     f" rồi tới kích thước). Danh sách đầy đủ nằm trong CSV kiểm kê.")
        lines.append("")
    lines.append("| File | Loại | Kích thước | Bản sao nguồn |")
    lines.append("| --- | --- | ---: | ---: |")
    for entry in shown:
        target = f"{managed_folder}/{library_folder}/{entry['vault_relative']}"
        duplicate_count = len(duplicates.get(entry.get("sha256", ""), []))
        lines.append(
            f"| {_note_link(target, entry['relative'])} | {entry['kind']} |"
            f" {_human_bytes(entry['size'])} | {duplicate_count} |")
    lines.append("")
    lines.append("## Liên kết")
    lines.append("")
    lines.append(f"- [[{managed_folder}/{library_folder}/00 - Local Library|Local Library]]")
    lines.append(f"- [[{managed_folder}/{library_folder}/Topics/{TOPICS[topic]['title']}|"
                 f"{TOPICS[topic]['title']}]]")
    lines.append(f"- [[{managed_folder}/00 - Brain 2 Dashboard|Brain 2 Dashboard]]")
    lines.append("")
    return ("\n".join(lines)).encode("utf-8")


def _render_topic_note(topic: str, buckets: list[dict], managed_folder: str,
                       library_folder: str) -> bytes:
    total_files = sum(len(bucket["entries"]) for bucket in buckets)
    total_bytes = sum(bucket["bytes"] for bucket in buckets)
    lines: list[str] = []
    lines.append("---")
    lines.append('dylight_kind: "library-topic"')
    lines.append(f"dylight_schema_version: {MANIFEST_SCHEMA_VERSION}")
    lines.append(f"topic: {_yaml_value(topic)}")
    lines.append(f"collection_count: {len(buckets)}")
    lines.append(f"file_count: {total_files}")
    lines.append(f"total_bytes: {total_bytes}")
    lines.append("evidence_status: REFERENCE_ONLY")
    lines.append('tags: ["dylight/library", ' + f'"dylight/library/{topic}"]')
    lines.append('cssclasses: ["dylight-note","dylight-library"]')
    lines.append("---")
    lines.append("")
    lines.append(f"# {TOPICS[topic]['title']}")
    lines.append("")
    lines.append(TOPICS[topic]["note"])
    lines.append("")
    lines.append(f"- Bộ sưu tập: **{len(buckets)}** · File: **{total_files}**"
                 f" · Dung lượng: **{_human_bytes(total_bytes)}**")
    lines.append("")
    lines.append("| Bộ sưu tập | File | Dung lượng |")
    lines.append("| --- | ---: | ---: |")
    for bucket in sorted(buckets, key=lambda item: -len(item["entries"])):
        link = (f"[[{managed_folder}/{library_folder}/Collections/{bucket['slug']}"
                f"|{_md_escape(bucket['name'])}]]")
        lines.append(f"| {link} | {len(bucket['entries'])} |"
                     f" {_human_bytes(bucket['bytes'])} |")
    lines.append("")
    lines.append(f"- [[{managed_folder}/{library_folder}/00 - Local Library|Local Library]]")
    lines.append("")
    return ("\n".join(lines)).encode("utf-8")


def _render_library_index(plan: dict, managed_folder: str,
                          library_folder: str, copied_bytes: int) -> bytes:
    collections = plan["collections"]
    by_topic: dict[str, list[dict]] = {}
    for bucket in collections.values():
        by_topic.setdefault(bucket["topic"], []).append(bucket)
    lines: list[str] = []
    lines.append("---")
    lines.append('dylight_kind: "library-index"')
    lines.append(f"dylight_schema_version: {MANIFEST_SCHEMA_VERSION}")
    lines.append(f"importer: {_yaml_value(IMPORTER_VERSION)}")
    lines.append(f"collection_count: {len(collections)}")
    lines.append(f"file_count: {len(plan['unique'])}")
    lines.append(f"total_bytes: {plan['unique_bytes']}")
    lines.append(f"duplicate_count: {plan['duplicate_count']}")
    lines.append("evidence_status: REFERENCE_ONLY")
    lines.append("source_roots:")
    for item in plan["sources"]:
        lines.append(f"  - {_yaml_value(item)}")
    lines.append('tags: ["dylight/library","dylight/dashboard"]')
    lines.append('cssclasses: ["dylight-note","dylight-dashboard"]')
    lines.append("---")
    lines.append("")
    lines.append("# Thư viện tài liệu cục bộ")
    lines.append("")
    lines.append("> [!IMPORTANT] Ranh giới an toàn")
    lines.append("> Toàn bộ vùng này là **REFERENCE_ONLY**. Tài liệu cá nhân, hồ sơ dự án"
                 " và thư viện BIM ở đây không phải nguồn chuẩn của hệ thống: JSON trong"
                 " repo là nguồn chuẩn, verifier là nơi duy nhất quyết định PASS/FAIL.")
    lines.append("")
    lines.append("## Tổng quan")
    lines.append("")
    lines.append(f"- Nguồn quét: {', '.join('`' + item + '`' for item in plan['sources'])}")
    lines.append(f"- File tìm thấy: **{plan['scanned']}** ({_human_bytes(plan['scanned_bytes'])})")
    lines.append(f"- Sau khử trùng lặp theo nội dung: **{len(plan['unique'])}**"
                 f" ({_human_bytes(plan['unique_bytes'])})")
    lines.append(f"- Bản sao trùng nội dung đã bỏ qua: **{plan['duplicate_count']}**"
                 f" (đường dẫn gốc vẫn được ghi trong manifest)")
    lines.append(f"- Đã copy vào vault trong lần chạy này: **{_human_bytes(copied_bytes)}**")
    lines.append(f"- Bộ sưu tập: **{len(collections)}**")
    lines.append("")
    lines.append("## Theo chủ đề")
    lines.append("")
    lines.append("| Chủ đề | Bộ sưu tập | File | Dung lượng |")
    lines.append("| --- | ---: | ---: | ---: |")
    for topic in TOPICS:
        buckets = by_topic.get(topic, [])
        if not buckets:
            continue
        files = sum(len(bucket["entries"]) for bucket in buckets)
        size = sum(bucket["bytes"] for bucket in buckets)
        link = (f"[[{managed_folder}/{library_folder}/Topics/{TOPICS[topic]['title']}"
                f"|{TOPICS[topic]['title']}]]")
        lines.append(f"| {link} | {len(buckets)} | {files} | {_human_bytes(size)} |")
    lines.append("")
    lines.append("## Bộ sưu tập lớn nhất")
    lines.append("")
    lines.append("| Bộ sưu tập | Chủ đề | File | Dung lượng |")
    lines.append("| --- | --- | ---: | ---: |")
    ranked = sorted(collections.values(), key=lambda item: -item["bytes"])[:40]
    for bucket in ranked:
        link = (f"[[{managed_folder}/{library_folder}/Collections/{bucket['slug']}"
                f"|{_md_escape(bucket['name'])}]]")
        lines.append(f"| {link} | {TOPICS[bucket['topic']]['title']} |"
                     f" {len(bucket['entries'])} | {_human_bytes(bucket['bytes'])} |")
    lines.append("")
    lines.append("## Cách dùng an toàn")
    lines.append("")
    lines.append("1. Tra cứu và trích dẫn: mở file gốc trong vault, ghi rõ đường dẫn và SHA-256.")
    lines.append("2. Muốn biến một kích thước thật thành tham số hệ thống: tạo"
                 " KnowledgeCard có provenance, thêm test, chờ kỹ sư duyệt.")
    lines.append("3. Không sửa file trong `Files/`; importer coi thay đổi là xung đột"
                 " và sẽ dừng cập nhật file đó.")
    lines.append("")
    lines.append(f"- [[{managed_folder}/00 - Brain 2 Dashboard|Brain 2 Dashboard]]")
    lines.append("")
    return ("\n".join(lines)).encode("utf-8")


def _render_inventory_csv(bucket: dict) -> bytes:
    rows = ["vault_path,source_path,extension,kind,size_bytes,sha256"]
    for entry in sorted(bucket["entries"], key=lambda item: item["relative"]):
        cells = [
            entry["vault_relative"], entry["path"], entry["extension"],
            entry["kind"], str(entry["size"]), entry.get("sha256", ""),
        ]
        rows.append(",".join('"' + cell.replace('"', '""') + '"' for cell in cells))
    return ("\n".join(rows) + "\n").encode("utf-8")


def import_local_library(
        sources: list[str | Path], *,
        vault_dir: str | Path | None = None,
        managed_folder: str = "DYLIGHT Bridge Evolution",
        library_folder: str = DEFAULT_LIBRARY_FOLDER,
        include_code: bool = False,
        include_markdown: bool = False,
        collection_depth: int = 2,
        dry_run: bool = False,
        progress: Callable[[str], None] | None = None,
        checkpoint_every: int = 200) -> dict:
    """Copy tài liệu cục bộ vào vault và sinh note chỉ mục có provenance.

    File đã có trong vault và còn khớp manifest thì bỏ qua, nên lệnh có thể chạy
    lại để tiếp tục một lần nhập bị ngắt. File người dùng đã sửa trong vault được
    báo ``CONFLICT`` và không bị ghi đè; không file nào bị xoá tự động.
    """
    vault = resolve_obsidian_vault(vault_dir)
    root = _managed_root(vault, f"{managed_folder}/{library_folder}")
    manifest_path = root / LIBRARY_MANIFEST
    manifest = _load_manifest(manifest_path)

    if progress:
        progress("Kiểm kê nguồn…")
    # Vault không bao giờ là nguồn của chính nó: quét nó sẽ nhân đôi vô hạn.
    exclude_roots = (vault.resolve(),)
    plan = plan_import([Path(item) for item in sources],
                       include_code=include_code,
                       include_markdown=include_markdown,
                       exclude_roots=exclude_roots,
                       collection_depth=collection_depth,
                       progress=progress)
    if progress:
        progress(f"Kiểm kê xong: {plan['scanned']} file "
                 f"({_human_bytes(plan['scanned_bytes'])}); duy nhất "
                 f"{len(plan['unique'])} ({_human_bytes(plan['unique_bytes'])})")

    result = {
        "vault": str(vault), "managed_folder": managed_folder,
        "library_folder": library_folder, "dry_run": dry_run,
        "scanned": plan["scanned"], "unique": len(plan["unique"]),
        "unique_bytes": plan["unique_bytes"],
        "duplicate_count": plan["duplicate_count"],
        "collections": len(plan["collections"]),
        "copied": 0, "copied_bytes": 0, "skipped": 0, "failed": [],
        "conflicts": [], "notes_written": 0, "notes_unchanged": 0,
    }
    if dry_run:
        result["plan_preview"] = [
            {"collection": bucket["name"], "topic": bucket["topic"],
             "files": len(bucket["entries"]), "bytes": bucket["bytes"]}
            for bucket in sorted(plan["collections"].values(),
                                 key=lambda item: -item["bytes"])[:40]
        ]
        return result

    root.mkdir(parents=True, exist_ok=True)
    files_state: dict[str, dict] = manifest["files"]
    processed = 0
    for bucket in plan["collections"].values():
        for entry in bucket["entries"]:
            relative = entry["vault_relative"]
            target = _safe_target(root, relative)
            recorded = files_state.get(relative)
            if target.exists():
                try:
                    stat = target.stat()
                except OSError:
                    stat = None
                if recorded and stat and stat.st_size == recorded.get("size") \
                        and int(stat.st_mtime) == recorded.get("vault_mtime"):
                    result["skipped"] += 1
                    entry.setdefault("sha256", recorded.get("sha256", ""))
                    continue
                if recorded is None or (stat and stat.st_size != recorded.get("size")):
                    result["conflicts"].append(relative)
                    continue
            try:
                digest = _atomic_copy(Path(entry["path"]), target)
            except OSError as error:
                result["failed"].append({"path": entry["path"], "error": str(error)})
                continue
            entry["sha256"] = digest
            try:
                vault_mtime = int(target.stat().st_mtime)
            except OSError:
                vault_mtime = 0
            files_state[relative] = {
                "sha256": digest, "size": entry["size"],
                "source": entry["path"], "source_mtime": entry["mtime"],
                "vault_mtime": vault_mtime, "collection": bucket["name"],
                "topic": entry["topic"],
            }
            result["copied"] += 1
            result["copied_bytes"] += entry["size"]
            processed += 1
            if progress and processed % 50 == 0:
                progress(f"  copy {result['copied']} file"
                         f" ({_human_bytes(result['copied_bytes'])})")
            if processed % checkpoint_every == 0:
                manifest["duplicates"] = plan["duplicates"]
                _atomic_write(manifest_path,
                              json.dumps(manifest, ensure_ascii=False,
                                         indent=2, sort_keys=True).encode("utf-8"))

    notes: dict[str, bytes] = {}
    for bucket in plan["collections"].values():
        notes[f"Collections/{bucket['slug']}.md"] = _render_collection_note(
            bucket, managed_folder, library_folder, plan["duplicates"])
        notes[f"Inventory/{bucket['slug']}.csv"] = _render_inventory_csv(bucket)
    by_topic: dict[str, list[dict]] = {}
    for bucket in plan["collections"].values():
        by_topic.setdefault(bucket["topic"], []).append(bucket)
    for topic, buckets in by_topic.items():
        notes[f"Topics/{TOPICS[topic]['title']}.md"] = _render_topic_note(
            topic, buckets, managed_folder, library_folder)
    notes["00 - Local Library.md"] = _render_library_index(
        plan, managed_folder, library_folder, result["copied_bytes"])

    notes_state: dict[str, dict] = manifest["notes"]
    for relative, payload in notes.items():
        target = _safe_target(root, relative)
        digest = _sha256_bytes(payload)
        recorded = notes_state.get(relative)
        if target.exists():
            current = _sha256_bytes(target.read_bytes())
            if current == digest:
                notes_state[relative] = {"sha256": digest}
                result["notes_unchanged"] += 1
                continue
            if recorded is None or recorded.get("sha256") != current:
                result["conflicts"].append(relative)
                continue
        _atomic_write(target, payload)
        notes_state[relative] = {"sha256": digest}
        result["notes_written"] += 1

    manifest["duplicates"] = plan["duplicates"]
    manifest["importer"] = IMPORTER_VERSION
    manifest["schema_version"] = MANIFEST_SCHEMA_VERSION
    _atomic_write(manifest_path,
                  json.dumps(manifest, ensure_ascii=False, indent=2,
                             sort_keys=True).encode("utf-8"))
    return result


# ---------------------------------------------------------------------------
# BRD-021 — Chỉ mục tài liệu cục bộ CHỈ-ĐỌC
# Hợp đồng: contracts/local_document_index.schema.json
#
# Khác hẳn import_local_library(): KHÔNG copy byte nào. Chỉ ghi đường dẫn +
# siêu dữ liệu. Không suy ra bất kỳ con số kỹ thuật nào từ tên file — trường
# ``reason`` chỉ được liệt kê từ khóa đã khớp, không được diễn giải kỹ thuật.
# ---------------------------------------------------------------------------

INDEX_TOOL_VERSION = "local-document-index/1"
INDEX_SCHEMA_VERSION = 1
# Phạm vi do chủ dự án chốt; phải khớp enum ``extension`` của schema.
INDEX_EXTENSIONS: tuple[str, ...] = ("pdf", "dwg", "dxf", "xlsx", "xls", "xlsm")
INDEX_FULL_HASH_MAX_BYTES = 8 * 1024 * 1024
# Dải document_id của schema là DOC-00001..DOC-99999; vượt dải phải DỪNG chứ
# không được cắt bớt im lặng.
INDEX_MAX_DOCUMENTS = 99999
PARTIAL_HASH_NOTE = (
    "sha256 CHỈ tính trên 1 MiB đầu + 1 MiB cuối + kích thước file, không phải"
    " hash toàn bộ nội dung; dùng để định danh bản sao, KHÔNG dùng làm bằng"
    " chứng toàn vẹn."
)

# Tài liệu cá nhân bị loại khỏi chỉ mục dự án (BRD-021 safety note 2). Loại
# theo từ khóa đường dẫn và GHI LẠI lý do — không im lặng bỏ qua.
PERSONAL_KEYWORDS = (
    "cccd", "cmnd", "hộ khẩu", "ho khau", "sơ yếu lý lịch", "so yeu ly lich",
    "bảng lương", "bang luong", "payroll", "salary", "thuế thu nhập",
    "thue thu nhap", "quyết toán thuế", "quyet toan thue", "sao kê", "sao ke",
    "bank statement", "hợp đồng lao động", "hop dong lao dong",
    "giấy khai sinh", "giay khai sinh", "đăng ký kết hôn", "dang ky ket hon",
    "passport", "hộ chiếu", "ho chieu", "học bạ", "hoc ba", "bảo hiểm y tế",
    "bao hiem y te", "bhxh", "sổ đỏ", "giấy khám sức khỏe",
    "giay kham suc khoe", "bệnh án", "benh an",
)
MANUAL_KEYWORDS = (
    "user guide", "user manual", "userguide", "reference manual", "help.pdf",
    "hướng dẫn sử dụng", "huong dan su dung", "getting started",
    "verification manual", "midas", "sap2000", "csi bridge", "csibridge",
    "plaxis", "ansys", "abaqus", "autodesk help", "installation guide",
)
# Tiêu chuẩn nói TRỰC TIẾP tới mô hình runtime đang dùng.
BRIDGE_STANDARD_KEYWORDS = ("11823", "10304", "22tcn 272", "22tcn272",
                            "aashto", "lrfd")

# GỢI Ý liên kết runtime. Đây KHÔNG phải khẳng định kỹ thuật: chưa ai mở file
# để xác nhận, và schema ghi rõ trường này chưa được xác nhận.
RUNTIME_LINK_HINTS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("super-t", "supert", "super t"),
     "catalogs/catalogs.json::girder_sections (A, I, y_b hiện là PLACEHOLDER)"),
    (("11823",), "docs/design_basis/DB-SUPERT-38M.json::governing_standard"),
    (("10304",),
     "docs/design_basis/SITE-UNSPECIFIED.json (nền móng — runtime chưa có rule)"),
    (("dự ứng lực", "du ung luc", "prestress", "bó cáp", "bo cap", "tim cap",
      "tim cáp"),
     "bridge_evolution/verifier/rules.py::SERV-001"),
    (("hl-93", "hl93", "hoạt tải", "hoat tai", "tải trọng", "tai trong"),
     "bridge_evolution/fe_adapter/line_girder.py"),
    (("bản mặt cầu", "ban mat cau", "mặt cầu", "mat cau", "deck"),
     "bridge_evolution/geometry.py::check_geometry (deck_thickness_mm)"),
    (("mố", "trụ ", "pier", "abutment", "xà mũ", "xa mu", "gối cầu", "bearing",
      "cọc khoan", "coc khoan", "pile"),
     "docs/runtime_capability_matrix.json (cấu kiện ngoài phạm vi L1 line-girder)"),
    (("vòm", "arch"),
     "bridge_grammar/experimental/arch_deck_v1.json (sandbox IDEA, chưa có solver)"),
)


def _utc_stamp(epoch: float) -> str:
    """Định dạng đúng pattern utcTimestamp của schema (giây, hậu tố Z)."""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(max(0.0, epoch)))


def _matched(lowered: str, words: Iterable[str]) -> list[str]:
    return [word for word in words if word in lowered]


def _index_category(lowered: str, extension: str) -> str:
    """Loại tài liệu suy từ ĐUÔI FILE và từ khóa đường dẫn, không từ nội dung."""
    if extension in ("dwg", "dxf"):
        return "DRAWING"
    if extension in ("xlsx", "xls", "xlsm"):
        return "SPREADSHEET"
    if extension == "pdf":
        if _matched(lowered, STANDARD_KEYWORDS):
            return "STANDARD"
        if _matched(lowered, MANUAL_KEYWORDS):
            return "SOFTWARE_MANUAL"
        if _matched(lowered, COURSE_KEYWORDS):
            return "COURSE_MATERIAL"
        return "REPORT_PDF"
    return "UNKNOWN"


def _index_relevance(lowered: str) -> tuple[str, str, list[str]]:
    """Mức liên quan + lý do (chỉ liệt kê từ khóa khớp) + gợi ý runtime."""
    bridge = _matched(lowered, BRIDGE_KEYWORDS)
    bridge_standard = _matched(lowered, BRIDGE_STANDARD_KEYWORDS)
    adjacent = (_matched(lowered, PROJECT_KEYWORDS)
                + _matched(lowered, STANDARD_KEYWORDS)
                + _matched(lowered, ROAD_KEYWORDS)
                + _matched(lowered, BIM_KEYWORDS)
                + _matched(lowered, COURSE_KEYWORDS)
                + _matched(lowered, SCRIPT_KEYWORDS))

    links: list[str] = []
    for words, link in RUNTIME_LINK_HINTS:
        if _matched(lowered, words) and link not in links:
            links.append(link)

    if bridge or bridge_standard:
        hits = sorted(set(bridge + bridge_standard))
        return ("DIRECT",
                "khớp từ khóa cầu/tiêu chuẩn cầu trong đường dẫn: "
                + ", ".join(repr(item) for item in hits), links)
    if adjacent:
        hits = sorted(set(adjacent))
        return ("ADJACENT",
                "khớp từ khóa lân cận (dự án/tiêu chuẩn khác/đường/BIM/học liệu): "
                + ", ".join(repr(item) for item in hits), links)
    return ("UNRELATED",
            "không khớp từ khóa cầu, dự án, tiêu chuẩn, đường, BIM hay học liệu nào",
            links)


def _index_hash(path: Path, size: int,
                full_hash_max_bytes: int) -> tuple[str, bool]:
    """Hash đủ khi file đủ nhỏ; ngược lại hash một phần và BÁO rõ là một phần."""
    if size <= full_hash_max_bytes:
        return _full_hash(path), False
    digest = hashlib.sha256()
    with open(_long_path(path), "rb") as stream:
        digest.update(stream.read(QUICK_HASH_WINDOW))
        if size > 2 * QUICK_HASH_WINDOW:
            stream.seek(-QUICK_HASH_WINDOW, os.SEEK_END)
            digest.update(stream.read(QUICK_HASH_WINDOW))
    digest.update(str(size).encode("ascii"))
    return digest.hexdigest(), True


_FILE_ATTRIBUTE_REPARSE_POINT = 0x400


def _extended_root(root: Path) -> str:
    """Gốc duyệt LUÔN mang tiền tố mở rộng.

    ``_long_path`` chỉ thêm tiền tố khi bản thân chuỗi đã dài, nên thư mục con
    sâu vẫn bị MAX_PATH chặn giữa chừng và biến thành ``FileNotFoundError`` giả.
    Gắn tiền tố ngay từ gốc thì mọi hậu duệ đều thừa hưởng.
    """
    text = os.path.abspath(str(root))
    if os.name != "nt" or text.startswith("\\\\?\\"):
        return text
    if text.startswith("\\\\"):
        return "\\\\?\\UNC" + text[1:]
    return "\\\\?\\" + text


def _strip_extended(text: str) -> str:
    """Bỏ tiền tố mở rộng để chỉ mục ghi đường dẫn người dùng gõ được."""
    if text.startswith("\\\\?\\UNC\\"):
        return "\\\\" + text[8:]
    if text.startswith("\\\\?\\"):
        return text[4:]
    return text


def _is_reparse(path: Path) -> bool:
    """Junction/symlink dẫn tới vòng lặp và bản sao ảo — không đi vào.

    Không đọc được thuộc tính thì trả False: cắt nhánh vì một lỗi stat sẽ làm
    mất im lặng cả cây con, còn đi vào nhầm một junction chỉ tạo bản trùng mà
    ``seen_paths`` đã chặn.
    """
    try:
        if os.name != "nt":
            return os.path.islink(path)
        info = os.lstat(_long_path(path))
    except OSError:
        return False
    return bool(getattr(info, "st_file_attributes", 0)
                & _FILE_ATTRIBUTE_REPARSE_POINT)


def _vault_library_state(vault_dir, managed_folder: str,
                         library_folder: str) -> tuple[Path | None, dict, set[str]]:
    """Đọc manifest thư viện đã nhập: (vault, map source→hash, tập source đã có)."""
    try:
        vault = resolve_obsidian_vault(vault_dir)
        root = _managed_root(vault, f"{managed_folder}/{library_folder}")
    except (FileNotFoundError, ValueError, OSError):
        return None, {}, set()
    manifest = _load_manifest(root / LIBRARY_MANIFEST)
    known: dict[str, dict] = {}
    present: set[str] = set()
    for record in manifest.get("files", {}).values():
        source = record.get("source")
        if not source:
            continue
        key = os.path.normcase(os.path.normpath(source))
        present.add(key)
        known[key] = {"sha256": record.get("sha256", ""),
                      "size": record.get("size"),
                      "mtime": record.get("source_mtime")}
    for paths in manifest.get("duplicates", {}).values():
        for source in paths:
            present.add(os.path.normcase(os.path.normpath(source)))
    return vault, known, present


def build_document_index(
        roots: list[str | Path], *,
        vault_dir: str | Path | None = None,
        managed_folder: str = "DYLIGHT Bridge Evolution",
        library_folder: str = DEFAULT_LIBRARY_FOLDER,
        full_hash_max_bytes: int = INDEX_FULL_HASH_MAX_BYTES,
        exclude_roots: tuple[Path, ...] = (),
        reuse_vault_hashes: bool = True,
        use_vault: bool = True,
        progress: Callable[[str], None] | None = None,
        clock: Callable[[], float] | None = None) -> dict:
    """Lập chỉ mục CHỈ-ĐỌC tài liệu kỹ thuật cục bộ theo LocalDocumentIndex.

    Không copy, không di chuyển, không sửa, không xoá bất kỳ file nguồn nào.
    Với cùng một cây thư mục, ``documents`` phát ra là tất định (sắp xếp theo
    ổ đĩa rồi đường dẫn casefold); chỉ hai mốc thời gian quét là thay đổi.
    """
    tick = clock or time.time
    started = tick()

    root_paths: list[Path] = []
    for item in roots:
        candidate = Path(item)
        if not candidate.exists():
            raise FileNotFoundError(f"Gốc quét không tồn tại: {candidate}")
        root_paths.append(candidate)
    if not root_paths:
        raise ValueError("Cần ít nhất một gốc quét")

    vault: Path | None = None
    known_hashes: dict[str, dict] = {}
    in_vault: set[str] = set()
    if use_vault:
        vault, known_hashes, in_vault = _vault_library_state(
            vault_dir, managed_folder, library_folder)
    if not reuse_vault_hashes:
        known_hashes = {}
    # Vault chứa BẢN SAO của chính các file nguồn; quét nó sẽ nhân đôi chỉ mục.
    excluded = tuple(Path(item).resolve() for item in exclude_roots)
    if vault is not None:
        excluded = excluded + (vault.resolve(),)

    wanted = {f".{item}" for item in INDEX_EXTENSIONS}
    documents: list[dict] = []
    skipped: list[dict] = []
    unreadable: list[dict] = []
    scanned_files = 0
    seen_paths: set[str] = set()

    def _note_unreadable(path_text: str, reason: str) -> None:
        unreadable.append({"path": path_text, "reason": reason})

    for root in root_paths:
        def _on_error(error: OSError, _root=root) -> None:
            raw = str(getattr(error, "filename", None) or _root)
            _note_unreadable(_strip_extended(raw),
                             f"{type(error).__name__}: {error.strerror or error}")

        for dirpath, dirnames, filenames in os.walk(
                _extended_root(root), topdown=True, onerror=_on_error):
            # ``io_dir`` giữ tiền tố mở rộng để đọc được; ``shown`` là đường dẫn
            # ghi vào chỉ mục.
            io_dir = Path(dirpath)
            shown = Path(_strip_extended(dirpath))
            kept: list[str] = []
            for name in dirnames:
                child = shown / name
                if name.lower() in SKIP_DIR_NAMES or name.startswith("$"):
                    continue
                if any(_is_within(child, item) or child == item
                       for item in excluded):
                    continue
                if _is_reparse(io_dir / name):
                    _note_unreadable(
                        str(child),
                        "reparse point (symlink/junction) — không đi vào để"
                        " tránh vòng lặp và bản sao ảo")
                    continue
                kept.append(name)
            dirnames[:] = kept

            for filename in filenames:
                scanned_files += 1
                extension = os.path.splitext(filename)[1].lower()
                if extension not in wanted:
                    continue
                candidate = io_dir / filename
                path_text = str(shown / filename)
                key = os.path.normcase(os.path.normpath(path_text))
                if key in seen_paths:
                    continue
                seen_paths.add(key)
                lowered = path_text.lower()

                if filename.startswith("~$") or filename.startswith("."):
                    skipped.append({"path": path_text,
                                    "reason": "file tạm/khóa của ứng dụng"})
                    continue
                personal = _matched(lowered, PERSONAL_KEYWORDS)
                if personal:
                    skipped.append({
                        "path": path_text,
                        "reason": "loại khỏi chỉ mục dự án — khớp từ khóa tài"
                                  " liệu cá nhân: "
                                  + ", ".join(repr(w) for w in personal)})
                    continue
                try:
                    info = os.stat(_long_path(candidate))
                except OSError as error:
                    _note_unreadable(
                        path_text,
                        f"{type(error).__name__}: {error.strerror or error}")
                    continue
                if info.st_size == 0:
                    skipped.append({"path": path_text,
                                    "reason": "file rỗng (0 byte)"})
                    continue
                if info.st_size > MAX_FILE_BYTES:
                    skipped.append({
                        "path": path_text,
                        "reason": f"vượt giới hạn {MAX_FILE_BYTES} byte của bộ"
                                  " lập chỉ mục"})
                    continue

                recorded = known_hashes.get(key)
                digest = ""
                partial = False
                if (recorded and recorded.get("sha256")
                        and recorded.get("size") == info.st_size
                        and recorded.get("mtime") == int(info.st_mtime)):
                    digest = recorded["sha256"]
                else:
                    try:
                        digest, partial = _index_hash(
                            candidate, info.st_size, full_hash_max_bytes)
                    except OSError as error:
                        _note_unreadable(
                            path_text,
                            f"{type(error).__name__}: {error.strerror or error}"
                            " — không đọc được để hash (có thể bị khóa hoặc đặt"
                            " mật khẩu); KHÔNG tìm cách phá")
                        continue

                extension_name = extension.lstrip(".")
                category = _index_category(lowered, extension_name)
                relevance, reason, links = _index_relevance(lowered)
                drive = os.path.splitdrive(path_text)[0] or str(root)
                documents.append({
                    "document_id": "",
                    "path": path_text,
                    "drive": drive,
                    "filename": filename,
                    "extension": extension_name,
                    "size_bytes": info.st_size,
                    "sha256": digest,
                    "sha256_is_partial": partial,
                    "modified_utc": _utc_stamp(info.st_mtime),
                    "category": category,
                    "relevance": relevance,
                    "reason": reason,
                    "runtime_link": links,
                    "already_in_vault": key in in_vault,
                    "notes": PARTIAL_HASH_NOTE if partial else "",
                })
                if progress and len(documents) % 250 == 0:
                    progress(f"  lập chỉ mục {len(documents)} tài liệu"
                             f" / {scanned_files} file đã duyệt")
        if progress:
            progress(f"xong gốc {root}: {len(documents)} tài liệu,"
                     f" {scanned_files} file đã duyệt")

    documents.sort(key=lambda item: (item["drive"].casefold(),
                                     item["path"].casefold()))
    if len(documents) > INDEX_MAX_DOCUMENTS:
        raise ValueError(
            f"{len(documents)} tài liệu vượt dải document_id DOC-00001.."
            f"DOC-{INDEX_MAX_DOCUMENTS:05d} của schema; thu hẹp gốc quét rồi"
            " chạy lại")
    for position, document in enumerate(documents, start=1):
        document["document_id"] = f"DOC-{position:05d}"
    skipped.sort(key=lambda item: item["path"].casefold())
    unreadable.sort(key=lambda item: (item["path"].casefold(), item["reason"]))

    def _tally(field: str) -> dict[str, int]:
        counts: dict[str, int] = {}
        for document in documents:
            counts[document[field]] = counts.get(document[field], 0) + 1
        return dict(sorted(counts.items()))

    return {
        "schema_version": INDEX_SCHEMA_VERSION,
        "tool_version": INDEX_TOOL_VERSION,
        "scan_started_utc": _utc_stamp(started),
        "scan_finished_utc": _utc_stamp(tick()),
        "roots": [str(item) for item in roots],
        "extensions_included": sorted(INDEX_EXTENSIONS),
        "counts": {
            "total": len(documents),
            "scanned_files": scanned_files,
            "by_extension": _tally("extension"),
            "by_category": _tally("category"),
            "by_relevance": _tally("relevance"),
            "by_drive": _tally("drive"),
        },
        "documents": documents,
        "skipped": skipped,
        "unreadable": unreadable,
    }


def write_document_index(index: dict, path: str | Path) -> dict:
    """Ghi chỉ mục ra JSON UTF-8 nguyên tử; trả thống kê ngắn để in ra CLI."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(index, ensure_ascii=False, indent=1,
                         sort_keys=True).encode("utf-8")
    _atomic_write(target, payload)
    return {
        "output": str(target),
        "bytes": len(payload),
        "total": index["counts"]["total"],
        "scanned_files": index["counts"]["scanned_files"],
        "skipped": len(index["skipped"]),
        "unreadable": len(index["unreadable"]),
        "by_relevance": index["counts"]["by_relevance"],
        "by_category": index["counts"]["by_category"],
    }


README_RUNTIME_LINK_ROWS = 40


def _readme_table(title: str, counts: dict[str, int], total: int) -> list[str]:
    lines = [f"### {title}", "", "| Nhóm | Số tài liệu | Tỷ lệ |", "|---|---:|---:|"]
    for key, value in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
        share = f"{100.0 * value / total:.1f}%" if total else "—"
        lines.append(f"| `{key}` | {value} | {share} |")
    lines.append("")
    return lines


def render_library_readme(index: dict) -> str:
    """Sinh README của thư viện TỪ CHÍNH chỉ mục, để con số không trôi khỏi dữ liệu.

    Mọi con số trong README đều được đếm lại từ ``index``; không con số nào
    được gõ tay. Test ``test_readme_is_generated_from_the_index`` giữ file trên
    đĩa luôn khớp với hàm này.
    """
    counts = index["counts"]
    total = counts["total"]
    documents = index["documents"]
    linked = [item for item in documents if item["runtime_link"]]
    direct = [item for item in documents if item["relevance"] == "DIRECT"]
    in_vault = sum(1 for item in documents if item["already_in_vault"])
    partial = sum(1 for item in documents if item["sha256_is_partial"])
    total_bytes = sum(item["size_bytes"] for item in documents)

    lines: list[str] = [
        "# Chỉ mục thư viện tài liệu kỹ thuật cục bộ",
        "",
        "> ⚠ **ĐÂY LÀ THƯ VIỆN THAM KHẢO UNVERIFIED.** Theo `multiagent/PROTOCOL.md`",
        "> quy tắc 6, thư viện tham khảo **không phải bằng chứng kỹ thuật**. Sự tồn tại",
        "> của một bản vẽ hay một tài liệu trong bảng dưới đây KHÔNG chứng minh bất kỳ",
        "> con số nào. Muốn biến một điều trong đây thành rule của runtime thì phải mở",
        "> đúng tài liệu, dẫn đúng điều khoản, thêm test và có kỹ sư duyệt.",
        "",
        "> ⚠ **KHÔNG ĐƯỢC SUY SỐ LIỆU KỸ THUẬT TỪ TÊN FILE.** Trường `reason` chỉ ghi",
        "> lại từ khóa đã khớp trong đường dẫn; `runtime_link` chỉ là **gợi ý chưa ai",
        "> xác nhận**. Chưa file nào trong chỉ mục này được mở ra đọc.",
        "",
        "Task **BRD-021** · claim ceiling **IDEA** · hợp đồng",
        "`contracts/local_document_index.schema.json`.",
        "",
        "## Bản quyền và quyền riêng tư",
        "",
        "Chỉ mục ghi **vị trí và siêu dữ liệu** (đường dẫn, kích thước, sha256, ngày",
        "sửa). Nó **không sao chép nội dung** của bất kỳ tài liệu có bản quyền nào, và",
        "bộ quét **chỉ đọc**: không copy, không di chuyển, không đổi tên, không xoá,",
        "không giải mã file đặt mật khẩu. File khớp từ khóa tài liệu cá nhân bị loại",
        "khỏi chỉ mục dự án và chỉ để lại đường dẫn cùng lý do trong `skipped`.",
        "",
        "## Lần quét đang được ghi",
        "",
        "| Trường | Giá trị |",
        "|---|---|",
        f"| Bộ quét | `{index['tool_version']}` |",
        f"| Bắt đầu (UTC) | {index['scan_started_utc']} |",
        f"| Kết thúc (UTC) | {index['scan_finished_utc']} |",
        "| Gốc quét | "
        + ", ".join(f"`{item}`" for item in index["roots"]) + " |",
        "| Đuôi file trong phạm vi | "
        + ", ".join(f"`{item}`" for item in index["extensions_included"]) + " |",
        f"| File đã duyệt qua | {counts['scanned_files']} |",
        f"| **Tài liệu trong chỉ mục** | **{total}** |",
        f"| Tổng dung lượng tài liệu | {_human_bytes(total_bytes)} |",
        f"| Bị loại có ghi lý do | {len(index['skipped'])} |",
        f"| Không đọc được | {len(index['unreadable'])} |",
        f"| Đã có bản sao trong vault Obsidian | {in_vault} |",
        f"| sha256 chỉ là một phần (file lớn) | {partial} |",
        "",
    ]

    lines += _readme_table("Theo mức liên quan tới runtime",
                           counts["by_relevance"], total)
    lines += _readme_table("Theo loại tài liệu", counts["by_category"], total)
    lines += _readme_table("Theo đuôi file", counts["by_extension"], total)
    lines += _readme_table("Theo ổ đĩa", counts["by_drive"], total)

    lines += [
        "## Tài liệu có gợi ý chạm tới runtime",
        "",
        f"{len(linked)}/{total} tài liệu có ít nhất một `runtime_link`;"
        f" {len(direct)} tài liệu ở mức `DIRECT`.",
        "",
        "**`runtime_link` là gợi ý theo từ khóa, chưa ai mở file để xác nhận.**",
        "Nó chỉ nói \"chỗ này trong repo có thể liên quan\", không nói tài liệu chứa",
        "số dùng được.",
        "",
    ]
    if linked:
        lines += ["| document_id | File | Gợi ý runtime |", "|---|---|---|"]
        for item in linked[:README_RUNTIME_LINK_ROWS]:
            links = "<br>".join(f"`{link}`" for link in item["runtime_link"])
            lines.append(f"| `{item['document_id']}` |"
                         f" {_md_escape(item['filename'])} | {links} |")
        lines.append("")
        if len(linked) > README_RUNTIME_LINK_ROWS:
            lines += [
                f"> Bảng trên chỉ liệt kê {README_RUNTIME_LINK_ROWS} dòng đầu theo"
                f" `document_id`; còn **{len(linked) - README_RUNTIME_LINK_ROWS}**"
                " tài liệu có `runtime_link` nữa nằm trong `index.json`. Không dòng"
                " nào bị cắt im lặng.",
                "",
            ]

    lines += [
        "## Dựng lại chỉ mục",
        "",
        "```python",
        "from bridge_evolution.knowledge import local_library as lib",
        "",
        "index = lib.build_document_index("
        + ", ".join(repr(item) for item in index["roots"]).join(["[", "]"])
        + ")",
        "lib.write_document_index(index, \"research/library/index.json\")",
        "open(\"research/library/README.md\", \"w\", encoding=\"utf-8\")"
        ".write(lib.render_library_readme(index))",
        "```",
        "",
        "Chạy lại trên cùng cây thư mục cho cùng `documents`; chỉ hai mốc thời gian",
        "quét thay đổi. Chỉ mục **chưa** có lệnh CLI riêng: `bridge_evolution/cli.py`",
        "nằm ngoài `write_scope` của BRD-021, nên việc mở lệnh phải là một task khác.",
        "",
        "## Cái chỉ mục này KHÔNG làm",
        "",
        "- Không mở, không đọc nội dung, không OCR, không trích số từ bản vẽ.",
        "- Không nâng bất kỳ claim nào. Trần claim toàn dự án vẫn là `SCREENED`;",
        "  riêng thư viện tham khảo này ở mức `IDEA`.",
        "- Không sửa `catalogs/`. Các giá trị `A`, `I`, `y_b` của tiết diện Super-T",
        "  vẫn là PLACEHOLDER cho tới khi một kỹ sư mở đúng bản vẽ và ký xác nhận.",
        "",
    ]
    return "\n".join(lines).rstrip("\n") + "\n"
