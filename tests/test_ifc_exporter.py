"""Kiểm thử mô-đun xuất mô hình Open BIM IFC 4.3 (ifc_bridge_exporter.py)."""
import json
from pathlib import Path
import pytest

ifcopenshell = pytest.importorskip("ifcopenshell")

from bridge_evolution.bim import export_bridge_to_ifc
from bridge_evolution.state import new_state


def test_export_bridge_to_ifc(tmp_path: Path):
    # Tạo một state hợp lệ
    state = new_state(
        design_variables={
            "girder_catalog_id": "ST-1750",
            "girder_count": 5,
            "girder_spacing_mm": 2400,
            "deck_slab_thickness_mm": 200,
            "diaphragm_layout_id": "DG-5",
            "prestress_layout_id": "PT-42",
        },
        girder_concrete_id="C45",
        deck_concrete_id="C35",
    )

    out_file = tmp_path / "test_bridge_out.ifc"
    res_path = export_bridge_to_ifc(
        state=state,
        output_path=out_file,
        evaluation_result={
            "objectives": {"relative_cost": 500.0, "embodied_carbon": 40000.0, "material_mass": 250.0},
            "status": "FEASIBLE",
        },
    )

    assert res_path.exists()
    assert res_path.stat().st_size > 1000

    # Đọc lại và kiểm tra tính toàn vẹn của mô hình IFC
    model = ifcopenshell.open(str(res_path))
    assert model.schema == "IFC4X3"

    # Kiểm tra thực thể cầu
    bridges = model.by_type("IfcBridge")
    assert len(bridges) == 1

    # Kiểm tra dầm chủ (5 dầm)
    beams = model.by_type("IfcBeam")
    assert len(beams) == 5

    # Kiểm tra bản mặt cầu
    slabs = model.by_type("IfcSlab")
    assert len(slabs) == 1

    # Kiểm tra PropertySet
    psets = model.by_type("IfcPropertySet")
    pset_names = [p.Name for p in psets]
    assert "Pset_DylightBridgeOptimization" in pset_names
