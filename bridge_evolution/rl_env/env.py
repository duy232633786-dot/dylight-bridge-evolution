"""Môi trường RL rời rạc trên grammar Super-T: đột biến ±1 bước lưới + SUBMIT.

Mọi đánh giá thật đi qua BudgetedEvaluator (trung thực ngân sách); safety shield
(check_geometry) rẻ nên dùng tự do để mask hành động và chọn điểm xuất phát.

Observation np.float64, dim = ``len(gene_order(grammar_id)) + 7``
(v1: 8 + 7 = 15; v2: 14 + 7 = 21), THỨ TỰ CỐ ĐỊNH với n = số biến gene:

  [0 .. n-1]  idx/(size-1) của từng biến theo gene_order(grammar_id)
  [n]         feasible của record hiện tại (0/1)
  [n+1]       min(cv, 2)/2
  [n+2]       min(max_utilization hoặc 2.0, 2.0)/2
  [n+3]       cost/3000        (0 nếu objectives None)
  [n+4]       mass_t/1000      (0 nếu objectives None)
  [n+5]       carbon/150000    (0 nếu objectives None)
  [n+6]       steps_left/max_steps

Với v1 (n = 8) đây đúng bố cục cũ: chỉ số 8..14 giữ nguyên ý nghĩa.
"""
import math
import random
from functools import lru_cache

import numpy as np

from ..optimization.common import DEFAULT_GRAMMAR_ID, gene_domains, gene_order
from ..pareto import ParetoArchive
from .actions import build_actions, submit_index, var_index
from .reward import compute_reward, submit_reward
from .shield import decode_gene, gene_l0_valid, valid_action_mask

#: Số đặc trưng trạng thái nối sau khối chỉ số gene (xem docstring module).
N_STATUS_FEATURES = 7

#: Observation dim của grammar v1 — hằng ĐÓNG BĂNG cho consumer cũ.
OBS_DIM = 8 + N_STATUS_FEATURES  # 15

#: Điểm xuất phát dự phòng của grammar v1: gene L0-hợp lệ đã biết. Giữ NGUYÊN
#: giá trị cũ để lịch sử v1 không đổi một byte.
_FALLBACK_GENE_V1 = {
    "girder_catalog_id": "ST-1750", "girder_count": 6,
    "girder_spacing_mm": 2200, "deck_slab_thickness_mm": 200,
    "girder_concrete_id": "C45", "deck_concrete_id": "C35",
    "diaphragm_layout_id": "DG-5", "prestress_layout_id": "PT-46",
}

#: Seed CỐ ĐỊNH của bộ dò fallback cho grammar khác v1. Tách khỏi RNG episode để
#: việc dò fallback không bao giờ làm lệch chuỗi ngẫu nhiên của môi trường.
_FALLBACK_SEED = 20240501
_FALLBACK_MAX_DRAWS = 20_000

#: Trần số lần thử của pha dò điểm xuất phát trong ``reset()``.
#: 500 là con số ĐÓNG BĂNG của grammar v1 (mật độ L0-hợp lệ ~4.7% ⇒ xác suất
#: phải fallback ~1e-10); grammar khác co giãn theo mật độ đo được (finding
#: review S2: với v2 mật độ chỉ ~0.6% nên trần 500 đẩy ~5% episode xuất phát từ
#: ĐÚNG MỘT điểm fallback cố định — lệch phân phối điểm xuất phát, chưa hề được
#: pre-register).
_RESET_MIN_DRAWS = 500
_RESET_MAX_DRAWS = 20_000
#: Xác suất phải dùng fallback mà ta chấp nhận khi chọn trần cho grammar mới.
_RESET_TARGET_FALLBACK_RATE = 1e-4
#: Bộ ước lượng mật độ L0: seed riêng, cố định ⇒ trần suy ra tái lập được.
_DENSITY_SEED = 20240502
_DENSITY_SAMPLES = 3000
#: Số sigma dùng cho CẬN DƯỚI của mật độ. Mật độ ước lượng từ vài trăm mẫu rất
#: nhiễu (đếm hit nhỏ ⇒ sd ≈ sqrt(hit)); lấy cận dưới thay vì điểm ước lượng để
#: trần không bị đặt quá thấp khi probe may mắn trúng nhiều hit.
_DENSITY_LOWER_SIGMA = 1.96


def obs_dim(grammar_id: str = DEFAULT_GRAMMAR_ID) -> int:
    """Chiều observation của một grammar = số biến gene + 7."""
    return len(gene_order(grammar_id)) + N_STATUS_FEATURES


@lru_cache(maxsize=None)
def _l0_valid_density(grammar_id: str) -> tuple[int, int]:
    """(số gene L0-hợp lệ, số mẫu) trên mẫu ngẫu nhiên seed cố định của grammar.

    Trả về SỐ ĐẾM thô chứ không phải tỷ lệ, để bên gọi tự chọn cận dưới. Chỉ
    dùng ``check_geometry`` (miễn phí, không mở solver) nên không tiêu ngân
    sách. RNG riêng ``_DENSITY_SEED`` để phép đo không bao giờ chạm chuỗi ngẫu
    nhiên của môi trường.
    """
    domains = gene_domains(grammar_id)
    order = gene_order(grammar_id)
    sizes = [len(domains[name]) for name in order]
    rng = random.Random(_DENSITY_SEED)
    hits = sum(1 for _ in range(_DENSITY_SAMPLES)
               if gene_l0_valid(
                   decode_gene([rng.randrange(s) for s in sizes], grammar_id),
                   grammar_id))
    return hits, _DENSITY_SAMPLES


@lru_cache(maxsize=None)
def _reset_max_draws(grammar_id: str) -> int:
    """Trần số lần thử tìm điểm xuất phát, CO GIÃN theo mật độ L0 của grammar.

    Chọn n nhỏ nhất sao cho ``(1 - p)^n <= _RESET_TARGET_FALLBACK_RATE``, với p
    là CẬN DƯỚI của mật độ (``(hits - 1.96·sqrt(hits)) / N``, xấp xỉ Poisson cho
    số đếm nhỏ), rồi kẹp vào ``[_RESET_MIN_DRAWS, _RESET_MAX_DRAWS]``. Dùng cận
    dưới vì probe vài nghìn mẫu trên grammar thưa có sai số lớn — lấy điểm ước
    lượng thì trần bị đặt hụt và tỷ lệ fallback thật cao hơn mục tiêu.

    Grammar v1 trả thẳng 500 để chuỗi ngẫu nhiên và điểm fallback cũ KHÔNG đổi.
    """
    if grammar_id == DEFAULT_GRAMMAR_ID:
        return _RESET_MIN_DRAWS
    hits, n_samples = _l0_valid_density(grammar_id)
    lower = hits - _DENSITY_LOWER_SIGMA * math.sqrt(hits)
    # Sàn: probe không trúng mẫu nào vẫn cho p > 0 nên công thức không chia 0.
    p = max(lower / n_samples, 1.0 / (n_samples + 1))
    if p >= 1.0:
        return _RESET_MIN_DRAWS
    need = math.ceil(math.log(_RESET_TARGET_FALLBACK_RATE) / math.log(1.0 - p))
    return max(_RESET_MIN_DRAWS, min(_RESET_MAX_DRAWS, need))


@lru_cache(maxsize=None)
def _fallback_idx_vec(grammar_id: str) -> tuple[int, ...]:
    """Vector chỉ số xuất phát dự phòng, L0-hợp lệ, XÁC ĐỊNH theo grammar.

    - v1: dùng đúng gene hằng cũ (``_FALLBACK_GENE_V1``).
    - grammar khác: KHÔNG hard-code gene v1 (girder_catalog_id của v2 bị khóa ở
      ST-PARAM và 6 biến hình dạng không tồn tại trong gene v1). Thay vào đó dò
      bằng RNG seed cố định nên kết quả tái lập được; nếu vẫn không tìm ra thì
      trả vector 0 — reset() sẽ đánh giá thật điểm đó và bước kế tiếp vẫn được
      shield bảo vệ.
    """
    domains = gene_domains(grammar_id)
    order = gene_order(grammar_id)
    sizes = [len(domains[name]) for name in order]
    if grammar_id == DEFAULT_GRAMMAR_ID:
        return tuple(domains[name].index(_FALLBACK_GENE_V1[name]) for name in order)

    rng = random.Random(_FALLBACK_SEED)
    for _ in range(_FALLBACK_MAX_DRAWS):
        cand = [rng.randrange(s) for s in sizes]
        if gene_l0_valid(decode_gene(cand, grammar_id), grammar_id):
            return tuple(cand)
    return tuple([0] * len(sizes))


class BridgeEnv:
    """Env kiểu gym tối giản: reset() -> obs; step(a) -> (obs, reward, done, info)."""

    def __init__(self, evaluator, seed: int, max_steps: int = 25,
                 archive: ParetoArchive | None = None,
                 grammar_id: str = DEFAULT_GRAMMAR_ID):
        self.evaluator = evaluator
        self.rng = random.Random(seed)
        self.max_steps = max_steps
        self.archive = archive if archive is not None else ParetoArchive()
        self.grammar_id = grammar_id
        self.order = gene_order(grammar_id)
        domains = gene_domains(grammar_id)
        self._domains = domains
        self.sizes = [len(domains[k]) for k in self.order]
        self.actions = build_actions(grammar_id)
        self.submit_index = submit_index(self.actions)
        self._var_index = var_index(self.order)
        self.obs_dim = obs_dim(grammar_id)
        #: Trần số lần thử của pha dò điểm xuất phát — theo mật độ L0 grammar.
        self.max_start_draws = _reset_max_draws(grammar_id)
        self.idx_vec: list[int] = [0] * len(self.order)
        self.current_record: dict | None = None
        self.steps = 0
        #: Lần reset() gần nhất có phải rơi về điểm fallback cố định không (đo
        #: được độ lệch phân phối điểm xuất phát thay vì phải đoán).
        self.last_reset_used_fallback = False

    # ------------------------------------------------------------------ vòng đời
    def _sample_start_idx_vec(self) -> tuple[list[int], bool]:
        """Dò điểm xuất phát L0-hợp lệ; trả ``(idx_vec, phải_dùng_fallback)``.

        Số lần thử là ``self.max_start_draws``, CO GIÃN theo mật độ L0-hợp lệ
        của grammar chứ không còn là hằng 500 hiệu chỉnh cho riêng v1: với
        grammar thưa (v2 ~0.6%) trần cũ đẩy ~5% episode về đúng một điểm
        fallback cố định, làm lệch phân phối điểm xuất phát. Việc dò chỉ dùng
        shield L0 (miễn phí) nên KHÔNG tiêu ngân sách solver.
        """
        for _ in range(self.max_start_draws):
            cand = [self.rng.randrange(s) for s in self.sizes]
            if gene_l0_valid(decode_gene(cand, self.grammar_id), self.grammar_id):
                return cand, False
        return list(_fallback_idx_vec(self.grammar_id)), True

    def reset(self) -> np.ndarray:
        """Bắt đầu episode: điểm xuất phát ngẫu nhiên L0-hợp lệ.

        Dò idx_vec qua được shield (v1: mật độ ~4.7%, kỳ vọng ~21 lần thử);
        nếu vẫn thất bại thì fallback về một gene L0-hợp lệ đã biết của CHÍNH
        grammar đó — KHÔNG BAO GIỜ đốt budget cho điểm xuất phát mà shield miễn
        phí đã biết là invalid (finding review P5). Đánh giá điểm xuất phát qua
        evaluator (TỐN budget — đây là đánh giá thật).
        """
        idx_vec, used_fallback = self._sample_start_idx_vec()
        self.idx_vec = idx_vec
        self.last_reset_used_fallback = used_fallback
        self.steps = 0
        self.current_record = self.evaluator.evaluate_gene(self._gene())
        self._maybe_archive(self.current_record)
        return self._obs()

    def step(self, action_idx: int) -> tuple[np.ndarray, float, bool, dict]:
        """Áp hành động; trả (obs, reward, done, info). info luôn chứa record mới."""
        _name, var, delta = self.actions[action_idx]
        if action_idx == self.submit_index:
            return (self._obs(), submit_reward(self.current_record), True,
                    {"submitted": True, "record": self.current_record})

        j = self._var_index[var]
        # kẹp vào biên lưới (shield đã mask, kẹp chỉ là phòng thủ khi gọi tay)
        new_idx = min(self.sizes[j] - 1, max(0, self.idx_vec[j] + delta))
        mutated = list(self.idx_vec)
        mutated[j] = new_idx

        rec = self.evaluator.evaluate_gene(decode_gene(mutated, self.grammar_id))
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
        return valid_action_mask(self.idx_vec, self.sizes, True, self.grammar_id)

    # ------------------------------------------------------------------ nội bộ
    def _gene(self) -> dict:
        return decode_gene(self.idx_vec, self.grammar_id)

    def _maybe_archive(self, rec: dict | None) -> bool:
        """Chỉ record.feasible của đánh giá thật mới được vào archive."""
        if rec is not None and rec["feasible"]:
            return self.archive.add(rec["case_id"], rec["objectives"], {"gene": rec["gene"]})
        return False

    def _obs(self) -> np.ndarray:
        n = len(self.order)
        obs = np.zeros(self.obs_dim, dtype=np.float64)
        for j, (idx, size) in enumerate(zip(self.idx_vec, self.sizes)):
            obs[j] = idx / (size - 1) if size > 1 else 0.0
        rec = self.current_record
        cv = rec["cv"] if rec is not None else 2.0
        mu = rec["max_utilization"] if rec is not None else None
        objectives = rec["objectives"] if rec is not None else None
        obs[n] = 1.0 if (rec is not None and rec["feasible"]) else 0.0
        obs[n + 1] = min(cv, 2.0) / 2.0
        obs[n + 2] = min(mu if mu is not None else 2.0, 2.0) / 2.0
        if objectives is not None:
            obs[n + 3] = objectives[0] / 3000.0
            obs[n + 4] = objectives[1] / 1000.0
            obs[n + 5] = objectives[2] / 150000.0
        obs[n + 6] = max(0, self.max_steps - self.steps) / self.max_steps
        return obs
