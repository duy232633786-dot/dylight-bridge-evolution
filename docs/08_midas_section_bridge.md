# 08 — Cầu nối mặt cắt MIDAS: PSC-1CELL / 2CELL (BRD-052)

Phiên bản: `midas-section/0.1.0` — 2026-09-03. Module: `bridge_evolution/midas_section.py`;
contract: `contracts/midas_psc_section.schema.json`; basis:
`docs/design_basis/midas_psc_section_basis.json`; giao diện: `dashboard/midas_section.html`
(tab *Hộp PSC · kiểu MIDAS* của bàn **Sáng tạo mặt cắt** trong phòng lab, `python scripts/serve_lab.py`);
test: `tests/test_midas_section.py` (27 ca, gồm 7 ca hồi quy cho findings review r001).

> Claim của mọi đầu ra: **IDEA — chỉ hình học và dữ liệu nhập MIDAS**. Module không
> kiểm tra chịu lực, không phát PASS/FAIL, không nâng trần SCREENED của dự án.

## 1. Bài toán

Anh cần phòng lab sinh ra **đúng bộ tham số mà MIDAS Civil dùng để định nghĩa một cấu
kiện thật**: dialog *Properties → Section Properties → PSC → PSC-1CELL, 2CELL* với
Joint On/Off (JO1…JO3, JI1…JI5), Outer (HO1…BO3), Inner (HI1…BI4). Module này:

1. giữ **đúng tên và thứ tự trường** như manual MIDAS API (bảng *Dimension Table for
   PSC Sections*), nên mọi thứ xuất ra dán được vào Table Input / JSON API;
2. **vẽ lại mặt cắt như PSC Viewer** theo đúng quy ước hình guide của MIDAS, có điểm khớp;
3. **tính đặc trưng** (A, Iyy, Izz, tâm, S, chu vi, vị trí kiểm cắt Z1/Z2/Z3 và tổng dày
   sườn t1/t2/t3) bằng tích phân đa giác để đối chiếu với *Show Calculation Results*;
4. sinh **họ mặt cắt biến thiên** cho cầu đúc hẫng (parabol/tuyến tính), xuất cặp i/j
   cho Tapered Section;
5. **đề xuất tham số từ nhịp và bề rộng** bằng bảng heuristic khai báo rõ là chưa có nguồn;
6. chuyển **gene Super-T** của Studio thành đa giác **PSC-Value** (MIDAS không có Super-T
   trong họ PSC chuẩn).

## 2. Nguồn và quy ước (đã ghi trong basis)

| Nội dung | Nguồn |
|---|---|
| Thứ tự trường vSIZE_PSC_A/B/C/D, JOINT | MIDAS API Online Manual › Section Properties - PSC (article 35851688190105) |
| Ví dụ số thật + hình guide | MIDAS Civil `Manual/Tutorials/05. FCM General.pdf`, Fig. 4 (nhịp) và Fig. 5 (trụ) |
| PSC-Value | MIDAS API Online Manual › Section Properties - PSC Value (article 39233604772633) |
| DBUSER Box đã nạp được | `midas-mcp/evidence/revit-to-midas-psc-box-live-verification.json` |

Quy ước hình học suy từ hình guide (nửa mặt cắt, tim ở mép phải):

- `H = HO1 + HO2 + HO3`. Lỗ: bản trên theo HI1 (từ đỉnh) + vút HI2; bản đáy theo HI5 (từ đáy) + vút
  HI4; băng sườn hiệu dụng = `H − HI1 − HI2 − HI4 − HI5`. MIDAS **không** bắt buộc
  `HI1+…+HI5 = H` (ví dụ PSC-1CELL trong manual lệch 0,03 m), nên lệch với HI3 nhập chỉ là
  cảnh báo (`consistency_warnings`, nút *Tự cân HI3*); lab chỉ chặn khi băng sườn ≤ 0.
  **Mọi khối xuất dùng HI3 hiệu dụng** (`effective_dims`, cờ `hi3_adjusted`) để tham số MIDAS,
  đa giác lab vẽ và đặc trưng `LAB_CROSS_CHECK` cùng mô tả một tiết diện; HI3 gõ vào được giữ
  trong `params.dims` và ghi thành dòng *Lưu ý* trong bảng ô dialog.
- `vSIZE_PSC_D` luôn xuất **8 phần tử** (BI4 = 0 với 1CEL) và `SECT_I.SWIDTH = vSIZE_PSC_A[0]`
  — đúng như ví dụ PSC-1CELL (Assign 401) của manual; preset *MIDAS API manual — ví dụ
  PSC-1CELL* tái tạo đúng bốn mảng đó (test).
- Nửa bề rộng đỉnh `= BO1 + BO2 + BO3`; nửa bề rộng đáy `= BO3`; `BO2` là độ chạy ngang sườn.
- **Ngoài:** BO1-1 (JO1), BO1-2 (JO2) đo từ **mút cánh**; HO2-1/HO2-2 đo từ mức đáy mút cánh
  xuống; JO3: BO2-1 đo từ **góc đáy ngoài** ra phía cánh, HO3-1 đo từ đáy lên.
- **Trong:** BI1-1 (JI1), BI1-2 (JI2), BI2-1 (JI3), BI3-1 (JI5), BI3-2 (JI4) đo từ **tim**;
  HI2-1/HI2-2 đo từ mặt trong bản trên xuống; HI3-1 từ góc trên lỗ xuống; HI4-1 (JI5),
  HI4-2 (JI4) đo từ mặt trong bản đáy **lên**. Thứ tự khớp quanh lỗ: JI1 (bản trên, gần tim)
  → JI2 → JI3 (sườn) → JI4 (bản đáy, gần sườn) → JI5 (gần tim).
- 2CELL: `BI4` = nửa dày sườn giữa, hai lỗ đối xứng — **giả định**, chưa đối chiếu guide 2CELL.

Bằng chứng khớp: với mặt cắt nhịp của tutorial, lab cho `Z3 = 0,51 m` và `t2 = t3 = 0,90 m`
đúng bằng số MIDAS hiển thị trong Fig. 4; `Z1` lab = 2,10 m (góc trên lỗ) còn MIDAS Auto
= 2,125 m — MIDAS chọn cao độ hơi khác, nên t1 chỉ là ước lượng.

## 3. Đầu ra và cờ kiểm chứng

| Đầu ra | Cờ | Ghi chú |
|---|---|---|
| Bảng ô dialog (kèm ô xám) | — | đường nhập chắc chắn nhất |
| Table Input TSV | — | dán qua Excel vào *Table Input…* |
| JSON db/SECT | `REFERENCE_ONLY` | Civil 2022 không có REST API; tập khoá và thứ tự bám ví dụ PSC-1CELL của manual, khoá tuỳ chọn lấy từ `midas_api_json_defaults` trong basis (mặc định của lab, không phải quyết định kỹ thuật) |
| MCT `*SECTION` PSC 1CEL/2CEL | **`SYNTAX_UNVERIFIED`** + `syntax_provenance = OFFICIAL_MCT_HEADER_7_0_1` | nhãn giữ nguyên vì **chưa nạp thử** trên Civil 2022; nhưng cấu trúc 8 dòng nay lấy từ bảng cú pháp do chính MIDAS ghi (mục 3a), không còn suy đoán |
| MCT DBUSER Box (B) | `VERIFIED_BY_EXTERNAL_EVIDENCE` | hộp lý tưởng hoá; bằng chứng nằm ở `midas-mcp/evidence` (ngoài repo), neo SHA-256 trong basis và phát kèm output |
| PSC-Value đa giác Super-T | `SYNTAX_UNVERIFIED` / **`NEEDS_ENGINEER_INPUT`** | khoá `VERTEX`, `SHAPE = VALU` theo JSON Schema/ví dụ manual; đỉnh xuất cùng hệ toạ độ với đặc trưng (gốc tim-đỉnh); `vSIZE = [HT, BT, T1, T2]` là *Param. for Design* của MIDAS — không có giá trị người dùng cung cấp thì lab chỉ điền giả định (hộp bao, gene) và hạ trạng thái xuống `NEEDS_ENGINEER_INPUT`; nhập bốn số thật (UI hoặc `vsize` trong API) → `USER_PROVIDED` |
| Đặc trưng | `LAB_CROSS_CHECK` | đối chiếu Show Calculation Results; không có Ixx xoắn |

Mọi cờ trên được phát nguyên văn trong `export_bundle()["verification_flags"]` và trong từng
khối xuất (`status`), để UI và reviewer không phải suy từ tài liệu.

## 3a. Cú pháp MCT lấy từ chính MIDAS (không còn suy đoán)

Bản cài MIDAS Civil trên máy có sẵn một file MCT **do MIDAS xuất**:
`C:/Program Files/MIDAS/midas Civil/Tutorial/18 LRB for non- linear_Structural Model.mct`
(MCT 7.0.1, SHA-256 `87eedea6…`). Đầu khối `*SECTION` của nó là **bảng cú pháp đầy đủ**
do MIDAS tự ghi. Khối PSC gồm **8 dòng**:

| Dòng | Nội dung | Số trường (1CELL/2CELL) |
|---|---|---|
| 1 | `iSEC, TYPE, SNAME, [OFFSET], bSD, [bWE], SHAPE` | 13 (Civil 2022) |
| 2 | `OPT1, OPT2, [JOINT]` | 2 + 8 |
| 3 | `bSHEARCHK, [SCHK], [WT], WIDTH, bSYM, bSIDEHOLE` | 1 + 4 + 8 + 3 |
| 4 | `bUSERDEFMESHSIZE, MESHSIZE, bUSERINPSTIFF` (+`[STIFF]` khi bật) | 3 |
| 5–8 | `[SIZE-A]` `[SIZE-B]` `[SIZE-C]` `[SIZE-D]` | 6 · 6 · 10 · 8 |

`[OFFSET]` = OFFSET, iCENT, iREF, iHORZ, HUSER, iVERT, VUSER. `[SCHK]` = bAUTO_Z1, Z1,
bAUTO_Z3, Z3. `[WT]` = bAUTO_TOR, TOR, bAUTO_SHR1, SHR1, bAUTO_SHR2, SHR2, bAUTO_SHR3, SHR3.
Số phần tử 6/6/10/8 **trùng khít** bốn mảng `vSIZE_PSC_A..D` của API, và `WIDTH` chính là
`SWIDTH`. Hai nguồn độc lập xác nhận lẫn nhau.

Dòng 1 phát theo **biến thể Civil 2022**: file tutorial (MCT 7.0.1) có 23 trường cho DBUSER,
còn file `midas-mcp/demo-beam.mct` đã nạp **thành công thật** trên Civil 2022 (0 lỗi, 0 cảnh báo)
có 25 trường, tức thêm một cờ bool `bWE` giữa `bSD` và `SHAPE`. Lab dùng biến thể 2022 và ghi
kèm **dòng 1 thay thế cho 7.0.1** ngay trong comment, để đổi đúng một dòng nếu Command Shell báo lỗi.

Cách gỡ cờ lên `VERIFIED`: MIDAS Civil 2022 → mô hình **trống** → *Tools › MCT Command Shell* →
dán khối → *Run*. Nếu 0 lỗi thì cập nhật cờ trong basis kèm ảnh. Nếu lỗi ở dòng 1, thử dòng thay thế.

## 3b. Ca kiểm chuẩn từ mô hình MIDAS chính hãng

`14 PSC Design (AASHTO)_completed model.mcb` (SHA-256 `74222933…`) chứa mặt cắt tên `Span`,
`SHAPE = 1CEL`. 30 số thực float64 liên tiếp tại byte 31032 giải mã **đúng** theo thứ tự
`[SIZE-A]6 + [SIZE-B]6 + [SIZE-C]10 + [SIZE-D]8`:

- H = HO1 + HO2 + HO3 = 0,2 + 0,3 + 2,5 = **3,00 m**; HI1+…+HI5 = 0,24 + 0,26 + 2,05 + 0,20 + 0,25 = **3,00 m** (mô hình này *có* đẳng thức);
- bề rộng đỉnh 8,5 m, đáy 4,5 m; khớp bật: **JO1, JI1, JI3, JI5**.

Đây là preset `midas_tutorial14_psc_aashto` và là **ca duy nhất có JI3 thật** (sườn trong
thẳng đứng từ BI1 = 2,2 xuống JI3 rồi mới vát tới BI3 = 1,932), độc lập với tutorial FCM.

## 4. Họ mặt cắt biến thiên

`variable_depth_family(pier, mid, L, stations, law, n)`: trọng số `f(x) = ((L − x)/L)^n`
(x từ trụ về giữa nhịp; n = 2 parabol đỉnh tại giữa nhịp, `linear` = tuyến tính). **Mọi kích
thước** được nội suy `d(x) = d_mid + (d_pier − d_mid)·f`, nên `H(x) = H_mid + (H_pier − H_mid)·f`,
x = 0 trả đúng nguyên mặt cắt trụ và x = L trả đúng nguyên mặt cắt nhịp (sườn, cánh, bản đáy,
khớp — kể cả khi hai mặt cắt khác sườn và sườn nghiêng), đẳng thức chiều cao trong được giữ.
**Giữ dày sườn:** chỉ khi cả hai mặt cắt đầu có sườn ngoài **thẳng** (JO3 tắt), sườn trong thẳng
(JI3 tắt) và song song nhau thì ở trạm giữa `BI3` được suy từ độ dốc sườn ngoài `BO2/HO3` thay
vì nội suy độc lập, nên sườn trong song song sườn ngoài ở mọi trạm (`web_parallel_preserved =
true`, `web_slopes` in ra từng trạm); JO3/JI3 bật làm sườn thành đường gãy nên rơi về nội suy
tuyến tính và phát `family_warnings`. Hai mặt cắt phải cùng loại cell và cùng
bộ khớp. Kiểm: đơn điệu, hai đầu đúng bằng, mọi trạm validate. Xuất cặp i/j để dùng **Tapered Section** như tutorial FCM (Size-I/Size-J, y/z
Variation Linear).

## 5. Đề xuất từ nhịp (IDEA)

`propose_box_from_spans(L, B)` dùng bảng `heuristics` trong basis, mỗi giá trị có
`clause_id = LAB-HEURISTIC-UNSOURCED-*`: H trụ ≈ L/17, H nhịp ≈ L/45 (≥ 2,2 m), cánh hẫng
≤ 3 m và ≈ 0,22 B, đáy ≈ 0,45 B, sườn 0,45 m (nhịp) / 0,60 m (trụ), bản mặt ≥ 0,25 m, bản đáy
0,25 m → ≥ 0,60 m tại trụ, vút 1,0 × 0,3 m, sàn kích thước phụ 0,05 m (`min_sub_dim_m`, cũng có
clause_id). **Miền áp dụng** khai trong basis (`applicability`: nhịp chính 40–250 m, bề rộng
6–16 m cho hộp một ngăn): ngoài miền thì hàm từ chối thay vì sinh cặp trụ/nhịp mà họ mặt cắt
không nhận (ví dụ L = 30 m cho H trụ 1,76 m < H nhịp tối thiểu 2,2 m); test lưới 6 × 6 điểm
kể cả bốn góc chứng minh miền **đóng** (mọi điểm sinh tiết diện hợp lệ và vào được họ mặt cắt).
Kiểm dày sườn trong `validate` đo ở **cùng cao độ** với góc lỗ (sườn nghiêng: góc đáy ngoài thấp
hơn góc đáy lỗ), thay cho phép trừ BO3 − BI3 sai trước đây. Đây là **điểm xuất phát để nhập MIDAS rồi
phân tích**, không phải thiết kế; kỹ sư rà từng số.

## 6. Giao diện

Tab *Hộp PSC · kiểu MIDAS* của bàn **Sáng tạo mặt cắt** (cùng chỗ với Studio Super-T v2 và
hình thái vòm) nhúng `dashboard/midas_section.html`: form giống dialog (Joint On/Off,
1/2 Cell, Outer/Inner, ô xám theo khớp), PSC Viewer SVG tỉ lệ thật có nhãn khớp và kích
thước chính, bảng đặc trưng + Shear Check, sáu tab xuất có nút sao chép, khối họ mặt cắt
(chọn trụ/nhịp từ form hoặc tutorial, vẽ trắc dọc chiều cao, MCT cả họ), khối đề xuất.
Nút *Xuất PSC-Value MIDAS →* ở Studio tiết diện gửi gene qua `postMessage` sang màn này.
API: `GET /api/midas/presets`, `POST /api/midas/psc-section | psc-family | propose | supert-value`
— chỉ là lớp gọi mỏng lên module.

## 7. Giới hạn trung thực và bước tiếp

- Chưa có cáp DƯL, cốt thép, giai đoạn thi công, tải; chưa có L2 (midas-mcp chưa đọc kết quả về).
- Cú pháp MCT PSC chưa kiểm chứng; 2CELL là giả định; Z1/t1 Auto của MIDAS chưa tái tạo đúng.
- Khi tham số đang nhập chưa hợp lệ, UI làm mờ hình/khối xuất của lần hợp lệ trước, khoá nút sao
  chép và ghi rõ; phản hồi cũ tới sau bị bỏ (đánh số yêu cầu) nên hình luôn là của số liệu mới nhất.
- Review r001 (codex, REVISE) đã được xử lý trong r002: kiểm cạnh lỗ cắt biên ngoài (không chỉ
  đỉnh), họ mặt cắt nội suy mọi kích thước, JSON đủ khoá theo ví dụ manual, cờ kiểm chứng phát
  trong output, bằng chứng ngoài neo SHA-256, PSC-Value đúng khoá VERTEX/vSIZE, bool/section_id
  nghiêm ngặt, test route qua HTTP thật.
- Review r002 (codex, REVISE) đã được xử lý trong r003: containment kiểm **đoạn kín** (cạnh lỗ
  chạm đỉnh JO3 cũng bị từ chối), họ mặt cắt giữ sườn song song, UI đọc `VERTEX`, khoá output ngay
  trong handler nhập và đánh số mọi luồng (family/propose/Super-T), sàn 0,05 m + miền áp dụng
  heuristic vào basis, `section_id` không ép 1,5 → 1, container sai kiểu bị từ chối, gene sai kiểu
  → HTTP 400, test HTTP phủ đủ 5 route; vSIZE của PSC-Value được ghi rõ là ánh xạ giả định.
- Review r003 (codex, REVISE) đã được xử lý trong r004: xuất HI3 hiệu dụng để tham số ↔ đa giác ↔
  đặc trưng nhất quán; JO3 không được nhận "giữ dày sườn"; PSC-Value dùng cùng hệ toạ độ và
  `NEEDS_ENGINEER_INPUT` khi thiếu vSIZE thật; input họ/đề xuất vô hiệu output cũ ngay, bắt tay
  iframe (`dylight:midas-ready`/`supert-ack`); kiểm dày sườn theo cao độ, miền heuristic 6–16 m
  đóng trên lưới; `stations`/Section ID không ép kiểu ngầm; schema đồng bộ runtime.
- Review r004 (codex, REVISE; 6/8 tiêu chí MET) đã được xử lý trong r005: gene Super-T vi phạm L0
  HARD **không** xuất PSC-Value (fail-closed, 400 kèm rule); DBUSER đo dày sườn tại cao độ góc lỗ
  và từ chối nếu ≤ 0; tên/tiền tố chỉ nhận identifier an toàn (không tab/phẩy/CRLF vào TSV/MCT);
  đề xuất đổi L vô hiệu họ mặt cắt cũ; vSIZE kiểm miền (HT, BT > 0, 0 ≤ T1 ≤ HT, 0 ≤ T2 ≤ BT);
  Section ID chuỗi → `int` trực tiếp, chặn số lớn, UI kiểm safe integer; nhãn hình dùng bộ kích
  thước xuất (HI3 hiệu dụng); BI4 ≠ 0 trên 1CELL bị từ chối ở runtime (UI đặt 0 khi 1 Cell).
- Bước tiếp theo đúng thứ tự: (1) anh nạp thử MCT trên Civil 2022 (hoặc gửi MCT mẫu) để gỡ
  cờ; (2) nối họ mặt cắt vào midas-mcp `midas_preview_revit_bridge` thay cho DBUSER Box;
  (3) adapter đọc kết quả MIDAS về thành evidence L2 (G2/G4) — khi đó "cân đối phương án"
  (hướng 2) mới có số thật để làm.
