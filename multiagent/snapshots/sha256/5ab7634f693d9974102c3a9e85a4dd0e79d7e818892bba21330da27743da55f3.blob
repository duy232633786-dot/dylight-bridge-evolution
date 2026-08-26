"""BRD-021 — chỉ mục tài liệu cục bộ CHỈ-ĐỌC.

Bốn tính chất phải giữ được, vì nếu mất thì chỉ mục thành nguồn sai lệch:

1. Chỉ ĐỌC — không file nguồn nào bị đổi nội dung, mtime hay bị thêm/bớt.
2. Chỉ SIÊU DỮ LIỆU — không byte nội dung nào lọt vào chỉ mục.
3. TÁI LẬP — chạy lại trên cùng cây thư mục cho cùng ``documents``.
4. FAIL-CLOSED có ghi nhận — file bị loại và file không đọc được đều phải để
   lại dấu vết kèm lý do, không được im lặng biến mất.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import jsonschema
import pytest

from bridge_evolution.knowledge import local_library as lib

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "contracts" / \
    "local_document_index.schema.json"


def _validator() -> jsonschema.Draft202012Validator:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    return jsonschema.Draft202012Validator(schema)


def _write(path: Path, payload: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return path


@pytest.fixture()
def tree(tmp_path: Path) -> Path:
    """Cây thư mục mẫu phủ mọi nhánh phân loại và mọi nhánh bị loại."""
    root = tmp_path / "kho"
    _write(root / "Cầu Super-T" / "Section Super T 38.2m.dwg", b"DWG" * 40)
    _write(root / "Cầu Super-T" / "TIM CAP DUL.dwg", b"CAP" * 40)
    _write(root / "Tiêu chuẩn" / "TCVN 11823-5-2017.pdf", b"%PDF-standard")
    _write(root / "Khoá học" / "Bài giảng cầu bê tông.pdf", b"%PDF-course")
    _write(root / "Phần mềm" / "Midas Civil user guide.pdf", b"%PDF-manual")
    _write(root / "Dự toán" / "THKL cầu.xlsx", b"XLSX-payload")
    _write(root / "Linh tinh" / "ghi chú lặt vặt.pdf", b"%PDF-misc")
    # Ngoài phạm vi đuôi file: phải được đếm vào scanned_files nhưng KHÔNG
    # được xuất hiện trong documents.
    _write(root / "Linh tinh" / "mô hình.rvt", b"RVT")
    _write(root / "Linh tinh" / "ghi chép.docx", b"DOCX")
    # Các nhánh bị loại có ghi nhận.
    _write(root / "Cá nhân" / "Bảng lương 2026.xlsx", b"PRIVATE")
    _write(root / "Cầu Super-T" / "~$Section Super T 38.2m.dwg", b"LOCK")
    _write(root / "Cầu Super-T" / "rỗng.dwg", b"")
    return root


def _index(tree: Path, **kwargs) -> dict:
    kwargs.setdefault("use_vault", False)
    return lib.build_document_index([tree], **kwargs)


def _by_name(index: dict, filename: str) -> dict:
    matches = [item for item in index["documents"] if item["filename"] == filename]
    assert len(matches) == 1, f"{filename}: {len(matches)} kết quả"
    return matches[0]


# --- 1. hợp đồng schema ------------------------------------------------------

def test_index_validates_against_contract(tree):
    errors = sorted(_validator().iter_errors(_index(tree)),
                    key=lambda error: error.path)
    assert errors == [], [f"{list(e.path)}: {e.message}" for e in errors]


def test_document_ids_are_dense_and_ordered(tree):
    documents = _index(tree)["documents"]
    assert [item["document_id"] for item in documents] == [
        f"DOC-{position:05d}" for position in range(1, len(documents) + 1)]
    keys = [(item["drive"].casefold(), item["path"].casefold())
            for item in documents]
    assert keys == sorted(keys)


def test_only_contract_extensions_are_indexed(tree):
    index = _index(tree)
    assert set(index["extensions_included"]) == set(lib.INDEX_EXTENSIONS)
    assert {item["extension"] for item in index["documents"]} <= \
        set(lib.INDEX_EXTENSIONS)
    indexed = {item["filename"] for item in index["documents"]}
    assert "mô hình.rvt" not in indexed
    assert "ghi chép.docx" not in indexed


def test_counts_agree_with_document_list(tree):
    index = _index(tree)
    documents = index["documents"]
    counts = index["counts"]
    assert counts["total"] == len(documents)
    # scanned_files đếm MỌI file đã duyệt, kể cả ngoài phạm vi đuôi.
    assert counts["scanned_files"] == 12
    assert counts["scanned_files"] > counts["total"]
    for field, key in (("extension", "by_extension"),
                       ("category", "by_category"),
                       ("relevance", "by_relevance"),
                       ("drive", "by_drive")):
        tally: dict[str, int] = {}
        for item in documents:
            tally[item[field]] = tally.get(item[field], 0) + 1
        assert counts[key] == tally
        assert sum(counts[key].values()) == counts["total"]


# --- 2. chỉ đọc, chỉ siêu dữ liệu -------------------------------------------

def test_scan_does_not_touch_source_files(tree):
    before = {path: (path.stat().st_size, path.stat().st_mtime_ns,
                     hashlib.sha256(path.read_bytes()).hexdigest())
              for path in sorted(tree.rglob("*")) if path.is_file()}
    _index(tree)
    after = {path: (path.stat().st_size, path.stat().st_mtime_ns,
                    hashlib.sha256(path.read_bytes()).hexdigest())
             for path in sorted(tree.rglob("*")) if path.is_file()}
    assert after == before


def test_index_carries_no_file_content(tree):
    marker = b"NOI-DUNG-BI-MAT-KHONG-DUOC-VAO-CHI-MUC"
    _write(tree / "Cầu Super-T" / "bí mật.pdf", b"%PDF " + marker)
    payload = json.dumps(_index(tree), ensure_ascii=False)
    assert marker.decode() not in payload
    assert "XLSX-payload" not in payload


def test_hash_is_full_for_small_files_and_flagged_when_partial(tree):
    drawing = tree / "Cầu Super-T" / "Section Super T 38.2m.dwg"
    document = _by_name(_index(tree), drawing.name)
    assert document["sha256_is_partial"] is False
    assert document["sha256"] == hashlib.sha256(drawing.read_bytes()).hexdigest()
    assert document["notes"] == ""

    partial = _by_name(_index(tree, full_hash_max_bytes=1), drawing.name)
    assert partial["sha256_is_partial"] is True
    assert partial["sha256"] != document["sha256"]
    # Schema bắt buộc notes không rỗng khi hash chỉ là một phần.
    assert partial["notes"].strip()


# --- 3. tái lập --------------------------------------------------------------

def test_repeat_scan_reproduces_identical_documents(tree):
    first = _index(tree)
    second = _index(tree)
    assert first["documents"] == second["documents"]
    assert first["skipped"] == second["skipped"]
    assert first["counts"] == second["counts"]


def test_scan_timestamps_are_recorded_and_ordered(tree):
    ticks = iter([1_780_000_000.0, 1_780_000_050.0])
    index = _index(tree, clock=lambda: next(ticks))
    assert index["scan_started_utc"] == "2026-05-28T20:26:40Z"
    assert index["scan_finished_utc"] == "2026-05-28T20:27:30Z"
    assert index["scan_started_utc"] <= index["scan_finished_utc"]


def test_roots_are_recorded_verbatim(tmp_path, tree):
    index = lib.build_document_index([str(tree)], use_vault=False)
    assert index["roots"] == [str(tree)]
    with pytest.raises(FileNotFoundError):
        lib.build_document_index([tmp_path / "khong-ton-tai"], use_vault=False)


# --- 4. fail-closed có ghi nhận ---------------------------------------------

def test_personal_documents_are_excluded_with_a_recorded_reason(tree):
    index = _index(tree)
    assert "Bảng lương 2026.xlsx" not in {item["filename"]
                                         for item in index["documents"]}
    entry = next(item for item in index["skipped"]
                 if item["path"].endswith("Bảng lương 2026.xlsx"))
    assert "cá nhân" in entry["reason"]
    assert "bảng lương" in entry["reason"]


def test_empty_and_lock_files_are_skipped_with_reasons(tree):
    skipped = {Path(item["path"]).name: item["reason"]
               for item in _index(tree)["skipped"]}
    assert "0 byte" in skipped["rỗng.dwg"]
    assert "tạm" in skipped["~$Section Super T 38.2m.dwg"]


def test_unreadable_file_is_recorded_not_silently_dropped(tree, monkeypatch):
    target = tree / "Cầu Super-T" / "TIM CAP DUL.dwg"
    real_hash = lib._full_hash

    def _explode(path: Path) -> str:
        if Path(path).name == target.name:
            raise PermissionError(13, "Access is denied", str(path))
        return real_hash(path)

    monkeypatch.setattr(lib, "_full_hash", _explode)
    index = _index(tree)
    assert target.name not in {item["filename"] for item in index["documents"]}
    entry = next(item for item in index["unreadable"]
                 if item["path"].endswith(target.name))
    assert "PermissionError" in entry["reason"]
    assert _validator().iter_errors(index) is not None
    assert list(_validator().iter_errors(index)) == []


def test_skip_dir_names_are_not_walked(tree):
    _write(tree / "node_modules" / "vendor.pdf", b"%PDF-vendor")
    _write(tree / "$RECYCLE.BIN" / "deleted.dwg", b"DWG")
    indexed = {item["filename"] for item in _index(tree)["documents"]}
    assert "vendor.pdf" not in indexed
    assert "deleted.dwg" not in indexed


# --- phân loại và liên kết runtime -------------------------------------------

@pytest.mark.parametrize("filename,category", [
    ("Section Super T 38.2m.dwg", "DRAWING"),
    ("THKL cầu.xlsx", "SPREADSHEET"),
    ("TCVN 11823-5-2017.pdf", "STANDARD"),
    ("Bài giảng cầu bê tông.pdf", "COURSE_MATERIAL"),
    ("Midas Civil user guide.pdf", "SOFTWARE_MANUAL"),
    ("ghi chú lặt vặt.pdf", "REPORT_PDF"),
])
def test_category_follows_extension_then_path_keywords(tree, filename, category):
    assert _by_name(_index(tree), filename)["category"] == category


def test_relevance_reason_only_quotes_matched_keywords(tree):
    document = _by_name(_index(tree), "Section Super T 38.2m.dwg")
    assert document["relevance"] == "DIRECT"
    assert "'super-t'" in document["reason"] and "'cầu'" in document["reason"]
    # Lý do là bằng chứng khớp chuỗi, KHÔNG được là kết luận kỹ thuật.
    for forbidden in ("mô men", "sức kháng", "PASS", "FAIL", "đạt", "an toàn"):
        assert forbidden not in document["reason"]


def test_unrelated_document_has_no_runtime_link(tree):
    document = _by_name(_index(tree), "ghi chú lặt vặt.pdf")
    assert document["relevance"] == "UNRELATED"
    assert document["runtime_link"] == []


def test_super_t_section_points_at_the_placeholder_catalog(tree):
    document = _by_name(_index(tree), "Section Super T 38.2m.dwg")
    assert any("catalogs/catalogs.json" in link
               for link in document["runtime_link"])
    assert any("PLACEHOLDER" in link for link in document["runtime_link"])


def test_runtime_link_targets_exist_in_the_repo():
    repo = Path(__file__).resolve().parent.parent
    for _words, link in lib.RUNTIME_LINK_HINTS:
        relative = link.split("::")[0].split(" (")[0].strip()
        assert (repo / relative).exists(), f"gợi ý trỏ vào file không có: {link}"


# --- tích hợp với thư viện đã nhập vào vault ---------------------------------

def test_already_in_vault_is_read_from_the_import_manifest(tree, tmp_path,
                                                           monkeypatch):
    vault = tmp_path / "Vault"
    library = vault / "DYLIGHT Bridge Evolution" / "Library"
    library.mkdir(parents=True)
    (vault / ".obsidian").mkdir()
    source = tree / "Tiêu chuẩn" / "TCVN 11823-5-2017.pdf"
    payload = source.read_bytes()
    (library / lib.LIBRARY_MANIFEST).write_text(json.dumps({
        "schema_version": lib.MANIFEST_SCHEMA_VERSION,
        "importer": lib.IMPORTER_VERSION,
        "files": {"Files/tcvn.pdf": {
            "sha256": hashlib.sha256(payload).hexdigest(),
            "size": len(payload),
            "source": str(source),
            "source_mtime": int(source.stat().st_mtime),
        }},
        "duplicates": {}, "notes": {},
    }, ensure_ascii=False), encoding="utf-8")

    index = lib.build_document_index([tree], vault_dir=vault)
    document = _by_name(index, source.name)
    assert document["already_in_vault"] is True
    # Hash tái dùng từ manifest là hash ĐẦY ĐỦ, nên vẫn phải khớp nội dung thật.
    assert document["sha256"] == hashlib.sha256(payload).hexdigest()
    assert document["sha256_is_partial"] is False
    assert _by_name(index, "THKL cầu.xlsx")["already_in_vault"] is False


def test_vault_copies_are_never_indexed_as_sources(tmp_path):
    vault = tmp_path / "kho" / "Vault"
    library = vault / "DYLIGHT Bridge Evolution" / "Library"
    library.mkdir(parents=True)
    (vault / ".obsidian").mkdir()
    (library / lib.LIBRARY_MANIFEST).write_text(
        json.dumps({"schema_version": lib.MANIFEST_SCHEMA_VERSION,
                    "importer": lib.IMPORTER_VERSION,
                    "files": {}, "duplicates": {}, "notes": {}}),
        encoding="utf-8")
    _write(library / "Files" / "ban sao cau.dwg", b"DWG-copy")
    _write(tmp_path / "kho" / "goc" / "cầu thật.dwg", b"DWG-real")

    index = lib.build_document_index([tmp_path / "kho"], vault_dir=vault)
    indexed = {item["filename"] for item in index["documents"]}
    assert indexed == {"cầu thật.dwg"}


def test_missing_vault_degrades_to_no_vault_knowledge(tree, tmp_path,
                                                      monkeypatch):
    monkeypatch.setenv("DYLIGHT_OBSIDIAN_VAULT", str(tmp_path / "khong-co"))
    index = lib.build_document_index([tree])
    assert index["counts"]["total"] > 0
    assert all(item["already_in_vault"] is False for item in index["documents"])


# --- ghi ra đĩa --------------------------------------------------------------

def test_write_document_index_round_trips(tree, tmp_path):
    index = _index(tree)
    target = tmp_path / "research" / "library" / "index.json"
    summary = lib.write_document_index(index, target)
    assert summary["output"] == str(target)
    assert summary["total"] == index["counts"]["total"]
    reloaded = json.loads(target.read_text(encoding="utf-8"))
    assert reloaded == index
    assert list(_validator().iter_errors(reloaded)) == []
    # Ghi lại lần hai không được để lại file tạm.
    lib.write_document_index(index, target)
    assert [item.name for item in target.parent.iterdir()] == ["index.json"]


def test_utc_stamp_matches_schema_pattern():
    import re
    pattern = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")
    for epoch in (0.0, 1_780_000_000.0, 1_780_000_000.9):
        assert pattern.match(lib._utc_stamp(epoch))
    assert lib._utc_stamp(-1.0) == lib._utc_stamp(0.0)


def test_document_id_range_stops_instead_of_truncating(tree, monkeypatch):
    """Vượt dải DOC-00001..DOC-99999 phải DỪNG, không được cắt bớt im lặng."""
    monkeypatch.setattr(lib, "INDEX_MAX_DOCUMENTS", 2)
    with pytest.raises(ValueError, match="document_id"):
        _index(tree)
    monkeypatch.setattr(lib, "INDEX_MAX_DOCUMENTS", 99999)
    assert all(len(item["document_id"]) == len("DOC-00001")
               for item in _index(tree)["documents"])


# --- hồi quy: đường dẫn dài và reparse point --------------------------------
# Cả hai lỗi dưới đây đã xảy ra thật trong lần quét thử ổ D: và làm MẤT dữ liệu
# im lặng (62 file có thật bị báo FileNotFoundError). Test giữ chúng không quay lại.

def test_extended_prefix_round_trips():
    slash = chr(92)
    extended = lib._extended_root(Path("D:" + slash))
    assert extended.startswith(slash * 2 + "?" + slash)
    assert lib._strip_extended(extended).rstrip(slash) == "D:"
    unc = slash * 2 + "?" + slash + "UNC" + slash + "srv" + slash + "share"
    assert lib._strip_extended(unc) == slash * 2 + "srv" + slash + "share"
    assert lib._strip_extended("D:" + slash + "a") == "D:" + slash + "a"


@pytest.mark.skipif(os.name != "nt", reason="giới hạn MAX_PATH là của Windows")
def test_deep_path_is_indexed_not_reported_unreadable(tmp_path):
    """Thư mục sâu quá MAX_PATH phải vào chỉ mục, không thành 'không đọc được'."""
    deep = tmp_path / "kho"
    os.mkdir(deep)
    # mkdir(parents=True) của pathlib cũng vướng MAX_PATH, nên tự tạo từng cấp
    # qua đúng tiền tố mở rộng mà module đang dùng.
    while len(str(deep)) < 300:
        deep = deep / "thu-muc-rat-dai-de-vuot-qua-gioi-han-MAX-PATH-cua-windows"
        os.mkdir(lib._long_path(deep))
    target = deep / "cầu sâu.dwg"
    with open(lib._long_path(target), "wb") as stream:
        stream.write(b"DWG-deep")

    index = lib.build_document_index([tmp_path / "kho"], use_vault=False)
    assert index["unreadable"] == []
    document = _by_name(index, "cầu sâu.dwg")
    assert len(document["path"]) > 260
    # Đường dẫn ghi vào chỉ mục KHÔNG được mang tiền tố mở rộng.
    assert not document["path"].startswith(chr(92) * 2 + "?")
    assert document["sha256"] == hashlib.sha256(b"DWG-deep").hexdigest()


def test_unstattable_path_is_not_pruned_as_reparse(tmp_path):
    """lstat lỗi KHÔNG được biến thành 'cắt cả cây con' — đó là mất dữ liệu im lặng."""
    assert lib._is_reparse(tmp_path / "khong-ton-tai") is False
    assert lib._is_reparse(tmp_path) is False


@pytest.mark.skipif(os.name != "nt", reason="junction là khái niệm của Windows")
def test_junction_is_recorded_and_not_followed(tmp_path):
    import subprocess
    root = tmp_path / "kho"
    _write(root / "that" / "cầu.dwg", b"DWG")
    link = root / "lối tắt"
    completed = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(root / "that")],
        capture_output=True, text=True)
    if completed.returncode != 0:
        pytest.skip(f"không tạo được junction: {completed.stderr.strip()}")

    index = lib.build_document_index([root], use_vault=False)
    assert len(index["documents"]) == 1
    entry = next(item for item in index["unreadable"]
                 if item["path"].endswith("lối tắt"))
    assert "reparse point" in entry["reason"]


# --- README phải được SINH từ chỉ mục, không gõ tay -------------------------
# Repo này đã một lần bị lệch docs–runtime (BRD-019, BRD-022). Cách rẻ nhất để
# không lặp lại: README không có con số nào do người gõ.

LIBRARY_DIR = Path(__file__).resolve().parent.parent / "research" / "library"


def test_readme_on_disk_matches_the_index_on_disk():
    index_path = LIBRARY_DIR / "index.json"
    readme_path = LIBRARY_DIR / "README.md"
    if not index_path.exists() or not readme_path.exists():
        pytest.skip("chưa có chỉ mục thật trên đĩa — chạy build_document_index trước")
    index = json.loads(index_path.read_text(encoding="utf-8"))
    assert list(_validator().iter_errors(index)) == []
    assert readme_path.read_text(encoding="utf-8") == lib.render_library_readme(index)


def test_readme_numbers_are_counted_from_the_index(tree):
    index = _index(tree)
    text = lib.render_library_readme(index)
    counts = index["counts"]
    assert f"| **Tài liệu trong chỉ mục** | **{counts['total']}** |" in text
    assert f"| File đã duyệt qua | {counts['scanned_files']} |" in text
    assert f"| Bị loại có ghi lý do | {len(index['skipped'])} |" in text
    for group in ("by_relevance", "by_category", "by_extension", "by_drive"):
        for key, value in counts[group].items():
            assert f"| `{key}` | {value} |" in text


def test_readme_states_the_unverified_ceiling_and_never_more(tree):
    text = lib.render_library_readme(_index(tree))
    assert "UNVERIFIED" in text
    assert "IDEA" in text
    assert "PLACEHOLDER" in text
    for forbidden in ("NUMERICALLY_VERIFIED", "LAB_VALIDATED",
                      "PILOT_VALIDATED", "ENGINEERING_CANDIDATE"):
        assert forbidden not in text


def test_readme_carries_copyright_and_read_only_notice(tree):
    text = lib.render_library_readme(_index(tree))
    assert "Bản quyền" in text
    assert "không sao chép nội dung" in text
    assert "chỉ đọc" in text
    assert "mật khẩu" in text


def test_readme_reports_truncation_instead_of_hiding_it(tree, monkeypatch):
    index = _index(tree)
    linked = [item for item in index["documents"] if item["runtime_link"]]
    assert len(linked) > 1, "cây mẫu phải có nhiều hơn một tài liệu có runtime_link"
    monkeypatch.setattr(lib, "README_RUNTIME_LINK_ROWS", 1)
    text = lib.render_library_readme(index)
    assert f"còn **{len(linked) - 1}**" in text
    assert "Không dòng nào bị cắt im lặng" in text


def test_readme_lists_filenames_not_document_paths(tree):
    """Bảng README chỉ nêu TÊN file; đường dẫn đầy đủ chỉ nằm trong index.json.

    Gốc quét thì ngược lại: phải ghi nguyên văn, vì không có nó thì không ai
    dựng lại được chỉ mục.
    """
    index = _index(tree)
    text = lib.render_library_readme(index)
    for document in index["documents"]:
        assert document["path"] not in text
    assert index["roots"][0] in text
