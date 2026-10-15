# Hướng dẫn sử dụng M49

Cài và khởi động theo [README](../README.md). Luồng sử dụng: **10 Manual → AI trên Colab → 10 Assisted → kết quả**, một người thao tác trên máy local.

<a id="du-lieu"></a>

## Chuẩn bị dữ liệu

Repo không kèm dataset và chưa cung cấp gói tải tự động. Nhận bộ mẫu đã chuẩn bị từ người cung cấp hoặc chuẩn bị từ BDD100K/KITTI, đặt tại `data/test20/`. Có thể đặt biến môi trường `M49_TEST20_DIR` trước khi khởi động backend để dùng thư mục khác.

Cấu trúc mà bộ đọc hiện tại yêu cầu:

```text
data/test20/
  bdd100k_manifest.json
  kitti_2d_manifest.json
  segmentation_manifest.json
  kitti_3d_manifest.json
  bdd100k/
    assets/<ten-anh>.jpg
    labels.json
  segmentation/
    assets/<ten-anh>.jpg
    source_annotations/<ten-anh>.jpg.json
  kitti/training/
    image_2/<ma-mau>.png
    label_2/<ma-mau>.txt
    calib/<ma-mau>.txt
    velodyne/<ma-mau>.bin
```

Mỗi manifest là JSON danh sách tên tệp, không chứa đường dẫn. KITTI 2D dùng tên PNG; KITTI 3D dùng tên BIN. Manifest không tồn tại thì nguồn đó không được đưa vào kho mẫu. Mỗi manifest có tối đa 20 tên không trùng; tác vụ cần tổng cộng ít nhất 10 mẫu hợp lệ.

- **2D:** BDD100K box2d hoặc KITTI object detection. BDD100K cần JSON danh sách frame theo định dạng gốc; lớp `car`. KITTI dùng `Car`, được đổi thành `car` khi tạo lượt.
- **SEG:** bản BDD100K polygon chuyển đổi Supervisely; nhãn có `size`, `objects`, `classTitle`, `geometryType` và `points.exterior/interior`. Bộ đọc chỉ nhận polygon đơn hợp lệ. Box không được thay thế mask.
- **3D:** KITTI có đủ ảnh camera, LiDAR BIN, calibration và nhãn cùng mã mẫu. Backend dùng calibration để chuyển nhãn sang hệ LiDAR và lọc phạm vi đánh giá.

Bộ SEG local được lọc còn 17 ảnh; một ảnh có số box/polygon không khớp được loại nguyên mẫu khỏi manifest trước khi chạy AI. Nhãn và ảnh gốc được giữ nguyên; danh sách ban đầu và lý do nằm trong `segmentation/selection_validation.json`. Không tự bỏ đối tượng lỗi rồi coi phần còn lại là ground truth đầy đủ.

Giữ ảnh gốc và tọa độ tương ứng. Chọn mẫu/cấu hình model trước khi xem kết quả đo chính; dùng pilot riêng nếu cần chỉnh confidence. Bộ mẫu nhỏ này phục vụ demo, không đại diện toàn dataset. Không lấy dự đoán của chính model đang chấm làm đáp án chuẩn.

`scripts/prepare_test20.py` cần các bộ local `data/bdd100k_2d_pilot` và `data/kitti_pilot` cùng metadata/checksum tương ứng; script từ chối ghi đè bộ đã tồn tại. Nó không tự tải dữ liệu hay chuẩn bị nhãn SEG.

<a id="ket-noi-google"></a>
<a id="kết-nối-google-một-lần-trên-máy-local"></a>

## Kết nối Google một lần trên máy local

1. Trong Google Cloud, chọn/tạo project và bật Google Drive API.
2. Cấu hình OAuth consent screen. Nếu ứng dụng External đang Testing, thêm tài khoản thực hiện vào Test users.
3. Tạo OAuth client loại **Desktop app**, tải JSON.
4. Tại bước AI trong M49, mở **Cấu hình kết nối Google một lần** và chọn JSON đó.
5. Chọn model/confidence rồi bấm **Đồng ý cấp quyền và tự tải notebook**, đăng nhập bằng tài khoản muốn chạy Colab. Giữ web M49 mở: sau khi đồng ý cấp quyền, web tự tạo lượt, tải notebook `.ipynb` và dữ liệu lên Drive rồi mở Colab. Không cần gửi/dán URL. Nếu popup bị chặn, dùng liên kết cấp quyền trên web và liên kết notebook khi tải xong. Có thể hủy chờ hoặc thử lại khi phiên cấp quyền hết hạn.

Backend chạy cổng 8000 trên cùng máy với trình duyệt; callback là `http://127.0.0.1:8000/api/colab/google/callback`. M49 dùng quyền `drive.file`; Colab xin quyền riêng khi chạy notebook.

Notebook và dữ liệu được tải lên Drive của người cấp quyền. Người tải repo có thể dùng tài khoản của chính họ, nhưng bản hiện tại vẫn cần cấu hình OAuth một lần. Chưa có luồng công khai chỉ cần đăng nhập là dùng cho mọi tài khoản.

Client/token được lưu trong `STORAGE_DIR/google-colab/`, mặc định `backend/storage/google-colab/`, và không đưa lên Git hoặc chèn vào notebook. **Ngắt kết nối trên máy này** xóa token local, không xóa file Drive hoặc thu hồi quyền Google. Có thể thu hồi quyền trong phần bảo mật tài khoản Google.

## Chạy một lượt

1. Chọn 2D, SEG hoặc 3D, nhập tên người thực hiện và bấm bắt đầu. Ứng dụng lấy ngẫu nhiên 10 mẫu không trùng và lưu cố định cho cả lượt.
2. Gán nhãn từng mẫu Manual rồi **Lưu và chốt**. Timer tự bắt đầu khi mở mẫu. Ground truth và nhãn AI không hiển thị ở bước này.
3. Sau đủ 10 Manual, chọn model/confidence và bấm **Đồng ý cấp quyền và tự tải notebook** (hoặc **Đồng ý tải notebook và mở Colab** nếu đã kết nối). Web tự gửi sau khi cấp quyền thành công. Với checkpoint riêng, kết nối Google trước, chọn tệp phù hợp tác vụ rồi đồng ý tải notebook; 3D dùng PointPillars.
4. Trong Colab, kiểm tra đúng tài khoản Google, chọn GPU theo yêu cầu notebook, bấm **Runtime → Run all** và cấp quyền. Notebook đã có cấu hình lượt; không cần điền mã lượt hoặc đường dẫn.
5. Giữ backend chạy để nhận kết quả. Khi đủ kết quả hợp lệ, ứng dụng mở Assisted. Kiểm tra/sửa nhãn AI rồi chốt từng mẫu, kể cả khi giữ nguyên dự đoán.
6. Sau đủ 10 Assisted, xem điểm ba phương pháp, thời gian người thao tác và xuất CSV.

Tải lại trang rồi chọn **Tiếp tục lượt đã lưu** để tiếp tục; không lấy bộ mẫu khác. Ứng dụng không tự bấm Run all hay khởi động runtime Colab.

## Thao tác và cách đo

Box/polygon có chọn, thêm, kéo, sửa, xóa, undo/redo và autosave. Với cuboid, chỉnh tâm/kích thước/yaw bằng trường số hoặc tay nắm ở góc Trên/Trước/Bên; góc phối cảnh dùng quan sát. Bật timer để chỉnh sửa; nhãn đã chốt được giữ riêng.

Timer tính cả thời gian quan sát, không tự loại thời gian đứng yên. Bấm Tạm dừng khi nghỉ; ẩn tab hoặc mất kết nối sẽ gửi pause khi có thể. Heartbeat mỗi 10 giây, lease 30 giây giới hạn phần cộng thêm nếu tab crash/mất mạng. Khi quay lại, tiếp tục timer trước khi sửa.

Bảng điểm hiển thị chất lượng và số liệu thời gian; đã bỏ cột Đạt/Chưa đạt. Thời gian AI inference hiển thị riêng, không cộng vào thời gian người gán nhãn. Công thức và ý nghĩa N/A ở [mô tả hệ thống](SYSTEM.md#scoring).

## Xử lý lỗi

- **Nút tác vụ bị khóa:** đọc lý do ở nút; kiểm tra manifest, đủ 10 mẫu và nhãn đúng loại. Một tệp lỗi trong manifest có thể chặn cả nguồn.
- **Không mở Colab:** đợi tải xong, dùng liên kết notebook nếu popup bị chặn.
- **Không kết nối Google:** kiểm tra Desktop client, Drive API, Test users, cổng callback và cấu hình mạng.
- **Đổi tài khoản/Google hết hạn quyền:** kết nối lại bằng tài khoản đã tạo lượt. Lượt gắn với tài khoản gửi ban đầu.
- **Chạy xong nhưng chưa có Assisted:** kiểm tra lỗi cell cuối, đủ kết quả, đúng tài khoản và backend còn chạy. M49 kiểm tra mã lượt, checksum, manifest và schema trước khi nhập.
- **SEG báo mask có lỗ/nhiều vùng:** biểu diễn polygon hiện tại chưa hỗ trợ; không sửa nhãn thành box để né lỗi.
- **3D lỗi GPU/CUDA:** giữ log notebook để chẩn đoán. Pipeline PointPillars đã có code và kiểm thử fixture, chưa nghiệm thu GPU thật.
- **Lượt cũ dùng Drive Desktop:** backend còn hỗ trợ transport cũ; các lượt mới trên giao diện dùng Google API.

## Kiểm tra trước khi thu kết quả

Thử lưu/tải lại, timer pause/resume, giữ nguyên nhãn AI rồi chốt và xuất CSV. Chạy pilot riêng cho SEG/3D trước khi đo chính. Không thay đổi nhãn chuẩn, confidence hoặc danh sách mẫu sau khi xem kết quả chính để làm đẹp số liệu.

Sao lưu SQLite và storage khi backend đã dừng; nếu dùng dataset riêng, sao lưu cả manifest/nhãn nguồn. Không xóa database để xử lý thay đổi schema.
