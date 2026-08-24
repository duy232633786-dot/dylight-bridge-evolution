"""Thí nghiệm A/B grammar v1 vs v2 — khóa pre-registration, cô lập arm, tái lập.

Bộ test này KHÔNG chạy thí nghiệm đầy đủ (600 solver call × 3 arm × 3 seed);
điều phối viên chạy bản đầy đủ. Ở đây chỉ dùng ngân sách rất nhỏ để khóa các
khẳng định về giao thức:

  1. **Pre-registration là bắt buộc và khóa trước** — hằng hypervolume trong file
     JSON phải khớp ĐÚNG hằng đã khóa trong ``experiments/run_baseline.py`` (so
     bằng import, không chép tay), và thiếu file thì thí nghiệm phải DỪNG.
  2. **Arm được cô lập** — arm A2 không bao giờ sinh ra gene có
     ``girder_concrete_id`` ngoài {C40, C45, C50}; A1 luôn ở family v1; A3 luôn ở
     family v2.
  3. **Ngân sách đúng nghĩa** — mỗi run tiêu không quá ``--budget`` lần
     ``solver.status != NOT_RUN``.
  4. **Tái lập** — cùng seed, hai thư mục khác nhau ⇒ summary.csv giống hệt.
  5. **Đường tìm kiếm riêng của A2 tương đương API tham chiếu** — với miền KHÔNG
     bị cắt, bản sao trong ``run_grammar_ab`` phải cho lịch sử trùng khớp
     ``random_search``/``nsga2``. Nếu không, chênh lệch giữa A2 và A1/A3 lẫn cả
     hiệu ứng hiện thực thuật toán, và so sánh mất giá trị.
  6. **Phán quyết không được vượt cổng trung thực** — run bị điều kiện vô hiệu
     chạm vào, hoặc chạy lệch run matrix đã đăng ký, KHÔNG BAO GIỜ được nhận
     phán quyết ``ĐẠT``; trung bình phải ghi rõ dùng bao nhiêu trên tổng bao
     nhiêu run; ngân sách solver thực tiêu phải hiện trong báo cáo.
"""
import csv
import hashlib
import json

import pytest

from bridge_evolution.optimization import nsga2, random_search
from bridge_evolution.optimization.common import gene_domains
from experiments import run_baseline, run_grammar_ab

#: Ngân sách smoke — cố định TRƯỚC, chỉ đủ để kiểm giao thức chứ không so sánh arm.
SMOKE_BUDGET = 12
SMOKE_SEED = 42

#: Miền bê tông dầm mà arm A2 được phép dùng (đúng tập của grammar v1).
A2_ALLOWED_CONCRETE = {"C40", "C45", "C50"}

GRAMMAR_V1 = "super_t_simple_v1"
GRAMMAR_V2 = "super_t_parametric_v2"


def _smoke(tmp_dir, arms="A1,A2,A3", algos="rs", seeds=str(SMOKE_SEED)):
    return run_grammar_ab.main([
        "--budget", str(SMOKE_BUDGET), "--seeds", seeds, "--algos", algos,
        "--arms", arms, "--pop", "6", "--output-dir", str(tmp_dir),
    ])


@pytest.fixture(scope="module")
def smoke_run(tmp_path_factory):
    """Một lần chạy smoke dùng chung cho nhiều khẳng định (giữ bộ test nhanh)."""
    out = tmp_path_factory.mktemp("ab") / "run"
    return _smoke(out)


# --------------------------------------------------------- pre-registration
def test_preregistration_valid():
    """File tồn tại, đủ khóa bắt buộc, và hằng HV khớp bản đã khóa trong run_baseline."""
    path = run_grammar_ab.DEFAULT_PREREG
    assert path.is_file(), f"thiếu pre-registration: {path}"
    prereg = json.loads(path.read_text(encoding="utf-8"))

    for key in run_grammar_ab.REQUIRED_PREREG_KEYS:
        assert key in prereg, f"pre-registration thiếu khóa {key}"

    # Hằng HV so bằng IMPORT, không chép tay: nếu run_baseline đổi mà prereg
    # không đổi thì test này phải đỏ.
    hv = prereg["hypervolume_protocol"]
    assert tuple(hv["ideal_3d"]) == run_baseline.HV_IDEAL_3D
    assert tuple(hv["reference_3d"]) == run_baseline.HV_REFERENCE_3D
    assert hv["mc_samples"] == run_baseline.HV_MC_SAMPLES
    assert hv["mc_seed"] == run_baseline.HV_MC_SEED
    assert hv["locked_before_experiment"] is True

    # Ba arm, đúng vai trò đã đăng ký.
    arms = run_grammar_ab.arms_by_id(prereg)
    assert set(arms) == {"A1_v1_catalog", "A2_v2_shape_only", "A3_v2_full"}
    assert arms["A1_v1_catalog"]["grammar_id"] == GRAMMAR_V1
    assert arms["A2_v2_shape_only"]["grammar_id"] == GRAMMAR_V2
    assert arms["A3_v2_full"]["grammar_id"] == GRAMMAR_V2
    assert (set(arms["A2_v2_shape_only"]["domain_restriction"]["girder_concrete_id"])
            == A2_ALLOWED_CONCRETE)
    assert not arms["A1_v1_catalog"]["domain_restriction"]
    assert not arms["A3_v2_full"]["domain_restriction"]

    # Giao thức nghiên cứu: ngân sách, seed, tiêu chí bác bỏ, claim ceiling.
    assert prereg["budget_definition"].startswith("solver.status != NOT_RUN")
    assert prereg["seeds"] == [42, 43, 44]
    assert prereg["decision_rule"]["improvement_threshold_relative"] == 0.02
    assert prereg["claim_ceiling"] == "SCREENED"
    assert prereg["confounds"]["not_separable_in_this_experiment"]
    assert prereg["invalidation_conditions"]["conditions"]

    # load_preregistration là cổng chặn thật, không chỉ đọc file.
    assert run_grammar_ab.load_preregistration(path)["preregistration_id"] == (
        "grammar_ab_v1_vs_v2")


def test_refuses_without_prereg(tmp_path):
    """Không có pre-registration ⇒ DỪNG có kiểm soát, KHÔNG tạo artifact nào."""
    missing = tmp_path / "khong-ton-tai.json"
    out = tmp_path / "should-not-exist"
    with pytest.raises((FileNotFoundError, SystemExit)):
        run_grammar_ab.main([
            "--budget", "4", "--seeds", "42", "--algos", "rs", "--arms", "A1",
            "--preregistration", str(missing), "--output-dir", str(out),
        ])
    # Thí nghiệm không được chạy nửa vời rồi để lại thư mục kết quả.
    assert not out.exists()


def test_rejects_prereg_with_tampered_hv_reference(tmp_path):
    """Reference point bị nới ⇒ DỪNG; không được suy/sửa ref theo kết quả."""
    prereg = json.loads(run_grammar_ab.DEFAULT_PREREG.read_text(encoding="utf-8"))
    prereg["hypervolume_protocol"]["reference_3d"] = [9_999.0, 9_999.0, 999_999.0]
    tampered = tmp_path / "tampered.json"
    tampered.write_text(json.dumps(prereg, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="reference_3d"):
        run_grammar_ab.load_preregistration(tampered)


# ------------------------------------------------------------------- smoke
def test_ab_smoke_runs(smoke_run):
    """Chạy được 3 arm ở ngân sách nhỏ và sinh đủ artifact chuẩn."""
    out = smoke_run
    for name in ("summary.csv", "summary.md", "manifest.json"):
        assert (out / name).is_file(), f"thiếu artifact {name}"

    rows = list(csv.DictReader((out / "summary.csv").open(encoding="utf-8")))
    assert len(rows) == 3                       # 3 arm × 1 thuật toán × 1 seed
    assert {r["arm_id"] for r in rows} == {
        "A1_v1_catalog", "A2_v2_shape_only", "A3_v2_full"}
    for row in rows:
        assert int(row["solver_calls"]) <= SMOKE_BUDGET
        assert int(row["seed"]) == SMOKE_SEED
        assert int(row["budget_solver_calls"]) == SMOKE_BUDGET

    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    # Pre-registration nhúng NGUYÊN VĂN + hash của chính nó.
    assert manifest["preregistration"]["preregistration_id"] == "grammar_ab_v1_vs_v2"
    assert len(manifest["preregistration_sha256"]) == 64
    assert manifest["software_version"]
    assert manifest["budget_definition"] == "solver.status != NOT_RUN"
    assert manifest["claim_ceiling"] == "SCREENED"
    assert tuple(manifest["hypervolume_protocol"]["reference_3d"]) == (
        run_baseline.HV_REFERENCE_3D)
    # SHA-256 phủ mọi file kết quả (manifest tự nó viết sau nên không tự hash).
    assert "summary.csv" in manifest["artifact_sha256"]
    assert "summary.md" in manifest["artifact_sha256"]
    assert all(len(h) == 64 for h in manifest["artifact_sha256"].values())
    for run in manifest["runs"]:
        assert run["counters"]["solver_calls"] <= SMOKE_BUDGET

    # Mỗi run có đủ history/proposals/pareto theo chuẩn run_baseline.
    for run in manifest["runs"]:
        key = run["run_key"]
        for suffix in (f"history_{key}.csv", f"history_{key}.jsonl",
                       f"proposals_{key}.jsonl", f"pareto_{key}.json"):
            assert (out / suffix).is_file(), f"thiếu {suffix}"

    text = (out / "summary.md").read_text(encoding="utf-8")
    assert "Đánh giá theo tiêu chí bác bỏ đã đăng ký" in text
    assert "Cảnh báo suy biến" in text
    assert "SCREENED" in text


def test_arms_isolated(smoke_run):
    """A2 không bao giờ đề xuất bê tông ngoài {C40,C45,C50}; family đúng theo arm."""
    out = smoke_run
    expected_family = {
        "A1_v1_catalog": GRAMMAR_V1,
        "A2_v2_shape_only": GRAMMAR_V2,
        "A3_v2_full": GRAMMAR_V2,
    }
    seen_arms = set()
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))

    for run in manifest["runs"]:
        arm_id, key = run["arm_id"], run["run_key"]
        seen_arms.add(arm_id)
        assert run["grammar_id"] == expected_family[arm_id]

        # proposal_history chứa MỌI ứng viên từng được đề xuất, kể cả bị L0 loại
        # và cache hit — nên đây là bằng chứng miền bị cắt trước khi đề xuất, chứ
        # không phải lọc sau khi đã tiêu ngân sách.
        proposals = [json.loads(line) for line in
                     (out / f"proposals_{key}.jsonl").read_text(
                         encoding="utf-8").splitlines()]
        assert proposals, f"{key}: không có proposal nào"
        concretes = {p["gene"]["girder_concrete_id"] for p in proposals}
        if arm_id == "A2_v2_shape_only":
            assert concretes <= A2_ALLOWED_CONCRETE, (
                f"A2 rò rỉ bê tông ngoài miền: {concretes - A2_ALLOWED_CONCRETE}")

        records = [json.loads(line) for line in
                   (out / f"history_{key}.jsonl").read_text(
                       encoding="utf-8").splitlines()]
        assert records
        for rec in records:
            assert rec["design_state"]["family"] == expected_family[arm_id]
            if arm_id == "A2_v2_shape_only":
                assert rec["gene"]["girder_concrete_id"] in A2_ALLOWED_CONCRETE

        # v1 chọn tiết diện định hình; v2 khóa marker tham số hóa.
        catalogs = {p["gene"]["girder_catalog_id"] for p in proposals}
        if arm_id == "A1_v1_catalog":
            assert catalogs <= {"ST-1650", "ST-1750", "ST-1850"}
            assert all("girder_depth_mm" not in p["gene"] for p in proposals)
        else:
            assert catalogs == {"ST-PARAM"}
            # v2 phải THẬT SỰ tìm kiếm trên 6 biến hình dạng.
            assert all("girder_depth_mm" in p["gene"] for p in proposals)

    assert seen_arms == set(expected_family)


def test_reproducible(tmp_path):
    """Cùng seed, hai thư mục khác nhau ⇒ summary.csv giống hệt tới từng byte."""
    first = _smoke(tmp_path / "run-1", arms="A1,A2")
    second = _smoke(tmp_path / "run-2", arms="A1,A2")
    assert first != second
    assert ((first / "summary.csv").read_bytes()
            == (second / "summary.csv").read_bytes())


# ------------------------------------------- cô lập miền và tương đương đường A2
def test_restricted_domains_only_narrows():
    """Miền bị cắt giữ thứ tự grammar, chỉ thu hẹp, và từ chối giá trị lạ."""
    full = gene_domains(GRAMMAR_V2)
    narrowed = run_grammar_ab.restricted_domains(
        GRAMMAR_V2, {"girder_concrete_id": ["C40", "C45", "C50"]})
    assert list(narrowed) == list(full)              # thứ tự biến không đổi
    assert narrowed["girder_concrete_id"] == ["C40", "C45", "C50"]
    for name, values in narrowed.items():
        assert set(values) <= set(full[name])        # chỉ thu hẹp, không mở rộng

    # Thứ tự người viết liệt kê không ảnh hưởng kết quả (tái lập được).
    shuffled = run_grammar_ab.restricted_domains(
        GRAMMAR_V2, {"girder_concrete_id": ["C50", "C40", "C45"]})
    assert shuffled == narrowed

    with pytest.raises(ValueError, match="không được mở rộng miền"):
        run_grammar_ab.restricted_domains(
            GRAMMAR_V2, {"girder_concrete_id": ["C40", "C70"]})
    with pytest.raises(ValueError, match="không có trong grammar"):
        run_grammar_ab.restricted_domains(GRAMMAR_V2, {"khong_ton_tai": [1]})


def _fingerprint(run: dict) -> str:
    """Chữ ký xác định của một run: gene, hash, status và ngân sách đã tiêu."""
    return json.dumps({
        "counters": run["counters"],
        "history": [{k: r[k] for k in ("record_index", "solver_call_index",
                                       "input_hash", "gene", "status",
                                       "solver_status", "feasible", "objectives")}
                    for r in run["history"]],
        "proposals": [{k: p[k] for k in ("proposal_index", "input_hash", "gene",
                                         "outcome")} for p in run["proposal_history"]],
        "front": sorted(e["objectives"] for e in run["archive"].entries),
    }, ensure_ascii=False, sort_keys=True, default=list)


@pytest.mark.parametrize("algo", ["rs", "nsga2"])
def test_restricted_path_matches_reference_when_unrestricted(algo):
    """Đường riêng của A2 phải TRÙNG API tham chiếu khi miền không bị cắt.

    Đây là điều kiện tiên quyết để A2 so sánh được với A1/A3: nếu hai đường cho
    lịch sử khác nhau thì chênh lệch giữa các arm lẫn cả hiệu ứng hiện thực
    thuật toán chứ không chỉ hiệu ứng grammar (invalidation condition
    EQUIVALENCE_GUARD_FAILED trong pre-registration).
    """
    budget, seed = 10, 3
    domains = gene_domains(GRAMMAR_V2)
    if algo == "rs":
        reference = random_search(budget, seed, grammar_id=GRAMMAR_V2)
        mirrored = run_grammar_ab._restricted_random_search(
            budget, seed, GRAMMAR_V2, domains)
    else:
        reference = nsga2(budget, seed, pop_size=6, grammar_id=GRAMMAR_V2)
        mirrored = run_grammar_ab._restricted_nsga2(
            budget, seed, GRAMMAR_V2, domains, pop_size=6)
    assert _fingerprint(mirrored) == _fingerprint(reference)


# =========================================================================
# Cổng trung thực của phán quyết (đợt sửa sau review đối kháng)
# =========================================================================
#: Giá trị KHÓA TRƯỚC ở pre-registration 1.0.0. Bản 1.1.0 chỉ được BỔ SUNG
#: confound và điều kiện vô hiệu; đụng vào bất kỳ giá trị nào dưới đây là sửa
#: tiêu chí sau khi đã thấy kết quả, và test này phải đỏ.
FROZEN_SEEDS = [42, 43, 44]
FROZEN_BUDGET_PER_RUN = 600
FROZEN_IMPROVEMENT_THRESHOLD = 0.02
FROZEN_PRIMARY_METRIC = "best_relative_cost"
FROZEN_DECISION_RULE_TEXT = (
    "Kết luận grammar v2 tốt hơn v1 CHỈ được phát biểu khi, với arm v2 đang xét, "
    "trên TẤT CẢ seed đã đăng ký VÀ TẤT CẢ thuật toán đã chạy: (a) (best_cost_A1 - "
    "best_cost_v2) / best_cost_A1 >= 0.02, VÀ (b) hypervolume_2d_cost_carbon_v2 >= "
    "hypervolume_2d_cost_carbon_A1. Chỉ cần MỘT cặp (thuật toán, seed) không đạt "
    "là kết luận bị bác."
)
FROZEN_SECONDARY_GUARD = (
    "hypervolume_2d_cost_carbon của arm v2 phải KHÔNG NHỎ HƠN arm A1 ở cùng cặp "
    "(thuật toán, seed)."
)
FROZEN_ATTRIBUTION_RULE = (
    "Nếu A3 đạt tiêu chí mà A2 không đạt thì phần cải thiện được quy cho BÊ TÔNG "
    "CƯỜNG ĐỘ CAO (C55/C60), KHÔNG được quy cho tự do hình dạng."
)
FROZEN_ON_FAILURE = (
    "Ghi nhận KẾT QUẢ ÂM một cách tường minh trong summary.md và trong handoff. "
    "Không được đổi ngưỡng, không được bỏ seed, không được chọn thuật toán có lợi "
    "sau khi đã thấy số liệu."
)


@pytest.fixture(scope="module")
def prereg():
    return run_grammar_ab.load_preregistration(run_grammar_ab.DEFAULT_PREREG)


def _fake_run(arm_id, algo_id, seed, *, budget=FROZEN_BUDGET_PER_RUN,
              termination="budget_exhausted"):
    """Run tối giản đủ cho _invalidation_flags / _evaluate_decision_rule."""
    return {"arm_id": arm_id, "algo_id": algo_id, "seed": seed,
            "grammar_id": GRAMMAR_V1, "search_path": "reference_api",
            "termination": termination,
            "config": {"budget_solver_calls": budget}}


def _fake_summary(best_cost, hv2d, **override):
    """Summary 'khỏe mạnh': không điều kiện vô hiệu nào được phép kích hoạt."""
    summary = {
        "feasible_count": 60, "archive_size": 5, "solver_calls": FROZEN_BUDGET_PER_RUN,
        "solver_conditional_feasible_rate": 0.5, "corr_sample_size": 60,
        "corr_cost_mass": 0.5, "corr_cost_carbon": 0.6, "corr_mass_carbon": 0.7,
        "best_relative_cost": best_cost, "hypervolume_2d_cost_carbon": hv2d,
        # Các khóa còn lại chỉ để render được bảng báo cáo.
        "median_feasible_cost": best_cost + 100.0, "first_feasible_solver_call": 1,
        "hypervolume_3d_mc": 3.0e11, "best_material_mass_t": 530.0,
        "best_embodied_carbon": 90000.0, "proposals": 11000, "l0_checks": 11000,
        "l0_rejected": 10400, "cache_hits": 0, "termination": "budget_exhausted",
    }
    summary.update(override)
    return summary


def _winning_matrix():
    """Ma trận đầy đủ trong đó arm v2 THẮNG rõ ràng ở mọi cặp (thuật toán, seed)."""
    items = []
    for algo in ("rs", "nsga2"):
        for seed in FROZEN_SEEDS:
            items.append({"run": _fake_run("A1_v1_catalog", algo, seed),
                          "summary": _fake_summary(2000.0, 4.0e8)})
            items.append({"run": _fake_run("A2_v2_shape_only", algo, seed),
                          "summary": _fake_summary(1800.0, 4.5e8)})
    return items


def _compliant(prereg, **override):
    kwargs = {
        "budget": prereg["budget_per_run"],
        "seeds": list(prereg["seeds"]),
        "algo_names": [a["algorithm_id"] for a in prereg["algorithms"]],
        "arms": [a["arm_id"] for a in prereg["arms"]],
        "pop": next(a["pop_size"] for a in prereg["algorithms"]
                    if a["algorithm_id"] == "nsga2"),
    }
    kwargs.update(override)
    return run_grammar_ab._protocol_compliance(prereg, **kwargs)


def test_fixture_can_reach_pass_verdict(prereg):
    """Neo âm bản: ma trận sạch và thắng rõ PHẢI cho ĐẠT.

    Không có test này thì mọi khẳng định "không bao giờ ĐẠT" ở dưới đều vô nghĩa
    (một hàm luôn trả VÔ HIỆU cũng sẽ qua).
    """
    items = _winning_matrix()
    flags = run_grammar_ab._invalidation_flags(items, prereg)
    assert flags == [], f"ma trận neo lẽ ra phải sạch: {flags}"
    compliance = _compliant(prereg)
    assert compliance["matches"]
    assert compliance["deviations"] == []
    assert compliance["label"] == run_grammar_ab.COMPLIANCE_LABEL == "khớp giao thức"
    decision = run_grammar_ab._evaluate_decision_rule(
        items, prereg, "A1_v1_catalog", flags, compliance)
    assert decision["arms"]["A2_v2_shape_only"]["verdict"] == run_grammar_ab.VERDICT_PASS


def test_degenerate_front_never_yields_pass(prereg):
    """M1 — một run bị DEGENERATE_FRONT ⇒ phán quyết là VÔ HIỆU, không bao giờ ĐẠT."""
    items = _winning_matrix()
    # Đúng MỘT run của arm v2 có front suy biến; mọi thứ khác vẫn thắng rõ.
    items[1]["summary"]["archive_size"] = 1
    flags = run_grammar_ab._invalidation_flags(items, prereg)
    assert any(f["condition_id"] == "DEGENERATE_FRONT" for f in flags)

    decision = run_grammar_ab._evaluate_decision_rule(
        items, prereg, "A1_v1_catalog", flags, _compliant(prereg))
    verdict = decision["arms"]["A2_v2_shape_only"]
    assert verdict["verdict"] == run_grammar_ab.VERDICT_VOID
    assert verdict["verdict"] != run_grammar_ab.VERDICT_PASS
    # Phán quyết thô vẫn là ĐẠT — bằng chứng rằng chính cổng vô hiệu đã chặn.
    assert verdict["verdict_ignoring_invalidation"] == run_grammar_ab.VERDICT_PASS
    assert verdict["void_pair_count"] == 1
    assert any("DEGENERATE_FRONT" in reason for reason in verdict["void_reasons"])
    # Cặp dính vô hiệu mang trạng thái thứ ba, không phải OK.
    void_pairs = [p for p in verdict["pairs"] if p["void_reasons"]]
    assert [p["status"] for p in void_pairs] == [run_grammar_ab.VERDICT_VOID]


def test_invalid_baseline_run_also_voids_the_pair(prereg):
    """Vô hiệu ở run ĐỐI CHỨNG cũng làm cặp đó vô hiệu (so sánh cần cả hai vế)."""
    items = _winning_matrix()
    items[0]["summary"]["feasible_count"] = 0          # run A1 của cặp (rs, 42)
    flags = run_grammar_ab._invalidation_flags(items, prereg)
    assert any(f["condition_id"] == "NO_FEASIBLE" for f in flags)
    decision = run_grammar_ab._evaluate_decision_rule(
        items, prereg, "A1_v1_catalog", flags, _compliant(prereg))
    assert decision["arms"]["A2_v2_shape_only"]["verdict"] == run_grammar_ab.VERDICT_VOID


def test_protocol_deviation_forbids_pass(prereg):
    """M2 — chạy lệch run matrix ⇒ dán nhãn lệch và CẤM phán quyết ĐẠT."""
    items = _winning_matrix()
    flags = run_grammar_ab._invalidation_flags(items, prereg)
    assert flags == []
    deviant = _compliant(prereg, seeds=[42])           # bỏ bớt seed sau khi thấy số liệu
    assert not deviant["matches"]
    assert deviant["label"] == run_grammar_ab.DEVIATION_LABEL
    assert [d["field"] for d in deviant["deviations"]] == ["seeds"]
    assert deviant["deviations"][0]["registered"] == FROZEN_SEEDS

    decision = run_grammar_ab._evaluate_decision_rule(
        items, prereg, "A1_v1_catalog", flags, deviant)
    verdict = decision["arms"]["A2_v2_shape_only"]
    assert verdict["verdict"] == run_grammar_ab.VERDICT_VOID
    assert run_grammar_ab.DEVIATION_LABEL in verdict["blockers"]
    assert verdict["verdict_ignoring_invalidation"] == run_grammar_ab.VERDICT_PASS


def test_compliant_run_is_labelled_and_may_pass(prereg):
    """M2 — chạy ĐÚNG ma trận thì báo cáo ghi 'khớp giao thức' và ĐẠT được phép."""
    items = _winning_matrix()
    flags = run_grammar_ab._invalidation_flags(items, prereg)
    compliance = _compliant(prereg)
    decision = run_grammar_ab._evaluate_decision_rule(
        items, prereg, "A1_v1_catalog", flags, compliance)

    class _Args:
        budget = FROZEN_BUDGET_PER_RUN
        pop = 40

    lines = run_grammar_ab._report_lines(
        _Args(), prereg, run_grammar_ab.DEFAULT_PREREG,
        ["A1_v1_catalog", "A2_v2_shape_only"],
        ["rs", "nsga2"], FROZEN_SEEDS, items, decision, flags,
        run_grammar_ab.arms_by_id(prereg),
        compliance=compliance,
        condition_status=run_grammar_ab._invalidation_condition_status(prereg, flags),
        prereg_sha="0" * 64, prereg_is_default=True)
    text = "\n".join(lines)
    assert run_grammar_ab.COMPLIANCE_LABEL in text
    assert run_grammar_ab.DEVIATION_LABEL not in text
    assert (f"### `A2_v2_shape_only` → **{run_grammar_ab.VERDICT_PASS}**") in text
    assert "(n=6/6)" in text                       # 2 thuật toán × 3 seed
    assert "| **Run KHÔNG có phương án khả thi nào** | 0/6 | 0/6 |" in text
    assert "budget_exhausted" in text              # termination của từng run


@pytest.mark.parametrize("field,value", [
    ("budget", 12), ("seeds", [42]), ("algo_names", ["rs"]),
    ("arms", ["A1_v1_catalog"]), ("pop", 6),
])
def test_every_matrix_field_is_compared(prereg, field, value):
    """Mọi trường của run matrix đều được đối chiếu, không chỉ một vài trường."""
    deviant = _compliant(prereg, **{field: value})
    assert not deviant["matches"]
    assert deviant["deviations"]


def test_smoke_report_is_labelled_as_deviating(smoke_run):
    """M2 đầu-cuối — smoke ngân sách nhỏ VẪN chạy, nhưng bị dán nhãn lệch."""
    text = (smoke_run / "summary.md").read_text(encoding="utf-8")
    manifest = json.loads((smoke_run / "manifest.json").read_text(encoding="utf-8"))

    assert run_grammar_ab.DEVIATION_LABEL in text
    compliance = manifest["protocol_compliance"]
    assert compliance["matches"] is False
    assert compliance["label"] == run_grammar_ab.DEVIATION_LABEL
    fields = {d["field"] for d in compliance["deviations"]}
    assert {"budget_per_run", "seeds", "algorithms"} <= fields
    for dev in compliance["deviations"]:
        assert f"`{dev['field']}`" in text          # lệch ở đâu phải in ra

    # CẤM ĐẠT, và trạng thái verdict phải y hệt ở summary.md và manifest.json.
    verdicts = manifest["decision_rule_evaluation"]["arms"]
    assert verdicts, "smoke phải có ít nhất một arm so với đối chứng"
    for arm_id, verdict in verdicts.items():
        assert verdict["verdict"] != run_grammar_ab.VERDICT_PASS
        assert f"### `{arm_id}` → **{verdict['verdict']}**" in text


def test_mean_cells_report_used_over_total(smoke_run):
    """M3 — mọi ô trung bình ghi n dùng/tổng; run vô khả thi được đếm riêng."""
    text = (smoke_run / "summary.md").read_text(encoding="utf-8")
    assert "(n=1/1)" in text
    assert "Run KHÔNG có phương án khả thi nào" in text

    # Đơn vị: run có metric None bị loại phải được đánh dấu, không im lặng.
    cell = run_grammar_ab.mean_std([1.0, None, 3.0])
    assert "(n=2/3)" in cell
    assert "⚠ thiếu 1 run" in cell
    assert run_grammar_ab.mean_std([None, None]).startswith("n/a (n=0/2)")
    assert "(n=2/2)" in run_grammar_ab.mean_std([1.0, 3.0])


def test_infeasible_runs_counted_separately(prereg):
    """M3 — run không có phương án khả thi nào phải được đếm, không bị nuốt lặng."""
    items = _winning_matrix()
    items[1]["summary"].update(feasible_count=0, best_relative_cost=None)
    n_zero = sum(1 for i in items if i["summary"]["feasible_count"] == 0)
    assert n_zero == 1
    flags = run_grammar_ab._invalidation_flags(items, prereg)
    assert [f["run_key"] for f in flags
            if f["condition_id"] == "NO_FEASIBLE"] == ["A2_v2_shape_only_rs_s42"]


def test_actual_solver_calls_and_termination_in_report(smoke_run):
    """M4 — solver_calls và termination THỰC TẾ của từng run có trong summary.md."""
    text = (smoke_run / "summary.md").read_text(encoding="utf-8")
    assert "solver_calls" in text and "termination" in text

    rows = list(csv.DictReader((smoke_run / "summary.csv").open(encoding="utf-8")))
    manifest = json.loads((smoke_run / "manifest.json").read_text(encoding="utf-8"))
    terminations = {r["run_key"]: r["termination"] for r in manifest["runs"]}
    for row in rows:
        key = f"{row['arm_id']}_{row['algorithm']}_s{row['seed']}"
        prefix = f"| {row['arm_id']} | {row['algorithm']} | {row['seed']} |"
        detail = [ln for ln in text.splitlines()
                  if ln.startswith(prefix) and terminations[key] in ln]
        assert len(detail) == 1, f"thiếu dòng chi tiết cho {key}"
        assert f"| {row['solver_calls']} |" in detail[0]
        assert f"| {terminations[key]} |" in detail[0]


def test_unequal_solver_budget_raises_invalidation_flag(prereg):
    """M4 — run tiêu ít solver call hơn ngân sách được cấp ⇒ cờ vô hiệu + không ĐẠT."""
    items = _winning_matrix()
    items[1]["run"]["termination"] = "proposal_guard"
    items[1]["summary"]["solver_calls"] = FROZEN_BUDGET_PER_RUN - 137

    flags = run_grammar_ab._invalidation_flags(items, prereg)
    budget_flags = [f for f in flags if f["condition_id"] == "UNEQUAL_SOLVER_BUDGET"]
    assert len(budget_flags) == 1
    assert budget_flags[0]["run_key"] == "A2_v2_shape_only_rs_s42"
    assert "proposal_guard" in budget_flags[0]["message"]

    decision = run_grammar_ab._evaluate_decision_rule(
        items, prereg, "A1_v1_catalog", flags, _compliant(prereg))
    assert decision["arms"]["A2_v2_shape_only"]["verdict"] == run_grammar_ab.VERDICT_VOID


def test_pearson_needs_at_least_three_points():
    """m7 — với đúng 2 điểm, |r| luôn bằng 1 nên phải trả None, không bật cờ giả."""
    assert run_grammar_ab._pearson([1.0, 2.0], [2.0, 4.0]) is None
    assert run_grammar_ab._pearson([1.0, 2.0], [4.0, 2.0]) is None
    assert run_grammar_ab._pearson([1.0, 2.0, 3.0], [2.0, 4.0, 6.0]) == 1.0
    # Chuỗi hằng vẫn là None (không xác định), không phải suy biến.
    assert run_grammar_ab._pearson([1.0, 1.0, 1.0], [2.0, 4.0, 6.0]) is None


def test_two_feasible_points_do_not_flag_collinear(prereg):
    """m7 — chỉ 2 điểm khả thi ⇒ không được bật OBJECTIVES_COLLINEAR."""
    items = _winning_matrix()
    items[1]["summary"].update(
        corr_sample_size=2, corr_cost_mass=None, corr_cost_carbon=None,
        corr_mass_carbon=None)
    flags = run_grammar_ab._invalidation_flags(items, prereg)
    assert not [f for f in flags if f["condition_id"] == "OBJECTIVES_COLLINEAR"]


def test_manifest_records_preregistration_sha256(smoke_run):
    """m5 — hash của chính file pre-registration đã dùng nằm trong manifest."""
    manifest = json.loads((smoke_run / "manifest.json").read_text(encoding="utf-8"))
    expected = hashlib.sha256(
        run_grammar_ab.DEFAULT_PREREG.read_bytes()).hexdigest()
    assert manifest["preregistration_sha256"] == expected
    assert manifest["preregistration_is_default_file"] is True
    assert manifest["preregistration_version"] == "1.1.0"

    text = (smoke_run / "summary.md").read_text(encoding="utf-8")
    assert expected in text                      # hash phải in ra để đối chiếu
    assert FROZEN_DECISION_RULE_TEXT in text     # nội dung tiêu chí đã dùng
    assert FROZEN_SECONDARY_GUARD in text


def test_non_default_preregistration_is_reported(tmp_path, prereg):
    """m5 — trỏ --preregistration sang file khác mặc định phải được nói rõ."""
    copy = tmp_path / "prereg-khac.json"
    copy.write_text(
        run_grammar_ab.DEFAULT_PREREG.read_text(encoding="utf-8"), encoding="utf-8")
    out = tmp_path / "run-prereg-khac"
    run_grammar_ab.main([
        "--budget", str(SMOKE_BUDGET), "--seeds", str(SMOKE_SEED), "--algos", "rs",
        "--arms", "A1,A3", "--pop", "6", "--preregistration", str(copy),
        "--output-dir", str(out),
    ])
    text = (out / "summary.md").read_text(encoding="utf-8")
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["preregistration_is_default_file"] is False
    assert "KHÔNG dùng pre-registration mặc định" in text
    assert str(copy) in text
    assert manifest["preregistration_sha256"] == hashlib.sha256(
        copy.read_bytes()).hexdigest()


def test_invalidation_thresholds_come_from_preregistration(prereg, tmp_path):
    """m6 — ngưỡng đọc từ file; đổi ngưỡng trong file thì hành vi phải đổi theo."""
    conds = run_grammar_ab._condition_index(prereg)
    assert conds["DEGENERATE_FRONT"]["threshold"]["archive_size_at_most"] == 2
    assert (conds["FEASIBLE_RATE_TOO_LOW"]["threshold"]
            ["solver_conditional_feasible_rate_below"] == 0.05)
    assert conds["OBJECTIVES_COLLINEAR"]["threshold"]["abs_pearson_at_least"] == 0.999
    assert conds["OBJECTIVES_COLLINEAR"]["threshold"]["min_sample_size"] == 3

    items = _winning_matrix()                    # archive_size = 5 ở mọi run
    assert not run_grammar_ab._invalidation_flags(items, prereg)

    tighter = json.loads(json.dumps(prereg))
    for cond in tighter["invalidation_conditions"]["conditions"]:
        if cond["condition_id"] == "DEGENERATE_FRONT":
            cond["threshold"]["archive_size_at_most"] = 9
    flags = run_grammar_ab._invalidation_flags(items, tighter)
    assert flags and all(f["condition_id"] == "DEGENERATE_FRONT" for f in flags)

    # Thiếu ngưỡng ⇒ DỪNG, không âm thầm rơi về hằng trong code.
    broken = json.loads(json.dumps(prereg))
    for cond in broken["invalidation_conditions"]["conditions"]:
        if cond["condition_id"] == "DEGENERATE_FRONT":
            cond.pop("threshold")
    with pytest.raises(ValueError, match="DEGENERATE_FRONT"):
        run_grammar_ab._invalidation_flags(items, broken)


def test_unevaluated_conditions_are_declared_explicitly(prereg, smoke_run):
    """m6 — điều kiện chưa đánh giá tự động phải được LIỆT KÊ, không im lặng."""
    status = run_grammar_ab._invalidation_condition_status(prereg, [])
    assert {r["condition_id"] for r in status} == {
        c["condition_id"] for c in prereg["invalidation_conditions"]["conditions"]}
    not_auto = {r["condition_id"] for r in status
                if not r["auto_evaluated_in_runner"]}
    assert not_auto == {"HV_DOMAIN_VIOLATION", "EQUIVALENCE_GUARD_FAILED"}
    for row in status:
        if row["condition_id"] in not_auto:
            assert row["status"] == "CHƯA ĐƯỢC ĐÁNH GIÁ TỰ ĐỘNG"
            assert row["evaluation_note"]

    text = (smoke_run / "summary.md").read_text(encoding="utf-8")
    for condition_id in {c["condition_id"]
                         for c in prereg["invalidation_conditions"]["conditions"]}:
        assert f"`{condition_id}`" in text
    assert "CHƯA ĐƯỢC ĐÁNH GIÁ TỰ ĐỘNG" in text


def test_preregistration_lying_about_auto_evaluation_is_rejected(tmp_path):
    """m6 — file tuyên bố tự đánh giá một điều kiện runner không hiện thực ⇒ DỪNG."""
    prereg = json.loads(
        run_grammar_ab.DEFAULT_PREREG.read_text(encoding="utf-8"))
    for cond in prereg["invalidation_conditions"]["conditions"]:
        if cond["condition_id"] == "EQUIVALENCE_GUARD_FAILED":
            cond["auto_evaluated_in_runner"] = True
    path = tmp_path / "noi-doi.json"
    path.write_text(json.dumps(prereg, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="EQUIVALENCE_GUARD_FAILED"):
        run_grammar_ab.load_preregistration(path)


# ------------------------------- pre-registration 1.1.0 vs 1.0.0 (m8)
def test_amendment_1_1_0_declares_itself_post_hoc(prereg):
    """m8 — sửa đổi sau khi thấy kết quả phải tự khai báo, không được giấu."""
    assert prereg["preregistration_version"] == "1.1.0"
    amendments = prereg["amendments"]
    assert amendments, "1.1.0 phải có mảng amendments"
    latest = amendments[-1]
    assert latest["version"] == "1.1.0"
    assert latest["made_after_seeing_results"] is True
    assert latest["date_utc"]
    assert latest["reason"]
    assert latest["changed_fields"]


def test_amendment_1_1_0_keeps_frozen_criteria_unchanged(prereg):
    """m8 — 1.1.0 KHÔNG được đụng vào tiêu chí/ngưỡng/seed/ngân sách của 1.0.0."""
    rule = prereg["decision_rule"]
    assert rule["improvement_threshold_relative"] == FROZEN_IMPROVEMENT_THRESHOLD
    assert rule["primary_metric"] == FROZEN_PRIMARY_METRIC
    assert rule["rule"] == FROZEN_DECISION_RULE_TEXT
    assert rule["secondary_guard"] == FROZEN_SECONDARY_GUARD
    assert rule["attribution_rule"] == FROZEN_ATTRIBUTION_RULE
    assert rule["on_failure"] == FROZEN_ON_FAILURE
    assert prereg["seeds"] == FROZEN_SEEDS
    assert prereg["budget_per_run"] == FROZEN_BUDGET_PER_RUN

    hv = prereg["hypervolume_protocol"]
    assert hv["ideal_3d"] == [0.0, 0.0, 0.0]
    assert hv["reference_3d"] == [5000.0, 1200.0, 250000.0]
    assert hv["mc_samples"] == 40000
    assert hv["mc_seed"] == 1729

    # Điều kiện vô hiệu của 1.0.0 phải còn nguyên, chỉ được THÊM cái mới.
    ids = [c["condition_id"] for c in prereg["invalidation_conditions"]["conditions"]]
    assert {"DEGENERATE_FRONT", "NO_FEASIBLE", "FEASIBLE_RATE_TOO_LOW",
            "OBJECTIVES_COLLINEAR", "HV_DOMAIN_VIOLATION",
            "EQUIVALENCE_GUARD_FAILED"} <= set(ids)
    assert "UNEQUAL_SOLVER_BUDGET" in ids       # điều kiện SIẾT THÊM ở 1.1.0


def test_l0_asymmetry_confound_is_registered_with_measured_numbers(prereg):
    """m8 — confound bất đối xứng sàng L0 có mặt và kèm số liệu thực đo."""
    confounds = prereg["confounds"]
    assert any("SÀNG L0" in c.upper()
               for c in confounds["not_separable_in_this_experiment"])

    measured = confounds["measured_l0_screening_asymmetry"]
    assert measured["made_after_seeing_results"] is True
    assert measured["source_run"].startswith("experiments/results/grammar_ab_")
    rows = measured["per_arm_algorithm"]
    assert {r["arm_id"] for r in rows} == {
        "A1_v1_catalog", "A2_v2_shape_only", "A3_v2_full"}
    for row in rows:
        assert row["l0_checks_total_3_seeds"] > 0
        assert 0.0 < row["l0_pass_rate"] < 1.0
    # Số thật, không phải chỗ giữ chỗ: rs của v2 sàng nhiều hơn v1 rõ rệt.
    rs = {r["arm_id"]: r for r in rows if r["algorithm"] == "rs"}
    assert (rs["A2_v2_shape_only"]["l0_checks_total_3_seeds"]
            > 10 * rs["A1_v1_catalog"]["l0_checks_total_3_seeds"])
    assert measured["honest_reading"]


def test_l0_counters_are_reported_per_run(smoke_run):
    """m8 — số lần sàng L0 miễn phí phải xuất hiện trong artifact, không bị giấu."""
    rows = list(csv.DictReader((smoke_run / "summary.csv").open(encoding="utf-8")))
    for row in rows:
        assert int(row["l0_checks"]) >= int(row["l0_rejected"]) >= 0
    text = (smoke_run / "summary.md").read_text(encoding="utf-8")
    assert "l0_checks" in text
    assert "Sàng L0 miễn phí" in text
