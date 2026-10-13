# Roadmap demo một người

## Cập nhật 12/10/2026 — BDD100K, KITTI và Drive

- [x] Nhập BDD100K box 2D, KITTI box 2D/cuboid 3D từ thư mục, chọn 1–20 mẫu và lớp; rollback khi lỗi.
- [x] Timer tự bắt đầu khi mở nhiệm vụ, tính cả quan sát; không dùng thời gian nhập tay để kết luận tăng tốc.
- [x] Xuất lượt AI qua Drive, notebook 2D/segmentation xuất tự động, backend polling/checksum/validation và chống nhập trùng.
- [x] 49 test backend, 5 test frontend và build đạt.
- [ ] Người dùng tải dataset và cấu hình Drive; thử toàn luồng với dữ liệu thật.
- [ ] Chạy inference Colab/GPU và kiểm duyệt UI thực tế.
- [ ] Model inference KITTI 3D; adapter segmentation BDD100K và KITTI AP chính thức chưa có.

Chi tiết: [DATASETS_COLAB](DATASETS_COLAB.md). Phần này được ưu tiên hơn checklist lịch sử bên dưới.

## Cập nhật segmentation/3D

- [x] Python 3.14: 41 test backend đạt, gồm COCO segmentation và nhiệm vụ segmentation/3D.
- [x] Frontend build và 5 test hình học cuboid đạt.
- [x] COCO ZIP polygon đơn: xuất AI, nhập Manual/Assisted, chốt và chấm IoU/Dice.
- [x] Cuboid: kéo tâm, resize và yaw bằng chuột ở góc Trên/Trước/Bên.
- [x] Viết pipeline Colab YOLO11s-seg, dùng validator backend; chưa chạy inference thực tế.
- [ ] Kiểm duyệt thao tác giao diện (chưa có trình duyệt kết nối với công cụ).
- [ ] Chạy notebook segmentation trên GPU/pilot thật.
- [ ] AI 3D, KITTI/calibration; brush/RLE/multipart vẫn chưa triển khai.

Xem [hướng dẫn sử dụng](../README.md). Kế hoạch ngày 10/10 phía dưới được giữ làm lịch sử;
trạng thái mới ở trên được ưu tiên khi có khác biệt.

Cập nhật kế hoạch ban đầu ngày **10/10/2026 (UTC+7)**.

## Phạm vi

Ứng dụng dùng để **một người chạy demo trên máy cá nhân**, thao tác lần lượt với manual, AI và assisted. Mục tiêu là minh họa luồng nhập dữ liệu → gán nhãn → lưu/chốt → so sánh điểm và thời gian trên bộ mẫu nhỏ. Kết quả phục vụ demo, chưa đại diện cho nghiên cứu nhiều người.

Đã có code cho box 2D, polygon segmentation, cuboid 3D, lưu nhãn và chấm điểm. **Chưa xác nhận các phần này chạy đúng bằng test/build và thử giao diện.** Chi tiết implementation trước đó nằm trong [báo cáo thay đổi](VALIDATION.md).

## 1. Cách chạy demo để giảm tải máy

- Chạy trực tiếp backend với SQLite và frontend theo README. Docker/PostgreSQL là tùy chọn, không bắt buộc.
- Chỉ chạy một backend worker, một người thao tác và một tab gán nhãn; làm từng tác vụ, không chấm nhiều thử nghiệm cùng lúc.
- Bắt đầu với 3–5 mẫu nhỏ cho mỗi tác vụ cần trình diễn; chỉ tăng sau khi quan sát RAM/CPU và độ phản hồi. Đây là quy mô khởi đầu, không phải mức tải đã được kiểm chứng.
- Dùng ảnh vừa phải và point cloud BIN hoặc PCD ASCII/binary nhỏ. Viewer hiện lấy mẫu tối đa 60.000 điểm để vẽ; giới hạn này không giới hạn dung lượng tệp phải đọc vào bộ nhớ.
- Chạy AI riêng trên Colab hoặc dùng kết quả AI thật đã xuất sẵn rồi nhập JSON. Không tải model, train hoặc chạy inference trong backend trên máy cá nhân.
- Upload hiện giới hạn 32 MiB mỗi tệp. Đây không phải bảo đảm tổng RAM thấp; vẫn cần chọn dữ liệu nhỏ và kiểm tra tải thực tế.

Một backend worker và một người là phạm vi vận hành; chưa có khóa đăng nhập một người hay giới hạn tổng RAM. Đã thêm giới hạn chấm trong mục 3, còn chờ bạn kiểm tra thực tế.

## 2. Việc cần làm trước khi demo

**Kiểm tra và sửa lỗi:**

- [ ] Chạy `python -m pytest -q` trong `backend` và `pnpm build` trong `frontend`; sửa lỗi phát hiện được.
- [ ] Bổ sung test cho Experiment/Assignment: lưu nháp, chốt nhãn, xung đột revision và giữ nguyên bản AI gốc.
- [ ] Bổ sung test bộ chấm: trùng/lệch hình, thừa/thiếu đối tượng, sai lớp, matching và N/A; kiểm tra mask segmentation và hộp 3D có yaw.
- [ ] Một người thử lần lượt các tác vụ cần trình diễn: thêm/sửa/xóa, undo/redo, autosave, tải lại trang, chốt nhãn, xem kết quả và xuất CSV.
- [ ] Quan sát RAM/CPU khi tải dữ liệu và tính điểm bộ mẫu demo. Nếu chậm hoặc tốn bộ nhớ, giảm số mẫu/kích thước dữ liệu trước khi mở rộng chức năng.

**Chuẩn bị dữ liệu:**

- [ ] Chọn bộ mẫu nhỏ, lớp đối tượng và ground truth; lưu danh sách mẫu dùng demo.
- [ ] Chuẩn bị nhãn AI thật ở định dạng M49. Nếu chưa có kết quả model, dùng dữ liệu tổng hợp trong `examples/` để thử luồng và ghi rõ đó là dữ liệu tổng hợp.
- [ ] Đối chiếu vài đáp án tính tay với điểm hệ thống. Nếu dùng converter BDD100K, kiểm tra tên ảnh, lớp và tọa độ đầu ra.

**Kết quả cần có:** một người hoàn thành được luồng demo trên máy cá nhân, nhãn được lưu đúng và điểm khớp các mẫu kiểm tra.

## 3. Code ưu tiên đã bổ sung, chờ bạn test

- [ ] **Kiểm tra timer:** đã code heartbeat 10 giây, lease 30 giây, pause khi ẩn tab/idle 60 giây và yêu cầu bật timer trước khi sửa nhãn. Không đổi schema database.
- [ ] **Kiểm tra giới hạn tải:** đã code tối đa 20 mẫu/thử nghiệm, 40 nhiệm vụ khi chấm, 3 AI run/dự án và một yêu cầu chấm trong mỗi backend process. Bộ chấm giới hạn 80 đối tượng mỗi phía và giảm ngân sách mask. Cần bạn đo RAM/CPU; chưa bảo đảm máy luôn đủ tải.
- [ ] **Kiểm tra so sánh thời gian:** đã code ghép cùng ảnh/cùng người, thời gian tiết kiệm, tỷ lệ tăng tốc và trạng thái đạt/chưa đạt; CSV có các cột so sánh. Mục tiêu là assisted nhanh hơn tổng thể, F1 không thấp hơn từng ảnh. Kết quả không được ép luôn đạt; chưa bao gồm thời gian AI/nhập dữ liệu trong tổng thời gian người.
- [ ] **Kiểm tra thao tác nhanh:** đã thêm Lưu và chốt một lần, kể cả giữ nguyên AI, cùng phím Delete/Undo/Redo.
- [ ] **Chạy notebook 2D:** đã có YOLO11s trên Colab, pin Ultralytics, ghi hash checkpoint và thời gian riêng; chưa chạy kiểm chứng. Segmentation/3D còn template, chỉ tích hợp khi chọn demo các tác vụ đó.
- [ ] **Chuẩn bị mẫu:** đã có script chọn 20 ảnh phân tầng và 3 ảnh pilot, xuất manifest/lịch hai lượt. Bạn chọn dữ liệu ứng viên và chạy script theo [quy trình demo](DEMO_PROTOCOL.md).

Giữ editor hiện có: polygon đơn cho segmentation và nhập tâm/kích thước/yaw cho cuboid. Báo cáo M49 và CSV hiện có là đầu ra mục tiêu của demo sau khi kiểm tra đúng; chưa yêu cầu COCO/KITTI AP chính thức.

## 4. Tạm hoãn ngoài phạm vi demo

Các mục này chưa hoàn thành nhưng không chặn demo một người:

- Đăng nhập, phân quyền, quản lý nhiều người, giao nhiệm vụ đồng thời và tổ chức benchmark mù.
- Docker/PostgreSQL bắt buộc, tối ưu nhiều người truy cập và kiểm thử tải lớn.
- Brush, mask có lỗ/nhiều vùng, RLE; gizmo kéo/resize/xoay 3D; PCD nén và camera–LiDAR calibration.
- COCO/KITTI AP, macro-F1 toàn thử nghiệm, hiển thị nhãn chuẩn chồng lên nhãn chấm, thống kê sửa nhãn chi tiết, chi phí, khoảng tin cậy và báo cáo nâng cao ngoài CSV.
- Nhập ZIP, tự động sao lưu và dọn file thừa; Alembic khi chưa cần thay đổi cấu trúc database.

Nếu cần giữ dữ liệu demo, dừng backend rồi sao chép database SQLite và thư mục lưu tệp trước khi thay đổi cấu trúc dữ liệu. `create_all` hiện không nâng cấp bảng cũ; khi thay đổi schema phải có cách chuyển dữ liệu hoặc tạo database demo mới, không tự xóa dữ liệu đang có.

## Thứ tự thực hiện

Bạn chạy test/build và thử 3–5 mẫu → sửa lỗi được báo → chạy notebook trên pilot, chốt cấu hình và 20 mẫu → đo manual/assisted theo lịch → xem mục tiêu thời gian có đạt không. Kiểm tra chi tiết ở [DEMO_PROTOCOL](DEMO_PROTOCOL.md). Ưu tiên thời gian, không triển khai báo cáo chi phí cho demo này.
