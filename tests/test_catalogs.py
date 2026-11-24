"""Cách ly sandbox phải là BẤT BIẾN ĐƯỢC THỰC THI, không phải tính chất tình cờ.

`bridge_grammar/experimental/` chứa họ kết cấu mà runtime KHÔNG có solver (vòm),
ở mức claim IDEA. Trước BRD-022, `load_grammar("experimental/arch_deck_v1")` nạp
được và `gene_order()`/`gene_domains()` chạy trơn trên nó; đường sinh số chỉ dừng
ở `BudgetedEvaluator` bằng một `KeyError 'girder_concrete_id'` — tức bằng TAI NẠN.
Thêm một giá trị mặc định ở đúng chỗ đó là hàng rào biến mất trong im lặng.

Các test dưới đây ĐỎ trên bản chưa vá.
"""
import json

import pytest

from bridge_evolution import GRAMMAR_DIR
from bridge_evolution.catalogs import all_domains, grid_domain, load_catalogs, load_grammar

try:  # bản CHƯA vá không có lớp lỗi riêng
    from bridge_evolution.catalogs import GrammarIdError
except ImportError:  # pragma: no cover — chỉ xảy ra trên bản chưa vá
    GrammarIdError = None

SANDBOX_ID = "experimental/arch_deck_v1"


def assert_refused(grammar_id):
    """Khẳng định loader TỪ CHỐI, và ĐỎ chứ không lỗi-collection trên bản chưa vá.

    Import `GrammarIdError` ở cấp module sẽ làm cả file không collect được trên
    bản chưa vá — khi đó pytest báo lỗi thu thập, không phải một test đỏ nói rõ
    hàng rào còn thiếu. Đi qua helper này thì bản chưa vá cho **failure có thông
    điệp**, đúng yêu cầu "test tái hiện lỗ hổng phải ĐỎ trên bản chưa vá".
    """
    if GrammarIdError is None:
        pytest.fail(
            "bridge_evolution.catalogs.GrammarIdError không tồn tại — loader chưa có "
            f"hàng rào riêng, nên {grammar_id!r} vẫn đi xuyên được vào sandbox"
        )
    with pytest.raises(GrammarIdError):
        load_grammar(grammar_id)


def test_production_grammar_still_loads():
    grammar = load_grammar("super_t_simple_v1")
    assert grammar["design_variables"]
    assert load_grammar()["design_variables"], "grammar mặc định phải nạp được"


def test_sandbox_grammar_is_refused_by_the_loader():
    """Chính lỗ hổng BRD-022 mô tả — phải ĐỎ trên bản chưa vá."""
    assert_refused(SANDBOX_ID)


@pytest.mark.parametrize(
    "grammar_id",
    [
        "experimental/arch_deck_v1",
        "experimental\\arch_deck_v1",       # biến thể Windows
        "./experimental/arch_deck_v1",
        ".\\experimental\\arch_deck_v1",
        "../bridge_grammar/super_t_simple_v1",
        "..\\bridge_grammar\\super_t_simple_v1",
        "..",
        "sub/dir/name",
        "D:\\BIM\\anything",                # đường dẫn tuyệt đối Windows
        "/etc/passwd",                      # đường dẫn tuyệt đối POSIX
        "\\\\server\\share\\grammar",       # UNC
        "super_t_simple_v1.json",           # có đuôi -> sinh ra .json.json
        "",
    ],
)
def test_every_path_shaped_id_is_refused(grammar_id):
    assert_refused(grammar_id)


def test_refusal_names_the_reason_not_a_bare_missing_file():
    """FileNotFoundError chung chung không nói được vì sao — người đọc log sẽ tưởng thiếu file."""
    if GrammarIdError is None:
        pytest.fail("loader chưa có lớp lỗi riêng để nói lý do")
    with pytest.raises(GrammarIdError) as excinfo:
        load_grammar(SANDBOX_ID)
    message = str(excinfo.value)
    assert "grammar_id" in message
    assert "sandbox" in message.lower()


def test_non_string_id_is_refused():
    if GrammarIdError is None:
        pytest.fail("loader chưa có lớp lỗi riêng")
    for bad in (None, 3, ["super_t_simple_v1"]):
        with pytest.raises(GrammarIdError):
            load_grammar.__wrapped__(bad)


def test_missing_but_well_formed_id_still_raises_file_not_found():
    """Tên hợp lệ mà không có tệp vẫn là FileNotFoundError — hai lỗi khác nhau."""
    with pytest.raises(FileNotFoundError):
        load_grammar("khong_ton_tai_v9")


def test_sandbox_grammar_file_is_still_there_untouched():
    """Không được 'sửa' lỗ hổng bằng cách xoá/đổi sandbox — cái sai nằm ở loader."""
    sandbox = GRAMMAR_DIR / "experimental" / "arch_deck_v1.json"
    assert sandbox.is_file()
    data = json.loads(sandbox.read_text(encoding="utf-8"))
    assert data["claim_level"] == "IDEA"


def test_gene_helpers_cannot_reach_the_sandbox_anymore():
    """Đường sinh số phải bị chặn ở loader, không phải ở KeyError cuối đường."""
    from bridge_evolution.optimization.common import gene_domains, gene_order

    if GrammarIdError is None:
        pytest.fail("loader chưa có hàng rào — đường sinh số vẫn chạm được sandbox")
    with pytest.raises(GrammarIdError):
        gene_order(SANDBOX_ID)
    with pytest.raises(GrammarIdError):
        gene_domains(SANDBOX_ID)


def test_catalogs_load_and_expose_rule_profiles():
    catalogs = load_catalogs()
    assert catalogs["catalogs_version"]
    assert catalogs["rule_profiles"], "rule_profiles là nơi mọi ngưỡng có provenance"


def test_domain_helpers_reject_unknown_variable_type():
    assert grid_domain({"type": "int", "domain": [5, 6]}) == [5, 6]
    assert grid_domain({"type": "grid", "min": 2, "max": 6, "step": 2}) == [2, 4, 6]
    with pytest.raises(ValueError):
        grid_domain({"type": "khong_ho_tro"})
    assert set(all_domains(load_grammar("super_t_simple_v1"))) == set(
        load_grammar("super_t_simple_v1")["design_variables"]
    )
