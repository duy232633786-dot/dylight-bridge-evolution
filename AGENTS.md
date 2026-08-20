# DYLIGHT Bridge Research Lab — agent contract

This repository is a safety-constrained bridge R&D environment. Before acting,
read `multiagent/PROTOCOL.md`, `multiagent/PHYSICS_GATES.md`, and the task file
you claim.

## Required workflow

If the user gives a new research topic without naming an existing task, route it
through `python -m bridge_evolution.cli lab orchestrate --topic "..."`. Do not
create an informal private plan or bypass the canonical intake/run records.

1. Run `python -m bridge_evolution.cli lab status`.
2. Claim exactly one `READY` task with `lab claim`; edit only its `write_scope`.
3. Keep units, design basis, solver/version, seed, hashes and assumptions explicit.
4. Run relevant tests and preserve raw negative results.
5. Submit a hashed handoff. The CLI mirrors it to Obsidian automatically; a
   different agent must review it.

## Non-negotiable boundaries

- LLMs, NotebookLM, Obsidian notes and surrogate models may propose or rank;
  they never calculate authoritative forces/capacities or issue PASS/FAIL.
- Current built-in L0/L1 output is at most `SCREENED`. Midas/OpenSees L2/L3,
  laboratory tests and field validation are not currently implemented.
- Safety, stability, fatigue, durability, constructability and code constraints
  are hard gates; cost, carbon and aesthetics cannot trade them away.
- A proposer cannot review its own handoff. Only a responsible human engineer
  may authorize technical use; `ENGINEERING_CANDIDATE` is not IFC/build-ready.
- Never add an unverified novel material directly to production catalogs.
- Never store credentials in the repository. Preserve unrelated user changes.
- Every invention, calculation, negative result and durable lesson must be a
  hashed artifact in a handoff and mirrored to Obsidian. A chat transcript alone
  is not retained research knowledge.

Use `python -m pytest tests -q` after code or contract changes.
