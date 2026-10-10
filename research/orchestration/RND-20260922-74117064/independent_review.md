# Independent source and fault-injection review

Reviewer: Codex subagent `/root/audit_pipeline`, separate from implementer.
This is the same platform, not cross-vendor review or engineering approval.

Reviewed module SHA-256:
`5ac2c9e59ef1a60c7aff40b6ee5dd0a1d0b34f7a41f9662079d6dce2a1abf8da`.

First review reproduced four false benchmark PASS cases in the initial patch:
compensating E×2/I÷2 mapping errors; incomplete model-quality check list;
10 m support displacement; forged solver source hash. Raw result self-hashes
were recomputed in memory, so the tests exercised semantic guards rather than
only trivial checksum failure. Findings were sent to the implementer and fixed.

Second review executed an isolated Python assertion script using the bundled
Python and workspace dependencies, PYTHONDONTWRITEBYTECODE=1, exit 0:

| Case | Observed result after fixes |
|---|---|
| Actual h=0.8 m kernel evaluation | PASS / VALID_FOR_BENCHMARK |
| Missing six quality checks | INCONCLUSIVE / INVALID |
| Support N0 uy=10 m | INCONCLUSIVE / INVALID |
| Solver source hash replaced with zeros | INCONCLUSIVE / INVALID |
| E×2/I÷2 compiler fault | INCONCLUSIVE / INVALID, zero solver calls |
| Duplicate probes | Exactly four calls with explicit DISABLED_ALL_PROBES_COUNTED |

Reviewer found no new blocking source issue for the stated B1 scope after these
fixes. Point-load Green's-function reference was independently inspected and
found appropriate to the disclosed discrete loading. Exact inventory/cross-link
code was source-reviewed; root tests additionally execute tamper/restart cases.
In a later independent documentation/evidence review, the same reviewer actually
ran `verify_evidence` on all five packages: all returned INTEGRITY_VERIFIED,
exit 0. Solver counts 3/2/2/0/1 and measured deflections matched the session
report. Two documentation citations were corrected: `evidence()` is in
site/spec.py; GC-05 is a BUILTIN_L1 failure fixture, not an external-solver run.
The identical semantic faults are retained as reproducible tests in
`tests/test_evobridge.py`; review chat alone is not the only record.

Remaining boundary: original production `evaluate_candidate` does not gain these
guards. The review did not certify a standard, unique physical cause, transfer
benefit, arbitrary geometry, live CAD/solver adapter or complete SAGE-EvoBridge.
