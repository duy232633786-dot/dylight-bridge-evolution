# 04 — Kết nối Obsidian cho Brain 2

## Mục tiêu và ranh giới

Obsidian là giao diện để đọc, liên kết và ghi chú kho tri thức. KnowledgeCard
JSON trong `knowledge/cards/` vẫn là nguồn chuẩn được runtime nạp và validate.
Markdown trong vault **không** được dùng để kết luận PASS/FAIL, không được solver
đọc và không tự ghi ngược vào JSON.

Luồng dữ liệu:

```text
KnowledgeCard JSON + knowledge audit
              │ validate + hash
              ▼
      Obsidian Markdown snapshot
              │ đọc / liên kết / ghi chú
              └── không đi vào verifier
```

Thiết kế một chiều này tránh hai nguồn sự thật và giữ thí nghiệm tái lập. Khi
cần cho phép biên tập từ Obsidian, phải bổ sung compiler staging, review và
snapshot bất biến; không được cho runtime đọc trực tiếp note đang được sửa.

## Kết nối hiện tại

CLI ưu tiên vault truyền bằng `--vault`, sau đó biến môi trường
`DYLIGHT_OBSIDIAN_VAULT`; nếu cả hai đều thiếu, nó đọc registry Obsidian và chỉ
tự chọn khi tìm thấy đúng một vault.

```powershell
# Chỉ xem những gì sẽ thay đổi
python -m bridge_evolution.cli knowledge-export --dry-run

# Tạo/cập nhật vùng Brain 2
python -m bridge_evolution.cli knowledge-export

# Chỉ định vault khác
python -m bridge_evolution.cli knowledge-export --vault "D:\Obsidian Vault"
```

Vùng được quản lý có dạng:

```text
<vault>/DYLIGHT Bridge Evolution/
├── 00 - Brain 2 Dashboard.md
├── Cards/
│   ├── KC-001.md
│   └── ... toàn bộ card runtime đã validate
├── Rules/
│   ├── 00 - Rules Index.md
│   └── ... các node STR/SERV/GEOM/CONS/MODEL/SOLVER
├── Variables/
│   ├── 00 - Variables Index.md
│   └── ... 8 biến của design grammar
├── Standards/TCVN 11823-2017/
│   ├── Parts/
│   └── PDF/
├── NotebookLM/
│   ├── 00 - NotebookLM Bridge Library.md
│   └── ... 32 snapshot note theo notebook ID
├── Research Lab/
│   ├── 00 - Research Lab Dashboard.md
│   ├── Tasks/
│   ├── Handoffs/
│   └── Reviews/
└── .dylight-manifest.json
```

Lệnh `knowledge-export` không sửa `.obsidian/`, không quét toàn vault, không xóa file và không
theo symlink/junction cho managed folder. Đường dẫn được resolve và kiểm tra vẫn
nằm dưới vault trước khi ghi. Mỗi lần ghi dùng file tạm cùng thư mục rồi
`os.replace`.

## Đồng bộ và conflict

Manifest giữ SHA-256 của từng file ở lần xuất gần nhất:

- file chưa có: tạo mới;
- file còn đúng hash cũ: được phép cập nhật;
- file đã giống output mới: giữ nguyên;
- file đã được người dùng sửa: báo `CONFLICT`, không ghi đè;
- file lạ hoặc file cũ không còn trong snapshot: không xóa.

Lệnh trả exit code `0` khi thành công, `3` khi có conflict và `2` khi cấu hình
hoặc dữ liệu không hợp lệ. Nội dung sinh ra không chứa timestamp nên lần xuất
lặp lại là byte-deterministic.

## Metadata và audit

Mỗi note có Obsidian Properties/frontmatter gồm `card_id`, version, status,
family, rules, variables, nguồn chuẩn và SHA-256. Tags tách riêng trạng thái duyệt,
nguồn legacy, mức risk và kết quả claim audit.

Audit hiện tại nằm trong `knowledge/audits/current.json`, được validate bằng
`contracts/knowledge_audit.schema.json` và tham chiếu exhaustive oracle đầy đủ.
CLI `knowledge` và `diagnose` tự gắn `knowledge_audit` vào card/repair trả về để
planner không bỏ qua cảnh báo chỉ vì không mở Obsidian.
Dashboard phải luôn hiển thị độc lập hai trục:

- `status`: DRAFT / ENGINEER_APPROVED / REJECTED;
- `claim_audit` và `risk`: mức bằng chứng hiện tại, không phải phê duyệt kỹ sư.

Hiện cả 9 card là DRAFT; 6 card trích nguồn experiment legacy và 3 card có risk
RED. Không được tự nâng status từ kết quả audit.

## Quy trình cập nhật tri thức

1. Tạo/sửa KnowledgeCard JSON và tăng `version` khi nội dung semantic đổi.
2. Chạy test schema/query.
3. Cập nhật audit từ evidence có hash và provenance rõ ràng.
4. Chạy `knowledge-export --dry-run`; xử lý conflict thủ công nếu có.
5. Chạy `knowledge-export` và kiểm tra dashboard trong Obsidian.
6. Kỹ sư duyệt bằng quy trình riêng trước khi đổi `ENGINEER_APPROVED`.

Không lưu credential, token hoặc dữ liệu dự án nhạy cảm trong card. Obsidian
Sync là cấu hình ngoài dự án; người vận hành phải tự xác nhận chính sách lưu trữ
trước khi bật đồng bộ cloud.

## Thư viện tiêu chuẩn PDF

`knowledge-import-tcvn` nhập bản PDF nguyên byte vào `Standards/`, tạo note theo
từng phần và một chỉ mục collection. Số phần được đọc từ trang bìa PDF, không
suy từ hậu tố filename; điều này tránh nhầm `part07` thành TCVN phần 7 trong khi
file cục bộ thực tế là TCVN 11823-9:2017.

```powershell
python -m bridge_evolution.cli knowledge-import-tcvn "<thu_muc_pdf>" --dry-run
python -m bridge_evolution.cli knowledge-import-tcvn "<thu_muc_pdf>"
```

Mỗi note lưu số trang, filename nguồn, SHA-256, chất lượng lớp chữ, nội dung
chính đã chuẩn hóa và embed PDF. Manifest riêng bảo vệ PDF/note đã được người
dùng chỉnh; gặp conflict thì toàn bộ lần cập nhật bị chặn. Raw extracted text
không được đẩy hàng loạt vì font tiếng Việt của bộ hiện tại chèn khoảng trắng
giữa ký tự. Việc có PDF trong vault không tự tạo rule: ánh xạ điều khoản sang
solver/verifier vẫn phải qua review, test và phê duyệt kỹ sư.

## Đồ thị liên kết và quy ước màu

Snapshot tạo các liên kết hai chiều theo luồng:

```text
TCVN Standard ↔ Rule thực thi ↔ KnowledgeCard ↔ Biến thiết kế
```

Mỗi card cũng liên kết trực tiếp tới phần TCVN liên quan. Các node rule/variable
là mục lục điều hướng; code, catalog, grammar và ruleset version hóa vẫn là nơi
định nghĩa hành vi thực thi.

Chạy lệnh sau để bật CSS snippet và các nhóm màu trong Graph View:

```powershell
python -m bridge_evolution.cli knowledge-theme --dry-run
python -m bridge_evolution.cli knowledge-theme
```

Quy ước màu:

- đỏ: claim/risk cần xử lý;
- cam: DRAFT hoặc bằng chứng partial;
- xanh lá: `ENGINEER_APPROVED`;
- xanh dương: tiêu chuẩn;
- tím: dashboard, index và rule;
- xanh ngọc: biến thiết kế.
- Research Lab: IDEA xám, SCREENED cam, NUMERICALLY_VERIFIED xanh dương,
  LAB_VALIDATED tím, PILOT_VALIDATED xanh ngọc và ENGINEERING_CANDIDATE xanh lá;
  review REJECT đỏ.

Lệnh chỉ merge `enabledCssSnippets` và `colorGroups`, giữ các thiết lập/group màu
khác của người dùng. CSS có manifest riêng; nếu CSS đã bị chỉnh thủ công, lệnh
báo conflict và không ghi đè. Màu là metadata trình bày, không tự đổi `status`,
`risk`, verifier hoặc nguồn JSON chuẩn.

## Snapshot NotebookLM

`knowledge-import-notebooklm` xuất snapshot chỉ-đọc được kiểm kê từ phiên
NotebookLM đã đăng nhập. Phạm vi hiện tại gồm 32 notebook có tiêu đề liên quan
cầu, dầm, I-Beam, form traveler hoặc Bridge BIM; notebook cá nhân ngoài phạm vi
dự án không được nhập.

```powershell
python -m bridge_evolution.cli knowledge-import-notebooklm --dry-run
python -m bridge_evolution.cli knowledge-import-notebooklm
```

Snapshot ngày 2026-08-20 ghi nhận 218 nguồn NotebookLM khai báo, 215 source item
có tên và 3 nguồn phi-item/nhóm hội thoại. Mỗi note lưu URL notebook gốc, nhãn
ngày cập nhật, source inventory, summary hiện có và prompt hội thoại quan sát
được. NotebookLM không cung cấp bulk-download bản gốc qua giao diện này, vì vậy
source inventory không được diễn giải là bản sao file.

Summary và chat do NotebookLM sinh được gắn `AI-generated / UNVERIFIED`, màu
xanh cyan và tag `#dylight/notebooklm`. Chúng chỉ tạo cạnh tham khảo tới
Dashboard, Rules, Variables và thư viện TCVN; không được runtime, solver hoặc
verifier đọc. Muốn chuyển một claim thành rule phải quay về nguồn gốc, dẫn đúng
điều khoản, thêm test và được kỹ sư duyệt.

## Research Lab dài hạn

Mọi phát minh, phép tính, kết quả âm và bài học của multi-agent phải được nộp
qua `lab submit` thành handoff có artifact SHA-256. Lệnh tự mirror task/handoff
vào `Research Lab/`; `lab review` tiếp tục mirror review độc lập. Có thể bootstrap
hoặc đồng bộ lại bằng:

```powershell
python -m bridge_evolution.cli lab sync-obsidian --dry-run
python -m bridge_evolution.cli lab sync-obsidian
```

Research Lab dùng manifest riêng, không xóa file lạ và không ghi đè note đã sửa.
Nếu sync chưa thành công, CLI báo pending/conflict. Artifact/JSON trong project
vẫn là canonical để tính toán và tái lập; Markdown không được solver đọc ngược.
