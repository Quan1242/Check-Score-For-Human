# Notebook Colab

Các notebook là mẫu để backend tạo bản riêng cho từng lượt trên Drive của tài khoản người dùng. Trên web: hoàn thành Manual → kết nối Google → gửi mẫu → mở Colab → **Run all**.

- `detection_2d.ipynb`: YOLO11, xuất box 2D.
- `instance_segmentation.ipynb`: YOLO11-seg, xuất polygon đơn; dừng nếu mask có lỗ/nhiều vùng hoặc hình học không hợp lệ.
- `detection_3d.ipynb`: PointPillars KITTI, cần GPU và biên dịch CUDA; xuất cuboid hệ LiDAR.
- `drive_transport.py`: kiểm tra request/checksum và xuất kết quả cho transport thư mục Drive; vẫn được notebook generator và test sử dụng.

Backend thay transport bằng Google API khi tạo notebook cho lượt mới. Bản notebook trong repo còn cấu hình Drive Desktop cho lượt cũ; tải trực tiếp notebook không tự tạo dữ liệu/request của một lượt mới.

Chỉ ảnh/point cloud, calibration và cấu hình model được gửi để inference; không gửi ground truth hay Manual. Kết quả gồm nhãn, thời gian và thông tin môi trường để backend kiểm tra rồi nhập.

Từ thư mục gốc, trong môi trường Python đã cài dependencies:

```bash
python scripts/build_segmentation_notebook.py
python scripts/build_3d_notebook.py
```

Generator SEG lấy notebook 2D làm nền và dùng validator schema backend. Generator 3D dùng adapter PointPillars và helper transport. Sau khi sinh lại, chạy kiểm thử backend và kiểm tra diff notebook.

Xem [hướng dẫn dữ liệu và Google](../docs/GUIDED_WORKFLOW.md) và [hợp đồng dữ liệu](../docs/SYSTEM.md#data-contract). Trạng thái kiểm chứng hiện tại được ghi một nơi trong [README](../README.md#kiểm-thử-và-trạng-thái).
