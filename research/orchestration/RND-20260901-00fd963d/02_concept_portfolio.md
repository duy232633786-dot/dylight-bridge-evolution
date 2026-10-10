# F0 — Concept portfolio Hybrid Grand Bridge (4 cơ chế khác nhau)

**Task:** `RND-00fd963d-02` — workstream `geometry`, owner `claude`, role `form_inventor`.
**Brief:** `RND-20260901-00fd963d`. **Run:** `RUN-20260901-00fd963d`.
**Amendment áp dụng:** `AMD-acc47bcbe2a7496b`
(`multiagent/amendments/RND-00fd963d-02.amendment.r001.json`) — `required_gates`
đổi từ `["G1"]` → `[]`; task được re-scope thành **portfolio F0/IDEA**.

## 0. Trạng thái phát hành và ranh giới

| Mục | Giá trị |
|---|---|
| Fidelity | **F0 (IDEA)** — topology + giả thuyết đường lực. Không có claim kỹ thuật. |
| Claim level của tài liệu | `IDEA` (trần brief `SCREENED`, trần dự án `SCREENED`) |
| `G0` | **FAIL / STOP_FOR_ENGINEERING_CLAIMS** — kế thừa `01_design_basis_and_evidence.md` §10, §19. Không được lật ở đây. |
| `G1` (Geometry & reality) | **NOT_EVALUATED / NOT_CLAIMED** — xem §11.1 |
| `G2`…`G7` | `NOT_EVALUATED` — không solver, không vật liệu, không thí nghiệm |
| Engineering use | `PROHIBITED` |
| Ngân sách solver đã tiêu | **0** (không có solver hợp lệ cho họ kết cấu này — `E-01`, `E-02`) |

**Tài liệu này KHÔNG chứa và KHÔNG được phép chứa:** nội lực, ứng suất, utilization,
sức kháng, hệ số an toàn, tần số dao động, vận tốc flutter, chuyển vị, cường độ vật
liệu, tải trọng thiết kế, chi phí, carbon, tuyên bố "đủ khả năng", "an toàn",
"đã kiểm ổn định", "world-first", `BUILD_READY` hay `TECHNICAL_RELEASE`.

**Ba nguồn hình ảnh/ý tưởng dùng ở đây đều là `IDEA`:**
`project_knowledge/hybrid-grand-bridge/Hybrid Grand Bridge Final Concept v1.7.png` và
`00 - Hybrid Grand Bridge Research Program.md` là **lịch sử concept do người dùng viết
và design seed**, **không** phải bằng chứng chịu lực (`multiagent/PHYSICS_GATES.md`:
"AI, NotebookLM và hình render chỉ sinh giả thuyết"; đối chiếu tiền lệ
`bridge_grammar/experimental/arch_deck_v1.json` → `image_provenance.engineering_evidence_value = NONE`).

**Ranh giới lineage (bắt buộc, kế thừa §16 của `01_...md`):** **không** giá trị nào của
đề bài đồ án PSC 45+75+45 m (`AF-*`, `AA-*`) được dùng trong tài liệu này. Portfolio
này thuộc lineage **hybrid 650 m**. Không có `AF-*`/`AA-*` nào xuất hiện dưới đây.

**Quy ước nhãn trạng thái dùng xuyên suốt:**

| Nhãn | Nghĩa |
|---|---|
| `DESIGN_SEED_UNVERIFIED` | Con số/ý định do người đặt đề bài nêu trong concept history; chưa xác minh, chỉ để tham số hóa |
| `HYPOTHESIS` | Phát biểu do agent suy ra bằng tĩnh học tay/lập luận topology; **chưa** kiểm bằng bất kỳ mô hình nào |
| `NOT_EVALUATED` | Có thể phát biểu câu hỏi, **không** có phương tiện trả lời (thiếu solver/dữ liệu). Không bao giờ ánh xạ thành `PASS` |
| `MISSING` | Bộ phận/dữ liệu/đường lực **không tồn tại** trong topology hoặc trong repo |

---

## 1. Sổ hạt giống thiết kế (design seed) — đọc từ concept history

Chỉ những giá trị **do người dùng nêu tường minh** mới được mang vào. Tất cả mang nhãn
`DESIGN_SEED_UNVERIFIED`. Không giá trị nào dưới đây được dùng làm design basis, làm căn
cứ sức kháng, hay làm đầu vào tính toán.

| ID | Seed | Ký hiệu | Nguồn | Độ tin đọc |
|---|---|---|---|---|
| `S-01` | Nhịp giữa treo `650 m` | `L_MS` | brief; render v1.7; program §v1.1 | cao (khớp 3 nguồn) |
| `S-02` | Quạt dây văng **chỉ** phía đất liền | — | brief; render; program §v1.1 | cao |
| `S-03` | Một vòm CFST-UHPC trung tâm liên tục, hạ thấp, nhập tiếp tuyến vào nút chân tháp | `AC` | brief; render; program §v1.3/§v1.5/§v1.7 | cao |
| `S-04` | Hai nửa vòm biên CFST-UHPC, từ nút chân tháp cong lên nối nút gia cường dưới dầm nhịp biên gần mố | `AH-L/R` | brief; render; program §v1.7 | cao |
| `S-05` | Khổ thông thuyền `60 m` | `C_nav` | brief `constraints[2]`; render | trung bình — chưa có văn bản AHJ (`SM-02`) |
| `S-06` | Nhịp giữa **chỉ** dùng cáp chủ võng + dây treo đứng; **không** dây văng xiên phía trong tháp | `MS`,`HG` | program §v1.1 | cao |
| `S-07` | Tổng chiều dài `1490 m` (khai trong bảng render) | `L_tot` | render, bảng "PRELIMINARY DESIGN DATA" | trung bình — **xem `F-01`** |
| `S-08` | Nhịp biên `250 m` (each), nhịp chuyển tiếp `250 m` (each), nhịp dẫn `145 m` (each) | `L_SS`,`L_TR`,`L_AP` | render, bảng + chuỗi kích thước trên đỉnh hình | trung bình — **xem `F-01`** |
| `S-09` | Bề rộng mặt cầu `32 m` | `B_D` | render | trung bình |
| `S-10` | Chiều cao tháp `210 m` (khai "to pile cap") | `h_PY` | render | trung bình |
| `S-11` | Tuổi thọ thiết kế "120+ năm" | — | render | thấp — là **nguyện vọng** trên render; **không** đóng `SM-03` (design life vẫn `MISSING`) |
| `S-12` | Tiết diện hộp vòm `6,0 m × 3,5 m` | `b_a × d_a` | render, khung "ARCH SECTION (TYP.)" | thấp — đọc từ ảnh; là seed hình học, **không** phải kết quả thiết kế |
| `S-13` | Dầm hộp thép ba khoang khí động, lớp chạy UHPC, hành lang kiểm tra bên trong | `DK` | render; program §v0.4, §3 | cao (định tính) |
| `S-14` | Sườn xiên thép vĩnh cửu đỡ cánh hẫng ("permanent diagonal steel outriggers — static only") | `OR` | render; program §v0.6 | cao (định tính) |
| `S-15` | Giảm chấn nhớt chỉ điều khiển động, **không** chịu tải thường xuyên, liên kết chốt, thay được | `DP` | render; program §v0.6 | cao (định tính) |
| `S-16` | "Dedicated thrust block on competent ground" ở đầu đất liền của mỗi nửa vòm biên | `TB-L/R` | render | trung bình |
| `S-17` | Cọc xiên (raking piles) căn theo hợp lực xô tại bệ tháp | `FD` | render, khung "TOWER FOUNDATION DETAIL" | trung bình |

### 1.1 Kết quả kiểm số học trên chính seed set — `F-01`

Đây **không** phải tính toán kết cấu; đây là phép cộng trên các con số do render khai
báo, và nó là một `M-02`/`M-04` finding phải ghi lại.

- Chuỗi kích thước dọc đọc trên đỉnh hình: `145 + 250 + 650 + 250 + 145 = 1440 m`.
- Bảng dữ liệu khai `TOTAL LENGTH = 1490 m`.
- Bảng đồng thời khai **cả** `SIDE SPANS (EACH) = 250` **và** `TRANSITIONS (EACH) = 250`
  **và** `APPROACH SPANS (EACH) = 145`; nếu cả ba đều là nhịp riêng biệt thì
  `650 + 2·250 + 2·250 + 2·145 = 1940 m`.

**Kết luận `F-01`:** ba cách đọc cho `1440` / `1490` / `1940 m` — chuỗi nhịp dọc của
v1.7 **chưa khép về mặt số học**. Trạng thái: `MISSING` (sơ đồ nhịp dọc chính tắc).
Đây là đầu vào **P0** phải do người dùng chốt trước khi bất kỳ node table nào được sinh
(xem §10). Agent **không** tự chọn một trong ba giá trị.

> Cảnh báo đọc ảnh: `S-07`…`S-12` được agent đọc từ một ảnh raster. Sai số đọc là có
> thật và **bản thân nó là một unresolved item**. Không giá trị nào trong nhóm này được
> phép đi vào bất kỳ phép tính nào mà không được người dùng xác nhận lại.

---

## 2. Khung so sánh chung (áp dụng đồng nhất cho cả 4 concept)

So sánh chỉ hợp lệ khi cùng chỗ vượt, cùng khung tham số, cùng bộ trạng thái tải và
cùng bộ trạng thái thi công (`PROTOCOL.md` §Quy tắc nghiên cứu 2; `01_...md` §6.1).

### 2.1 Họ bộ phận (member families)

`MS` cáp chủ · `BS` đoạn cáp chủ sau tháp (backstay) · `HG` dây treo đứng ·
`ST-L/R` quạt dây văng phía đất liền · `DK` dầm/mặt cầu · `AC` vòm trung tâm ·
`AH-L/R` nửa vòm biên · `SP` cột/thanh treo khoang vòm · `PY` tháp ·
`TN` nút chân tháp tích hợp · `TB` khối chịu lực xô · `AN` mố neo cáp ·
`CATB` khối tổ hợp neo–chịu xô (chỉ HGB-B) · `BR` hệ giằng ngang/khung ngang ·
`OR` sườn xiên cánh hẫng · `DP` giảm chấn · `FD` móng/cọc.

### 2.2 Trạng thái tải bắt buộc mô tả (F0 — chỉ mô tả đường lực, không tính)

| ID | Trạng thái |
|---|---|
| `LC-DL` | Tĩnh tải toàn cầu (kể cả tĩnh tải giai đoạn 2) |
| `LC-LLs` | Hoạt tải đối xứng toàn nhịp |
| `LC-LLh` | Hoạt tải **nửa nhịp** (mẫu bất lợi cho hệ mềm và cho cân bằng dọc tháp) |
| `LC-WT` | Gió ngang + xoắn (kể cả mẫu gió lệch một nửa nhịp) |
| `LC-CS*` | Ít nhất một trạng thái thi công (mỗi concept nêu **trạng thái khống chế giả định** của mình) |

### 2.3 Bộ trạng thái thi công chung (schema, chưa phải kế hoạch)

`C0` móng + bệ · `C1` tháp hoàn chỉnh · `C2` lắp/đúc hẫng vòm (**consol — dấu nội lực
ngược với khai thác**, `E-05`) · `C3` hợp long vòm (**chuyển đổi sơ đồ**) · `C4` bơm/đổ
lõi CFST-UHPC (**đổi tiết diện chịu lực giữa chừng**) · `C5` catwalk + kéo cáp chủ ·
`C6` lắp dây treo + lắp block dầm · `C7` lắp và căng chỉnh quạt dây văng ·
`C8` tháo có kiểm soát hệ tạm · `C9` khai thác.

### 2.4 Tham số ký hiệu và không thứ nguyên dùng chung

| Ký hiệu | Định nghĩa | Ghi chú |
|---|---|---|
| `L_MS`, `L_SS`, `L_TR`, `L_AP` | Nhịp giữa / biên / chuyển tiếp / dẫn | `S-01`, `S-08` |
| `B_D`, `C_nav` | Bề rộng mặt cầu, khổ thông thuyền | `S-09`, `S-05` |
| `f_c`, `χ_c = f_c/L_MS` | Độ võng cáp chủ và tỷ số võng | `MISSING` |
| `h_PY`, `h_T = h_PY − z_DK` | Cao tháp; chiều cao tháp **trên** mặt cầu | `S-10`; `z_DK` `MISSING` |
| `L_a`, `f_a`, `r_a = L_a/f_a` | Khẩu độ, đường tên, tỷ số thoải của `AC` | `L_a ≠ L_MS` (tính giữa hai nút `TN`) |
| `μ = H_a/V_a = r_a/4` | Tỷ số lực xô / phản lực đứng của vòm parabol chịu tải phân bố đều | **suy ra**, `E-06`/`derivations.thrust_to_vertical_ratio` |
| `λ_gap = g/d_a` | Khe kỹ thuật vòm–đáy dầm chuẩn hóa theo chiều cao vòm | `g` `MISSING` |
| `ψ_a` | Phần tĩnh tải nhịp giữa đi qua `AC` (0 = vòm không chịu tĩnh tải sàn, 1 = vòm chịu toàn bộ) | **NOT_EVALUATED** — chỉ solver phi tuyến có staged construction mới trả lời |
| `κ_stiff = K_AC/K_MS` | Tỷ số độ cứng đứng vòm/hệ cáp tại tim nhịp | `NOT_EVALUATED` |
| `α_T` | Mất cân bằng dọc đỉnh tháp chuẩn hóa `= (ΣH_hướng nước − ΣH_hướng bờ)/ΣH_hướng nước` | Chỉ tiêu thiết kế; `NOT_EVALUATED` |
| `η_TN` | Lực ngang dư tại nút chân tháp chuẩn hóa `= |H_AC − H_AH|/H_AC` | Chỉ tiêu thiết kế; `NOT_EVALUATED` |
| `κ_CATB = H_AH/H_MS,anchor` | Mức triệt tiêu lẫn nhau trong khối tổ hợp (chỉ HGB-B) | `NOT_EVALUATED` |
| `n_s`, `θ_s,min…max`, `s_DK` | Số dây văng mỗi quạt, dải góc nghiêng, bước neo trên dầm | `MISSING` |
| `ρ_HG` | Bước dây treo | `MISSING` |

---

## 3. HGB-A — "v1.7 as drawn" (baseline truy vết ý định người dùng)

**Cơ chế chính (khai báo của concept):** hệ treo nhịp giữa **song song** với một vòm
CFST-UHPC hạ thấp; hai nửa vòm biên; quạt dây văng chỉ phía đất liền.
**Vai trò trong portfolio:** *baseline không được sửa*. Mọi concept khác chỉ có nghĩa
khi so được với A. Giữ nguyên ý định kiến trúc `S-01`…`S-04`, `S-06`.

### 3.1 Topology graph (đồ thị bộ phận)

```
AN? ──?── MS ══ saddle@PY ══ ST-L fan
                 │hangers HG
                 ▼
 AB-L ─ DK(AP) ─ DK(TR) ─ DK(SS) ─── TN-L ═══ DK(MS 650) ═══ TN-R ─── DK(SS) ─ ...
            │                        ║                        ║
            └── node AH-L/DK ──AH-L──╝                        ╚──AH-R── node AH-R/DK
                     │                                                      │
                    TB-L                            AC (650-ish, hạ thấp) ──┘
                     │                    TN-L ═════════ AC ═════════ TN-R
                    FD                                   │
                                                     (không tựa đất giữa nhịp)
```

Cạnh (edge list, rút gọn): `HG:(MS→DK)`, `MS:(TN-L…TN-R qua saddle PY)`,
`ST:(PY_top→DK trong TR/SS)`, `AC:(TN-L→TN-R)`, `AH:(TN→node AH/DK gần mố)`,
`TB:(node AH/DK→FD)` — **lưu ý** `TB` trong render nằm ở **mặt đất dưới mố**, còn đầu
vòm biên nối vào **nút dưới dầm**; hai điểm này không trùng nhau (xem `A-FH-05`).

### 3.2 Text elevation

Từ trái sang: mố `AB-L` → nhịp dẫn UHPC composite → nhịp chuyển tiếp thép–UHPC →
tháp `PY-L` cao `h_PY` với nút chân tháp `TN-L` tích hợp → nhịp giữa `L_MS` treo bằng
`MS + HG` → `PY-R`/`TN-R` → gương đối xứng. Dưới dầm nhịp giữa: **một** vòm hộp
CFST-UHPC liên tục, hạ thấp, có khe kỹ thuật `g` với đáy dầm, hai đầu nhập **tiếp
tuyến** vào `TN`. Từ mỗi `TN` một nửa vòm cong lên phía bờ, kết thúc tại nút gia cường
dưới dầm nhịp biên gần mố. Quạt dây văng chỉ ở hai đoạn phía bờ.

### 3.3 Đường lực (primary / secondary) — tất cả là `HYPOTHESIS`

| Trạng thái | Đường chính (giả thuyết) | Đường phụ (giả thuyết) | Điểm chưa giải |
|---|---|---|---|
| `LC-DL` | Sàn → `DK` (uốn cục bộ) → `HG` (kéo) → `MS` (kéo) → yên tháp → `PY` (nén) → `TN` → `FD` | `AC` nhận một phần `ψ_a` **nếu và chỉ nếu** có liên kết đứng vòm–dầm; render vẽ **khe kỹ thuật** ⇒ `ψ_a` phụ thuộc chi tiết chưa có | `ψ_a` = `NOT_EVALUATED`; thành phần ngang của `MS` = **`MISSING`** (§3.4) |
| `LC-LLs` | như `LC-DL` | `AC` + `AH` tăng độ cứng tổng thể (nếu có liên kết) | phân phối `MS`↔`AC` = `NOT_EVALUATED` |
| `LC-LLh` | `MS` đổi dạng (hệ mềm chịu lực bằng **thay đổi hình dạng**) → `DK` uốn dọc lớn | `AC` **cứng**, chống lại chính chuyển vị đó ⇒ **cạnh tranh độ cứng** | `FC-03`; phản lực giao diện vòm–dầm có thể **đổi dấu** ⇒ đòi gối chịu nhổ chưa có trong topology |
| `LC-WT` | Gió ngang → `DK` (hộp kín, xoắn) → `BR`/`OR` → `TN`/`PY` | `AC` đơn (một sườn trên tim cầu) ⇒ **toàn bộ mô men xoắn chạy xuống một sườn** (đối chiếu `arch_rib_count = 1` note) | ổn định ngoài mặt phẳng của `AC` = `NOT_EVALUATED` (`ARCH_RIB_STABILITY = ABSENT`) |
| `LC-CS2` (**khống chế giả định**) | `C2` lắp hẫng vòm 650 m: hai consol CFST rỗng, **thớ trên kéo**, làm việc bằng **uốn** — ngược dấu hoàn toàn với `C9` | hệ tháp khóa + cáp khóa/neo tạm | `E-05`; `STAGED_PRESTRESS_EFFECTS = ABSENT` ⇒ `NOT_EVALUATED` |

### 3.4 Bốn tuyến khép lực bắt buộc

| # | Lực | Tuyến trong HGB-A | Trạng thái |
|---|---|---|---|
| 1 | **Thành phần ngang cáp chủ `H_MS`** | Render **không** vẽ mố neo, **không** khai tự neo. Ba tuyến ứng viên: `A-r1` mố neo trong đất/đá (bộ phận `AN` **không tồn tại** trong topology); `A-r2` tự neo — `H_MS` vào `DK` dưới dạng **nén dọc** chạy suốt nhịp chuyển tiếp/nhịp biên (đòi dầm liên tục, không khe, đủ ổn định nén); `A-r3` cân bằng tại đỉnh tháp với quạt dây văng — chỉ đúng nếu `α_T = 0` ở **mọi** tổ hợp, điều không thể với `LC-LLh` | **`MISSING`** — đây là `unresolved_equilibrium_count ≥ 1`, chính là `FC-01` |
| 2 | **Lực quạt dây văng** | `ST` (kéo) → neo đỉnh tháp → `PY` (nén dọc) → `TN` → `FD`; thành phần ngang kéo tháp **về phía bờ**, chỉ cân bằng được bởi thành phần hướng nước của `MS`; phần dư → **uốn tháp** | `HYPOTHESIS`; dư `α_T` ở `LC-LLh` = `NOT_EVALUATED`; chính là `FC-02` |
| 3 | **Lực xô vòm trung tâm `H_AC`** | `AC` → nhập tiếp tuyến `TN` → bệ tháp → cọc đứng + **cọc xiên căn theo hợp lực** (`S-17`) → nền | `HYPOTHESIS`. Render khai "BALANCED FOUNDATION THRUST" — nhưng cân bằng chỉ đạt khi `η_TN → 0`, tức `H_AC ≈ H_AH` tại cùng cao độ và cùng phương. Chưa có hình học để kiểm ⇒ `NOT_EVALUATED` |
| 4 | **Lực xô nửa vòm biên `H_AH`** | `AH` → **nút dưới dầm nhịp biên gần mố** → ? → `TB` trên nền tốt | **PARTIAL**. Render vẽ `TB` ở mặt đất nhưng đầu vòm biên kết thúc ở **nút trên dầm**. Nếu lực xô phải đi qua đoạn dầm/gối trước khi tới `TB` thì có **phần tử mềm mắc nối tiếp trong đường lực xô chính** — đúng điều kiện bác bỏ `FC-05` |

### 3.5 Vai trò riêng của từng họ bộ phận + phép thử gỡ bỏ

| Họ | Vai trò tuyên bố | Phép thử gỡ bỏ (F0: topology còn khép lực không?) | Kết luận F0 |
|---|---|---|---|
| `MS`+`HG` | Chịu phần lớn tĩnh tải + hoạt tải nhịp giữa | Gỡ `MS` ⇒ nhịp 650 m chỉ còn `AC`; `AC` đơn sườn không có hệ treo/cột nối lên dầm (render vẽ **khe**) ⇒ **không khép** | Vai trò **riêng biệt**, `HYPOTHESIS` |
| `ST` | Đỡ nhịp biên + cân bằng dọc tháp | Gỡ `ST` ⇒ nhịp biên mất đỡ **và** `α_T` tăng vọt (không còn lực kéo về bờ) | Vai trò **kép, riêng biệt**, `HYPOTHESIS` |
| `AC` | "Assumed to carry all main-span loads" (nguyên văn render) — **mâu thuẫn** với `S-06` ("nhịp giữa chỉ dùng cáp chủ + dây treo") | Gỡ `AC` ⇒ nếu `ψ_a ≈ 0` (có khe, không liên kết đứng) thì hệ **vẫn khép lực** ⇒ `AC` là **ứng viên roleless** | **XUNG ĐỘT KHAI BÁO** — `A-FH-06`. Trạng thái: `NOT_EVALUATED`, và là câu hỏi F0 quan trọng nhất của HGB-A |
| `AH` | Truyền nén từ dầm nhịp biên vào tháp | Gỡ `AH` ⇒ nhịp biên vẫn có `ST` + trụ; hệ có thể vẫn khép ⇒ **ứng viên roleless** trừ khi `AH` là bộ phận **cân bằng `H_AC`** tại `TN` | Vai trò **có điều kiện**: chỉ riêng biệt nếu `η_TN` phụ thuộc `AH`. `NOT_EVALUATED` |
| `OR`,`DP`,`BR` | Sườn xiên tĩnh; giảm chấn **chỉ động**; giằng ngang | Gỡ `DP` ⇒ đường lực tĩnh **không đổi** (theo `S-15`) — đúng thiết kế, không phải roleless | Vai trò riêng biệt (khác miền tần số), `HYPOTHESIS` |

### 3.6 Chế tạo / lắp dựng / kiểm tra / thay thế

- **Giả thuyết chế tạo:** `AC`/`AH` = hộp thép kín chế tạo phân đoạn tại xưởng, hàn/bulông tại chỗ, **bơm lõi UHPC sau khi hợp long** (`C4`) ⇒ tiết diện chịu lực **đổi giữa chừng**. `DK` = block hộp thép ba khoang lắp bằng cẩu nổi/gantry sau khi có `MS`+`HG`.
- **Trình tự giả thuyết:** `C0→C1→C2→C3→C4→C5→C6→C7→C8→C9`. Render đề xuất đúng thứ tự này (khung "CONSTRUCTION SEQUENCE"), tức **vòm được xây trước cáp chủ**. Hệ quả: `C2` (consol vòm 650 m trên luồng thông thuyền) là trạng thái khống chế giả định.
- **Tiếp cận kiểm tra:** hành lang trong hộp `DK` (`S-13`); hành lang trong hộp vòm (render khai "INSPECTION / ACCESS CORRIDOR"); sàn thao tác tại yên tháp và tại neo dây văng.
- **Thay thế:** `HG`, `ST`, `DP`, gối = thay được theo tuyên bố concept. **`MS`, `AC`, `AH`, nút `TN` = KHÔNG thay được** ⇒ chúng phải đạt tuổi thọ toàn công trình. Đây là ràng buộc thiết kế, không phải kết luận độ bền.
- **Trạng thái:** toàn bộ mục này `HYPOTHESIS`; không có FAB rule nào của runtime áp được (§11.1).

### 3.7 Giả thuyết phá hoại (≥5) — tất cả `NOT_EVALUATED`

| ID | Giả thuyết phá hoại | Ánh xạ `01_...md` |
|---|---|---|
| `A-FH-01` | **Mất cân bằng dọc tháp:** quạt dây văng chỉ một phía + `H_MS` chưa có tuyến khép ⇒ cơ chế cân bằng duy nhất còn lại là **uốn tháp**; tháp 210 m biến từ cấu kiện trục thành cấu kiện uốn; `LC-LLh` là mẫu khống chế | `FC-02` |
| `A-FH-02` | **Ổn định vòm trong/ngoài mặt phẳng:** `AC` một sườn, khẩu độ bậc 650 m, không có sườn thứ hai để giằng ⇒ oằn ngoài mặt phẳng là trạng thái giới hạn khống chế nghi vấn; ở `C2` (consol rỗng chưa bơm lõi) còn bất lợi hơn | `FC-08`, `ARCH-NEED-01/02` |
| `A-FH-03` | **Cạnh tranh độ cứng cáp/dầm/vòm:** hệ mềm (`MS`) và hệ cứng (`AC`) mắc **song song** vào cùng `DK`; `LC-LLh` gây chuyển vị cưỡng bức lên `AC`; phản lực giao diện có thể đổi dấu (đòi gối chịu nhổ **chưa có**) | `FC-03` |
| `A-FH-04` | **Mỏi nút dầm–vòm:** nút `AH`/`DK` gần mố và nút `TN` nằm trong đường lực **chính**, chịu đảo dấu theo mỗi lượt xe và theo nhiệt độ; là nút liên hợp thép–UHPC; thư viện repo **không có** nguồn mỏi chi tiết thép (`N-02`, `ARCH-NEED-08`) | `FC-10` |
| `A-FH-05` | **Đường lực xô có phần tử mềm nối tiếp:** đầu vòm biên vào **nút trên dầm**, còn `TB` ở **mặt đất** ⇒ nếu tuyến đi qua dầm/gối thì vi phạm nguyên tắc "lực xô đi vào nền bằng đường **cứng và ngắn**" | `FC-05` |
| `A-FH-06` | **Xâm phạm khổ thông thuyền:** khổ `C_nav = 60 m` phải đo tới **cấu kiện thấp nhất** trong bề rộng luồng. Với vòm **hạ dưới dầm**, cấu kiện thấp nhất tại vùng giữa nhịp là **đỉnh vòm**, không phải đáy dầm. Render khai "60 m clearance maintained" nhưng cao độ đỉnh vòm, cao độ đáy dầm và MNTK đều `MISSING` | `M-05`, `SM-02` |
| `A-FH-07` | **Xung đột khai báo vai trò:** render ghi vòm "assumed to carry all main-span loads" trong khi program §v1.1 ghi nhịp giữa "chỉ dùng dây chủ võng và dây treo đứng". Hai phát biểu **loại trừ nhau**; không thể cùng đúng | `FC-04`, `M-03` |
| `A-FH-08` | **Khí động đàn hồi:** nhịp treo 650 m rơi thẳng vào nhóm "nhạy gió" theo tiêu chí đề xuất trong `LIT-089`; thêm một vòm hạ thấp dưới dầm làm đổi hoàn toàn dòng khí quanh mặt cắt so với hộp khí động đơn thuần | `FC-07` |

### 3.8 Điều gì **bác bỏ HGB-A ngay tại F0** / cần gì ở F1+

**Bác bỏ tại F0 (không cần solver):** (a) người dùng xác nhận **không** có mố neo và
**không** chấp nhận dầm chịu nén tự neo ⇒ `H_MS` vĩnh viễn không khép ⇒ topology bị bác
bỏ; (b) sơ đồ nhịp dọc không đóng được (`F-01` không giải được); (c) hình học chốt cho
thấy đỉnh vòm cắt vào hộp khổ thông thuyền được AHJ phê duyệt.
**Cần ở F1+:** sơ đồ nhịp chính tắc + cao độ (`P0-10`); mô hình cân bằng nút đỉnh tháp
và nút `TN` cho toàn bộ `C0…C9`; solver 3D phi tuyến hình học + staged construction +
oằn vành vòm (`SM-11`); dữ liệu gió + phân tích khí động (`P0-9`, `FC-07`).

---

## 4. HGB-B — "Cable-primary, force-closed" (giữ ngôn ngữ hình ảnh, tách vai trò)

**Tên đầy đủ:** *Cầu treo neo đất, khối tổ hợp neo–chịu xô ở đầu bờ, vòm trung tâm được
hạ cấp thành spine xoắn–khí động và giá lắp dựng.*

**Ý tưởng cơ chế (đây là điểm khác biệt thật sự, không phải đổi kích thước):**

1. `MS` chạy **liên tục qua yên tháp** và tiếp tục xuống bờ thành `BS`, kết thúc tại
   **khối `CATB`** đặt trên nền tốt phía đất liền.
2. **Cùng khối `CATB`** đó nhận **lực xô của nửa vòm biên `AH`**. Cáp kéo khối **về phía
   tim cầu**; vòm đẩy khối **ra phía bờ**. Hai lực **ngược chiều** ⇒ triệt tiêu một phần,
   đo bằng `κ_CATB = H_AH/H_MS,anchor`. Khối chỉ phải nhận **phần dư** `|1 − κ_CATB|`.
3. `AC` bị **hạ cấp có chủ ý**: liên kết vòm–dầm là **ngang cố định, dọc trượt, đứng tự
   do** ⇒ `ψ_a ≡ 0` **theo thiết kế**, không phải theo may rủi. Vòm giữ nguyên hình ảnh
   v1.7 nhưng **không** cạnh tranh độ cứng đứng với hệ cáp.
4. Cân bằng dọc đỉnh tháp trở thành **phương trình thiết kế** chứ không phải giả định:
   chọn góc `BS` sao cho `H_MS,inner − H_MS,back = H_ST,ngang` tại trạng thái tĩnh tải
   tham chiếu, tức `α_T(DL) = 0` theo cấu tạo.

### 4.1 Topology graph

```
CATB-L ══BS══ saddle@PY-L ══MS══(HG)══ saddle@PY-R ══BS══ CATB-R
   ║                │                        │               ║
   ║          ST-L fan│                 │ST-R fan             ║
   ║                ▼ ▼                 ▼ ▼                   ║
AB-L ─ DK(AP) ─ DK(TR) ─ DK(SS) ─ TN-L ══ DK(MS) ══ TN-R ─ DK(SS) ─ ...
   ║                                  ║           ║
   ╚═══════════ AH-L ═════════════════╝           ╚═══ AH-R ═══════ CATB-R
                                    AC: TN-L ═════╧═════ TN-R
                            (liên kết ngang-cố định / đứng-tự do với DK)
```

### 4.2 Text elevation

Giống HGB-A về ngôn ngữ hình ảnh (một vòm hạ thấp giữa hai chân tháp, hai nửa vòm biên
cong lên phía bờ, quạt dây văng chỉ phía đất liền), **khác ở ba chỗ nhìn thấy được**:
(i) cáp chủ **không dừng ở đỉnh tháp** mà tiếp tục xuống một khối neo lộ thiên trên bờ;
(ii) nửa vòm biên **kết thúc ở chính khối neo đó**, không kết thúc ở nút dưới dầm;
(iii) giữa vòm trung tâm và đáy dầm là các **liên kết ngang** (bộ chống lắc) thay vì
liên kết đỡ đứng.

### 4.3 Đường lực

| Trạng thái | Đường chính | Đường phụ | Ghi chú |
|---|---|---|---|
| `LC-DL` | `DK → HG → MS → yên → BS → CATB → nền` | `PY` nhận **thành phần đứng** của `MS`; `AC` chỉ mang trọng lượng bản thân | `ψ_a ≡ 0` theo cấu tạo ⇒ không còn ẩn số phân phối |
| `LC-LLs` | như trên | `ST` gánh phần nhịp biên | `α_T` lệch nhẹ |
| `LC-LLh` | `MS` đổi dạng; `DK` (hộp thép) cung cấp độ cứng uốn dọc | `AC` **không** chống lại chuyển vị đứng (liên kết đứng tự do) ⇒ **loại bỏ nguồn cạnh tranh chính** | Đây là lợi ích cơ học chính của B so với A. `HYPOTHESIS` |
| `LC-WT` | Gió ngang → `DK` → **liên kết ngang** → `AC` (làm dầm ngang cong rất cứng trong mặt phẳng ngang) → `TN` → `FD` | `BR`,`OR`,`DP` | `AC` được **gán một vai trò riêng biệt và duy nhất**: đường lực ngang/xoắn |
| `LC-CS2/CS5` (**khống chế giả định**) | `C2` consol vòm; **và** `C5` kéo cáp chủ khi `CATB` đã có sẵn (khối neo phải hoàn thành **trước** `C5`) | `AC` sau `C4` làm **giá lắp dựng và đường công vụ** cho `C6` | Trình tự có thứ tự bắt buộc: `CATB` trước `MS` |

### 4.4 Bốn tuyến khép lực

| # | Lực | Tuyến trong HGB-B | Trạng thái |
|---|---|---|---|
| 1 | `H_MS` | `MS → yên (truyền qua) → BS → CATB → nền tốt` — **khép, tường minh, có bộ phận nhận** | `HYPOTHESIS` (khép về topology; khả năng chịu của nền = `NOT_EVALUATED`, đòi `P0-7`) |
| 2 | `H_ST` | Cân bằng tại đỉnh tháp với hiệu `H_MS,inner − H_MS,back` theo **phương trình thiết kế** `α_T(DL) = 0`; dư ở `LC-LLh` → uốn tháp, bị chặn bởi chỉ tiêu `α_T,max` | `HYPOTHESIS` — vẫn cần solver để biết `α_T(LLh)` |
| 3 | `H_AC` | Nhỏ hơn hẳn A theo giả thuyết (vòm chỉ mang bản thân + gió) → `TN` → bệ → cọc xiên | `HYPOTHESIS`; `η_TN` giảm nhưng `NOT_EVALUATED` |
| 4 | `H_AH` | `AH → CATB` **trực tiếp**, không qua dầm ⇒ **đường cứng và ngắn**, và triệt tiêu một phần với lực neo cáp (`κ_CATB`) | `HYPOTHESIS` — đây là điểm sửa lỗi trực tiếp của `FC-05` |

### 4.5 Vai trò riêng + phép thử gỡ bỏ

| Họ | Vai trò **duy nhất** | Gỡ bỏ ⇒ |
|---|---|---|
| `MS`+`HG` | Toàn bộ tải trọng đứng nhịp giữa | Nhịp giữa **không còn hệ đỡ** (vòm không nối đứng) ⇒ sập cơ chế. Vai trò **duy nhất, chứng minh được ở F0** |
| `BS`+`CATB` | Khép `H_MS`; đồng thời khép `H_AH` | Gỡ ⇒ `H_MS` `MISSING` ngay lập tức. Vai trò **duy nhất** |
| `ST` | Đỡ nhịp biên + tinh chỉnh `α_T` | Gỡ ⇒ nhịp biên mất đỡ; `α_T` phải gánh hoàn toàn bằng hình học `BS` | 
| `AC` | **Chỉ** đường lực ngang/xoắn + giá lắp dựng `C6` + hành lang kỹ thuật | Gỡ `AC` ⇒ `LC-WT` mất một đường lực ngang **và** `C6` mất giá lắp ⇒ phải thay bằng cẩu nổi. Vai trò **riêng biệt nhưng cần chứng minh giá trị** (xem `B-FH-05`) |
| `AH` | **Chỉ** truyền lực nén nhịp biên xuống `CATB` và tạo thành phần triệt tiêu `κ_CATB` | Gỡ `AH` ⇒ `κ_CATB = 0` ⇒ `CATB` phải to hơn; nhịp biên phải dựa hoàn toàn `ST` + trụ. Vai trò **riêng biệt, định lượng được bằng `κ_CATB`** |

### 4.6 Chế tạo / lắp dựng / kiểm tra / thay thế

- `CATB` là hạng mục **bê tông khối lớn trên nền tốt**, đòi khảo sát địa chất tại đúng
  hai vị trí đó (`P0-7`) và đòi kiểm **trượt + lật + nhổ**; đây là **rủi ro dự án lớn
  nhất của B** và phải được nêu, không được giấu.
- Ưu điểm thi công: `AC` hoàn thành ở `C4` trở thành **kết cấu công vụ** cho `C5`/`C6`
  ⇒ giảm phụ thuộc cẩu nổi trên luồng 60 m.
- Kiểm tra: `CATB` cho phép **hành lang neo có thể vào được**, là điều kiện tiên quyết
  để kiểm tra cáp chủ theo thực hành neo đất (nguồn chưa lập chỉ mục — `N-02`, phải bổ
  sung trước F1).
- Thay thế: `HG`, `ST`, `DP`, gối, **và** liên kết ngang vòm–dầm đều thay được.
  `MS`, `AC`, `AH`, `CATB`, `TN` không thay được.

### 4.7 Giả thuyết phá hoại (≥5)

| ID | Giả thuyết |
|---|---|
| `B-FH-01` | **Mất cân bằng dọc tháp:** `α_T(DL) = 0` chỉ đúng ở **một** trạng thái tham chiếu; nhiệt độ, từ biến cáp, `LC-LLh` và trình tự căng chỉnh đều làm lệch. Nếu `α_T` khai thác vượt khả năng uốn tháp ⇒ bác bỏ |
| `B-FH-02` | **Ổn định vòm:** `AC` giờ nhẹ tải đứng nhưng vẫn là cấu kiện nén dài; ở `C2`/`C3` nó **vẫn** là consol 650 m. Trạng thái khống chế **chuyển hẳn sang giai đoạn thi công** |
| `B-FH-03` | **Cạnh tranh độ cứng "rò rỉ":** liên kết "đứng tự do" trong thực tế luôn có ma sát/độ cứng dư; nếu độ cứng dư đủ lớn, `ψ_a > 0` quay lại và toàn bộ lợi thế của B biến mất. **Đây là falsifier trung tâm của HGB-B** |
| `B-FH-04` | **Mỏi nút dầm–vòm / nút neo:** liên kết ngang vòm–dầm chịu **đảo dấu** theo mỗi chu kỳ gió và mỗi chuyển vị dọc do nhiệt; nút `CATB`–cáp là nút mỏi cao chu kỳ trong môi trường có thể ăn mòn |
| `B-FH-05` | **Vòm vẫn có thể là roleless:** nếu cùng chức năng ngang/xoắn đạt được bằng hệ giằng ngang thông thường rẻ hơn nhiều, thì `AC` là **chi phí kiến trúc**, không phải bộ phận chịu lực cần thiết. Phải so với HGB-D để trả lời |
| `B-FH-06` | **Xâm phạm khổ thông thuyền:** giống `A-FH-06` — vòm hạ thấp vẫn là cấu kiện thấp nhất giữa nhịp |
| `B-FH-07` | **Khối `CATB`:** nền không đủ sức kháng ngang/nhổ, hoặc `κ_CATB` thực tế gần 1 gây **đảo dấu** hợp lực trong khối theo tổ hợp tải (khối bị kéo trong tổ hợp này, bị đẩy trong tổ hợp kia) ⇒ bài toán neo hai chiều, khó hơn neo một chiều |
| `B-FH-08` | **Khí động:** như `A-FH-08`; thêm vấn đề rung cáp `BS` dài lộ thiên (mưa–gió trên dây) |

### 4.8 Bác bỏ tại F0 / cần gì ở F1+

**Bác bỏ tại F0:** (a) không tồn tại nền tốt trong tầm với ở hai đầu bờ để đặt `CATB`
(quyết định bằng khảo sát, `P0-7`); (b) người dùng bác bỏ khối neo lộ thiên vì lý do
kiến trúc/mặt bằng; (c) không thiết kế được liên kết vòm–dầm có `ψ_a ≈ 0` bền vững
(`B-FH-03`).
**Cần ở F1+:** địa kỹ thuật hai khối neo; mô hình phi tuyến có staged construction để
tính `α_T`, `κ_CATB`, `η_TN`; nghiên cứu chi tiết liên kết ngang–trượt dọc; khí động.

---

## 5. HGB-C — "Arch-primary / tied-arch" (cáp chỉ giữ vai trò phụ, tách bạch)

**Tên đầy đủ:** *Vòm CFST-UHPC liên tục là hệ chịu lực chính của nhịp giữa; dầm là
thanh căng khép lực xô; hệ cáp chỉ còn ba vai trò phụ tách bạch.*

Hai biến thể **khác cơ chế**, không phải khác kích thước:

- **C1 — vòm chạy trên hạ thấp (deck-arch):** vòm dưới dầm, tải xuống vòm qua **cột
  khoang chịu nén** `SP`. Giữ đúng ngôn ngữ hình ảnh v1.7.
- **C2 — vòm chạy giữa/chạy dưới (through-arch):** vòm **trên** mặt cầu, tải lên vòm
  qua **thanh treo chịu kéo** `HG`. Bảo vệ được hộp khổ thông thuyền nhưng **phá vỡ**
  ngôn ngữ hình ảnh v1.7.

Cáp được hạ cấp thành đúng ba vai trò **không chồng lấn**:
(i) `ST` quạt dây văng phía đất liền — **chỉ** đỡ nhịp biên + cân bằng dọc tháp;
(ii) cáp lắp dựng tạm được **giữ lại vĩnh viễn** làm đường dự phòng/tinh chỉnh, khóa ở
**mức lực bằng 0 ở trạng thái tĩnh tải sau hợp long** (vai trò: robustness, không phải
gánh tải); (iii) cáp gió nằm ngang ở cao độ mặt cầu — **chỉ** rút ngắn nhịp ngang của
dầm dưới `LC-WT`.

### 5.1 Topology graph (C1)

```
AB-L ─ DK(AP) ─ DK(TR) ─ DK(SS) ─ TN-L ══════ DK(MS) = THANH CĂNG ══════ TN-R ─ ...
                    │              ║   │ │ │ │ SP (cột nén) │ │ │        ║
                ST-L fan           ╚═════════ AC (vòm chính) ═══════════╝
                                   ║                                     ║
                                 AH-L ─ TB-L                          AH-R ─ TB-R
```

Trong C2, `SP` (cột nén) được thay bằng `HG` (thanh treo kéo) và `AC` nằm **trên** `DK`.

### 5.2 Đường lực

| Trạng thái | Đường chính | Đường phụ |
|---|---|---|
| `LC-DL` | `DK → SP (C1) / HG (C2) → AC (nén) → TN`; **thành phần ngang khép ngay trong `DK` dưới dạng kéo dọc (thanh căng)** ⇒ về nguyên tắc **không** truyền lực xô ngang xuống móng | `ST` gánh nhịp biên |
| `LC-LLs` | như trên; vòm gần trạng thái funicular | — |
| `LC-LLh` | **Uốn vành vòm** là hệ quả trực tiếp của tải nửa nhịp (đường áp lực rời khỏi trục vòm) ⇒ chiều cao tiết diện vòm bị chi phối bởi yêu cầu **giữ đường áp lực trong lõi**, không bởi cường độ nén | `DK` (thanh căng) chịu kéo + uốn đồng thời |
| `LC-WT` | Gió → `DK` → cáp gió nằm ngang + `BR` → `TN`; **oằn ngoài mặt phẳng của vòm là trạng thái giới hạn nghi vấn chính** | `DP` |
| `LC-CS2/CS3` (**khống chế giả định**) | Consol vòm 650 m ở `C2`, **hợp long `C3` là điểm chuyển đổi sơ đồ** (consol→vòm, đảo dấu), `C4` đổi tiết diện | Cáp tạm khóa ở `C8` về lực 0 |

### 5.3 Bốn tuyến khép lực

| # | Lực | Tuyến trong HGB-C |
|---|---|---|
| 1 | `H_MS` | **KHÔNG TỒN TẠI** — không có cáp chủ nhịp giữa. Đây vừa là ưu điểm cơ học (xóa hẳn `FC-01`) vừa là **xung đột ý định** với `S-01`/`S-06` |
| 2 | `H_ST` | `ST → đỉnh tháp → PY → TN`; **không còn `MS` kéo về phía nước để cân bằng** ⇒ cân bằng dọc tháp phải do **chính vòm** (đẩy về phía nước) đảm nhận, hoặc do backstay riêng. Đây là **ẩn số trung tâm của C** |
| 3 | `H_AC` | Khép **nội bộ** trong `DK` (tied arch) ⇒ móng chỉ nhận phản lực đứng. Điều kiện: `DK` liên tục, không khe trong phạm vi nhịp giữa, và **một điểm cố định dọc duy nhất** |
| 4 | `H_AH` | `AH → TB` trên nền tốt (đường cứng, ngắn) |

### 5.4 Vai trò riêng + phép thử gỡ bỏ

`AC` = hệ chính (gỡ ⇒ sập). `DK` = **kiêm hai vai trò: bản mặt cầu và thanh căng** (gỡ
vai trò thanh căng ⇒ lực xô 650 m rơi thẳng xuống móng, không có bộ phận nhận ⇒ không
khép). `SP`/`HG` = truyền tải sàn lên vòm (gỡ ⇒ không khép). `ST` = đỡ nhịp biên + cân
bằng tháp. Cáp tạm giữ lại = **chỉ** robustness/tinh chỉnh; nếu ở trạng thái tĩnh tải
lực khác 0 thì nó đã lẻn vào hệ chính và vi phạm nguyên tắc phân vai. Cáp gió ngang =
**chỉ** `LC-WT`.
**Kết quả F0:** HGB-C có `roleless_member_count` giả định **thấp nhất** trong bốn
concept — mỗi họ bộ phận có đúng một vai trò không thay thế được.

### 5.5 Chế tạo / lắp dựng / kiểm tra / thay thế

Lắp hẫng vòm bằng hệ cáp tạm + tháp khóa (`C2`), hợp long (`C3`), bơm lõi (`C4`), rồi
lắp `SP`/`HG` và các đốt dầm (`C6`), cuối cùng tháo/khóa hệ tạm (`C8`).
**Vấn đề thay thế nghiêm trọng:** thanh căng (`DK`) là bộ phận **không dư thừa** — mất
thanh căng là mất cơ chế. Với C, "replaceability" phải được thiết kế ở cấp **hệ**
(nhiều đường kéo song song, thay từng phần dưới tải) chứ không phải cấp cấu kiện.

### 5.6 Giả thuyết phá hoại (≥5)

| ID | Giả thuyết |
|---|---|
| `C-FH-01` | **Mất cân bằng dọc tháp:** không còn `MS` kéo tháp về phía nước; quạt dây văng một phía kéo tháp về bờ ⇒ tháp bị uốn thường xuyên trừ khi vòm cung cấp thành phần đẩy đúng bằng. Nghiêm trọng hơn HGB-A |
| `C-FH-02` | **Oằn vành vòm trong/ngoài mặt phẳng ở khẩu độ bậc 650 m** — trạng thái giới hạn khống chế nghi vấn; `ARCH_RIB_STABILITY = ABSENT` nên **không kiểm được trong repo này** |
| `C-FH-03` | **Cạnh tranh độ cứng dầm–vòm ngược chiều:** dầm vừa là thanh căng (kéo dọc) vừa là bản mặt cầu (uốn); nhiệt độ và từ biến làm đổi phân phối; `LC-LLh` gây uốn vòm lớn |
| `C-FH-04` | **Mỏi nút dầm–vòm** tại chân vòm và tại từng nút `SP`/`HG` — số lượng nút rất lớn, mỗi nút là chi tiết hàn liên hợp |
| `C-FH-05` | **Xâm phạm khổ thông thuyền:** **C1 gần như chắc chắn xung đột** — vòm dưới dầm ở giữa luồng. **C2 tránh được** nhưng đổi lấy việc mất ngôn ngữ hình ảnh và tăng diện cản gió trên cao |
| `C-FH-06` | **Robustness của thanh căng:** hỏng thanh căng = mất cơ chế; không có đường lực thứ hai |
| `C-FH-07` | **Trạng thái thi công:** consol vòm 650 m chưa bơm lõi, treo trên luồng, nhạy gió (`FALS-05`, `LIT-089`) |

### 5.7 Bác bỏ tại F0 / cần gì ở F1+

**Bác bỏ tại F0:** (a) người dùng khẳng định nhịp giữa **phải** là nhịp treo 650 m
(`S-01` + `S-06`) — khi đó **C bị bác bỏ vì mâu thuẫn ý định, không phải vì vật lý**;
(b) hộp khổ thông thuyền được AHJ chốt loại trừ cấu kiện dưới dầm (loại C1) hoặc giới
hạn chiều cao trên dầm (loại C2).
**Cần ở F1+:** phân tích oằn 3D + phi tuyến hình học; mô hình thanh căng có nhiệt/từ
biến; nghiên cứu robustness mất thanh căng; khí động.

---

## 6. HGB-D — "Control / reference" (một cơ chế chính duy nhất)

**Tên đầy đủ:** *Cầu treo neo đất cổ điển 650 m: cáp chủ + dây treo + dầm hộp thép cứng
+ hai mố neo; **không** vòm, **không** quạt dây văng, **không** hệ lai.*

**Mục đích trong portfolio:** đây **không** phải phương án dự thi thẩm mỹ. Nó là **đối
chứng bắt buộc** để trả lời đúng một câu hỏi: *mỗi bộ phận lai trong A/B/C có mang lại
vai trò nào mà D không có không?* (`01_...md` §6.1 baseline `B1`; `FC-04`; `M-03`).
Nếu A/B/C không chỉ ra được vai trò đó, các bộ phận lai là **roleless** và phải bị loại
hoặc định nghĩa lại.

### 6.1 Topology graph

```
AN-L ══MS══ saddle@PY-L ══MS══(HG)══ saddle@PY-R ══MS══ AN-R
                │                                    │
AB-L ─ DK(AP) ─ P ─ DK(SS) ── TN-L ═ DK(MS 650) ═ TN-R ── DK(SS) ─ P ─ DK(AP) ─ AB-R
```

### 6.2 Đường lực

`LC-DL`/`LC-LLs`: `DK → HG → MS → yên → nhánh sau tháp → AN → nền`. Thành phần đứng
xuống `PY`. `LC-LLh`: hệ mềm chịu lực bằng **thay đổi hình dạng**; độ cứng chống biến
dạng do **dầm cứng** cung cấp — đây chính là lý do tồn tại của dầm hộp cứng, và là
**mốc so sánh** cho câu hỏi "vòm có thêm được gì". `LC-WT`: dầm hộp khí động + hệ giằng;
`LC-CS5/CS6` (**khống chế giả định**): catwalk + spinning/kéo cáp chủ và lắp block dầm —
trạng thái nhạy gió nhất, không có kết cấu công vụ nào khác hỗ trợ.

### 6.3 Bốn tuyến khép lực

`H_MS` → `AN` (khép, cổ điển, đòi địa kỹ thuật nặng). `H_ST` → **không tồn tại** (không
có quạt dây văng); cân bằng dọc đỉnh tháp do **cáp chủ liên tục qua yên** đảm nhận, dư
là chênh lệch hai bên. `H_AC`, `H_AH` → **không tồn tại** (không có vòm).
⇒ `unresolved_equilibrium_count` giả định **= 0** ở mức topology.

### 6.4 Vai trò riêng + phép thử gỡ bỏ

Bốn họ bộ phận, bốn vai trò, không chồng lấn: `MS`+`HG` (tải đứng), `DK` (độ cứng chống
biến dạng + xoắn + hành lang kiểm tra), `PY` (đưa `MS` lên cao, nhận thành phần đứng),
`AN` (khép `H_MS`). Gỡ bất kỳ họ nào ⇒ mất cơ chế. `roleless_member_count = 0` (giả
thuyết ở mức topology).

### 6.5 Chế tạo / lắp dựng / kiểm tra / thay thế

Trình tự cổ điển, **narratable nhất** trong bốn concept: `C0→C1→C5→C6→C9`, không có
`C2/C3/C4` (không có vòm) và không có `C7`. Kiểm tra: hành lang trong dầm hộp, buồng
neo vào được, kiểm tra cáp chủ theo thực hành đã có (nguồn **chưa** lập chỉ mục trong
repo — `N-02`). Thay thế: `HG`, gối, `DP`, lớp phủ thay được; `MS`, `AN` không.

### 6.6 Giả thuyết phá hoại (≥5)

| ID | Giả thuyết |
|---|---|
| `D-FH-01` | **Mất cân bằng dọc tháp:** chênh lệch lực cáp hai bên yên tháp + ma sát yên; nhỏ hơn A/B/C nhưng **không bằng 0** |
| `D-FH-02` | **Ổn định vòm:** `NOT_APPLICABLE` — **không có vòm**. (Đây chính là dữ liệu so sánh: A/B/C phải "trả giá" bằng rủi ro này) |
| `D-FH-03` | **Cạnh tranh độ cứng cáp/dầm:** vẫn tồn tại ở dạng cổ điển (dầm cứng vs cáp mềm) nhưng là bài toán **đã có tiền lệ ngành**, không phải hệ song song mới |
| `D-FH-04` | **Mỏi:** tại neo dây treo, tại bản trực hướng (mối hàn sườn–bản), tại buồng neo cáp chủ. Không có nút dầm–vòm |
| `D-FH-05` | **Khổ thông thuyền:** cấu kiện thấp nhất là đáy dầm ⇒ **kiểm đơn giản nhất**; rủi ro xâm phạm thấp nhất |
| `D-FH-06` | **Khí động đàn hồi:** rủi ro **cao nhất tính theo mức phụ thuộc**, vì không có bộ phận nào khác đóng góp độ cứng xoắn ngoài chính dầm hộp |
| `D-FH-07` | **Mố neo:** đòi khối lượng đất/đá lớn và địa chất tốt ở hai đầu; nếu địa chất xấu thì D bị bác bỏ trước tiên |
| `D-FH-08` | **Không có tính mới:** D **không** đáp ứng mục tiêu nghiên cứu của brief. Đây là hạn chế **về mục tiêu**, không phải về cơ học |

### 6.7 Bác bỏ tại F0 / cần gì ở F1+

**Bác bỏ tại F0:** không có nền đủ tốt cho mố neo ⇒ D bị loại (và khi đó B cũng gặp rủi
ro tương tự vì cùng dùng neo đất). **Cần ở F1+:** địa kỹ thuật mố neo; khí động; mô hình
phi tuyến cáp.

---

## 7. So sánh chéo — bảng khép lực và bảng vai trò

### 7.1 Bốn tuyến khép lực

| Lực | HGB-A | HGB-B | HGB-C | HGB-D |
|---|---|---|---|---|
| `H_MS` | **`MISSING`** (3 tuyến ứng viên, chưa chọn) | Khép: `BS → CATB → nền` | `N/A` (không có `MS`) | Khép: `AN → nền` |
| `H_ST` | Cân bằng bằng **giả định**; dư → uốn tháp | Cân bằng bằng **phương trình thiết kế** `α_T(DL)=0` | **Ẩn số trung tâm** (không còn `MS` đối trọng) | `N/A` |
| `H_AC` | `TN → cọc xiên`, phụ thuộc `η_TN` chưa kiểm | như A nhưng biên độ giả định nhỏ hơn (`ψ_a≡0`) | Khép **nội bộ** trong `DK` (thanh căng) | `N/A` |
| `H_AH` | **PARTIAL** — nghi có phần tử mềm nối tiếp (`FC-05`) | Khép: `AH → CATB` trực tiếp | Khép: `AH → TB` | `N/A` |
| `unresolved_equilibrium_count` (F0, giả thuyết) | **≥ 2** | **1** (`α_T` khai thác) | **1** (cân bằng dọc tháp) | **0** |

### 7.2 Ma trận vai trò (mỗi ô: vai trò có **duy nhất** không?)

| Họ | A | B | C | D |
|---|---|---|---|---|
| `MS`/`HG` | Có | Có | `N/A` | Có |
| `ST` | Có (kép) | Có | Có | `N/A` |
| `AC` | **Xung đột khai báo** (`A-FH-07`) | Có (ngang/xoắn + giá lắp) — cần chứng minh giá trị | Có (hệ chính) | `N/A` |
| `AH` | **Có điều kiện** | Có (`κ_CATB` định lượng được) | Có | `N/A` |
| `DK` | Có | Có | Có (**kiêm hai vai trò**, phải kiểm tương thích) | Có |
| `roleless_member_count` (giả thuyết F0) | **1–2** | **0–1** | **0** | **0** |

---

## 8. Ma trận quyết định — **chỉ chấm chất lượng F0**, không phải bằng chứng kỹ thuật

> **CẢNH BÁO BẮT BUỘC.** Bảng dưới đây **KHÔNG** phải bằng chứng kỹ thuật, **KHÔNG**
> phải so sánh hiệu năng, **KHÔNG** nói phương án nào chịu lực tốt hơn, an toàn hơn, rẻ
> hơn hay bền hơn. Nó chỉ chấm **chất lượng tài liệu ở mức F0**: mức khép kín của *giả
> thuyết* đường lực, mức phân vai, mức kể được câu chuyện thi công, mức kiểm tra được,
> mức đầy đủ tham số, và **số** rủi ro chưa giải. Thang **ordinal 0–3**, không có đơn
> vị vật lý, không có trọng số kỹ thuật. Đổi thang hoặc trọng số sẽ đổi thứ hạng — điều
> đó **được phép** và chính là lý do bảng này không phải bằng chứng.

**Rubric:** `3` = phát biểu được đầy đủ và **không** còn ô trống ở mức topology ·
`2` = phát biểu được, còn ≤1 ô trống · `1` = phát biểu được nhưng có ô trống cấu trúc ·
`0` = có bộ phận/tuyến `MISSING`.
Riêng `unresolved-risk`: `3` = 0 điểm mất cân bằng chưa có bộ phận nhận; `2` = 1;
`1` = 2; `0` = ≥3.

| Tiêu chí F0 | HGB-A | HGB-B | HGB-C | HGB-D |
|---|---|---|---|---|
| `C1` Giả thuyết khép kín đường lực (`M-01`) | 0 (`H_MS` `MISSING`) | 3 | 2 (cân bằng tháp hở) | 3 |
| `C2` Tính duy nhất của vai trò (`M-03`) | 1 (xung đột khai báo `AC`) | 2 | 3 | 3 |
| `C3` Kể được trình tự thi công (`M-06`) | 2 (có sơ đồ 10 bước trong render) | 3 (thứ tự `CATB`→`MS` bắt buộc, tường minh) | 2 | 3 |
| `C4` Khả năng kiểm tra/tiếp cận | 2 | 3 (buồng neo + hành lang vòm + hộp dầm) | 2 (rất nhiều nút `SP`/`HG`) | 3 |
| `C5` Đầy đủ tham số hình học (`M-04`) | 1 (`F-01` chưa đóng; `f_c`,`z_DK`,`f_a` `MISSING`) | 2 | 2 | 2 |
| `C6` Rủi ro chưa giải (đảo chiều, `M-02`) | 1 | 2 | 2 | 3 |
| **Tổng (0–18, ordinal)** | **7** | **15** | **13** | **17** |

**Đọc bảng cho đúng:** D được điểm cao **vì nó đơn giản và đã có tiền lệ**, không phải
vì nó "tốt hơn". A được điểm thấp **vì tài liệu nguồn còn ô trống**, không phải vì
topology của người dùng đã bị chứng minh là sai — **chưa có gì được chứng minh sai**.
Toàn bộ các ô về sức kháng, ổn định, mỏi, khí động, chi phí, carbon: `NOT_EVALUATED`.

---

## 9. Khuyến nghị — hai finalist cho vòng hình học tham số kế tiếp

### 9.1 Finalist 1 — **HGB-B**

*Vì sao:* đây là concept **duy nhất** vừa giữ trọn ngôn ngữ hình ảnh v1.7 (vòm trung
tâm hạ thấp nhập tiếp tuyến vào chân tháp, hai nửa vòm biên, quạt dây văng chỉ phía đất
liền, nhịp treo 650 m) vừa **đóng được cả bốn tuyến khép lực ở mức topology**, và vừa
biến hai ẩn số nguy hiểm nhất của A thành **tham số thiết kế đo được**: `α_T` (cân bằng
dọc tháp) và `κ_CATB` (triệt tiêu neo–xô). Nó cũng gán cho vòm một vai trò **kiểm chứng
được bằng phép gỡ bỏ** (`LC-WT` + giá lắp dựng `C6`) thay vì một vai trò tự mâu thuẫn.

### 9.2 Finalist 2 — **HGB-D**

*Vì sao:* D **phải** đi cùng B vào vòng tham số, **cùng chỗ vượt, cùng bộ tham số, cùng
design basis hash**. Không có D thì phép thử `FC-04` (member-removal / rolelessness)
**không thực hiện được**, và mọi phát biểu kiểu "vòm CFST-UHPC mang lại giá trị" sẽ là
khẳng định không kiểm được. D là **thiết bị đo**, không phải đối thủ thẩm mỹ. Nếu ở F1+
B không thể hiện được vai trò nào mà D thiếu, thì **B tự bác bỏ phần lai của nó** — và
đó là một kết quả nghiên cứu có giá trị, không phải thất bại.

### 9.3 Giữ lại (HELD) — **HGB-A**

**Không bị bác bỏ.** A là baseline ý định của người dùng và phải được giữ nguyên vẹn để
truy vết. Lý do **giữ chứ chưa đưa vào vòng tham số**: A **chưa tham số hóa được** —
`H_MS` chưa có tuyến khép (`A-r1/r2/r3` chưa chọn) và sơ đồ nhịp dọc chưa đóng số học
(`F-01`). Ngay khi người dùng chốt hai điều đó, A quay lại ngay lập tức; và đáng chú ý:
chọn `A-r1` (mố neo) đưa A **hội tụ về B**; chọn `A-r2` (tự neo bằng dầm nén) sinh ra
một concept mới `A2` phải đánh giá riêng; chọn `A-r3` là **không hợp lệ** về tĩnh học
cho mọi tổ hợp tải và sẽ bị bác bỏ. Trạng thái: `HELD_PENDING_USER_INPUT` (P0).

### 9.4 Bác bỏ có điều kiện — **HGB-C**

C bị đưa ra khỏi vòng kế tiếp **vì mâu thuẫn với ý định kiến trúc đã khai của người
dùng** (`S-01` + `S-06`: nhịp giữa 650 m **phải** là nhịp treo bằng cáp chủ võng), chứ
**không** vì đã chứng minh C không đủ khả năng chịu lực — điều đó **chưa hề được đánh
giá** (`NOT_EVALUATED`). Ghi nhận trung thực: C có `roleless_member_count` giả định
**thấp nhất** và xóa hẳn `FC-01`. Nếu người dùng nới ý định (chấp nhận mất hình ảnh
nhịp treo), C **phải được đưa trở lại** và khi đó C2 (through-arch) là biến thể ưu tiên
vì nó bảo vệ hộp khổ thông thuyền. Trạng thái: `REJECTED_ON_DECLARED_INTENT`,
`NOT_REJECTED_ON_PHYSICS`.

### 9.5 Đề xuất bổ sung cho vòng sau (chưa thuộc portfolio này)

`HGB-E` — đối chứng thứ hai: cầu dây văng thuần, nhịp 650 m, không vòm, không cáp chủ.
Mục đích: tách bạch xem lợi ích của B đến từ *hệ treo* hay chỉ từ *có hai hệ cáp*. Chưa
lập vì ngân sách task; ghi lại để không mất dấu.

---

## 10. Danh sách tham số hình học để Codex sinh và **kiểm độc lập** node table

Nguyên tắc: Codex **sinh lại từ đầu** node table từ bảng này, **không** đọc lại kết quả
của tài liệu này; sau đó đối chiếu. Mọi tham số dưới đây phải mang `domain_provenance`
trung thực; giá trị `DESIGN_SEED_UNVERIFIED` **chỉ** dùng làm điểm khởi tạo, không phải
đề xuất.

### 10.1 Tham số dọc (longitudinal)

| Ký hiệu | Ý nghĩa | Loại | Nguồn miền |
|---|---|---|---|
| `L_MS` | Nhịp giữa | scalar | `DESIGN_SEED_UNVERIFIED` (`S-01`) |
| `L_SS`, `L_TR`, `L_AP` | Nhịp biên / chuyển tiếp / dẫn | scalar | `DESIGN_SEED_UNVERIFIED` (`S-08`) — **chặn bởi `F-01`** |
| `L_tot` | Tổng chiều dài | **derived** = `L_MS + 2(L_SS + L_TR + L_AP)` | phải **kiểm** với `S-07`; hiện lệch (§1.1) |
| `x_PY,L/R` | Lý trình tim tháp | derived | — |
| `x_AN/CATB,L/R` | Lý trình khối neo/khối tổ hợp (B, D) | scalar | `MISSING` |
| `x_TB,L/R` | Lý trình khối chịu xô nửa vòm biên (A, C) | scalar | `MISSING` |

### 10.2 Tham số cao độ (vertical)

| Ký hiệu | Ý nghĩa | Loại | Nguồn miền |
|---|---|---|---|
| `z_ref` | Cao độ tham chiếu (= mực nước thiết kế) | scalar | **`MISSING`** — `P0-2`, `P0-8` |
| `z_DK(x)` | Trắc dọc mặt cầu (đường cong đứng) | function | `MISSING` |
| `z_soffit(x)` | Cao độ **đáy dầm** | derived = `z_DK − h_DK` | — |
| `h_DK` | Chiều cao dầm hộp | scalar | `MISSING` |
| `h_PY` | Cao tháp | scalar | `DESIGN_SEED_UNVERIFIED` (`S-10`) |
| `z_saddle` | Cao độ yên cáp | derived | — |
| `f_c`, `χ_c = f_c/L_MS` | Độ võng cáp chủ, tỷ số võng | scalar | `MISSING` — **P0** |
| `z_TN` | Cao độ nút chân tháp (điểm nhập vòm) | scalar | `MISSING` |
| `f_a`, `r_a = L_a/f_a` | Đường tên và độ thoải vòm trung tâm | scalar | `MISSING`; ràng buộc `μ = r_a/4` (`E-06`) |
| `g`, `λ_gap = g/d_a` | Khe kỹ thuật vòm–đáy dầm | scalar | `MISSING` |
| `z_crown_AC` | **Cao độ đỉnh vòm trung tâm** | derived | **bắt buộc** cho kiểm khổ thông thuyền |

### 10.3 Tham số ngang (transverse)

`B_D` (=`S-09`, seed) · `n_lane` (`MISSING`) · `b_a × d_a` (=`S-12`, seed) ·
`n_rib_AC ∈ {1, 2}` (topology enum; ảnh hưởng trực tiếp đường lực xoắn) ·
`s_cable` khoảng cách hai mặt phẳng cáp (`MISSING`) · `n_OR`, `θ_OR` sườn xiên
(`MISSING`).

### 10.4 Tham số hệ cáp

`ρ_HG` bước dây treo · `n_s` số dây mỗi quạt · `θ_s,min/max` dải góc ·
`s_DK` bước neo trên dầm · `θ_BS` góc backstay (**B**, là biến điều khiển `α_T`) —
toàn bộ `MISSING`.

### 10.5 Node families mà Codex phải sinh

`N-AB` mố · `N-PIER` trụ dẫn · `N-PY-base` chân tháp · `N-TN` nút chân tháp tích hợp ·
`N-PY-top`/`N-SADDLE` · `N-MS(i)` điểm cáp chủ theo bước `ρ_HG` · `N-HG(i)` neo dây
treo trên dầm · `N-ST-tower(j)`/`N-ST-deck(j)` · `N-AC(k)` trục vòm trung tâm ·
`N-AH(m)` trục nửa vòm biên · `N-AH-end` nút cuối nửa vòm biên · `N-TB`/`N-CATB`/`N-AN`
· `N-DK(x)` trục dầm.

### 10.6 Kiểm tra độc lập bắt buộc (Codex chạy, **không** lấy kết quả từ đây)

1. **Đóng chuỗi dọc:** `Σ` nhịp `≡ L_tot`. Hiện **FAIL** theo `F-01` ⇒ phải chặn cho tới
   khi người dùng chốt.
2. **Hộp khổ thông thuyền:** `min_x∈luồng( z_lowest_structure(x) ) − z_MNTK ≥ C_nav`,
   trong đó `z_lowest_structure` **phải** xét cả `z_crown_AC`, không chỉ `z_soffit`.
   Kết quả hiện tại: `NOT_EVALUATED` (thiếu `z_ref`, `z_DK`, `f_a`).
3. **Liên tục tiếp tuyến tại `TN`:** góc tiếp tuyến của `AC` và của `AH` tại nút phải
   được xuất ra tường minh; nếu lệch, `η_TN ≠ 0` và phải có bộ phận nhận phần dư.
4. **Đơn điệu:** bước dây treo/dây văng và biến thiên chiều cao tiết diện vòm phải đơn
   điệu; nhảy bậc ngẫu nhiên là lỗi topology (`FALS-06`).
5. **Không giao cắt:** `AC` ∩ `DK` = ∅ (khe `g > 0`); `ST` ∩ `MS` = ∅ trong nhịp giữa
   (ràng buộc `S-06`: **không** dây văng xiên phía trong tháp).
6. **Tái lập:** cùng bộ tham số ⇒ cùng hash node table (`FC-11`).
7. **Fail-closed:** mọi tham số `MISSING` ⇒ node table trả `UNKNOWN_INPUT_MISSING`,
   **không** điền giá trị mặc định.

---

## 11. Trạng thái gate, tiêu chí bác bỏ ở F0 và yêu cầu F1+

### 11.1 `G1 — Geometry & reality`: **NOT_EVALUATED / NOT_CLAIMED**

Lý do, kiểm được trong repo:

1. `docs/runtime_capability_matrix.md` §1 — `L0_FABRICATION_RULES` = **PARTIAL**, và
   giới hạn được khai nguyên văn: *"Chỉ áp cho tiết diện `PARAMETRIC`"* (Super-T), ngưỡng
   FAB là mặc định repo, **chưa** lấy từ crane chart / khảo sát tuyến vận chuyển / hệ
   ván khuôn nhà máy thực. Không rule FAB nào chạm tới cáp chủ, dây văng, vành vòm, tháp
   hay nút liên hợp.
2. `L0_LAYOUT_RULES` (`GEOM-*`, `CONS-*`) hiệu chỉnh cho **mặt cắt ngang n dầm Super-T
   song song**, không áp được cho mặt cắt hộp thép ba khoang có sườn xiên.
3. `ARCH_RIB_STABILITY` = **ABSENT**; engine cột **chủ động từ chối** cấu kiện
   `ARCH_RIB` (`bridge_evolution/column_capacity/engine.py::require_straight_prismatic`).
4. Không có grammar/schema nào mô tả được hệ lai (`N-01`, `SM-12`); họ `arch_deck_v1` là
   sandbox bị loader chặn và hộp `span_m` của nó tối đa 600 m — **không chứa** 650 m.
5. Tham số hình học cốt lõi (`z_ref`, `z_DK`, `f_c`, `f_a`, `g`) đều `MISSING`; chuỗi
   nhịp dọc chưa đóng (`F-01`) ⇒ **clash-free** và **parametric repeatable** đều chưa
   kiểm được.

⇒ Không có cơ sở trung thực nào để claim `G1 PASS`. Ghi **`NOT_EVALUATED`**, và
`NOT_EVALUATED` **không bao giờ** ánh xạ thành `PASS`.

### 11.2 Ma trận "cái gì bác bỏ concept ngay ở F0"

| Concept | Bác bỏ tại F0 nếu… |
|---|---|
| A | Người dùng loại cả mố neo lẫn tự neo; hoặc `F-01` không giải được; hoặc đỉnh vòm cắt hộp khổ thông thuyền đã phê duyệt |
| B | Không có nền tốt cho `CATB` ở hai đầu; hoặc không thiết kế được liên kết vòm–dầm giữ `ψ_a ≈ 0` |
| C | Ý định "nhịp treo 650 m" là bất biến (**đã xảy ra** ⇒ §9.4); hoặc C1 xung đột khổ thông thuyền |
| D | Không có nền tốt cho mố neo; hoặc mục tiêu nghiên cứu bắt buộc phải có tính mới |

### 11.3 Dữ liệu và solver cần cho F1+ (không concept nào lên F1 được hôm nay)

- **Dữ liệu người dùng (P0, `01_...md` §18.1):** `P0-1` chốt lineage · `P0-2` site thật ·
  `P0-3` văn bản AHJ về khổ thông thuyền · `P0-4` design life/exposure/AHJ/tiêu chuẩn ·
  `P0-5` tải + tổ hợp cho **từng** giai đoạn · `P0-6` động đất · `P0-7`/`P0-8`/`P0-9`
  địa chất/thủy văn/gió thực đo · `P0-10` hình học đầy đủ. **Bổ sung của task này:**
  đóng `F-01` (sơ đồ nhịp dọc chính tắc) và chốt tuyến khép `H_MS` cho HGB-A.
- **Năng lực (P1):** solver 3D phi tuyến hình học + staged construction (`SM-11`,
  `STAGED_PRESTRESS_EFFECTS = ABSENT`) · trị riêng oằn vành vòm trong/ngoài mặt phẳng
  (`ARCH_RIB_STABILITY = ABSENT`) · phân tích khí động đàn hồi (`FC-07`) · thuộc tính
  UHPC/CFST trong miền áp dụng (`E-07`, `N-03`, `FC-09`) · thuộc tính cáp/neo và S-N
  (`SM-09`) · grammar hệ lai (`SM-12`) · nguồn đã xác minh về cầu dây/khí động
  (`N-02`, `P1-7`).

---

## 12. Đối chiếu acceptance criteria (đã sửa đổi theo `AMD-acc47bcbe2a7496b`)

| Acceptance criterion | Đáp ứng ở |
|---|---|
| Tối thiểu ba concept **khác cơ chế**, không chỉ đổi kích thước | §3 (treo ∥ vòm song song), §4 (treo neo đất, vòm hạ cấp thành hệ ngang), §5 (vòm chính, dầm là thanh căng — thêm hai biến thể cột nén / thanh treo kéo), §6 (một cơ chế duy nhất). Bốn cơ chế **khác nhau về đường lực**, không phải khác `L`, `f` hay tiết diện |
| Mỗi concept nêu load path, novelty, chế tạo, bảo trì, failure hypothesis | §3.3–3.7, §4.3–4.7, §5.2–5.6, §6.2–6.6 (≥5 giả thuyết phá hoại mỗi concept, bao gồm đủ 5 nhóm bắt buộc: mất cân bằng dọc tháp, ổn định vòm trong/ngoài mặt phẳng, cạnh tranh độ cứng cáp/dầm/vòm, mỏi nút dầm–vòm, xâm phạm khổ thông thuyền) |
| Render hoặc ý tưởng AI được gắn nhãn `IDEA` | §0 (khối ranh giới), §1 (sổ seed + cảnh báo đọc ảnh), `F-01` |
| Chỉ sản xuất portfolio F0; `G1` = `NOT_EVALUATED`/`NOT_CLAIMED` vì `L0_FABRICATION_RULES` mới `PARTIAL` | §0 bảng trạng thái, §11.1 (5 lý do kiểm được trong repo) |
| Không dùng dữ liệu PSC 45+75+45 m làm design basis đã xác minh cho hybrid 650 m | §0 khối "Ranh giới lineage" — **không** `AF-*`/`AA-*` nào được trích trong tài liệu này |
| `safety_notes`: nêu rõ điểm mất cân bằng lực, bộ phận nhận lực xô, giai đoạn thi công chưa giải được | §3.4, §4.4, §5.3, §6.3 (bốn tuyến khép lực/concept); §7.1 (bảng chéo); mỗi concept nêu `LC-CS*` **khống chế giả định** ở §3.3, §4.3, §5.2, §6.2 |

---

## 13. Tuyên bố cấm — nhắc lại để không mất dấu

Tài liệu này **không** phát hành `PASS/FAIL` kỹ thuật, **không** phát hành kích thước
thiết kế, sức kháng, utilization, tần số, vận tốc flutter, biên an toàn, chi phí hay
carbon. Nó **không** tuyên bố bất kỳ concept nào đủ khả năng chịu lực, ổn định, an
toàn, khả thi thi công hay có tính mới toàn cầu. Ma trận §8 là **thang chất lượng tài
liệu F0**, không phải bằng chứng kỹ thuật. `G0` vẫn `FAIL`; `G1` vẫn
`NOT_EVALUATED / NOT_CLAIMED`; trần claim của tài liệu là `IDEA`.
