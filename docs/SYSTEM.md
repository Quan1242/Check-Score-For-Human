# Mô tả hệ thống M49

Tài liệu mô tả hành vi hiện có. Cách cài và trạng thái kiểm chứng ở [README](../README.md); dữ liệu, Google và thao tác ở [hướng dẫn sử dụng](GUIDED_WORKFLOW.md).

<a id="architecture"></a>

## Kiến trúc và lưu trữ

Frontend React/TypeScript chạy qua Vite hoặc Nginx, gọi API FastAPI. Backend dùng SQLModel với SQLite local hoặc PostgreSQL qua Docker. Ảnh, point cloud và các tệp làm việc nằm trong storage; model AI chạy riêng trên Colab.

- `Project`: một tác vụ và danh sách lớp.
- `Asset`: tài nguyên có tên duy nhất trong dự án, đường dẫn lưu nội bộ và metadata kích thước.
- `LabelSet`: snapshot nhãn với nguồn ground_truth, ai, manual hoặc assisted. Assisted trỏ tới bản AI cùng dự án bằng parent_id.
- `Experiment`: cố định ground truth, danh sách mẫu và ngưỡng IoU.
- `Assignment`: một người, một mẫu, một chế độ; draft/final trỏ tới snapshot riêng. Revision ngăn ghi đè thay đổi cũ, trả 409 khi xung đột.
- `AnnotationEvent`: sự kiện timer, lưu và chốt; chưa ghi từng thay đổi hình học.
- `GuidedRun`: tiến độ luồng 10 Manual → AI → 10 Assisted → kết quả.
- `ColabJob`: cấu hình model, manifest, transport, trạng thái và bản AI đã nhập.

Editor không trả payload ground truth. Lưu nháp/chốt tạo bản nhãn riêng và không ghi đè bản AI gốc. Frontend có undo/redo và autosave debounce 900 ms.

Biến môi trường chính: `DATABASE_URL`, `STORAGE_DIR`, `M49_TEST20_DIR`, `CORS_ORIGINS`. Mặc định khi chạy từ backend là `backend/m49.db`, `backend/storage/`; bộ mẫu nằm ở `data/test20/` từ gốc repo.

Database dùng create_all, chưa có migration nâng cấp bảng cũ. File và database không có giao dịch phân tán hay tác vụ quét file mồ côi sau crash. Sao lưu khi backend đã dừng trước khi đổi cấu trúc dữ liệu.

## Dữ liệu và Colab

Luồng 2D lấy BDD100K/KITTI; SEG đọc polygon BDD100K dạng Supervisely; 3D đọc KITTI LiDAR kèm calibration. Mỗi lượt lấy ngẫu nhiên 10 mẫu không trùng, lưu danh sách để tiếp tục đúng bộ mẫu sau khi tải lại trang.

Google OAuth Desktop dùng PKCE/state với callback localhost:8000. M49 xin quyền drive.file; token chỉ lưu local. Notebook dùng xác thực riêng của Colab và không chứa token M49.

Backend chỉ cho gửi AI sau đủ 10 Manual. Request cố định mẫu, lớp, model và checksum; không chứa ground truth hoặc Manual. 3D gửi thêm thông tin camera/calibration để lọc cùng phạm vi đánh giá.

ID file Drive được lưu trước upload để retry không tạo bản trùng. Mỗi job gắn với tài khoản gửi ban đầu. Notebook ghi dự đoán và marker hoàn tất; backend kiểm tra mã lượt, checksum, schema và đủ mẫu rồi nhập một lần. Trạng thái awaiting_colab chỉ có nghĩa chờ chạy/chờ kết quả, không xác nhận runtime đang chạy.

Model mặc định là YOLO11s, YOLO11s-seg và PointPillars KITTI theo tác vụ. 3D đánh giá car có tâm hộp trong FOV camera, x thuộc [0, 69.12), y thuộc [-39.68, 39.68). Đây là giao thức pilot M49, không phải KITTI AP độc lập.

<a id="data-contract"></a>

## Hợp đồng dữ liệu M49

Nguồn thực thi là [schemas.py](../backend/app/schemas.py), bản xuất là [label-bundle.schema.json](label-bundle.schema.json). Chạy `python scripts/export_schema.py` từ gốc repo để sinh lại.

Bundle gồm schema_version 1.0, task, name, annotator, parent_id, run và samples. Trường run lưu model, checkpoint, GPU, library_version và thời gian; giá trị chưa đo để null. Mỗi sample có asset_name khớp chính xác tên tài nguyên và danh sách objects.

Object gồm id duy nhất trong mẫu, category thuộc lớp dự án, geometry và confidence. Nhãn AI phải có confidence từ 0 đến 1; nhãn người có thể để null. Danh sách objects rỗng biểu thị mẫu đã gán nhãn nhưng không có đối tượng, khác với thiếu sample hoặc Assignment chưa chốt.

### Tọa độ và hình học

- **Box 2D:** `{"kind":"bbox2d","xyxy":[x1,y1,x2,y2]}`. Pixel ảnh gốc, x sang phải, y xuống; x2 > x1 và y2 > y1. Tọa độ sau resize/letterbox phải chuyển về ảnh gốc.
- **SEG:** `{"kind":"polygon","points":[[x,y],...]}`. Từ 3 đến 1.000 đỉnh; không lặp điểm đầu ở cuối. Từ chối điểm trùng, tự giao/tự chạm, cạnh chồng hoặc diện tích 0. Chỉ một polygon đơn, chưa hỗ trợ holes, multipart hay RLE.
- **Cuboid 3D:** `{"kind":"cuboid3d","center":[x,y,z],"size_lwh":[l,w,h],"yaw":0,"frame":"lidar"}`. Đơn vị mét, tâm hình học, x tiến/y trái/z lên, yaw radian quanh +z; l/w/h dương.

KITTI camera labels có tâm đáy và hệ tọa độ khác; adapter dùng calibration để chuyển tâm/hướng về LiDAR. Cuboid M49 chỉ có yaw, bỏ roll/pitch nhỏ của camera khi biểu diễn hướng. Chưa có giao diện ghép ảnh camera với LiDAR.

### API và nhập dữ liệu

API tương tác tại /docs là danh sách endpoint hiện hành. Các nhóm chính: projects/assets/label-sets, experiments/assignments, guided, datasets, cvat và colab.

Importer BDD100K/KITTI và CVAT được giữ qua API/script. CVAT hỗ trợ COCO box 2D và polygon đơn; thời gian nhập tay được ghi nguồn riêng. `scripts/import_folder.py` đọc assets/ground_truth/ai, upload tuần tự; lỗi không rollback toàn bộ những lần upload đã thành công. Bỏ qua asset trùng tên không có nghĩa đã kiểm tra nội dung giống nhau.

<a id="scoring"></a>

## Công thức chấm điểm

Code ở [metrics.py](../backend/app/evaluation/metrics.py) và [benchmark.py](../backend/app/benchmark.py). Chấm độc lập từng tác vụ, lớp và mẫu, so với ground truth cố định. Chỉ nhãn người đã chốt được chấm.

### IoU và Dice

- **Box 2D:** IoU = diện tích giao / diện tích hợp. Diện tích dùng (x2 − x1) × (y2 − y1), không cộng 1.
- **SEG:** rasterize polygon ở kích thước ảnh gốc; mask IoU = |P ∩ G| / |P ∪ G|. Dice = 2|P ∩ G| / (|P| + |G|). Polygon rasterize thành mask rỗng bị từ chối.
- **3D:** giao thể tích = diện tích giao hai đáy xoay yaw × độ cao giao. IoU3D = Vgiao / (VA + VB − Vgiao). Đây là IoU thể tích, không phải chỉ IoU hình chiếu BEV.

Ví dụ hai box 10 × 10 lệch ngang 5 pixel có IoU = 50 / 150 = 1/3. Hai cuboid cùng tâm kích thước 4 × 2 × 2, lệch yaw 90° cũng có IoU3D = 1/3.

### Ghép nhãn và chỉ số

Chỉ ghép cùng lớp và IoU ≥ ngưỡng của Experiment. Ghép một–một theo thứ tự ưu tiên: tối đa số cặp hợp lệ, sau đó tối đa tổng IoU. Không dùng greedy theo confidence cho điểm bộ nhãn cuối.

- TP: số cặp đã ghép.
- FP: dự đoán không được ghép.
- FN: ground truth không được ghép.
- Precision = TP / (TP + FP).
- Recall = TP / (TP + FN).
- F1 = 2TP / (2TP + FP + FN).
- IoU trung bình: tổng IoU các cặp ghép / TP.

Mẫu số bằng 0 trả null và giao diện hiện N/A. Cả hai bộ nhãn rỗng không được tự gán F1 = 1. Ví dụ một ground truth có hai dự đoán trùng hoàn toàn: TP = 1, FP = 1, FN = 0, F1 = 2/3.

Điểm tổng dùng tổng TP/FP/FN trên các mẫu đã hoàn thành để tính micro-F1. Mean IoU tổng được gia quyền theo số cặp ghép. Tỷ lệ hoàn thành được báo riêng; mẫu thiếu/chưa chốt không bị coi là dự đoán rỗng.

### Thời gian

Timer phía server tính cả thao tác và quan sát, heartbeat mỗi 10 giây và lease 30 giây. Lease hết hạn cần resume; heartbeat muộn không tự khôi phục. Không ghi event cho từng heartbeat. Ẩn tab/mất mạng gửi pause khi có thể; không tự loại thời gian người đứng yên quan sát.

Chỉ ghép Manual/Assisted của cùng người, cùng mẫu, cả hai đã chốt. Chỉ tính các chỉ số dưới đây khi mọi cặp có thời gian server đo dương:

- Tiết kiệm = tổng Manual − tổng Assisted.
- Tăng tốc = tổng Manual / tổng Assisted.
- Tỷ lệ giảm = 1 − tổng Assisted / tổng Manual.

Số tiết kiệm âm nghĩa là Assisted chậm hơn. Thời gian AI inference, truyền dữ liệu và thiết lập không nằm trong thời gian người thao tác; inference được báo riêng. Thời gian CVAT nhập tay không được dùng để tính tăng tốc.

Giao diện đã bỏ Đạt/Chưa đạt. API vẫn có status/quality_not_lower và CSV còn time_goal để tương thích: passed yêu cầu đủ cặp, đo được, tổng Assisted nhanh hơn và F1 không giảm ở từng cặp. Đây không phải điểm chất lượng tổng hợp.

CSV có các cột tổng thời gian lặp lại trên từng dòng mẫu; không cộng những cột tổng đó qua các dòng. active_seconds là thời gian riêng của nhiệm vụ.

## Giới hạn vận hành

- Một người, một tab gán nhãn, một backend worker local. Chưa có đăng nhập/phân quyền; API quản trị vẫn đọc được ground truth, chưa phù hợp benchmark mù nhiều người.
- Upload tối đa 32 MiB mỗi asset; checkpoint riêng tối đa 512 MiB.
- Tối đa 20 mẫu/Experiment, 40 Assignment khi chấm, 3 AI run/dự án và một yêu cầu chấm đồng thời trong mỗi process.
- Tối đa 80 đối tượng mỗi phía/mẫu. SEG tối đa 4 triệu pixel/ảnh và 32 triệu pixel tổng mask/mẫu.
- Viewer lấy mẫu tối đa 60.000 điểm; vẫn cần đọc tệp point cloud vào bộ nhớ. Hỗ trợ BIN và PCD ASCII/binary, chưa hỗ trợ PCD nén.
- Chưa có COCO/KITTI AP chính thức, tổng điểm có trọng số, báo cáo chi phí, thống kê từng thao tác sửa, khoảng tin cậy hoặc kiểm thử tải lớn.

Các giới hạn trên là giới hạn code/phạm vi vận hành, không bảo đảm một mức RAM hay độ chính xác thực nghiệm. Bộ mẫu pilot nhỏ và lịch Manual trước Assisted có thể tạo hiệu ứng nhớ; không suy rộng kết quả thành benchmark đại diện.
