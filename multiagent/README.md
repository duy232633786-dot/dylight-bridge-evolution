# DYLIGHT Multi-Agent Bridge Research Lab

Đây là bảng điều phối dùng chung cho Codex, Claude, OpenCode và Antigravity.
Nó chia sẻ **nhiệm vụ và bằng chứng**, không chia sẻ tài khoản, API key hay lịch
sử hội thoại của từng công cụ.

```powershell
python -m bridge_evolution.cli lab status
python -m bridge_evolution.cli lab validate
python -m bridge_evolution.cli lab brief --agent codex
python -m bridge_evolution.cli lab claim BRD-001 --agent codex
python -m bridge_evolution.cli lab sync-obsidian --dry-run
python -m bridge_evolution.cli lab sync-obsidian

# Đề tài mới: lập kế hoạch an toàn, chưa gọi model
python -m bridge_evolution.cli lab orchestrate --topic "Nghiên cứu ..."

# Sau khi `lab doctor` xác nhận worker + reviewer khác hãng đã đăng nhập
python -m bridge_evolution.cli lab resume RUN-... --execute
```

Mỗi task là một file riêng trong `tasks/`; claim dùng lock độc quyền và ghi
atomic. Kết quả được nộp vào `handoffs/` kèm SHA-256 của artifact, rồi một agent
khác review vào `reviews/`. Transcript AI không phải evidence.

`lab submit` và `lab review` tự đồng bộ bản ghi sang
`DYLIGHT Bridge Evolution/Research Lab` trong vault Obsidian. Dùng
`lab sync-obsidian` để bootstrap hoặc xử lý một lần sync còn pending. Note bị
người dùng sửa được bảo vệ bằng manifest và sẽ báo conflict, không bị ghi đè.

`lab doctor` phân biệt GUI với CLI headless và không chạy model. Worker chỉ được
gọi qua argv (không shell), có timeout/output cap; orchestrator tự kiểm scope,
artifact và test allowlist rồi mới xin reviewer độc lập. Brief, run, event,
handoff và review đều được mirror conflict-safe sang Obsidian.

“Tự động hoàn toàn” ở đây nghĩa là chu trình nghiên cứu **số**. Hệ thống chủ động
dừng ở thiếu design basis/provider, thí nghiệm vật lý, dữ liệu hiện trường, xác
minh vật liệu và ký duyệt kỹ thuật. Đây là hành vi an toàn, không phải lỗi.

Agent chạy tuần tự trên baseline Git và bị kiểm tra diff theo `write_scope`.
Parallel worktree/merge chỉ được bật khi isolation manager đã có test riêng.
