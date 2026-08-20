# Cơ sở Thiết kế và Hồ sơ Rủi ro Vị trí Công trình Cầu (Design Basis & Site-Hazard Profile)

Tài liệu này định nghĩa cấu trúc máy đọc được cho các ràng buộc đầu vào của dự án cầu thực tế trước khi kích hoạt vòng tối ưu hóa của AI Agent.

## 1. Mục tiêu
- Loại bỏ các phỏng đoán tùy tiện về vị trí, địa chất, gió, động đất và cấp ăn mòn.
- Khóa toàn bộ đơn vị đo lường, phiên bản tiêu chuẩn (`TCVN 11823:2017`, `AASHTO LRFD`), tải trọng di động và tuổi thọ thiết kế.
- Đảm bảo Gate G0 được kiểm toán đầy đủ trước khi cho phép AI Agent sinh phương án.

## 2. Các Schema Quản lý
- `contracts/design_basis.schema.json`: Cơ sở thiết kế kỹ thuật, tiêu chuẩn áp dụng, vật liệu và tĩnh không.
- `contracts/site_hazard_profile.schema.json`: Hồ sơ rủi ro động đất, gió bão, xói lở mố trụ và phân loại địa chất.
