"""Atomic file protocol shared by Codex, Claude, OpenCode and Antigravity.

The protocol deliberately coordinates artifacts, not model conversations.  Each
agent keeps its own credentials and transcript while task ownership, hashes and
independent review remain inspectable in the project workspace.
"""

from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
from typing import Iterable

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
TASK_ID_RE = re.compile(r"^(?:BRD-[0-9]{3}|RND-[a-f0-9]{8}-[0-9]{2})$")


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


def validate_lab(lab_dir: str | Path | None = None) -> dict:
    """Validate schemas, graph links, handoff hashes and review independence."""
    root = _lab_dir(lab_dir)
    errors: list[str] = []
    if not (root / "lab.json").is_file():
        errors.append(f"Thiếu {root / 'lab.json'}")
        return {"valid": False, "errors": errors, "task_count": 0}

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
        for artifact in handoff.get("artifacts", []):
            artifact_path = (REPO_ROOT / artifact["path"]).resolve()
            if not artifact_path.is_file():
                errors.append(f"{path.name}: thiếu artifact {artifact['path']}")
            elif _sha256(artifact_path) != artifact["sha256"]:
                errors.append(f"{path.name}: hash đã thay đổi {artifact['path']}")

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
    tools = {name: bool(shutil.which(binary)) for name, binary in {
        "codex": "codex", "claude": "claude", "opencode": "opencode", "antigravity": "agy"
    }.items()}
    return {
        "lab_dir": str(root),
        "valid": validation["valid"],
        "errors": validation["errors"],
        "tasks": by_status,
        "cli_available": tools,
        "git_initialized": (REPO_ROOT / ".git").is_dir(),
        "current_project_claim_ceiling": "SCREENED",
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
        if CLAIM_ORDER[claim_level] > CLAIM_ORDER[task["claim_ceiling"]]:
            raise ValueError(f"Claim {claim_level} vượt trần {task['claim_ceiling']}")
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
        previous_reviews = sorted((root / "reviews").glob(f"{task_id}.*.r*.json"))
        revision = len(previous_reviews) + 1
        review_path = root / "reviews" / f"{task_id}.{reviewer_id}.r{revision:03d}.json"
        _atomic_json(review_path, review)
        task["reviewer"] = reviewer_id
        task["status"] = {"APPROVE": "ACCEPTED", "REVISE": "ACTIVE", "REJECT": "REJECTED"}[decision]
        task.setdefault("review_notes", []).append(notes)
        _atomic_json(task_path, task)
    return review
