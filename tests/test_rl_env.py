"""Test MODULE P5 — RL environment + safety shield + Q-learning."""
import random

import numpy as np

from bridge_evolution.optimization.common import BudgetedEvaluator, GENE_ORDER, gene_domains
from bridge_evolution.rl_env import ACTIONS, BridgeEnv, train_qlearning
from bridge_evolution.rl_env.reward import compute_reward
from bridge_evolution.rl_env.shield import valid_action_mask


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
