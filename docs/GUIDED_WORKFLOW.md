# Một lượt so sánh Người / AI / Người + AI

Màn hình mặc định là **Bắt đầu thử nghiệm**. Ba kiểu so sánh là Manual, AI và Assisted; 2D/segmentation/3D là tác vụ chọn cho một lượt.

1. Chọn tác vụ và nhập tên người thực hiện; không có bước chọn dự án hoặc dataset.
2. Nhấn **Lấy ngẫu nhiên 10 ảnh và bắt đầu**. Với 2D, ứng dụng bốc 10 mẫu không lặp từ kho BDD100K + KITTI trong `data/test20`, chuẩn hóa lớp car/Car thành car, tạo dự án riêng và khóa danh sách ảnh/ground truth. Tên ảnh có tiền tố nguồn để tránh trùng. Mỗi lượt mới bốc lại; tiếp tục lượt cũ giữ nguyên mẫu. Không ép tỷ lệ nguồn hoặc độ khó cho 10 ảnh được bốc.
3. Gán nhãn lần lượt 10 mẫu từ đầu. Timer tự đo; **Chốt và sang mẫu tiếp theo** giữ nhãn cuối và mở mẫu kế tiếp.
4. Sau đủ 10 mẫu, bấm **Kết nối và cấp quyền Google Drive**. Chọn model **Tự chọn (YOLO11s)**, YOLO11n/s/m hoặc checkpoint `.pt` riêng (tối đa 512 MiB). Bấm **Gửi 10 ảnh và mở Colab** để đồng ý chuyển đúng ảnh gốc của lượt này và cấu hình model lên tài khoản Drive đã kết nối. Không chuyển Manual hoặc ground truth.
5. Backend tự tải ảnh/model, tạo notebook gắn với lượt và mở Colab khi sẵn sàng. Nếu trình duyệt chặn cửa sổ mới, bấm liên kết **Mở notebook của lượt này trên Colab**. Trong Colab, bấm **Runtime → Run all** và cấp quyền bằng cùng tài khoản Google. Không tải/kéo file, mount thư mục Drive, nhập đường dẫn hoặc điền mã lượt. Notebook tự tải đúng dữ liệu, kiểm tra checksum, chạy model và gửi kết quả về các tệp Drive đã được ứng dụng chuẩn bị.
6. Khi backend nhận đủ 10 dự đoán hợp lệ từ Drive API, giao diện tự chuyển sang Assisted. Mỗi mẫu mở bản AI gốc để người kiểm tra/sửa; kết quả Manual được giữ riêng. Chốt cả trường hợp không sửa AI.
7. Sau mẫu Assisted thứ 10, ứng dụng tự chấm và hiện kết quả Manual, AI, Assisted. Cùng 10 mẫu, cùng lớp, cùng ngưỡng IoU và ground truth. Thời gian AI inference được hiển thị riêng; speedup so sánh thời gian người thao tác Manual/Assisted, không cộng thời gian truyền dữ liệu.

AI nhận **ảnh gốc**, không nhận nhãn Manual hoặc ground truth. Vì vậy ba nhánh là các kết quả độc lập hoặc sửa từ AI, không lấy nhãn người làm đầu vào AI.

Tiến độ lưu ở backend qua GuidedRun/Experiment/Assignment/ColabJob. Tải lại trang rồi chọn **Tiếp tục lượt đã lưu**. Backend từ chối gửi AI trước khi chốt đủ 10 Manual; gọi bước tiếp theo nhiều lần không tạo trùng nhiệm vụ Assisted. Giữ một backend worker như phạm vi local hiện tại.

## Phạm vi đã có

- Luồng đầy đủ hiện mở cho **2D trên BDD100K và KITTI**, từ `data/test20`. Có thể đặt `M49_TEST20_DIR` khi lưu dữ liệu ở nơi khác.
- Segmentation hiện bị khóa trong luồng này vì bộ 10 mẫu chưa có ground truth mask/polygon. Mã nguồn notebook/editor segmentation vẫn được giữ để dùng khi có dữ liệu phù hợp.
- BDD100K 3D chưa có LiDAR trong bộ này. KITTI 3D đã có dữ liệu/editor nhưng còn thiếu pipeline AI; chưa mở một lượt khép kín không thể hoàn thành.
- Colab cần người dùng đăng nhập và bắt đầu runtime. Nhận kết quả, mở Assisted và chấm điểm là tự động. Chưa nghiệm thu OAuth/Drive/Colab/GPU thật; kiểm thử tự động dùng Google API giả lập.

Kiểm thử: 52 test backend đạt, bao gồm vòng 10 Manual → AI fixture → 10 Assisted → báo cáo ba nguồn, tiếp tục lượt, chặn gửi AI sớm, không tạo trùng và chọn/upload model. 5 test hình học frontend và build đạt. Fixture không phải kết quả inference thật.

Tham chiếu model: [Ultralytics YOLO11](https://docs.ultralytics.com/models/yolo11/). Hướng dẫn dữ liệu/Drive: [DATASETS_COLAB](DATASETS_COLAB.md).

## Kết nối Google một lần trên máy local

1. Trong [Google Cloud Console](https://console.cloud.google.com/apis/library/drive.googleapis.com), chọn/tạo project và bật **Google Drive API**. Không cần dùng Colab Enterprise.
2. Cấu hình **Google Auth Platform / OAuth consent screen**. Với ứng dụng External đang Testing, thêm địa chỉ Google của bạn vào **Test users**.
3. Tại **Clients**, tạo OAuth client loại **Desktop app**, tải JSON. Trong bước AI của M49, mở **Cấu hình kết nối Google một lần** và chọn JSON đó. Không dùng service account hoặc client loại Web.
4. Backend phải chạy trên cùng máy với trình duyệt, cổng **8000**. Callback cố định là `http://127.0.0.1:8000/api/colab/google/callback`. Luồng dùng OAuth state một lần (10 phút) và PKCE; nếu backend khởi động lại trong lúc cấp quyền thì bấm kết nối lại.
5. Bấm kết nối và duyệt màn hình quyền Google. M49 chỉ xin `drive.file`: các tệp do ứng dụng tạo hoặc được người dùng chia sẻ với ứng dụng. Quyền Google bên trong Colab được Colab xin riêng; kiểm tra màn hình quyền trước khi đồng ý.

Client/token nằm trong `STORAGE_DIR/google-colab/`, thuộc thư mục storage đã bị loại khỏi Git. Token không trả về frontend và không chèn vào notebook. **Ngắt kết nối trên máy này** xóa token local, dừng các lần đồng bộ tiếp theo; không xóa dữ liệu Drive hoặc thu hồi quyền trong tài khoản Google. Có thể thu hồi quyền ứng dụng trong cài đặt bảo mật Google. Khi Google hết hạn/thu hồi token, kết nối lại đúng tài khoản đã gửi lượt để tiếp tục.

Ảnh và các tệp kết quả nằm trong thư mục riêng `M49-<job_id>` trên Drive. ID tệp được lưu trước khi tải lên để tiếp tục sau lỗi mạng mà không tạo trùng. Tệp kết quả được tạo bởi M49 rồi notebook cập nhật đúng ID, vì quyền `drive.file` không cho đọc tùy ý mọi tệp do Colab tạo. Backend kiểm tra mã lượt, checksum, danh sách mẫu và schema trước khi nhập; tiếp tục dùng snapshot bất biến và không nhập lặp. Giữ backend đang chạy để nhận kết quả; nếu tắt, mở lại để tiếp tục đồng bộ.

Lượt cũ dùng Drive Desktop vẫn được hỗ trợ. Các lượt mới trên giao diện dùng Google API, không cần cài Drive Desktop. Notebook 3D vẫn là template; tác vụ chưa đủ dữ liệu/model vẫn bị khóa.

Colab cá nhân cần thao tác **Run all** và cấp quyền runtime, không có triển khai tự khởi chạy runtime trong M49. [FAQ Colab](https://research.google.com/colaboratory/faq.html), [OAuth Desktop + PKCE](https://developers.google.com/identity/protocols/oauth2/native-app), [quyền Drive](https://developers.google.com/workspace/drive/api/guides/api-specific-auth).
