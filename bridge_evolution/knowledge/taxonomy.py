"""Taxonomy liên kết tiêu chuẩn, rule, knowledge card và biến thiết kế."""
from __future__ import annotations

from typing import Any


TCVN_PART_TITLES = {
    1: "Yêu cầu chung",
    2: "Tổng thể và đặc điểm vị trí cầu",
    3: "Tải trọng và hệ số tải trọng",
    4: "Phân tích và đánh giá kết cấu",
    5: "Kết cấu bê tông",
    6: "Kết cấu thép",
    9: "Mặt cầu và hệ mặt cầu",
    10: "Nền móng",
    11: "Mố, trụ và tường chắn",
    12: "Kết cấu vùi và áo hầm",
    13: "Lan can",
    14: "Khe co giãn và gối cầu",
}


RULES: dict[str, dict[str, Any]] = {
    "MODEL-001": {
        "title": "Miền hợp lệ của mô hình khối nén L1",
        "description": "Khối ứng suất nén phải nằm trong chiều dày bản; vượt miền này làm công thức sức kháng uốn L1 mất hiệu lực.",
        "severity": "HARD", "layer": "L1 verifier",
        "standards": [5, 9],
        "variables": ["deck_slab_thickness_mm", "girder_concrete_id", "prestress_layout_id"],
    },
    "STR-001": {
        "title": "Sức kháng uốn - Cường độ I",
        "description": "Nhu cầu mô men phải không vượt sức kháng uốn có hệ số.",
        "severity": "HARD", "layer": "L1 verifier",
        "standards": [1, 3, 5],
        "variables": ["girder_catalog_id", "girder_count", "prestress_layout_id"],
    },
    "STR-002": {
        "title": "Sức kháng cắt - Cường độ I",
        "description": "Nhu cầu lực cắt phải không vượt sức kháng cắt có hệ số của mô hình L1.",
        "severity": "HARD", "layer": "L1 verifier",
        "standards": [1, 3, 5],
        "variables": ["girder_catalog_id", "girder_count", "girder_spacing_mm"],
    },
    "SERV-001": {
        "title": "Ứng suất kéo thớ dưới - Sử dụng III",
        "description": "Ứng suất kéo thớ dưới dầm ở tổ hợp Sử dụng III phải nằm trong giới hạn cho phép.",
        "severity": "HARD", "layer": "L1 verifier",
        "standards": [1, 3, 5],
        "variables": ["girder_catalog_id", "girder_concrete_id", "prestress_layout_id"],
    },
    "SERV-002": {
        "title": "Giới hạn võng hoạt tải",
        "description": "Độ võng hoạt tải của nhịp phải nằm trong giới hạn sử dụng đã khai báo.",
        "severity": "HARD", "layer": "L1 verifier",
        "standards": [1, 3, 4],
        "variables": ["girder_catalog_id", "girder_count", "girder_spacing_mm"],
    },
    "SERV-003": {
        "title": "Tần số dao động cơ bản",
        "description": "Cảnh báo mềm khi tần số dao động cơ bản thấp hơn ngưỡng mô hình.",
        "severity": "SOFT", "layer": "L1 verifier",
        "standards": [1, 4],
        "variables": ["girder_catalog_id", "girder_count", "deck_slab_thickness_mm"],
    },
    "GEOM-001": {
        "title": "Cánh hẫng và bề rộng bố trí dầm",
        "description": "Hệ dầm phải nằm trong bề rộng cầu và cánh hẫng phải nằm trong miền cho phép.",
        "severity": "HARD", "layer": "L0 geometry",
        "standards": [2, 4],
        "variables": ["girder_count", "girder_spacing_mm"],
    },
    "GEOM-002": {
        "title": "Khe hở cánh dầm liền kề",
        "description": "Khoảng hở giữa các cánh dầm liền kề phải thỏa miền hình học của catalog.",
        "severity": "HARD", "layer": "L0 geometry",
        "standards": [2, 4],
        "variables": ["girder_catalog_id", "girder_spacing_mm"],
    },
    "GEOM-003": {
        "title": "Chiều dày tối thiểu của bản mặt cầu",
        "description": "Chiều dày bản phải đáp ứng giới hạn tối thiểu theo nhịp bản giữa dầm.",
        "severity": "HARD", "layer": "L0 geometry",
        "standards": [5, 9],
        "variables": ["girder_spacing_mm", "deck_slab_thickness_mm"],
    },
    "CONS-001": {
        "title": "Khoảng cách dầm ngang",
        "description": "Số hàng và khoảng cách dầm ngang phải phù hợp giới hạn nội bộ của project/ruleset.",
        "severity": "HARD", "layer": "L0 constructability",
        "standards": [4, 5],
        "variables": ["diaphragm_layout_id"],
    },
    "CONS-002": {
        "title": "Biến thiết kế nằm trên lưới grammar",
        "description": "Mọi biến số học phải thuộc đúng miền rời rạc của design grammar.",
        "severity": "HARD", "layer": "L0 contract",
        "standards": [],
        "variables": ["girder_count", "girder_spacing_mm", "deck_slab_thickness_mm"],
    },
    "SOLVER-001": {
        "title": "Lỗi solver hoặc dữ liệu catalog",
        "description": "Solver không hội tụ/kỳ dị được coi là lỗi mô hình hoặc dữ liệu, không phải đường né constraint.",
        "severity": "HARD", "layer": "Solver contract",
        "standards": [4],
        "variables": ["girder_catalog_id", "girder_concrete_id", "deck_concrete_id"],
    },
}


VARIABLES: dict[str, dict[str, Any]] = {
    "girder_catalog_id": {
        "title": "Tiết diện dầm Super-T",
        "description": "Chọn catalog tiết diện dầm chủ; chi phối hình học, độ cứng, khối lượng và sức kháng.",
        "standards": [4, 5],
    },
    "girder_count": {
        "title": "Số lượng dầm chủ",
        "description": "Số dầm trên mặt cắt ngang; chi phối spacing, cánh hẫng, phân bố tải và tải mỗi dầm.",
        "standards": [2, 4, 5],
    },
    "girder_spacing_mm": {
        "title": "Khoảng cách tim dầm",
        "description": "Khoảng cách tim các dầm chủ; chi phối hình học, nhịp bản và hệ số phân bố tải.",
        "standards": [2, 4, 9],
    },
    "deck_slab_thickness_mm": {
        "title": "Chiều dày bản mặt cầu",
        "description": "Chiều dày deck slab; ảnh hưởng khối lượng, tải chết, độ cứng và miền khối nén.",
        "standards": [5, 9],
    },
    "girder_concrete_id": {
        "title": "Cấp bê tông dầm",
        "description": "Cấp bê tông dầm chủ, ảnh hưởng mô đun, sức kháng và giới hạn ứng suất.",
        "standards": [5],
    },
    "deck_concrete_id": {
        "title": "Cấp bê tông bản",
        "description": "Cấp bê tông bản mặt cầu, ảnh hưởng tải trọng, carbon và sức kháng composite.",
        "standards": [5, 9],
    },
    "diaphragm_layout_id": {
        "title": "Bố trí dầm ngang",
        "description": "Chọn số hàng/vị trí dầm ngang theo catalog constructability.",
        "standards": [4, 5],
    },
    "prestress_layout_id": {
        "title": "Bố trí cáp dự ứng lực",
        "description": "Chọn cấu hình tao cáp DƯL; chi phối ứng suất sử dụng và sức kháng uốn.",
        "standards": [3, 5],
    },
}


EXTRA_CARD_STANDARDS = {
    "KC-008": [2, 5],
}


def standards_for_card(card: dict) -> list[int]:
    parts = set(EXTRA_CARD_STANDARDS.get(card["card_id"], []))
    for rule_id in card["applies_to"]["rules"]:
        parts.update(RULES.get(rule_id, {}).get("standards", []))
    for variable in card["applies_to"]["variables"]:
        parts.update(VARIABLES.get(variable, {}).get("standards", []))
    return sorted(parts)


def cards_for_standard(cards: list[dict], part: int) -> list[str]:
    return sorted(card["card_id"] for card in cards if part in standards_for_card(card))


def rules_for_standard(part: int) -> list[str]:
    return sorted(rule_id for rule_id, meta in RULES.items()
                  if part in meta["standards"])


def variables_for_standard(part: int) -> list[str]:
    return sorted(name for name, meta in VARIABLES.items()
                  if part in meta["standards"])


__all__ = [
    "RULES", "TCVN_PART_TITLES", "VARIABLES", "cards_for_standard", "rules_for_standard",
    "standards_for_card", "variables_for_standard",
]
