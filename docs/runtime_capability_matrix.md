# Ma trận Năng lực Runtime — DYLIGHT Bridge Evolution

Phiên bản: `RCM-2.0.0` — cập nhật `2026-08-21` (BRD-001). Package: `0.8.0`.

Tài liệu này ghi **runtime CÓ gì và KHÔNG có gì**, kèm bằng chứng là đường dẫn
file và tên hàm. Trần claim hiện tại của toàn dự án là **`SCREENED`**
(nguồn: `multiagent/lab.json` → `current_project_claim_ceiling`).

> **Bản này KHÔNG phải nguồn chuẩn.** Nguồn chuẩn máy đọc là
> `docs/runtime_capability_matrix.json` (schema:
> `contracts/runtime_capability_matrix.schema.json`). Bộ kiểm
> `docs/check_runtime_drift.py` import và **gọi thật** từng năng lực rồi so với
> bảng dưới đây; lệch một ô là đỏ. Sửa bảng mà quên sửa JSON — hoặc ngược lại —
> cũng đỏ.
>
> ```
> PYTHONIOENCODING=utf-8 python docs/check_runtime_drift.py
> ```

Ba trạng thái, hiểu theo nghĩa kiểm được:

| Trạng thái | Nghĩa | Bộ kiểm chứng minh bằng cách |
|---|---|---|
| `PRESENT` | Gọi được thật, không kèm điều kiện đặc biệt | import module + gọi hàm |
| `PARTIAL` | Gọi được nhưng có giới hạn BẮT BUỘC phải nêu ở cột cuối | import + gọi, và kiểm chính giới hạn đó (ví dụ: phụ thuộc không khai báo trong `pyproject.toml`) |
| `ABSENT` | **Không** gọi được | gọi và bắt đúng exception, hoặc chứng minh không dòng mã nào trong `bridge_evolution/` dùng tới |

---

## 1. Bảng năng lực

| ID | Trạng thái | Năng lực | Bằng chứng (file::hàm) | Giới hạn trung thực |
|---|---|---|---|---|
| `GRAMMAR_V1_CATALOG` | PRESENT | Grammar v1 — tiết diện định hình tra catalog | `bridge_grammar/super_t_simple_v1.json`; `bridge_evolution/geometry.py::resolve_section` | Đặc trưng tiết diện, đơn giá và hệ số carbon trong `catalogs/catalogs.json` là **placeholder đúng bậc độ lớn**, chưa hiệu chỉnh theo hồ sơ Super-T thực. |
| `GRAMMAR_V2_PARAMETRIC` | PRESENT | Grammar v2 — tiết diện tham số hoá 6 biến hình dạng, nằm **trong** vòng tối ưu | `bridge_grammar/super_t_parametric_v2.json`; `bridge_evolution/section.py::section_from_params`; `bridge_evolution/geometry.py::resolve_section` | Đặc trưng tiết diện tính bằng **tích phân Green trên đa giác gần đúng** (bỏ vút, bỏ bo góc, sườn coi như dày đều). Vòng tìm kiếm **không** dùng phần tử hữu hạn 2D. |
| `L0_LAYOUT_RULES` | PRESENT | L0 bố trí mặt cắt ngang — 5 rule bố trí L0 (`GEOM-001…003`, `CONS-001…002`) | `bridge_evolution/geometry.py::check_geometry` | — |
| `L0_FABRICATION_RULES` | PARTIAL | L0 chế tạo/vận chuyển/cẩu lắp — 7 rule FAB-001…FAB-007 cộng `FAB-000` (fail-closed) | `bridge_evolution/section.py::fabrication_violations`; `bridge_evolution/geometry.py::check_geometry` | **Chỉ áp cho tiết diện `PARAMETRIC`.** Tiết diện catalog v1 **không** bị FAB-\* kiểm. Ngưỡng FAB là giá trị mặc định của repo/rule profile, **chưa** lấy từ crane chart, khảo sát tuyến vận chuyển hay hệ ván khuôn của một nhà máy thực. |
| `L1_LINE_GIRDER_SOLVER` | PRESENT | L1 — dầm đơn + hệ số phân bố ngang, hoạt tải HL-93/TCVN 11823 | `bridge_evolution/fe_adapter/line_girder.py::analyze`; `bridge_evolution/fe_adapter/solver.py::run_analysis` | Đàn hồi, tức thời. **Không** có mất mát DƯL theo giai đoạn, ứng suất lúc truyền lực, co ngót–từ biến, ổn định thành mỏng, xoắn. |
| `INDEPENDENT_VERIFIER` | PRESENT | Verifier độc lập ra PASS/FAIL (`STR-001/002`, `SERV-001/002/003`, `MODEL-001`) | `bridge_evolution/verifier/rules.py::verify_candidate` | — |
| `EVALUATION_CONTRACT` | PRESENT | Contract trung tâm + provenance SHA-256 tái lập | `bridge_evolution/evaluate.py::evaluate_candidate` | — |
| `OPTIMIZATION_BUILTIN` | PRESENT | Random Search + NSGA-II nội bộ, ngân sách solver công bằng | `bridge_evolution/optimization/nsga2.py::nsga2`; `bridge_evolution/optimization/common.py::BudgetedEvaluator` | — |
| `OPTIMIZATION_PYMOO` | PARTIAL | Adapter pymoo (NSGA-II của thư viện ngoài) | `bridge_evolution/optimization/pymoo_adapter.py::run_pymoo_optimization` | `pymoo` được **import cứng** nhưng **không** khai báo trong `pyproject.toml` lẫn `requirements-dev.lock`. Cài đúng theo README thì module này và test của nó lỗi import. |
| `SECTION_FEA_2D` | PARTIAL | Phân tích tiết diện 2D bằng `sectionproperties` | `bridge_evolution/geometry_parametric.py::compute_super_t_section_properties` | **Không nằm trong vòng tối ưu.** Đây là mô hình tiết diện **thứ hai**, bộ tham số khác hẳn grammar v2 (`bottom_thickness_m`…), chỉ chạy khi truyền `use_sectionproperties_fem=True` qua CLI `section --fem` hoặc bộ xuất IFC. `shapely` và `sectionproperties` **không** khai báo trong `pyproject.toml`. |
| `IFC_4X3_EXPORT` | PARTIAL | Xuất Open BIM IFC 4.3 (`IfcBridge`) | `bridge_evolution/bim/ifc_bridge_exporter.py::export_bridge_to_ifc` | `ifcopenshell` **không** khai báo trong `pyproject.toml` lẫn `requirements-dev.lock`. Hình học xuất ra lấy từ `geometry_parametric.py`, **không phải** tiết diện mà vòng tối ưu grammar v2 thực sự dùng. |
| `KNOWLEDGE_CARD_STORE` | PRESENT | Não 2 — kho thẻ tri thức: 20 thẻ (`KC-001`…`KC-020`), có schema | `bridge_evolution/knowledge/store.py::load_cards`; `contracts/knowledge_card.schema.json` | Thẻ chỉ **gợi ý**; PASS/FAIL luôn thuộc verifier. Toàn bộ 20 thẻ đang là `DRAFT`. |
| `KNOWLEDGE_AUDIT` | PARTIAL | Audit thẻ — audit phủ đủ 20 thẻ mà runtime nạp | `knowledge/audits/current.json`; `contracts/knowledge_audit.schema.json` | Khối `evidence` của audit chỉ có **một** nguồn: oracle vét cạn grammar v1. Thẻ v2 (`KC-010…KC-020`) được phủ nhưng **không** có oracle tương ứng, phần lớn mang `claim_audit = NOT_TESTED`. **Phủ đủ ≠ đã kiểm chứng.** |
| `SOLVER_MIDAS_CIVIL` | ABSENT | L2/L3 — adapter Midas Civil | `bridge_evolution/fe_adapter/solver.py::run_analysis` | Chỉ là nhánh dispatch **ném `SolverError`**. Không có kết nối MCP/Open API, không có mô hình, không có kết quả Midas nào trong repo. |
| `SOLVER_OPENSEESPY` | ABSENT | L2 — adapter OpenSeesPy | `bridge_evolution/fe_adapter/solver.py::run_analysis` | Nhánh dispatch **ném `SolverError`**. Thư viện `openseespy` có thể cài được, nhưng **không dòng mã nào** trong `bridge_evolution/` gọi tới nó. |
| `GRILLAGE_3D` | ABSENT | L2 — mạng dầm 3D (grillage) qua `ospgrillage` | `bridge_evolution/fe_adapter/solver.py::run_analysis` | **Không tồn tại wrapper nào.** Không module nào trong `bridge_evolution/` import `ospgrillage`. Mọi phát biểu kiểu "hạ tầng grillage đã sẵn sàng" là **sai**. |
| `STAGED_PRESTRESS_EFFECTS` | ABSENT | Ứng suất lúc truyền lực, mất mát DƯL, co ngót–từ biến | `bridge_evolution/verifier/rules.py::verify_candidate` | Runtime **không phát ra rule nào** cho các hiệu ứng này. Tập đầy đủ `rule_id` runtime có thể phát ra được khai tại `runtime_rule_inventory` trong file JSON. |
| `ENGINEER_APPROVED_KNOWLEDGE` | ABSENT | Tri thức đã được kỹ sư cầu phê duyệt | `bridge_evolution/knowledge/store.py::load_cards`; `contracts/knowledge_card.schema.json` | **0/20 thẻ** ở trạng thái `ENGINEER_APPROVED`. Không thẻ nào được dùng làm căn cứ kết luận. |
| `PHYSICAL_TEST_EVIDENCE` | ABSENT | Thí nghiệm vật lý / quan trắc hiện trường | `multiagent/lab.json`; `knowledge/audits/current.json` | Không có dữ liệu đo nào trong repo. Mọi "evidence" hiện có đều là kết quả mô phỏng `builtin-l1/0.2.0`. Trần claim dự án bị khoá ở `SCREENED`. |
| `GRAMMAR_V2_ORACLE` | ABSENT | Oracle vét cạn cho grammar v2 | `knowledge/audits/current.json` | Miền v2 ~41,9 tỷ tổ hợp — không vét cạn được, và chưa có mẫu phân tầng thay thế. Vì vậy `KC-010…KC-020` **không có nguồn oracle**. |

Grammar v1 hiện có **3 mã dầm Super-T định hình** dùng được (`ST-1650`, `ST-1750`,
`ST-1850`); `ST-PARAM` chỉ là marker của grammar v2 và `ST-TEST-SINGULAR` là
entry test-only cho đường `SOLVER_FAILED`.

---

## 2. Những phát biểu đã bị gỡ khỏi bản 1.0.0 vì nói quá

Bản trước của tài liệu này (`1.0.0`, 2026-08-21) chứa các phát biểu sau. Chúng
được ghi lại ở đây để chuỗi kiểm toán không mất dấu, **không** để dùng lại.

| Phát biểu cũ | Vì sao sai | Trạng thái đúng |
|---|---|---|
| "L2 Solver Grillage 3D — `ospgrillage` + `OpenSeesPy` — Sẵn sàng hạ tầng" | Không có module nào trong `bridge_evolution/` import `ospgrillage`; nhánh `OPENSEESPY` ném `SolverError` | `GRILLAGE_3D` = ABSENT |
| Gán cấp claim `NUMERICALLY_VERIFIED` cho L2 | Vượt trần `SCREENED` của chính dự án (`multiagent/lab.json`) — vi phạm `CLAIM_ORDER` trong `bridge_evolution/collaboration/lab.py` | Không năng lực nào được gán cấp cao hơn `SCREENED` |
| "Hình học Tham số Tự do (v2) — `geometry_parametric.py` — Phân tích FEA 2D qua `sectionproperties` và Green's Theorem" | Gộp hai mô hình khác nhau làm một. Vòng tối ưu v2 dùng `section.py` (Green, thuần toán); `geometry_parametric.py` là mô hình riêng, chỉ chạy khi bật cờ | Tách thành `GRAMMAR_V2_PARAMETRIC` (PRESENT) và `SECTION_FEA_2D` (PARTIAL) |
| "Kho Tri thức Não 2 — 20 thẻ — ✅ Hoàn thành khung" trong khi audit chỉ phủ 9 thẻ | Ma trận và audit mâu thuẫn nhau ngay trong cùng một repo | `KNOWLEDGE_AUDIT` = PARTIAL, audit phủ đủ 20 thẻ với trạng thái thật |
| "Open BIM IFC 4.3 — ✅ Hoàn thành" | `ifcopenshell` không khai báo phụ thuộc; cài theo README là không chạy được | `IFC_4X3_EXPORT` = PARTIAL |

---

## 3. Quy tắc an toàn và bất biến (không đổi)

1. **Ràng buộc cứng**: uốn `STR-001`, cắt `STR-002`, kéo thớ dưới `SERV-001`,
   võng hoạt tải `SERV-002`, cấu tạo `GEOM-*`/`CONS-*` và chế tạo `FAB-*` là bất
   khả xâm phạm; chi phí/carbon không mua được vi phạm.
2. **Ngân sách solver** chỉ tăng khi solver vật lý thật sự chạy
   (`solver.status != NOT_RUN`).
3. **Tái lập**: mọi kết quả định danh bằng SHA-256 qua `canonical_json(state)`.
4. **Trần claim**: `SCREENED`. Nâng trần đòi hỏi L2/L3 thật, kiểm chứng độc lập,
   thí nghiệm/quan trắc thích hợp **và** kỹ sư chịu trách nhiệm phê duyệt —
   không bước nào trong ba bước đó tồn tại trong repo hôm nay.

---

## 4. Cách bảo trì tài liệu này

1. Đổi runtime → sửa `docs/runtime_capability_matrix.json` trước.
2. Chạy `python docs/check_runtime_drift.py`; nó sẽ nói chính xác ô nào trong
   `.md` còn lệch.
3. Sửa `.md` cho khớp. Không sửa ngược lại từ `.md` sang JSON.
4. Bộ kiểm **chưa** nằm trong `python -m pytest tests -q` vì `tests/` nằm ngoài
   `write_scope` của BRD-001. Cách nối vào pytest được ghi nguyên văn trong
   docstring đầu file `docs/check_runtime_drift.py` (một file ba dòng).
