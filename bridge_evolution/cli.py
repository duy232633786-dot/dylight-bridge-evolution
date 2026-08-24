"""CLI cho planner (não 1 — Claude) điều khiển hệ bổ trợ.

  python -m bridge_evolution.cli evaluate <design_state.json> [--save-artifacts]
  python -m bridge_evolution.cli diagnose <design_state.json>
  python -m bridge_evolution.cli knowledge --rules SERV-001 [--vars ...] [--text ...]
  python -m bridge_evolution.cli knowledge-export [--vault PATH] [--dry-run]
  python -m bridge_evolution.cli knowledge-import-tcvn <PDF_DIR> [--vault PATH]
  python -m bridge_evolution.cli knowledge-import-notebooklm [--vault PATH]
  python -m bridge_evolution.cli knowledge-theme [--vault PATH] [--dry-run]
  python -m bridge_evolution.cli lab status|doctor|intake|orchestrate|resume|run-status
"""
import argparse
import json
import sys

from .evaluate import evaluate_candidate


def _configure_console_utf8() -> None:
    """Giữ JSON tiếng Việt dùng được trên Windows console mặc định cp1252."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def _load_state(path: str) -> dict:
    with open(path, encoding="utf-8-sig") as f:  # chấp nhận BOM từ PowerShell
        return json.load(f)


def main(argv=None):
    _configure_console_utf8()
    ap = argparse.ArgumentParser(prog="bridge_evolution")
    sub = ap.add_subparsers(dest="cmd", required=True)

    ev = sub.add_parser("evaluate", help="Đánh giá một BridgeDesignState")
    ev.add_argument("state_file")
    ev.add_argument("--save-artifacts", action="store_true")

    dg = sub.add_parser("diagnose", help="Đánh giá + đề xuất nước sửa (kèm card não 2)")
    dg.add_argument("state_file")
    dg.add_argument("--top-k", type=int, default=5)

    kn = sub.add_parser("knowledge", help="Truy vấn thẻ tri thức (não thứ 2)")
    kn.add_argument("--rules", nargs="*", default=None, help="rule_id bị FAIL")
    kn.add_argument("--vars", nargs="*", default=None, help="tên biến thiết kế liên quan")
    kn.add_argument("--text", default=None, help="từ khóa tự do")
    kn.add_argument("--top-k", type=int, default=5)
    kn.add_argument("--approved-only", action="store_true",
                    help="chỉ trả thẻ đã được kỹ sư duyệt")

    ko = sub.add_parser(
        "knowledge-export",
        help="xuất não 2 vào vùng DYLIGHT được quản lý trong Obsidian")
    ko.add_argument(
        "--vault", default=None,
        help="thư mục vault; bỏ trống để auto-discover hoặc dùng DYLIGHT_OBSIDIAN_VAULT")
    ko.add_argument(
        "--managed-folder", default="DYLIGHT Bridge Evolution",
        help="thư mục tương đối được quản lý bên trong vault")
    ko.add_argument("--approved-only", action="store_true",
                    help="chỉ xuất thẻ ENGINEER_APPROVED")
    ko.add_argument("--dry-run", action="store_true",
                    help="chỉ báo thay đổi/xung đột, không ghi file")

    kt = sub.add_parser(
        "knowledge-import-tcvn",
        help="nhập bộ PDF TCVN 11823:2017 vào vùng Standards của Obsidian")
    kt.add_argument("source_dir", help="thư mục chứa các PDF TCVN")
    kt.add_argument(
        "--vault", default=None,
        help="thư mục vault; bỏ trống để auto-discover hoặc dùng DYLIGHT_OBSIDIAN_VAULT")
    kt.add_argument(
        "--managed-folder", default="DYLIGHT Bridge Evolution",
        help="thư mục Brain 2 tương đối bên trong vault")
    kt.add_argument("--dry-run", action="store_true",
                    help="chỉ kiểm tra và báo kế hoạch, không ghi file")

    knb = sub.add_parser(
        "knowledge-import-notebooklm",
        help="nhập snapshot NotebookLM cầu/BIM vào vùng tham khảo Obsidian")
    knb.add_argument("--snapshot", default=None,
                     help="snapshot JSON; mặc định dùng snapshot đóng gói")
    knb.add_argument("--vault", default=None,
                     help="vault; bỏ trống để auto-discover")
    knb.add_argument("--managed-folder", default="DYLIGHT Bridge Evolution")
    knb.add_argument("--dry-run", action="store_true")

    kl = sub.add_parser(
        "knowledge-import-library",
        help="nhập thư viện tài liệu kỹ thuật cục bộ (ổ trong máy + USB) vào Obsidian")
    kl.add_argument("sources", nargs="+",
                    help="một hoặc nhiều thư mục/ổ đĩa nguồn")
    kl.add_argument("--vault", default=None,
                    help="vault; bỏ trống để auto-discover")
    kl.add_argument("--managed-folder", default="DYLIGHT Bridge Evolution")
    kl.add_argument("--library-folder", default="Library",
                    help="thư mục thư viện bên trong vùng được quản lý")
    kl.add_argument("--include-code", action="store_true",
                    help="nhập thêm script lsp/vlx/py/json")
    kl.add_argument("--include-markdown", action="store_true",
                    help="nhập cả .md; mặc định tắt vì Obsidian sẽ index chúng thành note")
    kl.add_argument("--collection-depth", type=int, default=2,
                    help="số cấp thư mục kể từ gốc nguồn dùng làm bộ sưu tập")
    kl.add_argument("--quiet", action="store_true", help="không in tiến độ")
    kl.add_argument("--dry-run", action="store_true",
                    help="chỉ kiểm kê và báo kế hoạch, không ghi file")

    kc = sub.add_parser(
        "knowledge-theme",
        help="bật màu Brain 2 trong Obsidian và cấu hình nhóm màu Graph View")
    kc.add_argument(
        "--vault", default=None,
        help="thư mục vault; bỏ trống để auto-discover hoặc dùng DYLIGHT_OBSIDIAN_VAULT")
    kc.add_argument("--dry-run", action="store_true",
                    help="chỉ kiểm tra và báo kế hoạch, không ghi file")

    lab = sub.add_parser(
        "lab", help="điều phối Bridge Research Lab đa tác tử")
    lab_sub = lab.add_subparsers(dest="lab_cmd", required=True)
    lab_sub.add_parser("status", help="trạng thái task, adapter và CLI")
    lab_sub.add_parser("validate", help="kiểm schema, dependency, hash và reviewer")
    lab_sub.add_parser("doctor", help="probe CLI/auth cho bốn provider, không chạy agent")

    lab_intake = lab_sub.add_parser("intake", help="lưu một đề tài thành brief canonical")
    lab_intake.add_argument("--topic", required=True)
    lab_intake.add_argument("--objective", action="append", default=[])
    lab_intake.add_argument("--constraint", action="append", default=[])
    lab_intake.add_argument("--requested-by", default="project_owner")
    lab_intake.add_argument("--plan-only", action="store_true")
    lab_intake.add_argument("--max-tasks", type=int, default=5)
    lab_intake.add_argument("--max-parallel", type=int, default=1)
    lab_intake.add_argument("--max-retries", type=int, default=1)
    lab_intake.add_argument("--task-timeout", type=int, default=1800)
    lab_intake.add_argument("--wall-time", type=int, default=21600)

    lab_plan = lab_sub.add_parser("plan", help="materialize task DAG cho brief đã lưu")
    lab_plan.add_argument("brief_id")
    lab_plan.add_argument(
        "--provider-policy", choices=["STRICT_MULTI_VENDOR", "AVAILABLE_WITH_FALLBACK"],
        default="STRICT_MULTI_VENDOR")

    lab_orchestrate = lab_sub.add_parser(
        "orchestrate", help="tiếp nhận + lập kế hoạch; thêm --execute để chạy agent")
    lab_orchestrate.add_argument("--topic", required=True)
    lab_orchestrate.add_argument("--objective", action="append", default=[])
    lab_orchestrate.add_argument("--constraint", action="append", default=[])
    lab_orchestrate.add_argument("--requested-by", default="project_owner")
    lab_orchestrate.add_argument("--max-tasks", type=int, default=5)
    lab_orchestrate.add_argument("--max-parallel", type=int, default=1)
    lab_orchestrate.add_argument("--max-retries", type=int, default=1)
    lab_orchestrate.add_argument("--task-timeout", type=int, default=1800)
    lab_orchestrate.add_argument("--wall-time", type=int, default=21600)
    lab_orchestrate.add_argument(
        "--provider-policy", choices=["STRICT_MULTI_VENDOR", "AVAILABLE_WITH_FALLBACK"],
        default="STRICT_MULTI_VENDOR")
    lab_orchestrate.add_argument("--execute", action="store_true")
    lab_orchestrate.add_argument("--vault", default=None)

    lab_resume = lab_sub.add_parser("resume", help="tiếp tục một run đã dừng có kiểm soát")
    lab_resume.add_argument("run_id")
    lab_resume.add_argument("--execute", action="store_true")
    lab_resume.add_argument("--vault", default=None)

    lab_recover = lab_sub.add_parser(
        "recover", help="authorize retry/reassign có giới hạn cho FAILED + BLOCKED")
    lab_recover.add_argument("run_id")
    lab_recover.add_argument("task_id")
    lab_recover.add_argument("--authorized-by", required=True,
                             help="phải khớp requested_by của research brief")
    lab_recover.add_argument("--reason", required=True)
    lab_recover.add_argument(
        "--provider", choices=["codex", "claude", "opencode", "antigravity"],
        default=None, help="giữ provider hiện tại nếu bỏ trống")
    lab_recover.add_argument("--grant-attempts", type=int, default=1)

    lab_repair_review = lab_sub.add_parser(
        "repair-orphaned-review",
        help="fail-closed REVIEW->ACTIVE khi unauthorized handoff đã quarantine")
    lab_repair_review.add_argument("run_id")
    lab_repair_review.add_argument("task_id")
    lab_repair_review.add_argument("--authorized-by", required=True,
                                   help="phải khớp requested_by của research brief")
    lab_repair_review.add_argument("--reason", required=True)
    lab_repair_review.add_argument("--quarantined-handoff", required=True,
                                   help="đường dẫn lab-relative trong unauthorized_handoffs")
    lab_repair_review.add_argument("--quarantine-sha256", required=True)
    lab_repair_review.add_argument("--attempt", type=int, required=True)

    lab_quarantine_attempt = lab_sub.add_parser(
        "quarantine-contaminated-attempt",
        help="fail-closed repair cho failed attempt đã ghi canonical state ngoài scope",
    )
    lab_quarantine_attempt.add_argument("run_id")
    lab_quarantine_attempt.add_argument("task_id")
    lab_quarantine_attempt.add_argument("--attempt", type=int, required=True)
    lab_quarantine_attempt.add_argument(
        "--authorized-by", required=True,
        help="phải khớp requested_by của research brief",
    )
    lab_quarantine_attempt.add_argument("--reason", required=True)
    lab_quarantine_attempt.add_argument(
        "--manifest", required=True,
        help="file JSON array chứa exact {path,sha256,disposition} entries",
    )

    lab_run_status = lab_sub.add_parser("run-status", help="xem trạng thái một orchestration run")
    lab_run_status.add_argument("run_id")

    lab_sync = lab_sub.add_parser(
        "sync-obsidian", help="lưu task/handoff/review vào Research Lab trong Obsidian")
    lab_sync.add_argument("--vault", default=None)
    lab_sync.add_argument("--dry-run", action="store_true")

    lab_brief = lab_sub.add_parser("brief", help="sinh brief dùng chung cho một agent")
    lab_brief.add_argument("--agent", required=True)

    lab_claim = lab_sub.add_parser("claim", help="nhận độc quyền một task READY")
    lab_claim.add_argument("task_id")
    lab_claim.add_argument("--agent", required=True)

    lab_amend = lab_sub.add_parser(
        "amend-task",
        help="re-scope task chưa claim bằng amendment bất biến có pre-hash",
    )
    lab_amend.add_argument("task_id")
    lab_amend.add_argument(
        "--changes", required=True,
        help="file JSON object ánh xạ field được phép sang giá trị mới",
    )
    lab_amend.add_argument("--reason", required=True)
    lab_amend.add_argument("--authorized-by", required=True)
    lab_amend.add_argument("--pre-task-sha256", required=True)

    lab_submit = lab_sub.add_parser("submit", help="nộp handoff có hash để review độc lập")
    lab_submit.add_argument("task_id")
    lab_submit.add_argument("--agent", required=True)
    lab_submit.add_argument("--role", required=True)
    lab_submit.add_argument("--summary", required=True)
    lab_submit.add_argument("--claim-level", required=True)
    lab_submit.add_argument("--gates", nargs="*", default=[])
    lab_submit.add_argument("--artifact", action="append", required=True)
    lab_submit.add_argument("--artifact-kind", default="report")
    lab_submit.add_argument("--assumption", action="append", default=[])
    lab_submit.add_argument("--risk", action="append", default=[])
    lab_submit.add_argument("--next-action", default="Independent review")
    lab_submit.add_argument("--vault", default=None,
                            help="vault nhận bản ghi nghiên cứu; mặc định auto-discover")

    lab_review = lab_sub.add_parser("review", help="review độc lập một handoff")
    lab_review.add_argument("task_id")
    lab_review.add_argument("--agent", required=True, help="reviewer_id, phải khác owner")
    lab_review.add_argument("--decision", choices=["APPROVE", "REVISE", "REJECT"], required=True)
    lab_review.add_argument("--findings", required=True,
                            help="JSON chứa mảng {gate,status,evidence}")
    lab_review.add_argument("--notes", required=True)
    lab_review.add_argument("--vault", default=None,
                            help="vault nhận bản ghi review; mặc định auto-discover")

    lab_correct = lab_sub.add_parser(
        "correct-provenance",
        help="ghi incident + snapshot bất biến + correction handoff; vẫn chờ review độc lập")
    lab_correct.add_argument("task_id")
    lab_correct.add_argument("--agent", required=True)
    lab_correct.add_argument("--handoff", required=True,
                             help="đường dẫn project-relative tới handoff lịch sử")
    lab_correct.add_argument("--artifact", required=True,
                             help="artifact project-relative đã drift")
    lab_correct.add_argument("--snapshot-source", required=True,
                             help="file chứa đúng bytes tại recorded hash")
    lab_correct.add_argument("--reason", required=True)
    lab_correct.add_argument("--summary", required=True)
    lab_correct.add_argument(
        "--verification-command", action="append", required=True,
        help='JSON array argv đã chạy, ví dụ ["python","-m","pytest","tests/x.py","-q"]')
    lab_correct.add_argument("--assumption", action="append", default=[])
    lab_correct.add_argument("--risk", action="append", default=[])

    lab_correction_review = lab_sub.add_parser(
        "review-provenance", help="review độc lập correction handoff bất biến")
    lab_correction_review.add_argument("correction_id")
    lab_correction_review.add_argument("--agent", required=True)
    lab_correction_review.add_argument(
        "--decision", choices=["APPROVE", "REVISE", "REJECT"], required=True)
    lab_correction_review.add_argument("--finding", action="append", required=True)
    lab_correction_review.add_argument("--notes", required=True)

    cs = sub.add_parser("compute-section", help="Tính toán đặc trưng hình học tiết diện Super-T tham số")
    cs.add_argument("--depth", type=float, default=1.75, help="Chiều cao dầm (m)")
    cs.add_argument("--top-flange-width", type=float, default=2.06, help="Bề rộng cánh trên (m)")
    cs.add_argument("--top-flange-thickness", type=float, default=0.09, help="Chiều dày cánh trên (m)")
    cs.add_argument("--bottom-width", type=float, default=0.74, help="Bề rộng đáy dầm (m)")
    cs.add_argument("--bottom-thickness", type=float, default=0.25, help="Chiều dày đáy dầm (m)")
    cs.add_argument("--web-thickness", type=float, default=0.10, help="Chiều dày sườn dầm (m)")
    cs.add_argument("--fem", action="store_true", help="Chạy phân tích FEA 2D qua sectionproperties")

    eifc = sub.add_parser("export-ifc", help="Xuất mô hình Open BIM IFC 4.3 Bridge từ BridgeDesignState")
    eifc.add_argument("state_file", help="Đường dẫn file BridgeDesignState JSON")
    eifc.add_argument("-o", "--output", default="bridge_model.ifc", help="Đường dẫn file .ifc đầu ra")

    opymoo = sub.add_parser("optimize-pymoo", help="Chạy tối ưu hóa đa mục tiêu với pymoo NSGA-II")
    opymoo.add_argument("--budget", type=int, default=600, help="Ngân sách gọi solver tối đa")
    opymoo.add_argument("--pop-size", type=int, default=40, help="Kích thước quần thể")
    opymoo.add_argument("--seed", type=int, default=42, help="Random seed")
    opymoo.add_argument("--grammar", default="super_t_simple_v1", help="ID của design grammar")

    args = ap.parse_args(argv)

    if args.cmd == "evaluate":
        result = evaluate_candidate(_load_state(args.state_file),
                                    save_artifacts=args.save_artifacts)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result["feasible"] else 1

    if args.cmd == "diagnose":
        from .analysis import suggest_repairs
        from .knowledge import load_card_audit
        state = _load_state(args.state_file)
        result = evaluate_candidate(state)
        repairs = ([] if result["status"] == "SCHEMA_INVALID" else
                   suggest_repairs(state, result, top_k=args.top_k))
        audit = load_card_audit()
        if audit:
            for repair in repairs:
                card_id = repair.get("card_id")
                if card_id in audit["cards"]:
                    repair["knowledge_audit"] = {
                        "audit_id": audit["audit_id"],
                        **audit["cards"][card_id],
                    }
        print(json.dumps({"case_id": result["case_id"], "status": result["status"],
                          "feasible": result["feasible"],
                          "violations": result["violations"],
                          "suggested_repairs": repairs},
                         indent=2, ensure_ascii=False))
        return 0 if result["feasible"] else 1

    if args.cmd == "knowledge":
        from .knowledge import load_card_audit, query_knowledge
        hits = query_knowledge(failed_rules=args.rules, variables=args.vars,
                               text=args.text, top_k=args.top_k,
                               include_draft=not args.approved_only)
        audit = load_card_audit()
        if audit:
            for hit in hits:
                card_id = hit["card"]["card_id"]
                if card_id in audit["cards"]:
                    hit["knowledge_audit"] = {
                        "audit_id": audit["audit_id"],
                        **audit["cards"][card_id],
                    }
        print(json.dumps(hits, indent=2, ensure_ascii=False))
        return 0

    if args.cmd == "knowledge-export":
        from .knowledge import export_obsidian_vault
        try:
            result = export_obsidian_vault(
                args.vault, managed_folder=args.managed_folder,
                include_draft=not args.approved_only, dry_run=args.dry_run)
        except (FileNotFoundError, OSError, ValueError) as exc:
            print(json.dumps({"status": "ERROR", "error": str(exc)},
                             indent=2, ensure_ascii=False), file=sys.stderr)
            return 2
        result["status"] = "CONFLICT" if result["conflicts"] else "SUCCESS"
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 3 if result["conflicts"] else 0

    if args.cmd == "knowledge-import-tcvn":
        from .knowledge import import_tcvn_collection
        try:
            result = import_tcvn_collection(
                args.source_dir, args.vault,
                managed_folder=args.managed_folder, dry_run=args.dry_run)
        except (FileNotFoundError, OSError, RuntimeError, ValueError) as exc:
            print(json.dumps({"status": "ERROR", "error": str(exc)},
                             indent=2, ensure_ascii=False), file=sys.stderr)
            return 2
        result["status"] = "CONFLICT" if result["conflicts"] else "SUCCESS"
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 3 if result["conflicts"] else 0

    if args.cmd == "knowledge-import-notebooklm":
        from .knowledge import import_notebooklm_snapshot
        try:
            result = import_notebooklm_snapshot(
                args.vault, snapshot_path=args.snapshot,
                managed_folder=args.managed_folder, dry_run=args.dry_run)
        except (FileNotFoundError, OSError, ValueError) as exc:
            print(json.dumps({"status": "ERROR", "error": str(exc)},
                             indent=2, ensure_ascii=False), file=sys.stderr)
            return 2
        result["status"] = "CONFLICT" if result["conflicts"] else "SUCCESS"
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 3 if result["conflicts"] else 0

    if args.cmd == "knowledge-import-library":
        from .knowledge import import_local_library
        reporter = None if args.quiet else (
            lambda message: print(message, file=sys.stderr, flush=True))
        try:
            result = import_local_library(
                args.sources, vault_dir=args.vault,
                managed_folder=args.managed_folder,
                library_folder=args.library_folder,
                include_code=args.include_code,
                include_markdown=args.include_markdown,
                collection_depth=args.collection_depth,
                dry_run=args.dry_run, progress=reporter)
        except (FileNotFoundError, OSError, ValueError) as exc:
            print(json.dumps({"status": "ERROR", "error": str(exc)},
                             indent=2, ensure_ascii=False), file=sys.stderr)
            return 2
        result["status"] = "CONFLICT" if result["conflicts"] else "SUCCESS"
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 3 if result["conflicts"] else 0

    if args.cmd == "knowledge-theme":
        from .knowledge import configure_obsidian_colors
        try:
            result = configure_obsidian_colors(args.vault, dry_run=args.dry_run)
        except (FileNotFoundError, OSError, ValueError) as exc:
            print(json.dumps({"status": "ERROR", "error": str(exc)},
                             indent=2, ensure_ascii=False), file=sys.stderr)
            return 2
        result["status"] = "CONFLICT" if result["conflicts"] else "SUCCESS"
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 3 if result["conflicts"] else 0

    if args.cmd == "lab":
        from .collaboration import (
            amend_task_contract, build_agent_brief, claim_task,
            export_research_to_obsidian,
            create_research_brief, intake_and_plan, lab_status,
            orchestration_status, plan_research, provider_doctor,
            record_provenance_correction, recover_failed_task,
            quarantine_contaminated_attempt, repair_orphaned_review, review_handoff,
            review_provenance_correction, run_orchestration, set_knowledge_sync,
            submit_handoff, validate_lab,
        )
        try:
            if args.lab_cmd == "status":
                print(json.dumps(lab_status(), indent=2, ensure_ascii=False))
                return 0
            if args.lab_cmd == "validate":
                result = validate_lab()
                print(json.dumps(result, indent=2, ensure_ascii=False))
                return 0 if result["valid"] else 1
            if args.lab_cmd == "doctor":
                print(json.dumps(provider_doctor(), indent=2, ensure_ascii=False))
                return 0
            if args.lab_cmd == "intake":
                result = create_research_brief(
                    args.topic,
                    objectives=args.objective or None,
                    constraints=args.constraint or None,
                    requested_by=args.requested_by,
                    autonomy_mode="PLAN_ONLY" if args.plan_only else "DIGITAL_AUTO",
                    max_tasks=args.max_tasks, max_parallel=args.max_parallel,
                    max_retries=args.max_retries, task_timeout_seconds=args.task_timeout,
                    wall_time_seconds=args.wall_time,
                )
                print(json.dumps(result, indent=2, ensure_ascii=False))
                return 0
            if args.lab_cmd == "plan":
                result = plan_research(args.brief_id, provider_policy=args.provider_policy)
                print(json.dumps(result, indent=2, ensure_ascii=False))
                return 0
            if args.lab_cmd == "orchestrate":
                created = intake_and_plan(
                    args.topic,
                    objectives=args.objective or None,
                    constraints=args.constraint or None,
                    requested_by=args.requested_by,
                    max_tasks=args.max_tasks, max_parallel=args.max_parallel,
                    max_retries=args.max_retries, task_timeout_seconds=args.task_timeout,
                    wall_time_seconds=args.wall_time,
                    provider_policy=args.provider_policy,
                )
                advanced = run_orchestration(created["run"]["run_id"], execute=args.execute)
                try:
                    obsidian = export_research_to_obsidian(args.vault)
                    sync_state = "CONFLICT" if obsidian["conflicts"] else "SYNCED"
                    set_knowledge_sync(created["run"]["run_id"], sync_state)
                    if sync_state == "SYNCED":
                        obsidian = export_research_to_obsidian(args.vault)
                except (FileNotFoundError, OSError, RuntimeError, ValueError) as exc:
                    obsidian = {"status": "PENDING", "error": str(exc)}
                print(json.dumps({**created, "status": advanced, "obsidian": obsidian},
                                 indent=2, ensure_ascii=False))
                return 0 if not args.execute or advanced["run"]["status"] == "DIGITAL_COMPLETE" else 4
            if args.lab_cmd == "resume":
                advanced = run_orchestration(args.run_id, execute=args.execute)
                try:
                    obsidian = export_research_to_obsidian(args.vault)
                    sync_state = "CONFLICT" if obsidian["conflicts"] else "SYNCED"
                    set_knowledge_sync(args.run_id, sync_state)
                    if sync_state == "SYNCED":
                        obsidian = export_research_to_obsidian(args.vault)
                except (FileNotFoundError, OSError, RuntimeError, ValueError) as exc:
                    obsidian = {"status": "PENDING", "error": str(exc)}
                print(json.dumps({"status": advanced, "obsidian": obsidian},
                                 indent=2, ensure_ascii=False))
                return 0 if not args.execute or advanced["run"]["status"] == "DIGITAL_COMPLETE" else 4
            if args.lab_cmd == "recover":
                result = recover_failed_task(
                    args.run_id, args.task_id,
                    authorized_by=args.authorized_by,
                    reason=args.reason,
                    provider=args.provider,
                    grant_attempts=args.grant_attempts,
                )
                print(json.dumps(result, indent=2, ensure_ascii=False))
                return 0
            if args.lab_cmd == "repair-orphaned-review":
                result = repair_orphaned_review(
                    args.run_id, args.task_id,
                    authorized_by=args.authorized_by,
                    reason=args.reason,
                    quarantined_handoff=args.quarantined_handoff,
                    quarantine_sha256=args.quarantine_sha256,
                    attempt=args.attempt,
                )
                print(json.dumps(result, indent=2, ensure_ascii=False))
                return 0
            if args.lab_cmd == "quarantine-contaminated-attempt":
                manifest = _load_state(args.manifest)
                if not isinstance(manifest, list):
                    raise ValueError("--manifest phải chứa một JSON array")
                result = quarantine_contaminated_attempt(
                    args.run_id, args.task_id,
                    attempt=args.attempt,
                    authorized_by=args.authorized_by,
                    reason=args.reason,
                    manifest=manifest,
                )
                print(json.dumps(result, indent=2, ensure_ascii=False))
                return 0
            if args.lab_cmd == "run-status":
                print(json.dumps(orchestration_status(args.run_id), indent=2,
                                 ensure_ascii=False))
                return 0
            if args.lab_cmd == "sync-obsidian":
                result = export_research_to_obsidian(
                    args.vault, dry_run=args.dry_run)
                result["status"] = "CONFLICT" if result["conflicts"] else "SUCCESS"
                print(json.dumps(result, indent=2, ensure_ascii=False))
                return 3 if result["conflicts"] else 0
            if args.lab_cmd == "brief":
                print(build_agent_brief(args.agent), end="")
                return 0
            if args.lab_cmd == "claim":
                print(json.dumps(claim_task(args.task_id, args.agent), indent=2,
                                 ensure_ascii=False))
                return 0
            if args.lab_cmd == "amend-task":
                changes = _load_state(args.changes)
                if not isinstance(changes, dict):
                    raise ValueError("--changes phải chứa một JSON object")
                result = amend_task_contract(
                    args.task_id,
                    changes,
                    reason=args.reason,
                    authorized_by=args.authorized_by,
                    expected_pre_task_sha256=args.pre_task_sha256,
                )
                print(json.dumps(result, indent=2, ensure_ascii=False))
                return 0
            if args.lab_cmd == "submit":
                handoff = submit_handoff(
                    args.task_id, args.agent, args.role, args.summary,
                    args.claim_level, args.gates, args.artifact,
                    artifact_kind=args.artifact_kind,
                    assumptions=args.assumption, unresolved_risks=args.risk,
                    next_action=args.next_action)
                try:
                    obsidian = export_research_to_obsidian(args.vault)
                except (FileNotFoundError, OSError, RuntimeError, ValueError) as exc:
                    print(json.dumps({
                        "status": "OBSIDIAN_SYNC_PENDING",
                        "canonical_handoff_saved": True,
                        "handoff": handoff,
                        "error": str(exc),
                    }, indent=2, ensure_ascii=False), file=sys.stderr)
                    return 2
                status = "CONFLICT" if obsidian["conflicts"] else "SUCCESS"
                print(json.dumps({"status": status, "handoff": handoff,
                                  "obsidian": obsidian}, indent=2,
                                 ensure_ascii=False))
                return 3 if obsidian["conflicts"] else 0
            if args.lab_cmd == "review":
                findings = _load_state(args.findings)
                if not isinstance(findings, list):
                    raise ValueError("--findings phải là một JSON array")
                review = review_handoff(
                    args.task_id, args.agent, args.decision, findings, args.notes)
                try:
                    obsidian = export_research_to_obsidian(args.vault)
                except (FileNotFoundError, OSError, RuntimeError, ValueError) as exc:
                    print(json.dumps({
                        "status": "OBSIDIAN_SYNC_PENDING",
                        "canonical_review_saved": True,
                        "review": review,
                        "error": str(exc),
                    }, indent=2, ensure_ascii=False), file=sys.stderr)
                    return 2
                status = "CONFLICT" if obsidian["conflicts"] else "SUCCESS"
                print(json.dumps({"status": status, "review": review,
                                  "obsidian": obsidian}, indent=2,
                                 ensure_ascii=False))
                return 3 if obsidian["conflicts"] else 0
            if args.lab_cmd == "correct-provenance":
                commands = []
                for encoded in args.verification_command:
                    command = json.loads(encoded)
                    if not isinstance(command, list) or not all(
                        isinstance(item, str) and item for item in command
                    ):
                        raise ValueError("--verification-command phải là JSON argv array")
                    commands.append(command)
                result = record_provenance_correction(
                    args.task_id, args.agent, args.handoff, args.artifact,
                    args.snapshot_source, args.reason, args.summary, commands,
                    assumptions=args.assumption, unresolved_risks=args.risk,
                )
                print(json.dumps(result, indent=2, ensure_ascii=False))
                return 0
            if args.lab_cmd == "review-provenance":
                result = review_provenance_correction(
                    args.correction_id, args.agent, args.decision,
                    args.finding, args.notes,
                )
                print(json.dumps(result, indent=2, ensure_ascii=False))
                return 0
        except (FileExistsError, FileNotFoundError, OSError, PermissionError, RuntimeError,
                KeyError, ValueError) as exc:
            print(json.dumps({"status": "ERROR", "error": str(exc)},
                             indent=2, ensure_ascii=False), file=sys.stderr)
            return 2
    if args.cmd == "compute-section":
        from .geometry_parametric import compute_super_t_section_properties
        res = compute_super_t_section_properties(
            depth_m=args.depth,
            top_flange_width_m=args.top_flange_width,
            top_flange_thickness_m=args.top_flange_thickness,
            bottom_width_m=args.bottom_width,
            bottom_thickness_m=args.bottom_thickness,
            web_thickness_m=args.web_thickness,
            use_sectionproperties_fem=args.fem,
        )
        print(json.dumps(res.to_catalog_dict(), indent=2, ensure_ascii=False))
        return 0

    if args.cmd == "export-ifc":
        from .bim import export_bridge_to_ifc
        state = _load_state(args.state_file)
        eval_res = evaluate_candidate(state)
        out_path = export_bridge_to_ifc(state, args.output, evaluation_result=eval_res)
        print(json.dumps({
            "status": "SUCCESS",
            "ifc_file": str(out_path),
            "file_size_bytes": out_path.stat().st_size,
            "span_m": state["project_inputs"]["span_length_m"],
            "girder_count": state["design_variables"]["girder_count"],
        }, indent=2, ensure_ascii=False))
        return 0

    if args.cmd == "optimize-pymoo":
        from .optimization.pymoo_adapter import run_pymoo_optimization
        res = run_pymoo_optimization(
            budget=args.budget,
            pop_size=args.pop_size,
            seed=args.seed,
            grammar_id=args.grammar,
        )
        report = {
            "algorithm": res["algorithm"],
            "seed": res["seed"],
            "counters": res["counters"],
            "pareto_solutions_count": res["pareto_solutions_count"],
            "pareto_solutions": res["pareto_solutions"],
        }
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
