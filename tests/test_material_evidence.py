"""Kiểm thử hợp đồng schema Material Evidence."""
import json
from pathlib import Path
import jsonschema
import pytest

from bridge_evolution import CONTRACTS_DIR, REPO_ROOT
from bridge_evolution.catalogs import load_catalogs


def test_material_evidence_schema_valid():
    with open(CONTRACTS_DIR / "material_evidence.schema.json", encoding="utf-8") as f:
        schema = json.load(f)

    evidence_path = REPO_ROOT / "research" / "materials" / "evidence_matrix.json"
    if evidence_path.exists():
        with open(evidence_path, encoding="utf-8") as f:
            matrix = json.load(f)

        validator = jsonschema.Draft202012Validator(schema)
        for mat in matrix.get("materials", []):
            errors = list(validator.iter_errors(mat))
            assert errors == []


# ====================================================================
# Rào chắn vật liệu (BRD-005). Chặn đúng kịch bản: mot claim vật liệu do AI
# sinh ra được "thêm một dòng vào catalogs.json" và lập tức có số liệu trông
# hợp lệ nhưng nằm ngoài miền hiệu lực của công thức L1.
# ====================================================================

#: Trần f'c mà khối ứng suất chữ nhật của TCVN 11823-5 / AASHTO LRFD còn hiệu
#: lực. Xem docs/03_shape_evolution.md §4. UHPC (f'c >= 160 MPa) nằm NGOÀI.
L1_FC_VALIDITY_LIMIT_MPA = 120.0

CLAIMS_REGISTER = REPO_ROOT / "research" / "materials" / "unverified_claims_register.md"


def test_production_catalog_stays_inside_l1_validity_domain():
    """Không cấp bê tông nào trong catalog sản xuất được vượt miền hiệu lực L1.

    Đây là rào chắn cho MODEL-001: solver L1 sẽ vẫn CHẠY và vẫn TRẢ SỐ với
    f'c = 160 MPa, chỉ là những con số đó vô nghĩa. Không có test này thì lỗi
    im lặng, và im lặng là dạng nguy hiểm nhất.
    """
    for concrete_id, data in load_catalogs()["concretes"].items():
        fc = data["fc_MPa"]
        assert fc <= L1_FC_VALIDITY_LIMIT_MPA, (
            f"{concrete_id} có f'c = {fc} MPa, vượt miền hiệu lực của công thức L1 "
            f"({L1_FC_VALIDITY_LIMIT_MPA} MPa). Muốn dùng vật liệu này phải thay mô "
            f"hình vật liệu và mô hình sức kháng tiết diện trước, không được chỉ "
            f"thêm một dòng vào catalog — xem research/materials/"
            f"unverified_claims_register.md mục UCR-001.")


def test_every_evidence_entry_names_who_tested_it():
    """Không có báo cáo thử nghiệm thì không được nằm trong evidence matrix."""
    evidence_path = REPO_ROOT / "research" / "materials" / "evidence_matrix.json"
    if not evidence_path.exists():
        pytest.skip("chưa có evidence matrix")
    matrix = json.loads(evidence_path.read_text(encoding="utf-8"))
    for material in matrix.get("materials", []):
        provenance = material["provenance"]
        for field in ("source_ref", "test_report_id", "tested_by"):
            assert provenance.get(field), (
                f"{material['material_id']} thiếu {field}; claim chưa có nguồn phải "
                f"nằm ở unverified_claims_register.md, không phải ở đây")


def test_unverified_claims_register_states_blocker_for_each_claim():
    """Mỗi claim chưa kiểm chứng phải nêu rõ vì sao bị chặn và cần gì để gỡ."""
    assert CLAIMS_REGISTER.exists(), "thiếu sổ đăng ký claim chưa kiểm chứng"
    text = CLAIMS_REGISTER.read_text(encoding="utf-8")
    for claim_id in ("UCR-001", "UCR-002", "UCR-003"):
        assert claim_id in text, f"thiếu {claim_id}"
    # Sổ phải nói thẳng ba điều, nếu không nó chỉ là chỗ chứa ý tưởng đẹp.
    assert "Không được bịa" in text
    assert "IDEA" in text
    assert "catalogs.json" in text


def test_uhpc_and_frp_are_not_in_production_catalog():
    """Vật liệu ở mức IDEA không được lọt vào catalog sản xuất."""
    catalogs = load_catalogs()
    concrete_ids = set(catalogs["concretes"])
    steel_ids = set(catalogs["prestressing_steels"])
    for banned in ("UHPC", "CFRP", "FRP", "GEOPOLYMER"):
        offenders = [i for i in concrete_ids | steel_ids if banned in i.upper()]
        assert not offenders, (
            f"{offenders} mang tên gợi ý vật liệu chưa được kiểm chứng; xem "
            f"research/materials/unverified_claims_register.md")
