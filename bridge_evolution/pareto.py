"""Pareto archive + hypervolume (minimize mọi mục tiêu)."""
import random


def dominates(a: tuple, b: tuple) -> bool:
    """a trội b: không tệ hơn ở mọi mục tiêu và tốt hơn ít nhất một."""
    return all(x <= y for x, y in zip(a, b)) and any(x < y for x, y in zip(a, b))


class ParetoArchive:
    """Kho phương án khả thi không bị trội. Chỉ nhận candidate feasible."""

    def __init__(self):
        self.entries: list[dict] = []   # {case_id, objectives(tuple), gene, result}

    def add(self, case_id: str, objectives: tuple, payload: dict | None = None) -> bool:
        for e in self.entries:
            if dominates(e["objectives"], objectives) or e["objectives"] == objectives:
                return False
        self.entries = [e for e in self.entries if not dominates(objectives, e["objectives"])]
        self.entries.append({"case_id": case_id, "objectives": objectives,
                             "payload": payload or {}})
        return True

    @property
    def front(self) -> list[tuple]:
        return [e["objectives"] for e in self.entries]


def hypervolume_2d(points: list[tuple], ref: tuple) -> float:
    """HV chính xác cho 2 mục tiêu (minimize), ref = điểm tham chiếu xấu nhất."""
    pts = sorted({(p[0], p[1]) for p in points if p[0] < ref[0] and p[1] < ref[1]})
    hv, prev_y = 0.0, ref[1]
    for x, y in pts:
        if y < prev_y:
            hv += (ref[0] - x) * (prev_y - y)
            prev_y = y
    return hv


def hypervolume_mc(points: list[tuple], ref: tuple, ideal: tuple,
                   n_samples: int = 40000, seed: int = 0) -> float:
    """HV xấp xỉ Monte Carlo cho ≥3 mục tiêu, chuẩn hóa về [ideal, ref] (seeded, tái lập)."""
    dims = len(ref)
    pts = [p for p in points if all(p[i] < ref[i] for i in range(dims))]
    if not pts:
        return 0.0
    rng = random.Random(seed)
    hit = 0
    for _ in range(n_samples):
        s = tuple(ideal[i] + rng.random() * (ref[i] - ideal[i]) for i in range(dims))
        if any(all(p[i] <= s[i] for i in range(dims)) for p in pts):
            hit += 1
    vol_box = 1.0
    for i in range(dims):
        vol_box *= (ref[i] - ideal[i])
    return hit / n_samples * vol_box
