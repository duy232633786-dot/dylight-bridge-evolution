# 07 — DYLIGHT Lab: phòng lab hướng 1 (sáng tạo hình học và chất lượng cấu kiện)

Phiên bản: `lab-ui/0.1.0` — 2026-09-03 (BRD-051). Máy chủ: `scripts/serve_lab.py`;
giao diện: `dashboard/lab.html`, `dashboard/lab.js`, `dashboard/lab.css`,
`dashboard/inspector.html`; profile mặc định: `dashboard/lab_creative_profile.json`;
test: `tests/test_lab_api.py`.

```bash
python scripts/serve_lab.py          # http://127.0.0.1:8790/lab.html
```

## 1. Phòng lab là gì, không là gì

Phòng lab là **giao diện đọc và gọi** lên các contract đã có của repo. Nó không
chứa công thức sức kháng, không phát PASS/FAIL và không nâng trần claim. Ba lớp:

| Lớp | Nội dung | Nguồn sự thật |
|---|---|---|
| Mô hình | 3D cấu kiện Super-T, mặt cắt, đo, khối lượng, nạp IFC | `inspector.html` dựng từ BridgeDesignState/report |
| Bằng chứng | D/C theo rule kèm fidelity, audit đa cấu kiện, cổng G0–G7, claim | `evaluate_candidate`, `build_component_audit`, `design_loop` |
| Quy trình | task, handoff, review chéo, thẻ tri thức, Obsidian | `multiagent/`, `knowledge/cards`, `lab_status` |

Máy chủ chỉ lắng nghe `127.0.0.1`. Không có xác thực vì không phục vụ ra ngoài máy.

## 2. Các màn

- **Tổng quan**: trần claim, thang cổng G0–G7 với lý do từng cổng, ma trận năng
  lực PRESENT/PARTIAL/ABSENT, design basis và site profile (số trường UNKNOWN),
  trạng thái lab đa tác tử, não 2, oracle vét cạn v1 (mốc so sánh bắt buộc).
- **Bàn cấu kiện**: chọn seed (gold case, anchor grammar, gene từ Studio), đặt
  ngân sách solver, mục tiêu D/C, chính sách nước sửa và thứ tự TRIM, rồi chạy
  `run_design_loop`. Report được lưu vào `artifacts/design_loop/` với SHA-256 và
  nạp thẳng vào Component Inspector (3D, lineage, kiểm tra, mặt cắt).
- **Sáng tạo mặt cắt** (một bàn, ba tab; gõ số hoặc kéo → hình đổi theo tức thì):
  (a) *Hộp PSC kiểu MIDAS* (BRD-052, `docs/08_midas_section_bridge.md`): dialog PSC-1CELL/2CELL
  đúng tên/thứ tự trường MIDAS, PSC Viewer, đặc trưng đối chiếu, xuất Table Input/JSON/MCT, họ mặt
  cắt đúc hẫng, đề xuất heuristic (IDEA); (b) *Super-T tham số v2*: 6 tham số hình dạng + bố trí,
  thanh trượt kèm ô nhập số bắt vào lưới grammar, L0 và objective giải tích tức thời, bản vẽ tiết
  diện, nút "dùng làm seed" và "xuất PSC-Value MIDAS"; (c) *Hình thái vòm*: MAP-Elites có safety
  shield của `creative_shape`, lưới hình thái với đồ thị đường lực, chi tiết check F0 từng candidate.
- **Bằng chứng & cổng**: cho report đang xem: claim, verdict authority, D/C theo
  rule (fidelity L1), cổng G1/G2 của phương án và G0/G3–G7 của dự án, audit đa
  cấu kiện, thẻ tri thức đã dùng (kèm trạng thái DRAFT), provenance đầy đủ.
- **Quy trình lab**: bảng task theo trạng thái, chi tiết task (write scope, tiêu
  chí, an toàn, review notes), handoff gần nhất, review chéo với gate findings.
- **Não 2**: thẻ tri thức, tìm theo rule/biến/từ khoá qua `query_knowledge`, mở
  trong Obsidian khi vault được phát hiện.
## 3. API

| Đường | Phương thức | Gọi gì |
|---|---|---|
| `/api/lab/overview` | GET | capability matrix, site profile, design basis, cards, oracle, `lab_status` |
| `/api/catalog` | GET | catalog, miền grammar v1/v2, anchor gene, gold cases |
| `/api/evaluate` | POST `{state}` | `evaluate_candidate` + `suggest_repairs` |
| `/api/section` | POST `{grammar_id, gene}` | `state_from_gene` → `check_geometry` → `compute_objectives`, biên `build_section_polygon` |
| `/api/design-loop` | POST `{seed_file | gene+grammar_id | seed_state, budget, policy}` | `run_design_loop`, lưu report có hash |
| `/api/design-loop/runs[/name]` | GET | danh sách / một report đã lưu |
| `/api/creative-search` | POST `{seed, iterations}` | `run_constrained_map_elites` với profile mặc định của lab |
| `/api/knowledge/cards`, `/api/knowledge/query` | GET | `load_cards`, `query_knowledge` |
| `/api/live-data`, `/api/lab-status`, `/api/obsidian` | GET | `multiagent/`, `lab_status` + `validate_lab`, vault Obsidian |
| `/api/midas/presets` GET; `/api/midas/psc-section`, `psc-family`, `propose`, `supert-value` POST | | `bridge_evolution/midas_section.py` (BRD-052), chỉ hình học |

Ngân sách solver bị chặn ở 400 và số biến dị MAP-Elites ở 400 để một cú bấm không
chiếm máy; muốn chạy lớn thì dùng CLI/experiments với pre-registration.

## 4. Giới hạn trung thực

- Profile kỹ thuật cho MAP-Elites là **giới hạn tìm kiếm mặc định của lab**,
  `clause_id = LAB-DEFAULT-UNSOURCED-*`, trỏ về chính file JSON của nó. Mọi hình
  thái sinh ra là `IDEA` và tự khai chưa có nguồn; thay bằng profile có
  `source_ref` thật trước khi diễn giải.
- Studio tiết diện chỉ là L0 + objective giải tích: chưa nói gì về chịu lực.
- Cổng G0 và G3–G7 đang chặn ở cấp dự án (site UNKNOWN, không L2/L3, không thí
  nghiệm, không kỹ sư duyệt). Lab hiển thị điều đó ở mọi màn thay vì giấu đi.
- Lab không thay `lab claim/submit/review`: giao diện chỉ đọc quy trình; mọi
  thay đổi trạng thái task vẫn qua CLI để giữ lock và hash.

## 5. Lộ trình nối vật lý thật (thứ tự không đổi được)

1. G0: điền site profile từ số liệu thật, kỹ sư duyệt.
2. L2 qua midas-mcp: adapter state → MCT → chạy → đọc kết quả thành evidence L2,
   benchmark với L1 trên gold case (G2, G4).
3. Grammar cốt thép thường + verifier RC theo TCVN 11823-5 (mới tối ưu được thép).
4. L3 giai đoạn thi công, từ biến co ngót, mất mát theo thời gian.
5. Thẻ tri thức và gold case lên ENGINEER_APPROVED trước khi nâng trần claim.

## 6. Kiểm thử và sửa lỗi sau khi dựng (2026-09-03)

Phiên dựng lab dừng ngay trước bước kiểm thử; phiên kế tiếp đã chạy và sửa:

| Vấn đề | Nguyên nhân | Sửa |
|---|---|---|
| `test_design_loop_api_saves_hashed_report` lệch SHA-256 | `write_text` trên Windows đổi LF thành CRLF nên hash file khác hash báo về UI (cùng họ lỗi BRD-024) | `api_design_loop` ghi **bytes** và băm đúng bytes đã ghi |
| Server sập ngay dòng banner | console cp1252 không in được đường dẫn repo có chữ Việt | ép `stdout`/`stderr` sang UTF-8 khi khởi động |
| Não 2 trống sau khi mở Bằng chứng | `loadKnowledge` bị bỏ qua vì màn Bằng chứng đã nạp sẵn `state.cards` | cờ `knowledgeLoaded`, mở lại màn thì render lại danh sách |
| Sửa `lab.js` mà trình duyệt vẫn chạy bản cũ | file tĩnh không có `Cache-Control` | server gửi `no-store` cho mọi phản hồi |

Đã kiểm trên trình duyệt (server thật, không mock): Tổng quan (thang cổng, 23 năng
lực, design basis, lab status), Bàn cấu kiện (chạy GC-06 budget 40 → CONVERGED,
khả thi, D/C 0,999, 29 solver, report lưu có hash, Inspector tự nạp lineage 12
bước), Bằng chứng (D/C theo rule, G1/G2 của phương án, audit BLOCKED, thẻ KC-001
đã dùng), Studio tiết diện v2 (L0 sạch tại anchor, bản vẽ tiết diện), MAP-Elites
(26 hình thái, claim IDEA, profile chưa có nguồn), Quy trình lab (bảng task theo
trạng thái, handoff, review), Não 2 (20 thẻ, chi tiết thẻ, tìm theo rule, link
Obsidian). Test: `tests/test_lab_api.py` 10/10; kèm `test_design_loop.py` và
`test_creative_shape.py` 79/79.
