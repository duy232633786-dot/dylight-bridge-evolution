"""Lõi tối ưu đa grammar.

``GENE_ORDER`` là dãy 8 biến ĐÓNG BĂNG của grammar v1 (backward compat).
Thuật toán mới nên dùng ``gene_order(grammar_id)`` / ``gene_domains(grammar_id)``
để chạy được cả grammar tham số hóa v2 (14 biến).
"""
from .common import (  # noqa: F401
    DEFAULT_GRAMMAR_ID,
    GENE_ORDER,
    BudgetedEvaluator,
    gene_domains,
    gene_order,
    gene_sizes,
)
from .random_search import random_search  # noqa: F401
from .nsga2 import nsga2  # noqa: F401
