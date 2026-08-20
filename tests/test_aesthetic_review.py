"""Kiểm thử hợp đồng schema Aesthetic & Constructability Review."""
import json
from pathlib import Path
import jsonschema
import pytest

from bridge_evolution import CONTRACTS_DIR


def test_aesthetic_review_schema_valid():
    with open(CONTRACTS_DIR / "aesthetic_review.schema.json", encoding="utf-8") as f:
        schema = json.load(f)

    protocol_path = Path("research/aesthetics/review_protocol.json")
    if protocol_path.exists():
        with open(protocol_path, encoding="utf-8") as f:
            protocol = json.load(f)

        validator = jsonschema.Draft202012Validator(schema)
        errors = list(validator.iter_errors(protocol))
        assert errors == []
