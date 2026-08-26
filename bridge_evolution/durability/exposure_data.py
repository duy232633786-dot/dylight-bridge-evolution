"""Nạp dữ liệu phơi ĐO ĐẠC THẬT — con đường hoàn tất G6 (BRD-026).

Mô hình khấu hao mặc định dùng TRỊ SÀNG LỌC có dẫn nguồn. Khi dự án có đo
đạc hiện trường (trạm quan trắc, mẫu bột đo clorua/carbonat, sensor ẩm),
nạp qua ``load_exposure_data`` để GHI ĐÈ mặc định — khi đó kết quả tuổi thọ
mang ``data_provenance: "MEASURED"`` thay vì ``"SCREENING_DEFAULT"``.

File JSON đầu vào (mẫu trong exposure_template.json cùng thư mục):

{
  "source": "Trạm QNXX 2024 / mẫu bột cột P3",
  "measured": {
    "rh_percent": 78.0,            // tùy chọn
    "carbonation_k_mm_sqrt_year": 3.2,   // tùy chọn — k đo được
    "chloride": {                   // tùy chọn — cụm clorua
      "cs_percent": 2.1,
      "d_ref_m2s": 8.0e-12,
      "m": 0.38,
      "ccrit_percent": 0.5
    }
  }
}

Quy tắc fail-closed: khóa lạ bị TỪ CHỐI (không lặng lẽ bỏ qua) để dữ liệu
kém chất lượng không trôi vào mô hình dưới dạng giá trị "có vẻ hợp lệ".
"""
from __future__ import annotations

import json
from pathlib import Path

__all__ = ["ExposureDataError", "load_exposure_data", "apply_exposure_overrides"]

_ALLOWED_ROOT = {"source", "measured"}
_ALLOWED_MEASURED = {"rh_percent", "carbonation_k_mm_sqrt_year", "chloride"}
_ALLOWED_CHLORIDE = {"cs_percent", "d_ref_m2s", "m", "ccrit_percent"}


class ExposureDataError(ValueError):
    """Dữ liệu phơi không hợp lệ — từ chối thay vì đoán."""


def load_exposure_data(path: str | Path) -> dict:
    """Đọc + kiểm tra file dữ liệu phơi. Raise ExposureDataError nếu sai cấu trúc."""
    path = Path(path)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ExposureDataError(f"Không đọc được {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ExposureDataError("Root phải là object")
    unknown = set(raw) - _ALLOWED_ROOT
    if unknown:
        raise ExposureDataError(f"Khóa lạ ở root: {sorted(unknown)}")
    measured = raw.get("measured")
    if not isinstance(measured, dict) or not measured:
        raise ExposureDataError("Thiếu khối 'measured' hoặc rỗng")
    unknown = set(measured) - _ALLOWED_MEASURED
    if unknown:
        raise ExposureDataError(f"Khóa lạ trong measured: {sorted(unknown)}")

    rh = measured.get("rh_percent")
    if rh is not None and not (0 < float(rh) <= 100):
        raise ExposureDataError("rh_percent phải trong (0, 100]")

    chl = measured.get("chloride")
    if chl is not None:
        if not isinstance(chl, dict):
            raise ExposureDataError("chloride phải là object")
        unknown = set(chl) - _ALLOWED_CHLORIDE
        if unknown:
            raise ExposureDataError(f"Khóa lạ trong chloride: {sorted(unknown)}")
        if "cs_percent" in chl and float(chl["cs_percent"]) <= 0:
            raise ExposureDataError("cs_percent phải dương")
        if "d_ref_m2s" in chl and float(chl["d_ref_m2s"]) <= 0:
            raise ExposureDataError("d_ref_m2s phải dương")
        if "m" in chl and not (0 <= float(chl["m"]) <= 1.0):
            raise ExposureDataError("m phải trong [0, 1]")
        if "ccrit_percent" in chl and float(chl["ccrit_percent"]) <= 0:
            raise ExposureDataError("ccrit_percent phải dương")
    if "source" not in raw or not str(raw["source"]).strip():
        raise ExposureDataError("Thiếu 'source' — dữ liệu không provenance thì không nạp")
    return raw


def apply_exposure_overrides(kwargs: dict, measured: dict | None) -> dict:
    """Ghi đè kwargs mô hình bằng giá trị đo được (khóa khớp mới ghi đè).

    Trả (kwargs_mới, provenance) — provenance là "MEASURED" nếu có ít nhất
    một giá trị đo được áp vào, ngược lại "SCREENING_DEFAULT".
    """
    if not measured:
        return dict(kwargs), "SCREENING_DEFAULT"
    out = dict(kwargs)
    applied = False
    if "rh_percent" in measured:
        out["rh_percent"] = float(measured["rh_percent"])
        applied = True
    if "carbonation_k_mm_sqrt_year" in measured:
        out["measured_k"] = float(measured["carbonation_k_mm_sqrt_year"])
        applied = True
    chl = measured.get("chloride") or {}
    mapping = {"cs_percent": "cs_percent", "d_ref_m2s": "d_ref_m2s",
               "m": "m", "ccrit_percent": "ccrit_percent"}
    for src, dst in mapping.items():
        if src in chl:
            out[dst] = float(chl[src])
            applied = True
    return out, ("MEASURED" if applied else "SCREENING_DEFAULT")
