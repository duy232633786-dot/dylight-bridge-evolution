"""Interface solver — dispatch theo state.analysis.solver.

BUILTIN_L1  : line-girder thuần Python/numpy (mặc định, dùng cho EA/RL hàng loạt).
MIDAS_CIVIL : chỗ cắm cho L2/L3 — solver kiểm chứng CHÍNH theo định hướng dự án
              (mô hình = Revit, phân tích = Midas Civil NX qua MCP/Open API JSON).
OPENSEESPY  : phương án L2 mã nguồn mở dự phòng (openseespy chưa có wheel cho
              Python 3.14; sẽ chạy qua env riêng/MCP nếu cần).
"""
from time import perf_counter

from .line_girder import analyze as _analyze_l1, SolverError  # noqa: F401

SOLVER_VERSION = "builtin-l1/0.2.0"


def run_analysis(state: dict, geom: dict) -> dict:
    solver = state["analysis"].get("solver", "BUILTIN_L1")
    t0 = perf_counter()
    if solver == "BUILTIN_L1":
        result = _analyze_l1(state, geom)
    elif solver == "MIDAS_CIVIL":
        raise SolverError("MIDAS_CIVIL adapter thuộc phạm vi L2 — sẽ nối qua MCP/Open API")
    elif solver == "OPENSEESPY":
        raise SolverError("OPENSEESPY adapter thuộc phạm vi L2 — chưa triển khai trong MVP")
    else:
        raise SolverError(f"Solver không hỗ trợ: {solver}")
    result["solver"]["runtime_ms"] = (perf_counter() - t0) * 1000.0
    return result
