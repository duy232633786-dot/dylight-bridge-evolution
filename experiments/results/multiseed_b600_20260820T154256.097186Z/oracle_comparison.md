# Đối chiếu exhaustive oracle

Oracle: `exhaustive_20260820T154139.606695Z` · 3 Pareto points

| run | archive_size | oracle_points_found | oracle_size | oracle_recall | exact_oracle_front | extra_nondominated_points | best_cost | best_cost_gap_pct | hv_2d_ratio | hv_3d_ratio | igd_plus_normalized | epsilon_additive_normalized |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| nsga2_s42 | 2 | 2 | 3 | 0.666667 | False | 0 | 2072.94 | 0 | 1 | 0.999882 | 0.00124918 | 0.0033064 |
| nsga2_s43 | 3 | 3 | 3 | 1 | True | 0 | 2072.94 | 0 | 1 | 1 | 0 | 0 |
| nsga2_s44 | 3 | 3 | 3 | 1 | True | 0 | 2072.94 | 0 | 1 | 1 | 0 | 0 |
| qlearning_s42 | 4 | 0 | 3 | 0 | False | 4 | 2093.61 | 0.997135 | 0.979164 | 0.949769 | 0.0206919 | 0.0232083 |
| qlearning_s43 | 6 | 0 | 3 | 0 | False | 6 | 2104.74 | 1.53405 | 0.968604 | 0.956522 | 0.0239967 | 0.0197083 |
| qlearning_s44 | 3 | 1 | 3 | 0.333333 | False | 2 | 2072.94 | 0 | 1 | 0.98993 | 0.00717222 | 0.0136333 |
| rs_s42 | 1 | 0 | 3 | 0 | False | 1 | 2114.57 | 2.00826 | 0.97814 | 0.979268 | 0.00476993 | 0.008326 |
| rs_s43 | 3 | 0 | 3 | 0 | False | 3 | 2096.38 | 1.13076 | 0.989402 | 0.97986 | 0.00437575 | 0.006564 |
| rs_s44 | 3 | 0 | 3 | 0 | False | 3 | 2080.75 | 0.37676 | 0.992108 | 0.982467 | 0.0110889 | 0.0123316 |
| surrogate_s42 | 2 | 2 | 3 | 0.666667 | False | 0 | 2072.94 | 0 | 1 | 0.999882 | 0.00124918 | 0.0033064 |
| surrogate_s43 | 3 | 3 | 3 | 1 | True | 0 | 2072.94 | 0 | 1 | 1 | 0 | 0 |
| surrogate_s44 | 2 | 2 | 3 | 0.666667 | False | 0 | 2072.94 | 0 | 1 | 0.999882 | 0.00124918 | 0.0033064 |