# Reproduce the implemented B1 slice

Run from the existing repository checkout; this is not a new standalone project
or a validated wheel release. Use installed dependencies or the verified local
runtime below. Do not install a new solver or invoke an AI API for this demo.

```powershell
$env:PYTHONPATH='D:\BIM  CIM\DỰ ÁN NCKH 2 2026\tmp\bridge_python_deps'
$env:PYTHONUTF8='1'
$b1Python='C:\Users\ADMIN\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$b1Out='research/orchestration/RND-20260922-74117064/evidence/reproduce_'+(Get-Date -Format yyyyMMdd_HHmmss)
& $b1Python -m bridge_evolution.evobridge --contract docs/sage_evobridge/beam_contract.json --initial-height .5 --heights .4 .8 --out $b1Out
& $b1Python -m bridge_evolution.evobridge --verify $b1Out
& $b1Python -m pytest tests/test_evobridge.py tests/test_frame_f1.py -o addopts='' -q
```

Expected behavior: initial deflection failure, first hypothesis contradicted,
second supported in the model, all three benchmark checks satisfied at 0.8 m.
The observed session run required three FE solver calls, including the initial
reference. All probes use the same immutable contract. Cache is disabled;
duplicate probes count as new solver calls. These counts are run-specific and
are not a transfer-efficiency result.

For the budget/collateral/unsupported cases, substitute `budget_contract.json`,
`collateral_contract.json`, or `unsupported_contract.json`; use a fresh output
directory. CLI exit 0 means a benchmark-feasible candidate was found. Exit 2
means a persisted valid negative/inconclusive trajectory; exit 1 is a command/
input/output error. No exit code authorizes engineering release.

Each package contains contract.json, trajectory.json, native solver models,
solver raw results, source/environment metadata and an exact hashed manifest.
The session additionally keeps exact content-addressed source snapshots under
`evidence/source_snapshots/`, including the reused kernel and its schemas/basis.
Run IDs and timestamps change on reproduction; numerical comparisons use the
registered tolerance rather than demanding byte-identical whole reports.
`--verify` checks inventory, bytes and cross-links in a fresh process. A hash is
not a digital signature. Deliberately reauthoring an entire self-hashed package
requires an external trusted handoff/snapshot to detect; the existing Lab handoff
provides a separate recorded artifact hash.

The physical reference uses closed-form superposition of point loads, independent
of stiffness assembly. Self weight uses the documented nodal approximation.
The test suite also shows refinement toward the exact continuous UDL solution;
this supports this model only and is not code/field validation.

Raw session outputs live under
`research/orchestration/RND-20260922-74117064/evidence/`.
The broader existing design-loop runtime and regression logs are preserved in
workspace `artifacts/sage_evobridge_20260923` and copied into the session evidence
before the hashed handoff. The full-suite baseline used a temporary folder name
containing `bridge`, which exposed the old absolute-path keyword classifier test
failure. The isolated test passes with a neutral temporary name. The unchanged
classifier implementation is not silently patched or claimed fixed here.

No production UI change, A/B approval gate, verified engineering memory,
unseen-task transfer, external MIDAS/OpenSees execution, or standards compliance
is implemented by this command. Production `evaluate_candidate` still requires
its own central output guard and provenance-safe integration task.
