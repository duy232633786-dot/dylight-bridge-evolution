# 09 — Lớp đề xuất AI có hợp đồng: phòng lab ảo cần gì để đưa "bộ não AI" vào sáng tạo

Task: BRD-053. Trần claim: SCREENED. Bộ não AI không có quyền phán quyết.

## 1. Câu hỏi và câu trả lời ngắn

**Câu hỏi:** một phòng lab ảo như DYLIGHT cần những gì để đưa một bộ não AI vào
sáng tạo cấu kiện cầu cho tốt nhất?

**Trả lời ngắn:** bộ não AI chỉ đáng tin khi nó bị bao bởi bốn thứ, theo đúng
thứ tự ưu tiên:

1. **Miền hành động đóng** (grammar/genome): AI chỉ được chọn giá trị trong miền
   đã khai, không tự bịa biến. Đã có cho 5 họ (`bridge_grammar/*.json`).
2. **Bộ đánh giá độc lập, tách hai tầng**: *claim* chỉ từ cổng
   `design_study.assess_candidate` (schema → L0 → applicability registry neo hash →
   site/evidence → L1 → verifier); *phản hồi vật lý* để bộ não học từ
   `evaluate_candidate` + independent verifier (violations, utilization,
   objectives). Đã có cho Super‑T/I ở L1; dầm hộp chỉ L0.
3. **Phản hồi có cấu trúc + trí nhớ lineage**: AI phải nhìn thấy rule nào vi
   phạm, margin bao nhiêu, nước nào đã bị từ chối, thẻ tri thức nào gợi ý gì.
   Trước BRD-053 lab chưa có hợp đồng này; nay có `contracts/ai_proposal.schema.json`.
4. **Pre-registration + falsification**: mỗi phiên khóa câu hỏi, ngân sách, tiêu
   chí thành công/bác bỏ trước vòng 1, giữ kết quả âm. Nay có trong báo cáo phiên.

Thứ bị THIẾU nhiều nhất không phải LLM tốt hơn, mà là **phản hồi vật lý cho
những họ cấu kiện anh muốn sáng tạo** (dầm hộp, đúc hẫng): registry cấm L1 cho
hộp vì BUILTIN_L1 không mô hình xoắn/phân bố ngang; cầu nối MIDAS (BRD-052, đã
ACCEPTED) mới xuất hình học một chiều, chưa đọc kết quả về. Không có phản hồi thì
bộ não nào cũng chỉ "đoán đẹp".

## 2. Hiện trạng theo ma trận năng lực (`docs/runtime_capability_matrix.json`)

| Trạng thái | Năng lực | Ý nghĩa với bộ não AI |
|---|---|---|
| PRESENT | GRAMMAR_V1/V2, L0_LAYOUT_RULES, L1_LINE_GIRDER_SOLVER, INDEPENDENT_VERIFIER, EVALUATION_CONTRACT, OPTIMIZATION_BUILTIN, KNOWLEDGE_CARD_STORE | Đủ để AI đề xuất và nhận phản hồi L1 cho Super‑T/I |
| PARTIAL | L0_FABRICATION_RULES, SECTION_FEA_2D, OPTIMIZATION_PYMOO, KNOWLEDGE_AUDIT, COMPONENT_AUDIT_ORCHESTRATION | Có dùng được nhưng chưa phủ hết họ/điều khoản |
| ABSENT | SOLVER_MIDAS_CIVIL, GRILLAGE_3D, STAGED_PRESTRESS_EFFECTS, ENGINEER_APPROVED_KNOWLEDGE, PHYSICAL_TEST_EVIDENCE, GRAMMAR_V2_ORACLE | Dầm hộp/đúc hẫng chưa có phản hồi L2; 20/20 thẻ tri thức đang DRAFT |

Bộ não hiện có trong repo trước BRD-053: `rl_env` (Q-learning + shield L0) và
`surrogate` (FeasibilitySurrogate) — đều không phải LLM; `lab orchestrate` dùng
LLM làm *lập trình viên/reviewer* (codex/claude/opencode), không phải người đề
xuất thiết kế. `grep` toàn package không thấy dòng nào nối LLM vào vòng gene.

### 2b. Phát hiện khi nối dây: cổng claim đang chặn L1 của Super‑T

Chạy gene neo Super‑T (`model_applicability.json`, anchor_gene) qua
`assess_candidate(study_level="L1_STRUCTURAL", site_profile=None)` ngày
2026‑09‑04 cho `BLOCKED` với hai blocker có nguồn:

| Mã | Ý nghĩa | Cách gỡ (ngoài phạm vi BRD-053) |
|---|---|---|
| `APP-EVIDENCE-001` | `domain_evidence.status` của họ là PARTIAL: cận số S, ts, L, Kg chưa đối chiếu trên bản tiêu chuẩn chính thức → L1 phải BLOCKED | Đối chiếu cận số với TCVN 11823/AASHTO bản chính thức, nâng registry lên VERIFIED qua task riêng |
| `SITE-001` | Không có hồ sơ site, trong khi rule DUR/GEO/HYDRO/SEIS/WIND cần 11 trường (G0) | Nạp `site_hazard_profile` đủ trường cho dự án thật |

Cùng gene đó, `evaluate_candidate` (BUILTIN_L1 + verifier) cho `feasible=true`,
`max_utilization ≈ 0.98`. Hai kết quả không mâu thuẫn: một cái là **claim** (chưa
được phép), cái kia là **phản hồi vật lý** ở fidelity L1. Lớp đề xuất giữ đúng
hai tầng này trong từng bản ghi và không giả lập site hay nới cổng — đây cũng là
cách `design_loop`, `rl_env`, `surrogate` đang dùng evaluate_candidate.

## 3. Kiến trúc lớp đề xuất (BRD-053)

```
ProposalRequest ──► bộ não (heuristic | HTTP OpenAI-compatible | vendor CLI)
   miền grammar, gene, đánh giá 2 tầng,          │
   lịch sử (kể cả âm), thẻ tri thức có nhãn,     ▼
   ngân sách, luật chơi              ProposalResponse: changes + hypothesis
                                                 │  (schema additionalProperties=false:
                                                 │   verdict/pass/feasible → MALFORMED)
apply_changes (đúng miền, đúng kiểu) ◄───────────┘
        │
        ├─► assess_candidate(study_level theo registry)  → status / claim_level / blockers   (CLAIM)
        └─► evaluate_candidate (chỉ khi registry cho L1)  → verifier_feasible / violations /
                                                            utilization / objectives         (PHẢN HỒI)
        ▼
summarize_assessment ──► lineage (hash request/response/gene/assessment)
```

* `bridge_evolution/proposer/contract.py`: schema, băm chuẩn, `apply_changes`
  nghiêm ngặt (catalog = chuỗi, int/grid = số nguyên, bool bị loại), tóm tắt đánh
  giá hai tầng, dựng request có `request_id` = SHA-256 nội dung,
  `failed_rule_ids` ưu tiên mã verifier và bỏ mã cổng claim (SITE-/APP-).
* `bridge_evolution/proposer/adapters.py`: ba adapter cùng giao diện
  `propose(request) -> AdapterResult(status OK|MALFORMED|UNAVAILABLE|TIMEOUT)`.
  HTTP: endpoint/model từ tham số hoặc `DYLIGHT_LLM_ENDPOINT`/`DYLIGHT_LLM_MODEL`;
  API key chỉ đọc từ `DYLIGHT_LLM_API_KEY` lúc gửi, báo cáo chỉ ghi host.
  CLI: `run_provider(..., writable=False)` (codex `--sandbox read-only`).
* `bridge_evolution/proposer/loop.py`: `run_proposal_session` — pre-registration
  khóa trước vòng 1, mode REPAIR/TRIM/EXPLORE_L0, dedupe theo hash gene, ngân sách
  vòng/lượt, dừng khi adapter hỏng 2 lần liên tiếp, báo cáo validate theo schema.
* `scripts/propose_cli.py`: chạy độc lập (không sửa `cli.py`/`serve_lab.py`).

### Ví dụ chạy

Đường chính (theo yêu cầu của chủ dự án): dùng thẳng não **Claude** (Claude Code
CLI đã đăng nhập trên máy) hoặc **GPT** (codex CLI) — không cần LLM local:

```bash
python scripts/propose_cli.py --family super_t_simple_v1 --adapter cli:claude --rounds 3 --out .tmp/proposer/claude_supert.json
```

```bash
python scripts/propose_cli.py --family super_t_simple_v1 --adapter cli:codex --rounds 3 --out .tmp/proposer/codex_supert.json
```

Cả hai chạy **chỉ đọc** (`claude.exe -p … --tools Read,Glob,Grep --max-budget-usd 2`;
`codex exec --sandbox read-only`), mỗi vòng là một lần gọi CLI (vài chục giây tới
vài phút), output là dữ liệu không tin cậy và chỉ được dùng sau khi qua schema.

Đối chứng không LLM (bắt buộc cho mọi so sánh):

```bash
python scripts/propose_cli.py --family super_t_simple_v1 --adapter heuristic --rounds 3 --out .tmp/proposer/heur_supert.json
```

Tuỳ chọn LLM local hoặc dịch vụ OpenAI-compatible (GPT qua API): `--adapter http
--endpoint https://api.openai.com/v1 --model <model>` với API key đặt trong biến
môi trường `DYLIGHT_LLM_API_KEY` (không bao giờ ghi vào repo/báo cáo); LM Studio
`http://127.0.0.1:1234/v1`, Ollama `http://127.0.0.1:11434/v1`. Không có endpoint
thì adapter trả `UNAVAILABLE` và phiên dừng sạch với báo cáo — không gì bị giả lập.

## 4. Bất biến an toàn (kiểm bằng test)

| Bất biến | Test |
|---|---|
| Hai tầng authority tách bạch: claim BLOCKED/IDEA nhưng verifier_feasible=true được ghi đúng | `test_seed_anchor_shows_two_tiers_claim_gate_vs_physics_feedback` |
| Bộ não phát `verdict`/`feasible` → MALFORMED, không đánh giá, dừng sau 2 lần | `test_http_adapter_verdict_keys_are_malformed_and_session_stops` |
| Giá trị ngoài miền/sai lưới/biến lạ → OUT_OF_DOMAIN, không ném lỗi; số thực → MALFORMED bởi schema | `test_apply_changes_is_strict…`, `test_http_adapter_request_id_mismatch_and_out_of_domain…`, `test_http_adapter_float_value_is_malformed_by_schema` |
| Họ chỉ L0 (dầm hộp) không bao giờ gọi evaluate_candidate; objective báo không có | `test_box_family_only_uses_l0_and_never_calls_l1_evaluator` |
| API key không rò vào báo cáo | `test_http_adapter_valid_proposal_is_evaluated_and_key_never_leaks` |
| CLI chạy chỉ đọc (`--sandbox read-only`) | `test_cli_adapter_parses_codex_events_with_fake_runner` |
| Pre-registration băm trước vòng 1; báo cáo tái lập | `test_heuristic_session_on_anchor_is_valid_and_reproducible` |
| Kết quả âm được đếm và giữ | `test_heuristic_repair_records_negative_results_from_infeasible_seed` |
| Truy vấn thẻ tri thức dùng mã verifier, bỏ mã cổng claim | `test_failed_rule_ids_prefer_verifier_codes_and_skip_claim_gate_codes` |

## 4b. Lần chạy thật đầu tiên (2026-09-05, seed gene neo Super‑T, 2 vòng, ≤ 6 lượt)

| Bộ não | Kết quả | Điều học được |
|---|---|---|
| `heuristic/0.1.0` (3 vòng, 9 lượt) | 7 lượt đánh giá, 4 âm, không hạ được `relative_cost` dưới 2072,94 → giả thuyết bị bác | Gene neo chính là oracle của thí nghiệm grammar A/B trước; kết quả âm là đúng |
| `cli/claude` (Claude Code CLI, chỉ đọc) | Vòng 1 **MALFORMED**: LLM ghi `direction: "unchanged"` ngoài enum → cả câu trả lời bị loại, không đánh giá. Vòng 2 OK: 3 đề xuất có lập luận đúng số liệu (ứng suất thớ dưới −2,371 MPa so với giới hạn 3,162; Mu/φMn ≈ 0,79; trích KC‑018/KC‑020) nhưng cả 3 kèm `DG-3`/bản 175 mm → **L0 từ chối** (claim REJECTED, không mở L1) | (1) Enum `direction` thiếu giá trị hợp lý → đã thêm `unchanged` (test bảo đảm giá trị lạ vẫn bị loại). (2) Bộ não chưa biết luật L0 cấu tạo; vòng sau nó thấy `blocker_codes` trong history — đúng cơ chế học từ phản hồi, nhưng ngân sách 2 vòng chưa đủ. Kết quả âm được giữ trong `.tmp/proposer/real_claude_supert.json` |
| `cli/codex` (GPT) | 2 vòng **UNAVAILABLE**: API trả 400 "model `gpt-6-astra` requires a newer version of Codex" (codex-cli 0.148.0, `~/.codex/config.toml` đặt `service_tier = "priority"`) | Lỗi môi trường của CLI, không phải lab; phiên dừng sạch sau 2 lần theo `adapter_failure_stop_after`. Cần nâng cấp codex CLI trước khi dùng não GPT |

Ba phiên đều tái lập được từ báo cáo (hash request/response, pre-registration khóa,
seed). Không phiên nào phát PASS/FAIL; claim của mọi gene vẫn IDEA (cổng site/evidence).

## 5. Vì sao heuristic đối chứng là bắt buộc

Muốn nói "LLM sáng tạo tốt hơn" phải có baseline cùng ngân sách, cùng seed,
cùng evaluator (PROTOCOL §Quy tắc nghiên cứu 2). `HeuristicProposer` là baseline
không LLM, tất định, dùng đúng thẻ tri thức và bước lân cận. Một phiên A/B
(heuristic vs Qwen local vs codex) trên cùng seed gene là thí nghiệm pre-registered
có thể nộp thành handoff — đó là việc của task kế tiếp, không phải kết luận của
task này.

## 6. Lộ trình để bộ não AI thật sự sáng tạo được cấu kiện phức tạp

| Task đề xuất | Nội dung | Vì sao cần trước |
|---|---|---|
| BRD-054 | Đọc kết quả MIDAS về lab (midas-mcp → phản lực, nội lực, ứng suất, chuyển vị) thành `evaluation` L2 có provenance solver/version/hash; cổng G2 | Không có phản hồi vật lý cho dầm hộp thì AI chỉ vẽ |
| BRD-055 | Nối studio "Sáng tạo mặt cắt" (PSC 1CELL/2CELL) với genome hộp `BOX-PARAM` + L0 chế tạo (FAB-001/002) và đặc trưng Green làm phản hồi L0 có cấu trúc cho bộ não | Để AI đề xuất được tham số MIDAS thật thay vì gene Super‑T |
| BRD-056 | Thí nghiệm pre-registered: heuristic vs LLM local vs vendor CLI, 20 seed, cùng ngân sách; báo cả kết quả âm | Chứng minh (hoặc bác) giá trị của LLM bằng số |
| BRD-057 | Nâng `domain_evidence` Super‑T lên VERIFIED (đối chiếu S/ts/L/Kg bản chính thức) + hồ sơ site đủ 11 trường cho dự án mẫu | Để claim qua cổng lên được SCREENED thật, không chỉ "verifier-khả thi" |
| BRD-058 | Thư viện điều khoản TCVN 11823 có provenance + quy trình kỹ sư duyệt thẻ (ENGINEER_APPROVED_KNOWLEDGE) | Để gợi ý của bộ não dựa trên luật có nguồn, không chỉ thẻ DRAFT |
| sau | Hook UI trong `serve_lab.py` (BRD-051): nút "Hỏi bộ não" trong studio, hiển thị lineage hai tầng | Trải nghiệm, không phải năng lực |

## 7. Giới hạn trung thực của task này

* Không có LLM nào được gọi thật trong test; mọi kết luận về "chất lượng đề xuất
  của LLM" đều chưa tồn tại. Lớp này chỉ bảo đảm *nếu* có LLM thì nó không thể
  vượt quyền.
* Claim của mọi gene Super‑T qua lớp này hôm nay là IDEA (cổng chặn bởi
  APP-EVIDENCE-001/SITE-001); "verifier-khả thi ở L1" là phản hồi, không phải claim.
* Heuristic là LAB-HEURISTIC-UNSOURCED-PROPOSER-01, chưa có nguồn tiêu chuẩn.
* Dầm hộp: chỉ L0_GEOMETRY; không có utilization/objective ở mức này.
* Trần claim SCREENED; không đường nào từ lớp này lên NUMERICALLY_VERIFIED.
