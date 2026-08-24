# Sổ đăng ký claim vật liệu & công nghệ CHƯA KIỂM CHỨNG

Phiên bản: `UCR-1.0` · Task: BRD-005 · Claim level: **IDEA** (chưa phải SCREENED).

Sổ này ghi những đề xuất vật liệu/công nghệ **chưa có bằng chứng**, để chúng không
bị mất và cũng không lọt vào catalog sản xuất. Nguyên tắc phân định:

- `research/materials/evidence_matrix.json` — chỉ dành cho vật liệu **đã có báo cáo
  thử nghiệm**; schema bắt buộc `source_ref` + `test_report_id` + `tested_by`.
- Sổ này — dành cho **claim chưa có nguồn**. Một mục chỉ được chuyển sang evidence
  matrix khi điền được đủ ba trường trên bằng dữ liệu thật.

**Không được bịa `test_report_id`, tên phòng thí nghiệm hay nhà cung cấp để lách
schema.** Nếu chưa có báo cáo thì mục đó ở lại đây.

---

## UCR-001 — UHPC f'c ≥ 160 MPa, cốt sợi thép phân tán 2,5% thể tích

**Nguồn claim:** văn bản do một AI khác sinh ra, chủ dự án dán vào phiên làm việc
2026-08-21. **Không kèm tài liệu, tiêu chuẩn hay báo cáo thử nghiệm nào.**

**Trạng thái: BỊ CHẶN — không phải vì thiếu dữ liệu, mà vì ngoài miền hiệu lực mô hình.**

`docs/03_shape_evolution.md` §4 đã ghi trước đó: khối ứng suất chữ nhật của
TCVN 11823-5 / AASHTO LRFD được hiệu chỉnh cho dải bê tông thường và **không phủ
vùng f'c > ~120 MPa**. Thêm một dòng `f'c = 160` vào `catalogs.json` sẽ khiến toàn
bộ STR-001 / SERV-001 / STR-002 cho ra những con số **trông hợp lệ nhưng vô nghĩa** —
đúng loại lỗi nguy hiểm nhất trong hệ này (MODEL-001).

Ngoài ra, đóng góp của cốt sợi vào sức kháng cắt là **cơ chế riêng**, không suy ra
được từ f'c; mô hình STR-002 hiện tại ở mức L1 không mô tả được nó.

**Điều kiện để gỡ chặn (theo thứ tự, không được nhảy bước):**

1. Thay **mô hình vật liệu**: quan hệ ứng suất–biến dạng nén, và ứng xử kéo sau nứt
   của bê tông cốt sợi — không dùng lại khối ứng suất chữ nhật.
2. Thay **mô hình sức kháng tiết diện** tương ứng, kèm bộ tiêu chuẩn/hướng dẫn thiết
   kế riêng cho UHPC (không dùng TCVN 11823-5 ngoài miền của nó).
3. Gold case kiểm chứng do kỹ sư duyệt cho cả uốn và cắt.
4. Dữ liệu G6: cấp phối, quy trình dưỡng hộ, co ngót–từ biến của chính cấp phối đó,
   độ bền mỏi, chống cháy, báo giá nhà cung cấp, ranh giới EPD.

Chừng nào chưa xong bước 1–3, mọi con số tối ưu có UHPC đều **không được trích dẫn**.

---

## UCR-002 — Cáp CFRP, độ dão dưới 0,5% sau 100 năm

**Nguồn claim:** cùng nguồn với UCR-001. Không kèm dữ liệu.

**Trạng thái: BỊ CHẶN — claim tuổi thọ không có bằng chứng.**

`multiagent/PROTOCOL.md` quy tắc nghiên cứu số 5 cấm claim dạng "rẻ và trường tồn";
chỉ được nêu design life, exposure, maintenance, uncertainty, nguồn cung, LCCA và
bằng chứng thử nghiệm cụ thể. Một con số "sau 100 năm" **không thể** đến từ suy luận
— nó phải đến từ thí nghiệm dão gia tốc kèm mô hình ngoại suy có sai số công bố.

**Điều kiện để gỡ chặn:**

1. Dữ liệu dão **theo thời gian thực + gia tốc**, kèm mô hình ngoại suy và **khoảng
   tin cậy** cho mốc 100 năm — không được nêu một con số trần trụi.
2. Ứng xử phụ thuộc môi trường: kiềm, ẩm, tia UV, chu kỳ nhiệt, ăn mòn điện hóa tại
   vùng neo.
3. Mỏi dưới hoạt tải chu kỳ, và **cơ chế phá hoại**: CFRP phá hoại giòn, không có
   vùng chảy dẻo như thép DƯL — điều này đổi cả triết lý an toàn của kết cấu, không
   chỉ đổi một con số trong catalog.
4. Vùng neo và mất mát DƯL của hệ CFRP; hệ số riêng phần theo tiêu chuẩn áp dụng.
5. Nguồn cung, báo giá, EPD.

---

## UCR-003 — Lắp ghép phân đoạn đúc sẵn siêu nhẹ + cần cẩu robot tự hành

**Nguồn claim:** cùng nguồn. Nội dung: phân đoạn dài 6 m nặng 45–60 t thay vì 250 t;
mối nối keo epoxy kết hợp căng cáp tức thì; cẩu robot chạy trên lưng dầm.

**Trạng thái: NGOÀI PHẠM VI mô hình hiện tại — chưa đánh giá được, chưa bác bỏ được.**

`docs/03_shape_evolution.md` §1 xếp "công nghệ chế tạo" ở **cấp 4** của thang tự do
thiết kế và ghi rõ điều kiện mở: phải có **mô hình giai đoạn thi công (L3)** và kiểm
tra mối nối/vùng neo. Hệ hiện tại chỉ có L0 + L1 line-girder, **không có khái niệm
giai đoạn thi công**, nên không thể kiểm bất kỳ phát biểu nào ở mục này.

Đối chiếu số liệu trong hệ: phiến Super-T ở dải phương án đang xét nặng khoảng
59–65 t (thẻ KC-008). Con số "250 t của cầu truyền thống" trong claim **không ứng với
loại kết cấu mà repo này đang mô hình hóa** — nó nói về cầu đúc hẫng, một họ kết cấu
khác. So sánh 45–60 t với 250 t vì vậy là **so sai đối tượng**.

**Điều kiện để đánh giá được:**

1. Mô hình L3 có giai đoạn thi công: nội lực từng bước lắp, ổn định trong khi lắp.
2. Mô hình mối nối epoxy: cường độ, ứng xử cắt trượt, dung sai khớp, ảnh hưởng nhiệt
   độ và độ ẩm lúc thi công, và **cơ chế phá hoại** của khớp khô/ướt.
3. Ràng buộc thiết bị thật: tải trọng cẩu robot đặt lên chính kết cấu chưa hoàn thiện
   (đây là một trường hợp tải, không phải chi tiết hậu cần).
4. Dữ liệu G6/G5 cho keo: dão, mỏi, lão hóa, chống cháy.

---

## Quy tắc dùng sổ này

1. Mục trong sổ này ở mức **IDEA**. Không được dùng để định hướng tối ưu, không được
   xuất hiện trong báo cáo như phương án, không được nhập vào `catalogs/catalogs.json`.
2. Muốn chuyển lên: mở task riêng, nêu rõ gate cần đạt, và nộp bằng chứng có hash.
3. Claim do AI sinh ra được đối xử **giống hệt** claim từ nguồn khác: không có nguồn
   thì không có số. Việc một mô hình phát biểu trôi chảy không phải là bằng chứng.
