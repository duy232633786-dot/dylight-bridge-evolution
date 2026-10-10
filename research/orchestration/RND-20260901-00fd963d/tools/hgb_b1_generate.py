from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SEED_PATH = ROOT / "b1_1440_geometry_seed.json"


def load_seed(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def f(value: float) -> float:
    return round(float(value), 6)


def parabolic_cable_z(x: float, x0: float, x1: float, saddle_z: float, sag: float) -> float:
    u = (x - x0) / (x1 - x0)
    return saddle_z - 4.0 * sag * u * (1.0 - u)


def parabolic_arch_z(x: float, x0: float, x1: float, spring_z: float, crown_z: float) -> float:
    u = (x - x0) / (x1 - x0)
    rise = crown_z - spring_z
    return spring_z + 4.0 * rise * u * (1.0 - u)


def hermite_z(u: float, z0: float, z1: float, m0: float, m1: float) -> float:
    h00 = 2.0 * u**3 - 3.0 * u**2 + 1.0
    h10 = u**3 - 2.0 * u**2 + u
    h01 = -2.0 * u**3 + 3.0 * u**2
    h11 = u**3 - u**2
    return h00 * z0 + h10 * m0 + h01 * z1 + h11 * m1


def stations_from_spans(seed: dict[str, Any]) -> list[float]:
    render = seed["render_seed"]
    counts = [render["approach_panel_count"], render["side_panel_count"], 26,
              render["side_panel_count"], render["approach_panel_count"]]
    stations: list[float] = []
    for span, count in zip(seed["span_chain"], counts, strict=True):
        x0 = float(span["x0_m"])
        x1 = float(span["x1_m"])
        for i in range(int(count)):
            stations.append(f(x0 + (x1 - x0) * i / count))
    stations.append(f(seed["span_chain"][-1]["x1_m"]))
    return sorted(set(stations))


def build_geometry(seed: dict[str, Any]) -> dict[str, Any]:
    r = seed["render_seed"]
    x_ab_l, x_catb_l, x_tn_l = 0.0, 145.0, 395.0
    x_tn_r, x_catb_r, x_ab_r = 1045.0, 1295.0, 1440.0
    deck_z = float(r["deck_z_local_m"])
    saddle_z = float(r["tower_saddle_z_local_m"])
    foot_z = float(r["tower_foot_z_local_m"])
    panel = float(r["main_cable_panel_m"])
    nodes: list[dict[str, Any]] = []
    members: list[dict[str, Any]] = []

    def add_node(node_id: str, family: str, x: float, y: float, z: float,
                 provenance: str = "DERIVED_FROM_CANONICAL_SEED") -> None:
        nodes.append({"id": node_id, "family": family, "x_m": f(x), "y_m": f(y),
                      "z_local_m": f(z), "provenance": provenance})

    def add_member(member_id: str, family: str, start: str, end: str,
                   role: str) -> None:
        members.append({"id": member_id, "family": family, "start": start,
                        "end": end, "role": role})

    # Deck: nodes are generated span-by-span so the complete 1,440 m chain closes exactly.
    deck_stations = stations_from_spans(seed)
    for i, x in enumerate(deck_stations):
        add_node(f"B.DK.{i:03d}", "DK", x, 0.0, deck_z)
        if i:
            add_member(f"B.DK.M.{i:03d}", "DK", f"B.DK.{i-1:03d}", f"B.DK.{i:03d}",
                       "continuous aerodynamic steel-box deck line")

    deck_by_x = {f(float(n["x_m"])): n["id"] for n in nodes if n["family"] == "DK"}

    # Support and tower landmarks. Vertical values are presentation seeds only.
    support_data = [
        ("B.AB.L", "AB", x_ab_l, foot_z),
        ("B.CATB.L", "CATB", x_catb_l, float(r["side_arch_catb_z_local_m"])),
        ("B.TN.L", "TN", x_tn_l, foot_z),
        ("B.TN.R", "TN", x_tn_r, foot_z),
        ("B.CATB.R", "CATB", x_catb_r, float(r["side_arch_catb_z_local_m"])),
        ("B.AB.R", "AB", x_ab_r, foot_z),
    ]
    for node_id, family, x, z in support_data:
        add_node(node_id, family, x, 0.0, z)
        ground_id = node_id.replace("B.", "B.GND.", 1)
        add_node(ground_id, "GND", x, 0.0, foot_z - 15.0)
        add_member(f"B.FND.{node_id.split('.')[-1]}.{family}", "FND", node_id, ground_id,
                   "explicit support-to-ground topology; foundation not sized")
    for side, x in (("L", x_tn_l), ("R", x_tn_r)):
        add_node(f"B.SAD.{side}", "SAD", x, 0.0, saddle_z)
        add_member(f"B.PY.{side}", "PY", f"B.TN.{side}", f"B.SAD.{side}",
                   "tower compression/flexure path; not solver-sized")

    # Main cable and straight backstays. MS law is parabolic geometry, not equilibrium catenary.
    ms_x = [f(x_tn_l + i * panel) for i in range(int((x_tn_r - x_tn_l) / panel) + 1)]
    for i, x in enumerate(ms_x):
        z = parabolic_cable_z(x, x_tn_l, x_tn_r, saddle_z, float(r["main_cable_sag_m"]))
        add_node(f"B.MS.{i:03d}", "MS", x, 0.0, z)
        if i:
            add_member(f"B.MS.M.{i:03d}", "MS", f"B.MS.{i-1:03d}", f"B.MS.{i:03d}",
                       "main suspension cable geometry")
    add_member("B.MS.JOINT.L", "MS", "B.SAD.L", "B.MS.000",
               "main-cable continuity through left saddle")
    add_member("B.MS.JOINT.R", "MS", f"B.MS.{len(ms_x)-1:03d}", "B.SAD.R",
               "main-cable continuity through right saddle")

    for side, xa, xs in (("L", x_catb_l, x_tn_l), ("R", x_catb_r, x_tn_r)):
        direction = 1.0 if side == "L" else -1.0
        count = int(abs(xs - xa) / panel)
        previous = f"B.CATB.{side}"
        for i in range(1, count):
            x = xa + direction * panel * i
            u = abs(x - xa) / abs(xs - xa)
            z = float(r["side_arch_catb_z_local_m"]) + u * (saddle_z - float(r["side_arch_catb_z_local_m"]))
            node_id = f"B.BS.{side}.{i:02d}"
            add_node(node_id, "BS", x, 0.0, z)
            add_member(f"B.BS.M.{side}.{i:02d}", "BS", previous, node_id,
                       "continuous ground-anchored backstay segment")
            previous = node_id
        add_member(f"B.BS.M.{side}.END", "BS", previous, f"B.SAD.{side}",
                   "continuous ground-anchored backstay segment")

    # Hangers: vertical interfaces from each internal main-cable node to the deck.
    for i, x in enumerate(ms_x[1:-1], start=1):
        deck_id = deck_by_x[f(x)]
        add_member(f"B.HG.{i:03d}", "HG", f"B.MS.{i:03d}", deck_id,
                   "vertical hanger; force unknown until solver")

    # Landward-only stay fans. No stay deck anchor is allowed inside the two saddles.
    n_stays = int(r["stay_count_per_side"])
    first = float(r["stay_anchor_first_offset_m"])
    spacing = float(r["stay_anchor_spacing_m"])
    for side, catb, sad, sign in (("L", x_catb_l, x_tn_l, 1.0), ("R", x_catb_r, x_tn_r, -1.0)):
        anchor_xs = [f(catb + sign * (first + j * spacing)) for j in range(n_stays)]
        for j, x in enumerate(anchor_xs, start=1):
            deck_id = deck_by_x[f(x)]
            add_member(f"B.ST.{side}.{j:02d}", "ST", f"B.SAD.{side}", deck_id,
                       "landward-only stay; separate from main cable")

    # Central B1 arch and vertical spandrels. psi_a is deliberately not assigned.
    arch_crown = float(r["central_arch_crown_z_local_m"])
    for i, x in enumerate(ms_x):
        z = parabolic_arch_z(x, x_tn_l, x_tn_r, foot_z, arch_crown)
        add_node(f"B.AC.{i:03d}", "AC", x, 0.0, z)
        if i:
            add_member(f"B.AC.M.{i:03d}", "AC", f"B.AC.{i-1:03d}", f"B.AC.{i:03d}",
                       "single continuous CFST-UHPC concept rib")
        if 0 < i < len(ms_x) - 1:
            add_member(f"B.SP.AC.{i:03d}", "SP-AC", f"B.AC.{i:03d}", deck_by_x[f(x)],
                       "B1 vertical interface; force share is solver-locked")
    add_member("B.AC.JOINT.L", "AC", "B.TN.L", "B.AC.000",
               "central-arch closure at left tower foot")
    add_member("B.AC.JOINT.R", "AC", f"B.AC.{len(ms_x)-1:03d}", "B.TN.R",
               "central-arch closure at right tower foot")

    # Side half-arches use an explicit cubic-Hermite render law and close at CATB/TN.
    side_count = int(r["side_panel_count"])
    z_catb = float(r["side_arch_catb_z_local_m"])
    m_catb = float(r["side_arch_tangent_dz_du_catb_m"])
    m_tower = float(r["side_arch_tangent_dz_du_tower_m"])
    for side, xa, xt, sign in (("L", x_catb_l, x_tn_l, 1.0), ("R", x_catb_r, x_tn_r, -1.0)):
        previous = f"B.CATB.{side}"
        for i in range(1, side_count):
            u = i / side_count
            x = xa + sign * abs(xt - xa) * u
            z = hermite_z(u, z_catb, foot_z, m_catb, m_tower)
            node_id = f"B.AH.{side}.{i:02d}"
            add_node(node_id, "AH", x, 0.0, z)
            add_member(f"B.AH.M.{side}.{i:02d}", "AH", previous, node_id,
                       "side half-arch concept rib")
            add_member(f"B.SP.AH.{side}.{i:02d}", "SP-AH", node_id, deck_by_x[f(x)],
                       "side-span spandrel; force unknown until solver")
            previous = node_id
        add_member(f"B.AH.M.{side}.END", "AH", previous, f"B.TN.{side}",
                   "side half-arch endpoint closure")

    # Support paths are explicit graph edges, not inferred from the drawing.
    for side, ab_x, catb_x in (("L", x_ab_l, x_catb_l), ("R", x_ab_r, x_catb_r)):
        ab_deck = deck_by_x[f(ab_x)]
        catb_deck = deck_by_x[f(catb_x)]
        add_member(f"B.BRG.AB.{side}", "BRG", ab_deck, f"B.AB.{side}", "deck-to-abutment support path")
        add_member(f"B.BRG.CATB.{side}", "BRG", catb_deck, f"B.CATB.{side}", "deck-to-transition-support path")
    for side, x in (("L", x_tn_l), ("R", x_tn_r)):
        add_member(f"B.BRG.TN.{side}", "BRG", deck_by_x[f(x)], f"B.TN.{side}",
                   "deck-to-tower-foot support/interface path")

    nodes = sorted(nodes, key=lambda item: item["id"])
    members = sorted(members, key=lambda item: item["id"])
    return {
        "schema_version": "1.0",
        "concept_id": seed["concept_id"],
        "fidelity": "F0",
        "claim_level": "IDEA",
        "coordinate_notice": seed["coordinate_system"],
        "nodes": nodes,
        "members": members,
        "solver_locked_unknowns": seed["solver_locked_unknowns"],
        "forbidden_claims": seed["forbidden_claims"]
    }


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_csv(path: Path, geometry: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["id", "family", "x_m", "y_m", "z_local_m", "provenance"])
        writer.writeheader()
        writer.writerows(geometry["nodes"])


def svg_elevation(seed: dict[str, Any], geometry: dict[str, Any]) -> str:
    width, height = 1600, 760
    left, right, top, bottom = 80, 1520, 90, 620
    x_scale = (right - left) / 1440.0
    z_min, z_max = -70.0, 175.0
    z_scale = (bottom - top) / (z_max - z_min)

    def sx(x: float) -> float:
        return left + x * x_scale

    def sy(z: float) -> float:
        return bottom - (z - z_min) * z_scale

    nodes = {node["id"]: node for node in geometry["nodes"]}
    family_nodes: dict[str, list[dict[str, Any]]] = {}
    for node in geometry["nodes"]:
        family_nodes.setdefault(node["family"], []).append(node)
    for values in family_nodes.values():
        values.sort(key=lambda n: n["x_m"])

    def polyline(family: str, css: str) -> str:
        pts = " ".join(f"{sx(n['x_m']):.1f},{sy(n['z_local_m']):.1f}" for n in family_nodes.get(family, []))
        return f'<polyline class="{css}" points="{pts}" />' if pts else ""

    parts = [f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
<style>
  .bg{{fill:#f7f8fb}} .ink{{stroke:#183153;fill:none;stroke-width:3}} .deck{{stroke:#1d2939;fill:none;stroke-width:8}}
  .cable{{stroke:#315efb;fill:none;stroke-width:3}} .stay{{stroke:#5477d8;fill:none;stroke-width:1.8}}
  .hanger{{stroke:#ef4444;fill:none;stroke-width:1.4}} .arch{{stroke:#b45309;fill:none;stroke-width:10;stroke-linecap:round}}
  .spandrel{{stroke:#8b5e34;fill:none;stroke-width:1.5}} .support{{stroke:#475467;fill:#d0d5dd;stroke-width:2}}
  .dim{{stroke:#667085;fill:none;stroke-width:1.2}} .tick{{stroke:#667085;stroke-width:1.2}}
  .t1{{font:700 26px 'Segoe UI',sans-serif;fill:#102a56}} .t2{{font:600 16px 'Segoe UI',sans-serif;fill:#344054}}
  .txt{{font:14px 'Segoe UI',sans-serif;fill:#344054}} .small{{font:12px 'Segoe UI',sans-serif;fill:#475467}}
  .warn{{fill:#b42318;font:700 14px 'Segoe UI',sans-serif}} .seed{{fill:#fff7ed;stroke:#f79009;stroke-dasharray:7 5}}
</style><rect class="bg" width="100%" height="100%"/>
<text x="80" y="42" class="t1">HGB-B1 — SƠ ĐỒ HÌNH HỌC CONCEPT 1.440 m</text>
<text x="80" y="68" class="t2">145 + 250 + 650 + 250 + 145 m · F0/IDEA · cao độ đứng chỉ là seed trình bày</text>
<rect x="{sx(595):.1f}" y="{sy(-5):.1f}" width="{250*x_scale:.1f}" height="{sy(-62)-sy(-5):.1f}" class="seed"/>
<text x="{sx(720):.1f}" y="{sy(-64):.1f}" text-anchor="middle" class="warn">KHỔ THÔNG THUYỀN: BLOCKED — thiếu datum và envelope duyệt</text>
''']

    # Deck, towers, cables and arches.
    deck_points = " ".join(f"{sx(n['x_m']):.1f},{sy(n['z_local_m']):.1f}" for n in family_nodes["DK"])
    parts.append(f'<polyline class="deck" points="{deck_points}"/>')
    for side in ("L", "R"):
        tn, sad = nodes[f"B.TN.{side}"], nodes[f"B.SAD.{side}"]
        x = sx(tn["x_m"])
        parts.append(f'<path class="support" d="M {x-11:.1f},{sy(tn["z_local_m"]):.1f} L {x-7:.1f},{sy(sad["z_local_m"]):.1f} L {x+7:.1f},{sy(sad["z_local_m"]):.1f} L {x+11:.1f},{sy(tn["z_local_m"]):.1f} Z"/>')

    # Backstay paths assembled side by side, then main cable.
    for side in ("L", "R"):
        ids = [f"B.CATB.{side}"] + [n["id"] for n in sorted(family_nodes.get("BS", []), key=lambda n: n["x_m"]) if f".{side}." in n["id"]] + [f"B.SAD.{side}"]
        ids = sorted(ids, key=lambda node_id: nodes[node_id]["x_m"])
        pts = " ".join(f"{sx(nodes[i]['x_m']):.1f},{sy(nodes[i]['z_local_m']):.1f}" for i in ids)
        parts.append(f'<polyline class="cable" points="{pts}"/>')
    parts.append(polyline("MS", "cable"))
    parts.append(polyline("AC", "arch"))
    for side in ("L", "R"):
        ids = [f"B.CATB.{side}"] + [n["id"] for n in family_nodes.get("AH", []) if f".{side}." in n["id"]] + [f"B.TN.{side}"]
        ids = sorted(ids, key=lambda node_id: nodes[node_id]["x_m"])
        pts = " ".join(f"{sx(nodes[i]['x_m']):.1f},{sy(nodes[i]['z_local_m']):.1f}" for i in ids)
        parts.append(f'<polyline class="arch" points="{pts}"/>')

    # Interface members are drawn directly from the canonical graph.
    member_css = {"HG": "hanger", "ST": "stay", "SP-AC": "spandrel", "SP-AH": "spandrel"}
    for member in geometry["members"]:
        if member["family"] not in member_css:
            continue
        a, b = nodes[member["start"]], nodes[member["end"]]
        parts.append(f'<line class="{member_css[member["family"]]}" x1="{sx(a["x_m"]):.1f}" y1="{sy(a["z_local_m"]):.1f}" x2="{sx(b["x_m"]):.1f}" y2="{sy(b["z_local_m"]):.1f}"/>')

    # Supports and station labels.
    for x, label in ((0,"MỐ L"),(145,"CATB/PIER L"),(395,"THÁP L"),(1045,"THÁP R"),(1295,"CATB/PIER R"),(1440,"MỐ R")):
        parts.append(f'<line class="support" x1="{sx(x):.1f}" y1="{sy(0):.1f}" x2="{sx(x):.1f}" y2="{sy(-62):.1f}"/>')
        parts.append(f'<text x="{sx(x):.1f}" y="{sy(-68):.1f}" text-anchor="middle" class="small">{label}</text>')

    dim_y = 690
    spans = [(0,145,"145 m"),(145,395,"250 m"),(395,1045,"650 m"),(1045,1295,"250 m"),(1295,1440,"145 m")]
    for x0, x1, label in spans:
        parts.append(f'<line class="dim" x1="{sx(x0):.1f}" y1="{dim_y}" x2="{sx(x1):.1f}" y2="{dim_y}"/>')
        parts.append(f'<line class="tick" x1="{sx(x0):.1f}" y1="{dim_y-7}" x2="{sx(x0):.1f}" y2="{dim_y+7}"/>')
        parts.append(f'<line class="tick" x1="{sx(x1):.1f}" y1="{dim_y-7}" x2="{sx(x1):.1f}" y2="{dim_y+7}"/>')
        parts.append(f'<text x="{(sx(x0)+sx(x1))/2:.1f}" y="{dim_y-10}" text-anchor="middle" class="txt">{label}</text>')
    parts.append('<text x="800" y="735" text-anchor="middle" class="warn">KHÔNG DÙNG ĐỂ THI CÔNG · ψₐ CHƯA TÍNH · G0=FAIL KẾ THỪA</text></svg>')
    return "".join(parts)


def svg_cross_section(seed: dict[str, Any]) -> str:
    r = seed["render_seed"]
    width, height = 1100, 650
    cx, deck_y = 550, 220
    scale = 24.0
    half_w = float(r["deck_width_m"]) / 2.0 * scale
    box_top = float(r["steel_box_top_width_m"]) / 2.0 * scale
    box_bottom = float(r["steel_box_bottom_width_m"]) / 2.0 * scale
    depth = float(r["steel_box_depth_m"]) * scale
    cable = float(r["cable_plane_half_spacing_m"]) * scale
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
<style>
 .bg{{fill:#f7f8fb}} .steel{{fill:#d0d5dd;stroke:#1d2939;stroke-width:4}} .uhpc{{fill:#e4e7ec;stroke:#344054;stroke-width:3}}
 .rib{{stroke:#344054;stroke-width:9}} .cable{{stroke:#315efb;stroke-width:8}} .cfrp{{stroke:#12b76a;stroke-width:10;stroke-dasharray:14 8}}
 .dim{{stroke:#667085;stroke-width:1.5;fill:none}} .t1{{font:700 26px 'Segoe UI',sans-serif;fill:#102a56}}
 .t2{{font:600 16px 'Segoe UI',sans-serif;fill:#344054}} .txt{{font:14px 'Segoe UI',sans-serif;fill:#344054}}
 .small{{font:12px 'Segoe UI',sans-serif;fill:#475467}} .warn{{font:700 13px 'Segoe UI',sans-serif;fill:#b42318}}
</style><rect class="bg" width="100%" height="100%"/>
<text x="55" y="45" class="t1">MẶT CẮT NGANG CONCEPT B1</text>
<text x="55" y="72" class="t2">B = 32 m là seed hình ảnh; hộp thép khí động + cassette UHPC + sườn xiên thép</text>
<rect class="uhpc" x="{cx-half_w:.1f}" y="{deck_y-12:.1f}" width="{2*half_w:.1f}" height="24" rx="5"/>
<path class="steel" d="M {cx-box_top:.1f},{deck_y+12:.1f} L {cx+box_top:.1f},{deck_y+12:.1f} L {cx+box_bottom:.1f},{deck_y+depth:.1f} L {cx-box_bottom:.1f},{deck_y+depth:.1f} Z"/>
<line class="rib" x1="{cx-box_bottom:.1f}" y1="{deck_y+depth:.1f}" x2="{cx-half_w+18:.1f}" y2="{deck_y+12:.1f}"/>
<line class="rib" x1="{cx+box_bottom:.1f}" y1="{deck_y+depth:.1f}" x2="{cx+half_w-18:.1f}" y2="{deck_y+12:.1f}"/>
<line class="cable" x1="{cx-cable:.1f}" y1="{deck_y-85:.1f}" x2="{cx-cable:.1f}" y2="{deck_y-12:.1f}"/>
<line class="cable" x1="{cx+cable:.1f}" y1="{deck_y-85:.1f}" x2="{cx+cable:.1f}" y2="{deck_y-12:.1f}"/>
<line class="cfrp" x1="{cx-box_bottom+18:.1f}" y1="{deck_y+depth-13:.1f}" x2="{cx+box_bottom-18:.1f}" y2="{deck_y+depth-13:.1f}"/>
<line class="dim" x1="{cx-half_w:.1f}" y1="500" x2="{cx+half_w:.1f}" y2="500"/>
<line class="dim" x1="{cx-half_w:.1f}" y1="490" x2="{cx-half_w:.1f}" y2="510"/><line class="dim" x1="{cx+half_w:.1f}" y1="490" x2="{cx+half_w:.1f}" y2="510"/>
<text x="{cx}" y="490" text-anchor="middle" class="txt">32,0 m — CONCEPT_IMAGE / chưa khóa G0</text>
<text x="{cx}" y="{deck_y+70:.1f}" text-anchor="middle" class="txt">Hộp thép kín khí động</text>
<text x="{cx}" y="{deck_y+depth+38:.1f}" text-anchor="middle" class="txt">Dải CFRP bảo vệ cháy: gia cường mỏi cục bộ, không phải cấu kiện nén chính</text>
<text x="85" y="{deck_y+105:.1f}" class="txt">Sườn xiên thép vĩnh cửu</text><text x="830" y="{deck_y+105:.1f}" class="txt">Sườn xiên thép vĩnh cửu</text>
<text x="{cx-cable:.1f}" y="115" text-anchor="middle" class="small">mặt phẳng cáp L</text><text x="{cx+cable:.1f}" y="115" text-anchor="middle" class="small">mặt phẳng cáp R</text>
<text x="550" y="590" text-anchor="middle" class="warn">KÍCH THƯỚC MẶT CẮT CHỈ ĐỂ NGHIÊN CỨU HÌNH THÁI · CHƯA KIỂM TRA GIÓ/MỎI/CHÁY</text>
</svg>'''


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate deterministic F0 geometry for HGB-B1 1440 m.")
    parser.add_argument("--seed", type=Path, default=SEED_PATH)
    parser.add_argument("--output-dir", type=Path, default=ROOT)
    args = parser.parse_args()
    seed = load_seed(args.seed.resolve())
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    geometry = build_geometry(seed)
    write_json(output_dir / "b1_1440_geometry.json", geometry)
    write_csv(output_dir / "b1_1440_nodes.csv", geometry)
    (output_dir / "b1_1440_elevation.svg").write_text(svg_elevation(seed, geometry), encoding="utf-8")
    (output_dir / "b1_1440_cross_section.svg").write_text(svg_cross_section(seed), encoding="utf-8")
    digest = hashlib.sha256((output_dir / "b1_1440_geometry.json").read_bytes()).hexdigest()
    print(json.dumps({"status": "GENERATED_F0_IDEA", "nodes": len(geometry["nodes"]),
                      "members": len(geometry["members"]), "geometry_sha256": digest}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
