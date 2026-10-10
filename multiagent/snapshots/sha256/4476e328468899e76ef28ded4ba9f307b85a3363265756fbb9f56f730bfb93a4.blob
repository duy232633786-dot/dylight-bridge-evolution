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

**[S2] VOID trong family SKETCH KHÔNG tự cắt, và `SolidSolidCutUtils` TỪ CHỐI ở đó.**
Đo trên `FAM_BeMong.rfa`: khối 10.0 × 8.0 × 2.5 m cộng một void 1.2 × 1.2 × 3.0 m xuyên qua.
```
form solid=1  void=1                    <- void CÓ tồn tại
thể tích      = 200.000 m3              <- ĐÚNG BẰNG 10x8x2.5, tức KHÔNG cắt
                                           (nếu cắt phải còn 196.400)
CanElementCutElement = False   reason = CutNotAppropriateForElements
AddCutBetweenSolids  -> ArgumentException:
  "The element must be in a project document or in a conceptual model,
   pattern based curtain panel, or adaptive component family."
```
**Nguy hiểm vì nó IM LẶNG:** `NewExtrusion(false, ...)` trả về đối tượng bình thường, không lỗi,
và void hiện diện trong file — nhưng khối không bị khoét. Nhìn danh sách phần tử thì thấy đủ;
chỉ **đo thể tích** mới lộ ra.
**Quy tắc:** sau khi tạo void, PHẢI đối chiếu thể tích với giá trị kỳ vọng đã trừ phần khoét.
**CHƯA ĐO:** cách làm void cắt được trong family SKETCH (tham số "Cuts Geometry", hoặc phải dựng
void trong cùng sketch với solid). Chưa biết thì **đừng dùng void trong thế giới SKETCH**.

**[S3] Template family SHIP SẴN HÌNH HỌC — phải xoá trước khi dựng.**
Đo trên `FAM_DotVanhVom.rfa` (template `Metric Structural Framing - Beams and Braces.rft`):
```
Extrusion  id=999   vol=0.150 m3   <- CỦA TEMPLATE, không ai tạo
SweptBlend id=4816  vol=71.392 m3  <- của mình
```
Nếu chỉ đếm `GenericForm` rồi kết luận "đã dựng xong" thì con số bị nhiễm khối rác của template.
**Quy tắc:** ngay sau `NewFamilyDocument`, quét `GenericForm` có sẵn và **xoá hết** trước khi dựng.

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

**[A3] Điểm hosted trên đường: TIẾP TUYẾN nằm ở `BasisX`, nên mặt phẳng TIẾT DIỆN là `YZ`.**
Và hệ toạ độ **chỉ đúng SAU `Regenerate()`**. Đo trên spine hướng (0.6, 0.8, 0):
```
TRƯỚC Regenerate: BasisZ=(0,0,1)                    ← ma trận đơn vị, CHƯA tính
SAU   Regenerate: BasisX=(0.600,0.800,0.000)        ← chính là tiếp tuyến
                  BasisY=(-0.800,0.600,0.000)
                  BasisZ=(0.000,0.000,1.000)
```
Dùng `GetCoordinatePlaneReferenceXY()` là **SAI** — mặt phẳng đó CHỨA đường dẫn, nên profile
song song path và `NewLoftForm` ném `InvalidOperationException: Cannot create loft form.`
Phải dùng **`GetCoordinatePlaneReferenceYZ()`**.

**[A4] `NewLoftForm` qua API KHÔNG giữ liên kết tham số với điểm thích ứng — KẾT QUẢ ÂM.**

Dựng đúng theo [A3] thì form **tạo được** (`isSolid=True`, 54.533 m³). Nhưng FLEX TEST **HỎNG**:
```
TRƯỚC:  spine=10.000 m   hostB=null   form=1   vol=54.533 m3
SAU  :  spine=24.104 m   hostB=null   form=1   vol=54.533 m3
```
Spine **có** flex (10.000 → 24.104 m, đúng √(22²+9²+4²)). Nhưng thể tích form **đứng yên**, và
`hostB` trả `null` **ngay từ trước khi flex** — các `ReferencePoint` hosted bị **nuốt vào form**
lúc tạo. Form giữ bản sao hình học riêng và **đứt liên kết ngược** về điểm thích ứng.

Đổi sang profile đặt trên mặt phẳng của **chính điểm thích ứng** (bỏ điểm hosted trung gian)
cũng **không cứu được**: form dựng OK nhưng FLEX vẫn hỏng, tỷ lệ thể tích 1.0000.

**[A5] `NewSweptBlendForm` GIỮ ĐƯỢC liên kết tham số — ĐÂY LÀ LỐI ĐÚNG.**

Cùng nền adaptive, cùng mặt phẳng `YZ` theo [A3], chỉ đổi `NewLoftForm` → `NewSweptBlendForm`
và truyền **spine làm path**:

```csharp
var pathRa = new ReferenceArray();
pathRa.Append(spine.GeometryCurve.Reference);       // <-- MẤU CHỐT: có PATH
var raa = new ReferenceArrayArray();
raa.Append(prof(hostA, halfStart));                 // profile trên mp YZ của điểm hosted
raa.Append(prof(hostB, halfEnd));
fd.FamilyCreate.NewSweptBlendForm(true, pathRa, raa);
```

FLEX TEST **ĐẠT**:
```
vol 54.533 -> 131.447 m3    tỷ lệ = 2.4104
chiều dài 10.000 -> 24.104  tỷ lệ = 2.4104     <-- KHỚP CHÍNH XÁC
```

**Vì sao khác nhau:** `NewSweptBlendForm` nhận **path**, nên form bị ràng buộc vào spine — mà
spine do điểm thích ứng điều khiển. `NewLoftForm` **không có path**, nên nó chỉ loft hình học
tại thời điểm tạo rồi đứt liên kết.

**Quy tắc rút ra:** trong môi trường adaptive, muốn hình **flex** thì phải dùng phép dựng **CÓ
PATH**. Phép không path cho ra khối tĩnh — hình đúng, tham số giả.

Ghi chú: chủ dự án từng ghi lại rằng family panel adaptive **4 điểm** đặt tự động bị **méo** và
phải lùi về DirectShape. Ca 4 điểm **CHƯA ĐO** ở đây; kết quả [A5] chỉ áp cho **2 điểm**.

**[A6] Thành phần UV THỨ NHẤT luôn rơi vào trục ĐỨNG nhất — phải hoán vị `w`↔`h`.**

`NewPointOnPlane(planeRef, UV(u,v), ...)` trên mặt phẳng YZ của điểm hosted: Revit tự chọn
hướng U/V, và hướng đó **đổi theo phương của spine**. Đo bằng tiết diện bất đối xứng 10 × 2 m
đặt theo bốn phương, rồi đọc bao của instance thật:

| Phương spine (Revit) | 10 m rơi vào | 2 m rơi vào |
|---|---|---|
| X — dọc cầu | **Z (đứng)** | Y (ngang) |
| Y — ngang cầu | **Z (đứng)** | X (ngang) |
| Z — thẳng đứng | Y | X |

**Quy luật: `UV[0]` → trục đứng nhất; `UV[1]` → trục ngang còn lại.** Quy ước DirectShape thì
ngược (`w` ngang, `h` đứng), nên khi sinh family phải đặt **`h` vào `UV[0]` và `w` vào `UV[1]`**.

**Cách phát hiện:** hậu quả im lặng — hình vẫn dựng, số lượng vẫn đúng, chỉ **bao cao độ** sai.
Thanh thềm đá 63.0 × 7.5 m nằm ngang cầu bị dựng 63 m theo phương **đứng**:
```
TRƯỚC: SEC_035 span X=7.50   Y=44.00  Z=63.00   -> z_min toàn cầu = -57.75 m  SAI
SAU  : SEC_035 span X=63.00  Y=44.00  Z=7.50    -> z_min toàn cầu = -30.00 m  ĐÚNG
```
Sau khi hoán vị, bao toàn cầu của bản FAMILY **trùng khít** bản DirectShape:
`x -34..214 | y -22..22 | z -30..67.23`.

**Bài học phương pháp:** phép đo vector U/V (đặt một điểm ở U=1, một ở V=1 rồi đọc hướng) cho
kết quả **MÂU THUẪN** với hành vi thật của instance. Chỉ phép đo trên **cái quan sát được cuối
cùng** — bao của instance đã đặt — mới đúng. Khi hai phép đo đá nhau, tin phép đo gần với thứ
mình thật sự quan tâm.

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
| `FamilyManager.AddParameter` trong family **ADAPTIVE / MASSING** | chỉ đo trên `Metric Generic Model` (§2). **Hệ quả nặng:** dấu claim BẮT BUỘC (`DYLIGHT_ClaimLevel`) do đó CHƯA dán được vào family adaptive — phải đo trước khi dựng dầm chủ / gờ lan can |
| `SaveAs` .rfa từ template **Mass** hoặc template **2D** | mới lưu .rfa từ SKETCH (475.136 B) và ADAPTIVE (499.712 B). Rất có thể chạy được vì SaveAs là API mức `Document`, nhưng SUY RA không phải ĐO |
| `NewBlend` / `NewSweep` / `NewSweptBlend` / `NewRevolution` **ngoài** thế giới SKETCH | §1 chỉ đo ĐÍCH DANH `NewExtrusion` ngoài SKETCH. Kết luận §0 rất có thể phủ cả nhóm `FamilyItemFactory`, nhưng suy ra không phải đo |

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

---

## 8. Pha 2 — ma trận này đã thành mã chạy được

`bridge_evolution/revit_family/` mã hoá đúng tài liệu này thành **cổng chặn**, để
không ai sinh ra C# mà ta đã đo là hỏng:

| Thành phần | Vai |
|---|---|
| `worlds.py` — `TEMPLATES` | 12 hàng của §1: template → thế giới, category, cờ `IsAdaptiveComponentFamily` |
| `worlds.py` — `OPERATIONS` | mỗi phép ghi trạng thái theo **từng thế giới**: `MEASURED_OK` / `MEASURED_FAIL` / `NOT_MEASURED` |
| `worlds.py` — `require_operation(op, template)` | RAISE chứ không trả bool. Đã đo hỏng → `UnsupportedInWorldError` kèm lỗi Revit nguyên văn; chưa đo → `NotMeasuredError` kèm lý do và trỏ về mục 5 ở trên |
| `csharp.py` — `family_scaffold` | khuôn `NewFamilyDocument` → `Transaction` riêng → `Regenerate()` **trong** transaction → `SaveAs` → `Close(false)`, tự kiểm lại thứ tự đó trên chính chuỗi vừa sinh |
| `csharp.py` — `CSharpBuilder` | từ chối phát dòng mở `new Transaction(document…)`, dòng `Guid.NewGuid()`, dòng `document.Close(…)` và mọi ký tự ngoài ASCII |
| `tests/test_revit_family.py` | 207 test đối chiếu từng ô của tài liệu này; không test nào cần Revit chạy |

**Ranh giới claim không đổi: F0 IDEA.** Thư viện chỉ phát được mức claim
`F0_IDEA` — nâng mức là việc của hợp đồng nhiệm vụ, không phải của bộ sinh mã.
