"""BRD-010 — provenance phải khai ĐÚNG rule profile đã thực sự áp dụng.

Trước bản sửa, ``RULESET_VERSION`` là hằng cố định nên MỌI kết quả — kể cả
phương án grammar v2 chạy dưới BRIDGE-RULESET-V2 (có thêm FAB-001..FAB-007) —
đều tự khai là chạy dưới BRIDGE-RULESET-V1. Phép tính vẫn đúng (rule profile
được đọc từ state khi đánh giá), nhưng artifact nói dối về điều kiện sinh ra nó,
trái nguyên tắc truy vết của AGENTS.md.
"""
import pytest

from bridge_evolution.catalogs import load_catalogs
from bridge_evolution.evaluate import evaluate_candidate
from bridge_evolution.state import state_from_gene
from bridge_evolution.verifier import (
    RULESET_VERSION, ruleset_label, ruleset_version_for,
)

V1_GENE = {
    "girder_catalog_id": "ST-1750", "girder_count": 5, "girder_spacing_mm": 2350,
    "deck_slab_thickness_mm": 180, "girder_concrete_id": "C40",
    "deck_concrete_id": "C30", "diaphragm_layout_id": "DG-5",
    "prestress_layout_id": "PT-42",
}

V2_GENE = {
    "girder_catalog_id": "ST-PARAM", "girder_count": 5, "girder_spacing_mm": 2350,
    "deck_slab_thickness_mm": 180, "girder_concrete_id": "C40",
    "deck_concrete_id": "C30", "diaphragm_layout_id": "DG-5",
    "prestress_layout_id": "PT-34", "girder_depth_mm": 2000,
    "top_flange_width_mm": 1900, "top_flange_thickness_mm": 90,
    "web_thickness_mm": 100, "bottom_bulb_width_mm": 300,
    "bottom_bulb_height_mm": 350,
}


def test_v1_label_frozen():
    """Neo hồi quy: state v1 vẫn khai đúng nhãn cũ, từng ký tự."""
    state = state_from_gene(V1_GENE, grammar_id="super_t_simple_v1")
    assert state["constraints"]["rule_profile_id"] == "BRIDGE-RULESET-V1"
    result = evaluate_candidate(state)
    assert result["provenance"]["ruleset_version"] == "BRIDGE-RULESET-V1/1.1.0"
    assert RULESET_VERSION == "BRIDGE-RULESET-V1/1.1.0"


def test_v2_declares_v2_not_v1():
    """Lỗi gốc của BRD-010: state chạy dưới V2 phải KHAI V2."""
    state = state_from_gene(V2_GENE, grammar_id="super_t_parametric_v2")
    assert state["constraints"]["rule_profile_id"] == "BRIDGE-RULESET-V2"
    result = evaluate_candidate(state)
    label = result["provenance"]["ruleset_version"]
    assert label.startswith("BRIDGE-RULESET-V2/"), label
    assert "BRIDGE-RULESET-V1" not in label


def test_label_tracks_catalog_version():
    """Nhãn suy từ catalog nên không thể lệch khỏi dữ liệu thật."""
    profiles = load_catalogs()["rule_profiles"]
    for rule_profile_id, profile in profiles.items():
        assert ruleset_label(rule_profile_id) == (
            f"{rule_profile_id}/{profile['ruleset_version']}")


@pytest.mark.parametrize("bad_state", [
    {}, None, {"constraints": {}}, {"constraints": None},
    {"constraints": {"rule_profile_id": 7}},
])
def test_unresolvable_state_does_not_claim_v1(bad_state):
    """State hỏng phải trả UNRESOLVED — không được bịa là đã chạy dưới V1."""
    label = ruleset_version_for(bad_state)
    assert label == "UNRESOLVED"


def test_unknown_profile_id_is_flagged():
    label = ruleset_version_for(
        {"constraints": {"rule_profile_id": "BRIDGE-RULESET-KHONG-TON-TAI"}})
    assert label == "BRIDGE-RULESET-KHONG-TON-TAI/UNRESOLVED"
