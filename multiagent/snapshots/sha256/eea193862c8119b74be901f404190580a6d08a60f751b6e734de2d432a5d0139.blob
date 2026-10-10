import hashlib
import math

import pytest

from bridge_evolution.column_capacity import (
    CircularSection,
    ColumnCapacityError,
    ConcreteSteelMaterial,
    EvidenceRef,
    EffectiveLength,
    RebarLayer,
    RectangularSection,
    UnsupportedMemberGeometry,
    interaction_diagram,
    moment_magnification,
)


MM_PER_IN = 25.4
N_PER_KIP = 4_448.2216152605
NMM_PER_KIP_FT = N_PER_KIP * 12.0 * MM_PER_IN


def _evidence(case_id: str) -> EvidenceRef:
    return EvidenceRef(
        source_ref=f"test-source:{case_id}",
        clause_id="TEST-CLAUSE",
        model_sha256=hashlib.sha256(case_id.encode("utf-8")).hexdigest(),
        case_id=case_id,
    )


def _rectangle_case():
    section = RectangularSection(width_mm=600.0, height_mm=800.0)
    material = ConcreteSteelMaterial(
        concrete_strength_mpa=30.0,
        steel_yield_strength_mpa=500.0,
    )
    bars = (
        RebarLayer(area_mm2=2_000.0, y_mm=300.0),
        RebarLayer(area_mm2=2_000.0, y_mm=-300.0),
    )
    return section, material, bars


def _fhwa_circular_case():
    """FHWA PSC example, Design Step 7.2.3, Table 7.2-3.

    Published inputs: D=42 in, f'c=3 ksi, fy=60 ksi, sixteen #8 bars,
    As=0.79 in² each, 2-in side cover and #3 ties.  The bar-center radius
    follows the documented clear cover + tie + half longitudinal-bar diameter.
    Predeclared comparison tolerance for the published pure-bending point is 5%.
    """
    diameter_in = 42.0
    bar_radius_in = diameter_in / 2.0 - 2.0 - 0.375 - 0.5
    section = CircularSection(diameter_mm=diameter_in * MM_PER_IN)
    material = ConcreteSteelMaterial(
        concrete_strength_mpa=3.0 * 6.894757293168361,
        steel_yield_strength_mpa=60.0 * 6.894757293168361,
        steel_modulus_mpa=29_000.0 * 6.894757293168361,
    )
    bars = tuple(
        RebarLayer(
            area_mm2=0.79 * MM_PER_IN**2,
            y_mm=bar_radius_in * math.cos(2.0 * math.pi * index / 16.0) * MM_PER_IN,
        )
        for index in range(16)
    )
    return section, material, bars


def test_interaction_diagram_contains_four_mechanical_anchors():
    section, material, bars = _rectangle_case()
    result = interaction_diagram(
        section,
        material,
        bars,
        member_geometry="STRAIGHT_PRISMATIC",
    )

    assert result.pure_compression.label == "PURE_COMPRESSION"
    assert result.balanced.label == "BALANCED"
    assert result.pure_bending.label == "PURE_BENDING"
    assert result.pure_tension.label == "PURE_TENSION"
    assert result.pure_compression.nominal_axial_n > 0.0
    assert result.pure_tension.nominal_axial_n < 0.0
    assert abs(result.pure_bending.nominal_axial_n) <= (
        1e-9 * result.pure_compression.nominal_axial_n
    )
    assert result.design_verdict_authority == "NONE"


def test_balanced_point_yields_extreme_tension_steel_with_concrete_at_limit():
    section, material, bars = _rectangle_case()
    result = interaction_diagram(
        section,
        material,
        bars,
        member_geometry="STRAIGHT_PRISMATIC",
    )

    assert result.balanced.extreme_tension_strain == pytest.approx(
        material.steel_yield_strain, rel=1e-12
    )
    assert result.balanced.phi == pytest.approx(0.75)


def test_phi_changes_with_extreme_tension_strain():
    section, material, bars = _rectangle_case()
    result = interaction_diagram(
        section,
        material,
        bars,
        member_geometry="STRAIGHT_PRISMATIC",
        sample_count=120,
    )
    phis = {round(point.phi, 8) for point in result.points}

    assert min(phis) == pytest.approx(0.75)
    assert max(phis) == pytest.approx(0.90)
    assert len(phis) > 2


def test_rebar_input_order_cannot_change_interaction_anchors():
    section, material, bars = _rectangle_case()
    first = interaction_diagram(
        section, material, bars, member_geometry="STRAIGHT_PRISMATIC"
    )
    second = interaction_diagram(
        section, material, reversed(bars), member_geometry="STRAIGHT_PRISMATIC"
    )

    for name in ("pure_compression", "balanced", "pure_bending", "pure_tension"):
        a = getattr(first, name)
        b = getattr(second, name)
        assert a.nominal_axial_n == pytest.approx(b.nominal_axial_n, rel=1e-13)
        assert a.nominal_moment_nmm == pytest.approx(b.nominal_moment_nmm, rel=1e-13)


def test_fhwa_circular_column_matches_published_pure_bending_and_tension_points():
    """Measured: Mo=928.4446 kip-ft (+0.0479%); Pt=-682.56 kip (-0.0644%)."""
    section, material, bars = _fhwa_circular_case()
    result = interaction_diagram(
        section,
        material,
        bars,
        member_geometry="STRAIGHT_PRISMATIC",
        sample_count=160,
    )

    published_mo_kip_ft = 928.0
    calculated_mo_kip_ft = result.pure_bending.phi_moment_nmm / NMM_PER_KIP_FT
    published_tension_kip = -683.0
    calculated_tension_kip = result.pure_tension.phi_axial_n / N_PER_KIP

    assert calculated_mo_kip_ft == pytest.approx(published_mo_kip_ft, rel=0.05)
    assert calculated_tension_kip == pytest.approx(published_tension_kip, abs=1.0)


def test_fhwa_axial_cap_is_separate_from_nominal_uniform_compression():
    """FHWA Table 7.2-3: first envelope point Pmax=2555 kip, M=764 kip-ft."""
    section, material, bars = _fhwa_circular_case()
    result = interaction_diagram(
        section, material, bars, member_geometry="STRAIGHT_PRISMATIC", sample_count=160
    )

    assert result.pure_compression.phi_axial_n / N_PER_KIP == pytest.approx(
        3_194.28, rel=1e-4
    )
    assert result.maximum_factored_axial_n / N_PER_KIP == pytest.approx(
        2_555.0, rel=5e-4
    )
    assert result.maximum_factored_compression.phi_moment_nmm / NMM_PER_KIP_FT == (
        pytest.approx(764.0, rel=1e-3)
    )
    assert result.pure_compression not in result.points
    assert max(point.phi_axial_n for point in result.points) <= (
        result.maximum_factored_axial_n * (1.0 + 1e-10)
    )


def test_basis_coefficients_cannot_be_overridden_by_caller():
    section, material, bars = _rectangle_case()
    with pytest.raises(TypeError):
        ConcreteSteelMaterial(
            concrete_strength_mpa=30.0,
            steel_yield_strength_mpa=500.0,
            beta1=0.99,
        )
    with pytest.raises(ColumnCapacityError, match="basis_id chưa đăng ký"):
        interaction_diagram(
            section,
            material,
            bars,
            member_geometry="STRAIGHT_PRISMATIC",
            basis_id="CALLER-CUSTOM-BASIS",
        )


def test_reinforcement_ratio_and_symmetry_fail_closed():
    section, material, _ = _rectangle_case()
    with pytest.raises(ColumnCapacityError, match="As/Ag"):
        interaction_diagram(
            section,
            material,
            (
                RebarLayer(area_mm2=220_000.0, y_mm=300.0),
                RebarLayer(area_mm2=220_000.0, y_mm=-300.0),
            ),
            member_geometry="STRAIGHT_PRISMATIC",
        )
    with pytest.raises(ColumnCapacityError, match="đối xứng"):
        interaction_diagram(
            section,
            material,
            (
                RebarLayer(area_mm2=4_000.0, y_mm=300.0),
                RebarLayer(area_mm2=4_000.0, y_mm=-200.0),
            ),
            member_geometry="STRAIGHT_PRISMATIC",
        )


@pytest.mark.parametrize("depth_mm", [1.0e-7, 8.5e-7, 0.1, 499.9, 500.0])
def test_thin_circular_segment_remains_positive_and_bounded(depth_mm):
    area, centroid_depth = CircularSection(diameter_mm=1_000.0).compression_block(
        depth_mm
    )
    assert area > 0.0
    assert 0.0 <= centroid_depth <= depth_mm


def test_rejects_curved_member_and_bar_outside_section():
    section, material, bars = _rectangle_case()
    with pytest.raises(UnsupportedMemberGeometry, match="vành vòm"):
        interaction_diagram(section, material, bars, member_geometry="ARCH_RIB")

    with pytest.raises(ColumnCapacityError, match="ngoài tiết diện"):
        interaction_diagram(
            section,
            material,
            [RebarLayer(area_mm2=500.0, y_mm=500.0)],
            member_geometry="STRAIGHT_PRISMATIC",
        )

    with pytest.raises(ColumnCapacityError, match="60 MPa"):
        interaction_diagram(
            section,
            ConcreteSteelMaterial(
                concrete_strength_mpa=70.0,
                steel_yield_strength_mpa=500.0,
            ),
            bars,
            member_geometry="STRAIGHT_PRISMATIC",
        )


def test_short_column_returns_unmagnified_moment():
    result = moment_magnification(
        member_geometry="STRAIGHT_PRISMATIC",
        effective_length=EffectiveLength(
            k=1.0,
            unbraced_length_mm=3_000.0,
            provenance=_evidence("frame-analysis-case-17-effective-length"),
        ),
        radius_of_gyration_mm=200.0,
        cracked_ei_n_mm2=1.0e15,
        factored_axial_n=2.0e6,
        first_order_moment_nmm=5.0e8,
        phi_k=0.75,
        analysis_provenance=_evidence("frame-analysis-case-17-inputs"),
        end_moment_ratio_m1_over_m2=0.0,
        transverse_load_between_supports=False,
    )

    assert result.status == "SHORT_COLUMN"
    assert result.magnification == 1.0
    assert result.magnified_moment_nmm == 5.0e8


def test_fhwa_steel_bridge_pier_second_order_benchmark():
    """FHWA-NHI-04-041 pp. 8-53–8-55; tolerance predeclared at 0.5%.

    Measured: kLu/r=42.02694; member Pe=81,616.94 kip (-0.103%);
    delta_s=1.04138 and M2=2,007.78 kip-ft with published system ΣPe.
    """
    result = moment_magnification(
        member_geometry="STRAIGHT_PRISMATIC",
        effective_length=EffectiveLength(
            k=2.1,
            unbraced_length_mm=312.0 * MM_PER_IN,
            provenance=_evidence("FHWA-NHI-04-041-kLu"),
        ),
        radius_of_gyration_mm=15.59 * MM_PER_IN,
        cracked_ei_n_mm2=3.55e9 * N_PER_KIP * MM_PER_IN**2,
        factored_axial_n=2_435.0 * N_PER_KIP,
        first_order_moment_nmm=1_928.0 * NMM_PER_KIP_FT,
        phi_k=0.75,
        analysis_provenance=_evidence("FHWA-NHI-04-041-step-8.9-inputs"),
        analysis_mode="SWAY_SYSTEM",
        system_factored_axial_sum_n=2_435.0 * N_PER_KIP,
        system_euler_load_sum_n=81_701.0 * N_PER_KIP,
    )

    assert result.status == "MAGNIFIED"
    assert result.slenderness_ratio == pytest.approx(42.03, rel=5e-4)
    assert result.euler_load_n / N_PER_KIP == pytest.approx(81_701.0, rel=5e-3)
    assert result.magnification == pytest.approx(1.04, rel=5e-3)
    assert result.magnified_moment_nmm / NMM_PER_KIP_FT == pytest.approx(
        2_008.0, rel=5e-3
    )
    assert result.analysis_mode == "SWAY_SYSTEM"
    assert result.cm_used is None


def test_method_refuses_slenderness_at_or_above_100():
    result = moment_magnification(
        member_geometry="STRAIGHT_PRISMATIC",
        effective_length=EffectiveLength(
            k=2.0,
            unbraced_length_mm=5_000.0,
            provenance=_evidence("eigenvalue-study-case-2-effective-length"),
        ),
        radius_of_gyration_mm=100.0,
        cracked_ei_n_mm2=1.0e14,
        factored_axial_n=1.0e6,
        first_order_moment_nmm=1.0e8,
        phi_k=0.75,
        analysis_provenance=_evidence("eigenvalue-study-case-2-inputs"),
        end_moment_ratio_m1_over_m2=0.0,
        transverse_load_between_supports=False,
    )

    assert result.status == "OUT_OF_METHOD_RANGE"
    assert result.magnification is None
    assert result.magnified_moment_nmm is None


def test_slenderness_ceiling_and_cm_are_not_caller_overrides():
    kwargs = dict(
        member_geometry="STRAIGHT_PRISMATIC",
        effective_length=EffectiveLength(
            k=3.0,
            unbraced_length_mm=5_000.0,
            provenance=_evidence("fixed-method-limit-effective-length"),
        ),
        radius_of_gyration_mm=100.0,
        cracked_ei_n_mm2=1.0e14,
        factored_axial_n=1.0e6,
        first_order_moment_nmm=1.0e8,
        phi_k=0.75,
        analysis_provenance=_evidence("fixed-method-limit-inputs"),
        end_moment_ratio_m1_over_m2=0.0,
        transverse_load_between_supports=False,
    )
    assert moment_magnification(**kwargs).status == "OUT_OF_METHOD_RANGE"
    with pytest.raises(TypeError):
        moment_magnification(**kwargs, maximum_slenderness=1_000.0)
    with pytest.raises(TypeError):
        moment_magnification(**kwargs, cm=0.1)


def test_nonsway_cm_is_computed_and_sway_inputs_cannot_be_mixed():
    common = dict(
        member_geometry="STRAIGHT_PRISMATIC",
        effective_length=EffectiveLength(
            k=2.0,
            unbraced_length_mm=4_000.0,
            provenance=_evidence("cm-consistency-effective-length"),
        ),
        radius_of_gyration_mm=200.0,
        cracked_ei_n_mm2=8.0e13,
        factored_axial_n=1.0e6,
        first_order_moment_nmm=1.0e8,
        phi_k=0.75,
        analysis_provenance=_evidence("cm-consistency-inputs"),
    )
    nonsway = moment_magnification(
        **common,
        end_moment_ratio_m1_over_m2=0.0,
        transverse_load_between_supports=False,
    )
    assert nonsway.cm_used == pytest.approx(0.6)

    with pytest.raises(ColumnCapacityError, match="không được trộn"):
        moment_magnification(
            **common,
            analysis_mode="SWAY_SYSTEM",
            end_moment_ratio_m1_over_m2=0.0,
            transverse_load_between_supports=False,
            system_factored_axial_sum_n=1.0e6,
            system_euler_load_sum_n=1.0e8,
        )


def test_near_euler_limit_returns_status_instead_of_exploding_number():
    effective = EffectiveLength(
        k=2.0,
        unbraced_length_mm=4_000.0,
        provenance=_evidence("frame-buckling-model-case-9-effective-length"),
    )
    ei = 8.0e13
    pc = math.pi**2 * ei / (effective.k * effective.unbraced_length_mm) ** 2
    result = moment_magnification(
        member_geometry="STRAIGHT_PRISMATIC",
        effective_length=effective,
        radius_of_gyration_mm=200.0,
        cracked_ei_n_mm2=ei,
        factored_axial_n=0.75 * pc,
        first_order_moment_nmm=1.0e8,
        phi_k=0.75,
        analysis_provenance=_evidence("frame-buckling-model-case-9-inputs"),
        end_moment_ratio_m1_over_m2=0.0,
        transverse_load_between_supports=False,
    )

    assert result.status == "INSTABILITY_LIMIT"
    assert result.magnification is None


def test_locked_proximity_guard_blocks_a_billion_scale_delta():
    effective = EffectiveLength(
        k=2.0,
        unbraced_length_mm=4_000.0,
        provenance=_evidence("near-critical-effective-length"),
    )
    ei = 8.0e13
    pe = math.pi**2 * ei / (effective.k * effective.unbraced_length_mm) ** 2
    result = moment_magnification(
        member_geometry="STRAIGHT_PRISMATIC",
        effective_length=effective,
        radius_of_gyration_mm=200.0,
        cracked_ei_n_mm2=ei,
        factored_axial_n=0.75 * pe * (1.0 - 1.0e-9),
        first_order_moment_nmm=1.0e8,
        phi_k=0.75,
        analysis_provenance=_evidence("near-critical-inputs"),
        end_moment_ratio_m1_over_m2=0.0,
        transverse_load_between_supports=False,
    )
    assert result.status == "INSTABILITY_LIMIT"
    assert result.magnification is None


def test_sway_requires_system_level_sums():
    result = moment_magnification(
        member_geometry="STRAIGHT_PRISMATIC",
        effective_length=EffectiveLength(
            k=2.0,
            unbraced_length_mm=4_000.0,
            provenance=_evidence("global-frame-model-case-4-effective-length"),
        ),
        radius_of_gyration_mm=200.0,
        cracked_ei_n_mm2=8.0e13,
        factored_axial_n=1.0e6,
        first_order_moment_nmm=1.0e8,
        phi_k=0.75,
        analysis_provenance=_evidence("global-frame-model-case-4-inputs"),
        analysis_mode="SWAY_SYSTEM",
    )

    assert result.status == "NEEDS_SYSTEM_LEVEL_INPUT"
    assert result.magnification is None


def test_effective_length_provenance_is_mandatory_and_geometry_is_guarded():
    kwargs = dict(
        member_geometry="STRAIGHT_PRISMATIC",
        effective_length=EffectiveLength(k=1.0, unbraced_length_mm=5_000.0, provenance=""),
        radius_of_gyration_mm=150.0,
        cracked_ei_n_mm2=8.0e13,
        factored_axial_n=1.0e6,
        first_order_moment_nmm=1.0e8,
        phi_k=0.75,
        analysis_provenance=_evidence("provenance-guard-inputs"),
        end_moment_ratio_m1_over_m2=0.0,
        transverse_load_between_supports=False,
    )
    with pytest.raises(ColumnCapacityError, match="provenance"):
        moment_magnification(**kwargs)

    kwargs["effective_length"] = EffectiveLength(
        k=1.0,
        unbraced_length_mm=5_000.0,
        provenance=EvidenceRef(
            source_ref="somewhere",
            clause_id="x",
            model_sha256="12345678",
            case_id="case",
        ),
    )
    with pytest.raises(ColumnCapacityError, match="SHA-256"):
        moment_magnification(**kwargs)

    kwargs["effective_length"] = EffectiveLength(
        k=1.0,
        unbraced_length_mm=5_000.0,
        provenance=_evidence("frame-analysis-case-21-effective-length"),
    )
    kwargs["member_geometry"] = "CURVED_ARCH_RIB"
    with pytest.raises(UnsupportedMemberGeometry):
        moment_magnification(**kwargs)
