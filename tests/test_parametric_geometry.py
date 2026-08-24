"""Kiểm thử mô-đun hình học tham số và phân tích tiết diện (geometry_parametric.py)."""
import pytest
from bridge_evolution.geometry_parametric import (
    SuperTGeometryParams,
    build_super_t_polygons,
    compute_polygon_properties_exact,
    compute_super_t_section_properties,
)


def test_supert_geometry_params_valid():
    p = SuperTGeometryParams(depth_m=1.75, top_flange_width_m=2.06)
    assert p.validate() == []


def test_supert_geometry_params_invalid():
    # Chiều cao phi thực tế
    p_bad_depth = SuperTGeometryParams(depth_m=5.0)
    assert len(p_bad_depth.validate()) > 0

    # Cánh trên hẹp hơn đáy
    p_bad_width = SuperTGeometryParams(top_flange_width_m=0.5, bottom_width_m=0.8)
    assert len(p_bad_width.validate()) > 0


def test_build_polygons_and_exact_properties():
    params = SuperTGeometryParams(
        depth_m=1.75,
        top_flange_width_m=2.06,
        bottom_width_m=0.74,
        bottom_thickness_m=0.25,
        web_thickness_m=0.10,
    )
    outer, void = build_super_t_polygons(params)
    assert len(outer) >= 8
    assert len(void) == 4

    area, y_c, I_xx, I_yy = compute_polygon_properties_exact(outer, void)
    assert 0.5 < area < 1.5  # Diện tích mặt cắt dầm Super-T thông thường ~0.6 - 1.2 m2
    assert 0.4 < y_c < 1.3   # Trọng tâm nằm ở nửa dưới dầm
    assert I_xx > 0.1        # Mômen quán tính Ixx > 0.1 m4
    assert I_yy > 0.1        # Mômen quán tính Iyy > 0.1 m4


def test_compute_super_t_section_properties():
    res = compute_super_t_section_properties(depth_m=1.75)
    assert res.depth_m == 1.75
    assert res.top_flange_width_m == 2.06
    assert res.y_bottom_m > 0
    assert res.y_top_m > 0
    assert pytest.approx(res.y_bottom_m + res.y_top_m, rel=1e-5) == 1.75
    assert res.I_m4 > 0
    assert res.Z_bottom_m3 == pytest.approx(res.I_m4 / res.y_bottom_m)
    assert res.Z_top_m3 == pytest.approx(res.I_m4 / res.y_top_m)

    # Kiểm tra chuyển đổi sang catalog dict
    d = res.to_catalog_dict()
    assert "area_m2" in d
    assert "I_m4" in d
    assert "y_bottom_m" in d
    assert "web_width_total_m" in d


def test_sectionproperties_backend_runs_instead_of_silent_green_fallback():
    pytest.importorskip("shapely")
    pytest.importorskip("sectionproperties")
    compute_super_t_section_properties.cache_clear()

    green = compute_super_t_section_properties(depth_m=1.75)
    fem = compute_super_t_section_properties(
        depth_m=1.75, use_sectionproperties_fem=True)

    # Cùng đa giác nên A/I khớp, nhưng J Saint-Venant từ warping FEA
    # phải phân biệt rõ với công thức thành mỏng xấp xỉ.
    assert fem.area_m2 == pytest.approx(green.area_m2, rel=1e-9)
    assert fem.I_m4 == pytest.approx(green.I_m4, rel=1e-9)
    assert fem.J_m4 > 10.0 * green.J_m4
    assert fem.J_m4 == pytest.approx(0.36764, rel=0.02)


def test_sectionproperties_backend_error_is_not_silently_relabelled(monkeypatch):
    pytest.importorskip("shapely")
    sp_geom = pytest.importorskip("sectionproperties.pre.geometry")

    def fail_geometry(*_args, **_kwargs):
        raise RuntimeError("synthetic section FEA failure")

    monkeypatch.setattr(sp_geom, "Geometry", fail_geometry)
    compute_super_t_section_properties.cache_clear()
    with pytest.raises(RuntimeError, match="synthetic section FEA failure"):
        compute_super_t_section_properties(
            depth_m=1.751, use_sectionproperties_fem=True)
