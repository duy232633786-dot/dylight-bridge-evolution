"""Tầng chẩn đoán — dịch vi phạm HARD thành nước sửa cụ thể trong miền grammar.

Chẩn đoán chỉ GỢI Ý hướng sửa (rẻ, không mở solver) — khả thi hay không luôn
do independent verifier kết luận qua đánh giá thật.
"""
from .diagnose import suggest_repairs

__all__ = ["suggest_repairs"]
