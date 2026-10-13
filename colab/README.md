# Colab cho demo

**13/10/2026:** dùng nút Google trong bước AI để ứng dụng tạo notebook riêng của lượt trên Drive và mở Colab. Bấm **Run all**, cấp quyền bằng cùng tài khoản; ảnh/model tải tự động, kết quả tự gửi về M49. Không điền ROOT hay tải notebook thủ công cho lượt mới. [Cấu hình một lần](../docs/GUIDED_WORKFLOW.md#kết-nối-google-một-lần-trên-máy-local). Các notebook trong thư mục này là template; backend thay phần transport khi tạo notebook qua Google API. Các bước Drive Desktop bên dưới chỉ áp dụng cho lượt cũ.

**12/10/2026:** notebook 2D/segmentation đã chuyển sang tự đọc lượt và xuất kết quả qua Google Drive. Tạo lượt trong ứng dụng, mount Drive và đặt ROOT theo mã lượt; backend tự nhập. Không dùng bước download/upload thủ công bên dưới cho hai notebook này. Xem [hướng dẫn mới](../docs/DATASETS_COLAB.md). Transport được kiểm thử local; chưa chạy Drive/GPU thật. Notebook 3D vẫn template.

`detection_2d.ipynb` có pipeline YOLO11s với Ultralytics 8.3.203, đọc tối đa 20 ảnh theo request manifest và xuất `predictions.json`, `timing.json`, `environment.txt`. **Chưa chạy kiểm chứng notebook trên GPU.** Chạy trên Colab; không cài model vào backend local.

`instance_segmentation.ipynb` đã có pipeline YOLO11s-seg, Ultralytics 8.3.203, xuất polygon M49 và đo thời gian riêng. Validator được sinh từ schema backend, kiểm tra bằng test cục bộ. **Chưa chạy GPU/Colab thực tế.** Notebook dừng khi mask có nhiều vùng/lỗ hoặc polygon không hợp lệ, không bỏ dự đoán và không chuyển thành box. Chuẩn bị `/content/demo/assets/` và `manifest.json` như notebook 2D. Có thể tái tạo notebook bằng `python scripts/build_segmentation_notebook.py` sau khi cập nhật schema.

`detection_3d.ipynb` vẫn là template; cell inference báo NotImplementedError. Các bước dưới đây áp dụng khi hoàn thiện template 3D:

1. Tải notebook lên Colab, chọn GPU nếu model cần.
2. Cài và pin model/library sau khi kiểm tra tài liệu chính thức, khả năng GPU và checkpoint.
3. Đọc ảnh/point cloud, thực hiện chuyển đổi cần thiết.
4. Thay cell TODO bằng inference thật; đưa tọa độ về ảnh gốc / hệ lidar quy định.
5. Điền model/checkpoint/library_version; đo inference và train riêng. Không tính download vào GPU inference.
6. Cell export đã ghi kết quả tự động vào thư mục lượt trên Drive; backend nhận khi đồng bộ xong. Cần đo INFERENCE_SECONDS thực tế trong pipeline 3D trước khi export.

2D và segmentation cần checkpoint riêng. 3D cần pipeline phù hợp dữ liệu KITTI và hệ tọa độ. Không giả định một checkpoint xử lý cả ba tác vụ. Xem `docs/SYSTEM.md#data-contract`.
