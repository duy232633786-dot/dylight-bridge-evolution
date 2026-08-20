"""Não thứ 2 — kho thẻ tri thức kỹ thuật có cấu trúc (knowledge cards).

QUY TẮC BẤT DI BẤT DỊCH: thẻ tri thức chỉ GỢI Ý hướng sửa/hướng tìm kiếm —
PASS/FAIL luôn thuộc về independent verifier (bridge_evolution.verifier);
mọi con số trong thẻ phải đối chiếu lại catalogs/ruleset trước khi dùng.
Không model nào được kết luận khả thi từ nội dung thẻ.
"""
import json
import re
from functools import lru_cache
from pathlib import Path

import jsonschema

from .. import CONTRACTS_DIR, KNOWLEDGE_CARDS_DIR

CARDS_DIR = KNOWLEDGE_CARDS_DIR


@lru_cache(maxsize=None)
def _schema() -> dict:
    with open(CONTRACTS_DIR / "knowledge_card.schema.json", encoding="utf-8") as f:
        return json.load(f)


def validate_card(card: dict) -> list[str]:
    """Trả về danh sách lỗi schema của một thẻ (rỗng = hợp lệ). Không raise."""
    validator = jsonschema.Draft202012Validator(_schema())
    return [f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}"
            for e in validator.iter_errors(card)]


def load_cards(cards_dir: str | Path | None = None) -> list[dict]:
    """Nạp mọi thẻ *.json trong knowledge/cards/ (sắp theo tên file — tái lập).

    Thẻ vi phạm schema → raise ValueError kèm tên file để người duyệt sửa ngay,
    không cho tri thức hỏng lọt vào vòng tối ưu.
    """
    d = Path(cards_dir) if cards_dir is not None else CARDS_DIR
    cards = []
    seen_ids: dict[str, str] = {}
    for path in sorted(d.glob("*.json")):
        with open(path, encoding="utf-8") as f:
            card = json.load(f)
        errors = validate_card(card)
        if errors:
            raise ValueError(f"Thẻ tri thức không hợp lệ ({path.name}): {errors}")
        cid = card["card_id"]
        if cid in seen_ids:  # card_id phải duy nhất toàn kho — schema per-file không bắt được
            raise ValueError(f"card_id trùng lặp '{cid}' trong {seen_ids[cid]} và {path.name}")
        seen_ids[cid] = path.name
        cards.append(card)
    return cards


def query_knowledge(failed_rules: list[str] | None = None,
                    variables: list[str] | None = None,
                    text: str | None = None,
                    family: str | None = None,
                    include_draft: bool = True,
                    top_k: int = 5,
                    cards: list[dict] | None = None) -> list[dict]:
    """Truy vấn thẻ tri thức theo điểm khớp, trả về [{"card": dict, "score": float}].

    Xếp hạng theo BẬC: số rule khớp trước, rồi mới đến tổng điểm — một thẻ khớp
    rule bị fail LUÔN đứng trên mọi thẻ chỉ khớp từ khóa/biến, bất kể tổ hợp
    điểm text (finding review knowledge: text không được đè rule match).
    Cách chấm điểm (cộng dồn):
    - +3.0 mỗi rule trong failed_rules khớp applies_to.rules;
    - +1.0 nếu family khớp applies_to.family;
    - +1.0 mỗi variable khớp applies_to.variables;
    - +1.0 mỗi từ khóa DUY NHẤT của text (token \\w+ lowercase, dài ≥ 2 ký tự)
      khớp theo ranh giới từ trong title + guidance (không substring, không cộng lặp).
    Thẻ REJECTED luôn bị loại; thẻ DRAFT bị loại khi include_draft=False.
    Chỉ trả thẻ có score > 0, sắp (số rule khớp giảm, score giảm, card_id tăng),
    cắt top_k.
    """
    if cards is None:
        cards = load_cards()
    failed_rules = failed_rules or []
    variables = variables or []
    keywords = ({w for w in re.findall(r"\w+", text.lower()) if len(w) >= 2}
                if text else set())

    hits = []
    for card in cards:
        if card["status"] == "REJECTED":
            continue
        if card["status"] == "DRAFT" and not include_draft:
            continue
        applies = card["applies_to"]
        rule_matches = sum(1 for r in failed_rules if r in applies["rules"])
        score = 3.0 * rule_matches
        if family is not None and family == applies["family"]:
            score += 1.0
        score += 1.0 * sum(1 for v in variables if v in applies["variables"])
        if keywords:
            words = set(re.findall(r"\w+", (card["title"] + " " + card["guidance"]).lower()))
            score += 1.0 * len(keywords & words)
        if score > 0:
            hits.append({"card": card, "score": score, "_rules": rule_matches})

    hits.sort(key=lambda h: (-h["_rules"], -h["score"], h["card"]["card_id"]))
    return [{"card": h["card"], "score": h["score"]} for h in hits[:top_k]]
