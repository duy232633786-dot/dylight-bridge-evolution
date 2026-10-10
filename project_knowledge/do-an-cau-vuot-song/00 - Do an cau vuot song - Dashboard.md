---
title: "Đồ án tốt nghiệp - Thiết kế cầu vượt sông"
aliases:
  - "Đồ án cầu vượt sông"
  - "Cầu dầm hộp 45+75+45 m"
project: "do-an-cau-vuot-song"
knowledge_type: "project-dashboard"
status: "working-draft"
engineering_status: "academic-only"
standard_basis:
  - "TCVN 11823:2017"
  - "TCVN 9845:2013"
  - "QCVN 41:2019/BGTVT"
created: 2026-08-31
updated: 2026-08-31
tags:
  - dylight/project
  - bridge-design
  - graduation-project
  - psc-box-girder
  - balanced-cantilever
---

# Đồ án tốt nghiệp - Thiết kế cầu vượt sông

> [!warning] Ranh giới sử dụng
> Đây là kho kiến thức phục vụ đồ án học thuật. Các số liệu địa chất, thủy văn, khí tượng có nhãn `giả định` hoặc `needs_verification` không được dùng cho thiết kế thi công. Hồ sơ thực tế phải thay bằng số liệu khảo sát, thẩm tra, thẩm định và phê duyệt hợp lệ.

## 1. Mục tiêu dự án

Thiết kế cơ sở và thiết kế kỹ thuật cầu đường bộ vượt sông trên tuyến đường cấp III đồng bằng. Đồ án phải so sánh tối thiểu hai phương án, chọn một phương án để thiết kế chi tiết, kiểm toán theo các trạng thái giới hạn, lập mô hình tính, bản vẽ, thuyết minh và bảng khối lượng sơ bộ.

Phương án định hướng:

- Cầu dầm hộp BTCT dự ứng lực liên tục ba nhịp `45 + 75 + 45 m`.
- Thi công đúc hẫng cân bằng.
- Khổ cầu `B = 12,0 m`.

Phương án đối chứng:

- Cầu dầm Super-T BTCT dự ứng lực giản đơn `4 x 40 m`.

## 2. Nguồn và độ tin cậy

| Nguồn | Vai trò | Trạng thái |
|---|---|---|
| `De_bai_do_an_tot_nghiep_thiet_ke_cau_vuot_song.docx` | Nhiệm vụ và bộ số liệu giao | Nguồn đề bài |
| Nội dung trao đổi Codex ngày 2026-08-31 | Lộ trình và cách tổ chức thực hiện | Hướng dẫn, cần kỹ sư/GVHD duyệt |
| Hồ sơ địa hình, địa chất, thủy văn thực tế | Đầu vào thiết kế | Chưa cung cấp |
| TCVN/QCVN được viện dẫn | Cơ sở tiêu chuẩn | Phải kiểm tra hiệu lực và điều khoản cụ thể |

Nguyên tắc: không chuyển một nhận xét trong chat thành kết luận thiết kế nếu chưa có phép tính, điều khoản tiêu chuẩn và kiểm tra độc lập tương ứng.

## 3. Dữ liệu đầu vào đã biết

| Mã | Thông số | Giá trị | Nguồn | Trạng thái |
|---|---|---:|---|---|
| IN-001 | Cấp đường | Cấp III đồng bằng | Đề bài | assigned |
| IN-002 | Vận tốc thiết kế | 80 km/h | Đề bài | assigned |
| IN-003 | Số làn xe | 2 | Đề bài | assigned |
| IN-004 | Khổ cầu | 12,0 m | Đề bài | needs_clarification về phân chia lan can/lề |
| IN-005 | Sơ đồ nhịp PA2 | 45 + 75 + 45 m | Đề bài | preliminary-selected |
| IN-006 | Bề rộng dòng chủ | 92 m | Đề bài | assumed |
| IN-007 | MNTN | +3,20 m | Đề bài | assumed |
| IN-008 | MNCN | +6,80 m | Đề bài | assumed |
| IN-009 | MNLTK P=1% | +8,10 m | Đề bài | assumed |
| IN-010 | MN kiểm tra | +8,70 m | Đề bài | assumed |
| IN-011 | Tĩnh không thông thuyền | 40 x 7 m | Đề bài | needs_authority_confirmation |
| IN-012 | Bê tông dầm | C50/60 | Đề bài | preliminary |
| IN-013 | Bê tông mố, trụ | C35/45 | Đề bài | preliminary |
| IN-014 | Cốt thép thường | CB400-V | Đề bài | preliminary |
| IN-015 | Cáp DƯL | 1860 MPa | Đề bài | preliminary |
| IN-016 | Gió tham chiếu | 30 m/s | Đề bài | assumed |
| IN-017 | Q1% | 1.850 m3/s | Đề bài | assumed |
| IN-018 | Xói chung | 1,8 m | Đề bài | assumed |
| IN-019 | Xói cục bộ tại trụ | 3,5 m | Đề bài | assumed |

## 4. Các điểm phải khóa trước khi tính sâu

- [ ] Phân chia chính xác mặt cắt ngang trong tổng bề rộng 12,0 m.
- [ ] Độ dốc ngang mặt cầu và cấu tạo lớp phủ.
- [ ] Giá trị mực nước dùng làm chuẩn tĩnh không thông thuyền.
- [ ] Cao độ khống chế thấp nhất của đáy dầm.
- [ ] File địa hình có hệ tọa độ, hệ cao độ và mốc khống chế.
- [ ] Vị trí xây dựng để xác định động đất, gió và điều kiện môi trường.
- [ ] Yêu cầu của GVHD về phần mềm, số lượng bản vẽ và mức độ tính toán.
- [ ] Phiên bản/hiệu lực tiêu chuẩn và điều khoản áp dụng cho từng phép kiểm toán.

## 5. Luồng thực hiện chuẩn

```text
Khóa nhiệm vụ và dữ liệu
  -> Dựng địa hình, tuyến, mặt cắt sông
  -> Xác định khẩu độ, cao độ, vị trí mố trụ
  -> So sánh PA1 và PA2
  -> Khóa phương án chọn
  -> Chọn sơ bộ hình học dầm hộp
  -> Tải trọng và tổ hợp
  -> Mô hình theo giai đoạn thi công
  -> Thiết kế DƯL và kiểm toán kết cấu nhịp
  -> Thiết kế trụ, mố, móng
  -> Gối, khe, lan can, thoát nước, bản dẫn, chống xói
  -> Biện pháp thi công đúc hẫng
  -> Bản vẽ, thuyết minh, khối lượng
  -> Kiểm tra chéo và bảo vệ
```

## 6. Các giai đoạn và cổng kiểm soát

### Giai đoạn A - Khởi tạo hồ sơ

Đầu ra:

- Bảng nhiệm vụ đồ án.
- Nhật ký giả thiết đầu vào.
- Danh mục tiêu chuẩn và điều khoản.
- Cấu trúc thư mục, quy ước tên file và phiên bản.

Cổng A: tất cả đầu vào phải có `nguồn` và `trạng thái`; dữ liệu thiếu không được ngầm giả định.

### Giai đoạn B - Địa hình, tuyến và thủy văn sơ bộ

Thực hiện:

1. Kiểm tra đơn vị, hệ tọa độ và hệ cao độ.
2. Dựng bề mặt địa hình, mép sông, dòng chủ và mặt cắt ngang sông.
3. Đặt tim tuyến, xác định góc giao với dòng chảy.
4. Bố trí sơ bộ M1, T1, T2, M2.
5. Xác định trắc dọc, cao độ mặt cầu và cao độ đáy dầm.
6. Kiểm tra sơ bộ khẩu độ thoát lũ, nước dâng và xói.

Đầu ra:

- Bình đồ, trắc dọc, mặt cắt ngang sông.
- Bảng mực nước và các cao độ khống chế.
- Vị trí mố trụ sơ bộ.

Cổng B: không khóa cao độ mặt cầu nếu chưa đồng thời xét tĩnh không, chiều cao dầm, độ võng/độ vồng, độ dốc tuyến và mực nước kiểm tra.

### Giai đoạn C - So sánh phương án

PA1 Super-T `4 x 40 m`:

- Số dầm, chiều cao dầm, số trụ trong sông.
- Biện pháp lao lắp.
- Ảnh hưởng thông thuyền, dòng chảy và khối lượng sơ bộ.

PA2 dầm hộp `45 + 75 + 45 m`:

- Hình học dầm hộp biến chiều cao.
- Sơ đồ đúc hẫng và vị trí hợp long.
- Số trụ trong sông, yêu cầu xe đúc, khối lượng sơ bộ.

Tiêu chí so sánh: thông thuyền, thoát lũ, ảnh hưởng dòng chảy, chịu lực, thi công, tiến độ, kinh tế, bảo trì và cảnh quan.

Cổng C: phương án chỉ được khóa khi sơ đồ nhịp, cao độ sơ bộ, vị trí mố trụ và mặt cắt ngang đã được GVHD chấp thuận.

### Giai đoạn D - Kết cấu nhịp và DƯL

Thực hiện:

1. Chọn dầm hộp một ngăn/nhiều ngăn.
2. Chọn chiều cao tại trụ và giữa nhịp, bề rộng đáy, chiều dày bản và thành.
3. Lập tải trọng và tổ hợp theo tiêu chuẩn.
4. Mô hình các giai đoạn: K0, các đốt hẫng, hợp long biên, hợp long giữa, hoàn thiện và khai thác.
5. Bố trí cáp âm trên trụ, cáp dương giữa nhịp và cáp liên tục.
6. Tính mất mát DƯL: ma sát, tụt neo, co ngắn đàn hồi, co ngót, từ biến và chùng cáp.
7. Kiểm toán cường độ, sử dụng, mỏi liên quan, ứng suất, nứt, võng và vùng neo.

Cổng D: không chốt số bó cáp trước khi có nội lực theo giai đoạn; mô hình phải có kiểm tra độc lập về phản lực, cân bằng và biến dạng.

### Giai đoạn E - Trụ, mố và móng

Trụ/mố:

- Nhận phản lực và tác động từ kết cấu nhịp.
- Kiểm tra uốn-nén, cắt, trượt, lật và ổn định.
- Xét áp lực đất, lực hãm, gió, nhiệt, dòng chảy, xói, động đất và va xô nếu thuộc phạm vi.

Móng cọc khoan nhồi:

- Chọn đường kính, chiều dài và số cọc.
- Tính sức chịu tải dọc trục, ngang, nhóm cọc và lún.
- Xét chiều sâu xói khi xác định chiều dài làm việc.
- Thiết kế bệ cọc và lồng thép cọc.

Cổng E: sức chịu tải địa kỹ thuật và kết cấu phải được kiểm tra riêng; không dùng lớp đất giả định để đưa ra kết luận thi công.

### Giai đoạn F - Hạng mục phụ và thi công

- Chọn gối theo phản lực, chuyển vị và quay.
- Chọn khe co giãn theo tổng chuyển vị nhiệt, co ngót, từ biến và biến dạng dài hạn.
- Thiết kế lan can, thoát nước, chống thấm, bản dẫn và chống xói.
- Lập trình tự: cọc -> bệ -> trụ -> K0 -> xe đúc -> đốt hẫng -> hợp long -> hoàn thiện.
- Lập bảng chu kỳ đúc, cao độ thiết kế/thực tế và điều kiện an toàn.

Cổng F: trình tự thi công trong thuyết minh, mô hình giai đoạn và bản vẽ phải thống nhất.

### Giai đoạn G - Hồ sơ nộp và bảo vệ

Hồ sơ tối thiểu:

- Thuyết minh thiết kế.
- Bộ bản vẽ bố trí chung, dầm hộp, DƯL, mố, trụ, móng, gối/khe, thoát nước, lan can và thi công.
- Tệp mô hình tính.
- Bảng Excel kiểm tra.
- Bảng khối lượng sơ bộ.
- Nhật ký giả thiết đầu vào.
- Phụ lục nguồn, ảnh địa hình và dữ liệu cần thay trước triển khai thực tế.

Cổng G: kích thước, cao độ, vật liệu, tải trọng và kết quả giữa mô hình, Excel, bản vẽ và thuyết minh phải đối chiếu chéo.

## 7. Cấu trúc thư mục làm việc đề xuất

```text
00_DE_BAI
01_TIEU_CHUAN
02_SO_LIEU_DAU_VAO
03_DIA_HINH_TUYEN
04_PHUONG_AN_CAU
05_MO_HINH_MIDAS
06_TINH_KET_CAU_NHIP
07_TINH_TRU_MO_MONG
08_HANG_MUC_PHU
09_BIEN_PHAP_THI_CONG
10_BAN_VE
11_KHOI_LUONG
12_THUYET_MINH
13_KIEM_TRA_CHEO
14_SLIDE_BAO_VE
```

## 8. Nhật ký quyết định

| ID | Quyết định | Trạng thái | Bằng chứng cần có |
|---|---|---|---|
| DEC-001 | Chọn PA2 dầm hộp 45+75+45 m | preliminary | Bảng so sánh + duyệt GVHD |
| DEC-002 | Thi công đúc hẫng cân bằng | assigned | Đề bài |
| DEC-003 | Dùng dầm hộp biến chiều cao | proposed | Kiểm toán hình học và nội lực |
| DEC-004 | Móng cọc khoan nhồi ngàm cát chặt | preliminary | Khảo sát địa chất + tính cọc |

## 9. Checklist kiểm tra cuối

- [ ] Mọi đầu vào có nguồn và trạng thái.
- [ ] Tiêu chuẩn có điều khoản tương ứng với từng phép kiểm toán.
- [ ] Sơ đồ nhịp, cao độ và mặt cắt thống nhất giữa mô hình và bản vẽ.
- [ ] Tải trọng và tổ hợp đầy đủ.
- [ ] Mô hình xét đúng giai đoạn thi công.
- [ ] Mất mát DƯL, co ngót, từ biến và nhiệt đã được xét.
- [ ] Đã kiểm tra cường độ, sử dụng và mỏi liên quan.
- [ ] Trụ/mố/móng đã xét xói, lún, ổn định và nhóm cọc.
- [ ] Gối và khe đủ khả năng chuyển vị/quay.
- [ ] Trình tự thi công thống nhất với mô hình.
- [ ] Khối lượng truy xuất được từ kích thước đã khóa.
- [ ] Có kiểm tra độc lập và danh mục dữ liệu giả định phải thay.

## 10. Liên kết kiến thức

- [[00 - Brain 2 Dashboard|DYLIGHT Brain 2 Dashboard]]
- [[Standards/TCVN 11823-2017/00 - TCVN 11823-2017|TCVN 11823:2017]]
- [[Research Lab/00 - Research Lab Dashboard|DYLIGHT Research Lab]]
- [[DYLIGHT Bridge Evolution/Projects/Do an cau vuot song/01 - NotebookLM Research Map|Bản đồ NotebookLM cho đồ án]]
- [[DYLIGHT Bridge Evolution/Projects/Do an cau vuot song/02 - NotebookLM Two-Way Sync|Nhật ký đồng bộ hai chiều NotebookLM]]
- [[DYLIGHT Bridge Evolution/NotebookLM/00 - NotebookLM Bridge Library|Toàn bộ thư viện NotebookLM cầu và Bridge BIM]]

## 11. Việc tiếp theo

1. Nhập file địa hình và khóa hệ tọa độ/hệ cao độ.
2. Hỏi GVHD năm điểm ở mục 4.
3. Tạo `Input_Register.xlsx` và `Decision_Log.xlsx`.
4. Dựng bình đồ/trắc dọc sơ bộ trước khi mô hình kết cấu.
