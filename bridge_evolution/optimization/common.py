"""Hạ tầng đánh giá chung cho mọi thuật toán tối ưu.

Ngân sách ở đây có một nghĩa duy nhất: số lần solver thực sự được mở. Một
proposal bị L0 loại hoặc trả từ cache không tiêu ngân sách solver. Tất cả thuật
toán đi qua cùng ``prescreen_gene`` nên cùng nhận chính sách L0 và objective rẻ.
"""
from __future__ import annotations

from .. import __version__
from ..catalogs import all_domains, load_grammar
from ..evaluate import evaluate_candidate, hard_violation_score
from ..geometry import check_geometry
from ..objectives import compute_objectives, objectives_tuple
from ..state import input_hash, state_from_gene

#: Grammar mặc định của mọi API trong module (arm đối chứng v1).
DEFAULT_GRAMMAR_ID = "super_t_simple_v1"

# Thứ tự biến cố định cho biểu diễn gene dạng vector chỉ số (EA/RL dùng chung).
# Đây là dãy ĐÓNG BĂNG của grammar v1: nhiều module (rl_env.actions, shield,
# surrogate, experiments/run_exhaustive.py) và mọi artifact đã sinh đều neo vào
# nó, nên hằng này không được đổi thứ tự. Với grammar khác v1, dùng
# ``gene_order(grammar_id)`` — thứ tự lấy trực tiếp từ file grammar.
GENE_ORDER = [
    "girder_catalog_id", "girder_count", "girder_spacing_mm", "deck_slab_thickness_mm",
    "girder_concrete_id", "deck_concrete_id", "diaphragm_layout_id", "prestress_layout_id",
]


def gene_order(grammar_id: str = DEFAULT_GRAMMAR_ID) -> list[str]:
    """Thứ tự biến gene của một grammar = thứ tự khai báo ``design_variables``.

    Lấy thứ tự từ chính file grammar (JSON giữ thứ tự khai báo) thay vì từ một
    hằng module, nên grammar v2 (14 biến) không còn bị cắt xuống 8 biến v1.
    Grammar v1 khai báo đúng dãy ``GENE_ORDER`` nên hành vi cũ không đổi —
    ``tests/test_multigrammar_search.py::test_v1_gene_order_frozen`` khóa điều đó.
    """
    return list(load_grammar(grammar_id)["design_variables"])


def gene_domains(grammar_id: str = DEFAULT_GRAMMAR_ID) -> dict:
    """{tên biến: [giá trị hợp lệ]} cho MỌI biến của grammar, theo ``gene_order``.

    Dict giữ insertion order nên thứ tự lặp trùng với ``gene_order(grammar_id)``;
    thuật toán rút số ngẫu nhiên theo thứ tự này để cùng seed cho cùng lịch sử.
    """
    # 2 biến vật liệu nằm trong materials của state nhưng là gene của bài toán tối ưu
    domains = all_domains(load_grammar(grammar_id))
    return {name: domains[name] for name in gene_order(grammar_id)}


def gene_sizes(grammar_id: str = DEFAULT_GRAMMAR_ID) -> list[int]:
    """Kích thước miền từng biến theo đúng thứ tự ``gene_order`` (tiện cho EA/RL)."""
    domains = gene_domains(grammar_id)
    return [len(domains[name]) for name in domains]


class BudgetedEvaluator:
    """Prescreen, cache và đánh giá solver với bộ đếm không nhập nhằng.

    ``history`` chứa mỗi kết quả duy nhất (cả L0 reject và solver result).
    ``proposal_history`` chứa mọi proposal, kể cả cache hit và ứng viên được
    prescreen nhưng surrogate không chọn để chạy solver. Hai lịch sử đều chỉ
    chứa dữ liệu xác định; runtime/timestamp không được đưa vào để cùng seed có
    thể tái lập byte-for-byte sau khi serialize có sort key.
    """

    def __init__(self, budget: int, generation_action: str = "SEARCH", *,
                 seed: int | None = None, grammar_id: str = DEFAULT_GRAMMAR_ID):
        if budget < 0:
            raise ValueError("budget phải không âm")
        self.budget = budget
        self.seed = seed
        self.grammar_id = grammar_id
        self.generation_action = generation_action

        self.n_proposals = 0
        self.n_l0_checks = 0
        self.n_l0_passed = 0
        self.n_l0_rejected = 0
        self.n_cache_hits = 0
        self.n_solver_calls = 0
        self.n_budget_blocked = 0

        self.cache: dict[str, dict] = {}
        self.history: list[dict] = []
        self.proposal_history: list[dict] = []

    @property
    def exhausted(self) -> bool:
        return self.n_solver_calls >= self.budget

    @property
    def counters(self) -> dict[str, int]:
        """Snapshot JSON-friendly dùng trực tiếp trong report/manifest."""
        return {
            "proposals": self.n_proposals,
            "l0_checks": self.n_l0_checks,
            "l0_passed": self.n_l0_passed,
            "l0_rejected": self.n_l0_rejected,
            "cache_hits": self.n_cache_hits,
            "solver_calls": self.n_solver_calls,
            "budget_blocked": self.n_budget_blocked,
            "unique_results": len(self.history),
        }

    @property
    def config(self) -> dict:
        return {
            "budget_solver_calls": self.budget,
            "seed": self.seed,
            "grammar_id": self.grammar_id,
            "generation_action": self.generation_action,
            "software_version": __version__,
            "budget_definition": "solver.status != NOT_RUN",
            "prescreen_policy": "shared_l0_and_exact_cheap_objectives_v1",
        }

    def _state(self, gene: dict, parent_id: str | None) -> dict:
        return state_from_gene(
            gene,
            grammar_id=self.grammar_id,
            parent_id=parent_id,
            generation_action=self.generation_action,
            seed=self.seed,
        )

    def _proposal_event(self, gene: dict, h: str, outcome: str) -> dict:
        self.n_proposals += 1
        event = {
            "proposal_index": self.n_proposals,
            "input_hash": h,
            "gene": dict(gene),
            "seed": self.seed,
            "software_version": __version__,
            "outcome": outcome,
        }
        self.proposal_history.append(event)
        return event

    def _record_result(self, result: dict, gene: dict, state: dict, h: str,
                       event: dict, *, solver_call_index: int | None) -> dict:
        provenance = dict(result.get("provenance", {}))
        # Timestamp từ evaluate chỉ mô tả thời điểm chạy, không thuộc lịch sử
        # deterministic. Manifest thí nghiệm lưu created_at riêng.
        provenance.pop("timestamp_utc", None)
        record = {
            "record_index": len(self.history) + 1,
            # Tên cũ được giữ cho consumer hiện tại; chỉ solver result mới có index.
            "eval_index": solver_call_index,
            "solver_call_index": solver_call_index,
            "proposal_index": event["proposal_index"],
            "case_id": result["case_id"],
            "input_hash": h,
            "gene": dict(gene),
            "design_state": state,
            "seed": self.seed,
            "software_version": __version__,
            "status": result["status"],
            "solver_status": result.get("solver", {}).get("status", "NOT_RUN"),
            "solver_name": result.get("solver", {}).get("name"),
            "feasible": result["feasible"],
            "objectives": objectives_tuple(result["objectives"])
            if "objectives" in result else None,
            "cv": hard_violation_score(result) if not result["feasible"] else 0.0,
            "max_utilization": result.get("responses", {}).get("max_utilization"),
            "responses": result.get("responses"),
            "violations": result.get("violations", []),
            "provenance": provenance,
        }
        self.cache[h] = record
        self.history.append(record)
        event["record_index"] = record["record_index"]
        event["solver_call_index"] = solver_call_index
        return record

    def prescreen_gene(self, gene: dict, parent_id: str | None = None) -> dict:
        """Áp dụng cache + L0 + objective rẻ, chưa mở solver.

        Kết quả có ``outcome`` thuộc CACHE_HIT, BUDGET_EXHAUSTED,
        L0_REJECTED hoặc READY. Với READY, ``state``, ``geometry`` và
        ``cheap_objectives`` có thể được mọi thuật toán sử dụng như nhau.
        """
        gene = dict(gene)
        state = self._state(gene, parent_id)
        h = input_hash(state)

        if h in self.cache:
            event = self._proposal_event(gene, h, "CACHE_HIT")
            self.n_cache_hits += 1
            event["record_index"] = self.cache[h]["record_index"]
            event["solver_call_index"] = self.cache[h]["solver_call_index"]
            return {"outcome": "CACHE_HIT", "record": self.cache[h], "event": event,
                    "input_hash": h}

        # Khi ngân sách đã hết, không cần làm thêm L0 mới. Cache vẫn được phép đọc
        # vì đã xử lý ở nhánh trên.
        if self.exhausted:
            event = self._proposal_event(gene, h, "BUDGET_EXHAUSTED")
            self.n_budget_blocked += 1
            return {"outcome": "BUDGET_EXHAUSTED", "event": event,
                    "input_hash": h}

        self.n_l0_checks += 1
        try:
            violations, geom = check_geometry(state)
        except (KeyError, TypeError, ValueError):
            # evaluate_candidate tạo đúng EvaluationResult/violation contract cho
            # id catalog hoặc cấu trúc lỗi; solver vẫn NOT_RUN.
            result = evaluate_candidate(state)
            event = self._proposal_event(gene, h, "L0_REJECTED")
            self.n_l0_rejected += 1
            record = self._record_result(result, gene, state, h, event,
                                         solver_call_index=None)
            return {"outcome": "L0_REJECTED", "record": record, "event": event,
                    "input_hash": h}

        if any(v.get("severity") == "HARD" for v in violations):
            result = evaluate_candidate(state)
            event = self._proposal_event(gene, h, "L0_REJECTED")
            self.n_l0_rejected += 1
            record = self._record_result(result, gene, state, h, event,
                                         solver_call_index=None)
            return {"outcome": "L0_REJECTED", "record": record, "event": event,
                    "input_hash": h}

        self.n_l0_passed += 1
        event = self._proposal_event(gene, h, "L0_PASSED")
        # Tính cùng một objective rẻ cho mọi algorithm tại cùng điểm prescreen.
        cheap = objectives_tuple(compute_objectives(state, geom))
        return {"outcome": "READY", "gene": gene, "state": state,
                "geometry": geom, "cheap_objectives": cheap, "event": event,
                "input_hash": h}

    def evaluate_prescreened(self, screened: dict) -> dict | None:
        """Mở solver cho một READY result và tăng budget theo status thực tế."""
        outcome = screened.get("outcome")
        if outcome in ("CACHE_HIT", "L0_REJECTED"):
            return screened["record"]
        if outcome == "BUDGET_EXHAUSTED":
            return None
        if outcome != "READY":
            raise ValueError(f"prescreen outcome không hợp lệ: {outcome!r}")

        h = screened["input_hash"]
        # Phòng trường hợp một READY cũ được submit sau khi cùng hash đã chạy.
        if h in self.cache:
            self.n_cache_hits += 1
            screened["event"]["outcome"] = "CACHE_HIT_AFTER_PRESCREEN"
            return self.cache[h]
        if self.exhausted:
            self.n_budget_blocked += 1
            screened["event"]["outcome"] = "BUDGET_EXHAUSTED"
            return None

        result = evaluate_candidate(screened["state"])
        solver_status = result.get("solver", {}).get("status", "NOT_RUN")
        solver_call_index = None
        if solver_status != "NOT_RUN":
            self.n_solver_calls += 1
            solver_call_index = self.n_solver_calls
            screened["event"]["outcome"] = "SOLVER_EVALUATED"
        else:
            # Schema-level reject lọt qua check hình học không được giả làm solver call.
            self.n_l0_rejected += 1
            screened["event"]["outcome"] = "PRE_SOLVER_REJECTED"

        return self._record_result(
            result,
            screened["gene"],
            screened["state"],
            h,
            screened["event"],
            solver_call_index=solver_call_index,
        )

    def evaluate_gene(self, gene: dict, parent_id: str | None = None) -> dict | None:
        """Prescreen rồi đánh giá; cache/L0 result trả về mà không tiêu solver."""
        return self.evaluate_prescreened(self.prescreen_gene(gene, parent_id=parent_id))
