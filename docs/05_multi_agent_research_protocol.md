# 05 — Môi trường Multi-Agent Bridge Research Lab

> Bản triển khai 0.8 bổ sung `lab orchestrate`: tiếp nhận đề tài, materialize DAG,
> chạy agent có budget, test allowlist, reviewer khác provider và mirror brief/run
> sang Obsidian. Tự động chỉ áp dụng cho nghiên cứu số; G5–G7 và phát hành kỹ thuật
> luôn cần dữ liệu vật lý thật cùng responsible bridge engineer.

Phiên bản: `MARP-1.1 / PG-1.0` — DYLIGHT v0.8.0.

## Kết quả triển khai

Một nguồn luật duy nhất nằm tại:

- `multiagent/PROTOCOL.md`: vòng đời task, vai trò, claim và review độc lập;
- `multiagent/PHYSICS_GATES.md`: physics-in-the-loop và reality-in-the-loop;
- `multiagent/tasks/`: backlog theo file, có dependency và write scope;
- `multiagent/handoffs/`: output bất biến kèm SHA-256;
- `multiagent/reviews/`: quyết định của reviewer độc lập.

Mỗi lần `lab submit` hoặc `lab review`, Research Lab được mirror tự động sang
Obsidian. Task, phát minh, phép tính, artifact hash, giả định, kết quả âm và
review xuất hiện dưới `DYLIGHT Bridge Evolution/Research Lab`. JSON/artifact
trong repo vẫn là canonical; Markdown chỉ là bề mặt đọc–liên kết dài hạn.

Codex đọc `AGENTS.md`; Claude nạp `CLAUDE.md`; OpenCode nạp `AGENTS.md` và
`opencode.json`; Antigravity dùng rule always-on `.agents/rules/bridge-lab.md`.
Các adapter chỉ dẫn về cùng protocol để không tạo bốn nguồn sự thật.

## Vận hành

```powershell
python -m bridge_evolution.cli lab status
python -m bridge_evolution.cli lab validate
python -m bridge_evolution.cli lab brief --agent claude
python -m bridge_evolution.cli lab claim BRD-005 --agent claude
python -m bridge_evolution.cli lab sync-obsidian --dry-run
python -m bridge_evolution.cli lab sync-obsidian
```

Sau khi hoàn thành artifact:

```powershell
python -m bridge_evolution.cli lab submit BRD-005 `
  --agent claude --role materials_researcher `
  --summary "Evidence matrix và test plan đã validate" `
  --claim-level IDEA --gates G0 G6 `
  --artifact research/materials/evidence_matrix.json
```

Reviewer khác owner tạo file JSON findings rồi chạy `lab review`. `APPROVE` chỉ
được chấp nhận khi findings phủ toàn bộ gate bắt buộc. Handoff/review cũ không
bị ghi đè; vòng sửa tạo revision mới. Nếu Obsidian không truy cập được hoặc note
đã sửa, CLI báo `OBSIDIAN_SYNC_PENDING`/`CONFLICT`; canonical không mất nhưng
agent phải xử lý pending trước khi coi vòng nghiên cứu đã lưu trọn vẹn.

## Trạng thái công cụ trên máy

Codex CLI hiện có trong PATH. Claude, OpenCode và Antigravity đã có ứng dụng GUI
nhưng CLI `claude`, `opencode`, `agy` chưa có trong PATH; có thể mở cùng project
bằng GUI ngay. Muốn tự động hóa terminal, cài/đăng nhập theo tài liệu chính thức
của từng hãng, rồi chạy lại `lab status`. Không lưu token trong repo.

Tài liệu cấu hình chính thức dùng để tạo adapter:

- OpenAI Codex `AGENTS.md`: https://developers.openai.com/codex/guides/agents-md
- Claude Code memory/import: https://code.claude.com/docs/en/memory
- OpenCode rules/config: https://dev.opencode.ai/docs/rules/ và https://dev.opencode.ai/docs/config
- Antigravity workspace rules: https://antigravity.google/docs/ide/rules

## Ranh giới kỹ thuật hiện tại

Runtime chỉ hỗ trợ họ Super-T giản đơn cố định và L0/L1. Midas/OpenSees adapter,
mô hình 3D, phi tuyến, hazards, thử vật liệu/cấu kiện và field SHM còn là backlog.
Vì vậy `lab status` cố định claim ceiling hiện tại là `SCREENED`; task có trần
cao hơn mô tả mục tiêu tương lai, không chứng minh gate đã hoàn tất.

Trước khi bốn agent cùng sửa code, cần baseline Git đã được chủ dự án kiểm tra.
Repo hiện chưa có `.git`; cho tới khi có baseline, chỉ thực hiện task có
`write_scope` tách biệt và dùng claim lock.
