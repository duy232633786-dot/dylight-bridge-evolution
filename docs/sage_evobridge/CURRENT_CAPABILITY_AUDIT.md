# CURRENT_CAPABILITY_AUDIT — SAGE-EvoBridge, 2026-09-23 ICT

Audit checkout: `dylight-bridge-evolution`, Git HEAD
`5e3b214ae6b6bca46a499f62bb25eaf83d90ace5`. The working tree was already dirty;
HEAD alone does not identify this runtime. Original tracked diff/status and
command logs are preserved under workspace `artifacts/sage_evobridge_20260923`.
No previous source, model, accepted handoff or user report was rewritten.

Environment actually used: Windows, CPython 3.12.14, workspace dependencies
pytest 9.1.1, NumPy 2.5.2, scikit-learn 1.9.0. `python` was absent from PATH;
the bundled interpreter plus existing workspace `tmp/bridge_python_deps` worked.
No dependency installation, model API purchase, CAD execution or solver license
assumption was needed. Raw commands/exit codes and final results are consolidated
in the session handoff, not inferred from old README checkmarks.

Read: AGENTS.md, multiagent/PROTOCOL.md, PHYSICS_GATES.md, README.md,
pyproject.toml, contracts/research_task.schema.json, CLI/orchestrator/lab,
frame_f1/model/result/basis/tests, evaluate/design_loop/verifier/solver paths,
and source inspection by a separate agent of the UI, proposer, knowledge and QD.
Both named proposal DOCX files are absent from the workspace search. `_de_bai.docx`
was read: it is a different graduation bridge design assignment, not either
proposal, and supplies no EvoBridge source claims.

## Actual traced call chain

`dashboard/lab.js` / `lab-cockpit-v2.html` POST `/api/design-loop`
→ `scripts/serve_lab.py::api_design_loop`
→ `design_loop::run_design_loop` → `BudgetedEvaluator.evaluate_prescreened`
→ `evaluate::evaluate_candidate` → `fe_adapter.solver::run_analysis`
→ `line_girder::analyze` → `verifier.rules::verify_candidate`
→ `_finish` / UI run JSON storage. Knowledge cards are queried for repair hints;
there is no demonstrated learned intervention memory in that path.

| Capability | File/symbol | Runtime path | Actual test/command | Evidence | Status | Gap | Decision |
|---|---|---|---|---|---|---|---|
| Lab intake/task/locks | collaboration/lab.py, orchestrator.py; CLI lab | intake → planned DAG → claim | lab status; lab orchestrate; lab claim BRD-054 | intake.json, claim.json; initial lab valid=true | VERIFIED_RUNNING | Planner template cannot amend write_scope; source-based capability planning still limited | KEEP/EXTEND |
| Design genome/constraints | state.py; design_loop.py::run_design_loop | fixed seed inputs/grammar → bounded mutation | existing design_loop GC-06, budget 12 | existing_design_loop.json/.log; exit 0 | VERIFIED_RUNNING | No full two-branch versioned approval library | KEEP |
| L1 solver/repair | line_girder.py; optimization/common.py; design_loop.py | solver → verifier → repair/trim | same actual 12-call loop | final feasible=true in L1, component audit BLOCKED, termination BUDGET_EXHAUSTED | VERIFIED_RUNNING | This is scoped screening, not full code compliance or final engineering candidate | KEEP/EXTEND |
| Direct evaluator output guard | evaluate.py: evaluate_candidate; verifier/rules.py | raw solver values → comparisons | isolated NaN-deflection and nonconverged-status injection on GC-01, exit 0 | legacy_output_guard_probe.json: both return SUCCESS/feasible=true | PARTIAL | Confirmed false-feasible behavior under injected invalid output; direct pipeline does not gain B1 guards | EXTEND urgently |
| Frame/truss solver | frame_f1.py::analyze_frame_model | model JSON → direct stiffness → result JSON | tests/test_frame_f1.py + test_evobridge.py; real B1 calls | focused_03.log: 63 passed; native model/raw/reference artifacts | VERIFIED_RUNNING | Linear 2D Euler–Bernoulli/truss only, claim IDEA | KEEP/WRAP |
| Independent closed form | evobridge.py::reference_response | contract → point-load Green function/statics | numerical benchmark, mesh refinement, discrepancy injection | focused logs + independent_reference in trajectories | VERIFIED_RUNNING | Same discrete physical loading; no field validation or independent licensed solver run | KEEP |
| MIDAS/OpenSees production adapter | fe_adapter/solver.py::run_analysis | target dispatch → SolverError | Source inspection only; external target NOT_RUN | Explicit branches raise SolverError; GC-05 separately tests a BUILTIN_L1 singular fixture, not MIDAS/OpenSees | PARTIAL | Target solver not executed; standalone reference scripts are separate from production dispatch | DEFER |
| OpenSees external benchmark | experiments/validation/opensees_frame_reference_v2.py | isolated reference runner | NOT_RUN this session | source only; old logs not promoted | IMPLEMENTED_UNVERIFIED | Version/license/runtime compatibility not freshly demonstrated | KEEP/DEFER |
| Model-quality / failure / probe | evobridge.py::evaluate_beam, run_interventions | frame native model → guards → benchmark rules → typed failure → probe | real success, contradiction, rejected probe, collateral and budget cases | new evidence packages; test matrix | VERIFIED_RUNNING | B1 only, no general causal diagnosis or confidence calibration | EXTEND |
| DecisionSpec / PSL / skeleton composer | searched bridge_evolution, contracts, scripts | no typed composer found | source search | independent source audit | MISSING | Search bounded to this repository; external DOSCO infrastructure not audited | DEFER |
| Hole map / missing data | site/spec.py::check_site_readiness, evidence | site inputs → evidence blocking | NOT_RUN independently this session | source review; hole-map phrase is a comment, not a composer | PARTIAL | Typed workflow dependency composition absent | KEEP/EXTEND |
| Tool capability inventory | docs/runtime_capability_matrix.json; collaboration/providers.py | inventory / provider discovery | intake doctor version/auth probes only | intake.json separates available/callable/authenticated | PARTIAL | No general per-tool schemas, retry/idempotency/permissions contracts demonstrated | KEEP/EXTEND |
| Revit families / BIM-FEM | revit_family/, docs/revit_family_capability.md | source interfaces | NOT_RUN | source available, no live Revit evidence | IMPLEMENTED_UNVERIFIED | No geometry mapping verification in this session | DEFER |
| Component approval A←B | component audit; catalogs; creative_shape.py | partial supporting primitives | NOT_RUN branch approval | no complete gate located | MISSING | Approval evidence/type versions/research domain must be explicit | EXTEND |
| QD/NSGA-II | creative_shape.py::run_constrained_map_elites; optimization/ | geometric MAP-Elites / production optimization | NOT_RUN as QD benchmark this session | source functions, no fresh coverage experiment | IMPLEMENTED_UNVERIFIED | Geometric QD is not a feasible engineering archive | KEEP/EXTEND |
| Knowledge/cards/logs | knowledge/store.py; handoff/Obsidian exporter | retrieval and persisted reports | lab intake mirror to workspace staging | intake.json | PARTIAL | Cards/log persistence is not verified engineering memory or demonstrated learning | KEEP/EXTEND |
| Structured memory / transfer | no existing verified trajectory retrieval identified | not implemented in B1 slice | NOT_RUN | traceability explicitly pending | MISSING | Frozen/sequential protocols, leakage checks, fair baselines required | DEFER to P4 |
| Immutable B1 raw evidence | evobridge.py::write_evidence, verify_evidence | unique output → manifest → restart verify | subprocess restart, tamper, inventory omission, overwrite tests | focused tests, new manifests | VERIFIED_RUNNING | Hash integrity does not establish authenticity, physics approval or learning | KEEP |

## Priority gaps and next slice

1. Centralize the finite/status/mapping guard in the original production evaluator
   with existing schema compatibility and correction records for accepted artifacts.
   The new B1 wrapper must not be described as fixing that original entrypoint.
   The gap is now runtime-reproduced, not only suspected from source: injecting
   NaN deflection or a NOT_CONVERGED status into otherwise genuine GC-01 solver
   output still returned feasible=true. This is fault-injection evidence of a
   software guard defect, not evidence that the numerical kernel actually emitted
   those invalid outputs in ordinary benchmark runs.
2. Add generalized typed FailureSignature/Hypothesis/InterventionResult to existing
   design_loop trajectories, retaining its grammar, budget/cache and optimizer.
3. Implement A/B identity and scoped Component Approval Gate before new shapes
   enter the production configuration library.
4. Build versioned structured memory and a preregistered frozen transfer harness
   on the validated trajectory; do not claim learning from hash persistence.

P0 is a current-session audit; P1 and P3 have a bounded B1 slice. P2/P4 and the
research program are not complete. Missing proposal sources block their detailed
reconciliation and literature extraction, not the independent benchmark work.
