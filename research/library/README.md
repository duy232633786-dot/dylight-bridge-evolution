# Chỉ mục thư viện tài liệu kỹ thuật cục bộ

> ⚠ **ĐÂY LÀ THƯ VIỆN THAM KHẢO UNVERIFIED.** Theo `multiagent/PROTOCOL.md`
> quy tắc 6, thư viện tham khảo **không phải bằng chứng kỹ thuật**. Sự tồn tại
> của một bản vẽ hay một tài liệu trong bảng dưới đây KHÔNG chứng minh bất kỳ
> con số nào. Muốn biến một điều trong đây thành rule của runtime thì phải mở
> đúng tài liệu, dẫn đúng điều khoản, thêm test và có kỹ sư duyệt.

> ⚠ **KHÔNG ĐƯỢC SUY SỐ LIỆU KỸ THUẬT TỪ TÊN FILE.** Trường `reason` chỉ ghi
> lại từ khóa đã khớp trong đường dẫn; `runtime_link` chỉ là **gợi ý chưa ai
> xác nhận**. Chưa file nào trong chỉ mục này được mở ra đọc.

Task **BRD-021** · claim ceiling **IDEA** · hợp đồng
`contracts/local_document_index.schema.json`.

## Bản quyền và quyền riêng tư

Chỉ mục ghi **vị trí và siêu dữ liệu** (đường dẫn, kích thước, sha256, ngày
sửa). Nó **không sao chép nội dung** của bất kỳ tài liệu có bản quyền nào, và
bộ quét **chỉ đọc**: không copy, không di chuyển, không đổi tên, không xoá,
không giải mã file đặt mật khẩu. File khớp từ khóa tài liệu cá nhân bị loại
khỏi chỉ mục dự án và chỉ để lại đường dẫn cùng lý do trong `skipped`.

## Lần quét đang được ghi

| Trường | Giá trị |
|---|---|
| Bộ quét | `local-document-index/1` |
| Bắt đầu (UTC) | 2026-08-26T04:57:17Z |
| Kết thúc (UTC) | 2026-08-26T04:57:26Z |
| Gốc quét | `D:/` |
| Đuôi file trong phạm vi | `dwg`, `dxf`, `pdf`, `xls`, `xlsm`, `xlsx` |
| File đã duyệt qua | 18275 |
| **Tài liệu trong chỉ mục** | **263** |
| Tổng dung lượng tài liệu | 304.2 MB |
| Bị loại có ghi lý do | 1 |
| Không đọc được | 2 |
| Đã có bản sao trong vault Obsidian | 233 |
| sha256 chỉ là một phần (file lớn) | 3 |

### Theo mức liên quan tới runtime

| Nhóm | Số tài liệu | Tỷ lệ |
|---|---:|---:|
| `UNRELATED` | 216 | 82.1% |
| `DIRECT` | 34 | 12.9% |
| `ADJACENT` | 13 | 4.9% |

### Theo loại tài liệu

| Nhóm | Số tài liệu | Tỷ lệ |
|---|---:|---:|
| `DRAWING` | 216 | 82.1% |
| `SPREADSHEET` | 38 | 14.4% |
| `REPORT_PDF` | 9 | 3.4% |

### Theo đuôi file

| Nhóm | Số tài liệu | Tỷ lệ |
|---|---:|---:|
| `dwg` | 215 | 81.7% |
| `xlsx` | 27 | 10.3% |
| `pdf` | 9 | 3.4% |
| `xls` | 6 | 2.3% |
| `xlsm` | 5 | 1.9% |
| `dxf` | 1 | 0.4% |

### Theo ổ đĩa

| Nhóm | Số tài liệu | Tỷ lệ |
|---|---:|---:|
| `D:` | 263 | 100.0% |

## Tài liệu có gợi ý chạm tới runtime

8/263 tài liệu có ít nhất một `runtime_link`; 34 tài liệu ở mức `DIRECT`.

**`runtime_link` là gợi ý theo từ khóa, chưa ai mở file để xác nhận.**
Nó chỉ nói "chỗ này trong repo có thể liên quan", không nói tài liệu chứa
số dùng được.

| document_id | File | Gợi ý runtime |
|---|---|---|
| `DOC-00192` | FB-MultiPier.pdf | `docs/runtime_capability_matrix.json (cấu kiện ngoài phạm vi L1 line-girder)` |
| `DOC-00222` | Bridge_Pier_Verification_Calculation.xlsx | `docs/runtime_capability_matrix.json (cấu kiện ngoài phạm vi L1 line-girder)` |
| `DOC-00227` | FRP_Calculation_Prestressed_RC_I-Girder.xlsx | `bridge_evolution/verifier/rules.py::SERV-001` |
| `DOC-00235` | Trụ T1 - XM.xlsm | `docs/runtime_capability_matrix.json (cấu kiện ngoài phạm vi L1 line-girder)` |
| `DOC-00236` | Trụ T2 - XM.xlsm | `docs/runtime_capability_matrix.json (cấu kiện ngoài phạm vi L1 line-girder)` |
| `DOC-00239` | 03. TM DAM SUPERT-23.95M.xlsx | `catalogs/catalogs.json::girder_sections (A, I, y_b hiện là PLACEHOLDER)` |
| `DOC-00245` | Trụ T2.xlsm | `docs/runtime_capability_matrix.json (cấu kiện ngoài phạm vi L1 line-girder)` |
| `DOC-00262` | VN-MS-Pier Shaft MS-P3.pdf | `docs/runtime_capability_matrix.json (cấu kiện ngoài phạm vi L1 line-girder)` |

## Dựng lại chỉ mục

```python
from bridge_evolution.knowledge import local_library as lib

index = lib.build_document_index(['D:/'])
lib.write_document_index(index, "research/library/index.json")
open("research/library/README.md", "w", encoding="utf-8").write(lib.render_library_readme(index))
```

Chạy lại trên cùng cây thư mục cho cùng `documents`; chỉ hai mốc thời gian
quét thay đổi. Chỉ mục **chưa** có lệnh CLI riêng: `bridge_evolution/cli.py`
nằm ngoài `write_scope` của BRD-021, nên việc mở lệnh phải là một task khác.

## Cái chỉ mục này KHÔNG làm

- Không mở, không đọc nội dung, không OCR, không trích số từ bản vẽ.
- Không nâng bất kỳ claim nào. Trần claim toàn dự án vẫn là `SCREENED`;
  riêng thư viện tham khảo này ở mức `IDEA`.
- Không sửa `catalogs/`. Các giá trị `A`, `I`, `y_b` của tiết diện Super-T
  vẫn là PLACEHOLDER cho tới khi một kỹ sư mở đúng bản vẽ và ký xác nhận.
