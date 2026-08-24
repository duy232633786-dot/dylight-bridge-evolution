"""Bộ kiểm CHỐNG LỆCH giữa tài liệu và runtime.

Vì sao tồn tại
--------------
Sửa tay một con số trong README hôm nay thì tháng sau nó lệch lại. Sản phẩm cần
thiết KHÔNG phải con số đúng, mà là **cơ chế không cho phép nó sai lần nữa**.
Mọi tuyên bố đếm được và mọi tuyên bố "có/không có năng lực X" trong tài liệu
phải được đối chiếu với runtime bằng cách IMPORT VÀ GỌI THẬT.

Nguồn chuẩn máy đọc: ``docs/runtime_capability_matrix.json``
  (schema: ``contracts/runtime_capability_matrix.schema.json``)
Bản người đọc phải khớp: ``docs/runtime_capability_matrix.md``

Chạy
----
    PYTHONIOENCODING=utf-8 python docs/check_runtime_drift.py

Thoát 0 = không lệch. Thoát 1 = có lệch, in từng dòng lệch.

Nối vào pytest
--------------
``tests/`` NẰM NGOÀI write_scope của task BRD-001 nên bộ kiểm này CHƯA được nối
vào ``python -m pytest tests -q``. Người có quyền ghi vào ``tests/`` chỉ cần tạo
``tests/test_runtime_drift.py`` với đúng ba dòng::

    import importlib.util, pathlib, sys
    _p = pathlib.Path(__file__).resolve().parent.parent / "docs" / "check_runtime_drift.py"
    _s = importlib.util.spec_from_file_location("check_runtime_drift", _p)
    _m = importlib.util.module_from_spec(_s); sys.modules[_s.name] = _m; _s.loader.exec_module(_m)

    def test_docs_do_not_drift_from_runtime():
        assert _m.run_all_checks() == []

Chừng nào chưa nối, phải chạy tay hoặc thêm một bước vào
``.github/workflows/tests.yml`` (cũng ngoài scope).
"""
from __future__ import annotations

import importlib
import json
import re
import sys
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

MATRIX_JSON = REPO_ROOT / "docs" / "runtime_capability_matrix.json"
MATRIX_SCHEMA = REPO_ROOT / "contracts" / "runtime_capability_matrix.schema.json"
AUDIT_JSON = REPO_ROOT / "knowledge" / "audits" / "current.json"
AUDIT_SCHEMA = REPO_ROOT / "contracts" / "knowledge_audit.schema.json"
PACKAGE_DIR = REPO_ROOT / "bridge_evolution"

#: rule_id là literal chuỗi dạng "XXX-NNN" trong mã nguồn package.
_RULE_ID_LITERAL = re.compile(r'"([A-Z]{3,6}-[0-9]{3})"')

#: Hàng bảng năng lực trong file .md: | `ID` | STATE | ...
_MD_ROW = re.compile(r"^\|\s*`([A-Z][A-Z0-9_]*)`\s*\|\s*(PRESENT|PARTIAL|ABSENT)\s*\|",
                     re.MULTILINE)


def _read_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# --------------------------------------------------------------- tiện ích
def _json_pointer(doc, pointer: str):
    """Giải JSON Pointer tối giản (/a/b/c). Trả về sentinel khi không có."""
    cur = doc
    for token in pointer.split("/"):
        if token == "":
            continue
        token = token.replace("~1", "/").replace("~0", "~")
        if isinstance(cur, list):
            try:
                cur = cur[int(token)]
            except (ValueError, IndexError):
                return _MISSING
        elif isinstance(cur, dict):
            if token not in cur:
                return _MISSING
            cur = cur[token]
        else:
            return _MISSING
    return cur


class _Missing:
    def __repr__(self) -> str:  # pragma: no cover - chỉ để thông báo lỗi đẹp
        return "<KHÔNG CÓ>"


_MISSING = _Missing()


def scan_runtime_rule_ids() -> set[str]:
    """Tập rule_id mà runtime có thể phát ra, quét literal trong bridge_evolution/."""
    found: set[str] = set()
    for path in sorted(PACKAGE_DIR.rglob("*.py")):
        found.update(_RULE_ID_LITERAL.findall(path.read_text(encoding="utf-8")))
    return found


def package_imports(module_name: str) -> list[str]:
    """File nào trong bridge_evolution/ import ``module_name`` (top-level)."""
    pattern = re.compile(rf"^\s*(?:from|import)\s+{re.escape(module_name)}\b", re.MULTILINE)
    return [str(p.relative_to(REPO_ROOT)).replace("\\", "/")
            for p in sorted(PACKAGE_DIR.rglob("*.py"))
            if pattern.search(p.read_text(encoding="utf-8"))]


def declared_dependencies() -> set[str]:
    """Tên gói khai báo trong pyproject.toml (dependencies + optional)."""
    with open(REPO_ROOT / "pyproject.toml", "rb") as f:
        cfg = tomllib.load(f)
    project = cfg.get("project", {})
    specs = list(project.get("dependencies", []))
    for group in (project.get("optional-dependencies") or {}).values():
        specs.extend(group)
    names = set()
    for spec in specs:
        m = re.match(r"[A-Za-z0-9._-]+", spec.strip())
        if m:
            names.add(m.group(0).lower().replace("_", "-"))
    return names


# --------------------------------------------------------------- probe
def _run_probe(probe: dict, ctx: dict) -> str | None:
    """Chạy một probe. Trả về thông báo lệch, hoặc None nếu đạt."""
    kind = probe["kind"]

    if kind == "file_exists":
        return None if (REPO_ROOT / probe["path"]).exists() \
            else f"không tìm thấy file bằng chứng: {probe['path']}"

    if kind == "module_attr":
        try:
            mod = importlib.import_module(probe["module"])
        except Exception as exc:
            return f"không import được {probe['module']}: {type(exc).__name__}: {exc}"
        if not hasattr(mod, probe["attr"]):
            return f"{probe['module']} không có thuộc tính {probe['attr']}"
        if probe.get("callable") and not callable(getattr(mod, probe["attr"])):
            return f"{probe['module']}.{probe['attr']} không gọi được"
        return None

    if kind == "raises":
        try:
            mod = importlib.import_module(probe["module"])
        except Exception as exc:
            return f"không import được {probe['module']}: {type(exc).__name__}: {exc}"
        fn = getattr(mod, probe["attr"], None)
        if fn is None:
            return f"{probe['module']} không có {probe['attr']}"
        try:
            fn(*probe["args"])
        except BaseException as exc:  # noqa: BLE001 — cần bắt đúng tên lớp
            names = {c.__name__ for c in type(exc).__mro__}
            if probe["exception"] in names:
                return None
            return (f"{probe['module']}.{probe['attr']} ném {type(exc).__name__}, "
                    f"chờ {probe['exception']}")
        return (f"{probe['module']}.{probe['attr']} KHÔNG ném {probe['exception']} — "
                f"năng lực được khai là ABSENT nhưng gọi được")

    if kind == "no_package_import":
        hits = package_imports(probe["module_name"])
        return None if not hits else \
            f"bridge_evolution/ CÓ import {probe['module_name']} tại: {', '.join(hits)}"

    if kind == "json_value_equals":
        doc = _read_json(REPO_ROOT / probe["path"])
        actual = _json_pointer(doc, probe["pointer"])
        return None if actual == probe["value"] else \
            f"{probe['path']}{probe['pointer']} = {actual!r}, tài liệu khai {probe['value']!r}"

    if kind == "card_status_count":
        cards = ctx["cards"]
        n = sum(1 for c in cards if c["status"] == probe["status"])
        return None if n == probe["expected"] else \
            f"số thẻ status={probe['status']} là {n}, tài liệu khai {probe['expected']}"

    if kind == "rule_absent":
        return None if probe["rule_id"] not in ctx["runtime_rules"] else \
            f"rule {probe['rule_id']} CÓ trong runtime nhưng năng lực được khai là ABSENT"

    if kind == "pyproject_dependency":
        name = probe["name"].lower().replace("_", "-")
        present = name in ctx["declared_deps"]
        if present == probe["declared"]:
            return None
        return (f"pyproject.toml {'CÓ' if present else 'KHÔNG'} khai báo phụ thuộc "
                f"'{probe['name']}', tài liệu nói ngược lại")

    if kind == "declared_not_machine_provable":
        ctx["unproven"].append(probe["rationale"])
        return None

    return f"probe kind không hỗ trợ: {kind}"


# --------------------------------------------------------------- đếm
def _runtime_count(source: str, ctx: dict) -> int:
    if source == "load_cards":
        return len(ctx["cards"])
    if source == "knowledge_card_files":
        return len(list((REPO_ROOT / "knowledge" / "cards").glob("KC-*.json")))
    if source == "audit_cards":
        return len(ctx["audit"]["cards"])
    if source == "fabrication_rules":
        return len({r for r in ctx["runtime_rules"]
                    if r.startswith("FAB-") and r != "FAB-000"})
    if source == "production_girder_sections":
        from bridge_evolution.catalogs import load_catalogs
        return len([k for k in load_catalogs()["girder_sections"]
                    if k not in ("ST-PARAM",) and "TEST" not in k])
    if source == "l0_layout_rules":
        return len({r for r in ctx["runtime_rules"]
                    if r.startswith(("GEOM-", "CONS-"))})
    if source in ("notebooklm_notebooks", "notebooklm_declared_sources"):
        snap = _read_json(REPO_ROOT / "bridge_evolution" / "knowledge"
                          / "notebooklm_bridge_snapshot.json")
        if source == "notebooklm_notebooks":
            return len(snap["notebooks"])
        return sum(n["declared_source_count"] for n in snap["notebooks"])
    raise KeyError(f"source đếm không hỗ trợ: {source}")


# --------------------------------------------------------------- kiểm tra
def check_schemas(ctx: dict) -> list[str]:
    """Ma trận và audit phải hợp lệ theo schema của chính repo."""
    import jsonschema

    errs = []
    for doc, schema_path, label in ((ctx["matrix"], MATRIX_SCHEMA, "runtime_capability_matrix.json"),
                                    (ctx["audit"], AUDIT_SCHEMA, "knowledge/audits/current.json")):
        validator = jsonschema.Draft202012Validator(_read_json(schema_path))
        for e in validator.iter_errors(doc):
            loc = "/".join(str(p) for p in e.absolute_path) or "<root>"
            errs.append(f"[schema] {label}: {loc}: {e.message}")
    return errs


def check_audit_covers_runtime_cards(ctx: dict) -> list[str]:
    """Audit phải phủ ĐÚNG TẬP card runtime nạp — so tập, không chỉ so số lượng.

    So số lượng thôi là chưa đủ: một card thiếu và một card thừa triệt tiêu nhau.
    """
    runtime_ids = {c["card_id"] for c in ctx["cards"]}
    audit_ids = set(ctx["audit"]["cards"])
    errs = []
    missing = sorted(runtime_ids - audit_ids)
    extra = sorted(audit_ids - runtime_ids)
    if missing:
        errs.append(f"[audit] load_cards() nạp {len(runtime_ids)} thẻ nhưng audit "
                    f"KHÔNG phủ: {', '.join(missing)}")
    if extra:
        errs.append(f"[audit] audit phủ thẻ KHÔNG tồn tại trong runtime: {', '.join(extra)}")
    if len(runtime_ids) != len(audit_ids) and not missing and not extra:
        errs.append("[audit] số thẻ lệch mà tập lại trùng — dữ liệu audit hỏng")
    return errs


def check_audit_does_not_overclaim(ctx: dict) -> list[str]:
    """Audit không được nâng trạng thái thẻ khi chưa có kỹ sư duyệt."""
    errs = []
    approved = [c["card_id"] for c in ctx["cards"] if c["status"] == "ENGINEER_APPROVED"]
    if approved:
        errs.append(f"[audit] có thẻ ENGINEER_APPROVED ({', '.join(approved)}) — "
                    f"phải có bản duyệt của kỹ sư kèm theo trước khi được phép")
    for cid, entry in ctx["audit"]["cards"].items():
        if entry["claim_audit"] == "CONFIRMED" and entry["evidence_freshness"] == "EXPERT_UNVERIFIED":
            errs.append(f"[audit] {cid}: claim_audit=CONFIRMED nhưng "
                        f"evidence_freshness=EXPERT_UNVERIFIED — mâu thuẫn")
    return errs


def check_cards_reference_real_runtime(ctx: dict) -> list[str]:
    """applies_to của thẻ phải trỏ tới grammar/biến/rule CÓ THẬT trong runtime.

    Lệch đã biết mà chưa sửa được (thẻ nằm ngoài write_scope, chờ kỹ sư duyệt…)
    phải nằm trong ``known_card_reference_exceptions`` — có lý do, có người gỡ.
    Miễn trừ KHÔNG được phép mục ruỗng: khi lệch đã được sửa mà miễn trừ vẫn còn,
    bộ kiểm báo đỏ để buộc dọn.
    """
    from bridge_evolution.catalogs import load_grammar

    errs = []
    waivers = {(w["card_id"], w["kind"], w["value"]): w
               for w in ctx["matrix"]["known_card_reference_exceptions"]}
    used: set[tuple[str, str, str]] = set()

    grammars: dict[str, set[str]] = {}
    for path in sorted((REPO_ROOT / "bridge_grammar").glob("*.json")):
        g = load_grammar(path.stem)
        grammars[g["grammar_id"]] = set(g["design_variables"])

    def report(card_id: str, kind: str, value: str, message: str) -> None:
        key = (card_id, kind, value)
        if key in waivers:
            used.add(key)
            ctx["waived"].append(f"{card_id}: {message} "
                                 f"[miễn trừ — gỡ tại: {waivers[key]['must_fix_in']}]")
        else:
            errs.append(f"[card] {card_id}: {message}")

    for card in ctx["cards"]:
        applies = card["applies_to"]
        fam = applies["family"]
        if fam not in grammars:
            report(card["card_id"], "family", fam,
                   f"applies_to.family '{fam}' không phải grammar nào trong bridge_grammar/")
            continue
        for var in applies["variables"]:
            if var not in grammars[fam]:
                report(card["card_id"], "variable", var,
                       f"biến '{var}' không tồn tại trong grammar '{fam}' — "
                       f"truy vấn tri thức không bao giờ khớp được")
        for rule in applies["rules"]:
            if rule not in ctx["runtime_rules"]:
                report(card["card_id"], "rule", rule,
                       f"rule '{rule}' không nằm trong tập rule runtime phát ra được")

    for key in sorted(set(waivers) - used):
        errs.append(f"[waiver] miễn trừ {key[0]}/{key[1]}/{key[2]} không còn cần thiết — "
                    f"lệch đã được sửa, hãy xoá khỏi known_card_reference_exceptions")
    return errs


def check_rule_inventory(ctx: dict) -> list[str]:
    """Tập rule khai báo phải bằng đúng tập rule quét được từ mã nguồn."""
    declared = set(ctx["matrix"]["runtime_rule_inventory"])
    actual = ctx["runtime_rules"]
    errs = []
    if declared - actual:
        errs.append(f"[rules] ma trận khai rule không còn trong runtime: "
                    f"{', '.join(sorted(declared - actual))}")
    if actual - declared:
        errs.append(f"[rules] runtime có rule chưa khai trong ma trận: "
                    f"{', '.join(sorted(actual - declared))}")
    return errs


def check_capabilities(ctx: dict) -> list[str]:
    """Mọi năng lực PRESENT/PARTIAL phải gọi được thật; ABSENT phải không gọi được."""
    errs = []
    for cap in ctx["matrix"]["capabilities"]:
        for probe in cap["probes"]:
            msg = _run_probe(probe, ctx)
            if msg:
                errs.append(f"[capability] {cap['id']} ({cap['state']}): {msg}")
    return errs


def check_markdown_mirror(ctx: dict) -> list[str]:
    """File .md người đọc phải khớp từng năng lực và mang đủ bằng chứng."""
    md_path = REPO_ROOT / ctx["matrix"]["doc_mirror"]
    if not md_path.exists():
        return [f"[doc] không có {ctx['matrix']['doc_mirror']}"]
    text = _read_text(md_path)
    rows = dict(_MD_ROW.findall(text))
    caps = {c["id"]: c for c in ctx["matrix"]["capabilities"]}

    errs = []
    for missing in sorted(set(caps) - set(rows)):
        errs.append(f"[doc] {ctx['matrix']['doc_mirror']} thiếu hàng cho năng lực {missing}")
    for extra in sorted(set(rows) - set(caps)):
        errs.append(f"[doc] {ctx['matrix']['doc_mirror']} có năng lực {extra} "
                    f"không tồn tại trong ma trận máy đọc")
    for cid, cap in caps.items():
        if cid in rows and rows[cid] != cap["state"]:
            errs.append(f"[doc] {cid}: .md ghi {rows[cid]} nhưng ma trận máy đọc "
                        f"ghi {cap['state']}")
        for ev in cap["evidence"]:
            if ev not in text:
                errs.append(f"[doc] {cid}: bằng chứng '{ev}' không xuất hiện trong "
                            f"{ctx['matrix']['doc_mirror']}")
    if ctx["matrix"]["claim_ceiling"] not in text:
        errs.append(f"[doc] {ctx['matrix']['doc_mirror']} không nêu trần claim "
                    f"{ctx['matrix']['claim_ceiling']}")
    return errs


def check_declared_counts(ctx: dict) -> list[str]:
    """Mọi con số đếm được trong tài liệu phải bằng số runtime đếm lại."""
    errs = []
    for item in ctx["matrix"]["declared_counts"]:
        try:
            actual = _runtime_count(item["source"], ctx)
        except Exception as exc:  # noqa: BLE001
            errs.append(f"[count] {item['id']}: không đếm lại được: {exc}")
            continue
        for claim in item["doc_claims"]:
            path = REPO_ROOT / claim["file"]
            if not path.exists():
                errs.append(f"[count] {item['id']}: không có file {claim['file']}")
                continue
            m = re.search(claim["pattern"], _read_text(path))
            if m is None:
                errs.append(f"[count] {item['id']}: {claim['file']} không còn câu khớp "
                            f"mẫu /{claim['pattern']}/ — tài liệu đã bị sửa mất chỗ neo")
                continue
            if int(m.group(1)) != actual:
                errs.append(f"[count] {item['id']}: {claim['file']} ghi {m.group(1)} "
                            f"nhưng runtime đếm {actual}")
    # Bất biến độc lập với tài liệu: số file thẻ == số thẻ nạp == số thẻ audit.
    n_files = _runtime_count("knowledge_card_files", ctx)
    n_loaded = _runtime_count("load_cards", ctx)
    n_audit = _runtime_count("audit_cards", ctx)
    if not (n_files == n_loaded == n_audit):
        errs.append(f"[count] lệch: {n_files} file thẻ, {n_loaded} thẻ nạp được, "
                    f"{n_audit} thẻ được audit")
    return errs


def check_fabrication_rules_actually_fire(ctx: dict) -> list[str]:
    """Từng rule FAB phải KÍCH HOẠT ĐƯỢC thật, không chỉ tồn tại trong mã."""
    from bridge_evolution.section import fabrication_violations

    errs = []
    covered = set()
    for probe in ctx["matrix"]["fabrication_rule_probes"]:
        try:
            fired = {v["rule_id"] for v in
                     fabrication_violations(probe["params"], probe["context"])}
        except Exception as exc:  # noqa: BLE001
            errs.append(f"[fab] {probe['rule_id']}: probe lỗi: {type(exc).__name__}: {exc}")
            continue
        if probe["rule_id"] not in fired:
            errs.append(f"[fab] {probe['rule_id']} KHÔNG kích hoạt với bộ tham số probe "
                        f"(chỉ thấy {sorted(fired) or 'không có vi phạm nào'}) — "
                        f"rule đã đổi ngưỡng hoặc đã bị gỡ")
        covered.add(probe["rule_id"])
    expected = {r for r in ctx["runtime_rules"] if r.startswith("FAB-") and r != "FAB-000"}
    if expected - covered:
        errs.append(f"[fab] rule chế tạo chưa có probe kích hoạt: "
                    f"{', '.join(sorted(expected - covered))}")
    if covered - expected:
        errs.append(f"[fab] probe cho rule không còn trong runtime: "
                    f"{', '.join(sorted(covered - expected))}")
    return errs


def check_l0_pipeline(ctx: dict) -> list[str]:
    """FAB-* phải chạy trong PIPELINE L0 thật, không chỉ trong hàm thuần toán."""
    from bridge_evolution.geometry import check_geometry
    from bridge_evolution.state import new_state

    spec = ctx["matrix"]["l0_pipeline_probe"]
    dv = dict(spec["design_variables"])
    try:
        state = new_state(dv,
                          girder_concrete_id=spec["girder_concrete_id"],
                          deck_concrete_id=spec["deck_concrete_id"],
                          grammar_id=spec["grammar_id"])
        violations, geom = check_geometry(state)
    except Exception as exc:  # noqa: BLE001
        return [f"[l0] không chạy được check_geometry trên grammar "
                f"{spec['grammar_id']}: {type(exc).__name__}: {exc}"]

    errs = []
    if geom.get("section_source") != spec["expect_section_source"]:
        errs.append(f"[l0] section_source = {geom.get('section_source')!r}, "
                    f"chờ {spec['expect_section_source']!r}")
    fired = {v["rule_id"] for v in violations}
    for rule in spec["expect_rule_ids"]:
        if rule not in fired:
            errs.append(f"[l0] check_geometry KHÔNG phát {rule} cho state probe "
                        f"(thấy {sorted(fired) or 'không có vi phạm nào'}) — "
                        f"FAB-* không còn chạy ở L0")
    return errs


def check_claim_ceiling(ctx: dict) -> list[str]:
    """Trần claim trong ma trận phải bằng trần claim của phòng lab."""
    ev = ctx["matrix"]["claim_ceiling_evidence"]
    doc = _read_json(REPO_ROOT / ev["path"])
    actual = _json_pointer(doc, ev["pointer"])
    if actual != ctx["matrix"]["claim_ceiling"]:
        return [f"[claim] ma trận khai trần {ctx['matrix']['claim_ceiling']} nhưng "
                f"{ev['path']}{ev['pointer']} = {actual!r}"]
    caps = ctx["matrix"]["capabilities"]
    order = ["IDEA", "SCREENED", "NUMERICALLY_VERIFIED", "LAB_VALIDATED",
             "FIELD_VALIDATED", "ENGINEERING_CANDIDATE"]
    md = _read_text(REPO_ROOT / ctx["matrix"]["doc_mirror"])
    errs = []
    ceiling_rank = order.index(ctx["matrix"]["claim_ceiling"])
    for level in order[ceiling_rank + 1:]:
        # Cấp claim cao hơn trần chỉ được nhắc trong ngữ cảnh phủ định/điều kiện,
        # không được gán cho một năng lực nào.
        for cap in caps:
            if level in cap.get("limits", "") or level in cap["title"]:
                errs.append(f"[claim] năng lực {cap['id']} nhắc cấp claim {level} "
                            f"vượt trần {ctx['matrix']['claim_ceiling']}")
        if re.search(rf"^\|[^|\n]*\|[^|\n]*{level}", md, re.MULTILINE):
            errs.append(f"[claim] bảng trong {ctx['matrix']['doc_mirror']} gán cấp "
                        f"{level} cho một hàng năng lực — vượt trần "
                        f"{ctx['matrix']['claim_ceiling']}")
    return errs


CHECKS = (
    check_schemas,
    check_rule_inventory,
    check_audit_covers_runtime_cards,
    check_audit_does_not_overclaim,
    check_cards_reference_real_runtime,
    check_capabilities,
    check_markdown_mirror,
    check_declared_counts,
    check_fabrication_rules_actually_fire,
    check_l0_pipeline,
    check_claim_ceiling,
)


def build_context() -> dict:
    from bridge_evolution.knowledge import load_cards

    return {
        "matrix": _read_json(MATRIX_JSON),
        "audit": _read_json(AUDIT_JSON),
        "cards": load_cards(),
        "runtime_rules": scan_runtime_rule_ids(),
        "declared_deps": declared_dependencies(),
        "unproven": [],
        "waived": [],
    }


def run_all_checks(ctx: dict | None = None) -> list[str]:
    """Trả về danh sách lệch (rỗng = tài liệu khớp runtime). Không raise."""
    if ctx is None:
        try:
            ctx = build_context()
        except Exception as exc:  # noqa: BLE001
            return [f"[fatal] không dựng được bối cảnh kiểm tra: {type(exc).__name__}: {exc}"]
    errors: list[str] = []
    for check in CHECKS:
        try:
            errors.extend(check(ctx))
        except Exception as exc:  # noqa: BLE001
            errors.append(f"[fatal] {check.__name__} lỗi: {type(exc).__name__}: {exc}")
    return errors


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    try:
        ctx = build_context()
    except Exception as exc:  # noqa: BLE001
        print(f"LECH: 1")
        print(f"  - [fatal] {type(exc).__name__}: {exc}")
        return 1
    errors = run_all_checks(ctx)
    for w in ctx["waived"]:
        print(f"  ! MIEN TRU: {w}")
    if ctx["unproven"]:
        print(f"  ! {len(ctx['unproven'])} khang dinh ABSENT khong chung minh duoc bang may:")
        for r in ctx["unproven"]:
            print(f"      {r}")
    if errors:
        print(f"LECH: {len(errors)}")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("OK: tai lieu khop runtime.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
