"""Sổ tài sản vận hành: mỗi cấu kiện cầu thành một tài sản theo dõi được (BRD-027).

MỨC CLAIM: IDEA. Đây là **lớp dữ liệu trung gian mở**, KHÔNG phải phần mềm quản
lý tài sản chính thức và không thay thế hệ thống quản lý cầu của cơ quan quản lý.
Không hàm nào ở đây trả PASS/FAIL, và không hàm nào tự ý đổi tình trạng cấu kiện.

Hai ranh giới cứng, cả hai đều có test hồi quy neo lại:

1. **GUID xác định.** Định danh sinh bằng UUIDv5 từ một namespace cố định cộng
   khoá cấu kiện. Cùng đầu vào luôn cho cùng GUID, kể cả khác tiến trình, khác
   máy, khác lần chạy. Tuyệt đối không dùng ``uuid4`` hay bất kỳ nguồn ngẫu
   nhiên nào — nếu GUID đổi giữa hai lần xuất thì mọi liên kết giữa hồ sơ kiểm
   định và mô hình BIM đều đứt.

2. **Tình trạng chỉ đổi qua bản ghi kiểm tra của người thật.** ``condition_state``
   không có setter. Cách duy nhất để nó thay đổi là ``record_inspection`` với
   ngày kiểm tra và tên người ghi. Một hệ tự nâng tình trạng cấu kiện là hệ tự
   khai bằng chứng nó không có.

Thang tình trạng 1–4 theo AASHTO Manual for Bridge Element Inspection (element
condition state GOOD/FAIR/POOR/SEVERE). Ở đây chỉ mượn THANG ĐO; việc chấm điểm
là của người kiểm định, module không suy tình trạng ra từ bất cứ tính toán nào.
"""
from __future__ import annotations

import re
import uuid

__all__ = [
    "AssetRegistryError",
    "CONDITION_STATES",
    "DYLIGHT_ASSET_NAMESPACE",
    "asset_guid",
    "build_registry",
    "record_inspection",
    "export_cobie_lite",
    "import_cobie_lite",
]

# Namespace cố định. KHÔNG được đổi: đổi nó là đổi toàn bộ GUID lịch sử.
DYLIGHT_ASSET_NAMESPACE = uuid.UUID("6f1b2c34-5d6e-5f70-8192-a3b4c5d6e7f8")

CONDITION_STATES = {1: "GOOD", 2: "FAIR", 3: "POOR", 4: "SEVERE"}

_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_REGISTRY_NOTE = ("Lớp dữ liệu trung gian mở — không thay thế hệ quản lý cầu "
                  "chính thức; mọi tình trạng đến từ bản ghi kiểm tra của người thật.")


class AssetRegistryError(ValueError):
    """Dữ liệu tài sản không hợp lệ — từ chối thay vì đoán."""


def _require_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AssetRegistryError(f"{field} phải là chuỗi không rỗng")
    return value.strip()


def _require_date(value: object, field: str) -> str:
    text = _require_text(value, field)
    if not _ISO_DATE.match(text):
        raise AssetRegistryError(f"{field} phải theo dạng YYYY-MM-DD, nhận {text!r}")
    return text


def _require_state(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise AssetRegistryError("condition_state phải là số nguyên 1–4")
    if value not in CONDITION_STATES:
        raise AssetRegistryError(
            f"condition_state phải trong {sorted(CONDITION_STATES)}, nhận {value}")
    return value


def _require_index(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise AssetRegistryError("element_index phải là số nguyên")
    if value < 0:
        raise AssetRegistryError("element_index không âm")
    return value


def asset_guid(bridge_id: str, element_type: str, element_index: int) -> str:
    """GUID XÁC ĐỊNH cho một cấu kiện. Cùng đầu vào ⇒ cùng GUID, không RNG.

    Khoá được chuẩn hoá (bỏ khoảng trắng thừa, hạ chữ thường) trước khi băm, để
    hai cách gõ khác nhau của cùng một cấu kiện không sinh ra hai tài sản.
    """
    bridge = _require_text(bridge_id, "bridge_id").lower()
    etype = _require_text(element_type, "element_type").lower()
    index = _require_index(element_index)
    return str(uuid.uuid5(DYLIGHT_ASSET_NAMESPACE, f"{bridge}|{etype}|{index}"))


def build_registry(bridge_id: str, elements: list) -> dict:
    """Dựng sổ tài sản từ danh sách cấu kiện.

    Mỗi phần tử cần ``element_type`` và ``element_index``; ``design_life_years``
    là tuỳ chọn. Tình trạng ban đầu của MỌI cấu kiện là 1 (GOOD) với lịch sử
    RỖNG và ``condition_evidence = "NONE"`` — chưa ai kiểm tra thì chưa có bằng
    chứng nào về tình trạng, và hồ sơ phải nói thẳng điều đó.
    """
    bridge = _require_text(bridge_id, "bridge_id")
    if not isinstance(elements, list) or not elements:
        raise AssetRegistryError("elements phải là list không rỗng")

    assets: dict = {}
    for item in elements:
        if not isinstance(item, dict):
            raise AssetRegistryError("mỗi element phải là object")
        etype = _require_text(item.get("element_type"), "element_type")
        index = _require_index(item.get("element_index"))
        guid = asset_guid(bridge, etype, index)
        if guid in assets:
            raise AssetRegistryError(
                f"trùng cấu kiện {etype}#{index} — mỗi (loại, chỉ số) chỉ một tài sản")
        design_life = item.get("design_life_years")
        if design_life is not None:
            design_life = float(design_life)
            if design_life <= 0:
                raise AssetRegistryError("design_life_years phải dương")
        assets[guid] = {
            "guid": guid,
            "bridge_id": bridge,
            "element_type": etype,
            "element_index": index,
            "design_life_years": design_life,
            "condition_state": 1,
            "condition_label": CONDITION_STATES[1],
            "inspection_history": [],
            "condition_evidence": "NONE",
        }
    return {
        "schema_version": 1,
        "bridge_id": bridge,
        "assets": assets,
        "advisory": True,
        "note": _REGISTRY_NOTE,
    }


def record_inspection(registry: dict, guid: str, condition_state: int,
                      inspected_on: str, inspector: str, notes: str = "") -> dict:
    """Ghi một lần kiểm tra. ĐÂY LÀ CÁCH DUY NHẤT tình trạng được thay đổi.

    Bản ghi chỉ được nối thêm vào ``inspection_history``; không sửa và không xoá
    bản cũ. Thiếu ngày hoặc thiếu người ghi thì từ chối. Ngày lùi về trước lần
    kiểm tra gần nhất cũng bị từ chối — lịch sử phải tiến theo thời gian.
    """
    assets = registry.get("assets") if isinstance(registry, dict) else None
    if not isinstance(assets, dict):
        raise AssetRegistryError("registry không hợp lệ")
    asset = assets.get(guid)
    if asset is None:
        raise AssetRegistryError(f"không có tài sản nào mang guid {guid}")

    state = _require_state(condition_state)
    day = _require_date(inspected_on, "inspected_on")
    who = _require_text(inspector, "inspector")

    history = asset["inspection_history"]
    if history and day < history[-1]["inspected_on"]:
        raise AssetRegistryError(
            f"ngày kiểm tra {day} sớm hơn lần trước {history[-1]['inspected_on']} — "
            "lịch sử phải tiến theo thời gian")

    record = {
        "inspected_on": day,
        "inspector": who,
        "condition_state": state,
        "condition_label": CONDITION_STATES[state],
        "notes": str(notes),
    }
    history.append(record)
    asset["condition_state"] = state
    asset["condition_label"] = CONDITION_STATES[state]
    asset["condition_evidence"] = "INSPECTION_RECORD"
    return record


def export_cobie_lite(registry: dict) -> dict:
    """Xuất COBie-lite: ba bảng type / component / attribute.

    Giữ đúng ba bảng tối thiểu của COBie để dữ liệu đi sang hệ khác được mà
    không phải mang theo schema riêng của dự án này.
    """
    assets = registry.get("assets") if isinstance(registry, dict) else None
    if not isinstance(assets, dict):
        raise AssetRegistryError("registry không hợp lệ")

    types: dict = {}
    components: list = []
    attributes: list = []

    for guid in sorted(assets):
        asset = assets[guid]
        etype = asset["element_type"]
        types.setdefault(etype, {"Name": etype, "Category": "BridgeElement"})
        components.append({
            "Name": f"{etype}-{asset['element_index']}",
            "TypeName": etype,
            "Space": asset["bridge_id"],
            "ExternalIdentifier": guid,
        })
        attributes.append({
            "ExternalIdentifier": guid,
            "ConditionState": asset["condition_state"],
            "ConditionLabel": asset["condition_label"],
            "ConditionEvidence": asset["condition_evidence"],
            "DesignLifeYears": asset["design_life_years"],
            "InspectionHistory": [dict(r) for r in asset["inspection_history"]],
        })

    return {
        "schema_version": 1,
        "facility": registry.get("bridge_id"),
        "types": [types[k] for k in sorted(types)],
        "components": components,
        "attributes": attributes,
    }


def import_cobie_lite(document: dict) -> dict:
    """Nạp ngược COBie-lite thành registry.

    GUID trong hồ sơ được TÍNH LẠI từ (facility, TypeName, chỉ số) và phải khớp;
    lệch là hồ sơ đã bị sửa tay hoặc sinh bởi namespace khác, và bị từ chối.
    """
    if not isinstance(document, dict):
        raise AssetRegistryError("document phải là object")
    facility = _require_text(document.get("facility"), "facility")
    components = document.get("components")
    attributes = document.get("attributes")
    if not isinstance(components, list) or not isinstance(attributes, list):
        raise AssetRegistryError("thiếu components hoặc attributes")

    by_guid = {a.get("ExternalIdentifier"): a for a in attributes}
    if len(by_guid) != len(attributes):
        raise AssetRegistryError("ExternalIdentifier trùng trong attributes")

    assets: dict = {}
    for comp in components:
        guid = comp.get("ExternalIdentifier")
        attr = by_guid.get(guid)
        if attr is None:
            raise AssetRegistryError(f"component {guid} không có attribute tương ứng")
        etype = _require_text(comp.get("TypeName"), "TypeName")
        name = _require_text(comp.get("Name"), "Name")
        try:
            index = int(name.rsplit("-", 1)[1])
        except (IndexError, ValueError) as exc:
            raise AssetRegistryError(
                f"Name {name!r} không mang chỉ số cấu kiện") from exc
        expected = asset_guid(facility, etype, index)
        if expected != guid:
            raise AssetRegistryError(
                f"GUID không tái lập được cho {name}: hồ sơ ghi {guid}, "
                f"tính lại ra {expected}")
        design_life = attr.get("DesignLifeYears")
        assets[guid] = {
            "guid": guid,
            "bridge_id": facility,
            "element_type": etype,
            "element_index": index,
            "design_life_years": None if design_life is None else float(design_life),
            "condition_state": _require_state(attr.get("ConditionState")),
            "condition_label": CONDITION_STATES[_require_state(attr.get("ConditionState"))],
            "inspection_history": [dict(r) for r in (attr.get("InspectionHistory") or [])],
            "condition_evidence": attr.get("ConditionEvidence", "NONE"),
        }
    return {
        "schema_version": 1,
        "bridge_id": facility,
        "assets": assets,
        "advisory": True,
        "note": _REGISTRY_NOTE,
    }
