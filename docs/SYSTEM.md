# Cấu trúc hệ thống và công thức đánh giá

<a id="architecture"></a>

## 1. Cấu trúc hệ thống

M49 so sánh người tự gán nhãn, AI và người chỉnh sửa nhãn AI trên cùng bộ 10 mẫu. Mỗi lượt thuộc một tác vụ: hộp 2D, phân vùng polygon hoặc hộp 3D LiDAR.

```text
Trình duyệt (React / TypeScript)
              │
              ▼
Backend (FastAPI / SQLModel)
    ├── SQLite: dự án, nhãn, nhiệm vụ, thời gian, lượt chạy
    ├── Storage: ảnh, point cloud, tệp làm việc
    ├── CVAT local: tạo task và nhận nhãn 2D/polygon qua REST API
    └── Google Drive ↔ Colab: dữ liệu đầu vào và kết quả AI
```

Frontend cung cấp trình gán nhãn và bảng kết quả. Backend quản lý dữ liệu, đo thời gian, kiểm tra nhãn và tính điểm. Colab chạy YOLO11 cho 2D/SEG hoặc PointPillars cho 3D.

### Các thư mục chính

```text
backend/app/
  main.py               API dự án, tài nguyên và nhập nhãn
  models.py             Mô hình lưu trữ
  schemas.py            Định dạng và kiểm tra dữ liệu
  guided.py             Điều phối lượt 10 mẫu
  benchmark.py          Nhiệm vụ, timer, tổng hợp điểm, xuất CSV
  evaluation/metrics.py IoU, ghép nhãn và chỉ số đánh giá
  colab_google.py       Kết nối Google và gửi notebook
  colab_sync.py         Đồng bộ kết quả AI
  cvat_local.py         Kết nối CVAT trên máy và đồng bộ nhãn từng mẫu
frontend/src/features/
  annotation/           Trình gán nhãn ảnh và point cloud
  GuidedWorkflow.tsx    Giao diện luồng 10 mẫu
  Experiments.tsx       Bảng kết quả
colab/                  Notebook và mã trao đổi dữ liệu
scripts/                Chuẩn bị dữ liệu, sinh notebook và schema
data/test20/            Bộ mẫu được cung cấp riêng
```

### Các thực thể dữ liệu

- `Project`: tác vụ và danh sách lớp đối tượng.
- `Asset`: ảnh hoặc point cloud, tên tệp và metadata.
- `LabelSet`: bản nhãn chuẩn, AI, người tự gán nhãn hoặc người sửa AI. Nhãn sửa AI giữ `parent_id` trỏ về bản AI gốc.
- `Experiment`: bộ mẫu, nhãn chuẩn và ngưỡng IoU cố định.
- `Assignment`: nhiệm vụ của một người trên một mẫu ở một chế độ; giữ bản nháp, bản đã chốt và thời gian.
- `AnnotationEvent`: sự kiện timer, lưu và chốt nhãn.
- `GuidedRun`: tiến độ lượt 10 mẫu.
- `ColabJob`: cấu hình, danh sách mẫu và trạng thái lượt AI.

### Luồng dữ liệu

1. Chọn 10 mẫu và cố định bộ mẫu cùng nhãn chuẩn cho lượt thử nghiệm.
2. Người dùng tự gán nhãn và chốt đủ 10 mẫu. Trình gán nhãn không hiển thị nhãn chuẩn hoặc dự đoán AI ở bước này.
3. Backend gửi đầu vào, calibration cần thiết và cấu hình model qua Drive để Colab chạy. Nhãn chuẩn và nhãn người không được gửi.
4. Backend kiểm tra mã lượt, checksum, định dạng và đủ mẫu trước khi nhận kết quả AI.
5. Người dùng sửa và chốt nhãn AI. Bản AI gốc được giữ nguyên.
6. Backend so sánh từng phương pháp với nhãn chuẩn, tổng hợp điểm và thời gian.

### Kết nối CVAT local

Backend kết nối CVAT đã chạy trên localhost bằng Personal Access Token. Mỗi nhiệm vụ 2D/SEG tương ứng một task CVAT có một ảnh. Nguồn nhãn ban đầu là bản nháp của nhiệm vụ, bản AI gốc ở chế độ sửa AI hoặc danh sách rỗng ở chế độ tự gán nhãn; không gửi ground truth.

M49 lưu liên kết nhiệm vụ với máy chủ, tài khoản, task và revision. Khi nhận nhãn, backend kiểm tra tên ảnh, kích thước, frame, lớp và hình học, sau đó chốt bằng giao dịch dữ liệu. Nhiệm vụ đã thay đổi revision hoặc đã chốt không được ghi đè. Chỉ hỗ trợ Shape rectangle không xoay và polygon đơn; Track, Tag, mask và 3D không thuộc luồng kết nối này.

Tham chiếu: [CVAT Tasks API](https://docs.cvat.ai/docs/api_sdk/sdk/reference/apis/tasks-api/) và [Personal Access Tokens](https://docs.cvat.ai/docs/api_sdk/access_tokens/).

### Chuyển model riêng sang Colab

Checkpoint `.pt` được lưu trên backend bằng tên riêng và ghi SHA-256 vào request của lượt AI. Backend kiểm tra lại SHA-256 trước khi gửi, tải theo từng khối và đối chiếu dung lượng/MD5 của tệp trên Drive. Tệp tải dở được tải lại với cùng ID.

Notebook tải model theo ID Drive đã gắn với lượt chạy, kiểm tra SHA-256 trước khi nạp, rồi kiểm tra tác vụ và các lớp. Kiểm tra định dạng model thực tế diễn ra trên Colab; backend không nạp hoặc thực thi checkpoint. Nhận tệp thành công trên backend không đồng nghĩa inference thành công.

<a id="data-contract"></a>

## 2. Cấu trúc nhãn

Định dạng được khai báo trong [schemas.py](../backend/app/schemas.py) và [JSON schema](label-bundle.schema.json).

Một bộ nhãn chứa tác vụ, tên, người thực hiện, nguồn AI liên quan, thông tin lượt chạy và danh sách mẫu. Mỗi mẫu chứa `asset_name`, danh sách `objects` và thời gian nếu có.

Mỗi đối tượng có ID duy nhất trong mẫu, lớp, hình học và confidence. Nhãn AI phải có confidence từ 0 đến 1. Danh sách đối tượng rỗng nghĩa là mẫu đã gán nhãn nhưng không có đối tượng; khác với mẫu thiếu kết quả hoặc nhiệm vụ chưa chốt.

- **Hộp 2D:** `xyxy = [x1, y1, x2, y2]`, đơn vị pixel ảnh gốc; x sang phải, y xuống. Yêu cầu x2 > x1, y2 > y1.
- **Polygon:** danh sách ít nhất 3 đỉnh ở tọa độ ảnh gốc, không tự giao; chỉ hỗ trợ polygon đơn, không có lỗ hoặc nhiều vùng rời.
- **Hộp 3D:** tâm hình học `[x, y, z]`, kích thước `[dài, rộng, cao]` và yaw. Hệ LiDAR: x tiến, y trái, z lên; đơn vị mét, yaw tính bằng radian quanh trục z.

## 3. Tính độ chồng khớp

### Hộp 2D

`IoU = diện tích giao / diện tích hợp`

Diện tích hộp bằng `(x2 − x1) × (y2 − y1)`, không cộng 1.

### Phân vùng polygon

Polygon được chuyển thành mask ở độ phân giải ảnh gốc theo tâm pixel.

- `IoU = |P ∩ G| / |P ∪ G|`
- `Dice = 2 × |P ∩ G| / (|P| + |G|)`

P là vùng dự đoán, G là vùng chuẩn. Polygon tạo mask rỗng bị từ chối.

### Hộp 3D

`Thể tích giao = diện tích giao hai đáy xoay yaw × độ cao giao`

`IoU3D = thể tích giao / (thể tích A + thể tích B − thể tích giao)`

Phép tính dùng thể tích 3D.

<a id="scoring"></a>

## 4. Ghép nhãn và tính điểm

Code tính toán nằm trong [metrics.py](../backend/app/evaluation/metrics.py); phần tổng hợp ở [benchmark.py](../backend/app/benchmark.py).

Nhãn được ghép độc lập theo từng mẫu và từng lớp. Một cặp hợp lệ phải cùng lớp và có IoU ≥ ngưỡng của thử nghiệm, mặc định 0,5. Mỗi nhãn chỉ được ghép một lần. Thuật toán ưu tiên tối đa số cặp hợp lệ, sau đó tối đa tổng IoU.

### Số lượng đối tượng

- **Tìm đúng (TP):** số cặp ghép hợp lệ.
- **Vẽ thừa hoặc sai (FP):** số nhãn dự đoán không ghép được.
- **Bỏ sót (FN):** số đối tượng chuẩn không được ghép.
- **Tổng đối tượng chuẩn:** TP + FN.
- **Tổng nhãn dự đoán:** TP + FP.

Một hộp vẽ sai vị trí có thể làm tăng cả FP và FN: hộp dự đoán không ghép được, còn đối tượng chuẩn vẫn bị bỏ sót. Hai hộp trùng nhau cùng dự đoán một đối tượng chỉ có tối đa một hộp được tính là tìm đúng.

### Các chỉ số

- **Tỷ lệ nhãn đúng (Precision):** TP / (TP + FP).
- **Mức độ đầy đủ (Recall):** TP / (TP + FN).
- **Điểm F1:** 2TP / (2TP + FP + FN).
- **Độ khớp các nhãn đúng:** tổng IoU của các cặp ghép / TP.

Mẫu số bằng 0 trả `null`, giao diện hiện N/A. Hai bộ nhãn cùng rỗng không được tự gán F1 = 100%. IoU trung bình chỉ tính trên các cặp ghép đúng, không phản ánh số đối tượng bị bỏ sót.

### Tổng hợp cả bộ 10 mẫu

Cộng TP, FP và FN của tất cả mẫu đã hoàn thành cho từng phương pháp, rồi mới tính Precision, Recall và F1. Đây là micro-F1; không lấy trung bình phần trăm F1 của từng ảnh. IoU tổng bằng tổng IoU của mọi cặp ghép chia cho tổng TP.

**Tiến độ mẫu** = số mẫu đã hoàn thành / tổng số mẫu của thử nghiệm, kể cả mẫu chưa tạo nhiệm vụ. Tiến độ này khác với mức độ đầy đủ của đối tượng.

Chỉ nhãn người đã chốt được chấm. Mẫu đã chốt với nhãn rỗng vẫn được chấm và toàn bộ đối tượng chuẩn trong mẫu đó được tính là bỏ sót. Mẫu chưa chốt hoặc thiếu kết quả bị loại khỏi chỉ số và báo riêng ở tiến độ. Khi chưa đủ 10 mẫu, điểm là tạm tính; các phương pháp có thể đang được chấm trên các tập mẫu khác nhau.

## 5. Tính thời gian

Timer server cộng thời gian thao tác và quan sát. Frontend gửi heartbeat mỗi 10 giây; mỗi lần chỉ ghi nhận tối đa 30 giây kể từ mốc đang chạy. Khi lease hết hạn, người dùng cần tiếp tục timer; heartbeat muộn không tự khởi động lại.

Chỉ so sánh các cặp cùng người, cùng mẫu, có cả nhãn tự làm và nhãn sửa AI đã chốt. Gọi M là tổng thời gian tự làm và A là tổng thời gian sửa AI trên các cặp đó:

- **Tiết kiệm:** M − A.
- **Tăng tốc:** M / A.
- **Tỷ lệ giảm:** 1 − A / M.

Chỉ tính ba chỉ số này khi mọi cặp đều có thời gian server đo dương. Thời gian nhập tay từ CVAT không được dùng để tính tăng tốc: kết nối CVAT ghi thời gian từng mẫu với nguồn `declared_cvat_sample`; nhập tệp COCO ghi tổng thời gian chia đều với nguồn `declared_total_uniformly_distributed`. Số tiết kiệm âm nghĩa là sửa AI chậm hơn tự làm.

Thời gian AI inference được báo riêng, không cộng vào thời gian người thao tác. Các chỉ số trên chưa bao gồm truyền dữ liệu hoặc thiết lập. Trong CSV, các cột tổng thời gian được lặp trên từng dòng mẫu; không cộng lại các cột tổng này.

## 6. Phạm vi phép đánh giá

M49 đánh giá bộ nhãn cuối theo ngưỡng IoU cố định, không tính COCO/KITTI AP chính thức. Với 3D, phạm vi đánh giá gồm lớp car có tâm hộp trong góc nhìn camera, x thuộc [0; 69,12) m và y thuộc [−39,68; 39,68) m.

Mỗi thử nghiệm hỗ trợ tối đa 20 mẫu, 40 nhiệm vụ và 3 bản AI trong dự án khi chấm. Mỗi mẫu có tối đa 80 đối tượng mỗi phía; SEG giới hạn 4 triệu pixel/ảnh và 32 triệu pixel tổng mask/mẫu.

Bộ mẫu gồm 10 mẫu và thứ tự tự làm trước, sửa AI sau có thể tạo hiệu ứng nhớ. Phạm vi đánh giá giới hạn trong bộ mẫu được chọn, không đại diện cho toàn bộ dataset.
