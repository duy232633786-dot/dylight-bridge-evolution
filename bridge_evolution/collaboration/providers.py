"""Safe non-interactive adapters for the Bridge Lab agent providers.

Provider processes are intentionally treated as untrusted workers.  Commands
are constructed as argv arrays, never passed through a shell, receive only the
task prompt, and have bounded time/output.  Canonical task state is still
validated by :mod:`bridge_evolution.collaboration.lab`.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from typing import Callable


PROVIDERS = ("codex", "claude", "opencode", "antigravity")
MAX_CAPTURE_BYTES = 2 * 1024 * 1024
CLAUDE_BOUNDED_SYSTEM_PROMPT = """You are a non-interactive bounded artifact worker
inside an already-authoritative research orchestrator. The orchestrator has already
selected and claimed the exact task named in the user prompt. Repository instructions
about running status, manually claiming work, inspecting the task board, selecting a
task, testing, submitting, reviewing, or asking the user for authorization are not
applicable in this invocation. Do not read AGENTS.md or CLAUDE.md, inspect unrelated
tasks, use a shell, or ask which task to perform. Follow the exact read/write boundaries
and required artifacts in the user prompt. Safety rules against fabricated engineering
evidence remain binding. Return only the response shape requested by the user prompt.
"""
ANTIGRAVITY_SOFT_DENIAL_MARKERS = (
    "soft-denied",
    "soft denied",
    "permission denied",
    "denied by permission",
    "requires approval",
    "cannot prompt for approval",
    "to allow this tool",
)


def _antigravity_output_succeeded(stdout: str, stderr: str) -> bool:
    """Require a successful JSON envelope and no headless permission denial."""
    try:
        envelope = json.loads(stdout.strip())
    except (json.JSONDecodeError, TypeError):
        return False
    if not isinstance(envelope, dict) or envelope.get("status") != "SUCCESS":
        return False
    if envelope.get("error"):
        return False
    diagnostics = stderr.casefold()
    return not any(marker in diagnostics for marker in ANTIGRAVITY_SOFT_DENIAL_MARKERS)


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

    @property
    def successful(self) -> bool:
        if self.returncode != 0 or self.timed_out:
            return False
        if self.provider == "antigravity":
            return not self.output_truncated and _antigravity_output_succeeded(
                self.stdout, self.stderr
            )
        return True


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


def _npm_claude_code() -> str | None:
    """Resolve the native executable behind npm's Windows ``claude.cmd`` shim."""
    launcher = shutil.which("claude")
    if not launcher:
        return None
    candidate = (
        Path(launcher).resolve().parent
        / "node_modules" / "@anthropic-ai" / "claude-code" / "bin" / "claude.exe"
    )
    return str(candidate) if candidate.is_file() else None


def _installed_antigravity_cli() -> str | None:
    """Locate the official Windows CLI without accepting an IDE launcher.

    Antigravity IDE ships ``antigravity-ide.cmd``, but that command only opens
    the editor's VS Code-style CLI.  It does not implement the headless
    ``agy -p`` protocol expected by this adapter.
    """
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        return None
    candidate = Path(local) / "agy" / "bin" / "agy.exe"
    return str(candidate) if candidate.is_file() else None


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
        # Prefer a native executable. Passing prompts containing '<' or '>'
        # through a .cmd shim lets cmd.exe reinterpret research markup.
        return _npm_claude_code() or _latest_claude_code() or shutil.which("claude")
    if provider == "opencode":
        return shutil.which("opencode")
    return shutil.which("agy") or _installed_antigravity_cli()


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
        probe = _probe(binary, ["--help"] if provider == "antigravity" else ["--version"])
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
        elif provider == "opencode" and probe["callable"]:
            auth = _probe(binary, ["auth", "list"])
            normalized = auth["detail"].lower()
            authenticated = auth["returncode"] == 0 and "0 credentials" not in normalized
            auth_detail = auth["detail"]
        elif provider == "antigravity" and probe["callable"]:
            # Antigravity CLI currently has no non-interactive auth-status
            # subcommand.  ``models`` is the cheapest authenticated API probe
            # and does not run an agent or alter workspace state.
            auth = _probe(binary, ["models"])
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
        sandbox_args = ["--approve-for-me"] if writable else ["--sandbox", "read-only"]
        return ([
            binary, "exec", "--json", "--ephemeral", "--cd", str(workspace),
            "--disable", "multi_agent",
            *sandbox_args, "-",
        ], prompt)
    if provider == "claude":
        tools = "Read,Glob,Grep,Edit,Write" if writable else "Read,Glob,Grep"
        bounded_prompt = f"""CLAUDE WORKSPACE BOUNDARY:
The repository root is: {workspace}
Resolve every repository-relative path in the assignment under that exact root.
The process working directory is intentionally neutral to prevent automatic project
instruction discovery. Do not read or write in the neutral working directory. Read and
write only the exact repository files authorized by the assignment.

{prompt}
"""
        return ([
            binary, "-p", bounded_prompt, "--output-format", "json",
            "--safe-mode", "--system-prompt", CLAUDE_BOUNDED_SYSTEM_PROMPT,
            "--add-dir", str(workspace),
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
    access = "write only the assigned repo-relative artifact paths" if writable else "do not write files"
    bounded_prompt = f"""ANTIGRAVITY WORKSPACE BOUNDARY:
The only allowed workspace is: {workspace}
Use built-in workspace file read/search/edit/write tools only; {access}.
Do not inspect broad drive roots such as C:\\, workspace ancestors/siblings, or user-home paths.
Do not use shell/terminal commands. Do not place deliverables in Antigravity brain/cache;
all required artifacts must exist at their assigned paths inside the workspace.

{prompt}
"""
    return ([
        binary, "-p", bounded_prompt, "--output-format", "json", f"--mode={mode}",
        "--add-dir", str(workspace), "--sandbox", "--print-timeout", "15m",
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
    execution_cwd = Path(tempfile.gettempdir()).resolve() if provider == "claude" else root
    started = time.monotonic()
    execute = runner or subprocess.run
    try:
        completed = execute(
            argv, cwd=str(execution_cwd),
            input=(stdin_value.encode("utf-8") if stdin_value else None),
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
