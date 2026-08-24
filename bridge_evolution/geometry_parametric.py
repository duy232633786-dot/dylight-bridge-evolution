"""Hình học tham số và đặc trưng tiết diện cầu tùy biến.

Đường mặc định dùng tích phân Green thuần Python/NumPy. Khi người dùng
bật ``use_sectionproperties_fem``, Shapely và sectionproperties được nạp như
một backend FEA tiết diện 2D tùy chọn. Backend lỗi phải ném exception;
không được im lặng trả kết quả của đường Green như thể FEA đã chạy.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, List, Tuple

import numpy as np


@dataclass(frozen=True)
class SuperTGeometryParams:
    """Tham số hình học chi tiết của dầm Super-T (đơn vị: mét).

    Mô hình hóa chính xác hình học mặt cắt máng Super-T theo tiêu chuẩn TCVN / AASHTO:
    - depth_m (H): Chiều cao dầm tổng thể (thường 1.50 - 2.10 m)
    - top_flange_width_m (B_top): Bề rộng cánh trên (thường 1.80 - 2.30 m)
    - top_flange_thickness_m (t_top): Chiều dày cánh trên (thường 0.08 - 0.15 m)
    - bottom_width_m (B_bot): Bề rộng đáy dầm (thường 0.60 - 0.90 m)
    - bottom_thickness_m (t_bot): Chiều dày bản đáy (thường 0.20 - 0.35 m)
    - web_thickness_m (t_web): Chiều dày mỗi sườn dầm nghiêng (thường 0.09 - 0.15 m)
    - top_flange_taper_m (t_taper): Chiều cao đoạn vát chuyển tiếp từ cánh vào sườn
    """
    depth_m: float = 1.75
    top_flange_width_m: float = 2.06
    top_flange_thickness_m: float = 0.09
    bottom_width_m: float = 0.74
    bottom_thickness_m: float = 0.25
    web_thickness_m: float = 0.10
    top_flange_taper_m: float = 0.06

    def validate(self) -> list[str]:
        """Kiểm tra tính hợp lệ hình học L0 của tiết diện dầm."""
        errs = []
        if self.depth_m <= 0.5 or self.depth_m > 3.5:
            errs.append(f"depth_m={self.depth_m} nằm ngoài khoảng thực tế (0.5m - 3.5m)")
        if self.top_flange_width_m <= self.bottom_width_m:
            errs.append(f"top_flange_width_m ({self.top_flange_width_m}) phải lớn hơn bottom_width_m ({self.bottom_width_m})")
        if self.bottom_thickness_m + self.top_flange_thickness_m + self.top_flange_taper_m >= self.depth_m:
            errs.append("Tổng chiều dày cánh trên, đáy và đoạn vát vượt quá chiều cao dầm")
        if self.web_thickness_m * 2 >= self.bottom_width_m:
            errs.append("Tổng chiều dày 2 sườn dầm vượt quá bề rộng đáy dầm")
        return errs


@dataclass
class SectionPropertiesResult:
    """Kết quả đặc trưng hình học tiết diện mặt cắt dầm."""
    area_m2: float
    depth_m: float
    top_flange_width_m: float
    bottom_width_m: float
    web_width_total_m: float
    y_bottom_m: float
    y_top_m: float
    I_m4: float           # I_xx: Mômen quán tính uốn chính quanh trục trung hòa
    I_yy_m4: float        # I_yy: Mômen quán tính uốn phương ngang
    J_m4: float           # Hằng số xoắn Saint-Venant
    Z_bottom_m3: float    # Mômen kháng uốn thớ đáy W_bot = I / y_bottom
    Z_top_m3: float       # Mômen kháng uốn thớ đỉnh W_top = I / y_top
    polygon_outer: list[tuple[float, float]]  # Tọa độ đỉnh đa giác ngoài (x, y)
    polygon_void: list[tuple[float, float]] | None  # Tọa độ lỗ rỗng trong nếu có

    def to_catalog_dict(self) -> dict[str, Any]:
        """Chuyển đổi thành định dạng tương thích với girder_sections trong catalogs.json."""
        return {
            "depth_m": round(self.depth_m, 4),
            "area_m2": round(self.area_m2, 4),
            "I_m4": round(self.I_m4, 5),
            "y_bottom_m": round(self.y_bottom_m, 4),
            "top_flange_width_m": round(self.top_flange_width_m, 4),
            "web_width_total_m": round(self.web_width_total_m, 4),
            "I_yy_m4": round(self.I_yy_m4, 5),
            "J_m4": round(self.J_m4, 6),
        }


def build_super_t_polygons(params: SuperTGeometryParams) -> tuple[list[tuple[float, float]], list[tuple[float, float]]]:
    """Sinh tọa độ đa giác biên ngoài và biên trong (hốc rỗng) của tiết diện Super-T.

    Hệ tọa độ: Gốc (0, 0) tại điểm chính giữa đáy dầm.
    Trục X: ngang (đối xứng qua X=0).
    Trục Y: hướng lên trên (từ y=0 tại đáy tới y=H tại đỉnh cánh).
    """
    H = params.depth_m
    B_top = params.top_flange_width_m
    t_top = params.top_flange_thickness_m
    B_bot = params.bottom_width_m
    t_bot = params.bottom_thickness_m
    t_w = params.web_thickness_m
    t_taper = params.top_flange_taper_m

    half_top = B_top / 2.0
    half_bot = B_bot / 2.0

    # Đa giác biên ngoài (theo chiều kim đồng hồ)
    # Bắt đầu từ góc đáy trái (-half_bot, 0)
    outer = [
        (-half_bot, 0.0),
        (half_bot, 0.0),
        # Đáy dầm lên sườn ngoài dầm
        (half_bot + 0.05, t_bot * 0.4),
        (half_top - 0.25, H - t_top - t_taper),
        (half_top, H - t_top),
        (half_top, H),
        (-half_top, H),
        (-half_top, H - t_top),
        (-half_top + 0.25, H - t_top - t_taper),
        (-half_bot - 0.05, t_bot * 0.4),
    ]

    # Đa giác hốc trong (lỗ rỗng máng Super-T)
    # Hốc rỗng nằm bên trong, cách sườn dầm t_w, cách đáy t_bot, cách đỉnh hở/kín
    inner_half_bot = max(0.05, half_bot - t_w - 0.05)
    inner_half_top = max(0.10, half_top - 0.35 - t_w)
    y_inner_bot = t_bot
    y_inner_top = H - t_top - 0.02

    inner_void = [
        (-inner_half_bot, y_inner_bot),
        (inner_half_bot, y_inner_bot),
        (inner_half_top, y_inner_top),
        (-inner_half_top, y_inner_top),
    ]

    return outer, inner_void


def compute_polygon_properties_exact(
    outer_pts: list[tuple[float, float]],
    void_pts: list[tuple[float, float]] | None = None,
) -> tuple[float, float, float, float]:
    """Tính chính xác Diện tích A, Trọng tâm Y_c, Mômen quán tính I_xx, I_yy bằng Green's Theorem.

    Trả về: (Area, Y_centroid, I_xx_centroid, I_yy_centroid)
    """
    def _poly_props(pts: list[tuple[float, float]]) -> tuple[float, float, float, float]:
        n = len(pts)
        area = 0.0
        cy_num = 0.0
        I_x_origin = 0.0
        I_y_origin = 0.0

        for i in range(n):
            x0, y0 = pts[i]
            x1, y1 = pts[(i + 1) % n]
            cross = x0 * y1 - x1 * y0
            area += cross
            cy_num += (y0 + y1) * cross
            I_x_origin += (y0**2 + y0 * y1 + y1**2) * cross
            I_y_origin += (x0**2 + x0 * x1 + x1**2) * cross

        area = area * 0.5
        if abs(area) < 1e-9:
            return 0.0, 0.0, 0.0, 0.0
        cy = cy_num / (6.0 * area)
        I_x_origin = I_x_origin / 12.0
        I_y_origin = I_y_origin / 12.0
        return abs(area), cy, abs(I_x_origin), abs(I_y_origin)

    A_out, cy_out, Ix_out, Iy_out = _poly_props(outer_pts)

    if void_pts:
        A_void, cy_void, Ix_void, Iy_void = _poly_props(void_pts)
        A_net = A_out - A_void
        if A_net <= 1e-6:
            return A_out, cy_out, Ix_out - A_out * (cy_out**2), Iy_out
        cy_net = (A_out * cy_out - A_void * cy_void) / A_net
        Ix_net_origin = Ix_out - Ix_void
        Iy_net_origin = Iy_out - Iy_void
        Ix_centroid = Ix_net_origin - A_net * (cy_net**2)
        Iy_centroid = Iy_net_origin
        return A_net, cy_net, max(0.0, Ix_centroid), max(0.0, Iy_centroid)

    Ix_centroid = Ix_out - A_out * (cy_out**2)
    return A_out, cy_out, max(0.0, Ix_centroid), max(0.0, Iy_out)


@lru_cache(maxsize=1024)
def compute_super_t_section_properties(
    depth_m: float,
    top_flange_width_m: float = 2.06,
    top_flange_thickness_m: float = 0.09,
    bottom_width_m: float = 0.74,
    bottom_thickness_m: float = 0.25,
    web_thickness_m: float = 0.10,
    top_flange_taper_m: float = 0.06,
    use_sectionproperties_fem: bool = False,
) -> SectionPropertiesResult:
    """Tính toán toàn diện đặc trưng hình học của tiết diện Super-T tham số.

    Hàm được bọc bởi `@lru_cache` để tối ưu hóa hiệu năng tính toán.
    """
    params = SuperTGeometryParams(
        depth_m=depth_m,
        top_flange_width_m=top_flange_width_m,
        top_flange_thickness_m=top_flange_thickness_m,
        bottom_width_m=bottom_width_m,
        bottom_thickness_m=bottom_thickness_m,
        web_thickness_m=web_thickness_m,
        top_flange_taper_m=top_flange_taper_m,
    )

    errs = params.validate()
    if errs:
        raise ValueError(f"Thông số tiết diện Super-T không hợp lệ: {'; '.join(errs)}")

    outer_pts, void_pts = build_super_t_polygons(params)

    # 1. Tính toán giải tích hình học chính xác tuyệt đối
    A, y_bot, I_xx, I_yy = compute_polygon_properties_exact(outer_pts, void_pts)
    H = params.depth_m
    y_top = H - y_bot

    # Hằng số xoắn gần đúng cho tiết diện thành mỏng hở / hộp
    # J xấp xỉ theo tổng b * t^3 / 3 (cho dạng hở) hoặc Bredt-Batho (cho dạng kín)
    t_avg_web = 2 * params.web_thickness_m
    J_approx = (
        params.top_flange_width_m * (params.top_flange_thickness_m**3) / 3.0
        + params.bottom_width_m * (params.bottom_thickness_m**3) / 3.0
        + 2 * (H * (params.web_thickness_m**3) / 3.0)
    )

    # 2. Backend FEA tiết diện 2D tùy chọn. Import để trong nhánh này
    # để đường Green/core không phụ thuộc Shapely. Mọi lỗi import,
    # mesh hay API phải nổi lên (fail-closed); không fallback im lặng.
    if use_sectionproperties_fem:
        import sectionproperties.pre.geometry as sp_geom
        from sectionproperties.analysis.section import Section
        from shapely.geometry import Polygon

        poly_out = Polygon(outer_pts)
        if void_pts:
            poly_void = Polygon(void_pts)
            diff = poly_out.difference(poly_void)
            geom = sp_geom.Geometry(diff)
        else:
            geom = sp_geom.Geometry(poly_out)

        geom.create_mesh(mesh_sizes=[0.02])
        sec = Section(geom)
        sec.calculate_geometric_properties()
        sec.calculate_warping_properties()

        A = float(sec.get_area())
        _, cy = sec.get_c()
        y_bot = float(cy)
        y_top = H - y_bot
        I_xx = float(sec.get_ic()[0])
        I_yy = float(sec.get_ic()[1])
        J_approx = float(sec.get_j())

    Z_bot = I_xx / y_bot if y_bot > 0 else 0.0
    Z_top = I_xx / y_top if y_top > 0 else 0.0

    return SectionPropertiesResult(
        area_m2=A,
        depth_m=H,
        top_flange_width_m=params.top_flange_width_m,
        bottom_width_m=params.bottom_width_m,
        web_width_total_m=t_avg_web,
        y_bottom_m=y_bot,
        y_top_m=y_top,
        I_m4=I_xx,
        I_yy_m4=I_yy,
        J_m4=J_approx,
        Z_bottom_m3=Z_bot,
        Z_top_m3=Z_top,
        polygon_outer=outer_pts,
        polygon_void=void_pts,
    )
