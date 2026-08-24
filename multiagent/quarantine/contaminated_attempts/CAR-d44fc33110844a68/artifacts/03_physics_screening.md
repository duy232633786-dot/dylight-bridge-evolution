# Kiểm toán Vật lý F0 & Điều kiện Gỡ STOP cho Giả thuyết Dầm 480 m
## Physics-in-the-Loop Audit, Dimensional Verification & STOP Removal Conditions — F0 IDEA

**Mã task:** `RND-b471879e-03` · **Workstream:** `structural_physics` · **Claim level:** **F0 IDEA** (Chưa đạt `SCREENED`, chưa chạy solver)  
**Agent thực hiện:** `codex` (Vai trò: `structural_analyst`) · **Reviewer chỉ định:** `opencode` (`independent_reproducer`)  
**Mã đợt nghiên cứu (Brief ID):** `RND-20260821-b471879e` · **Trạng thái Solver:** `solver_status = NOT_RUN`

---

> [!CAUTION]
> ### TRẠNG THÁI KIỂM TOÁN VẬT LÝ: STOP / INCONCLUSIVE — F0 IDEA ONLY
> 1. **TRẠNG THÁI CÁC CỔNG VẬT LÝ (PHYSICS GATES PG-1.0):**
>    - **Gate G0 (Design Basis):** `PENDING` — Đang chờ Kỹ sư Cầu đường / Lab Operator cung cấp dữ liệu địa chất, gió, động đất thực địa.
>    - **Gate G1 (Geometry & Reality):** `PENDING` — Đang chờ mô hình 3D tham số hóa có kiểm tra clash, dung sai và tiếp cận bảo trì.
>    - **Gate G2 (Model Quality & Equilibrium):** `PENDING` — Chưa xây dựng mô hình phần tử hữu hạn 3D (F2).
>    - **Solver Status:** **`NOT_RUN`** (Tuyệt đối không chạy giả lập solver, không bịa đặt output số học).
> 2. **CẢNH BÁO AN TOÀN KỸ THUẬT (PG-1.0 / MARP-1.0):**
>    - Không xem hình ảnh render hay mô hình khái niệm F0 là bằng chứng chịu lực.
>    - Nghiêm cấm ép mô hình dầm giản đơn Super-T 38.3 m (`super_t_simple_v1`) hiện có trong mã nguồn làm đại diện cho dầm liên tục nhịp lớn 480 m.
>    - Mọi chỉ tiêu định lượng trong đề tài nghiên cứu đều gắn nhãn **`[UNVERIFIED TARGET / HYPOTHESIS]`**.

---

## 1. Truy vết Nguồn gốc & Mã băm Artifacts Đầu vào (Lineage & Hash Register)

| Thành phần tài liệu | Mã định danh / Đường dẫn | Mã băm SHA-256 xác thực | Trạng thái phê duyệt |
| :--- | :--- | :--- | :---: |
| **Research Brief** | `multiagent/intake/RND-20260821-b471879e.json` | `589f6f7b66ab67fb4608888899276292b6b61c82f181dfb61a0ef2cab7589119` | `CANONICAL` |
| **Task Contract** | `multiagent/tasks/RND-b471879e-03.json` | `d46a623f2330a2ebbfab7d1052804bc407e32077685955b54b75c8a327011250` | `ACTIVE` |
| **Artifact 01 (Design Basis)** | `research/orchestration/RND-20260821-b471879e/01_design_basis_and_evidence.md` | `f5ac96b888a4693c8117a5895524362ff6a78afc9f7a0d0991d87fde058f1910` | `ACCEPTED (F0 IDEA)` |
| **Artifact 02 (Concept Portfolio)** | `research/orchestration/RND-20260821-b471879e/02_concept_portfolio.md` | `13c0b564f157beba54c15d5d26abee5237adacb8947c51a0228c0ff6de3c12e2` | `ACCEPTED (F0 IDEA)` |

---

## 2. Kiểm toán Đại số Bắt buộc về Tỷ số Mômen $M_D / M_L$ (Mandatory Algebra Audit)

### 2.1. Phép tính Đại số Chuẩn xác
Quy tắc nghiên cứu của phòng thí nghiệm yêu cầu tái lập phép kiểm tra đại số cơ bản đối với phát biểu chuyển dịch tỷ số tĩnh tải / hoạt tải $M_D / M_L$ từ $5.50$ về $1.80$:

1. **Giả định Hoạt tải $M_L$ và Đường ảnh hưởng không đổi:**
   - Ban đầu (Baseline):
     $$\left(\frac{M_D}{M_L}\right)_{base} = 5.50 \implies M_{D,base} = 5.50 \cdot M_L$$
   - Khi giảm $60\%$ tổng mômen tĩnh tải $M_D$ (tức còn lại $40\%$ tổng tĩnh tải ban đầu):
     $$M_{D,new} = 0.40 \cdot M_{D,base} = 0.40 \times (5.50 \cdot M_L) = \mathbf{2.20} \cdot M_L$$
     $$\implies \left(\frac{M_D}{M_L}\right)_{new} = \mathbf{2.20} \neq \mathbf{1.80}$$
   - Để đạt chính xác tỷ số mục tiêu $M_D / M_L = 1.80$:
     $$\frac{M_{D,target}}{M_{D,base}} = \frac{1.80 \cdot M_L}{5.50 \cdot M_L} = \frac{1.80}{5.50} = \frac{18}{55} = \mathbf{0.3272727...}$$
     $$\implies \Delta M_{D,required} = 1 - 0.3272727 = \mathbf{67.2727\%}$$

### 2.2. Kết luận Kiểm toán Đại số
- Mức giảm $60\%$ trên tổng tĩnh tải chỉ hạ tỷ số $M_D / M_L$ xuống **$2.20$**.
- Muốn đạt **$1.80$**, tổng mômen tĩnh tải phải giảm tới **$67.2727\%$**.
- Trong thực tế dầm hộp, bản bụng chỉ chiếm khoảng $30\text{--}35\%$ tổng tĩnh tải tại đỉnh trụ. Việc giảm $60\%$ riêng diện tích bản bụng ($A_{web}$) chỉ làm giảm khoảng $18\text{--}21\%$ tổng tĩnh tải ($M_D / M_L \approx 4.35\text{--}4.50$).
- Do đó, mục tiêu $1.80$ không thể đạt được nếu chỉ khoét rỗng bản bụng giàn Michell, mà bắt buộc phải có giải pháp giảm tải đồng bộ (Bản mặt cầu UHPC siêu nhẹ, tối ưu bản đáy, hệ căng CFRP mật độ thấp và cơ chế vòm tự cân bằng).

---

## 3. Kiểm toán Thứ nguyên Cơ học & Năng lượng Biến dạng (Dimensional & Energy Audit)

### 3.1. Tổng Thế Năng $\Pi = U - W$
Quy ước biến phân cơ học cổ điển cho hệ kết cấu đàn hồi:
$$\Pi = U - W$$
Trong đó:
- $U$ là nội năng biến dạng đàn hồi tích lũy trong kết cấu ($[U] = \text{J} = \text{kN}\cdot\text{m}$).
- $W$ là công ngoại lực sinh ra do tải trọng ($[W] = \text{J} = \text{kN}\cdot\text{m}$).
- Trạng thái cân bằng tĩnh học tương ứng với điểm dừng của hàm thế năng: $\delta \Pi = \delta (U - W) = 0$.

### 3.2. Thứ nguyên Năng lượng Uốn và Cắt theo Mô hình Timoshenko
Đối với dầm Timoshenko chịu uốn phẳng và biến dạng cắt:
$$U = U_{bending} + U_{shear} = \frac{1}{2} \int_0^L EI \cdot \kappa(x)^2 \, dx + \frac{1}{2} \int_0^L GA_{eq} \cdot \gamma(x)^2 \, dx$$

Kiểm tra tính nhất quán thứ nguyên chuẩn SI:
1. **Thành phần Năng lượng Uốn ($U_{bending}$):**
   - Độ cứng chống uốn: $[EI] = \text{kN/m}^2 \cdot \text{m}^4 = \text{kN}\cdot\text{m}^2$.
   - Độ cong uốn: $\kappa(x) = \frac{d\theta(x)}{dx}$, đơn vị $[\kappa] = \text{rad/m} = \text{m}^{-1}$.
   - Tích phân năng lượng:
     $$[U_{bending}] = [\text{kN}\cdot\text{m}^2] \cdot [\text{m}^{-2}] \cdot [\text{m}] = \text{kN}\cdot\text{m} = \text{J} \quad (\text{HỢP LỆ})$$

2. **Thành phần Năng lượng Cắt ($U_{shear}$):**
   - Độ cứng chống cắt hiệu dụng: $[GA_{eq}] = \text{kN/m}^2 \cdot \text{m}^2 = \text{kN}$.
   - Biến dạng trượt trung bình: $\gamma(x) = \frac{dw(x)}{dx} - \theta(x)$, đơn vị $[\gamma] = \text{rad} = [-]$ (không thứ nguyên).
   - Tích phân năng lượng:
     $$[U_{shear}] = [\text{kN}] \cdot [-]^2 \cdot [\text{m}] = \text{kN}\cdot\text{m} = \text{J} \quad (\text{HỢP LỆ})$$

---

## 4. Danh mục Các Hiện tượng Cơ học & Bằng chứng Còn thiếu (Missing Physics & Evidence)

Mô hình sơ bộ dầm Timoshenko 1D chỉ là phép tính bậc thấp (L1). Trước khi có thể đưa ra bất kỳ kết luận nào về tính khả thi của nhịp dầm liên tục 480 m, các hiện tượng cơ học sau bắt buộc phải được giải quyết:

```
+====================================================================================================+
|                          DANH MỤC HIỆN TƯỢNG CƠ HỌC BẮT BUỘC PHẢI BỔ SUNG                          |
+====================================================================================================+
| 1. Lực dọc trục và hiệu ứng P-Delta (Axial-Bending Interaction & Geometric Nonlinearity):          |
|    Lực đẩy nén lớn từ vòm Catenary tương tác với mômen uốn âm làm tăng độ võng và ứng suất cục bộ.  |
+----------------------------------------------------------------------------------------------------+
| 2. Xoắn thuần, Xoắn vênh và Mất ổn định xoắn uốn (Torsion, Warping & Lateral-Torsional Buckling):  |
|    Bản bụng dạng giàn hở làm suy giảm nghiêm trọng độ cứng xoắn St. Venant (GJ) và độ cứng vênh (E_Iw)|
|    so với dầm hộp vách kín truyền thống.                                                           |
+----------------------------------------------------------------------------------------------------+
| 3. Độ mềm xoay và Ứng suất tập trung tại Nút Giàn (Joint Compliance & Stress Concentration):       |
|    Mối nối giữa thanh CFRP/thép và bản bê tông UHPC phát sinh biến dạng xoay phi tuyến và tập trung  |
|    ứng suất cắt nguy hiểm, không thể coi là nút ngàm lý tưởng.                                      |
+----------------------------------------------------------------------------------------------------+
| 4. Trình tự Thi công và Lịch sử Tải trọng (Construction Stages & Time-Dependent Effects):          |
|    Quá trình vươn hẫng đúc/lắp ghép 240 m mỗi bên trụ đòi hỏi cáp giằng tạm, kiểm soát dao động gió  |
|    và tích lũy từ biến/co ngót bê tông theo thời gian.                                             |
+----------------------------------------------------------------------------------------------------+
| 5. Ổn định Khí đàn hồi (Aeroelastic Stability — Flutter, Vortex-Induced Vibration, Buffeting):     |
|    Nhịp dầm mảnh 480 m có tần số dao động riêng thấp, nhạy cảm với hiện tượng cộng hưởng gió bão.  |
+----------------------------------------------------------------------------------------------------+
| 6. Độ bền Mỏi và Dão-Phá hủy của Cáp & Neo CFRP (Fatigue, Creep-Rupture & Anchor Durability):      |
|    Thiếu dữ liệu thử nghiệm độc lập chu kỳ mỏi (2 triệu chu kỳ) và hệ số dão dài hạn (Gate G6).   |
+====================================================================================================+
```

---

## 5. Năm Điều kiện Bắt buộc để Gỡ bỏ Trạng thái STOP (STOP Removal Conditions)

Trạng thái `STOP` hiện tại chỉ được phép gỡ bỏ khi toàn bộ 5 điều kiện sau được thỏa mãn đầy đủ:

1. **Điều kiện 1 (Gate G0 Approval):**  
   Chủ nhiệm đề tài / Kỹ sư Cầu đường có thẩm quyền phê duyệt bộ Cơ sở Thiết kế (Design Basis) hoàn chỉnh với số liệu địa chất móng, điều kiện gió bão, phổ động đất thực địa và tải trọng giao thông cụ thể.
2. **Điều kiện 2 (Gate G1 Repeatable Geometry):**  
   Xây dựng mô hình hình học 3D tham số hóa (B-Rep / IFC) tái lập được với đầy đủ kiểm tra không gian: không xung đột thanh giàn (clash-free), có phân tích dung sai chế tạo (fabrication tolerances) và lối tiếp cận bảo trì/kiểm tra bên trong lòng dầm.
3. **Điều kiện 3 (Gate G2/F2 Verified 3D FE Solver):**  
   Thiết lập mô hình phần tử hữu hạn 3D (dầm không gian / vỏ / khối) trên phần mềm tiêu chuẩn (Midas Civil, OpenSees hoặc Abaqus) với phân tích hội tụ lưới (mesh convergence) và kiểm tra cân bằng phản lực độc lập.
4. **Điều kiện 4 (Gate G6 Material Provenance & Test Data):**  
   Cung cấp hồ sơ nguồn gốc xuất xứ vật liệu (batch provenance, EPD), đường cong ứng suất - biến dạng thực nghiệm của bê tông UHPC và báo cáo thử nghiệm kéo/mỏi/dão độc lập của cáp và đầu neo CFRP.
5. **Điều kiện 5 (Pre-Registered Numerical Experiment Protocol):**  
   Đăng ký trước (pre-register) toàn bộ ma trận tính toán, solver version, tolerance và tiêu chí bác bỏ cụ thể trước khi thực hiện chạy số liệu.

---

## 6. Kết luận & Khuyến nghị Điều phối (Orchestration Summary)

- **Kết luận:** Giả thuyết dầm liên tục 480 m bản bụng giàn Michell và cáp CFRP ở giai đoạn F0 là một ý tưởng hình học giàu tiềm năng nhưng **chưa có cơ sở dữ liệu để khẳng định tính khả thi kết cấu**.
- **Quyết định:** Duy trì trạng thái **`STOP / INCONCLUSIVE`** ở cấp độ **F0 IDEA**.
- **Chuyển giao:** Nộp handoff cho Task `RND-b471879e-03` để `opencode` tiến hành kiểm tra tái lập độc lập tại Task `RND-b471879e-04`.

---
*Báo cáo được lập bởi Codex Structural Analyst. Tuân thủ nghiêm ngặt Giao thức MARP-1.0 và Bộ cổng Vật lý PHYSICS_GATES.md (PG-1.0).*
