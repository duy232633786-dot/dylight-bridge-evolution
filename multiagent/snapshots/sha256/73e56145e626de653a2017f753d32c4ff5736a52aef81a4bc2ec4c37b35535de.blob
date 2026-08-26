"""Atomic file protocol shared by Codex, Claude, OpenCode and Antigravity.

The protocol deliberately coordinates artifacts, not model conversations.  Each
agent keeps its own credentials and transcript while task ownership, hashes and
independent review remain inspectable in the project workspace.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import tempfile
from typing import Iterable
import uuid

from jsonschema import Draft202012Validator

from bridge_evolution import CONTRACTS_DIR, REPO_ROOT


CLAIM_ORDER = {
    "IDEA": 0,
    "SCREENED": 1,
    "NUMERICALLY_VERIFIED": 2,
    "LAB_VALIDATED": 3,
    "PILOT_VALIDATED": 4,
    "ENGINEERING_CANDIDATE": 5,
}
CLAIM_GATES = {
    "IDEA": set(),
    "SCREENED": {"G0", "G1", "G2"},
    "NUMERICALLY_VERIFIED": {"G0", "G1", "G2", "G3", "G4"},
    "LAB_VALIDATED": {"G0", "G1", "G2", "G3", "G4", "G5"},
    "PILOT_VALIDATED": {"G0", "G1", "G2", "G3", "G4", "G5", "G6"},
    "ENGINEERING_CANDIDATE": {"G0", "G1", "G2", "G3", "G4", "G5", "G6", "G7"},
}
LEGACY_CEILING_EXEMPTIONS = frozenset({
    "BRD-003.claude.r001.json",
    "BRD-014.antigravity.r001.json",
})
TASK_ID_RE = re.compile(r"^(?:BRD-[0-9]{3}|RND-[a-f0-9]{8}-[0-9]{2})$")
TASK_AMENDABLE_STATES = {"BACKLOG", "READY", "BLOCKED"}
TASK_AMENDABLE_FIELDS = {
    "title",
    "research_question",
    "required_gates",
    "claim_ceiling",
    "acceptance_criteria",
    "safety_notes",
    "human_gate",
    "status",
}
TASK_AMENDMENT_TRANSITIONS = {
    "BACKLOG": {"BACKLOG", "READY"},
    "READY": {"BACKLOG", "READY"},
    "BLOCKED": {"BACKLOG", "READY", "BLOCKED"},
}
# These fields are changed by the normal claim/submit/review/recovery lifecycle.
# The task contract itself is every other field and remains pinned by amendments.
TASK_LIFECYCLE_FIELDS = {
    "status", "owner", "reviewer", "review_notes", "preferred_provider"
}


def _lab_dir(lab_dir: str | Path | None = None) -> Path:
    configured = lab_dir or os.environ.get("DYLIGHT_MULTIAGENT_DIR")
    return Path(configured).resolve() if configured else (REPO_ROOT / "multiagent").resolve()


def _schema(name: str) -> dict:
    return json.loads((CONTRACTS_DIR / name).read_text(encoding="utf-8"))


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _json_file_bytes(value: dict) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _task_contract(value: dict) -> dict:
    return {
        key: item for key, item in value.items()
        if key not in TASK_LIFECYCLE_FIELDS
    }


def _amendment_sha256(value: dict) -> str:
    """Hash the canonical amendment payload, excluding its self-hash field."""
    payload = {key: item for key, item in value.items() if key != "amendment_sha256"}
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _snapshot_path(root: Path, sha256: str) -> Path:
    return (root / "snapshots" / "sha256" / f"{sha256}.blob").resolve()


def _ensure_artifact_snapshot(root: Path, artifact: dict) -> Path:
    """Persist exact reviewed bytes under their SHA-256 without overwriting."""
    source = _project_path(artifact["path"])
    if not source.is_file():
        raise FileNotFoundError(source)
    expected = artifact["sha256"]
    if _sha256(source) != expected:
        raise ValueError(
            f"Artifact đã drift trước review: {artifact['path']} không khớp {expected}"
        )
    target = _snapshot_path(root, expected)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if not target.is_file() or _sha256(target) != expected:
            raise ValueError(f"Snapshot path tồn tại nhưng bytes sai hash: {target}")
        return target
    try:
        with target.open("xb") as stream:
            stream.write(source.read_bytes())
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError as exc:
        raise FileExistsError(f"Snapshot được tạo đồng thời: {target}") from exc
    return target


def _atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def _atomic_bytes(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def _ensure_exact_snapshot(path: Path, value: bytes, expected_sha256: str) -> None:
    if hashlib.sha256(value).hexdigest() != expected_sha256:
        raise ValueError("Snapshot input không khớp expected SHA-256")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if not path.is_file() or _sha256(path) != expected_sha256:
            raise ValueError(f"Snapshot path tồn tại nhưng bytes sai hash: {path}")
        return
    try:
        with path.open("xb") as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError as exc:
        raise FileExistsError(f"Snapshot được tạo đồng thời: {path}") from exc


def _exclusive_json(path: Path, value: dict) -> None:
    """Create an immutable canonical record and refuse in-place replacement."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError as exc:
        raise FileExistsError(f"Từ chối ghi đè canonical record: {path}") from exc


def _project_path(relative: str) -> Path:
    path = (REPO_ROOT / relative).resolve()
    try:
        path.relative_to(REPO_ROOT.resolve())
    except ValueError as exc:
        raise ValueError(f"Đường dẫn vượt khỏi project: {relative}") from exc
    return path


def _lab_link_path(root: Path, relative: str) -> Path:
    """Resolve a stored ``multiagent/...`` link against the selected lab copy."""
    normalized = Path(relative.replace("/", os.sep))
    if not normalized.parts or normalized.parts[0] != "multiagent":
        raise ValueError(f"Lab record path phải bắt đầu bằng multiagent/: {relative}")
    path = (root / Path(*normalized.parts[1:])).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"Lab record path vượt khỏi lab directory: {relative}") from exc
    return path


def _lab_relative(root: Path, path: Path) -> str:
    try:
        inside = path.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"Đường dẫn phải nằm trong lab directory: {path}") from exc
    return (Path("multiagent") / inside).as_posix()


def _record_collection(
    root: Path,
    directory: str,
    schema_name: str,
    id_field: str,
    errors: list[str],
) -> tuple[dict[str, tuple[Path, dict]], dict[str, tuple[Path, dict]]]:
    """Load immutable records, returning all and schema-valid subsets by ID."""
    all_records: dict[str, tuple[Path, dict]] = {}
    valid_records: dict[str, tuple[Path, dict]] = {}
    validator = Draft202012Validator(_schema(schema_name))
    for path in sorted((root / directory).glob("*.json")):
        try:
            value = _load_json(path)
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"{path.name}: {exc}")
            continue
        record_id = value.get(id_field, path.stem)
        if record_id in all_records:
            errors.append(f"{path.name}: trùng {id_field} {record_id}")
            continue
        all_records[record_id] = (path, value)
        schema_errors = list(validator.iter_errors(value))
        for error in schema_errors:
            errors.append(f"{path.name}: {error.json_path}: {error.message}")
        if not schema_errors:
            valid_records[record_id] = (path, value)
    return all_records, valid_records


def _task_runs(root: Path, task_id: str) -> list[tuple[Path, dict]]:
    matches = []
    validator = Draft202012Validator(_schema("orchestration_run.schema.json"))
    for path in sorted((root / "runs").glob("*/run.json")):
        value = _load_json(path)
        if task_id not in value.get("task_ids", []):
            continue
        schema_errors = list(validator.iter_errors(value))
        if schema_errors:
            raise ValueError(
                f"Run chứa {task_id} không hợp lệ: "
                + "; ".join(error.message for error in schema_errors)
            )
        matches.append((path, value))
    return matches


def _amendment_head(
    root: Path, task_id: str, current_task_sha256: str
) -> tuple[str | None, list[tuple[Path, dict]]]:
    """Return the unique amendment head, refusing malformed or stale chains."""
    validator = Draft202012Validator(_schema("task_contract_amendment.schema.json"))
    records: list[tuple[Path, dict]] = []
    by_hash: dict[str, tuple[Path, dict]] = {}
    referenced: set[str] = set()
    for path in sorted((root / "amendments").glob("*.json")):
        value = _load_json(path)
        if value.get("task_id") != task_id:
            continue
        schema_errors = list(validator.iter_errors(value))
        if schema_errors:
            raise ValueError(
                f"Amendment chain {task_id} không hợp lệ: "
                + "; ".join(error.message for error in schema_errors)
            )
        observed = _amendment_sha256(value)
        if observed != value["amendment_sha256"]:
            raise ValueError(f"Amendment {value['amendment_id']} có self-hash sai")
        if observed in by_hash:
            raise ValueError(f"Amendment hash bị trùng cho {task_id}: {observed}")
        by_hash[observed] = (path, value)
        previous = value.get("previous_amendment_sha256")
        if previous:
            referenced.add(previous)
        records.append((path, value))
    if not records:
        return None, []
    for _, value in records:
        previous = value.get("previous_amendment_sha256")
        if previous:
            parent = by_hash.get(previous)
            if not parent or parent[1]["post_task_sha256"] != value["pre_task_sha256"]:
                raise ValueError(f"Amendment chain {task_id} bị đứt")
    heads = [item for digest, item in by_hash.items() if digest not in referenced]
    roots = [item for item in records if item[1].get("previous_amendment_sha256") is None]
    if len(heads) != 1 or len(roots) != 1:
        raise ValueError(f"Amendment chain {task_id} phải có đúng một root và một head")
    head_path, head = heads[0]
    task = _load_json(_task_path(root, task_id))
    if current_task_sha256 != head["post_task_sha256"]:
        # Claim/review/recovery mutate lifecycle metadata after a valid amendment.
        snapshot = _load_json(_lab_link_path(root, head["snapshot"]["path"]))
        reconstructed = dict(snapshot)
        for change in head["changes"]:
            reconstructed[change["field"]] = change["after"]
        if _task_contract(task) != _task_contract(reconstructed):
            raise ValueError(
                f"Task contract {task_id} đã drift khỏi amendment head "
                f"{head['amendment_id']}"
            )
    return head["amendment_sha256"], records


@contextmanager
def _task_lock(root: Path, task_id: str, agent_id: str):
    locks = root / ".locks"
    locks.mkdir(parents=True, exist_ok=True)
    path = locks / f"{task_id}.lock"
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise RuntimeError(f"Task {task_id} đang được một tiến trình khác cập nhật: {path}") from exc
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(agent_id + "\n")
        yield
    finally:
        path.unlink(missing_ok=True)


def _task_path(root: Path, task_id: str) -> Path:
    if not TASK_ID_RE.fullmatch(task_id):
        raise ValueError(f"task_id không hợp lệ: {task_id}")
    path = (root / "tasks" / f"{task_id}.json").resolve()
    if path.parent != (root / "tasks").resolve():
        raise ValueError("task path vượt khỏi task directory")
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


def _all_tasks(root: Path) -> dict[str, dict]:
    tasks: dict[str, dict] = {}
    for path in sorted((root / "tasks").glob("*.json")):
        task = _load_json(path)
        task_id = task.get("task_id", path.stem)
        if not TASK_ID_RE.fullmatch(task_id):
            raise ValueError(f"task_id không hợp lệ trong {path.name}: {task_id}")
        if task_id in tasks:
            raise ValueError(f"Trùng task_id {task_id}")
        tasks[task_id] = task
    return tasks


def _strict_project_relative(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("path phải là chuỗi project-relative")
    path = PurePosixPath(value.replace("\\", "/"))
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"path không an toàn: {value}")
    if path.parts[0].endswith(":"):
        raise ValueError(f"path không được là đường dẫn ổ đĩa: {value}")
    return path.as_posix()


def _repair_source_path(root: Path, relative: str) -> Path:
    normalized = _strict_project_relative(relative)
    parts = PurePosixPath(normalized).parts
    if parts[0] == "multiagent":
        path = (root / Path(*parts[1:])).resolve()
        boundary = root.resolve()
    else:
        path = (REPO_ROOT / Path(*parts)).resolve()
        boundary = REPO_ROOT.resolve()
    try:
        path.relative_to(boundary)
    except ValueError as exc:
        raise ValueError(f"path vượt khỏi boundary: {relative}") from exc
    return path


def _repair_descendants(tasks: dict[str, dict], trigger: str) -> set[str]:
    descendants: set[str] = set()
    changed = True
    while changed:
        changed = False
        for task_id, task in tasks.items():
            if task_id == trigger or task_id in descendants:
                continue
            dependencies = set(task.get("dependencies", []))
            if trigger in dependencies or dependencies & descendants:
                descendants.add(task_id)
                changed = True
    return descendants


def _repair_candidates(
    run: dict, tasks: dict[str, dict], trigger: str, attempt: dict
) -> dict[str, dict]:
    descendants = _repair_descendants(tasks, trigger) & set(run.get("task_ids", []))
    affected = {trigger, *descendants}
    artifacts = {
        _strict_project_relative(path): owner
        for owner in affected
        for path in tasks.get(owner, {}).get("required_artifacts", [])
    }
    changed_files = {
        _strict_project_relative(path) for path in attempt.get("changed_files", [])
    }
    candidates: dict[str, dict] = {}
    for supplied in attempt.get("out_of_scope", []):
        path = _strict_project_relative(supplied)
        if path not in changed_files:
            continue
        parts = PurePosixPath(path).parts
        if len(parts) == 3 and parts[:2] == ("multiagent", "tasks"):
            owner = PurePosixPath(parts[-1]).stem
            if owner == trigger:
                candidates[path] = {
                    "disposition": "RESTORE_TRIGGER_LIFECYCLE", "task_id": owner,
                }
            elif owner in descendants:
                candidates[path] = {
                    "disposition": "RESTORE_DOWNSTREAM_LIFECYCLE", "task_id": owner,
                }
            continue
        if len(parts) == 3 and parts[:2] in {
            ("multiagent", "handoffs"), ("multiagent", "reviews")
        }:
            matching = next(
                (owner for owner in affected if parts[-1].startswith(owner + ".")), None
            )
            if matching:
                candidates[path] = {
                    "disposition": "QUARANTINE_NOT_EVIDENCE",
                    "task_id": matching,
                    "category": "HANDOFF" if parts[1] == "handoffs" else "REVIEW",
                }
            continue
        if path in artifacts:
            candidates[path] = {
                "disposition": "QUARANTINE_NOT_EVIDENCE",
                "task_id": artifacts[path],
                "category": "ARTIFACT",
            }
    # A failed attempt with proven canonical out-of-scope contamination cannot
    # leave any changed required artifact canonical, including its in-scope
    # trigger artifact.  Without the initial candidate this expansion is not
    # applied, avoiding false positives for ordinary failed drafts.
    if candidates:
        for path in changed_files:
            if path in artifacts:
                candidates.setdefault(path, {
                    "disposition": "QUARANTINE_NOT_EVIDENCE",
                    "task_id": artifacts[path],
                    "category": "ARTIFACT",
                })
    return candidates


def _repair_manifest_sha256(entries: list[dict]) -> str:
    encoded = json.dumps(
        sorted(entries, key=lambda item: item["path"]),
        ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _validate_contaminated_attempt_repairs(
    root: Path, tasks: dict[str, dict], errors: list[str]
) -> None:
    """Validate fail-closed quarantine records and detect un-repaired state."""
    repair_validator = Draft202012Validator(
        _schema("orchestration_contaminated_attempt_repair.schema.json")
    )
    valid_coverages: dict[tuple[str, str, int], set[str]] = {}
    seen_repair_ids: set[str] = set()
    repair_paths = sorted(
        (root / "runs").glob("*/repairs/*.contaminated-attempt.r*.json")
    )
    for repair_path in repair_paths:
        prefix = repair_path.relative_to(root).as_posix()
        try:
            repair = _load_json(repair_path)
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"{prefix}: {exc}")
            continue
        schema_errors = list(repair_validator.iter_errors(repair))
        for error in schema_errors:
            errors.append(f"{prefix}: {error.json_path}: {error.message}")
        if schema_errors:
            continue
        repair_id = repair["repair_id"]
        if repair_id in seen_repair_ids:
            errors.append(f"{prefix}: trùng repair_id {repair_id}")
            continue
        seen_repair_ids.add(repair_id)
        link_errors: list[str] = []
        run_path = root / "runs" / repair["run_id"] / "run.json"
        if repair_path.parent.parent.name != repair["run_id"]:
            link_errors.append("repair record nằm sai run directory")
        if not re.fullmatch(
            rf"{re.escape(repair['task_id'])}\.contaminated-attempt\.r[0-9]{{3}}\.json",
            repair_path.name,
        ):
            link_errors.append("filename không khớp task_id/revision")
        if not run_path.is_file():
            link_errors.append("thiếu run canonical")
            run = None
        else:
            try:
                run = _load_json(run_path)
                run_schema_errors = list(Draft202012Validator(
                    _schema("orchestration_run.schema.json")
                ).iter_errors(run))
                if run_schema_errors:
                    link_errors.append("run canonical không hợp lệ")
            except (OSError, json.JSONDecodeError) as exc:
                run = None
                link_errors.append(f"run canonical không đọc được: {exc}")
        attempt_path = root / Path(*PurePosixPath(repair["failed_attempt"]["path"]).parts)
        attempt = None
        if not attempt_path.is_file():
            link_errors.append("thiếu immutable failed attempt")
        elif _sha256(attempt_path) != repair["failed_attempt"]["sha256"]:
            link_errors.append("failed attempt hash không khớp")
        else:
            try:
                attempt = _load_json(attempt_path)
            except (OSError, json.JSONDecodeError) as exc:
                link_errors.append(f"failed attempt không đọc được: {exc}")
        if attempt is not None and not (
            attempt.get("task_id") == repair["task_id"]
            and attempt.get("kind") == "WORK"
            and attempt.get("attempt") == repair["attempt"]
            and attempt.get("success") is False
            and attempt.get("provider_result", {}).get("provider")
            == repair["failed_attempt"]["provider"]
        ):
            link_errors.append("failed attempt linkage không khớp")
        if run is not None:
            if repair["task_id"] not in run.get("task_ids", []):
                link_errors.append("trigger task không thuộc run")
            if run.get("attempts", {}).get(repair["task_id"], 0) < repair["attempt"]:
                link_errors.append("repair attempt vượt quá số attempts của task trong run")
            event_matches = [
                event for event in run.get("events", [])
                if event.get("kind") == "CONTAMINATED_ATTEMPT_QUARANTINED"
                and event.get("task_id") == repair["task_id"]
                and repair_id in event.get("message", "")
            ]
            if len(event_matches) != 1:
                link_errors.append("thiếu hoặc trùng quarantine event")
            brief_path = root / "intake" / f"{run.get('brief_id')}.json"
            if not brief_path.is_file():
                link_errors.append("thiếu brief để xác minh authorized_by")
            else:
                try:
                    brief = _load_json(brief_path)
                    if repair["authorized_by"] != brief.get("requested_by"):
                        link_errors.append("authorized_by không phải brief requester")
                except (OSError, json.JSONDecodeError) as exc:
                    link_errors.append(f"brief không đọc được: {exc}")

        task_paths: set[str] = set()
        manifest_entries: list[dict] = []
        trigger_count = 0
        for item in repair["tasks"]:
            if item["path"] in task_paths:
                link_errors.append(f"task path trùng: {item['path']}")
                continue
            task_paths.add(item["path"])
            expected_disposition = (
                "RESTORE_TRIGGER_LIFECYCLE"
                if item["relationship"] == "TRIGGER"
                else "RESTORE_DOWNSTREAM_LIFECYCLE"
            )
            trigger_count += int(item["relationship"] == "TRIGGER")
            manifest_entries.append({
                "path": item["path"],
                "sha256": item["pre_task_sha256"],
                "disposition": expected_disposition,
            })
            current = tasks.get(item["task_id"])
            if current is None:
                link_errors.append(f"restored task không tồn tại: {item['task_id']}")
                continue
            if item["path"] != f"multiagent/tasks/{item['task_id']}.json":
                link_errors.append("task path/task_id không khớp")
            expected_lifecycle = item["post_lifecycle"]
            if item["relationship"] == "TRIGGER":
                provider = repair["failed_attempt"]["provider"]
                if expected_lifecycle != {
                    "status": "BLOCKED", "owner": provider,
                    "reviewer": None, "review_notes": [],
                }:
                    link_errors.append("trigger post lifecycle không fail-closed")
            else:
                if item["attempt_count"] != 0:
                    link_errors.append("downstream restored task có attempt_count > 0")
                if expected_lifecycle != {
                    "status": "READY", "owner": None,
                    "reviewer": None, "review_notes": [],
                }:
                    link_errors.append("downstream post lifecycle không sạch")
            # While the run remains at the repaired FAILED state, lifecycle and
            # full task bytes must still equal the recorded commit point.
            if (
                run is not None
                and run.get("status") == "FAILED"
                and run.get("attempts", {}).get(repair["task_id"]) == repair["attempt"]
            ):
                observed_lifecycle = {
                    "status": current.get("status"),
                    "owner": current.get("owner"),
                    "reviewer": current.get("reviewer"),
                    "review_notes": list(current.get("review_notes", [])),
                }
                if observed_lifecycle != expected_lifecycle:
                    link_errors.append(f"restored lifecycle drift: {item['task_id']}")
                current_path = root / "tasks" / f"{item['task_id']}.json"
                if current_path.is_file() and _sha256(current_path) != item["post_task_sha256"]:
                    link_errors.append(f"restored task hash drift: {item['task_id']}")
        if trigger_count != 1:
            link_errors.append("repair phải có đúng một trigger task")

        moved_sources: set[str] = set()
        for item in repair["moved"]:
            source_path = item["source_path"]
            if source_path in moved_sources:
                link_errors.append(f"moved source trùng: {source_path}")
                continue
            moved_sources.add(source_path)
            manifest_entries.append({
                "path": source_path,
                "sha256": item["sha256"],
                "disposition": "QUARANTINE_NOT_EVIDENCE",
            })
            expected_category = item["category"].lower() + "s"
            expected_quarantine = (
                root / "quarantine" / "contaminated_attempts" / repair_id
                / expected_category / PurePosixPath(source_path).name
            ).resolve()
            stored_quarantine = (root / Path(
                *PurePosixPath(item["quarantine_path"]).parts
            )).resolve()
            if stored_quarantine != expected_quarantine:
                link_errors.append(f"quarantine path không canonical: {source_path}")
            elif not stored_quarantine.is_file():
                link_errors.append(f"thiếu quarantine bytes: {source_path}")
            elif _sha256(stored_quarantine) != item["sha256"]:
                link_errors.append(f"quarantine hash không khớp: {source_path}")
            try:
                canonical_source = _repair_source_path(root, source_path)
                if canonical_source.exists():
                    link_errors.append(f"source vẫn còn canonical sau quarantine: {source_path}")
            except ValueError as exc:
                link_errors.append(str(exc))

        if repair["manifest_sha256"] != _repair_manifest_sha256(manifest_entries):
            link_errors.append("manifest_sha256 không khớp exact record entries")
        candidates: dict[str, dict] = {}
        if run is not None and attempt is not None:
            try:
                candidates = _repair_candidates(run, tasks, repair["task_id"], attempt)
            except (KeyError, ValueError) as exc:
                link_errors.append(f"không tái dựng được contamination set: {exc}")
            if set(candidates) != task_paths | moved_sources:
                link_errors.append("repair không phủ chính xác canonical contamination set")
            else:
                for entry in manifest_entries:
                    if candidates[entry["path"]]["disposition"] != entry["disposition"]:
                        link_errors.append(f"disposition lệch attempt: {entry['path']}")
        for message in link_errors:
            errors.append(f"{prefix}: {message}")
        if not link_errors:
            key = (repair["run_id"], repair["task_id"], repair["attempt"])
            if key in valid_coverages:
                errors.append(f"{prefix}: nhiều repair cho cùng attempt")
            else:
                valid_coverages[key] = set(candidates)

    # Any failed attempt that wrote canonical lifecycle/evidence out of scope is
    # invalid until one exact, valid quarantine repair covers it.
    run_validator = Draft202012Validator(_schema("orchestration_run.schema.json"))
    for run_path in sorted((root / "runs").glob("*/run.json")):
        try:
            run = _load_json(run_path)
        except (OSError, json.JSONDecodeError):
            continue
        if list(run_validator.iter_errors(run)):
            continue
        attempts_root = run_path.parent / "attempts"
        for attempt_path in sorted(attempts_root.glob("*.work.r*.json")):
            try:
                attempt = _load_json(attempt_path)
                if attempt.get("success") is not False or not attempt.get("out_of_scope"):
                    continue
                trigger = attempt.get("task_id")
                if trigger not in run.get("task_ids", []):
                    continue
                candidates = _repair_candidates(run, tasks, trigger, attempt)
            except (OSError, KeyError, ValueError, json.JSONDecodeError):
                continue
            if not candidates:
                continue
            key = (run["run_id"], trigger, attempt.get("attempt"))
            if valid_coverages.get(key) != set(candidates):
                errors.append(
                    f"{attempt_path.relative_to(root).as_posix()}: canonical contamination "
                    "chưa có valid repair/quarantine"
                )


def validate_lab(lab_dir: str | Path | None = None) -> dict:
    """Validate schemas, graph links, handoff hashes and review independence."""
    root = _lab_dir(lab_dir)
    errors: list[str] = []
    if not (root / "lab.json").is_file():
        errors.append(f"Thiếu {root / 'lab.json'}")
        return {"valid": False, "errors": errors, "task_count": 0}

    try:
        lab_config = _load_json(root / "lab.json")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return {"valid": False, "errors": [f"lab.json không hợp lệ: {exc}"], "task_count": 0}
    project_claim_ceiling = lab_config.get("current_project_claim_ceiling", "SCREENED")

    task_validator = Draft202012Validator(_schema("research_task.schema.json"))
    handoff_validator = Draft202012Validator(_schema("research_handoff.schema.json"))
    review_validator = Draft202012Validator(_schema("research_review.schema.json"))
    try:
        tasks = _all_tasks(root)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return {"valid": False, "errors": [str(exc)], "task_count": 0}

    for task_id, task in tasks.items():
        for error in task_validator.iter_errors(task):
            errors.append(f"{task_id}: {error.json_path}: {error.message}")
        if task.get("task_id") != task_id:
            errors.append(f"{task_id}: tên file và task_id không khớp")
        missing = sorted(set(task.get("dependencies", [])) - tasks.keys())
        if missing:
            errors.append(f"{task_id}: dependency không tồn tại: {missing}")
        if task_id in task.get("dependencies", []):
            errors.append(f"{task_id}: task không được phụ thuộc chính nó")
        if task.get("status") in {"ACTIVE", "REVIEW"} and not task.get("owner"):
            errors.append(f"{task_id}: {task.get('status')} nhưng thiếu owner")
        if task.get("owner") and task.get("owner") == task.get("reviewer"):
            errors.append(f"{task_id}: owner và reviewer phải độc lập")

    # Dependency cycles make an autonomous scheduler wait forever.
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(task_id: str, trail: list[str]) -> None:
        if task_id in visiting:
            errors.append("Dependency cycle: " + " -> ".join([*trail, task_id]))
            return
        if task_id in visited:
            return
        visiting.add(task_id)
        for dependency in tasks[task_id].get("dependencies", []):
            if dependency in tasks:
                visit(dependency, [*trail, task_id])
        visiting.remove(task_id)
        visited.add(task_id)

    for task_id in tasks:
        visit(task_id, [])

    _validate_contaminated_attempt_repairs(root, tasks, errors)

    _, valid_amendments = _record_collection(
        root, "amendments", "task_contract_amendment.schema.json",
        "amendment_id", errors)
    amendments_by_hash: dict[str, tuple[Path, dict]] = {}
    amendments_by_task: dict[str, list[tuple[Path, dict]]] = {}
    reconstructed_by_hash: dict[str, dict] = {}
    amendment_link_valid: dict[str, bool] = {}
    for amendment_id, (path, amendment) in valid_amendments.items():
        link_errors: list[str] = []
        observed_amendment_sha = _amendment_sha256(amendment)
        if observed_amendment_sha != amendment["amendment_sha256"]:
            link_errors.append("amendment_sha256 không khớp canonical payload")
        if observed_amendment_sha in amendments_by_hash:
            link_errors.append("amendment_sha256 bị trùng")
        else:
            amendments_by_hash[observed_amendment_sha] = (path, amendment)
        if not re.fullmatch(
            rf"{re.escape(amendment['task_id'])}\.amendment\.r[0-9]{{3}}\.json",
            path.name,
        ):
            link_errors.append("filename không khớp task_id/revision")
        task = tasks.get(amendment["task_id"])
        if not task:
            link_errors.append("task_id không tồn tại")
        fields = [change["field"] for change in amendment["changes"]]
        if len(fields) != len(set(fields)):
            link_errors.append("mỗi field chỉ được xuất hiện một lần")
        unsupported = sorted(set(fields) - TASK_AMENDABLE_FIELDS)
        if unsupported:
            link_errors.append(f"field không được amendment: {unsupported}")
        snapshot_value = None
        try:
            snapshot_path = _lab_link_path(root, amendment["snapshot"]["path"])
            expected_snapshot_path = (
                root / "task_contract_snapshots" / "sha256"
                / f"{amendment['pre_task_sha256']}.json"
            ).resolve()
            if snapshot_path != expected_snapshot_path:
                link_errors.append("snapshot path không phải content-addressed path chuẩn")
            if not snapshot_path.is_file():
                link_errors.append("thiếu immutable pre-task snapshot")
            elif _sha256(snapshot_path) != amendment["pre_task_sha256"]:
                link_errors.append("snapshot bytes không khớp pre_task_sha256")
            elif amendment["snapshot"]["sha256"] != amendment["pre_task_sha256"]:
                link_errors.append("snapshot.sha256 không khớp pre_task_sha256")
            else:
                snapshot_value = _load_json(snapshot_path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            link_errors.append(f"snapshot không hợp lệ: {exc}")
        if snapshot_value is not None:
            if snapshot_value.get("task_id") != amendment["task_id"]:
                link_errors.append("snapshot thuộc task khác")
            reconstructed = dict(snapshot_value)
            for change in amendment["changes"]:
                field = change["field"]
                if field not in snapshot_value:
                    link_errors.append(f"snapshot thiếu field {field}")
                    continue
                if snapshot_value[field] != change["before"]:
                    link_errors.append(f"before không khớp snapshot tại {field}")
                if change["before"] == change["after"]:
                    link_errors.append(f"change {field} không thay đổi giá trị")
                reconstructed[field] = change["after"]
            post_sha = hashlib.sha256(_json_file_bytes(reconstructed)).hexdigest()
            if post_sha != amendment["post_task_sha256"]:
                link_errors.append("post_task_sha256 không khớp exact patch")
            if snapshot_value.get("status") != amendment["previous_status"]:
                link_errors.append("previous_status không khớp snapshot")
            if reconstructed.get("status") != amendment["next_status"]:
                link_errors.append("next_status không khớp patched task")
            allowed_next = TASK_AMENDMENT_TRANSITIONS.get(amendment["previous_status"], set())
            if amendment["next_status"] not in allowed_next:
                link_errors.append("status transition không được phép")
            schema_errors = list(task_validator.iter_errors(reconstructed))
            if schema_errors:
                link_errors.append(
                    "patched task không hợp lệ: "
                    + "; ".join(error.message for error in schema_errors)
                )
            reconstructed_by_hash[observed_amendment_sha] = reconstructed
        try:
            memberships = _task_runs(root, amendment["task_id"])
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            memberships = []
            link_errors.append(f"không đọc được run membership: {exc}")
        if len(memberships) > 1:
            link_errors.append("task thuộc nhiều run; audit event không đơn trị")
        elif memberships:
            run_path, run = memberships[0]
            if amendment.get("run_id") != run["run_id"]:
                link_errors.append("run_id không khớp run chứa task")
            event_matches = [
                event for event in run["events"]
                if event.get("kind") == "TASK_CONTRACT_AMENDED"
                and event.get("task_id") == amendment["task_id"]
                and amendment_id in event.get("message", "")
                and amendment["amendment_sha256"] in event.get("message", "")
            ]
            if len(event_matches) != 1:
                link_errors.append(
                    f"{run_path.parent.name}: thiếu hoặc trùng TASK_CONTRACT_AMENDED event"
                )
            brief_path = root / "intake" / f"{run['brief_id']}.json"
            if not brief_path.is_file():
                link_errors.append("run thiếu research brief để xác minh authorized_by")
            else:
                try:
                    brief = _load_json(brief_path)
                    if amendment["authorized_by"] != brief.get("requested_by"):
                        link_errors.append("authorized_by không phải brief requester")
                except (OSError, json.JSONDecodeError) as exc:
                    link_errors.append(f"research brief không hợp lệ: {exc}")
        elif amendment.get("run_id"):
            link_errors.append("run_id được khai báo nhưng task không thuộc run")
        for message in link_errors:
            errors.append(f"{path.name}: {message}")
        amendment_link_valid[observed_amendment_sha] = not link_errors
        amendments_by_task.setdefault(amendment["task_id"], []).append((path, amendment))

    for task_id, records in amendments_by_task.items():
        if task_id not in tasks:
            # The record-level check above already reports the dangling task.
            # Continue collecting validator errors instead of raising here.
            continue
        record_hashes = {record["amendment_sha256"] for _, record in records}
        referenced: set[str] = set()
        roots = []
        children: dict[str, list[str]] = {digest: [] for digest in record_hashes}
        for path, amendment in records:
            previous = amendment.get("previous_amendment_sha256")
            if previous is None:
                roots.append(amendment["amendment_sha256"])
                continue
            referenced.add(previous)
            parent_entry = amendments_by_hash.get(previous)
            if not parent_entry or parent_entry[1]["task_id"] != task_id:
                errors.append(f"{path.name}: previous amendment không tồn tại/cùng task")
                continue
            if parent_entry[1]["post_task_sha256"] != amendment["pre_task_sha256"]:
                errors.append(f"{path.name}: amendment chain gãy tại pre-task hash")
            children.setdefault(previous, []).append(amendment["amendment_sha256"])
        heads = sorted(record_hashes - referenced)
        if len(roots) != 1 or len(heads) != 1:
            errors.append(f"{task_id}: amendment chain phải có đúng một root và một head")
            continue
        seen: set[str] = set()
        cursor = roots[0]
        while cursor not in seen:
            seen.add(cursor)
            next_items = children.get(cursor, [])
            if len(next_items) > 1:
                errors.append(f"{task_id}: amendment chain bị fork")
                break
            if not next_items:
                break
            cursor = next_items[0]
        if seen != record_hashes or cursor != heads[0]:
            errors.append(f"{task_id}: amendment chain có cycle hoặc record rời")
            continue
        head_hash = heads[0]
        head = amendments_by_hash[head_hash][1]
        current_path = _task_path(root, task_id)
        current_sha = _sha256(current_path)
        current_task = tasks[task_id]
        if current_sha != head["post_task_sha256"]:
            expected = reconstructed_by_hash.get(head_hash)
            if expected is None or _task_contract(current_task) != _task_contract(expected):
                errors.append(
                    f"{task_id}: current task contract không khớp amendment head "
                    f"{head['amendment_id']}"
                )
            if (
                current_task.get("status") in TASK_AMENDABLE_STATES
                and current_task.get("owner") is None
                and current_task.get("reviewer") is None
            ):
                errors.append(
                    f"{task_id}: unclaimed task hash không khớp amendment head; "
                    "có silent edit hoặc transaction dang dở"
                )

    _, valid_incidents = _record_collection(
        root, "incidents", "provenance_incident.schema.json", "incident_id", errors)
    _, valid_corrections = _record_collection(
        root, "corrections", "provenance_correction.schema.json", "correction_id", errors)
    _, valid_correction_reviews = _record_collection(
        root, "correction_reviews", "provenance_correction_review.schema.json",
        "review_id", errors)

    for incident_id, (path, incident) in valid_incidents.items():
        if path.name != f"{incident_id}.json":
            errors.append(f"{path.name}: filename không khớp incident_id")
        if incident["task_id"] not in tasks:
            errors.append(f"{path.name}: task_id không tồn tại")

    correction_by_sha = {
        _sha256(path): (path, correction)
        for path, correction in valid_corrections.values()
    }
    # Phán quyết của từng correction, tiền tính TRƯỚC vòng lặp dưới. Vòng kiểm
    # review chạy sau vòng kiểm correction, nên không được tra ngược
    # ``approved_corrections`` ở đây — sẽ phụ thuộc thứ tự lặp.
    #
    # FAIL-CLOSED với review trùng: ``review_provenance_correction`` không cho
    # ghi review thứ hai, nhưng một file chép tay thì có thể. Nếu một correction
    # có nhiều phán quyết KHÁC nhau thì không được lấy cái ghi sau cùng — đó là
    # đường để đầu độc bảng này. Xung đột ⇒ coi như KHÔNG có phán quyết hợp lệ,
    # và báo lỗi để người ta nhìn thấy.
    _decisions_by_correction: dict[str, set[str]] = {}
    for _path, _review in valid_correction_reviews.values():
        _decisions_by_correction.setdefault(
            _review["correction_sha256"], set()).add(_review["decision"])
    correction_decision: dict[str, str] = {}
    for _sha, _decisions in _decisions_by_correction.items():
        if len(_decisions) == 1:
            correction_decision[_sha] = next(iter(_decisions))
        else:
            errors.append(
                f"correction {_sha[:12]}: có {len(_decisions)} phán quyết xung đột "
                f"({sorted(_decisions)}); review của correction là bất biến nên đây là "
                "dấu hiệu bản ghi bị sửa tay — coi như chưa có phán quyết"
            )

    correction_link_valid: dict[str, bool] = {}
    for correction_id, (path, correction) in valid_corrections.items():
        link_errors: list[str] = []
        if path.name != f"{correction_id}.json":
            link_errors.append("filename không khớp correction_id")
        if correction["task_id"] not in tasks:
            link_errors.append("task_id không tồn tại")
        incident_entry = valid_incidents.get(correction["incident_id"])
        if not incident_entry:
            link_errors.append("incident_id không trỏ tới incident hợp lệ")
        else:
            _, incident = incident_entry
            linked_fields = (
                ("task_id", correction["task_id"]),
                ("original_handoff_path", correction["original_handoff_path"]),
                ("original_handoff_sha256", correction["original_handoff_sha256"]),
                ("artifact_path", correction["corrected_artifact"]["path"]),
                ("recorded_sha256", correction["corrected_artifact"]["previous_sha256"]),
            )
            for field, expected in linked_fields:
                if incident[field] != expected:
                    link_errors.append(f"incident linkage lệch {field}")
        try:
            original_handoff = _lab_link_path(root, correction["original_handoff_path"])
            handoff_root = (root / "handoffs").resolve()
            if original_handoff.parent != handoff_root:
                link_errors.append("original_handoff_path không nằm trong handoffs canonical")
            elif not original_handoff.is_file():
                link_errors.append("thiếu original handoff")
            elif _sha256(original_handoff) != correction["original_handoff_sha256"]:
                link_errors.append("original handoff hash không khớp")
            else:
                original_value = _load_json(original_handoff)
                if original_value.get("task_id") != correction["task_id"]:
                    link_errors.append("original handoff thuộc task khác")
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            link_errors.append(f"original handoff không hợp lệ: {exc}")
        try:
            snapshot = _lab_link_path(root, correction["snapshot"]["path"])
            expected_snapshot = correction["snapshot"]["sha256"]
            expected_previous = correction["corrected_artifact"]["previous_sha256"]
            if not snapshot.is_file():
                link_errors.append("thiếu immutable snapshot")
            elif _sha256(snapshot) != expected_snapshot:
                link_errors.append("snapshot bytes không khớp snapshot hash")
            if expected_snapshot != expected_previous:
                link_errors.append("snapshot hash không khớp recorded artifact hash")
        except (OSError, ValueError) as exc:
            link_errors.append(f"snapshot không hợp lệ: {exc}")
        supersedes = correction.get("supersedes_correction_sha256")
        if supersedes:
            previous = correction_by_sha.get(supersedes)
            if not previous or previous[1].get("task_id") != correction["task_id"]:
                link_errors.append("supersedes không trỏ tới correction cùng task")
            else:
                previous_correction = previous[1]
                previous_artifact = previous_correction["corrected_artifact"]
                current_artifact = correction["corrected_artifact"]
                if (
                    previous_correction["original_handoff_path"]
                    != correction["original_handoff_path"]
                    or previous_correction["original_handoff_sha256"]
                    != correction["original_handoff_sha256"]
                    or previous_artifact["path"] != current_artifact["path"]
                ):
                    link_errors.append("supersedes correction khác lineage/artifact")
                # Cùng MỘT quy tắc với correction_chain_is_approved: mắt xích
                # trước được APPROVE thì bước này nối vào kết quả của nó; mắt
                # xích trước bị REVISE/REJECT là VÔ HIỆU nên bước này phải xuất
                # phát lại từ đúng mốc mà nó xuất phát.
                if correction_decision.get(supersedes) == "APPROVE":
                    expected_link = previous_artifact["current_sha256"]
                else:
                    expected_link = previous_artifact["previous_sha256"]
                if expected_link != current_artifact["previous_sha256"]:
                    link_errors.append("correction chain bị đứt old/new hash")
        for message in link_errors:
            errors.append(f"{path.name}: {message}")
        correction_link_valid[_sha256(path)] = not link_errors

    approved_corrections: set[str] = set()
    for review_id, (path, review) in valid_correction_reviews.items():
        link_errors: list[str] = []
        if path.name != f"{review_id}.json":
            link_errors.append("filename không khớp review_id")
        correction_entry = correction_by_sha.get(review["correction_sha256"])
        if not correction_entry:
            link_errors.append("correction_sha256 không trỏ tới correction handoff")
        else:
            _, correction = correction_entry
            if review["task_id"] != correction["task_id"]:
                link_errors.append("review task_id lệch correction")
            if review["incident_id"] != correction["incident_id"]:
                link_errors.append("review incident_id lệch correction")
            if review["reviewer_id"] == correction["agent_id"]:
                link_errors.append("correction agent không được tự review")
            try:
                original = _load_json(_lab_link_path(
                    root, correction["original_handoff_path"]
                ))
                if review["reviewer_id"] == original.get("agent_id"):
                    link_errors.append("original handoff agent không được review correction")
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                link_errors.append(f"không đọc được original handoff agent: {exc}")
        for message in link_errors:
            errors.append(f"{path.name}: {message}")
        if (
            not link_errors
            and review["decision"] == "APPROVE"
            and correction_link_valid.get(review["correction_sha256"], False)
            # Xung đột phán quyết ⇒ không có phán quyết. Nếu thiếu điều kiện này
            # thì chỉ cần chép thêm một file review APPROVE bên cạnh một REVISE
            # là hợp thức hoá được drift.
            and correction_decision.get(review["correction_sha256"]) == "APPROVE"
        ):
            approved_corrections.add(review["correction_sha256"])

    def correction_chain_is_approved(
        correction_sha256: str, original_artifact_sha256: str
    ) -> bool:
        """Require an unbroken, independently approved chain back to handoff bytes."""
        visited: set[str] = set()
        current_sha256 = correction_sha256
        is_head = True
        while current_sha256:
            if current_sha256 in visited:
                return False
            visited.add(current_sha256)
            entry = correction_by_sha.get(current_sha256)
            if not entry or not correction_link_valid.get(current_sha256, False):
                return False
            # Mắt xích ĐANG XÉT phải được review độc lập APPROVE. Mắt xích cũ hơn
            # có thể là bản VÔ HIỆU (bị REVISE/REJECT) đã bị thay thế — đi xuyên
            # qua nó KHÔNG nới lỏng gì, vì bản thay thế vẫn phải được duyệt và
            # snapshot của nó vẫn phải khớp đúng mốc mà bản vô hiệu xuất phát.
            if is_head and current_sha256 not in approved_corrections:
                return False
            correction = entry[1]
            supersedes = correction.get("supersedes_correction_sha256")
            if not supersedes:
                return (
                    correction["corrected_artifact"]["previous_sha256"]
                    == original_artifact_sha256
                )
            previous_entry = correction_by_sha.get(supersedes)
            if not previous_entry or not correction_link_valid.get(supersedes, False):
                return False
            previous_correction = previous_entry[1]
            if supersedes in approved_corrections:
                # Bản trước ĐÃ được chấp nhận: bước này phải nối vào kết quả của nó.
                expected = previous_correction["corrected_artifact"]["current_sha256"]
            else:
                # Bản trước VÔ HIỆU: bước này phải xuất phát từ đúng mốc của nó.
                expected = previous_correction["corrected_artifact"]["previous_sha256"]
            if correction["corrected_artifact"]["previous_sha256"] != expected:
                return False
            is_head = False
            current_sha256 = supersedes
        return False

    def drift_has_approved_correction(
        handoff_path: Path, handoff: dict, artifact: dict, observed_sha256: str
    ) -> bool:
        original_relative = _lab_relative(root, handoff_path)
        original_sha256 = _sha256(handoff_path)
        for correction_sha256, (_, correction) in correction_by_sha.items():
            corrected = correction["corrected_artifact"]
            incident_entry = valid_incidents.get(correction["incident_id"])
            if not incident_entry:
                continue
            _, incident = incident_entry
            if not (
                correction_link_valid.get(correction_sha256, False)
                and correction_chain_is_approved(correction_sha256, artifact["sha256"])
                and correction["task_id"] == handoff.get("task_id")
                and correction["original_handoff_path"] == original_relative
                and correction["original_handoff_sha256"] == original_sha256
                and corrected["path"] == artifact["path"]
                and corrected["current_sha256"] == observed_sha256
                and incident["observed_sha256"] == observed_sha256
            ):
                continue
            return True
        return False

    # A REVISE review makes that exact handoff historical.  Only its latest
    # review decision matters; an APPROVE must never be bypassed by an older
    # REVISE record.  Snapshot existence alone grants no exception.
    latest_review_by_handoff: dict[str, dict] = {}

    def review_revision(path: Path) -> int:
        match = re.search(r"\.r([0-9]+)\.json$", path.name)
        return int(match.group(1)) if match else -1

    for review_path in sorted(
        (root / "reviews").glob("*.json"), key=review_revision
    ):
        try:
            review_value = _load_json(review_path)
        except (OSError, json.JSONDecodeError):
            continue
        if list(review_validator.iter_errors(review_value)):
            continue
        latest_review_by_handoff[review_value["handoff_sha256"]] = review_value

    def revised_handoff_has_exact_snapshot(
        handoff_path: Path, handoff: dict, artifact: dict
    ) -> bool:
        review = latest_review_by_handoff.get(_sha256(handoff_path))
        if not review or not (
            review["task_id"] == handoff.get("task_id")
            and review["decision"] == "REVISE"
        ):
            return False
        snapshot = _snapshot_path(root, artifact["sha256"])
        return snapshot.is_file() and _sha256(snapshot) == artifact["sha256"]

    for path in sorted((root / "handoffs").glob("*.json")):
        try:
            handoff = _load_json(path)
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"{path.name}: {exc}")
            continue
        for error in handoff_validator.iter_errors(handoff):
            errors.append(f"{path.name}: {error.json_path}: {error.message}")
        task = tasks.get(handoff.get("task_id"))
        if handoff.get("task_id") and not path.name.startswith(handoff["task_id"] + "."):
            errors.append(f"{path.name}: filename không khớp task_id")
        if task and task.get("owner") != handoff.get("agent_id"):
            errors.append(f"{path.name}: handoff agent không phải task owner")
        if task and CLAIM_ORDER.get(handoff.get("claim_level"), 99) > CLAIM_ORDER[task["claim_ceiling"]]:
            errors.append(f"{path.name}: claim vượt trần của task")
        exemptions = set(lab_config.get("legacy_ceiling_exemptions", [])) | LEGACY_CEILING_EXEMPTIONS
        if path.name not in exemptions and CLAIM_ORDER.get(handoff.get("claim_level"), 99) > CLAIM_ORDER[project_claim_ceiling]:
            errors.append(f"{path.name}: claim {handoff.get('claim_level')} vượt trần cấp dự án ({project_claim_ceiling})")
        for artifact in handoff.get("artifacts", []):
            artifact_path = _project_path(artifact["path"])
            if not artifact_path.is_file():
                errors.append(f"{path.name}: thiếu artifact {artifact['path']}")
            else:
                observed_sha256 = _sha256(artifact_path)
                if (
                    observed_sha256 != artifact["sha256"]
                    and not drift_has_approved_correction(
                        path, handoff, artifact, observed_sha256)
                    and not revised_handoff_has_exact_snapshot(path, handoff, artifact)
                ):
                    errors.append(
                        f"{path.name}: hash đã thay đổi {artifact['path']} và chưa có "
                        "snapshot/incident/correction review hợp lệ"
                    )

    for path in sorted((root / "reviews").glob("*.json")):
        try:
            review = _load_json(path)
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"{path.name}: {exc}")
            continue
        for error in review_validator.iter_errors(review):
            errors.append(f"{path.name}: {error.json_path}: {error.message}")
        task = tasks.get(review.get("task_id"))
        if review.get("task_id") and not path.name.startswith(review["task_id"] + "."):
            errors.append(f"{path.name}: filename không khớp task_id")
        if task and task.get("owner") == review.get("reviewer_id"):
            errors.append(f"{path.name}: người thực hiện không được tự review")
        matching_handoffs = [
            candidate for candidate in (root / "handoffs").glob(
                f"{review.get('task_id', '')}.*.r*.json"
            ) if _sha256(candidate) == review.get("handoff_sha256")
        ]
        if review.get("task_id") and not matching_handoffs:
            errors.append(f"{path.name}: handoff_sha256 không trỏ tới handoff cùng task")

    for task_id, task in tasks.items():
        if task.get("status") == "ACCEPTED":
            if not list((root / "handoffs").glob(f"{task_id}.*.r*.json")):
                errors.append(f"{task_id}: ACCEPTED nhưng thiếu handoff")
            if not list((root / "reviews").glob(f"{task_id}.*.r*.json")):
                errors.append(f"{task_id}: ACCEPTED nhưng thiếu independent review")

    return {"valid": not errors, "errors": errors, "task_count": len(tasks)}


def lab_status(lab_dir: str | Path | None = None) -> dict:
    root = _lab_dir(lab_dir)
    validation = validate_lab(root)
    tasks = _all_tasks(root) if validation["task_count"] else {}
    by_status: dict[str, int] = {}
    for task in tasks.values():
        by_status[task["status"]] = by_status.get(task["status"], 0) + 1
    from .providers import discover_provider
    tools = {name: bool(discover_provider(name)) for name in ("codex", "claude", "opencode", "antigravity")}
    lab_config = _load_json(root / "lab.json") if (root / "lab.json").is_file() else {}
    project_claim_ceiling = lab_config.get("current_project_claim_ceiling", "SCREENED")
    return {
        "lab_dir": str(root),
        "valid": validation["valid"],
        "errors": validation["errors"],
        "tasks": by_status,
        "cli_available": tools,
        "git_initialized": (REPO_ROOT / ".git").is_dir(),
        "current_project_claim_ceiling": project_claim_ceiling,
        "warning": "L2/L3 và thử nghiệm vật lý chưa được triển khai; output runtime hiện tại chỉ là SCREENED.",
    }


def build_agent_brief(agent_id: str, lab_dir: str | Path | None = None) -> str:
    root = _lab_dir(lab_dir)
    lab = _load_json(root / "lab.json")
    tasks = _all_tasks(root)
    ready = []
    for task in tasks.values():
        if task["status"] != "READY":
            continue
        if all(tasks.get(dep, {}).get("status") == "ACCEPTED" for dep in task["dependencies"]):
            ready.append(task)
    lines = [
        f"# Brief cho agent `{agent_id}` — {lab['name']}",
        "",
        "Đọc theo thứ tự: `AGENTS.md` → `multiagent/PROTOCOL.md` → `multiagent/PHYSICS_GATES.md`.",
        "Không bắt đầu sửa trước khi claim task. Không dùng LLM/surrogate làm solver hoặc verifier.",
        "Claim ceiling hiện tại của runtime: SCREENED.",
        "",
        "## Task có thể claim",
    ]
    if not ready:
        lines.append("- Không có task READY đã thỏa dependencies.")
    for task in sorted(ready, key=lambda item: (item["priority"], item["task_id"])):
        lines.append(
            f"- {task['task_id']} [{task['priority']}] {task['title']} — "
            f"gates {','.join(task['required_gates'])}; scope {', '.join(task['write_scope'])}"
        )
    lines.extend(["", f"Claim: `python -m bridge_evolution.cli lab claim <TASK> --agent {agent_id}`"])
    return "\n".join(lines) + "\n"


def amend_task_contract(
    task_id: str,
    changes: dict,
    *,
    reason: str,
    authorized_by: str,
    expected_pre_task_sha256: str,
    lab_dir: str | Path | None = None,
) -> dict:
    """Apply a pre-claim task re-scope with an immutable, hash-linked audit trail.

    ``changes`` is a field-to-new-value mapping, not a merge patch. The record
    captures both old and new values, and a stale caller cannot apply after the
    task bytes have changed. No active/reviewed/accepted work can be rewritten.
    """
    root = _lab_dir(lab_dir)
    if not isinstance(changes, dict) or not changes:
        raise ValueError("changes phải là một JSON object không rỗng")
    if not isinstance(reason, str) or len(reason.strip()) < 5:
        raise ValueError("Lý do amendment phải có ít nhất 5 ký tự")
    if not isinstance(authorized_by, str) or not (2 <= len(authorized_by) <= 64):
        raise ValueError("authorized_by phải có 2-64 ký tự")
    if not re.fullmatch(r"[a-f0-9]{64}", expected_pre_task_sha256 or ""):
        raise ValueError("expected pre-task SHA-256 không hợp lệ")
    unsupported = sorted(set(changes) - TASK_AMENDABLE_FIELDS)
    if unsupported:
        raise ValueError(f"Field không được amendment: {unsupported}")

    with _task_lock(root, task_id, authorized_by):
        task_path = _task_path(root, task_id)
        pre_task_bytes = task_path.read_bytes()
        pre_task_sha256 = hashlib.sha256(pre_task_bytes).hexdigest()
        if pre_task_sha256 != expected_pre_task_sha256:
            raise ValueError(
                f"Stale pre-task hash cho {task_id}: expected "
                f"{expected_pre_task_sha256}, current {pre_task_sha256}"
            )
        task = json.loads(pre_task_bytes.decode("utf-8"))
        schema_errors = list(Draft202012Validator(
            _schema("research_task.schema.json")
        ).iter_errors(task))
        if schema_errors:
            raise ValueError(
                "Task hiện tại không hợp lệ: "
                + "; ".join(error.message for error in schema_errors)
            )
        if task["status"] not in TASK_AMENDABLE_STATES:
            raise ValueError(
                f"Không được amendment task {task['status']}; chỉ BACKLOG/READY/"
                "BLOCKED chưa claim"
            )
        if task.get("owner") is not None or task.get("reviewer") is not None:
            raise ValueError("Task đã từng/đang được claim; không được amendment contract")
        if (
            list((root / "handoffs").glob(f"{task_id}.*.r*.json"))
            or list((root / "reviews").glob(f"{task_id}.*.r*.json"))
        ):
            raise ValueError("Task đã có handoff/review; phải tạo task/lineage mới")
        for field in changes:
            if field not in task:
                raise ValueError(f"Task hiện tại thiếu field amendment {field}")

        previous_amendment_sha256, _ = _amendment_head(
            root, task_id, pre_task_sha256
        )
        patched = dict(task)
        exact_changes = []
        for field in sorted(changes):
            before = task[field]
            after = changes[field]
            if before == after:
                raise ValueError(f"Amendment field {field} không thay đổi giá trị")
            exact_changes.append({"field": field, "before": before, "after": after})
            patched[field] = after
        next_status = patched["status"]
        allowed_next = TASK_AMENDMENT_TRANSITIONS[task["status"]]
        if next_status not in allowed_next:
            raise ValueError(
                f"Status transition amendment không hợp lệ: "
                f"{task['status']} -> {next_status}"
            )
        schema_errors = list(Draft202012Validator(
            _schema("research_task.schema.json")
        ).iter_errors(patched))
        if schema_errors:
            raise ValueError(
                "Patched task không hợp lệ: "
                + "; ".join(error.message for error in schema_errors)
            )

        memberships = _task_runs(root, task_id)
        if len(memberships) > 1:
            raise ValueError(f"Task {task_id} thuộc nhiều run; từ chối amendment mơ hồ")
        run_path = None
        run_before_bytes = None
        run_after = None
        if memberships:
            run_path, run = memberships[0]
            brief_path = root / "intake" / f"{run['brief_id']}.json"
            if not brief_path.is_file():
                raise ValueError("Run thiếu research brief canonical")
            brief = _load_json(brief_path)
            if authorized_by != brief.get("requested_by"):
                raise PermissionError(
                    f"Chỉ brief requester {brief.get('requested_by')} được authorize amendment"
                )
            run_before_bytes = run_path.read_bytes()

        created_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        amendment_id = f"AMD-{uuid.uuid4().hex[:16]}"
        post_task_bytes = _json_file_bytes(patched)
        post_task_sha256 = hashlib.sha256(post_task_bytes).hexdigest()
        snapshot_relative = (
            Path("multiagent") / "task_contract_snapshots" / "sha256"
            / f"{pre_task_sha256}.json"
        ).as_posix()
        amendment = {
            "schema_version": "1.0",
            "amendment_id": amendment_id,
            "amendment_sha256": "",
            "created_at": created_at,
            "task_id": task_id,
            "authorized_by": authorized_by,
            "reason": reason.strip(),
            "pre_task_sha256": pre_task_sha256,
            "post_task_sha256": post_task_sha256,
            "previous_amendment_sha256": previous_amendment_sha256,
            "snapshot": {
                "path": snapshot_relative,
                "sha256": pre_task_sha256,
            },
            "changes": exact_changes,
            "previous_status": task["status"],
            "next_status": next_status,
        }
        if memberships:
            amendment["run_id"] = memberships[0][1]["run_id"]
        amendment["amendment_sha256"] = _amendment_sha256(amendment)
        amendment_errors = list(Draft202012Validator(
            _schema("task_contract_amendment.schema.json")
        ).iter_errors(amendment))
        if amendment_errors:
            raise ValueError(
                "Amendment record không hợp lệ: "
                + "; ".join(error.message for error in amendment_errors)
            )

        if memberships:
            run_after = json.loads(run_before_bytes.decode("utf-8"))
            event = {
                "at": created_at,
                "kind": "TASK_CONTRACT_AMENDED",
                "message": (
                    f"{amendment_id} {amendment['amendment_sha256']}: "
                    f"{', '.join(item['field'] for item in exact_changes)}"
                ),
                "task_id": task_id,
            }
            run_after["events"].append(event)
            run_after["updated_at"] = created_at
            run_after["knowledge_sync"] = "PENDING"
            run_errors = list(Draft202012Validator(
                _schema("orchestration_run.schema.json")
            ).iter_errors(run_after))
            if run_errors:
                raise ValueError(
                    "Run sau amendment không hợp lệ: "
                    + "; ".join(error.message for error in run_errors)
                )

        snapshot_path = _lab_link_path(root, snapshot_relative)
        amendments_root = root / "amendments"
        revision = len(list(amendments_root.glob(f"{task_id}.amendment.r*.json"))) + 1
        amendment_path = amendments_root / f"{task_id}.amendment.r{revision:03d}.json"
        snapshot_existed = snapshot_path.exists()
        amendment_created = False
        run_written = False
        try:
            _ensure_exact_snapshot(snapshot_path, pre_task_bytes, pre_task_sha256)
            _exclusive_json(amendment_path, amendment)
            amendment_created = True
            if run_path is not None and run_after is not None:
                _atomic_json(run_path, run_after)
                run_written = True
            # Task is the commit point: audit record and run event already exist.
            _atomic_bytes(task_path, post_task_bytes)
        except BaseException:
            if run_written and run_path is not None and run_before_bytes is not None:
                _atomic_bytes(run_path, run_before_bytes)
            if task_path.read_bytes() != pre_task_bytes:
                _atomic_bytes(task_path, pre_task_bytes)
            if amendment_created:
                amendment_path.unlink(missing_ok=True)
            if not snapshot_existed:
                snapshot_path.unlink(missing_ok=True)
            raise

    return {
        "amendment": amendment,
        "amendment_path": _lab_relative(root, amendment_path),
        "amendment_sha256": amendment["amendment_sha256"],
        "snapshot_path": snapshot_relative,
        "task": patched,
        "run": run_after,
    }


def claim_task(task_id: str, agent_id: str, lab_dir: str | Path | None = None) -> dict:
    root = _lab_dir(lab_dir)
    with _task_lock(root, task_id, agent_id):
        tasks = _all_tasks(root)
        task = _load_json(_task_path(root, task_id))
        if task["status"] != "READY" or task.get("owner") is not None:
            raise ValueError(f"{task_id} không ở trạng thái READY chưa có owner")
        blocked = [dep for dep in task["dependencies"] if tasks[dep]["status"] != "ACCEPTED"]
        if blocked:
            raise ValueError(f"{task_id} còn dependency chưa ACCEPTED: {blocked}")
        task["owner"] = agent_id
        task["status"] = "ACTIVE"
        _atomic_json(_task_path(root, task_id), task)
    return task


def _artifact_records(paths: Iterable[str], kind: str) -> list[dict]:
    records = []
    for supplied in paths:
        path = (REPO_ROOT / supplied).resolve()
        try:
            relative = path.relative_to(REPO_ROOT.resolve())
        except ValueError as exc:
            raise ValueError(f"Artifact phải nằm trong project: {supplied}") from exc
        if not path.is_file():
            raise FileNotFoundError(path)
        records.append({"path": relative.as_posix(), "sha256": _sha256(path), "kind": kind})
    return records


def submit_handoff(
    task_id: str,
    agent_id: str,
    role: str,
    summary: str,
    claim_level: str,
    gates_completed: Iterable[str],
    artifact_paths: Iterable[str],
    *,
    artifact_kind: str = "report",
    assumptions: Iterable[str] = (),
    unresolved_risks: Iterable[str] = (),
    next_action: str = "Independent review",
    lab_dir: str | Path | None = None,
) -> dict:
    root = _lab_dir(lab_dir)
    with _task_lock(root, task_id, agent_id):
        task_path = _task_path(root, task_id)
        task = _load_json(task_path)
        if task["status"] != "ACTIVE" or task.get("owner") != agent_id:
            raise ValueError(f"{agent_id} không sở hữu task ACTIVE {task_id}")
        lab_config = _load_json(root / "lab.json") if (root / "lab.json").is_file() else {}
        project_claim_ceiling = lab_config.get("current_project_claim_ceiling", "SCREENED")
        if CLAIM_ORDER[claim_level] > CLAIM_ORDER[task["claim_ceiling"]]:
            raise ValueError(f"Claim {claim_level} vượt trần {task['claim_ceiling']}")
        if CLAIM_ORDER[claim_level] > CLAIM_ORDER[project_claim_ceiling]:
            raise ValueError(f"Claim {claim_level} vượt trần cấp dự án ({project_claim_ceiling})")
        completed = set(gates_completed)
        missing = CLAIM_GATES[claim_level] - completed
        if missing:
            raise ValueError(f"Claim {claim_level} thiếu gate: {sorted(missing)}")
        handoff = {
            "schema_version": "1.0",
            "task_id": task_id,
            "agent_id": agent_id,
            "role": role,
            "summary": summary,
            "claim_level": claim_level,
            "gates_completed": sorted(completed),
            "artifacts": _artifact_records(artifact_paths, artifact_kind),
            "assumptions": list(assumptions),
            "unresolved_risks": list(unresolved_risks),
            "next_action": next_action,
        }
        errors = list(Draft202012Validator(_schema("research_handoff.schema.json")).iter_errors(handoff))
        if errors:
            raise ValueError("Handoff invalid: " + "; ".join(error.message for error in errors))
        previous = sorted((root / "handoffs").glob(f"{task_id}.{agent_id}.r*.json"))
        revision = len(previous) + 1
        handoff_path = root / "handoffs" / f"{task_id}.{agent_id}.r{revision:03d}.json"
        _atomic_json(handoff_path, handoff)
        task["status"] = "REVIEW"
        task["reviewer"] = None
        _atomic_json(task_path, task)
    return handoff


def review_handoff(
    task_id: str,
    reviewer_id: str,
    decision: str,
    gate_findings: list[dict],
    notes: str,
    lab_dir: str | Path | None = None,
) -> dict:
    root = _lab_dir(lab_dir)
    with _task_lock(root, task_id, reviewer_id):
        task_path = _task_path(root, task_id)
        task = _load_json(task_path)
        if task["status"] != "REVIEW":
            raise ValueError(f"{task_id} không ở trạng thái REVIEW")
        if task.get("owner") == reviewer_id:
            raise ValueError("Người thực hiện không được tự review")
        handoff_paths = sorted((root / "handoffs").glob(f"{task_id}.*.r*.json"))
        if not handoff_paths:
            raise ValueError(f"Không tìm thấy handoff cho {task_id}")
        handoff_path = handoff_paths[-1]
        handoff = _load_json(handoff_path)
        for artifact in handoff.get("artifacts", []):
            source = _project_path(artifact["path"])
            if not source.is_file():
                raise FileNotFoundError(source)
            if _sha256(source) != artifact["sha256"]:
                raise ValueError(
                    f"Không thể review handoff đã drift: {artifact['path']}"
                )
        review = {
            "schema_version": "1.0",
            "task_id": task_id,
            "handoff_sha256": _sha256(handoff_path),
            "reviewer_id": reviewer_id,
            "decision": decision,
            "independence_confirmed": True,
            "gate_findings": gate_findings,
            "notes": notes,
        }
        errors = list(Draft202012Validator(_schema("research_review.schema.json")).iter_errors(review))
        if errors:
            raise ValueError("Review invalid: " + "; ".join(error.message for error in errors))
        required = set(task["required_gates"])
        passed = {item["gate"] for item in gate_findings if item["status"] in {"PASS", "NOT_APPLICABLE"}}
        if decision == "APPROVE" and not required.issubset(passed):
            raise ValueError(f"Không thể APPROVE; thiếu gate review: {sorted(required - passed)}")
        if decision == "REVISE":
            for artifact in handoff.get("artifacts", []):
                _ensure_artifact_snapshot(root, artifact)
        previous_reviews = sorted((root / "reviews").glob(f"{task_id}.*.r*.json"))
        revision = len(previous_reviews) + 1
        review_path = root / "reviews" / f"{task_id}.{reviewer_id}.r{revision:03d}.json"
        _atomic_json(review_path, review)
        task["reviewer"] = reviewer_id
        task["status"] = {"APPROVE": "ACCEPTED", "REVISE": "ACTIVE", "REJECT": "REJECTED"}[decision]
        task.setdefault("review_notes", []).append(notes)
        _atomic_json(task_path, task)
    return review


def record_provenance_correction(
    task_id: str,
    agent_id: str,
    original_handoff_path: str,
    artifact_path: str,
    snapshot_source: str | Path,
    reason: str,
    summary: str,
    verification_commands: Iterable[Iterable[str]],
    *,
    assumptions: Iterable[str] = (),
    unresolved_risks: Iterable[str] = (),
    lab_dir: str | Path | None = None,
) -> dict:
    """Record drift without mutating prior handoff/review records.

    The historical bytes are copied to a content-addressed immutable snapshot.
    A correction is deliberately insufficient by itself: ``validate_lab`` keeps
    rejecting the drift until another agent approves the correction handoff.
    """
    root = _lab_dir(lab_dir)
    with _task_lock(root, task_id, agent_id):
        _task_path(root, task_id)
        if not re.fullmatch(r"[a-z][a-z0-9_-]{1,31}", agent_id):
            raise ValueError(f"agent_id không hợp lệ: {agent_id}")
        handoff_path = _lab_link_path(root, original_handoff_path)
        if handoff_path.parent != (root / "handoffs").resolve() or not handoff_path.is_file():
            raise ValueError("original_handoff_path phải trỏ tới handoff canonical")
        handoff = _load_json(handoff_path)
        if handoff.get("task_id") != task_id:
            raise ValueError("original handoff thuộc task khác")
        matching = [
            item for item in handoff.get("artifacts", [])
            if item.get("path") == artifact_path
        ]
        if len(matching) != 1:
            raise ValueError("artifact phải xuất hiện đúng một lần trong original handoff")
        normalized_handoff_path = _lab_relative(root, handoff_path)
        previous_entries: list[tuple[Path, dict]] = []
        for candidate in sorted((root / "corrections").glob(f"COR-{task_id}-*.json")):
            value = _load_json(candidate)
            if (
                value.get("original_handoff_path") == normalized_handoff_path
                and value.get("corrected_artifact", {}).get("path") == artifact_path
            ):
                previous_entries.append((candidate, value))
        supersedes = None
        if previous_entries:
            previous_path, previous_correction = previous_entries[-1]
            supersedes = _sha256(previous_path)
            decisions = [
                review.get("decision")
                for review in (
                    _load_json(path)
                    for path in (root / "correction_reviews").glob("*.json")
                )
                if review.get("correction_sha256") == supersedes
            ]
            if not decisions:
                raise ValueError(
                    "Previous correction chưa được independent review — không được "
                    "chồng correction mới lên một correction chưa ai xem"
                )
            if "APPROVE" in decisions:
                # Bản trước đã được chấp nhận: correction mới nối tiếp kết quả của nó.
                recorded_sha256 = previous_correction["corrected_artifact"]["current_sha256"]
            else:
                # Bản trước bị REVISE/REJECT nên VÔ HIỆU. Trước đây chỗ này chặn
                # cứng, khiến một correction bị REVISE khoá chết artifact: không sửa
                # tiếp được mà cũng không review lại được (review là bất biến). Bản
                # thay thế phải xuất phát lại từ đúng mốc cũ và vẫn phải được review
                # độc lập APPROVE thì drift mới được coi là đã xử lý.
                recorded_sha256 = previous_correction["corrected_artifact"]["previous_sha256"]
        else:
            recorded_sha256 = matching[0]["sha256"]
        source = Path(snapshot_source).resolve()
        if not source.is_file():
            raise FileNotFoundError(source)
        if _sha256(source) != recorded_sha256:
            raise ValueError("snapshot bytes không khớp recorded artifact hash")
        current = _project_path(artifact_path)
        if not current.is_file():
            raise FileNotFoundError(current)
        observed_sha256 = _sha256(current)
        if observed_sha256 == recorded_sha256:
            raise ValueError("Artifact không drift; không cần provenance correction")

        incident_revision = len(list((root / "incidents").glob(f"INC-{task_id}-*.json"))) + 1
        correction_revision = len(list((root / "corrections").glob(f"COR-{task_id}-*.json"))) + 1
        incident_id = f"INC-{task_id}-{incident_revision:03d}"
        correction_id = f"COR-{task_id}-{correction_revision:03d}"
        snapshot_relative = (
            Path("multiagent") / "snapshots" / "sha256" / f"{recorded_sha256}.blob"
        ).as_posix()
        snapshot_path = _lab_link_path(root, snapshot_relative)
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        if snapshot_path.exists():
            if not snapshot_path.is_file() or _sha256(snapshot_path) != recorded_sha256:
                raise ValueError("Content-addressed snapshot path đã tồn tại nhưng sai hash")
        else:
            try:
                with snapshot_path.open("xb") as stream:
                    stream.write(source.read_bytes())
                    stream.flush()
                    os.fsync(stream.fileno())
            except FileExistsError as exc:
                raise FileExistsError(f"Snapshot được tạo đồng thời: {snapshot_path}") from exc

        incident = {
            "schema_version": "1.0",
            "incident_id": incident_id,
            "task_id": task_id,
            "detected_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "detected_by": agent_id,
            "original_handoff_path": normalized_handoff_path,
            "original_handoff_sha256": _sha256(handoff_path),
            "artifact_path": artifact_path,
            "recorded_sha256": recorded_sha256,
            "observed_sha256": observed_sha256,
            "reason": reason,
            "disposition": "CONTROLLED_CORRECTION",
        }
        commands = [list(command) for command in verification_commands]
        correction = {
            "schema_version": "1.0",
            "correction_id": correction_id,
            "task_id": task_id,
            "incident_id": incident_id,
            "agent_id": agent_id,
            "role": "evidence_safety_auditor",
            "summary": summary,
            "original_handoff_path": normalized_handoff_path,
            "original_handoff_sha256": _sha256(handoff_path),
            "snapshot": {"path": snapshot_relative, "sha256": recorded_sha256},
            "corrected_artifact": {
                "path": artifact_path,
                "previous_sha256": recorded_sha256,
                "current_sha256": observed_sha256,
            },
            "verification_commands": commands,
            "assumptions": list(assumptions),
            "unresolved_risks": list(unresolved_risks),
            "supersedes_correction_sha256": supersedes,
        }
        for schema_name, value in (
            ("provenance_incident.schema.json", incident),
            ("provenance_correction.schema.json", correction),
        ):
            schema_errors = list(Draft202012Validator(_schema(schema_name)).iter_errors(value))
            if schema_errors:
                raise ValueError(
                    f"{schema_name} invalid: "
                    + "; ".join(error.message for error in schema_errors)
                )
        incident_path = root / "incidents" / f"{incident_id}.json"
        correction_path = root / "corrections" / f"{correction_id}.json"
        _exclusive_json(incident_path, incident)
        _exclusive_json(correction_path, correction)
    return {
        "incident": incident,
        "incident_path": _lab_relative(root, incident_path),
        "correction": correction,
        "correction_path": _lab_relative(root, correction_path),
        "correction_sha256": _sha256(correction_path),
        "review_required": True,
    }


def review_provenance_correction(
    correction_id: str,
    reviewer_id: str,
    decision: str,
    findings: Iterable[str],
    notes: str,
    lab_dir: str | Path | None = None,
) -> dict:
    """Independently review one immutable correction handoff."""
    root = _lab_dir(lab_dir)
    correction_path = root / "corrections" / f"{correction_id}.json"
    if not correction_path.is_file():
        raise FileNotFoundError(correction_path)
    correction = _load_json(correction_path)
    task_id = correction.get("task_id")
    if not TASK_ID_RE.fullmatch(task_id or ""):
        raise ValueError("Correction có task_id không hợp lệ")
    with _task_lock(root, task_id, reviewer_id):
        if reviewer_id == correction.get("agent_id"):
            raise ValueError("Correction agent không được tự review")
        original_handoff = _load_json(_lab_link_path(
            root, correction["original_handoff_path"]
        ))
        if reviewer_id == original_handoff.get("agent_id"):
            raise ValueError("Original handoff agent không được review correction")
        if decision not in {"APPROVE", "REVISE", "REJECT"}:
            raise ValueError(f"Decision không hợp lệ: {decision}")
        correction_sha256 = _sha256(correction_path)
        for prior in (root / "correction_reviews").glob("*.json"):
            if _load_json(prior).get("correction_sha256") == correction_sha256:
                raise ValueError("Correction handoff đã có review; không sửa/ghi đè review cũ")
        revision = len(list((root / "correction_reviews").glob(f"CRV-{task_id}-*.json"))) + 1
        review_id = f"CRV-{task_id}-{revision:03d}"
        review = {
            "schema_version": "1.0",
            "review_id": review_id,
            "task_id": task_id,
            "incident_id": correction["incident_id"],
            "correction_sha256": correction_sha256,
            "reviewer_id": reviewer_id,
            "decision": decision,
            "independence_confirmed": True,
            "findings": list(findings),
            "notes": notes,
        }
        schema_errors = list(Draft202012Validator(
            _schema("provenance_correction_review.schema.json")
        ).iter_errors(review))
        if schema_errors:
            raise ValueError(
                "Correction review invalid: "
                + "; ".join(error.message for error in schema_errors)
            )
        review_path = root / "correction_reviews" / f"{review_id}.json"
        _exclusive_json(review_path, review)
    return {
        "review": review,
        "review_path": _lab_relative(root, review_path),
        "drift_accepted": decision == "APPROVE",
    }
