# DYLIGHT Bridge Evolution

Prototype nghiên cứu khám phá phương án cầu dầm **Super-T giản đơn** bằng
design grammar, mô phỏng vật lý đa cấp và tối ưu có ràng buộc. L1 chỉ dùng để
sàng lọc sơ bộ; hệ thống chưa thay thế kiểm chứng Midas và phê duyệt kỹ sư.

## Trạng thái phát triển

| Giai đoạn | Nội dung | Trạng thái |
|-----------|----------|-----------|
| P0 | Research Contract, grammar, catalogs, schemas | ✅ Hoàn thành |
| P1 | Parametric Generator (`BridgeDesignState` → hình học + L0) | ✅ Hoàn thành |
| P2 | Physics (L1 line-girder solver) + Independent Verifier | ✅ Hoàn thành (L1). **L2/L3 CHƯA CÓ**: `MIDAS_CIVIL` và `OPENSEESPY` chỉ là nhánh dispatch ném `SolverError` |
| P3 | Baseline Optimization (Random Search, NSGA-II, Pareto archive, hypervolume) | ✅ Hoàn thành |
| P4 | Surrogate model (`surrogate/` — RF sàng lọc, chỉ xếp hạng, không kết luận) | ✅ Hoàn thành |
| P5 | RL (`rl_env/` — env + safety shield + reward chống hacking + Q-learning tuyến tính) | ✅ Hoàn thành (PPO/torch để sau) |
| Grammar v2 | Tiết diện tham số hoá 6 biến (`super_t_parametric_v2`) + ràng buộc chế tạo `FAB-000…FAB-007` chạy ở L0 | ✅ Có thật trong runtime; ngưỡng FAB vẫn là mặc định repo, chưa gắn nguồn nhà máy |
| Não 2 | Knowledge layer (`knowledge/` — 20 thẻ tri thức (KC-001…KC-020), audit phủ đủ 20 thẻ với trạng thái thật) | ✅ Audit khép kín; **0/20 thẻ được kỹ sư duyệt**, toàn kho vẫn `DRAFT` |
| Chẩn đoán | `analysis/` — FAIL → nước sửa trong grammar, gắn card não 2 | ✅ Hoàn thành |
| P6 | Multi-Agent Bridge Lab (Codex + Claude + OpenCode + Antigravity) | ✅ Protocol/task/handoff/review; CLI ngoài Codex cần đưa vào PATH |
| Hardening 0.2 | Contract semantic, artifact sandbox, solver-budget công bằng, `MODEL-001`, packaging/CI | ✅ Hoàn thành |
| Brain 2 / Obsidian 0.3 | Dashboard + card notes (xuất theo đúng số thẻ đang có), audit oracle, manifest chống ghi đè | ✅ Hoàn thành |
| Standards / Obsidian 0.4 | Import PDF TCVN, mục lục curated, hash và conflict safety | ✅ Hoàn thành |
| Knowledge graph / Obsidian 0.5 | Standard ↔ rule ↔ card ↔ variable, CSS và màu Graph View | ✅ Hoàn thành |
| NotebookLM / Obsidian 0.6 | 32 notebook cầu/BIM, 218 nguồn khai báo, summary chỉ-đọc và provenance | ✅ Hoàn thành |
| Physics/Reality Lab 0.8 | Intake → DAG → bounded agents → test/review → Obsidian | ✅ Digital auto có cổng dừng; runtime hiện chỉ `SCREENED` |
| Kiểm toán đa cấu kiện | Dầm, bản, trụ/mố, móng/cọc, gối/khe, cáp-DƯL, vòm, giàn, liên kết và kết cấu tạm | ✅ Điều phối evidence fail-closed; **chưa có** physics oracle cho các check ngoài verifier L1 |
| Chống lệch docs–runtime | `docs/runtime_capability_matrix.json` + `docs/check_runtime_drift.py` | ✅ Chạy được; **chưa** nối vào `pytest` (xem bên dưới) |

## Cài đặt

```bash
python -m pip install -e ".[dev]"
```

Môi trường audit chính xác được ghi trong `requirements-dev.lock`. Khi cài
wheel, schema/catalog/grammar/knowledge cards được đóng gói cùng package;
`DYLIGHT_ARTIFACTS_DIR` có thể dùng để chọn thư mục artifact ghi được.

`.[dev]` cài đủ bốn backend để chạy toàn bộ test. Nếu chỉ dùng một
năng lực, có thể cài nhỏ hơn bằng extra riêng:

```bash
python -m pip install -e ".[optimization]"  # pymoo / NSGA-II ngoài
python -m pip install -e ".[section-fea]"   # Shapely + sectionproperties
python -m pip install -e ".[ifc]"           # IfcOpenShell + Shapely
python -m pip install -e ".[all]"           # toàn bộ backend tùy chọn
```

Không cài extra thì đường core/Green vẫn chạy. Khi yêu cầu FEA tiết diện
2D, lỗi import/mesh/backend sẽ nổi lên và dừng; hệ thống không im lặng
trả kết quả Green như thể `sectionproperties` đã chạy. FEA tiết diện
này vẫn chỉ là năng lực nghiên cứu tùy chọn, không phải L2/L3 và
không nâng trần claim `SCREENED` của dự án.

## Chạy nhanh

```bash
# Toàn bộ test (schema, hình học, solver, verifier, gold cases, Pareto, P4/P5, não 2)
python -m pytest tests -q

# Kiểm LỆCH giữa tài liệu và runtime (đếm lại mọi con số, gọi thật mọi năng lực)
python docs/check_runtime_drift.py

# Đánh giá 1 phương án đơn lẻ
python -m bridge_evolution.cli evaluate gold_cases/cases/GC-01_standard_pass.json

# Chẩn đoán FAIL → nước sửa (kèm thẻ tri thức não 2)
python -m bridge_evolution.cli diagnose gold_cases/cases/GC-06_cheap_but_fails.json

# Truy vấn não thứ 2
python -m bridge_evolution.cli knowledge --rules SERV-001

# Kiểm tra rồi xuất não 2 vào vault Obsidian đang đăng ký
python -m bridge_evolution.cli knowledge-export --dry-run
python -m bridge_evolution.cli knowledge-export

# Nhập bộ PDF TCVN 11823:2017 vào Standards library của Brain 2
python -m bridge_evolution.cli knowledge-import-tcvn "<thu_muc_pdf>" --dry-run
python -m bridge_evolution.cli knowledge-import-tcvn "<thu_muc_pdf>"

# Bật màu note và nhóm màu Graph View (giữ nguyên thiết lập khác của user)
python -m bridge_evolution.cli knowledge-theme --dry-run
python -m bridge_evolution.cli knowledge-theme

# Xuất snapshot NotebookLM cầu/BIM đã kiểm kê vào Obsidian
python -m bridge_evolution.cli knowledge-import-notebooklm --dry-run
python -m bridge_evolution.cli knowledge-import-notebooklm

# Phòng thí nghiệm đa tác tử: kiểm tra, lấy brief và claim task
python -m bridge_evolution.cli lab status
python -m bridge_evolution.cli lab validate
python -m bridge_evolution.cli lab brief --agent codex
python -m bridge_evolution.cli lab sync-obsidian --dry-run
python -m bridge_evolution.cli lab sync-obsidian

# Đề tài mới: tạo brief + DAG + lưu Obsidian; mặc định chưa gọi model
python -m bridge_evolution.cli lab orchestrate --topic "Nghiên cứu hình cầu mới ..."
python -m bridge_evolution.cli lab doctor
# Chỉ chạy sau khi worker/reviewer khác hãng đã đăng nhập
python -m bridge_evolution.cli lab resume RUN-YYYYMMDD-xxxxxxxx --execute

# Oracle toàn miền hữu hạn (bắt buộc trước khi diễn giải benchmark)
python experiments/run_exhaustive.py

# Cùng ngân sách solver thật; mỗi lệnh tạo thư mục kết quả mới, không ghi đè
python experiments/run_baseline.py --budget 600 --seed 42
python experiments/run_multiseed.py --budget 600 --seeds 42,43,44 --algos rs,nsga2,surrogate,qlearning

# Định lượng recall, IGD+, epsilon và HV ratio so với oracle vừa tạo
python experiments/compare_to_oracle.py --oracle-dir experiments/results/exhaustive_<timestamp> --run-dir experiments/results/multiseed_b600_<timestamp>
```

API có thể nhận thêm `component_manifest` để gom bằng chứng theo từng cấu kiện:

```python
from bridge_evolution.evaluate import evaluate_candidate

component_manifest = {
    "components": [{
        "component_id": "G1",
        "kind": "LONGITUDINAL_GIRDER",
        "checks": [{
            "check_id": "FLEXURE_STRENGTH",
            "status": "PASS",
            "severity": "HARD",
            "evidence": {
                "source_ref": "results/midas/G1-flexure.json",
                "sha256": evidence_sha256,
                "fidelity": "EXTERNAL_SOLVER",
                "producer": "midas-export-adapter",
            },
            "message": "Kết quả do adapter bên ngoài cung cấp.",
            "utilization": 0.82,
        }],
    }],
}
result = evaluate_candidate(state, component_manifest=component_manifest)
```

Ví dụ cố ý chỉ đưa một check nên audit sẽ `BLOCKED`: các hard check còn thiếu
được sinh thành `NOT_EVALUATED`. Registry hiện bao phủ 20 họ cấu kiện nhưng chỉ
**tổ chức bằng chứng**; nó không tự tạo nội lực/sức kháng. Proposal luôn là
`UNVERIFIED_PROPOSAL`, bắt buộc phân tích lại và không thay `result.feasible`.

`budget` chỉ tăng khi solver thật sự chạy (`solver.status != NOT_RUN`). Proposal,
L0 reject và cache hit được đếm riêng. Hypervolume dùng reference point cố định,
không suy hậu nghiệm từ kết quả thuật toán. Các báo cáo cũ trong
`experiments/results/run_b600_s42` và `multiseed_b600` dùng định nghĩa ngân sách
legacy và không được dùng để so sánh với protocol mới.

## Kiến trúc

```
BridgeDesignState (JSON, schema-validated)
      │
      ├─ L0  geometry.check_geometry()      – loại phương án vô lý, không mở solver
      ├─ L1  fe_adapter.line_girder         – dầm đơn + hệ số phân bố ngang, tải HL-93/TCVN 11823
      │        (interface solver.py sẵn chỗ cho OpenSeesPy ở L2/L3)
      ├─ verifier.rules                     – PASS/FAIL độc lập với solver (STR/SERV/GEOM/CONS)
      ├─ objectives                         – chi phí tương đối, khối lượng, carbon
      ├─ evaluate.build_component_audit()   – envelope evidence đa cấu kiện, fail-closed
      └─ evaluate.evaluate_candidate()      – contract trung tâm, provenance + artifacts + audit tùy chọn
                    │
        optimization/ (random_search, nsga2) → pareto.ParetoArchive → experiments/
```

**Nguyên tắc bất biến:**
1. Mọi LLM là *planner/proposer*, không bao giờ là *solver* hay *verifier*.
2. Mọi ràng buộc an toàn là **hard constraint** — không đánh đổi lấy chi phí.
3. Mọi kết quả phải tái lập được: `input_hash + ruleset_version + solver_version + seed`.
4. Solver crash / không hội tụ = phương án bị loại, **không** phải đường thoát phạt cho RL.
5. `case_id` chỉ là ID rút gọn 64-bit; full SHA-256 trong provenance là định danh chuẩn.

## Runtime có gì, không có gì (đọc trước khi trích dẫn bất kỳ số nào)

`docs/runtime_capability_matrix.md` ghi từng năng lực kèm bằng chứng là đường dẫn
file và tên hàm; nguồn chuẩn máy đọc là `docs/runtime_capability_matrix.json`.
Tóm tắt phần **KHÔNG có**: L2/L3 (`MIDAS_CIVIL`/`OPENSEESPY` chỉ ném
`SolverError`), mạng dầm 3D grillage (không module nào import `ospgrillage`),
hiệu ứng theo giai đoạn (ứng suất lúc truyền lực, mất mát DƯL, co ngót–từ biến),
thí nghiệm/quan trắc thật, và phê duyệt kỹ sư (0/20 thẻ `ENGINEER_APPROVED`).
Trần claim toàn dự án là `SCREENED`.

`COMPONENT_AUDIT_ORCHESTRATION` là năng lực `PARTIAL`: runtime có thể phát hiện
thiếu evidence, khóa hard check, kiểm lineage/hash và sinh đề xuất tái phân tích.
Nó **không** phải solver cho N-M, P-Delta, ổn định, mỏi, địa kỹ thuật, thủy lực,
giai đoạn thi công hay độ bền; các nội dung đó phải có bằng chứng từ công cụ phù
hợp trước khi check được giữ ở trạng thái `PASS/FAIL`.

Hai bộ kiểm giữ cho tài liệu không trôi khỏi runtime — chạy chúng sau mỗi thay
đổi mã hoặc tài liệu:

```bash
python docs/check_runtime_drift.py        # đếm lại mọi con số, gọi thật mọi năng lực
python docs/check_handoff_provenance.py   # artifact đã hash có tái dựng được không
```

Quy tắc version-control cho artifact có hash nằm ở
`docs/baseline_version_control_plan.md`. Quy tắc cốt lõi: **không hash vào
handoff một artifact chưa được version-control** — hôm nay 0/15 artifact đã ký
tái dựng được từ `HEAD`, và kế hoạch đóng khoảng trống đó nằm ở §5 của tài liệu.

> **2 test đang đỏ có chủ đích.** `tests/test_obsidian.py` khoá cứng con số 9
> thẻ của bản audit cũ (`range(1, 10)` và câu cảnh báo "card ngoài snapshot chưa
> được audit"). Audit nay phủ đủ 20 thẻ nên hai khẳng định đó sai. Cách sửa
> chính xác nằm ở `docs/baseline_version_control_plan.md` §5 mục 0; `tests/`
> nằm ngoài `write_scope` của BRD-001 nên không được sửa trong đợt này. **Không**
> chỉnh dữ liệu audit cho khớp test — đó đúng là kiểu gian lận mà task cấm.

## Ghi chú hiệu chỉnh (quan trọng)

Số liệu trong `catalogs/` (đặc trưng tiết diện Super-T, đơn giá, hệ số phát thải)
là **placeholder có bậc độ lớn đúng**, phục vụ phát triển pipeline. Trước khi dùng
cho kết luận khoa học, phải hiệu chỉnh theo hồ sơ tiết diện thực và kiểm chứng
bằng `gold_cases/` do kỹ sư duyệt (xem docs/01_research_contract.md §7).

Protocol công bố/kiểm chứng bắt buộc nằm tại `docs/03_validation_protocol.md`.
Đặc biệt, phương án có khối nén vượt chiều dày bản bị chặn bởi hard violation
`MODEL-001`; chưa được tự suy rộng công thức khi catalog không đủ hình học.

Kết nối Obsidian được mô tả tại `docs/04_obsidian_integration.md`. JSON vẫn là
nguồn chuẩn của não 2; Markdown trong vault không được tham gia verifier. Có thể
chỉ định vault bằng `--vault` hoặc biến môi trường `DYLIGHT_OBSIDIAN_VAULT`.
Các node Standards, Rules, Cards và Variables được liên kết hai chiều; màu sắc
chỉ là lớp điều hướng trực quan, không thay đổi trạng thái duyệt hay kết quả kỹ thuật.

Phòng lab đa tác tử được mô tả tại `docs/05_multi_agent_research_protocol.md`.
Nguồn luật chung nằm trong `multiagent/`; adapter của từng hãng chỉ nạp lại cùng
một protocol. Kết quả hiện tại không được nâng quá `SCREENED` cho tới khi có
L2/L3 thật, kiểm chứng độc lập, thí nghiệm/quan trắc thích hợp và kỹ sư duyệt.
