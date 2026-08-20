"""Q-learning xấp xỉ tuyến tính (semi-gradient) với action mask từ safety shield.

Q(s, a) = W[a] @ x với x = [obs, 1.0] (bias), W shape (17, 16).
epsilon-greedy CHỈ trên hành động hợp lệ (cả nhánh greedy lẫn nhánh random);
target = r + gamma * max_valid Q(s') (bằng r nếu done).
"""
import random

import numpy as np

from ..optimization.common import BudgetedEvaluator
from ..pareto import ParetoArchive
from .actions import ACTIONS
from .env import BridgeEnv, OBS_DIM


def train_qlearning(budget: int, seed: int, max_steps: int = 25, alpha: float = 0.05,
                    gamma: float = 0.95, eps_start: float = 0.5, eps_end: float = 0.05,
                    eps_decay_episodes: int = 30) -> dict:
    """Huấn luyện Q-learning trên BridgeEnv đến khi cạn ngân sách solver.

    Tái lập: cùng seed → cùng chuỗi episode, cùng lịch sử đánh giá.
    """
    rng = random.Random(seed)
    ev = BudgetedEvaluator(budget, generation_action="QLEARNING", seed=seed)
    archive = ParetoArchive()
    env = BridgeEnv(ev, seed=seed, max_steps=max_steps, archive=archive)
    W = np.zeros((len(ACTIONS), OBS_DIM + 1), dtype=np.float64)

    def features(obs: np.ndarray) -> np.ndarray:
        return np.append(obs, 1.0)

    def select_action(q: np.ndarray, mask: np.ndarray, eps: float) -> int:
        valid = np.flatnonzero(mask)
        if rng.random() < eps:
            return int(valid[rng.randrange(len(valid))])
        return int(valid[int(np.argmax(q[valid]))])

    episodes = 0
    while not ev.exhausted:
        obs = env.reset()
        frac = 1.0 if eps_decay_episodes <= 0 else min(1.0, episodes / eps_decay_episodes)
        eps = eps_start + frac * (eps_end - eps_start)  # giảm tuyến tính theo episode

        done = False
        mask = env.valid_actions()
        while not done:
            x = features(obs)
            q = W @ x
            a = select_action(q, mask, eps)
            obs2, r, done, _info = env.step(a)
            if done:
                target = r
            else:
                mask2 = env.valid_actions()
                q2 = W @ features(obs2)
                target = r + gamma * float(np.max(q2[np.flatnonzero(mask2)]))
                mask = mask2  # tái dùng cho bước kế tiếp (shield rẻ nhưng không miễn phí)
            W[a] += alpha * (target - float(q[a])) * x  # semi-gradient TD(0)
            obs = obs2
        episodes += 1

    config = {**ev.config, "algorithm": "qlearning", "max_steps": max_steps,
              "alpha": alpha, "gamma": gamma, "eps_start": eps_start,
              "eps_end": eps_end, "eps_decay_episodes": eps_decay_episodes}
    return {"algorithm": "qlearning", "seed": seed, "config": config,
            "counters": ev.counters, "history": ev.history,
            "proposal_history": ev.proposal_history, "archive": archive,
            "episodes": episodes,
            "model_state": {"type": "linear_q", "weights": W.tolist()},
            "termination": "budget_exhausted" if ev.exhausted else "stopped"}
