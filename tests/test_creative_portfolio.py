from __future__ import annotations

import hashlib
import json
from copy import deepcopy

import pytest

from bridge_evolution import (
    arch_action_f1,
    creative_frame_adapter,
    creative_portfolio,
    creative_shape,
    frame_f1,
    funicular_reference,
)
from bridge_evolution.creative_portfolio import (
    CreativePortfolioError,
    run_creative_portfolio,
    validate_creative_portfolio,
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
    return hashlib.sha256(json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")).hexdigest()


def _reseal(study: dict) -> None:
    payload = deepcopy(study)
    payload.pop("study_sha256", None)
    study["study_sha256"] = _canonical_sha256(payload)


def _walk_keys(value: object):
    if isinstance(value, dict):
        yield from value
        for child in value.values():
            yield from _walk_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_keys(child)


@pytest.fixture
def portfolio_environment(tmp_path, monkeypatch) -> dict:
    # Các module source/basis vẫn neo vào __file__ thật. Chỉ evidence do caller
    # cung cấp được chuyển vào sandbox tạm để kiểm source-ref contract.
    monkeypatch.setattr(creative_shape, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(creative_frame_adapter, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(frame_f1, "REPO_ROOT", tmp_path)

    technical_bytes = b'{"kind":"portfolio-technical-test"}'
    structural_bytes = b'{"kind":"portfolio-structural-test"}'
    (tmp_path / "technical-evidence.json").write_bytes(technical_bytes)
    (tmp_path / "structural-evidence.json").write_bytes(structural_bytes)
    technical_digest = hashlib.sha256(technical_bytes).hexdigest()
    structural_digest = hashlib.sha256(structural_bytes).hexdigest()

    def sourced(value: float) -> dict:
        return {
            "value": value,
            "source_ref": "technical-evidence.json",
            "expected_source_sha256": technical_digest,
            "clause_id": "TEST-ONLY-PORTFOLIO",
        }

    technical_profile = {
        "max_abs_slope": sourced(3.0),
        "min_curvature_radius_m": sourced(0.5),
        "max_member_length_m": sourced(120.0),
        "max_member_slenderness": sourced(250.0),
        "deck_member_depth_m": sourced(2.0),
        "spandrel_member_depth_m": sourced(1.0),
        "end_post_member_depth_m": sourced(1.0),
        "hanger_member_depth_m": sourced(0.5),
        "min_deck_arch_separation_m": sourced(0.25),
        "min_through_arch_clearance_m": sourced(0.25),
        "distributed_load_kN_m": sourced(20.0),
        "rib_area_m2": sourced(3.0),
        "allowable_compression_MPa": sourced(150.0),
    }

    def structural_profile(candidate: dict) -> dict:
        def material() -> dict:
            return {
                "elastic_modulus_GPa": 200.0,
                "source_ref": "structural-evidence.json",
                "expected_source_sha256": structural_digest,
                "clause_id": "TEST-ONLY-E",
            }

        def section() -> dict:
            return {
                "area_m2": 6.0,
                "inertia_m4": 150.0,
                "source_ref": "structural-evidence.json",
                "expected_source_sha256": structural_digest,
                "clause_id": "TEST-ONLY-A-I",
            }

        return {
            "schema_version": "1.0",
            "profile_id": "CFP-PORTFOLIO-TEST",
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
                "expected_source_sha256": structural_digest,
                "clause_id": "TEST-ONLY-DECK-UDL",
            },
        }

    return {
        "technical_profile": technical_profile,
        "structural_profile": structural_profile,
    }


@pytest.fixture
def screened_study(portfolio_environment) -> dict:
    result = run_creative_portfolio(
        technical_profile=portfolio_environment["technical_profile"],
        structural_profile_factory=portfolio_environment["structural_profile"],
        seed=31,
        iterations=0,
        max_candidates=1,
        robustness_samples=3,
        perturbation_fraction=0.002,
    )
    assert result["archive"], result["blocked_candidates"]
    return result


def test_portfolio_is_deterministic_diverse_safe_and_reproducible(
    portfolio_environment, screened_study,
):
    repeated = run_creative_portfolio(
        technical_profile=portfolio_environment["technical_profile"],
        structural_profile_factory=portfolio_environment["structural_profile"],
        seed=31,
        iterations=0,
        max_candidates=1,
        robustness_samples=3,
        perturbation_fraction=0.002,
    )
    assert repeated == screened_study
    validate_creative_portfolio(screened_study)
    assert screened_study["claim_level"] == "IDEA"
    assert screened_study["design_verdict_authority"] == "NONE"
    assert len(screened_study["structural_comparison_sha256"]) == 64
    assert not ({"feasible", "verified", "design_pass"} & set(_walk_keys(screened_study)))
    assert screened_study["statistics"] == {
        "map_elites_evaluated": 3,
        "map_elites_occupied_cells": 3,
        "selected_for_chain": 1,
        "research_screened": 1,
        "blocked": 0,
        "pareto_front": 1,
    }
    entry = screened_study["archive"][0]
    assert entry["pareto_rank"] == 0
    assert entry["pareto_front"] is True
    assert len(entry["robustness_samples"]) == 3
    assert len({s["input_digest"] for s in entry["robustness_samples"]}) == 3
    assert all(s["status"] == "RESEARCH_SCREENED" for s in entry["robustness_samples"])


def test_end_to_end_keeps_three_topologies_under_one_comparison_profile(
    portfolio_environment,
):
    result = run_creative_portfolio(
        technical_profile=portfolio_environment["technical_profile"],
        structural_profile_factory=portfolio_environment["structural_profile"],
        seed=31,
        iterations=6,
        max_candidates=6,
        robustness_samples=3,
        perturbation_fraction=0.002,
    )
    validate_creative_portfolio(result)
    assert len(result["archive"]) >= 3, result["blocked_candidates"]
    assert len({item["topology"] for item in result["archive"]}) >= 2
    assert result["statistics"]["selected_for_chain"] >= 3
    assert result["structural_comparison_sha256"] is not None
    assert all(item["pareto_rank"] >= 0 for item in result["archive"])


def test_pareto_ranking_builds_multiple_fronts():
    def entry(vector):
        return {
            "robust_metrics": {
                "worst_axis_rms_deviation_ratio": vector[0],
                "worst_bending_proxy_max_abs_ratio": vector[1],
                "worst_translation_ratio": vector[2],
                "inverse_minimum_l0_margin": vector[3],
            },
            "pareto_rank": 0,
            "pareto_front": False,
        }

    entries = [
        entry((1.0, 1.0, 1.0, 1.0)),
        entry((2.0, 2.0, 2.0, 2.0)),
        entry((0.5, 3.0, 1.0, 1.0)),
        entry((4.0, 4.0, 4.0, 4.0)),
    ]
    creative_portfolio._assign_pareto_ranks(entries)
    assert [item["pareto_rank"] for item in entries] == [0, 1, 0, 2]
    assert [item["pareto_front"] for item in entries] == [True, False, True, False]


def test_topology_round_robin_and_quality_tie_break_are_deterministic():
    def item(topology, quality, candidate_id):
        return {
            "quality_score": quality,
            "candidate": {
                "candidate_id": candidate_id,
                "genome": {"topology": topology},
            },
        }

    search = {"archive": [
        item("THROUGH_ARCH", 2.0, "CS-through-low"),
        item("DECK_ARCH", 3.0, "CS-deck-high"),
        item("NETWORK_ARCH", 3.0, "CS-network-z"),
        item("DECK_ARCH", 1.0, "CS-deck-low"),
        item("NETWORK_ARCH", 3.0, "CS-network-a"),
        item("THROUGH_ARCH", 4.0, "CS-through-high"),
    ]}
    selected = creative_portfolio._selected_archive_items(search, 5)
    assert [value["candidate"]["candidate_id"] for value in selected] == [
        "CS-deck-high",
        "CS-network-a",
        "CS-through-high",
        "CS-deck-low",
        "CS-network-z",
    ]


@pytest.mark.parametrize("target", ["metric", "lineage", "sample", "verdict"])
def test_tamper_and_reseal_cannot_change_screened_evidence(screened_study, target):
    tampered = deepcopy(screened_study)
    entry = tampered["archive"][0]
    if target == "metric":
        entry["robust_metrics"]["worst_translation_ratio"] *= 0.1
    elif target == "lineage":
        entry["lineage"]["frame_result_sha256"] = "0" * 64
    elif target == "sample":
        entry["robustness_samples"][0]["sample_seed"] += 1
    else:
        entry["base_reference"]["feasible"] = True
    _reseal(tampered)
    with pytest.raises(CreativePortfolioError):
        validate_creative_portfolio(tampered)


def test_sample_replay_is_rejected_even_after_outer_hash_is_resealed(screened_study):
    tampered = deepcopy(screened_study)
    samples = tampered["archive"][0]["robustness_samples"]
    samples[1] = deepcopy(samples[0])
    _reseal(tampered)
    with pytest.raises(CreativePortfolioError, match="sample 1|replay|duplicate"):
        validate_creative_portfolio(tampered)


def test_profile_factory_failure_is_a_blocked_record_not_a_false_success(
    portfolio_environment,
):
    def broken_factory(_candidate):
        raise RuntimeError("không có tiết diện đã phê duyệt")

    result = run_creative_portfolio(
        technical_profile=portfolio_environment["technical_profile"],
        structural_profile_factory=broken_factory,
        seed=7,
        iterations=0,
        max_candidates=1,
        robustness_samples=3,
        perturbation_fraction=0.002,
    )
    assert result["archive"] == []
    assert result["statistics"]["blocked"] == 1
    blocker = result["blocked_candidates"][0]
    assert blocker["stage"] == "BASE_CHAIN"
    assert blocker["blockers"][0]["code"] == "CP-PROFILE-001"
    validate_creative_portfolio(result)


def test_a_failed_perturbation_blocks_the_whole_parent(portfolio_environment):
    valid_factory = portfolio_environment["structural_profile"]

    def baseline_only(candidate):
        if any(abs(float(value)) > 0.0 for value in candidate["genome"]["shape_coefficients"]):
            raise RuntimeError("perturbed geometry chưa có structural profile")
        return valid_factory(candidate)

    result = run_creative_portfolio(
        technical_profile=portfolio_environment["technical_profile"],
        structural_profile_factory=baseline_only,
        seed=11,
        iterations=0,
        max_candidates=1,
        robustness_samples=3,
        perturbation_fraction=0.002,
    )
    assert result["archive"] == []
    assert result["blocked_candidates"][0]["stage"] == "ROBUSTNESS"
    assert result["blocked_candidates"][0]["blockers"][0]["code"] == "CP-PERTURB-002"
    validate_creative_portfolio(result)


@pytest.mark.parametrize(
    "overrides",
    [
        {"seed": True},
        {"iterations": -1},
        {"max_candidates": 0},
        {"robustness_samples": 2},
        {"perturbation_fraction": 0.000999},
        {"perturbation_fraction": float("nan")},
        {"perturbation_fraction": 0.11},
    ],
)
def test_invalid_run_policy_is_fail_closed(portfolio_environment, overrides):
    kwargs = {
        "technical_profile": portfolio_environment["technical_profile"],
        "structural_profile_factory": portfolio_environment["structural_profile"],
        "seed": 3,
        "iterations": 0,
        "max_candidates": 1,
        "robustness_samples": 3,
        "perturbation_fraction": 0.002,
    }
    kwargs.update(overrides)
    with pytest.raises(CreativePortfolioError):
        run_creative_portfolio(**kwargs)


def test_upstream_failure_is_kept_as_blocker(portfolio_environment, monkeypatch):
    def fail_action(_analysis):
        raise arch_action_f1.ArchActionF1Error("cơ chế không xác định")

    monkeypatch.setattr(arch_action_f1, "run_arch_action_study", fail_action)
    result = run_creative_portfolio(
        technical_profile=portfolio_environment["technical_profile"],
        structural_profile_factory=portfolio_environment["structural_profile"],
        seed=9,
        iterations=0,
        max_candidates=1,
        robustness_samples=3,
        perturbation_fraction=0.002,
    )
    assert result["archive"] == []
    assert result["blocked_candidates"][0]["blockers"][0]["code"] == "CP-ACTION-001"


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        ("analysis_status", "CP-F1-001"),
        ("case_status", "CP-F1-002"),
        ("check_status", "CP-F1-003"),
    ],
)
def test_f1_stage_guards_are_reachable_before_downstream_reference(
    portfolio_environment, screened_study, monkeypatch, mutation, expected_code,
):
    analysis = deepcopy(
        screened_study["archive"][0]["base_reference"]["parent_study"]
        ["parent_analysis"]
    )
    if mutation == "analysis_status":
        analysis["status"] = "MECHANISM"
    elif mutation == "case_status":
        analysis["frame_result"]["load_case_results"][0]["status"] = "MECHANISM"
    else:
        analysis["frame_result"]["load_case_results"][0]["checks"][0]["status"] = "FAIL"
    monkeypatch.setattr(
        creative_frame_adapter, "analyze_creative_candidate", lambda *args, **kwargs: analysis
    )
    monkeypatch.setattr(
        creative_frame_adapter, "validate_creative_frame_analysis", lambda _value: None
    )
    result = run_creative_portfolio(
        technical_profile=portfolio_environment["technical_profile"],
        structural_profile_factory=portfolio_environment["structural_profile"],
        seed=31,
        iterations=0,
        max_candidates=1,
        robustness_samples=3,
        perturbation_fraction=0.002,
    )
    blocked = result["blocked_candidates"][0]
    assert expected_code in {item["code"] for item in blocked["blockers"]}
    assert blocked["evidence"]["evidence_kind"] == "FRAME_ANALYSIS"


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        ("study_status", "CP-ACTION-002"),
        ("diagnostic_status", "CP-ACTION-003"),
    ],
)
def test_arch_action_stage_guards_are_reachable(
    portfolio_environment, screened_study, monkeypatch, mutation, expected_code,
):
    action = deepcopy(screened_study["archive"][0]["base_reference"]["parent_study"])
    if mutation == "study_status":
        action["status"] = "EXPECTED_ACTION_NOT_DETECTED"
    else:
        action["diagnostics"][0]["action_status"] = "EXPECTED_ACTION_NOT_DETECTED"
    monkeypatch.setattr(arch_action_f1, "run_arch_action_study", lambda _analysis: action)
    monkeypatch.setattr(arch_action_f1, "validate_arch_action_study", lambda _value: None)
    result = run_creative_portfolio(
        technical_profile=portfolio_environment["technical_profile"],
        structural_profile_factory=portfolio_environment["structural_profile"],
        seed=31,
        iterations=0,
        max_candidates=1,
        robustness_samples=3,
        perturbation_fraction=0.002,
    )
    blocked = result["blocked_candidates"][0]
    assert expected_code in {item["code"] for item in blocked["blockers"]}
    assert blocked["evidence"]["evidence_kind"] == "ARCH_ACTION"


def test_funicular_outside_band_is_reachable(
    portfolio_environment, screened_study, monkeypatch,
):
    reference = deepcopy(screened_study["archive"][0]["base_reference"])
    reference["reference_result"]["f1_comparison"]["agreement_status"] = (
        "AGREEMENT_OUTSIDE_ORDER_BAND"
    )
    monkeypatch.setattr(
        funicular_reference, "run_funicular_reference", lambda _action: reference
    )
    monkeypatch.setattr(
        funicular_reference, "validate_funicular_reference", lambda _value: None
    )
    result = run_creative_portfolio(
        technical_profile=portfolio_environment["technical_profile"],
        structural_profile_factory=portfolio_environment["structural_profile"],
        seed=31,
        iterations=0,
        max_candidates=1,
        robustness_samples=3,
        perturbation_fraction=0.002,
    )
    blocked = result["blocked_candidates"][0]
    assert [item["code"] for item in blocked["blockers"]] == ["CP-FUNICULAR-002"]
    assert blocked["evidence"]["evidence_kind"] == "FUNICULAR_REFERENCE"


def test_source_drift_is_blocked_before_search(portfolio_environment, tmp_path, monkeypatch):
    drifted = tmp_path / "creative_portfolio.py"
    drifted.write_text("# drift", encoding="utf-8")
    paths = list(creative_portfolio._SOURCE_PATHS)
    paths[0] = (paths[0][0], drifted)
    monkeypatch.setattr(creative_portfolio, "_SOURCE_PATHS", tuple(paths))
    with pytest.raises(CreativePortfolioError, match="drift"):
        run_creative_portfolio(
            technical_profile=portfolio_environment["technical_profile"],
            structural_profile_factory=portfolio_environment["structural_profile"],
            seed=3,
            iterations=0,
            max_candidates=1,
            robustness_samples=3,
            perturbation_fraction=0.002,
        )


def test_schema_drift_is_blocked_before_search(portfolio_environment, tmp_path, monkeypatch):
    drifted = tmp_path / "creative_portfolio.schema.json"
    drifted.write_text('{"type":"object"}', encoding="utf-8")
    monkeypatch.setattr(creative_portfolio, "_SCHEMA_PATH", drifted)
    with pytest.raises(CreativePortfolioError, match="schema.*drift"):
        run_creative_portfolio(
            technical_profile=portfolio_environment["technical_profile"],
            structural_profile_factory=portfolio_environment["structural_profile"],
            seed=3,
            iterations=0,
            max_candidates=1,
            robustness_samples=3,
            perturbation_fraction=0.002,
        )


def test_nondeterministic_profile_factory_is_blocked(portfolio_environment):
    valid_factory = portfolio_environment["structural_profile"]
    calls = 0

    def alternating(candidate):
        nonlocal calls
        calls += 1
        profile = valid_factory(candidate)
        profile["deck_line_load"]["q_kN_m"] = 1.0 if calls % 2 else 1.1
        return profile

    result = run_creative_portfolio(
        technical_profile=portfolio_environment["technical_profile"],
        structural_profile_factory=alternating,
        seed=4,
        iterations=0,
        max_candidates=1,
        robustness_samples=3,
        perturbation_fraction=0.002,
    )
    assert result["archive"] == []
    assert result["blocked_candidates"][0]["blockers"][0]["code"] == "CP-PROFILE-003"
    validate_creative_portfolio(result)


def test_wrong_profile_factory_type_is_rejected(portfolio_environment):
    with pytest.raises(CreativePortfolioError, match="callable"):
        run_creative_portfolio(
            technical_profile=portfolio_environment["technical_profile"],
            structural_profile_factory=None,
            seed=3,
            iterations=0,
            max_candidates=1,
            robustness_samples=3,
            perturbation_fraction=0.002,
        )


def test_perturbation_true_l0_failure_emits_cp_perturb_001(
    portfolio_environment, screened_study, monkeypatch,
):
    reference = screened_study["archive"][0]["base_reference"]
    parent = reference["parent_study"]["parent_analysis"]["candidate"]
    domain = creative_shape.load_creative_domain()
    comparison_sha256 = creative_portfolio._structural_comparison_sha256(
        reference["parent_study"]["parent_analysis"]["structural_profile"]
    )
    original = creative_shape.evaluate_genome

    def reject_perturbed(genome, technical_profile, supplied_domain):
        if genome != parent["genome"]:
            raise creative_shape.CreativeShapeError("L0 perturbation rejected")
        return original(genome, technical_profile, supplied_domain)

    monkeypatch.setattr(creative_shape, "evaluate_genome", reject_perturbed)
    sample, blockers, evidence, _comparison = creative_portfolio._sample_record(
        parent,
        portfolio_environment["technical_profile"],
        portfolio_environment["structural_profile"],
        study_seed=31,
        sample_index=0,
        perturbation_fraction=0.002,
        domain=domain,
        expected_comparison_sha256=comparison_sha256,
    )
    assert sample is None
    assert [item["code"] for item in blockers] == ["CP-PERTURB-001"]
    assert evidence["evidence_kind"] == "PERTURBATION_L0"
    assert evidence["evidence_reproducible"] is True


def test_structural_profiles_must_be_comparable_across_topologies(
    portfolio_environment,
):
    baseline_factory = portfolio_environment["structural_profile"]

    def topology_dependent(candidate):
        profile = baseline_factory(candidate)
        if candidate["genome"]["topology"] != "DECK_ARCH":
            profile["edge_properties"]["ARCH_RIB"]["section"]["area_m2"] += 1.0
        return profile

    result = run_creative_portfolio(
        technical_profile=portfolio_environment["technical_profile"],
        structural_profile_factory=topology_dependent,
        seed=31,
        iterations=0,
        max_candidates=3,
        robustness_samples=3,
        perturbation_fraction=0.002,
    )
    validate_creative_portfolio(result)
    assert len(result["archive"]) == 1
    assert result["archive"][0]["topology"] == "DECK_ARCH"
    assert len(result["blocked_candidates"]) == 2
    assert all(
        item["blockers"][0]["code"] == "CP-COMPARABILITY-001"
        and item["evidence"]["evidence_kind"] == "STRUCTURAL_COMPARISON"
        for item in result["blocked_candidates"]
    )


def test_robustness_comparability_block_is_reproducible_with_empty_archive(
    portfolio_environment,
):
    baseline_factory = portfolio_environment["structural_profile"]

    def span_dependent(candidate):
        profile = baseline_factory(candidate)
        profile["edge_properties"]["ARCH_RIB"]["section"]["area_m2"] = (
            6.0 + float(candidate["genome"]["span_m"]) * 0.001
        )
        return profile

    result = run_creative_portfolio(
        technical_profile=portfolio_environment["technical_profile"],
        structural_profile_factory=span_dependent,
        seed=31,
        iterations=0,
        max_candidates=1,
        robustness_samples=3,
        perturbation_fraction=0.002,
    )
    validate_creative_portfolio(result)
    assert result["archive"] == []
    assert len(result["structural_comparison_sha256"]) == 64
    blocked = result["blocked_candidates"][0]
    assert blocked["stage"] == "ROBUSTNESS"
    assert blocked["blockers"][0]["code"] == "CP-PERTURB-002"
    nested = blocked["evidence"]["payload"]
    assert nested["cause_blockers"][0]["code"] == "CP-COMPARABILITY-001"
    assert nested["cause_evidence"]["evidence_kind"] == "STRUCTURAL_COMPARISON"


def test_perturbation_l0_block_runs_end_to_end_and_wraps_forged_upstream_error(
    portfolio_environment, monkeypatch,
):
    original = creative_shape.evaluate_genome

    def reject_nonzero_coefficients(genome, technical_profile, supplied_domain):
        if any(abs(float(value)) > 0.0 for value in genome["shape_coefficients"]):
            raise creative_shape.CreativeShapeError("L0 perturbation rejected end-to-end")
        return original(genome, technical_profile, supplied_domain)

    monkeypatch.setattr(
        creative_shape, "evaluate_genome", reject_nonzero_coefficients
    )
    result = run_creative_portfolio(
        technical_profile=portfolio_environment["technical_profile"],
        structural_profile_factory=portfolio_environment["structural_profile"],
        seed=31,
        iterations=0,
        max_candidates=1,
        robustness_samples=3,
        perturbation_fraction=0.002,
    )
    validate_creative_portfolio(result)
    assert result["archive"] == []
    blocked = result["blocked_candidates"][0]
    assert blocked["stage"] == "ROBUSTNESS"
    assert blocked["blockers"][0]["code"] == "CP-PERTURB-001"
    assert blocked["evidence"]["evidence_kind"] == "PERTURBATION_L0"

    forged = deepcopy(result)
    forged["blocked_candidates"][0]["evidence"]["evidence_kind"] = (
        "ROBUSTNESS_STAGE"
    )
    _reseal(forged)
    with pytest.raises(CreativePortfolioError, match="Robustness-stage candidate"):
        validate_creative_portfolio(forged)


def test_blocked_stage_is_rederived_not_trusted(portfolio_environment):
    def broken_factory(_candidate):
        raise RuntimeError("caller profile unavailable")

    result = run_creative_portfolio(
        technical_profile=portfolio_environment["technical_profile"],
        structural_profile_factory=broken_factory,
        seed=7,
        iterations=0,
        max_candidates=1,
        robustness_samples=3,
        perturbation_fraction=0.002,
    )
    tampered = deepcopy(result)
    tampered["blocked_candidates"][0]["stage"] = "ROBUSTNESS"
    _reseal(tampered)
    with pytest.raises(CreativePortfolioError, match="stage không khớp"):
        validate_creative_portfolio(tampered)


@pytest.mark.parametrize("bad_margin", [None, float("inf"), -1.0])
def test_pass_check_margin_must_be_finite_and_nonnegative(screened_study, bad_margin):
    candidate = deepcopy(
        screened_study["archive"][0]["base_reference"]["parent_study"]
        ["parent_analysis"]["candidate"]
    )
    passing = next(item for item in candidate["checks"] if item["status"] == "PASS")
    passing["margin"] = bad_margin
    with pytest.raises(CreativePortfolioError, match="margin"):
        creative_portfolio._candidate_minimum_margin(candidate)


def test_perturbation_fallback_cannot_return_unchanged_parent(monkeypatch):
    domain = creative_shape.load_creative_domain()
    parent = creative_shape.anchor_genomes(domain)[0]
    frozen = {
        id(domain["span_m"]): parent["span_m"],
        id(domain["rise_ratio"]): parent["rise_ratio"],
        id(domain["rib_depth_m"]): parent["rib_depth_m"],
        id(domain["deck_clearance_m"]): parent["deck_clearance_m"],
        id(domain["coefficient_bounds"]): 0.0,
    }
    monkeypatch.setattr(
        creative_portfolio, "_clip", lambda _value, bounds: frozen[id(bounds)]
    )
    with pytest.raises(CreativePortfolioError, match="khác parent"):
        creative_portfolio._perturbed_genome(
            parent,
            sample_seed=1,
            perturbation_fraction=0.002,
            domain=domain,
        )


def test_reproducible_blocked_evidence_cannot_be_forged(
    portfolio_environment,
):
    valid_factory = portfolio_environment["structural_profile"]
    calls = 0

    def alternating(candidate):
        nonlocal calls
        calls += 1
        profile = valid_factory(candidate)
        profile["deck_line_load"]["q_kN_m"] = 1.0 if calls % 2 else 1.1
        return profile

    result = run_creative_portfolio(
        technical_profile=portfolio_environment["technical_profile"],
        structural_profile_factory=alternating,
        seed=4,
        iterations=0,
        max_candidates=1,
        robustness_samples=3,
        perturbation_fraction=0.002,
    )
    tampered = deepcopy(result)
    pair = tampered["blocked_candidates"][0]["evidence"]["payload"]
    pair["second_profile"] = deepcopy(pair["first_profile"])
    tampered["blocked_candidates"][0]["evidence"]["evidence_sha256"] = (
        _canonical_sha256(pair)
    )
    _reseal(tampered)
    with pytest.raises(CreativePortfolioError, match="không chứng minh drift"):
        validate_creative_portfolio(tampered)
