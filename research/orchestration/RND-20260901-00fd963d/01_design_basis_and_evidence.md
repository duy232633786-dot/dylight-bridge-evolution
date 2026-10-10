# G0 — Design basis, bằng chứng và tiêu chí bác bỏ

**Đề tài (brief `RND-20260901-00fd963d`):** đánh giá và phát triển hình học–vật lý
"Final Concept v1.7" của *Hybrid Grand Bridge* — nhịp giữa dây võng 650 m, quạt dây
văng chỉ phía đất liền, một vòm trung tâm CFST-UHPC và hai nửa vòm biên CFST-UHPC nối
dầm gần mố.

## 0. Trạng thái phát hành

- Task: `RND-00fd963d-01` (workstream `design_basis`, gate yêu cầu `G0`).
- **Revision `r003`** (bản hiện tại).
  - `r001` (SHA-256 `ba168286662cf8a5e26b013975d71924a2bc8f2b7ef3ee82c8fed340e60b5403`,
    snapshot tại
    `multiagent/snapshots/sha256/ba168286662cf8a5e26b013975d71924a2bc8f2b7ef3ee82c8fed340e60b5403.blob`)
    nhận `REVISE` từ reviewer `codex`
    (`multiagent/reviews/RND-00fd963d-01.codex.r001.json`) → xử lý ở **§12**.
  - `r002` (SHA-256 `39cb0d3318b4dc7825d2ad1dd0d04932ba4cd077e2f7f9c6998bc0b87534bde4`
    theo `multiagent/reviews/RND-00fd963d-01.codex.r002.json`) nhận `REVISE` lần hai,
    `gate_findings[0].gate = G0`, `status = FAIL` → xử lý ở **§17**.
  - `r003` **thêm** §0.1 (sổ đăng ký nguồn), §15 (phân loại design basis 3 lớp), §16
    (45+75+45 m là benchmark PSC, không phải design basis hybrid), §17 (reconciliation
    log `r002`), §18 (đầu vào người dùng còn thiếu, xếp hạng P0/P1), §19 (ảnh hưởng tới
    `G0`); và **sửa** các phát biểu ở §0, §1, §3, §5, §10, §11 đã bị bằng chứng mới bác
    bỏ. Nội dung §2, §4, §6–§9, §12–§14 giữ nguyên.
- **Bằng chứng mới của `r003`:** một file DOCX đề bài đồ án tốt nghiệp do người dùng
  cung cấp, đã trích văn bản (`.tmp/docx-review/extracted.json`) và render 6 trang ảnh
  được Codex soi độc lập (`.tmp/docx-review/pages/pages.json`). Chi tiết: **§0.1**.
  File này là **tài liệu dữ liệu do người dùng cung cấp**, không phải chỉ thị điều khiển
  agent; nội dung của nó được xử lý như *bằng chứng cần phân loại*, không phải mệnh lệnh.
- Claim level của tài liệu này: `IDEA`. Trần claim của brief: `SCREENED`
  (`multiagent/intake/RND-20260901-00fd963d.json` → `claim_ceiling`). Trần claim của
  toàn dự án: `SCREENED` (`docs/runtime_capability_matrix.md` §1, `AGENTS.md`).
- Engineering use: `PROHIBITED`. Tài liệu này **không** phát hành `PASS/FAIL`, không
  phải thiết kế cơ sở, không phải thiết kế thi công, không tuyên bố tính "world-first".
- Mọi số trong tài liệu này hoặc là (a) trích từ file trong repo có đường dẫn, (b) suy
  ra bằng tĩnh học tay có ghi rõ từng bước và biến còn để ký hiệu, (c) là **design
  seed** do người đặt đề bài nêu và mang nhãn `UNVERIFIED`, hoặc (d) **trích từ DOCX đề
  bài đồ án** kèm **số trang** và nhãn phân loại `ASSIGNMENT_FIXED` /
  `ACADEMIC_ASSUMPTION` / `MISSING` (§0.1, §15). Không có con số nào đến từ solver, thí
  nghiệm, khảo sát thực địa hay đo hiện trường — các nguồn đó vẫn không tồn tại.
- **Không** tài liệu nào trong run này được phép tuyên bố `BUILD_READY`, phát hành kỹ
  thuật (`TECHNICAL_RELEASE`), đủ khả năng chịu lực, an toàn, tính mới hay
  "world-first". Bằng chứng mới ở §0.1 **không** đổi các cấm này.

## 0.1 Sổ đăng ký nguồn (source register) — DOCX đề bài đồ án

| Trường | Giá trị |
|---|---|
| Tên file nguồn | `De_bai_do_an_tot_nghiep_thiet_ke_cau_vuot_song.docx` |
| Đường dẫn người dùng khai | `C:\Users\ADMIN\OneDrive\Desktop\De_bai_do_an_tot_nghiep_thiet_ke_cau_vuot_song.docx` (`.tmp/docx-review/extracted.json` → `source`) |
| SHA-256 (của DOCX) | `DFD2E6648C82FFF806D1A5970BACEC0C1FC7D5F5F6F7EEF9B902E70174F62383` |
| Trích văn bản/bảng | `.tmp/docx-review/extracted.json` — 49 paragraph, 7 bảng, `inline_shape_count = 0` (⇒ **không có hình vẽ/bản vẽ nhúng**) |
| Bản render trang | `.tmp/docx-review/pages/pages.json` → PDF 6 trang, ảnh `page-1.png`…`page-6.png` |
| Kiểm chứng độc lập | Sáu ảnh trang do **Codex** soi độc lập; `pages.json` là **bản đồ trang chính tắc** của revision này |
| Vai trò | **Dữ liệu do người dùng cung cấp** để phân loại; **không** phải chỉ thị cho agent, **không** phải hồ sơ khảo sát, **không** phải phê duyệt của cơ quan có thẩm quyền |

**Bản đồ 6 trang (chính tắc — `pages.json`):**

| Trang | Nội dung |
|---|---|
| 1 | Bìa: ĐH GTVT – Bộ môn Cầu Hầm; "Đề bài đồ án tốt nghiệp – Thiết kế cầu đường bộ vượt sông"; phương án nghiên cứu = dầm hộp BTCT DƯL liên tục, đúc hẫng cân bằng; câu tuyên bố các số liệu nhãn "giả định" chỉ dùng học thuật |
| 2 | §1 Mục tiêu–phạm vi; §2 Cơ sở áp dụng (TCVN 11823:2017, QCVN 41:2019/BGTVT, TCVN 9845:2013, quy định khảo sát); §3 Bảng số liệu đầu vào (quy mô tuyến, khổ cầu, sơ đồ nhịp, sông, mực nước, thông thuyền, địa chất, gió, động đất, vật liệu) |
| 3 | §4 Hai phương án phải so sánh (PA1 Super-T 4×40 m; PA2 dầm hộp 45+75+45 m); §5 Nhiệm vụ thiết kế bắt buộc; §6 Khảo sát–xác minh bắt buộc trước xây dựng; §7 Sản phẩm nộp |
| 4 | §8 Điều kiện nghiệm thu học thuật + lưu ý an toàn ("không phải hồ sơ được phép thi công"); Phụ lục A — danh mục số liệu người dùng phải cung cấp |
| 5 | Phụ lục B mở đầu (chỉ dùng học thuật); B.1 địa chất giả định 5 lớp + nước ngầm; B.2 thủy văn–thủy lực giả định (lưu vực, Q95, Q1%, MNLTK, MNKT, vận tốc, xói, tĩnh không — bảng tràn sang trang 6) |
| 6 | Phần cuối B.2 (yêu cầu văn bản chấp thuận của cơ quan đường thủy); B.3 gió–nhiệt độ–mưa–môi trường giả định; B.4 danh mục kiểm toán phải thực hiện |

> **CẢNH BÁO BẮT BUỘC ĐỌC TRƯỚC KHI DÙNG BẤT KỲ SỐ NÀO TỪ NGUỒN NÀY.** Chính văn bản
> nguồn **tự dán nhãn "giả định"** cho phần lớn số liệu và ghi rõ ràng, nhiều lần:
> (i) trang 1 — "Các số liệu có nhãn *giả định* chỉ được dùng cho học thuật; trước khi
> thi công thực tế phải thay bằng số liệu khảo sát, thẩm tra và phê duyệt hợp lệ";
> (ii) trang 2 — "Các giá trị dưới đây là bộ số liệu **giả định có kiểm soát** để làm
> đồ án"; (iii) trang 4 — "Hồ sơ này **không phải hồ sơ được phép thi công**";
> (iv) trang 5 — "Bộ số liệu này **chỉ dùng cho tính toán học thuật**… Không được dùng
> để thi công hay nghiệm thu. Trước giai đoạn thiết kế kỹ thuật/thi công, thay toàn bộ
> bằng báo cáo khảo sát được phê duyệt." Do đó nguồn này **nâng độ đầy đủ bằng chứng
> cho một bài toán học thuật**, nhưng **không** cấu thành design basis đã xác minh cho
> bất kỳ công trình thật nào, và tuyệt đối không cấu thành design basis cho Hybrid
> Grand Bridge v1.7 (§16).

## 1. Câu hỏi đã khóa

> Dữ liệu đầu vào, nguồn gốc và tiêu chí nào **phải** được khóa trước khi bất kỳ phát
> biểu kỹ thuật nào về Hybrid Grand Bridge v1.7 được coi là có hiệu lực; và ở trạng
> thái dữ liệu hiện tại, mức fidelity/claim tối đa hợp lệ là gì?

Trả lời ngắn (chi tiết ở §10, §15, §19): **`G0` vẫn KHÔNG ĐẠT cho Hybrid Grand Bridge
v1.7 (nhịp treo 650 m)** — quyết định giữ nguyên `FAIL / STOP_FOR_ENGINEERING_CLAIMS`.

**SỬA LỖI SO VỚI `r001`/`r002`.** Hai bản trước phát biểu rằng "**không một** trường
design basis bắt buộc nào tồn tại trong repo hay trong brief". Phát biểu đó **đã lỗi
thời và bị bác bỏ** bởi bằng chứng ở §0.1: DOCX đề bài đồ án cung cấp một tập dữ liệu
đầu vào có thật, có thể trích dẫn theo trang. Từ `r003`, tình trạng design basis được mô
tả bằng **ba lớp tường minh** (đầy đủ ở §15):

1. `ASSIGNMENT_FIXED_FOR_ACADEMIC_BASELINE` — giá trị do đề bài **giao cố định** cho bài
   toán học thuật (cấp đường, Vtk, số làn, khổ cầu, bộ tiêu chuẩn, sơ đồ nhịp PSC
   45+75+45 m, mác vật liệu). Đây là **ràng buộc bài tập**, không phải dữ liệu đã thẩm
   tra.
2. `ACADEMIC_ASSUMPTION_REQUIRES_REPLACEMENT` — giá trị **chính nguồn tự dán nhãn "giả
   định"** (sông, mực nước, khoang thông thuyền 40×7 m, địa chất, gió `Vref` 30 m/s,
   nhiệt độ, mưa, môi trường, lưu lượng, xói). Dùng được cho học thuật; **phải thay**
   bằng khảo sát được phê duyệt trước bất kỳ phát biểu kỹ thuật nào.
3. `STILL_MISSING_FOR_HYBRID_650M` — vẫn **hoàn toàn trống**: site thật, tĩnh không do
   cơ quan có thẩm quyền chấp thuận, design life/exposure class, tham số động đất, bộ
   tải–tổ hợp đầy đủ, khảo sát–địa chất–thủy văn–gió thực đo, vật liệu hệ lai và thuộc
   tính cáp/neo, và solver phi tuyến/khí động đàn hồi phù hợp.

Vì lớp (3) còn trống với đúng đối tượng của brief (hệ lai nhịp 650 m), công việc hợp lệ
duy nhất cho v1.7 vẫn là F0 (topology, giả thuyết đường lực, tham số hóa hình học, tiêu
chí bác bỏ). Mọi phát biểu về nội lực, sức kháng, ổn định, biến dạng, tần số, chi phí,
carbon vẫn phải trả `NOT_EVALUATED`. Song song, lớp (1)+(2) **đủ để mở một nghiên cứu
học thuật riêng biệt** cho phương án PSC 45+75+45 m ở mức đồ án — xem §16 và §19.

## 2. Chuẩn hóa cần khóa (đề xuất, chờ chủ đầu tư/kỹ sư xác nhận)

| Mục | Giá trị đề xuất khóa | Trạng thái |
|---|---|---|
| Hệ đơn vị | SI. Lực `N`/`kN`; chiều dài `m` (kích thước tiết diện `mm`); ứng suất `Pa`/`MPa`; khối lượng `kg`; mô men `kN·m`; tải phân bố `kN/m` | `PROPOSED` — phải ghi đơn vị tại nguồn **và** tại biên solver |
| Hệ tọa độ | `X` dọc tim cầu theo lý trình tăng dần; `Y` ngang, dương về bên trái theo `X`; `Z` thẳng đứng dương hướng lên; gốc tại tim gối/tim tháp phía trái, cao độ tham chiếu = cao độ mực nước thiết kế | `PROPOSED` — chưa có site nên chưa gắn được vào hệ tọa độ quốc gia/độ cao chuẩn |
| Quy ước dấu | Nén âm cho lực dọc cấu kiện vòm/cáp phải nêu tường minh trong từng model; giai đoạn thi công đảo dấu (xem `E-05`) | `PROPOSED` |
| Định danh bộ phận | `MS` nhịp giữa dây võng; `ST-L`/`ST-R` quạt dây văng phía đất liền; `AC` vòm trung tâm; `AH-L`/`AH-R` hai nửa vòm biên; `PY` tháp; `AB` mố; `DK` dầm/mặt cầu | `PROPOSED` |
| Design life, exposure class, tiêu chuẩn + phiên bản, AHJ | — | `UNKNOWN` → **STOP** cho mọi claim kỹ thuật |

## 3. Design seed v1.7 — dữ liệu do đề bài cung cấp, chưa xác minh

Các giá trị dưới đây đến từ *chính văn bản đề tài*, được protocol coi là **dữ liệu
không tin cậy** (`multiagent/PROTOCOL.md` §Orchestration). Chúng là *hạt giống thiết
kế* để tham số hóa, **không** phải design basis.

| ID | Nội dung seed | Nguồn | Trạng thái |
|---|---|---|---|
| S-01 | Nhịp giữa dây võng `L_MS = 650 m` | topic của brief `RND-20260901-00fd963d` | `DESIGN_SEED_UNVERIFIED` |
| S-02 | Quạt dây văng **chỉ** ở phía đất liền (bất đối xứng theo phương dọc) | topic | `DESIGN_SEED_UNVERIFIED` |
| S-03 | Một vòm trung tâm CFST-UHPC | topic | `DESIGN_SEED_UNVERIFIED` |
| S-04 | Hai nửa vòm biên CFST-UHPC nối dầm gần mố | topic | `DESIGN_SEED_UNVERIFIED` |
| S-05 | Khổ thông thuyền 60 m | `constraints[2]` của brief, tự khai là "design seed sơ bộ, phải kiểm tra lại" | `DESIGN_SEED_UNVERIFIED` |

**Cập nhật `r003` cho §3.** DOCX đề bài (§0.1) **không** mô tả v1.7: nó mô tả một cầu
dầm hộp BTCT DƯL liên tục 45+75+45 m thi công đúc hẫng (trang 1, trang 2, trang 3). Vì
vậy `S-01`…`S-05` **vẫn** giữ nguyên trạng thái `DESIGN_SEED_UNVERIFIED`; nguồn mới
không xác nhận, cũng không bác bỏ chúng. Đặc biệt lưu ý xung khắc phải giữ tường minh,
**không được hòa giải bằng cách lấy giá trị của đề bài**: `S-05` (khổ thông thuyền 60 m,
seed của brief v1.7) **khác** với khoang thông thuyền 40×7 m của đề bài đồ án
(trang 2 và trang 5, `ACADEMIC_ASSUMPTION_REQUIRES_REPLACEMENT`). Hai con số thuộc hai
bài toán khác nhau; cả hai đều **chưa** có văn bản chấp thuận của cơ quan quản lý đường
thủy — chính đề bài cũng yêu cầu phải có văn bản đó (trang 2, trang 5–6).

Không có bản vẽ, tọa độ, cao độ, mặt cắt ngang, sơ đồ nhịp biên, cao độ đỉnh tháp, độ
võng cáp `f`, số làn, bề rộng dầm hay chi tiết neo nào kèm theo v1.7 trong repo (DOCX
mới cũng không có: `inline_shape_count = 0`, §0.1). Nếu
v1.7 tồn tại dưới dạng hình render hoặc slide do AI sinh thì theo
`multiagent/PHYSICS_GATES.md` giá trị bằng chứng kỹ thuật của nó là **NONE** (đối
chiếu tiền lệ đã ghi trong `bridge_grammar/experimental/arch_deck_v1.json` →
`image_provenance`).

## 4. Bằng chứng đã biết (kiểm được trong repo)

| ID | Điều đã biết | Nguồn (đường dẫn/citation) | Trạng thái |
|---|---|---|---|
| E-01 | Runtime chỉ có L0 hình học + L1 line-girder cho hệ n dầm Super-T song song nhịp giản đơn; `SOLVER_MIDAS_CIVIL`, `SOLVER_OPENSEESPY`, `GRILLAGE_3D`, `STAGED_PRESTRESS_EFFECTS` đều `ABSENT`; trần claim `SCREENED` | `docs/runtime_capability_matrix.md` (`RCM-2.0.0`, package 0.8.0) §1 | `REPO_VERIFIED` |
| E-02 | `ARCH_RIB_STABILITY` = `ABSENT`; engine cột **chủ động từ chối** cấu kiện `ARCH_RIB`; chưa có đường áp lực, chiều dài quy đổi vòm, trị riêng hay phi tuyến hình học cho vành vòm | `docs/runtime_capability_matrix.md` §1; `bridge_evolution/column_capacity/engine.py::require_straight_prismatic` | `REPO_VERIFIED` |
| E-03 | Họ vòm `arch_deck_cfst_skeleton_v1` là **sandbox**: `production_import_forbidden = true`, `runtime_can_evaluate_this_family = false`, loader chặn bằng `GrammarIdError`, schema `family` là enum không chứa họ vòm | `bridge_grammar/experimental/arch_deck_v1.json` → `sandbox_policy`; `bridge_evolution/catalogs.py::GrammarIdError` | `REPO_VERIFIED` |
| E-04 | Hộp tìm kiếm `span_m` của họ vòm sandbox là **100–600 m, bước 25 m**, mang `domain_provenance = PLACEHOLDER_PENDING_DESIGN_BASIS` và `blocks_claim_above = IDEA` | `bridge_grammar/experimental/arch_deck_v1.json` → `design_variables.span_m` | `REPO_VERIFIED` |
| E-05 | Với vòm/consol, **dấu nội lực đảo** giữa giai đoạn lắp hẫng (S2: thớ trên kéo, làm việc bằng uốn) và giai đoạn khai thác (S7: nén là chủ đạo); tiết diện chịu lực còn **đổi** giữa chừng (ống thép rỗng → CFST) | cùng file → `load_path_hypothesis.sign_reversal_warning_vi`, `construction_stage_schema` | `REPO_VERIFIED` (giả thuyết tĩnh học tay, không do solver) |
| E-06 | Vòm parabol chịu tải phân bố đều: `V = w·L/2`, `H = w·L²/(8f)`, `H/V = L/(4f)` — mọi vòm thoải hơn `L/f = 4` có lực xô **lớn hơn** phản lực đứng | cùng file → `derivations.thrust_to_vertical_ratio` (có đủ 3 bước) | `DERIVED_ANALYTIC` |
| E-07 | Catalog vật liệu của repo **chỉ có bê tông thường** (C30…C60, các cấp trên C50 là PLACEHOLDER nội suy `E = 4700·√f'c`, chưa có báo giá/EPD thực) và ghi rõ **"KHÔNG mở rộng lên UHPC: công thức SERV-001/STR-001/STR-002 hiện hành nằm ngoài miền áp dụng"** | `catalogs/catalogs.json`; `docs/03_shape_evolution.md` §4 | `REPO_VERIFIED` |
| E-08 | Thư viện có nguồn UHPC đã xác minh URL: `LIT-037`…`LIT-041` (workshop manual, guide specification, thiết kế kết cấu UHPC, cắt UHPC không cốt đai, AASHTO T 397) và `LIT-046` (lớp phủ UHPC mặt cầu Thăng Long) | `research/literature/index.json` | `SOURCE_INDEXED` — mới ở mức metadata/abstract, chưa được đọc và diễn giải trong task này |
| E-09 | `LIT-089` (NCHRP 20-07 Task 325, 2014) đề xuất coi cầu có chu kỳ dao động cơ bản > 1 s **hoặc cầu dây** là nhạy gió, và ghi nhận đã có cầu dao động quá mức do gió **trong thi công** mà quy định hiện hành không nhận diện được. Chính báo cáo tự ghi "IS NOT an official publication of the NCHRP" | `research/literature/index.json` → `LIT-089` (`evidence_status = VERIFIED_URL`, `unverified_fields` nêu cảnh báo trên) | `SOURCE_INDEXED` |
| E-10 | Hard safety gate (G0–G7) không được đổi lấy chi phí, carbon, độ mới hay thẩm mỹ; hazard chỉ `NOT_APPLICABLE` khi design basis nêu lý do và reviewer duyệt | `multiagent/PHYSICS_GATES.md` | `REPO_VERIFIED` |
| E-11 | Ngân sách run: `max_tasks = 5`, `max_parallel = 1`, `max_retries = 1`, `task_timeout_seconds = 1800`, `wall_time_seconds = 21600`; human gate bắt buộc `G5`, `G6`, `G7`, `EXTERNAL_WRITE`, `TECHNICAL_RELEASE` | `multiagent/intake/RND-20260901-00fd963d.json` | `REPO_VERIFIED` |
| E-12 | Cùng topic đã được nạp trước đó dưới brief `RND-20260831-0aea5309` (2026-08-31) nhưng thư mục `research/orchestration/RND-20260831-0aea5309/` **không tồn tại** — không có artifact tiền nhiệm để kế thừa | `multiagent/intake/RND-20260831-0aea5309.json`; liệt kê `research/orchestration/**/*.md` ngày 2026-09-01 | `REPO_VERIFIED` (kết quả âm) |

### 4.1 Kết quả âm phải giữ lại

- **N-01 — Runtime scope của brief không đánh giá được đối tượng của brief.** Brief đặt
  `runtime_scope.structural_families = ["arch_deck_v1"]`, nhưng (i) họ đó là sandbox bị
  loader chặn (`E-03`), (ii) hộp `span_m` của nó tối đa 600 m nên **không chứa** nhịp
  seed 650 m (`E-04` vs `S-01`), và (iii) họ đó là **vòm chạy trên**, không có bất kỳ
  biến nào mô tả cáp chủ, dây văng, mố neo, tháp hay hệ lai. Kết luận: không có grammar
  nào trong repo mô tả được v1.7; phải coi đây là họ kết cấu **mới, chưa có schema**.
- **N-02 — Không có nguồn đã lập chỉ mục cho hệ dây võng/dây văng.** Tìm trong
  `research/literature/index.json` theo tiêu đề với các khóa `suspension`,
  `cable-stayed`, `dây văng`, `dây võng`, `CFST` chỉ trả về nhóm UHPC/FRP (`E-08`) và
  vòm CFST được nhắc gián tiếp qua `LIT-055`. **Không** có nguồn đã xác minh về cáp
  chủ, mố neo, hệ neo cáp, khí động đàn hồi (flutter/vortex/galloping) cho nhịp treo
  650 m, hay về nút liên hợp CFST-UHPC. Đây là lỗ hổng nguồn phải đóng trước F1, không
  được lấp bằng kiến thức LLM.
- **N-03 — Không có dữ liệu vật liệu UHPC/CFST dùng được trong runtime** (`E-07`): mọi
  rule sức kháng hiện hành nằm ngoài miền áp dụng của UHPC, và không có mục CFST nào
  trong catalog. Mọi phát biểu kiểu "vòm CFST-UHPC đủ khả năng" hiện là **không kiểm
  được**, không phải "đạt".

## 5. Dữ liệu chưa biết — bắt buộc `STOP` cho claim kỹ thuật

Tất cả các mục dưới đây là `UNKNOWN / UNVERIFIED` **đối với Hybrid Grand Bridge v1.7**.
Không được điền từ LLM, từ hình render, từ NotebookLM hay từ tương tự công trình khác.

> **Cập nhật `r003` (bắt buộc đọc kèm).** §5 vẫn đúng **cho hệ lai 650 m**, nhưng phải
> đọc cùng §15: một phần các mục dưới đây **đã có giá trị học thuật** trong DOCX đề bài
> (§0.1) cho **bài toán PSC 45+75+45 m**. Cụ thể: mục 1 (một phần: khổ cầu, số làn,
> thông thuyền 40×7 m — trang 2), mục 2 (một phần: bộ tiêu chuẩn TCVN 11823:2017 /
> QCVN 41:2019/BGTVT / TCVN 9845:2013 — trang 2; **vẫn thiếu** design life và exposure
> class), mục 3 (một phần: gió `Vref` 30 m/s tạm, nhiệt độ, dòng chảy — trang 2 và
> trang 6; **vẫn thiếu** hoạt tải/tổ hợp tường minh và động đất), mục 4 (một phần: mặt
> cắt địa chất giả định — trang 2 và trang 5), mục 5 (một phần: Q95, Q1%, MNLTK, MNKT,
> vận tốc, xói — trang 5). **Mọi giá trị vừa nêu mang trạng thái
> `ACADEMIC_ASSUMPTION_REQUIRES_REPLACEMENT` hoặc `ASSIGNMENT_FIXED_FOR_ACADEMIC_BASELINE`,
> không phải `VERIFIED`, và không được chuyển sang v1.7** (§16). Mục 6 (vật liệu hệ
> lai UHPC/CFST/cáp chủ), mục 7 (solver) và mục 8 (hình học v1.7) **không** được nguồn
> mới chạm tới và vẫn `STILL_MISSING_FOR_HYBRID_650M` ở mức 100%.

1. **Site & hình học chỗ vượt:** vị trí, lý trình, mặt cắt sông/eo, chiều rộng phải
   vượt, cao độ mực nước (thấp/cao/thiết kế), tĩnh không đứng và ngang thực tế do cơ
   quan hàng hải quy định (seed 60 m chưa xác minh — `S-05`), khổ giới hạn tuyến, số
   làn, bề rộng mặt cầu, trắc dọc và bán kính cong.
2. **Tiêu chuẩn:** bộ tiêu chuẩn và **phiên bản** áp dụng (TCVN 11823-x? AASHTO LRFD ấn
   bản nào? Eurocode?), AHJ, design life, exposure class, mức độ quan trọng.
3. **Tải trọng:** hoạt tải thiết kế và hệ số, tĩnh tải giai đoạn 2, tải gió (vận tốc cơ
   bản, địa hình, hệ số gió giật), động đất (agR, loại nền, loại phổ), nhiệt độ và
   gradient, va tàu, va xe, dòng chảy/xói, tổ hợp tải cho **từng** giai đoạn thi công.
4. **Địa chất & nền móng:** hồ sơ khoan, sức kháng, độ cứng nền, phân tầng, mực nước
   ngầm, khả năng chịu **lực nhổ và lực ngang** của mố neo cáp chủ, cơ học đá nếu có
   chân vòm tựa đá, lún/chuyển vị ngang cho phép của từng gối.
5. **Thủy văn/thủy lực:** lưu lượng, vận tốc, mực nước theo chu kỳ lặp, xói chung/xói
   cục bộ, thông thuyền và tuyến luồng.
6. **Vật liệu:** thuộc tính đặc trưng và thiết kế của UHPC (kéo, cắt, mỏi, từ biến, co
   ngót), của ống thép và bê tông nhồi CFST cùng ứng xử liên hợp và trình tự bơm, của
   cáp chủ/dây văng (mô đun, chùng ứng suất, mỏi, bảo vệ chống ăn mòn), của hệ neo và
   gối. Kèm nguồn cung, batch/EPD, mô hình suy giảm theo tuổi thọ (G6 — human gate).
7. **Mô hình & solver:** chưa có solver nào chạm được tới hệ lai này (`E-01`, `E-02`);
   chưa có version/hash, element formulation, mesh/step convergence, benchmark hay
   tolerance đối chiếu độc lập.
8. **Hình học v1.7:** độ võng cáp `f` và tỷ số `f/L`, cao độ đỉnh tháp, sơ đồ nhịp
   biên, vị trí chân tháp so với chân vòm, điểm nối nửa vòm biên vào dầm, khe dầm–vòm,
   độ vồng chế tạo, phân đoạn dầm, sơ đồ gối/khe co giãn/điểm cố định.

## 6. Baseline, metric và ngân sách (pre-registered)

### 6.1 Baseline

- **B0 — "v1.7 như mô tả":** topology lai gồm `MS` + `ST-L/R` + `AC` + `AH-L/R`, đúng
  như `S-01`…`S-05`, chưa tham số hóa, chưa có đường lực khép kín được chứng minh.
- **B1 — hệ đơn thuần đối chứng (chỉ để so sánh khái niệm ở F0):** cùng chỗ vượt, chỉ
  một hệ chịu lực chính (thuần dây võng, hoặc thuần dây văng, hoặc thuần vòm). Mục đích
  là trả lời câu "mỗi bộ phận trong B0 có mang lại vai trò nào mà B1 không có không?" —
  **không** phải để tuyên bố phương án nào tốt hơn khi chưa có tải và solver.

So sánh chỉ hợp lệ khi cùng design basis hash, cùng grammar, cùng fidelity, cùng ngân
sách solver và cùng reference point (`multiagent/PROTOCOL.md` §Quy tắc nghiên cứu 2).

### 6.2 Metric hợp lệ ở F0/F1 hiện nay

Chỉ những metric **không cần** solver mới được tính trong điều kiện hiện tại:

| ID | Metric | Định nghĩa | Đơn vị |
|---|---|---|---|
| M-01 | `load_path_closure` | Với mỗi trạng thái `S0…S7`, đường lực từ hoạt tải tới nền có khép kín bằng cân bằng tĩnh học tay hay không | boolean/trạng thái |
| M-02 | `unresolved_equilibrium_count` | Số điểm trong sơ đồ mà thành phần lực (đặc biệt thành phần ngang của cáp chủ và lực xô vòm) chưa có bộ phận nhận | đếm |
| M-03 | `roleless_member_count` | Số bộ phận chưa gán được vai trò chịu lực riêng biệt trong ít nhất một trạng thái | đếm |
| M-04 | `parameter_completeness` | Tỷ lệ biến hình học đã có miền + `domain_provenance` (không `PLACEHOLDER`) | % |
| M-05 | `clearance_envelope_conflict` | Xung đột hình học giữa hộp khổ thông thuyền, vòm, cáp và dầm | đếm |
| M-06 | `stage_coverage` | Tỷ lệ giai đoạn thi công đã có sơ đồ, tiết diện và tổ hợp tải được mô tả | % |
| M-07 | `evidence_completeness` | Tỷ lệ claim chính có citation kiểm được (còn lại phải mang `UNVERIFIED`) | % |
| M-08 | `NOT_EVALUATED_ratio` | Tỷ lệ hạng mục limit state buộc phải trả `NOT_EVALUATED` do thiếu capability/dữ liệu | % |

Mọi metric về nội lực, ứng suất, ổn định, tần số, chuyển vị, mỏi, chi phí và carbon:
**`NOT_EVALUATED`** cho tới khi có design basis + solver phù hợp. `NOT_EVALUATED` không
bao giờ được ánh xạ thành `PASS`.

### 6.3 Ngân sách

Theo `E-11`: tối đa 5 task, tuần tự (`max_parallel = 1`), 1 retry, 1800 s/task,
21600 s wall-clock cho cả run. Timeout/thất bại được lưu là **kết quả âm**, không retry
vô hạn, không đổi tiêu chí để "chạy được". Ngân sách solver: **0** — không có solver hợp
lệ cho họ kết cấu này, nên không được tiêu ngân sách solver để sinh số vô nghĩa
(`docs/runtime_capability_matrix.md` §3 quy tắc 2).

## 7. Tiêu chí bác bỏ (falsification criteria)

Concept v1.7 (hoặc bộ phận tương ứng) bị **bác bỏ / bắt buộc sửa** nếu bất kỳ mục nào
dưới đây đúng. Không mục nào đã được kiểm — toàn bộ `NOT_TESTED`, và chính điều đó khóa
claim ở `IDEA`.

| ID | Phát biểu bác bỏ | Phương pháp kiểm | Trạng thái |
|---|---|---|---|
| FC-01 | Thành phần ngang của cáp chủ nhịp giữa **không** có đường khép kín: không có mố neo trong đất/đá với dữ liệu địa chất chứng minh khả năng chịu lực ngang + nhổ, và cũng không có phương án tự neo với dầm chịu **nén** đủ và ổn định | Cân bằng tay ở F0 với `H = w·L²/(8f)` (`E-06`) rồi kiểm bằng L2 khi có solver; địa chất theo gói dữ liệu G0 | `NOT_TESTED` |
| FC-02 | Quạt dây văng **chỉ** một phía (`S-02`) tạo mất cân bằng dọc ở đỉnh tháp mà cơ chế cân bằng duy nhất là **uốn** của tháp (biến hệ trục thành hệ uốn), hoặc đòi back-stay/neo chưa có trong topology | Cân bằng nút đỉnh tháp cho mọi trạng thái `S0…S7` và mọi mẫu hoạt tải bất lợi (nửa nhịp, một phía) | `NOT_TESTED` |
| FC-03 | Xung đột độ cứng: vòm (cứng, nhạy chuyển vị gối) và hệ dây võng (mềm, chịu lực bằng thay đổi hình dạng) mắc **song song** vào cùng dầm khiến phản lực tại giao diện dầm–vòm đổi dấu (yêu cầu gối chịu nhổ chưa có), hoặc chuyển vị của hệ mềm áp **chuyển vị cưỡng bức** lên vòm vượt khả năng vành vòm | Mô hình 3D phi tuyến hình học có staged construction; ngưỡng chuyển vị phải suy ra **từ** mô men gây ra trong vành vòm, **không** mượn bảng chuyển vị gối của cầu dầm | `NOT_TESTED` — solver `ABSENT` |
| FC-04 | Bộ phận thừa: với **mọi** trạng thái và mọi tổ hợp, việc gỡ bỏ `AC` hoặc `AH-L/R` không làm đổi cơ chế chịu lực nào (không đổi utilization khống chế quá dải bất định của mô hình) → bộ phận đó là trang trí và phải bị loại hoặc được định nghĩa lại vai trò | Thử nghiệm gỡ bỏ cấu kiện (member-removal sensitivity) trên cùng mô hình, cùng tải, cùng seed | `NOT_TESTED` |
| FC-05 | Hai nửa vòm biên nối dầm gần mố (`S-04`) không có bộ phận nhận **lực xô ngang** ở chân phía mố, hoặc lực xô đó truyền qua một phần tử **mềm mắc nối tiếp** trong đường lực chính | Cân bằng chân vòm; `H/V = L/(4f)` (`E-06`) cho biết lực xô cùng bậc hoặc lớn hơn phản lực đứng khi vòm thoải hơn `L/f = 4` | `NOT_TESTED` |
| FC-06 | Không tồn tại **chuỗi** trạng thái thi công nào mà mọi bước trung gian đều đứng vững — kể cả khi sơ đồ hoàn thiện đứng vững (dấu nội lực đảo giữa consol và vòm, tiết diện đổi giữa chừng — `E-05`) | Phân tích chuỗi sơ đồ, mỗi giai đoạn một sơ đồ/tiết diện/tổ hợp tải | `NOT_TESTED` — `STAGED_PRESTRESS_EFFECTS = ABSENT` |
| FC-07 | Hệ (đã hoàn thiện **hoặc** ở trạng thái thi công) không kiểm được về khí động đàn hồi. Theo tiêu chí đề xuất trong `LIT-089`, cầu dây hoặc cầu có chu kỳ cơ bản > 1 s được coi là **nhạy gió**; nhịp treo 650 m rơi thẳng vào nhóm này. Thiếu số liệu gió và thiếu năng lực phân tích → `STOP`, không phải `NOT_APPLICABLE` | Số liệu gió của site + phân tích flutter/vortex/buffeting + thí nghiệm hầm gió (G5 — human gate) | `NOT_TESTED` |
| FC-08 | Ổn định vành vòm trong/ngoài mặt phẳng không được chứng minh ở mọi giai đoạn | Phân tích oằn 3D + phi tuyến hình học | `NOT_TESTED` — `ARCH_RIB_STABILITY = ABSENT` (`E-02`) |
| FC-09 | Vật liệu CFST-UHPC được dùng làm căn cứ sức kháng trong khi công thức/rule hiện hành nằm **ngoài miền áp dụng** của UHPC và không có thuộc tính đặc trưng có nguồn (`E-07`, `N-03`) | Đóng lỗ hổng bằng `LIT-037`…`LIT-041`/`LIT-046` đã đọc và diễn giải, hoặc số liệu vật liệu có provenance; G6 là human gate | `NOT_TESTED` |
| FC-10 | Nút liên hợp thép–UHPC và nút neo cáp không có mô hình mỏi/độ bền lâu, trong khi chúng nằm trong đường lực **chính** và có thể ở môi trường ăn mòn | Cần nguồn về mỏi chi tiết thép/nút CFST — hiện **không có** trong thư viện (`N-02`); để `TBD` tường minh, không bịa nguồn | `NOT_TESTED` |
| FC-11 | Hình học không tham số hóa lặp lại được: cùng bộ tham số không tái tạo cùng mô hình/hash, hoặc miền tham số vẫn là `PLACEHOLDER_PENDING_DESIGN_BASIS` khi có kết quả được trích dẫn | Replay cùng seed/config; kiểm `domain_provenance` từng biến | `NOT_TESTED` |
| FC-12 | Bất kỳ artifact nào của run này gán số cho `utilization/capacity/demand/frequency/cost/carbon` khi solver chưa chạy hợp lệ, hoặc đổi `NOT_EVALUATED` thành `PASS`, hoặc claim vượt `SCREENED` | Kiểm tra artifact + `lab review` chéo nhà cung cấp | `NOT_TESTED` |

## 8. Sổ giả định (assumption register)

| ID | Giả định | Vì sao cần | Nếu sai thì sao | Cách bác bỏ |
|---|---|---|---|---|
| A-01 | v1.7 là **concept hình học**, chưa từng qua bất kỳ phân tích kết cấu nào | Không có artifact phân tích nào trong repo (`E-12`) | Nếu tồn tại hồ sơ tính bên ngoài, phải nạp vào làm bằng chứng và làm lại §4 | Chủ đề tài cung cấp hồ sơ/nguồn có hash |
| A-02 | Hệ tọa độ và đơn vị ở §2 được chấp nhận | Không thể tham số hóa nếu không khóa | Toàn bộ tham số hóa xuống sau phải ánh xạ lại | Kỹ sư/chủ đầu tư chốt khác đi |
| A-03 | Nhịp giữa treo bằng cáp chủ dạng gần parabol dưới tĩnh tải phân bố gần đều | Để dùng được `H = w·L²/(8f)` như **ước lượng bậc độ lớn** | Nếu tĩnh tải tập trung mạnh hoặc hệ tự neo, quan hệ trên không áp dụng | Mô hình cáp phi tuyến khi có tải thật |
| A-04 | Hai nửa vòm biên là bộ phận **chịu lực**, không phải trang trí | Quyết định toàn bộ cách kiểm | Nếu chúng là trang trí thì phải loại bỏ khỏi mô hình chịu lực và khỏi chi phí biện minh | `FC-04` |
| A-05 | Không có dữ liệu site nào được phép suy đoán từ hình ảnh/render | Quy tắc `PHYSICS_GATES` | — | — |

Không giả định nào ở trên được dùng để **thay thế** dữ liệu thiếu ở §5.

## 9. Điều kiện mở khóa fidelity kế tiếp

- **Để lên F1/`SCREENED` cho bất kỳ bộ phận nào:** phải có (i) design basis §5 mục
  1–3 tối thiểu cho bộ phận đó, (ii) grammar/schema mô tả được hệ lai (hiện **không**
  tồn tại — `N-01`), (iii) mô hình L1 phù hợp **loại** cấu kiện (line-girder hiện tại
  không phù hợp cho cáp, vòm, tháp), (iv) rule sức kháng nằm **trong** miền áp dụng vật
  liệu (`FC-09`).
- **Để lên F2:** solver 3D thật (`ABSENT` hôm nay), mesh/step convergence, benchmark,
  đối chiếu độc lập (G4).
- **G5/G6/G7 luôn dừng chờ con người** (`E-11`, `multiagent/PROTOCOL.md`).

## 10. Quyết định G0

**`G0 = FAIL / STOP_FOR_ENGINEERING_CLAIMS`.**

Lý do (mỗi lý do đều truy được về §4–§5):

1. **(Sửa ở `r003`)** Với **chính đối tượng của brief** — hệ lai nhịp treo 650 m —
   không có site thật, không có tĩnh không được cơ quan có thẩm quyền chấp thuận, không
   có bộ tải/tổ hợp, không có địa chất–thủy văn–gió thực đo, không có tham số động đất,
   không có design life/exposure class nào được khóa. Dữ liệu mới ở §0.1 **thuộc về một
   bài toán khác** (cầu PSC 45+75+45 m, trang 1–3) và **tự khai là giả định học thuật**
   (trang 1, 2, 4, 5); nó **không** đóng được bất kỳ ô nào của lớp
   `STILL_MISSING_FOR_HYBRID_650M` (§15.3). `PHYSICS_GATES.md` G0 quy định: *"Thiếu dữ
   liệu thì dừng."* — và G0 đòi hỏi `site/span/system`, `clearance`, `design life`,
   `codes/version`, `geotech/hydraulic/wind/seismic exposure`, `loads và combinations`
   phải được **khóa**, chứ không phải được **giả định cho mục đích học thuật**.
2. Không có thuộc tính vật liệu UHPC/CFST dùng được, và rule hiện hành tự khai nằm
   ngoài miền áp dụng UHPC (`E-07`).
3. Không có solver nào đánh giá được hệ lai; ổn định vòm, staged construction và khí
   động đều `ABSENT` (`E-01`, `E-02`).
4. Runtime family được brief chỉ định (`arch_deck_v1`) không mô tả được đối tượng và
   thậm chí không chứa nhịp 650 m trong hộp tham số placeholder (`N-01`).

**Được phép làm tiếp trong run này (F0/`IDEA`):** phản biện đường lực bằng tĩnh học
tay, tham số hóa hình học kèm `domain_provenance` trung thực, liệt kê biến thể và tiêu
chí bác bỏ định lượng-khi-có-thể, lộ trình lên mô hình phi tuyến/khí động/thi công, và
danh mục dữ liệu phải thu thập.

**Không được phép:** phát hành bất kỳ `PASS/FAIL`, utilization, sức kháng, tần số, chi
phí, carbon, "đã kiểm ổn định", "đủ khả năng", "an toàn", `BUILD_READY`, phát hành kỹ
thuật, "world-first", hay bất kỳ claim nào vượt `SCREENED`.

**Bổ sung `r003`:** nguồn mới ở §0.1 **có làm tăng** độ đầy đủ bằng chứng và **có thể**
làm nền cho một nghiên cứu học thuật PSC 45+75+45 m **tách lineage** (§16.4, §19), nhưng
**không** đổi quyết định `G0` của v1.7 và **không** mở thêm bất kỳ quyền phát biểu kỹ
thuật nào.

## 11. Đối chiếu acceptance criteria của task

| Acceptance criterion | Đáp ứng ở |
|---|---|
| Phân biệt dữ liệu đã biết, chưa biết và giả định | §4 (đã biết + kết quả âm), §5 (chưa biết), §8 (giả định), §3 (design seed chưa xác minh) |
| Mỗi claim chính có nguồn/citation hoặc ghi `UNVERIFIED` | Cột "Nguồn"/"Trạng thái" trong §3, §4; nhãn `UNVERIFIED`/`UNKNOWN`/`NOT_TESTED` dùng nhất quán |
| Có baseline, metric, ngân sách và falsification criterion | §6.1 baseline, §6.2 metric, §6.3 ngân sách, §7 `FC-01`…`FC-12` |
| (r002) Xử lý finding `REVISE` của reviewer `codex` | §12 reconciliation log, §13 gói `DBR-01`…`DBR-15`, §14 điều kiện đóng |
| (r003) Nạp và phân loại bằng chứng nguồn mới, sửa phát biểu lỗi thời | §0.1 sổ đăng ký nguồn (tên file, SHA-256, bản đồ 6 trang, cảnh báo "giả định"), §15 ba lớp phân loại có số trang, §16 ranh giới benchmark PSC ↔ hybrid, §17 reconciliation `r002`, §18 đầu vào còn thiếu P0/P1, §19 ảnh hưởng tới `G0`; sửa §0, §1, §3, §5, §10 |

## 12. Xử lý review `r001` (codex) — reconciliation log

Nguồn: `multiagent/reviews/RND-00fd963d-01.codex.r001.json` (`decision = REVISE`,
`independence_confirmed = true`, `handoff_sha256 = 750f4b3b0d390117ba535f58b3d513e8e4a89b75f39a4108c002b97bf6bc4d8e`
— hash của file handoff `multiagent/handoffs/RND-00fd963d-01.claude.r001.json`; artifact
được reviewer đối chiếu là `ba168286…b5403` như khai trong handoff đó).

| # | Finding của reviewer (trích) | Trạng thái | Cách xử lý ở r002 |
|---|---|---|---|
| R-01 | `gate_findings[0]`: `G0` = **FAIL** | **ĐỒNG THUẬN, không tranh luận** | Đây **trùng khớp** với kết luận tự khai của chính artifact (§10: `G0 = FAIL / STOP_FOR_ENGINEERING_CLAIMS`). r002 **không** tìm cách lật `FAIL` thành `PASS`; `FAIL` ở đây là *sản phẩm đúng* của một task design-basis khi dữ liệu đầu vào không tồn tại. |
| R-02 | "It explicitly records site, loads, codes/version, design life, geotechnical, hydraulic, wind, seismic and material basis as UNKNOWN/UNVERIFIED" | **XÁC NHẬN** | Reviewer đọc đúng §5. Không mục nào trong §5 được điền thêm ở r002, vì **không có nguồn dữ liệu mới** nào xuất hiện trong repo. Điền chúng bằng suy đoán sẽ vi phạm `safety_notes` của task và `PHYSICS_GATES.md`. |
| R-03 | "Independent repo checks confirm `arch_deck_v1` is non-evaluable, spans only 100–600 m, and `ARCH_RIB_STABILITY` plus relevant L2 solvers are `ABSENT`" | **XÁC NHẬN — trùng `E-02`, `E-03`, `E-04`, `N-01`** | Kiểm chứng độc lập của reviewer **củng cố** (không mâu thuẫn) bằng chứng đã ghi. Không có điểm nào cần reconcile theo G4. |
| R-04 | `notes`: "retain IDEA and obtain verified engineering inputs before technical claims" | **THỰC THI** | (a) Claim level của artifact giữ nguyên `IDEA` (§0) — **không** nâng lên `SCREENED` dù trần brief cho phép; (b) yêu cầu "obtain verified engineering inputs" được chuyển thành **gói yêu cầu dữ liệu có thể hành động** ở §13, và **điều kiện đóng** ở §14. |

**Kết luận reconciliation:** giữa handoff `r001` và review `r001` **không có bất đồng kỹ
thuật nào** cần hòa giải; reviewer yêu cầu *hành động* (giữ IDEA + chuyển blocker thành
yêu cầu dữ liệu tường minh), không yêu cầu *sửa số liệu*. Không có giá trị nào bị lấy
trung bình, không có bằng chứng nào bị gỡ bỏ (`PROTOCOL.md` §Quy tắc 2, G4).

**Kết quả âm giữ lại (bổ sung):**
- **N-04 — Vòng lặp G0 không thể tự đóng bằng agent.** Blocker của task này là *thiếu dữ
  liệu ngoài repo* (site/tải/địa chất/thủy văn/gió/động đất/vật liệu). Không có bất kỳ
  lượng công LLM nào đóng được nó. Retry thêm sẽ tạo ra cùng một `FAIL` với chi phí lớn
  hơn ⇒ đây là **blocker chờ đầu vào của con người**, phải được ghi nhận thay vì lặp.

## 13. Gói yêu cầu dữ liệu design basis (`DBR`) — đầu vào cần con người cung cấp

Mục đích: biến câu "obtain verified engineering inputs" (R-04) thành danh mục **kiểm
đếm được**. Mỗi dòng chỉ được chuyển sang `CLOSED` khi có **nguồn thật** (hồ sơ khảo
sát, điều khoản tiêu chuẩn có số hiệu + phiên bản, báo cáo phòng thí nghiệm, quyết định
của AHJ). **Không** agent nào được tự điền. Tất cả hiện là `OPEN`.

| ID | Hạng mục | Đơn vị / dạng | Bằng chứng chấp nhận được | Khóa mục nào | Trạng thái |
|---|---|---|---|---|---|
| DBR-01 | Vị trí chỗ vượt, lý trình, mặt cắt ngang sông/eo, hệ tọa độ & cao độ chuẩn quốc gia | `m`, hệ quy chiếu có tên | Bản đồ/khảo sát địa hình–thủy đạc có ngày và đơn vị đo | §2 hệ tọa độ, §5.1 | `OPEN` |
| DBR-02 | Tĩnh không thông thuyền đứng × ngang do cơ quan hàng hải quyết định (thay cho seed `S-05` = 60 m) | `m` × `m` | Văn bản chấp thuận tuyến luồng/tĩnh không của AHJ | `S-05`, `M-05`, `FC-11` | `OPEN` |
| DBR-03 | Bộ tiêu chuẩn **và phiên bản** (ví dụ TCVN 11823-x:năm / AASHTO LRFD ấn bản / Eurocode phần+NA), AHJ, design life, exposure class, hệ số tầm quan trọng | định danh văn bản | Trích dẫn số hiệu + năm ban hành | §2, §5.2, toàn bộ §7 | `OPEN` |
| DBR-04 | Hoạt tải thiết kế + hệ số, tĩnh tải giai đoạn 2, tổ hợp tải cho **từng** giai đoạn thi công | `kN`, `kN/m`, `kN/m²` | Điều khoản tiêu chuẩn theo `DBR-03` | §5.3, `FC-06` | `OPEN` |
| DBR-05 | Gió: vận tốc cơ bản, chu kỳ lặp, loại địa hình, hệ số giật, profile theo cao độ, **kèm số liệu cho giai đoạn thi công** | `m/s` | Trạm khí tượng/phân vùng gió của tiêu chuẩn áp dụng | `FC-07` | `OPEN` |
| DBR-06 | Động đất: `agR`, loại nền, phổ thiết kế, phân loại công trình | `g`, phổ | Bản đồ/phụ lục phân vùng của `DBR-03` | §5.3 | `OPEN` |
| DBR-07 | Nhiệt độ & gradient, va tàu, va xe, dòng chảy | `°C`, `kN` | Tiêu chuẩn + dữ liệu luồng tàu của site | §5.3 | `OPEN` |
| DBR-08 | Địa chất: hồ sơ khoan, phân tầng, sức kháng, độ cứng nền, mực nước ngầm; **riêng khả năng chịu lực nhổ + lực ngang tại vị trí mố neo cáp chủ** | `kPa`, `MN/m`, `kN` | Báo cáo khảo sát địa chất có ID lỗ khoan | `FC-01`, `FC-05` | `OPEN` |
| DBR-09 | Thủy văn/thủy lực: lưu lượng, vận tốc, mực nước theo chu kỳ lặp, xói chung/cục bộ | `m³/s`, `m/s`, `m` | Báo cáo thủy văn | §5.5 | `OPEN` |
| DBR-10 | Vật liệu UHPC: cường độ kéo/nén đặc trưng, mỏi, từ biến, co ngót, đường cong ứng xử sau nứt; **kèm miền áp dụng của công thức sức kháng sẽ dùng** | `MPa`, hệ số | Báo cáo thí nghiệm có batch/ID mẫu, hoặc guide specification đã đọc và diễn giải (`LIT-037`…`LIT-041`) | `E-07`, `N-03`, `FC-09` | `OPEN` — G6 human gate |
| DBR-11 | CFST: ống thép (mác, chiều dày), bê tông nhồi, ứng xử liên hợp, trình tự bơm, khe hở/co ngót tại giao diện | `MPa`, `mm` | Nguồn thí nghiệm/tiêu chuẩn CFST có trích dẫn | `N-03`, `FC-08`, `FC-09` | `OPEN` — G6 human gate |
| DBR-12 | Cáp chủ & dây văng: mô đun, cường độ, chùng ứng suất, đường cong mỏi, hệ bảo vệ chống ăn mòn, chi tiết neo | `GPa`, `MPa`, S-N | Catalog nhà sản xuất + tiêu chuẩn nghiệm thu | `FC-01`, `FC-02`, `FC-10` | `OPEN` — G6 human gate |
| DBR-13 | Hình học v1.7 đầy đủ: `f` và `f/L`, cao độ đỉnh tháp, sơ đồ nhịp biên, vị trí chân tháp/chân vòm, điểm nối nửa vòm–dầm, khe dầm–vòm, mặt cắt ngang, số làn, độ vồng chế tạo, sơ đồ gối/khe co giãn | `m`, `mm` | Bản vẽ/mô hình có tác giả + ngày; **hình render không được tính** (`E-03` `image_provenance`, `A-05`) | §5.8, `M-04`, `FC-11` | `OPEN` |
| DBR-14 | Năng lực phân tích: solver 3D phi tuyến + staged construction + ổn định vòm + khí động, kèm version/hash và benchmark | định danh phần mềm | Cài đặt thật + biên bản verification | `E-01`, `E-02`, `FC-03`, `FC-06`, `FC-07`, `FC-08` | `OPEN` |
| DBR-15 | Grammar/schema mô tả được hệ lai (cáp chủ + dây văng + vòm + tháp + mố neo) | schema có test | Task riêng ngoài `write_scope` của task này (`N-01`) | `N-01`, F1 | `OPEN` |

Quy tắc dùng bảng này: `DBR-01`…`DBR-04` là **tối thiểu** để bất kỳ bộ phận nào lên F1;
`DBR-10`…`DBR-12` là **tối thiểu** để nói tới sức kháng; `DBR-14` là **tối thiểu** để nói
tới ổn định, thi công hay khí động. Đóng một phần bảng **không** nâng claim của toàn hệ.

## 14. Điều kiện đóng task và định nghĩa "xong" cho `G0`

- **Task này (`RND-00fd963d-01`) coi là hoàn thành khi:** (i) mọi acceptance criterion ở
  §11 đạt, (ii) quyết định `G0` được ghi tường minh kèm lý do truy vết được (§10), (iii)
  các blocker được chuyển thành danh mục dữ liệu có thể hành động (§13), (iv) claim level
  giữ ở `IDEA`. Hoàn thành **không** đồng nghĩa `G0 = PASS`.
- **`G0` chỉ chuyển `FAIL → PASS` khi:** toàn bộ `DBR-01`…`DBR-09` và `DBR-13` ở trạng
  thái `CLOSED` với nguồn thật, do **kỹ sư chịu trách nhiệm** ký; `DBR-10`…`DBR-12` đi
  qua human gate `G6`; `DBR-14`/`DBR-15` là điều kiện riêng cho F1/F2 chứ không phải cho
  `G0`. Việc chuyển này **nằm ngoài** thẩm quyền của agent.
- **Bất biến khi `G0 = FAIL`:** mọi task xuôi dòng của brief `RND-20260901-00fd963d`
  (`RND-00fd963d-02`…`-05`) chỉ được sản xuất nội dung F0/`IDEA`: topology, phản biện
  đường lực bằng tĩnh học tay, tham số hóa có `domain_provenance` trung thực, biến thể +
  tiêu chí bác bỏ, lộ trình. Mọi ô limit state trả `NOT_EVALUATED` (§6.2) và `FC-12` là
  tiêu chí tự kiểm cho chính các artifact đó.
- **Nếu design basis về sau thay đổi:** theo `PROTOCOL.md` §Vòng đời task, thay đổi
  geometry/material/load/design basis **vô hiệu hóa** mọi bằng chứng xuôi dòng; phải tạo
  candidate lineage mới, không sửa lịch sử của artifact này.

## 15. Phân loại design basis theo DOCX đề bài — ba lớp tường minh

Mục này **thay thế** phát biểu lỗi thời "không tồn tại thông tin design basis nào".
Nguồn: §0.1. **Mọi dòng đều ghi số trang DOCX**. Trạng thái được dùng nhất quán:

- `ASSIGNMENT_FIXED` = `ASSIGNMENT_FIXED_FOR_ACADEMIC_BASELINE` — đề bài **giao cố định**
  cho bài toán học thuật. Ràng buộc bài tập; **không** phải dữ liệu đã thẩm tra/phê duyệt.
- `ACADEMIC_ASSUMPTION` = `ACADEMIC_ASSUMPTION_REQUIRES_REPLACEMENT` — **chính nguồn tự
  dán nhãn "giả định"**; bắt buộc thay bằng khảo sát được phê duyệt trước thiết kế kỹ
  thuật/thi công.
- `MISSING` = `STILL_MISSING_FOR_HYBRID_650M` — không có trong bất kỳ nguồn nào; là
  blocker của `G0`.

### 15.1 `ASSIGNMENT_FIXED_FOR_ACADEMIC_BASELINE`

| ID | Nội dung (trích đề bài) | Trang | Trạng thái |
|---|---|---|---|
| AF-01 | Tuyến đường **cấp III đồng bằng** | 2 | `ASSIGNMENT_FIXED` |
| AF-02 | **Vtk = 80 km/h** | 2 | `ASSIGNMENT_FIXED` |
| AF-03 | **2 làn xe** | 2 | `ASSIGNMENT_FIXED` |
| AF-04 | Khổ cầu **B = 12,0 m** = 2×3,50 m làn + 2×1,50 m lề/bộ hành + lan can | 2 | `ASSIGNMENT_FIXED` |
| AF-05 | Tiêu chuẩn thiết kế cầu **TCVN 11823:2017** (yêu cầu chung, vị trí, tải trọng, phân tích, BTCT, nền móng, mố trụ, gối/khe) | 2 | `ASSIGNMENT_FIXED` — **phiên bản đã có**, nhưng phần/điều khoản áp dụng cho từng kiểm toán vẫn phải chỉ định |
| AF-06 | Báo hiệu & ATGT **QCVN 41:2019/BGTVT** (nguồn tự ghi: phải kiểm tra văn bản còn hiệu lực trước khi dùng cho hồ sơ thật) | 2 | `ASSIGNMENT_FIXED` |
| AF-07 | Thủy văn **TCVN 9845:2013** + "số liệu thủy văn được phê duyệt" (số liệu phê duyệt: **chưa có**) | 2 | `ASSIGNMENT_FIXED` (tiêu chuẩn) + `MISSING` (số liệu phê duyệt) |
| AF-08 | Sơ đồ nhịp **(45 + 75 + 45) m**, dầm hộp **BTCT DƯL liên tục 3 nhịp**, thi công **đúc hẫng cân bằng** | 1, 2, 3 | `ASSIGNMENT_FIXED` — **benchmark/baseline PSC học thuật**, xem §16 |
| AF-09 | Phương án đối chứng bắt buộc **PA1: Super-T BTCT DƯL giản đơn 4×40 m**; **PA2 (chọn sơ bộ)**: dầm hộp 45+75+45 m đúc hẫng | 3 | `ASSIGNMENT_FIXED` |
| AF-10 | Bê tông dầm **C50/60** | 2 | `ASSIGNMENT_FIXED` — mác danh định; **không** kèm thuộc tính đặc trưng/EPD/batch (G6 vẫn mở) |
| AF-11 | Bê tông trụ/mố **C35/45** | 2 | `ASSIGNMENT_FIXED` — như AF-10 |
| AF-12 | Cốt thép thường **CB400-V** | 2 | `ASSIGNMENT_FIXED` — như AF-10 |
| AF-13 | Cáp DƯL **1860 MPa** (nguồn ghi "xác nhận theo thiết kế") | 2 | `ASSIGNMENT_FIXED` — cấp cường độ danh định; đường cong mỏi/chùng ứng suất/hệ neo **chưa có** |
| AF-14 | Nhiệm vụ thiết kế bắt buộc và danh mục sản phẩm nộp (bố trí tổng thể, KCN, mố–trụ–móng cọc khoan nhồi, gối/khe/thoát nước/chống xói, tổ chức thi công đúc hẫng) | 3 | `ASSIGNMENT_FIXED` (phạm vi công việc, không phải dữ liệu vật lý) |
| AF-15 | Điều kiện nghiệm thu **học thuật** + tuyên bố "không phải hồ sơ được phép thi công" | 4 | `ASSIGNMENT_FIXED` (ràng buộc phạm vi sử dụng) |

### 15.2 `ACADEMIC_ASSUMPTION_REQUIRES_REPLACEMENT`

Tất cả các dòng dưới đây **do chính nguồn dán nhãn "giả định"** (trang 1, 2, 5) hoặc kèm
yêu cầu kiểm chứng. **Không dòng nào** được coi là dữ liệu khảo sát.

| ID | Nội dung (trích đề bài) | Trang | Trạng thái |
|---|---|---|---|
| AA-01 | Sông (giả định): **bề rộng dòng chủ 92 m**; **hướng dòng chảy vuông góc tim cầu ±10°** | 2 | `ACADEMIC_ASSUMPTION` |
| AA-02 | Mực nước: **MNTN +3,20 m; MNCN +6,80 m; MNLTK (P=1%) +8,10 m** | 2 | `ACADEMIC_ASSUMPTION` |
| AA-03 | Khoang thông thuyền **B×H = 40×7 m** tính từ MNTK; nguồn tự ghi "phải xác nhận với cơ quan quản lý đường thủy" / "phải có văn bản chấp thuận của cơ quan đường thủy" | 2, 5, 6 | `ACADEMIC_ASSUMPTION` — **chưa** có văn bản chấp thuận ⇒ envelope thông thuyền vẫn `MISSING` (§15.3 SM-02) |
| AA-04 | Địa chất (giả định) tóm tắt: bùn/sét mềm 0–8 m; sét pha dẻo cứng 8–22 m; cát chặt từ 22 m; cọc khoan nhồi dự kiến ngàm vào lớp cát chặt | 2 | `ACADEMIC_ASSUMPTION` |
| AA-05 | Trắc diện địa chất giả định chi tiết B.1: L1 0,0–3,0 m bùn sét hữu cơ (γ=16,5 kN/m³; cu=12 kPa; Eoed=2,5 MPa; **không đặt móng nông**); L2 3,0–8,0 m sét mềm–dẻo mềm (γ=17,5; cu=22 kPa; φ=8°; Eoed=5 MPa); L3 8,0–22,0 m sét pha dẻo cứng (γ=19,0; cu=65 kPa; φ=16°; Eoed=18 MPa); L4 22,0–35,0 m cát hạt vừa chặt (γ=20,0; φ=34°; N-SPT ≥ 35; E=45 MPa); L5 >35,0 m sỏi sạn/cát rất chặt (N-SPT > 50, "phải xác định bằng khoan thực tế"); nước ngầm ~**+2,50 m** | 5 | `ACADEMIC_ASSUMPTION` |
| AA-06 | Gió (giả định): dùng số liệu **tạm 30 m/s** để kiểm tra sơ bộ, nguồn tự ghi **"không dùng để thi công"**; B.3: **Vref = 30 m/s** tại cao độ quy ước, "xác định lại theo vị trí thực tế" | 2, 6 | `ACADEMIC_ASSUMPTION` |
| AA-07 | Hướng gió bất lợi: **vuông góc tim cầu**; yêu cầu kiểm thêm góc xiên và tổ hợp gió–hoạt tải theo TCVN 11823 | 6 | `ACADEMIC_ASSUMPTION` |
| AA-08 | Nhiệt độ: **Tmin = 10 °C; Tmax = 40 °C**; ΔT thiết kế **"cần xác định"** | 6 | `ACADEMIC_ASSUMPTION` (ΔT: `MISSING`) |
| AA-09 | Mưa thiết kế **I = 180 mm/h (giả định)**; nguồn tự ghi "không thay cho số liệu khí tượng chính thức" | 6 | `ACADEMIC_ASSUMPTION` |
| AA-10 | Môi trường: **ẩm ướt, có nguy cơ cacbonat hóa/xâm thực nhẹ**; cấp môi trường/lớp bảo vệ **"xác định"** (chưa cho) | 6 | `ACADEMIC_ASSUMPTION` (exposure class: `MISSING`) |
| AA-11 | Lưu vực **A = 1.250 km²** | 5 | `ACADEMIC_ASSUMPTION` |
| AA-12 | Lưu lượng kiệt **Q95 = 35 m³/s** | 5 | `ACADEMIC_ASSUMPTION` |
| AA-13 | Lưu lượng lũ **Q1% = 1.850 m³/s** | 5 | `ACADEMIC_ASSUMPTION` |
| AA-14 | **MNLTK = +8,10 m**; **MNKT = +8,70 m** | 5 | `ACADEMIC_ASSUMPTION` |
| AA-15 | Vận tốc dòng chảy tại Q1%: **Vtb = 2,6 m/s; Vmax = 3,4 m/s** | 5 | `ACADEMIC_ASSUMPTION` |
| AA-16 | Xói: **xói chung 1,8 m; xói cục bộ tại trụ 3,5 m** | 5 | `ACADEMIC_ASSUMPTION` |
| AA-17 | Động đất: **không cho giá trị**, chỉ ghi "xác định theo bản đồ phân vùng và quy chuẩn/tiêu chuẩn hiện hành tại vị trí xây dựng" | 2 | `MISSING` (ghi ở đây để đối chiếu; xem SM-05) |

> Nhắc lại nguyên văn ràng buộc của nguồn (trang 5): *"Bộ số liệu này chỉ dùng cho tính
> toán học thuật và lựa chọn phương án trong đồ án. Không được dùng để thi công hay
> nghiệm thu."* Bất kỳ artifact xuôi dòng nào dùng `AA-01`…`AA-16` **phải** mang kèm
> nhãn `ACADEMIC_ASSUMPTION_REQUIRES_REPLACEMENT`.

### 15.3 `STILL_MISSING_FOR_HYBRID_650M`

Không nguồn nào (repo, brief, DOCX đề bài) cung cấp các mục sau. Đây là **blocker `G0`**.

| ID | Hạng mục còn thiếu | Vì sao nguồn mới không đóng được | DBR liên quan |
|---|---|---|---|
| SM-01 | **Site thật**: vị trí, tọa độ, hệ quy chiếu–cao độ chuẩn, bình đồ/trắc dọc/trắc ngang sông đo đạc thực tế | Đề bài **tự yêu cầu người dùng nộp** tệp địa hình DWG/LandXML/CSV/PDF có tỷ lệ, hệ tọa độ và mốc cao độ (trang 4, Phụ lục A) và liệt kê khảo sát địa hình là bắt buộc trước xây dựng (trang 3) ⇒ nguồn xác nhận **đang thiếu**, không cung cấp | `DBR-01` |
| SM-02 | **Envelope thông thuyền được cơ quan có thẩm quyền phê duyệt** | Nguồn ghi rõ 40×7 m "phải xác nhận với cơ quan quản lý đường thủy" / "phải có văn bản chấp thuận" (trang 2, 5, 6); văn bản đó **chưa tồn tại**. Seed 60 m của v1.7 (`S-05`) cũng chưa được phê duyệt | `DBR-02` |
| SM-03 | **Design life** và **exposure class** chính thức | Trang 6 chỉ mô tả định tính "ẩm ướt, nguy cơ cacbonat hóa/xâm thực nhẹ" và giao việc "xác định cấp môi trường"; không có tuổi thọ thiết kế ở bất kỳ trang nào | `DBR-03` |
| SM-04 | **Hệ số tầm quan trọng / AHJ / điều khoản áp dụng cho từng kiểm toán** | Trang 2 chỉ nêu tên tiêu chuẩn, không nêu cấp công trình hay AHJ | `DBR-03` |
| SM-05 | **Tham số động đất**: `agR`, loại nền, phổ thiết kế | Trang 2 **giao lại việc xác định**, không cho số | `DBR-06` |
| SM-06 | **Bộ tải trọng và tổ hợp đầy đủ** cho khai thác **và từng giai đoạn thi công** | Trang 2–3 và trang 6 chỉ liệt kê *loại* tải và *danh mục kiểm toán* (B.4), không cho giá trị hoạt tải, hệ số, tĩnh tải GĐ2, va tàu/va xe hay bảng tổ hợp | `DBR-04`, `DBR-07` |
| SM-07 | **Khảo sát địa hình – địa chất – thủy văn – khí tượng thực đo** (khoan tại mố/trụ, SPT/CPT, chuỗi mực nước/lưu lượng, gió cực trị có thời đoạn quan trắc) | Trang 3 §6 liệt kê **đúng các yêu cầu này** như "khảo sát và xác minh bắt buộc **trước xây dựng**"; toàn bộ số liệu B.1–B.3 là giả định (trang 5–6) | `DBR-05`, `DBR-08`, `DBR-09` |
| SM-08 | **Vật liệu hệ lai**: UHPC (kéo/cắt/mỏi/từ biến/co ngót, miền áp dụng công thức), CFST (ống thép, bê tông nhồi, ứng xử liên hợp, trình tự bơm) | Đề bài chỉ có bê tông thường C50/60 & C35/45, CB400-V, cáp DƯL 1860 MPa (trang 2) — **không có** UHPC/CFST; `E-07`/`N-03` vẫn nguyên | `DBR-10`, `DBR-11` |
| SM-09 | **Cáp chủ / dây văng / hệ neo**: mô đun, chùng ứng suất, đường cong S-N, chống ăn mòn, chi tiết neo, khả năng chịu nhổ–lực ngang của mố neo | Không xuất hiện ở bất kỳ trang nào 1–6 (đề bài là cầu dầm hộp, không phải cầu dây) | `DBR-08`, `DBR-12` |
| SM-10 | **Hình học v1.7 đầy đủ** (`f`, `f/L`, cao độ đỉnh tháp, nhịp biên, nút nối vòm–dầm, độ vồng, sơ đồ gối/khe) | DOCX không mô tả v1.7 và **không chứa hình nhúng nào** (`inline_shape_count = 0`, §0.1) | `DBR-13` |
| SM-11 | **Solver phù hợp**: 3D phi tuyến hình học + staged construction + ổn định vành vòm + khí động đàn hồi (flutter/vortex/buffeting) cho nhịp treo 650 m | Năng lực runtime không đổi: `E-01`, `E-02` vẫn `ABSENT`; đề bài là văn bản, không cấp năng lực tính toán | `DBR-14` |
| SM-12 | **Grammar/schema mô tả hệ lai** (cáp chủ + dây văng + vòm + tháp + mố neo) | `N-01` không bị nguồn mới chạm tới | `DBR-15` |

## 16. 45+75+45 m là **benchmark/baseline PSC học thuật**, không phải design basis của hybrid 650 m

Phát biểu **không thể hiểu nhầm**, và là ràng buộc cứng cho mọi task xuôi dòng:

1. Sơ đồ **(45 + 75 + 45) m dầm hộp BTCT DƯL liên tục, đúc hẫng cân bằng** (trang 1, 2,
   3 — `AF-08`) là **đề bài đồ án tốt nghiệp**, tức một **benchmark/baseline học thuật**
   cho cầu PSC nhịp trung bình vượt sông rộng ~92 m (giả định, `AA-01`).
2. Nó **KHÔNG** được **âm thầm chuyển thành** (silently transplanted) design basis đã
   xác minh cho Hybrid Grand Bridge v1.7 (nhịp treo 650 m). Nhịp lớn nhất của đề bài là
   **75 m**; nhịp đối tượng của brief là **650 m** — chênh lệch ~**8,7 lần**. Loại hệ
   chịu lực khác nhau (dầm hộp liên tục ↔ hệ dây võng + dây văng + vòm CFST-UHPC), vật
   liệu khác nhau (bê tông thường ↔ UHPC/CFST), cơ chế phá hoại khống chế khác nhau
   (uốn/DƯL/mất mát ↔ ổn định vành vòm, khí động đàn hồi, neo cáp chủ, phi tuyến hình
   học).
3. Vì vậy **cấm** các thao tác sau trong mọi artifact của run này: (a) dùng `AF-*` /
   `AA-*` làm design basis cho v1.7; (b) ngoại suy tải, địa chất, thủy văn, gió, mác
   vật liệu hay tĩnh không của đề bài sang nhịp 650 m; (c) trích một con số của đề bài
   mà **không** kèm số trang và nhãn `ASSIGNMENT_FIXED` / `ACADEMIC_ASSUMPTION`;
   (d) coi `Vref = 30 m/s` (`AA-06`) là đủ cho kiểm tra khí động của nhịp treo 650 m —
   `FC-07` vẫn `NOT_TESTED` và vẫn là `STOP`.
4. Hệ quả về scoping: đây là **hai lineage tách biệt**. Nếu muốn dùng bộ dữ liệu đề bài,
   phải mở **candidate/lineage riêng** cho *nghiên cứu học thuật PSC 45+75+45 m*, với
   design basis hash riêng, và **không** trộn bằng chứng với lineage v1.7
   (`PROTOCOL.md` §Quy tắc nghiên cứu 2: so sánh chỉ hợp lệ khi cùng design basis hash).
5. Ngay cả trong lineage PSC học thuật đó, trần sử dụng vẫn là **học thuật**: chính
   nguồn tuyên bố "**không phải hồ sơ được phép thi công**" và "cầu chỉ được đưa vào sử
   dụng sau khảo sát chính thức, thẩm tra–thẩm định, phê duyệt, nghiệm thu và kiểm định
   theo pháp luật" (trang 4).

## 17. Xử lý review `r002` (codex) — reconciliation log

Nguồn: `multiagent/reviews/RND-00fd963d-01.codex.r002.json` — `decision = REVISE`,
`independence_confirmed = true`,
`handoff_sha256 = e243c1769ef190f3e911a07632e2a0d743bb74ec64dc2b5fcc0cbc490f3f6544`,
`gate_findings[0] = {gate: G0, status: FAIL}` đối chiếu artifact
`39cb0d3318b4dc7825d2ad1dd0d04932ba4cd077e2f7f9c6998bc0b87534bde4` (bản `r002`).

| # | Finding của reviewer (trích) | Trạng thái | Cách xử lý ở `r003` |
|---|---|---|---|
| R2-01 | `G0` = **FAIL**; artifact tự ghi `STOP_FOR_ENGINEERING_CLAIMS` | **ĐỒNG THUẬN** | `r003` **giữ nguyên** `G0 = FAIL / STOP_FOR_ENGINEERING_CLAIMS` cho v1.7 (§10, §19). Không có nỗ lực lật `FAIL` thành `PASS`; bằng chứng mới **không** đủ để lật, và §16 giải thích vì sao. |
| R2-02 | "site, loads, codes/version, design life, geotechnical, hydraulic, wind, seismic, material, and full geometry inputs remain UNKNOWN/UNVERIFIED" | **ĐÚNG TẠI THỜI ĐIỂM `r002`; ĐÃ TINH CHỈNH Ở `r003`** | Sau khi có DOCX đề bài (§0.1 — **chưa tồn tại** khi reviewer đánh giá `r002`), phát biểu "tất cả đều UNKNOWN" bị thay bằng phân loại 3 lớp (§15): `codes/version` đã có ở mức **`ASSIGNMENT_FIXED`** (TCVN 11823:2017, QCVN 41:2019/BGTVT, TCVN 9845:2013 — trang 2); `geotechnical/hydraulic/wind` đã có ở mức **`ACADEMIC_ASSUMPTION`** (trang 2, 5, 6); còn `site`, `design life`, `seismic`, `loads/combinations`, vật liệu hệ lai và `full geometry` **vẫn `MISSING`** (§15.3). Kết luận gate **không đổi**. |
| R2-03 | Ngụ ý: cần "verified engineering inputs" trước mọi claim kỹ thuật | **THỰC THI** | Claim level giữ `IDEA` (§0). "Verified" được định nghĩa chặt: khảo sát/phê duyệt hợp lệ, **không** phải "giả định có kiểm soát" của đề bài. Danh mục đầu vào còn thiếu, xếp hạng P0/P1: **§18**. |
| R2-04 | Không có finding nào yêu cầu sửa số liệu hay bác bỏ bằng chứng đã ghi | **XÁC NHẬN** | Không giá trị nào bị lấy trung bình, không bằng chứng nào bị gỡ (`PROTOCOL.md` G4). Các sửa đổi của `r003` là **thêm bằng chứng có nguồn + sửa phát biểu bị bằng chứng mới bác bỏ**, có ghi rõ nguyên nhân tại §1, §10 (lý do 1, đã sửa) và §19. |

**Bất đồng cần ghi nhận:** không có. Reviewer và artifact thống nhất `G0 = FAIL`. Điểm
duy nhất được cập nhật là **cơ sở lập luận** cho `FAIL` (từ "không có gì" → "có dữ liệu
học thuật cho một bài toán khác, nhưng lớp bắt buộc cho hệ lai 650 m vẫn trống").

**Kết quả âm giữ lại (bổ sung):**

- **N-05 — Bổ sung dữ liệu học thuật không nâng được gate kỹ thuật.** Một tài liệu tự
  khai "giả định", tự khai "không phải hồ sơ được phép thi công" (trang 1, 4, 5) không
  thể chuyển bất kỳ ô `G0` nào sang `PASS`, dù nó làm tăng `M-07 evidence_completeness`.
  Ghi lại để các run sau không nhầm "có thêm file" với "đã đóng gate".
- **N-06 — Sai lệch phạm vi giữa nguồn và đối tượng nghiên cứu.** Nguồn duy nhất có dữ
  liệu đầu vào định lượng lại **không** nói về đối tượng của brief. Đây là kết quả âm
  quan trọng: nó cho thấy `G0` của v1.7 bị chặn bởi **thiếu đầu vào của con người**
  (`N-04`), không phải bởi thiếu công sức phân tích.

## 18. Đầu vào người dùng còn thiếu để đóng `G0` — xếp hạng P0/P1

Chỉ liệt kê thứ **người dùng/kỹ sư phải cung cấp**; agent không được tự điền (task
`safety_notes`: *"Không tự bịa site, tải, địa chất, thủy văn hay thuộc tính vật liệu"*).
`P0` = chặn trực tiếp `G0`; `P1` = chặn F1/F2 và các gate sau, cần nhưng không chặn
riêng quyết định `G0`.

### 18.1 P0 — bắt buộc để `G0` có thể chuyển `FAIL → PASS`

| # | Đầu vào cần cung cấp | Dạng bằng chứng chấp nhận | Đóng | DBR |
|---|---|---|---|---|
| P0-1 | **Đối tượng nghiên cứu thật sự là gì?** Xác nhận tường minh: (a) tiếp tục hybrid 650 m v1.7, (b) chuyển sang đồ án PSC 45+75+45 m, hay (c) chạy **hai lineage tách biệt** | Câu trả lời của người dùng, ghi vào brief/task | quyết định scoping (§16.4) | — |
| P0-2 | **Site thật**: vị trí/lý trình, tọa độ, hệ quy chiếu + mốc cao độ, bình đồ–trắc dọc–mặt cắt ngang sông (DWG/LandXML/CSV/PDF có tỷ lệ) | Hồ sơ đo đạc có ngày + đơn vị đo (đúng danh mục trang 4) | `SM-01` | `DBR-01` |
| P0-3 | **Văn bản chấp thuận tĩnh không thông thuyền** (đứng × ngang) của cơ quan quản lý đường thủy | Văn bản của AHJ (nguồn yêu cầu ở trang 2, 5, 6) | `SM-02`, `AA-03`, `S-05` | `DBR-02` |
| P0-4 | **Design life + exposure class + hệ số tầm quan trọng + AHJ**, và phần/điều khoản TCVN 11823:2017 áp dụng cho từng kiểm toán | Trích dẫn số hiệu + năm + điều khoản | `SM-03`, `SM-04` | `DBR-03` |
| P0-5 | **Bộ tải trọng và tổ hợp đầy đủ**: hoạt tải + hệ số, tĩnh tải GĐ2, nhiệt độ/gradient (ΔT), va tàu, va xe, dòng chảy, và tổ hợp cho **từng** giai đoạn thi công | Điều khoản tiêu chuẩn theo P0-4 | `SM-06`, `AA-08` | `DBR-04`, `DBR-07` |
| P0-6 | **Tham số động đất**: `agR`, loại nền, phổ thiết kế, phân loại công trình tại vị trí thật | Bản đồ/phụ lục phân vùng theo P0-4 | `SM-05`, `AA-17` | `DBR-06` |
| P0-7 | **Báo cáo khảo sát địa chất thực đo**: khoan tại mố/trụ, SPT/CPT, thí nghiệm mẫu, nước ngầm, tham số thiết kế (thay `AA-04`, `AA-05`) | Báo cáo địa kỹ thuật có ID lỗ khoan | `SM-07` | `DBR-08` |
| P0-8 | **Báo cáo thủy văn–thủy lực được phê duyệt**: chuỗi mực nước/lưu lượng, lũ thiết kế, xói chung/cục bộ, bùn cát, biến động lòng dẫn (thay `AA-11`…`AA-16`) | Báo cáo thủy văn + phê duyệt | `SM-07` | `DBR-09` |
| P0-9 | **Số liệu gió thực đo/quy chuẩn theo vị trí**: vận tốc cơ bản, chu kỳ lặp, loại địa hình, hệ số giật, profile theo cao độ, **kèm số liệu giai đoạn thi công** (thay `AA-06`, `AA-07`) | Trạm khí tượng/phân vùng gió + thời đoạn quan trắc (nguồn yêu cầu ở trang 3) | `SM-07`, `FC-07` | `DBR-05` |
| P0-10 | **Hình học đầy đủ của phương án được chọn** (với v1.7: `f`, `f/L`, cao độ đỉnh tháp, nhịp biên, nút nối vòm–dầm, mặt cắt ngang, sơ đồ gối/khe) | Bản vẽ/mô hình có tác giả + ngày; **hình render không tính** (`A-05`) | `SM-10` | `DBR-13` |

### 18.2 P1 — cần để lên F1/F2 và để nói tới sức kháng/ổn định/khí động

| # | Đầu vào cần cung cấp | Dạng bằng chứng chấp nhận | Đóng | DBR |
|---|---|---|---|---|
| P1-1 | **Thuộc tính vật liệu UHPC** (kéo/nén đặc trưng, mỏi, từ biến, co ngót, ứng xử sau nứt) + miền áp dụng công thức sức kháng | Báo cáo thí nghiệm có batch/ID, hoặc `LIT-037`…`LIT-041` đã đọc–diễn giải | `SM-08`, `FC-09` | `DBR-10` — G6 human gate |
| P1-2 | **CFST**: mác/chiều dày ống thép, bê tông nhồi, ứng xử liên hợp, trình tự bơm, khe hở/co ngót giao diện | Nguồn thí nghiệm/tiêu chuẩn CFST có trích dẫn | `SM-08`, `FC-08` | `DBR-11` — G6 |
| P1-3 | **Cáp chủ/dây văng/hệ neo**: mô đun, cường độ, chùng ứng suất, S-N, chống ăn mòn, chi tiết neo; **và** khả năng chịu nhổ + lực ngang của mố neo theo địa chất thật | Catalog nhà sản xuất + tiêu chuẩn nghiệm thu + báo cáo địa kỹ thuật | `SM-09`, `FC-01`, `FC-10` | `DBR-12`, `DBR-08` — G6 |
| P1-4 | **Solver phù hợp**: 3D phi tuyến hình học + staged construction + ổn định vành vòm + phân tích khí động; kèm version/hash + benchmark | Cài đặt thật + biên bản verification | `SM-11`, `FC-03`, `FC-06`, `FC-08` | `DBR-14` |
| P1-5 | **Grammar/schema hệ lai** (cáp chủ + dây văng + vòm + tháp + mố neo), có test | Task riêng ngoài `write_scope` hiện tại | `SM-12`, `N-01` | `DBR-15` |
| P1-6 | **Yêu cầu của giảng viên/chủ nhiệm** về loại cầu, phần mềm, tiêu chuẩn và khối lượng bản vẽ (nếu chọn nhánh đồ án) | Văn bản/hướng dẫn (nguồn liệt kê ở trang 4) | phạm vi nhánh PSC | — |
| P1-7 | **Nguồn đã xác minh cho hệ dây võng/dây văng & khí động đàn hồi nhịp lớn** (lỗ hổng `N-02`) | Tài liệu có URL/DOI được lập chỉ mục vào `research/literature/index.json` | `N-02`, `FC-07`, `FC-10` | — |

## 19. Ảnh hưởng của nguồn mới tới `G0` và tới `evidence_completeness`

- **Quyết định gate không đổi:** `G0 = FAIL / STOP_FOR_ENGINEERING_CLAIMS` **cho Hybrid
  Grand Bridge v1.7 (nhịp treo 650 m)**. Lý do đầy đủ ở §10 (đã sửa) và §15.3: 12/12 mục
  `STILL_MISSING_FOR_HYBRID_650M` còn `OPEN`.
- **Điều đã cải thiện (ghi nhận trung thực):** DOCX đề bài **làm tăng đáng kể**
  `M-07 evidence_completeness` của workstream `design_basis` — lần đầu tiên run này có
  một nguồn ngoài repo, có hash, có bản đồ trang, có kiểm chứng độc lập, cung cấp bộ
  tiêu chuẩn áp dụng và một tập dữ liệu đầu vào định lượng có thể trích dẫn theo trang.
  Nguồn cũng cung cấp **danh mục khảo sát bắt buộc trước xây dựng** (trang 3) và **danh
  mục dữ liệu người dùng phải nộp** (trang 4), hai thứ đã được ánh xạ trực tiếp vào §18.
- **Điều nguồn mới cho phép:** mở một **nghiên cứu học thuật riêng biệt** (lineage
  tách) cho baseline PSC 45+75+45 m ở mức đồ án tốt nghiệp, dùng `AF-*` +
  `AA-*` với nhãn nguyên vẹn. Trong lineage đó, mọi kết quả vẫn là **học thuật**, vẫn
  phải trả `NOT_EVALUATED` cho hạng mục nào runtime không đánh giá được, và vẫn không
  được dùng cho thi công/nghiệm thu (trang 4, 5).
- **Điều nguồn mới KHÔNG cho phép — tuyên bố dứt khoát:** không `BUILD_READY`; không
  `TECHNICAL_RELEASE` / phát hành kỹ thuật; không kết luận "đủ khả năng chịu lực",
  "đã kiểm ổn định", "an toàn"; không tuyên bố tính mới hay "world-first"; không nâng
  claim vượt `IDEA` cho artifact này (trần brief `SCREENED` vẫn không được dùng hết);
  không chuyển bất kỳ giá trị nào của đề bài thành design basis cho v1.7 (§16).
- **Bất biến kiểm tra được cho các task xuôi dòng:** `FC-12` được mở rộng — bất kỳ
  artifact nào dùng số liệu từ DOCX đề bài mà **thiếu số trang** hoặc **thiếu nhãn**
  `ASSIGNMENT_FIXED_FOR_ACADEMIC_BASELINE` / `ACADEMIC_ASSUMPTION_REQUIRES_REPLACEMENT`
  / `STILL_MISSING_FOR_HYBRID_650M` đều bị coi là **vi phạm bằng chứng** và phải bị
  reviewer trả `REVISE`.
