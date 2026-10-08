# Kiểm tra bộ khung — 2026-10-08

- Backend: 10 tests đạt trên Python 3.12, SQLite in-memory.
- Kiểm tra: ảnh hỏng, tên trùng, giới hạn kích thước, mẫu/lớp sai, tọa độ ngoài ảnh, confidence thiếu, task sai, mẫu trùng, parent khác dự án, polygon và cuboid, giữ bản AI gốc.
- Frontend: TypeScript và Vite production build đạt.
- Docker Compose: cấu hình hợp lệ qua `docker compose config --quiet`.
- Chưa chạy Docker containers/PostgreSQL vì tài khoản hiện tại không được truy cập Docker daemon.
- Chưa kiểm thử trình duyệt tự động hoặc model inference; notebook là template, editor trực quan và evaluation chưa triển khai.

Các tests xác nhận hợp đồng API và lưu trữ, không xác nhận chất lượng mô hình hoặc tính đúng đắn của metric chưa được cài đặt.
