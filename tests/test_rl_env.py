"""Test MODULE P5 — RL environment + safety shield + Q-learning."""
import random

import numpy as np
import pytest

from bridge_evolution.geometry import check_geometry
from bridge_evolution.optimization.common import BudgetedEvaluator, GENE_ORDER, gene_domains
from bridge_evolution.optimization.common import gene_order
from bridge_evolution.rl_env import ACTIONS, BridgeEnv, train_qlearning
from bridge_evolution.rl_env.actions import build_actions, submit_index
from bridge_evolution.rl_env.env import (
    OBS_DIM, _RESET_MIN_DRAWS, _fallback_idx_vec, _reset_max_draws, obs_dim,
)
from bridge_evolution.rl_env.reward import (
    STEP_PENALTY, compute_reward, submit_reward,
)
from bridge_evolution.rl_env.shield import decode_gene, gene_l0_valid, valid_action_mask
from bridge_evolution.state import state_from_gene


def _sizes() -> list[int]:
    d = gene_domains()
    return [len(d[k]) for k in GENE_ORDER]


def test_action_catalog():
    assert len(ACTIONS) == 17
    assert ACTIONS[-1][0] == "SUBMIT"
    names = [a[0] for a in ACTIONS]
    for var in GENE_ORDER:  # đủ cặp DEC/INC cho từng biến
        assert f"DEC_{var}" in names and f"INC_{var}" in names


def test_mask_bounds():
    sizes = _sizes()
    lo = valid_action_mask([0] * len(sizes), sizes, l0_precheck=False)
    hi = valid_action_mask([s - 1 for s in sizes], sizes, l0_precheck=False)
    for i, (_name, var, delta) in enumerate(ACTIONS):
        if var is None:
            continue
        if delta == -1:  # DEC bị mask ở biên dưới, hợp lệ ở biên trên
            assert not lo[i]
            assert hi[i]
        else:            # INC ngược lại
            assert lo[i]
            assert not hi[i]
    assert lo[-1] and hi[-1]  # SUBMIT luôn hợp lệ


def test_shield_blocks_l0():
    domains = gene_domains()
    gene = {"girder_catalog_id": "ST-1750", "girder_count": 6,
            "girder_spacing_mm": 2200, "deck_slab_thickness_mm": 200,
            "girder_concrete_id": "C45", "deck_concrete_id": "C35",
            "diaphragm_layout_id": "DG-5", "prestress_layout_id": "PT-46"}
    idx_vec = [domains[k].index(gene[k]) for k in GENE_ORDER]
    sizes = [len(domains[k]) for k in GENE_ORDER]
    mask = valid_action_mask(idx_vec, sizes, l0_precheck=True)
    names = [a[0] for a in ACTIONS]
    # S=2250 → cánh hẫng 0.375 m < 0.4 m; n=7 → bố trí dầm tràn khổ cầu
    assert not mask[names.index("INC_girder_spacing_mm")]
    assert not mask[names.index("INC_girder_count")]
    assert mask[names.index("SUBMIT")]


def test_env_episode():
    ev = BudgetedEvaluator(40)
    env = BridgeEnv(ev, seed=5)
    obs = env.reset()
    assert obs.shape == (15,)
    assert np.all(obs >= 0.0) and np.all(obs <= 1.5)

    rng = random.Random(5)
    done = False
    while not done:
        valid = np.flatnonzero(env.valid_actions())
        action = int(valid[rng.randrange(len(valid))])
        obs, _reward, done, _info = env.step(action)
        assert obs.shape == (15,)
        assert np.all(obs >= 0.0) and np.all(obs <= 1.5)
    assert done
    assert ev.n_solver_calls <= 40


def test_reward_hierarchy():
    """Chống reward hacking: crash solver là ĐÁY tuyệt đối của mọi nhánh reward."""
    crash = {"status": "SOLVER_FAILED", "feasible": False, "cv": 1.0, "objectives": None}
    worst_infeasible = {"status": "SUCCESS", "feasible": False, "cv": 2.0, "objectives": None}
    plain_feasible = {"status": "SUCCESS", "feasible": True, "cv": 0.0,
                      "objectives": (2600.0, 600.0, 110000.0)}

    r_crash, t_crash = compute_reward(None, crash, False)
    r_inf, t_inf = compute_reward(None, worst_infeasible, False)
    r_feas, t_feas = compute_reward(None, plain_feasible, False)

    assert r_crash == -1.0 and t_crash is True
    assert t_inf is False and t_feas is False
    assert r_crash < r_inf < r_feas
    # cv cực lớn vẫn bị chặn tại min(cv, 2) — crash vẫn thấp nhất
    much_worse = {"status": "SUCCESS", "feasible": False, "cv": 50.0, "objectives": None}
    assert compute_reward(None, much_worse, False)[0] > r_crash


def test_no_reward_farming_by_oscillation():
    """Hồi quy finding review P5: dao động giữa 2 gene feasible đã cache phải LỖ.

    Bước feasible→feasible không cải thiện nhận ròng -STEP_PENALTY < 0, và tổng
    reward một cặp đi-về (số hạng chi phí phản đối xứng) phải âm — không còn
    chính sách 'farm +0.03/bước miễn phí ngân sách rồi mới SUBMIT'.
    """
    a = {"status": "SUCCESS", "feasible": True, "cv": 0.0,
         "objectives": (2200.0, 500.0, 90000.0)}
    b = {"status": "SUCCESS", "feasible": True, "cv": 0.0,
         "objectives": (2260.0, 505.0, 90100.0)}
    r_neutral, _ = compute_reward(a, dict(a), False)
    assert r_neutral < 0.0                      # bước trung tính không được dương
    r_ab, _ = compute_reward(a, b, False)
    r_ba, _ = compute_reward(b, a, False)
    assert r_ab + r_ba < 0.0                    # cặp dao động luôn lỗ


def test_no_reward_farming_on_any_two_state_cycle():
    """Hồi quy finding CRITICAL: MỌI chu trình đóng phải LỖ, không chỉ feasible↔feasible.

    Test cũ (``test_no_reward_farming_by_oscillation``) chỉ kiểm nhánh
    feasible↔feasible — nhánh duy nhất vốn đã phản đối xứng — nên vẫn XANH trong
    khi đường farm THẬT là infeasible↔feasible: bản cũ cộng +1.0 mỗi lần vào vùng
    khả thi mà đi ra chỉ mất ~0.07, và cả hai gene đều đã nằm trong cache nên
    chu trình KHÔNG tốn một lần gọi solver nào.
    """
    feasible = {"status": "SUCCESS", "feasible": True, "cv": 0.0,
                "objectives": (2200.0, 500.0, 90000.0)}
    feasible_worse = {"status": "SUCCESS", "feasible": True, "cv": 0.0,
                      "objectives": (2260.0, 505.0, 90100.0)}
    infeasible = {"status": "SUCCESS", "feasible": False, "cv": 0.5,
                  "objectives": None}
    infeasible_worse = {"status": "SUCCESS", "feasible": False, "cv": 1.5,
                        "objectives": None}

    cycles = {
        "feasible↔feasible": (feasible, feasible_worse),
        "feasible↔chính nó": (feasible, dict(feasible)),
        "feasible↔infeasible": (feasible, infeasible),
        "infeasible↔infeasible": (infeasible, infeasible_worse),
    }
    for label, (a, b) in cycles.items():
        forward, _ = compute_reward(a, b, False)
        backward, _ = compute_reward(b, a, False)
        assert forward + backward < 0.0, f"chu trình {label} farm được"


def test_long_oscillation_is_strictly_losing():
    """Chu trình dài giữa hai gene đã cache phải lỗ tuyến tính theo số bước."""
    feasible = {"status": "SUCCESS", "feasible": True, "cv": 0.0,
                "objectives": (2200.0, 500.0, 90000.0)}
    infeasible = {"status": "SUCCESS", "feasible": False, "cv": 0.5,
                  "objectives": None}

    total, current = 0.0, feasible
    for _ in range(25):
        nxt = infeasible if current is feasible else feasible
        reward, _ = compute_reward(current, nxt, False)
        total += reward
        current = nxt
    # Trước bản sửa chuỗi này cho +9.79; giờ phải âm và thua xa SUBMIT ngay.
    assert total < 0.0
    assert total < submit_reward(feasible)


def test_shaping_is_potential_based():
    """Shaping chỉ phụ thuộc trạng thái ⇒ triệt tiêu trên chu trình đóng."""
    feasible = {"status": "SUCCESS", "feasible": True, "cv": 0.0,
                "objectives": (2200.0, 500.0, 90000.0)}
    infeasible = {"status": "SUCCESS", "feasible": False, "cv": 0.5,
                  "objectives": None}
    enter, _ = compute_reward(infeasible, feasible, False)
    leave, _ = compute_reward(feasible, infeasible, False)
    # Phần shaping của hai chiều triệt tiêu: chênh lệch còn lại chỉ là các số
    # hạng phụ thuộc trạng thái (phạt vi phạm) và hai lần STEP_PENALTY.
    assert enter + leave == pytest.approx(
        -0.05 - 0.2 * infeasible["cv"] - 2 * STEP_PENALTY, abs=1e-9)


def test_entering_feasible_still_rewarded():
    """Đóng đường farm KHÔNG được làm mất động lực đi vào vùng khả thi."""
    feasible = {"status": "SUCCESS", "feasible": True, "cv": 0.0,
                "objectives": (2200.0, 500.0, 90000.0)}
    infeasible = {"status": "SUCCESS", "feasible": False, "cv": 0.5,
                  "objectives": None}
    enter, _ = compute_reward(infeasible, feasible, False)
    stay_infeasible, _ = compute_reward(infeasible, dict(infeasible), False)
    assert enter > 0.0
    assert enter > stay_infeasible


def test_train_runs_deterministic():
    r1 = train_qlearning(budget=60, seed=3)
    r2 = train_qlearning(budget=60, seed=3)
    assert r1["algorithm"] == "qlearning" and r1["seed"] == 3
    assert r1["episodes"] == r2["episodes"]
    assert r1["counters"]["solver_calls"] == r2["counters"]["solver_calls"] == 60
    assert len(r1["history"]) == len(r2["history"])
    assert ([rec["case_id"] for rec in r1["history"]]
            == [rec["case_id"] for rec in r2["history"]])
    assert r1["proposal_history"] == r2["proposal_history"]
    assert r1["model_state"] == r2["model_state"]


# ====================================================================
# MODULE P5b — RL đa grammar: v2 (14 biến) chạy được, v1 (8 biến) đóng băng.
#
# Trước thay đổi này, ACTIONS/VAR_INDEX/OBS_DIM là hằng cấp module suy từ
# GENE_ORDER (8 biến v1), nên RL ÂM THẦM vứt 6 biến hình dạng của grammar
# super_t_parametric_v2. Các test dưới khóa hai khẳng định đối nghịch:
#   1. v1 đóng băng — 17 hành động, obs dim 15, lịch sử tái lập y như cũ;
#   2. v2 tham số hóa thật — 29 hành động, obs dim 21, shield chặn FAB-* ở L0
#      MIỄN PHÍ và Q-learning chạy trọn trong đúng ngân sách solver.
# ====================================================================
GRAMMAR_V1 = "super_t_simple_v1"
GRAMMAR_V2 = "super_t_parametric_v2"

#: 6 biến hình dạng mà v2 thêm vào so với v1 (AI tự thiết kế mặt cắt).
SHAPE_VARS = (
    "girder_depth_mm", "top_flange_width_mm", "top_flange_thickness_mm",
    "web_thickness_mm", "bottom_bulb_width_mm", "bottom_bulb_height_mm",
)

#: Mốc v2 L0-hợp lệ cho ca shield: lấy example_valid của grammar nhưng đặt
#: web_thickness_mm = 100 mm, tức ĐÚNG ngưỡng FAB-001, nên hạ một bước lưới
#: (100 -> 90 mm) chắc chắn thành vi phạm HARD FAB-001.
V2_EDGE_GENE = {
    "girder_catalog_id": "ST-PARAM", "girder_count": 6,
    "girder_spacing_mm": 2200, "deck_slab_thickness_mm": 200,
    "girder_concrete_id": "C45", "deck_concrete_id": "C35",
    "diaphragm_layout_id": "DG-5", "prestress_layout_id": "PT-42",
    "girder_depth_mm": 1750, "top_flange_width_mm": 2050,
    "top_flange_thickness_mm": 120, "web_thickness_mm": 100,
    "bottom_bulb_width_mm": 350, "bottom_bulb_height_mm": 350,
}


def _v2_idx_and_sizes(gene: dict) -> tuple[list[int], list[int]]:
    domains = gene_domains(GRAMMAR_V2)
    order = gene_order(GRAMMAR_V2)
    return ([domains[k].index(gene[k]) for k in order],
            [len(domains[k]) for k in order])


# ------------------------------------------------------------------ v1 đóng băng
def test_v1_action_space_and_obs_frozen():
    """Bản v1 cấp module không đổi, và build_actions(v1) trùng nó từng phần tử."""
    assert len(ACTIONS) == 17
    assert submit_index(ACTIONS) == 16
    assert build_actions() == ACTIONS
    assert build_actions(GRAMMAR_V1) == ACTIONS
    assert OBS_DIM == 15
    assert obs_dim() == obs_dim(GRAMMAR_V1) == OBS_DIM


# ------------------------------------------------------------------ v2 hành động
def test_build_actions_v2():
    """v2 có 14 biến nên có 29 hành động, cặp DEC/INC đúng thứ tự, SUBMIT ở CUỐI."""
    order = gene_order(GRAMMAR_V2)
    assert len(order) == 14
    actions = build_actions(GRAMMAR_V2)
    assert len(actions) == 29
    assert actions[-1] == ("SUBMIT", None, 0)
    assert submit_index(actions) == 28
    for j, var in enumerate(order):
        assert actions[2 * j] == (f"DEC_{var}", var, -1)
        assert actions[2 * j + 1] == (f"INC_{var}", var, +1)
    # Chỉ SUBMIT được phép có biến None; 6 biến hình dạng phải có mặt.
    assert [a for a in actions if a[1] is None] == [("SUBMIT", None, 0)]
    names = [a[0] for a in actions]
    for var in SHAPE_VARS:
        assert f"DEC_{var}" in names and f"INC_{var}" in names


def test_mask_v2_blocks_fabrication_violation():
    """Shield v2 chặn hành động dẫn tới vi phạm HARD FAB-* — miễn phí ở L0."""
    assert gene_l0_valid(V2_EDGE_GENE, GRAMMAR_V2)  # mốc xuất phát phải sạch
    idx_vec, sizes = _v2_idx_and_sizes(V2_EDGE_GENE)
    mask = valid_action_mask(idx_vec, sizes, True, GRAMMAR_V2)
    assert len(mask) == 29
    names = [a[0] for a in build_actions(GRAMMAR_V2)]

    # Tự chứng minh ca minh họa: 100 -> 90 mm vi phạm HARD FAB-001.
    thinner = dict(V2_EDGE_GENE, web_thickness_mm=90)
    violations, _ = check_geometry(state_from_gene(thinner, grammar_id=GRAMMAR_V2))
    fab = [v for v in violations
           if v["severity"] == "HARD" and v["rule_id"].startswith("FAB")]
    assert fab, "ca minh hoa khong con vi pham FAB-* — phai chon lai moc"

    assert not mask[names.index("DEC_web_thickness_mm")]  # bị shield chặn
    assert mask[names.index("INC_web_thickness_mm")]      # 110 mm vẫn hợp lệ
    assert mask[names.index("SUBMIT")]                    # luôn còn lối thoát


def test_mask_v2_bounds():
    """Chặn vượt biên chỉ số vẫn đúng trên toàn bộ 14 biến của v2."""
    order = gene_order(GRAMMAR_V2)
    sizes = _v2_idx_and_sizes(V2_EDGE_GENE)[1]
    actions = build_actions(GRAMMAR_V2)
    lo = valid_action_mask([0] * len(sizes), sizes, False, GRAMMAR_V2)
    hi = valid_action_mask([s - 1 for s in sizes], sizes, False, GRAMMAR_V2)
    for i, (_name, var, delta) in enumerate(actions):
        if var is None:
            continue
        j = order.index(var)
        if sizes[j] == 1:
            # girder_catalog_id của v2 bị khóa ở ST-PARAM: cả DEC lẫn INC đều
            # vượt biên nên luôn bị mask.
            assert not lo[i] and not hi[i]
        elif delta == -1:  # DEC bị mask ở biên dưới, hợp lệ ở biên trên
            assert not lo[i]
            assert hi[i]
        else:              # INC ngược lại
            assert lo[i]
            assert not hi[i]
    assert lo[-1] and hi[-1]  # SUBMIT luôn hợp lệ


# ------------------------------------------------------------------ v2 môi trường
def test_v2_fallback_start_is_l0_valid():
    """Fallback của v2 phải tự dò được (seed cố định), KHÔNG mượn gene v1."""
    fb = _fallback_idx_vec(GRAMMAR_V2)
    assert fb == _fallback_idx_vec(GRAMMAR_V2)      # tái lập
    assert len(fb) == 14
    gene = decode_gene(list(fb), GRAMMAR_V2)
    assert gene_l0_valid(gene, GRAMMAR_V2)
    assert gene["girder_catalog_id"] == "ST-PARAM"  # không phải catalog v1
    assert set(SHAPE_VARS) <= set(gene)


def test_env_v2_episode_within_budget():
    """Một episode v2 trọn vẹn: obs dim 21 và KHÔNG vượt ngân sách solver."""
    ev = BudgetedEvaluator(40, grammar_id=GRAMMAR_V2)
    env = BridgeEnv(ev, seed=5, grammar_id=GRAMMAR_V2)
    assert env.obs_dim == obs_dim(GRAMMAR_V2) == 21
    assert len(env.actions) == 29 and env.submit_index == 28

    obs = env.reset()
    assert obs.shape == (21,)
    assert np.all(obs >= 0.0) and np.all(np.isfinite(obs))

    rng = random.Random(5)
    done = False
    while not done:
        valid = np.flatnonzero(env.valid_actions())
        assert len(valid) >= 1            # SUBMIT luôn còn nên không bao giờ kẹt
        action = int(valid[rng.randrange(len(valid))])
        obs, _reward, done, _info = env.step(action)
        assert obs.shape == (21,)
        assert np.all(obs >= 0.0) and np.all(np.isfinite(obs))
    assert ev.n_solver_calls <= 40

    for rec in ev.history:
        assert list(rec["gene"]) == gene_order(GRAMMAR_V2)
        assert rec["design_state"]["family"] == GRAMMAR_V2
        for name in SHAPE_VARS:
            assert rec["design_state"]["design_variables"][name] == rec["gene"][name]


def test_train_qlearning_v2_deterministic():
    """Q-learning chạy trọn trên v2: W shape (29, 22), cùng seed cho cùng lịch sử."""
    r1 = train_qlearning(budget=60, seed=3, grammar_id=GRAMMAR_V2)
    r2 = train_qlearning(budget=60, seed=3, grammar_id=GRAMMAR_V2)

    assert r1["config"]["grammar_id"] == GRAMMAR_V2
    assert r1["config"]["n_actions"] == 29 and r1["config"]["obs_dim"] == 21
    assert np.array(r1["model_state"]["weights"]).shape == (29, 22)
    assert r1["counters"]["solver_calls"] == r2["counters"]["solver_calls"] == 60
    assert r1["episodes"] == r2["episodes"]
    assert ([rec["case_id"] for rec in r1["history"]]
            == [rec["case_id"] for rec in r2["history"]])
    assert r1["proposal_history"] == r2["proposal_history"]
    assert r1["model_state"] == r2["model_state"]

    for rec in r1["history"]:
        assert list(rec["gene"]) == gene_order(GRAMMAR_V2)
        assert rec["design_state"]["family"] == GRAMMAR_V2

    # Archive chỉ nhận phương án FEASIBLE THẬT, đối chiếu ngược vào history.
    feasible = {rec["case_id"]: rec for rec in r1["history"] if rec["feasible"]}
    for entry in r1["archive"].entries:
        rec = feasible.get(entry["case_id"])
        assert rec is not None, "archive chua case khong feasible"
        assert rec["solver_call_index"] is not None
        assert rec["objectives"] == entry["objectives"]


def test_train_qlearning_v1_shape_unchanged():
    """Mở đường v2 không được kéo v1 sang không gian 14 biến."""
    r = train_qlearning(budget=30, seed=3)
    assert r["config"]["grammar_id"] == GRAMMAR_V1
    assert np.array(r["model_state"]["weights"]).shape == (17, 16)
    for rec in r["history"]:
        assert list(rec["gene"]) == GENE_ORDER
        assert rec["design_state"]["family"] == GRAMMAR_V1


# ====================================================================
# MODULE P5c — ĐIỂM XUẤT PHÁT của reset() (finding review S2)
#
# Trần 500 lần thử được hiệu chỉnh cho mật độ L0 của v1 (~5%). Mật độ của v2 chỉ
# ~0.43% nên với trần đó ~13.8% episode (đo trên 400 seed) xuất phát từ ĐÚNG MỘT
# điểm fallback cố định — phân phối điểm xuất phát lệch nặng và chưa hề được
# pre-register. Trần bây giờ co giãn theo mật độ đo được của từng grammar.
# ====================================================================
#: Ngưỡng CHỐT TRƯỚC cho "tỷ lệ fallback không đáng kể" (đo trên nhiều seed).
MAX_FALLBACK_RATE = 0.02
FALLBACK_PROBE_SEEDS = 120


def _start_points(grammar_id: str, n_seeds: int) -> list[tuple]:
    """(idx_vec, dùng_fallback) của lần dò điểm xuất phát đầu tiên theo từng seed.

    Chỉ dùng shield L0 (miễn phí) nên evaluator budget 0 là đủ — pha dò KHÔNG
    được tiêu một lần gọi solver nào.
    """
    out = []
    for seed in range(n_seeds):
        ev = BudgetedEvaluator(0, grammar_id=grammar_id)
        env = BridgeEnv(ev, seed=seed, grammar_id=grammar_id)
        idx_vec, used_fallback = env._sample_start_idx_vec()
        assert ev.n_solver_calls == 0
        out.append((tuple(idx_vec), used_fallback))
    return out


def test_v1_start_draw_budget_frozen():
    """v1 ĐÓNG BĂNG: vẫn đúng 500 lần thử, cùng seed cho cùng điểm xuất phát."""
    assert _reset_max_draws(GRAMMAR_V1) == _RESET_MIN_DRAWS == 500
    env = BridgeEnv(BudgetedEvaluator(0), seed=5)
    assert env.max_start_draws == 500

    first = _start_points(GRAMMAR_V1, 20)
    assert first == _start_points(GRAMMAR_V1, 20)          # tái lập
    assert not any(used for _idx, used in first)           # v1 không cần fallback


def test_v2_start_draw_budget_scales_with_density():
    """v2 thưa hơn v1 ⇒ trần phải LỚN HƠN, và trần là hằng tái lập được."""
    assert _reset_max_draws(GRAMMAR_V2) > _reset_max_draws(GRAMMAR_V1)
    assert _reset_max_draws(GRAMMAR_V2) == _reset_max_draws(GRAMMAR_V2)
    env = BridgeEnv(BudgetedEvaluator(0), seed=0, grammar_id=GRAMMAR_V2)
    assert env.max_start_draws == _reset_max_draws(GRAMMAR_V2)


def test_v2_fallback_rate_is_negligible():
    """v2: tỷ lệ episode phải dùng điểm fallback cố định < ngưỡng đã chốt trước."""
    points = _start_points(GRAMMAR_V2, FALLBACK_PROBE_SEEDS)
    n_fallback = sum(used for _idx, used in points)
    assert n_fallback / FALLBACK_PROBE_SEEDS <= MAX_FALLBACK_RATE, (
        f"{n_fallback}/{FALLBACK_PROBE_SEEDS} episode xuat phat tu diem fallback")

    # Phân phối điểm xuất phát không được dồn về vài điểm: mọi điểm phải L0-hợp lệ
    # và gần như đôi một khác nhau.
    starts = {idx for idx, _used in points}
    assert len(starts) >= 0.9 * FALLBACK_PROBE_SEEDS
    for idx, _used in points[:20]:
        assert gene_l0_valid(decode_gene(list(idx), GRAMMAR_V2), GRAMMAR_V2)


def test_env_reset_reports_fallback_usage():
    """reset() ghi lại có phải dùng fallback không — đo được thay vì đoán."""
    ev = BudgetedEvaluator(2, grammar_id=GRAMMAR_V2)
    env = BridgeEnv(ev, seed=7, grammar_id=GRAMMAR_V2)
    assert env.last_reset_used_fallback is False
    env.reset()
    assert env.last_reset_used_fallback is False
    assert gene_l0_valid(decode_gene(env.idx_vec, GRAMMAR_V2), GRAMMAR_V2)
