# Ma trận năng lực dựng Family Revit — RFC-1.1.0

Task: **BRD-036** · Pha 1 (cổng chặn) · Đo trên **Revit 2026** máy này, ngày **2026-08-26**.

Mọi dòng là **kết quả chạy thật qua `send_code_to_revit`**, không đọc từ tài liệu API.
Chỗ nào chưa đo thì ghi `CHƯA ĐO`, không suy đoán.

---

## 0. Kết luận lớn nhất — ĐỌC TRƯỚC

**Revit có HAI THẾ GIỚI DỰNG HÌNH RỜI NHAU, cộng một thế giới 2D. Template quyết định bạn ở
thế giới nào, và hai thế giới 3D LOẠI TRỪ NHAU.**

| | Thế giới **SKETCH** | Thế giới **MASSING/ADAPTIVE** | Thế giới **2D** |
|---|---|---|---|
| Dựng khối bằng | `FamilyItemFactory`: Extrusion, Blend, Sweep, SweptBlend, Revolution | `Form`: LoftForm, ExtrusionForm | không dựng khối được |
| `NewReferencePoint` | ❌ `FamilyContextException` | ✅ | ❌ |
| `NewExtrusion` | ✅ | ❌ `InvalidOperationException`<br>*"not permitted in this type of family"* | ❌ `ArgumentException` |
| Điểm điều khiển hình | tham số + mặt phẳng làm việc | **điểm thích ứng** | — |

Đây **không phải chi tiết kỹ thuật vặt**. Nó có nghĩa: chọn template là chọn **cả bộ công cụ**.
Không thể dùng `NewExtrusion` trong family adaptive, và không thể dùng điểm thích ứng trong
family thường. Mọi thiết kế family phải quyết định thế giới **trước**, không sửa được sau.

---

## 1. Thế giới nào cho template nào — đo được

| Template | Category | isAdaptive | `NewExtrusion` | `NewReferencePoint` | `Form` | Thế giới |
|---|---|---|---|---|---|---|
| Metric Generic Model | Generic Models | False | ✅ | ❌ | ❌ | SKETCH |
| Metric Structural Framing - Beams and Braces | Structural Framing | False | ✅ | ❌ | ❌ | SKETCH |
| Metric Structural Column | Structural Columns | False | ✅ | ❌ | ❌ | SKETCH |
| Metric Structural Foundation | Structural Foundations | False | ✅ | ❌ | ❌ | SKETCH |
| Metric Generic Model line based | Generic Models | False | ✅ | ❌ | ❌ | SKETCH |
| Metric Generic Model face based | Generic Models | False | ✅ | ❌ | ❌ | SKETCH |
| **Metric Generic Model Adaptive** | Generic Models | **True** | ❌ | ✅ | ✅ | **ADAPTIVE** |
| Conceptual Mass\Metric Mass | Mass | False | ❌ | ✅ | ✅ | **MASSING** |
| Metric Generic Model Pattern Based | Curtain Panels | **True** | ❌ | ✅ | ✅ | **ADAPTIVE** |
| Metric Curtain Panel Pattern Based | Curtain Panels | **True** | ❌ | ✅ | ✅ | **ADAPTIVE** |
| Metric Profile-Hosted | Profiles | False | ❌ | ❌ | ❌ | 2D |
| Metric Detail Item | Detail Items | False | ❌ | ❌ | ❌ | 2D |

**MỞ ĐƯỢC HẾT 12/12.** Vẽ thì tuỳ thế giới.

Lưu ý tinh tế: **Mass có `isAdaptive = False` nhưng vẫn thuộc thế giới massing** (điểm + form
chạy được). Nên cờ `IsAdaptiveComponentFamily` **không** dùng để đoán thế giới; phải nhìn
template.

---

## 2. Thế giới SKETCH — `FamilyItemFactory`

Template đo: `Metric Generic Model.rft`

| Phép | Trạng thái | Bằng chứng |
|---|---|---|
| `NewExtrusion` (solid) | **OK** | 2 Extrusion trong `_probe_family.rfa` |
| `NewExtrusion` (**void**) | **OK** | `GenericForm VOID = 1` |
| `NewBlend` | **OK** | id=2939 — ràng buộc **[B1]** |
| `NewRevolution` | **OK** | id=2950 — ràng buộc **[R1]** |
| `NewSweep` (path nhiều đoạn) | **OK** | Sweep=1, path 2 đoạn |
| `NewSweptBlend` (path **thẳng**) | **OK** | ràng buộc **[S1]** |
| `NewSweptBlend` (path **CUNG TRÒN**) | **OK** | cùng phép, path là `Arc` |
| Model Line `NewModelCurve` | **OK** | id=2939, type `ModelLine` |
| Reference Line `ChangeToReferenceLine()` | **OK** | id=2940 (type vẫn báo `ModelLine`) |
| Reference Plane `NewReferencePlane` | **OK** | id=2943, đặt tên được; cần một `View` |
| Model Text `NewModelText` | **OK** | id=2944 |
| **Work plane NGHIÊNG** + Extrusion trên nó | **OK** | pháp tuyến (0.6, 0, 0.8) |
| Component — `LoadFamily` family lồng | **OK** | `loaded=True` |
| `FamilyManager.AddParameter` + `Set` | **OK** | `DYLIGHT_ChieuCao` còn sau khi lưu |
| `SaveAs` .rfa | **OK** | 475.136 bytes |

### Ràng buộc — phần đắt giá nhất

**[S1] `NewSweptBlend` nhận `Reference`, KHÔNG nhận `Curve`.**
```
Argument 2: cannot convert from 'Autodesk.Revit.DB.Curve' to 'Autodesk.Revit.DB.Reference'
```
Path phải là tham chiếu tới đường **đã tồn tại** trong family:
```csharp
ModelCurve mc = fd.FamilyCreate.NewModelCurve(arc, sketchPlane);
fd.FamilyCreate.NewSweptBlend(true, mc.GeometryCurve.Reference, profBottom, profTop);
```
**Nghi vấn ban đầu bị bác theo hướng thuận lợi:** path **cong được**, nên một đốt vòm cong
tiết diện thuôn dựng được bằng **một phép**, không phải chia đoạn.

**[B1] `NewBlend` đòi hai profile ở CAO ĐỘ KHÁC NHAU.** Cả hai ở `z=0` → hỏng.

**[R1] `NewRevolution` đòi trục NẰM TRONG mặt phẳng phác thảo.** Trục vuông góc → hỏng.

---

## 3. Thế giới MASSING / ADAPTIVE — `Form` + điểm thích ứng

Template đo: `Metric Generic Model Adaptive.rft`

| Phép | Trạng thái | Bằng chứng |
|---|---|---|
| `NewReferencePoint` | **OK** | id=7586, 7587 |
| `MakeAdaptivePoint` (PlacementPoint) | **OK** | 2 điểm |
| `IsAdaptiveComponentFamily` | **OK** | True — ràng buộc **[A1]** |
| `NewCurveByPoints` | **OK** | dài 10.0000 m |
| **`NewLoftForm`** (2 profile, thuôn) | **OK** | id=7602, `isSolid=True` |
| **`NewExtrusionForm`** | **OK** | id=7645 |
| **`NewLoftForm` VOID** | **OK** | id=7706, `isSolid=False` |
| `NewSweptBlendForm` | **FAIL** *(chưa loại trừ lỗi người gọi)* | `InvalidOperationException: Cannot create swept blend form.` |
| **FLEX TEST** | **OK** | xem dưới |
| `SaveAs` .rfa | **OK** | 499.712 bytes |

### FLEX TEST — phép đo quyết định

Một family adaptive dựng đúng hình **nhưng không chạy theo điểm** thì chỉ là khối cứng đội lốt
family — **tệ hơn DirectShape**, vì trông như tham số mà không phải.

```
dài TRƯỚC          = 10.0000 m
→ dời điểm 2 tới (25, 8, 0)
dài SAU            = 26.2488 m
kỳ vọng √(25²+8²)  = 26.2488 m
sai lệch           = 3.55E-15
CHẠY THEO          = True
```

**[A1]** `IsAdaptiveComponentFamily` nhận `Family` chứ không phải `Document` → dùng `fd.OwnerFamily`.
**[A2]** Không có `AdaptiveComponentFamilyUtils.GetPlacementPoints`. Tên đúng **CHƯA ĐO**.

---

## 4. Ghi chú phương pháp — quan trọng ngang số liệu

Ở lần đo đầu, `NewBlend` và `NewRevolution` **đều trả về 0 đối tượng**. Nếu dừng ở đó và ghi
`ABSENT` thì ma trận này đã **sai**: cả hai chạy được, lỗi nằm ở tham số tôi truyền vào.

> **Không được ghi ABSENT khi chưa loại trừ lỗi của chính mình.**

Cùng nguyên tắc, `NewSweptBlendForm` ở trên ghi là **FAIL (chưa loại trừ lỗi người gọi)**, KHÔNG
phải ABSENT — nhiều khả năng profile chưa đặt đúng vị trí dọc path.

---

## 5. CHƯA ĐO — không được coi là có

| Phép | Vì sao |
|---|---|
| `NewRevolveForm` (massing) | chưa chạy |
| Profile **không phẳng** trong form adaptive | nghi vấn (ii) của task, chưa trả lời |
| `CreateAdaptiveComponentInstance` + `SetInstancePlacementPointElementRefIds` | bước LẮP, thuộc Pha 3 |
| Opening, Model Group | trong ribbon, chưa đo |
| Connectors (Electrical/Duct/Pipe/Cable Tray/Conduit) | trong ribbon; **không liên quan cầu**, cố ý bỏ |
| Family adaptive **4 điểm** | skill của chủ dự án ghi panel 4 điểm đặt tự động bị **MÉO**, đã phải lùi về DirectShape. Ranh giới **chưa rõ** — phải đo trước khi dùng |
| Titleblock, Annotation, Baluster, Railing Support/Termination, Curtain Wall Panel | chưa đo |

---

## 6. Ánh xạ cấu kiện → thế giới → phép dựng

Rút từ số đo, không suy đoán:

| Cấu kiện | Thế giới | Template | Phép | Vì sao |
|---|---|---|---|---|
| Đốt vành vòm (cong, thuôn) | SKETCH | Structural Framing | `NewSweptBlend` + ModelCurve cong | [S1] path cong được ⇒ 1 đốt = 1 phép |
| Thân trụ thuôn | SKETCH | Structural Column | `NewBlend` | [B1] hai profile khác cao độ |
| Móng | SKETCH | Structural Foundation | `NewExtrusion` | khối lăng trụ đơn giản |
| Cấu kiện tròn xoay | SKETCH | Generic Model | `NewRevolution` | [R1] trục trong mặt phẳng |
| Giằng chéo, cột nghiêng | SKETCH | Structural Framing | work plane **nghiêng** + Extrusion | work plane nghiêng đã chứng minh |
| Lỗ, khoét | SKETCH | — | `NewExtrusion` void | đã chứng minh |
| Cụm lặp (khoang vòm) | SKETCH | — | `LoadFamily` lồng | đã chứng minh |
| **Dầm chủ, gờ lan can, lan can thép** | **ADAPTIVE** | Generic Model Adaptive | điểm thích ứng + `NewLoftForm` | FLEX đạt; dự án thật đã dùng adaptive 2 điểm |
| Mặt cầu cong / vênh siêu cao | **MASSING** | Metric Mass | `NewLoftForm` | massing hợp cho mặt trơn biến thiên |

**Ranh giới claim không đổi.** Family tham số trông giống hồ sơ kỹ thuật thật hơn DirectShape
nhiều, nên rủi ro đọc nhầm **cao hơn**. Mức claim vẫn **F0 IDEA**: chưa có design basis
(BRD-004 bị hai nhà cung cấp REVISE vì `project_inputs` toàn null) và runtime vẫn không có
solver cho vòm. Mỗi family và mỗi instance phải mang dấu claim level **đọc được trong Revit**.

---

## 7. Artifact probe

| File | Nội dung |
|---|---|
| `tmp/arch_massing/_probe_family.rfa` | 475.136 B — 2 Extrusion, 1 Sweep, 2 SweptBlend, 1 void, tham số `DYLIGHT_ChieuCao` |
| `tmp/arch_massing/_probe_adaptive.rfa` | 479.232 B — 2 điểm thích ứng, `CurveByPoints`, đã qua FLEX TEST |
| `tmp/arch_massing/_probe_adaptive_forms.rfa` | 499.712 B — LoftForm, ExtrusionForm, LoftForm void |

Khi lệnh MCP timeout: **mở lại `.rfa` và đếm đối tượng theo kiểu** thay vì chạy lại probe.
Đã dùng đúng cách đó một lần trong đợt đo này.
