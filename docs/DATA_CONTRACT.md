# Hợp đồng dữ liệu M49 v1.0

Schema thực thi ở `backend/app/schemas.py`; `label-bundle.schema.json` được sinh từ Pydantic. Gói JSON nội bộ **không phải** định dạng nhãn BDD100K/KITTI gốc. Cần adapter trước khi import dữ liệu thật.

Mỗi bundle có:

- `schema_version`: `1.0`.
- `task`: `detection_2d`, `instance_segmentation` hoặc `detection_3d`.
- `name`: tên bộ nhãn/lần chạy.
- `annotator`: bắt buộc cho manual/assisted.
- `parent_id`: ID lần chạy AI, chỉ dùng cho assisted.
- `run`: model, checkpoint, gpu, library_version, inference_seconds, training_seconds, compute_cost_vnd; giá trị chưa đo để null.
- `samples`: tên tệp khớp chính xác tài nguyên đã upload, objects, active_seconds (null nếu chưa đo).

Một đối tượng có id duy nhất trong mẫu, category trong danh sách lớp dự án, geometry và confidence. AI bắt buộc confidence [0,1]; nhãn người có thể để null.

## Hình học

- 2D: `{"kind":"bbox2d","xyxy":[x1,y1,x2,y2]}`. Pixel theo ảnh gốc, gốc góc trên trái, x sang phải, y xuống dưới. x2>x1, y2>y1. Chuyển khung sau letterbox/resize về ảnh gốc trước khi xuất.
- Instance segmentation: `{"kind":"polygon","points":[[x,y],...]}`. Từ 3 đến 1.000 đỉnh, pixel ảnh gốc. Từ chối đỉnh trùng, tự giao/tự chạm, cạnh chồng và diện tích 0; không lặp đỉnh đầu ở cuối. Chưa hỗ trợ holes, multipart hoặc RLE. Không coi một polygon là biểu diễn đầy đủ mọi mask thực tế.
- 3D: `{"kind":"cuboid3d","center":[x,y,z],"size_lwh":[l,w,h],"yaw":0,"frame":"lidar"}`. Mét, tâm hình học hộp, hệ LiDAR x tiến, y trái, z lên; yaw radian quanh +z. KITTI camera labels dùng quy ước khác: phải chuyển tọa độ và tâm hộp bằng calibration trước khi nhập. Chưa có converter này trong scaffold.

3D gắn nhãn vào asset pointcloud. Ảnh camera có thể upload nhưng quan hệ ảnh–pointcloud–calibration chưa triển khai.

## Nhãn sau sửa AI

Giữ nguyên object id khi sửa tọa độ/lớp; tạo id mới khi thêm. Về sau dùng id và event log để tính edits, không tự suy diễn toàn bộ lịch sử chỉ từ hai snapshot. Backend hiện chỉ kiểm tra parent cùng dự án/source AI, chưa xác minh từng thay đổi có đúng nguồn gốc hay không.

## Nhãn trống

`objects: []` là mẫu đã được biểu diễn với không đối tượng. Không có sample trong bundle nghĩa là thiếu kết quả cho mẫu đó. Bộ chấm giữ mẫu thiếu ở báo cáo completion, loại khỏi metric với missing_policy công khai; không tự chuyển thành nhãn rỗng.

## Bổ sung ngày 2026-10-09

Cấu trúc bundle vẫn là v1.0; bổ sung ràng buộc polygon như trên. Experiment/Assignment được lưu riêng, không nhét thêm trường vào bundle.

- POST `/api/projects/{id}/experiments`: name, ground_truth_id, asset_ids, iou_threshold (0 < ngưỡng <= 1). Mỗi asset phải có sample trong ground truth, kể cả objects rỗng.
- POST `/api/experiments/{id}/assignments`: asset_id, annotator, mode manual/assisted, parent_id chỉ với assisted. Parent AI phải có sample tương ứng.
- GET `/api/assignments/{id}/editor`: assignment, asset và objects; không có ground truth payload.
- POST `/api/assignments/{id}/draft`: revision hiện tại và objects. Server tự xác định asset/task/annotator/parent từ assignment, trả revision mới.
- POST `/api/assignments/{id}/finalize`: revision; yêu cầu có draft trước đó. Final trỏ vào draft hiện tại và bất biến qua API này.
- POST `/api/assignments/{id}/events`: revision, kind resume/pause. GET cùng đường dẫn để đọc event log. Thời gian kết thúc phiên ở Assignment là nguồn chuẩn cho báo cáo, còn active_seconds trong bundle là snapshot tại lúc save.
- GET `/api/experiments/{id}/score` và `/results.csv`: metric M49; null hiển thị N/A. Không gọi các kết quả này là COCO/KITTI official.

Segmentation raster hóa ở độ phân giải ảnh gốc bằng quy tắc tâm pixel (x+0.5,y+0.5), even/odd scanline; giao điểm/cạnh dùng khoảng nửa mở để tránh đếm đôi. Mask instance rỗng bị từ chối khi chấm. IoU mask dùng giao/hợp pixel, Dice của cặp ghép = 2*IoU/(1+IoU).

IoU 3D dùng giao hai hình chữ nhật đáy đã xoay yaw, nhân phần giao chiều cao. Không hỗ trợ pitch/roll, không dùng BEV thay cho 3D.

Giới hạn hiện tại: 300 đối tượng/mẫu cho bộ chấm và lưu draft; mask tối đa 25 triệu pixel/ảnh và 128 triệu pixel tổng kích thước mask/mẫu. Viewer đọc BIN little-endian x,y,z,intensity và PCD ASCII/binary không nén, chỉ lấy mẫu tối đa 60.000 điểm để hiển thị; không thay đổi file point cloud gốc.
