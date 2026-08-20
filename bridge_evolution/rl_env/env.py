"""Môi trường RL rời rạc trên grammar Super-T: đột biến ±1 bước lưới + SUBMIT.

Mọi đánh giá thật đi qua BudgetedEvaluator (trung thực ngân sách); safety shield
(check_geometry) rẻ nên dùng tự do để mask hành động và chọn điểm xuất phát.

Observation np.float64 dim 15, THỨ TỰ CỐ ĐỊNH:
  [0..7]  idx/(size-1) của 8 biến theo GENE_ORDER
  [8]     feasible của record hiện tại (0/1)
  [9]     min(cv, 2)/2
  [10]    min(max_utilization hoặc 2.0, 2.0)/2
  [11]    cost/3000        (0 nếu objectives None)
  [12]    mass_t/1000      (0 nếu objectives None)
  [13]    carbon/150000    (0 nếu objectives None)
  [14]    steps_left/max_steps
"""
import random

import numpy as np

from ..optimization.common import GENE_ORDER, gene_domains
from ..pareto import ParetoArchive
from .actions import ACTIONS, SUBMIT_INDEX, VAR_INDEX
from .reward import compute_reward, submit_reward
from .shield import decode_gene, gene_l0_valid, valid_action_mask

OBS_DIM = 15


class BridgeEnv:
    """Env kiểu gym tối giản: reset() -> obs; step(a) -> (obs, reward, done, info)."""

    def __init__(self, evaluator, seed: int, max_steps: int = 25,
                 archive: ParetoArchive | None = None):
        self.evaluator = evaluator
        self.rng = random.Random(seed)
        self.max_steps = max_steps
        self.archive = archive if archive is not None else ParetoArchive()
        domains = gene_domains()
        self._domains = domains
        self.sizes = [len(domains[k]) for k in GENE_ORDER]
        self.idx_vec: list[int] = [0] * len(GENE_ORDER)
        self.current_record: dict | None = None
        self.steps = 0

    # ------------------------------------------------------------------ vòng đời
    def reset(self) -> np.ndarray:
        """Bắt đầu episode: điểm xuất phát ngẫu nhiên L0-hợp lệ.

        Thử tối đa 500 lần tìm idx_vec qua được shield (mật độ L0-hợp lệ ~5%
        nên kỳ vọng ~18 lần thử); nếu vẫn thất bại thì fallback về một gene
        L0-hợp lệ đã biết — KHÔNG BAO GIỜ đốt budget cho điểm xuất phát mà
        shield miễn phí đã biết là invalid (finding review P5). Đánh giá điểm
        xuất phát qua evaluator (TỐN budget — đây là đánh giá thật).
        """
        idx_vec = None
        for _ in range(500):
            cand = [self.rng.randrange(s) for s in self.sizes]
            if gene_l0_valid(decode_gene(cand)):
                idx_vec = cand
                break
        if idx_vec is None:
            fallback = {"girder_catalog_id": "ST-1750", "girder_count": 6,
                        "girder_spacing_mm": 2200, "deck_slab_thickness_mm": 200,
                        "girder_concrete_id": "C45", "deck_concrete_id": "C35",
                        "diaphragm_layout_id": "DG-5", "prestress_layout_id": "PT-46"}
            idx_vec = [self._domains[k].index(fallback[k]) for k in GENE_ORDER]
        self.idx_vec = idx_vec
        self.steps = 0
        self.current_record = self.evaluator.evaluate_gene(decode_gene(self.idx_vec))
        self._maybe_archive(self.current_record)
        return self._obs()

    def step(self, action_idx: int) -> tuple[np.ndarray, float, bool, dict]:
        """Áp hành động; trả (obs, reward, done, info). info luôn chứa record mới."""
        _name, var, delta = ACTIONS[action_idx]
        if action_idx == SUBMIT_INDEX:
            return (self._obs(), submit_reward(self.current_record), True,
                    {"submitted": True, "record": self.current_record})

        j = VAR_INDEX[var]
        # kẹp vào biên lưới (shield đã mask, kẹp chỉ là phòng thủ khi gọi tay)
        new_idx = min(self.sizes[j] - 1, max(0, self.idx_vec[j] + delta))
        mutated = list(self.idx_vec)
        mutated[j] = new_idx

        rec = self.evaluator.evaluate_gene(decode_gene(mutated))
        if rec is None:  # hết ngân sách solver — kết thúc trung tính
            return self._obs(), 0.0, True, {"budget_exhausted": True}

        newly_archived = self._maybe_archive(rec)
        reward, terminate = compute_reward(self.current_record, rec, newly_archived)
        self.idx_vec = mutated
        self.current_record = rec
        self.steps += 1
        done = terminate or self.steps >= self.max_steps
        return self._obs(), reward, done, {"record": rec, "newly_archived": newly_archived}

    def valid_actions(self) -> np.ndarray:
        """Mask hành động hợp lệ từ trạng thái hiện tại (safety shield L0)."""
        return valid_action_mask(self.idx_vec, self.sizes)

    # ------------------------------------------------------------------ nội bộ
    def _maybe_archive(self, rec: dict | None) -> bool:
        """Chỉ record.feasible của đánh giá thật mới được vào archive."""
        if rec is not None and rec["feasible"]:
            return self.archive.add(rec["case_id"], rec["objectives"], {"gene": rec["gene"]})
        return False

    def _obs(self) -> np.ndarray:
        obs = np.zeros(OBS_DIM, dtype=np.float64)
        for j, (idx, size) in enumerate(zip(self.idx_vec, self.sizes)):
            obs[j] = idx / (size - 1) if size > 1 else 0.0
        rec = self.current_record
        cv = rec["cv"] if rec is not None else 2.0
        mu = rec["max_utilization"] if rec is not None else None
        objectives = rec["objectives"] if rec is not None else None
        obs[8] = 1.0 if (rec is not None and rec["feasible"]) else 0.0
        obs[9] = min(cv, 2.0) / 2.0
        obs[10] = min(mu if mu is not None else 2.0, 2.0) / 2.0
        if objectives is not None:
            obs[11] = objectives[0] / 3000.0
            obs[12] = objectives[1] / 1000.0
            obs[13] = objectives[2] / 150000.0
        obs[14] = max(0, self.max_steps - self.steps) / self.max_steps
        return obs
