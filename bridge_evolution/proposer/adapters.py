"""Ba adapter cùng một giao diện ``propose(request) -> AdapterResult`` (BRD-053).

* ``HeuristicProposer`` — đối chứng KHÔNG LLM, tất định theo seed.
* ``OpenAICompatibleProposer`` — LLM local (LM Studio/Ollama/vLLM) hoặc dịch vụ
  tương thích OpenAI ``/chat/completions``; transport tiêm được để test hermetic;
  API key chỉ đọc từ biến môi trường lúc chạy, không bao giờ vào báo cáo.
* ``VendorCLIProposer`` — tái dùng ``collaboration.providers.run_provider`` ở chế
  độ chỉ đọc (codex/claude/opencode/antigravity).

Mọi adapter đều trả JSON đã qua ``validate_response``; output hỏng, khóa lạ hay
``request_id`` sai → ``MALFORMED`` (không phải exception). Không adapter nào có
quyền phán quyết.
"""
from __future__ import annotations

import json
import os
import random
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Protocol

from .contract import (
    ProposerError,
    SCHEMA_VERSION,
    canonical_json,
    load_basis,
    sha256_json,
    sha256_text,
    validate_response,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
ADAPTER_STATUSES = ("OK", "MALFORMED", "UNAVAILABLE", "TIMEOUT")
RAW_EXCERPT_CHARS = 600


@dataclass(frozen=True)
class AdapterResult:
    status: str
    response: dict | None
    raw_text: str
    error: str | None
    elapsed_s: float
    meta: dict = field(default_factory=dict)

    @property
    def raw_sha256(self) -> str | None:
        return sha256_text(self.raw_text) if self.raw_text else None

    @property
    def raw_excerpt(self) -> str:
        return self.raw_text[:RAW_EXCERPT_CHARS]


class ProposerAdapter(Protocol):
    adapter_id: str
    kind: str

    def propose(self, request: dict) -> AdapterResult: ...

    def describe(self) -> dict: ...


# --------------------------------------------------------------------------- parse helpers
def extract_json_object(text: str) -> dict:
    """Lấy JSON object đầu tiên–cuối cùng trong text (bỏ code fence); ném ValueError nếu không có."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1]
        cleaned = cleaned.rsplit("```", 1)[0].strip()
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("không tìm thấy JSON object trong câu trả lời")
    parsed = json.loads(cleaned[start:end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("JSON trả về không phải object")
    return parsed


def finalize(raw_text: str, request_id: str, started: float, meta: dict) -> AdapterResult:
    """Parse + validate output thô của một bộ não; mọi lỗi nội dung là MALFORMED."""
    elapsed = time.perf_counter() - started
    try:
        parsed = extract_json_object(raw_text)
    except (ValueError, json.JSONDecodeError) as exc:
        return AdapterResult("MALFORMED", None, raw_text, f"không parse được JSON: {exc}", elapsed, meta)
    errors = validate_response(parsed, expected_request_id=request_id)
    if errors:
        return AdapterResult("MALFORMED", None, raw_text, "; ".join(errors[:6]), elapsed, meta)
    return AdapterResult("OK", parsed, raw_text, None, elapsed, meta)


def build_prompt(request: dict) -> tuple[str, str, str]:
    """(system, user, prompt_template_sha256) từ basis; request được nhúng như DỮ LIỆU."""
    prompt = load_basis()["prompt"]
    system = prompt["system"]
    user = prompt["user_prefix"] + json.dumps(request, ensure_ascii=False, indent=1) + prompt["user_suffix"]
    template_sha = sha256_json({"system": system, "user_prefix": prompt["user_prefix"],
                                "user_suffix": prompt["user_suffix"]})
    return system, user, template_sha


# --------------------------------------------------------------------------- heuristic
class HeuristicProposer:
    """Đối chứng không LLM: bước lân cận trong miền theo thẻ tri thức + thứ tự khai trong basis.

    REPAIR (gene hiện tại chưa SCREENED): tăng một bậc biến mà thẻ tri thức
    xếp hạng cao chỉ ra, rồi lần lượt các biến theo ``strengthen_order``.
    TRIM (đã SCREENED): giảm một bậc biến theo ``trim_order``.
    EXPLORE_L0: như TRIM nhưng chỉ có mục tiêu đi qua L0.
    Luôn thêm một nước ngẫu nhiên có seed để thăm dò. Không lặp (biến, giá trị)
    đã bị từ chối trên cùng gene gốc trong history.
    """

    kind = "heuristic"

    def __init__(self, seed: int = 0):
        self.seed = int(seed)
        policy = load_basis()["heuristic_policy"]
        self.adapter_id = load_basis()["adapters"]["heuristic"]["adapter_id"]
        self.strengthen_order = list(policy["strengthen_order"])
        self.trim_order = list(policy["trim_order"])
        self.strengthen_direction = dict(policy.get("strengthen_direction", {}))
        self.trim_direction = dict(policy.get("trim_direction", {}))
        self.default_strengthen = int(policy.get("default_strengthen_step", 1))
        self.default_trim = int(policy.get("default_trim_step", -1))
        self._proposed: dict[str, set[tuple[str, object]]] = {}

    def describe(self) -> dict:
        return {"kind": self.kind, "adapter_id": self.adapter_id, "model": None,
                "endpoint_host": None, "provider": None, "api_key_env": None,
                "api_key_present": False, "prompt_template_sha256": None, "seed": self.seed}

    @staticmethod
    def _ordered(order: list[str], names: list[str]) -> list[str]:
        known = [n for n in order if n in names]
        return known + sorted(n for n in names if n not in known)

    def _step(self, gene: dict, space: dict, name: str, step: int) -> object | None:
        domain = space[name]["domain"]
        try:
            idx = domain.index(gene[name])
        except (ValueError, KeyError):
            return None
        target = idx + step
        if 0 <= target < len(domain):
            return domain[target]
        return None

    def propose(self, request: dict) -> AdapterResult:
        started = time.perf_counter()
        gene = request["current_gene"]
        space = request["design_space"]
        mode = request["mode"]
        base_key = sha256_json(gene)
        already = self._proposed.setdefault(base_key, set())
        rejected = {
            (name, value)
            for entry in request.get("history", [])
            if entry.get("verifier_feasible") is not True and entry.get("status") != "L0_SCREENED"
            for name, value in (entry.get("changes") or {}).items()
        }
        names = list(space)
        candidates: list[tuple[dict, str, list[dict]]] = []

        def add(name: str, value: object, why: str, effects: list[dict]) -> None:
            if value is None or (name, value) in already or (name, value) in rejected:
                return
            if any(c[0] == {name: value} for c in candidates):
                return
            candidates.append(({name: value}, why, effects))

        current = request["current_assessment"]
        blocker_codes = [v["code"] for v in current.get("feedback_violations", [])] or [
            b["code"] for b in current.get("blockers", [])
            if not b["code"].startswith(("SITE-", "APP-", "EVALUATOR-", "SCHEMA-"))]
        effects = [{"rule_id": code[:40], "direction": "decrease"} for code in blocker_codes[:6]]
        if mode == "REPAIR":
            for card in request.get("knowledge_cards", []):
                for name in card.get("applies_to", {}).get("variables", []):
                    if name in space:
                        step = self.strengthen_direction.get(name, self.default_strengthen)
                        add(name, self._step(gene, space, name, step),
                            f"Theo thẻ {card['card_id']} (tham khảo chưa kiểm chứng): tăng một bậc {name} "
                            f"để giảm vi phạm {', '.join(blocker_codes[:3]) or 'hiện có'}", effects)
            for name in self._ordered(self.strengthen_order, names):
                step = self.strengthen_direction.get(name, self.default_strengthen)
                add(name, self._step(gene, space, name, step),
                    f"Tăng một bậc {name} theo thứ tự sửa của lab để giảm {', '.join(blocker_codes[:3]) or 'vi phạm'}",
                    effects)
        else:
            objective = request["objective"]["key"]
            for name in self._ordered(self.trim_order, names):
                step = self.trim_direction.get(name, self.default_trim)
                add(name, self._step(gene, space, name, step),
                    f"Giảm một bậc {name} để hạ {objective} mà kỳ vọng vẫn giữ SCREENED",
                    [{"rule_id": "max_utilization", "direction": "increase"}])
        rng = random.Random(self.seed * 1_000_003 + int(request["round"]))
        for _ in range(8):
            name = rng.choice(names)
            value = rng.choice(space[name]["domain"])
            if value != gene.get(name):
                add(name, value, f"Thăm dò ngẫu nhiên có seed: {name} → {value}",
                    [{"rule_id": "max_utilization", "direction": "unknown"}])
                break
        limit = int(request["budget"]["max_proposals_this_round"])
        chosen = candidates[:limit]
        for changes, _, _ in chosen:
            already.add(next(iter(changes.items())))
        if not chosen:
            payload = {"schema_version": SCHEMA_VERSION, "request_id": request["request_id"],
                       "proposals": [], "notes": "heuristic hết nước đi chưa thử trên gene này"}
            raw = canonical_json(payload)
            # proposals rỗng vi phạm minItems=1 → MALFORMED có chủ đích: lab sẽ ghi và dừng.
            return finalize(raw, request["request_id"], started, self.describe())
        payload = {
            "schema_version": SCHEMA_VERSION,
            "request_id": request["request_id"],
            "proposals": [
                {"changes": changes, "hypothesis": why, "rationale": "heuristic đối chứng của lab, "
                 "clause LAB-HEURISTIC-UNSOURCED-PROPOSER-01", "expected_effects": eff,
                 "cites": [c["card_id"] for c in request.get("knowledge_cards", [])[:2]],
                 "confidence": 0.3}
                for changes, why, eff in chosen
            ],
            "notes": f"mode={mode}; {len(candidates)} nước ứng viên, chọn {len(chosen)}",
        }
        return finalize(canonical_json(payload), request["request_id"], started, self.describe())


# --------------------------------------------------------------------------- HTTP (OpenAI-compatible)
Transport = Callable[[str, bytes, dict, float], tuple[int, str]]


def _urllib_transport(url: str, body: bytes, headers: dict, timeout: float) -> tuple[int, str]:
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - endpoint do người dùng cấu hình
            return int(resp.status), resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return int(exc.code), exc.read().decode("utf-8", errors="replace")


class OpenAICompatibleProposer:
    """Bộ não LLM qua endpoint tương thích OpenAI (LM Studio, Ollama, vLLM, dịch vụ có key)."""

    kind = "http"

    def __init__(self, endpoint: str | None = None, model: str | None = None, *,
                 timeout_seconds: float | None = None, transport: Transport | None = None,
                 api_key_env: str | None = None, temperature: float | None = None,
                 max_tokens: int | None = None, json_mode: bool | None = None):
        cfg = load_basis()["adapters"]["http"]
        self.endpoint = (endpoint or os.environ.get(cfg["endpoint_env"], "")).strip().rstrip("/")
        self.model = (model or os.environ.get(cfg["model_env"], "")).strip()
        if not self.endpoint or not self.model:
            raise ProposerError(
                f"Adapter HTTP cần endpoint và model (tham số hoặc biến môi trường "
                f"{cfg['endpoint_env']}/{cfg['model_env']})")
        parsed = urllib.parse.urlparse(self.endpoint)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ProposerError(f"Endpoint không hợp lệ: {self.endpoint!r}")
        self.endpoint_host = parsed.netloc
        self.api_key_env = api_key_env or cfg["api_key_env"]
        self.timeout = float(timeout_seconds if timeout_seconds is not None else cfg["timeout_seconds"])
        self.temperature = float(temperature if temperature is not None else cfg["temperature"])
        self.max_tokens = int(max_tokens if max_tokens is not None else cfg["max_tokens"])
        self.json_mode = bool(cfg["json_mode"] if json_mode is None else json_mode)
        self.transport = transport or _urllib_transport
        self.adapter_id = f"{cfg['adapter_id_prefix']}/{self.model}"
        self.path = cfg["path"]

    def describe(self) -> dict:
        return {"kind": self.kind, "adapter_id": self.adapter_id, "model": self.model,
                "endpoint_host": self.endpoint_host, "provider": None,
                "api_key_env": self.api_key_env,
                "api_key_present": bool(os.environ.get(self.api_key_env)),
                "prompt_template_sha256": build_prompt({"request_id": "x"})[2]}

    def propose(self, request: dict) -> AdapterResult:
        started = time.perf_counter()
        system, user, template_sha = build_prompt(request)
        meta = self.describe()
        meta["prompt_template_sha256"] = template_sha
        payload = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        if self.json_mode:
            payload["response_format"] = {"type": "json_object"}
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        api_key = os.environ.get(self.api_key_env)  # chỉ tồn tại trong bộ nhớ của request này
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        url = self.endpoint + self.path
        try:
            status, text = self.transport(url, json.dumps(payload).encode("utf-8"), headers, self.timeout)
        except (socket.timeout, TimeoutError) as exc:
            return AdapterResult("TIMEOUT", None, "", f"endpoint quá thời gian {self.timeout}s: {exc}",
                                 time.perf_counter() - started, meta)
        except (urllib.error.URLError, OSError, ValueError) as exc:
            return AdapterResult("UNAVAILABLE", None, "", f"không gọi được endpoint: {exc}",
                                 time.perf_counter() - started, meta)
        if status != 200:
            return AdapterResult("UNAVAILABLE", None, text[:RAW_EXCERPT_CHARS],
                                 f"HTTP {status} từ endpoint", time.perf_counter() - started, meta)
        try:
            envelope = json.loads(text)
            content = envelope["choices"][0]["message"]["content"]
            if not isinstance(content, str):
                raise TypeError("content không phải chuỗi")
        except (json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
            return AdapterResult("MALFORMED", None, text, f"envelope chat/completions không đúng: {exc}",
                                 time.perf_counter() - started, meta)
        return finalize(content, request["request_id"], started, meta)


# --------------------------------------------------------------------------- vendor CLI
class VendorCLIProposer:
    """Bộ não là một CLI AI (codex/claude/opencode/antigravity) chạy CHỈ ĐỌC qua run_provider."""

    kind = "cli"

    def __init__(self, provider: str, *, timeout_seconds: int | None = None, runner=None,
                 workspace: str | Path | None = None):
        cfg = load_basis()["adapters"]["cli"]
        if provider not in cfg["providers"]:
            raise ProposerError(f"Provider CLI không hỗ trợ: {provider}")
        self.provider = provider
        self.timeout = int(timeout_seconds if timeout_seconds is not None else cfg["timeout_seconds"])
        self.runner = runner
        self.workspace = Path(workspace) if workspace else REPO_ROOT
        self.adapter_id = f"{cfg['adapter_id_prefix']}{provider}/0.1.0"

    def describe(self) -> dict:
        return {"kind": self.kind, "adapter_id": self.adapter_id, "model": None,
                "endpoint_host": None, "provider": self.provider, "api_key_env": None,
                "api_key_present": False, "prompt_template_sha256": build_prompt({"request_id": "x"})[2]}

    def propose(self, request: dict) -> AdapterResult:
        from ..collaboration.orchestrator import _extract_json
        from ..collaboration.providers import run_provider

        started = time.perf_counter()
        system, user, template_sha = build_prompt(request)
        meta = self.describe()
        meta["prompt_template_sha256"] = template_sha
        prompt = (
            f"{system}\n\nRÀNG BUỘC CHO CLI: không gọi bất kỳ lab CLI/API nào, không đọc task board, "
            f"không sửa/tạo file. Trả về DUY NHẤT một JSON object.\n\n{user}"
        )
        kwargs = {"timeout_seconds": self.timeout, "writable": False}
        if self.runner is not None:
            kwargs["runner"] = self.runner
        try:
            result = run_provider(self.provider, prompt, self.workspace, **kwargs)
        except FileNotFoundError as exc:
            return AdapterResult("UNAVAILABLE", None, "", str(exc), time.perf_counter() - started, meta)
        if result.timed_out:
            return AdapterResult("TIMEOUT", None, result.stdout[:RAW_EXCERPT_CHARS],
                                 f"CLI {self.provider} quá {self.timeout}s", time.perf_counter() - started, meta)
        if not result.successful:
            return AdapterResult("UNAVAILABLE", None, result.stdout[:RAW_EXCERPT_CHARS],
                                 f"CLI {self.provider} returncode={result.returncode}: {result.stderr[-300:]}",
                                 time.perf_counter() - started, meta)
        try:
            parsed = _extract_json(self.provider, result.stdout)
        except (ValueError, json.JSONDecodeError, KeyError, TypeError) as exc:
            return AdapterResult("MALFORMED", None, result.stdout, f"không trích được JSON: {exc}",
                                 time.perf_counter() - started, meta)
        return finalize(canonical_json(parsed), request["request_id"], started, meta)


# --------------------------------------------------------------------------- factory
def make_adapter(spec: str, *, seed: int = 0, endpoint: str | None = None, model: str | None = None,
                 timeout_seconds: float | None = None, runner=None, transport: Transport | None = None):
    """``heuristic`` | ``http`` | ``cli:<provider>`` → adapter."""
    spec = (spec or "").strip()
    if spec == "heuristic":
        return HeuristicProposer(seed=seed)
    if spec == "http":
        return OpenAICompatibleProposer(endpoint, model, timeout_seconds=timeout_seconds, transport=transport)
    if spec.startswith("cli:"):
        return VendorCLIProposer(spec.split(":", 1)[1],
                                 timeout_seconds=int(timeout_seconds) if timeout_seconds else None,
                                 runner=runner)
    raise ProposerError(f"Adapter không hỗ trợ: {spec!r} (dùng heuristic | http | cli:<provider>)")
