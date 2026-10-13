# Demo một người: ưu tiên thời gian

## Chọn dữ liệu

Dùng 20 mẫu chính thức cho một tác vụ, thêm 3–5 mẫu pilot riêng để làm quen và chọn model/ngưỡng confidence. Không tải toàn bộ dataset vào ứng dụng. Bắt đầu với detection 2D; segmentation và 3D là các demo riêng, cần nhãn và pipeline riêng.

Đề xuất 20 ảnh gồm 6 dễ, 8 vừa và 6 khó. Đây là cách phân bổ phục vụ demo, không phải mẫu đại diện thống kê của dataset. Quy định mức khó trước khi xem dự đoán AI (ví dụ số đối tượng, kích thước, che khuất, ánh sáng), chọn ngẫu nhiên trong từng nhóm với seed cố định và lưu manifest tên ảnh. Nếu chỉ dùng 20 ca khó, ghi rõ là thử nghiệm ca khó; không suy rộng kết quả sang ảnh thông thường. Không đổi ảnh sau khi thấy assisted chậm.

Với BDD100K box2d, lấy ảnh và nhãn detection của cùng phiên bản/split có ground truth, ví dụ validation. Tham khảo [hướng dẫn dữ liệu chính thức](https://github.com/SysCV/bdd100k-models/blob/main/doc/PREPARE_DATASET.md). Nguồn có thể đóng gói ảnh thành archive lớn: tải/giải nén ở Colab hoặc Drive nếu cần, rồi chỉ chuyển các ảnh trong manifest về máy cá nhân. Không hứa nguồn tải luôn hỗ trợ tải lẻ từng ảnh.

Giữ ảnh gốc để tọa độ đúng; nếu đổi kích thước phải chuyển cả ground truth và AI. Chốt một số lớp đơn giản trước (ví dụ car, truck, pedestrian); thống nhất cách xử lý che khuất, cắt mép và đối tượng bỏ qua. Bộ chấm M49 không tự xử lý quy tắc ignore của BDD/COCO/KITTI.

`scripts/convert_bdd100k.py` nhận manifest là JSON list tên file, ví dụ `["a.jpg", "b.jpg"]`. Chuyển ground truth bằng lệnh trong README. Không đưa ground truth vào notebook inference. AI không được lấy đáp án chuẩn làm dự đoán.

Có thể dùng `scripts/prepare_demo.py` để tạo bộ ảnh và lịch làm lặp lại được. Chuẩn bị `candidates.json` gồm ba danh sách `easy`, `medium`, `hard`, ít nhất 7/9/7 ảnh tương ứng và không trùng tên. Ví dụ cấu trúc: `{"easy": ["a.jpg"], "medium": ["b.jpg"], "hard": ["c.jpg"]}` (cần điền đủ số ảnh). Chạy từ thư mục repo:

```bash
python scripts/prepare_demo.py --candidates data/candidates.json --images data/source_images --output data/demo-01 --seed 49
```

Script sao chép đúng 20 ảnh chính và 3 ảnh pilot vào `main/assets/` và `pilot/assets/`, tạo manifest cho mỗi nhóm, lưu danh sách ứng viên và lịch hai lượt trong `protocol.json`. Output phải là thư mục mới. Chỉ đưa thư mục main hoặc pilot lên Colab cho từng lần chạy; không trộn chúng. Dùng `data/demo-01/main/manifest.json` khi chuyển ground truth cho bộ chính. Lịch làm do bạn thực hiện theo file; ứng dụng chưa tự giao theo lịch.

## Notebook và luồng nhập

1. Mở `colab/detection_2d.ipynb` trong Colab. Notebook đã có pipeline YOLO11s 2D, chưa được chạy kiểm chứng. Model mặc định là điểm bắt đầu cho pilot, không bảo đảm đủ tốt trên BDD100K.
2. Đặt ảnh đã chọn trong `/content/demo/assets/` và manifest trong `/content/demo/manifest.json` bằng upload hoặc Drive; notebook chỉ đọc tối đa 20 ảnh có trong manifest.
3. Chạy cell cài Ultralytics đã pin phiên bản, cấu hình lớp và confidence, rồi inference từng ảnh. Không train model cho demo này. Cấu hình chỉ chỉnh trên pilot rồi giữ cố định cho bộ 20 ảnh.
4. Tải `predictions.json`, `timing.json`, `environment.txt`; giữ manifest và checkpoint/hash để tái lập. Nhập ảnh, ground truth và predictions vào cùng dự án M49. Không nhập timing.json như bộ nhãn.
5. Notebook segmentation/3D còn là template. Không dùng checkpoint 2D để tạo mask hoặc hộp 3D; các tác vụ đó cần lựa chọn dataset/model riêng.

## Cách đo

- Dùng cùng tên người thực hiện, cùng 20 mẫu, cùng lớp và ngưỡng IoU trong cả manual và assisted. Mỗi ảnh có hai Assignment.
- Chốt lịch trước: 10 ảnh manual trước, 10 ảnh assisted trước; lượt hai đổi chế độ, xáo thứ tự và nghỉ giữa hai lượt. Một người vẫn có thể nhớ ảnh nên đây là giới hạn của demo.
- Bắt đầu timer trước khi nhìn kỹ/đánh giá nhãn; thời gian assisted bao gồm rà soát nhãn AI đúng, sửa, xóa và bổ sung nhãn thiếu. Không chỉ đo thao tác kéo chuột.
- Editor yêu cầu timer đang chạy mới sửa nhãn. Tự pause khi ẩn tab hoặc sau 60 giây không có input; nếu vẫn đang quan sát, tiếp tục timer và ghi nhận ảnh bị gián đoạn. Không dùng việc idle để làm thời gian assisted có vẻ ngắn hơn.
- Heartbeat mỗi 10 giây; backend chỉ tính tối đa 30 giây từ heartbeat cuối khi tab crash/mất mạng. Sai số sự cố có thể tới 30 giây, không phải phép đo chính xác thời điểm đóng trang. Lưu nhãn còn trong editor rồi tải lại nhiệm vụ sau lỗi kết nối.
- Báo cáo hiện so sánh **thời gian thao tác của người**. Công thức: tiết kiệm = manual − assisted; tăng tốc = manual / assisted; tỷ lệ giảm = 1 − assisted/manual. Chỉ ghép cùng ảnh/cùng người đã chốt ở cả hai chế độ; thiếu cặp không kết luận đạt.
- Mục tiêu bắt buộc để gọi demo thành công: đủ cặp, thời gian dương ở cả hai phía, tổng assisted < tổng manual và F1 assisted không thấp hơn manual trên từng ảnh. F1 N/A không đủ bằng chứng đạt chất lượng. Đây là tiêu chí đạt, không phải kết quả được ép sẵn; giao diện hiển thị Đạt/Chưa đạt/Thiếu thời gian/Chưa đủ cặp.
- Nếu cần so sánh từ đầu đến cuối: cộng thêm thời gian inference, xử lý kết quả, truyền/nhập dữ liệu và thiết lập vào assisted; báo riêng cold start tải model/khởi động. Không gọi chỉ số thời gian thao tác là tổng thời gian toàn quy trình. Notebook xuất timing riêng để tính phần AI; giao diện chưa tự cộng phần này.
- Nếu chưa đạt: cải thiện model/ngưỡng trên pilot hoặc giảm thao tác thừa trong editor, rồi chạy một lượt mới và giữ kết quả cũ. Không sửa số giây hoặc chỉ giữ những ảnh AI thắng.
- CSV giữ từng dòng theo mẫu và lặp lại tổng thời gian ghép cặp của người đó ở các cột `manual_paired_seconds`, `assisted_paired_seconds`, `saved_seconds`, `speedup`, `time_goal`. Không cộng các cột tổng này qua các dòng; `active_seconds` mới là thời gian riêng của từng nhiệm vụ.

## Giới hạn máy và kiểm tra do người dùng thực hiện

Chạy một backend worker trên localhost với SQLite. Code giới hạn 20 mẫu/thử nghiệm, 40 nhiệm vụ khi chấm và 3 bản AI/dự án; dùng dự án demo riêng nếu dữ liệu cũ vượt giới hạn. Mỗi lần chỉ một yêu cầu chấm được chạy trong process, yêu cầu khác nhận 429. Giới hạn này không áp dụng liên process: không chạy nhiều worker.

Bộ chấm giới hạn 80 đối tượng mỗi phía/mẫu; segmentation tối đa 4 triệu pixel/ảnh và 32 triệu pixel tổng mask/mẫu. Đây là rào chắn quy mô, không bảo đảm mức RAM cụ thể trên mọi máy.

Người dùng chạy test/build và kiểm tra giao diện; đợt code này không chạy các lệnh đó:

- Backend: `python -m pytest -q` trong `backend`.
- Frontend: `pnpm build` trong `frontend`.
- Thử timer resume/pause, ẩn tab, idle, mất mạng/đóng tab, autosave cạnh heartbeat và tải lại; nhãn chưa lưu không được mất.
- Assisted giữ nguyên nhãn AI: bấm Lưu và chốt một lần; bản AI nguồn phải không đổi. Thử lỗi lưu: không được chốt bản nháp cũ.
- So sánh đủ/thiếu cặp, thời gian bằng 0, assisted nhanh/chậm và F1 thấp hơn; không được luôn hiển thị Đạt.
- Thử quá 20 mẫu, quá giới hạn mask và hai yêu cầu chấm đồng thời; theo dõi RAM/CPU với 3–5 mẫu trước khi tăng lên 20.
- Chạy notebook trên pilot, kiểm tra tọa độ/lớp/confidence và các tệp xuất trước khi nhập bộ chính thức.

Không đổi schema database trong đợt này. Dừng/pause các timer của bản cũ trước khi nâng cấp: cách tính timer mới dùng lease 30 giây, không tiếp tục đo một phiên đang chạy từ bản cũ.
