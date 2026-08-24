"""Reward định hình phân tầng, chống reward hacking.

Ba bất biến, mỗi cái ứng với một đường farm đã bị đóng:

1. Nhánh ``status != SUCCESS`` (GEOMETRY_INVALID / SOLVER_FAILED / SCHEMA_INVALID)
   nhận -1.0 — THẤP HƠN mọi nhánh khác, để RL không bao giờ coi việc phá solver
   là "lối thoát" khỏi vùng bị phạt.

2. Bước ``feasible → feasible`` không cải thiện nhận ròng ``-STEP_PENALTY`` (< 0):
   không có base dương vô điều kiện, và số hạng cải thiện chi phí phản đối xứng
   nên tổng hai chiều bằng 0.

3. Bước ``infeasible ↔ feasible`` cũng không farm được. Đây là lỗ hổng THỰC ĐÃ BỊ
   KHAI THÁC: bản trước cộng thẳng +1.0 mỗi lần bước vào vùng khả thi trong khi
   bước ra chỉ mất ~0.07, nên chu trình giữa hai gene ĐÃ CACHE (không tốn một
   lần gọi solver nào) sinh reward dương lớn — Q-learning thật đã lấy 71–78%
   tổng reward từ cache hit. Bản này thay phần thưởng chuyển trạng thái bằng
   **potential-based shaping** (Ng, Harada & Russell 1999):

       F(s, s') = GAMMA * Φ(s') - Φ(s),   Φ(s) = FEASIBLE_POTENTIAL nếu s khả thi

   Shaping dạng này có tổng bằng 0 trên mọi chu trình (với GAMMA = 1) nên không
   farm được, đồng thời KHÔNG đổi thứ tự chính sách tối ưu: động lực đi vào vùng
   khả thi vẫn còn nguyên, chỉ mất khả năng lặp lại nó để cộng điểm.

Hệ quả kiểm được: mọi chu trình đóng đều lỗ đúng bằng tổng STEP_PENALTY (cộng
thêm phần phạt vi phạm nếu chu trình đi qua vùng infeasible).
"""
STEP_PENALTY = 0.02          # phí mỗi bước — khuyến khích episode ngắn gọn
COST_REF = 3000.0            # thang chuẩn hóa chênh lệch chi phí giữa hai bước
FEASIBLE_POTENTIAL = 1.0     # Φ của trạng thái khả thi (Φ = 0 nếu không khả thi)
SHAPING_GAMMA = 1.0          # giữ 1.0 để tổng shaping trên chu trình đúng bằng 0


def _potential(record: dict | None) -> float:
    """Φ(s) — chỉ phụ thuộc TRẠNG THÁI, không phụ thuộc đường đi tới nó."""
    if record is None:
        return 0.0
    return FEASIBLE_POTENTIAL if record.get("feasible") else 0.0


def compute_reward(prev_record: dict | None, new_record: dict,
                   newly_archived: bool) -> tuple[float, bool]:
    """(reward, terminate) cho một bước đột biến đã được đánh giá THẬT.

    - ``status != SUCCESS`` → (-1.0, True): sàn tuyệt đối, kết thúc episode.
    - infeasible: phạt theo mức vi phạm cv, thưởng nhỏ nếu cv giảm so với prev.
    - feasible: cải thiện chi phí + bonus Pareto archive.
    - cả hai nhánh cộng thêm shaping ``GAMMA*Φ(new) - Φ(prev)``.
    """
    if new_record["status"] != "SUCCESS":
        return -1.0, True

    shaping = SHAPING_GAMMA * _potential(new_record) - _potential(prev_record)

    if not new_record["feasible"]:
        base = -0.05 - 0.2 * min(new_record["cv"], 2.0)
        if (prev_record is not None and not prev_record["feasible"]
                and new_record["cv"] < prev_record["cv"]):
            base += 0.1  # tiến bộ: mức vi phạm giảm
        return base + shaping - STEP_PENALTY, False

    # Không có base dương vô điều kiện: bước feasible trung tính = -STEP_PENALTY
    r = 0.0
    if (prev_record is not None and prev_record["feasible"]
            and prev_record["objectives"] is not None
            and new_record["objectives"] is not None):
        r += 2.0 * (prev_record["objectives"][0] - new_record["objectives"][0]) / COST_REF
    if newly_archived:
        r += 0.5  # cải thiện Pareto archive thật sự (ParetoArchive.add chống lặp)
    return r + shaping - STEP_PENALTY, False


def submit_reward(current_record: dict | None) -> float:
    """Reward khi SUBMIT: chỉ thưởng nếu phương án hiện tại THẬT SỰ khả thi."""
    if current_record is not None and current_record["feasible"]:
        cost = current_record["objectives"][0]
        return min(1.0, max(0.0, (2500.0 - cost) / 1000.0))
    return -0.2
