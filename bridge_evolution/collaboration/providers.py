"""Safe non-interactive adapters for the Bridge Lab agent providers.

Provider processes are intentionally treated as untrusted workers.  Commands
are constructed as argv arrays, never passed through a shell, receive only the
task prompt, and have bounded time/output.  Canonical task state is still
validated by :mod:`bridge_evolution.collaboration.lab`.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import os
from pathlib import Path
import shutil
import subprocess
import time
from typing import Callable


PROVIDERS = ("codex", "claude", "opencode", "antigravity")
MAX_CAPTURE_BYTES = 2 * 1024 * 1024


@dataclass(frozen=True)
class ProviderResult:
    provider: str
    command: list[str]
    returncode: int | None
    stdout: str
    stderr: str
    elapsed_seconds: float
    timed_out: bool
    output_truncated: bool


def _latest_claude_code() -> str | None:
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        return None
    root = Path(local) / "Packages"
    candidates = sorted(
        root.glob("Claude_*/*/Roaming/Claude/claude-code/*/claude.exe"),
        key=lambda item: item.parent.name,
        reverse=True,
    )
    return str(candidates[0]) if candidates else None


def discover_provider(provider: str) -> str | None:
    """Return a real CLI binary, excluding similarly named desktop GUIs."""
    if provider not in PROVIDERS:
        raise ValueError(f"Provider không được hỗ trợ: {provider}")
    environment = os.environ.get(f"DYLIGHT_{provider.upper()}_CLI")
    if environment:
        supplied = Path(environment).expanduser().resolve()
        return str(supplied) if supplied.is_file() else None
    if provider == "codex":
        return shutil.which("codex")
    if provider == "claude":
        return shutil.which("claude") or _latest_claude_code()
    if provider == "opencode":
        return shutil.which("opencode")
    return shutil.which("agy")


def _bounded(value: bytes) -> tuple[str, bool]:
    truncated = len(value) > MAX_CAPTURE_BYTES
    data = value[:MAX_CAPTURE_BYTES]
    return data.decode("utf-8", errors="replace"), truncated


def _probe(binary: str, args: list[str], timeout: int = 10) -> dict:
    started = time.monotonic()
    try:
        completed = subprocess.run(
            [binary, *args], cwd=str(Path.cwd()), stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False,
            timeout=timeout, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "callable": False,
            "returncode": None,
            "detail": str(exc),
            "elapsed_seconds": round(time.monotonic() - started, 3),
        }
    stdout, _ = _bounded(completed.stdout)
    stderr, _ = _bounded(completed.stderr)
    detail = (stdout or stderr).strip().splitlines()
    return {
        "callable": completed.returncode == 0,
        "returncode": completed.returncode,
        "detail": detail[0][:300] if detail else "no output",
        "elapsed_seconds": round(time.monotonic() - started, 3),
    }


def provider_doctor() -> dict:
    """Report availability without opening a GUI or exposing credentials."""
    report: dict[str, dict] = {}
    for provider in PROVIDERS:
        binary = discover_provider(provider)
        if not binary:
            report[provider] = {
                "binary": None, "available": False, "callable": False,
                "authenticated": None, "detail": "CLI không có trong PATH/cấu hình",
            }
            continue
        probe = _probe(binary, ["--version"])
        authenticated: bool | None = None
        auth_detail = None
        if provider == "claude" and probe["callable"]:
            auth = _probe(binary, ["auth", "status"])
            authenticated = auth["returncode"] == 0
            auth_detail = auth["detail"]
        elif provider == "codex" and probe["callable"]:
            auth = _probe(binary, ["login", "status"])
            authenticated = auth["returncode"] == 0
            auth_detail = auth["detail"]
        report[provider] = {
            "binary": binary,
            "available": True,
            "callable": probe["callable"],
            "authenticated": authenticated,
            "detail": probe["detail"],
            "auth_detail": auth_detail,
        }
    return report


def _command(
    provider: str, binary: str, workspace: Path, prompt: str, *, writable: bool
) -> tuple[list[str], str | None]:
    if provider == "codex":
        return ([
            binary, "exec", "--json", "--ephemeral", "--cd", str(workspace),
            "--sandbox", "workspace-write" if writable else "read-only",
            "--ask-for-approval", "never", "-",
        ], prompt)
    if provider == "claude":
        tools = "Read,Glob,Grep,Edit,Write" if writable else "Read,Glob,Grep"
        return ([
            binary, "-p", prompt, "--output-format", "json",
            "--permission-mode", "dontAsk", "--tools", tools,
            "--allowedTools", tools, "--no-session-persistence",
            "--max-turns", "20", "--max-budget-usd", "2",
        ], None)
    if provider == "opencode":
        agent = "dylight-worker" if writable else "dylight-reviewer"
        return ([
            binary, "--pure", "run", "--dir", str(workspace),
            "--agent", agent, "--format", "json", prompt,
        ], None)
    mode = "accept-edits" if writable else "plan"
    return ([
        binary, "-p", prompt, "--output-format", "json", f"--mode={mode}",
        "--sandbox", "--print-timeout", "15m",
    ], None)


def run_provider(
    provider: str,
    prompt: str,
    workspace: str | Path,
    *,
    timeout_seconds: int,
    writable: bool = True,
    runner: Callable[..., subprocess.CompletedProcess] | None = None,
) -> ProviderResult:
    """Run one bounded worker attempt.  ``runner`` exists for hermetic tests."""
    binary = discover_provider(provider)
    if not binary:
        raise FileNotFoundError(f"Không tìm thấy CLI cho provider {provider}")
    root = Path(workspace).resolve()
    if not root.is_dir():
        raise FileNotFoundError(root)
    argv, stdin_value = _command(provider, binary, root, prompt, writable=writable)
    started = time.monotonic()
    execute = runner or subprocess.run
    try:
        completed = execute(
            argv, cwd=str(root), input=(stdin_value.encode("utf-8") if stdin_value else None),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False,
            timeout=timeout_seconds, check=False,
        )
        stdout, stdout_truncated = _bounded(completed.stdout or b"")
        stderr, stderr_truncated = _bounded(completed.stderr or b"")
        return ProviderResult(
            provider=provider, command=[Path(argv[0]).name, *argv[1:]],
            returncode=completed.returncode, stdout=stdout, stderr=stderr,
            elapsed_seconds=round(time.monotonic() - started, 3), timed_out=False,
            output_truncated=stdout_truncated or stderr_truncated,
        )
    except subprocess.TimeoutExpired as exc:
        stdout, stdout_truncated = _bounded(exc.stdout or b"")
        stderr, stderr_truncated = _bounded(exc.stderr or b"")
        return ProviderResult(
            provider=provider, command=[Path(argv[0]).name, *argv[1:]],
            returncode=None, stdout=stdout, stderr=stderr,
            elapsed_seconds=round(time.monotonic() - started, 3), timed_out=True,
            output_truncated=stdout_truncated or stderr_truncated,
        )


def result_as_dict(result: ProviderResult) -> dict:
    return asdict(result)
