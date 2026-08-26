"""Đọc và kiểm hồ sơ site; phát SITE-001 khi rule hạ nguồn thiếu đầu vào.

Ranh giới của module này, nói trước cho khỏi hiểu nhầm:

* Nó KHÔNG tính hazard. Không xói, không phổ động đất, không áp lực gió. Việc đó
  thuộc nhóm rule ``HYDRO-*`` / ``SEIS-*`` / ``WIND-*`` / ``GEO-*`` sẽ viết sau.
* Nó KHÔNG điền giá trị mặc định. Một trường ``UNKNOWN`` đi ra khỏi đây vẫn là
  ``UNKNOWN``. "Với cầu nhịp 38 m thì rủi ro khí động thường thấp" là suy đoán,
  không phải bằng chứng — chính ``SITE-UNSPECIFIED.json`` đã từ chối hạ trường
  ``aerodynamic_risk_level`` xuống LOW vì lý do đó.
* Nó CHỈ trả lời: rule X cần những trường nào, và trong hồ sơ này trường nào
  chưa có. Thiếu thì dừng — đúng tinh thần G0 "thiếu dữ liệu thì dừng".
"""
from __future__ import annotations

import json
from pathlib import Path

#: Rule chặn: chạy tối ưu trên hồ sơ site thiếu dữ liệu mà rule hạ nguồn cần.
SITE_READINESS_RULE = "SITE-001"

#: Trường site mà mỗi nhóm rule hạ nguồn CẦN. Con trỏ dạng JSON pointer rút gọn.
#: Bảng này là hợp đồng: thêm một rule hazard mới thì phải khai nó cần gì ở đây,
#: nếu không rule đó sẽ chạy trên dữ liệu trống mà không ai biết.
RULE_INPUT_REQUIREMENTS: dict[str, tuple[str, ...]] = {
    "HYDRO": (
        "hydrology_scour/design_flood_frequency_years",
        "hydrology_scour/design_water_level_m",
        "hydrology_scour/estimated_scour_depth_m",
        "hydrology_scour/navigation_clearance",
    ),
    "SEIS": (
        "seismic_hazard/pga_g",
        "seismic_hazard/site_class",
    ),
    "WIND": (
        "wind_hazard/basic_wind_speed_m_s",
        "geographic_location/terrain_category",
    ),
    "GEO": (
        "geotechnical_category",
        "geotechnical_investigation/investigation_status",
    ),
    "DUR": (
        "corrosion_exposure",
    ),
}


class SiteDataError(ValueError):
    """Hồ sơ site không đọc được hoặc không đúng hợp đồng."""


def load_site_profile(path: str | Path) -> dict:
    """Đọc hồ sơ site. Không suy diễn, không vá thiếu."""
    source = Path(path)
    if not source.is_file():
        raise SiteDataError(f"Không tìm thấy hồ sơ site: {source}")
    try:
        profile = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SiteDataError(f"Hồ sơ site không phải JSON hợp lệ: {exc}") from exc
    if "site_id" not in profile:
        raise SiteDataError("Hồ sơ site thiếu site_id")
    return profile


def evidence(profile: dict, pointer: str) -> tuple[str, object | None]:
    """Trạng thái và giá trị của một trường, theo con trỏ ``a/b/c``.

    Trả ``("MISSING", None)`` khi hồ sơ không có trường đó — khác hẳn ``UNKNOWN``
    (đã khai là chưa biết) và khác hẳn ``KNOWN`` (đã có bằng chứng).
    """
    node: object = profile
    for part in pointer.split("/"):
        if not isinstance(node, dict) or part not in node:
            return "MISSING", None
        node = node[part]
    if not isinstance(node, dict) or "status" not in node:
        return "MISSING", None
    status = node["status"]
    return status, node.get("value") if status == "KNOWN" else None


def required_site_fields(rule_groups: object) -> tuple[str, ...]:
    """Hợp các trường site mà một tập nhóm rule cần."""
    if isinstance(rule_groups, str):
        rule_groups = [rule_groups]
    fields: list[str] = []
    for group in rule_groups:
        prefix = str(group).split("-")[0].upper()
        for field in RULE_INPUT_REQUIREMENTS.get(prefix, ()):
            if field not in fields:
                fields.append(field)
    return tuple(fields)


def check_site_readiness(profile: dict | None, rule_groups: object) -> list[dict]:
    """Vi phạm SITE-001, nêu ĐÍCH DANH trường thiếu.

    Không có hồ sơ cũng là một vi phạm — im lặng chạy tiếp mới là điều nguy hiểm.
    """
    needed = required_site_fields(rule_groups)
    if not needed:
        return []
    if profile is None:
        return [{
            "rule_id": SITE_READINESS_RULE,
            "severity": "HARD",
            "message": (
                "Không có hồ sơ site nào được khai, trong khi các rule "
                f"{sorted(set(str(g).split('-')[0].upper() for g in ([rule_groups] if isinstance(rule_groups, str) else rule_groups)))} "
                f"cần {len(needed)} trường site. Thiếu dữ liệu thì dừng (G0)."
            ),
            "margin": 1.0,
        }]

    missing: list[str] = []
    for pointer in needed:
        status, _ = evidence(profile, pointer)
        if status != "KNOWN":
            missing.append(f"{pointer} [{status}]")
    if not missing:
        return []
    return [{
        "rule_id": SITE_READINESS_RULE,
        "severity": "HARD",
        "message": (
            f"Hồ sơ site {profile.get('site_id', '?')} thiếu {len(missing)}/{len(needed)} "
            f"trường mà rule hạ nguồn cần: {', '.join(missing)}. "
            "Không được thay bằng giá trị giả định."
        ),
        "margin": len(missing) / len(needed),
    }]


def site_binding(profile: dict | None) -> dict | None:
    """Dấu vết site để ghi vào provenance của một lần đánh giá."""
    if profile is None:
        return None
    return {
        "site_id": profile.get("site_id"),
        "site_status": profile.get("site_status"),
        "schema_version": profile.get("schema_version"),
    }


def n60(
    n_field: int,
    *,
    energy_ratio: float,
    rod_length_m: float,
    borehole_diameter_mm: float = 100.0,
    liner: bool = False,
) -> float:
    """SPT hiệu chỉnh về năng lượng 60% — N60 = N · CE · CR · CB · CS.

    Hệ số theo thực hành phổ biến (Skempton 1986; FHWA GEC-5). Đây là phép hiệu
    chỉnh NĂNG LƯỢNG và hình học lỗ khoan, KHÔNG phải hiệu chỉnh ứng suất phủ
    (N1)60 — hai thứ đó khác nhau và không được dùng lẫn.
    """
    if n_field < 0:
        raise SiteDataError("N hiện trường không thể âm")
    if not 0 < energy_ratio <= 1.5:
        raise SiteDataError(f"energy_ratio phi lý: {energy_ratio}")
    ce = energy_ratio / 0.60
    if rod_length_m < 3:
        cr = 0.75
    elif rod_length_m < 4:
        cr = 0.80
    elif rod_length_m < 6:
        cr = 0.85
    elif rod_length_m < 10:
        cr = 0.95
    else:
        cr = 1.00
    if borehole_diameter_mm <= 115:
        cb = 1.00
    elif borehole_diameter_mm <= 150:
        cb = 1.05
    else:
        cb = 1.15
    cs = 1.20 if liner else 1.00
    return n_field * ce * cr * cb * cs


def borehole_layer_at(borehole: dict, depth_m: float) -> dict | None:
    """Lớp địa tầng tại một độ sâu. Ngoài phạm vi hố khoan thì trả None."""
    if depth_m < 0:
        raise SiteDataError("Độ sâu không thể âm")
    for layer in borehole.get("layers", []):
        if layer["from_depth_m"] <= depth_m < layer["to_depth_m"]:
            return layer
    return None
