# Colab templates

Ba notebook cung cấp các cell chuẩn bị metadata và xuất bundle M49. **Chưa train/chạy model**; cell inference chủ động báo NotImplementedError để tránh tạo nhãn AI giả. Nhập output thật từ model vào `samples` rồi chạy cell export.

1. Tải notebook lên Colab, chọn GPU nếu model cần.
2. Cài và pin model/library sau khi kiểm tra tài liệu chính thức, khả năng GPU và checkpoint.
3. Đọc ảnh/point cloud, thực hiện chuyển đổi cần thiết.
4. Thay cell TODO bằng inference thật; đưa tọa độ về ảnh gốc / hệ lidar quy định.
5. Điền model/checkpoint/library_version; đo inference và train riêng. Không tính download vào GPU inference.
6. Export JSON, tải về và upload vào mục AI trên website.

2D và segmentation cần checkpoint riêng. 3D cần pipeline phù hợp dữ liệu KITTI và hệ tọa độ. Không giả định một checkpoint xử lý cả ba tác vụ. Xem `docs/DATA_CONTRACT.md`.
