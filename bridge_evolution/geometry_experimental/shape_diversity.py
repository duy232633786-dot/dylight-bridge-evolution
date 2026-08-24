"""Chọn tập hình thái ĐA DẠNG — KHÔNG hàm mục tiêu — SANDBOX BRD-004.

===========================================================================
GIỚI HẠN HIỆU LỰC — ĐỌC TRƯỚC KHI DÙNG
===========================================================================
Họ vòm chạy trên (``arch_deck_cfst_skeleton_v1``) KHÔNG có hàm mục tiêu nào
trong runtime: không chi phí, không carbon, không solver nào chạm tới vòm
(RCM-2.0.0: SOLVER_MIDAS_CIVIL, SOLVER_OPENSEESPY, GRILLAGE_3D,
STAGED_PRESTRESS_EFFECTS đều ABSENT). Vì vậy tiêu chí nghiệm thu của BRD-004
"top set giữ đa dạng hình dạng, không chỉ chọn phương án rẻ nhất" được hiện
thực bằng một cơ chế chọn ĐỘC LẬP VỚI MỌI HÀM MỤC TIÊU: chỉ đo KHOẢNG CÁCH
HÌNH THÁI (Gower) giữa các bộ mô tả rời rạc/liên tục, rồi chọn tập trải rộng
nhất bằng greedy max-min tất định.

Module này KHÔNG tính nội lực, KHÔNG xếp hạng hiệu năng, KHÔNG phán xét
phương án nào "tốt hơn" phương án nào. Mọi kết quả mang
``claim_level = "IDEA"`` (F0 theo multiagent/PHYSICS_GATES.md): một tập
GIẢ THUYẾT hình thái để nghiên cứu tiếp, KHÔNG phải tập thiết kế. Việc một
ứng viên có mặt trong tập chọn không nói lên điều gì về kỹ thuật.

Fail-closed: đầu vào thiếu hoặc sai thì raise :class:`ShapeDiversityError`
(kế thừa ``ValueError``); không bịa giá trị mặc định, không tự sửa tham số
của người gọi. KHÔNG ngưỡng số nào được hard-code ở đây — mọi ngưỡng sàng L0
(chiều dài đốt, tải cẩu, khe hở kiểm tra...) thuộc về logistics_profile do
kỹ sư cung cấp ở nơi khác, kèm provenance.

Chiều import: module sandbox này ĐƯỢC PHÉP import từ production
(``bridge_evolution.catalogs``); chiều ngược lại — production import sandbox —
bị cấm và bị test ``test_experimental_geometry_module_is_not_imported_by_production``
canh giữ.
"""

from __future__ import annotations

import hashlib
import json
import math
from itertools import product as _cartesian_product

from bridge_evolution.catalogs import grid_domain

#: Mức claim cố định của mọi kết quả module này trả về.
CLAIM_LEVEL = "IDEA"

#: Các trạng thái sàng L0 hợp lệ của một ứng viên. ``None`` = chưa sàng.
ALLOWED_L0_STATUS = ("PASS", "FAIL", "UNKNOWN_INPUT_MISSING", None)

#: Các xuất xứ miền được phép LIỆT KÊ thành giả thuyết hình thái. Miền
#: PLACEHOLDER_PENDING_DESIGN_BASIS bị TỪ CHỐI: đó là hộp tìm kiếm tạm chưa
#: có căn cứ, liệt kê nó sẽ giả trang thành không gian thiết kế.
_TOPOLOGY_PROVENANCE_EXACT = "ENUMERATED_TOPOLOGY"
_TOPOLOGY_PROVENANCE_PREFIX = "SOURCE_"


class ShapeDiversityError(ValueError):
    """Đầu vào chọn tập đa dạng thiếu hoặc phi lý.

    Fail-closed: module KHÔNG bịa giá trị mặc định và KHÔNG "sửa nhẹ" tham số
    của người gọi. Sai thì báo sai.
    """


# ---------------------------------------------------------------------------
# Kiểm tra đầu vào
# ---------------------------------------------------------------------------

def _is_real_number(value) -> bool:
    """Số thực thật (int/float hữu hạn, không phải bool)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return math.isfinite(float(value))


def _validated_key_list(keys, name: str) -> list[str]:
    if not isinstance(keys, (list, tuple)):
        raise ShapeDiversityError(f"{name} phai la list/tuple, nhan duoc {type(keys).__name__}")
    out = []
    for key in keys:
        if not isinstance(key, str) or not key:
            raise ShapeDiversityError(f"{name} chua phan tu khong phai chuoi: {key!r}")
        out.append(key)
    if len(out) != len(set(out)):
        raise ShapeDiversityError(f"{name} co khoa trung lap: {sorted(out)}")
    return out


def _validated_candidates(candidates) -> list[dict]:
    if not isinstance(candidates, list) or not candidates:
        raise ShapeDiversityError("candidates phai la list khac rong")
    seen: set = set()
    for i, cand in enumerate(candidates):
        if not isinstance(cand, dict):
            raise ShapeDiversityError(f"candidates[{i}] khong phai dict")
        cid = cand.get("candidate_id")
        if not isinstance(cid, str) or not cid:
            raise ShapeDiversityError(f"candidates[{i}] thieu candidate_id dang chuoi khac rong")
        if cid in seen:
            raise ShapeDiversityError(f"candidate_id trung lap: {cid!r}")
        seen.add(cid)
        if not isinstance(cand.get("descriptors"), dict):
            raise ShapeDiversityError(f"{cid}: thieu khoi descriptors dang dict")
        status = cand.get("l0_status")
        if status not in ALLOWED_L0_STATUS:
            raise ShapeDiversityError(
                f"{cid}: l0_status {status!r} khong hop le; chi chap nhan {ALLOWED_L0_STATUS}"
            )
    return candidates


def _require_descriptor(cand: dict, key: str):
    descriptors = cand["descriptors"]
    if key not in descriptors:
        raise ShapeDiversityError(
            f"{cand['candidate_id']}: thieu descriptor {key!r} — khong duoc doan gia tri thay nguoi goi"
        )
    return descriptors[key]


# ---------------------------------------------------------------------------
# Khoảng cách Gower
# ---------------------------------------------------------------------------

def _numeric_ranges_for(
    valid: list[dict],
    numeric_keys: list[str],
    numeric_ranges: dict | None,
) -> tuple[dict, str]:
    """Bề rộng miền chuẩn hoá cho từng numeric key.

    Ưu tiên giá trị NGƯỜI GỌI cung cấp (``numeric_ranges``); key nào thiếu thì
    tính từ chính tập ứng viên hợp lệ (max - min). Bề rộng 0 -> đóng góp
    khoảng cách của key đó bằng 0 (quy ước Gower).
    """
    provided = dict(numeric_ranges) if numeric_ranges else {}
    for key in provided:
        if key not in numeric_keys:
            raise ShapeDiversityError(
                f"numeric_ranges co khoa {key!r} khong nam trong numeric_keys"
            )
        width = provided[key]
        if not _is_real_number(width) or float(width) < 0.0:
            raise ShapeDiversityError(
                f"numeric_ranges[{key!r}] = {width!r} — be rong mien phai la so thuc >= 0"
            )
        provided[key] = float(width)
    source = "CALLER_PROVIDED" if numeric_ranges else "COMPUTED_FROM_CANDIDATE_SET"
    if provided and len(provided) < len(numeric_keys):
        source = "MIXED_CALLER_AND_COMPUTED"
    ranges = {}
    for key in numeric_keys:
        if key in provided:
            ranges[key] = provided[key]
            continue
        values = [float(_require_descriptor(c, key)) for c in valid]
        ranges[key] = max(values) - min(values)
    return ranges, source


def _gower(
    da: dict,
    db: dict,
    categorical_keys: list[str],
    numeric_keys: list[str],
    ranges: dict,
) -> float:
    """Khoảng cách Gower giữa hai bộ descriptor, trong [0, 1]."""
    total = 0.0
    for key in categorical_keys:
        total += 0.0 if da[key] == db[key] else 1.0
    for key in numeric_keys:
        width = ranges[key]
        if width == 0.0:
            continue
        total += abs(float(da[key]) - float(db[key])) / width
    return total / (len(categorical_keys) + len(numeric_keys))


# ---------------------------------------------------------------------------
# Chọn tập đa dạng — greedy max-min tất định
# ---------------------------------------------------------------------------

def select_diverse_top_set(
    candidates: list[dict],
    k: int,
    *,
    categorical_keys: list[str],
    numeric_keys: list[str] = (),
    numeric_ranges: dict | None = None,
    coverage_quota: dict | None = None,
    seed_index: int = 0,
) -> dict:
    """Chọn ``k`` ứng viên trải rộng nhất về HÌNH THÁI — không hàm mục tiêu.

    Cơ chế (tất định, không random):

    1. Loại trước mọi ứng viên ``l0_status == "FAIL"`` (ghi vào
       ``excluded_l0_fail``). Ứng viên ``UNKNOWN_INPUT_MISSING`` được GIỮ
       nhưng gắn cờ trong ``unknown_l0_included``; ứng viên ``None`` (chưa
       sàng) được giữ và liệt kê trong ``unscreened_l0_included``.
    2. Khoảng cách Gower: categorical -> 0/1 mismatch; numeric ->
       ``|a - b| / range`` với range do NGƯỜI GỌI cung cấp qua
       ``numeric_ranges`` (bề rộng miền, >= 0) hoặc tính từ tập hợp lệ;
       range 0 -> đóng góp 0.
    3. Greedy max-min (farthest-first) bắt đầu từ ``candidates[seed_index]``;
       hoà thì chọn ``candidate_id`` NHỎ HƠN theo thứ tự chuỗi.
    4. ``coverage_quota`` (vd ``{"arch_axis_type": 2}``): sau greedy, nếu một
       khoá chưa đủ số GIÁ TRỊ PHÂN BIỆT thì hoán đổi phần tử có đóng góp đa
       dạng thấp nhất bằng ứng viên mang giá trị còn thiếu; không thể thoả thì
       ghi rõ trong ``quota_unmet`` thay vì im lặng.

    Fail-closed (raise :class:`ShapeDiversityError`): ``k < 1``; ``k`` lớn hơn
    số ứng viên hợp lệ sau khi loại FAIL; ứng viên thiếu descriptor;
    ``seed_index`` ngoài phạm vi hoặc trỏ vào ứng viên FAIL; quota lớn hơn
    ``k`` (không thể thoả theo nguyên lý ngăn kéo — người gọi phải biết).

    Kết quả KHÔNG chứa bất kỳ đại lượng hiệu năng nào: giá trị số duy nhất là
    ``min_pairwise_distance`` (khoảng cách hình thái nhỏ nhất trong tập chọn;
    ``None`` khi ``k == 1``). ``claim_level = "IDEA"``.
    """
    _validated_candidates(candidates)
    categorical = _validated_key_list(categorical_keys, "categorical_keys")
    numeric = _validated_key_list(numeric_keys, "numeric_keys")
    if not categorical and not numeric:
        raise ShapeDiversityError("phai co it nhat mot descriptor key (categorical hoac numeric)")
    overlap = set(categorical) & set(numeric)
    if overlap:
        raise ShapeDiversityError(f"khoa vua categorical vua numeric: {sorted(overlap)}")
    if isinstance(k, bool) or not isinstance(k, int):
        raise ShapeDiversityError(f"k phai la so nguyen, nhan duoc {k!r}")
    if k < 1:
        raise ShapeDiversityError(f"k = {k} < 1 — khong co gi de chon")
    if isinstance(seed_index, bool) or not isinstance(seed_index, int):
        raise ShapeDiversityError(f"seed_index phai la so nguyen, nhan duoc {seed_index!r}")
    if not (0 <= seed_index < len(candidates)):
        raise ShapeDiversityError(
            f"seed_index = {seed_index} ngoai pham vi [0, {len(candidates) - 1}]"
        )

    excluded_l0_fail = [c["candidate_id"] for c in candidates if c.get("l0_status") == "FAIL"]
    valid = [c for c in candidates if c.get("l0_status") != "FAIL"]
    if k > len(valid):
        raise ShapeDiversityError(
            f"k = {k} lon hon so ung vien hop le sau khi loai FAIL ({len(valid)}). "
            "Nguoi goi phai biet dieu nay thay vi nhan ve mot tap nho hon trong im lang."
        )
    seed_id = candidates[seed_index]["candidate_id"]
    if seed_id in excluded_l0_fail:
        raise ShapeDiversityError(
            f"candidates[{seed_index}] = {seed_id!r} co l0_status == FAIL — khong lam seed duoc; "
            "chon seed_index khac"
        )

    # Kiểm đủ descriptor cho MỌI ứng viên hợp lệ trước khi tính bất kỳ khoảng cách nào.
    all_keys = categorical + numeric
    desc: dict = {}
    for cand in valid:
        for key in all_keys:
            value = _require_descriptor(cand, key)
            if key in numeric and not _is_real_number(value):
                raise ShapeDiversityError(
                    f"{cand['candidate_id']}: descriptor {key!r} = {value!r} khong phai so thuc"
                )
        desc[cand["candidate_id"]] = cand["descriptors"]

    ranges, ranges_source = _numeric_ranges_for(valid, numeric, numeric_ranges)

    def dist(id_a: str, id_b: str) -> float:
        return _gower(desc[id_a], desc[id_b], categorical, numeric, ranges)

    # Quota: kiểm hợp lệ trước khi chọn.
    quota = dict(coverage_quota) if coverage_quota else {}
    for qkey in quota:
        if qkey not in categorical:
            raise ShapeDiversityError(
                f"coverage_quota co khoa {qkey!r} khong nam trong categorical_keys"
            )
        qval = quota[qkey]
        if isinstance(qval, bool) or not isinstance(qval, int) or qval < 1:
            raise ShapeDiversityError(
                f"coverage_quota[{qkey!r}] = {qval!r} — quota phai la so nguyen >= 1"
            )
        if qval > k:
            raise ShapeDiversityError(
                f"coverage_quota[{qkey!r}] = {qval} > k = {k} — khong the thoa theo "
                "nguyen ly ngan keo; nguoi goi phai sua quota hoac k"
            )

    # 3. Greedy max-min, tất định.
    selected = [seed_id]
    remaining = sorted(cid for cid in desc if cid != seed_id)
    while len(selected) < k:
        best_id = None
        best_d = -1.0
        for cid in remaining:  # duyệt theo thứ tự chuỗi tăng dần -> hoà giữ id nhỏ hơn
            d_min = min(dist(cid, sid) for sid in selected)
            if d_min > best_d:
                best_d = d_min
                best_id = cid
        selected.append(best_id)
        remaining.remove(best_id)

    # 4. Hoán đổi để thoả coverage_quota (nếu có), vẫn tất định.
    def distinct_values(ids: list[str], key: str) -> set:
        return {desc[cid][key] for cid in ids}

    quota_unmet: list[dict] = []
    for qkey in sorted(quota):
        required = quota[qkey]
        while len(distinct_values(selected, qkey)) < required:
            have = distinct_values(selected, qkey)
            pool = [cid for cid in sorted(remaining) if desc[cid][qkey] not in have]
            if not pool:
                quota_unmet.append({
                    "key": qkey,
                    "required": required,
                    "achieved": len(have),
                    "reason_vi": "Khong con ung vien hop le nao mang gia tri con thieu cua khoa nay.",
                })
                break
            incoming = None
            incoming_d = -1.0
            for cid in pool:  # hoà -> id nhỏ hơn (duyệt tăng dần, so sánh chặt)
                d_min = min(dist(cid, sid) for sid in selected)
                if d_min > incoming_d:
                    incoming_d = d_min
                    incoming = cid
            # Ứng viên bị đưa ra: giá trị của nó tại qkey phải đang LẶP (để số giá trị
            # phân biệt của qkey không giảm) và việc bỏ nó không phá quota nào khác.
            value_counts: dict = {}
            for cid in selected:
                value_counts[desc[cid][qkey]] = value_counts.get(desc[cid][qkey], 0) + 1
            eligible = []
            for out_id in selected:
                if value_counts[desc[out_id][qkey]] < 2:
                    continue
                trial = [cid for cid in selected if cid != out_id] + [incoming]
                breaks_other = False
                for other_key, other_req in quota.items():
                    achieved_now = len(distinct_values(selected, other_key))
                    achieved_trial = len(distinct_values(trial, other_key))
                    if achieved_trial < min(other_req, achieved_now) and other_key != qkey:
                        breaks_other = True
                        break
                if not breaks_other:
                    eligible.append(out_id)
            if not eligible:
                quota_unmet.append({
                    "key": qkey,
                    "required": required,
                    "achieved": len(have),
                    "reason_vi": "Moi hoan doi kha dung deu pha quota cua khoa khac.",
                })
                break
            outgoing = None
            outgoing_d = None
            for out_id in sorted(eligible):  # hoà -> id nhỏ hơn bị đưa ra
                others = [cid for cid in selected if cid != out_id]
                d_min = min(dist(out_id, oid) for oid in others)
                if outgoing_d is None or d_min < outgoing_d:
                    outgoing_d = d_min
                    outgoing = out_id
            selected.remove(outgoing)
            remaining.append(outgoing)
            remaining.sort()
            selected.append(incoming)
            remaining.remove(incoming)

    # Ghi nhận quota chưa thoả còn sót (không entry trùng khoá).
    reported = {entry["key"] for entry in quota_unmet}
    for qkey in sorted(quota):
        achieved = len(distinct_values(selected, qkey))
        if achieved < quota[qkey] and qkey not in reported:
            quota_unmet.append({
                "key": qkey,
                "required": quota[qkey],
                "achieved": achieved,
                "reason_vi": "Quota chua thoa sau khi het cach hoan doi.",
            })

    if len(selected) >= 2:
        min_pairwise = min(
            dist(selected[i], selected[j])
            for i in range(len(selected))
            for j in range(i + 1, len(selected))
        )
    else:
        min_pairwise = None  # k == 1: không có cặp nào để đo

    coverage = {
        key: {}
        for key in categorical
    }
    for key in categorical:
        for cid in selected:
            value = desc[cid][key]
            coverage[key][value] = coverage[key].get(value, 0) + 1

    status_by_id = {c["candidate_id"]: c.get("l0_status") for c in candidates}
    return {
        "claim_level": CLAIM_LEVEL,
        "selection_is_objective_free": True,
        "statement_vi": (
            "Tap chon chi phan anh DA DANG HINH THAI (khoang cach Gower, greedy "
            "max-min tat dinh), khong phai xep hang hieu nang: runtime khong co "
            "solver nao cho ho vom va khong ham muc tieu nao duoc dung. Muc claim "
            "F0 IDEA — viec mot ung vien duoc chon khong noi len dieu gi ve ky thuat."
        ),
        "k": k,
        "valid_candidate_count": len(valid),
        "selected": list(selected),
        "selected_descriptors": [dict(desc[cid]) for cid in selected],
        "selected_l0_status": {cid: status_by_id[cid] for cid in selected},
        "min_pairwise_distance": min_pairwise,
        "coverage": coverage,
        "quota_unmet": quota_unmet,
        "excluded_l0_fail": excluded_l0_fail,
        "unknown_l0_included": [
            cid for cid in selected if status_by_id[cid] == "UNKNOWN_INPUT_MISSING"
        ],
        "unscreened_l0_included": [cid for cid in selected if status_by_id[cid] is None],
        "numeric_ranges_used": ranges,
        "numeric_ranges_source": ranges_source,
    }


# ---------------------------------------------------------------------------
# Liệt kê giả thuyết hình thái từ grammar
# ---------------------------------------------------------------------------

def enumerate_topology_hypotheses(grammar: dict, keys: list[str]) -> list[dict]:
    """Tích Descartes các miền HÌNH THÁI đã liệt kê của grammar.

    Chỉ chấp nhận ``design_variables`` có ``domain_provenance`` bằng
    ``"ENUMERATED_TOPOLOGY"`` hoặc bắt đầu bằng ``"SOURCE_"`` — tức miền do
    LIỆT KÊ topo hoặc do nguồn đã lập chỉ mục chống lưng. Miền
    ``PLACEHOLDER_PENDING_DESIGN_BASIS`` (hộp tìm kiếm tạm chưa có căn cứ) và
    ``NON_INDEXED_SOURCE`` bị TỪ CHỐI: liệt kê chúng sẽ giả trang một hộp số
    tuỳ tiện thành không gian thiết kế.

    Mỗi phần tử trả về::

        {"candidate_id": "HYP-<16 hex sha256>", "descriptors": {...}, "l0_status": None}

    với hash lấy trên JSON chính tắc của descriptors theo ĐÚNG quy ước
    ``canonical_json`` của production (bridge_evolution/state.py):
    ``json.dumps(sort_keys=True, separators=(",", ":"), ensure_ascii=False)``.

    Đây là TẬP GIẢ THUYẾT HÌNH THÁI mức F0 IDEA, KHÔNG phải tập thiết kế:
    hàm này KHÔNG áp các ràng buộc ghép cặp (vd ``lateral_bracing_system``
    x ``arch_rib_count``) — việc đó thuộc sàng L0 với ngưỡng và quy tắc do
    kỹ sư cung cấp.
    """
    if not isinstance(grammar, dict) or not isinstance(grammar.get("design_variables"), dict):
        raise ShapeDiversityError("grammar phai la dict co khoi design_variables")
    key_list = _validated_key_list(keys, "keys")
    if not key_list:
        raise ShapeDiversityError("keys rong — khong co gi de liet ke")
    variables = grammar["design_variables"]
    domains = []
    for key in key_list:
        if key not in variables:
            raise ShapeDiversityError(f"design_variables khong co bien {key!r}")
        spec = variables[key]
        provenance = spec.get("domain_provenance")
        is_topology = provenance == _TOPOLOGY_PROVENANCE_EXACT or (
            isinstance(provenance, str) and provenance.startswith(_TOPOLOGY_PROVENANCE_PREFIX)
        )
        if not is_topology:
            raise ShapeDiversityError(
                f"{key}: domain_provenance = {provenance!r} khong phai mien hinh thai "
                "liet ke duoc (can ENUMERATED_TOPOLOGY hoac SOURCE_*). Mien placeholder "
                "phai co design basis truoc, khong duoc liet ke thanh gia thuyet."
            )
        domains.append(grid_domain(spec))
    hypotheses = []
    for combo in _cartesian_product(*domains):
        descriptors = dict(zip(key_list, combo))
        canonical = json.dumps(
            descriptors, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        )
        candidate_id = "HYP-" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
        hypotheses.append({
            "candidate_id": candidate_id,
            "descriptors": descriptors,
            "l0_status": None,
        })
    return hypotheses
