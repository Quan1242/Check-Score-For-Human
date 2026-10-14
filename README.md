# M49 — Human vs AI Annotation Benchmark

Ứng dụng local so sánh **Manual**, **AI** và **Assisted** trên cùng 10 mẫu và cùng ground truth. Người dùng gán nhãn từ đầu, chạy AI trên Colab cá nhân, sửa nhãn AI rồi xem điểm và thời gian.

Hỗ trợ box 2D, instance segmentation bằng polygon đơn và cuboid 3D LiDAR. Giao diện chọn tác vụ; dự án và thử nghiệm được tạo tự động. Chạy một người, một backend worker trên máy cá nhân.

## Chạy trên Windows

Yêu cầu Python 3.14.x tiêu chuẩn và Node.js 22. Từ thư mục gốc:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --only-binary=:all: -r backend/requirements-dev.txt
.\.venv\Scripts\python.exe -m pip check
cd frontend
npx --yes pnpm@10.11.0 install --frozen-lockfile
cd ..
.\chay_web.bat
```

Mở <http://127.0.0.1:5173>. File BAT mở backend và frontend; giữ hai cửa sổ trong lúc dùng. Chạy `chay_web.bat --check` để kiểm tra môi trường mà không mở server.

Hoặc chạy `scripts/run_backend.ps1` và `npx --yes pnpm@10.11.0 dev` trong thư mục `frontend` ở hai terminal riêng.

Trên Linux/macOS, tạo và kích hoạt môi trường Python 3.14, cài cùng requirements rồi chạy:

```bash
cd backend
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Luôn chạy backend từ thư mục `backend/` để dùng đúng SQLite và vùng lưu tệp.

## Dữ liệu và Google Colab

**Clone repo chưa có dữ liệu mẫu.** Thư mục `data/` không được đưa lên Git và chưa có gói dữ liệu phát hành hoặc trình tải tự động. Cần chuẩn bị dữ liệu tại `data/test20/`; xem cấu trúc, nguồn nhãn và manifest trong [hướng dẫn sử dụng](docs/GUIDED_WORKFLOW.md#du-lieu).

Tác vụ chỉ mở khi có ít nhất 10 mẫu đọc được và nhãn đúng định dạng. Bộ mẫu local đã kiểm tra có 20 mẫu 2D, 17 mẫu SEG và 10 mẫu 3D; các số này không áp dụng cho bản clone mới.

AI dùng YOLO11 cho 2D, YOLO11-seg cho SEG và PointPillars cho KITTI 3D. Sau khi người dùng cấp quyền, ứng dụng gửi notebook và dữ liệu lên Drive của tài khoản đó. Người dùng bấm **Run all** trong Colab; backend tự nhận kết quả.

Cần cấu hình OAuth client Desktop một lần theo [hướng dẫn Google](docs/GUIDED_WORKFLOW.md#ket-noi-google). Backend không gửi ground truth hoặc nhãn Manual lên Colab.

## Tài liệu

- [Hướng dẫn sử dụng](docs/GUIDED_WORKFLOW.md): dữ liệu, Google, các bước chạy và xử lý lỗi.
- [Mô tả hệ thống](docs/SYSTEM.md): kiến trúc, schema, tọa độ, công thức chấm và giới hạn.
- [JSON schema](docs/label-bundle.schema.json): hợp đồng nhãn M49, sinh từ `backend/app/schemas.py`.
- [Notebook Colab](colab/README.md): vai trò từng notebook và cách tái tạo.

API tương tác: <http://127.0.0.1:8000/docs>. API/script nhập dữ liệu và CVAT vẫn được giữ dù không có màn hình quản trị riêng. `examples/` chứa fixture tổng hợp để kiểm thử, không phải dataset thực nghiệm.

## Kiểm thử và trạng thái

Backend, chạy từ `backend/` với môi trường đã cài:

```bash
python -m pytest -q -W error
```

Frontend, chạy từ `frontend/`:

```bash
npx --yes pnpm@10.11.0 test
npx --yes pnpm@10.11.0 build
```

Ngày 14/10/2026: 73 test backend, 5 test frontend và build đã qua. API local ghi nhận một lượt 2D hoàn thành với YOLO11s trên Tesla T4, đã nhập kết quả Google và chốt đủ 10 Manual/10 Assisted. Đã thử tải notebook lên Drive và đọc lại xác minh nội dung. Chưa nghiệm thu toàn luồng SEG/3D trên GPU hoặc bằng tài khoản Google thứ hai; test Google tự động dùng API giả lập.

Ứng dụng chưa có xác thực/phân quyền, COCO/KITTI AP chính thức, brush/RLE/mask nhiều vùng hoặc migration database tự động. Phù hợp thử nghiệm local; các giới hạn chi tiết nằm trong mô tả hệ thống.

## Docker tùy chọn

```bash
cp .env.example .env
docker compose up --build
```

Web tại <http://localhost:3000>, API tại <http://localhost:8000>. Compose dùng PostgreSQL và volume lưu dữ liệu; các cổng bind localhost. Cấu hình hiện tại chưa mount bộ mẫu `data/test20`: cần thêm volume chỉ đọc và đặt `M49_TEST20_DIR` trỏ tới đường dẫn trong container trước khi dùng luồng 10 mẫu. Chưa nghiệm thu toàn bộ Docker stack.

`docker compose down` giữ volume. Chỉ thêm `-v` nếu chủ động muốn xóa dữ liệu.

## Công cụ bảo trì

- `scripts/export_schema.py`: sinh lại JSON schema.
- `scripts/build_segmentation_notebook.py`, `scripts/build_3d_notebook.py`: sinh notebook từ code.
- `scripts/convert_bdd100k.py`, `scripts/import_folder.py`: chuyển và nhập dữ liệu qua API.
- `scripts/prepare_test20.py`: dựng bộ mẫu cố định từ dữ liệu local đã tải; không tải dataset và không dựng bộ SEG.
- `scripts/prepare_demo.py`: lựa chọn 20 ảnh chính và 3 pilot từ danh sách đã phân nhóm; công cụ chuẩn bị riêng, không phải luồng tự chọn 10 mẫu trên web.

Database, tệp upload, OAuth client/token, dữ liệu mẫu và môi trường cài đặt đều nằm ngoài Git.
