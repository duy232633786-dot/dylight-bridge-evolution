"""BRD-051 — API phòng lab: lớp gọi mỏng, không tự tính, không phát verdict."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import jsonschema
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location("serve_lab", REPO_ROOT / "scripts" / "serve_lab.py")
serve_lab = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = serve_lab
_SPEC.loader.exec_module(serve_lab)

REPORT_SCHEMA = json.loads((REPO_ROOT / "contracts" / "design_loop_report.schema.json").read_text(encoding="utf-8"))


@pytest.fixture
def runs_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(serve_lab, "LAB_RUNS_DIR", tmp_path / "design_loop")
    return tmp_path / "design_loop"


def test_overview_reports_ceiling_gates_and_capabilities():
    ov = serve_lab.api_overview()
    assert ov["claim_ceiling"] == "SCREENED"
    assert [g["gate"] for g in ov["gates"]] == ["G0", "G1", "G2", "G3", "G4", "G5", "G6", "G7"]
    assert ov["gates"][0]["status"] == "BLOCKED"  # site profile chưa có
    assert all(g["status"] == "ABSENT" for g in ov["gates"][3:])
    ids = {c["id"]: c["state"] for c in ov["capabilities"]}
    assert ids["L1_LINE_GIRDER_SOLVER"] == "PRESENT" and ids["SOLVER_MIDAS_CIVIL"] == "ABSENT"
    assert "SERV-001" in ov["rule_inventory"]
    assert ov["site"]["unknown_fields"] and ov["knowledge"]["cards"] >= 20
    assert ov["knowledge"]["by_status"].get("ENGINEER_APPROVED", 0) == 0
    assert ov["oracle_v1"] and ov["oracle_v1"]["domain_size"] == 331776


def test_catalog_exposes_grammars_anchors_and_gold_cases():
    cat = serve_lab.api_catalog()
    assert "super_t_parametric_v2" in cat["grammars"] and len(cat["grammars"]["super_t_parametric_v2"]["domains"]) == 14
    assert cat["anchor_genes"]["super_t_simple_v1"]["girder_catalog_id"] == "ST-1750"
    files = [g["file"] for g in cat["gold_cases"]]
    assert "GC-06_cheap_but_fails.json" in files and all(g["state"]["family"] for g in cat["gold_cases"])


def test_section_studio_anchor_is_l0_clean_and_polygon_matches_section():
    res = serve_lab.api_section({"grammar_id": "super_t_parametric_v2", "gene": {}})
    assert res["schema_errors"] == []
    assert not any(v["severity"] == "HARD" for v in res["violations"])
    assert res["section"]["area_m2"] > 0 and res["objectives"]["relative_cost"] > 0
    assert len(res["polygon"]) >= 12 and res["geometry"]["section_source"] == "PARAMETRIC"
    thin = serve_lab.api_section({"gene": {"web_thickness_mm": 90, "bottom_bulb_width_mm": 250}})
    assert thin["grammar_id"] == "super_t_parametric_v2"
    assert thin["state"]["design_variables"]["web_thickness_mm"] == 90


def test_section_rejects_unknown_grammar_and_ignores_unknown_keys():
    with pytest.raises(serve_lab.LabApiError):
        serve_lab.api_section({"grammar_id": "arch_deck_v1"})
    res = serve_lab.api_section({"gene": {"not_a_variable": 1}})
    assert "not_a_variable" not in res["gene"]


def test_design_loop_api_saves_hashed_report(runs_dir):
    out = serve_lab.api_design_loop({"seed_file": "GC-06_cheap_but_fails.json", "budget": 6,
                                     "policy": {"utilization_target": 1.0, "trim_order": "recent_reject_last"}})
    report = out["report"]
    errors = list(jsonschema.Draft202012Validator(REPORT_SCHEMA).iter_errors(report))
    assert not errors
    assert report["counters"]["evaluator"]["solver_calls"] <= 6
    saved = runs_dir / out["saved_as"]
    assert saved.is_file()
    assert hashlib.sha256(saved.read_bytes()).hexdigest() == out["saved_sha256"]
    runs = serve_lab.api_runs()["runs"]
    assert runs and runs[0]["name"] == out["saved_as"] and runs[0]["seed_case_id"] == report["seed"]["case_id"]
    loaded = serve_lab.api_run(out["saved_as"])["report"]
    assert loaded["report_sha256"] == report["report_sha256"]


def test_design_loop_api_rejects_bad_inputs(runs_dir):
    with pytest.raises(serve_lab.LabApiError):
        serve_lab.api_design_loop({"seed_file": "../secrets.json", "budget": 1})
    with pytest.raises(serve_lab.LabApiError):
        serve_lab.api_design_loop({"seed_file": "GC-01_standard_pass.json", "budget": 10_000})
    with pytest.raises(serve_lab.LabApiError):
        serve_lab.api_design_loop({"seed_file": "GC-01_standard_pass.json", "budget": 2, "policy": {"utilization_target": 1.5}})
    with pytest.raises(serve_lab.LabApiError):
        serve_lab.api_design_loop({"seed_file": "GC-01_standard_pass.json", "budget": 2, "policy": {"evil": 1}})
    with pytest.raises(serve_lab.LabApiError):
        serve_lab.api_run("../../pyproject.toml")


def test_design_loop_from_gene_uses_lab_seed_action(runs_dir):
    cat = serve_lab.api_catalog()
    gene = cat["anchor_genes"]["super_t_simple_v1"]
    out = serve_lab.api_design_loop({"gene": gene, "grammar_id": "super_t_simple_v1", "budget": 2})
    assert out["report"]["seed"]["gene"] == gene


def test_evaluate_api_returns_verifier_result_and_repairs():
    state = json.loads((REPO_ROOT / "gold_cases" / "cases" / "GC-06_cheap_but_fails.json").read_text(encoding="utf-8"))
    out = serve_lab.api_evaluate({"state": state})
    assert out["result"]["status"] == "SUCCESS" and out["result"]["feasible"] is False
    assert out["repairs"][0]["rule_id"] == "SERV-001"
    with pytest.raises(serve_lab.LabApiError):
        serve_lab.api_evaluate({"state": "not a dict"})


def test_creative_search_uses_unsourced_lab_profile_and_stays_idea():
    out = serve_lab.api_creative_search({"seed": 3, "iterations": 6})
    assert out["claim_level"] == "IDEA"
    assert out["profile"]["source_ref"] == "dashboard/lab_creative_profile.json"
    expected = hashlib.sha256((REPO_ROOT / "dashboard" / "lab_creative_profile.json").read_bytes()).hexdigest()
    assert out["profile"]["sha256"] == expected
    assert out["archive_size"] >= 1
    for cand in out["candidates"]:
        assert cand["claim_level"] == "IDEA" and cand["screening_status"]
        assert cand["graph"]["nodes"] and cand["genome"]["topology"] in {"DECK_ARCH", "THROUGH_ARCH", "NETWORK_ARCH"}
        assert "feasible" not in cand and "design_pass" not in cand
    profile, meta = serve_lab.lab_technical_profile()
    assert all(v["clause_id"].startswith("LAB-DEFAULT-UNSOURCED-") for v in profile.values())
    with pytest.raises(serve_lab.LabApiError):
        serve_lab.api_creative_search({"seed": 1, "iterations": 10**6})


def test_knowledge_and_lab_endpoints():
    cards = serve_lab.api_cards()["cards"]
    assert any(c["card_id"] == "KC-001" for c in cards)
    hits = serve_lab.api_knowledge_query({"rules": "SERV-001"})["hits"]
    assert hits and hits[0]["card"]["card_id"] == "KC-001"
    live = serve_lab.get_live_data()
    assert "BRD-050" in live["tasks"] and isinstance(live["handoffs"], list)
    status = serve_lab.api_lab_status()
    assert "tasks" in status and "valid" in status
    ob = serve_lab.api_obsidian()
    assert "available" in ob
