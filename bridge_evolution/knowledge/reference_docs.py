"""Nhập bộ PDF TCVN 11823:2017 vào vùng Standards của Obsidian.

PDF được giữ nguyên byte; Markdown chỉ chứa metadata, mục lục chuẩn hóa và liên
kết. Nội dung tài liệu là dữ liệu tham khảo, không phải lệnh thực thi và không
tự thay đổi solver/verifier/ruleset.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any

from .obsidian import (_managed_root, _safe_target, _yaml_value,
                       resolve_obsidian_vault)
from .store import load_cards
from .taxonomy import (cards_for_standard, rules_for_standard,
                       variables_for_standard)

IMPORTER_VERSION = "tcvn-pdf-import/2"
REFERENCE_MANIFEST = ".dylight-reference-manifest.json"
DEFAULT_COLLECTION_FOLDER = "Standards/TCVN 11823-2017"
MAX_PDF_BYTES = 100 * 1024 * 1024

TCVN_PARTS: dict[int, dict[str, Any]] = {
    1: {
        "title": "Yêu cầu chung",
        "topics": ["Phạm vi và thuật ngữ", "Triết lý thiết kế",
                   "Các trạng thái giới hạn", "Tính dẻo, tính dư và tầm quan trọng"],
        "relevance": "Nền tảng LRFD và trạng thái giới hạn cho toàn bộ verifier.",
    },
    2: {
        "title": "Tổng thể và đặc điểm vị trí cầu",
        "topics": ["Đặc trưng và bố trí vị trí cầu", "Tĩnh không và môi trường",
                   "Khảo sát móng", "Yêu cầu cơ bản đối với thiết kế",
                   "Thủy văn, thủy lực và xói"],
        "relevance": "Đầu vào hình học, bố trí tổng thể và các gate khảo sát dự án.",
    },
    3: {
        "title": "Tải trọng và hệ số tải trọng",
        "topics": ["Hệ số và tổ hợp tải trọng", "Tĩnh tải DC, DW, EV",
                   "Hoạt tải LL, PL và xung kích IM", "Gió, nước và động đất",
                   "Áp lực đất, biến dạng cưỡng bức và va tàu"],
        "relevance": "Nguồn tham khảo cốt lõi cho load model, tổ hợp và HL-93 của L1/L2.",
    },
    4: {
        "title": "Phân tích và đánh giá kết cấu",
        "topics": ["Phương pháp phân tích được chấp nhận", "Mô hình toán học",
                   "Phân tích tĩnh", "Phân bố tải bản-dầm",
                   "Phân tích động lực và mô hình vật lý"],
        "relevance": "Ranh giới mô hình L1 và cơ sở nâng cấp/đối chiếu L2 Midas.",
    },
    5: {
        "title": "Kết cấu bê tông",
        "topics": ["Tính chất vật liệu và trạng thái giới hạn",
                   "Uốn và lực dọc trục", "Cắt và xoắn", "Dự ứng lực",
                   "Chi tiết cốt thép, độ bền và cấu kiện đặc biệt"],
        "relevance": "Nguồn tham khảo cốt lõi cho dầm Super-T, bản mặt cầu và prestress.",
    },
    6: {
        "title": "Kết cấu thép",
        "topics": ["Vật liệu và trạng thái giới hạn", "Mỏi và nứt gãy",
                   "Cấu kiện kéo/nén/uốn", "Mặt cắt I và hộp",
                   "Liên kết, mối nối và cọc thép"],
        "relevance": "Tham khảo cho cấu kiện/phụ kiện thép và các family cầu thép tương lai.",
    },
    9: {
        "title": "Mặt cầu và hệ mặt cầu",
        "topics": ["Yêu cầu thiết kế chung", "Các trạng thái giới hạn",
                   "Phân tích mặt cầu", "Bản mặt cầu bê tông", "Mặt cầu kim loại"],
        "relevance": "Liên quan trực tiếp deck slab, phân bố tải và kiểm tra bản mặt cầu.",
    },
    10: {
        "title": "Nền móng",
        "topics": ["Đặc tính đất đá", "Trạng thái giới hạn và hệ số sức kháng",
                   "Móng nông", "Cọc đóng", "Cọc khoan và cọc siêu nhỏ"],
        "relevance": "Nguồn cho module nền móng/L2 tương lai; chưa được mô hình L1 hiện tại dùng.",
    },
    11: {
        "title": "Mố, trụ và tường chắn",
        "topics": ["Tính chất đất và vật liệu", "Trạng thái giới hạn",
                   "Mố và tường chắn thông thường", "Trụ cầu",
                   "Tường hẫng, tường neo, MSE và tường mô-đun"],
        "relevance": "Nguồn cho substructure và tương tác đất-kết cấu; ngoài phạm vi L1 hiện tại.",
    },
    12: {
        "title": "Kết cấu vùi và áo hầm",
        "topics": ["Đất, vật liệu và trạng thái giới hạn", "Quy định thiết kế chung",
                   "Cống kim loại và kết cấu bản mỏng", "Cống/hộp bê tông cốt thép",
                   "Ống nhựa, áo hầm và cấu kiện đúc sẵn"],
        "relevance": "Nguồn tham khảo ngoài family cầu Super-T hiện tại.",
    },
    13: {
        "title": "Lan can",
        "topics": ["Vật liệu và trạng thái giới hạn", "Lan can đường ô tô",
                   "Cấp thử nghiệm và thiết kế", "Lan can người đi bộ/xe đạp",
                   "Lan can kết hợp, bó vỉa và lề đi bộ"],
        "relevance": "Nguồn cho tải/phụ kiện biên và safety system của mô hình mở rộng.",
    },
    14: {
        "title": "Khe co giãn và gối cầu",
        "topics": ["Chuyển vị và tải trọng", "Khe co giãn cầu",
                   "Gối PTFE, mặt trượt cong, gối chậu và gối đĩa",
                   "Gối chất dẻo phương pháp A/B", "Dẫn hướng, neo và chống ăn mòn"],
        "relevance": "Nguồn cho boundary conditions, chuyển vị, gối và chi tiết liên kết.",
    },
}

_PART_PATTERN = re.compile(
    r"TCVN\s*11823\s*-\s*(\d+)\s*:\s*2017", re.IGNORECASE)
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _extract_standard_part(first_page_text: str) -> int:
    match = _PART_PATTERN.search(first_page_text)
    if not match:
        raise ValueError("Không tìm thấy số hiệu TCVN 11823-<part>:2017 trên trang bìa")
    return int(match.group(1))


def _inspect_pdf(path: Path) -> dict:
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - CI/dev extra luôn có pypdf
        raise RuntimeError(
            "Cần cài extra PDF: python -m pip install -e '.[pdf]'") from exc
    if path.stat().st_size > MAX_PDF_BYTES:
        raise ValueError(f"PDF vượt giới hạn {MAX_PDF_BYTES} bytes: {path.name}")
    try:
        reader = PdfReader(path, strict=False)
        if reader.is_encrypted and reader.decrypt("") == 0:
            raise ValueError(f"PDF có mật khẩu: {path.name}")
        pages = len(reader.pages)
        first_text = reader.pages[0].extract_text() or "" if pages else ""
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(f"PDF không đọc được: {path.name}") from exc
    if pages < 1:
        raise ValueError(f"PDF không có trang: {path.name}")
    part = _extract_standard_part(first_text)
    if part not in TCVN_PARTS:
        raise ValueError(f"TCVN 11823-{part}:2017 chưa có metadata curated")
    raw = path.read_bytes()
    return {
        "part": part,
        "pages": pages,
        "source_filename": path.name,
        "source_sha256": _sha256(raw),
        "size_bytes": len(raw),
        "text_layer": len(first_text.strip()) >= 100,
        "raw": raw,
    }


def _vault_path(managed_folder: str, collection_folder: str,
                relative: str) -> str:
    return "/".join(part.strip("/\\") for part in (
        managed_folder, collection_folder, relative) if part)


def _render_part_note(info: dict, managed_folder: str,
                      collection_folder: str, cards: list[dict]) -> str:
    part = info["part"]
    meta = TCVN_PARTS[part]
    pdf_name = f"TCVN 11823-{part}-2017.pdf"
    pdf_link = _vault_path(managed_folder, collection_folder, f"PDF/{pdf_name}")
    tags = ["dylight/standard", "dylight/tcvn-11823", f"dylight/tcvn-part-{part}"]
    lines = [
        "---",
        f"dylight_kind: {_yaml_value('standard-reference')}",
        "dylight_schema_version: 1",
        f"standard_id: {_yaml_value(f'TCVN 11823-{part}:2017')}",
        f"standard_part: {part}",
        f"standard_title: {_yaml_value(meta['title'])}",
        f"reference_status: {_yaml_value('LOCAL_COPY_UNVERIFIED_OFFICIAL_SOURCE')}",
        f"pages: {info['pages']}",
        f"text_layer: {_yaml_value(info['text_layer'])}",
        f"source_filename: {_yaml_value(info['source_filename'])}",
        f"source_sha256: {_yaml_value(info['source_sha256'])}",
        f"tags: {_yaml_value(tags)}",
        f"cssclasses: {_yaml_value(['dylight-note', 'dylight-standard'])}",
        "---",
        "",
        f"# TCVN 11823-{part}:2017 - {meta['title']}",
        "",
        "> [!IMPORTANT] Nguồn tham khảo, không phải rule thực thi",
        "> Việc lưu tài liệu trong Brain 2 không tự thay đổi solver, verifier hoặc"
        " ruleset. Khi dùng phải dẫn đúng điều/khoản và được kỹ sư kiểm tra.",
        "",
        "> [!WARNING] Provenance",
        "> Đây là bản PDF cục bộ do người dùng cung cấp; hash đã được ghi nhưng"
        " chưa đối chiếu với bản phát hành từ cơ quan tiêu chuẩn.",
        "",
        "## Nội dung chính",
        "",
    ]
    lines.extend(f"- {topic}" for topic in meta["topics"])
    related_rules = rules_for_standard(part)
    related_variables = variables_for_standard(part)
    related_cards = cards_for_standard(cards, part)
    rule_links = ", ".join(
        f"[[{managed_folder}/Rules/{rule_id}|{rule_id}]]"
        for rule_id in related_rules) or "—"
    variable_links = ", ".join(
        f"[[{managed_folder}/Variables/{name}|{name}]]"
        for name in related_variables) or "—"
    card_links = ", ".join(
        f"[[{managed_folder}/Cards/{card_id}|{card_id}]]"
        for card_id in related_cards) or "—"
    lines.extend([
        "",
        "## Liên kết Brain 2",
        "",
        f"- **Rules:** {rule_links}",
        f"- **Variables:** {variable_links}",
        f"- **Knowledge cards:** {card_links}",
        "",
        "## Liên quan tới DYLIGHT",
        "",
        meta["relevance"],
        "",
        "## Chất lượng số hóa",
        "",
        f"- Số trang: **{info['pages']}**",
        f"- Có lớp chữ chọn được: **{'Có' if info['text_layer'] else 'Không/không chắc'}**",
        "- Text extraction tiếng Việt có thể bị chèn khoảng trắng giữa ký tự;"
        " note này dùng mục lục curated thay vì chép raw text.",
        "",
        "## Provenance",
        "",
        f"- File nguồn: `{info['source_filename']}`",
        f"- SHA-256: `{info['source_sha256']}`",
        f"- Kích thước: `{info['size_bytes']}` bytes",
        f"- Importer: `{IMPORTER_VERSION}`",
        "",
        "## PDF nguyên bản",
        "",
        f"![[{pdf_link}]]",
        "",
    ])
    return "\n".join(lines)


def _render_index(infos: list[dict], managed_folder: str,
                  collection_folder: str) -> str:
    parts = [info["part"] for info in infos]
    total_pages = sum(info["pages"] for info in infos)
    total_bytes = sum(info["size_bytes"] for info in infos)
    missing = [part for part in range(1, 15) if part not in parts]
    collection_hash = _sha256("\n".join(
        f"{info['part']}:{info['source_sha256']}" for info in infos).encode("ascii"))
    lines = [
        "---",
        f"dylight_kind: {_yaml_value('standard-collection')}",
        "dylight_schema_version: 1",
        f"collection_id: {_yaml_value('TCVN-11823-2017')}",
        f"document_count: {len(infos)}",
        f"total_pages: {total_pages}",
        f"collection_sha256: {_yaml_value(collection_hash)}",
        f"tags: {_yaml_value(['dylight/standard', 'dylight/tcvn-11823', 'dylight/index'])}",
        f"cssclasses: {_yaml_value(['dylight-note', 'dylight-standard', 'dylight-standard-index'])}",
        "---",
        "",
        "# TCVN 11823:2017 - Thiết kế cầu đường bộ",
        "",
        "> [!IMPORTANT] Phạm vi sử dụng",
        "> Bộ PDF là nguồn tham khảo cho Brain 2. Không nội dung nào tự trở thành"
        " hard rule; mọi ánh xạ sang code cần trích điều/khoản, test và duyệt kỹ sư.",
        "",
        "## Tổng quan bộ cục bộ",
        "",
        f"- Tệp PDF: **{len(infos)}**",
        f"- Tổng số trang: **{total_pages}**",
        f"- Tổng dung lượng: **{total_bytes / (1024 * 1024):.2f} MiB**",
        f"- Các phần có trong thư mục nguồn: **{', '.join(map(str, parts))}**",
        f"- Không có tệp mang số phần: **{', '.join(map(str, missing)) or 'không'}**",
        f"- Collection SHA-256: `{collection_hash}`",
        "",
        "> [!CAUTION] Tên file tải xuống không đồng nhất với số phần tiêu chuẩn",
        "> `part07` và `part08` trên tên file lần lượt là TCVN phần 9 và 10;"
        " importer nhận dạng từ trang bìa, không dùng hậu tố filename.",
        "",
        "## Danh mục",
        "",
        "| Phần | Nội dung | Trang | Mức liên quan | Note | PDF | SHA-256 |",
        "|---:|---|---:|---|---|---|---|",
    ]
    for info in infos:
        part = info["part"]
        meta = TCVN_PARTS[part]
        note_name = f"TCVN 11823-{part}-2017 - {meta['title']}"
        note_link = _vault_path(
            managed_folder, collection_folder, f"Parts/{note_name}")
        pdf_link = _vault_path(
            managed_folder, collection_folder, f"PDF/TCVN 11823-{part}-2017.pdf")
        lines.append(
            f"| {part} | {meta['title']} | {info['pages']} | {meta['relevance']} |"
            f" [[{note_link}|Mở note]] | [[{pdf_link}|Mở PDF]] |"
            f" `{info['source_sha256'][:12]}...` |")
    lines.extend([
        "",
        "## Ghi chú tìm kiếm",
        "",
        "Các PDF đều có lớp chữ, nhưng extraction có khoảng trắng bất thường trong"
        " từ tiếng Việt. Hãy tìm theo số điều/khoản hoặc dùng mục lục curated trong"
        " từng note; chỉ OCR chọn lọc trang sơ đồ/bản đồ khi thật sự cần.",
        "",
    ])
    return "\n".join(lines)


def _load_manifest(path: Path, root: Path) -> dict:
    if not path.exists():
        return {"schema_version": 1, "files": {}}
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("Reference manifest không đọc được") from exc
    if manifest.get("schema_version") != 1 or not isinstance(manifest.get("files"), dict):
        raise ValueError("Reference manifest sai schema")
    for relative, digest in manifest["files"].items():
        _safe_target(root, relative)
        if not isinstance(digest, str) or not _SHA256_PATTERN.fullmatch(digest):
            raise ValueError("Reference manifest có SHA-256 sai")
    return manifest


def import_tcvn_collection(
        source_dir: str | Path, vault_dir: str | Path | None = None, *,
        managed_folder: str = "DYLIGHT Bridge Evolution",
        collection_folder: str = DEFAULT_COLLECTION_FOLDER,
        dry_run: bool = False) -> dict:
    """Copy PDF nguyên bản + note curated vào Obsidian, không ghi đè conflict."""
    source = Path(source_dir).expanduser()
    if not source.is_dir():
        raise FileNotFoundError(f"Thư mục PDF không tồn tại: {source}")
    paths = sorted(path for path in source.glob("*.pdf") if path.is_file())
    if not paths:
        raise FileNotFoundError(f"Không có PDF trong: {source}")

    infos = [_inspect_pdf(path) for path in paths]
    infos.sort(key=lambda item: item["part"])
    parts = [info["part"] for info in infos]
    if len(parts) != len(set(parts)):
        duplicates = sorted({part for part in parts if parts.count(part) > 1})
        raise ValueError(f"Trùng số phần TCVN: {duplicates}")
    cards = load_cards()

    vault = resolve_obsidian_vault(vault_dir)
    managed_root = _managed_root(vault, managed_folder)
    collection_root = _safe_target(managed_root, collection_folder)
    manifest_path = _safe_target(collection_root, REFERENCE_MANIFEST)
    old_manifest = (_load_manifest(manifest_path, collection_root)
                    if manifest_path.exists() else {"schema_version": 1, "files": {}})
    old_files = dict(old_manifest.get("files", {}))

    outputs: dict[str, bytes] = {
        "00 - TCVN 11823-2017.md": (
            _render_index(infos, managed_folder, collection_folder) + "\n").encode("utf-8")
    }
    documents = {}
    for info in infos:
        part = info["part"]
        meta = TCVN_PARTS[part]
        pdf_relative = f"PDF/TCVN 11823-{part}-2017.pdf"
        note_relative = f"Parts/TCVN 11823-{part}-2017 - {meta['title']}.md"
        outputs[pdf_relative] = info["raw"]
        outputs[note_relative] = (
            _render_part_note(info, managed_folder, collection_folder, cards)
            + "\n").encode("utf-8")
        documents[str(part)] = {
            "pages": info["pages"],
            "pdf": pdf_relative,
            "note": note_relative,
            "source_filename": info["source_filename"],
            "source_sha256": info["source_sha256"],
        }

    planned_writes: list[str] = []
    unchanged: list[str] = []
    conflicts: list[str] = []
    desired_hashes = {relative: _sha256(data) for relative, data in outputs.items()}
    for relative, desired_hash in sorted(desired_hashes.items()):
        target = _safe_target(collection_root, relative)
        current_hash = _sha256(target.read_bytes()) if target.is_file() else None
        if current_hash == desired_hash:
            unchanged.append(relative)
        elif current_hash is not None and old_files.get(relative) != current_hash:
            conflicts.append(relative)
        else:
            planned_writes.append(relative)

    stale = sorted(set(old_files) - set(outputs))
    written: list[str] = []
    manifest_changed = False
    if not conflicts and not dry_run:
        for relative in planned_writes:
            _atomic_write(_safe_target(collection_root, relative), outputs[relative])
            written.append(relative)
        manifest = {
            "schema_version": 1,
            "importer_version": IMPORTER_VERSION,
            "collection_id": "TCVN-11823-2017",
            "collection_folder": collection_folder.replace("\\", "/"),
            "files": dict(sorted(desired_hashes.items())),
            "documents": documents,
        }
        manifest_bytes = (json.dumps(
            manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
        manifest_changed = (not manifest_path.is_file()
                            or manifest_path.read_bytes() != manifest_bytes)
        if manifest_changed:
            _atomic_write(manifest_path, manifest_bytes)
    elif not conflicts:
        manifest_changed = bool(planned_writes or stale or not manifest_path.is_file())

    return {
        "vault": str(vault),
        "managed_folder": managed_folder.replace("\\", "/"),
        "collection_folder": collection_folder.replace("\\", "/"),
        "documents": len(infos),
        "parts": parts,
        "total_pages": sum(info["pages"] for info in infos),
        "total_bytes": sum(info["size_bytes"] for info in infos),
        "planned_writes": planned_writes,
        "written": written,
        "unchanged": unchanged,
        "conflicts": conflicts,
        "stale_not_deleted": stale,
        "manifest_changed": manifest_changed,
        "dry_run": dry_run,
    }


__all__ = ["TCVN_PARTS", "import_tcvn_collection"]
