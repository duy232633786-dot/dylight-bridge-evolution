# G0 — Design basis, evidence và tiêu chí bác bỏ

## Trạng thái phát hành

- Task: `RND-e03038f3-01`
- Claim ceiling: `IDEA`
- Engineering use: `PROHIBITED`
- Current project ceiling: `SCREENED`; tài liệu này không nâng fidelity và không phát hành `PASS/FAIL`.
- Units cho mọi dữ liệu số tương lai: SI, phải ghi rõ `N/kN`, `m/mm`, `Pa/MPa` tại nguồn và tại boundary của solver.

## Câu hỏi đã khóa

Hệ thống có thể nâng cấp vòng lặp kiểm toán–đề xuất để: tạo candidate, đánh giá bằng oracle thật, nhận diện cơ chế chi phối, đề xuất sửa chữa có phả hệ, loại nghiệm vượt hard gate, quay về nghiệm khả thi gần nhất và tiếp tục tìm kiếm — mà không để LLM/surrogate tự cấp `feasible`, không che kết quả âm và không vượt claim ceiling hay không?

## Bằng chứng đã biết

| ID | Điều đã biết | Nguồn | Trạng thái |
|---|---|---|---|
| E-01 | Video mô tả vòng lặp: dựng mô hình; xét độ mảnh và hiệu ứng bậc hai; tạo đường tương tác N–M; thử phương án; loại phương án vượt sức kháng; quay về nghiệm khả thi; tiếp tục tìm kiếm. Các utilization chỉ minh họa và thiết kế thật cần đủ tải, vật liệu, cấu tạo, tiêu chuẩn và kỹ sư kiểm tra. | TikTok `@structural_lab`, video `7677568358631623944`, caption truy cập 2026-08-26: https://www.tiktok.com/@structural_lab/video/7677568358631623944 | `SOURCE_OBSERVED`; không dùng con số trong video làm dữ liệu kỹ thuật |
| E-02 | Runtime hiện có contract `evaluate_candidate`, independent verifier L1, `suggest_repairs`, random/NSGA-II, surrogate chỉ xếp hạng và audit history. | `bridge_evolution/evaluate.py`, `verifier/rules.py`, `analysis/diagnose.py`, `optimization/`, `surrogate/` | `REPO_VERIFIED` |
| E-03 | Runtime hiện tại chưa có MIDAS/OpenSees L2/L3; kết quả tối đa `SCREENED`. | `AGENTS.md`, `multiagent/PHYSICS_GATES.md`, `docs/runtime_capability_matrix.md` | `REPO_VERIFIED` |
| E-04 | G0–G4 yêu cầu design basis, geometry/reality, model quality, limit states và independent verification; hard safety gate không được đổi lấy cost/carbon/aesthetics. | `multiagent/PHYSICS_GATES.md` | `REPO_VERIFIED` |

## Dữ liệu chưa biết — bắt buộc dừng claim kỹ thuật

- Đối tượng thiết kế cụ thể: cầu/cột/dầm, topology, span, site và hệ tọa độ.
- Tiêu chuẩn cùng phiên bản, design life, exposure và authority having jurisdiction.
- Tải, tổ hợp, construction stages, imperfection và accidental eccentricity.
- Địa chất, thủy văn/xói, gió, động đất, nhiệt, va chạm và điều kiện biên.
- Thuộc tính vật liệu characteristic/design, creep/shrinkage, fatigue, fracture và durability.
- Solver L2/L3, version/hash, element formulation, mesh convergence, benchmark và tolerance đối chiếu.
- Định nghĩa tương tác N–M phù hợp vật liệu/cấu tạo; runtime hiện tại chưa có oracle N–M tổng quát.
- Tiêu chí độ mảnh và phương pháp bậc hai đúng theo code đã khóa.

Mọi mục trên là `UNKNOWN / UNVERIFIED`; không được tự điền từ LLM hoặc từ video.

## Baseline và kiến trúc mục tiêu

Baseline `B0` là pipeline hiện có:

`schema → L0 → solver L1 → verifier → objectives`, sau đó `suggest_repairs` chỉ gợi ý và optimizer đánh giá candidate mới qua `evaluate_candidate`.

Mục tiêu `A1` cần giữ nguyên authority boundary nhưng bổ sung audit envelope cho mỗi bước:

1. `CandidateEnvelope`: `candidate_id`, `parent_candidate_id`, gene diff, units, design-basis hash, proposer, seed và timestamp.
2. `ModelAudit`: fidelity, solver/version/hash, equilibrium, dimensional checks, warnings, convergence và missing-capability flags.
3. `LimitStateAudit`: từng hard gate có demand, capacity, utilization, source, applicability và uncertainty; thiếu dữ liệu trả `NOT_EVALUATED`, không mặc định đạt.
4. `RepairProposal`: cơ chế chi phối, thay đổi đề xuất, expected direction, trade-offs, violated constraints và evidence IDs; tuyệt đối không gắn `feasible=True` trước đánh giá thật.
5. `FallbackTrace`: khi candidate bị loại, lưu nearest verified feasible ancestor/archive member, khoảng cách gene, lý do fallback và bước tiếp theo.
6. `SearchLedger`: proposal, L0 reject, cache hit, solver call, hard-gate rejection, first feasible, negative results và budget accounting tách biệt.

## Metric và ngân sách preregistered

So sánh `B0` với `A1` trên cùng grammar, seed, solver budget, L0 prefilter và reference point.

- Primary safety metric: `authority_violation_count = 0` — không record nào do LLM/surrogate đề xuất được ghi feasible nếu chưa qua oracle/verifier.
- Primary audit metric: `complete_trace_rate = 100%` cho candidate đã gọi solver; đủ parent, input hash, solver provenance, gate verdict và reason code.
- Primary recovery metric: tỷ lệ candidate infeasible có ít nhất một repair proposal hợp lệ và fallback target đã được đánh giá thật.
- Efficiency metrics: solver calls tới feasible đầu tiên, feasible rate có điều kiện theo solver, cache hit, L0 reject, proposal/solver ratio.
- Quality metrics: max utilization chỉ từ verifier; Pareto cost/mass/carbon chỉ trên tập feasible thật; báo riêng `NOT_EVALUATED` capability.
- Robustness: replay cùng seed/config cho cùng candidate hashes và verdicts.
- Initial digital budget: 10 seed × 200 solver calls/arm; có thể giảm trong smoke test nhưng không được dùng smoke test để claim superiority.
- Wall-clock/task budget: theo orchestrator; timeout/failure được lưu là kết quả âm, không tự retry vô hạn.

## Tiêu chí bác bỏ

Đề xuất nâng cấp bị bác bỏ hoặc trả về `REVISE` nếu xảy ra bất kỳ điều nào:

1. LLM/surrogate có thể phát hành `feasible`, `PASS/FAIL` hoặc capacity mà không qua verifier.
2. Thiếu `parent_candidate_id`, design-basis hash, solver provenance hoặc reason code nhưng record vẫn được archive/promote.
3. `NOT_EVALUATED` bị ánh xạ thành `PASS`, utilization giả định, hoặc penalty mềm.
4. Candidate infeasible bị xóa/ghi đè thay vì giữ immutable negative result.
5. Fallback trỏ tới candidate chưa được đánh giá thật hoặc khác design basis.
6. So sánh thuật toán dùng solver budget, fidelity, seed policy hoặc reference point khác nhau.
7. N–M, slenderness hoặc P-Delta được tuyên bố đã kiểm khi capability tương ứng chưa tồn tại.
8. Test replay không tái tạo candidate hash/verdict hoặc validator phát hiện artifact drift.

## Quyết định G0

`G0 = PARTIAL / STOP_FOR_ENGINEERING_CLAIMS`.

Đủ cơ sở để triển khai và kiểm thử **hạ tầng audit/proposal ở cấp digital**, nhưng chưa đủ design basis để tính N–M, độ mảnh, P-Delta hoặc đưa phương án kết cấu thật. Bước kế tiếp phải tạo contract/schema và test cho các envelope trên; capability vật lý thiếu phải hiển thị `NOT_IMPLEMENTED`/`NOT_EVALUATED` cho tới khi có solver và verifier phù hợp.
