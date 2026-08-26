"""Hồ sơ site: địa chất, thuỷ văn, gió, động đất, exposure — đầu vào của G0.

Module này KHÔNG nâng claim của bất cứ thứ gì. Nó chỉ trả lời một câu duy nhất:
*dữ liệu site có đủ để rule hạ nguồn chạy hợp lệ hay không*, và khi không đủ thì
nói đích danh trường nào thiếu. Trường `UNKNOWN` không bao giờ được điền bằng giả
định ngầm — đó là nguyên tắc hole-map của DYLIGHT và cũng là điều
`tests/test_design_basis.py::test_no_fabricated_site_data` được viết ra để cấm.
"""
from .spec import (  # noqa: F401
    SITE_READINESS_RULE,
    SiteDataError,
    borehole_layer_at,
    evidence,
    load_site_profile,
    n60,
    required_site_fields,
    check_site_readiness,
    site_binding,
)
