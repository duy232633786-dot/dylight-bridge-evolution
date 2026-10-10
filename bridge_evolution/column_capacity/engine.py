"""Fail-closed F1 screening for straight prismatic RC columns and piers.

Units are explicit SI-derived engineering units: geometry in mm, stress in MPa
(N/mm²), axial force in N, moment in N·mm, and flexural stiffness in N·mm².
The implementation is intentionally independent from the bridge verifier.  It
does not create load combinations and has no authority to declare a design safe.

Published implementation anchors:

* FHWA, *Comprehensive Design Example for Prestressed Concrete Girder
  Superstructure Bridge*, Design Step 7.2.3, circular 42-in pier interaction
  table and moment magnification example (updated 2017),
  https://www.fhwa.dot.gov/bridge/lrfd/pscus72.cfm
* FHWA-NHI-04-041, *LRFD Design Example for Steel Girder Superstructure
  Bridge*, Design Step 8.9, pp. 8-51–8-56 (archived FHWA PDF),
  https://www.fhwa.dot.gov/bridge/lrfd/fhwanhi04041_steel.pdf

Matching those examples checks this implementation only.  It is not independent
solver validation and does not raise the project claim above SCREENED.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable, Literal, Protocol


DEFAULT_BASIS_ID = "DYLIGHT-FHWA-AASHTO-LRFD-SCREENING-v1"


class ColumnCapacityError(ValueError):
    """Invalid input or an explicitly unsupported mechanical domain."""


class UnsupportedMemberGeometry(ColumnCapacityError):
    """Raised before calculation for curved or non-prismatic members."""


def require_straight_prismatic(member_geometry: str) -> None:
    """Machine-probeable domain guard shared by both calculation paths."""
    if member_geometry != "STRAIGHT_PRISMATIC":
        raise UnsupportedMemberGeometry(
            "Engine chỉ áp dụng cho cấu kiện STRAIGHT_PRISMATIC; "
            "vành vòm/cấu kiện cong cần mô hình ổn định riêng"
        )


@dataclass(frozen=True)
class RebarLayer:
    """One bar or an aggregated layer at ``y_mm`` from the section centroid.

    Positive ``y_mm`` points toward the compression face used for positive
    bending.  Discrete bars at the same ordinate may be aggregated by area.
    """

    area_mm2: float
    y_mm: float


@dataclass(frozen=True)
class ConcreteSteelMaterial:
    concrete_strength_mpa: float
    steel_yield_strength_mpa: float
    steel_modulus_mpa: float = 200_000.0

    def validate(self) -> None:
        values = (
            self.concrete_strength_mpa,
            self.steel_yield_strength_mpa,
            self.steel_modulus_mpa,
        )
        if not all(math.isfinite(value) and value > 0.0 for value in values):
            raise ColumnCapacityError("Mọi tham số vật liệu phải hữu hạn và dương")
        if self.concrete_strength_mpa > 60.0:
            raise ColumnCapacityError(
                "f'c > 60 MPa nằm ngoài miền vật liệu đã khai của engine F1"
            )

    @property
    def steel_yield_strain(self) -> float:
        return self.steel_yield_strength_mpa / self.steel_modulus_mpa


@dataclass(frozen=True)
class EvidenceRef:
    """Structured provenance for caller-supplied analysis inputs."""

    source_ref: str
    clause_id: str
    model_sha256: str
    case_id: str

    def validate(self, label: str) -> None:
        for field_name in ("source_ref", "clause_id", "case_id"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ColumnCapacityError(f"{label}.{field_name} không được rỗng")
        if not (
            isinstance(self.model_sha256, str)
            and len(self.model_sha256) == 64
            and all(character in "0123456789abcdef" for character in self.model_sha256)
        ):
            raise ColumnCapacityError(
                f"{label}.model_sha256 phải là SHA-256 chữ thường 64 ký tự"
            )


@dataclass(frozen=True)
class _ScreeningBasis:
    basis_id: str = DEFAULT_BASIS_ID
    source_ref: str = "FHWA PSC Design Step 7.2.3 / AASHTO LRFD clauses cited there"
    alpha1: float = 0.85
    ultimate_concrete_strain: float = 0.003
    compression_phi: float = 0.75
    tension_phi: float = 0.90
    tension_control_strain: float = 0.005
    maximum_factored_axial_ratio: float = 0.80
    maximum_reinforcement_ratio: float = 0.08
    minimum_mechanical_reinforcement_index: float = 0.135
    maximum_slenderness: float = 100.0
    instability_proximity_ratio: float = 0.95

    def beta1(self, concrete_strength_mpa: float) -> float:
        # AASHTO/ACI rectangular-block reduction expressed in SI: 0.85 through
        # 4 ksi, minus 0.05 per additional 1 ksi, bounded below by 0.65.
        four_ksi_mpa = 4.0 * 6.894757293168361
        one_ksi_mpa = 6.894757293168361
        reduction = max(0.0, concrete_strength_mpa - four_ksi_mpa)
        return max(0.65, 0.85 - 0.05 * reduction / one_ksi_mpa)

    def phi(self, extreme_tension_strain: float, yield_strain: float) -> float:
        if extreme_tension_strain <= yield_strain:
            return self.compression_phi
        if extreme_tension_strain >= self.tension_control_strain:
            return self.tension_phi
        fraction = (
            (extreme_tension_strain - yield_strain)
            / (self.tension_control_strain - yield_strain)
        )
        return self.compression_phi + fraction * (
            self.tension_phi - self.compression_phi
        )


def _screening_basis(basis_id: str) -> _ScreeningBasis:
    if basis_id != DEFAULT_BASIS_ID:
        raise ColumnCapacityError(
            f"basis_id chưa đăng ký: {basis_id}; engine không nhận hệ số tùy ý"
        )
    return _ScreeningBasis()


class Section(Protocol):
    @property
    def depth_mm(self) -> float: ...

    @property
    def gross_area_mm2(self) -> float: ...

    @property
    def gross_inertia_mm4(self) -> float: ...

    def compression_block(self, depth_mm: float) -> tuple[float, float]:
        """Return compressed area and centroid depth from compression face."""

    def contains_rebar(self, layer: RebarLayer, *, tolerance_mm: float = 1e-9) -> bool: ...


@dataclass(frozen=True)
class RectangularSection:
    width_mm: float
    height_mm: float

    def _validate(self) -> None:
        if not (
            math.isfinite(self.width_mm)
            and math.isfinite(self.height_mm)
            and self.width_mm > 0.0
            and self.height_mm > 0.0
        ):
            raise ColumnCapacityError("Kích thước tiết diện chữ nhật phải dương")

    @property
    def depth_mm(self) -> float:
        self._validate()
        return self.height_mm

    @property
    def gross_area_mm2(self) -> float:
        self._validate()
        return self.width_mm * self.height_mm

    @property
    def gross_inertia_mm4(self) -> float:
        self._validate()
        return self.width_mm * self.height_mm**3 / 12.0

    def compression_block(self, depth_mm: float) -> tuple[float, float]:
        self._validate()
        depth = min(max(float(depth_mm), 0.0), self.height_mm)
        return self.width_mm * depth, depth / 2.0

    def contains_rebar(self, layer: RebarLayer, *, tolerance_mm: float = 1e-9) -> bool:
        return abs(layer.y_mm) <= self.height_mm / 2.0 + tolerance_mm


@dataclass(frozen=True)
class CircularSection:
    diameter_mm: float

    def _validate(self) -> None:
        if not math.isfinite(self.diameter_mm) or self.diameter_mm <= 0.0:
            raise ColumnCapacityError("Đường kính tiết diện tròn phải dương")

    @property
    def depth_mm(self) -> float:
        self._validate()
        return self.diameter_mm

    @property
    def gross_area_mm2(self) -> float:
        self._validate()
        radius = self.diameter_mm / 2.0
        return math.pi * radius**2

    @property
    def gross_inertia_mm4(self) -> float:
        self._validate()
        return math.pi * self.diameter_mm**4 / 64.0

    def compression_block(self, depth_mm: float) -> tuple[float, float]:
        """Exact circular-segment area and centroid for a horizontal block."""
        self._validate()
        radius = self.diameter_mm / 2.0
        depth = min(max(float(depth_mm), 0.0), self.diameter_mm)
        if depth <= 0.0:
            return 0.0, 0.0
        if depth >= self.diameter_mm:
            return math.pi * radius**2, radius

        def small_cap(cap_depth: float) -> tuple[float, float]:
            # theta=acos(1-h/R) loses precision for h/R << 1.  The asin form
            # and the series for theta-sin(theta)cos(theta) remain positive.
            theta = 2.0 * math.asin(math.sqrt(cap_depth / (2.0 * radius)))
            if theta < 1.0e-3:
                theta2 = theta * theta
                area_term = theta**3 * (
                    2.0 / 3.0
                    - 2.0 * theta2 / 15.0
                    + 4.0 * theta2**2 / 315.0
                    - 2.0 * theta2**3 / 2835.0
                )
            else:
                area_term = theta - math.sin(theta) * math.cos(theta)
            area = radius**2 * area_term
            centroid_from_center = radius * (
                2.0 * math.sin(theta) ** 3 / (3.0 * area_term)
            )
            centroid_depth = radius - centroid_from_center
            if not (area > 0.0 and 0.0 <= centroid_depth <= cap_depth):
                raise ColumnCapacityError(
                    "Tích phân phân đoạn tròn mất ổn định số ngoài miền cho phép"
                )
            return area, centroid_depth

        if depth <= radius:
            return small_cap(depth)

        missing_area, missing_centroid_from_bottom = small_cap(
            self.diameter_mm - depth
        )
        full_area = math.pi * radius**2
        area = full_area - missing_area
        first_moment_from_top = (
            full_area * radius
            - missing_area * (self.diameter_mm - missing_centroid_from_bottom)
        )
        return area, first_moment_from_top / area

    def contains_rebar(self, layer: RebarLayer, *, tolerance_mm: float = 1e-9) -> bool:
        # A uniaxial layer gives only the bending-axis ordinate.  Its horizontal
        # coordinate is intentionally not invented; the necessary condition is
        # therefore |y| <= R and is documented in the result limitations.
        return abs(layer.y_mm) <= self.diameter_mm / 2.0 + tolerance_mm


@dataclass(frozen=True)
class InteractionPoint:
    label: str
    neutral_axis_depth_mm: float | None
    nominal_axial_n: float
    nominal_moment_nmm: float
    phi: float
    phi_axial_n: float
    phi_moment_nmm: float
    extreme_tension_strain: float


@dataclass(frozen=True)
class InteractionDiagram:
    """Code-limited uniaxial envelope plus raw uniform-strain endpoints.

    ``points`` excludes the nominal uniform-compression endpoint above the
    maximum factored axial limit.  It is retained separately as ``pure_compression``
    so Po can be audited without being mistaken for an admissible envelope point.
    """

    points: tuple[InteractionPoint, ...]
    pure_compression: InteractionPoint
    maximum_factored_compression: InteractionPoint
    balanced: InteractionPoint
    pure_bending: InteractionPoint
    pure_tension: InteractionPoint
    maximum_factored_axial_n: float
    basis_id: str
    basis_source_ref: str
    claim_level: Literal["SCREENED"] = "SCREENED"
    design_verdict_authority: Literal["NONE"] = "NONE"


def _validated_reinforcement(
    section: Section,
    reinforcement: Iterable[RebarLayer],
    material: ConcreteSteelMaterial,
    basis: _ScreeningBasis,
) -> tuple[RebarLayer, ...]:
    layers = tuple(reinforcement)
    if not layers:
        raise ColumnCapacityError("Tiết diện phải có ít nhất một lớp cốt thép")
    for layer in layers:
        if not (
            math.isfinite(layer.area_mm2)
            and math.isfinite(layer.y_mm)
            and layer.area_mm2 > 0.0
        ):
            raise ColumnCapacityError("Diện tích và tọa độ cốt thép phải hợp lệ")
        if not section.contains_rebar(layer):
            raise ColumnCapacityError("Cốt thép nằm ngoài tiết diện")
    layers = tuple(sorted(layers, key=lambda item: (item.y_mm, item.area_mm2)))
    steel_area = sum(layer.area_mm2 for layer in layers)
    reinforcement_ratio = steel_area / section.gross_area_mm2
    if reinforcement_ratio > basis.maximum_reinforcement_ratio + 1e-12:
        raise ColumnCapacityError(
            f"As/Ag={reinforcement_ratio:.6g} vượt "
            f"{basis.maximum_reinforcement_ratio:.6g} của screening basis"
        )
    mechanical_index = (
        steel_area * material.steel_yield_strength_mpa
        / (section.gross_area_mm2 * material.concrete_strength_mpa)
    )
    if mechanical_index < basis.minimum_mechanical_reinforcement_index - 1e-12:
        raise ColumnCapacityError(
            f"As*fy/(Ag*f'c)={mechanical_index:.6g} dưới "
            f"{basis.minimum_mechanical_reinforcement_index:.6g}; "
            "MVP không dùng reduced effective section"
        )

    # This MVP produces one positive-bending branch and therefore requires a
    # reinforcement layout symmetric about the bending centroid.  Biaxial or
    # asymmetric layouts need both signs and are rejected instead of mislabeled.
    unmatched = list(layers)
    ordinate_tolerance = max(1e-8, 1e-10 * section.depth_mm)
    while unmatched:
        layer = unmatched.pop(0)
        match_index = next(
            (
                index
                for index, candidate in enumerate(unmatched)
                if abs(candidate.y_mm + layer.y_mm) <= ordinate_tolerance
                and math.isclose(
                    candidate.area_mm2,
                    layer.area_mm2,
                    rel_tol=1e-10,
                    abs_tol=1e-8,
                )
            ),
            None,
        )
        if match_index is None:
            if abs(layer.y_mm) <= ordinate_tolerance:
                continue
            raise ColumnCapacityError(
                "MVP chỉ nhận bố trí cốt thép đối xứng qua trọng tâm uốn"
            )
        unmatched.pop(match_index)
    return layers


def _point_from_neutral_axis(
    section: Section,
    material: ConcreteSteelMaterial,
    layers: tuple[RebarLayer, ...],
    neutral_axis_depth_mm: float,
    *,
    label: str,
    basis: _ScreeningBasis,
) -> InteractionPoint:
    c = float(neutral_axis_depth_mm)
    if not math.isfinite(c) or c <= 0.0:
        raise ColumnCapacityError("Chiều sâu trục trung hòa phải hữu hạn và dương")
    depth = section.depth_mm
    block_depth = min(basis.beta1(material.concrete_strength_mpa) * c, depth)
    concrete_area, concrete_centroid_depth = section.compression_block(block_depth)
    concrete_stress = basis.alpha1 * material.concrete_strength_mpa
    concrete_force = concrete_stress * concrete_area
    axial = concrete_force
    moment = concrete_force * (depth / 2.0 - concrete_centroid_depth)
    strains: list[float] = []
    for layer in layers:
        layer_depth = depth / 2.0 - layer.y_mm
        strain = basis.ultimate_concrete_strain * (1.0 - layer_depth / c)
        steel_stress = max(
            -material.steel_yield_strength_mpa,
            min(material.steel_yield_strength_mpa, material.steel_modulus_mpa * strain),
        )
        # The equivalent block used gross concrete area.  Subtract its stress
        # over embedded steel to avoid counting the same area twice.
        net_stress = steel_stress
        if layer_depth <= block_depth + 1e-12:
            net_stress -= concrete_stress
        force = layer.area_mm2 * net_stress
        axial += force
        moment += force * layer.y_mm
        strains.append(strain)
    extreme_tension = max(0.0, -min(strains))
    phi = basis.phi(extreme_tension, material.steel_yield_strain)
    return InteractionPoint(
        label=label,
        neutral_axis_depth_mm=c,
        nominal_axial_n=axial,
        nominal_moment_nmm=moment,
        phi=phi,
        phi_axial_n=phi * axial,
        phi_moment_nmm=phi * moment,
        extreme_tension_strain=extreme_tension,
    )


def _uniform_point(
    section: Section,
    material: ConcreteSteelMaterial,
    layers: tuple[RebarLayer, ...],
    *,
    compression: bool,
    basis: _ScreeningBasis,
) -> InteractionPoint:
    concrete_stress = basis.alpha1 * material.concrete_strength_mpa
    if compression:
        axial = concrete_stress * section.gross_area_mm2
        moment = 0.0
        compression_steel_stress = min(
            material.steel_yield_strength_mpa,
            material.steel_modulus_mpa * basis.ultimate_concrete_strain,
        )
        for layer in layers:
            net_force = layer.area_mm2 * (
                compression_steel_stress - concrete_stress
            )
            axial += net_force
            moment += net_force * layer.y_mm
        extreme_tension = 0.0
        label = "PURE_COMPRESSION"
    else:
        axial = -sum(
            layer.area_mm2 * material.steel_yield_strength_mpa for layer in layers
        )
        moment = sum(
            -layer.area_mm2 * material.steel_yield_strength_mpa * layer.y_mm
            for layer in layers
        )
        extreme_tension = basis.tension_control_strain
        label = "PURE_TENSION"
    phi = basis.phi(extreme_tension, material.steel_yield_strain)
    return InteractionPoint(
        label=label,
        neutral_axis_depth_mm=None,
        nominal_axial_n=axial,
        nominal_moment_nmm=moment,
        phi=phi,
        phi_axial_n=phi * axial,
        phi_moment_nmm=phi * moment,
        extreme_tension_strain=extreme_tension,
    )


def _pure_bending_depth(
    section: Section,
    material: ConcreteSteelMaterial,
    layers: tuple[RebarLayer, ...],
    basis: _ScreeningBasis,
) -> float:
    low = section.depth_mm * 1e-9
    high = section.depth_mm
    f_low = _point_from_neutral_axis(
        section, material, layers, low, label="ROOT", basis=basis
    ).nominal_axial_n
    f_high = _point_from_neutral_axis(
        section, material, layers, high, label="ROOT", basis=basis
    ).nominal_axial_n
    while f_low * f_high > 0.0 and high < section.depth_mm * 1e9:
        high *= 10.0
        f_high = _point_from_neutral_axis(
            section, material, layers, high, label="ROOT", basis=basis
        ).nominal_axial_n
    if f_low * f_high > 0.0:
        raise ColumnCapacityError("Không chặn được nghiệm uốn thuần N=0")
    for _ in range(160):
        mid = (low + high) / 2.0
        f_mid = _point_from_neutral_axis(
            section, material, layers, mid, label="ROOT", basis=basis
        ).nominal_axial_n
        if abs(f_mid) <= max(1e-6, 1e-12 * material.concrete_strength_mpa * section.gross_area_mm2):
            return mid
        if f_low * f_mid <= 0.0:
            high = mid
            f_high = f_mid
        else:
            low = mid
            f_low = f_mid
    return (low + high) / 2.0


def _maximum_factored_compression_point(
    section: Section,
    material: ConcreteSteelMaterial,
    layers: tuple[RebarLayer, ...],
    basis: _ScreeningBasis,
    pure_compression: InteractionPoint,
    pure_bending_depth: float,
) -> tuple[InteractionPoint, float]:
    limit = basis.maximum_factored_axial_ratio * pure_compression.phi_axial_n
    low = pure_bending_depth
    high = section.depth_mm

    def residual(c: float) -> float:
        return _point_from_neutral_axis(
            section, material, layers, c, label="ROOT", basis=basis
        ).phi_axial_n - limit

    low_residual = residual(low)
    high_residual = residual(high)
    while high_residual < 0.0 and high < section.depth_mm * 1e9:
        high *= 10.0
        high_residual = residual(high)
    if low_residual > 0.0 or high_residual < 0.0:
        raise ColumnCapacityError("Không chặn được giới hạn nén dọc có hệ số")
    for _ in range(160):
        mid = (low + high) / 2.0
        mid_residual = residual(mid)
        if abs(mid_residual) <= max(1e-6, 1e-12 * abs(limit)):
            point = _point_from_neutral_axis(
                section,
                material,
                layers,
                mid,
                label="MAXIMUM_FACTORED_COMPRESSION",
                basis=basis,
            )
            return point, limit
        if mid_residual > 0.0:
            high = mid
        else:
            low = mid
    mid = (low + high) / 2.0
    return (
        _point_from_neutral_axis(
            section,
            material,
            layers,
            mid,
            label="MAXIMUM_FACTORED_COMPRESSION",
            basis=basis,
        ),
        limit,
    )


def interaction_diagram(
    section: Section,
    material: ConcreteSteelMaterial,
    reinforcement: Iterable[RebarLayer],
    *,
    member_geometry: str,
    sample_count: int = 80,
    basis_id: str = DEFAULT_BASIS_ID,
) -> InteractionDiagram:
    """Build a uniaxial N–M diagram by strain compatibility.

    ``member_geometry`` must be exactly ``STRAIGHT_PRISMATIC``.  Curved arch
    ribs, tapered members, hollow sections and biaxial bending remain outside
    this method and are rejected before any number is returned.
    """
    require_straight_prismatic(member_geometry)
    material.validate()
    basis = _screening_basis(basis_id)
    _ = section.depth_mm
    layers = _validated_reinforcement(section, reinforcement, material, basis)
    if not isinstance(sample_count, int) or sample_count < 8:
        raise ColumnCapacityError("sample_count phải là số nguyên >= 8")

    pure_compression = _uniform_point(
        section, material, layers, compression=True, basis=basis
    )
    pure_tension = _uniform_point(
        section, material, layers, compression=False, basis=basis
    )
    tension_layer_depth = max(section.depth_mm / 2.0 - layer.y_mm for layer in layers)
    balanced_depth = tension_layer_depth / (
        1.0 + material.steel_yield_strain / basis.ultimate_concrete_strain
    )
    balanced = _point_from_neutral_axis(
        section,
        material,
        layers,
        balanced_depth,
        label="BALANCED",
        basis=basis,
    )
    pure_bending_depth = _pure_bending_depth(section, material, layers, basis)
    pure_bending = _point_from_neutral_axis(
        section,
        material,
        layers,
        pure_bending_depth,
        label="PURE_BENDING",
        basis=basis,
    )
    maximum_factored_compression, maximum_factored_axial_n = (
        _maximum_factored_compression_point(
            section,
            material,
            layers,
            basis,
            pure_compression,
            pure_bending_depth,
        )
    )

    c_min = section.depth_mm * 1e-4
    c_max = section.depth_mm * 1e4
    logarithmic = [
        c_min * (c_max / c_min) ** (index / (sample_count - 1))
        for index in range(sample_count)
    ]
    sampled = [
        _point_from_neutral_axis(
            section,
            material,
            layers,
            c,
            label="STRAIN_COMPATIBILITY",
            basis=basis,
        )
        for c in logarithmic
    ]
    envelope_samples = [
        point
        for point in sampled
        if point.phi_axial_n <= maximum_factored_axial_n * (1.0 + 1e-12)
    ]
    anchors = [maximum_factored_compression, balanced, pure_bending, pure_tension]
    points = tuple(
        sorted(
            envelope_samples + anchors,
            key=lambda point: (
                -point.phi_axial_n,
                -abs(point.phi_moment_nmm),
                point.label,
            ),
        )
    )
    return InteractionDiagram(
        points=points,
        pure_compression=pure_compression,
        maximum_factored_compression=maximum_factored_compression,
        balanced=balanced,
        pure_bending=pure_bending,
        pure_tension=pure_tension,
        maximum_factored_axial_n=maximum_factored_axial_n,
        basis_id=basis.basis_id,
        basis_source_ref=basis.source_ref,
    )


@dataclass(frozen=True)
class EffectiveLength:
    k: float
    unbraced_length_mm: float
    provenance: EvidenceRef

    def validate(self) -> None:
        if not (
            math.isfinite(self.k)
            and math.isfinite(self.unbraced_length_mm)
            and self.k > 0.0
            and self.unbraced_length_mm > 0.0
        ):
            raise ColumnCapacityError("k và Lu phải hữu hạn, dương")
        if not isinstance(self.provenance, EvidenceRef):
            raise ColumnCapacityError(
                "k cần provenance dạng EvidenceRef; engine không tự đoán k"
            )
        self.provenance.validate("effective_length_provenance")


@dataclass(frozen=True)
class SecondOrderResult:
    status: Literal[
        "SHORT_COLUMN",
        "MAGNIFIED",
        "OUT_OF_METHOD_RANGE",
        "INSTABILITY_LIMIT",
        "NEEDS_SYSTEM_LEVEL_INPUT",
    ]
    slenderness_ratio: float
    slenderness_limit: float
    euler_load_n: float | None
    cm_used: float | None
    magnification: float | None
    magnified_moment_nmm: float | None
    analysis_mode: Literal["NONSWAY_MEMBER", "SWAY_SYSTEM"]
    basis_id: str
    reason: str
    claim_level: Literal["SCREENED"] = "SCREENED"
    design_verdict_authority: Literal["NONE"] = "NONE"


def moment_magnification(
    *,
    member_geometry: str,
    effective_length: EffectiveLength,
    radius_of_gyration_mm: float,
    cracked_ei_n_mm2: float,
    factored_axial_n: float,
    first_order_moment_nmm: float,
    phi_k: float,
    analysis_provenance: EvidenceRef,
    end_moment_ratio_m1_over_m2: float | None = None,
    transverse_load_between_supports: bool | None = None,
    analysis_mode: Literal["NONSWAY_MEMBER", "SWAY_SYSTEM"] = "NONSWAY_MEMBER",
    system_factored_axial_sum_n: float | None = None,
    system_euler_load_sum_n: float | None = None,
    basis_id: str = DEFAULT_BASIS_ID,
) -> SecondOrderResult:
    """Screen member slenderness and apply a bounded magnification method.

    This is not a nonlinear P–Delta analysis.  For a sidesway system, system
    sums must be supplied explicitly; a single member is never silently treated
    as the whole bent or frame.
    """
    require_straight_prismatic(member_geometry)
    effective_length.validate()
    if not isinstance(analysis_provenance, EvidenceRef):
        raise ColumnCapacityError(
            "r, EI, phi_k, moment và tải cần analysis_provenance dạng EvidenceRef"
        )
    analysis_provenance.validate("analysis_provenance")
    basis = _screening_basis(basis_id)
    numeric = (
        radius_of_gyration_mm,
        cracked_ei_n_mm2,
        phi_k,
    )
    if not all(math.isfinite(value) and value > 0.0 for value in numeric):
        raise ColumnCapacityError("r, EI và phi_k phải hữu hạn, dương")
    if not (
        math.isfinite(factored_axial_n)
        and factored_axial_n >= 0.0
        and math.isfinite(first_order_moment_nmm)
    ):
        raise ColumnCapacityError("Pu phải không âm; moment phải hữu hạn")
    if not (0.0 < phi_k <= 1.0):
        raise ColumnCapacityError("phi_k phải nằm trong (0, 1]")

    if analysis_mode == "NONSWAY_MEMBER":
        if system_factored_axial_sum_n is not None or system_euler_load_sum_n is not None:
            raise ColumnCapacityError("NONSWAY_MEMBER không nhận tổng tải của SWAY_SYSTEM")
        if end_moment_ratio_m1_over_m2 is None or not math.isfinite(
            end_moment_ratio_m1_over_m2
        ):
            raise ColumnCapacityError("NONSWAY_MEMBER cần M1/M2 do caller cung cấp")
        if not -1.0 <= end_moment_ratio_m1_over_m2 <= 1.0:
            raise ColumnCapacityError("M1/M2 phải nằm trong [-1, 1]")
        if not isinstance(transverse_load_between_supports, bool):
            raise ColumnCapacityError(
                "NONSWAY_MEMBER phải khai có/không tải ngang giữa hai đầu"
            )
        cm_used = (
            1.0
            if transverse_load_between_supports
            else max(0.4, 0.6 + 0.4 * end_moment_ratio_m1_over_m2)
        )
        slenderness_limit = min(
            40.0,
            34.0 - 12.0 * end_moment_ratio_m1_over_m2,
        )
    elif analysis_mode == "SWAY_SYSTEM":
        if (
            end_moment_ratio_m1_over_m2 is not None
            or transverse_load_between_supports is not None
        ):
            raise ColumnCapacityError(
                "SWAY_SYSTEM dùng delta_s; không được trộn M1/M2 hoặc Cm của delta_b"
            )
        cm_used = None
        slenderness_limit = 22.0
    else:
        raise ColumnCapacityError("analysis_mode không được hỗ trợ")

    slenderness = (
        effective_length.k * effective_length.unbraced_length_mm
        / radius_of_gyration_mm
    )
    if slenderness >= basis.maximum_slenderness:
        return SecondOrderResult(
            status="OUT_OF_METHOD_RANGE",
            slenderness_ratio=slenderness,
            slenderness_limit=slenderness_limit,
            euler_load_n=None,
            cm_used=cm_used,
            magnification=None,
            magnified_moment_nmm=None,
            analysis_mode=analysis_mode,
            basis_id=basis.basis_id,
            reason=(
                f"kLu/r={slenderness:.6g} >= {basis.maximum_slenderness:.6g}; "
                "phương pháp khuếch đại mômen không được ngoại suy"
            ),
        )
    if slenderness <= slenderness_limit:
        return SecondOrderResult(
            status="SHORT_COLUMN",
            slenderness_ratio=slenderness,
            slenderness_limit=slenderness_limit,
            euler_load_n=None,
            cm_used=cm_used,
            magnification=1.0,
            magnified_moment_nmm=first_order_moment_nmm,
            analysis_mode=analysis_mode,
            basis_id=basis.basis_id,
            reason="Độ mảnh không vượt ngưỡng xét hiệu ứng bậc hai",
        )

    member_euler = (
        math.pi**2 * cracked_ei_n_mm2
        / (effective_length.k * effective_length.unbraced_length_mm) ** 2
    )
    if analysis_mode == "SWAY_SYSTEM":
        if system_factored_axial_sum_n is None or system_euler_load_sum_n is None:
            return SecondOrderResult(
                status="NEEDS_SYSTEM_LEVEL_INPUT",
                slenderness_ratio=slenderness,
                slenderness_limit=slenderness_limit,
                euler_load_n=member_euler,
                cm_used=None,
                magnification=None,
                magnified_moment_nmm=None,
                analysis_mode=analysis_mode,
                basis_id=basis.basis_id,
                reason="Sway cần ΣPu và ΣPe của toàn hệ; không thay bằng một cột",
            )
        if not (
            math.isfinite(system_factored_axial_sum_n)
            and math.isfinite(system_euler_load_sum_n)
            and system_factored_axial_sum_n >= 0.0
            and system_euler_load_sum_n > 0.0
        ):
            raise ColumnCapacityError("ΣPu và ΣPe của hệ phải hữu hạn, hợp lệ")
        demand = system_factored_axial_sum_n
        critical = phi_k * system_euler_load_sum_n
        numerator = 1.0
    else:
        demand = factored_axial_n
        critical = phi_k * member_euler
        numerator = cm_used

    critical_ratio = demand / critical
    if critical_ratio >= basis.instability_proximity_ratio:
        return SecondOrderResult(
            status="INSTABILITY_LIMIT",
            slenderness_ratio=slenderness,
            slenderness_limit=slenderness_limit,
            euler_load_n=member_euler,
            cm_used=cm_used,
            magnification=None,
            magnified_moment_nmm=None,
            analysis_mode=analysis_mode,
            basis_id=basis.basis_id,
            reason=(
                f"Pu/(phi_k*Pc)={critical_ratio:.6g} >= "
                f"{basis.instability_proximity_ratio:.6g}; fail-closed gần mất ổn định"
            ),
        )
    magnification = max(1.0, numerator / (1.0 - critical_ratio))
    return SecondOrderResult(
        status="MAGNIFIED",
        slenderness_ratio=slenderness,
        slenderness_limit=slenderness_limit,
        euler_load_n=member_euler,
        cm_used=cm_used,
        magnification=magnification,
        magnified_moment_nmm=magnification * first_order_moment_nmm,
        analysis_mode=analysis_mode,
        basis_id=basis.basis_id,
        reason="Khuếch đại đàn hồi xấp xỉ; không phải phân tích P–Delta phi tuyến",
    )
