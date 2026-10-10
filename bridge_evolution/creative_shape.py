"""Sáng tạo hình thái vòm bằng Constrained MAP-Elites ở mức nghiên cứu F0.

Module này tạo hình học và sàng lọc bằng các bất biến hình học, đồ thị đường
truyền lực và proxy cơ học đơn giản. Nó KHÔNG phải solver kết cấu, không kiểm
được ổn định, dao động, mỏi, liên kết, móng, thi công hoặc tổ hợp tải theo tiêu
chuẩn. Vì vậy kết quả luôn có ``claim_level=IDEA`` và không có trường
``feasible``/``verified``.

Nguyên tắc fail-closed: độ mới hình thái không được bù cho một kiểm tra FAIL;
thiếu ngưỡng hoặc thiếu tệp nguồn tạo ``UNKNOWN_INPUT_MISSING`` và ứng viên
không được vào archive MAP-Elites.
"""
from __future__ import annotations

import bisect
import hashlib
import json
import math
import random
import statistics
from copy import deepcopy
from pathlib import Path, PurePosixPath
from typing import Iterable

import jsonschema

from . import CONTRACTS_DIR, REPO_ROOT


CLAIM_LEVEL = "IDEA"
GENERATOR_ID = "CONSTRAINED_MAP_ELITES_ARCH"
GENERATOR_VERSION = "creative-shape/0.3.0"
TECHNICAL_SCOPE = "GEOMETRY_AND_SCREENING_PROXY_ONLY_NO_STRUCTURAL_VERIFICATION"

_DEFAULT_DOMAIN = REPO_ROOT / "docs" / "design_basis" / "creative_shape_domain.json"
_CANDIDATE_SCHEMA = CONTRACTS_DIR / "creative_shape_candidate.schema.json"
_GENOME_KEYS = {
    "topology",
    "span_m",
    "rise_ratio",
    "panel_count",
    "rib_count",
    "rib_depth_m",
    "deck_clearance_m",
    "shape_coefficients",
}
_THRUST_PROFILE_KEYS = (
    "distributed_load_kN_m",
    "rib_area_m2",
    "allowable_compression_MPa",
)
_MEMBER_DEPTH_KEYS = {
    "DECK": "deck_member_depth_m",
    "SPANDREL": "spandrel_member_depth_m",
    "END_POST": "end_post_member_depth_m",
    "HANGER": "hanger_member_depth_m",
    "NETWORK_HANGER": "hanger_member_depth_m",
}
_PASS_LIKE_STATUSES = {"PASS", "NOT_APPLICABLE"}
_EXPECTED_CHECK_IDS = {f"CQD-L0-{index:02d}" for index in range(1, 8)}
_TIED_ARCH_TOPOLOGIES = {"THROUGH_ARCH", "NETWORK_ARCH"}
_TIED_THRUST_NA_MODEL_KIND = "NOT_APPLICABLE_TIED_ARCH_THRUST_PROXY"
_TIED_THRUST_NA_MESSAGE = (
    "Proxy lực xô vòm parabol không áp dụng cho tied/through/network arch vì "
    "lực xô được thanh kéo tiếp nhận thay vì truyền trực tiếp xuống móng"
)
_COMMON_LIMITATIONS = [
    "Chỉ sàng lọc hình học và proxy F0 ở claim IDEA; không phải thiết kế khả thi.",
    "Không có phân tích ổn định, dao động, mỏi, liên kết, móng, thi công hoặc tổ hợp tải tiêu chuẩn.",
    "source_ref, source_sha256 và source_clause_id chỉ chứng minh provenance; không chứng minh applicability.",
]
_TIED_ARCH_LIMITATION = (
    "CQD-L0-07 không áp dụng cho tied/through/network arch; vì chưa có proxy thay thế, "
    "hai topology này hiện không có sàng lọc cơ học F0 và chỉ được sàng lọc hình học."
)


class CreativeShapeError(ValueError):
    """Dữ liệu miền, genome hoặc output vi phạm hợp đồng nghiên cứu."""


def _canonical(value: object) -> str:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise CreativeShapeError(f"Dữ liệu không thể canonical JSON: {exc}") from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _is_finite_number(value: object) -> bool:
    return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)


def _bounds_valid(bounds: object) -> bool:
    return (
        isinstance(bounds, dict)
        and set(bounds) == {"min", "max"}
        and _is_finite_number(bounds["min"])
        and _is_finite_number(bounds["max"])
        and float(bounds["min"]) < float(bounds["max"])
    )


def _strictly_increasing(values: object) -> bool:
    return (
        isinstance(values, list)
        and len(values) >= 2
        and all(_is_finite_number(value) for value in values)
        and all(float(a) < float(b) for a, b in zip(values, values[1:]))
    )


def load_creative_domain(path: str | Path | None = None) -> dict:
    """Đọc miền tìm kiếm; không suy diễn ngưỡng kỹ thuật từ miền này."""
    source = Path(path) if path is not None else _DEFAULT_DOMAIN
    if not source.is_file():
        raise CreativeShapeError(f"Không tìm thấy miền sáng tạo: {source}")
    try:
        domain = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CreativeShapeError(f"Không đọc được miền sáng tạo: {exc}") from exc

    return validate_creative_domain(domain)


def validate_creative_domain(domain: dict) -> dict:
    """Kiểm miền kể cả khi caller truyền object thay vì đọc tệp mặc định."""
    if not isinstance(domain, dict):
        raise CreativeShapeError("Miền sáng tạo phải là object")

    required = {
        "schema_version", "domain_id", "claim_ceiling", "generator_version",
        "technical_scope", "topology_values", "span_m", "rise_ratio",
        "panel_count_values", "rib_count_values", "rib_depth_m",
        "deck_clearance_m", "coefficient_count", "coefficient_bounds",
        "axis_point_count", "bins", "not_applicable_justifications", "notes_vi",
    }
    if set(domain) != required:
        raise CreativeShapeError(
            f"Miền sáng tạo sai khóa; missing={sorted(required - set(domain))}, "
            f"extra={sorted(set(domain) - required)}")
    if domain["claim_ceiling"] != CLAIM_LEVEL:
        raise CreativeShapeError("Miền sáng tạo không được nâng claim_ceiling khỏi IDEA")
    if domain["generator_version"] != GENERATOR_VERSION:
        raise CreativeShapeError("generator_version của miền không khớp runtime")
    if domain["technical_scope"] != "SEARCH_BOUNDS_ONLY_NOT_DESIGN_LIMITS":
        raise CreativeShapeError("Miền phải tự khai là biên tìm kiếm, không phải giới hạn thiết kế")
    if domain["topology_values"] != ["DECK_ARCH", "THROUGH_ARCH", "NETWORK_ARCH"]:
        raise CreativeShapeError("topology_values phải gồm đúng ba topology đã hỗ trợ")
    for name in ("span_m", "rise_ratio", "rib_depth_m", "deck_clearance_m", "coefficient_bounds"):
        if not _bounds_valid(domain[name]):
            raise CreativeShapeError(f"{name} phải có min < max hữu hạn")
    for name in ("panel_count_values", "rib_count_values"):
        values = domain[name]
        if (
            not isinstance(values, list)
            or not values
            or any(isinstance(value, bool) or not isinstance(value, int) or value <= 0 for value in values)
            or values != sorted(set(values))
        ):
            raise CreativeShapeError(f"{name} phải là danh sách số nguyên dương, tăng và duy nhất")
    if any(value % 2 for value in domain["panel_count_values"]):
        raise CreativeShapeError("panel_count_values phải chẵn để giữ một nút tại giữa nhịp")
    count = domain["coefficient_count"]
    if isinstance(count, bool) or not isinstance(count, int) or count < 1:
        raise CreativeShapeError("coefficient_count phải là số nguyên dương")
    points = domain["axis_point_count"]
    if isinstance(points, bool) or not isinstance(points, int) or points < 21 or points % 2 == 0:
        raise CreativeShapeError("axis_point_count phải là số lẻ >= 21")
    if set(domain["bins"]) != {"rise_ratio", "curvature_complexity", "asymmetry"}:
        raise CreativeShapeError("bins thiếu hoặc thừa descriptor")
    if any(not _strictly_increasing(edges) for edges in domain["bins"].values()):
        raise CreativeShapeError("Mỗi dãy bin phải tăng nghiêm ngặt và hữu hạn")
    justification = domain["not_applicable_justifications"]
    expected_justification_keys = {
        "topologies", "check_id", "status", "model_kind", "reason_vi", "consequence_vi",
    }
    if (
        not isinstance(justification, dict)
        or set(justification) != {"CQD-L0-07"}
        or not isinstance(justification["CQD-L0-07"], dict)
        or set(justification["CQD-L0-07"]) != expected_justification_keys
    ):
        raise CreativeShapeError("not_applicable_justifications phải khai đúng CQD-L0-07")
    thrust_justification = justification["CQD-L0-07"]
    if (
        thrust_justification["topologies"] != ["THROUGH_ARCH", "NETWORK_ARCH"]
        or thrust_justification["check_id"] != "CQD-L0-07"
        or thrust_justification["status"] != "NOT_APPLICABLE"
        or thrust_justification["model_kind"] != _TIED_THRUST_NA_MODEL_KIND
        or not isinstance(thrust_justification["reason_vi"], str)
        or not thrust_justification["reason_vi"].strip()
        or "thanh kéo" not in thrust_justification["reason_vi"]
        or "móng" not in thrust_justification["reason_vi"]
        or not isinstance(thrust_justification["consequence_vi"], str)
        or "không có sàng lọc cơ học F0" not in thrust_justification["consequence_vi"]
    ):
        raise CreativeShapeError("Biện minh NOT_APPLICABLE của CQD-L0-07 không nhất quán")
    if not isinstance(domain["notes_vi"], list) or not all(
        isinstance(note, str) and note.strip() for note in domain["notes_vi"]
    ):
        raise CreativeShapeError("notes_vi phải là danh sách chuỗi không rỗng")
    return domain


def validate_genome(genome: dict, domain: dict | None = None) -> None:
    """Fail-fast với genome ngoài miền hoặc chứa NaN/Infinity."""
    if not isinstance(genome, dict) or set(genome) != _GENOME_KEYS:
        actual = set(genome) if isinstance(genome, dict) else set()
        raise CreativeShapeError(
            f"Genome sai khóa; missing={sorted(_GENOME_KEYS - actual)}, "
            f"extra={sorted(actual - _GENOME_KEYS)}")
    domain = load_creative_domain() if domain is None else validate_creative_domain(domain)
    if genome["topology"] not in domain["topology_values"]:
        raise CreativeShapeError(f"Topology ngoài miền: {genome['topology']!r}")

    for name in ("span_m", "rise_ratio", "rib_depth_m", "deck_clearance_m"):
        value = genome[name]
        if not _is_finite_number(value):
            raise CreativeShapeError(f"{name} phải hữu hạn và không được là boolean")
        bounds = domain[name]
        if float(value) < float(bounds["min"]) or float(value) > float(bounds["max"]):
            raise CreativeShapeError(f"{name}={value} nằm ngoài [{bounds['min']}, {bounds['max']}]")

    for name in ("panel_count", "rib_count"):
        value = genome[name]
        if isinstance(value, bool) or not isinstance(value, int) or value not in domain[f"{name}_values"]:
            raise CreativeShapeError(f"{name}={value!r} nằm ngoài tập cho phép")

    coefficients = genome["shape_coefficients"]
    if not isinstance(coefficients, list) or len(coefficients) != domain["coefficient_count"]:
        raise CreativeShapeError(
            f"shape_coefficients phải có đúng {domain['coefficient_count']} phần tử")
    bounds = domain["coefficient_bounds"]
    for index, value in enumerate(coefficients):
        if not _is_finite_number(value):
            raise CreativeShapeError(f"shape_coefficients[{index}] không hữu hạn")
        if float(value) < float(bounds["min"]) or float(value) > float(bounds["max"]):
            raise CreativeShapeError(
                f"shape_coefficients[{index}]={value} ngoài [{bounds['min']}, {bounds['max']}]")


def _raw_axis_ordinate(t: float, coefficients: Iterable[float]) -> float:
    base = 4.0 * t * (1.0 - t)
    modulation = 1.0 + sum(
        float(coefficient) * math.sin(order * math.pi * t)
        for order, coefficient in enumerate(coefficients, start=1)
    )
    return base * modulation


def generate_arch_axis(genome: dict, domain: dict | None = None) -> list[dict]:
    """Sinh trục vòm: đúng hai gối, x đơn điệu và đúng chiều cao mục tiêu."""
    domain = load_creative_domain() if domain is None else validate_creative_domain(domain)
    validate_genome(genome, domain)
    count = domain["axis_point_count"]
    raw = [
        _raw_axis_ordinate(index / (count - 1), genome["shape_coefficients"])
        for index in range(count)
    ]
    if any(value <= 0.0 for value in raw[1:-1]):
        raise CreativeShapeError("Hệ số hình dạng tạo trục không dương trong lòng nhịp")
    raw_max = max(raw)
    if not math.isfinite(raw_max) or raw_max <= 0.0:
        raise CreativeShapeError("Không xác định được chiều cao trục vòm")
    span = float(genome["span_m"])
    target_rise = span * float(genome["rise_ratio"])
    scale = target_rise / raw_max
    peak_index = raw.index(raw_max)
    points: list[dict] = []
    for index, ordinate in enumerate(raw):
        t = index / (count - 1)
        y = target_rise if index == peak_index else ordinate * scale
        if index in (0, count - 1):
            y = 0.0
        points.append({"index": index, "t": t, "x_m": span * t, "y_m": y})
    points[0]["x_m"] = 0.0
    points[-1]["x_m"] = span
    if not all(a["x_m"] < b["x_m"] for a, b in zip(points, points[1:])):
        raise CreativeShapeError("Trục sinh ra không đơn điệu theo x")
    return points


def _interpolate_axis(points: list[dict], t: float) -> tuple[float, float]:
    scaled = t * (len(points) - 1)
    left = min(int(math.floor(scaled)), len(points) - 2)
    fraction = scaled - left
    a, b = points[left], points[left + 1]
    return (
        a["x_m"] + fraction * (b["x_m"] - a["x_m"]),
        a["y_m"] + fraction * (b["y_m"] - a["y_m"]),
    )


def build_load_path_graph(genome: dict, axis_points: list[dict] | None = None,
                          domain: dict | None = None) -> dict:
    """Dựng graph khái niệm; graph này không thay thế mô hình phần tử hữu hạn."""
    domain = load_creative_domain() if domain is None else validate_creative_domain(domain)
    validate_genome(genome, domain)
    axis_points = axis_points or generate_arch_axis(genome, domain)
    panel_count = genome["panel_count"]
    topology = genome["topology"]
    arch_panel = [_interpolate_axis(axis_points, index / panel_count) for index in range(panel_count + 1)]
    rise = max(point["y_m"] for point in axis_points)
    deck_y = rise + float(genome["deck_clearance_m"]) if topology == "DECK_ARCH" else 0.0

    tied_arch = topology in {"THROUGH_ARCH", "NETWORK_ARCH"}
    nodes: list[dict] = []
    for index, (x_m, y_m) in enumerate(arch_panel):
        nodes.append({
            "id": f"A{index}",
            "kind": "ARCH_DECK" if tied_arch and index in (0, panel_count) else "ARCH",
            "x_m": x_m, "y_m": y_m,
            "support": index in (0, panel_count),
        })
    deck_indices = range(panel_count + 1) if not tied_arch else range(1, panel_count)
    for index in deck_indices:
        x_m, _y_m = arch_panel[index]
        nodes.append({
            "id": f"D{index}", "kind": "DECK", "x_m": x_m, "y_m": deck_y,
            "support": False,
        })

    edges: list[dict] = []

    def add_edge(a: str, b: str, kind: str) -> None:
        edges.append({"id": f"E{len(edges):03d}", "from": a, "to": b, "kind": kind})

    def deck_node(index: int) -> str:
        if tied_arch and index in (0, panel_count):
            return f"A{index}"
        return f"D{index}"

    for index in range(panel_count):
        add_edge(f"A{index}", f"A{index + 1}", "ARCH_RIB")
        add_edge(deck_node(index), deck_node(index + 1), "DECK")
    if not tied_arch:
        add_edge("D0", "A0", "END_POST")
        add_edge(f"D{panel_count}", f"A{panel_count}", "END_POST")

    if topology == "DECK_ARCH":
        for index in range(1, panel_count):
            add_edge(f"A{index}", f"D{index}", "SPANDREL")
    elif topology == "THROUGH_ARCH":
        for index in range(1, panel_count):
            add_edge(f"D{index}", f"A{index}", "HANGER")
    else:
        offset = max(1, panel_count // 4)
        for index in range(1, panel_count):
            left = max(1, index - offset)
            right = min(panel_count - 1, index + offset)
            add_edge(f"D{index}", f"A{left}", "NETWORK_HANGER")
            if right != left:
                add_edge(f"D{index}", f"A{right}", "NETWORK_HANGER")
    return {"topology": topology, "nodes": nodes, "edges": edges}


def load_path_connected(graph: dict) -> bool:
    """Mọi nút mặt cầu phải truyền tải sang vòm rồi nối được tới gối."""
    if not isinstance(graph, dict) or not isinstance(graph.get("nodes"), list) or not isinstance(graph.get("edges"), list):
        return False
    if any(not isinstance(node, dict) for node in graph["nodes"]):
        return False
    node_ids = [node.get("id") for node in graph["nodes"]]
    if len(node_ids) != len(graph["nodes"]) or len(set(node_ids)) != len(node_ids):
        return False
    if any(
        node.get("kind") not in {"ARCH", "DECK", "ARCH_DECK"}
        or not isinstance(node.get("support"), bool)
        or not _is_finite_number(node.get("x_m"))
        or not _is_finite_number(node.get("y_m"))
        for node in graph["nodes"]
    ):
        return False
    coordinates = [(float(node["x_m"]), float(node["y_m"])) for node in graph["nodes"]]
    if len(set(coordinates)) != len(coordinates):
        return False
    known = set(node_ids)
    nodes = {node["id"]: node for node in graph["nodes"]}
    adjacency = {node_id: set() for node_id in known}
    edge_ids: set[str] = set()
    transfer_kinds = {"SPANDREL", "HANGER", "NETWORK_HANGER"}
    structural_kinds = transfer_kinds | {"ARCH_RIB", "DECK", "END_POST"}
    transfer_nodes: set[str] = set()
    for edge in graph["edges"]:
        if not isinstance(edge, dict):
            return False
        edge_id, a, b, kind = edge.get("id"), edge.get("from"), edge.get("to"), edge.get("kind")
        if (
            not isinstance(edge_id, str) or edge_id in edge_ids
            or a not in known or b not in known or a == b or kind not in structural_kinds
            or _distance(nodes[a], nodes[b]) <= 1e-9
        ):
            return False
        edge_ids.add(edge_id)
        kind_a, kind_b = nodes[a]["kind"], nodes[b]["kind"]
        a_is_arch, b_is_arch = kind_a in {"ARCH", "ARCH_DECK"}, kind_b in {"ARCH", "ARCH_DECK"}
        a_is_deck, b_is_deck = kind_a in {"DECK", "ARCH_DECK"}, kind_b in {"DECK", "ARCH_DECK"}
        if kind == "ARCH_RIB" and not (a_is_arch and b_is_arch):
            return False
        if kind == "DECK" and not (a_is_deck and b_is_deck):
            return False
        if kind in transfer_kinds | {"END_POST"}:
            if not ((kind_a == "DECK" and b_is_arch) or (kind_b == "DECK" and a_is_arch)):
                return False
            transfer_nodes.add(a if kind_a == "DECK" else b)
        adjacency[a].add(b)
        adjacency[b].add(a)
    supports = {
        node["id"] for node in graph["nodes"]
        if node.get("support") is True
    }
    deck_nodes = [
        node["id"] for node in graph["nodes"]
        if node.get("kind") in {"DECK", "ARCH_DECK"}
    ]
    if not supports or not deck_nodes:
        return False
    deck_nodes_requiring_transfer = [
        node["id"] for node in graph["nodes"]
        if node["kind"] == "DECK" and node["support"] is not True
    ]
    if any(node_id not in transfer_nodes for node_id in deck_nodes_requiring_transfer):
        return False
    reached = set(supports)
    frontier = list(supports)
    while frontier:
        current = frontier.pop()
        for neighbour in adjacency[current] - reached:
            reached.add(neighbour)
            frontier.append(neighbour)
    return all(node_id in reached for node_id in deck_nodes)


def _distance(a: dict, b: dict) -> float:
    return math.hypot(float(b["x_m"]) - float(a["x_m"]), float(b["y_m"]) - float(a["y_m"]))


def _circumradius(a: dict, b: dict, c: dict) -> float | None:
    ab, bc, ca = _distance(a, b), _distance(b, c), _distance(c, a)
    twice_area = abs(
        (float(b["x_m"]) - float(a["x_m"])) * (float(c["y_m"]) - float(a["y_m"]))
        - (float(b["y_m"]) - float(a["y_m"])) * (float(c["x_m"]) - float(a["x_m"]))
    )
    if twice_area <= 1e-12:
        return None
    radius = ab * bc * ca / (2.0 * twice_area)
    return radius if math.isfinite(radius) and radius > 0.0 else None


def describe_shape(genome: dict, axis_points: list[dict], graph: dict) -> dict:
    """Tính descriptor hình thái và đại lượng sàng lọc thuần hình học."""
    if not isinstance(genome, dict) or not isinstance(graph, dict):
        raise CreativeShapeError("Genome và graph phải là object")
    if genome.get("topology") != graph.get("topology"):
        raise CreativeShapeError("Topology của genome và graph không khớp")
    if not load_path_connected(graph):
        raise CreativeShapeError("Graph không thỏa bất biến đường truyền lực")
    segments = list(zip(axis_points, axis_points[1:]))
    lengths = [_distance(a, b) for a, b in segments]
    slopes = [
        (float(b["y_m"]) - float(a["y_m"])) / (float(b["x_m"]) - float(a["x_m"]))
        for a, b in segments
    ]
    radii = [
        radius for radius in (
            _circumradius(a, b, c) for a, b, c in zip(axis_points, axis_points[1:], axis_points[2:])
        ) if radius is not None
    ]
    if not radii:
        raise CreativeShapeError("Không tính được bán kính cong của trục vòm")
    curvatures = [1.0 / radius for radius in radii]
    mean_curvature = statistics.fmean(curvatures)
    curvature_complexity = (
        statistics.pstdev(curvatures) / mean_curvature if mean_curvature > 0.0 else 0.0
    )
    rise = max(float(point["y_m"]) for point in axis_points)
    paired = zip(axis_points[1:len(axis_points) // 2 + 1], reversed(axis_points[len(axis_points) // 2:-1]))
    asymmetry = statistics.fmean(
        abs(float(left["y_m"]) - float(right["y_m"])) / rise for left, right in paired
    ) if rise > 0.0 else 0.0

    nodes = {node["id"]: node for node in graph["nodes"]}
    edge_lengths = {
        edge["id"]: _distance(nodes[edge["from"]], nodes[edge["to"]])
        for edge in graph["edges"]
    }
    arch_edges = [edge for edge in graph["edges"] if edge["kind"] == "ARCH_RIB"]
    panel_lengths = [edge_lengths[edge["id"]] for edge in arch_edges]
    if graph["topology"] == "DECK_ARCH":
        deck_y = float(nodes["D0"]["y_m"])
        deck_arch_separation = min(deck_y - float(point["y_m"]) for point in axis_points)
        through_arch_clearance = None
    else:
        deck_y = 0.0
        deck_arch_separation = None
        through_arch_clearance = min(
            float(point["y_m"]) - deck_y for point in axis_points[1:-1]
        )
    max_arch_panel = max(panel_lengths)
    return {
        "rise_ratio": rise / float(genome["span_m"]),
        "curvature_complexity": curvature_complexity,
        "asymmetry": asymmetry,
        "arc_length_m": sum(lengths),
        "max_abs_slope": max(abs(value) for value in slopes),
        "min_curvature_radius_m": min(radii),
        "max_member_length_m": max(edge_lengths.values()),
        "max_arch_rib_slenderness": max_arch_panel / float(genome["rib_depth_m"]),
        "min_deck_arch_separation_m": deck_arch_separation,
        "min_through_arch_clearance_m": through_arch_clearance,
    }


def _source_path(source_ref: object) -> Path | None:
    if not isinstance(source_ref, str) or not source_ref.strip():
        return None
    path_text = source_ref.split("#", 1)[0]
    if "\\" in path_text:
        return None
    posix = PurePosixPath(path_text)
    if (
        posix.is_absolute()
        or not posix.parts
        or any(part in {"", ".", ".."} for part in posix.parts)
        or posix.as_posix() != path_text
    ):
        return None
    supplied = Path(*posix.parts)
    resolved = (REPO_ROOT / supplied).resolve(strict=False)
    try:
        resolved.relative_to(REPO_ROOT.resolve())
    except ValueError:
        return None
    return resolved if resolved.is_file() else None


def _source_sha256(source_ref: object) -> str | None:
    path = _source_path(source_ref)
    return hashlib.sha256(path.read_bytes()).hexdigest() if path is not None else None


def _profile_snapshot(profile: dict) -> dict:
    """Hash cả giá trị profile lẫn bytes nguồn để nguồn drift đổi fingerprint."""
    if not isinstance(profile, dict):
        raise CreativeShapeError("technical_profile phải là object")
    refs = sorted({
        item.get("source_ref")
        for item in profile.values()
        if isinstance(item, dict) and isinstance(item.get("source_ref"), str)
    })
    return {
        "profile": profile,
        "source_sha256": {source_ref: _source_sha256(source_ref) for source_ref in refs},
    }


def _profile_value(
    profile: dict, key: str,
) -> tuple[float | None, str | None, str | None, str | None, str | None]:
    item = profile.get(key)
    if not isinstance(item, dict):
        return None, None, None, None, f"Thiếu technical_profile.{key}"
    required_keys = {"value", "source_ref", "expected_source_sha256", "clause_id"}
    if set(item) != required_keys:
        source_ref = item.get("source_ref")
        clause_id = item.get("clause_id")
        return (
            None,
            source_ref if isinstance(source_ref, str) else None,
            _source_sha256(source_ref),
            clause_id if isinstance(clause_id, str) and clause_id.strip() else None,
            f"technical_profile.{key} phải có đúng value, source_ref, "
            "expected_source_sha256 và clause_id",
        )
    value, source_ref, clause_id = item["value"], item["source_ref"], item["clause_id"]
    expected_source_sha256 = item["expected_source_sha256"]
    if not isinstance(clause_id, str) or not clause_id.strip() or len(clause_id) > 200:
        return (
            None,
            source_ref if isinstance(source_ref, str) else None,
            _source_sha256(source_ref),
            None,
            f"technical_profile.{key}.clause_id phải là chuỗi không rỗng, tối đa 200 ký tự",
        )
    if not _is_finite_number(value) or float(value) <= 0.0:
        return (
            None,
            source_ref if isinstance(source_ref, str) else None,
            _source_sha256(source_ref),
            clause_id,
            f"technical_profile.{key}.value phải > 0 và hữu hạn",
        )
    source_sha256 = _source_sha256(source_ref)
    if source_sha256 is None:
        return (
            None, source_ref if isinstance(source_ref, str) else None, None, clause_id,
            f"source_ref của {key} không tồn tại trong repo",
        )
    if (
        not isinstance(expected_source_sha256, str)
        or len(expected_source_sha256) != 64
        or any(character not in "0123456789abcdef" for character in expected_source_sha256)
    ):
        return (
            None, source_ref, source_sha256, clause_id,
            f"expected_source_sha256 của {key} không hợp lệ",
        )
    if source_sha256 != expected_source_sha256:
        return (
            None, source_ref, source_sha256, clause_id,
            f"source_ref của {key} đã drift: expected={expected_source_sha256}, observed={source_sha256}",
        )
    return float(value), source_ref, source_sha256, clause_id, None


def _unknown_check(check_id: str, demand: float | None, model_kind: str,
                   source_ref: str | None, source_sha256: str | None,
                   source_clause_id: str | None, issue: str) -> dict:
    return {
        "check_id": check_id,
        "status": "UNKNOWN_INPUT_MISSING",
        "demand": demand,
        "limit": None,
        "utilization": None,
        "margin": None,
        "model_kind": model_kind,
        "source_ref": source_ref,
        "source_sha256": source_sha256,
        "source_clause_id": source_clause_id,
        "message": issue,
    }


def _combined_clause_id(clauses: Iterable[str]) -> str | None:
    unique = sorted(set(clauses))
    return " | ".join(unique) if unique else None


def _limit_check(check_id: str, demand: float, profile: dict, key: str, *,
                 upper: bool, model_kind: str) -> dict:
    limit, source_ref, source_sha256, source_clause_id, issue = _profile_value(profile, key)
    if issue is not None or limit is None:
        return _unknown_check(
            check_id, demand, model_kind, source_ref, source_sha256, source_clause_id,
            issue or "Thiếu ngưỡng")
    if upper:
        utilization = demand / limit
        margin = (limit - demand) / limit
        passed = demand <= limit
        relation = "không vượt"
    else:
        utilization = limit / demand if demand > 0.0 else None
        margin = (demand - limit) / limit
        passed = demand >= limit
        relation = "không nhỏ hơn"
    status = "PASS" if passed else "FAIL"
    return {
        "check_id": check_id,
        "status": status,
        "demand": demand,
        "limit": limit,
        "utilization": utilization,
        "margin": margin,
        "model_kind": model_kind,
        "source_ref": source_ref,
        "source_sha256": source_sha256,
        "source_clause_id": source_clause_id,
        "message": f"{key}: demand={demand:.6g} phải {relation} limit={limit:.6g}",
    }


def _member_slenderness_check(genome: dict, graph: dict, profile: dict) -> dict:
    """Kiểm L/depth trên mọi edge; thiếu depth của một kind thì UNKNOWN."""
    known_kinds = {"ARCH_RIB", *_MEMBER_DEPTH_KEYS}
    unknown_kinds = sorted(
        repr(kind) for kind in {edge.get("kind") for edge in graph["edges"]} - known_kinds)
    if unknown_kinds:
        raise CreativeShapeError(f"Kind cạnh không được hỗ trợ cho kiểm độ mảnh: {unknown_kinds}")
    nodes = {node["id"]: node for node in graph["nodes"]}
    required_depth_keys = sorted({
        _MEMBER_DEPTH_KEYS[edge["kind"]]
        for edge in graph["edges"] if edge["kind"] != "ARCH_RIB"
    })
    threshold = _profile_value(profile, "max_member_slenderness")
    depth_inputs = {key: _profile_value(profile, key) for key in required_depth_keys}
    all_inputs = [threshold, *depth_inputs.values()]
    issues = [issue for _value, _source, _sha, _clause, issue in all_inputs if issue is not None]
    sources = [source for _value, source, _sha, _clause, _issue in all_inputs if source is not None]
    hashes = [sha for _value, _source, sha, _clause, _issue in all_inputs if sha is not None]
    clauses = [clause for _value, _source, _sha, clause, _issue in all_inputs if clause is not None]
    if len(set(sources)) > 1:
        issues.append("Ngưỡng độ mảnh và mọi member depth phải cùng source_ref")
    if issues:
        return _unknown_check(
            "CQD-L0-05", None, "SCREENING_PROXY_GEOMETRIC_L_OVER_DEPTH_ALL_EDGES",
            sources[0] if len(set(sources)) == 1 else None,
            hashes[0] if len(set(hashes)) == 1 else None,
            _combined_clause_id(clauses),
            "; ".join(issues),
        )
    limit = threshold[0]
    assert limit is not None
    demands = []
    for edge in graph["edges"]:
        length = _distance(nodes[edge["from"]], nodes[edge["to"]])
        if edge["kind"] == "ARCH_RIB":
            depth = float(genome["rib_depth_m"])
        else:
            depth = depth_inputs[_MEMBER_DEPTH_KEYS[edge["kind"]]][0]
            assert depth is not None
        demands.append(length / depth)
    demand = max(demands)
    utilization = demand / limit
    return {
        "check_id": "CQD-L0-05",
        "status": "PASS" if demand <= limit else "FAIL",
        "demand": demand,
        "limit": limit,
        "utilization": utilization,
        "margin": 1.0 - utilization,
        "model_kind": "SCREENING_PROXY_GEOMETRIC_L_OVER_DEPTH_ALL_EDGES",
        "source_ref": sources[0],
        "source_sha256": hashes[0],
        "source_clause_id": _combined_clause_id(clauses),
        "message": "Proxy L/depth lớn nhất trên mọi edge; không phải kiểm ổn định cấu kiện",
    }


def technical_checks(genome: dict, graph: dict, descriptors: dict,
                     technical_profile: dict) -> list[dict]:
    """Sàng lọc fail-closed; proxy không mang thẩm quyền kết luận thiết kế."""
    if not isinstance(technical_profile, dict):
        raise CreativeShapeError("technical_profile phải là object")
    connected = load_path_connected(graph)
    checks = [{
        "check_id": "CQD-L0-01",
        "status": "PASS" if connected else "FAIL",
        "demand": 1.0 if connected else 0.0,
        "limit": 1.0,
        "utilization": 0.0 if connected else 1.0,
        "margin": 1.0 if connected else -1.0,
        "model_kind": "EXACT_GRAPH_INVARIANT",
        "source_ref": None,
        "source_sha256": None,
        "source_clause_id": None,
        "message": "Mọi nút mặt cầu nối được tới gối" if connected else "Graph không có đường từ mọi nút mặt cầu tới gối",
    }]
    checks.extend([
        _limit_check("CQD-L0-02", descriptors["max_abs_slope"], technical_profile,
                     "max_abs_slope", upper=True, model_kind="GEOMETRY_SCREEN"),
        _limit_check("CQD-L0-03", descriptors["min_curvature_radius_m"], technical_profile,
                     "min_curvature_radius_m", upper=False, model_kind="GEOMETRY_SCREEN"),
        _limit_check("CQD-L0-04", descriptors["max_member_length_m"], technical_profile,
                     "max_member_length_m", upper=True, model_kind="GEOMETRY_SCREEN"),
    ])
    checks.append(_member_slenderness_check(genome, graph, technical_profile))
    if genome["topology"] == "DECK_ARCH":
        clearance_demand = descriptors["min_deck_arch_separation_m"]
        clearance_key = "min_deck_arch_separation_m"
        clearance_kind = "GEOMETRY_DECK_TO_ARCH_SEPARATION_NOT_TRAFFIC_CLEARANCE"
    else:
        clearance_demand = descriptors["min_through_arch_clearance_m"]
        clearance_key = "min_through_arch_clearance_m"
        clearance_kind = "GEOMETRY_ALL_INTERIOR_AXIS_CLEARANCE"
    assert clearance_demand is not None
    checks.append(_limit_check(
        "CQD-L0-06", clearance_demand, technical_profile,
        clearance_key, upper=False, model_kind=clearance_kind))

    thrust_inputs = [_profile_value(technical_profile, key) for key in _THRUST_PROFILE_KEYS]
    issues = [
        issue for _value, _source, _sha, _clause, issue in thrust_inputs
        if issue is not None
    ]
    sources = [
        source for _value, source, _sha, _clause, _issue in thrust_inputs
        if source is not None
    ]
    source_hashes = [
        sha for _value, _source, sha, _clause, _issue in thrust_inputs
        if sha is not None
    ]
    source_clauses = [
        clause for _value, _source, _sha, clause, _issue in thrust_inputs
        if clause is not None
    ]
    if len(set(sources)) > 1:
        issues.append("Ba input thrust proxy phải cùng source_ref để giữ provenance một nghĩa")
    if genome["topology"] in _TIED_ARCH_TOPOLOGIES:
        checks.append({
            "check_id": "CQD-L0-07",
            "status": "NOT_APPLICABLE",
            "demand": None,
            "limit": None,
            "utilization": None,
            "margin": None,
            "model_kind": _TIED_THRUST_NA_MODEL_KIND,
            "source_ref": None,
            "source_sha256": None,
            "source_clause_id": None,
            "message": _TIED_THRUST_NA_MESSAGE,
        })
    elif issues:
        checks.append(_unknown_check(
            "CQD-L0-07", None, "SCREENING_PROXY_IDEALISED_PARABOLIC_ARCH",
            sources[0] if len(set(sources)) == 1 else None,
            source_hashes[0] if len(set(source_hashes)) == 1 else None,
            _combined_clause_id(source_clauses),
            "; ".join(issues)))
    else:
        distributed_load, rib_area, allowable = (item[0] for item in thrust_inputs)
        assert distributed_load is not None and rib_area is not None and allowable is not None
        span = float(genome["span_m"])
        rise = span * float(genome["rise_ratio"])
        horizontal = distributed_load * span ** 2 / (8.0 * rise)
        vertical = distributed_load * span / 2.0
        compression_kN = math.hypot(horizontal, vertical) / int(genome["rib_count"])
        stress_MPa = compression_kN / (rib_area * 1000.0)
        utilization = stress_MPa / allowable
        checks.append({
            "check_id": "CQD-L0-07",
            "status": "PASS" if utilization <= 1.0 else "FAIL",
            "demand": stress_MPa,
            "limit": allowable,
            "utilization": utilization,
            "margin": 1.0 - utilization,
            "model_kind": "SCREENING_PROXY_IDEALISED_PARABOLIC_ARCH",
            "source_ref": sources[0],
            "source_sha256": source_hashes[0],
            "source_clause_id": _combined_clause_id(source_clauses),
            "message": (
                "Proxy tham chiếu vòm parabol lý tưởng dưới tải phân bố; không phải bao "
                "cho trục đã sinh và không phải phân tích vòm/giàn: "
                f"stress_proxy={stress_MPa:.6g} MPa, limit={allowable:.6g} MPa"
            ),
        })
    return checks


def _candidate_limitations(topology: str) -> list[str]:
    limitations = list(_COMMON_LIMITATIONS)
    if topology in _TIED_ARCH_TOPOLOGIES:
        limitations.append(_TIED_ARCH_LIMITATION)
    return limitations


def _not_applicable_allowed(genome: dict, check: dict) -> bool:
    null_fields = (
        "demand", "limit", "utilization", "margin", "source_ref",
        "source_sha256", "source_clause_id",
    )
    return (
        genome.get("topology") in _TIED_ARCH_TOPOLOGIES
        and check.get("check_id") == "CQD-L0-07"
        and check.get("status") == "NOT_APPLICABLE"
        and check.get("model_kind") == _TIED_THRUST_NA_MODEL_KIND
        and check.get("message") == _TIED_THRUST_NA_MESSAGE
        and all(check.get(field) is None for field in null_fields)
    )


def _screening_state(checks: list[dict], genome: dict) -> tuple[bool, str]:
    if not isinstance(checks, list) or len(checks) != 7 or any(
        not isinstance(check, dict) for check in checks
    ):
        raise CreativeShapeError("Checks phải gồm đúng bảy object CQD-L0-01..07")
    check_ids = [check.get("check_id") for check in checks]
    if set(check_ids) != _EXPECTED_CHECK_IDS or len(set(check_ids)) != len(check_ids):
        raise CreativeShapeError("Checks phải có duy nhất CQD-L0-01..07")
    allowed_statuses = {"PASS", "FAIL", "UNKNOWN_INPUT_MISSING", "NOT_APPLICABLE"}
    if any(check.get("status") not in allowed_statuses for check in checks):
        raise CreativeShapeError("Check chứa status ngoài hợp đồng fail-closed")
    not_applicable = [check for check in checks if check.get("status") == "NOT_APPLICABLE"]
    if genome.get("topology") in _TIED_ARCH_TOPOLOGIES:
        if len(not_applicable) != 1:
            raise CreativeShapeError("Tied arch phải có đúng một CQD-L0-07 NOT_APPLICABLE")
    elif not_applicable:
        raise CreativeShapeError("DECK_ARCH không được chứa NOT_APPLICABLE")
    if any(not _not_applicable_allowed(genome, check) for check in not_applicable):
        raise CreativeShapeError("NOT_APPLICABLE không hợp lệ với check_id/topology/nội dung check")
    has_fail = any(check["status"] == "FAIL" for check in checks)
    has_unknown = any(check["status"] == "UNKNOWN_INPUT_MISSING" for check in checks)
    all_known_pass = not has_fail and not has_unknown and all(
        check["status"] in _PASS_LIKE_STATUSES for check in checks)
    status = "REJECTED" if has_fail else "UNKNOWN_INPUT_MISSING" if has_unknown else "L0_PASSED"
    return all_known_pass, status


def validate_candidate(candidate: dict, *, domain: dict | None = None,
                       technical_profile: dict | None = None) -> None:
    """Kiểm schema và tái lập các bất biến có thể xác minh từ candidate."""
    _canonical(candidate)
    try:
        schema = json.loads(_CANDIDATE_SCHEMA.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CreativeShapeError(f"Không đọc được candidate schema: {exc}") from exc
    errors = sorted(
        jsonschema.Draft202012Validator(schema).iter_errors(candidate),
        key=lambda error: list(error.absolute_path),
    )
    if errors:
        details = "; ".join(
            f"{'/'.join(str(part) for part in error.absolute_path) or '<root>'}: {error.message}"
            for error in errors[:12]
        )
        raise CreativeShapeError(f"Creative candidate sai schema: {details}")
    domain = load_creative_domain() if domain is None else validate_creative_domain(domain)
    validate_genome(candidate["genome"], domain)
    if candidate["generator"]["version"] != GENERATOR_VERSION:
        raise CreativeShapeError("Generator version của candidate không khớp runtime")
    if candidate["generator"]["domain_id"] != domain["domain_id"]:
        raise CreativeShapeError("domain_id của candidate không khớp domain")
    if candidate["domain_sha256"] != _sha256(domain):
        raise CreativeShapeError("domain_sha256 của candidate không khớp domain")
    expected_axis = generate_arch_axis(candidate["genome"], domain)
    expected_graph = build_load_path_graph(candidate["genome"], expected_axis, domain)
    if candidate["axis_points"] != expected_axis or candidate["graph"] != expected_graph:
        raise CreativeShapeError("Hình học/graph candidate không tái lập được từ genome và domain")
    expected_geometry_sha256 = _sha256({"axis_points": expected_axis, "graph": expected_graph})
    if candidate["geometry_sha256"] != expected_geometry_sha256:
        raise CreativeShapeError("geometry_sha256 không khớp axis_points và graph")
    if not load_path_connected(candidate["graph"]):
        raise CreativeShapeError("Graph candidate không thỏa bất biến đường truyền lực")
    expected_descriptors = describe_shape(candidate["genome"], expected_axis, expected_graph)
    if candidate["descriptors"] != expected_descriptors:
        raise CreativeShapeError("Descriptor candidate không khớp hình học tái lập")
    payload = deepcopy(candidate)
    claimed_candidate_sha256 = payload.pop("candidate_sha256")
    expected_candidate_sha256 = _sha256(payload)
    if claimed_candidate_sha256 != expected_candidate_sha256:
        raise CreativeShapeError(
            "candidate_sha256 không khớp toàn bộ payload candidate: "
            f"expected={expected_candidate_sha256}, actual={claimed_candidate_sha256}")
    if candidate["limitations"] != _candidate_limitations(candidate["genome"]["topology"]):
        raise CreativeShapeError("limitations của candidate không khớp topology và miền hiệu lực")
    expected_all_known_pass, expected_status = _screening_state(
        candidate["checks"], candidate["genome"])
    if (
        candidate["all_known_pass"] is not expected_all_known_pass
        or candidate["screening_status"] != expected_status
    ):
        raise CreativeShapeError("all_known_pass/screening_status không khớp trạng thái checks")
    if technical_profile is not None:
        expected_profile_sha256 = _sha256(_profile_snapshot(technical_profile))
        if candidate["profile_sha256"] != expected_profile_sha256:
            raise CreativeShapeError("profile_sha256 không khớp technical_profile")
        expected_checks = technical_checks(
            candidate["genome"], expected_graph, expected_descriptors, technical_profile)
        if candidate["checks"] != expected_checks:
            raise CreativeShapeError("Checks candidate không tái lập được từ technical_profile")
    identity = {
        "generator_id": candidate["generator"]["id"],
        "generator_version": candidate["generator"]["version"],
        "domain_id": candidate["generator"]["domain_id"],
        "domain_sha256": candidate["domain_sha256"],
        "genome": candidate["genome"],
        "profile_sha256": candidate["profile_sha256"],
    }
    if candidate["candidate_id"] != f"CS-{_sha256(identity)[:16]}":
        raise CreativeShapeError("candidate_id không khớp identity canonical")


def evaluate_genome(genome: dict, technical_profile: dict,
                    domain: dict | None = None) -> dict:
    """Tạo và sàng một hình thái; không trả verdict thiết kế kỹ thuật."""
    domain = load_creative_domain() if domain is None else validate_creative_domain(domain)
    validate_genome(genome, domain)
    if not isinstance(technical_profile, dict):
        raise CreativeShapeError("technical_profile phải là object")
    profile_sha256 = _sha256(_profile_snapshot(technical_profile))
    axis_points = generate_arch_axis(genome, domain)
    graph = build_load_path_graph(genome, axis_points, domain)
    descriptors = describe_shape(genome, axis_points, graph)
    checks = technical_checks(genome, graph, descriptors, technical_profile)
    all_known_pass, status = _screening_state(checks, genome)
    identity = {
        "generator_id": GENERATOR_ID,
        "generator_version": GENERATOR_VERSION,
        "domain_id": domain["domain_id"],
        "domain_sha256": _sha256(domain),
        "genome": genome,
        "profile_sha256": profile_sha256,
    }
    candidate = {
        "schema_version": "1.0",
        "candidate_id": f"CS-{_sha256(identity)[:16]}",
        "claim_level": CLAIM_LEVEL,
        "generator": {
            "id": GENERATOR_ID,
            "version": GENERATOR_VERSION,
            "domain_id": domain["domain_id"],
        },
        "genome": deepcopy(genome),
        "domain_sha256": _sha256(domain),
        "profile_sha256": profile_sha256,
        "geometry_sha256": _sha256({"axis_points": axis_points, "graph": graph}),
        "axis_points": axis_points,
        "graph": graph,
        "descriptors": descriptors,
        "checks": checks,
        "screening_status": status,
        "all_known_pass": all_known_pass,
        "technical_scope": TECHNICAL_SCOPE,
        "limitations": _candidate_limitations(genome["topology"]),
    }
    candidate["candidate_sha256"] = _sha256(candidate)
    validate_candidate(candidate, domain=domain, technical_profile=technical_profile)
    return candidate


def anchor_genomes(domain: dict | None = None) -> list[dict]:
    """Ba mốc topology bảo đảm lần chạy nhỏ vẫn thăm đủ họ hình thái."""
    domain = load_creative_domain() if domain is None else validate_creative_domain(domain)
    middle_panel = domain["panel_count_values"][len(domain["panel_count_values"]) // 2]
    base = {
        "span_m": (domain["span_m"]["min"] + domain["span_m"]["max"]) / 2.0,
        "rise_ratio": (domain["rise_ratio"]["min"] + domain["rise_ratio"]["max"]) / 2.0,
        "panel_count": middle_panel,
        "rib_count": max(domain["rib_count_values"]),
        "rib_depth_m": (domain["rib_depth_m"]["min"] + domain["rib_depth_m"]["max"]) / 2.0,
        "deck_clearance_m": (domain["deck_clearance_m"]["min"] + domain["deck_clearance_m"]["max"]) / 2.0,
        "shape_coefficients": [0.0] * domain["coefficient_count"],
    }
    return [{"topology": topology, **deepcopy(base)} for topology in domain["topology_values"]]


def random_genome(rng: random.Random, domain: dict | None = None) -> dict:
    domain = load_creative_domain() if domain is None else validate_creative_domain(domain)
    coefficient_bounds = domain["coefficient_bounds"]
    genome = {
        "topology": rng.choice(domain["topology_values"]),
        "span_m": rng.uniform(domain["span_m"]["min"], domain["span_m"]["max"]),
        "rise_ratio": rng.uniform(domain["rise_ratio"]["min"], domain["rise_ratio"]["max"]),
        "panel_count": rng.choice(domain["panel_count_values"]),
        "rib_count": rng.choice(domain["rib_count_values"]),
        "rib_depth_m": rng.uniform(domain["rib_depth_m"]["min"], domain["rib_depth_m"]["max"]),
        "deck_clearance_m": rng.uniform(domain["deck_clearance_m"]["min"], domain["deck_clearance_m"]["max"]),
        "shape_coefficients": [
            rng.uniform(coefficient_bounds["min"], coefficient_bounds["max"])
            for _ in range(domain["coefficient_count"])
        ],
    }
    validate_genome(genome, domain)
    return genome


def _clip(value: float, bounds: dict) -> float:
    return min(float(bounds["max"]), max(float(bounds["min"]), value))


def mutate_genome(parent: dict, rng: random.Random, domain: dict | None = None) -> dict:
    """Biến dị có chiếu về miền; không sửa candidate sau khi kiểm kỹ thuật."""
    domain = load_creative_domain() if domain is None else validate_creative_domain(domain)
    validate_genome(parent, domain)
    child = deepcopy(parent)
    if rng.random() < 0.15:
        child["topology"] = rng.choice(domain["topology_values"])
    if rng.random() < 0.35:
        child["panel_count"] = rng.choice(domain["panel_count_values"])
    if rng.random() < 0.20:
        child["rib_count"] = rng.choice(domain["rib_count_values"])
    for key, sigma_fraction in (
        ("span_m", 0.08), ("rise_ratio", 0.10), ("rib_depth_m", 0.12), ("deck_clearance_m", 0.12),
    ):
        if rng.random() < 0.65:
            bounds = domain[key]
            sigma = (float(bounds["max"]) - float(bounds["min"])) * sigma_fraction
            child[key] = _clip(float(child[key]) + rng.gauss(0.0, sigma), bounds)
    coefficient_bounds = domain["coefficient_bounds"]
    coefficient_sigma = (coefficient_bounds["max"] - coefficient_bounds["min"]) * 0.12
    for index in range(len(child["shape_coefficients"])):
        if rng.random() < 0.75:
            child["shape_coefficients"][index] = _clip(
                float(child["shape_coefficients"][index]) + rng.gauss(0.0, coefficient_sigma),
                coefficient_bounds,
            )
    validate_genome(child, domain)
    return child


def _bin_index(value: float, edges: list[float]) -> int:
    return max(0, min(len(edges) - 2, bisect.bisect_right(edges, value) - 1))


def _cell(candidate: dict, domain: dict) -> tuple[str, int, int, int]:
    descriptors = candidate["descriptors"]
    bins = domain["bins"]
    return (
        candidate["genome"]["topology"],
        _bin_index(descriptors["rise_ratio"], bins["rise_ratio"]),
        _bin_index(descriptors["curvature_complexity"], bins["curvature_complexity"]),
        _bin_index(descriptors["asymmetry"], bins["asymmetry"]),
    )


def _quality(candidate: dict) -> float:
    margins = [
        float(check["margin"]) for check in candidate["checks"]
        if check["status"] == "PASS" and check["margin"] is not None
    ]
    return min(margins) if margins else 0.0


def run_constrained_map_elites(*, technical_profile: dict, seed: int,
                               iterations: int = 100,
                               domain: dict | None = None) -> dict:
    """Chạy QD có safety shield; archive chỉ nhận all-known-pass.

    ``iterations`` là số biến dị sau ba anchor topology. Cùng domain, profile,
    seed và số vòng lặp cho output byte-canonical giống nhau.
    """
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise CreativeShapeError("seed phải là số nguyên")
    if isinstance(iterations, bool) or not isinstance(iterations, int) or iterations < 0:
        raise CreativeShapeError("iterations phải là số nguyên không âm")
    domain = load_creative_domain() if domain is None else validate_creative_domain(domain)
    rng = random.Random(seed)
    archive: dict[tuple[str, int, int, int], dict] = {}
    rejected: list[str] = []
    unknown: list[str] = []

    def consider(candidate: dict) -> None:
        if not candidate["all_known_pass"]:
            target = rejected if candidate["screening_status"] == "REJECTED" else unknown
            target.append(candidate["candidate_id"])
            return
        cell = _cell(candidate, domain)
        quality = _quality(candidate)
        incumbent = archive.get(cell)
        if (
            incumbent is None
            or quality > incumbent["quality_score"]
            or (
                math.isclose(quality, incumbent["quality_score"], rel_tol=0.0, abs_tol=1e-15)
                and candidate["candidate_id"] < incumbent["candidate"]["candidate_id"]
            )
        ):
            archive[cell] = {"quality_score": quality, "candidate": candidate}

    for genome in anchor_genomes(domain):
        consider(evaluate_genome(genome, technical_profile, domain))
    for _ in range(iterations):
        if archive:
            parents = [archive[key]["candidate"]["genome"] for key in sorted(archive)]
            genome = mutate_genome(rng.choice(parents), rng, domain)
        else:
            genome = random_genome(rng, domain)
        consider(evaluate_genome(genome, technical_profile, domain))

    archive_items = []
    for (topology, rise_bin, curvature_bin, asymmetry_bin), item in sorted(archive.items()):
        archive_items.append({
            "cell": {
                "topology": topology,
                "rise_bin": rise_bin,
                "curvature_bin": curvature_bin,
                "asymmetry_bin": asymmetry_bin,
            },
            "quality_score": item["quality_score"],
            "candidate": item["candidate"],
        })
    result = {
        "schema_version": "1.0",
        "algorithm": GENERATOR_ID,
        "algorithm_version": GENERATOR_VERSION,
        "claim_level": CLAIM_LEVEL,
        "technical_scope": TECHNICAL_SCOPE,
        "seed": seed,
        "iterations": iterations,
        "domain_sha256": _sha256(domain),
        "profile_sha256": _sha256(_profile_snapshot(technical_profile)),
        "archive": archive_items,
        "rejected_candidate_ids": rejected,
        "unknown_candidate_ids": unknown,
        "statistics": {
            "evaluated": len(domain["topology_values"]) + iterations,
            "occupied_cells": len(archive_items),
            "rejected": len(rejected),
            "unknown": len(unknown),
        },
    }
    _canonical(result)
    return result
