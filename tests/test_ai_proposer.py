"""Kiểm thử lớp đề xuất AI có hợp đồng (BRD-053) — hermetic, không gọi LLM thật."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

import bridge_evolution.evaluate as evaluate_mod
from bridge_evolution.catalogs import all_domains, load_grammar
from bridge_evolution.proposer import (
    HeuristicProposer,
    OpenAICompatibleProposer,
    ProposerError,
    VendorCLIProposer,
    apply_changes,
    gene_in_domain,
    load_basis,
    load_schema,
    make_adapter,
    run_proposal_session,
    seed_gene_for_family,
    sha256_json,
    validate_report,
    validate_response,
)
from bridge_evolution.proposer import adapters as adapters_mod
from bridge_evolution.proposer import loop as loop_mod
from bridge_evolution.proposer.contract import failed_rule_ids

ROOT = Path(__file__).resolve().parents[1]
FAMILY = "super_t_simple_v1"
VOLATILE = {"created_at_utc", "elapsed_s"}
CLAIM_GATE_CODES = ("SITE-", "APP-")


def _strip(value):
    if isinstance(value, dict):
        return {k: _strip(v) for k, v in value.items() if k not in VOLATILE}
    if isinstance(value, list):
        return [_strip(v) for v in value]
    return value


def _weak_gene() -> dict:
    """Gene L0-hợp lệ nhưng yếu (cáp ít nhất, dầm thấp nhất) → kỳ vọng verifier L1 từ chối."""
    gene = seed_gene_for_family(FAMILY)
    gene["prestress_layout_id"] = "PT-34"
    gene["girder_catalog_id"] = "ST-1650"
    return gene


def _assessed_items(report: dict) -> list[dict]:
    return [item for rnd in report["rounds"] for item in rnd["proposals"] if item["outcome"] == "ASSESSED"]


# --------------------------------------------------------------------------- hợp đồng
def test_schema_and_basis_are_valid():
    schema = load_schema()
    Draft202012Validator.check_schema(schema)
    for name in ("ProposalRequest", "ProposalResponse", "ProposalSessionReport"):
        assert name in schema["$defs"]
    basis = load_basis()
    assert basis["authority"]["proposer_authority"] == "NONE"
    assert basis["authority"]["claim_ceiling"] == "SCREENED"
    assert basis["adapters"]["http"]["api_key_env"] == "DYLIGHT_LLM_API_KEY"


def test_apply_changes_is_strict_about_domain_and_type():
    domains = all_domains(load_grammar(FAMILY))
    base = seed_gene_for_family(FAMILY)
    assert gene_in_domain(base, domains) == []
    gene, errors = apply_changes(base, {"prestress_layout_id": "PT-46"}, domains)
    assert errors == [] and gene["prestress_layout_id"] == "PT-46"
    for bad in ({"prestress_layout_id": "PT-99"}, {"girder_count": "6"}, {"girder_count": 6.0},
                {"girder_count": True}, {"deck_slab_thickness_mm": 201}, {"khong_ton_tai": 1}, {}, "x"):
        gene, errors = apply_changes(base, bad, domains)
        assert gene is None and errors, bad
    gene, errors = apply_changes(base, {"girder_count": base["girder_count"]}, domains)
    assert gene is None and "không đổi" in errors[0]


def test_response_schema_rejects_verdict_keys_and_request_id_mismatch():
    rid = "a" * 64
    good = {"schema_version": "1.0", "request_id": rid,
            "proposals": [{"changes": {"prestress_layout_id": "PT-42"}, "hypothesis": "giảm SERV-001"}]}
    assert validate_response(good, expected_request_id=rid) == []
    leaked = dict(good, verdict="PASS")
    errors = validate_response(leaked, expected_request_id=rid)
    assert any("phán quyết" in e for e in errors)
    leaked_inner = {"schema_version": "1.0", "request_id": rid,
                    "proposals": [{"changes": {"girder_count": 6}, "hypothesis": "abcdef", "feasible": True}]}
    assert validate_response(leaked_inner, expected_request_id=rid)
    assert validate_response(good, expected_request_id="b" * 64)[0].startswith("request_id")
    assert validate_response({"schema_version": "1.0", "request_id": rid, "proposals": []}, rid)
    # Phát hiện từ lần chạy thật đầu tiên với não Claude (2026-09-05): LLM ghi direction "unchanged"
    # cho rule không đổi — hợp lý, phải chấp nhận; nhưng giá trị ngoài bốn từ khoá vẫn bị loại.
    for direction, ok in (("unchanged", True), ("unknown", True), ("worse", False)):
        resp = {"schema_version": "1.0", "request_id": rid,
                "proposals": [{"changes": {"girder_count": 6}, "hypothesis": "kiểm enum direction",
                               "expected_effects": [{"rule_id": "STR-001", "direction": direction}]}]}
        assert (validate_response(resp, expected_request_id=rid) == []) is ok, direction


def test_failed_rule_ids_prefer_verifier_codes_and_skip_claim_gate_codes():
    summary = {"feedback_violations": [{"code": "SERV-001"}, {"code": "STR-001"}, {"code": "SERV-001"}],
               "blockers": [{"code": "SITE-001"}, {"code": "APP-EVIDENCE-001"}, {"code": "GEO-002"}]}
    assert failed_rule_ids(summary) == ["SERV-001", "STR-001", "GEO-002"]


# --------------------------------------------------------------------------- hai tầng authority
def test_seed_anchor_shows_two_tiers_claim_gate_vs_physics_feedback():
    report = run_proposal_session(seed_gene_for_family(FAMILY), family=FAMILY,
                                  adapter=HeuristicProposer(seed=0), rounds=1, max_evaluations=1, seed=0)
    seed = report["seed_assessment"]
    # Tầng phản hồi: verifier L1 nói gene neo khả thi
    assert seed["feedback_status"] == "SUCCESS" and seed["verifier_feasible"] is True
    assert seed["max_utilization"] is not None and seed["objective_value"] is not None
    # Tầng claim: cổng assess_candidate hôm nay chặn bằng site/evidence → IDEA, không được giả lập
    assert seed["status"] in ("BLOCKED", "SCREENED")
    if seed["status"] == "BLOCKED":
        assert seed["claim_level"] == "IDEA"
        assert all(b["code"].startswith(CLAIM_GATE_CODES) for b in seed["blockers"]), seed["blockers"]
    assert report["feedback_authority"].startswith("evaluate_candidate")
    assert "assess_candidate" in report["verdict_authority"]
    assert "assess_candidate" in report["preregistration"]["claim_gate_note"]


# --------------------------------------------------------------------------- heuristic
def test_heuristic_session_on_anchor_is_valid_and_reproducible():
    seed_gene = seed_gene_for_family(FAMILY)
    kwargs = dict(family=FAMILY, objective_key="relative_cost", rounds=2, max_evaluations=6, seed=7)
    report_a = run_proposal_session(seed_gene, adapter=HeuristicProposer(seed=7), **kwargs)
    report_b = run_proposal_session(seed_gene, adapter=HeuristicProposer(seed=7), **kwargs)
    assert validate_report(report_a) == []
    assert _strip(report_a) == _strip(report_b)
    assert report_a["study_level"] == "L1_STRUCTURAL" and report_a["objective_available"] is True
    assert report_a["seed_assessment"]["verifier_feasible"] is True
    assert report_a["proposer_authority"] == "NONE" and report_a["claim_ceiling"] == "SCREENED"
    assert report_a["evaluations_used"] >= 1
    assert report_a["preregistration_sha256"] == sha256_json(report_a["preregistration"])
    assert report_a["preregistration"]["locked_before_round_1"] is True
    assert report_a["preregistration"]["seed_verifier_feasible"] is True
    assert report_a["rounds"][0]["mode"] == "TRIM"
    for rnd in report_a["rounds"]:
        assert rnd["adapter_status"] == "OK"
        for item in rnd["proposals"]:
            assert item["in_domain"] is True
            if item["outcome"] == "ASSESSED":
                assessment = item["assessment"]
                assert assessment["claim_level"] in ("IDEA", "SCREENED")
                if assessment["status"] == "REJECTED":
                    # L0 từ chối → không mở L1: không có phản hồi verifier, nhưng phải có mã L0 để bộ não học
                    assert assessment["feedback_status"] is None and assessment["blockers"]
                    assert assessment["verifier_feasible"] is None
                else:
                    assert assessment["feedback_status"] is not None
    assert report_a["best"] is not None and report_a["best"]["verifier_feasible"] is True
    assert {d["path"] for d in report_a["source_digests"]} >= {
        "bridge_evolution/proposer/loop.py", "contracts/ai_proposal.schema.json"}


def test_heuristic_repair_records_negative_results_from_infeasible_seed():
    weak = _weak_gene()
    report = run_proposal_session(weak, family=FAMILY, adapter=HeuristicProposer(seed=1),
                                  rounds=3, max_evaluations=8, seed=1)
    assert validate_report(report) == []
    seed = report["seed_assessment"]
    assert seed["verifier_feasible"] is False and seed["feedback_status"] == "SUCCESS"
    assert seed["feedback_violations"], "seed yếu phải có vi phạm từ verifier"
    assert all(not v["code"].startswith(CLAIM_GATE_CODES) for v in seed["feedback_violations"])
    assert report["rounds"][0]["mode"] == "REPAIR"
    assert "verifier" in report["preregistration"]["success_criterion"]
    items = _assessed_items(report)
    assert items, "phải có ít nhất một đề xuất được đánh giá"
    assert report["negative_results"] == sum(1 for i in items if i["assessment"]["verifier_feasible"] is not True)
    if report["best"]:
        assert report["termination_reason"] == "SUCCESS_CRITERION_MET"
        assert report["hypothesis_supported"] is True
    else:
        assert report["hypothesis_supported"] is False


def test_box_family_only_uses_l0_and_never_calls_l1_evaluator(monkeypatch):
    family = "box_girder_parametric_v1"
    calls: list[str] = []
    original = loop_mod.assess_candidate

    def spy(state, **kwargs):
        calls.append(kwargs["study_level"])
        return original(state, **kwargs)

    def forbidden(state, *args, **kwargs):
        raise AssertionError("evaluate_candidate không được gọi cho họ chỉ L0")

    monkeypatch.setattr(loop_mod, "assess_candidate", spy)
    monkeypatch.setattr(evaluate_mod, "evaluate_candidate", forbidden)
    report = run_proposal_session(seed_gene_for_family(family), family=family,
                                  adapter=HeuristicProposer(seed=3), rounds=1, max_evaluations=3, seed=3)
    assert validate_report(report) == []
    assert report["study_level"] == "L0_GEOMETRY" and report["objective_available"] is False
    assert calls and set(calls) == {"L0_GEOMETRY"}
    seed = report["seed_assessment"]
    assert seed["objective_value"] is None and seed["verifier_feasible"] is None
    assert seed["feedback_authority"] == "NONE_AT_THIS_STUDY_LEVEL"
    assert seed["status"] in ("L0_SCREENED", "REJECTED", "BLOCKED")
    assert report["rounds"][0]["mode"] == "EXPLORE_L0"
    assert report["best"] is None
    assert "L0_GEOMETRY" in report["preregistration"]["success_criterion"]


# --------------------------------------------------------------------------- HTTP adapter (hermetic)
def _fake_transport(reply_builder):
    captured = {}

    def transport(url, body, headers, timeout):
        captured["url"], captured["headers"], captured["timeout"] = url, dict(headers), timeout
        payload = json.loads(body.decode("utf-8"))
        captured["payload"] = payload
        request = json.loads(payload["messages"][1]["content"].split("\n", 1)[1].rsplit("\nTrả về", 1)[0])
        content = reply_builder(request)
        return 200, json.dumps({"choices": [{"message": {"role": "assistant", "content": content}}]})

    return transport, captured


def test_http_adapter_valid_proposal_is_evaluated_and_key_never_leaks(monkeypatch):
    monkeypatch.setenv("DYLIGHT_LLM_API_KEY", "sk-test-secret-123")

    def reply(request):
        gene = request["current_gene"]
        domain = request["design_space"]["prestress_layout_id"]["domain"]
        idx = domain.index(gene["prestress_layout_id"])
        target = domain[max(idx - 1, 0)] if request["mode"] == "TRIM" else domain[min(idx + 1, len(domain) - 1)]
        return "```json\n" + json.dumps({
            "schema_version": "1.0", "request_id": request["request_id"],
            "proposals": [{"changes": {"prestress_layout_id": target},
                           "hypothesis": "đổi cấp cáp DƯL một bậc theo mode",
                           "expected_effects": [{"rule_id": "SERV-001", "direction": "unknown"}],
                           "cites": ["KC-001"], "confidence": 0.4}],
            "notes": "fake llm"}) + "\n```"

    transport, captured = _fake_transport(reply)
    adapter = OpenAICompatibleProposer("http://127.0.0.1:1234/v1", "fake-model", transport=transport)
    report = run_proposal_session(seed_gene_for_family(FAMILY), family=FAMILY, adapter=adapter,
                                  rounds=2, max_evaluations=4, seed=0)
    assert validate_report(report) == []
    assert captured["url"] == "http://127.0.0.1:1234/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer sk-test-secret-123"
    assert "sk-test-secret-123" not in json.dumps(report, ensure_ascii=False)
    assert report["adapter"]["endpoint_host"] == "127.0.0.1:1234"
    assert report["adapter"]["api_key_present"] is True and report["adapter"]["model"] == "fake-model"
    first = report["rounds"][0]
    assert first["adapter_status"] == "OK" and first["mode"] == "TRIM"
    assert first["proposals"][0]["outcome"] == "ASSESSED"
    assert first["proposals"][0]["changes"] == {"prestress_layout_id": "PT-38"}
    # request gửi cho LLM phải mang cả hai tầng và luật chơi
    sent = json.loads(captured["payload"]["messages"][1]["content"].split("\n", 1)[1].rsplit("\nTrả về", 1)[0])
    assert "feedback_violations" in sent["current_assessment"] and sent["rules_for_the_proposer"]


def test_http_adapter_verdict_keys_are_malformed_and_session_stops():
    def reply(request):
        return json.dumps({"schema_version": "1.0", "request_id": request["request_id"], "verdict": "PASS",
                           "proposals": [{"changes": {"girder_count": 6}, "hypothesis": "tự phán quyết"}]})

    transport, _ = _fake_transport(reply)
    adapter = OpenAICompatibleProposer("http://localhost:11434/v1", "qwen-fake", transport=transport)
    report = run_proposal_session(seed_gene_for_family(FAMILY), family=FAMILY, adapter=adapter,
                                  rounds=4, max_evaluations=4, seed=0)
    assert validate_report(report) == []
    assert [r["adapter_status"] for r in report["rounds"]] == ["MALFORMED", "MALFORMED"]
    assert "phán quyết" in report["rounds"][0]["adapter_error"]
    assert report["evaluations_used"] == 0
    assert report["termination_reason"] == "ADAPTER_FAILED_REPEATEDLY"
    assert report["hypothesis_supported"] is False


def test_http_adapter_request_id_mismatch_and_out_of_domain_are_recorded():
    state = {"n": 0}

    def reply(request):
        state["n"] += 1
        if state["n"] == 1:
            return json.dumps({"schema_version": "1.0", "request_id": "f" * 64,
                               "proposals": [{"changes": {"girder_count": 6}, "hypothesis": "sai id"}]})
        return json.dumps({"schema_version": "1.0", "request_id": request["request_id"],
                           "proposals": [{"changes": {"girder_count": 99}, "hypothesis": "ngoài miền"},
                                         {"changes": {"girder_spacing_mm": 2175}, "hypothesis": "lệch lưới"},
                                         {"changes": {"bien_la": "x"}, "hypothesis": "biến không tồn tại"}]})

    transport, _ = _fake_transport(reply)
    adapter = OpenAICompatibleProposer("http://127.0.0.1:8000/v1", "m", transport=transport)
    report = run_proposal_session(seed_gene_for_family(FAMILY), family=FAMILY, adapter=adapter,
                                  rounds=2, max_evaluations=4, seed=0)
    assert report["rounds"][0]["adapter_status"] == "MALFORMED"
    assert report["rounds"][0]["adapter_error"].startswith("request_id")
    second = report["rounds"][1]
    assert second["adapter_status"] == "OK"
    assert [p["outcome"] for p in second["proposals"]] == ["OUT_OF_DOMAIN"] * 3
    assert all(p["domain_errors"] for p in second["proposals"])
    assert report["out_of_domain"] == 3 and report["evaluations_used"] == 0
    assert report["termination_reason"] == "BUDGET_ROUNDS_EXHAUSTED"


def test_http_adapter_float_value_is_malformed_by_schema():
    def reply(request):
        return json.dumps({"schema_version": "1.0", "request_id": request["request_id"],
                           "proposals": [{"changes": {"deck_slab_thickness_mm": 2.5}, "hypothesis": "sai kiểu"}]})

    transport, _ = _fake_transport(reply)
    adapter = OpenAICompatibleProposer("http://127.0.0.1:8000/v1", "m", transport=transport)
    result = adapter.propose({"request_id": "a" * 64})
    assert result.status == "MALFORMED"


def test_http_adapter_unavailable_and_bad_envelope():
    def boom(url, body, headers, timeout):
        raise OSError("connection refused")

    adapter = OpenAICompatibleProposer("http://127.0.0.1:1/v1", "m", transport=boom)
    request = {"request_id": "a" * 64}
    result = adapter.propose(request)
    assert result.status == "UNAVAILABLE" and result.response is None

    def bad_envelope(url, body, headers, timeout):
        return 200, json.dumps({"unexpected": True})

    adapter = OpenAICompatibleProposer("http://127.0.0.1:1/v1", "m", transport=bad_envelope)
    assert adapter.propose(request).status == "MALFORMED"

    def http_500(url, body, headers, timeout):
        return 500, "server error"

    adapter = OpenAICompatibleProposer("http://127.0.0.1:1/v1", "m", transport=http_500)
    assert adapter.propose(request).status == "UNAVAILABLE"

    def slow(url, body, headers, timeout):
        raise TimeoutError("timed out")

    adapter = OpenAICompatibleProposer("http://127.0.0.1:1/v1", "m", transport=slow)
    assert adapter.propose(request).status == "TIMEOUT"

    with pytest.raises(ProposerError):
        OpenAICompatibleProposer("ftp://x", "m", transport=boom)
    with pytest.raises(ProposerError):
        OpenAICompatibleProposer(None, None, transport=boom)


# --------------------------------------------------------------------------- vendor CLI adapter (hermetic)
def test_cli_adapter_parses_codex_events_with_fake_runner(monkeypatch):
    import bridge_evolution.collaboration.providers as providers

    monkeypatch.setattr(providers, "discover_provider", lambda provider: "codex-fake")
    seen = {}

    def fake_runner(command, *args, **kwargs):
        seen["command"] = list(command)
        seen["kwargs"] = kwargs
        prompt = kwargs.get("input") or b""
        if isinstance(prompt, bytes):  # run_provider gửi prompt qua stdin dạng bytes UTF-8
            prompt = prompt.decode("utf-8", errors="replace")
        # Request được nhúng như DỮ LIỆU giữa user_prefix và user_suffix; bộ não giả đọc lại nó.
        start = prompt.find("{", prompt.find("ProposalRequest (JSON"))
        end = prompt.rfind("}", 0, prompt.rfind("Trả về DUY NHẤT"))
        request = json.loads(prompt[start:end + 1])
        current = request["current_gene"]["girder_catalog_id"]
        target = next(v for v in request["design_space"]["girder_catalog_id"]["domain"] if v != current)
        seen["target"] = target
        message = json.dumps({"schema_version": "1.0", "request_id": request["request_id"],
                              "proposals": [{"changes": {"girder_catalog_id": target},
                                             "hypothesis": "đổi cấp dầm để kiểm đường CLI chỉ đọc"}]})
        stdout = "\n".join([
            json.dumps({"type": "item.started", "item": {"type": "reasoning"}}),
            json.dumps({"type": "item.completed", "item": {"type": "agent_message", "text": message}}),
        ])
        # run_provider đọc stdout/stderr dạng bytes (capture_output, không text=True)
        return subprocess.CompletedProcess(command, 0, stdout=stdout.encode("utf-8"), stderr=b"")

    adapter = VendorCLIProposer("codex", timeout_seconds=30, runner=fake_runner)
    report = run_proposal_session(seed_gene_for_family(FAMILY), family=FAMILY, adapter=adapter,
                                  rounds=1, max_evaluations=2, seed=0)
    assert validate_report(report) == []
    assert "--sandbox" in seen["command"] and "read-only" in seen["command"], "CLI phải chạy chỉ đọc"
    assert report["adapter"]["provider"] == "codex" and report["adapter"]["kind"] == "cli"
    first = report["rounds"][0]
    assert first["adapter_status"] == "OK"
    assert first["proposals"][0]["outcome"] == "ASSESSED"
    assert first["proposals"][0]["gene"]["girder_catalog_id"] == seen["target"]
    assert first["proposals"][0]["assessment"]["feedback_status"] is not None


def test_cli_adapter_missing_binary_is_unavailable(monkeypatch):
    import bridge_evolution.collaboration.providers as providers

    monkeypatch.setattr(providers, "discover_provider", lambda provider: None)
    adapter = VendorCLIProposer("opencode", timeout_seconds=5)
    result = adapter.propose({"request_id": "a" * 64})
    assert result.status == "UNAVAILABLE"
    with pytest.raises(ProposerError):
        VendorCLIProposer("khong-co")


def test_make_adapter_factory():
    assert isinstance(make_adapter("heuristic", seed=2), HeuristicProposer)
    assert isinstance(make_adapter("cli:codex"), VendorCLIProposer)
    with pytest.raises(ProposerError):
        make_adapter("magic")


# --------------------------------------------------------------------------- loop guards
def test_session_rejects_bad_seed_and_budget():
    bad = dict(seed_gene_for_family(FAMILY), prestress_layout_id="PT-00")
    with pytest.raises(ProposerError):
        run_proposal_session(bad, family=FAMILY, adapter=HeuristicProposer())
    with pytest.raises(ProposerError):
        run_proposal_session(seed_gene_for_family(FAMILY), family=FAMILY, adapter=HeuristicProposer(), rounds=0)
    with pytest.raises(ProposerError):
        run_proposal_session(seed_gene_for_family(FAMILY), family=FAMILY, adapter=object())


def test_duplicate_proposals_are_not_re_evaluated():
    class Repeat:
        kind = "http"
        adapter_id = "fake/repeat"

        def describe(self):
            return {"kind": "http", "adapter_id": self.adapter_id, "model": "m", "endpoint_host": "h",
                    "provider": None, "api_key_env": None, "api_key_present": False,
                    "prompt_template_sha256": None}

        def propose(self, request):
            payload = {"schema_version": "1.0", "request_id": request["request_id"],
                       "proposals": [{"changes": {"girder_count": 6}, "hypothesis": "lặp lại y hệt"},
                                     {"changes": {"girder_count": 6}, "hypothesis": "lặp lại y hệt"}]}
            return adapters_mod.finalize(json.dumps(payload), request["request_id"], 0.0, self.describe())

    report = run_proposal_session(seed_gene_for_family(FAMILY), family=FAMILY, adapter=Repeat(),
                                  rounds=2, max_evaluations=5, seed=0)
    outcomes = [p["outcome"] for r in report["rounds"] for p in r["proposals"]]
    assert outcomes.count("ASSESSED") == 1
    assert outcomes.count("DUPLICATE") >= 1
    assert report["duplicates"] >= 1 and report["evaluations_used"] == 1


# --------------------------------------------------------------------------- script end-to-end
def test_propose_cli_script_end_to_end(tmp_path):
    out = tmp_path / "report.json"
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "propose_cli.py"), "--family", FAMILY, "--adapter", "heuristic",
         "--rounds", "1", "--max-evaluations", "2", "--seed", "5", "--out", str(out)],
        cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
    assert proc.returncode == 0, proc.stderr
    report = json.loads(out.read_text(encoding="utf-8"))
    assert validate_report(report) == []
    assert "phien" in proc.stdout and "bao cao" in proc.stdout
    bad = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "propose_cli.py"), "--family", FAMILY, "--adapter", "magic",
         "--out", str(tmp_path / "x.json")],
        cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    assert bad.returncode == 2 and "LOI HOP DONG" in bad.stderr
