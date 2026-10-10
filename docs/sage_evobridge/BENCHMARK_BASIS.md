# SAGE-EvoBridge B1 beam benchmark v1

Source: user master prompt sections 8, 10–14, 18, 20, 25;
IMPLEMENTATION_EXTENSION. These are invented research inputs and explicit
BENCHMARK_CONSTRAINT thresholds, not any TCVN/JRA/AASHTO provision or material approval.

The evaluator extends the existing `frame_f1` kernel with a straight rectangular
Euler–Bernoulli beam, pin and roller, positive downward midpoint load, and
geometry-dependent nodal self weight. SI input units are m, kN, GPa. Area is
b*h; second moment is b*h^3/12; GPa converts to kN/m2 by 1e6.
All nodes have y=0 and local x is the global span axis. One fixed research load
case combines the external load and self weight, with no implied code factors.

Self weight q=b*h*gamma is distributed to nodes by tributary length: q*dx at
interior nodes and q*dx/2 at end supports. This is a **lumped nodal approximation**,
not an exact uniformly distributed member load. The registered analytical
reference evaluates the identical discrete physical loading independently from
the contract, without reading FE nodes, sections, loads, or results.
It sums simply supported beam point-load influence functions at midspan,
computes reactions by statics and maximum moment at midspan by symmetry.
Mesh-refinement tests separately compare against the continuum UDL solution.

The reference relative tolerance is fixed before execution at 1e-7. Model
equilibrium, conditioning, residual, energy and small-displacement guards come
from the existing kernel. Nonconvergence, warnings, missing/nonfinite channels,
stale model mapping or reference discrepancy cannot produce benchmark PASS.

DEFLECTION, elastic STRESS (M/(b*h^2/6)), and VOLUME are mandatory benchmark
constraints. STRESS is not reinforced-concrete or prestressed-concrete capacity.
VOLUME is a research material-use cap, not a fabrication approval.
Requested unsupported checks/fidelity block execution; compliance remains
INCONCLUSIVE and approval remains NOT_REVIEWED even for a benchmark PASS.

Only height is an intervention variable. Span, width, external load, material
properties, supports, thresholds, checks, mesh and solver budget are immutable
within one contract. Every child recalculates area, inertia and self weight;
all checks rerun. Each child is compared to the original reference. This is a
controlled probe runner, not an alternative optimizer to `design_loop`.
Improving deflection supports an intervention hypothesis only in this model;
it does not identify a unique physical cause. No numeric confidence is claimed.

This slice belongs to evaluator benchmark B1. It does not implement branch A
or B, component approval, Revit mapping, memory learning, transfer, code checks,
nonlinear/staged/dynamic/buckling analysis or engineering release. Claim ceiling
remains the kernel's IDEA, design verdict authority NONE.
