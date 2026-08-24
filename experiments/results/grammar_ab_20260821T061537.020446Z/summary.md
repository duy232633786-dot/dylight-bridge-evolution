# A/B grammar — tiết diện định hình (v1) vs AI tự thiết kế hình dạng (v2)

**Claim ceiling: SCREENED.** Số liệu là L0 + L1 line-girder sơ bộ, KHÔNG phải thiết kế và không phải build-ready.

**Tuân thủ run matrix đã đăng ký: khớp giao thức.**

Pre-registration khóa trước: `D:\BIM  CIM\DỰ ÁN AI\DỰ ÁN NCKH 2 2026\dylight-bridge-evolution\experiments\preregistration\grammar_ab_v1_vs_v2.json` (v1.1.0)

SHA-256 pre-registration đã dùng: `fc20d3fc519a8224980a0a00e0174e43b3945d6080310e8ab881bb0724b0769d`

**Sửa đổi pre-registration đã ghi nhận:**

- v1.1.0 (2026-08-21) — SAU KHI ĐÃ THẤY KẾT QUẢ: Reviewer đối kháng chỉ ra rằng muc confounds của bản 1.0.0 TỰ NHẬN là liệt kê đầy đủ khác biệt v2 vs v1 nhưng đã BỎ SÓT một khác biệt thật: ở CÙNG ngân sách solver, các arm v2 được sàng L0 MIỄN PHÍ nhiều hơn hẳn arm v1 (không gian lớn hơn, tỷ lệ qua L0 thấp hơn). Bỏ sót này làm điều kiện 'cùng ngân sách' bị hiểu sai thành 'cùng công tìm kiếm'. Đồng thời reviewer chỉ ra runner không đối chiếu solver_calls thực tế với ngân sách đã đăng ký, nên bổ sung điều kiện vô hiệu UNEQUAL_SOLVER_BUDGET, và bổ sung ngưỡng dạng máy đọc được cho mọi invalidation condition để runner không còn hard-code ngưỡng.

> Ở CÙNG một ngân sách solver, việc cho bộ tối ưu TỰ THIẾT KẾ hình dạng mặt cắt dầm (grammar super_t_parametric_v2, 14 biến, trong đó 6 biến hình dạng) có thật sự cho phương án tốt hơn so với chỉ chọn tiết diện Super-T định hình có sẵn (grammar super_t_simple_v1, 8 biến) hay không?

Ngân sách: **600 solver calls** / (arm × thuật toán × seed) · seeds [42, 43, 44] · thuật toán ['rs', 'nsga2'] · pop NSGA-II 40

Định nghĩa ngân sách: `solver.status != NOT_RUN — một lần gọi solver chỉ được tính khi solver thực sự chạy. Proposal bị L0 loại (hình học/FAB), proposal trả về từ cache, và proposal bị chặn vì hết ngân sách ĐỀU KHÔNG tiêu ngân sách và được đếm riêng trong counters.`

HV khóa trước: ref `(5000.0, 1200.0, 250000.0)` · ideal `(0.0, 0.0, 0.0)` · MC samples 40000 · MC seed 1729

## Arm

| Arm | Grammar | Miền bị cắt | Đường tìm kiếm |
|---|---|---|---|
| `A1_v1_catalog` | `super_t_simple_v1` | `{}` | `reference_api` |
| `A2_v2_shape_only` | `super_t_parametric_v2` | `{"girder_concrete_id": ["C40", "C45", "C50"], "girder_count": [5, 6]}` | `local_restricted_domain_path` |
| `A3_v2_full` | `super_t_parametric_v2` | `{}` | `reference_api` |

## Metric theo arm (mean ± std trên mọi thuật toán × seed)

Mỗi ô ghi `(n=số run được dùng/tổng số run)`. Run không có metric (thường vì KHÔNG tìm được phương án khả thi nào) bị loại khỏi trung bình và được đánh dấu `⚠`; đọc trung bình có `⚠` như một con số đã được lọc theo hướng có lợi cho arm đó.

| Chỉ số | `A1_v1_catalog` | `A2_v2_shape_only` | `A3_v2_full` |
|---|---:|---:|---:|
| Chi phí tương đối tốt nhất | 2085.09 ± 17.0777 (n=6/6) | 2074.96 ± 65.4272 (n=6/6) | 2082.38 ± 38.7331 (n=6/6) |
| Chi phí trung vị khả thi | 2238.31 ± 59.612 (n=6/6) | 2234.75 ± 102.301 (n=6/6) | 2293.46 ± 124.522 (n=6/6) |
| P(khả thi \| solver chạy) | 0.496667 ± 0.0862753 (n=6/6) | 0.398883 ± 0.257323 (n=6/6) | 0.378333 ± 0.235389 (n=6/6) |
| Solver call tới khả thi đầu tiên | 1.66667 ± 1.0328 (n=6/6) | 6.33333 ± 8.6641 (n=6/6) | 46.3333 ± 103.281 (n=6/6) |
| HV 2D (cost×carbon) | 4.64277e+08 ± 4.08079e+06 (n=6/6) | 4.59823e+08 ± 2.5424e+07 (n=6/6) | 4.53682e+08 ± 1.89582e+07 (n=6/6) |
| HV 3D (MC, seed cố định) | 3.1345e+11 ± 3.38571e+09 (n=6/6) | 2.93856e+11 ± 2.83585e+10 (n=6/6) | 2.86575e+11 ± 2.14469e+10 (n=6/6) |
| Kích thước Pareto front | 2.5 ± 0.83666 (n=6/6) | 1.83333 ± 1.16905 (n=6/6) | 2.16667 ± 1.16905 (n=6/6) |
| Khối lượng vật liệu nhỏ nhất (t) | 528.958 ± 3.1392 (n=6/6) | 564.087 ± 26.9952 (n=6/6) | 570.897 ± 21.8661 (n=6/6) |
| Carbon hàm chứa nhỏ nhất (kgCO2e) | 90724.7 ± 523.503 (n=6/6) | 92879.9 ± 5331.66 (n=6/6) | 94541.6 ± 4534.58 (n=6/6) |
| **Run KHÔNG có phương án khả thi nào** | 0/6 | 0/6 | 0/6 |

Mọi run đều có ít nhất một phương án khả thi.

## Chi tiết từng run

`solver_calls` là ngân sách THỰC SỰ tiêu; `termination` cho biết run dừng vì hết ngân sách hay vì chạm `proposal_guard`. Hai cột này phải được đọc TRƯỚC mọi so sánh: hai run khác solver_calls thì không cùng ngân sách nên không so sánh được. `l0_checks` là số lần sàng L0 MIỄN PHÍ (không tiêu ngân sách) — chênh lệch lớn giữa các arm là confound đã đăng ký, không phải nhiễu.

| Arm | Thuật toán | Seed | Ngân sách cấp | solver_calls | termination | proposals | l0_checks | l0_rejected | cache_hits | feasible_count | best_relative_cost | median_feasible_cost | solver_conditional_feasible_rate | first_feasible_solver_call | hypervolume_2d_cost_carbon | hypervolume_3d_mc | archive_size | best_material_mass_t | best_embodied_carbon |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A1_v1_catalog | rs | 42 | 600 | 600 | budget_exhausted | 11164 | 11004 | 10404 | 160 | 264 | 2114.57 | 2293.93 | 0.44 | 1 | 457202442.9 | 309975000000.0 | 1 | 527.38 | 91547.9 |
| A1_v1_catalog | rs | 43 | 600 | 600 | budget_exhausted | 11409 | 11194 | 10594 | 215 | 254 | 2096.38 | 2294.39 | 0.4233 | 3 | 462466253.06 | 310162500000.0 | 3 | 532.55 | 90721.3 |
| A1_v1_catalog | rs | 44 | 600 | 600 | budget_exhausted | 11050 | 10887 | 10287 | 163 | 243 | 2080.75 | 2289.05 | 0.405 | 1 | 463731328.32 | 310987500000.0 | 3 | 533.42 | 91147.1 |
| A1_v1_catalog | nsga2 | 42 | 600 | 600 | budget_exhausted | 13197 | 2689 | 2089 | 10508 | 312 | 2072.94 | 2184.71 | 0.52 | 1 | 467420162.46 | 316500000000.0 | 2 | 526.8 | 90310.7 |
| A1_v1_catalog | nsga2 | 43 | 600 | 600 | budget_exhausted | 6570 | 1686 | 1086 | 4884 | 357 | 2072.94 | 2192.73 | 0.595 | 3 | 467420162.46 | 316537500000.0 | 3 | 526.8 | 90310.7 |
| A1_v1_catalog | nsga2 | 44 | 600 | 600 | budget_exhausted | 4594 | 1363 | 763 | 3231 | 358 | 2072.94 | 2175.03 | 0.5967 | 1 | 467420162.46 | 316537500000.0 | 3 | 526.8 | 90310.7 |
| A2_v2_shape_only | rs | 42 | 600 | 600 | budget_exhausted | 133150 | 133149 | 132549 | 1 | 98 | 2133.13 | 2339.35 | 0.1633 | 3 | 429237004.46 | 262462500000.0 | 4 | 588.77 | 100222.1 |
| A2_v2_shape_only | rs | 43 | 600 | 600 | budget_exhausted | 141391 | 141390 | 140790 | 1 | 100 | 2092.46 | 2312.28 | 0.1667 | 3 | 449326870.29 | 271200000000.0 | 1 | 597.03 | 95461.5 |
| A2_v2_shape_only | rs | 44 | 600 | 600 | budget_exhausted | 132238 | 132237 | 131637 | 1 | 101 | 2165.91 | 2326.69 | 0.1683 | 3 | 433851849.7 | 270825000000.0 | 1 | 578.62 | 96916.7 |
| A2_v2_shape_only | nsga2 | 42 | 600 | 600 | budget_exhausted | 2020 | 1433 | 833 | 587 | 354 | 2027.9 | 2173.28 | 0.59 | 3 | 479479382.28 | 316912500000.0 | 2 | 541.26 | 88673.2 |
| A2_v2_shape_only | nsga2 | 43 | 600 | 600 | budget_exhausted | 2079 | 1478 | 878 | 601 | 367 | 2021.39 | 2111.93 | 0.6117 | 24 | 482525884.17 | 320250000000.0 | 1 | 539.42 | 88003.0 |
| A2_v2_shape_only | nsga2 | 44 | 600 | 600 | budget_exhausted | 1883 | 1262 | 662 | 621 | 416 | 2008.95 | 2144.98 | 0.6933 | 2 | 484519616.85 | 321487500000.0 | 2 | 539.42 | 88003.0 |
| A3_v2_full | rs | 42 | 600 | 600 | budget_exhausted | 133579 | 133579 | 132979 | 0 | 108 | 2133.13 | 2420.76 | 0.18 | 2 | 429342486.12 | 268950000000.0 | 4 | 573.47 | 100222.1 |
| A3_v2_full | rs | 43 | 600 | 600 | budget_exhausted | 141033 | 141032 | 140432 | 1 | 106 | 2098.81 | 2378.99 | 0.1767 | 12 | 440365238.26 | 268312500000.0 | 3 | 591.44 | 98193.3 |
| A3_v2_full | rs | 44 | 600 | 600 | budget_exhausted | 131760 | 131760 | 131160 | 0 | 114 | 2100.47 | 2395.48 | 0.19 | 3 | 446056736.33 | 271125000000.0 | 2 | 593.05 | 96162.4 |
| A3_v2_full | nsga2 | 42 | 600 | 600 | budget_exhausted | 7046 | 2033 | 1433 | 5013 | 338 | 2082.75 | 2185.15 | 0.5633 | 1 | 462928192.12 | 303375000000.0 | 1 | 550.12 | 91313.5 |
| A3_v2_full | nsga2 | 43 | 600 | 600 | budget_exhausted | 7694 | 3249 | 2649 | 4445 | 257 | 2057.71 | 2262.76 | 0.4283 | 257 | 460873106.85 | 287437500000.0 | 2 | 577.88 | 93355.0 |
| A3_v2_full | nsga2 | 44 | 600 | 600 | budget_exhausted | 1841 | 1199 | 599 | 642 | 439 | 2021.39 | 2117.6 | 0.7317 | 3 | 482525884.17 | 320250000000.0 | 1 | 539.42 | 88003.0 |

## Đánh giá theo tiêu chí bác bỏ đã đăng ký

Ba trạng thái phán quyết: `ĐẠT` · `KHÔNG ĐẠT — KẾT QUẢ ÂM` · `VÔ HIỆU`. `VÔ HIỆU` nghĩa là KHÔNG kết luận theo hướng nào — nó không phải kết quả âm, và tuyệt đối không được đọc thành kết quả dương.

**Nội dung tiêu chí đã dùng (trích nguyên văn từ file pre-registration có SHA-256 `fc20d3fc519a8224980a0a00e0174e43b3945d6080310e8ab881bb0724b0769d`):**

- `primary_metric` = `best_relative_cost`
- `improvement_threshold_relative` = `0.02`
- `secondary_guard`: hypervolume_2d_cost_carbon của arm v2 phải KHÔNG NHỎ HƠN arm A1 ở cùng cặp (thuật toán, seed).
- `rule`: Kết luận grammar v2 tốt hơn v1 CHỈ được phát biểu khi, với arm v2 đang xét, trên TẤT CẢ seed đã đăng ký VÀ TẤT CẢ thuật toán đã chạy: (a) (best_cost_A1 - best_cost_v2) / best_cost_A1 >= 0.02, VÀ (b) hypervolume_2d_cost_carbon_v2 >= hypervolume_2d_cost_carbon_A1. Chỉ cần MỘT cặp (thuật toán, seed) không đạt là kết luận bị bác.
- `on_failure`: Ghi nhận KẾT QUẢ ÂM một cách tường minh trong summary.md và trong handoff. Không được đổi ngưỡng, không được bỏ seed, không được chọn thuật toán có lợi sau khi đã thấy số liệu.
- `attribution_rule`: Nếu A3 đạt tiêu chí mà A2 không đạt thì phần cải thiện được quy cho BÊ TÔNG CƯỜNG ĐỘ CAO (C55/C60), KHÔNG được quy cho tự do hình dạng.

Arm đối chứng: `A1_v1_catalog` · ngưỡng cải thiện `2.0%` · tuân thủ giao thức: **khớp giao thức**

### `A2_v2_shape_only` → **VÔ HIỆU**

**Lý do phán quyết là VÔ HIỆU:**
- 6/6 cặp (thuật toán, seed) dính điều kiện vô hiệu đã đăng ký

Điều kiện vô hiệu đã kích hoạt trên các cặp của arm này (gồm cả điều kiện kích hoạt ở run đối chứng của cùng cặp):
- DEGENERATE_FRONT — A1_v1_catalog_nsga2_s42: Pareto front chỉ còn 2 điểm (≤2), không được diễn giải Pareto.
- DEGENERATE_FRONT — A1_v1_catalog_rs_s42: Pareto front chỉ còn 1 điểm (≤2), không được diễn giải Pareto.
- DEGENERATE_FRONT — A2_v2_shape_only_nsga2_s42: Pareto front chỉ còn 2 điểm (≤2), không được diễn giải Pareto.
- DEGENERATE_FRONT — A2_v2_shape_only_nsga2_s43: Pareto front chỉ còn 1 điểm (≤2), không được diễn giải Pareto.
- DEGENERATE_FRONT — A2_v2_shape_only_nsga2_s44: Pareto front chỉ còn 2 điểm (≤2), không được diễn giải Pareto.
- DEGENERATE_FRONT — A2_v2_shape_only_rs_s43: Pareto front chỉ còn 1 điểm (≤2), không được diễn giải Pareto.
- DEGENERATE_FRONT — A2_v2_shape_only_rs_s44: Pareto front chỉ còn 1 điểm (≤2), không được diễn giải Pareto.

Phán quyết theo quy tắc NẾU BỎ QUA vô hiệu: `KHÔNG ĐẠT — KẾT QUẢ ÂM` — con số này chỉ để kiểm toán, KHÔNG phải kết luận và không được trích dẫn tách khỏi nhãn VÔ HIỆU.

| Thuật toán | Seed | best_cost đối chứng | best_cost arm | Cải thiện | Cost đạt | HV không giảm | Kết luận cặp |
|---|---:|---:|---:|---:|:---:|:---:|:---:|
| rs | 42 | 2114.57 | 2133.13 | -0.88% | KHÔNG | KHÔNG | VÔ HIỆU |
| rs | 43 | 2096.38 | 2092.46 | 0.19% | KHÔNG | KHÔNG | VÔ HIỆU |
| rs | 44 | 2080.75 | 2165.91 | -4.09% | KHÔNG | KHÔNG | VÔ HIỆU |
| nsga2 | 42 | 2072.94 | 2027.9 | 2.17% | ĐẠT | ĐẠT | VÔ HIỆU |
| nsga2 | 43 | 2072.94 | 2021.39 | 2.49% | ĐẠT | ĐẠT | VÔ HIỆU |
| nsga2 | 44 | 2072.94 | 2008.95 | 3.09% | ĐẠT | ĐẠT | VÔ HIỆU |

- `rs` seed 42 → VÔ HIỆU: DEGENERATE_FRONT — A1_v1_catalog_rs_s42: Pareto front chỉ còn 1 điểm (≤2), không được diễn giải Pareto.
- `rs` seed 43 → VÔ HIỆU: DEGENERATE_FRONT — A2_v2_shape_only_rs_s43: Pareto front chỉ còn 1 điểm (≤2), không được diễn giải Pareto.
- `rs` seed 44 → VÔ HIỆU: DEGENERATE_FRONT — A2_v2_shape_only_rs_s44: Pareto front chỉ còn 1 điểm (≤2), không được diễn giải Pareto.
- `nsga2` seed 42 → VÔ HIỆU: DEGENERATE_FRONT — A2_v2_shape_only_nsga2_s42: Pareto front chỉ còn 2 điểm (≤2), không được diễn giải Pareto.
- `nsga2` seed 42 → VÔ HIỆU: DEGENERATE_FRONT — A1_v1_catalog_nsga2_s42: Pareto front chỉ còn 2 điểm (≤2), không được diễn giải Pareto.
- `nsga2` seed 43 → VÔ HIỆU: DEGENERATE_FRONT — A2_v2_shape_only_nsga2_s43: Pareto front chỉ còn 1 điểm (≤2), không được diễn giải Pareto.
- `nsga2` seed 44 → VÔ HIỆU: DEGENERATE_FRONT — A2_v2_shape_only_nsga2_s44: Pareto front chỉ còn 2 điểm (≤2), không được diễn giải Pareto.

**KHÔNG KẾT LUẬN.** Theo `invalidation_conditions` đã khóa trước, so sánh này vô hiệu: không được nói grammar v2 tốt hơn, và cũng không được ghi nhận đây là kết quả âm hợp lệ. Phải xử lý nguyên nhân vô hiệu rồi chạy lại đúng run matrix.

### `A3_v2_full` → **VÔ HIỆU**

**Lý do phán quyết là VÔ HIỆU:**
- 5/6 cặp (thuật toán, seed) dính điều kiện vô hiệu đã đăng ký

Điều kiện vô hiệu đã kích hoạt trên các cặp của arm này (gồm cả điều kiện kích hoạt ở run đối chứng của cùng cặp):
- DEGENERATE_FRONT — A1_v1_catalog_nsga2_s42: Pareto front chỉ còn 2 điểm (≤2), không được diễn giải Pareto.
- DEGENERATE_FRONT — A1_v1_catalog_rs_s42: Pareto front chỉ còn 1 điểm (≤2), không được diễn giải Pareto.
- DEGENERATE_FRONT — A3_v2_full_nsga2_s42: Pareto front chỉ còn 1 điểm (≤2), không được diễn giải Pareto.
- DEGENERATE_FRONT — A3_v2_full_nsga2_s43: Pareto front chỉ còn 2 điểm (≤2), không được diễn giải Pareto.
- DEGENERATE_FRONT — A3_v2_full_nsga2_s44: Pareto front chỉ còn 1 điểm (≤2), không được diễn giải Pareto.
- DEGENERATE_FRONT — A3_v2_full_rs_s44: Pareto front chỉ còn 2 điểm (≤2), không được diễn giải Pareto.

Phán quyết theo quy tắc NẾU BỎ QUA vô hiệu: `KHÔNG ĐẠT — KẾT QUẢ ÂM` — con số này chỉ để kiểm toán, KHÔNG phải kết luận và không được trích dẫn tách khỏi nhãn VÔ HIỆU.

| Thuật toán | Seed | best_cost đối chứng | best_cost arm | Cải thiện | Cost đạt | HV không giảm | Kết luận cặp |
|---|---:|---:|---:|---:|:---:|:---:|:---:|
| rs | 42 | 2114.57 | 2133.13 | -0.88% | KHÔNG | KHÔNG | VÔ HIỆU |
| rs | 43 | 2096.38 | 2098.81 | -0.12% | KHÔNG | KHÔNG | KHÔNG |
| rs | 44 | 2080.75 | 2100.47 | -0.95% | KHÔNG | KHÔNG | VÔ HIỆU |
| nsga2 | 42 | 2072.94 | 2082.75 | -0.47% | KHÔNG | KHÔNG | VÔ HIỆU |
| nsga2 | 43 | 2072.94 | 2057.71 | 0.73% | KHÔNG | KHÔNG | VÔ HIỆU |
| nsga2 | 44 | 2072.94 | 2021.39 | 2.49% | ĐẠT | ĐẠT | VÔ HIỆU |

- `rs` seed 42 → VÔ HIỆU: DEGENERATE_FRONT — A1_v1_catalog_rs_s42: Pareto front chỉ còn 1 điểm (≤2), không được diễn giải Pareto.
- `rs` seed 44 → VÔ HIỆU: DEGENERATE_FRONT — A3_v2_full_rs_s44: Pareto front chỉ còn 2 điểm (≤2), không được diễn giải Pareto.
- `nsga2` seed 42 → VÔ HIỆU: DEGENERATE_FRONT — A3_v2_full_nsga2_s42: Pareto front chỉ còn 1 điểm (≤2), không được diễn giải Pareto.
- `nsga2` seed 42 → VÔ HIỆU: DEGENERATE_FRONT — A1_v1_catalog_nsga2_s42: Pareto front chỉ còn 2 điểm (≤2), không được diễn giải Pareto.
- `nsga2` seed 43 → VÔ HIỆU: DEGENERATE_FRONT — A3_v2_full_nsga2_s43: Pareto front chỉ còn 2 điểm (≤2), không được diễn giải Pareto.
- `nsga2` seed 44 → VÔ HIỆU: DEGENERATE_FRONT — A3_v2_full_nsga2_s44: Pareto front chỉ còn 1 điểm (≤2), không được diễn giải Pareto.

**KHÔNG KẾT LUẬN.** Theo `invalidation_conditions` đã khóa trước, so sánh này vô hiệu: không được nói grammar v2 tốt hơn, và cũng không được ghi nhận đây là kết quả âm hợp lệ. Phải xử lý nguyên nhân vô hiệu rồi chạy lại đúng run matrix.

Quy tắc quy kết: Nếu A3 đạt tiêu chí mà A2 không đạt thì phần cải thiện được quy cho BÊ TÔNG CƯỜNG ĐỘ CAO (C55/C60), KHÔNG được quy cho tự do hình dạng.

## Cảnh báo suy biến

Hệ số tương quan Pearson giữa các mục tiêu, tính trên record khả thi của từng run (|r| ≥ 0.999 ⇒ mục tiêu suy biến, hypervolume và Pareto front mất ý nghĩa đa mục tiêu). Cần tối thiểu **3 mẫu khả thi**; dưới ngưỡng đó ghi `không đủ mẫu` và KHÔNG bật cờ suy biến — với đúng 2 điểm thì |r| luôn bằng 1 theo định nghĩa nên cờ sẽ bật giả.

| Arm | Thuật toán | Seed | Pareto front | Mẫu khả thi | r(cost,mass) | r(cost,carbon) | r(mass,carbon) |
|---|---|---:|---:|---:|---:|---:|---:|
| A1_v1_catalog | rs | 42 | 1 | 264 | 0.827264 | 0.935541 | 0.854687 |
| A1_v1_catalog | rs | 43 | 3 | 254 | 0.789011 | 0.917048 | 0.86977 |
| A1_v1_catalog | rs | 44 | 3 | 243 | 0.79468 | 0.916447 | 0.863599 |
| A1_v1_catalog | nsga2 | 42 | 2 | 312 | 0.617276 | 0.895602 | 0.785508 |
| A1_v1_catalog | nsga2 | 43 | 3 | 357 | 0.720309 | 0.945452 | 0.813347 |
| A1_v1_catalog | nsga2 | 44 | 3 | 358 | 0.623018 | 0.944123 | 0.760187 |
| A2_v2_shape_only | rs | 42 | 4 | 98 | 0.771729 | 0.929013 | 0.816806 |
| A2_v2_shape_only | rs | 43 | 1 | 100 | 0.73834 | 0.899804 | 0.819268 |
| A2_v2_shape_only | rs | 44 | 1 | 101 | 0.751086 | 0.915387 | 0.807451 |
| A2_v2_shape_only | nsga2 | 42 | 2 | 354 | 0.7288 | 0.962455 | 0.853884 |
| A2_v2_shape_only | nsga2 | 43 | 1 | 367 | 0.879534 | 0.996014 | 0.910666 |
| A2_v2_shape_only | nsga2 | 44 | 2 | 416 | 0.712996 | 0.959321 | 0.844598 |
| A3_v2_full | rs | 42 | 4 | 108 | 0.724324 | 0.921227 | 0.674559 |
| A3_v2_full | rs | 43 | 3 | 106 | 0.643491 | 0.910749 | 0.656449 |
| A3_v2_full | rs | 44 | 2 | 114 | 0.799409 | 0.954372 | 0.764168 |
| A3_v2_full | nsga2 | 42 | 1 | 338 | 0.725614 | 0.994854 | 0.777508 |
| A3_v2_full | nsga2 | 43 | 2 | 257 | 0.69566 | 0.964555 | 0.793103 |
| A3_v2_full | nsga2 | 44 | 1 | 439 | 0.687894 | 0.984908 | 0.754973 |

**Điều kiện làm so sánh VÔ HIỆU đã kích hoạt:**
- DEGENERATE_FRONT — A1_v1_catalog_rs_s42: Pareto front chỉ còn 1 điểm (≤2), không được diễn giải Pareto.
- DEGENERATE_FRONT — A1_v1_catalog_nsga2_s42: Pareto front chỉ còn 2 điểm (≤2), không được diễn giải Pareto.
- DEGENERATE_FRONT — A2_v2_shape_only_rs_s43: Pareto front chỉ còn 1 điểm (≤2), không được diễn giải Pareto.
- DEGENERATE_FRONT — A2_v2_shape_only_rs_s44: Pareto front chỉ còn 1 điểm (≤2), không được diễn giải Pareto.
- DEGENERATE_FRONT — A2_v2_shape_only_nsga2_s42: Pareto front chỉ còn 2 điểm (≤2), không được diễn giải Pareto.
- DEGENERATE_FRONT — A2_v2_shape_only_nsga2_s43: Pareto front chỉ còn 1 điểm (≤2), không được diễn giải Pareto.
- DEGENERATE_FRONT — A2_v2_shape_only_nsga2_s44: Pareto front chỉ còn 2 điểm (≤2), không được diễn giải Pareto.
- DEGENERATE_FRONT — A3_v2_full_rs_s44: Pareto front chỉ còn 2 điểm (≤2), không được diễn giải Pareto.
- DEGENERATE_FRONT — A3_v2_full_nsga2_s42: Pareto front chỉ còn 1 điểm (≤2), không được diễn giải Pareto.
- DEGENERATE_FRONT — A3_v2_full_nsga2_s43: Pareto front chỉ còn 2 điểm (≤2), không được diễn giải Pareto.
- DEGENERATE_FRONT — A3_v2_full_nsga2_s44: Pareto front chỉ còn 1 điểm (≤2), không được diễn giải Pareto.

So sánh giữa các arm ở trên KHÔNG được diễn giải như bằng chứng cho tới khi các điều kiện này được xử lý.

### Trạng thái từng điều kiện vô hiệu đã đăng ký

Bảng này liệt kê TẤT CẢ điều kiện trong pre-registration, kể cả điều kiện runner CHƯA đánh giá tự động được — im lặng về chúng sẽ khiến người đọc tưởng cả bộ điều kiện đã được kiểm.

| Điều kiện | Ngưỡng (từ pre-registration) | Trạng thái | Ghi chú |
|---|---|---|---|
| `DEGENERATE_FRONT` | `{"archive_size_at_most": 2}` | KÍCH HOẠT (11 run) | `A1_v1_catalog_nsga2_s42`, `A1_v1_catalog_rs_s42`, `A2_v2_shape_only_nsga2_s42`, `A2_v2_shape_only_nsga2_s43`, `A2_v2_shape_only_nsga2_s44`, `A2_v2_shape_only_rs_s43`, `A2_v2_shape_only_rs_s44`, `A3_v2_full_nsga2_s42`, `A3_v2_full_nsga2_s43`, `A3_v2_full_nsga2_s44`, `A3_v2_full_rs_s44` |
| `NO_FEASIBLE` | `{"feasible_count_at_most": 0}` | không kích hoạt | — |
| `FEASIBLE_RATE_TOO_LOW` | `{"solver_conditional_feasible_rate_below": 0.05}` | không kích hoạt | — |
| `OBJECTIVES_COLLINEAR` | `{"abs_pearson_at_least": 0.999, "min_sample_size": 3}` | không kích hoạt | — |
| `UNEQUAL_SOLVER_BUDGET` | `{"solver_calls_must_equal": "budget_per_run_of_this_run"}` | không kích hoạt | — |
| `HV_DOMAIN_VIOLATION` | `{"ideal_3d": [0.0, 0.0, 0.0], "reference_3d": [5000.0, 1200.0, 250000.0]}` | CHƯA ĐƯỢC ĐÁNH GIÁ TỰ ĐỘNG | KHÔNG xuất hiện dưới dạng cờ trong summary.md. Điều kiện này được thi hành bằng cách DỪNG chương trình: experiments/run_baseline.py::_assert_hv_domain ném ValueError ngay trong add_hypervolume, nên run vi phạm sẽ không sinh ra báo cáo nào. Một summary.md tồn tại chỉ chứng minh 'không phát hiện vi phạm', không chứng minh gì thêm. |
| `EQUIVALENCE_GUARD_FAILED` | `—` | CHƯA ĐƯỢC ĐÁNH GIÁ TỰ ĐỘNG | CHƯA ĐƯỢC ĐÁNH GIÁ TỰ ĐỘNG trong runner. Chỉ được kiểm bởi tests/test_grammar_ab_experiment.py::test_restricted_path_matches_reference_when_unrestricted, chạy TÁCH RỜI khỏi thí nghiệm. Báo cáo của một run KHÔNG chứng minh điều kiện này đã được kiểm cho chính run đó. |

**Chưa được đánh giá tự động trong lần chạy này: `HV_DOMAIN_VIOLATION`, `EQUIVALENCE_GUARD_FAILED`.** Báo cáo này KHÔNG chứng minh các điều kiện đó không xảy ra.

## Confound đã đăng ký (không bóc tách được ở thí nghiệm này)

- girder_count: A1 tìm trên {5, 6, 7, 8} còn A2/A3 chỉ có {5, 6}. Không bóc tách được vì miền v1 bị đóng băng và miền v2 do file grammar quy định; muốn bóc tách phải có arm thứ tư (v1 giới hạn girder_count {5,6}) — NGOÀI phạm vi thí nghiệm này.
- diaphragm_layout_id: A1 có thêm lựa chọn DG-END-ONLY mà A2/A3 không có.
- Rule profile: V2 áp thêm FAB-001..FAB-007 nên arm v2 chịu ràng buộc HARD chặt hơn arm v1. Đây là confound cố hữu và TUYỆT ĐỐI KHÔNG được nới để arm v2 thắng (AGENTS.md: ràng buộc chế tạo là hard gate).
- Số chiều: cùng ngân sách solver nhưng không gian v2 lớn hơn nhiều bậc, nên một kết quả âm có thể mang nghĩa v2 cần nhiều ngân sách hơn chứ không nhất thiết là tự do hình dạng vô ích. Kết luận phải nêu giới hạn này.
- Marker ST-PARAM: v2 không thể chọn tiết diện định hình, nên A2/A3 không bao trùm (superset) A1 về mặt không gian phương án.
- BẤT ĐỐI XỨNG SÀNG L0 MIỄN PHÍ (bổ sung ở 1.1.0, sau khi thấy kết quả): ngân sách chỉ đếm solver call, nên số lần sàng L0 là MIỄN PHÍ và KHÔNG bị giới hạn. Ở cùng 600 solver call, arm v2 chạy random search phải sàng L0 nhiều gấp ~12,3 lần arm v1 (tỷ lệ qua L0 ~0,44% so với ~5,44%). 'Cùng ngân sách solver' vì thế KHÔNG có nghĩa 'cùng công tìm kiếm': arm v2 được xem nhiều ứng viên hơn hẳn ở tầng hình học/chế tạo trước khi tiêu ngân sách. Không bóc tách được trong thí nghiệm này vì bản thân định nghĩa ngân sách (solver.status != NOT_RUN) đã khóa trước; muốn bóc tách phải có một thí nghiệm thứ hai khóa thêm ngân sách proposal/L0, NGOÀI phạm vi thí nghiệm này. Hệ quả diễn giải: một kết quả DƯƠNG cho v2 có thể một phần đến từ việc v2 được sàng miễn phí nhiều hơn, còn một kết quả ÂM cho v2 thì KHÔNG được giải thích bằng confound này (nó có lợi cho v2, không có hại).

### Sàng L0 miễn phí trong CHÍNH lần chạy này

L0 không tiêu ngân sách solver, nên số lần sàng là công tìm kiếm được cấp thêm MIỄN PHÍ. Ở cùng số solver call, arm sàng nhiều hơn được xem nhiều ứng viên hơn.

| Arm | Thuật toán | l0_checks | l0_rejected | Tỷ lệ qua L0 |
|---|---|---:|---:|---:|
| A1_v1_catalog | rs | 33085 | 31285 | 5.4405% |
| A1_v1_catalog | nsga2 | 5738 | 3938 | 31.3698% |
| A2_v2_shape_only | rs | 406776 | 404976 | 0.4425% |
| A2_v2_shape_only | nsga2 | 4173 | 2373 | 43.1344% |
| A3_v2_full | rs | 406371 | 404571 | 0.4429% |
| A3_v2_full | nsga2 | 6481 | 4681 | 27.7735% |

_Toàn bộ số liệu của thí nghiệm này sinh từ L0 (hình học + chế tạo) và L1 line-girder sơ bộ của solver BUILTIN_L1. Đây là SÀNG LỌC, không phải thiết kế: không được gọi bất kỳ phương án nào là thiết kế thật, build-ready, NUMERICALLY_VERIFIED hay ENGINEERING_CANDIDATE. Muốn lên cấp phải có artifact L2/L3 thật (MARP-1.0 muc Cap do claim, PG-1.0 G2-G4)._

_Tuân thủ run matrix đã đăng ký: **khớp giao thức**._