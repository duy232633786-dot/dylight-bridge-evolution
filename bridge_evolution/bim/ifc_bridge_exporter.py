"""Mô-đun xuất mô hình Open BIM chuẩn quốc tế IFC 4.3 Infrastructure (IfcBridge).

Sử dụng IfcOpenShell để sinh mô hình hình học 3D Solid của dàn dầm Super-T,
bản mặt cầu, dầm ngang, kèm theo đầy đủ bảng thuộc tính (Property Sets),
thông số hình học và chỉ số tối ưu (Cost, Carbon, Mass).
"""
from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Any

import ifcopenshell
import ifcopenshell.api
import ifcopenshell.guid

from ..geometry import derive_geometry
from ..geometry_parametric import compute_super_t_section_properties


def _create_guid() -> str:
    """Tạo GUID chuẩn IFC (22 ký tự Base64)."""
    return ifcopenshell.guid.compress(uuid.uuid4().hex)


def export_bridge_to_ifc(
    state: dict[str, Any],
    output_path: str | Path,
    evaluation_result: dict[str, Any] | None = None,
) -> Path:
    """Xuất phương án thiết kế BridgeDesignState ra file IFC4X3 Bridge.

    Args:
        state: Dict BridgeDesignState (chứa project_inputs, design_variables, materials, v.v.)
        output_path: Đường dẫn file .ifc đầu ra.
        evaluation_result: Kết quả đánh giá tùy chọn (chứa objectives, violations, status).

    Returns:
        Path dẫn tới file .ifc đã tạo thành công.
    """
    output_file = Path(output_path).resolve()
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # 1. Khởi tạo mô hình IFC 4.3
    model = ifcopenshell.file(schema="IFC4X3")

    # 2. Thiết lập thông tin dự án, đơn vị và không gian
    owner_history = model.create_entity(
        "IfcOwnerHistory",
        OwningUser=model.create_entity(
            "IfcPersonAndOrganization",
            ThePerson=model.create_entity("IfcPerson", FamilyName="DYLIGHT", GivenName="Agent"),
            TheOrganization=model.create_entity("IfcOrganization", Name="BridgeAI Research Lab"),
        ),
        OwningApplication=model.create_entity(
            "IfcApplication",
            ApplicationDeveloper=model.create_entity("IfcOrganization", Name="DYLIGHT"),
            Version="0.6.0",
            ApplicationFullName="DYLIGHT Bridge Evolution AI",
            ApplicationIdentifier="DYLIGHT_AI",
        ),
        ChangeAction="ADDED",
        CreationDate=1700000000,
    )

    # Đơn vị: Mét, Radian, Celsius
    length_unit = model.create_entity(
        "IfcSIUnit", UnitType="LENGTHUNIT", Name="METRE"
    )
    plane_angle_unit = model.create_entity(
        "IfcSIUnit", UnitType="PLANEANGLEUNIT", Name="RADIAN"
    )
    unit_assignment = model.create_entity(
        "IfcUnitAssignment", Units=[length_unit, plane_angle_unit]
    )

    # Hệ tọa độ 3D chuẩn
    origin = model.create_entity("IfcCartesianPoint", Coordinates=(0.0, 0.0, 0.0))
    axis3d_z = model.create_entity("IfcDirection", DirectionRatios=(0.0, 0.0, 1.0))
    axis3d_x = model.create_entity("IfcDirection", DirectionRatios=(1.0, 0.0, 0.0))
    world_placement_axis = model.create_entity(
        "IfcAxis2Placement3D", Location=origin, Axis=axis3d_z, RefDirection=axis3d_x
    )
    context = model.create_entity(
        "IfcGeometricRepresentationContext",
        ContextType="Model",
        CoordinateSpaceDimension=3,
        Precision=1e-5,
        WorldCoordinateSystem=world_placement_axis,
    )

    project = model.create_entity(
        "IfcProject",
        GlobalId=_create_guid(),
        OwnerHistory=owner_history,
        Name="DYLIGHT_Parametric_Bridge_Project",
        Description="Mô hình cầu Super-T tham số sinh bởi AI Agent",
        UnitsInContext=unit_assignment,
    )

    site = model.create_entity(
        "IfcSite",
        GlobalId=_create_guid(),
        OwnerHistory=owner_history,
        Name="Bridge_Site",
        CompositionType="ELEMENT",
    )

    # Thực thể IfcBridge trong IFC4X3
    bridge = model.create_entity(
        "IfcBridge",
        GlobalId=_create_guid(),
        OwnerHistory=owner_history,
        Name="Super_T_Bridge",
        Description=f"Cầu dầm Super-T nhịp {state['project_inputs']['span_length_m']}m",
        CompositionType="ELEMENT",
    )

    # Phân cấp: Superstructure
    superstructure = model.create_entity(
        "IfcBridgePart",
        GlobalId=_create_guid(),
        OwnerHistory=owner_history,
        Name="Superstructure",
        PredefinedType="SUPERSTRUCTURE",
        CompositionType="ELEMENT",
    )

    # Liên kết phân cấp không gian
    model.create_entity(
        "IfcRelAggregates",
        GlobalId=_create_guid(),
        RelatingObject=project,
        RelatedObjects=[site],
    )
    model.create_entity(
        "IfcRelAggregates",
        GlobalId=_create_guid(),
        RelatingObject=site,
        RelatedObjects=[bridge],
    )
    model.create_entity(
        "IfcRelAggregates",
        GlobalId=_create_guid(),
        RelatingObject=bridge,
        RelatedObjects=[superstructure],
    )

    # 3. Lấy thông số hình học
    geom = derive_geometry(state)
    span_L = float(geom["span_m"])
    deck_W = float(geom["deck_width_m"])
    n_girders = int(geom["girder_count"])
    spacing_S = float(geom["spacing_m"])
    ts = float(geom["slab_thickness_m"])
    overhang = float(geom["overhang_m"])
    sec_info = geom["section"]
    H_girder = float(sec_info["depth_m"])

    # Tính toán tọa độ đa giác dầm Super-T
    sec_props = compute_super_t_section_properties(depth_m=H_girder)
    outer_pts = sec_props.polygon_outer

    # Tạo Profile dầm 2D trong IFC
    cartesian_pts = [
        model.create_entity("IfcCartesianPoint", Coordinates=(float(x), float(y)))
        for x, y in outer_pts
    ]
    # Đóng kín đường bao
    cartesian_pts.append(cartesian_pts[0])
    polyline = model.create_entity("IfcPolyline", Points=cartesian_pts)
    profile_def = model.create_entity(
        "IfcArbitraryClosedProfileDef",
        ProfileType="AREA",
        ProfileName=f"SuperT_{H_girder*1000:.0f}mm",
        OuterCurve=polyline,
    )

    # 4. Sinh dàn dầm chủ 3D (IfcBeam)
    extrusion_dir = model.create_entity("IfcDirection", DirectionRatios=(0.0, 0.0, 1.0))
    # Đùn dọc theo chiều dài nhịp L
    extruded_solid = model.create_entity(
        "IfcExtrudedAreaSolid",
        SweptArea=profile_def,
        Position=world_placement_axis,
        ExtrudedDirection=extrusion_dir,
        Depth=span_L,
    )

    girder_elements = []
    # Tọa độ dầm đầu tiên (tính từ trái qua phải theo phương Y)
    start_y = -(deck_W / 2.0) + overhang

    for i in range(n_girders):
        girder_y = start_y + i * spacing_S

        # Vị trí đặt dầm: Gốc tại (0, girder_y, 0), xoay đùn dọc theo trục X
        loc = model.create_entity("IfcCartesianPoint", Coordinates=(0.0, girder_y, 0.0))
        # Hướng trục đùn (X = 1, 0, 0)
        axis_z = model.create_entity("IfcDirection", DirectionRatios=(1.0, 0.0, 0.0))
        axis_x = model.create_entity("IfcDirection", DirectionRatios=(0.0, 0.0, 1.0))
        placement_axis = model.create_entity(
            "IfcAxis2Placement3D", Location=loc, Axis=axis_z, RefDirection=axis_x
        )
        local_placement = model.create_entity(
            "IfcLocalPlacement", RelativePlacement=placement_axis
        )

        shape_rep = model.create_entity(
            "IfcShapeRepresentation",
            ContextOfItems=context,
            RepresentationIdentifier="Body",
            RepresentationType="SweptSolid",
            Items=[extruded_solid],
        )
        prod_def_shape = model.create_entity(
            "IfcProductDefinitionShape", Representations=[shape_rep]
        )

        beam = model.create_entity(
            "IfcBeam",
            GlobalId=_create_guid(),
            OwnerHistory=owner_history,
            Name=f"Girder_SuperT_{i+1}",
            Description=f"Dầm Super-T số {i+1}/{n_girders}, H={H_girder}m, L={span_L}m",
            ObjectPlacement=local_placement,
            Representation=prod_def_shape,
            PredefinedType="GIRDER_SEGMENT",
        )
        girder_elements.append(beam)

    # 5. Sinh bản mặt cầu (IfcSlab)
    # Bản mặt cầu dày ts, rộng deck_W, dài span_L đặt trên đỉnh dầm (Z = H_girder)
    slab_origin = model.create_entity(
        "IfcCartesianPoint", Coordinates=(0.0, -deck_W / 2.0, H_girder)
    )
    slab_rect_profile = model.create_entity(
        "IfcRectangleProfileDef",
        ProfileType="AREA",
        ProfileName="DeckSlabProfile",
        XDim=span_L,
        YDim=deck_W,
    )
    # Đặt profile tại tâm bản
    slab_center = model.create_entity(
        "IfcCartesianPoint", Coordinates=(span_L / 2.0, 0.0, H_girder + ts / 2.0)
    )
    slab_placement_axis = model.create_entity(
        "IfcAxis2Placement3D", Location=slab_center, Axis=axis3d_z, RefDirection=axis3d_x
    )
    slab_extruded_solid = model.create_entity(
        "IfcExtrudedAreaSolid",
        SweptArea=slab_rect_profile,
        Position=world_placement_axis,
        ExtrudedDirection=axis3d_z,
        Depth=ts,
    )
    slab_shape_rep = model.create_entity(
        "IfcShapeRepresentation",
        ContextOfItems=context,
        RepresentationIdentifier="Body",
        RepresentationType="SweptSolid",
        Items=[slab_extruded_solid],
    )
    slab_prod_shape = model.create_entity(
        "IfcProductDefinitionShape", Representations=[slab_shape_rep]
    )

    slab_placement = model.create_entity(
        "IfcLocalPlacement",
        RelativePlacement=model.create_entity(
            "IfcAxis2Placement3D", Location=origin, Axis=axis3d_z, RefDirection=axis3d_x
        ),
    )
    deck_slab = model.create_entity(
        "IfcSlab",
        GlobalId=_create_guid(),
        OwnerHistory=owner_history,
        Name="Bridge_Deck_Slab",
        Description=f"Bản mặt cầu bê tông cốt thép dày {ts*1000:.0f}mm",
        ObjectPlacement=slab_placement,
        Representation=slab_prod_shape,
        PredefinedType="FLOOR",
    )

    all_bridge_elements = girder_elements + [deck_slab]

    # Liên kết các cấu kiện vào Superstructure
    model.create_entity(
        "IfcRelContainedInSpatialStructure",
        GlobalId=_create_guid(),
        RelatingStructure=superstructure,
        RelatedElements=all_bridge_elements,
    )

    # 6. Gán bảng thuộc tính kỹ thuật (Property Sets)
    cost_val = evaluation_result.get("objectives", {}).get("relative_cost") if evaluation_result else None
    carbon_val = evaluation_result.get("objectives", {}).get("embodied_carbon") if evaluation_result else None
    mass_val = evaluation_result.get("objectives", {}).get("material_mass") if evaluation_result else None

    props = [
        model.create_entity("IfcPropertySingleValue", Name="SpanLength_m", NominalValue=model.create_entity("IfcReal", span_L)),
        model.create_entity("IfcPropertySingleValue", Name="DeckWidth_m", NominalValue=model.create_entity("IfcReal", deck_W)),
        model.create_entity("IfcPropertySingleValue", Name="GirderCount", NominalValue=model.create_entity("IfcInteger", n_girders)),
        model.create_entity("IfcPropertySingleValue", Name="GirderSpacing_m", NominalValue=model.create_entity("IfcReal", spacing_S)),
        model.create_entity("IfcPropertySingleValue", Name="GirderConcrete", NominalValue=model.create_entity("IfcLabel", state["materials"]["girder_concrete_id"])),
        model.create_entity("IfcPropertySingleValue", Name="DeckConcrete", NominalValue=model.create_entity("IfcLabel", state["materials"]["deck_concrete_id"])),
    ]
    if cost_val is not None:
        props.append(model.create_entity("IfcPropertySingleValue", Name="RelativeCost", NominalValue=model.create_entity("IfcReal", float(cost_val))))
    if carbon_val is not None:
        props.append(model.create_entity("IfcPropertySingleValue", Name="EmbodiedCarbon_kgCO2e", NominalValue=model.create_entity("IfcReal", float(carbon_val))))
    if mass_val is not None:
        props.append(model.create_entity("IfcPropertySingleValue", Name="MaterialMass_tonnes", NominalValue=model.create_entity("IfcReal", float(mass_val))))

    pset = model.create_entity(
        "IfcPropertySet",
        GlobalId=_create_guid(),
        OwnerHistory=owner_history,
        Name="Pset_DylightBridgeOptimization",
        HasProperties=props,
    )
    model.create_entity(
        "IfcRelDefinesByProperties",
        GlobalId=_create_guid(),
        RelatingPropertyDefinition=pset,
        RelatedObjects=[bridge],
    )

    # 7. Lưu file
    model.write(str(output_file))
    return output_file
