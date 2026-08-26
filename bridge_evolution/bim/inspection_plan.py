"""Kế hoạch quan trắc sinh từ engine tuổi thọ, gắn vào từng tài sản (BRD-027).

MỨC CLAIM: IDEA/ADVISORY. Không hàm nào ở đây trả PASS/FAIL. Đầu ra là **đề
xuất** lịch kiểm tra, không phải phê duyệt kỹ thuật và không thay quy định quan
trắc của chủ đầu tư hay cơ quan quản lý.

Module này KHÔNG chứa mô hình khấu hao nào. Toàn bộ phần vật lý được lấy từ
``bridge_evolution.durability`` (BRD-026): ``carbonation_initiation_years`` /
``chloride_initiation_years`` cho thời điểm khởi phát ăn mòn, và
``inspection_plan`` / ``optimal_inspection_interval`` cho lịch. Viết lại chúng ở
đây là tạo bản sao thứ hai của cùng một giả định — đúng lớp lỗi đã cắn repo này
ba lần ở BRD-030, BRD-032 và BRD-033.

Nguyên tắc của lịch: **lần kiểm tra đầu phải rơi TRƯỚC thời điểm khởi phát dự
báo**. Kiểm tra sau khi ăn mòn đã khởi phát thì chỉ còn ghi nhận thiệt hại, mất
hẳn quãng thời gian mà can thiệp còn rẻ.
"""
from __future__ import annotations

from ..durability import (carbonation_initiation_years,
                          chloride_initiation_years, inspection_plan,
                          optimal_inspection_interval)
from .asset_registry import AssetRegistryError

__all__ = ["MECHANISMS", "initiation_years", "plan_for_asset", "plan_for_registry"]

MECHANISMS = ("carbonation", "chloride")


def initiation_years(cover_mm: float, mechanism: str = "carbonation", **kwargs) -> float:
    """Thời điểm khởi phát ăn mòn (năm), lấy thẳng từ engine BRD-026."""
    if mechanism not in MECHANISMS:
        raise AssetRegistryError(
            f"mechanism phải trong {list(MECHANISMS)}, nhận {mechanism!r}")
    if cover_mm <= 0:
        raise AssetRegistryError("cover_mm phải dương")
    if mechanism == "carbonation":
        return carbonation_initiation_years(cover_mm, **kwargs)
    return chloride_initiation_years(cover_mm, **kwargs)


def plan_for_asset(asset: dict, cover_mm: float, mechanism: str = "carbonation",
                   design_life_years: float = 100.0, current_age_years: float = 0.0,
                   **kwargs) -> dict:
    """Lịch quan trắc đề xuất cho MỘT tài sản.

    ``design_life_years`` ưu tiên lấy từ chính tài sản nếu nó có khai; tham số
    chỉ là giá trị lùi. Không bịa tuổi thọ thiết kế khi hồ sơ đã nói.
    """
    if not isinstance(asset, dict) or "guid" not in asset:
        raise AssetRegistryError("asset không hợp lệ")

    declared = asset.get("design_life_years")
    life = float(declared) if declared else float(design_life_years)
    if life <= 0:
        raise AssetRegistryError("design_life_years phải dương")

    t_init = initiation_years(cover_mm, mechanism, **kwargs)
    schedule = inspection_plan(t_initiate_years=t_init, design_life_years=life,
                               current_age_years=current_age_years)

    years = list(schedule.get("inspection_years") or [])
    first = schedule.get("first_inspection_year")
    # Bất biến phải giữ: lần đầu nằm TRƯỚC khởi phát. Nếu engine trả lịch không
    # thoả (ví dụ khởi phát rất sớm so với tuổi hiện tại), nói thẳng ra thay vì
    # lặng lẽ đưa ra một lịch đã muộn.
    covered = bool(years) and float(first) < t_init
    return {
        "guid": asset["guid"],
        "element_type": asset.get("element_type"),
        "mechanism": mechanism,
        "cover_mm": float(cover_mm),
        "t_initiate_years": round(float(t_init), 1),
        "design_life_years": life,
        "first_inspection_year": first,
        "inspection_years": years,
        "first_inspection_precedes_initiation": covered,
        "condition_state": asset.get("condition_state"),
        "condition_evidence": asset.get("condition_evidence", "NONE"),
        "advisory": True,
        "note": ("Lịch ĐỀ XUẤT từ mô hình sàng lọc; không phải phê duyệt kỹ thuật "
                 "và không thay quy định quan trắc của cơ quan quản lý."),
    }


def plan_for_registry(registry: dict, cover_by_type: dict,
                      mechanism: str = "carbonation",
                      design_life_years: float = 100.0,
                      current_age_years: float = 0.0, **kwargs) -> dict:
    """Lịch quan trắc cho cả sổ tài sản, gom theo loại cấu kiện.

    ``cover_by_type`` cho chiều dày lớp bảo vệ của từng loại cấu kiện. Loại nào
    KHÔNG có trong bảng thì bị bỏ qua và ghi vào ``skipped`` kèm lý do — im lặng
    bỏ sót một cấu kiện khỏi kế hoạch quan trắc là kiểu hỏng nguy hiểm nhất của
    một module như thế này.
    """
    assets = registry.get("assets") if isinstance(registry, dict) else None
    if not isinstance(assets, dict):
        raise AssetRegistryError("registry không hợp lệ")
    if not isinstance(cover_by_type, dict) or not cover_by_type:
        raise AssetRegistryError("cover_by_type phải là dict không rỗng")

    plans: list = []
    skipped: list = []
    for guid in sorted(assets):
        asset = assets[guid]
        etype = asset["element_type"]
        cover = cover_by_type.get(etype)
        if cover is None:
            skipped.append({
                "guid": guid,
                "element_type": etype,
                "reason": "thiếu cover_mm cho loại cấu kiện này — không đoán",
            })
            continue
        plans.append(plan_for_asset(
            asset, cover_mm=cover, mechanism=mechanism,
            design_life_years=design_life_years,
            current_age_years=current_age_years, **kwargs))

    return {
        "schema_version": 1,
        "bridge_id": registry.get("bridge_id"),
        "mechanism": mechanism,
        "plans": plans,
        "skipped": skipped,
        "advisory": True,
    }


def optimal_interval_for_asset(asset: dict, cover_mm: float, cost_inspection: float,
                               cost_late_detection: float,
                               mechanism: str = "carbonation",
                               design_life_years: float = 100.0, **kwargs) -> dict:
    """Chu kỳ kiểm tra tối ưu theo LCC-lite, uỷ thác cho engine BRD-026."""
    t_init = initiation_years(cover_mm, mechanism, **kwargs)
    result = optimal_inspection_interval(
        t_initiate_years=t_init, cost_inspection=cost_inspection,
        cost_late_detection=cost_late_detection, design_life_years=design_life_years)
    return {"guid": asset.get("guid"), "mechanism": mechanism, **result,
            "advisory": True}
