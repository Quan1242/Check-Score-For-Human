# M49 — Hướng dẫn sử dụng

M49 so sánh **Người tự gán nhãn → AI → Người sửa nhãn AI** trên cùng 10 mẫu. Hỗ trợ box 2D, segmentation bằng polygon đơn và cuboid 3D LiDAR. Web chạy local cho một người dùng; AI chạy trên Google Colab của người cấp quyền.

## 1. Cài đặt lần đầu

Cài Python **3.14.x** và Node.js **22**. Mở PowerShell tại thư mục dự án:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --only-binary=:all: -r backend/requirements-dev.txt
.\.venv\Scripts\python.exe -m pip check
cd frontend
npx --yes pnpm@10.11.0 install --frozen-lockfile
cd ..
```

## 2. Chuẩn bị dữ liệu test

Repo không chứa dataset. Nếu đã nhận **m49-test-data.zip**, giải nén vào thư mục gốc dự án. ZIP đã chứa đường dẫn `data/test20/`, không giải nén vào một thư mục `data/test20` khác.

Kiểm tra sau khi giải nén:

```text
data/test20/bdd100k_manifest.json
data/test20/kitti_2d_manifest.json
data/test20/segmentation_manifest.json
data/test20/kitti_3d_manifest.json
data/test20/bdd100k/assets/
data/test20/segmentation/assets/
data/test20/kitti/training/
```

ZIP được chuẩn bị riêng tại `data/exports/m49-test-data.zip` trên máy đóng gói; không tải xuống cùng khi clone Git. Bộ mẫu hiện có 20 mẫu 2D, 17 mẫu SEG và 10 mẫu 3D hợp lệ. Mỗi lượt lấy ngẫu nhiên 10 mẫu của tác vụ đã chọn.

Nếu tự chuẩn bị dữ liệu, xem [cấu trúc dataset và nhãn](docs/GUIDED_WORKFLOW.md#du-lieu). Có thể đặt `M49_TEST20_DIR` để dùng thư mục khác. Tác vụ chỉ mở khi có ít nhất 10 mẫu hợp lệ.

## 3. Mở web

Nhấp đúp **chay_web.bat**, hoặc chạy:

```powershell
.\chay_web.bat
```

Web mở tại **http://127.0.0.1:5173**. Giữ hai cửa sổ backend và frontend hoạt động trong suốt quá trình sử dụng, kể cả lúc AI chạy trên Colab.

Những lần sau chỉ cần chạy lại file BAT. Dùng `chay_web.bat --check` để kiểm tra môi trường mà chưa mở server. Để dừng, nhấn `Ctrl+C` trong từng cửa sổ server rồi đóng cửa sổ.

## 4. Bắt đầu và gán nhãn Manual

1. Chọn tác vụ **2D**, **SEG** hoặc **3D**.
2. Nhập tên người thực hiện, bấm **Lấy ngẫu nhiên 10 mẫu và bắt đầu**.
3. Gán nhãn từng mẫu từ dữ liệu gốc rồi bấm **Lưu và chốt**.
4. Hoàn thành đủ 10 mẫu để chuyển sang bước AI.

Web giữ nguyên 10 mẫu cho cả ba phương pháp. Timer đo thời gian thao tác; bấm **Tạm dừng** khi nghỉ. Nhãn chuẩn và dự đoán AI không hiển thị trong bước Manual.

## 5. Cấp quyền Google và tự tải notebook

### Cấu hình Google một lần trên máy

Nếu chưa cấu hình, tại bước AI mở **Cấu hình kết nối Google một lần**:

1. Trong Google Cloud, bật **Google Drive API**.
2. Cấu hình OAuth consent screen; nếu đang ở chế độ Testing, thêm tài khoản sử dụng vào **Test users**.
3. Tạo OAuth client loại **Desktop app**, tải tệp JSON.
4. Chọn tệp đó trong ô **OAuth client JSON** trên web.

Xem [hướng dẫn kết nối Google](docs/GUIDED_WORKFLOW.md#ket-noi-google). Bản clone mới cần cấu hình này trước khi người dùng có thể bấm cấp quyền.

### Thao tác cho mỗi lượt AI

1. Chọn model và ngưỡng confidence. Mặc định dùng YOLO11s cho 2D, YOLO11s-seg cho SEG, PointPillars cho 3D.
2. Bấm **Đồng ý cấp quyền và tự tải notebook**.
3. Trong cửa sổ Google, đăng nhập và đồng ý cấp quyền Drive. Giữ trang M49 mở.
4. **Web tự tạo và tải file `.ipynb` cùng 10 mẫu lên Drive của tài khoản vừa cấp quyền, rồi mở Colab.** Không cần tải notebook thủ công, dán mã lượt, gửi URL cho người khác hoặc bấm gửi lần nữa sau khi cấp quyền.

Nếu đã kết nối Google, nút hiển thị **Đồng ý tải notebook và mở Colab**. Với checkpoint riêng, chọn model tùy chỉnh, kết nối Google trước, tải tệp `.pt` phù hợp rồi bấm đồng ý tải notebook.

Chỉ dữ liệu đầu vào, calibration cần thiết và cấu hình model được gửi để chạy AI. Ground truth và nhãn Manual không được gửi lên Colab.

## 6. Chạy AI trong Colab

1. Kiểm tra Colab dùng cùng tài khoản Google vừa kết nối.
2. Chọn GPU theo yêu cầu notebook; 3D cần GPU.
3. Bấm **Runtime → Run all** và xác nhận quyền Google nếu notebook yêu cầu.
4. Chờ notebook chạy xong, giữ backend M49 hoạt động.

**Tải notebook lên là tự động; thao tác Run all vẫn do bạn thực hiện trong Colab.** Khi nhận đủ kết quả hợp lệ qua Drive, web tự chuyển sang bước Người sửa AI.

## 7. Sửa nhãn AI và xem kết quả

1. Rà soát dự đoán trên từng mẫu, sửa nếu cần.
2. Bấm **Lưu và chốt** cho từng mẫu, kể cả khi giữ nguyên dự đoán.
3. Hoàn thành đủ 10 mẫu Assisted để xem điểm Người / AI / Người + AI, thời gian và xuất CSV.

Nếu tải lại trang, chọn lượt trong **Tiếp tục lượt đã lưu**. Web giữ bộ mẫu đã chọn. Xem [hướng dẫn chi tiết](docs/GUIDED_WORKFLOW.md) để thực hiện các lượt và đo thời gian nhất quán.

## Khi gặp lỗi

- **Tác vụ bị khóa:** kiểm tra đã giải nén đúng `data/test20/`, đủ mẫu và nhãn hợp lệ; đọc lý do trên web.
- **BAT không chạy:** chạy `chay_web.bat --check`, kiểm tra Python/Node và thư viện. Nếu cổng 8000/5173 đang dùng, dừng server cũ trước khi mở lại.
- **Không hiện cửa sổ Google:** bấm liên kết **Mở cửa sổ cấp quyền nếu trình duyệt chặn popup**.
- **Từ chối hoặc chưa cấp quyền:** bấm **Hủy chờ cấp quyền**, rồi thử lại. Phiên chờ hết hạn sau khoảng 10 phút.
- **Google báo lỗi:** kiểm tra Drive API, Desktop OAuth client, Test users và backend cổng 8000.
- **Notebook đã tải nhưng Colab chưa mở:** bấm **Mở notebook của lượt này trên Colab** trên web.
- **AI chạy xong nhưng web chưa chuyển bước:** giữ backend chạy, kiểm tra lỗi cell cuối notebook và đúng tài khoản Google. Web chỉ nhận kết quả đủ mẫu, đúng lượt và đúng định dạng.
- **Đổi tài khoản hoặc quyền hết hạn:** kết nối lại bằng tài khoản đã tạo lượt AI đó.

## Tài liệu và kiểm thử

- [Hướng dẫn chi tiết](docs/GUIDED_WORKFLOW.md): dữ liệu, Google, thao tác và xử lý lỗi.
- [Mô tả hệ thống](docs/SYSTEM.md): kiến trúc, công thức chấm và giới hạn.
- [Notebook Colab](colab/README.md): model và cách tái tạo notebook.
- [JSON schema](docs/label-bundle.schema.json): định dạng nhãn.
- API local: http://127.0.0.1:8000/docs.

Kiểm thử backend từ thư mục `backend/`:

```powershell
..\.venv\Scripts\python.exe -m pytest -q -W error
```

Kiểm thử frontend từ thư mục `frontend/`:

```powershell
npx --yes pnpm@10.11.0 test
npx --yes pnpm@10.11.0 build
```

Ngày 15/10/2026: thay đổi tự gửi notebook sau cấp quyền đã qua 9 test frontend, 16 test backend liên quan và build. Test Google dùng API giả lập; luồng cấp quyền mới chưa được thử lại với tài khoản Google thật. Trước đó đã kiểm chứng một lượt 2D với YOLO11s trên Tesla T4; chưa nghiệm thu toàn luồng SEG/3D trên GPU hoặc tài khoản Google thứ hai.

Ứng dụng dành cho thử nghiệm local, chưa có xác thực nhiều người dùng hoặc COCO/KITTI AP chính thức. Database, dữ liệu mẫu, file upload và OAuth client/token nằm ngoài Git.
