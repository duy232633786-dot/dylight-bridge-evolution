from __future__ import annotations

import hashlib
import json
from copy import deepcopy

import pytest

import bridge_evolution.creative_frame_adapter as adapter
import bridge_evolution.creative_shape as creative
import bridge_evolution.frame_f1 as frame_f1
from bridge_evolution.creative_frame_adapter import (
    CreativeFrameAdapterError,
    analyze_creative_candidate,
    load_adapter_basis,
    validate_creative_frame_analysis,
    validate_structural_profile,
)


EDGE_KINDS = (
    "ARCH_RIB",
    "DECK",
    "SPANDREL",
    "END_POST",
    "HANGER",
    "NETWORK_HANGER",
)


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _base_genome(topology: str = "THROUGH_ARCH") -> dict:
    return {
        "topology": topology,
        "span_m": 100.0,
        "rise_ratio": 0.20,
        "panel_count": 12,
        "rib_count": 2,
        "rib_depth_m": 2.0,
        "deck_clearance_m": 5.0,
        "shape_coefficients": [0.0, 0.0, 0.0],
    }


@pytest.fixture
def adapter_environment(tmp_path, monkeypatch) -> dict:
    monkeypatch.setattr(creative, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(adapter, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(frame_f1, "REPO_ROOT", tmp_path)

    technical_bytes = b'{"kind":"test-only-creative-screen"}'
    structural_bytes = b'{"kind":"test-only-structural-input"}'
    (tmp_path / "technical-evidence.json").write_bytes(technical_bytes)
    (tmp_path / "structural-evidence.json").write_bytes(structural_bytes)
    technical_digest = hashlib.sha256(technical_bytes).hexdigest()
    structural_digest = hashlib.sha256(structural_bytes).hexdigest()

    def sourced(value: float) -> dict:
        return {
            "value": value,
            "source_ref": "technical-evidence.json",
            "expected_source_sha256": technical_digest,
            "clause_id": "TEST-ONLY-CREATIVE",
        }

    technical_profile = {
        "max_abs_slope": sourced(3.0),
        "min_curvature_radius_m": sourced(1.0),
        "max_member_length_m": sourced(100.0),
        "max_member_slenderness": sourced(200.0),
        "deck_member_depth_m": sourced(2.0),
        "spandrel_member_depth_m": sourced(1.0),
        "end_post_member_depth_m": sourced(1.0),
        "hanger_member_depth_m": sourced(0.5),
        "min_deck_arch_separation_m": sourced(0.5),
        "min_through_arch_clearance_m": sourced(0.5),
        "distributed_load_kN_m": sourced(20.0),
        "rib_area_m2": sourced(2.0),
        "allowable_compression_MPa": sourced(100.0),
    }
    return {
        "root": tmp_path,
        "technical_profile": technical_profile,
        "structural_digest": structural_digest,
    }


def _candidate(environment: dict, topology: str = "THROUGH_ARCH", *,
               technical_profile: dict | None = None) -> dict:
    profile = technical_profile or environment["technical_profile"]
    return creative.evaluate_genome(_base_genome(topology), profile)


def _structural_profile(environment: dict, candidate: dict) -> dict:
    digest = environment["structural_digest"]

    def material() -> dict:
        return {
            "elastic_modulus_GPa": 200.0,
            "source_ref": "structural-evidence.json",
            "expected_source_sha256": digest,
            "clause_id": "TEST-ONLY-E",
        }

    def section() -> dict:
        return {
            "area_m2": 5.0,
            "inertia_m4": 100.0,
            "source_ref": "structural-evidence.json",
            "expected_source_sha256": digest,
            "clause_id": "TEST-ONLY-A-I",
        }

    return {
        "schema_version": "1.0",
        "profile_id": "CFP-TEST",
        "candidate_id": candidate["candidate_id"],
        "candidate_profile_sha256": candidate["profile_sha256"],
        "support_policy": "LEFT_PIN_RIGHT_VERTICAL_ROLLER",
        "edge_properties": {
            kind: {"material": material(), "section": section()}
            for kind in EDGE_KINDS
        },
        "deck_line_load": {
            "q_kN_m": 1.0,
            "direction": "GLOBAL_NEGATIVE_Y",
            "source_ref": "structural-evidence.json",
            "expected_source_sha256": digest,
            "clause_id": "TEST-ONLY-DECK-UDL",
        },
    }


def _rehash_candidate(candidate: dict) -> None:
    candidate["geometry_sha256"] = _canonical_sha256({
        "axis_points": candidate["axis_points"],
        "graph": candidate["graph"],
    })
    payload = deepcopy(candidate)
    payload.pop("candidate_sha256", None)
    candidate["candidate_sha256"] = _canonical_sha256(payload)


def _rehash_analysis(analysis: dict) -> None:
    payload = deepcopy(analysis)
    payload.pop("analysis_sha256", None)
    analysis["analysis_sha256"] = _canonical_sha256(payload)


@pytest.mark.parametrize("topology", ["DECK_ARCH", "THROUGH_ARCH", "NETWORK_ARCH"])
def test_each_topology_maps_explicitly_and_solves_without_a_design_verdict(
    adapter_environment, topology,
):
    candidate = _candidate(adapter_environment, topology)
    profile = _structural_profile(adapter_environment, candidate)
    analysis = analyze_creative_candidate(
        candidate,
        technical_profile=adapter_environment["technical_profile"],
        structural_profile=profile,
    )

    expected_mapping = {
        "ARCH_RIB": "FRAME_2D",
        "DECK": "FRAME_2D",
        "SPANDREL": "FRAME_2D",
        "END_POST": "FRAME_2D",
        "HANGER": "TRUSS_2D",
        "NETWORK_HANGER": "TRUSS_2D",
    }
    graph_edges = {edge["id"]: edge for edge in candidate["graph"]["edges"]}
    model_elements = {element["id"]: element for element in analysis["frame_model"]["elements"]}
    assert set(model_elements) == set(graph_edges)
    for edge_id, edge in graph_edges.items():
        assert model_elements[edge_id]["kind"] == expected_mapping[edge["kind"]]

    # Fixture rất cứng và tải nhỏ có chủ ý: cả ba topology chuẩn phải giải được.
    # Điều này chỉ kiểm đường tích hợp, không nâng CONVERGED thành verdict thiết kế.
    assert analysis["status"] == "CONVERGED"
    assert analysis["claim_level"] == "IDEA"
    assert analysis["design_verdict_authority"] == "NONE"
    assert not ({"feasible", "verified", "design_pass"} & set(analysis))
    assert any("CONVERGED" in item and "not a design verdict" in item
               for item in analysis["limitations"])
    validate_creative_frame_analysis(analysis)


@pytest.mark.parametrize("topology", ["THROUGH_ARCH", "NETWORK_ARCH"])
def test_tied_arch_uses_merged_feet_and_has_no_zero_length_member(
    adapter_environment, topology,
):
    candidate = _candidate(adapter_environment, topology)
    analysis = analyze_creative_candidate(
        candidate,
        technical_profile=adapter_environment["technical_profile"],
        structural_profile=_structural_profile(adapter_environment, candidate),
    )
    nodes = {node["id"]: node for node in analysis["frame_model"]["nodes"]}
    assert "D0" not in nodes and "D12" not in nodes
    assert nodes["A0"] == {"id": "A0", "x_m": 0.0, "y_m": 0.0}
    assert nodes["A12"] == {"id": "A12", "x_m": 100.0, "y_m": 0.0}
    assert not any(edge["kind"] == "END_POST" for edge in candidate["graph"]["edges"])
    for element in analysis["frame_model"]["elements"]:
        first, second = nodes[element["node_i"]], nodes[element["node_j"]]
        assert (first["x_m"], first["y_m"]) != (second["x_m"], second["y_m"])


def test_supports_are_exactly_left_pin_and_right_vertical_roller(adapter_environment):
    candidate = _candidate(adapter_environment)
    analysis = analyze_creative_candidate(
        candidate,
        technical_profile=adapter_environment["technical_profile"],
        structural_profile=_structural_profile(adapter_environment, candidate),
    )
    assert analysis["frame_model"]["supports"] == [
        {"node_id": "A0", "ux": True, "uy": True, "rz": False},
        {"node_id": "A12", "ux": False, "uy": True, "rz": False},
    ]


def test_tributary_load_conversion_conserves_q_times_deck_length(adapter_environment):
    candidate = _candidate(adapter_environment, "NETWORK_ARCH")
    analysis = analyze_creative_candidate(
        candidate,
        technical_profile=adapter_environment["technical_profile"],
        structural_profile=_structural_profile(adapter_environment, candidate),
    )
    conservation = analysis["load_conservation"]
    loads = analysis["frame_model"]["load_cases"][0]["nodal_loads"]
    assert conservation["status"] == "PASS"
    assert conservation["deck_length_m"] == pytest.approx(100.0)
    assert conservation["expected_total_vertical_load_kN"] == pytest.approx(100.0)
    assert conservation["actual_total_vertical_load_kN"] == pytest.approx(100.0)
    assert -sum(load["fy_kN"] for load in loads) == pytest.approx(100.0)
    assert sum(
        item["tributary_length_m"]
        for item in conservation["tributary_length_by_node_m"]
    ) == pytest.approx(100.0)


def test_output_is_deterministic_and_manifest_is_fully_bound(adapter_environment):
    candidate = _candidate(adapter_environment)
    profile = _structural_profile(adapter_environment, candidate)
    kwargs = {
        "technical_profile": adapter_environment["technical_profile"],
        "structural_profile": profile,
    }
    first = analyze_creative_candidate(candidate, **kwargs)
    second = analyze_creative_candidate(candidate, **kwargs)
    assert first == second
    assert first["manifest"]["candidate_id"] == candidate["candidate_id"]
    assert first["manifest"]["candidate_sha256"] == candidate["candidate_sha256"]
    assert first["manifest"]["geometry_sha256"] == candidate["geometry_sha256"]
    assert first["manifest"]["candidate_profile_sha256"] == candidate["profile_sha256"]
    assert first["manifest"]["model_sha256"] == first["frame_result"]["model_sha256"]
    assert first["manifest"]["frame_result_sha256"] == first["frame_result"]["result_sha256"]
    assert first["adapter_source_sha256"] == _canonical_sha256(
        first["adapter_source_digests"])


@pytest.mark.parametrize("screen_state", ["REJECTED", "UNKNOWN_INPUT_MISSING"])
def test_nonpassing_f0_candidate_is_blocked_before_solver(
    adapter_environment, monkeypatch, screen_state,
):
    profile = deepcopy(adapter_environment["technical_profile"])
    if screen_state == "REJECTED":
        profile["max_abs_slope"]["value"] = 0.01
    else:
        del profile["max_abs_slope"]
    candidate = _candidate(adapter_environment, technical_profile=profile)
    assert candidate["screening_status"] == screen_state
    called = False

    def forbidden_solver(_model):
        nonlocal called
        called = True
        raise AssertionError("solver must not run")

    monkeypatch.setattr(frame_f1, "analyze_frame_model", forbidden_solver)
    with pytest.raises(CreativeFrameAdapterError, match="L0_PASSED"):
        analyze_creative_candidate(
            candidate,
            technical_profile=profile,
            structural_profile=_structural_profile(adapter_environment, candidate),
        )
    assert not called


@pytest.mark.parametrize("tamper", ["coordinate", "disconnected", "support", "unknown_kind"])
def test_tampered_candidate_graph_is_blocked_before_solver(
    adapter_environment, monkeypatch, tamper,
):
    candidate = _candidate(adapter_environment, "NETWORK_ARCH")
    mutated = deepcopy(candidate)
    if tamper == "coordinate":
        mutated["graph"]["nodes"][1]["x_m"] = mutated["graph"]["nodes"][0]["x_m"]
        mutated["graph"]["nodes"][1]["y_m"] = mutated["graph"]["nodes"][0]["y_m"]
    elif tamper == "disconnected":
        mutated["graph"]["edges"] = [
            edge for edge in mutated["graph"]["edges"]
            if edge["from"] != "D6" and edge["to"] != "D6"
        ]
    elif tamper == "support":
        mutated["graph"]["nodes"][0]["support"] = False
    else:
        mutated["graph"]["edges"][0]["kind"] = "MAGIC_CABLE"
    _rehash_candidate(mutated)
    called = False

    def forbidden_solver(_model):
        nonlocal called
        called = True
        raise AssertionError("solver must not run")

    monkeypatch.setattr(frame_f1, "analyze_frame_model", forbidden_solver)
    with pytest.raises(CreativeFrameAdapterError, match="Candidate không tái lập"):
        analyze_creative_candidate(
            mutated,
            technical_profile=adapter_environment["technical_profile"],
            structural_profile=_structural_profile(adapter_environment, mutated),
        )
    assert not called


@pytest.mark.parametrize("missing", ["kind", "elastic_modulus", "area", "inertia", "clause"])
def test_structural_profile_must_supply_all_kinds_values_and_clauses(
    adapter_environment, missing,
):
    candidate = _candidate(adapter_environment)
    profile = _structural_profile(adapter_environment, candidate)
    if missing == "kind":
        del profile["edge_properties"]["NETWORK_HANGER"]
    elif missing == "elastic_modulus":
        del profile["edge_properties"]["ARCH_RIB"]["material"]["elastic_modulus_GPa"]
    elif missing == "area":
        del profile["edge_properties"]["DECK"]["section"]["area_m2"]
    elif missing == "inertia":
        del profile["edge_properties"]["HANGER"]["section"]["inertia_m4"]
    else:
        del profile["deck_line_load"]["clause_id"]
    with pytest.raises(CreativeFrameAdapterError, match="sai schema"):
        validate_structural_profile(profile, candidate)


def test_profile_binding_and_support_policy_are_fail_closed(adapter_environment):
    candidate = _candidate(adapter_environment)
    for field, value, message in (
        ("candidate_id", "CS-0000000000000000", "candidate_id"),
        ("candidate_profile_sha256", "0" * 64, "profile hash"),
        ("support_policy", "TWO_FIXED_SUPPORTS", "sai schema"),
    ):
        profile = _structural_profile(adapter_environment, candidate)
        profile[field] = value
        with pytest.raises(CreativeFrameAdapterError, match=message):
            validate_structural_profile(profile, candidate)


def test_structural_source_drift_is_blocked_before_solver(
    adapter_environment, monkeypatch,
):
    candidate = _candidate(adapter_environment)
    profile = _structural_profile(adapter_environment, candidate)
    (adapter_environment["root"] / "structural-evidence.json").write_bytes(b"drift")
    called = False

    def forbidden_solver(_model):
        nonlocal called
        called = True
        raise AssertionError("solver must not run")

    monkeypatch.setattr(frame_f1, "analyze_frame_model", forbidden_solver)
    with pytest.raises(CreativeFrameAdapterError, match="source drift"):
        analyze_creative_candidate(
            candidate,
            technical_profile=adapter_environment["technical_profile"],
            structural_profile=profile,
        )
    assert not called


@pytest.mark.parametrize("forbidden", ["feasible", "verified", "design_pass"])
def test_analysis_schema_rejects_design_verdict_backdoors(
    adapter_environment, forbidden,
):
    candidate = _candidate(adapter_environment)
    analysis = analyze_creative_candidate(
        candidate,
        technical_profile=adapter_environment["technical_profile"],
        structural_profile=_structural_profile(adapter_environment, candidate),
    )
    analysis[forbidden] = True
    _rehash_analysis(analysis)
    with pytest.raises(CreativeFrameAdapterError, match="sai schema"):
        validate_creative_frame_analysis(analysis)


@pytest.mark.parametrize("tamper", ["manifest", "load", "model", "result"])
def test_recalculated_outer_hash_cannot_hide_semantic_analysis_tamper(
    adapter_environment, tamper,
):
    candidate = _candidate(adapter_environment)
    analysis = analyze_creative_candidate(
        candidate,
        technical_profile=adapter_environment["technical_profile"],
        structural_profile=_structural_profile(adapter_environment, candidate),
    )
    if tamper == "manifest":
        analysis["manifest"]["model_sha256"] = "0" * 64
    elif tamper == "load":
        analysis["load_conservation"]["actual_total_vertical_load_kN"] += 1.0
    elif tamper == "model":
        analysis["frame_model"]["supports"][1]["ux"] = True
    else:
        analysis["frame_result"]["status"] = "NUMERICAL_FAILURE"
        result_payload = deepcopy(analysis["frame_result"])
        result_payload.pop("result_sha256")
        analysis["frame_result"]["result_sha256"] = _canonical_sha256(result_payload)
    _rehash_analysis(analysis)
    with pytest.raises(CreativeFrameAdapterError):
        validate_creative_frame_analysis(analysis)


def test_basis_rejects_a_same_named_but_different_support_policy(
    adapter_environment, tmp_path, monkeypatch,
):
    basis = json.loads(adapter._BASIS_PATH.read_text(encoding="utf-8"))
    basis["support_policy"]["right"]["ux"] = True
    corrupt_basis = tmp_path / "corrupt-basis.json"
    corrupt_basis.write_text(json.dumps(basis), encoding="utf-8")
    monkeypatch.setattr(adapter, "_BASIS_PATH", corrupt_basis)
    with pytest.raises(CreativeFrameAdapterError, match="support policy"):
        load_adapter_basis()


def test_basis_rejects_an_unimplemented_load_transfer_method(
    adapter_environment, tmp_path, monkeypatch,
):
    basis = json.loads(adapter._BASIS_PATH.read_text(encoding="utf-8"))
    basis["load_transfer"]["method"] = "EQUAL_SPLIT_BY_NODE_COUNT"
    corrupt_basis = tmp_path / "corrupt-load-basis.json"
    corrupt_basis.write_text(json.dumps(basis), encoding="utf-8")
    monkeypatch.setattr(adapter, "_BASIS_PATH", corrupt_basis)
    with pytest.raises(CreativeFrameAdapterError, match="method"):
        load_adapter_basis()
