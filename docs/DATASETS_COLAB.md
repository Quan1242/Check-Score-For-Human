# BDD100K / KITTI, thời gian gán nhãn và Colab tự đồng bộ

Cập nhật 12/10/2026. Luồng local một người, một backend worker. Chưa có dataset thật trên máy; chưa chạy Colab/GPU hoặc Google Drive thực tế trong đợt này.

## 1. Tải dữ liệu có ground truth

- BDD100K: lấy ảnh **100k val** và JSON **detection val** từ [trang dữ liệu BDD100K](https://bdd-data.berkeley.edu/). Giải nén; giữ nguyên tên ảnh. Chọn thư mục ảnh `images/100k/val` và file JSON nhãn tương ứng. Importer đọc danh sách frame với `labels[].box2d`; chưa hỗ trợ nhãn segmentation của BDD100K.
- KITTI: tải từ [KITTI object detection](https://www.cvlibs.net/datasets/kitti/eval_object.php). Cho 2D cần training images (left color) và training labels; cho 3D cần training Velodyne, training labels và calibration. Giải nén để cùng một thư mục `training` chứa `image_2`, `velodyne`, `label_2`, `calib` theo các phần đã tải.
- Không chọn split test không có ground truth công khai để chấm local. Dùng một tập con train/val làm **dữ liệu thử ứng dụng**, không tuyên bố điểm trên benchmark test chính thức.
- Chưa tự tải toàn dataset; việc tải/đăng nhập ở trang cung cấp do bạn thực hiện. Ứng dụng sao chép 1–20 mẫu mỗi lượt, tối đa 32 MiB/tệp và 256 MiB/lượt.

Trong tab **Dữ liệu → Nhập BDD100K / KITTI**:

1. Chọn dataset/tác vụ, nhập đường dẫn trên máy chạy backend.
2. BDD100K dùng tên lớp như `car`; KITTI dùng `Car` (phân biệt hoa/thường). Để thử notebook YOLO 2D hiện tại, bắt đầu bằng lớp này.
3. Nhập tên mẫu cụ thể nếu có (`000000.bin` cho KITTI 3D). Để trống sẽ chọn các tên tệp đầu tiên theo thứ tự, mặc định 5 mẫu. Đây là thử luồng, không phải lấy mẫu đại diện.
4. Nhấn **Nhập dataset và ground truth**. Ứng dụng tạo dự án riêng và nhập ảnh/point cloud cùng nhãn chuẩn trong một transaction. Lỗi nhãn/tệp sẽ rollback dữ liệu và dọn các tệp vừa tạo, không sửa nguồn dataset.
5. Tạo Experiment để khóa ground truth, danh sách mẫu và ngưỡng chấm.

KITTI được chấm bằng metric M49. `DontCare` và lớp ngoài lựa chọn được bỏ; chưa áp dụng quy tắc ignore/difficulty/AP của benchmark KITTI. Tâm hộp được chuyển từ bottom-center trong rectified camera sang tâm hình học LiDAR bằng `inverse(R0_rect × Tr_velo_to_cam)`. Hướng chiều dài được chuyển rồi chiếu lên XY để lấy yaw; cuboid M49 không biểu diễn roll/pitch nhỏ của calibration. Dữ liệu nguồn không bị sửa.

Tài liệu định dạng: [BDD100K](https://github.com/bdd100k/bdd100k/blob/master/doc/source/format.rst), [quy ước camera/LiDAR của MMDetection3D](https://github.com/open-mmlab/mmdetection3d/blob/main/mmdet3d/structures/bbox_3d/coord_3d_mode.py).

## 2. Cấu hình Drive một lần

1. Đăng nhập Google Drive for desktop trên máy và cùng tài khoản trên Colab.
2. Tạo thư mục `M49` trong **My Drive**, chọn **Available offline / Có sẵn khi ngoại tuyến**.
3. Trong **Dữ liệu → Colab**, nhập đường dẫn Windows thực tế, ví dụ `G:\My Drive\M49`, rồi lưu kết nối. Không nhập đường dẫn ví dụ nếu máy bạn dùng ổ khác.
4. Chọn các mẫu của Experiment rồi nhấn **Tạo lượt Colab**. Gói gồm `request.json` (mã lượt, tác vụ, lớp, danh sách mẫu và SHA-256) cùng `assets/`. Không xuất ground truth trong gói Colab.

Ứng dụng lưu cấu hình local trong `backend/storage/colab-sync.json` (hoặc STORAGE_DIR đã cấu hình). Đường dẫn của mỗi lượt được giữ cố định dù sau đó đổi cấu hình. Với Docker phải mount thư mục Drive vào backend và dùng đường dẫn trong container; nên chạy trực tiếp trên Windows cho luồng này.

## 3. Chạy Colab và tự nhận kết quả

1. Mở `colab/detection_2d.ipynb` trên Colab, chọn runtime phù hợp.
2. Chạy cell cài dependency, rồi mount Drive. Điền mã lượt do ứng dụng hiển thị vào `ROOT = Path('/content/drive/MyDrive/M49/PASTE_JOB_ID')`.
3. Chạy các cell còn lại. Notebook kiểm tra ảnh theo checksum; nếu Drive chưa đồng bộ xong, chờ rồi chạy lại cell cấu hình.
4. Cuối lượt, notebook tự ghi `predictions.json`, `timing.json`, `environment.txt` rồi `result.ready.json`. Không tải/upload JSON thủ công.
5. Giữ backend chạy và Drive kết nối. Backend kiểm tra mỗi 5 giây; tốc độ nhận thực tế còn phụ thuộc độ trễ Drive. Chỉ nhập khi checksum, mã lượt, tác vụ, tên mẫu, lớp và hình học đều hợp lệ.
6. Giao diện hiện **Đã tự nhập AI**. Chọn bản AI đó khi tạo nhiệm vụ Assisted. Tab Kết quả hiện model, checkpoint/hash, GPU và thời gian inference toàn lượt; chi tiết từng ảnh và môi trường giữ trong thư mục lượt trên Drive.

Lỗi đồng bộ/validation được hiển thị và tự thử lại. Snapshot AI và trạng thái đã nhập được commit cùng transaction nên khởi động lại không nhập trùng. Lượt đã xuất thành công không được ghi đè từ notebook; tạo lượt mới để đổi cấu hình/model. Demo giới hạn 3 lượt AI/dự án, kể cả lượt đang chờ.

“Tự động” ở đây là xuất gói, nhận và nhập kết quả. Đăng nhập, cấp quyền mount Drive và bắt đầu chạy Colab vẫn cần người dùng. Không mở API local ra Internet và không cất token Google trong ứng dụng.

Notebook YOLO 2D dùng checkpoint COCO, chỉ ánh xạ các lớp có nghĩa tương ứng (`person → pedestrian/Pedestrian`, `car → Car`). Không giả định hỗ trợ mọi lớp BDD100K/KITTI: `rider`, `Cyclist`, `traffic sign` cần model phù hợp. Notebook dừng với lớp không có trong model. Notebook segmentation cũng dùng Drive nhưng cần dự án/ground truth segmentation riêng. **Notebook inference KITTI 3D vẫn là template**; bộ nhập KITTI 3D và transport kết quả 3D đã có, chưa có model 3D chạy thật.

## 4. Thời gian đo khi gán nhãn

- Mở hoặc tạo nhiệm vụ trong **Gán nhãn**: timer tự bắt đầu, bao gồm xem ảnh, vẽ, sửa và rà soát AI. Không tự loại thời gian đứng yên để quan sát.
- Nhấn **Tạm dừng** khi nghỉ; ẩn tab sẽ gửi pause. Quay lại nhấn tiếp tục. Chốt phiên bản dừng timer và dùng thời gian phía server.
- Heartbeat mỗi 10 giây; nếu tab crash/mất mạng, server cộng tối đa 30 giây sau heartbeat cuối. Đây là sai số giới hạn khi có sự cố, không phải đo chính xác thời điểm đóng tab.
- Manual và Assisted được ghép cùng mẫu/cùng người. Thời gian AI inference, tải model và đồng bộ không cộng vào thời gian người gán nhãn; inference trình bày riêng.
- CVAT cũ vẫn nhập được để giữ tương thích, nhưng cặp có thời gian nhập tay không được tính speedup, tiết kiệm thời gian hoặc đạt mục tiêu. Dùng editor cho thí nghiệm mới.

## Kiểm tra đã thực hiện

49 test backend đạt, gồm fixture định dạng BDD100K/KITTI, calibration có translation, rollback, checksum, đủ mẫu, retry không nhập trùng, notebook transport và timer heartbeat/pause/mất kết nối. 5 test frontend và build TypeScript/Vite đạt. Fixture là dữ liệu tổng hợp phục vụ test, không phải dataset thật. Chưa kiểm duyệt UI bằng trình duyệt, chưa chạy inference hoặc đồng bộ Drive thật.
