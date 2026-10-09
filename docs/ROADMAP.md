# Những việc cần làm tiếp

Cập nhật lúc **09:13 ngày 09/10/2026 (giờ Việt Nam, UTC+7)**.

Đã có code cho vẽ khung 2D, vẽ vùng đối tượng bằng đa giác, chỉnh hộp 3D, lưu nhãn và chấm điểm. **Các phần này chưa được chạy thử nên chưa xác nhận hoạt động đúng.** Chi tiết thay đổi nằm trong [báo cáo trước khi push](VALIDATION.md).

Danh sách dưới đây chỉ ghi việc còn lại. Phần ghi **Bạn thực hiện** là dữ liệu, chạy thử và kiểm duyệt đang đợi bạn. Phần ghi **Cần viết thêm code** là chức năng chưa làm xong.

## 1. Chạy thử bản hiện tại trước

**Bạn thực hiện:**

- [ ] Chuẩn bị môi trường chạy: Python, Node.js và pnpm theo README. Nếu thêm thư viện trong file DOCX, cần kiểm tra phiên bản có tương thích với dự án hay không.
- [ ] Chạy kiểm tra backend bằng `python -m pytest -q` trong thư mục `backend`. Đây là bước kiểm tra các API và logic đã có test.
- [ ] Chạy `pnpm build` trong thư mục `frontend` để kiểm tra code giao diện có biên dịch được không.
- [ ] Mở ứng dụng và thử cả ba loại dự án: khung 2D, vùng đối tượng và hộp 3D. Thử thêm, sửa, xóa, hoàn tác, lưu tự động và tải lại trang để kiểm tra nhãn còn nguyên.
- [ ] Thử tạo nhiệm vụ, sửa nhãn AI, chốt bản cuối và xem kết quả. Kiểm tra bản AI ban đầu không bị thay đổi.
- [ ] Kiểm tra chạy bằng Docker với PostgreSQL. Nếu đã có database cũ, thử trên bản sao để xác nhận dữ liệu cũ được giữ lại.

**Kết quả cần có:** biết ứng dụng chạy được đến đâu và ghi lại lỗi thực tế cần sửa. Test cũ chưa bao phủ toàn bộ phần code mới.

## 2. Chuẩn bị dữ liệu thật và kiểm tra điểm

**Bạn thực hiện:**

- [ ] Chọn ảnh cho 2D/segmentation và dữ liệu đám mây điểm cho 3D. Chốt các lớp cần gán nhãn, ví dụ xe con, xe tải và người đi bộ.
- [ ] Chuẩn bị nhãn chuẩn để làm đáp án chấm điểm. Nhãn chuẩn còn gọi là ground truth.
- [ ] Lập danh sách mẫu dùng thử và mẫu dùng cho thí nghiệm chính thức. Lưu lại cách chia dữ liệu để có thể chạy lại cùng thí nghiệm sau này.
- [ ] Nếu dùng BDD100K, kiểm tra file JSON do script chuyển đổi tạo ra: đúng ảnh, đúng lớp và đúng tọa độ. Chốt cách xử lý đối tượng bị che, bị cắt ở mép ảnh hoặc được đánh dấu bỏ qua.
- [ ] Chọn vài mẫu nhỏ và tính tay để đối chiếu bộ chấm: khung trùng nhau, khung lệch nhau, thừa/thiếu đối tượng và sai lớp.
- [ ] Với segmentation, kiểm tra vùng pixel được tô và điểm IoU/Dice. Với 3D, kiểm tra hộp có góc xoay và độ cao khác nhau. IoU/Dice là các chỉ số đo mức độ trùng khớp giữa nhãn và đáp án.
- [ ] Kiểm tra cách ghép đối tượng: ưu tiên ghép được nhiều cặp đúng ngưỡng nhất, rồi mới chọn cách có tổng IoU cao nhất. Trường hợp không tính được điểm phải hiện N/A.
- [ ] Chạy thử một nhóm mẫu nhỏ cho từng tác vụ với manual, AI và assisted; ghi lỗi và duyệt kết quả trước khi dùng cho báo cáo chính thức.

**Kết quả cần có:** bộ dữ liệu đã chốt và một số đáp án tính tay để biết bộ chấm có tính đúng hay không.

## 3. Nâng cấp công cụ gán nhãn

**Cần viết thêm code:**

- [ ] **Segmentation:** cho phép tô bằng cọ, tạo vùng có lỗ hoặc một đối tượng gồm nhiều vùng rời nhau. Hiện chỉ vẽ được một đa giác liền; cần bổ sung cách lưu mask như RLE nếu chọn định dạng này.
- [ ] **3D:** cho phép kéo, đổi kích thước và xoay hộp trực tiếp bằng chuột. Hiện phải nhập tâm, kích thước và góc xoay vào các ô số.
- [ ] **Đám mây điểm lớn:** đọc được PCD dạng nén và cải thiện tốc độ hiển thị. Hiện viewer chỉ lấy mẫu tối đa 60.000 điểm để vẽ.
- [ ] **Ghép ảnh camera với LiDAR:** đọc thông số căn chỉnh của KITTI để một hộp 3D xuất hiện đúng vị trí trên ảnh. Đồng thời chuyển đúng tọa độ, tâm hộp và góc xoay giữa hai hệ.
- [ ] **Bộ đếm thời gian:** tự nhận biết lúc người dùng ngừng thao tác, mất mạng hoặc đóng trang đột ngột. Hiện người dùng phải bấm tạm dừng để tránh thời gian tiếp tục tăng.

## 4. Kết nối AI tạo nhãn thật

**Bạn chọn dữ liệu và phần cứng; sau đó cần viết thêm code:**

- [ ] Chọn model phù hợp cho từng tác vụ và GPU sẽ dùng. Ghi cố định phiên bản model, file trọng số và thư viện để có thể chạy lại cùng kết quả.
- [ ] Hoàn thiện notebook Colab để model thực sự tạo nhãn 2D, segmentation và 3D. Các notebook hiện mới là khung, chưa chạy model.
- [ ] Viết bộ chuyển đổi nhãn segmentation từ bộ dữ liệu được chọn sang định dạng ứng dụng. Công cụ chuyển đổi phải phù hợp phiên bản của bộ dữ liệu đó.
- [ ] Xuất kết quả AI đúng tọa độ ảnh gốc hoặc hệ LiDAR trước khi nhập vào ứng dụng.
- [ ] Đo riêng thời gian tải model, chạy khởi động, dự đoán, xử lý kết quả và huấn luyện; không gộp tất cả thành thời gian dự đoán.

## 5. Bổ sung báo cáo so sánh

**Cần viết thêm code:**

- [ ] Thêm cách chấm AI theo chuẩn COCO và KITTI nếu cần so sánh với kết quả công bố của các model. Phải xử lý đúng điểm tin cậy, đối tượng bỏ qua, đám đông và mức độ khó; điểm M49 hiện tại chưa thay thế các chuẩn này.
- [ ] Tổng hợp kết quả của từng lớp trên toàn thử nghiệm, ví dụ điểm riêng của xe con và người đi bộ. Bổ sung macro-F1, tức trung bình F1 giữa các lớp theo quy tắc đã chọn.
- [ ] Cho người duyệt xem nhãn chuẩn và nhãn cần chấm chồng lên nhau để tìm lỗi bằng mắt.
- [ ] Thống kê có bao nhiêu nhãn AI được giữ nguyên, sửa, xóa và bao nhiêu đối tượng được thêm mới. Cần ghi lịch sử chi tiết hơn; hiện mới ghi các lần lưu, chạy/dừng timer và chốt nhãn.
- [ ] Cho nhập đơn giá nhân công, giá thuê GPU và cách phân bổ chi phí huấn luyện để so sánh chi phí giữa các phương pháp.
- [ ] Xuất báo cáo ngoài CSV, kèm danh sách mẫu và cấu hình chấm để người khác có thể chạy lại. Bổ sung khoảng tin cậy để thể hiện mức độ bất định của kết quả thống kê.

## 6. Hoàn thiện trước khi dùng lâu dài hoặc nhiều người

**Cần viết thêm code:**

- [ ] Bổ sung Alembic để nâng cấp cấu trúc database mà vẫn giữ dữ liệu cũ. Hiện create_all chỉ tạo bảng còn thiếu, không nâng cấp bảng đã tồn tại.
- [ ] Bổ sung nhập file ZIP có kiểm tra đường dẫn an toàn và hiển thị tiến trình tải lên.
- [ ] Bổ sung sao lưu dữ liệu và dọn file đã lưu trên đĩa nhưng không còn bản ghi trong database.
- [ ] Phân quyền: người gán nhãn không được xem đáp án chuẩn; người quản lý/người duyệt mới được truy cập. Đồng thời sắp xếp nhiệm vụ để người tham gia không nhớ đáp án từ lượt làm trước.

**Bạn kiểm duyệt sau khi có code:** thử nâng cấp trên bản sao database, kiểm tra quyền truy cập và duyệt quy trình trước khi dùng với dữ liệu thật hoặc nhiều người.

## Thứ tự ưu tiên

Trước mắt làm **mục 1 và 2** để biết bản hiện tại chạy ra sao và có tính đúng điểm không. Sau đó sửa lỗi phát hiện được, bổ sung công cụ còn thiếu ở **mục 3**, rồi kết nối AI ở **mục 4**. Các phần báo cáo nâng cao ở **mục 5** làm theo nhu cầu thí nghiệm. **Mục 6** cần hoàn thiện trước khi dùng lâu dài hoặc tổ chức cho nhiều người tham gia.
