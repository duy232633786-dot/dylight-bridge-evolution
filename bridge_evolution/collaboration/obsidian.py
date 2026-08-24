"""Conflict-safe Obsidian mirror for long-lived multi-agent research records."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from bridge_evolution import REPO_ROOT
from bridge_evolution.knowledge.obsidian import (
    _atomic_write,
    _load_manifest,
    _managed_root,
    _safe_target,
    resolve_obsidian_vault,
)

from .lab import _all_tasks, _lab_dir, _load_json, validate_lab


MANIFEST_NAME = ".dylight-research-manifest.json"
EXPORTER_VERSION = "research-obsidian/5"


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _yaml(value) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _clean(value) -> str:
    return str(value).replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def _task_link(task_id: str, managed_folder: str) -> str:
    return f"[[{managed_folder}/Research Lab/Tasks/{task_id}|{task_id}]]"


def _amendment_link(path: Path, managed_folder: str) -> str:
    return (
        f"[[{managed_folder}/Research Lab/Amendments/{path.stem}"
        f"|Amendment {path.stem}]]"
    )


def _repair_link(repair: dict, managed_folder: str) -> str:
    repair_id = repair["repair_id"]
    return (
        f"[[{managed_folder}/Research Lab/Repairs/{repair_id}"
        f"|Repair/quarantine {repair_id}]]"
    )


def _source_label(path: Path, lab_root: Path) -> str:
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return f"multiagent/{path.relative_to(lab_root).as_posix()}"


def _quarantined_managed_note_path(moved: dict) -> str | None:
    """Map only canonical handoff/review sources to their exact managed note."""
    parts = moved["source_path"].replace("\\", "/").split("/")
    if len(parts) != 3 or parts[0] != "multiagent":
        return None
    directory = {"handoffs": "Handoffs", "reviews": "Reviews"}.get(parts[1])
    if directory is None or moved.get("category") not in {"HANDOFF", "REVIEW"}:
        return None
    return f"{directory}/{Path(parts[2]).stem}.md"


def _render_task(task: dict, canonical_hash: str, managed_folder: str,
                 handoffs: list[Path], reviews: list[Path],
                 amendments: list[Path], repairs: list[dict]) -> str:
    status = task["status"]
    owner = task.get("owner") or "unassigned"
    tags = [
        "dylight/research-task",
        f"dylight/task-status/{status.lower()}",
        f"dylight/claim/{task['claim_ceiling'].lower()}",
        f"dylight/workstream/{task['workstream']}",
    ]
    lines = [
        "---",
        f"dylight_kind: {_yaml('research-task')}",
        "dylight_schema_version: 1",
        f"dylight_task_id: {_yaml(task['task_id'])}",
        f"dylight_task_status: {_yaml(status)}",
        f"dylight_priority: {_yaml(task['priority'])}",
        f"dylight_owner: {_yaml(owner)}",
        f"dylight_claim_ceiling: {_yaml(task['claim_ceiling'])}",
        f"dylight_required_gates: {_yaml(task['required_gates'])}",
        f"dylight_canonical_source: {_yaml('multiagent/tasks/' + task['task_id'] + '.json')}",
        f"dylight_canonical_sha256: {_yaml(canonical_hash)}",
        f"tags: {_yaml(tags)}",
        f"cssclasses: {_yaml(['dylight-note', 'dylight-research', 'dylight-claim-' + task['claim_ceiling'].lower()])}",
        "---",
        "",
        f"# {task['task_id']} — {task['title']}",
        "",
        "> [!IMPORTANT] Bản ghi nghiên cứu — không phải hồ sơ thiết kế",
        "> Runtime hiện tại chỉ đạt SCREENED. Claim cao hơn cần artifact vật lý thật và review độc lập.",
        "",
        "## Câu hỏi nghiên cứu",
        "",
        task["research_question"],
        "",
        "## Điều phối",
        "",
        f"- Trạng thái: **{status}**",
        f"- Owner: `{owner}`",
        f"- Reviewer: `{task.get('reviewer') or 'chưa gán'}`",
        f"- Workstream: `{task['workstream']}`",
        f"- Claim ceiling: **{task['claim_ceiling']}**",
        f"- Gates: {', '.join(task['required_gates']) or '—'}",
        "- Dependencies: " + (", ".join(_task_link(dep, managed_folder)
                                           for dep in task["dependencies"]) or "—"),
        "",
        "## Tiêu chí nghiệm thu",
        "",
        *[f"- {item}" for item in task["acceptance_criteria"]],
        "",
        "## Artifact bắt buộc",
        "",
        *[f"- `{item}`" for item in task["required_artifacts"]],
        "",
        "## Phạm vi được sửa",
        "",
        *[f"- `{item}`" for item in task["write_scope"]],
        "",
        "## Safety notes",
        "",
        *[f"- {item}" for item in task["safety_notes"]],
        "",
        "## Task contract amendments",
        "",
    ]
    if amendments:
        lines.extend(
            f"- {_amendment_link(path, managed_folder)}" for path in amendments
        )
    else:
        lines.append("- Chưa có.")
    lines.extend([
        "",
        "## Handoff và review",
        "",
    ])
    if not handoffs and not reviews:
        lines.append("- Chưa có.")
    for path in handoffs:
        name = path.stem
        lines.append(f"- [[{managed_folder}/Research Lab/Handoffs/{name}|Handoff {name}]]")
    for path in reviews:
        name = path.stem
        lines.append(f"- [[{managed_folder}/Research Lab/Reviews/{name}|Review {name}]]")
    lines.extend([
        "",
        "## Repair / quarantine",
        "",
    ])
    if repairs:
        lines.extend(f"- {_repair_link(repair, managed_folder)}" for repair in repairs)
    else:
        lines.append("- Chưa có.")
    lines.extend([
        "",
        "## Provenance",
        "",
        f"- Canonical: `multiagent/tasks/{task['task_id']}.json`",
        f"- SHA-256: `{canonical_hash}`",
        "",
    ])
    return "\n".join(lines)


def _render_amendment(
    amendment: dict,
    canonical_path: str,
    canonical_hash: str,
    managed_folder: str,
) -> str:
    previous = amendment.get("previous_amendment_sha256") or "—"
    run_line = ""
    if amendment.get("run_id"):
        run_line = (
            f"- Run: [[{managed_folder}/Research Lab/Runs/{amendment['run_id']}"
            f"|{amendment['run_id']}]]"
        )
    lines = [
        "---",
        f"dylight_kind: {_yaml('task-contract-amendment')}",
        "dylight_schema_version: 1",
        f"dylight_task_id: {_yaml(amendment['task_id'])}",
        f"dylight_amendment_id: {_yaml(amendment['amendment_id'])}",
        f"dylight_amendment_sha256: {_yaml(amendment['amendment_sha256'])}",
        f"dylight_created_at: {_yaml(amendment['created_at'])}",
        f"dylight_authorized_by: {_yaml(amendment['authorized_by'])}",
        f"dylight_canonical_source: {_yaml(canonical_path)}",
        f"dylight_canonical_sha256: {_yaml(canonical_hash)}",
        f"tags: {_yaml(['dylight/task-amendment', 'dylight/provenance/amendment'])}",
        f"cssclasses: {_yaml(['dylight-note', 'dylight-research', 'dylight-provenance'])}",
        "---",
        "",
        f"# Task contract amendment — {amendment['amendment_id']}",
        "",
        "> [!WARNING] Mirror đọc dài hạn — canonical JSON và snapshot là nguồn sự thật",
        "> Snapshot chỉ được tham chiếu bằng path; exporter không sao chép raw snapshot bytes.",
        "",
        f"- Task: {_task_link(amendment['task_id'], managed_folder)}",
    ]
    if run_line:
        lines.append(run_line)
    lines.extend([
        f"- Authorized by: `{amendment['authorized_by']}`",
        f"- Timestamp: `{amendment['created_at']}`",
        f"- Reason: {amendment['reason']}",
        f"- Status: `{amendment['previous_status']}` → `{amendment['next_status']}`",
        "",
        "## Hash chain",
        "",
        f"- Amendment self-hash: `{amendment['amendment_sha256']}`",
        f"- Previous amendment: `{previous}`",
        f"- Pre-task SHA-256: `{amendment['pre_task_sha256']}`",
        f"- Post-task SHA-256: `{amendment['post_task_sha256']}`",
        f"- Snapshot path: `{amendment['snapshot']['path']}`",
        f"- Snapshot SHA-256: `{amendment['snapshot']['sha256']}`",
        "",
        "## Exact field changes",
        "",
        "```json",
        json.dumps(amendment["changes"], ensure_ascii=False, indent=2),
        "```",
        "",
        "## Provenance",
        "",
        f"- Canonical: `{canonical_path}`",
        f"- Canonical file SHA-256: `{canonical_hash}`",
        "",
    ])
    return "\n".join(lines)


def _render_handoff(handoff: dict, canonical_path: str, canonical_hash: str,
                    managed_folder: str) -> str:
    claim = handoff["claim_level"]
    lines = [
        "---",
        f"dylight_kind: {_yaml('research-handoff')}",
        "dylight_schema_version: 1",
        f"dylight_task_id: {_yaml(handoff['task_id'])}",
        f"dylight_agent_id: {_yaml(handoff['agent_id'])}",
        f"dylight_role: {_yaml(handoff['role'])}",
        f"dylight_claim_level: {_yaml(claim)}",
        f"dylight_gates_completed: {_yaml(handoff['gates_completed'])}",
        f"dylight_canonical_source: {_yaml(canonical_path)}",
        f"dylight_canonical_sha256: {_yaml(canonical_hash)}",
        f"tags: {_yaml(['dylight/research-handoff', 'dylight/claim/' + claim.lower()])}",
        f"cssclasses: {_yaml(['dylight-note', 'dylight-research', 'dylight-claim-' + claim.lower()])}",
        "---",
        "",
        f"# Handoff — {handoff['task_id']} · {handoff['agent_id']}",
        "",
        "> [!WARNING] Claim phải được reviewer độc lập kiểm tra",
        "> Obsidian lưu bản đọc dài hạn; artifact gốc và hash bên dưới mới là bằng chứng.",
        "",
        f"Task: {_task_link(handoff['task_id'], managed_folder)}",
        "",
        "## Tóm tắt",
        "",
        handoff["summary"],
        "",
        f"- Role: `{handoff['role']}`",
        f"- Claim level: **{claim}**",
        f"- Gates completed: {', '.join(handoff['gates_completed']) or '—'}",
        "",
        "## Artifact và hash",
        "",
        "| Loại | Đường dẫn canonical | SHA-256 |",
        "|---|---|---|",
        *[f"| {_clean(item['kind'])} | `{_clean(item['path'])}` | `{item['sha256']}` |"
          for item in handoff["artifacts"]],
        "",
        "## Giả định",
        "",
        *([f"- {item}" for item in handoff["assumptions"]] or ["- Không khai báo."]),
        "",
        "## Rủi ro chưa giải quyết",
        "",
        *([f"- {item}" for item in handoff["unresolved_risks"]] or ["- Không khai báo."]),
        "",
        "## Bước kế tiếp",
        "",
        handoff["next_action"],
        "",
        "## Provenance",
        "",
        f"- Canonical: `{canonical_path}`",
        f"- SHA-256: `{canonical_hash}`",
        "",
    ]
    return "\n".join(lines)


def _render_review(review: dict, canonical_path: str, canonical_hash: str,
                   managed_folder: str) -> str:
    decision = review["decision"]
    lines = [
        "---",
        f"dylight_kind: {_yaml('research-review')}",
        "dylight_schema_version: 1",
        f"dylight_task_id: {_yaml(review['task_id'])}",
        f"dylight_reviewer_id: {_yaml(review['reviewer_id'])}",
        f"dylight_review_decision: {_yaml(decision)}",
        f"dylight_canonical_source: {_yaml(canonical_path)}",
        f"dylight_canonical_sha256: {_yaml(canonical_hash)}",
        f"tags: {_yaml(['dylight/research-review', 'dylight/review/' + decision.lower()])}",
        f"cssclasses: {_yaml(['dylight-note', 'dylight-research', 'dylight-review-' + decision.lower()])}",
        "---",
        "",
        f"# Independent review — {review['task_id']} · {decision}",
        "",
        f"Task: {_task_link(review['task_id'], managed_folder)}",
        "",
        f"- Reviewer: `{review['reviewer_id']}`",
        f"- Independence confirmed: `{review['independence_confirmed']}`",
        f"- Handoff SHA-256: `{review['handoff_sha256']}`",
        "",
        "## Gate findings",
        "",
        "| Gate | Trạng thái | Evidence |",
        "|---|---|---|",
        *[f"| {item['gate']} | **{item['status']}** | {_clean(item['evidence'])} |"
          for item in review["gate_findings"]],
        "",
        "## Nhận xét",
        "",
        review["notes"],
        "",
        "## Provenance",
        "",
        f"- Canonical: `{canonical_path}`",
        f"- SHA-256: `{canonical_hash}`",
        "",
    ]
    return "\n".join(lines)


def _render_contaminated_attempt_repair(
    repair: dict,
    canonical_path: str,
    canonical_hash: str,
    managed_folder: str,
) -> str:
    failed = repair["failed_attempt"]
    lines = [
        "---",
        f"dylight_kind: {_yaml('contaminated-attempt-repair')}",
        "dylight_schema_version: 1",
        f"dylight_evidence_status: {_yaml('NOT_EVIDENCE')}",
        f"dylight_repair_id: {_yaml(repair['repair_id'])}",
        f"dylight_run_id: {_yaml(repair['run_id'])}",
        f"dylight_task_id: {_yaml(repair['task_id'])}",
        f"dylight_failed_attempt_sha256: {_yaml(failed['sha256'])}",
        f"dylight_manifest_sha256: {_yaml(repair['manifest_sha256'])}",
        f"dylight_canonical_source: {_yaml(canonical_path)}",
        f"dylight_canonical_sha256: {_yaml(canonical_hash)}",
        f"tags: {_yaml(['dylight/repair-quarantine', 'dylight/evidence/not-evidence'])}",
        f"cssclasses: {_yaml(['dylight-note', 'dylight-research', 'dylight-quarantine'])}",
        "---",
        "",
        f"# Repair / quarantine — {repair['repair_id']}",
        "",
        "> [!DANGER] NOT_EVIDENCE — QUARANTINED",
        "> Các handoff, review và artifact liệt kê dưới đây không còn là bằng chứng canonical.",
        "> Note chỉ giữ path và SHA-256; exporter không sao chép snapshot hoặc raw artifact bytes.",
        "",
        "## Liên kết điều phối",
        "",
        f"- Dashboard: [[{managed_folder}/Research Lab/00 - Research Lab Dashboard|Research Lab Dashboard]]",
        f"- Run: [[{managed_folder}/Research Lab/Runs/{repair['run_id']}|{repair['run_id']}]]",
        f"- Trigger task: {_task_link(repair['task_id'], managed_folder)}",
        "",
        "## Authorization và nguyên nhân",
        "",
        f"- Authorized by: `{repair['authorized_by']}`",
        f"- Created at: `{repair['created_at']}`",
        f"- Reason: {repair['reason']}",
        f"- Evidence disposition: **{repair['evidence_disposition']}**",
        f"- Run status unchanged: `{repair['run_status_unchanged']}`",
        f"- Knowledge sync: `{repair['knowledge_sync_before']}` → `{repair['knowledge_sync_after']}`",
        "",
        "## Failed attempt và manifest",
        "",
        f"- Attempt: `{repair['attempt']}` / provider `{failed['provider']}` / success `{failed['success']}`",
        f"- Attempt record: `{failed['path']}`",
        f"- Failed attempt SHA-256: `{failed['sha256']}`",
        f"- Manifest SHA-256: `{repair['manifest_sha256']}`",
        f"- Previous run SHA-256: `{repair['previous_run_sha256']}`",
        "",
        "## Canonical records/artifacts đã chuyển vào quarantine",
        "",
        "| Category | Source trước repair | Quarantine path | SHA-256 | Disposition |",
        "|---|---|---|---|---|",
        *[
            f"| {item['category']} | `{_clean(item['source_path'])}` | "
            f"`{_clean(item['quarantine_path'])}` | `{item['sha256']}` | "
            f"**{item['disposition']}** |"
            for item in repair["moved"]
        ],
        "",
        "## Task lifecycle đã phục hồi",
        "",
        "| Task | Quan hệ | Attempts | Trước | Sau | Pre SHA-256 | Post SHA-256 |",
        "|---|---|---:|---|---|---|---|",
        *[
            f"| {_task_link(item['task_id'], managed_folder)} | {item['relationship']} | "
            f"{item['attempt_count']} | `{_clean(json.dumps(item['pre_lifecycle'], ensure_ascii=False))}` | "
            f"`{_clean(json.dumps(item['post_lifecycle'], ensure_ascii=False))}` | "
            f"`{item['pre_task_sha256']}` | `{item['post_task_sha256']}` |"
            for item in repair["tasks"]
        ],
        "",
        "## Snapshot/raw-byte boundary",
        "",
        "- Quarantine và snapshot chỉ được tham chiếu bằng canonical path + SHA-256 ở trên.",
        "- Không có raw snapshot, handoff, review hoặc artifact byte nào được nhúng vào note này.",
        "",
        "## Provenance",
        "",
        f"- Canonical repair record: `{canonical_path}`",
        f"- Canonical repair SHA-256: `{canonical_hash}`",
        "",
    ]
    return "\n".join(lines)


def _render_quarantine_tombstone(
    moved: dict,
    repair: dict,
    managed_folder: str,
) -> str:
    source_stem = Path(moved["source_path"]).stem
    return "\n".join([
        "---",
        f"dylight_kind: {_yaml('quarantine-tombstone')}",
        "dylight_schema_version: 1",
        f"dylight_evidence_status: {_yaml('NOT_EVIDENCE')}",
        f"dylight_quarantined_category: {_yaml(moved['category'])}",
        f"dylight_repair_id: {_yaml(repair['repair_id'])}",
        f"dylight_task_id: {_yaml(repair['task_id'])}",
        f"dylight_original_source: {_yaml(moved['source_path'])}",
        f"dylight_quarantine_path: {_yaml(moved['quarantine_path'])}",
        f"dylight_quarantined_sha256: {_yaml(moved['sha256'])}",
        f"tags: {_yaml(['dylight/quarantine-tombstone', 'dylight/evidence/not-evidence'])}",
        f"cssclasses: {_yaml(['dylight-note', 'dylight-research', 'dylight-quarantine'])}",
        "---",
        "",
        f"# QUARANTINED — {moved['category']} · {source_stem}",
        "",
        "> [!DANGER] NOT_EVIDENCE",
        "> Bản ghi từng xuất hiện tại note này đã bị một failed attempt làm nhiễm và không còn canonical.",
        "> Không dùng nội dung cũ, claim, gate finding hoặc review decision cho nghiên cứu/kỹ thuật.",
        "",
        f"- Repair: {_repair_link(repair, managed_folder)}",
        f"- Run: [[{managed_folder}/Research Lab/Runs/{repair['run_id']}|{repair['run_id']}]]",
        f"- Trigger task: {_task_link(repair['task_id'], managed_folder)}",
        f"- Original source: `{moved['source_path']}`",
        f"- Quarantine path: `{moved['quarantine_path']}`",
        f"- Preserved SHA-256: `{moved['sha256']}`",
        f"- Disposition: **{moved['disposition']}**",
        "",
        "Raw bytes không được nhúng; chỉ path và hash được giữ để audit.",
        "",
    ])


def _render_provenance_record(
    value: dict,
    kind: str,
    canonical_path: str,
    canonical_hash: str,
    managed_folder: str,
) -> str:
    record_id = (
        value.get("incident_id") or value.get("correction_id")
        or value.get("review_id") or "unknown"
    )
    decision = value.get("decision")
    tags = ["dylight/provenance", f"dylight/provenance/{kind}"]
    if decision:
        tags.append(f"dylight/review/{decision.lower()}")
    return "\n".join([
        "---",
        f"dylight_kind: {_yaml('provenance-' + kind)}",
        "dylight_schema_version: 1",
        f"dylight_task_id: {_yaml(value['task_id'])}",
        f"dylight_record_id: {_yaml(record_id)}",
        f"dylight_canonical_source: {_yaml(canonical_path)}",
        f"dylight_canonical_sha256: {_yaml(canonical_hash)}",
        f"tags: {_yaml(tags)}",
        f"cssclasses: {_yaml(['dylight-note', 'dylight-research', 'dylight-provenance'])}",
        "---",
        "",
        f"# Provenance {kind} — {record_id}",
        "",
        "> [!WARNING] Lịch sử bất biến — không sửa record hoặc snapshot tại chỗ",
        "> Drift chỉ được chấp nhận khi snapshot, incident, correction handoff và review độc lập đều hợp lệ.",
        "",
        f"Task: {_task_link(value['task_id'], managed_folder)}",
        "",
        "## Canonical record",
        "",
        "```json",
        json.dumps(value, ensure_ascii=False, indent=2),
        "```",
        "",
        "## Provenance",
        "",
        f"- Canonical: `{canonical_path}`",
        f"- SHA-256: `{canonical_hash}`",
        "",
    ])


def _render_brief(brief: dict, canonical_path: str, canonical_hash: str,
                  managed_folder: str) -> str:
    lines = [
        "---",
        f"dylight_kind: {_yaml('research-brief')}",
        "dylight_schema_version: 1",
        f"dylight_brief_id: {_yaml(brief['brief_id'])}",
        f"dylight_autonomy_mode: {_yaml(brief['autonomy_mode'])}",
        f"dylight_claim_ceiling: {_yaml(brief['claim_ceiling'])}",
        f"dylight_canonical_source: {_yaml(canonical_path)}",
        f"dylight_canonical_sha256: {_yaml(canonical_hash)}",
        f"tags: {_yaml(['dylight/research-brief', 'dylight/claim/' + brief['claim_ceiling'].lower()])}",
        f"cssclasses: {_yaml(['dylight-note', 'dylight-research', 'dylight-brief'])}",
        "---",
        "",
        f"# Research brief — {brief['brief_id']}",
        "",
        "> [!IMPORTANT] Đề tài là dữ liệu nghiên cứu, không phải lệnh thực thi tin cậy.",
        "> Claim kỹ thuật bị giới hạn bởi physics gates và human authority.",
        "",
        "## Đề tài",
        "",
        brief["topic"],
        "",
        "## Mục tiêu",
        "",
        *[f"- {item}" for item in brief["objectives"]],
        "",
        "## Ràng buộc",
        "",
        *[f"- {item}" for item in brief["constraints"]],
        "",
        "## Ngân sách tự động",
        "",
        f"- Mode: `{brief['autonomy_mode']}`",
        f"- Claim ceiling: **{brief['claim_ceiling']}**",
        f"- Max tasks/parallel/retries: `{brief['budget']['max_tasks']}` / `{brief['budget']['max_parallel']}` / `{brief['budget']['max_retries']}`",
        f"- Task timeout / wall time: `{brief['budget']['task_timeout_seconds']}s` / `{brief['budget']['wall_time_seconds']}s`",
        f"- Human gates: {', '.join(brief['human_gates'])}",
        "",
        "## Provenance",
        "",
        f"- Canonical: `{canonical_path}`",
        f"- SHA-256: `{canonical_hash}`",
        "",
    ]
    return "\n".join(lines)


def _render_run(run: dict, canonical_path: str, canonical_hash: str,
                managed_folder: str, amendments: list[Path], repairs: list[dict]) -> str:
    lines = [
        "---",
        f"dylight_kind: {_yaml('orchestration-run')}",
        "dylight_schema_version: 1",
        f"dylight_run_id: {_yaml(run['run_id'])}",
        f"dylight_brief_id: {_yaml(run['brief_id'])}",
        f"dylight_run_status: {_yaml(run['status'])}",
        f"dylight_canonical_source: {_yaml(canonical_path)}",
        f"dylight_canonical_sha256: {_yaml(canonical_hash)}",
        f"tags: {_yaml(['dylight/orchestration-run', 'dylight/run/' + run['status'].lower()])}",
        f"cssclasses: {_yaml(['dylight-note', 'dylight-research', 'dylight-run'])}",
        "---",
        "",
        f"# Orchestration run — {run['run_id']}",
        "",
        f"Brief: [[{managed_folder}/Research Lab/Briefs/{run['brief_id']}|{run['brief_id']}]]",
        "",
        f"- Status: **{run['status']}**",
        f"- Planner: `{run['planner']}`",
        f"- Provider policy: `{run['provider_policy']}`",
        f"- Knowledge sync: `{run['knowledge_sync']}`",
        f"- Human gate: {run.get('human_gate') or '—'}",
        "",
        "## Task DAG",
        "",
        *[f"- {_task_link(task_id, managed_folder)} — attempts `{run['attempts'].get(task_id, 0)}`"
          for task_id in run["task_ids"]],
        "",
        "## Task contract amendments",
        "",
    ]
    if amendments:
        lines.extend(
            f"- {_amendment_link(path, managed_folder)}" for path in amendments
        )
    else:
        lines.append("- Chưa có.")
    lines.extend([
        "",
        "## Repair / quarantine",
        "",
    ])
    if repairs:
        lines.extend(f"- {_repair_link(repair, managed_folder)}" for repair in repairs)
    else:
        lines.append("- Chưa có.")
    lines.extend([
        "",
        "## Event log",
        "",
        "| UTC | Event | Task/provider | Message |",
        "|---|---|---|---|",
        *[
            f"| {_clean(item['at'])} | `{_clean(item['kind'])}` | "
            f"{_clean(item.get('task_id', '—'))} / {_clean(item.get('provider', '—'))} | "
            f"{_clean(item['message'])} |"
            for item in run["events"]
        ],
        "",
        "## Provenance",
        "",
        f"- Canonical: `{canonical_path}`",
        f"- SHA-256: `{canonical_hash}`",
        "",
    ])
    return "\n".join(lines)


def _render_dashboard(
    tasks: dict[str, dict], managed_folder: str, amendments: list[Path],
    repairs: list[dict],
) -> str:
    lines = [
        "---",
        f"dylight_kind: {_yaml('research-lab-dashboard')}",
        "dylight_schema_version: 1",
        f"tags: {_yaml(['dylight/research-lab', 'dylight/dashboard'])}",
        f"cssclasses: {_yaml(['dylight-note', 'dylight-dashboard', 'dylight-research'])}",
        "---",
        "",
        "# DYLIGHT — Multi-Agent Research Lab",
        "",
        "> [!IMPORTANT] Physics-in-the-loop + Reality-in-the-loop",
        "> Mọi phát minh, phép tính, kết quả âm và review được lưu tại đây để nghiên cứu lâu dài. PASS/FAIL vẫn thuộc solver/verifier và kỹ sư.",
        "",
        f"Brain 2: [[{managed_folder}/00 - Brain 2 Dashboard|DYLIGHT Brain 2 Dashboard]]",
        "",
        "## Task board",
        "",
        "| Task | Chủ đề | Trạng thái | Owner | Claim ceiling | Gates |",
        "|---|---|---|---|---|---|",
    ]
    for task in sorted(tasks.values(), key=lambda item: (item["priority"], item["task_id"])):
        lines.append(
            f"| {_task_link(task['task_id'], managed_folder)} | {_clean(task['title'])} |"
            f" **{task['status']}** | `{task.get('owner') or '—'}` |"
            f" {task['claim_ceiling']} | {', '.join(task['required_gates']) or '—'} |"
        )
    lines.extend([
        "",
        "## Task contract amendments",
        "",
    ])
    if amendments:
        lines.extend(
            f"- {_amendment_link(path, managed_folder)}" for path in amendments
        )
    else:
        lines.append("- Chưa có.")
    lines.extend([
        "",
        "## Repair / quarantine — NOT_EVIDENCE",
        "",
    ])
    if repairs:
        lines.extend(
            f"- {_repair_link(repair, managed_folder)} — run "
            f"[[{managed_folder}/Research Lab/Runs/{repair['run_id']}|{repair['run_id']}]]; "
            f"trigger {_task_link(repair['task_id'], managed_folder)}"
            for repair in repairs
        )
    else:
        lines.append("- Chưa có.")
    lines.extend([
        "",
        f"Briefs: [[{managed_folder}/Research Lab/Briefs|thư mục Briefs]] · "
        f"Runs: [[{managed_folder}/Research Lab/Runs|thư mục Runs]] · "
        f"Amendments: [[{managed_folder}/Research Lab/Amendments|task contract amendments]] · "
        f"Incidents: [[{managed_folder}/Research Lab/Incidents|provenance incidents]] · "
        f"Corrections: [[{managed_folder}/Research Lab/Corrections|correction handoffs]] · "
        f"Reviews: [[{managed_folder}/Research Lab/Correction Reviews|correction reviews]] · "
        f"Repairs: [[{managed_folder}/Research Lab/Repairs|quarantine repairs]]",
        "",
        "## Quy tắc lưu giữ",
        "",
        "1. Artifact/JSON trong project là canonical; note này là mirror đọc–liên kết.",
        "2. Handoff bắt buộc ghi hash, assumptions, unresolved risks và next action.",
        "3. Kết quả âm được giữ lại để tránh lặp nghiên cứu thất bại.",
        "4. Sửa note thủ công gây conflict; ngoại lệ duy nhất là tombstone NOT_EVIDENCE cho exact managed handoff/review đã quarantine.",
        "",
    ])
    return "\n".join(lines)


def export_research_to_obsidian(
    vault_dir: str | Path | None = None,
    *,
    lab_dir: str | Path | None = None,
    managed_folder: str = "DYLIGHT Bridge Evolution",
    dry_run: bool = False,
) -> dict:
    """Mirror task/handoff/review records into Obsidian without losing edits."""
    root = _lab_dir(lab_dir)
    validation = validate_lab(root)
    if not validation["valid"]:
        raise ValueError(f"Research Lab không hợp lệ: {validation['errors']}")
    vault = resolve_obsidian_vault(vault_dir)
    research_root = _managed_root(vault, f"{managed_folder}/Research Lab")
    manifest_path = _safe_target(research_root, MANIFEST_NAME)
    old_manifest = (_load_manifest(manifest_path) if manifest_path.exists()
                    else {"schema_version": 1, "files": {}})
    old_files = dict(old_manifest.get("files", {}))
    tasks = _all_tasks(root)
    handoffs = sorted((root / "handoffs").glob("*.json"))
    reviews = sorted((root / "reviews").glob("*.json"))
    amendments = sorted((root / "amendments").glob("*.json"))
    incidents = sorted((root / "incidents").glob("*.json"))
    corrections = sorted((root / "corrections").glob("*.json"))
    correction_reviews = sorted((root / "correction_reviews").glob("*.json"))
    repair_paths = sorted(
        (root / "runs").glob("*/repairs/*.contaminated-attempt.r*.json")
    )
    repair_records = [(path, _load_json(path)) for path in repair_paths]
    repairs = [value for _, value in repair_records]
    briefs = sorted((root / "intake").glob("*.json"))
    runs = sorted((root / "runs").glob("*/run.json"))
    outputs: dict[str, bytes] = {
        "00 - Research Lab Dashboard.md": (
            _render_dashboard(tasks, managed_folder, amendments, repairs) + "\n"
        ).encode("utf-8")
    }
    for task_id, task in tasks.items():
        task_source = root / "tasks" / f"{task_id}.json"
        task_handoffs = [path for path in handoffs if path.name.startswith(task_id + ".")]
        task_reviews = [path for path in reviews if path.name.startswith(task_id + ".")]
        task_amendments = [
            path for path in amendments if path.name.startswith(task_id + ".")
        ]
        task_repairs = [
            repair for repair in repairs
            if any(item["task_id"] == task_id for item in repair["tasks"])
        ]
        outputs[f"Tasks/{task_id}.md"] = (
            _render_task(task, _sha256_bytes(task_source.read_bytes()), managed_folder,
                         task_handoffs, task_reviews, task_amendments,
                         task_repairs) + "\n").encode("utf-8")
    for path in amendments:
        value = _load_json(path)
        source = _source_label(path, root)
        outputs[f"Amendments/{path.stem}.md"] = (
            _render_amendment(
                value, source, _sha256_bytes(path.read_bytes()), managed_folder
            ) + "\n"
        ).encode("utf-8")
    for path in handoffs:
        value = _load_json(path)
        source = _source_label(path, root)
        outputs[f"Handoffs/{path.stem}.md"] = (
            _render_handoff(value, source, _sha256_bytes(path.read_bytes()), managed_folder) + "\n").encode("utf-8")
    for path in reviews:
        value = _load_json(path)
        source = _source_label(path, root)
        outputs[f"Reviews/{path.stem}.md"] = (
            _render_review(value, source, _sha256_bytes(path.read_bytes()), managed_folder) + "\n").encode("utf-8")
    for directory, kind, paths in (
        ("Incidents", "incident", incidents),
        ("Corrections", "correction-handoff", corrections),
        ("Correction Reviews", "correction-review", correction_reviews),
    ):
        for path in paths:
            value = _load_json(path)
            source = _source_label(path, root)
            outputs[f"{directory}/{path.stem}.md"] = (
                _render_provenance_record(
                    value, kind, source, _sha256_bytes(path.read_bytes()), managed_folder
                ) + "\n"
            ).encode("utf-8")
    forced_tombstones: set[str] = set()
    for path, repair in repair_records:
        source = _source_label(path, root)
        outputs[f"Repairs/{repair['repair_id']}.md"] = (
            _render_contaminated_attempt_repair(
                repair, source, _sha256_bytes(path.read_bytes()), managed_folder
            ) + "\n"
        ).encode("utf-8")
        for moved in repair["moved"]:
            relative = _quarantined_managed_note_path(moved)
            if relative is None:
                continue
            if relative in forced_tombstones:
                raise ValueError(f"Nhiều repair cùng tombstone managed note: {relative}")
            forced_tombstones.add(relative)
            outputs[relative] = (
                _render_quarantine_tombstone(moved, repair, managed_folder) + "\n"
            ).encode("utf-8")
    for path in briefs:
        value = _load_json(path)
        source = _source_label(path, root)
        outputs[f"Briefs/{path.stem}.md"] = (
            _render_brief(value, source, _sha256_bytes(path.read_bytes()), managed_folder) + "\n").encode("utf-8")
    for path in runs:
        value = _load_json(path)
        source = _source_label(path, root)
        run_amendments = [
            amendment_path for amendment_path in amendments
            if _load_json(amendment_path).get("run_id") == value["run_id"]
        ]
        run_repairs = [repair for repair in repairs if repair["run_id"] == value["run_id"]]
        outputs[f"Runs/{value['run_id']}.md"] = (
            _render_run(
                value, source, _sha256_bytes(path.read_bytes()), managed_folder,
                run_amendments, run_repairs,
            ) + "\n").encode("utf-8")

    written: list[str] = []
    unchanged: list[str] = []
    conflicts: list[str] = []
    new_files = dict(old_files)
    for relative, desired in sorted(outputs.items()):
        target = _safe_target(research_root, relative)
        desired_hash = _sha256_bytes(desired)
        current_hash = _sha256_bytes(target.read_bytes()) if target.is_file() else None
        if current_hash == desired_hash:
            unchanged.append(relative)
            new_files[relative] = desired_hash
            continue
        # A formerly managed handoff/review must not keep presenting quarantined
        # evidence as valid.  Override conflict protection only for the exact
        # manifest-tracked managed note path derived from the repair record.
        force_managed_tombstone = relative in forced_tombstones and relative in old_files
        if (
            current_hash is not None
            and old_files.get(relative) != current_hash
            and not force_managed_tombstone
        ):
            conflicts.append(relative)
            continue
        written.append(relative)
        new_files[relative] = desired_hash
        if not dry_run:
            _atomic_write(target, desired)

    stale = sorted(set(old_files) - set(outputs))
    manifest = {
        "schema_version": 1,
        "exporter_version": EXPORTER_VERSION,
        "files": dict(sorted(new_files.items())),
    }
    manifest_bytes = (json.dumps(manifest, ensure_ascii=False, indent=2,
                                 sort_keys=True) + "\n").encode("utf-8")
    manifest_changed = (not manifest_path.is_file()
                        or manifest_path.read_bytes() != manifest_bytes)
    if manifest_changed and not dry_run:
        _atomic_write(manifest_path, manifest_bytes)
    return {
        "vault": str(vault),
        "managed_folder": f"{managed_folder}/Research Lab",
        "tasks_exported": len(tasks),
        "handoffs_exported": len(handoffs),
        "reviews_exported": len(reviews),
        "amendments_exported": len(amendments),
        "incidents_exported": len(incidents),
        "corrections_exported": len(corrections),
        "correction_reviews_exported": len(correction_reviews),
        "repairs_exported": len(repair_records),
        "quarantine_tombstones_exported": len(forced_tombstones),
        "briefs_exported": len(briefs),
        "runs_exported": len(runs),
        "written": written,
        "unchanged": unchanged,
        "conflicts": conflicts,
        "stale_not_deleted": stale,
        "manifest_changed": manifest_changed,
        "dry_run": dry_run,
    }
