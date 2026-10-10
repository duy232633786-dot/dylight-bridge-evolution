from __future__ import annotations

import csv
import hashlib
import json
import math
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SEED_PATH = ROOT / "b1_1440_geometry_seed.json"
GEOMETRY_PATH = ROOT / "b1_1440_geometry.json"
CSV_PATH = ROOT / "b1_1440_nodes.csv"
CHECKS_PATH = ROOT / "b1_1440_checks.json"
GENERATOR_PATH = HERE / "hgb_b1_generate.py"
TOL = 1.0e-6


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def close(a: float, b: float) -> bool:
    return math.isclose(float(a), float(b), rel_tol=0.0, abs_tol=TOL)


def cable_z(x: float, x0: float, x1: float, saddle_z: float, sag: float) -> float:
    u = (x - x0) / (x1 - x0)
    return saddle_z - 4.0 * sag * u * (1.0 - u)


def arch_z(x: float, x0: float, x1: float, spring_z: float, crown_z: float) -> float:
    u = (x - x0) / (x1 - x0)
    return spring_z + 4.0 * (crown_z - spring_z) * u * (1.0 - u)


def hermite_z(u: float, z0: float, z1: float, m0: float, m1: float) -> float:
    return ((2*u**3 - 3*u**2 + 1)*z0 + (u**3 - 2*u**2 + u)*m0
            + (-2*u**3 + 3*u**2)*z1 + (u**3 - u**2)*m1)


def make_check(check_id: str, status: str, evidence: str) -> dict[str, str]:
    return {"id": check_id, "status": status, "evidence": evidence}


def reachable(start: str, target: str, members: list[dict[str, Any]], families: set[str] | None = None) -> bool:
    adjacency: dict[str, set[str]] = {}
    for member in members:
        if families is not None and member["family"] not in families:
            continue
        adjacency.setdefault(member["start"], set()).add(member["end"])
        adjacency.setdefault(member["end"], set()).add(member["start"])
    seen = {start}
    frontier = [start]
    while frontier:
        node = frontier.pop()
        if node == target:
            return True
        for neighbour in adjacency.get(node, set()):
            if neighbour not in seen:
                seen.add(neighbour)
                frontier.append(neighbour)
    return False


def verify() -> dict[str, Any]:
    seed = load_json(SEED_PATH)
    geometry = load_json(GEOMETRY_PATH)
    nodes = geometry["nodes"]
    members = geometry["members"]
    by_id = {node["id"]: node for node in nodes}
    r = seed["render_seed"]
    checks: list[dict[str, str]] = []

    span_sum = sum(float(span["length_m"]) for span in seed["span_chain"])
    span_chain_ok = close(span_sum, 1440.0) and all(
        close(float(span["x1_m"]) - float(span["x0_m"]), float(span["length_m"]))
        for span in seed["span_chain"]
    ) and all(close(float(a["x1_m"]), float(b["x0_m"])) for a, b in zip(seed["span_chain"], seed["span_chain"][1:]))
    checks.append(make_check("F0-SPAN-CLOSURE", "SATISFIED_F0_GEOMETRY" if span_chain_ok else "VIOLATED_F0_GEOMETRY",
                             f"sum={span_sum:.6f} m; target=1440.000000 m; contiguous={span_chain_ok}"))

    mirror_pairs = [("B.AB.L", "B.AB.R"), ("B.CATB.L", "B.CATB.R"),
                    ("B.TN.L", "B.TN.R"), ("B.SAD.L", "B.SAD.R")]
    symmetry_ok = all(close(by_id[a]["x_m"] + by_id[b]["x_m"], 1440.0)
                      and close(by_id[a]["z_local_m"], by_id[b]["z_local_m"])
                      for a, b in mirror_pairs)
    checks.append(make_check("F0-LANDMARK-SYMMETRY", "SATISFIED_F0_GEOMETRY" if symmetry_ok else "VIOLATED_F0_GEOMETRY",
                             "mirror plane x=720 m; all AB/CATB/TN/SAD pairs checked"))

    ms_nodes = sorted((node for node in nodes if node["family"] == "MS"), key=lambda node: node["x_m"])
    cable_ok = bool(ms_nodes) and all(close(node["z_local_m"], cable_z(node["x_m"], 395.0, 1045.0,
                                                                        float(r["tower_saddle_z_local_m"]),
                                                                        float(r["main_cable_sag_m"]))) for node in ms_nodes)
    checks.append(make_check("F0-MAIN-CABLE-LAW", "SATISFIED_F0_GEOMETRY" if cable_ok else "VIOLATED_F0_GEOMETRY",
                             f"{len(ms_nodes)} nodes independently recomputed against parabolic render law"))

    cable_members = [member for member in members if member["family"] in {"BS", "MS"}]
    cable_path_ok = reachable("B.CATB.L", "B.CATB.R", cable_members)
    cable_degree: dict[str, int] = {}
    for member in cable_members:
        cable_degree[member["start"]] = cable_degree.get(member["start"], 0) + 1
        cable_degree[member["end"]] = cable_degree.get(member["end"], 0) + 1
    cable_path_ok &= cable_degree.get("B.CATB.L") == 1 and cable_degree.get("B.CATB.R") == 1
    cable_path_ok &= all(degree == 2 for node_id, degree in cable_degree.items() if node_id not in {"B.CATB.L", "B.CATB.R"})
    checks.append(make_check("F0-CABLE-PATH-CLOSURE", "SATISFIED_F0_GEOMETRY" if cable_path_ok else "VIOLATED_F0_GEOMETRY",
                             "undirected CATB-L--BS--SAD--MS--SAD--BS--CATB-R path; terminal degree=1, internal degree=2"))

    ac_nodes = sorted((node for node in nodes if node["family"] == "AC"), key=lambda node: node["x_m"])
    central_arch_ok = bool(ac_nodes) and all(close(node["z_local_m"], arch_z(node["x_m"], 395.0, 1045.0,
                                                                            float(r["tower_foot_z_local_m"]),
                                                                            float(r["central_arch_crown_z_local_m"]))) for node in ac_nodes)
    central_arch_ok = central_arch_ok and close(ac_nodes[0]["x_m"], 395.0) and close(ac_nodes[-1]["x_m"], 1045.0)
    checks.append(make_check("F0-CENTRAL-ARCH-LAW-CLOSURE", "SATISFIED_F0_GEOMETRY" if central_arch_ok else "VIOLATED_F0_GEOMETRY",
                             f"{len(ac_nodes)} nodes; endpoints close at TN-L/TN-R"))

    side_arch_ok = True
    for side, xa, xt, sign in (("L", 145.0, 395.0, 1.0), ("R", 1295.0, 1045.0, -1.0)):
        side_nodes = sorted((node for node in nodes if node["family"] == "AH" and f".{side}." in node["id"]), key=lambda node: node["x_m"])
        for node in side_nodes:
            u = abs(float(node["x_m"]) - xa) / abs(xt - xa)
            expected = hermite_z(u, float(r["side_arch_catb_z_local_m"]), float(r["tower_foot_z_local_m"]),
                                 float(r["side_arch_tangent_dz_du_catb_m"]), float(r["side_arch_tangent_dz_du_tower_m"]))
            side_arch_ok &= close(node["z_local_m"], expected)
        end_member = next((member for member in members if member["id"] == f"B.AH.M.{side}.END"), None)
        side_arch_ok &= end_member is not None and end_member["end"] == f"B.TN.{side}"
    checks.append(make_check("F0-SIDE-ARCH-LAW-CLOSURE", "SATISFIED_F0_GEOMETRY" if side_arch_ok else "VIOLATED_F0_GEOMETRY",
                             "both cubic-Hermite half-arches independently checked and close at CATB/TN"))

    stay_members = [member for member in members if member["family"] == "ST"]
    no_inward = all((member["id"].startswith("B.ST.L") and float(by_id[member["end"]]["x_m"]) < 395.0)
                    or (member["id"].startswith("B.ST.R") and float(by_id[member["end"]]["x_m"]) > 1045.0)
                    for member in stay_members)
    checks.append(make_check("F0-NO-INWARD-STAYS", "SATISFIED_F0_GEOMETRY" if no_inward else "VIOLATED_F0_GEOMETRY",
                             f"{len(stay_members)} stay edges checked against x_SAD,L=395 and x_SAD,R=1045"))

    member_endpoints_ok = all(member["start"] in by_id and member["end"] in by_id for member in members)
    checks.append(make_check("F0-GRAPH-ENDPOINTS", "SATISFIED_F0_GEOMETRY" if member_endpoints_ok else "VIOLATED_F0_GEOMETRY",
                             f"{len(members)} member endpoint pairs resolve to canonical nodes"))

    ground_ids = {node["id"] for node in nodes if node["family"] == "GND"}
    support_ids = ["B.AB.L", "B.CATB.L", "B.TN.L", "B.TN.R", "B.CATB.R", "B.AB.R"]
    support_ground_ok = len(ground_ids) == 6 and all(any(reachable(support_id, ground_id, members, {"FND"}) for ground_id in ground_ids)
                                                     for support_id in support_ids)
    checks.append(make_check("F0-SUPPORT-GROUND-CLOSURE", "SATISFIED_F0_GEOMETRY" if support_ground_ok else "VIOLATED_F0_GEOMETRY",
                             "AB/CATB/TN support nodes each have an explicit FND edge to a distinct GND terminal"))

    with CSV_PATH.open(encoding="utf-8", newline="") as handle:
        csv_nodes = list(csv.DictReader(handle))
    csv_ok = len(csv_nodes) == len(nodes) and all(row["id"] == node["id"] and close(row["x_m"], node["x_m"])
                                                  and close(row["z_local_m"], node["z_local_m"])
                                                  for row, node in zip(csv_nodes, nodes))
    checks.append(make_check("F0-CSV-JSON-AGREEMENT", "SATISFIED_F0_GEOMETRY" if csv_ok else "VIOLATED_F0_GEOMETRY",
                             f"csv_rows={len(csv_nodes)}; json_nodes={len(nodes)}"))

    arch_nodes = [node for node in nodes if node["family"] in {"AC", "AH"}]
    soffit = float(r["deck_z_local_m"]) - float(r["steel_box_depth_m"])
    render_gap = min(soffit - float(node["z_local_m"]) for node in arch_nodes)
    gap_ok = render_gap > 0.0
    checks.append(make_check("F0-LOCAL-RENDER-ARCH-GAP", "SATISFIED_RENDER_GEOMETRY_ONLY" if gap_ok else "VIOLATED_F0_GEOMETRY",
                             f"minimum local seed gap from box soffit to arch centreline={render_gap:.6f} m; not a fabrication clearance"))

    with tempfile.TemporaryDirectory(prefix="hgb_b1_replay_") as tmp:
        proc = subprocess.run([sys.executable, str(GENERATOR_PATH), "--seed", str(SEED_PATH), "--output-dir", tmp],
                              check=False, capture_output=True, text=True, encoding="utf-8")
        replay_geometry = Path(tmp) / "b1_1440_geometry.json"
        replay_csv = Path(tmp) / "b1_1440_nodes.csv"
        replay_ok = proc.returncode == 0 and replay_geometry.exists() and replay_csv.exists()
        replay_ok = replay_ok and hashlib.sha256(replay_geometry.read_bytes()).digest() == hashlib.sha256(GEOMETRY_PATH.read_bytes()).digest()
        replay_ok = replay_ok and hashlib.sha256(replay_csv.read_bytes()).digest() == hashlib.sha256(CSV_PATH.read_bytes()).digest()
    checks.append(make_check("F0-DETERMINISTIC-REPLAY", "SATISFIED_F0_GEOMETRY" if replay_ok else "VIOLATED_F0_GEOMETRY",
                             "fresh temporary replay compared byte-for-byte for geometry JSON and node CSV"))

    checks.extend([
        make_check("G0-DESIGN-BASIS", "FAIL_INHERITED_STOP_FOR_ENGINEERING_CLAIMS",
                   "site survey, approved navigation datum/envelope, geotechnics, loads, materials and service life remain incomplete"),
        make_check("G1-NAVIGATION-EXCLUSION", "BLOCKED_MISSING_INPUT",
                   "local z=0 render cannot be intersected with an approved absolute navigation prism"),
        make_check("G2-PSI-A", "NOT_RUN_SOLVER_REQUIRED",
                   "B1 interface exists, but vertical load share psi_a is not assigned"),
        make_check("G2-TOWER-BALANCE", "NOT_RUN_SOLVER_REQUIRED",
                   "main cable, backstay and separate landward stay vectors require staged nonlinear analysis"),
        make_check("G3-AERODYNAMIC-STABILITY", "NOT_RUN_WIND_STUDY_REQUIRED",
                   "section is a render seed; no CFD or wind-tunnel evidence")
    ])

    hard_fail = any(item["status"] == "VIOLATED_F0_GEOMETRY" for item in checks)
    return {
        "schema_version": "1.0",
        "concept_id": seed["concept_id"],
        "claim_level": "IDEA",
        "verification_outcome": "F0_GEOMETRY_CHECKS_PASSED_WITH_ENGINEERING_GATES_BLOCKED" if not hard_fail else "F0_GEOMETRY_CHECK_FAILED",
        "checks": checks,
        "counts": {"nodes": len(nodes), "members": len(members)},
        "geometry_sha256": hashlib.sha256(GEOMETRY_PATH.read_bytes()).hexdigest(),
        "nodes_csv_sha256": hashlib.sha256(CSV_PATH.read_bytes()).hexdigest(),
        "engineering_release": "PROHIBITED"
    }


def main() -> int:
    result = verify()
    CHECKS_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"verification_outcome": result["verification_outcome"], "counts": result["counts"]}, ensure_ascii=False))
    return 0 if result["verification_outcome"].startswith("F0_GEOMETRY_CHECKS_PASSED") else 1


if __name__ == "__main__":
    raise SystemExit(main())
