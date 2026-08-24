"""Sandbox hình học THỰC NGHIỆM — BRD-004.

Gói này KHÔNG được nhập vào pipeline production (geometry.py / fe_adapter /
objectives / verifier). Nó chỉ dựng TOẠ ĐỘ cho các họ hình thái mà runtime hiện
tại chưa đánh giá được, ở mức claim F0 IDEA theo multiagent/PHYSICS_GATES.md.

Không module nào trong gói này được tính nội lực, ứng suất, chuyển vị hay bất kỳ
đại lượng hiệu năng nào: runtime không có solver cho các họ đó và không được giả
vờ có.
"""

__all__ = ["arch_geometry"]
