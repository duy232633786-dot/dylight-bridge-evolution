"""BridgeDesignState: validate contract, hash provenance, sinh state từ grammar."""
import hashlib
import json
from functools import lru_cache

import jsonschema

from . import CONTRACTS_DIR
from .catalogs import all_domains, load_catalogs, load_grammar


# 64 bit của SHA-256 đủ lớn cho namespace candidate hiện tại và loại
# collision đã quan sát khi chỉ dùng 8 hex (32 bit). Toàn bộ hash vẫn được
# lưu trong provenance.
CASE_ID_HASH_HEX = 16

_FIDELITY_SOLVERS = {
    "L1_LINE_GIRDER": {"BUILTIN_L1"},
    "L2_GRILLAGE": {"MIDAS_CIVIL", "OPENSEESPY"},
    "L3_NONLINEAR": {"MIDAS_CIVIL"},
}

_CATALOG_REFS = {
    ("design_variables", "girder_catalog_id"): "girder_sections",
    ("design_variables", "diaphragm_layout_id"): "diaphragm_layouts",
    ("design_variables", "prestress_layout_id"): "prestress_layouts",
    ("materials", "girder_concrete_id"): "concretes",
    ("materials", "deck_concrete_id"): "concretes",
    ("materials", "prestressing_steel_id"): "prestressing_steels",
    ("analysis", "load_profile_id"): "load_profiles",
    ("constraints", "rule_profile_id"): "rule_profiles",
}


@lru_cache(maxsize=None)
def _schema(name: str) -> dict:
    with open(CONTRACTS_DIR / name, encoding="utf-8") as f:
        return json.load(f)


def validate_design_state(state: dict) -> list[str]:
    """Trả về lỗi schema + semantic contract; không raise do input.

    JSON Schema chặn sai kiểu/cấu trúc. Các kiểm tra bên dưới khóa
    phạm vi dự án, miền grammar, tham chiếu catalog và cặp fidelity/solver
    trước khi code hình học có thể dereference các ID đó.
    """
    validator = jsonschema.Draft202012Validator(_schema("bridge_design_state.schema.json"))
    errors = [f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}"
              for e in validator.iter_errors(state)]
    if errors:
        return errors

    # Từ đây state đã đúng shape/type theo schema, nên có thể truy cập
    # an toàn mà không biến input xấu thành KeyError/TypeError.
    try:
        grammar = load_grammar(state["family"])
        catalogs = load_catalogs()
        domains = all_domains(grammar)
    except (KeyError, OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        return [f"family: không nạp được grammar/catalog: {exc}"]

    for name, expected in grammar["project_inputs"].items():
        actual = state["project_inputs"].get(name)
        if actual != expected:
            errors.append(
                f"project_inputs/{name}: {actual!r} khác giá trị cố định {expected!r}"
            )

    fidelity = state["analysis"]["fidelity"]
    solver = state["analysis"]["solver"]
    if solver not in _FIDELITY_SOLVERS.get(fidelity, set()):
        allowed = ", ".join(sorted(_FIDELITY_SOLVERS.get(fidelity, set()))) or "không có"
        errors.append(
            f"analysis/solver: {solver!r} không tương thích {fidelity!r}; "
            f"solver cho phép: {allowed}"
        )

    # Các ID cố định của grammar không phải biến tối ưu.
    fixed_paths = {
        ("materials", "prestressing_steel_id"): "prestressing_steel_id",
        ("analysis", "load_profile_id"): "load_profile_id",
        ("constraints", "rule_profile_id"): "rule_profile_id",
    }
    for (section, name), fixed_name in fixed_paths.items():
        actual = state[section][name]
        expected = grammar["fixed"][fixed_name]
        if actual != expected:
            errors.append(
                f"{section}/{name}: {actual!r} khác giá trị cố định {expected!r}"
            )

    # Xác minh mọi tham chiếu trước khi geometry/solver/objectives dùng []
    # để tra catalog.
    for (section, name), catalog_name in _CATALOG_REFS.items():
        value = state[section][name]
        if value not in catalogs.get(catalog_name, {}):
            errors.append(f"{section}/{name}: ID catalog không tồn tại: {value!r}")

    # Grammar v2 khai thêm 6 biến hình dạng mặt cắt; schema để chúng TÙY CHỌN nên
    # state v1 vẫn hợp lệ. Ở đây dùng sentinel thay vì [] để một biến grammar bị
    # thiếu thành lỗi contract có thông báo rõ, không phải KeyError.
    material_vars = {"girder_concrete_id", "deck_concrete_id"}
    for name, domain in domains.items():
        section = "materials" if name in material_vars else "design_variables"
        if name not in state[section]:
            errors.append(f"{section}/{name}: thiếu biến bắt buộc của grammar "
                          f"{state['family']!r}")
            continue
        value = state[section][name]
        if value in domain:
            continue

        # Tiết diện kỳ dị chỉ tồn tại để gold case xác minh nhánh
        # NOT_CONVERGED. Không cho candidate thông thường dùng test fixture.
        is_solver_fixture = (
            name == "girder_catalog_id"
            and catalogs.get("girder_sections", {}).get(value, {}).get("test_only") is True
            and state.get("provenance", {}).get("generation_action") == "GOLD_CASE"
        )
        if not is_solver_fixture:
            errors.append(f"{section}/{name}: {value!r} nằm ngoài miền grammar")

    return errors


def validate_evaluation_result(result: dict) -> list[str]:
    validator = jsonschema.Draft202012Validator(_schema("evaluation_result.schema.json"))
    return [e.message for e in validator.iter_errors(result)]


def canonical_json(state) -> str:
    """JSON chuẩn hóa (bỏ provenance/case_id/status) — cơ sở cho input_hash."""
    if isinstance(state, dict):
        core = {k: v for k, v in state.items()
                if k not in ("provenance", "case_id", "status")}
    else:
        core = state
    return json.dumps(core, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def input_hash(state) -> str:
    return hashlib.sha256(canonical_json(state).encode("utf-8")).hexdigest()


def make_case_id(state) -> str:
    """ID ổn định 64-bit; full SHA-256 trong provenance là định danh chuẩn."""
    return "BT-" + input_hash(state)[:CASE_ID_HASH_HEX]


def new_state(design_variables: dict, *, girder_concrete_id: str, deck_concrete_id: str,
              grammar_id: str = "super_t_simple_v1", parent_id: str | None = None,
              generation_action: str = "INITIAL", seed: int | None = None) -> dict:
    """Sinh BridgeDesignState đầy đủ từ grammar + bộ biến thiết kế."""
    g = load_grammar(grammar_id)
    state = {
        "family": g["grammar_id"],
        "status": "CANDIDATE",
        "project_inputs": dict(g["project_inputs"]),
        "design_variables": dict(design_variables),
        "materials": {
            "girder_concrete_id": girder_concrete_id,
            "deck_concrete_id": deck_concrete_id,
            "prestressing_steel_id": g["fixed"]["prestressing_steel_id"],
        },
        "analysis": {
            "fidelity": g["fixed"]["fidelity"],
            "solver": g["fixed"]["solver"],
            "load_profile_id": g["fixed"]["load_profile_id"],
        },
        "constraints": {"rule_profile_id": g["fixed"]["rule_profile_id"]},
        "provenance": {
            "random_seed": seed,
            "parent_candidate_id": parent_id,
            "generation_action": generation_action,
        },
    }
    state["case_id"] = make_case_id(state)
    return state


def state_from_gene(gene: dict, grammar_id: str = "super_t_simple_v1", **kw) -> dict:
    """Gene của EA/RL = dict {tên biến: giá trị} gồm cả 2 biến vật liệu."""
    gene = dict(gene)
    girder_conc = gene.pop("girder_concrete_id")
    deck_conc = gene.pop("deck_concrete_id")
    return new_state(gene, girder_concrete_id=girder_conc, deck_concrete_id=deck_conc,
                     grammar_id=grammar_id, **kw)
