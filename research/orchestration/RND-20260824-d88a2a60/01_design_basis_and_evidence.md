# Design basis and evidence — Revit V3 open-spandrel RC arch bridge

## Claim boundary

- Task: `RND-d88a2a60-01`
- Claim level: `IDEA`
- Gate: `G0`
- Status of engineering evidence: `CONCEPTUAL_UNVERIFIED`
- Subject: BIM Family V3 for a 160 m conceptual reinforced-concrete arch with an open-spandrel steel truss arrangement.

This report records reproducible BIM geometry and negative findings only. It does not claim structural capacity, compliance, constructability or suitability for technical release.

## Known and traced

The following values came from the saved Revit regeneration/verification result and its hashed QA report:

| Item | Verified BIM value |
|---|---:|
| Generator | `DYLIGHT.ARCH.OPEN_SPANDREL.RC.160M.V3` |
| Family type | `S160000_R18000_RIB1800_D1500-3000_P16` |
| Span / rise | 160.0 m / 18.0 m |
| Family parameters | 84, none missing |
| FreeForm solids | 388 expected / 388 found |
| Hollow RHS/SHS | 268 expected / 268 found |
| Gusset plates | 100 expected / 100 found |
| Concrete elements | 20, including 10 pier-interface parts |
| Steel-to-deck clearance | 0.15 m, clash-free geometrically |
| Crown workline height | 4.15 m |
| Crown clear steel zone | 3.25 m ≥ registered minimum 3.00 m |
| Arch-to-pier intersection | 2/2 pier Family instances |
| Painted faces | 3,400; failures 0 |
| Family bounds | 170.2 × 12.7 × 25.6 m |

The X-bracing members are split into four hollow half-members meeting at a central node; the model no longer represents two full RHS solids passing through each other. The upper steel workline is constrained below the concrete deck soffit.

## Baseline and decision metrics

The V2 baseline had no enforced minimum clear steel zone at the crown and produced a visibly compressed arrangement there. V3 adds `A_Min_Crown_Clear_Steel_Zone = 3.00 m`, reduces the default rise from 21.0 m to 18.0 m and rejects regeneration when the calculated usable crown zone is below the registered minimum.

The G0 BIM acceptance metrics are:

1. `deck_interface_clearance ≥ 0.15 m` and no detected steel/deck intersection.
2. `crown_clear_steel_zone ≥ 3.00 m`.
3. `hollow_RHS_found = hollow_RHS_expected` and no full-member X overlap.
4. `pier_interface_parts = 10` and arch geometry intersects both pier instances.
5. Geometry/design/RFA/project parameter snapshots agree.

V3 passes all five BIM metrics. These metrics are coordination checks, not physics gates.

## Negative result retained

The project-level arch verifier remains `ok = false`; it must not be reported as an accepted complete bridge model. Only 16/22 legacy DirectShape context groups remain. The absent replaced groups are `ARCH_TRANSVERSE_BRACING` and `SUBSTRUCTURE_TOWER_BRACING`; the absent required context groups are `ABUTMENTS_WINGWALLS` and `BACKSTAY_ANCHORS`.

There is also an unresolved 7.0 m vertical coordination mismatch: the existing pier/bearing top is at project z = 41.5 m, while the arch-option deck soffit is at z = 48.5 m. Intersecting springing collars with the raked pier legs does not prove that the deck is supported. An arch-specific pier head or independently verified transition assembly is required.

## Unknown / UNVERIFIED

- Site, alignment, terrain survey and hydraulic envelope.
- Traffic, wind, seismic, thermal, accidental and construction-stage loads.
- Geotechnical profile, rock anchorage and foundation stiffness/capacity.
- Concrete, structural steel, weld, bolt and reinforcement grades.
- Member forces, load distribution and effective buckling lengths.
- Global and local stability, fatigue, vibration and aerodynamic response.
- Gusset, bolt, weld, bearing, diaphragm and springing-node capacity.
- Reinforcement congestion, cover, spacing, anchorage and placement access.
- Erection sequence, temporary works, tolerances, drainage, inspection and maintenance access.
- L2/L3 numerical correlation and independent reproduction.

## Modelling assumptions

- The sketch/render are visual references; dimensions not explicitly labelled by the user are assumptions.
- Twin arch ribs, nominal RHS/SHS sizes, wall thicknesses and plates are LOD 300 coordination placeholders.
- `ElementIntersectsElementFilter` is used only as a geometric pier-interface check.
- TCVN 11823-6:2017 clauses on nominal thickness, bracing, diaphragms, connected crossings, symmetry and eccentricity informed the arrangement. No clause-level capacity or compliance calculation has been completed.

Standard reference: TCVN 11823-6:2017, *Thiết kế cầu đường bộ — Phần 6: Kết cấu thép*, local evidence file `C:/Users/ADMIN/Downloads/TCVN TCVN 118232017/TCVN TCVN 118232017/Tieu_chuan_Quoc_gia_TCVN_11823_2017_ve_thiet_ke_cau_duong_bo_part06.pdf`; official catalogue record: <https://tieuchuan.vsqi.gov.vn/tieuchuan/view?sohieu=TCVN+11823-6%3A2017>.

## Evidence and provenance

| Evidence | SHA-256 |
|---|---|
| Saved project-byte snapshot `Project1_V3_saved.rvt` | `B3D2EDC7122B378913ECD90D231E4D0431DEE5F007EFBC6B692F77635761C103` |
| Saved Family-byte snapshot `BRG_OPEN_SPANDREL_RC_ARCH_160M_01_V3_saved.rfa` | `06E46DA7A8325E3A49C475D8996FA6F91327D997178C5B36AFB80553DE3FA93D` |
| Generator source `ArchFamilyModel.cs` | `BBAB254E54D270986005042DA24E9535AF7BA129A52EE99E4E296F787C582E8E` |
| Built command assembly | `C800E71F03FFB05C2A54BCBCF68097DEE14854DE9EA765458C0AE4E54FE5F677` |
| BIM QA report | `228DD21889036866BF8B1C9637E078DE38AD2B7AB2FB2157C2E2A4ACF9B68DC0` |

Canonical QA source: `../artifacts/revit/BRG_OPEN_SPANDREL_RC_ARCH_160M_01_QA.md` relative to the workspace root (outside this repository). The RVT/RFA digests were calculated from read-only copies made immediately after the verified Revit save.

## Budget and next physics work

- This task budget is restricted to evidence locking and G0 documentation.
- No structural solver budget, seed set or material-test budget is authorized by this report.
- Subsequent tasks must register units, loads, boundary conditions, solver/version, tolerances, seeds and raw-output paths before raising a `SCREENED` claim.
- The 7.0 m pier-head mismatch must be resolved as a separate BIM/structural hypothesis before any complete load path is claimed.

## Falsification / STOP criteria

Reject the current BIM claim and regenerate from traced inputs if any hash changes without a new provenance record, any parameter snapshot drifts, any RHS becomes solid or self-intersecting, deck clearance falls below 0.15 m, the crown clear zone falls below 3.00 m, or either pier-interface intersection is lost.

Stop physics promotion if equilibrium/reaction checks fail, solver convergence fails, required legacy project context remains incomplete, or the 7.0 m pier-head transition has no explicit load-path model. Missing data must remain `UNVERIFIED`; it must not be replaced with invented values.
