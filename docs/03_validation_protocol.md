# 03 — Validation & Benchmark Protocol

Phiên bản: `VP-1.0` — 2026-08-20.

Tài liệu này là gate bắt buộc trước khi diễn giải kết quả như bằng chứng khoa
học hoặc dùng một phương án cho quyết định kỹ thuật. Kết quả L1 hiện tại chỉ là
**preliminary screening**; không thay thế hồ sơ tính toán do kỹ sư chịu trách
nhiệm phê duyệt.

## 1. Đơn vị ngân sách

Mỗi run phải báo riêng:

1. `proposal_count`: số gene thuật toán đã đề xuất, kể cả cache hit;
2. `unique_evaluation_count`: số thiết kế duy nhất đi qua contract;
3. `l0_rejected_count`: số thiết kế dừng trước solver;
4. `solver_calls`: số lần solver thật sự được mở, gồm cả NOT_CONVERGED;
5. `cache_hits`: số đề xuất tái sử dụng kết quả;
6. wall-clock time và cấu hình máy.

Ngân sách so sánh chính là `solver_calls`. Mọi thuật toán được dùng cùng một
L0 prefilter và cùng các mục tiêu giải tích rẻ. Nếu một phương pháp dùng thêm
pool/proposal miễn phí, phải báo `proposal_count` và thực hiện ablation theo
ngân sách proposal.

## 2. Oracle và metric tối ưu

Với grammar MVP hữu hạn, phải quét toàn miền L1 để tạo oracle trước khi chạy
benchmark. Mỗi thuật toán báo:

- xác suất tìm đúng tập Pareto oracle;
- optimality gap của best cost;
- IGD+/epsilon hoặc một metric khoảng cách tới oracle;
- hypervolume với reference point **khóa trước thí nghiệm**, không suy ra từ
  kết quả của các thuật toán tham gia;
- số solver call tới feasible đầu tiên và tới optimum/Pareto oracle.

Nếu oracle chỉ có một điểm, kết quả phải được mô tả là single-optimum search,
không được diễn giải là khám phá trade-off đa mục tiêu.

## 3. Thiết kế thống kê

- Tối thiểu 20 seed độc lập cho báo cáo chính; seed và hyperparameter khóa
  trước khi chạy.
- Báo median, IQR, mean, SD và confidence interval; dùng paired analysis khi
  các thuật toán dùng chung seed/problem instance.
- Tách tuning khỏi evaluation. Surrogate phải có calibration/held-out test;
  RL phải freeze policy rồi đánh giá trên điểm khởi tạo/problem instance chưa
  dùng để cập nhật trọng số.
- Bắt buộc có ablation: NSGA-II ± L0 prefilter, surrogate ± model, RL ± shield
  (nhánh không shield vẫn phải giữ hard safety gate trước khi đề cử phương án).

## 4. Gate kiểm chứng vật lý

Trước publication/engineering use:

1. Catalog tiết diện, vật liệu, giá và carbon có nguồn/version được kỹ sư duyệt.
2. Gold cases có kết quả tính tay hoặc hồ sơ phần mềm độc lập và trạng thái
   `APPROVED`.
3. L1 được đối chiếu với Midas L2 trên một mẫu phân tầng bao phủ section,
   spacing, slab, prestress và các candidate gần biên.
4. Báo sai số từng response và ma trận false PASS/false FAIL; false PASS chưa
   được kỹ sư xử lý là publication blocker.
5. Phương án cuối phải qua L2, kiểm tra giai đoạn, mất mát DƯL, co ngót–từ biến,
   dầm biên/xoắn/ngang và các limit state nằm ngoài L1.

## 5. Artifact bắt buộc

Mỗi run lưu config, seed, package/dependency version, source revision, fixed
reference point, full history (gene + full input hash + status + violations),
Pareto archive, model/policy nếu có và checksum của catalog/grammar/ruleset.
Không ghi đè một run cũ; thư mục run phải có ID bất biến theo config + thời gian.

## 6. Tuyên bố được phép

Khi chưa qua toàn bộ gate trên, chỉ được tuyên bố:

> Prototype deterministic, provenance-aware, safety-constrained dùng solver L1
> placeholder để sàng lọc một instance cầu Super-T trong phạm vi grammar MVP.

Không được tuyên bố giảm chi phí/carbon thực tế, RL vượt trội, thiết kế đạt tiêu
chuẩn cuối cùng hoặc hệ thống AI tự chủ thay thế phê duyệt kỹ sư.
