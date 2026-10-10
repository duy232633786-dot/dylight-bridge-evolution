from __future__ import annotations

import hashlib
import json
from copy import deepcopy

import jsonschema
import pytest

import bridge_evolution.creative_shape as creative
from bridge_evolution.creative_shape import (
    CreativeShapeError,
    build_load_path_graph,
    evaluate_genome,
    generate_arch_axis,
    load_creative_domain,
    load_path_connected,
    run_constrained_map_elites,
    validate_candidate,
    validate_creative_domain,
    validate_genome,
)


def base_genome(topology: str = "THROUGH_ARCH") -> dict:
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
def technical_profile(tmp_path, monkeypatch) -> dict:
    # Tệp này chỉ là fixture provenance; test không giả vờ các số dưới đây là
    # giới hạn tiêu chuẩn. Runtime vẫn buộc người gọi thật cung cấp nguồn thật.
    monkeypatch.setattr(creative, "REPO_ROOT", tmp_path)
    evidence_bytes = b'{"purpose":"test-only"}'
    (tmp_path / "evidence.json").write_bytes(evidence_bytes)
    source = "evidence.json"
    digest = hashlib.sha256(evidence_bytes).hexdigest()
    def sourced(value: float) -> dict:
        return {
            "value": value,
            "source_ref": source,
            "expected_source_sha256": digest,
            "clause_id": "TEST-ONLY",
        }
    return {
        "max_abs_slope": sourced(3.0),
        "min_curvature_radius_m": sourced(1.0),
        "max_member_length_m": sourced(100.0),
        "max_member_slenderness": sourced(100.0),
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


def test_domain_is_only_search_space_not_a_design_limit_register():
    domain = load_creative_domain()
    assert domain["claim_ceiling"] == "IDEA"
    assert domain["technical_scope"] == "SEARCH_BOUNDS_ONLY_NOT_DESIGN_LIMITS"
    assert "max_abs_slope" not in domain
    assert domain["topology_values"] == ["DECK_ARCH", "THROUGH_ARCH", "NETWORK_ARCH"]
    justification = domain["not_applicable_justifications"]["CQD-L0-07"]
    assert justification["topologies"] == ["THROUGH_ARCH", "NETWORK_ARCH"]
    assert "không có sàng lọc cơ học F0" in justification["consequence_vi"]


def test_domain_rejects_missing_not_applicable_justification():
    domain = deepcopy(load_creative_domain())
    del domain["not_applicable_justifications"]
    with pytest.raises(CreativeShapeError, match="missing"):
        validate_creative_domain(domain)


def test_special_axis_preserves_supports_monotonic_x_and_exact_rise():
    genome = base_genome()
    ordinary = generate_arch_axis(genome)
    genome["shape_coefficients"] = [0.08, -0.08, 0.06]
    special = generate_arch_axis(genome)

    assert special[0]["x_m"] == 0.0
    assert special[0]["y_m"] == 0.0
    assert special[-1]["x_m"] == genome["span_m"]
    assert special[-1]["y_m"] == 0.0
    assert all(a["x_m"] < b["x_m"] for a, b in zip(special, special[1:]))
    assert max(point["y_m"] for point in special) == pytest.approx(20.0, abs=1e-12)
    assert [point["y_m"] for point in special] != [point["y_m"] for point in ordinary]


@pytest.mark.parametrize("topology", ["DECK_ARCH", "THROUGH_ARCH", "NETWORK_ARCH"])
def test_each_topology_has_a_support_reachable_load_path(topology):
    genome = base_genome(topology)
    graph = build_load_path_graph(genome)
    assert graph["topology"] == topology
    assert load_path_connected(graph)
    if topology == "NETWORK_ARCH":
        assert sum(edge["kind"] == "NETWORK_HANGER" for edge in graph["edges"]) >= genome["panel_count"]


def test_disconnected_deck_node_is_detected():
    genome = base_genome("NETWORK_ARCH")
    graph = build_load_path_graph(genome)
    graph["edges"] = [
        edge for edge in graph["edges"]
        if edge["from"] != "D6" and edge["to"] != "D6"
    ]
    assert not load_path_connected(graph)


def test_deck_chain_alone_cannot_fake_an_arch_load_path():
    graph = build_load_path_graph(base_genome("THROUGH_ARCH"))
    graph["edges"] = [edge for edge in graph["edges"] if edge["kind"] != "HANGER"]
    assert not load_path_connected(graph)


def test_boundary_deck_node_without_transfer_cannot_evade_load_path_check():
    graph = build_load_path_graph(base_genome("THROUGH_ARCH"))
    graph["nodes"].append({
        "id": "D99", "kind": "DECK", "x_m": 0.0, "y_m": 5.0, "support": False,
    })
    graph["edges"].append({
        "id": "E-BOUNDARY-DECK", "from": "D99", "to": "D1", "kind": "DECK",
    })
    assert not load_path_connected(graph)


def test_describe_shape_rejects_genome_graph_topology_mismatch():
    genome = base_genome("DECK_ARCH")
    axis = generate_arch_axis(genome)
    graph = build_load_path_graph(base_genome("THROUGH_ARCH"))
    with pytest.raises(CreativeShapeError, match="Topology"):
        creative.describe_shape(genome, axis, graph)


@pytest.mark.parametrize("topology", ["THROUGH_ARCH", "NETWORK_ARCH"])
def test_tied_arch_endpoints_are_merged_and_every_edge_has_positive_length(topology):
    graph = build_load_path_graph(base_genome(topology))
    nodes = {node["id"]: node for node in graph["nodes"]}
    assert "D0" not in nodes and "D12" not in nodes
    assert nodes["A0"]["kind"] == "ARCH_DECK"
    assert nodes["A12"]["kind"] == "ARCH_DECK"
    assert not any(edge["kind"] == "END_POST" for edge in graph["edges"])
    for edge in graph["edges"]:
        a, b = nodes[edge["from"]], nodes[edge["to"]]
        assert (a["x_m"], a["y_m"]) != (b["x_m"], b["y_m"])


def test_deck_to_deck_edges_cannot_fake_hanger_transfer():
    graph = build_load_path_graph(base_genome("THROUGH_ARCH"))
    graph["edges"] = [edge for edge in graph["edges"] if edge["kind"] != "HANGER"]
    for index in range(1, 11):
        graph["edges"].append({
            "id": f"FAKE{index}", "from": f"D{index}", "to": f"D{index + 1}",
            "kind": "HANGER",
        })
    assert not load_path_connected(graph)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda genome: genome.__setitem__("span_m", float("nan")),
        lambda genome: genome.__setitem__("shape_coefficients", [0.081, 0.0, 0.0]),
        lambda genome: genome.__setitem__("panel_count", 11),
    ],
)
def test_invalid_genomes_fail_before_generation(mutation):
    genome = base_genome()
    mutation(genome)
    with pytest.raises(CreativeShapeError):
        validate_genome(genome)


def test_missing_threshold_is_unknown_and_never_all_known_pass(technical_profile):
    profile = deepcopy(technical_profile)
    del profile["max_abs_slope"]
    candidate = evaluate_genome(base_genome(), profile)
    assert candidate["screening_status"] == "UNKNOWN_INPUT_MISSING"
    assert not candidate["all_known_pass"]
    check = next(item for item in candidate["checks"] if item["check_id"] == "CQD-L0-02")
    assert check["status"] == "UNKNOWN_INPUT_MISSING"


def test_nonexistent_source_is_unknown_not_silently_trusted(technical_profile):
    profile = deepcopy(technical_profile)
    profile["min_curvature_radius_m"]["source_ref"] = "missing-source.json"
    candidate = evaluate_genome(base_genome(), profile)
    assert candidate["screening_status"] == "UNKNOWN_INPUT_MISSING"
    assert any(
        check["check_id"] == "CQD-L0-03" and check["status"] == "UNKNOWN_INPUT_MISSING"
        for check in candidate["checks"]
    )


def test_profile_threshold_requires_an_explicit_clause_id(technical_profile):
    profile = deepcopy(technical_profile)
    del profile["max_abs_slope"]["clause_id"]
    candidate = evaluate_genome(base_genome(), profile)
    check = next(item for item in candidate["checks"] if item["check_id"] == "CQD-L0-02")
    assert check["status"] == "UNKNOWN_INPUT_MISSING"
    assert check["source_clause_id"] is None


def test_profile_fingerprint_changes_when_source_bytes_drift(technical_profile, tmp_path):
    before = evaluate_genome(base_genome(), technical_profile)
    (tmp_path / "evidence.json").write_text('{"purpose":"test-only","revision":2}', encoding="utf-8")
    after = evaluate_genome(base_genome(), technical_profile)
    assert before["profile_sha256"] != after["profile_sha256"]
    assert before["candidate_id"] != after["candidate_id"]
    assert before["checks"][1]["source_sha256"] != after["checks"][1]["source_sha256"]
    assert after["screening_status"] == "UNKNOWN_INPUT_MISSING"


def test_windows_or_traversal_source_paths_are_unknown(technical_profile):
    for invalid in ("docs\\basis.json", "../evidence.json"):
        profile = deepcopy(technical_profile)
        profile["max_abs_slope"]["source_ref"] = invalid
        candidate = evaluate_genome(base_genome(), profile)
        check = next(item for item in candidate["checks"] if item["check_id"] == "CQD-L0-02")
        assert check["status"] == "UNKNOWN_INPUT_MISSING"


def test_non_dict_profile_raises_contract_error_not_attribute_error():
    with pytest.raises(CreativeShapeError, match="technical_profile"):
        evaluate_genome(base_genome(), [])


def test_caller_supplied_domain_cannot_raise_claim_ceiling():
    domain = deepcopy(load_creative_domain())
    domain["claim_ceiling"] = "SCREENED"
    with pytest.raises(CreativeShapeError):
        validate_creative_domain(domain)


def test_proxy_overload_rejects_candidate_and_is_explicitly_only_a_proxy(technical_profile):
    profile = deepcopy(technical_profile)
    profile["allowable_compression_MPa"]["value"] = 0.001
    candidate = evaluate_genome(base_genome("DECK_ARCH"), profile)
    check = next(item for item in candidate["checks"] if item["check_id"] == "CQD-L0-07")
    assert candidate["screening_status"] == "REJECTED"
    assert not candidate["all_known_pass"]
    assert check["status"] == "FAIL"
    assert check["model_kind"] == "SCREENING_PROXY_IDEALISED_PARABOLIC_ARCH"
    assert candidate["claim_level"] == "IDEA"
    assert "feasible" not in candidate
    assert "verified" not in candidate


def test_schema_rejects_feasible_or_verified_backdoors(technical_profile):
    candidate = evaluate_genome(base_genome(), technical_profile)
    for forbidden, value in (("feasible", True), ("verified", True)):
        mutated = deepcopy(candidate)
        mutated[forbidden] = value
        with pytest.raises(CreativeShapeError):
            validate_candidate(mutated)


@pytest.mark.parametrize("tamper", ["axis", "geometry_hash", "domain_hash", "profile_hash", "graph", "check"])
def test_candidate_integrity_rejects_internal_tamper(technical_profile, tamper):
    candidate = evaluate_genome(base_genome("NETWORK_ARCH"), technical_profile)
    mutated = deepcopy(candidate)
    if tamper == "axis":
        mutated["axis_points"][40]["y_m"] += 13.0
    elif tamper == "geometry_hash":
        mutated["geometry_sha256"] = "0" * 64
    elif tamper == "domain_hash":
        mutated["domain_sha256"] = "0" * 64
    elif tamper == "profile_hash":
        mutated["profile_sha256"] = "0" * 64
    elif tamper == "graph":
        mutated["graph"]["edges"] = [
            edge for edge in mutated["graph"]["edges"]
            if edge["kind"] != "NETWORK_HANGER"
        ]
    else:
        mutated["checks"][1]["status"] = "FAIL"
    with pytest.raises(CreativeShapeError):
        validate_candidate(mutated, technical_profile=technical_profile)


def test_candidate_wide_hash_blocks_check_tamper_without_profile(technical_profile):
    candidate = evaluate_genome(base_genome("NETWORK_ARCH"), technical_profile)
    candidate["checks"][0]["message"] = "tampered but schema-shaped"
    with pytest.raises(CreativeShapeError, match="candidate_sha256"):
        validate_candidate(candidate)


def test_not_applicable_cannot_launder_a_failed_clearance_check(technical_profile):
    profile = deepcopy(technical_profile)
    profile["min_through_arch_clearance_m"]["value"] = 8.0
    candidate = evaluate_genome(base_genome("THROUGH_ARCH"), profile)
    assert candidate["screening_status"] == "REJECTED"
    mutated = deepcopy(candidate)
    check = next(item for item in mutated["checks"] if item["check_id"] == "CQD-L0-06")
    check.update({
        "status": "NOT_APPLICABLE",
        "demand": None,
        "limit": None,
        "utilization": None,
        "margin": None,
        "model_kind": "NOT_APPLICABLE_TIED_ARCH_THRUST_PROXY",
        "source_ref": None,
        "source_sha256": None,
        "source_clause_id": None,
        "message": creative._TIED_THRUST_NA_MESSAGE,
    })
    mutated["all_known_pass"] = True
    mutated["screening_status"] = "L0_PASSED"
    payload = deepcopy(mutated)
    payload.pop("candidate_sha256")
    mutated["candidate_sha256"] = creative._sha256(payload)

    with pytest.raises(CreativeShapeError, match="NOT_APPLICABLE"):
        creative._screening_state(mutated["checks"], mutated["genome"])
    schema = json.loads(creative._CANDIDATE_SCHEMA.read_text(encoding="utf-8"))
    assert list(jsonschema.Draft202012Validator(schema).iter_errors(mutated))
    with pytest.raises(CreativeShapeError, match="sai schema"):
        validate_candidate(mutated)


def test_deck_arch_schema_and_runtime_forbid_not_applicable(technical_profile):
    candidate = evaluate_genome(base_genome("DECK_ARCH"), technical_profile)
    mutated = deepcopy(candidate)
    check = next(item for item in mutated["checks"] if item["check_id"] == "CQD-L0-07")
    check.update({
        "status": "NOT_APPLICABLE",
        "demand": None,
        "limit": None,
        "utilization": None,
        "margin": None,
        "model_kind": "NOT_APPLICABLE_TIED_ARCH_THRUST_PROXY",
        "source_ref": None,
        "source_sha256": None,
        "source_clause_id": None,
        "message": creative._TIED_THRUST_NA_MESSAGE,
    })
    with pytest.raises(CreativeShapeError, match="DECK_ARCH"):
        creative._screening_state(mutated["checks"], mutated["genome"])
    schema = json.loads(creative._CANDIDATE_SCHEMA.read_text(encoding="utf-8"))
    assert list(jsonschema.Draft202012Validator(schema).iter_errors(mutated))


def test_clearance_uses_all_interior_axis_points_not_favourable_middle_quarter(technical_profile):
    candidate = evaluate_genome(base_genome("NETWORK_ARCH"), technical_profile)
    expected = min(point["y_m"] for point in candidate["axis_points"][1:-1])
    assert candidate["descriptors"]["min_through_arch_clearance_m"] == pytest.approx(expected)
    assert expected < max(point["y_m"] for point in candidate["axis_points"]) / 4.0


def test_slenderness_screen_covers_network_hangers_not_only_arch_rib(technical_profile):
    profile = deepcopy(technical_profile)
    profile["max_member_slenderness"]["value"] = 10.0
    candidate = evaluate_genome(base_genome("NETWORK_ARCH"), profile)
    check = next(item for item in candidate["checks"] if item["check_id"] == "CQD-L0-05")
    assert check["model_kind"] == "SCREENING_PROXY_GEOMETRIC_L_OVER_DEPTH_ALL_EDGES"
    assert check["demand"] > 10.0
    assert check["status"] == "FAIL"


def test_tied_arch_thrust_proxy_is_explicitly_not_applicable(technical_profile):
    candidate = evaluate_genome(base_genome("THROUGH_ARCH"), technical_profile)
    check = next(item for item in candidate["checks"] if item["check_id"] == "CQD-L0-07")
    assert check["status"] == "NOT_APPLICABLE"
    assert check["model_kind"] == "NOT_APPLICABLE_TIED_ARCH_THRUST_PROXY"
    assert check["source_clause_id"] is None
    assert any("không có sàng lọc cơ học F0" in item for item in candidate["limitations"])


def test_member_slenderness_rejects_unknown_edge_kind_as_contract_error(technical_profile):
    genome = base_genome("THROUGH_ARCH")
    axis = generate_arch_axis(genome)
    graph = build_load_path_graph(genome, axis)
    descriptors = creative.describe_shape(genome, axis, graph)
    graph["edges"].append({
        "id": "E-CABLE", "from": "A1", "to": "A2", "kind": "CABLE",
    })
    with pytest.raises(CreativeShapeError, match="Kind cạnh"):
        creative.technical_checks(genome, graph, descriptors, technical_profile)


def test_weird_shape_cannot_trade_novelty_for_a_failed_technical_check(technical_profile):
    profile = deepcopy(technical_profile)
    profile["max_abs_slope"]["value"] = 0.10
    genome = base_genome("NETWORK_ARCH")
    genome["shape_coefficients"] = [0.08, -0.08, 0.08]
    candidate = evaluate_genome(genome, profile)
    assert candidate["descriptors"]["asymmetry"] > 0.0
    assert candidate["screening_status"] == "REJECTED"
    assert not candidate["all_known_pass"]


def test_map_elites_is_deterministic_diverse_and_archives_only_safe_screening(technical_profile):
    first = run_constrained_map_elites(technical_profile=technical_profile, seed=20260828, iterations=24)
    second = run_constrained_map_elites(technical_profile=technical_profile, seed=20260828, iterations=24)
    assert first == second
    assert first["claim_level"] == "IDEA"
    assert first["statistics"]["occupied_cells"] >= 3
    assert {item["cell"]["topology"] for item in first["archive"]} == {
        "DECK_ARCH", "THROUGH_ARCH", "NETWORK_ARCH"
    }
    for item in first["archive"]:
        candidate = item["candidate"]
        assert candidate["all_known_pass"]
        assert candidate["screening_status"] == "L0_PASSED"
        assert all(check["status"] in {"PASS", "NOT_APPLICABLE"} for check in candidate["checks"])
        assert "feasible" not in candidate
        assert "verified" not in candidate


def test_map_elites_archive_stays_empty_when_every_proxy_fails(technical_profile):
    profile = deepcopy(technical_profile)
    profile["max_abs_slope"]["value"] = 0.0001
    result = run_constrained_map_elites(technical_profile=profile, seed=7, iterations=8)
    assert result["archive"] == []
    assert result["statistics"]["rejected"] == result["statistics"]["evaluated"]
    assert result["statistics"]["unknown"] == 0
