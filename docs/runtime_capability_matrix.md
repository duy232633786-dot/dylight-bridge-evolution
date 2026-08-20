# Ma trận Năng lực Runtime (Runtime Capability Matrix) — DYLIGHT Bridge Evolution

Phiên bản: `1.0.0` — Ngày lập: `2026-08-21`

Tài liệu này ghi nhận chính xác năng lực tính toán, mô phỏng và kiểm toán thực tế của runtime `dylight-bridge-evolution`, ngăn ngừa tuyên bố sai lệch giữa tài liệu nghiên cứu và phần mềm.

---

## 1. Trạng thái các Phân hệ Runtime

| Phân hệ | Thành phần mã nguồn | Cấp độ Claim hiện tại | Trạng thái kỹ thuật | Ghi chú & Giới hạn |
|---|---|---|---|---|
| **Hình học Catalog (v1)** | `geometry.py`, `bridge_grammar/super_t_simple_v1.json` | `SCREENED` | ✅ Hoàn thành | 8 biến rời rạc, 3 mã dầm Super-T (ST-1650, ST-1750, ST-1850). |
| **Hình học Tham số Tự do (v2)** | `geometry_parametric.py` | `SCREENED` | ✅ Hoàn thành | Phân tích FEA 2D qua `sectionproperties` và Green's Theorem. |
| **L0 Hình học & Cấu tạo** | `geometry.py`, `check_geometry()` | `SCREENED` | ✅ Hoàn thành | Kiểm tra GEOM-001, GEOM-002, GEOM-003, CONS-001, CONS-002. |
| **L1 Solver Dầm đơn** | `fe_adapter/line_girder.py` | `SCREENED` | ✅ Hoàn thành | Quét hoạt tải HL-93 / TCVN 11823-3, phân bố ngang Type-k. |
| **L2 Solver Grillage 3D** | `ospgrillage` + `OpenSeesPy` | `NUMERICALLY_VERIFIED` (Mô phỏng) | 🔶 Sẵn sàng hạ tầng | Wrapper mạng dầm 3D, đang chờ hiệu chuẩn với dữ liệu Midas Civil. |
| **Open BIM IFC 4.3** | `bim/ifc_bridge_exporter.py` | `SCREENED` (Hình học BIM) | ✅ Hoàn thành | Xuất `IfcBridge` 3D Solid với thuộc tính Pset kỹ thuật chuẩn buildingSMART. |
| **Tối ưu Đa mục tiêu** | `optimization/nsga2.py`, `optimization/pymoo_adapter.py` | `SCREENED` | ✅ Hoàn thành | Quản lý ngân sách gọi solver chặt chẽ qua `BudgetedEvaluator`. |
| **Kho Tri thức Não 2** | `knowledge/cards/` (20 thẻ KC-001..KC-020) | `DRAFT` | ✅ Hoàn thành khung | Cần kỹ sư cầu phê duyệt trước khi nâng lên `ENGINEER_APPROVED`. |

---

## 2. Quy tắc An toàn và Tính toán Bất biến

1. **Ràng buộc cứng (Hard Constraints)**: Mọi điều kiện an toàn uốn (STR-001), cắt (STR-002), kéo thớ dưới (SERV-001), võng hoạt tải (SERV-002) và cấu tạo (GEOM, CONS) là bất khả xâm phạm.
2. **Ngân sách gọi solver**: Chỉ tăng khi solver vật lý thực sự chạy (`solver.status != NOT_RUN`).
3. **Tính tái lập**: Mọi kết quả được định danh bằng SHA-256 qua `canonical_json(state)`.
