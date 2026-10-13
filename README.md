# M49 — Human vs AI Annotation Benchmark

**13/10/2026 — AI qua Google:** bước AI có kết nối OAuth Google Drive, tự tải đúng ảnh/model của lượt và tạo notebook sẵn cấu hình. Bạn bấm Run all/cấp quyền trong Colab cá nhân; kết quả tự về web. Không cần kéo file hoặc nhập mã lượt. Cần cấu hình OAuth client Desktop một lần; xem [hướng dẫn](docs/GUIDED_WORKFLOW.md#kết-nối-google-một-lần-trên-máy-local). 63 test backend (Google giả lập) và build frontend đạt; chưa kiểm chứng OAuth/Drive/Colab thật. Cập nhật này thay thế hướng dẫn Drive Desktop cho các lượt mới.

**Cập nhật 12/10/2026:** thêm nhập trực tiếp BDD100K box 2D và KITTI 2D/3D từ thư mục local; timer tự bắt đầu khi mở nhiệm vụ; Colab 2D/segmentation tự gửi kết quả qua thư mục Google Drive đồng bộ. Xem [hướng dẫn dataset, timer và Drive](docs/DATASETS_COLAB.md). 49 test backend, 5 test frontend và build đạt; chưa chạy dataset/GPU/Drive thật. Notebook AI 3D còn template. Nội dung cập nhật này được ưu tiên hơn các ghi chú lịch sử bên dưới.

**Luồng hiện tại:** mở web và chọn tác vụ test để chạy một lượt 10 Manual → AI → 10 Assisted → tự chấm ba kiểu; có chọn/tải checkpoint cho Colab và tiếp tục tiến độ đã lưu. Xem [hướng dẫn luồng khép kín](docs/GUIDED_WORKFLOW.md). Hiện mở cho 2D BDD100K/KITTI; segmentation thiếu ground truth, 3D thiếu pipeline AI nên được khóa kèm lý do. 52 test backend và 5 test frontend đạt; build thành công.

**Chọn mẫu tự động:** màn hình bắt đầu đã bỏ chọn dataset; chỉ chọn tác vụ và ứng dụng bốc ngẫu nhiên 10 ảnh không trùng. Với 2D, kho ảnh gồm cả BDD100K và KITTI. Danh sách được lưu cố định cho Manual/AI/Assisted và khi tiếp tục lượt cũ.

M49 là bộ khung ứng dụng local để xây dựng thử nghiệm so sánh ba phương pháp gán nhãn:

- **Manual:** người gán nhãn từ đầu.
- **AI:** kết quả dự đoán do mô hình tạo.
- **Assisted:** người chỉnh sửa kết quả AI.

**Phạm vi demo (10/10/2026):** một người thao tác lần lượt trên máy cá nhân, dùng bộ mẫu nhỏ. Ưu tiên chạy trực tiếp với SQLite; Docker/PostgreSQL là tùy chọn. AI chạy riêng trên Colab hoặc nhập kết quả đã xuất sẵn để giảm tải máy local. Xem [roadmap demo một người](docs/ROADMAP.md) để biết việc cần làm và các chức năng tạm hoãn. Đây là phạm vi vận hành, chưa có cơ chế giới hạn một người dùng trong code.

Phạm vi dữ liệu gồm bounding box 2D, instance segmentation và bounding box 3D. Backend hiện nhận dữ liệu theo schema JSON nội bộ M49; AI được chạy riêng, ví dụ trên Google Colab, rồi nhập kết quả vào ứng dụng.

> **Trạng thái hiện tại:** 41 test backend Python 3.14 và 5 test hình học frontend đạt; frontend build thành công. Chưa nghiệm thu giao diện thực tế, inference Colab hoặc toàn bộ Docker stack. Xem [Roadmap](docs/ROADMAP.md) và [Kiểm tra đã thực hiện](docs/VALIDATION.md).

## Năng lực hệ thống

Giao diện hiện chỉ mở luồng test khép kín; các chức năng quản trị dữ liệu bên dưới vẫn có qua API/script.

- Quy trình CVAT: xuất ảnh/lớp và nhãn AI COCO ZIP, nhập Manual/Assisted cho box 2D hoặc polygon đơn vào Experiment. Thời gian khai báo được ghi rõ trong báo cáo/CSV.

- Tạo dự án theo tác vụ và khai báo danh sách lớp.
- Tải ảnh JPG/PNG; dự án 3D cũng nhận BIN/PCD.
- Xem danh sách tài nguyên và xem trước ảnh.
- Nhập ground truth và kết quả AI bằng JSON theo schema M49.
- Kiểm tra tác vụ, tên mẫu, lớp, hình học, confidence và giới hạn tọa độ ảnh.
- Editor SVG vẽ/kéo/resize box 2D; vẽ polygon, kéo đỉnh hoặc cả hình; zoom/pan.
- Viewer point cloud BIN/PCD ASCII/binary, top/front/side views; chỉnh tâm/kích thước/yaw bằng trường số hoặc chuột ở góc trực giao.
- Experiment khóa ground truth, mẫu và ngưỡng IoU; Assignment lưu bản nháp/chốt phiên bản cuối, chống ghi đè bằng revision.
- Undo/redo, autosave 900 ms, timer resume/pause phía server và event log; bản AI gốc được giữ riêng.
- Chấm IoU 2D, mask IoU/Dice và IoU cuboid 3D; matching tối ưu hai cấp; TP/FP/FN, Precision/Recall/F1, completion và CSV.
- Script nhập dữ liệu hàng loạt và converter box2d BDD100K theo manifest/lớp.
- Lưu dữ liệu trong SQLite khi chạy trực tiếp, hoặc PostgreSQL và Docker volumes khi chạy bằng Docker Compose.
- Cung cấp API và tài liệu OpenAPI tại `/docs`.

## Chưa được triển khai

- Brush/mask có holes/multipart/RLE, chỉnh cuboid bằng chuột ở góc nhìn tùy ý (hiện chỉ chỉnh ở góc trực giao), PCD nén.
- COCO/KITTI AP chính thức, báo cáo chi phí, thống kê chỉnh sửa chi tiết và dashboard nâng cao.
- Huấn luyện hoặc inference model trong ứng dụng. Notebook 2D/segmentation có pipeline Colab chưa chạy kiểm chứng; 3D còn là template.
- COCO RLE/multipart và ghép ảnh–LiDAR trực quan; importer KITTI đã có box 2D và cuboid 3D với calibration, BDD100K có box2d, trao đổi CVAT COCO có box2d và polygon đơn.
- Đăng nhập, phân quyền và bảo vệ ground truth ở API.

Ứng dụng hướng tới phát triển và thử nghiệm local, **chưa phù hợp để tổ chức benchmark mù nhiều người**. Editor endpoint không trả ground truth payload nhưng API quản trị chưa có xác thực/phân quyền. Công thức đánh giá ở [RATE_SCORE](docs/SYSTEM.md#scoring); implementation mới còn chờ xác minh.

## Chạy bằng Docker

**Cập nhật demo 10/10/2026:** đã thêm code heartbeat/idle cho timer, giới hạn tải chấm và so sánh thời gian manual/assisted, chưa chạy test/build. Timer mất kết nối chỉ cộng tối đa 30 giây từ heartbeat cuối. Xem [quy trình demo và checklist tự kiểm tra](docs/DEMO_PROTOCOL.md). Chạy một backend worker; chốt/tạm dừng timer bản cũ trước khi nâng cấp. Không thay schema database.

Yêu cầu Docker Engine/Desktop và Docker Compose.

```bash
cp .env.example .env
docker compose up --build
```

Truy cập:

- Website: <http://localhost:3000>
- API: <http://localhost:8000>
- Swagger UI: <http://localhost:8000/docs>
- Health check: <http://localhost:8000/api/health>

Các cổng chỉ bind vào `127.0.0.1`; PostgreSQL không mở cổng ra host.

Dừng ứng dụng:

```bash
docker compose down
```

Lệnh này giữ dữ liệu trong Docker volumes. Chỉ dùng `docker compose down -v` khi chủ động muốn xóa database và các tệp đã tải lên.

## Chạy trực tiếp để phát triển

**Chạy nhanh trên Windows:** sau khi cài dependency theo hướng dẫn dưới đây, nhấp đúp
`chay_web.bat` tại thư mục gốc. File mở hai cửa sổ backend/frontend và tự mở trình duyệt
khi cả hai server sẵn sàng. Giữ hai cửa sổ trong lúc dùng; nhấn Ctrl+C trong từng cửa sổ
để dừng. File không tự nâng/cài thư viện và báo lỗi nếu cổng 8000 hoặc 5173 đang bận.
Có thể chạy `chay_web.bat --check` để chỉ kiểm tra môi trường.

Yêu cầu **CPython 3.14.x (bản tiêu chuẩn, không phải free-threaded)**, Node.js 22 và pnpm 10.11.0. File `.python-version` và Docker đều dùng 3.14. Môi trường backend thống nhất ở `.venv/` tại thư mục gốc dự án.

### Backend

```bash
python3.14 -m venv .venv
source .venv/bin/activate
python -m pip install --only-binary=:all: -r backend/requirements-dev.txt
python -m pip check
cd backend
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Trên Windows PowerShell, chạy từ thư mục gốc dự án:

```powershell
python --version  # Phải là 3.14.x
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --only-binary=:all: -r backend/requirements-dev.txt
.\.venv\Scripts\python.exe -m pip check
.\scripts\run_backend.ps1
```

Script chạy dùng đúng `.venv` và kiểm tra Python 3.14 trước khi khởi động. Không dùng `.venv-cvat` (môi trường 3.12 từ lần kiểm tra trước). Nếu đã có `.venv` của phiên bản Python khác, hãy tạo môi trường 3.14 sạch, không cài đè thư viện vào môi trường đó. Trên Ubuntu, cài gói venv tương ứng Python 3.14 nếu thiếu.

### Frontend

Mở terminal thứ hai:

```bash
cd frontend
corepack enable
corepack prepare pnpm@10.11.0 --activate
pnpm install --frozen-lockfile
pnpm dev
```

Mở <http://localhost:5173>. Vite chuyển tiếp các yêu cầu `/api` đến backend. Khi chạy backend, giữ working directory là `backend/` để SQLite và vùng lưu tệp được đặt đúng chỗ.

## Chạy thử nghiệm

Mở web, chọn tác vụ muốn test, nhập tên và bắt đầu. Ứng dụng tự tạo dự án, chọn 10 mẫu và dẫn qua Manual → AI trên Colab → Assisted → kết quả. Có thể tiếp tục lượt đã lưu sau khi tải lại trang.

Xem [hướng dẫn từng bước](docs/GUIDED_WORKFLOW.md). Các màn hình chọn/tạo dự án, nhập dữ liệu nâng cao và CVAT đã được bỏ khỏi giao diện. API và script chuẩn bị dữ liệu vẫn được giữ; các file trong `examples/` là fixture tổng hợp, không phải kết quả thực nghiệm.

## Hợp đồng dữ liệu và đánh giá

### Chỉnh cuboid 3D bằng chuột

Bắt đầu timer, chọn hộp trong danh sách hoặc nhấp cạnh hộp. Ở góc **Trên**, kéo **Tâm** để
dịch trên XY, **Dài/Rộng** để resize quanh tâm, **Xoay** để đổi yaw. Ở góc **Trước/Bên**,
kéo Tâm trên YZ/XZ hoặc kéo **Cao**. Zoom để thấy rõ các nút. Mỗi lần thả chuột tạo một bước Undo;
autosave theo cơ chế hiện có. Trường số vẫn dùng để chỉnh chính xác.
Phối cảnh/góc tùy ý chỉ dùng quan sát; kéo nền để pan. Dừng timer hoặc chốt nhiệm vụ thì không sửa nhãn.

### Tài liệu tham khảo

- [Quy ước hệ thống](docs/SYSTEM.md): kiến trúc, schema, hệ tọa độ, quy tắc nhãn và công thức đánh giá.
- [Roadmap](docs/ROADMAP.md): các mốc phát triển.

JSON M49 là định dạng nội bộ, không phải định dạng gốc của BDD100K/KITTI/COCO. Có thể chuyển box2d BDD100K bằng `scripts/convert_bdd100k.py` với manifest JSON danh sách tên ảnh:

```bash
python scripts/convert_bdd100k.py --input data/bdd_labels.json --manifest data/pilot.json --classes car,pedestrian,truck --output data/pilot/ground_truth/labels.json
python scripts/import_folder.py --project PROJECT_ID --data data/pilot
```

Thư mục nhập gồm `assets/`, `ground_truth/` và `ai/`. Script upload assets trước rồi ground truth/AI; dừng ở lỗi đầu, không rollback các upload trước đó. `--skip-existing-assets` chỉ bỏ qua theo tên, không so sánh nội dung. Mỗi lần nhập JSON tạo snapshot mới. `data/` được bỏ ngoài git.

M49 phân biệt **đánh giá chất lượng bộ nhãn cuối** với **đánh giá detector theo benchmark**. COCO-style AP và KITTI AP_R40 có quy tắc matching riêng, không thay thế cho TP/FP/FN, Precision, Recall, F1 và IoU của giao thức M49. Code mới chỉ triển khai metric nhãn cuối M49.

## API chính

| Method | Endpoint | Chức năng |
|---|---|---|
| `GET`, `POST` | `/api/projects` | Liệt kê hoặc tạo dự án |
| `GET`, `POST` | `/api/projects/{id}/assets` | Liệt kê hoặc tải tài nguyên |
| `GET` | `/api/assets/{id}/file` | Đọc ảnh hoặc point cloud |
| `POST` | `/api/projects/{id}/imports/ground_truth` | Nhập ground truth JSON |
| `POST` | `/api/projects/{id}/imports/ai` | Nhập kết quả AI JSON |
| `POST` | `/api/projects/{id}/annotations/manual` | Lưu nhãn manual |
| `POST` | `/api/projects/{id}/annotations/assisted` | Lưu nhãn assisted |
| `GET` | `/api/projects/{id}/label-sets` | Liệt kê metadata các bộ nhãn |
| `GET` | `/api/label-sets/{id}` | Đọc nội dung một bộ nhãn |
| `GET` | `/api/projects/{id}/summary` | Đếm tài nguyên và phiên bản nhãn |

Upload dùng multipart field `file`, giới hạn 32 MiB mỗi tệp. API nhận từng tệp; giao diện tải nhiều tệp tuần tự. Nếu một tệp lỗi, các tệp đã tải thành công trước đó vẫn được giữ.

## Kiểm thử

Backend:

```bash
cd backend
python -m pytest -q
```

Frontend:

```bash
cd frontend
pnpm build
pnpm test
```

Backend tests dùng SQLite in-memory và vùng lưu tạm. Kết quả và giới hạn kiểm tra ở [VALIDATION](docs/VALIDATION.md).
Database vẫn dùng `create_all` để thêm bảng chưa có, chưa có migration Alembic. Kiểm tra trên bản sao khi nâng cấp dữ liệu thật.

## Cấu trúc dự án

```text
.
├── backend/       # FastAPI, SQLModel, kiểm tra và lưu nhãn
├── frontend/      # React, TypeScript, Vite
├── colab/         # Notebook template theo từng tác vụ
├── docs/          # Kiến trúc, hợp đồng dữ liệu, công thức, roadmap
├── examples/      # Dữ liệu tổng hợp dùng thử
├── scripts/       # Công cụ phát triển schema
└── compose.yaml   # Backend, frontend và PostgreSQL
```

Các dependency trực tiếp được pin trong `backend/requirements.in` và `requirements-dev.in`; dependency gián tiếp được khóa trong `backend/requirements-lock.txt` với điều kiện nền tảng Windows/Linux. Luôn cài qua `requirements.txt` hoặc `requirements-dev.txt`, không cài thẳng `.in`. Mô hình AI chạy riêng trên Colab; không cài PyTorch/YOLO vào backend. Xem [hướng dẫn notebook](colab/README.md).

Sau khi chủ động đổi pin, tạo lại khóa từ thư mục gốc bằng:

```powershell
uv pip compile backend/requirements-dev.in --universal --python-version 3.14 --only-binary :all: --output-file backend/requirements-lock.txt
```

Chỉ thêm `--upgrade` khi cần nâng dependency gián tiếp và kiểm tra lại. Không chép venv/site-packages giữa các phiên bản Python.
