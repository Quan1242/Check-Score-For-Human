# M49 — Human vs AI Annotation Benchmark

Bộ khung website chạy local cho đề tài so sánh **manual / AI / AI + người** trên ba tác vụ: bounding box 2D, instance segmentation và bounding box 3D. AI chạy ngoài hệ thống trên Colab; website nhập kết quả về.

Đây là **scaffold để phát triển tiếp**, chưa phải hệ thống benchmark hoàn chỉnh. Không hiển thị điểm đánh giá hoặc dữ liệu thí nghiệm giả.

## Những gì đã chạy được

- Tạo và chọn dự án theo tác vụ, định nghĩa các lớp.
- Upload nhiều ảnh JPG/PNG qua giao diện; dự án 3D nhận thêm BIN/PCD.
- Xem trước ảnh và danh sách tài nguyên.
- Nhập ground truth / AI dưới dạng JSON theo schema nội bộ M49.
- Kiểm tra tên mẫu, lớp, hình học, confidence, giới hạn tọa độ ảnh và quan hệ bản nhãn sửa AI.
- Sửa danh sách đối tượng bằng JSON, lưu phiên bản manual hoặc assisted vào database.
- Nạp bản sao nhãn AI để sửa; giữ nguyên dự đoán AI ban đầu.
- Thống kê số tài nguyên và phiên bản nhãn; API OpenAPI tại `/docs`.
- PostgreSQL + vùng lưu tệp bền vững bằng Docker; SQLite khi chạy trực tiếp.

## Chưa triển khai

- Trình vẽ bounding box, polygon/brush và chỉnh hộp 3D bằng chuột.
- Overlay nhãn, autosave, undo/redo, timer và lịch sử thao tác.
- Upload ZIP, upload tiếp tục, thanh tiến trình theo byte.
- Adapter chuyển trực tiếp BDD100K/KITTI/COCO; hiệu chỉnh camera và ghép ảnh–LiDAR.
- Mask dạng bitmap/RLE hoặc polygon có lỗ; schema hiện chỉ hỗ trợ một polygon đơn cho mỗi instance.
- Train/inference hoàn chỉnh: notebook chỉ là mẫu hợp đồng xuất dữ liệu, chưa kết nối model.
- IoU, AP, tổng hợp thời gian, chi phí, correction rate và xuất báo cáo.
- Tài khoản, phân quyền, chia nhiệm vụ, migrations và triển khai public.

Ground truth được ẩn khỏi màn hình gán nhãn, **chưa được bảo vệ bằng phân quyền API**. Bản này dùng cho phát triển local một người; chưa dùng nguyên trạng để tổ chức benchmark mù nhiều người.

## Chạy nhanh bằng Docker

Yêu cầu Docker Engine/Desktop và Docker Compose; tài khoản hệ điều hành phải có quyền truy cập Docker daemon.

```bash
cp .env.example .env
docker compose up --build
```

Mở:

- Website: http://localhost:3000
- Swagger API: http://localhost:8000/docs
- Health: http://localhost:8000/api/health

Các cổng chỉ bind `127.0.0.1`. PostgreSQL không mở cổng ra máy chủ.

```bash
docker compose down
```

Lệnh trên giữ database và uploads trong Docker volumes. `docker compose down -v` xóa toàn bộ các volumes của dự án, chỉ dùng khi chủ động muốn reset dữ liệu.

## Chạy trực tiếp để phát triển

Yêu cầu Python 3.11+ (khuyến nghị 3.12), Node.js 22 và pnpm 10.11.0.

Terminal 1:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Trên Ubuntu, nếu không tạo được venv, cài gói `python3-venv` tương ứng. Windows dùng `.venv\Scripts\activate`.

Terminal 2:

```bash
cd frontend
corepack enable
corepack prepare pnpm@10.11.0 --activate
pnpm install --frozen-lockfile
pnpm dev
```

Mở http://localhost:5173. Vite chuyển `/api` đến backend, tương tự Nginx trong Docker. Chạy backend từ thư mục `backend/` để database SQLite và storage được tạo đúng chỗ.

## Thử nhanh với dữ liệu mẫu

1. Tạo dự án `Demo 2D`, tác vụ `Bounding box 2D`, một lớp `car`.
2. Upload `examples/demo.png` ở mục dữ liệu.
3. Import `examples/ground_truth_2d.json` vào ground truth.
4. Import `examples/ai_2d.json` vào kết quả AI.
5. Mở **Gán nhãn**, chọn **Người sửa AI**, điền người thực hiện và chọn lần chạy AI.
6. Sửa tọa độ trong JSON, điền thời gian đo bên ngoài nếu có, rồi lưu.
7. Mở **Kết quả** để kiểm tra số phiên bản nhãn.

Ảnh và nhãn mẫu là hình học tổng hợp dùng kiểm tra luồng nhập/lưu; không phải dữ liệu hoặc kết quả BDD100K thực tế. Không dùng chúng trong báo cáo thí nghiệm.

Với segmentation, tạo dự án tương ứng, upload cùng ảnh rồi nhập `examples/ai_segmentation.json`. Với 3D, dùng `examples/demo.bin` và `examples/ai_3d.json`. BIN mẫu chỉ có vài điểm tổng hợp, không phải cảnh LiDAR thực tế.

## Cấu trúc thư mục

```text
m49-benchmark/
├── compose.yaml
├── backend/
│   ├── app/
│   │   ├── main.py           # API, upload, kiểm tra và lưu nhãn
│   │   ├── models.py         # Project, Asset, LabelSet
│   │   ├── schemas.py        # Hợp đồng dữ liệu ba tác vụ
│   │   ├── db.py             # PostgreSQL / SQLite + storage
│   │   ├── adapters/         # Điểm mở rộng BDD100K, KITTI, Colab
│   │   └── evaluation/       # Điểm mở rộng bộ chấm từng tác vụ
│   └── tests/                # Kiểm thử upload và tính toàn vẹn nhãn
├── frontend/src/
│   ├── App.tsx               # Dự án, upload, kết quả
│   ├── api.ts                # Gọi API
│   └── features/annotation/  # Không gian sửa JSON; thay bằng editor
├── colab/                    # Ba notebook template và hướng dẫn
├── examples/                 # Dữ liệu tổng hợp thử API/UI
├── docs/                     # Kiến trúc, schema, roadmap
└── scripts/                  # Export JSON Schema
```

## API chính

| Method | Endpoint | Chức năng |
|---|---|---|
| GET/POST | `/api/projects` | Xem/tạo dự án |
| GET/POST | `/api/projects/{id}/assets` | Xem/upload một tài nguyên |
| GET | `/api/assets/{id}/file` | Đọc ảnh/point cloud |
| POST | `/api/projects/{id}/imports/ground_truth` | Import JSON chuẩn |
| POST | `/api/projects/{id}/imports/ai` | Import JSON AI |
| POST | `/api/projects/{id}/annotations/manual` | Lưu phiên bản manual |
| POST | `/api/projects/{id}/annotations/assisted` | Lưu phiên bản sửa AI |
| GET | `/api/projects/{id}/label-sets` | Metadata các phiên bản |
| GET | `/api/label-sets/{id}` | Nội dung JSON một phiên bản |
| GET | `/api/projects/{id}/summary` | Số lượng, chưa phải điểm đánh giá |

Upload dùng multipart field `file`. Mỗi tệp tối đa 32 MiB. API nhận từng tệp; giao diện upload nhiều tệp tuần tự. Khi một tệp lỗi, các tệp trước đó đã thành công vẫn được giữ.

## Kiểm thử

```bash
cd backend
python -m pytest -q
```

```bash
cd frontend
pnpm build
```

Tests dùng SQLite in-memory và storage tạm, không sửa dữ liệu local. Xem `docs/VALIDATION.md` về kết quả kiểm tra bộ khung được bàn giao.

## Bước phát triển tiếp

Theo `docs/ROADMAP.md`: ưu tiên hoàn thiện editor 2D và bộ chấm 2D trước, sau đó segmentation và 3D. Theo dõi việc ánh xạ lớp và hệ tọa độ trong `docs/DATA_CONTRACT.md`.

Dependencies được pin để tái lập khung chạy; `backend/requirements-lock.txt` ghi lại môi trường Python đã kiểm thử và được dùng làm constraints. Mô hình AI cần được xác minh và pin riêng tại thời điểm tích hợp; bộ khung không tải checkpoint hay GPU model khi khởi động website.
