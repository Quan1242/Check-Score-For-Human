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
- Instance segmentation: `{"kind":"polygon","points":[[x,y],...]}`. Tối thiểu ba điểm, pixel ảnh gốc. Hiện chưa kiểm tra tự giao/cạnh trùng, chưa hỗ trợ holes, multipart hoặc RLE. Không coi một polygon là biểu diễn đầy đủ mọi mask thực tế.
- 3D: `{"kind":"cuboid3d","center":[x,y,z],"size_lwh":[l,w,h],"yaw":0,"frame":"lidar"}`. Mét, tâm hình học hộp, hệ LiDAR x tiến, y trái, z lên; yaw radian quanh +z. KITTI camera labels dùng quy ước khác: phải chuyển tọa độ và tâm hộp bằng calibration trước khi nhập. Chưa có converter này trong scaffold.

3D gắn nhãn vào asset pointcloud. Ảnh camera có thể upload nhưng quan hệ ảnh–pointcloud–calibration chưa triển khai.

## Nhãn sau sửa AI

Giữ nguyên object id khi sửa tọa độ/lớp; tạo id mới khi thêm. Về sau dùng id và event log để tính edits, không tự suy diễn toàn bộ lịch sử chỉ từ hai snapshot. Backend hiện chỉ kiểm tra parent cùng dự án/source AI, chưa xác minh từng thay đổi có đúng nguồn gốc hay không.

## Nhãn trống

`objects: []` là mẫu đã được biểu diễn với không đối tượng. Không có sample trong bundle nghĩa là thiếu kết quả cho mẫu đó. Bộ chấm tương lai cần phân biệt hai trường hợp này.
