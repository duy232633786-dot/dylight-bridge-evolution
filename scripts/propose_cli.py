"""CLI độc lập cho lớp đề xuất AI (BRD-053) — không đụng bridge_evolution/cli.py.

Ví dụ:
  python scripts/propose_cli.py --family super_t_simple_v1 --adapter heuristic --rounds 3 --out .tmp/prop.json
  python scripts/propose_cli.py --family super_t_simple_v1 --adapter http \
      --endpoint http://127.0.0.1:1234/v1 --model qwen2.5-coder-14b --out .tmp/prop_qwen.json
  python scripts/propose_cli.py --family super_t_simple_v1 --adapter cli:codex --rounds 2 --out .tmp/prop_codex.json

Exit code: 0 báo cáo được ghi (dù giả thuyết bị bác — đó là kết quả âm hợp lệ);
2 lỗi hợp đồng/cấu hình; 3 lỗi đối số.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bridge_evolution.proposer import (  # noqa: E402
    ProposerError,
    make_adapter,
    run_proposal_session,
    seed_gene_for_family,
)


def _load_seed(spec: str, family: str) -> dict:
    if spec == "anchor":
        return seed_gene_for_family(family)
    path = Path(spec)
    with open(path, encoding="utf-8") as stream:
        gene = json.load(stream)
    if not isinstance(gene, dict):
        raise ProposerError("File seed gene phải là JSON object {biến: giá trị}")
    return gene


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    parser = argparse.ArgumentParser(description="Phiên đề xuất AI có hợp đồng (bộ não chỉ đề xuất, lab phán quyết)")
    parser.add_argument("--family", required=True)
    parser.add_argument("--adapter", default="heuristic", help="heuristic | http | cli:<codex|claude|opencode|antigravity>")
    parser.add_argument("--seed-gene", default="anchor", help="'anchor' (registry) hoặc đường dẫn JSON")
    parser.add_argument("--objective", default="relative_cost")
    parser.add_argument("--direction", default="min", choices=["min", "max"])
    parser.add_argument("--rounds", type=int, default=None)
    parser.add_argument("--max-evaluations", type=int, default=None)
    parser.add_argument("--proposals-per-round", type=int, default=None)
    parser.add_argument("--improvement-min-rel", type=float, default=None)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--question", default=None)
    parser.add_argument("--endpoint", default=None, help="base URL /v1 cho adapter http (hoặc DYLIGHT_LLM_ENDPOINT)")
    parser.add_argument("--model", default=None, help="tên model cho adapter http (hoặc DYLIGHT_LLM_MODEL)")
    parser.add_argument("--timeout", type=float, default=None)
    parser.add_argument("--out", required=True, help="đường dẫn ghi ProposalSessionReport JSON")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return 3 if exc.code else 0
    try:
        adapter = make_adapter(args.adapter, seed=args.seed, endpoint=args.endpoint, model=args.model,
                               timeout_seconds=args.timeout)
        seed_gene = _load_seed(args.seed_gene, args.family)
        report = run_proposal_session(
            seed_gene, family=args.family, adapter=adapter, objective_key=args.objective,
            direction=args.direction, rounds=args.rounds, max_evaluations=args.max_evaluations,
            proposals_per_round=args.proposals_per_round, improvement_min_rel=args.improvement_min_rel,
            seed=args.seed, question=args.question)
    except ProposerError as exc:
        print(f"LOI HOP DONG: {exc}", file=sys.stderr)
        return 2
    except (OSError, ValueError, KeyError) as exc:
        print(f"LOI: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes((json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    best = report["best"]
    print(f"phien {report['session_id']} | ho {report['family']} | muc {report['study_level']} | "
          f"adapter {report['adapter']['adapter_id']}")
    print(f"seed: {report['seed_assessment']['status']} | objective seed = {report['seed_assessment']['objective_value']}")
    print(f"danh gia da dung: {report['evaluations_used']} | ket qua am: {report['negative_results']} | "
          f"trung lap: {report['duplicates']} | ngoai mien: {report['out_of_domain']}")
    if best:
        print(f"tot nhat: {best['status']} objective = {best['objective_value']} "
              f"(cai thien {best['improvement_rel']}) tim thay o vong {best['found_in_round']}")
    else:
        print("tot nhat: chua co gene SCREENED")
    print(f"ket thuc: {report['termination_reason']} | gia thuyet duoc ung ho: {report['hypothesis_supported']}")
    print(f"bao cao: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
