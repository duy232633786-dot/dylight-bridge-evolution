"""Reward định hình phân tầng, chống reward hacking.

Hai bất biến quan trọng:
1. Nhánh status != SUCCESS (GEOMETRY_INVALID / SOLVER_FAILED / SCHEMA_INVALID)
   nhận -1.0 — THẤP HƠN mọi nhánh khác, để RL không bao giờ coi việc phá solver
   là "lối thoát" khỏi vùng bị phạt.
2. Bước feasible→feasible KHÔNG cải thiện nhận ròng -STEP_PENALTY (< 0):
   không có base dương vô điều kiện, nên chính sách "dao động giữa hai gene
   đã cache để farm reward miễn phí ngân sách" luôn LỖ (finding review P5;
   số hạng cải thiện chi phí phản đối xứng nên tổng hai chiều = 0).
"""
STEP_PENALTY = 0.02   # phí mỗi bước — khuyến khích episode ngắn gọn
COST_REF = 3000.0     # thang chuẩn hóa chênh lệch chi phí giữa hai bước


def compute_reward(prev_record: dict | None, new_record: dict,
                   newly_archived: bool) -> tuple[float, bool]:
    """(reward, terminate) cho một bước đột biến đã được đánh giá THẬT.

    - status != SUCCESS → (-1.0, True): sàn tuyệt đối, kết thúc episode.
    - infeasible: phạt theo mức vi phạm cv, thưởng nhỏ nếu cv giảm so với prev.
    - feasible: thưởng cơ bản + bonus vào vùng khả thi / giảm chi phí / vào archive.
    """
    if new_record["status"] != "SUCCESS":
        return -1.0, True

    if not new_record["feasible"]:
        base = -0.05 - 0.2 * min(new_record["cv"], 2.0)
        if (prev_record is not None and not prev_record["feasible"]
                and new_record["cv"] < prev_record["cv"]):
            base += 0.1  # tiến bộ: mức vi phạm giảm
        return base - STEP_PENALTY, False

    # Không có base dương vô điều kiện: bước feasible trung tính = -STEP_PENALTY
    r = 0.0
    if prev_record is not None and not prev_record["feasible"]:
        r += 1.0  # bước từ vùng vi phạm vào vùng khả thi
    if (prev_record is not None and prev_record["feasible"]
            and prev_record["objectives"] is not None
            and new_record["objectives"] is not None):
        r += 2.0 * (prev_record["objectives"][0] - new_record["objectives"][0]) / COST_REF
    if newly_archived:
        r += 0.5  # cải thiện Pareto archive thật sự
    return r - STEP_PENALTY, False


def submit_reward(current_record: dict | None) -> float:
    """Reward khi SUBMIT: chỉ thưởng nếu phương án hiện tại THẬT SỰ khả thi."""
    if current_record is not None and current_record["feasible"]:
        cost = current_record["objectives"][0]
        return min(1.0, max(0.0, (2500.0 - cost) / 1000.0))
    return -0.2
