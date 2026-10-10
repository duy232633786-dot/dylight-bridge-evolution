# Incremental test matrix

`tests/test_evobridge.py` uses the real existing frame kernel unless a test is
explicitly fault injection. Injected outputs prove guards only, not physics.
`tests/test_frame_f1.py` supplies existing independent analytical kernel tests.
Fresh command logs, counts and exit codes are in the session evidence/handoff.

| Prompt test | Coverage this slice | Boundary |
|---|---|---|
| T01 missing units/material/load | missing-input parametrization | Implemented B1 |
| T02 wrong units/local axis | unit rejection, signed-deflection fault, coordinates audit | Implemented B1 controlled axes |
| T03 disconnected geometry | disconnected-node fault; explicit topology audit | Model/mapping error; general geometry taxonomy deferred |
| T04 timeout/nonconvergence/NaN | named output faults and TimeoutError | Injected timeout handling; no preemptive external-job timeout service |
| T05 dependency invalidation | distinct model/result hashes, self weight recalculated, stale result rejected | No cache; all real calls counted |
| T06 A unapproved component/bounds | height bounds only | A approval deferred |
| T07 B approval gate | None | Deferred |
| T08 valid model, physical violation | baseline real deflection failure with object/load/value/limit | Benchmark constraints only |
| T09 model correction vs design | no model-assumption changes allowed; mapping faults rejected | MODEL_CORRECTION workflow deferred |
| T10 wrong prediction | real .5→.4 height probe yields CONTRADICTED | Single mechanism/context |
| T11 collateral failure | deflection improved but VOLUME fails; no candidate admitted | Implemented B1 |
| T12 missing rule scope | unsupported required checks/fidelity blocked | Approved RuleIR engine deferred; no standard clause invented |
| T13 invalid/mock/stale memory | invalid evidence marked INELIGIBLE | Structured memory retrieval deferred |
| T14 process restart | separate process verifies persisted package | Evidence only, not project-authenticated memory retrieval |
| T15 frozen test | None | Deferred |
| T16 fair memory/no-memory | None | Deferred |
| T17 budget exhausted | reference and failed probe both counted; bounded action list | Implemented B1 |
| T18 attractive but FAIL | feasible benchmark list requires all checks | No aesthetics or cost objective invented |
| T19 checker discrepancy | independently changed reference blocks PASS | No averaging/reconciliation shortcut |
| T20 raw corruption | restart verify; raw tamper; manifest omission; overwrite refused | Hash integrity, not digital signature/authentication |
| T21 hidden ground truth | no diagnosis agent or exposed fault dataset | Deferred, no causal accuracy claim |
| T22 tool instruction injection | extra contract instruction field rejected | Narrow typed input test, not full LLM red-team coverage |

Additional independent review faults: incomplete seven-check set, forged solver
hash, nonzero constrained displacement, compensating E×2/I÷2 mapping errors.
All now block before a benchmark PASS; mapping fault uses zero solver calls.
