"""Kiểm thử hợp đồng schema Material Evidence."""
import json
from pathlib import Path
import jsonschema
import pytest

from bridge_evolution import CONTRACTS_DIR


def test_material_evidence_schema_valid():
    with open(CONTRACTS_DIR / "material_evidence.schema.json", encoding="utf-8") as f:
        schema = json.load(f)

    evidence_path = Path("research/materials/evidence_matrix.json")
    if evidence_path.exists():
        with open(evidence_path, encoding="utf-8") as f:
            matrix = json.load(f)

        validator = jsonschema.Draft202012Validator(schema)
        for mat in matrix.get("materials", []):
            errors = list(validator.iter_errors(mat))
            assert errors == []
