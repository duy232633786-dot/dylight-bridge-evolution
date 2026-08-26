"""Lớp tài sản vận hành BIM: GUID xác định, tình trạng có bằng chứng (BRD-027).

Hai hàng rào quan trọng hơn phần tính năng, và nới một dòng ở đây là hỏng đúng
thứ mà lớp này sinh ra để bảo vệ:

1. GUID phải TÁI LẬP ĐƯỢC qua tiến trình khác. Nếu nó đổi giữa hai lần xuất thì
   mọi liên kết giữa hồ sơ kiểm định và mô hình BIM đều đứt, mà đứt âm thầm.
2. Tình trạng cấu kiện KHÔNG được đổi bằng bất cứ đường nào ngoài bản ghi kiểm
   tra có ngày và người ghi. Một hệ tự nâng tình trạng là hệ tự khai bằng chứng
   nó không có.
"""
import json
import subprocess
import sys

import pytest

from bridge_evolution import REPO_ROOT
from bridge_evolution.bim.asset_registry import (CONDITION_STATES,
                                                 AssetRegistryError,
                                                 asset_guid, build_registry,
                                                 export_cobie_lite,
                                                 import_cobie_lite,
                                                 record_inspection)
from bridge_evolution.bim.inspection_plan import (plan_for_asset,
                                                  plan_for_registry)


def _registry():
    return build_registry("BR-01", [
        {"element_type": "girder", "element_index": 0},
        {"element_type": "girder", "element_index": 1},
        {"element_type": "bearing", "element_index": 0, "design_life_years": 25},
    ])


# ---------------------------------------------------------------------------
# 1. GUID xác định
# ---------------------------------------------------------------------------

def test_guid_is_stable_across_processes():
    """Chạy lại trong tiến trình KHÁC phải ra đúng GUID đó — không RNG, không seed."""
    here = asset_guid("BR-01", "girder", 3)
    out = subprocess.run(
        [sys.executable, "-c",
         "from bridge_evolution.bim.asset_registry import asset_guid;"
         "print(asset_guid('BR-01', 'girder', 3))"],
        cwd=REPO_ROOT, capture_output=True, text=True, check=True)
    assert out.stdout.strip() == here


def test_guid_normalises_the_key_so_one_element_is_one_asset():
    assert asset_guid("BR-01", "girder", 3) == asset_guid("  br-01 ", "GIRDER", 3)


def test_guid_separates_different_elements():
    seen = {asset_guid("BR-01", "girder", i) for i in range(5)}
    assert len(seen) == 5
    assert asset_guid("BR-01", "girder", 0) != asset_guid("BR-02", "girder", 0)
    assert asset_guid("BR-01", "girder", 0) != asset_guid("BR-01", "bearing", 0)


def test_guid_refuses_junk_input():
    for bad in ("", "   ", None, 7):
        with pytest.raises(AssetRegistryError):
            asset_guid(bad, "girder", 0)
    with pytest.raises(AssetRegistryError):
        asset_guid("BR-01", "girder", -1)
    with pytest.raises(AssetRegistryError):
        asset_guid("BR-01", "girder", True)


# ---------------------------------------------------------------------------
# 2. Tình trạng chỉ đổi qua bản ghi kiểm tra
# ---------------------------------------------------------------------------

def test_fresh_registry_claims_no_condition_evidence():
    """Chưa ai kiểm tra thì hồ sơ phải NÓI RA là chưa có bằng chứng."""
    reg = _registry()
    for asset in reg["assets"].values():
        assert asset["condition_state"] == 1
        assert asset["inspection_history"] == []
        assert asset["condition_evidence"] == "NONE"


def test_condition_changes_only_through_an_inspection_record():
    reg = _registry()
    guid = asset_guid("BR-01", "girder", 0)
    record_inspection(reg, guid, 3, "2026-05-04", "KS Nguyen Van A", "nut doc suon")
    asset = reg["assets"][guid]
    assert asset["condition_state"] == 3
    assert asset["condition_label"] == CONDITION_STATES[3]
    assert asset["condition_evidence"] == "INSPECTION_RECORD"
    assert len(asset["inspection_history"]) == 1
    assert asset["inspection_history"][0]["inspector"] == "KS Nguyen Van A"


def test_inspection_without_a_named_inspector_or_a_date_is_refused():
    reg = _registry()
    guid = asset_guid("BR-01", "girder", 0)
    with pytest.raises(AssetRegistryError):
        record_inspection(reg, guid, 2, "2026-05-04", "")
    with pytest.raises(AssetRegistryError):
        record_inspection(reg, guid, 2, "04/05/2026", "KS A")
    with pytest.raises(AssetRegistryError):
        record_inspection(reg, guid, 2, "", "KS A")
    # thất bại KHÔNG được để lại dấu vết nào
    assert reg["assets"][guid]["inspection_history"] == []
    assert reg["assets"][guid]["condition_evidence"] == "NONE"


def test_condition_state_outside_one_to_four_is_refused():
    reg = _registry()
    guid = asset_guid("BR-01", "girder", 0)
    for bad in (0, 5, -1, 2.5, True, "3"):
        with pytest.raises(AssetRegistryError):
            record_inspection(reg, guid, bad, "2026-05-04", "KS A")


def test_history_cannot_walk_backwards_in_time():
    reg = _registry()
    guid = asset_guid("BR-01", "girder", 0)
    record_inspection(reg, guid, 2, "2026-05-04", "KS A")
    with pytest.raises(AssetRegistryError):
        record_inspection(reg, guid, 1, "2025-01-01", "KS B")


def test_history_is_append_only():
    reg = _registry()
    guid = asset_guid("BR-01", "girder", 0)
    record_inspection(reg, guid, 2, "2026-05-04", "KS A")
    record_inspection(reg, guid, 3, "2027-05-04", "KS B")
    history = reg["assets"][guid]["inspection_history"]
    assert [r["condition_state"] for r in history] == [2, 3]
    assert history[0]["inspector"] == "KS A"


def test_inspecting_an_unknown_guid_is_refused():
    reg = _registry()
    with pytest.raises(AssetRegistryError):
        record_inspection(reg, "khong-ton-tai", 2, "2026-05-04", "KS A")


def test_duplicate_element_is_refused():
    with pytest.raises(AssetRegistryError):
        build_registry("BR-01", [
            {"element_type": "girder", "element_index": 0},
            {"element_type": "GIRDER", "element_index": 0},
        ])


# ---------------------------------------------------------------------------
# 3. COBie-lite round-trip
# ---------------------------------------------------------------------------

def test_cobie_lite_round_trip_is_lossless():
    reg = _registry()
    guid = asset_guid("BR-01", "girder", 1)
    record_inspection(reg, guid, 4, "2026-06-01", "KS C", "be vo be tong")

    doc = export_cobie_lite(reg)
    assert {t["Name"] for t in doc["types"]} == {"girder", "bearing"}
    assert len(doc["components"]) == len(doc["attributes"]) == 3

    back = import_cobie_lite(doc)
    assert back["assets"] == reg["assets"]
    assert json.loads(json.dumps(back)) == json.loads(json.dumps(reg))


def test_round_trip_survives_json_serialisation():
    reg = _registry()
    doc = json.loads(json.dumps(export_cobie_lite(reg)))
    assert import_cobie_lite(doc)["assets"] == reg["assets"]


def test_import_refuses_a_forged_guid():
    """GUID được TÍNH LẠI khi nạp; sửa tay một ký tự là bị bắt."""
    reg = _registry()
    doc = export_cobie_lite(reg)
    doc["attributes"][0]["ExternalIdentifier"] = "00000000-0000-5000-8000-000000000000"
    doc["components"][0]["ExternalIdentifier"] = "00000000-0000-5000-8000-000000000000"
    with pytest.raises(AssetRegistryError):
        import_cobie_lite(doc)


def test_import_refuses_a_component_with_no_attribute():
    reg = _registry()
    doc = export_cobie_lite(reg)
    doc["attributes"].pop()
    with pytest.raises(AssetRegistryError):
        import_cobie_lite(doc)


# ---------------------------------------------------------------------------
# 4. Kế hoạch quan trắc sinh từ engine tuổi thọ (BRD-026)
# ---------------------------------------------------------------------------

def test_first_inspection_falls_before_predicted_initiation():
    """Kiểm tra sau khi ăn mòn đã khởi phát thì chỉ còn ghi nhận thiệt hại."""
    reg = _registry()
    asset = reg["assets"][asset_guid("BR-01", "girder", 0)]
    plan = plan_for_asset(asset, cover_mm=40.0, mechanism="carbonation")
    assert plan["inspection_years"]
    assert plan["first_inspection_year"] < plan["t_initiate_years"]
    assert plan["first_inspection_precedes_initiation"] is True


def test_thinner_cover_brings_initiation_and_the_schedule_forward():
    """Bảo vệ mỏng hơn ⇒ khởi phát sớm hơn. Quan hệ này phải đi đúng chiều."""
    reg = _registry()
    asset = reg["assets"][asset_guid("BR-01", "girder", 0)]
    thin = plan_for_asset(asset, cover_mm=20.0)
    thick = plan_for_asset(asset, cover_mm=60.0)
    assert thin["t_initiate_years"] < thick["t_initiate_years"]


def test_plan_uses_the_design_life_declared_on_the_asset():
    reg = _registry()
    bearing = reg["assets"][asset_guid("BR-01", "bearing", 0)]
    plan = plan_for_asset(bearing, cover_mm=40.0, design_life_years=100.0)
    assert plan["design_life_years"] == 25.0
    assert max(plan["inspection_years"]) <= 25.0


def test_plan_carries_the_condition_evidence_flag_through():
    reg = _registry()
    guid = asset_guid("BR-01", "girder", 0)
    before = plan_for_asset(reg["assets"][guid], cover_mm=40.0)
    assert before["condition_evidence"] == "NONE"
    record_inspection(reg, guid, 2, "2026-05-04", "KS A")
    after = plan_for_asset(reg["assets"][guid], cover_mm=40.0)
    assert after["condition_evidence"] == "INSPECTION_RECORD"


def test_registry_plan_records_what_it_skipped_instead_of_dropping_it():
    """Im lặng bỏ một cấu kiện khỏi kế hoạch quan trắc là kiểu hỏng tệ nhất."""
    reg = _registry()
    out = plan_for_registry(reg, {"girder": 40.0})
    assert len(out["plans"]) == 2
    assert len(out["skipped"]) == 1
    assert out["skipped"][0]["element_type"] == "bearing"
    assert out["skipped"][0]["reason"]


def test_registry_plan_needs_a_cover_table():
    reg = _registry()
    with pytest.raises(AssetRegistryError):
        plan_for_registry(reg, {})


def test_unknown_mechanism_is_refused():
    reg = _registry()
    asset = reg["assets"][asset_guid("BR-01", "girder", 0)]
    with pytest.raises(AssetRegistryError):
        plan_for_asset(asset, cover_mm=40.0, mechanism="khong_ton_tai")


# ---------------------------------------------------------------------------
# 5. Ranh giới an toàn
# ---------------------------------------------------------------------------

def test_nothing_in_this_layer_returns_pass_or_fail():
    """Lớp tài sản là dữ liệu, không phải verifier. Mọi đầu ra là advisory."""
    reg = _registry()
    asset = reg["assets"][asset_guid("BR-01", "girder", 0)]
    plan = plan_for_asset(asset, cover_mm=40.0)
    assert plan["advisory"] is True
    assert reg["advisory"] is True
    for blob in (reg, plan, export_cobie_lite(reg)):
        text = json.dumps(blob, ensure_ascii=False)
        assert "PASS" not in text and "FAIL" not in text
