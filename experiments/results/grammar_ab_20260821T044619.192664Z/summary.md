# A/B grammar — tiết diện định hình (v1) vs AI tự thiết kế hình dạng (v2)

**Claim ceiling: SCREENED.** Số liệu là L0 + L1 line-girder sơ bộ, KHÔNG phải thiết kế và không phải build-ready.

Pre-registration khóa trước: `D:\BIM  CIM\DỰ ÁN AI\DỰ ÁN NCKH 2 2026\dylight-bridge-evolution\experiments\preregistration\grammar_ab_v1_vs_v2.json` (v1.0.0)

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

| Chỉ số | `A1_v1_catalog` | `A2_v2_shape_only` | `A3_v2_full` |
|---|---:|---:|---:|
| Chi phí tương đối tốt nhất | 2085.09 ± 17.0777 | 2074.96 ± 65.4272 | 2082.38 ± 38.7331 |
| Chi phí trung vị khả thi | 2238.31 ± 59.612 | 2234.75 ± 102.301 | 2293.46 ± 124.522 |
| P(khả thi \| solver chạy) | 0.496667 ± 0.0862753 | 0.398883 ± 0.257323 | 0.378333 ± 0.235389 |
| Solver call tới khả thi đầu tiên | 1.66667 ± 1.0328 | 6.33333 ± 8.6641 | 46.3333 ± 103.281 |
| HV 2D (cost×carbon) | 4.64277e+08 ± 4.08079e+06 | 4.59823e+08 ± 2.5424e+07 | 4.53682e+08 ± 1.89582e+07 |
| HV 3D (MC, seed cố định) | 3.1345e+11 ± 3.38571e+09 | 2.93856e+11 ± 2.83585e+10 | 2.86575e+11 ± 2.14469e+10 |
| Kích thước Pareto front | 2.5 ± 0.83666 | 1.83333 ± 1.16905 | 2.16667 ± 1.16905 |
| Khối lượng vật liệu nhỏ nhất (t) | 528.958 ± 3.1392 | 564.087 ± 26.9952 | 570.897 ± 21.8661 |
| Carbon hàm chứa nhỏ nhất (kgCO2e) | 90724.7 ± 523.503 | 92879.9 ± 5331.66 | 94541.6 ± 4534.58 |

## Chi tiết từng run

| Arm | Thuật toán | Seed | best_relative_cost | median_feasible_cost | solver_conditional_feasible_rate | first_feasible_solver_call | hypervolume_2d_cost_carbon | hypervolume_3d_mc | archive_size | best_material_mass_t | best_embodied_carbon |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A1_v1_catalog | rs | 42 | 2114.57 | 2293.93 | 0.44 | 1 | 457202442.9 | 309975000000.0 | 1 | 527.38 | 91547.9 |
| A1_v1_catalog | rs | 43 | 2096.38 | 2294.39 | 0.4233 | 3 | 462466253.06 | 310162500000.0 | 3 | 532.55 | 90721.3 |
| A1_v1_catalog | rs | 44 | 2080.75 | 2289.05 | 0.405 | 1 | 463731328.32 | 310987500000.0 | 3 | 533.42 | 91147.1 |
| A1_v1_catalog | nsga2 | 42 | 2072.94 | 2184.71 | 0.52 | 1 | 467420162.46 | 316500000000.0 | 2 | 526.8 | 90310.7 |
| A1_v1_catalog | nsga2 | 43 | 2072.94 | 2192.73 | 0.595 | 3 | 467420162.46 | 316537500000.0 | 3 | 526.8 | 90310.7 |
| A1_v1_catalog | nsga2 | 44 | 2072.94 | 2175.03 | 0.5967 | 1 | 467420162.46 | 316537500000.0 | 3 | 526.8 | 90310.7 |
| A2_v2_shape_only | rs | 42 | 2133.13 | 2339.35 | 0.1633 | 3 | 429237004.46 | 262462500000.0 | 4 | 588.77 | 100222.1 |
| A2_v2_shape_only | rs | 43 | 2092.46 | 2312.28 | 0.1667 | 3 | 449326870.29 | 271200000000.0 | 1 | 597.03 | 95461.5 |
| A2_v2_shape_only | rs | 44 | 2165.91 | 2326.69 | 0.1683 | 3 | 433851849.7 | 270825000000.0 | 1 | 578.62 | 96916.7 |
| A2_v2_shape_only | nsga2 | 42 | 2027.9 | 2173.28 | 0.59 | 3 | 479479382.28 | 316912500000.0 | 2 | 541.26 | 88673.2 |
| A2_v2_shape_only | nsga2 | 43 | 2021.39 | 2111.93 | 0.6117 | 24 | 482525884.17 | 320250000000.0 | 1 | 539.42 | 88003.0 |
| A2_v2_shape_only | nsga2 | 44 | 2008.95 | 2144.98 | 0.6933 | 2 | 484519616.85 | 321487500000.0 | 2 | 539.42 | 88003.0 |
| A3_v2_full | rs | 42 | 2133.13 | 2420.76 | 0.18 | 2 | 429342486.12 | 268950000000.0 | 4 | 573.47 | 100222.1 |
| A3_v2_full | rs | 43 | 2098.81 | 2378.99 | 0.1767 | 12 | 440365238.26 | 268312500000.0 | 3 | 591.44 | 98193.3 |
| A3_v2_full | rs | 44 | 2100.47 | 2395.48 | 0.19 | 3 | 446056736.33 | 271125000000.0 | 2 | 593.05 | 96162.4 |
| A3_v2_full | nsga2 | 42 | 2082.75 | 2185.15 | 0.5633 | 1 | 462928192.12 | 303375000000.0 | 1 | 550.12 | 91313.5 |
| A3_v2_full | nsga2 | 43 | 2057.71 | 2262.76 | 0.4283 | 257 | 460873106.85 | 287437500000.0 | 2 | 577.88 | 93355.0 |
| A3_v2_full | nsga2 | 44 | 2021.39 | 2117.6 | 0.7317 | 3 | 482525884.17 | 320250000000.0 | 1 | 539.42 | 88003.0 |

## Đánh giá theo tiêu chí bác bỏ đã đăng ký

Tiêu chí (khóa trước): Kết luận grammar v2 tốt hơn v1 CHỈ được phát biểu khi, với arm v2 đang xét, trên TẤT CẢ seed đã đăng ký VÀ TẤT CẢ thuật toán đã chạy: (a) (best_cost_A1 - best_cost_v2) / best_cost_A1 >= 0.02, VÀ (b) hypervolume_2d_cost_carbon_v2 >= hypervolume_2d_cost_carbon_A1. Chỉ cần MỘT cặp (thuật toán, seed) không đạt là kết luận bị bác.

Arm đối chứng: `A1_v1_catalog` · ngưỡng cải thiện `2.0%`

### `A2_v2_shape_only` → **KHÔNG ĐẠT — KẾT QUẢ ÂM**

| Thuật toán | Seed | best_cost đối chứng | best_cost arm | Cải thiện | Cost đạt | HV không giảm | Kết luận cặp |
|---|---:|---:|---:|---:|:---:|:---:|:---:|
| rs | 42 | 2114.57 | 2133.13 | -0.88% | KHÔNG | KHÔNG | KHÔNG |
| rs | 43 | 2096.38 | 2092.46 | 0.19% | KHÔNG | KHÔNG | KHÔNG |
| rs | 44 | 2080.75 | 2165.91 | -4.09% | KHÔNG | KHÔNG | KHÔNG |
| nsga2 | 42 | 2072.94 | 2027.9 | 2.17% | ĐẠT | ĐẠT | ĐẠT |
| nsga2 | 43 | 2072.94 | 2021.39 | 2.49% | ĐẠT | ĐẠT | ĐẠT |
| nsga2 | 44 | 2072.94 | 2008.95 | 3.09% | ĐẠT | ĐẠT | ĐẠT |

**KẾT QUẢ ÂM được ghi nhận.** Theo pre-registration, không đạt đồng thời hai điều kiện trên MỌI cặp (thuật toán, seed) thì không được phát biểu rằng grammar này tốt hơn đối chứng. Không được đổi ngưỡng, bỏ seed hay chọn thuật toán có lợi sau khi đã thấy số liệu.

### `A3_v2_full` → **KHÔNG ĐẠT — KẾT QUẢ ÂM**

| Thuật toán | Seed | best_cost đối chứng | best_cost arm | Cải thiện | Cost đạt | HV không giảm | Kết luận cặp |
|---|---:|---:|---:|---:|:---:|:---:|:---:|
| rs | 42 | 2114.57 | 2133.13 | -0.88% | KHÔNG | KHÔNG | KHÔNG |
| rs | 43 | 2096.38 | 2098.81 | -0.12% | KHÔNG | KHÔNG | KHÔNG |
| rs | 44 | 2080.75 | 2100.47 | -0.95% | KHÔNG | KHÔNG | KHÔNG |
| nsga2 | 42 | 2072.94 | 2082.75 | -0.47% | KHÔNG | KHÔNG | KHÔNG |
| nsga2 | 43 | 2072.94 | 2057.71 | 0.73% | KHÔNG | KHÔNG | KHÔNG |
| nsga2 | 44 | 2072.94 | 2021.39 | 2.49% | ĐẠT | ĐẠT | ĐẠT |

**KẾT QUẢ ÂM được ghi nhận.** Theo pre-registration, không đạt đồng thời hai điều kiện trên MỌI cặp (thuật toán, seed) thì không được phát biểu rằng grammar này tốt hơn đối chứng. Không được đổi ngưỡng, bỏ seed hay chọn thuật toán có lợi sau khi đã thấy số liệu.

Quy tắc quy kết: Nếu A3 đạt tiêu chí mà A2 không đạt thì phần cải thiện được quy cho BÊ TÔNG CƯỜNG ĐỘ CAO (C55/C60), KHÔNG được quy cho tự do hình dạng.

## Cảnh báo suy biến

Hệ số tương quan Pearson giữa các mục tiêu, tính trên record khả thi của từng run (|r| ≥ 0.999 ⇒ mục tiêu suy biến, hypervolume và Pareto front mất ý nghĩa đa mục tiêu):

| Arm | Thuật toán | Seed | Pareto front | r(cost,mass) | r(cost,carbon) | r(mass,carbon) |
|---|---|---:|---:|---:|---:|---:|
| A1_v1_catalog | rs | 42 | 1 | 0.827264 | 0.935541 | 0.854687 |
| A1_v1_catalog | rs | 43 | 3 | 0.789011 | 0.917048 | 0.86977 |
| A1_v1_catalog | rs | 44 | 3 | 0.79468 | 0.916447 | 0.863599 |
| A1_v1_catalog | nsga2 | 42 | 2 | 0.617276 | 0.895602 | 0.785508 |
| A1_v1_catalog | nsga2 | 43 | 3 | 0.720309 | 0.945452 | 0.813347 |
| A1_v1_catalog | nsga2 | 44 | 3 | 0.623018 | 0.944123 | 0.760187 |
| A2_v2_shape_only | rs | 42 | 4 | 0.771729 | 0.929013 | 0.816806 |
| A2_v2_shape_only | rs | 43 | 1 | 0.73834 | 0.899804 | 0.819268 |
| A2_v2_shape_only | rs | 44 | 1 | 0.751086 | 0.915387 | 0.807451 |
| A2_v2_shape_only | nsga2 | 42 | 2 | 0.7288 | 0.962455 | 0.853884 |
| A2_v2_shape_only | nsga2 | 43 | 1 | 0.879534 | 0.996014 | 0.910666 |
| A2_v2_shape_only | nsga2 | 44 | 2 | 0.712996 | 0.959321 | 0.844598 |
| A3_v2_full | rs | 42 | 4 | 0.724324 | 0.921227 | 0.674559 |
| A3_v2_full | rs | 43 | 3 | 0.643491 | 0.910749 | 0.656449 |
| A3_v2_full | rs | 44 | 2 | 0.799409 | 0.954372 | 0.764168 |
| A3_v2_full | nsga2 | 42 | 1 | 0.725614 | 0.994854 | 0.777508 |
| A3_v2_full | nsga2 | 43 | 2 | 0.69566 | 0.964555 | 0.793103 |
| A3_v2_full | nsga2 | 44 | 1 | 0.687894 | 0.984908 | 0.754973 |

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

## Confound đã đăng ký (không bóc tách được ở thí nghiệm này)

- girder_count: A1 tìm trên {5, 6, 7, 8} còn A2/A3 chỉ có {5, 6}. Không bóc tách được vì miền v1 bị đóng băng và miền v2 do file grammar quy định; muốn bóc tách phải có arm thứ tư (v1 giới hạn girder_count {5,6}) — NGOÀI phạm vi thí nghiệm này.
- diaphragm_layout_id: A1 có thêm lựa chọn DG-END-ONLY mà A2/A3 không có.
- Rule profile: V2 áp thêm FAB-001..FAB-007 nên arm v2 chịu ràng buộc HARD chặt hơn arm v1. Đây là confound cố hữu và TUYỆT ĐỐI KHÔNG được nới để arm v2 thắng (AGENTS.md: ràng buộc chế tạo là hard gate).
- Số chiều: cùng ngân sách solver nhưng không gian v2 lớn hơn nhiều bậc, nên một kết quả âm có thể mang nghĩa v2 cần nhiều ngân sách hơn chứ không nhất thiết là tự do hình dạng vô ích. Kết luận phải nêu giới hạn này.
- Marker ST-PARAM: v2 không thể chọn tiết diện định hình, nên A2/A3 không bao trùm (superset) A1 về mặt không gian phương án.

_Toàn bộ số liệu của thí nghiệm này sinh từ L0 (hình học + chế tạo) và L1 line-girder sơ bộ của solver BUILTIN_L1. Đây là SÀNG LỌC, không phải thiết kế: không được gọi bất kỳ phương án nào là thiết kế thật, build-ready, NUMERICALLY_VERIFIED hay ENGINEERING_CANDIDATE. Muốn lên cấp phải có artifact L2/L3 thật (MARP-1.0 muc Cap do claim, PG-1.0 G2-G4)._