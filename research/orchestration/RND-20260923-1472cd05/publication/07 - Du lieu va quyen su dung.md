# Quy ước dữ liệu và quyền sử dụng

Mỗi hồ sơ có ID, tiêu đề, cơ quan/tác giả, năm nếu xác minh được, URL gốc, DOI nếu có, quốc gia/phạm vi, chủ đề, mức truy cập, mức đọc, vị trí đọc, tóm tắt, giới hạn và liên hệ dự án. Mọi hồ sơ giữ `UNVERIFIED_REFERENCE`, trần `IDEA`; không có quy tắc nào tự động được đưa vào bộ tính.

| Trạng thái | Ý nghĩa |
|---|---|
| SELECTED_SECTIONS_READ | Đã đọc các phần được chỉ rõ; không có nghĩa đọc hết tài liệu |
| ABSTRACT_READ | Chỉ đọc tóm tắt; kết quả và phương pháp chưa đối chiếu toàn văn |
| OFFICIAL_PAGE_READ | Đọc trang cơ quan, dự án hoặc tài liệu phần mềm |
| METADATA_ONLY | Thư mục/chỉ mục; không dùng suy ra nội dung kỹ thuật |
| BLOCKED | Lần mở trực tiếp thất bại; vị trí đọc nói rõ nếu chỉ có chỉ mục |

Tệp PDF tải thành công được kiểm chữ ký, parse số trang và băm SHA-256. Số trang là quy mô tài liệu đã lưu, không phải khối lượng đã đọc. Các bản TCVN có sẵn được liên kết tại chỗ; không tạo thêm bản sao.

Đầu ra có [corpus JSON](Data/corpus.json), [từng hồ sơ JSONL](Data/sources.jsonl) và [sổ tệp tải](Data/downloads.json). Mã xây gói chỉ phục vụ tổ chức tài liệu, không phải thuật toán sáng chế.

## Khi bổ sung Family Revit sau này

Một hồ sơ Family nên có nguồn và quyền sử dụng; tên/phiên bản Revit; loại cấu kiện; tham số và đơn vị; hệ trục; hình học; vật liệu; kiểu liên kết; bản vẽ/tính toán liên quan; giới hạn áp dụng. Đợt này chưa trích xuất hoặc gắn nhãn bất kỳ Family nào.

Chưa xây tập dữ liệu huấn luyện. Quyền đọc/tải không tự động bao gồm tái phân phối, thu nạp toàn văn hoặc huấn luyện mô hình. Với tiêu chuẩn trả phí, giữ thư mục và liên kết; riêng AASHTO được gắn cờ hạn chế dùng với AI theo thông báo của nhà xuất bản. [[DYLIGHT Bridge Evolution/Literature/SAGE-EvoBridge Research 2026-09-23/Sources/ST-001|ST-001]]

## Liên hệ kho hiện có

Đã đối chiếu với 234 hồ sơ trong chỉ mục cũ theo DOI, tiêu đề chuẩn hóa hoặc URL. Các trường chưa khớp chính xác chỉ được ghi là chưa tìm thấy khớp; không khẳng định đều là tài liệu mới hoàn toàn. Những đánh giá nội dung của kho cũ không được tự động kế thừa vào bộ mới.

Quốc gia trong ghi chú phản ánh phạm vi nguồn, nơi công trình hoặc cơ quan tác giả đã xác minh; không phải quốc tịch tác giả. `European Union` và `International` không được tính là quốc gia.

[[DYLIGHT Bridge Evolution/Literature/SAGE-EvoBridge Research 2026-09-23/00 - Thu vien nghien cuu quoc te SAGE-EvoBridge|Về thư viện]]
