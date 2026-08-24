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

## 5b. Kết quả đợt A/B đầu tiên (BRD-009) — và điều KHÔNG được kết luận từ nó

Thí nghiệm đã chạy: `experiments/run_grammar_ab.py`, pre-registration khóa trước
tại `experiments/preregistration/grammar_ab_v1_vs_v2.json`, kết quả tại
`experiments/results/grammar_ab_20260821T061537.020446Z/` (run chính thức, chạy bằng
runner đã sửa và **khớp run matrix đã đăng ký**).
Cấu hình: 3 arm × 2 thuật toán (Random Search, NSGA-II) × 3 seed × **600 lần gọi
solver** mỗi lần chạy, cùng prefilter L0, cùng reference point hypervolume khai
báo trước trong `experiments/run_baseline.py`.

### 5b.1. Phán quyết theo tiêu chí đã đăng ký: **VÔ HIỆU** (không kết luận được)

Cả hai arm v2 đều nhận phán quyết **VÔ HIỆU**, không phải "kết quả âm". Phân biệt
này quan trọng: *âm* nghĩa là đã kiểm và bác bỏ; *vô hiệu* nghĩa là **không kiểm
được theo hướng nào**, và tuyệt đối không được đọc thành kết quả dương.

Lý do: điều kiện vô hiệu `DEGENERATE_FRONT` đã đăng ký trước kích hoạt ở 7/18 lần
chạy — Pareto front co về 1–2 điểm, trong khi tiêu chí quyết định lại dùng
hypervolume làm điều kiện phụ. Hypervolume của một front suy biến không mang
nghĩa đa mục tiêu, nên vế thứ hai của tiêu chí mất hiệu lực.

Ngoài ra, vế thứ nhất (cải thiện ≥ 2% trên **mọi** seed VÀ **mọi** thuật toán)
cũng không đạt, vì Random Search thua rõ trên không gian v2 — không gian đó lớn
**41,9 tỷ tổ hợp**, gấp ~126.000 lần không gian v1 (331.776 tổ hợp), nên lấy mẫu
đều ở ngân sách 600 là quá thưa.

> **Ghi chú lịch sử (bài học quy trình).** Bản runner đầu tiên xuất ra phán quyết
> "KHÔNG ĐẠT — KẾT QUẢ ÂM" cho chính bộ số liệu này, vì nó **không áp dụng chính
> các điều kiện vô hiệu mà pre-registration đã khai**. Reviewer đối kháng phát
> hiện lỗi đó; sau khi sửa, cùng dữ liệu cho phán quyết đúng là VÔ HIỆU. Kết luận
> chỉ đáng tin khi công cụ sinh ra nó cũng bị kiểm.

Điều kiện "cùng ngân sách solver" đã kiểm chứng được trong artifact: **cả 18 lần
chạy đều tiêu đúng 600 lần gọi solver**.

### 5b.2. Quan sát phụ, mạnh hơn mức "thắng một lần chạy"

Với NSGA-II, arm **A2** (tham số hóa hình dạng, **cùng dải bê tông C40–C50 như
v1**) cho chi phí tương đối **2027,90 / 2021,39 / 2008,95** trên ba seed 42/43/44.

Mốc so sánh không phải kết quả của một lần tìm kiếm may mắn, mà là **tối ưu toàn
cục đã chứng minh bằng vét cạn** toàn bộ không gian v1: **2072,94**
(`experiments/results/exhaustive_20260820T154139.606695Z/`, 331.776 tổ hợp,
18.036 hợp lệ L0, 7.572 khả thi). NSGA-II trên arm A1 tái lập đúng con số này ở
cả ba seed, nên arm đối chứng đã chạm trần thật của nó — công cụ đối chiếu độc
lập `experiments/compare_to_oracle.py` xác nhận `best_cost_gap = 0,00%` và với
seed 43/44 còn `exact_oracle_front = True`, `oracle_recall = 1,0` (tái lập ĐÚNG
toàn bộ Pareto front thật). Trên nền đó, arm A2 cho `gap = −2,17 / −2,49 /
−3,09%` và `hv_2d_ratio > 1` ở cả ba seed. Chênh lệch: **2,2–3,1%**.

Cơ chế kỹ thuật của phương án tốt nhất (`BT-0d93101c48b28dca`, đã kiểm chứng lại
độc lập: `feasible=True`, không vi phạm, `max_utilization = 0,894`):

| Đại lượng | AI tự thiết kế | ST-1750 định hình | Chênh |
|---|---:|---:|---:|
| Chiều cao | 2,000 m | 1,750 m | **+14,3%** |
| Diện tích | 0,6930 m² | 0,6490 m² | +6,8% |
| Mô men quán tính | 0,3683 m⁴ | 0,2260 m⁴ | **+63,0%** |
| Số tao cáp | PT-34 | PT-42 | **−8 tao** |

Nghĩa là agent mua độ cứng bằng **chiều cao** thay vì bằng **vật liệu**, rồi
tiêu khoản dư đó vào việc cắt bớt cáp DƯL — cấu phần đắt nhất. Phương án nằm
**đúng trên biên chế tạo**: sườn 100 mm = ngưỡng FAB-001, cánh trên 90 mm =
ngưỡng FAB-002. Đây là xác nhận thực nghiệm cho §2.1: tối ưu luôn bị đẩy tới rìa,
và nhóm FAB-\* chính là thứ giữ nó lại trong vùng sản xuất được.

### 5b.3. Quy tắc quy kết đã đăng ký đã kích hoạt

Arm **A3** (v2 đầy đủ, có thêm C55/C60) **kém hơn A2**. Theo quy tắc khóa trước,
điều đó loại trừ cách giải thích "cải thiện là nhờ bê tông cường độ cao": phần
chênh lệch không quy được cho vật liệu.

### 5b.4. Điều KHÔNG được kết luận

1. **Không** được nói "grammar v2 tốt hơn v1" — tiêu chí đăng ký trước phán
   VÔ HIỆU, và vô hiệu không phải là dương.
2. **Không** được diễn giải hypervolume hay hình dạng Pareto: cờ
   `DEGENERATE_FRONT` bật ở 11/18 lần chạy (front co về ≤ 2 điểm), và ba mục tiêu
   tương quan rất mạnh trên toàn miền v1 (cost–carbon 0,93; mass–carbon 0,86;
   cost–mass 0,80). Bài toán đang gần đơn mục tiêu.
3. **Không** được coi 2008,95 là "tiết kiệm 3%" ngoài đời: đơn giá và hệ số
   carbon trong `catalogs.json` vẫn là placeholder (gate §7 research contract).
4. **Không** được gọi phương án này là thiết kế. Claim ceiling là **SCREENED**:
   L0 + L1 line-girder. Tiết diện mảnh sát biên FAB chính là loại phương án mà
   L1 kém tin cậy nhất (§3.2) — phải qua L2 Midas trước khi bàn tiếp.
5. Confound còn lại chưa bóc tách: A1 tìm trên `girder_count ∈ {5,6,7,8}` còn
   A2/A3 chỉ có `{5,6}`; A1 có thêm `DG-END-ONLY`; arm v2 chịu thêm ràng buộc
   HARD FAB-\*; và ở cùng ngân sách solver, arm v2 phải sàng L0 nhiều hơn hẳn.

### 5b.5. Việc phải làm trước khi kết quả này được trích dẫn

- Chạy lại với **≥ 20 seed** (đợt này mới 3) theo đúng mục 3 của lộ trình.
- Thêm arm thứ tư: v1 giới hạn `girder_count ∈ {5,6}` để đóng nốt confound.
- Thiết kế lại tiêu chí đăng ký cho **lần sau**: yêu cầu "mọi thuật toán đều
  thắng" đang trộn hai câu hỏi khác nhau — *không gian thiết kế có tốt hơn không*
  và *thuật toán có đủ mạnh để khai thác không gian đó không*. Việc tách hai câu
  hỏi phải được pre-register **trước** khi chạy, không được sửa tiêu chí của đợt
  này sau khi đã thấy số liệu.

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
3. **Benchmark hai arm cùng ngân sách.** *(đã chạy đợt đầu — xem §5b; còn
   thiếu số seed và arm khử confound)* v1 (catalog) so với v2 (tham số hóa),
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
