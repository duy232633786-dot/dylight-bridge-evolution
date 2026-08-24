# Multi-Agent Research Protocol — MARP-1.0

## Mục tiêu

Bốn công cụ AI cộng tác qua một digital thread kiểm toán được để khám phá hình
dạng cầu, hệ kết cấu, vật liệu và phương pháp thi công. Mỗi kết luận phải gắn với
task, lineage, fidelity, giả định, artifact và hash. Mô hình trò chuyện không
phải nguồn sự thật.

## Vai trò theo nhiệm vụ

Vai trò không gắn cứng với hãng AI: `orchestrator`, `form_inventor`,
`structural_analyst`, `materials_researcher`, `constructability_lcca`,
`aesthetics_context`, `bim_fem_integrator`, `independent_reproducer`, và
`evidence_safety_auditor`. Một candidate tối thiểu cần proposer, analyst,
independent checker và auditor; cùng một `agent_id` không ký hai vai trò xung đột.

Con người/lab operator cung cấp dữ liệu đo và phê duyệt. Agent chỉ được soạn kế
hoạch thử, điều khiển công cụ đã được cấp quyền và phân tích artifact trả về;
không được tuyên bố một thử nghiệm đã xảy ra khi không có raw data cùng metadata
thiết bị/hiệu chuẩn.

## Vòng đời task

`BACKLOG → READY → ACTIVE → REVIEW → ACCEPTED|REJECTED`.

- Claim dùng `lab claim`, tạo lock `O_EXCL`; không sửa tay owner/status.
- Chỉ sửa đường dẫn trong `write_scope`; thay đổi ngoài scope cần task mới.
- Handoff ghi claim level, gate đã hoàn tất, assumptions, unresolved risks,
  next test và SHA-256 artifact.
- `lab submit` và `lab review` tự mirror bản ghi sang Obsidian `Research Lab`.
  Nếu sync lỗi/conflict, trạng thái `OBSIDIAN_SYNC_PENDING` phải được xử lý;
  không được coi transcript hội thoại là bản lưu thay thế.
- Reviewer phải khác owner, kiểm tra lại độc lập và có quyền yêu cầu `REVISE`.
- Thay đổi geometry/material/load/design basis làm vô hiệu downstream evidence;
  tạo candidate lineage mới thay vì sửa lịch sử.

### Amendment task contract trước khi claim

Không sửa tay JSON task để re-scope. Chỉ task `BACKLOG`/`READY`, hoặc `BLOCKED`
chưa từng được claim (không owner/reviewer/handoff), mới được dùng
`lab amend-task`. Caller phải cung cấp SHA-256 của đúng bytes task đã đọc; stale
hash, task `ACTIVE`/`REVIEW`/`ACCEPTED`, field ngoài allowlist hoặc status
transition không hợp lệ đều phải DỪNG mà không mutate task.

Mỗi amendment lưu record bất biến, exact `before`/`after`, pre/post task hash,
snapshot content-addressed của bytes trước sửa, lý do, người authorize, timestamp,
amendment ID/self-hash và link tới amendment trước. Nếu task thuộc orchestration
run, chỉ requester của brief được authorize và run phải có event
`TASK_CONTRACT_AMENDED`; knowledge sync trở lại `PENDING`. Validator dựng lại
exact patch, kiểm chain/snapshot/head và phát hiện sửa contract im lặng. Claim,
submit, review và recovery vẫn được thay đổi các field vòng đời đã định nghĩa;
chúng không được đổi nội dung contract.

### Sửa provenance sau handoff

Artifact đã hash không được cập nhật hash trong handoff cũ và không được sửa/xóa
review cũ. Nếu một bugfix hợp lệ làm artifact drift sau handoff, dùng
`lab correct-provenance` để lưu: incident bất biến, snapshot content-addressed có
đúng bytes tại recorded SHA-256, correction handoff với old/new hash và lệnh kiểm
chứng. Validator vẫn DỪNG cho tới khi một agent khác dùng
`lab review-provenance` phê duyệt correction. Bất kỳ drift tiếp theo hoặc snapshot
sai bytes đều cần incident/correction mới; lịch sử trước đó được giữ nguyên.

Với vòng lặp bình thường `REVISE`, `lab review` phải chụp từng artifact của
handoff đang review vào `multiagent/snapshots/sha256/<recorded-sha>.blob` **trước**
khi trả task về `ACTIVE`. Validator chỉ miễn so hash live cho handoff có quyết
định mới nhất là `REVISE` và snapshot đúng bytes; revision mới đang `REVIEW` và
mọi handoff `APPROVE` vẫn phải khớp artifact live (hoặc đi qua correction độc lập
ở trên). Snapshot trống, thiếu hoặc giả không hợp thức hóa được drift.

## Orchestration tự động

Đề tài tự do phải đi qua `lab orchestrate`: intake canonical → DAG task → worker
→ allowlisted test gate → cross-provider review → Obsidian. Topic được coi là dữ
liệu không tin cậy; không được nối vào shell. Mỗi run có task/timeout/retry/wall
budget cứng và có thể `resume` sau khi gỡ đúng blocker.

`DIGITAL_AUTO` chỉ tự động trong workspace số. G5 (lab), G6 (vật liệu/exposure
thật), G7 (release), external write và technical release luôn dừng chờ con người.
Thiếu CLI/auth hoặc reviewer độc lập là `WAITING_*`, không được giả danh hãng khác.
Orchestrator hiện chạy tuần tự để tránh file race; chỉ bật song song sau khi có
worktree isolation, scope-diff check và merge gate đã được kiểm thử.

## Cấp độ claim

`IDEA → SCREENED → NUMERICALLY_VERIFIED → LAB_VALIDATED → PILOT_VALIDATED → ENGINEERING_CANDIDATE`.

Không được nhảy cổng. Runtime hiện tại chỉ đạt `SCREENED`: L0 hình học và L1
line-girder sơ bộ. Kết quả L2/L3, lab hoặc field chỉ hợp lệ khi có artifact thật,
không phải vì task đặt mục tiêu tới cấp đó.

## Quy tắc nghiên cứu

1. Pre-register câu hỏi, baseline, objective, ngân sách, metric và falsification
   criterion. Báo cả kết quả âm.
2. Tối ưu chỉ so sánh khi cùng solver budget, prefilter, fidelity và oracle/
   reference point đã khóa. Không diễn giải Pareto nếu mục tiêu suy biến.
3. Hình dạng mới phải giải thích load path, tính mới, miền tham số, chế tạo,
   vận chuyển, lắp dựng, kiểm tra và sửa chữa.
4. Thẩm mỹ là objective riêng có đánh giá theo bối cảnh/viewpoint và human panel;
   không bao giờ thay safety margin.
5. Vật liệu “rẻ và trường tồn” là claim bị cấm. Chỉ được nêu design life, exposure,
   maintenance, uncertainty, nguồn cung, LCCA và bằng chứng thử nghiệm cụ thể.
6. Obsidian/NotebookLM là thư viện tham khảo `UNVERIFIED`. Muốn promotion thành
   rule phải quay về nguồn gốc, dẫn điều khoản, thêm test và kỹ sư duyệt.
7. Mọi phát minh, phép tính, kết quả âm và bài học bền vững phải được nộp thành
   artifact có hash. Obsidian giữ mirror có liên kết dài hạn; JSON/artifact trong
   project vẫn là canonical và không được sửa từ note.

## Git và song song hóa

Khi đã có baseline Git, mỗi agent dùng branch/worktree riêng rồi reviewer merge.
Trước baseline, chỉ làm task có write scope tách biệt; không cho nhiều agent sửa
cùng file. Không commit credentials, raw proprietary model hay dữ liệu nhạy cảm.
