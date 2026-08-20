# 01 — Research Contract (P0)

**Đề tài (phạm vi MVP):** Nghiên cứu môi trường AI tối ưu đa mục tiêu phương án
cầu dầm **Super-T giản đơn** thông qua mô hình BIM tham số, mô phỏng phần tử
hữu hạn và học tăng cường có ràng buộc.

Phiên bản: `RC-1.1` — 2026-08-21. Mọi thay đổi phạm vi phải tăng phiên bản.

**Thay đổi ở RC-1.1 (mở rộng phạm vi, giữ nguyên toàn bộ RC-1.0):** bổ sung
grammar thứ hai `super_t_parametric_v2` cho phép agent **tự thiết kế hình dạng
mặt cắt dầm** (6 biến hình học rời rạc) thay vì chỉ chọn tiết diện định hình,
kèm nhóm ràng buộc **chế tạo/vận chuyển/cẩu lắp (FAB-*)** ở cấp L0. Grammar v1
vẫn là **arm đối chứng** — mọi so sánh phải chạy hai arm cùng ngân sách solver.
Xem `docs/03_shape_evolution.md` cho thang 5 cấp tự do thiết kế và giới hạn
trung thực của từng cấp.

## 1. Phạm vi cố định (KHÔNG phải biến tối ưu)

| Đầu vào dự án | Giá trị MVP | Ghi chú |
|---|---|---|
| Họ cầu | Super-T, nhịp giản đơn | 1 họ duy nhất |
| Chiều dài nhịp | 38.3 m | tim gối → tim gối |
| Bề rộng mặt cầu | 12.0 m | 3 làn xe cơ giới quy đổi |
| Tuyến | Thẳng, skew = 0° | không cong, không xiên |
| Tải trọng | HL-93 (TCVN 11823-3), IM = 33% truck | LOAD-PROFILE-01 |
| Tổ hợp | Cường độ I, Sử dụng III, võng L/800 | BRIDGE-RULESET-V1 |
| Lớp phủ | Asphalt 75 mm, γ = 22.5 kN/m³ | DW |
| Lan can | 2 × 5.0 kN/m | DW |

## 2. Biến thiết kế (8 biến, toàn bộ rời rạc)

Xem `bridge_grammar/super_t_simple_v1.json`. Tóm tắt:

| # | Biến | Miền | Kiểu |
|---|---|---|---|
| 1 | `girder_catalog_id` | ST-1650 / ST-1750 / ST-1850 | catalog |
| 2 | `girder_count` | 5…8 | int |
| 3 | `girder_spacing_mm` | 2150…2900, bước 50 | grid |
| 4 | `deck_slab_thickness_mm` | 175…250, bước 5 | grid |
| 5 | `girder_concrete_id` | C40 / C45 / C50 | catalog |
| 6 | `deck_concrete_id` | C30 / C35 | catalog |
| 7 | `diaphragm_layout_id` | DG-END-ONLY / DG-3 / DG-5 | catalog |
| 8 | `prestress_layout_id` | PT-34 … PT-54 (bước 4 tao) | catalog |

RL/EA **không bao giờ** nhập giá trị liên tục tùy ý — chỉ chọn từ miền trên
(action mask + design grammar).

## 3. Mục tiêu tối ưu (minimize)

1. `relative_cost` — chi phí tương đối (bê tông + cáp DƯL + chi phí cố định/dầm).
2. `embodied_carbon` — phát thải carbon vật liệu (kgCO₂e).
3. `material_mass` — tổng khối lượng vật liệu (tấn).

Ràng buộc an toàn/cấu tạo là **hard constraint**, không nằm trong hàm mục tiêu
để đánh đổi.

## 4. Ràng buộc (BRIDGE-RULESET-V1)

| Rule | Nội dung | Loại |
|---|---|---|
| GEOM-001 | Bố trí dầm nằm gọn trong bề rộng cầu; cánh hẫng ∈ [0.4 m, min(1.5 m, 0.6·S)] | HARD |
| GEOM-002 | Khe hở cánh dầm liền kề ≥ 40 mm | HARD |
| GEOM-003 | Chiều dày bản ≥ max(175 mm, (S+3000)/30) | HARD |
| STR-001 | Uốn Cường độ I: Mu ≤ φMn (φ = 1.0, DƯL dính bám) | HARD |
| STR-002 | Cắt Cường độ I: Vu ≤ φVn (φ = 0.9, mô hình đơn giản hóa) | HARD |
| SERV-001 | Ứng suất kéo thớ dưới, Sử dụng III ≤ 0.5√f'c | HARD |
| SERV-002 | Võng hoạt tải ≤ L/800 | HARD |
| SERV-003 | Tần số dao động cơ bản ≥ 2.0 Hz | SOFT |
| CONS-001 | Số hàng dầm ngang tối thiểu theo nhịp (L > 30 m → ≥ 3 hàng, k/c ≤ 10 m) | HARD |
| CONS-002 | Biến nằm đúng lưới grammar (chuẩn hóa cấu kiện) | HARD |

## 5. Mô phỏng đa cấp

| Cấp | Nội dung | Dùng cho |
|---|---|---|
| L0 | Hình học, bố trí, cấu tạo — không mở solver | mọi candidate |
| L1 | Dầm đơn + hệ số phân bố ngang (AASHTO/TCVN 11823 type-k), hoạt tải di động quét chính xác, mặt cắt liên hợp | sinh mẫu hàng loạt, EA/RL |
| L2 | Grillage/3D — **Midas Civil NX qua MCP/Open API** (chính), OpenSeesPy (dự phòng mã mở) | top ứng viên (chưa triển khai) |
| L3 | Phi tuyến, co ngót–từ biến, giai đoạn thi công — Midas Civil | nhóm cuối (chưa triển khai) |

Định hướng công cụ đã chốt: **mô hình BIM = Revit** (qua revit-mcp hiện có), **phân tích
kiểm chứng = Midas Civil** (qua MCP), solver L1 nội bộ dùng cho sinh mẫu hàng loạt/EA/RL.

## 6. Đánh giá khoa học

So sánh trong **cùng ngân sách gọi solver**: Random Search / NSGA-II /
(sau này: surrogate-EA, RL±shield). Chỉ số: tỷ lệ khả thi, best/median cost,
Pareto hypervolume, độ đa dạng, số solver call tới phương án khả thi đầu tiên.
Kết luận dạng "RL thắng" **không** được đặt trước.

## 7. Điều kiện dữ liệu

Catalog tiết diện/giá/carbon hiện là placeholder bậc độ lớn đúng. Gate trước khi
công bố kết quả: hiệu chỉnh catalog theo hồ sơ Super-T thực + toàn bộ
`gold_cases/` được kỹ sư xác nhận (human approval REQUIRED).
