# Kế hoạch khoá baseline & version-control cho artifact có hash

Phiên bản: `BVC-1.0` — 2026-08-21 (BRD-001). Kèm `multiagent/PROTOCOL.md` (MARP-1.0).

Tài liệu ngắn, chỉ trả lời bốn câu: **cái gì phải vào Git trước khi được hash**,
**cái gì không bao giờ vào Git**, **dọn tồn đọng theo thứ tự nào**, và **cơ chế
nào giữ cho việc này không tái diễn**.

---

## 1. Sự cố đã đo được, không phải rủi ro giả định

MARP-1.0 yêu cầu mọi kết luận gắn với artifact có SHA-256. Nhưng repo chưa từng
kiểm rằng artifact đã ký có **tái dựng được bytes gốc** hay không. Đo ngày
2026-08-21 (`python docs/check_handoff_provenance.py --report`):

| Chỉ số | Giá trị |
|---|---|
| Artifact đã hash trong `multiagent/handoffs/*.json` | **15** |
| Tái dựng được từ `git show HEAD:<path>` | **0** |
| Tái dựng được từ `multiagent/snapshots/sha256/` | 3 |
| **Không tái dựng được bằng nguồn nào** | **12** |

Ba nhóm nguyên nhân, cả ba đều đã xảy ra thật:

1. **Bị `.gitignore` loại trừ.**
   `multiagent/handoffs/BRD-009.claude.r001.json` hash
   `experiments/results/grammar_ab_20260821T061537.020446Z/summary.md`.
   Dòng `experiments/results/*/` trong `.gitignore` loại trừ **cả thư mục**, nên
   theo ngữ nghĩa gitignore thì không file con nào re-include được. File đã ký
   nằm ngoài tầm với của Git ngay từ lúc ký.
2. **Chưa commit bao giờ.** `docs/design_basis/DB-SUPERT-38M.json` và
   `docs/design_basis/SITE-UNSPECIFIED.json` được `BRD-002.claude.r001.json`
   hash nhưng vẫn ở trạng thái untracked — `git show HEAD:...` trả
   `fatal: ... exists on disk, but not in 'HEAD'`. Cũng vậy với
   `experiments/preregistration/*.json`, `research/...`,
   `experiments/run_grammar_ab_confirmatory.py`.
3. **Có trong HEAD nhưng bytes đã trôi.** `tests/test_design_basis.py`,
   `tests/test_material_evidence.py`, `tests/test_rl_env.py` nằm trong HEAD
   nhưng bản HEAD **khác** bytes đã ký; bản đang ký chỉ tồn tại trong working
   tree. Một `git checkout .` là mất.

Có thêm một biến thể **ẩn hơn** của nhóm (3), phát hiện khi soạn tài liệu này:
`.gitattributes` ép `* text=auto eol=lf`, nhưng **4 artifact đã ký** vẫn còn
CRLF trong working tree (`tests/test_material_evidence.py`,
`tests/test_rl_env.py`, và hai file `summary.md`/`oracle_comparison.md` của run
`grammar_ab_...061537`). Bytes Git lưu là LF, bytes được hash là CRLF ⇒ hash
**không bao giờ khớp lại**, dù file "đã được commit". Trên máy Windows đây là
cách dễ nhất để tự phá chuỗi kiểm toán mà không nhận ra. Bộ kiểm
`docs/check_handoff_provenance.py` nay đo cả con số này.

Quét toàn repo (bỏ `.git/`, `build/`, `dist/`, `__pycache__/`, `.worktrees/`)
tìm được **188 file văn bản còn CRLF** trong khi `.gitattributes` ép `eol=lf` —
phần lớn do runner thí nghiệm và script vá file chạy trên Windows dùng
`Path.write_text()`, hàm này **tự dịch `\n` thành `\r\n`**. Cách chặn nguồn:
dùng `write_bytes()` hoặc `open(..., newline="\n")` trong mọi script sinh
artifact. Chuẩn hoá một file:

```bash
python -c "import pathlib,sys; p=pathlib.Path(sys.argv[1]); p.write_bytes(p.read_bytes().replace(b'\r\n',b'\n'))" <path>
```

Chỉ chuẩn hoá **trước** khi ký hash. Chuẩn hoá một file đã ký làm đổi SHA-256 và
phải đi qua `lab correct-provenance`.

Hệ quả trực tiếp: khi cần gỡ một provenance drift trong chính phiên này, một
artifact đã **không tái dựng nổi bytes gốc**, và phải chạy nghi thức
`lab correct-provenance` để đi tiếp.

---

## 2. Quy tắc bất biến

> **Không hash vào handoff một artifact chưa được version-control.**

Cụ thể, tại thời điểm chạy `lab submit`, mỗi đường dẫn trong `artifacts[]` phải
thoả **cả ba**:

1. **Không bị `.gitignore` loại trừ** — kiểm bằng `git check-ignore -q <path>`
   (mã thoát khác 0 là đạt).
2. **Đã nằm trong một commit** — `git show HEAD:<path>` chạy được.
3. **Bytes trong HEAD trùng đúng SHA-256 sắp ký** — không phải "có file cùng tên".
   Trên Windows, kiểm luôn ký tự xuống dòng: `.gitattributes` ép `eol=lf`, nên
   một file còn CRLF sẽ **không bao giờ** khớp lại hash sau khi commit.

Ba điều kiện này chính là cái `docs/check_handoff_provenance.py` đo. Nếu vì lý
do vòng đời (`REVISE`) mà bytes phải khác HEAD, thì phải có snapshot
content-addressed `multiagent/snapshots/sha256/<sha>.blob` đúng bytes — đó là
nguồn tái dựng hạng hai đã được MARP-1.0 định nghĩa, **không** phải cái thay thế
cho commit.

---

## 3. Cái gì vào Git, cái gì không

### Phải được commit trước khi hash

| Nhóm | Ví dụ | Lý do |
|---|---|---|
| Contract & schema | `contracts/*.json` | Là định nghĩa của chính chuỗi kiểm toán |
| Design basis & site | `docs/design_basis/*.json` | Ràng buộc đầu vào của mọi kết luận |
| Pre-registration | `experiments/preregistration/*.json` | Phải khoá TRƯỚC khi chạy, nếu không thì vô nghĩa |
| Mã sinh kết quả | `experiments/run_*.py`, `bridge_evolution/**` | Không có mã thì kết quả không tái lập |
| Test khẳng định kết quả | `tests/test_*.py` | Được hash trong handoff như bằng chứng |
| **Artifact văn bản nhỏ của thí nghiệm** | `experiments/results/*/summary.md`, `summary.json`, `manifest.json`, `oracle_comparison.md`, `pareto_*.json` | Chính là thứ được trích dẫn và ký; tổng chỉ ~406 KB cho 96 file |
| Ghi chép nghiên cứu canonical | `research/**` | JSON/artifact trong project là canonical, Obsidian chỉ là mirror |

### Không bao giờ vào Git

| Nhóm | Ví dụ | Kích thước thực đo | Cách trích dẫn thay thế |
|---|---|---|---|
| Log từng lần gọi solver | `experiments/results/*/history_*.jsonl`, `proposals_*.jsonl`, `solver_history.jsonl`, `*.csv` | ~13 GB (một run `grammar_ab` = 4,4 GB) | Hash `summary.md`/`manifest.json` — chúng đã tóm tắt và tham chiếu đủ |
| Artifact đánh giá từng phương án | `artifacts/BT-*/` | sinh lại được từ `state + seed` | Chép sang đường dẫn có version-control rồi mới hash |
| Rác build/công cụ | `build/`, `dist/`, `__pycache__/`, `.pytest_cache/`, `*.egg-info/`, `tmp/`, `.worktrees/`, `.venv/` | — | Không trích dẫn |
| Bí mật | credentials, model độc quyền, dữ liệu nhạy cảm | — | Không đưa vào repo (MARP-1.0) |

### Thay đổi `.gitignore` đã thực hiện

Vấn đề gitignore: *"không thể re-include một file nếu thư mục cha của nó đã bị
loại trừ"*. Vì vậy `experiments/results/*/` (loại trừ **thư mục**) không thể có
ngoại lệ. Bản mới loại trừ **nội dung** rồi re-include đúng những file cần:

```gitignore
experiments/results/**
!experiments/results/
!experiments/results/.gitkeep
!experiments/results/*/
!experiments/results/*/summary.md
!experiments/results/*/summary.json
!experiments/results/*/manifest.json
!experiments/results/*/oracle_comparison.md
!experiments/results/*/pareto_*.json
```

Kiểm chứng (đã chạy):

```
git check-ignore -q experiments/results/<run>/summary.md          -> khong bi loai (dat)
git check-ignore -q experiments/results/<run>/history_*.jsonl     -> bi loai (dat)
```

---

## 4. Checklist trước mỗi `lab submit`

```bash
# 1. Artifact sắp ký có được version-control không?
python docs/check_handoff_provenance.py

# 2. Tài liệu có còn khớp runtime không?
python docs/check_runtime_drift.py

# 3. Test
python -m pytest tests -q
```

Chỉ ký hash sau khi bước 1 và 2 xanh. Nếu một artifact không thể commit (quá
nặng), **đổi artifact** — hash bản tóm tắt đã commit — chứ không nới quy tắc.

---

## 5. Thứ tự dọn tồn đọng

Làm theo thứ tự, mỗi bước hạ `BASELINE_UNRECOVERABLE` (và `BASELINE_CRLF`) trong
`docs/check_handoff_provenance.py` xuống đúng con số mới (bánh cóc: script báo
đỏ cả khi cải thiện mà quên hạ baseline).

0. **[ĐÃ XONG 2026-10-12]** Sửa hai test đang khoá cứng con số 9 cũ. *(Ngoài `write_scope` của
   BRD-001 — cần task riêng, và là hệ quả TRỰC TIẾP của việc đóng lệch audit.)*
   - `tests/test_obsidian.py:187` — `assert set(audit["cards"]) == {…range(1, 10)}`
     đóng băng đúng cái lệch mà BRD-001 phải đóng. Tên test là
     `test_current_audit_valid_and_has_all_cards` nhưng nó khẳng định 9 thẻ.
     Sửa thành so với tập thẻ runtime nạp được:
     `assert set(audit["cards"]) == {c["card_id"] for c in load_cards()}`.
   - `tests/test_obsidian.py:69` — `assert "card ngoài snapshot chưa được audit"
     in dashboard` khẳng định dashboard phải cảnh báo có thẻ chưa được audit.
     Điều đó **không còn đúng** vì audit đã phủ 20/20. Đổi sang một câu cảnh báo
     còn hiệu lực, ví dụ `"0/20 card ở trạng thái ENGINEER_APPROVED"`.

   Hai test này chính là minh hoạ cho bài học của task: **test khoá cứng con số
   thay vì đếm lại từ runtime sẽ bảo vệ chính cái lệch**.

1. **Commit baseline hiện tại.** Toàn bộ file đang untracked mà nằm trong danh
   sách "phải được commit" ở §3 — 219 đường dẫn untracked, trong đó 96 file kết
   quả nhỏ (~406 KB) vừa được `.gitignore` mới cho phép. Đây là bước gỡ được 9
   trong 12 artifact.
2. **Đóng 3 artifact "HEAD khác bytes đã ký".** `tests/test_design_basis.py`,
   `tests/test_material_evidence.py`, `tests/test_rl_env.py`: commit đúng bytes
   đang được ký. Nếu bytes đã thay đổi sau khi ký thì **không** sửa hash trong
   handoff cũ — đi qua `lab correct-provenance` theo MARP-1.0.
3. **Hạ baseline về 0** và nối hai bộ kiểm vào cổng merge.

   > **Bánh cóc đã kêu ngay lần dùng đầu tiên.** Lúc soạn tài liệu này số artifact
   > không tái dựng được là **12**, và `BASELINE_UNRECOVERABLE = 12`. Ngay sau đó
   > hai handoff mới (`BRD-001.claude.r001.json`, `BRD-003.claude.r001.json`) hash
   > thêm artifact **chưa được commit** — trong đó có chính
   > `docs/runtime_capability_matrix.md` và `knowledge/audits/current.json` — nên
   > con số lên **14** và script báo đỏ. Đây là **hành vi đúng**, không phải lỗi
   > script. Cách xử lý đúng là làm bước 1 (commit baseline), **không** phải nâng
   > `BASELINE_UNRECOVERABLE` lên 14: nâng baseline để lấy màu xanh chính là cách
   > làm hỏng một cơ chế bánh cóc.
4. **Nối vào CI.** `.github/workflows/tests.yml` hiện chỉ chạy `pytest`. Thêm
   hai bước `python docs/check_handoff_provenance.py` và
   `python docs/check_runtime_drift.py`. *(Ngoài `write_scope` của BRD-001 —
   cần task riêng.)*
5. **Nối vào `pytest`.** Tạo `tests/test_runtime_drift.py` ba dòng theo docstring
   đầu `docs/check_runtime_drift.py`. *(Ngoài `write_scope` — cần task riêng.)*
6. **[ĐÃ CÓ SẴN — kiểm 2026-10-12]** `pyproject.toml` đã khai báo `pymoo`, `shapely`, `sectionproperties`, `ifcopenshell` trong `dev`/extras và `requirements-dev.lock` có cùng phiên bản. Gốc: **Sửa `pyproject.toml`** để khai báo `pymoo`, `shapely`, `sectionproperties`,
   `ifcopenshell`; đồng bộ `requirements-dev.lock`. Không có bước này thì
   "môi trường audit chính xác" trong README là sai và CI không tái lập được.
   *(Ngoài `write_scope` — cần task riêng.)*

---

## 6. Vì sao không dùng snapshot thay cho commit

`multiagent/snapshots/sha256/<sha>.blob` giữ đúng bytes và cứu được 3/15 artifact
hiện nay, nhưng nó **không** thay được Git:

- snapshot chỉ được tạo ở vòng `REVISE` và `correct-provenance`, tức là **sau**
  khi sự cố đã xảy ra — nó là băng cứu thương, không phải phòng ngừa;
- snapshot không có lịch sử, không có diff, không có branch/merge, nên không trả
  lời được "artifact này sinh ra từ mã nào";
- snapshot nằm cùng một cây thư mục với artifact gốc; mất máy là mất cả hai.

Git là nguồn tái dựng hạng nhất. Snapshot là hạng hai và phải kèm incident.

## 7. Trạng thái provenance hiện tại (ghi nhận, chưa sửa)

Ngày ghi: 2026-10-12, sau commit `672ba93`. Số liệu lấy từ `python docs/check_handoff_provenance.py`.

- Artifact đã hash trong handoff: 305 — dựng lại từ HEAD: 207; từ snapshot: 30; **không dựng lại được: 68** (baseline 12).
- File CRLF trong working tree (`.gitattributes` eol=lf): **86** (baseline 4).

Quyết định: **không** hạ hay nâng baseline, không sửa hash, không chuẩn hoá CRLF của file đã ký. Checker provenance chưa nối vào CI cho đến khi có bytes gốc hoặc correction được review độc lập. Chỉ drift (`tests/test_runtime_drift.py`) nằm trong pytest/CI.

### Danh sách 68 artifact không dựng lại được

- bridge_evolution/optimization/nsga2.py — `[HEAD KHAC BYTES DA KY, KHONG CO SNAPSHOT]`
- docs/sage_evobridge/beam_contract.json — `[HEAD KHAC BYTES DA KY, KHONG CO SNAPSHOT]`
- docs/sage_evobridge/budget_contract.json — `[HEAD KHAC BYTES DA KY, KHONG CO SNAPSHOT]`
- docs/sage_evobridge/collateral_contract.json — `[HEAD KHAC BYTES DA KY, KHONG CO SNAPSHOT]`
- docs/sage_evobridge/unsupported_contract.json — `[HEAD KHAC BYTES DA KY, KHONG CO SNAPSHOT]`
- experiments/results/grammar_ab_20260821T061537.020446Z/oracle_comparison.md — `[HEAD KHAC BYTES DA KY, KHONG CO SNAPSHOT]`
- experiments/results/grammar_ab_20260821T061537.020446Z/summary.md — `[HEAD KHAC BYTES DA KY, KHONG CO SNAPSHOT]`
- experiments/results/nsga2_operator_ab/pytest_full_suite_long_basetemp.log — `[BI GITIGNORE, CHUA COMMIT, KHONG CO SNAPSHOT]`
- experiments/results/nsga2_operator_ab/pytest_rerun_short_basetemp.log — `[BI GITIGNORE, CHUA COMMIT, KHONG CO SNAPSHOT]`
- experiments/results/nsga2_operator_ab/runs.jsonl — `[BI GITIGNORE, CHUA COMMIT, KHONG CO SNAPSHOT]`
- experiments/results/nsga2_operator_ab/summary.json — `[HEAD KHAC BYTES DA KY, KHONG CO SNAPSHOT]`
- experiments/validation/opensees_brd044_benchmarks.json — `[HEAD KHAC BYTES DA KY, KHONG CO SNAPSHOT]`
- research/orchestration/RND-20260901-00fd963d/b1_1440_checks.json — `[HEAD KHAC BYTES DA KY, KHONG CO SNAPSHOT]`
- research/orchestration/RND-20260901-00fd963d/b1_1440_cross_section.svg — `[HEAD KHAC BYTES DA KY, KHONG CO SNAPSHOT]`
- research/orchestration/RND-20260901-00fd963d/b1_1440_elevation.svg — `[HEAD KHAC BYTES DA KY, KHONG CO SNAPSHOT]`
- research/orchestration/RND-20260901-00fd963d/b1_1440_geometry.json — `[HEAD KHAC BYTES DA KY, KHONG CO SNAPSHOT]`
- research/orchestration/RND-20260901-00fd963d/b1_1440_nodes.csv — `[HEAD KHAC BYTES DA KY, KHONG CO SNAPSHOT]`
- research/orchestration/RND-20260922-74117064/MASTER_PROMPT.md — `[HEAD KHAC BYTES DA KY, KHONG CO SNAPSHOT]`
- research/orchestration/RND-20260922-74117064/checkpoint_20260923_0028.json — `[HEAD KHAC BYTES DA KY, KHONG CO SNAPSHOT]`
- research/orchestration/RND-20260922-74117064/checkpoint_20260923_003004.json — `[HEAD KHAC BYTES DA KY, KHONG CO SNAPSHOT]`
- research/orchestration/RND-20260922-74117064/checkpoint_20260923_003004.md — `[HEAD KHAC BYTES DA KY, KHONG CO SNAPSHOT]`
- research/orchestration/RND-20260922-74117064/evidence/bootstrap_failures.json — `[HEAD KHAC BYTES DA KY, KHONG CO SNAPSHOT]`
- research/orchestration/RND-20260922-74117064/evidence/budget_exhausted.stdout.log — `[HEAD KHAC BYTES DA KY, KHONG CO SNAPSHOT]`
- research/orchestration/RND-20260922-74117064/evidence/budget_exhausted/manifest.json — `[HEAD KHAC BYTES DA KY, KHONG CO SNAPSHOT]`
- research/orchestration/RND-20260922-74117064/evidence/collateral.stdout.log — `[HEAD KHAC BYTES DA KY, KHONG CO SNAPSHOT]`
- research/orchestration/RND-20260922-74117064/evidence/collateral/manifest.json — `[HEAD KHAC BYTES DA KY, KHONG CO SNAPSHOT]`
- research/orchestration/RND-20260922-74117064/evidence/commands.json — `[HEAD KHAC BYTES DA KY, KHONG CO SNAPSHOT]`
- research/orchestration/RND-20260922-74117064/evidence/inconclusive_probe.stdout.log — `[HEAD KHAC BYTES DA KY, KHONG CO SNAPSHOT]`
- research/orchestration/RND-20260922-74117064/evidence/inconclusive_probe/manifest.json — `[HEAD KHAC BYTES DA KY, KHONG CO SNAPSHOT]`
- research/orchestration/RND-20260922-74117064/evidence/legacy_output_guard_probe.json — `[HEAD KHAC BYTES DA KY, KHONG CO SNAPSHOT]`
- research/orchestration/RND-20260922-74117064/evidence/restart_verification.json — `[HEAD KHAC BYTES DA KY, KHONG CO SNAPSHOT]`
- research/orchestration/RND-20260922-74117064/evidence/session_logs/amendment.log — `[HEAD KHAC BYTES DA KY, KHONG CO SNAPSHOT]`
- research/orchestration/RND-20260922-74117064/evidence/session_logs/amendment_changes.json — `[HEAD KHAC BYTES DA KY, KHONG CO SNAPSHOT]`
- research/orchestration/RND-20260922-74117064/evidence/session_logs/baseline_exit.txt — `[HEAD KHAC BYTES DA KY, KHONG CO SNAPSHOT]`
- research/orchestration/RND-20260922-74117064/evidence/session_logs/baseline_tests.log — `[HEAD KHAC BYTES DA KY, KHONG CO SNAPSHOT]`
- research/orchestration/RND-20260922-74117064/evidence/session_logs/claim.json — `[HEAD KHAC BYTES DA KY, KHONG CO SNAPSHOT]`
- research/orchestration/RND-20260922-74117064/evidence/session_logs/existing_design_loop.json — `[HEAD KHAC BYTES DA KY, KHONG CO SNAPSHOT]`
- research/orchestration/RND-20260922-74117064/evidence/session_logs/existing_design_loop.log — `[HEAD KHAC BYTES DA KY, KHONG CO SNAPSHOT]`
- research/orchestration/RND-20260922-74117064/evidence/session_logs/existing_design_loop_exit.txt — `[HEAD KHAC BYTES DA KY, KHONG CO SNAPSHOT]`
- research/orchestration/RND-20260922-74117064/evidence/session_logs/existing_solver_failure.json — `[HEAD KHAC BYTES DA KY, KHONG CO SNAPSHOT]`
- research/orchestration/RND-20260922-74117064/evidence/session_logs/existing_solver_failure_exit.txt — `[HEAD KHAC BYTES DA KY, KHONG CO SNAPSHOT]`
- research/orchestration/RND-20260922-74117064/evidence/session_logs/focused_01.log — `[HEAD KHAC BYTES DA KY, KHONG CO SNAPSHOT]`
- research/orchestration/RND-20260922-74117064/evidence/session_logs/focused_02.log — `[HEAD KHAC BYTES DA KY, KHONG CO SNAPSHOT]`
- research/orchestration/RND-20260922-74117064/evidence/session_logs/focused_03.log — `[HEAD KHAC BYTES DA KY, KHONG CO SNAPSHOT]`
- research/orchestration/RND-20260922-74117064/evidence/session_logs/git_status_before.txt — `[HEAD KHAC BYTES DA KY, KHONG CO SNAPSHOT]`
- research/orchestration/RND-20260922-74117064/evidence/session_logs/intake.json — `[HEAD KHAC BYTES DA KY, KHONG CO SNAPSHOT]`
- research/orchestration/RND-20260922-74117064/evidence/session_logs/lab_validate_pre_handoff.json — `[HEAD KHAC BYTES DA KY, KHONG CO SNAPSHOT]`
- research/orchestration/RND-20260922-74117064/evidence/session_logs/path_diagnostic.log — `[HEAD KHAC BYTES DA KY, KHONG CO SNAPSHOT]`
- research/orchestration/RND-20260922-74117064/evidence/session_logs/regression_exit.txt — `[HEAD KHAC BYTES DA KY, KHONG CO SNAPSHOT]`
- research/orchestration/RND-20260922-74117064/evidence/session_logs/regression_tests.log — `[HEAD KHAC BYTES DA KY, KHONG CO SNAPSHOT]`
- research/orchestration/RND-20260922-74117064/evidence/session_logs/tracked_before.patch — `[HEAD KHAC BYTES DA KY, KHONG CO SNAPSHOT]`
- research/orchestration/RND-20260922-74117064/evidence/source_snapshots/index.json — `[HEAD KHAC BYTES DA KY, KHONG CO SNAPSHOT]`
- research/orchestration/RND-20260922-74117064/evidence/success.stdout.log — `[HEAD KHAC BYTES DA KY, KHONG CO SNAPSHOT]`
- research/orchestration/RND-20260922-74117064/evidence/success/manifest.json — `[HEAD KHAC BYTES DA KY, KHONG CO SNAPSHOT]`
- research/orchestration/RND-20260922-74117064/evidence/unsupported.stdout.log — `[HEAD KHAC BYTES DA KY, KHONG CO SNAPSHOT]`
- research/orchestration/RND-20260922-74117064/evidence/unsupported/manifest.json — `[HEAD KHAC BYTES DA KY, KHONG CO SNAPSHOT]`
- research/orchestration/RND-20260922-74117064/session_manifest.json — `[HEAD KHAC BYTES DA KY, KHONG CO SNAPSHOT]`
- research/orchestration/RND-20260922-74117064/session_metadata.json — `[HEAD KHAC BYTES DA KY, KHONG CO SNAPSHOT]`
- research/orchestration/RND-20260923-1472cd05/README.md — `[HEAD KHAC BYTES DA KY, KHONG CO SNAPSHOT]`
- research/orchestration/RND-20260923-1472cd05/corpus.json — `[HEAD KHAC BYTES DA KY, KHONG CO SNAPSHOT]`
- research/orchestration/RND-20260923-1472cd05/independent_review.json — `[HEAD KHAC BYTES DA KY, KHONG CO SNAPSHOT]`
- research/orchestration/RND-20260923-1472cd05/publication_manifest.json — `[HEAD KHAC BYTES DA KY, KHONG CO SNAPSHOT]`
- research/orchestration/RND-20260923-1472cd05/publication_receipt.json — `[HEAD KHAC BYTES DA KY, KHONG CO SNAPSHOT]`
- research/orchestration/RND-20260923-1472cd05/qa_report.json — `[HEAD KHAC BYTES DA KY, KHONG CO SNAPSHOT]`
- tests/test_material_evidence.py — `[HEAD KHAC BYTES DA KY, KHONG CO SNAPSHOT]`
- tests/test_nsga2_repaired_operators.py — `[HEAD KHAC BYTES DA KY, KHONG CO SNAPSHOT]`
- tests/test_rl_env.py — `[HEAD KHAC BYTES DA KY, KHONG CO SNAPSHOT]`
- tests/test_state.py — `[HEAD KHAC BYTES DA KY, KHONG CO SNAPSHOT]`

### Danh sách 86 file CRLF

- `bridge_evolution/collaboration/lab.py`
- `bridge_evolution/evaluate.py`
- `bridge_evolution/knowledge/local_library.py`
- `bridge_evolution/optimization/nsga2.py`
- `bridge_grammar/experimental/arch_deck_v1.json`
- `contracts/bridge_design_state.schema.json`
- `contracts/design_loop_report.schema.json`
- `contracts/site_hazard_profile.schema.json`
- `docs/design_basis/DB-SUPERT-38M.json`
- `docs/sage_evobridge/beam_contract.json`
- `docs/sage_evobridge/budget_contract.json`
- `docs/sage_evobridge/collateral_contract.json`
- `docs/sage_evobridge/unsupported_contract.json`
- `experiments/results/grammar_ab_20260821T061537.020446Z/oracle_comparison.md`
- `experiments/results/grammar_ab_20260821T061537.020446Z/summary.md`
- `experiments/results/nsga2_operator_ab/pytest_full_suite_long_basetemp.log`
- `experiments/results/nsga2_operator_ab/pytest_rerun_short_basetemp.log`
- `experiments/results/nsga2_operator_ab/summary.json`
- `experiments/shape_discovery/arch_render_study.md`
- `experiments/shape_discovery/pre_registration.json`
- `experiments/validation/opensees_brd044_benchmarks.json`
- `experiments/validation/opensees_brd045_benchmarks.json`
- `experiments/validation/opensees_brd045_negative_result.json`
- `research/library/README.md`
- `research/literature/README.md`
- `research/literature/index.json`
- `research/orchestration/RND-20260901-00fd963d/b1_1440_checks.json`
- `research/orchestration/RND-20260901-00fd963d/b1_1440_cross_section.svg`
- `research/orchestration/RND-20260901-00fd963d/b1_1440_elevation.svg`
- `research/orchestration/RND-20260901-00fd963d/b1_1440_geometry.json`
- `research/orchestration/RND-20260901-00fd963d/b1_1440_nodes.csv`
- `research/orchestration/RND-20260922-74117064/MASTER_PROMPT.md`
- `research/orchestration/RND-20260922-74117064/checkpoint_20260923_0028.json`
- `research/orchestration/RND-20260922-74117064/checkpoint_20260923_003004.json`
- `research/orchestration/RND-20260922-74117064/checkpoint_20260923_003004.md`
- `research/orchestration/RND-20260922-74117064/evidence/bootstrap_failures.json`
- `research/orchestration/RND-20260922-74117064/evidence/budget_exhausted.stdout.log`
- `research/orchestration/RND-20260922-74117064/evidence/budget_exhausted/manifest.json`
- `research/orchestration/RND-20260922-74117064/evidence/collateral.stdout.log`
- `research/orchestration/RND-20260922-74117064/evidence/collateral/manifest.json`
- `research/orchestration/RND-20260922-74117064/evidence/commands.json`
- `research/orchestration/RND-20260922-74117064/evidence/inconclusive_probe.stdout.log`
- `research/orchestration/RND-20260922-74117064/evidence/inconclusive_probe/manifest.json`
- `research/orchestration/RND-20260922-74117064/evidence/legacy_output_guard_probe.json`
- `research/orchestration/RND-20260922-74117064/evidence/restart_verification.json`
- `research/orchestration/RND-20260922-74117064/evidence/session_logs/amendment.log`
- `research/orchestration/RND-20260922-74117064/evidence/session_logs/amendment_changes.json`
- `research/orchestration/RND-20260922-74117064/evidence/session_logs/baseline_exit.txt`
- `research/orchestration/RND-20260922-74117064/evidence/session_logs/baseline_tests.log`
- `research/orchestration/RND-20260922-74117064/evidence/session_logs/claim.json`
- `research/orchestration/RND-20260922-74117064/evidence/session_logs/existing_design_loop.json`
- `research/orchestration/RND-20260922-74117064/evidence/session_logs/existing_design_loop.log`
- `research/orchestration/RND-20260922-74117064/evidence/session_logs/existing_design_loop_exit.txt`
- `research/orchestration/RND-20260922-74117064/evidence/session_logs/existing_solver_failure.json`
- `research/orchestration/RND-20260922-74117064/evidence/session_logs/existing_solver_failure_exit.txt`
- `research/orchestration/RND-20260922-74117064/evidence/session_logs/focused_01.log`
- `research/orchestration/RND-20260922-74117064/evidence/session_logs/focused_02.log`
- `research/orchestration/RND-20260922-74117064/evidence/session_logs/focused_03.log`
- `research/orchestration/RND-20260922-74117064/evidence/session_logs/git_status_before.txt`
- `research/orchestration/RND-20260922-74117064/evidence/session_logs/intake.json`
- `research/orchestration/RND-20260922-74117064/evidence/session_logs/lab_validate_pre_handoff.json`
- `research/orchestration/RND-20260922-74117064/evidence/session_logs/path_diagnostic.log`
- `research/orchestration/RND-20260922-74117064/evidence/session_logs/regression_exit.txt`
- `research/orchestration/RND-20260922-74117064/evidence/session_logs/regression_tests.log`
- `research/orchestration/RND-20260922-74117064/evidence/session_logs/tracked_before.patch`
- `research/orchestration/RND-20260922-74117064/evidence/source_snapshots/index.json`
- `research/orchestration/RND-20260922-74117064/evidence/success.stdout.log`
- `research/orchestration/RND-20260922-74117064/evidence/success/manifest.json`
- `research/orchestration/RND-20260922-74117064/evidence/unsupported.stdout.log`
- `research/orchestration/RND-20260922-74117064/evidence/unsupported/manifest.json`
- `research/orchestration/RND-20260922-74117064/session_manifest.json`
- `research/orchestration/RND-20260922-74117064/session_metadata.json`
- `research/orchestration/RND-20260923-1472cd05/README.md`
- `research/orchestration/RND-20260923-1472cd05/corpus.json`
- `research/orchestration/RND-20260923-1472cd05/independent_review.json`
- `research/orchestration/RND-20260923-1472cd05/publication_manifest.json`
- `research/orchestration/RND-20260923-1472cd05/publication_receipt.json`
- `research/orchestration/RND-20260923-1472cd05/qa_report.json`
- `tests/test_catalogs.py`
- `tests/test_local_library.py`
- `tests/test_material_evidence.py`
- `tests/test_nsga2_repaired_operators.py`
- `tests/test_rl_env.py`
- `tests/test_shape_grammar_experimental.py`
- `tests/test_site_spec.py`
- `tests/test_state.py`
