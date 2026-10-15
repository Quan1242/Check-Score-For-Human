# M49 — So sánh gán nhãn người và AI

Ứng dụng web so sánh chất lượng và thời gian của ba phương pháp trên cùng bộ 10 mẫu: **người tự gán nhãn**, **AI dự đoán** và **người chỉnh sửa nhãn AI**.

Hỗ trợ hộp 2D, phân vùng bằng polygon và hộp 3D trên dữ liệu LiDAR. Web chạy trên máy cá nhân; mô hình AI chạy trên Google Colab.

## Chức năng

- Chọn ngẫu nhiên 10 mẫu và giữ nguyên bộ mẫu cho cả ba phương pháp.
- Vẽ, chỉnh sửa, lưu nhãn và đo thời gian thao tác.
- Gửi dữ liệu sang Colab qua Google Drive và nhận kết quả AI.
- Đánh giá số đối tượng tìm đúng, vẽ thừa hoặc sai, bỏ sót, mức độ đầy đủ và độ khớp với nhãn chuẩn.
- Xem kết quả tổng cả lượt, chi tiết từng mẫu và xuất CSV.

## Chạy web

1. Giải nén mã nguồn vào một thư mục trên máy.
2. Giải nén **`m49-test-data.zip` vào thư mục gốc dự án**, cùng cấp với `chay_web.bat`. ZIP đã chứa `data/test20/`, không giải nén vào một thư mục `data/test20` khác.
3. Nhấp đúp **`chay_web.bat`**. File BAT tự chọn hai cổng còn trống cho backend và frontend, rồi mở web trong trình duyệt.

Giữ hai cửa sổ **M49 Backend** và **M49 Frontend** mở trong lúc sử dụng. Để dừng web, nhấn `Ctrl+C` trong từng cửa sổ rồi đóng lại. Những lần sau chỉ cần bật lại file BAT.

Kết nối Google Drive chỉ cần khi dùng luồng AI. Nếu mạng hoặc Google không truy cập được, ứng dụng sẽ báo lỗi kết nối khi thực hiện thao tác Google; các chức năng web cục bộ vẫn chạy.

Dữ liệu mẫu được cung cấp riêng, không nằm trong mã nguồn Git. Máy mới cần thực hiện phần cài đặt lần đầu bên dưới trước khi bật BAT.

<details>
<summary>Cài đặt lần đầu trên máy mới</summary>

Cài **Python 3.14.x** và **Node.js 22 trở lên**. Mở PowerShell tại thư mục dự án và chạy:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --only-binary=:all: -r backend/requirements.txt
cd frontend
npx --yes pnpm@10.11.0 install --frozen-lockfile
cd ..
```

Sau đó nhấp đúp `chay_web.bat`.

</details>

## Sử dụng

Chọn tác vụ và nhập tên → gán nhãn, chốt đủ 10 mẫu → kết nối Google và mở notebook Colab → bấm **Runtime → Run all** → chỉnh sửa, chốt nhãn AI → xem kết quả.

Ở bước AI, bấm **Đăng nhập Google và mở Colab**, đăng nhập tài khoản của bạn và đồng ý cấp quyền. Web tự tải notebook và dữ liệu lên Drive của tài khoản đó rồi mở Colab. Bấm **Runtime → Run all**, xác nhận tài khoản Google trong notebook khi được hỏi; kết quả tự về web để tiếp tục sửa nhãn AI. Giữ web và backend đang chạy. Không cần tải tệp thủ công hoặc nhập OAuth JSON trên giao diện. Colab 3D cần GPU.

<details>
<summary>Dành cho người cung cấp ứng dụng: cấu hình Google một lần</summary>

Repo có sẵn OAuth client **Desktop app** dùng chung cho bản thử tại `backend/app/google-oauth-client.json`. Bản clone mới tự dùng cấu hình này; mỗi người vẫn đăng nhập và cấp quyền bằng tài khoản Google riêng. Cấu hình riêng hiện có tại `backend/storage/google-colab/client.json` được ưu tiên khi chạy bằng BAT. Để dùng tệp cấu hình khác do quản trị viên quản lý, đặt đường dẫn tuyệt đối trong môi trường của backend trước khi khởi động:

```powershell
$env:M49_GOOGLE_CLIENT_FILE = 'C:\private\m49-google-client.json'
.\chay_web.bat
```

Tệp có thể là JSON Desktop app tải từ Google (`installed`) hoặc cấu hình gồm `client_id` và `client_secret`. Tệp `.env.example` chỉ minh họa biến môi trường; BAT không tự đọc `.env`. Nếu cấu hình thiếu hoặc sai, web báo tính năng Google chưa sẵn sàng thay vì yêu cầu người dùng tạo OAuth client.

Nếu ứng dụng Google còn ở chế độ Testing, quản trị viên cần thêm tài khoản được sử dụng vào Test users và bật Drive API cho dự án. Cấu hình client dùng chung không chứa access token hoặc refresh token. Không đóng gói `token.json` hoặc toàn bộ storage: mỗi người đăng nhập bằng tài khoản riêng. Muốn đổi OAuth client trên một bản cài đã kết nối, ngắt kết nối Google trước khi đổi cấu hình.

Ứng dụng vẫn chạy localhost, một người dùng trên mỗi bản cài; cấu hình này không biến backend thành dịch vụ nhiều tài khoản dùng chung.

</details>

### Dùng CVAT đã có trên máy

Ở bước gán nhãn 2D hoặc SEG, chọn **Kết nối CVAT trên máy**. Nhập địa chỉ CVAT (mặc định `http://localhost:8080`) và Personal Access Token có quyền đọc/ghi từ **User settings → Security** của CVAT. M49 không tự cài CVAT.

Bấm **Tạo task CVAT cho tối đa 10 ảnh**, chờ xử lý ảnh rồi mở task và job để gán nhãn. Các ảnh chưa chốt của cùng người, cùng lượt Manual hoặc Assisted được gom vào một task; lượt Assisted được nạp nhãn AI ban đầu. Task một ảnh đã tạo trước đây vẫn được giữ nguyên, không chuyển hoặc ghi đè nhãn cũ.

Bấm **Save** trong CVAT, quay về M49, nhập thời gian cho từng ảnh và bấm **Lấy nhãn đã lưu từ CVAT và chốt tất cả ảnh trong task**. M49 đối chiếu tên, kích thước và frame của từng ảnh trước khi nhập. Nếu một ảnh có nhãn không hợp lệ hoặc bản nháp M49 đã thay đổi, cả lần nhập bị hủy để tránh chốt dở dang. Thời gian nhập tay không dùng để tính tăng tốc tự động. Tác vụ 3D dùng trình gán nhãn M49.

### Dùng model riêng trên Colab

Ở bước AI, chọn **Tải checkpoint .pt của tôi**, kết nối Google rồi chọn model Ultralytics đúng tác vụ: detection cho 2D, segmentation cho SEG; tối đa 512 MiB. Model cần có lớp phù hợp với bộ mẫu (`car` trong luồng 10 mẫu).

Sau khi nhận tệp trên máy, bấm **Tải dữ liệu và mở Colab** để chuyển model và dữ liệu lên Drive. Trong Colab, bấm **Run all** bằng cùng tài khoản Google. Notebook kiểm tra checksum, tác vụ và lớp của model trước khi dự đoán. Việc tải tệp thành công chưa xác nhận model tương thích; lỗi nạp model được hiển thị ở cell Colab. Model riêng 3D chưa được hỗ trợ.

## Giới hạn triển khai và thông tin đăng nhập

Ứng dụng dành cho một người dùng trên máy cá nhân, chạy đúng **một backend worker**. OAuth state và khóa xử lý nằm trong bộ nhớ của tiến trình; không chạy nhiều worker hoặc nhiều backend cùng dùng một thư mục storage. Docker được cấu hình `--workers 1`; khi tự chạy Uvicorn cũng cần dùng tùy chọn này. Không công khai backend ra Internet hoặc mạng dùng chung.

Thư mục `storage` chứa OAuth client, Google refresh token và CVAT token. Chỉ tài khoản chạy ứng dụng được phép truy cập thư mục này; không đặt trên volume chia sẻ. Trên POSIX, thư mục Google được đặt quyền `0700`, các tệp thông tin đăng nhập và JSON mới ghi có quyền `0600`. Trên Windows, quyền truy cập phụ thuộc ACL kế thừa của thư mục: quyền POSIX không thay thế Windows ACL. Không chia sẻ hoặc commit storage.

Kết nối CVAT cho phép chọn cổng localhost vì CVAT có thể chạy ở cổng khác nhau; chỉ dùng với dịch vụ CVAT do chính người dùng quản lý. Chức năng này không phải ranh giới bảo mật cho môi trường nhiều người dùng. Khi đang chấm điểm, yêu cầu chấm khác nhận HTTP 429 và cần thử lại sau khi yêu cầu trước hoàn tất.

## Công nghệ

- **Frontend:** React, TypeScript, Vite.
- **Backend:** FastAPI, SQLModel, SQLite.
- **AI:** YOLO11 cho 2D/SEG, PointPillars cho 3D, chạy trên Colab.

## Tài liệu

- [Cấu trúc hệ thống và công thức đánh giá](docs/SYSTEM.md).
- [Định dạng dữ liệu nhãn](docs/label-bundle.schema.json).
- [Notebook Colab](colab/README.md).

Điểm đánh giá theo giao thức M49, không phải COCO/KITTI AP chính thức.
