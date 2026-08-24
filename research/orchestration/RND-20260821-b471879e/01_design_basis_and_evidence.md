# Cơ sở Thiết kế, Phân loại Bằng chứng & Tiêu chí Bác bỏ Giả thuyết Dầm Liên tục 480 m
## Design Basis, Evidence Boundary & Pre-Registered Falsification Criteria — G0 PENDING / F0 IDEA

**Mã task:** `RND-b471879e-01` · **Workstream:** `design_basis` · **Claim level:** **F0 IDEA** (Trạng thái Cổng G0: **PENDING**)  
**Agent thực hiện:** `antigravity` (Vai trò: `evidence_safety_auditor`) · **Reviewer chỉ định:** `codex` (`structural_analyst`)  
**Mã đợt nghiên cứu (Brief ID):** `RND-20260821-b471879e` · **Chế độ vận hành:** `DIGITAL_AUTO`  
**Tiêu chuẩn áp dụng:** `CHƯA XÁC ĐỊNH / TBD` (Không có tiêu chuẩn hay dữ liệu hiện trường nào được xác minh trong brief)

---

> [!IMPORTANT]
> **Tuyên bố Ranh giới Nghiên cứu, Kiểm soát Cổng An toàn & Cảnh báo Vật lý (MARP-1.0 / PG-1.0):**
> 1. **TRẠNG THÁI CỔNG G0: PENDING (ĐANG CHỜ / CHƯA ĐẠT)**  
>    Tài liệu này xác lập ranh giới dữ liệu, định nghĩa các đại lượng nghiên cứu, thiết lập phép kiểm tra đại số phản biện và đăng ký trước (pre-register) các ngưỡng bác bỏ giả thuyết. Tài liệu **KHÔNG** cấu thành cơ sở thiết kế kỹ thuật hoàn chỉnh để thi công, **KHÔNG** đưa ra kết luận PASS/FAIL, và **KHÔNG** tuyên bố bất kỳ phương án nào là khả thi.
> 2. **CÁC CON SỐ TỪ ĐỀ TÀI LÀ MỤC TIÊU CẦN KIỂM CHỨNG / NGƯỠNG BÁC BỎ (UNVERIFIED HYPOTHESES / FALSIFICATION THRESHOLDS), TUYỆT ĐỐI KHÔNG PHẢI BẰNG CHỨNG (EVIDENCE):**
>    - Chiều dài danh định: **$480\text{ m}$** `[UNVERIFIED TARGET]`
>    - Tỷ lệ giảm diện tích bản bụng: **$\ge 60\%$** (tức $A_{web,candidate} / A_{web,baseline} \le 0.40$) `[UNVERIFIED TARGET]`
>    - Tỷ số độ cứng cắt tương đương: **$GA_{eq} / GA_{baseline} \ge 0.85$** `[UNVERIFIED TARGET]`
>    - Tỷ số mômen tĩnh tải / hoạt tải ban đầu (Baseline): **$(M_D / M_L)_{baseline} = 5.5$** `[UNVERIFIED BASELINE]`
>    - Tỷ số mômen tĩnh tải / hoạt tải mục tiêu (Candidate): **$(M_D / M_L)_{target} = 1.8$** `[UNVERIFIED TARGET]`
> 3. **KIỂM TRA ĐẠI SỐ PHẢN BIỆN BẮT BUỘC (MANDATORY ALGEBRA FALSIFICATION CHECK):**
>    Nếu mômen hoạt tải thiết kế $M_L$ và đường ảnh hưởng nội lực không đổi, việc giảm $60\%$ trên tổng mômen tĩnh tải $M_D$ chỉ có thể đưa tỷ số $M_D / M_L$ từ $5.5$ xuống **$2.20$** ($5.5 \times 0.40 = 2.20 \neq 1.80$). Để đạt được **$1.80$**, tỷ số mômen tĩnh tải chuẩn hóa bắt buộc phải là $1.80 / 5.50 = 18/55 \approx \mathbf{0.32727}$ (tức tổng mômen tĩnh tải $M_D$ phải giảm **$67.273\%$**). Ngoài ra, do bản bụng chỉ đóng góp một phần vào tổng tự trọng kết cấu nhịp (cùng với bản mặt cầu, bản đáy, lớp phủ, lan can, dải phân cách, vách ngăn và hệ neo), việc giảm riêng diện tích bản bụng $60\%$ sẽ chỉ làm giảm tổng mômen tĩnh tải một tỷ lệ nhỏ hơn $60\%$.
> 4. **NGUYÊN TẮC QUY CHUẨN XUẤT XỨ VẬT LIỆU (GATE G6):**
>    Ứng suất tính toán của CFRP $\sigma_{CFRP}$ bắt buộc phải là **ứng suất thiết kế cho phép (design allowable)** có đầy đủ xuất xứ (provenance), dữ liệu thử nghiệm độc lập và hệ số chiết giảm an toàn theo Gate G6, không được tự ý chọn từ cường độ danh định. Mọi thông số vật liệu chưa có báo cáo thử nghiệm đều ở trạng thái `TBD_G6_REQUIRED / UNVERIFIED`.
> 5. **QUY TẮC DỪNG VÀ KHÔNG KẾT LUẬN (STOP / INCONCLUSIVE RULES):**
>    Thiếu dữ liệu Gate G0, solver không hội tụ, sai lệch đơn vị/thứ nguyên, vi phạm cân bằng tĩnh học hoặc sử dụng thuộc tính vật liệu không có xuất xứ đều phải kích hoạt trạng thái **STOP / INCONCLUSIVE**.

---

## 1. Phân loại Ranh giới Dữ liệu (Data Boundary Classification)

Toàn bộ dữ liệu của đề tài được phân định nghiêm ngặt thành đúng 3 nhóm theo quy tắc kiểm toán khoa học:

```
+----------------------------------------------------------------------------------------------------+
|                                    PHÂN LOẠI RANH GIỚI DỮ LIỆU ĐẦU VÀO                              |
+----------------------------------------------------------------------------------------------------+
| 1. KNOWN FROM USER / BRIEF (DỮ LIỆU ĐÃ BIẾT TỪ ĐỀ TÀI — HOÀN TOÀN LÀ UNVERIFIED):                  |
|    - Tên các tham số giả thuyết: h_pier, h_mid, alpha_catenary, theta_michell,                      |
|      t_deck, t_bottom, sigma_CFRP.                                                                 |
|    - Chiều dài danh định: 480 m [UNVERIFIED TARGET].                                               |
|    - Mục tiêu giảm diện tích bản bụng: A_web,cand / A_web,base <= 0.40 (giảm 60%) [UNVERIFIED].     |
|    - Mục tiêu độ cứng cắt tương đương: GA_eq / GA_base >= 0.85 [UNVERIFIED TARGET].                 |
|    - Tỷ số mômen tĩnh tải / hoạt tải baseline: (M_D / M_L)_base = 5.5 [UNVERIFIED BASELINE].        |
|    - Tỷ số mômen tĩnh tải / hoạt tải mục tiêu: (M_D / M_L)_target = 1.8 [UNVERIFIED TARGET].       |
+----------------------------------------------------------------------------------------------------+
| 2. UNKNOWN / TBD (DỮ LIỆU CHƯA BIẾT / CHƯA CÓ CĂN CỨ — BẮT BUỘC PHẢI KHÓA TRƯỚC KHI TÍNH TOÁN):     |
|    - Chiều dài 480 m là nhịp chính hay tổng chiều dài toàn cầu: TBD.                               |
|    - Sơ đồ bố trí nhịp (số nhịp, tỷ lệ nhịp biên / nhịp chính): TBD.                               |
|    - Điều kiện biên gối tựa và ngàm trụ (độ cứng xoay, gối di động/cố định, dầm-trụ): TBD.          |
|    - Bề rộng mặt cầu và cấu tạo mặt cắt ngang (số làn xe, lề bộ hành, dải phân cách): TBD.        |
|    - Tĩnh không thông thuyền đứng và ngang: TBD.                                                   |
|    - Vị trí địa lý, điều kiện địa chất công trình và sức chịu tải của nền móng: TBD.               |
|    - Tiêu chuẩn thiết kế áp dụng và phiên bản quy chuẩn: TBD.                                      |
|    - Mô hình hoạt tải xe, lực rải đều làn, người đi bộ, hệ số xung kích và tải thi công: TBD.     |
|    - Tổ hợp tải trọng và các hệ số tải trọng / sức kháng: TBD.                                     |
|    - Trình tự và giai đoạn thi công (đúc hẫng, lắp ghép phân đoạn, thiết bị nâng): TBD.            |
|    - Sơ đồ bố trí dự ứng lực (trong/ngoài, mất mát DƯL, giai đoạn căng kéo): TBD.                 |
|    - Mô hình ứng xử cơ lý vật liệu của bê tông / UHPC / thép: TBD.                                 |
|    - CFRP: cấu trúc sợi/nhựa, ứng suất thiết kế cho phép, suy giảm môi trường, dão, neo: TBD_G6.  |
|    - Tác động môi trường: gió bão và khí đàn hồi, động đất, thủy văn xói lở, nhiệt độ: TBD.        |
|    - Ràng buộc chế tạo, dung sai, vận chuyển, cẩu lắp và hành lang tiếp cận bảo trì: TBD.          |
+----------------------------------------------------------------------------------------------------+
| 3. PROPOSED RESEARCH DEFINITIONS (ĐỊNH NGHĨA PHỤC VỤ NGHIÊN CỨU & LOGIC BÁC BỎ):                  |
|    - Định nghĩa hệ đơn vị chuẩn hóa SI (m, kN, MPa, tonne, °C, s).                                 |
|    - Phân định các chỉ tiêu R_A (bản bụng, khối lượng, mômen tĩnh tải).                            |
|    - Định nghĩa toán tử độ cứng cắt tương đương R_K theo năng lượng biến dạng ô cơ sở RVE.         |
|    - Định nghĩa chỉ tiêu tỷ số mômen R_M và nguyên tắc xử lý điểm kỳ dị mẫu số gần 0.              |
|    - Bộ 3 tiêu chí bác bỏ giả thuyết (falsification thresholds), không phải tiêu chuẩn nghiệm thu. |
+----------------------------------------------------------------------------------------------------+
```

---

## 2. Kiểm tra Đại số Bắt buộc & Cơ chế Chuyển dịch Tỷ số $M_D / M_L$ (Mandatory Algebra Falsification)

### 2.1. Phép Suy dẫn Đại số Chính xác

Quy tắc nghiên cứu yêu cầu thực hiện kiểm tra đại số độc lập đối với phát biểu chuyển dịch tỷ số mômen tĩnh tải / hoạt tải từ baseline $5.5$ xuống mục tiêu $1.8$:

Giả định mô hình hoạt tải thiết kế $M_L$ và đường ảnh hưởng nội lực không đổi giữa Baseline và Candidate:
1. **Xét quan hệ tỷ số ban đầu (Baseline):**
   $$\left(\frac{M_D}{M_L}\right)_{base} = 5.5 \implies M_{D,base} = 5.5 \cdot M_L$$

2. **Trường hợp 1 — Giảm 60% trên TỔNG mômen tĩnh tải ($M_{D,total}$):**
   Nếu toàn bộ tĩnh tải kết cấu nhịp $M_D$ giảm được $60\%$:
   $$M_{D,new} = (1 - 0.60) \cdot M_{D,base} = 0.40 \times (5.5 \cdot M_L) = 2.20 \cdot M_L$$
   $$\implies \left(\frac{M_D}{M_L}\right)_{new} = \mathbf{2.20} \neq \mathbf{1.80}$$
   *Kết luận 1:* Giảm $60\%$ trên tổng tĩnh tải chỉ đưa tỷ số về $2.20$, **chưa thể đạt mức $1.80$**.

3. **Trường hợp 2 — Xác định mức giảm tổng tĩnh tải cần thiết để đạt chính xác $M_D / M_L = 1.80$:**
   Để đạt tỷ số mục tiêu $1.80$:
   $$M_{D,target} = 1.80 \cdot M_L \implies \frac{M_{D,target}}{M_{D,base}} = \frac{1.80 \cdot M_L}{5.50 \cdot M_L} = \frac{1.80}{5.50} = \frac{18}{55} \approx \mathbf{0.32727}$$
   $$\implies \Delta M_{D,required} = 1 - 0.32727 = \mathbf{67.273\%}$$
   *Kết luận 2:* Muốn đạt $M_D / M_L = 1.80$, **tổng mômen tĩnh tải $M_D$ bắt buộc phải giảm tới $67.273\%$** (tức tổng tự trọng chỉ còn lại $32.727\%$ so với baseline).

4. **Trường hợp 3 — Tác động thực tế khi CHỈ GIẢM 60% RIÊNG DIỆN TÍCH BẢN BỤNG ($A_{web}$):**
   Tự trọng kết cấu nhịp cầu dầm hộp bao gồm nhiều thành phần: bản mặt cầu trên, bản đáy, bản bụng, lớp phủ mặt cầu, lan can, dải phân cách, gờ neo, vách ngăn và hệ thống dự ứng lực.
   Do bản bụng chỉ đóng góp một phần trong tổng tự trọng, việc giảm $60\%$ diện tích bản bụng đơn thuần sẽ chỉ làm giảm tổng mômen tĩnh tải một tỷ lệ nhỏ hơn đáng kể so với $60\%$. Do đó, việc giảm riêng bản bụng chắc chắn không đủ để đưa $M_D / M_L$ về $2.20$, càng không thể đạt $1.80$.

```
+----------------------------------------------------------------------------------------------------+
|                         BIỂU ĐỒ ĐỐI CHIẾU CÁC MỨC CHUYỂN DỊCH TỶ SỐ M_D / M_L                      |
+----------------------------------------------------------------------------------------------------+
| BASELINE THAM CHIẾU:                                   [ M_D / M_L = 5.50 ]                        |
|                                                                                                    |
| Kịch bản A: Chỉ giảm riêng bản bụng (A_web) ----------> [ M_D / M_L > 2.20 ] (Giảm < 60% tổng M_D) |
|                                                                                                    |
| Kịch bản B: Giảm 60% toàn bộ tĩnh tải (A_total) ------> [ M_D / M_L = 2.20 ] (Giảm đúng 60% M_D)  |
|                                                                                                    |
| Kịch bản C: Đạt mục tiêu đề tài ----------------------> [ M_D / M_L = 1.80 ] (Phải giảm 67.273% M_D|
+----------------------------------------------------------------------------------------------------+
```

### 2.2. Giải trình Điều kiện Bắt buộc đối với Giả thuyết $M_D / M_L = 1.80$

Từ phép kiểm tra đại số trên, để mục tiêu $M_D / M_L = 1.80$ không bị bác bỏ ngay từ bước sàng lọc ban đầu, nhóm nghiên cứu bắt buộc phải giải trình các cơ chế phối hợp (chưa chứng minh, chỉ ở mức giả thuyết F0 IDEA):
1. Giảm tự trọng đồng bộ trên toàn bộ các bộ phận của kết cấu nhịp (bản mặt cầu, bản đáy, phụ kiện) chứ không chỉ riêng bản bụng.
2. Ứng dụng vật liệu mật độ thấp (như CFRP thay thế thép DƯL) cho các cấu kiện chịu kéo.
3. Thay đổi cơ chế truyền lực hoặc đường ảnh hưởng nội lực (ví dụ thành phần lực đẩy vòm Catenary tự cân bằng một phần tải trọng) để giảm mômen uốn tác dụng tại tiết diện kiểm tra.

---

## 3. Định nghĩa Tường minh Các Metric Nghiên cứu ($R_A$, $R_K$, $R_M$)

Các chỉ tiêu dưới đây được định nghĩa thuần túy phục vụ công tác nghiên cứu và kiểm tra tính nhất quán toán học, không phải là tiêu chuẩn nghiệm thu công trình:

### 3.1. Nhóm Chỉ tiêu Diện tích và Khối lượng ($R_A$)
Bắt buộc phải phân tách rõ ràng 3 tỷ số:

1. **Tỷ số diện tích / thể tích bản bụng ($R_{A,web}$ và $R_{V,web}$):**
   - Tỷ số diện tích bản bụng cục bộ tại tọa độ $x$:
     $$R_{A,web}(x) = \frac{A_{web,candidate}(x)}{A_{web,baseline}(x)}$$
   - Tỷ số thể tích / lượng vật liệu bản bụng tích phân trên toàn bộ chiều dài nhịp:
     $$R_{V,web} = \frac{\int_L A_{web,candidate}(x) \, dx}{\int_L A_{web,baseline}(x) \, dx}$$
2. **Tỷ số tổng khối lượng kết cấu nhịp ($R_{M,mass}$):**
   $$R_{M,mass} = \frac{M_{total,candidate}}{M_{total,baseline}} = \frac{\int_L \rho_{cand}(x) A_{total,cand}(x) \, dx}{\int_L \rho_{base}(x) A_{total,base}(x) \, dx}$$
3. **Tỷ số mômen tĩnh tải ($R_{M,dead}$):**
   $$R_{M,dead}(x) = \frac{M_{D,candidate}(x)}{M_{D,baseline}(x)}$$

### 3.2. Chỉ tiêu Độ cứng Cắt Tương đương theo Năng lượng Biến dạng ($R_K$)
Độ cứng cắt của mạng giàn rỗng Michell không thể biểu diễn bằng một đại lượng vô hướng (scalar) duy nhất. Đại lượng $R_K$ được định nghĩa là toán tử độ cứng cắt tương đương theo hướng tải và dải tải:

1. **Độ cứng cắt tương đương phương đứng ($GA_{eq,y}$):**
   Phụ thuộc vào biên độ lực cắt đứng $\bar{V}_y$, góc nghiêng thanh giàn $\theta_{Michell}$, độ cứng uốn cục bộ của thanh và độ cứng xoay của nút liên kết ($K_{\theta,joint}$):
   $$R_{K,y}(\bar{V}_y) = \frac{GA_{eq,y}(\bar{V}_y)}{GA_{baseline,y}}$$
2. **Độ cứng cắt tương đương phương ngang ($GA_{eq,z}$):**
   Đặc trưng cho khả năng kháng lực cắt ngang do tải trọng gió:
   $$R_{K,z}(\bar{V}_z) = \frac{GA_{eq,z}(\bar{V}_z)}{GA_{baseline,z}}$$
3. **Độ cứng kháng xoắn và vênh ($GJ_{eq}, EI_{\omega}$):**
   Đặc trưng cho khả năng kháng xoắn thuần và xoắn vênh của mặt cắt giàn không gian.

### 3.3. Chỉ tiêu Tỷ số Mômen Tĩnh tải / Hoạt tải ($R_M$)
$$R_M(x) = \frac{M_D(x)}{M_L(x)}$$
- Yêu cầu bắt buộc: Phải so sánh tại cùng tọa độ tiết diện $x$, cùng quy ước dấu mômen (vùng mômen dương hoặc mômen âm) và trên cùng một cơ sở hoạt tải thiết kế.
- **Nguyên tắc xử lý điểm kỳ dị mẫu số gần 0 (Near-Zero Denominator Handling — TBD):**
  Tại các vị trí điểm uốn (inflection points) trên dầm liên tục nơi $M_L(x) \to 0$ hoặc $M_D(x) \to 0$, tỷ số $R_M(x)$ sẽ tiến tới vô cùng hoặc không xác định. Quy tắc xử lý: Không chia trực tiếp tại lân cận điểm đổi dấu; việc đánh giá tỷ số $R_M$ bắt buộc phải được thực hiện trên đường bao (envelope) tại các tiết diện đặc trưng (đỉnh trụ, giữa nhịp) hoặc đánh giá độc lập từng hàm nội lực $M_D(x)$ và $M_L(x)$.

---

## 4. Hiệu chỉnh Cơ học Kết cấu & Năng lượng Biến dạng

### 4.1. Hiệu chỉnh Công thức Năng lượng Biến dạng Cắt và Hệ số $\kappa$
Trong lý thuyết dầm Timoshenko:
1. Nếu $\kappa$ là **hệ số hiệu chỉnh cắt tiêu chuẩn (Timoshenko shear coefficient)** (với $\kappa \le 1$, ví dụ $\kappa = 5/6$ cho tiết diện chữ nhật đặc), công thức thế năng biến dạng cắt đúng theo cơ học kết cấu là:
   $$U_s = \int \frac{V(x)^2}{2 \, \kappa \, G \, A} \, dx$$
2. Dạng công thức $U_s = \int \frac{\kappa \, V(x)^2}{2 \, G \, A} \, dx$ chỉ có giá trị khi $\kappa$ được định nghĩa tường minh là **hệ số độ mềm cắt (shear compliance / flexibility multiplier)** $\kappa_{flex} = 1/\kappa_{Timoshenko} \ge 1$.

### 4.2. Nguyên lý Thế năng Toàn phần và Điều kiện Cân bằng
Trạng thái cân bằng của kết cấu xuất phát từ tính dừng của **thế năng toàn phần (Total Potential Energy $\Pi$)**, không thể dựa vào năng lượng biến dạng nội năng $U$ đơn thuần:
$$\Pi = U - W \implies \delta \Pi = \delta U - \delta W = 0$$
Trong đó:
- $U$: Tổng nội năng biến dạng đàn hồi (bao gồm uốn, cắt, kéo nén dọc trục và biến dạng nút).
- $W$: Công của ngoại lực tác dụng.

### 4.3. Danh mục Các Kiểm tra Cơ học Còn thiếu trong Mô hình Đơn giản hóa (Missing Mechanics Checks)

Mô hình giải tích sơ bộ hiện tại chưa bao gồm các hiệu ứng cơ học phức tạp sau; toàn bộ danh mục này phải được giải quyết tại các cấp độ mô hình cao hơn (L2/L3):
1. **Lực dọc trục $N$ và hiệu ứng $P-\Delta$ / Độ cứng hình học ($K_g$):** Ảnh hưởng của lực dọc nén lớn đến độ võng thứ cấp và mất ổn định uốn.
2. **Uốn hai trục đồng thời ($M_y, M_z$):** Tác động kết hợp của tải trọng thẳng đứng và tải trọng gió ngang.
3. **Xoắn thuần St. Venant, Xoắn vênh ($B, T_{\omega}$) và Biến dạng méo hình mặt cắt (Distortion):** Khung giàn hở có độ cứng kháng méo hình thấp hơn nhiều so với dầm hộp đặc kín.
4. **Độ mềm xoay của nút liên kết ($K_{\theta,joint}$):** Sự mềm của liên kết làm giảm độ cứng cắt tương đương và tăng chuyển vị công trình.
5. **Mất ổn định cục bộ của thanh giàn (Local Member Buckling):** Nguy cơ mất ổn định nén của từng thanh giàn Michell mảnh.
6. **Phi tuyến vật liệu và hiện tượng chùng cáp (Cable Slackening):** Cáp CFRP không chịu được lực nén khi xảy ra đổi dấu ứng suất dưới hoạt tải lệch tâm.
7. **Mô hình hóa giai đoạn thi công theo thời gian (Staged Construction):** Ảnh hưởng của từ biến, co ngót, mất mát ứng suất trước và trình tự lắp dựng từng phân đoạn.
8. **Động học gió và rủi ro khí đàn hồi (Aeroelastic Hazards):** Nguy cơ mất ổn định flutter, buffeting và hiện tượng xoáy vortex ở nhịp lớn $480\text{ m}$.
9. **Mỏi và suy giảm độ bền môi trường dài hạn:** Đứt mỏi đầu neo và suy thoái tiếp giáp sợi/nhựa dưới tải trọng chu kỳ.

---

## 5. Pre-Registration: Ngưỡng Bác bỏ Giả thuyết (Falsification Thresholds) & Quy tắc Dừng

Ba chỉ tiêu nghiên cứu từ đề tài được đăng ký trước (pre-registered) dưới dạng **NGƯỠNG BÁC BỎ (FALSIFICATION TARGETS)**, tuyệt đối không phải tiêu chí nghiệm thu hay điều kiện PASS:

### 5.1. Bảng Đăng ký Trước Ngưỡng Bác bỏ Giả thuyết

```
+====================================================================================================+
|                               BẢNG ĐĂNG KÝ TRƯỚC NGƯỠNG BÁC BỎ GIẢ THUYẾT                          |
+====================================================================================================+
| MÃ TIÊU CHÍ | ĐẠI LƯỢNG KIỂM TRA           | MỤC TIÊU ĐĂNG KÝ   | ĐIỀU KIỆN BÁC BỎ GIẢ THUYẾT      |
|             |                              | (PRE-REGISTERED)   | (FALSIFIED IF VIOLATED)          |
+-------------+------------------------------+--------------------+----------------------------------+
| FAL-TGT-01  | Tỷ số thể tích bản bụng      | R_V,web <= 0.40    | Bị bác bỏ nếu mô hình chi tiết   |
|             | (Candidate / Baseline)       | (Giảm >= 60%)      | có R_V,web > 0.40                |
+-------------+------------------------------+--------------------+----------------------------------+
| FAL-TGT-02  | Tỷ số độ cứng cắt tương đương| R_K,y >= 0.85      | Bị bác bỏ nếu phân tích năng     |
|             | (Phương đứng qua RVE)        | (Độ cứng >= 85%)   | lượng RVE cho ra R_K,y < 0.85    |
+-------------+------------------------------+--------------------+----------------------------------+
| FAL-TGT-03  | Tỷ số mômen tĩnh / hoạt tải  | R_M = 1.80         | Bị bác bỏ nếu sau khi bóc tách   |
|             | (Tiết diện đỉnh trụ)         | (Từ baseline 5.50) | đầy đủ BOM mà R_M không đạt 1.80 |
+====================================================================================================+
```

### 5.2. Quy tắc Dừng và Không Kết luận Bắt buộc (Mandatory STOP / INCONCLUSIVE Rules)

Bất kỳ trường hợp nào dưới đây xuất hiện trong quá trình tính toán đều bắt buộc phải ghi nhận trạng thái **STOP** hoặc **INCONCLUSIVE**, không được công bố kết quả:
1. **Thiếu dữ liệu Gate G0:** Chưa xác định rõ mô hình tải trọng, điều kiện biên hoặc tiêu chuẩn thiết kế áp dụng.
2. **Không hội tụ số học (Non-convergence):** Solver không hội tụ hoặc cảnh báo lỗi chia cho 0.
3. **Lỗi thứ nguyên hoặc mất cân bằng tĩnh học:** Không thỏa mãn điều kiện cân bằng thế năng $\delta \Pi = 0$ hoặc sai lệch phản lực gối.
4. **Thuộc tính vật liệu không có xuất xứ (Unsupported Properties):** Tự ý gán cường độ CFRP hoặc UHPC mà không có báo cáo thử nghiệm Gate G6.
5. **Thay đổi cơ sở tải trọng (Changed Load Basis):** Thay đổi đường ảnh hưởng hoặc mô hình hoạt tải giữa Baseline và Candidate mà không giải trình.

---

## 6. Xuất xứ Vật liệu & Ràng buộc CFRP theo Gate G6

1. **Trạng thái Dữ liệu Vật liệu Hiện tại:**
   - Trong brief `RND-20260821-b471879e`, **chưa có bất kỳ báo cáo thử nghiệm hay chứng chỉ xuất xứ nào** cho vật liệu CFRP hay UHPC.
   - Do đó, toàn bộ đặc tính cơ lý chi tiết của vật liệu được phân loại là **`TBD_G6_REQUIRED / UNVERIFIED`**.
2. **Nguyên tắc Ràng buộc Ứng suất Thiết kế CFRP ($\sigma_{CFRP}$):**
   - Ứng suất tính toán của CFRP $\sigma_{CFRP}$ bắt buộc phải là **ứng suất thiết kế cho phép (design allowable)** được suy dẫn từ các tiêu chuẩn thiết kế chuyên ngành FRP (xét đến giới hạn dão-phá hủy, suy giảm môi trường và hiệu suất đầu neo).
   - Tuyệt đối cấm sử dụng cường độ kéo danh định chưa qua kiểm chứng trong các phân tích kết cấu.

---
*Tài liệu được khởi tạo và kiểm toán bởi Antigravity Evidence & Safety Auditor. Toàn bộ nội dung tuân thủ nghiêm ngặt Giao thức MARP-1.0 và Bộ cổng Vật lý PHYSICS_GATES.md (PG-1.0). Trạng thái Cổng G0: PENDING; Cấp độ Claim: F0 IDEA.*
