"""Test lớp tri thức: schema thẻ, nạp kho thẻ, truy vấn có chấm điểm."""
from bridge_evolution.knowledge import load_cards, query_knowledge, validate_card
from bridge_evolution.knowledge.store import CARDS_DIR
from bridge_evolution.catalogs import load_grammar


def _valid_card(card_id: str = "KC-999", status: str = "DRAFT") -> dict:
    return {
        "card_id": card_id,
        "type": "design_heuristic",
        "title": "Thẻ thử nghiệm",
        "applies_to": {"family": "super_t_simple_v1",
                       "rules": ["SERV-001"], "variables": []},
        "guidance": "Chỉ dùng trong test.",
        "evidence": "n/a",
        "source": {"kind": "experiment", "ref": "n/a"},
        "status": status,
        "version": 1,
    }


def test_all_cards_valid():
    cards = load_cards()
    expected_ids = sorted(path.stem for path in CARDS_DIR.glob("KC-*.json"))
    assert sorted(c["card_id"] for c in cards) == expected_ids
    for c in cards:
        assert validate_card(c) == []


def test_query_serv001():
    hits = query_knowledge(failed_rules=["SERV-001"])
    assert hits, "SERV-001 phải khớp ít nhất KC-001/KC-005/KC-009"
    # KC-001/KC-005/KC-009 cùng +3.0 → tie-break card_id tăng dần → KC-001 đứng đầu
    assert hits[0]["card"]["card_id"] == "KC-001"
    ids = [h["card"]["card_id"] for h in hits]
    assert {"KC-001", "KC-005", "KC-009"} <= set(ids)
    scores = [h["score"] for h in hits]
    assert scores == sorted(scores, reverse=True)
    assert all(h["score"] > 0 for h in hits)


def test_draft_filter():
    # Toàn bộ kho hiện là DRAFT → lọc DRAFT thì không còn gì
    assert query_knowledge(failed_rules=["SERV-001"], include_draft=False) == []


def test_rejected_excluded():
    rejected = _valid_card(status="REJECTED")
    hits = query_knowledge(failed_rules=["SERV-001"], cards=[rejected])
    assert hits == []


def test_schema_rejects_bad_card():
    bad = _valid_card()
    del bad["source"]
    errors = validate_card(bad)
    assert errors
    assert any("source" in e for e in errors)


def test_rule_match_beats_text_combo():
    """Hồi quy finding review: thẻ khớp rule bị fail phải thắng MỌI tổ hợp text.

    KC-007 là thẻ duy nhất áp dụng SOLVER-001 — trước đây bị KC-004 (7.0 điểm
    text) đè xuống chót và văng khỏi top_k=4.
    """
    hits = query_knowledge(failed_rules=["SOLVER-001"],
                           text="khoảng cách dầm ngang nhịp 38.3 m", top_k=4)
    assert hits[0]["card"]["card_id"] == "KC-007"


def test_text_scoring_dedupe_and_word_boundary():
    card = _valid_card()
    card["title"] = "Chọn số dầm chủ cho khổ cầu"
    # từ lặp không cộng dồn điểm
    once = query_knowledge(text="dầm", cards=[card])
    spam = query_knowledge(text="dầm dầm dầm dầm", cards=[card])
    assert once and spam and once[0]["score"] == spam[0]["score"]
    # token 1 ký tự bị loại — không còn khớp substring vạn năng
    assert query_knowledge(text="m", cards=[card]) == []


def test_duplicate_card_id_rejected(tmp_path):
    import json
    import pytest
    for name in ("a.json", "b.json"):
        card = _valid_card(card_id="KC-100")
        card["title"] = f"Bản {name}"
        (tmp_path / name).write_text(json.dumps(card, ensure_ascii=False),
                                     encoding="utf-8")
    with pytest.raises(ValueError, match="KC-100"):
        load_cards(cards_dir=tmp_path)


def test_kc017_matches_real_v2_bottom_bulb_variables():
    cards = load_cards()
    card = next(card for card in cards if card["card_id"] == "KC-017")
    grammar_variables = set(load_grammar("super_t_parametric_v2")["design_variables"])

    assert set(card["applies_to"]["variables"]) <= grammar_variables
    assert "bottom_thickness_mm" not in card["applies_to"]["variables"]
    for variable in ("bottom_bulb_width_mm", "bottom_bulb_height_mm"):
        assert variable in card["applies_to"]["variables"]
        hits = query_knowledge(
            family="super_t_parametric_v2",
            variables=[variable],
            cards=cards,
            top_k=len(cards),
        )
        assert "KC-017" in {hit["card"]["card_id"] for hit in hits}
