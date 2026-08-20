"""Kết nối kho thẻ tri thức với một vùng được quản lý trong Obsidian.

JSON KnowledgeCard trong dự án vẫn là nguồn chuẩn/runtime. Module này chỉ sinh
Markdown để duyệt, liên kết và ghi chú trong Obsidian; nó không cho Markdown
tham gia verifier hoặc tự động ghi ngược vào kho JSON.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any

import jsonschema

from .. import CONTRACTS_DIR, KNOWLEDGE_AUDITS_DIR, REPO_ROOT
from .store import CARDS_DIR, load_cards
from .taxonomy import RULES, TCVN_PART_TITLES, VARIABLES, standards_for_card

DEFAULT_MANAGED_FOLDER = "DYLIGHT Bridge Evolution"
DASHBOARD_NAME = "00 - Brain 2 Dashboard.md"
MANIFEST_NAME = ".dylight-manifest.json"
MANIFEST_SCHEMA_VERSION = 1
EXPORTER_VERSION = "obsidian-export/2"

_SAFE_LINK_VALUE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_LEGACY_EXPERIMENT_MARKERS = (
    "experiments/results/run_b600_s42",
    "experiments/results/multiseed_b600",
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_card_bytes(card: dict) -> bytes:
    return (json.dumps(card, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":")) + "\n").encode("utf-8")


def _yaml_value(value: Any) -> str:
    """JSON flow syntax là một tập con an toàn của YAML 1.2/Obsidian Properties."""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _table_text(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def _code_text(value: Any) -> str:
    return str(value).replace("`", "\\`").replace("\r", " ").replace("\n", " ")


def _knowledge_link(group: str, value: str,
                    managed_folder: str = DEFAULT_MANAGED_FOLDER) -> str:
    """Chỉ tạo wikilink với identifier đơn giản; dữ liệu lạ hiển thị dạng code."""
    if _SAFE_LINK_VALUE.fullmatch(value):
        return f"[[{managed_folder}/{group}/{value}|{value}]]"
    return f"`{_code_text(value)}`"


def _standard_link(part: int, managed_folder: str) -> str:
    title = TCVN_PART_TITLES.get(part)
    if title is None:
        return f"`TCVN 11823-{part}:2017`"
    target = (f"{managed_folder}/Standards/TCVN 11823-2017/Parts/"
              f"TCVN 11823-{part}-2017 - {title}")
    return f"[[{target}|TCVN 11823-{part}:2017]]"


def _is_legacy_experiment(card: dict) -> bool:
    source = card.get("source", {})
    ref = str(source.get("ref", "")).replace("\\", "/")
    return (source.get("kind") == "experiment"
            and any(marker in ref for marker in _LEGACY_EXPERIMENT_MARKERS))


def load_card_audit(audit_path: str | Path | None = None) -> dict | None:
    """Nạp sidecar audit nếu có và chặn metadata sai contract."""
    path = (Path(audit_path) if audit_path is not None
            else KNOWLEDGE_AUDITS_DIR / "current.json")
    if not path.is_file():
        return None
    try:
        audit = json.loads(path.read_text(encoding="utf-8"))
        schema = json.loads(
            (CONTRACTS_DIR / "knowledge_audit.schema.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Không đọc được knowledge audit: {path}") from exc
    errors = sorted(jsonschema.Draft202012Validator(schema).iter_errors(audit),
                    key=lambda error: list(error.absolute_path))
    if errors:
        rendered = [
            f"{'/'.join(str(p) for p in error.absolute_path) or '<root>'}:"
            f" {error.message}" for error in errors]
        raise ValueError(f"Knowledge audit không hợp lệ ({path.name}): {rendered}")
    evidence_ref = Path(audit["evidence"]["ref"])
    if (evidence_ref.is_absolute()
            or any(part in ("", ".", "..") for part in evidence_ref.parts)):
        raise ValueError("Knowledge audit có evidence ref không an toàn")
    evidence_path = (REPO_ROOT / evidence_ref).resolve(strict=False)
    repo_root = REPO_ROOT.resolve(strict=False)
    if repo_root not in evidence_path.parents:
        raise ValueError("Knowledge audit evidence thoát khỏi project root")
    if evidence_path.is_file():
        actual_hash = _sha256(evidence_path.read_bytes())
        if actual_hash != audit["evidence"]["sha256"]:
            raise ValueError("Knowledge audit evidence SHA-256 không khớp")
    return audit


def render_card_note(card: dict, canonical_path: str,
                     canonical_sha256: str | None = None,
                     audit: dict | None = None,
                     audit_meta: dict | None = None,
                     managed_folder: str = DEFAULT_MANAGED_FOLDER) -> str:
    """Render một KnowledgeCard đã validate thành Markdown byte-deterministic."""
    canonical_hash = canonical_sha256 or _sha256(_canonical_card_bytes(card))
    applies = card["applies_to"]
    source = card["source"]
    status = card["status"]
    legacy = _is_legacy_experiment(card)
    tags = ["dylight/knowledge-card", f"dylight/status/{status.lower()}"]
    if legacy:
        tags.append("dylight/source/legacy-experiment")
    if audit:
        tags.extend([
            f"dylight/risk/{audit['risk'].lower()}",
            f"dylight/claim-audit/{audit['claim_audit'].lower()}",
        ])
    cssclasses = ["dylight-note", "dylight-card",
                  f"dylight-status-{status.lower()}"]
    if audit:
        cssclasses.append(f"dylight-risk-{audit['risk'].lower()}")

    frontmatter = [
        "---",
        f"dylight_kind: {_yaml_value('knowledge-card')}",
        f"dylight_schema_version: {MANIFEST_SCHEMA_VERSION}",
        f"dylight_card_id: {_yaml_value(card['card_id'])}",
        f"dylight_card_version: {card['version']}",
        f"dylight_card_type: {_yaml_value(card['type'])}",
        f"dylight_status: {_yaml_value(status)}",
        f"dylight_family: {_yaml_value(applies['family'])}",
        f"dylight_rules: {_yaml_value(applies['rules'])}",
        f"dylight_variables: {_yaml_value(applies['variables'])}",
        f"dylight_source_kind: {_yaml_value(source['kind'])}",
        f"dylight_source_ref: {_yaml_value(source['ref'])}",
        f"dylight_source_quality: {_yaml_value('legacy' if legacy else 'declared')}",
        f"dylight_canonical_source: {_yaml_value(canonical_path)}",
        f"dylight_canonical_sha256: {_yaml_value(canonical_hash)}",
        f"dylight_evidence_freshness: {_yaml_value(audit['evidence_freshness'] if audit else 'NOT_AUDITED')}",
        f"dylight_claim_audit: {_yaml_value(audit['claim_audit'] if audit else 'NOT_AUDITED')}",
        f"dylight_risk: {_yaml_value(audit['risk'] if audit else 'NOT_AUDITED')}",
        f"aliases: {_yaml_value([card['card_id']])}",
        f"tags: {_yaml_value(tags)}",
        f"cssclasses: {_yaml_value(cssclasses)}",
        "---",
        "",
    ]

    if status == "DRAFT":
        warning = [
            "> [!WARNING] DRAFT — chưa được kỹ sư phê duyệt",
            "> Nội dung chỉ dùng để gợi ý hướng tìm kiếm. PASS/FAIL luôn thuộc"
            " independent verifier.",
            "",
        ]
    elif status == "REJECTED":
        warning = [
            "> [!DANGER] REJECTED",
            "> Thẻ này bị loại và không được não 2 trả về khi truy vấn.",
            "",
        ]
    else:
        warning = [
            "> [!NOTE] ENGINEER_APPROVED",
            "> Vẫn phải đối chiếu catalog/ruleset hiện hành trước khi áp dụng.",
            "",
        ]
    if legacy:
        warning.extend([
            "> [!CAUTION] Nguồn thí nghiệm legacy",
            "> Nguồn này dùng định nghĩa ngân sách cũ; không dùng để so sánh hiệu"
            " năng theo protocol hiện hành.",
            "",
        ])
    if audit:
        callout = "DANGER" if audit["risk"] == "RED" else "WARNING"
        warning.extend([
            f"> [!{callout}] Claim audit: {audit['risk']} · {audit['claim_audit']}",
            f"> {audit['summary']}",
            "",
        ])

    rules = ", ".join(_knowledge_link("Rules", value, managed_folder)
                      for value in applies["rules"]) or "—"
    variables = ", ".join(_knowledge_link("Variables", value, managed_folder)
                          for value in applies["variables"]) or "—"
    standards = ", ".join(
        _standard_link(part, managed_folder) for part in standards_for_card(card)) or "—"
    body = [
        f"# {card['title']}",
        "",
        f"- **Card:** `{_code_text(card['card_id'])}`",
        f"- **Family:** `{_code_text(applies['family'])}`",
        f"- **Rules:** {rules}",
        f"- **Variables:** {variables}",
        f"- **Standards:** {standards}",
        "",
        "## Guidance",
        "",
        card["guidance"].strip(),
        "",
        "## Evidence",
        "",
        card["evidence"].strip(),
        "",
        "## Source",
        "",
        f"- Kind: `{_code_text(source['kind'])}`",
        f"- Ref: `{_code_text(source['ref'])}`",
        "",
    ]
    if audit:
        body.extend([
            "## Latest claim audit",
            "",
            f"- Evidence freshness: `{audit['evidence_freshness']}`",
            f"- Claim audit: `{audit['claim_audit']}`",
            f"- Risk: `{audit['risk']}`",
            "",
        ])
        body.extend(f"- {finding}" for finding in audit["findings"])
        body.extend([
            "",
            f"**Next action:** {audit['next_action']}",
            "",
        ])
        if audit_meta:
            evidence = audit_meta["evidence"]
            body.extend([
                f"- Audit snapshot: `{_code_text(audit_meta['audit_id'])}`",
                f"- Evidence: `{_code_text(evidence['ref'])}`",
                f"- Evidence SHA-256: `{evidence['sha256']}`",
                "",
            ])
    body.extend([
        "## Provenance",
        "",
        f"- Canonical JSON: `{_code_text(canonical_path)}`",
        f"- Canonical SHA-256: `{canonical_hash}`",
        f"- Exporter: `{EXPORTER_VERSION}`",
        "",
        "---",
        "*Note này được sinh từ JSON chuẩn. Sửa note không tự thay đổi runtime"
        " của não 2.*",
        "",
    ])
    return "\n".join(frontmatter + warning + body)


def render_dashboard(cards: list[dict], audit: dict | None = None,
                     managed_folder: str = "DYLIGHT Bridge Evolution") -> str:
    """Render trang mục lục cho vùng Brain 2 trong vault."""
    draft_count = sum(card["status"] == "DRAFT" for card in cards)
    approved_count = sum(card["status"] == "ENGINEER_APPROVED" for card in cards)
    legacy_count = sum(_is_legacy_experiment(card) for card in cards)
    audit_cards = audit.get("cards", {}) if audit else {}
    red_count = sum(entry["risk"] == "RED" for entry in audit_cards.values())
    lines = [
        "---",
        f"dylight_kind: {_yaml_value('brain-2-dashboard')}",
        f"dylight_schema_version: {MANIFEST_SCHEMA_VERSION}",
        f"tags: {_yaml_value(['dylight/brain-2', 'dylight/dashboard'])}",
        f"cssclasses: {_yaml_value(['dylight-note', 'dylight-dashboard'])}",
        "---",
        "",
        "# DYLIGHT Bridge Evolution — Brain 2",
        "",
        "> [!IMPORTANT] Ranh giới an toàn",
        "> Obsidian là giao diện đọc, liên kết và ghi chú. JSON trong dự án là"
        " nguồn chuẩn; verifier là nơi duy nhất quyết định PASS/FAIL.",
        "",
        "## Trạng thái kho",
        "",
        f"- Tổng số thẻ xuất: **{len(cards)}**",
        f"- DRAFT: **{draft_count}**",
        f"- ENGINEER_APPROVED: **{approved_count}**",
        f"- Thẻ trích nguồn thí nghiệm legacy: **{legacy_count}**",
        f"- Audit risk RED: **{red_count}**",
        f"- Claim cần sửa/kiểm chứng khẩn: **{red_count}**",
        f"- Exporter: `{EXPORTER_VERSION}`",
        "",
    ]
    if legacy_count:
        lines.extend([
            "> [!CAUTION] Có thẻ dùng nguồn legacy",
            "> Giữ chúng ở DRAFT; không dùng làm bằng chứng so sánh thuật toán"
            " cho đến khi được cập nhật từ benchmark công bằng/oracle.",
            "",
        ])
    if audit:
        lines.extend([
            "## Cảnh báo audit toàn kho",
            "",
        ])
        lines.extend(f"- {warning}" for warning in audit["global_warnings"])
        evidence = audit["evidence"]
        lines.extend([
            "",
            f"Audit snapshot: `{_code_text(audit['audit_id'])}` · evidence"
            f" `{_code_text(evidence['ref'])}` · SHA-256 `{evidence['sha256']}`.",
            "",
        ])
    lines.extend([
        "## Standards library",
        "",
        f"- [[{managed_folder}/Standards/TCVN 11823-2017/00 - TCVN 11823-2017|TCVN 11823:2017 - Thiết kế cầu đường bộ]]"
        " - 12 PDF tham khảo, có provenance và mục lục curated.",
        "",
        "## NotebookLM library",
        "",
        f"- [[{managed_folder}/NotebookLM/00 - NotebookLM Bridge Library|32 notebook cầu và Bridge BIM]]"
        " - snapshot nguồn và summary có provenance, REFERENCE_ONLY.",
        "",
        "## Multi-Agent Research Lab",
        "",
        f"- [[{managed_folder}/Research Lab/00 - Research Lab Dashboard|Research Lab Dashboard]]"
        " - phát minh, phép tính, kết quả âm, handoff và review có hash.",
        "",
        "## Knowledge graph",
        "",
        f"- [[{managed_folder}/Rules/00 - Rules Index|Rules Index]] - rule của geometry, solver và verifier.",
        f"- [[{managed_folder}/Variables/00 - Variables Index|Variables Index]] - các biến trong design grammar.",
        "- Luồng chính: **Standard → Rule → Card → Variable**.",
        "",
        "## Chú giải màu",
        "",
        '<span class="dylight-chip dylight-chip-red">Đỏ - claim/risk cần xử lý</span> '
        '<span class="dylight-chip dylight-chip-orange">Cam - DRAFT/partial</span> '
        '<span class="dylight-chip dylight-chip-green">Xanh lá - engineer approved</span>',
        "",
        '<span class="dylight-chip dylight-chip-blue">Xanh dương - tiêu chuẩn</span> '
        '<span class="dylight-chip dylight-chip-purple">Tím - dashboard/rule</span> '
        '<span class="dylight-chip dylight-chip-teal">Xanh ngọc - biến thiết kế</span>',
        "",
        "## Knowledge cards",
        "",
        "| Card | Tiêu đề | Status | Audit | Rules | Nguồn |",
        "|---|---|---|---|---|---|",
    ])
    for card in sorted(cards, key=lambda item: item["card_id"]):
        source = card["source"]
        rules = ", ".join(_table_text(x) for x in card["applies_to"]["rules"]) or "—"
        source_label = ("⚠ legacy · " if _is_legacy_experiment(card) else "")
        source_label += f"{_table_text(source['kind'])}: {_table_text(source['ref'])}"
        card_audit = audit_cards.get(card["card_id"])
        audit_label = (f"{card_audit['risk']} · {card_audit['claim_audit']}"
                       if card_audit else "NOT_AUDITED")
        lines.append(
            f"| [[{managed_folder}/Cards/{card['card_id']}|{card['card_id']}]] |"
            f" {_table_text(card['title'])} | {card['status']} | {audit_label} | {rules} |"
            f" {source_label} |")
    lines.extend([
        "",
        "## Quy trình cập nhật",
        "",
        "1. Sửa hoặc bổ sung KnowledgeCard JSON trong dự án.",
        "2. Chạy `python -m bridge_evolution.cli knowledge-export`.",
        "3. Nếu note Obsidian từng được sửa, exporter báo conflict và không ghi đè.",
        "4. Chỉ kỹ sư có thẩm quyền mới nâng trạng thái lên `ENGINEER_APPROVED`.",
        "",
    ])
    return "\n".join(lines)


def _render_rule_note(rule_id: str, meta: dict, cards: list[dict],
                      managed_folder: str) -> str:
    related_cards = sorted(
        card["card_id"] for card in cards
        if rule_id in card["applies_to"]["rules"])
    card_links = ", ".join(
        f"[[{managed_folder}/Cards/{card_id}|{card_id}]]"
        for card_id in related_cards) or "—"
    variable_links = ", ".join(
        _knowledge_link("Variables", name, managed_folder)
        for name in meta["variables"]) or "—"
    standard_links = ", ".join(
        _standard_link(part, managed_folder) for part in meta["standards"]) or "—"
    tags = ["dylight/rule", f"dylight/rule-layer/{rule_id.split('-')[0].lower()}"]
    cssclasses = ["dylight-note", "dylight-rule",
                  f"dylight-severity-{meta['severity'].lower()}"]
    lines = [
        "---",
        f"dylight_kind: {_yaml_value('rule-node')}",
        f"rule_id: {_yaml_value(rule_id)}",
        f"severity: {_yaml_value(meta['severity'])}",
        f"layer: {_yaml_value(meta['layer'])}",
        f"tags: {_yaml_value(tags)}",
        f"cssclasses: {_yaml_value(cssclasses)}",
        "---", "",
        f"# {rule_id} - {meta['title']}", "",
        meta["description"], "",
        f"- **Severity:** `{meta['severity']}`",
        f"- **Layer:** `{meta['layer']}`",
        f"- **Standards:** {standard_links}",
        f"- **Knowledge cards:** {card_links}",
        f"- **Variables:** {variable_links}", "",
        "> [!IMPORTANT] Rule thực thi",
        "> Note này là node điều hướng. Định nghĩa thực thi vẫn nằm trong code,"
        " catalog và ruleset đã version hóa.", "",
    ]
    return "\n".join(lines)


def _render_variable_note(name: str, meta: dict, cards: list[dict],
                          managed_folder: str) -> str:
    related_cards = sorted(
        card["card_id"] for card in cards
        if name in card["applies_to"]["variables"])
    related_rules = sorted(
        rule_id for rule_id, rule in RULES.items() if name in rule["variables"])
    card_links = ", ".join(
        f"[[{managed_folder}/Cards/{card_id}|{card_id}]]"
        for card_id in related_cards) or "—"
    rule_links = ", ".join(
        _knowledge_link("Rules", rule_id, managed_folder)
        for rule_id in related_rules) or "—"
    standard_links = ", ".join(
        _standard_link(part, managed_folder) for part in meta["standards"]) or "—"
    lines = [
        "---",
        f"dylight_kind: {_yaml_value('design-variable-node')}",
        f"variable: {_yaml_value(name)}",
        f"tags: {_yaml_value(['dylight/variable', 'dylight/design-grammar'])}",
        f"cssclasses: {_yaml_value(['dylight-note', 'dylight-variable'])}",
        "---", "",
        f"# {name} - {meta['title']}", "",
        meta["description"], "",
        f"- **Standards:** {standard_links}",
        f"- **Rules:** {rule_links}",
        f"- **Knowledge cards:** {card_links}", "",
        "> [!NOTE] Miền giá trị",
        "> Miền hợp lệ được lấy từ design grammar/catalog runtime; note này không"
        " được dùng để hard-code miền riêng.", "",
    ]
    return "\n".join(lines)


def _render_taxonomy_index(kind: str, items: dict,
                           managed_folder: str) -> str:
    is_rule = kind == "Rules"
    title = "Rules Index" if is_rule else "Variables Index"
    tag = "dylight/rule-index" if is_rule else "dylight/variable-index"
    rows = [
        "---",
        f"dylight_kind: {_yaml_value('taxonomy-index')}",
        f"tags: {_yaml_value([tag, 'dylight/index'])}",
        f"cssclasses: {_yaml_value(['dylight-note', 'dylight-dashboard'])}",
        "---", "", f"# {title}", "",
        "| ID | Nội dung |", "|---|---|",
    ]
    for identifier, meta in sorted(items.items()):
        rows.append(
            f"| [[{managed_folder}/{kind}/{identifier}|{identifier}]] |"
            f" {meta['title']} |")
    rows.append("")
    return "\n".join(rows)


def _default_obsidian_config_path() -> Path | None:
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / "obsidian" / "obsidian.json"
    if os.name != "nt":
        candidate = Path.home() / ".config" / "obsidian" / "obsidian.json"
        return candidate
    return None


def discover_obsidian_vaults(config_path: str | Path | None = None) -> list[Path]:
    """Đọc registry vault của Obsidian; không thay đổi cấu hình ứng dụng."""
    path = Path(config_path) if config_path is not None else _default_obsidian_config_path()
    if path is None or not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Không đọc được cấu hình Obsidian: {path}") from exc
    vaults = []
    for entry in data.get("vaults", {}).values():
        raw = entry.get("path") if isinstance(entry, dict) else None
        if isinstance(raw, str):
            candidate = Path(raw).expanduser()
            if candidate.is_dir():
                vaults.append(candidate.resolve())
    return sorted(set(vaults), key=lambda item: str(item).casefold())


def resolve_obsidian_vault(vault_dir: str | Path | None = None) -> Path:
    """Ưu tiên tham số, rồi env, cuối cùng auto-discover đúng một vault."""
    raw = vault_dir or os.environ.get("DYLIGHT_OBSIDIAN_VAULT")
    if raw is not None:
        vault = Path(raw).expanduser()
        if not vault.is_dir():
            raise FileNotFoundError(f"Obsidian vault không tồn tại: {vault}")
        return vault.resolve()
    vaults = discover_obsidian_vaults()
    if not vaults:
        raise FileNotFoundError(
            "Không tìm thấy Obsidian vault; truyền --vault hoặc đặt"
            " DYLIGHT_OBSIDIAN_VAULT")
    if len(vaults) != 1:
        raise ValueError("Có nhiều Obsidian vault; cần chỉ định --vault")
    return vaults[0]


def _managed_root(vault: Path, managed_folder: str) -> Path:
    relative = Path(managed_folder)
    if (not managed_folder.strip() or relative.is_absolute()
            or any(part in ("", ".", "..") for part in relative.parts)
            or any(part.casefold() == ".obsidian" for part in relative.parts)):
        raise ValueError("managed_folder phải là đường dẫn tương đối an toàn")
    root = vault.resolve(strict=True)
    target = (root / relative).resolve(strict=False)
    if target == root or root not in target.parents:
        raise ValueError("Managed folder thoát khỏi Obsidian vault")
    if target.exists() and (
            target.is_symlink()
            or getattr(target, "is_junction", lambda: False)()):
        raise ValueError("Managed folder không được là symlink/junction")
    return target


def _safe_target(root: Path, relative_path: str) -> Path:
    relative = Path(relative_path)
    if relative.is_absolute() or any(part in ("", ".", "..") for part in relative.parts):
        raise ValueError(f"Đường dẫn manifest không an toàn: {relative_path}")
    target = (root / relative).resolve(strict=False)
    resolved_root = root.resolve(strict=False)
    if resolved_root not in target.parents:
        raise ValueError(f"Đường dẫn thoát managed folder: {relative_path}")
    return target


def _load_manifest(path: Path) -> dict:
    if not path.exists():
        return {"schema_version": MANIFEST_SCHEMA_VERSION, "files": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Manifest Obsidian không hợp lệ: {path.name}") from exc
    if data.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        raise ValueError("Manifest Obsidian có schema_version không được hỗ trợ")
    files = data.get("files")
    if not isinstance(files, dict):
        raise ValueError("Manifest Obsidian thiếu files map")
    for relative_path, digest in files.items():
        if not isinstance(relative_path, str) or not isinstance(digest, str):
            raise ValueError("Manifest Obsidian có entry sai kiểu")
        _safe_target(path.parent, relative_path)
        if not _SHA256.fullmatch(digest):
            raise ValueError("Manifest Obsidian có SHA-256 không hợp lệ")
    return data


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


def export_obsidian_vault(
        vault_dir: str | Path | None = None, *,
        cards_dir: str | Path | None = None,
        audit_path: str | Path | None = None,
        managed_folder: str = DEFAULT_MANAGED_FOLDER,
        include_draft: bool = True,
        dry_run: bool = False) -> dict:
    """Xuất card vào vault, bảo toàn mọi file người dùng đã sửa hoặc tạo thêm.

    Manifest ghi hash lần xuất gần nhất. Một file chỉ được cập nhật khi còn đúng
    hash đó; nếu người dùng đã sửa, kết quả trả ``conflicts`` và giữ nguyên file.
    Không file nào bị xóa tự động.
    """
    vault = resolve_obsidian_vault(vault_dir)
    managed_root = _managed_root(vault, managed_folder)
    manifest_path = _safe_target(managed_root, MANIFEST_NAME)
    old_manifest = (_load_manifest(manifest_path) if manifest_path.exists()
                    else {"schema_version": MANIFEST_SCHEMA_VERSION, "files": {}})
    old_files = dict(old_manifest.get("files", {}))

    source_dir = Path(cards_dir) if cards_dir is not None else CARDS_DIR
    cards = load_cards(source_dir)
    audit = load_card_audit(audit_path)
    if audit:
        unknown_audits = set(audit["cards"]) - {card["card_id"] for card in cards}
        if unknown_audits:
            raise ValueError(f"Knowledge audit tham chiếu card không tồn tại:"
                             f" {sorted(unknown_audits)}")
    selected = [card for card in cards
                if include_draft or card["status"] == "ENGINEER_APPROVED"]

    outputs: dict[str, bytes] = {
        DASHBOARD_NAME: (
            render_dashboard(selected, audit, managed_folder) + "\n"
        ).encode("utf-8")
    }
    outputs["Rules/00 - Rules Index.md"] = (
        _render_taxonomy_index("Rules", RULES, managed_folder) + "\n").encode("utf-8")
    outputs["Variables/00 - Variables Index.md"] = (
        _render_taxonomy_index("Variables", VARIABLES, managed_folder) + "\n").encode("utf-8")
    for rule_id, meta in RULES.items():
        outputs[f"Rules/{rule_id}.md"] = (
            _render_rule_note(rule_id, meta, selected, managed_folder) + "\n").encode("utf-8")
    for name, meta in VARIABLES.items():
        outputs[f"Variables/{name}.md"] = (
            _render_variable_note(name, meta, selected, managed_folder) + "\n").encode("utf-8")
    card_manifest = {}
    for card in selected:
        canonical_hash = _sha256(_canonical_card_bytes(card))
        canonical_path = f"knowledge/cards/{card['card_id']}.json"
        relative_path = f"Cards/{card['card_id']}.md"
        outputs[relative_path] = render_card_note(
            card, canonical_path, canonical_hash,
            audit["cards"].get(card["card_id"]) if audit else None,
            audit, managed_folder).encode("utf-8")
        card_manifest[card["card_id"]] = {
            "canonical_sha256": canonical_hash,
            "note": relative_path,
            "status": card["status"],
            "version": card["version"],
        }

    written: list[str] = []
    unchanged: list[str] = []
    conflicts: list[str] = []
    new_files = dict(old_files)
    for relative_path, desired in sorted(outputs.items()):
        target = _safe_target(managed_root, relative_path)
        desired_hash = _sha256(desired)
        current_hash = _sha256(target.read_bytes()) if target.is_file() else None
        if current_hash == desired_hash:
            unchanged.append(relative_path)
            new_files[relative_path] = desired_hash
            continue
        if current_hash is not None and old_files.get(relative_path) != current_hash:
            conflicts.append(relative_path)
            continue
        written.append(relative_path)
        new_files[relative_path] = desired_hash
        if not dry_run:
            _atomic_write(target, desired)

    stale = sorted(set(old_files) - set(outputs))
    manifest = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "exporter_version": EXPORTER_VERSION,
        "managed_folder": managed_folder.replace("\\", "/"),
        "files": dict(sorted(new_files.items())),
        "cards": dict(sorted(card_manifest.items())),
        "knowledge_audit_id": audit["audit_id"] if audit else None,
    }
    manifest_bytes = (json.dumps(manifest, ensure_ascii=False, indent=2,
                                 sort_keys=True) + "\n").encode("utf-8")
    manifest_changed = (not manifest_path.is_file()
                        or manifest_path.read_bytes() != manifest_bytes)
    if manifest_changed and not dry_run:
        _atomic_write(manifest_path, manifest_bytes)

    return {
        "vault": str(vault),
        "managed_folder": managed_folder.replace("\\", "/"),
        "cards_exported": len(selected),
        "written": written,
        "unchanged": unchanged,
        "conflicts": conflicts,
        "stale_not_deleted": stale,
        "manifest_changed": manifest_changed,
        "dry_run": dry_run,
    }


__all__ = [
    "DEFAULT_MANAGED_FOLDER",
    "discover_obsidian_vaults",
    "export_obsidian_vault",
    "load_card_audit",
    "render_card_note",
    "render_dashboard",
    "resolve_obsidian_vault",
]
