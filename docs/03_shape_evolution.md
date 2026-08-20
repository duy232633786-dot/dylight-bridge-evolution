# 03 — Tiến hóa hình dạng tiết diện: thang tự do thiết kế và giới hạn trung thực

Phiên bản: `SE-1.0` — 2026-08-21. Đi kèm `RC-1.1` (`docs/01_research_contract.md`).

Người đọc mục tiêu: kỹ sư cầu duyệt phương án. Tài liệu này trả lời ba câu hỏi:
agent được phép tự do tới đâu, vì sao ràng buộc chế tạo phải nằm trong vòng lặp
tối ưu, và **kết quả của đợt này KHÔNG được diễn giải như cái gì**.

---

## 1. Thang 5 cấp tự do thiết kế

Mỗi cấp mở thêm một nhóm biến cho agent. Nguyên tắc xuyên suốt: **chỉ mở một cấp
khi verifier có đủ mô hình để kiểm được cái vừa mở**. Tự do vượt quá năng lực
kiểm tra không tạo ra thiết kế tốt hơn — nó tạo ra phương án không ai dám ký.

| Cấp | Agent được chọn gì | Trạng thái | Verifier cần gì để kiểm được |
|---|---|---|---|
| 1 | Tiết diện **định hình** trong catalog (ST-1650/1750/1850) + bố trí, vật liệu, cáp | **Đã có** (`super_t_simple_v1`) | Đặc trưng tiết diện tra sẵn (A, I, y_b); L0 hình học + L1 line-girder là đủ vì hình dạng đã được nhà sản xuất bảo chứng |
| 2 | **Hình dạng mặt cắt tham số hóa**: chiều cao dầm, bề dày sườn, bề dày cánh trên, kích thước bầu dưới… | **Đợt này** (`super_t_parametric_v2`) | (a) Hàm tính đặc trưng tiết diện từ tham số, thay cho tra catalog; (b) nhóm rule **FAB-\*** ở L0 cho chế tạo/vận chuyển/cẩu lắp/bố trí cáp; (c) MODEL-001 vẫn phải chặn khi công thức L1 ra ngoài miền áp dụng |
| 3 | **Vật liệu mở rộng**: cấp bê tông cao hơn, loại tao cáp khác, cốt sợi | Chưa mở | Mô hình vật liệu theo giai đoạn: cường độ lúc truyền lực, mất mát DƯL, co ngót–từ biến, và **miền hiệu lực của công thức tiêu chuẩn theo f'c** (xem §4) |
| 4 | **Công nghệ chế tạo**: căng trước/căng sau, dầm ghép đoạn, mối nối, dầm liên tục hóa | Chưa mở | Mô hình giai đoạn thi công (L3), kiểm tra mối nối và vùng neo; catalog chi phí phải tách được chi phí công nghệ, không chỉ chi phí vật liệu |
| 5 | **Topology tự do**: hệ dầm không còn là "n dầm Super-T song song" (dầm hộp, bản rỗng, hệ lai) | Chưa mở | Phân tích 3D bắt buộc (L2 trở lên), kiểm ổn định tổng thể/thành mỏng, và một grammar mới — verifier hiện tại **không có** khái niệm nào ngoài hệ dầm song song |

Đợt nâng cấp này chỉ đi từ cấp 1 lên **cấp 2**. Grammar v1 vẫn được giữ nguyên
làm **arm đối chứng**: mọi kết luận "tham số hóa tốt hơn định hình" chỉ có giá
trị khi hai arm chạy **cùng ngân sách solver** theo `docs/03_validation_protocol.md`.

---

## 2. Vì sao ràng buộc chế tạo (FAB-\*) phải ở L0 và là HARD

### 2.1. Tối ưu không có ràng buộc chế tạo hội tụ về tiết diện không sản xuất được

Hàm mục tiêu của repo là chi phí, carbon và khối lượng vật liệu — cả ba đều
giảm đơn điệu khi bớt bê tông. Nếu chỉ có ràng buộc chịu lực, nghiệm tối ưu
luôn bị đẩy tới rìa của miền chịu lực, và ở cấp 2 cái rìa đó là:

- sườn mỏng tới mức không đổ/đầm được và không đủ lớp bảo vệ cốt thép (KC-010);
- sườn **thẳng đứng** vì mọi độ nghiêng đều là bê tông thừa — trong khi ván khuôn
  có lõi rút cần độ nghiêng tối thiểu mới tháo được (KC-013);
- bầu dưới bé nhất có thể, tới mức không còn chỗ xếp tao cáp, dù kiểm tra ứng
  suất vẫn đạt vì L1 chỉ dùng trọng tâm cáp quy đổi (KC-011);
- dầm cao nhất và ít dầm nhất, tức phiến nặng nhất và cao nhất — vượt năng lực
  cẩu hoặc tĩnh không tuyến vận chuyển (KC-012).

Đây không phải rủi ro giả định: ba trong bốn hướng trên là **hệ quả trực tiếp
của dạng hàm mục tiêu**, nên chúng sẽ xuất hiện ở mọi thuật toán tìm kiếm đủ tốt.

### 2.2. Vì sao HARD, không phải phạt mềm

Ràng buộc chế tạo cùng loại với ràng buộc an toàn: nó xác định phương án có tồn
tại được không, chứ không phải phương án đắt hay rẻ. Đưa FAB vào hàm mục tiêu
dưới dạng penalty cho phép thuật toán "mua" vi phạm bằng chi phí thấp — đúng
điều nguyên tắc bất biến số 2 của repo cấm. Vì vậy vi phạm FAB làm phương án
**INFEASIBLE**, không làm nó "tệ hơn một chút".

### 2.3. Vì sao L0, không phải sau solver

Ba lý do, theo thứ tự quan trọng:

1. **Đúng bản chất.** Không đúc được thì kết quả phân tích không có nghĩa gì —
   kiểm sau solver là kiểm nhầm thứ tự.
2. **Ngân sách.** L0 không tốn ngân sách solver. Chặn sớm giữ nguyên đơn vị so
   sánh `solver_calls` giữa các thuật toán.
3. **Shield cho EA/RL.** L0 vừa là bộ lọc rẻ vừa là safety shield: agent nhận
   tín hiệu "không chế tạo được" ngay tại bước đề xuất, không phải sau một vòng
   phân tích tốn kém.

Thứ tự trong `evaluate_candidate` giữ nguyên: schema → L0 (hình học + FAB) →
solver → independent verifier → objectives. **PASS/FAIL vẫn chỉ do verifier
quyết**; thẻ tri thức KC-010…KC-016 chỉ gợi ý hướng sửa.

---

## 3. GIỚI HẠN TRUNG THỰC của đợt này

Phần này quan trọng hơn mọi con số kết quả. Kết quả cấp 2 là **SƠ BỘ
(preliminary screening)**, không phải hồ sơ tính toán.

### 3.1. Solver vẫn là L1 line-girder

Mô hình phân tích **không đổi** trong đợt này: dầm đơn + hệ số phân bố ngang,
mặt cắt liên hợp, hoạt tải di động quét. Mọi cải tiến ở đây là về **không gian
thiết kế**, không phải về độ chính xác phân tích.

### 3.2. Những hiệu ứng chưa được mô hình — và vì sao chúng nguy hiểm hơn ở cấp 2

| Chưa xét | Vì sao đặc biệt quan trọng khi cho tự thiết kế hình dạng |
|---|---|
| Mất mát DƯL theo giai đoạn | Tiết diện mảnh hơn → ứng suất bê tông cao hơn → từ biến và mất mát lớn hơn; kết quả "đạt" ở L1 có thể trượt khi tính đủ mất mát |
| Ứng suất lúc truyền lực căng | Đây thường là tổ hợp **khống chế** kích thước bầu dưới và cấp bê tông lúc cắt cáp; bỏ qua nó là bỏ qua chính ràng buộc quyết định tiết diện mảnh |
| Co ngót – từ biến | Ảnh hưởng võng dài hạn và phân phối lại ứng suất; L1 chỉ có võng đàn hồi tức thời |
| Ổn định thành mỏng | Là ngưỡng vật lý thật của sườn mỏng; hiện chỉ có FAB-001 (ngưỡng chế tạo) đứng chắn — **hai ngưỡng này khác nhau** |
| Xoắn và biến dạng tiết diện | Dầm cao–thành mỏng nhạy xoắn hơn; cũng chưa có trong L1 |
| Bố trí cốt thép thường, vùng neo, cốt đai | FAB-003 chỉ kiểm chỗ cho **tao cáp** ở mức hình học, không thay được thiết kế cấu tạo |

### 3.3. Dữ liệu

Catalog giá và carbon vẫn là **placeholder đúng bậc độ lớn**. Vì vậy các số
`relative_cost` và `embodied_carbon` chỉ dùng để **xếp hạng tương đối trong cùng
một run**, không được trích ra ngoài như dự toán hay kiểm kê phát thải.

### 3.4. Trạng thái thẻ tri thức mới

KC-010…KC-016 đều là `DRAFT`, phần lớn có `source.kind = "expert"` — tức là
**kinh nghiệm chưa hiệu chỉnh bằng số liệu đo của repo**, không phải kết luận
thí nghiệm. Chúng dùng để định hướng tìm kiếm và để giải thích cho người đọc,
**không** dùng để kết luận khả thi. Ngưỡng số trong các thẻ phải đối chiếu lại
rule profile hiện hành trước khi hard-code ở bất kỳ đâu.

### 3.5. Gate bắt buộc trước khi dùng thật

Một phương án cấp 2 chỉ được đưa ra ngoài sau khi: (1) chạy lại ở **L2 Midas
Civil** (grillage/3D) và đối chiếu với L1; (2) kiểm tra các hiệu ứng ở §3.2 bằng
hồ sơ tính toán độc lập; (3) **kỹ sư chịu trách nhiệm phê duyệt**. Không có bước
nào trong repo thay thế được ba bước này.

---

## 4. Vì sao chưa đưa UHPC vào vòng lặp

Câu hỏi tự nhiên khi cho agent tự thiết kế tiết diện là: sao không mở luôn bê
tông siêu tính năng (UHPC) để mảnh hơn nữa? Lý do là **công thức đang dùng sẽ
sai, chứ không phải kết quả sẽ xấu**:

1. **Giới hạn kéo SERV-001** đang dùng dạng `0.5·√f'c` (MPa) theo rule profile
   BRIDGE-RULESET-V1. Đây là công thức cho bê tông thường; UHPC có cốt sợi giữ
   được **ứng suất kéo sau nứt**, nên vừa không đúng dạng vừa quá bảo thủ.
2. **Sức kháng uốn STR-001** đang dùng **khối ứng suất chữ nhật** cùng giả thiết
   khối nén nằm trong bản (MODEL-001). Biểu đồ ứng suất–biến dạng của UHPC khác
   hẳn; hệ số khối ứng suất của TCVN 11823-5 / AASHTO LRFD được hiệu chỉnh cho
   dải cường độ bê tông thường, **không phủ vùng f'c > ~120 MPa**.
3. **Sức kháng cắt STR-002** ở L1 vốn đã là mô hình đơn giản hóa; với UHPC, đóng
   góp của cốt sợi vào sức kháng cắt là cơ chế riêng, không suy ra được từ f'c.

Nói cách khác, đưa UHPC vào bằng cách thêm một dòng vào `catalogs.json` sẽ tạo
ra những con số **trông hợp lệ nhưng nằm ngoài miền hiệu lực của mô hình** — vi
phạm đúng tinh thần MODEL-001 và là loại lỗi nguy hiểm nhất trong hệ này.

Muốn mở UHPC thì phải thay **mô hình vật liệu** (quan hệ ứng suất–biến dạng, kéo
sau nứt của bê tông cốt sợi) và **mô hình tiết diện/sức kháng** tương ứng, kèm
bộ tiêu chuẩn/hướng dẫn thiết kế riêng và gold case kiểm chứng. Việc này được
ghi nhận là **hạng mục nghiên cứu riêng**, không phải một biến của cấp 2.

---

## 5. Lộ trình kế tiếp

Theo thứ tự ưu tiên; mỗi mục có tiêu chí "xong" kiểm được:

1. **Gold case cho tiết diện tham số.** Thêm case tính tay/độc lập cho hàm tính
   đặc trưng tiết diện (A, I, y_b) và cho từng rule FAB. *Xong khi:* case ở
   trạng thái `APPROVED` và chạy trong CI.
2. **Oracle grammar v2 + audit thẻ.** Quét toàn miền v2 (hoặc mẫu phân tầng nếu
   miền quá lớn), rồi cập nhật `knowledge/audits/` cho KC-010…KC-016 với
   `evidence_freshness`/`claim_audit` thật. *Xong khi:* không thẻ nào của v2 còn
   ở trạng thái `NOT_TESTED` mà vẫn được dùng để định hướng tìm kiếm.
3. **Benchmark hai arm cùng ngân sách.** v1 (catalog) so với v2 (tham số hóa),
   cùng `solver_calls`, ≥ 20 seed, theo `docs/03_validation_protocol.md`. *Xong
   khi:* báo được tỷ lệ khả thi, best/median cost, hypervolume với reference
   point khóa trước, và số solver call tới feasible đầu tiên cho cả hai arm.
4. **Bổ sung kiểm tra giai đoạn ở mức L1.5.** Ít nhất: ứng suất lúc truyền lực
   và mất mát DƯL đơn giản hóa — hai thứ trực tiếp khống chế tiết diện mảnh
   (§3.2). *Xong khi:* rule mới có gold case và không làm đổi kết quả v1.
5. **Đối chiếu L2 Midas Civil** trên mẫu phân tầng phủ dải chiều cao/bề dày mà
   v2 sinh ra, đặc biệt các phương án sát biên FAB. *Xong khi:* có bảng sai lệch
   L1–L2 và ngưỡng chấp nhận được ghi vào validation protocol.
6. **Hiệu chỉnh catalog giá/carbon** theo hồ sơ Super-T thực (gate của §7 trong
   research contract) — điều kiện bắt buộc trước khi công bố bất kỳ con số tiết
   kiệm nào.
7. **Xuất BIM Revit LOD 300** cho nhóm phương án top qua revit-mcp, để kỹ sư
   xem được hình dạng thật chứ không chỉ bảng số.
8. **Điều kiện lên cấp 3** (vật liệu mở rộng): chỉ mở sau khi mục 4 và mục 5
   hoàn tất — vì cấp 3 đúng là cấp mà thiếu mô hình giai đoạn sẽ cho kết quả sai
   một cách khó phát hiện (KC-015).
