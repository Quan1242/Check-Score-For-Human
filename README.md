# M49 — Human vs AI Annotation Benchmark

M49 là bộ khung ứng dụng local để xây dựng thử nghiệm so sánh ba phương pháp gán nhãn:

- **Manual:** người gán nhãn từ đầu.
- **AI:** kết quả dự đoán do mô hình tạo.
- **Assisted:** người chỉnh sửa kết quả AI.

Phạm vi dữ liệu gồm bounding box 2D, instance segmentation và bounding box 3D. Backend hiện nhận dữ liệu theo schema JSON nội bộ M49; AI được chạy riêng, ví dụ trên Google Colab, rồi nhập kết quả vào ứng dụng.

> **Trạng thái:** đây là scaffold phát triển, chưa phải hệ thống benchmark hoàn chỉnh. Ứng dụng hiện hỗ trợ quản lý dự án, nhập dữ liệu và lưu các phiên bản nhãn; chưa có editor hình học tương tác hoặc bộ tính điểm. Xem [Roadmap](docs/ROADMAP.md) để biết các phần còn thiếu.

## Tính năng hiện có

- Tạo dự án theo tác vụ và khai báo danh sách lớp.
- Tải ảnh JPG/PNG; dự án 3D cũng nhận BIN/PCD.
- Xem danh sách tài nguyên và xem trước ảnh.
- Nhập ground truth và kết quả AI bằng JSON theo schema M49.
- Kiểm tra tác vụ, tên mẫu, lớp, hình học, confidence và giới hạn tọa độ ảnh.
- Tạo phiên bản nhãn manual hoặc assisted từ giao diện JSON; bản AI gốc được giữ riêng.
- Lưu dữ liệu trong SQLite khi chạy trực tiếp, hoặc PostgreSQL và Docker volumes khi chạy bằng Docker Compose.
- Cung cấp API và tài liệu OpenAPI tại `/docs`.

## Chưa được triển khai

- Vẽ/chỉnh box, polygon, mask hoặc cuboid bằng chuột; overlay nhãn.
- Autosave, undo/redo, timer, event log và chia nhiệm vụ.
- Bộ chấm IoU/F1/AP, dashboard chất lượng, báo cáo thời gian và chi phí.
- Huấn luyện hoặc inference model trong ứng dụng. Các notebook trong `colab/` chỉ là template, chưa kết nối mô hình.
- Adapter nhập trực tiếp định dạng BDD100K/KITTI/COCO, calibration và ghép ảnh–LiDAR.
- Đăng nhập, phân quyền và bảo vệ ground truth ở API.

Ứng dụng hiện phù hợp để phát triển và thử nghiệm local một người, **chưa phù hợp để tổ chức benchmark mù nhiều người**. Công thức đánh giá được ghi riêng trong [Đặc tả công thức đánh giá](docs/RATE_SCORE.md); tài liệu công thức không có nghĩa là bộ chấm đã được cài vào ứng dụng.

## Chạy bằng Docker

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

Yêu cầu Python 3.11 trở lên (khuyến nghị 3.12), Node.js 22 và pnpm 10.11.0.

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Trên Ubuntu, nếu tạo virtual environment thất bại, cài gói `python3-venv` phù hợp với phiên bản Python. Trên Windows, kích hoạt bằng `.venv\Scripts\activate`.

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

## Thử luồng nhập/lưu với dữ liệu mẫu

1. Tạo dự án `Demo 2D`, chọn tác vụ **Bounding box 2D** và lớp `car`.
2. Trong mục **Dữ liệu**, tải `examples/demo.png`.
3. Nhập `examples/ground_truth_2d.json` làm ground truth.
4. Nhập `examples/ai_2d.json` làm kết quả AI.
5. Mở mục **Gán nhãn**, chọn chế độ người sửa AI, nhập tên người gán nhãn và chọn lần chạy AI.
6. Sửa JSON rồi lưu phiên bản assisted.
7. Mở mục **Kết quả** để xem số lượng phiên bản nhãn đã lưu.

Đây là luồng kiểm tra nhập/lưu, **không phải phép đánh giá chất lượng**. Ảnh và nhãn mẫu là dữ liệu tổng hợp, không phải dữ liệu hoặc kết quả BDD100K thực tế. Không dùng chúng trong báo cáo thí nghiệm.

Ví dụ khác:

- Segmentation: tạo dự án segmentation, tải ảnh mẫu và nhập `examples/ai_segmentation.json`.
- 3D: tạo dự án 3D, tải `examples/demo.bin` và nhập `examples/ai_3d.json`. BIN mẫu chỉ có vài điểm tổng hợp, không phải cảnh LiDAR thực tế.

## Hợp đồng dữ liệu và đánh giá

- [Hợp đồng dữ liệu M49](docs/DATA_CONTRACT.md): schema, hệ tọa độ và quy tắc nhãn.
- [Đặc tả công thức đánh giá](docs/RATE_SCORE.md): các chỉ số cho bộ nhãn cuối và công thức tham chiếu COCO/KITTI.
- [Kiến trúc](docs/ARCHITECTURE.md): các thành phần và cách lưu dữ liệu.
- [Roadmap](docs/ROADMAP.md): các mốc phát triển.

JSON M49 là định dạng nội bộ, không phải định dạng gốc của BDD100K/KITTI/COCO. Cần adapter chuyển đổi trước khi nhập dữ liệu từ các bộ dữ liệu đó.

M49 phân biệt **đánh giá chất lượng bộ nhãn cuối** với **đánh giá detector theo benchmark**. COCO-style AP và KITTI AP_R40 có quy tắc matching riêng, không thay thế cho TP/FP/FN, Precision, Recall, F1 và IoU của giao thức M49. Hiện các phép tính này mới được mô tả trong tài liệu, chưa được ứng dụng thực thi.

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
```

Backend tests dùng SQLite in-memory và vùng lưu tạm. Xem [Kết quả xác nhận](docs/VALIDATION.md) để biết phạm vi xác minh đã ghi nhận.

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

Các dependencies được pin để hỗ trợ tái lập môi trường. `backend/requirements-lock.txt` được dùng làm constraints cho dependencies Python. Mô hình AI/checkpoint chưa được chọn hoặc tải khi khởi động ứng dụng; cần xác minh và pin riêng khi tích hợp.
