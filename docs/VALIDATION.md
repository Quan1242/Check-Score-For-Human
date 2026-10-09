# Báo cáo thay đổi trước khi push

## Mốc ghi nhận 08:54 ngày 09/10/2026

Múi giờ: UTC+07:00, Việt Nam / Asia/Bangkok. Định dạng mốc ghi nhận: HH:mm ngày DD/MM/YYYY.

Báo cáo ghi nhận các thay đổi đang có trong working tree của dự án M49, phục vụ đọc và rà soát trước khi commit/push. Nội dung validation cũ, checklist kiểm thử và các kết quả kiểm tra lịch sử trong file này đã được thay thế hoàn toàn.

Mốc trên là thời điểm lập báo cáo cho đợt thay đổi, không phải thời điểm hoàn thành riêng từng file. Không có nhật ký đủ chính xác đến phút của từng thao tác trước đó nên không gán giờ hồi tố. Các đợt cập nhật tiếp theo sẽ được ghi thành mốc mới theo cùng định dạng.

Phạm vi đợt này gồm 23 file: 14 file đang được Git theo dõi có thay đổi và 9 file mới chưa được theo dõi tại thời điểm lập báo cáo. Đã triển khai code cho box 2D, polygon segmentation và cuboid LiDAR xoay yaw, trên cùng luồng quản lý thử nghiệm, giao nhiệm vụ, lưu nhãn và tính điểm.

## Backend và dữ liệu

### Mốc ghi nhận 08:54 ngày 09/10/2026 — Mô hình thử nghiệm và nhiệm vụ

File thay đổi: `backend/app/models.py`.

Bổ sung ba model SQLModel:

- `Experiment` lưu dự án, tên thử nghiệm, ID ground truth, danh sách asset, ngưỡng IoU và thời điểm tạo. Cấu hình được ghi khi tạo; chưa có endpoint sửa cấu hình sau đó.
- `Assignment` liên kết một thử nghiệm, một asset, một người thực hiện và chế độ manual/assisted. Các trường parent_id, draft_id và final_id xác định nguồn AI, bản nháp hiện tại và bản cuối dùng để chấm.
- `AnnotationEvent` lưu loại sự kiện, assignment_id, revision và timestamp phía server cho save/resume/pause/finalize.

Assignment có unique constraint theo experiment_id, asset_id, annotator và mode để tránh giao trùng cùng nhiệm vụ trong một chế độ. Trường revision phục vụ phát hiện yêu cầu cũ; active_seconds và running_since phục vụ đo thời gian.

Không thay đổi cột của Project, Asset và LabelSet. Database hiện vẫn khởi tạo bằng create_all; chưa bổ sung Alembic và chưa chạy khởi tạo/nâng cấp database cho thay đổi này.

### Mốc ghi nhận 08:54 ngày 09/10/2026 — API và giao dịch lưu nhãn

File mới: `backend/app/benchmark.py`. File tích hợp: `backend/app/main.py`.

Các nhóm API đã viết:

- GET/POST `/api/projects/{project_id}/experiments`: liệt kê và tạo thử nghiệm. Kiểm tra ground truth đúng dự án/source, tên không rỗng, asset không trùng và mỗi mẫu có nhãn chuẩn tương ứng.
- GET/POST `/api/experiments/{experiment_id}/assignments`: liệt kê và giao nhiệm vụ. Mẫu phải nằm trong thử nghiệm; assisted phải có parent AI đúng dự án và có sample tương ứng; manual không nhận parent_id.
- GET `/api/assignments/{assignment_id}/editor`: trả assignment, asset và objects. Ưu tiên nhãn final, rồi draft, rồi AI parent; manual mới bắt đầu với danh sách rỗng. Không trả payload ground truth.
- POST `/api/assignments/{assignment_id}/draft`: nhận revision và objects; lấy task, asset, người thực hiện và AI parent từ dữ liệu nhiệm vụ phía server.
- POST `/api/assignments/{assignment_id}/finalize`: chốt draft hiện tại và dừng timer. Cần có draft trước khi chốt, kể cả mẫu không có đối tượng.
- GET/POST `/api/assignments/{assignment_id}/events`: đọc event log hoặc thực hiện resume/pause.
- GET `/api/experiments/{experiment_id}/score`: tính báo cáo chất lượng nhãn theo giao thức M49.
- GET `/api/experiments/{experiment_id}/results.csv`: xuất kết quả theo mẫu.

Lưu draft, chốt và timer dùng compare-and-swap trên revision. Nếu nhiệm vụ đã chốt hoặc revision đã thay đổi, yêu cầu bị từ chối với HTTP 409. Lưu draft tạo LabelSet mới và cập nhật con trỏ draft_id trong cùng giao dịch, giữ nguyên snapshot AI.

Hàm save_bundle được bổ sung tham số commit để có thể tham gia giao dịch của Assignment. Các endpoint lưu nhãn cũ giữ mặc định commit như trước. Router mới được gắn vào ứng dụng FastAPI; summary đổi evaluation_status thành m49_available_pending_validation.

### Mốc ghi nhận 08:54 ngày 09/10/2026 — Kiểm tra polygon và schema

File thay đổi: `backend/app/schemas.py`, `docs/label-bundle.schema.json`.

Polygon nhận từ 3 đến 1.000 đỉnh. Code bổ sung kiểm tra đỉnh trùng, diện tích bằng 0, cạnh kề chồng lên nhau, tự giao và tự chạm. Đỉnh đầu không được lặp lại ở cuối danh sách.

JSON schema bổ sung maxItems=1000 cho points. Bundle vẫn giữ schema_version 1.0; các đối tượng Experiment/Assignment nằm ngoài bundle. Ràng buộc hình học mới được ghi trong DATA_CONTRACT để người nhập dữ liệu biết các polygon từng được chấp nhận có thể bị từ chối nếu không đáp ứng điều kiện mới.

## Bộ chấm và kết quả

### Mốc ghi nhận 08:54 ngày 09/10/2026 — Hình học và matching

File mới: `backend/app/evaluation/metrics.py`.

IoU box 2D được tính theo tọa độ liên tục trên ảnh gốc, dùng diện tích giao/hợp và không cộng 1 vào chiều rộng hoặc chiều cao.

Segmentation dùng polygon đơn để raster hóa mask ở độ phân giải ảnh gốc. Thuật toán xét tâm pixel (x+0.5, y+0.5), dùng even/odd scanline với khoảng nửa mở. Mask rỗng bị từ chối. IoU tính từ pixel giao/hợp, còn Dice của cặp đã ghép được suy ra bằng 2*IoU/(1+IoU).

Cuboid 3D được biểu diễn trong hệ LiDAR với tâm hình học, kích thước dài/rộng/cao và yaw. Code tạo hình chữ nhật đáy đã xoay, cắt giao bằng Sutherland-Hodgman rồi nhân với phần giao theo chiều cao để tính thể tích giao. Không dùng BEV IoU thay cho IoU 3D; chưa hỗ trợ pitch/roll.

Matching thực hiện riêng từng mẫu và từng lớp. Chỉ cạnh có IoU đạt ngưỡng mới hợp lệ. Thuật toán tăng luồng theo đường đi ngắn nhất ưu tiên số cặp ghép tối đa, sau đó tối đa tổng IoU. Không dùng matching này để tuyên bố kết quả COCO/KITTI official.

Các đầu ra gồm TP, FP, FN, Precision, Recall, F1, IoU trung bình cặp ghép, kết quả theo lớp và danh sách cặp ghép. Mẫu số bằng 0 trả null để giao diện hiển thị N/A.

Giới hạn được đặt trong code: tối đa 300 đối tượng cho mỗi phía của một mẫu; ảnh mask tối đa 25 triệu pixel và tổng kích thước các mask trong mẫu tối đa 128 triệu pixel. Hiệu năng thực tế của thuật toán chưa được đo.

### Mốc ghi nhận 08:54 ngày 09/10/2026 — Tổng hợp và CSV

File triển khai: `backend/app/benchmark.py`, `frontend/src/features/Experiments.tsx`.

Nhãn người chỉ được chấm khi Assignment có final_id. Mỗi bản AI được chấm trên các asset thuộc thử nghiệm. Mẫu thiếu hoặc chưa chốt vẫn xuất hiện trong báo cáo completion; không bị tự chuyển thành bộ nhãn rỗng.

Tổng hợp theo phương pháp và người thực hiện; AI được phân biệt thêm bằng run ID. Với nhãn người, mẫu số completion là số Assignment đã giao trong nhóm; với AI là số asset của thử nghiệm cho mỗi run. Code cộng TP/FP/FN trước khi tính tỷ số, không lấy trung bình F1 theo ảnh.

Giao diện có bảng tổng hợp, chi tiết theo mẫu/lớp và danh sách cặp ghép kèm IoU/Dice. Ngưỡng IoU và chính sách xử lý dữ liệu thiếu được hiển thị cùng kết quả.

CSV xuất UTF-8 kèm BOM, chứa experiment ID, task, ground truth ID, ngưỡng, missing policy, source, annotator, label-set ID, assignment ID, asset, trạng thái hoàn thành, thời gian và metric. Chuỗi có thể bị spreadsheet diễn giải thành công thức được thêm dấu nháy đơn ở đầu. Các giá trị null được ghi thành ô trống trong CSV; giao diện hiển thị N/A.

## Giao diện gán nhãn

### Mốc ghi nhận 08:54 ngày 09/10/2026 — Luồng làm việc dùng chung

File thay đổi: `frontend/src/App.tsx`, `frontend/src/features/annotation/AnnotationWorkspace.tsx`, `frontend/src/types.ts`, `frontend/src/styles.css`. File mới: `frontend/src/features/Experiments.tsx`, `frontend/src/features/annotation/history.ts`.

Tab Dữ liệu được bổ sung form tạo thử nghiệm: tên, ground truth, ngưỡng IoU và danh sách mẫu. Tab Gán nhãn cho phép chọn thử nghiệm, tạo nhiệm vụ manual/assisted, tải nhãn hiện tại và chỉnh sửa bằng editor theo tác vụ. Tab Kết quả gọi bộ chấm và cung cấp tải CSV; số lượng phiên bản nhãn vẫn được trình bày riêng.

AnnotationWorkspace được chuyển từ sửa JSON thủ công sang quản lý Assignment. JSON nhãn vẫn có thể xem ở phần thu gọn, nhưng thao tác chính dùng editor hình học. Chọn đối tượng, đổi lớp và xóa đối tượng dùng chung cả ba tác vụ.

History reducer lưu tối đa 100 trạng thái quá khứ cho undo/redo; khi tải nhiệm vụ khác, lịch sử được đặt lại. Autosave có debounce 900 ms, có nút lưu ngay và thông báo khi lỗi. Nội dung chưa lưu được giữ trong editor để người dùng xử lý.

Giao diện gửi revision hiện tại trong các thao tác lưu/chốt/timer và cập nhật revision từ server sau khi thành công. Điều hướng sang tab/dự án khác bị chặn khi có thay đổi chưa lưu, đang thao tác hoặc timer đang chạy. beforeunload được dùng để cảnh báo khi rời trang trong các trạng thái này; có nút tải lại nhiệm vụ để đồng bộ lại bản trên server.

Types bổ sung Point, Vec3, Geometry, Annotation, Experiment và Assignment. Styles bổ sung toolbar, vùng editor, danh sách mẫu, JSON preview và phần chi tiết kết quả.

### Mốc ghi nhận 08:54 ngày 09/10/2026 — Editor box 2D và polygon

File mới: `frontend/src/features/annotation/ImageEditor.tsx`.

Editor dùng SVG trên ảnh gốc, không thêm thư viện ngoài. Có ba chế độ chọn/kéo, vẽ và di chuyển ảnh; hỗ trợ zoom bằng cuộn chuột và đưa ảnh về khung nhìn ban đầu.

Với box 2D, người dùng kéo để tạo khung, chọn và kéo cả box hoặc kéo các nút góc để đổi kích thước. Tọa độ con trỏ được chuyển qua ma trận SVG về không gian ảnh, sau đó giới hạn theo biên ảnh. Bản preview trong khi kéo chỉ được đưa vào lịch sử khi kết thúc thao tác.

Với segmentation, người dùng thêm từng đỉnh rồi đóng polygon, có thể bỏ điểm cuối hoặc hủy hình đang vẽ. Polygon đã tạo có thể kéo toàn bộ hoặc kéo từng đỉnh. Editor hiển thị lớp và các điểm điều khiển của đối tượng đang chọn. Dữ liệu lưu là tọa độ pixel ảnh gốc, không phải tọa độ màn hình.

Chỉ hỗ trợ polygon đơn; chưa triển khai brush, holes, multipart hoặc RLE.

### Mốc ghi nhận 08:54 ngày 09/10/2026 — Point cloud và cuboid 3D

File mới: `frontend/src/features/annotation/CloudEditor.tsx`, `frontend/src/features/annotation/pointcloud.ts`.

Parser hỗ trợ BIN theo bộ bốn float32 little-endian x/y/z/intensity và PCD ASCII/binary không nén. PCD được đọc theo header FIELDS, SIZE, TYPE và COUNT để lấy tọa độ. Dạng binary_compressed có thông báo chưa hỗ trợ. Các điểm không có tọa độ hữu hạn bị bỏ qua trong viewer.

Viewer lấy mẫu tối đa 60.000 điểm để hiển thị bằng Canvas 2D với phép chiếu các tọa độ 3D. Có các góc nhìn trên/trước/bên, chỉnh góc nhìn và độ nghiêng, kéo khung nhìn và zoom. Trục X/Y/Z được ghi theo quy ước LiDAR. File point cloud gốc không bị thay đổi.

Cuboid được vẽ bằng các cạnh và đường chỉ hướng yaw. Người dùng thêm cuboid, chọn trong danh sách rồi chỉnh tâm X/Y/Z, dài/rộng/cao và yaw qua trường số; dùng chung đổi lớp, xóa và undo/redo. Chưa có gizmo kéo/resize/xoay cuboid trực tiếp trên point cloud hoặc ghép ảnh camera bằng calibration.

## Công cụ dữ liệu và tài liệu

### Mốc ghi nhận 08:54 ngày 09/10/2026 — Nhập dữ liệu hàng loạt

File mới: `scripts/import_folder.py`, `scripts/convert_bdd100k.py`. File thay đổi: `.gitignore`.

import_folder dùng thư viện chuẩn Python để upload thư mục assets trước, sau đó ground_truth và ai. Script gọi API hiện có, kiểm tra giới hạn kích thước và dừng khi gặp lỗi. Các upload trước lỗi vẫn được giữ. Tùy chọn skip-existing-assets chỉ bỏ qua theo tên, không đối chiếu nội dung; nhập lại JSON tạo phiên bản mới.

convert_bdd100k chuyển box2d từ danh sách nhãn BDD100K sang bundle M49. Danh sách ảnh lấy từ manifest JSON; lớp được chọn rõ bằng tham số, có tùy chọn class map. Script từ chối manifest rỗng/trùng, tên ảnh trùng trong input, thiếu nhãn hoặc thiếu box2d của lớp đã chọn. Không tự tạo confidence AI và không ghi đè file output đã có.

Thư mục data/ được thêm vào .gitignore để dữ liệu thực nghiệm không được đưa vào Git ngoài ý muốn. Đầu ra converter vẫn cần qua validation API theo ảnh/lớp của dự án.

### Mốc ghi nhận 08:54 ngày 09/10/2026 — Tài liệu dự án

Các file được cập nhật gồm README.md, docs/ARCHITECTURE.md, docs/DATA_CONTRACT.md, docs/ROADMAP.md và docs/label-bundle.schema.json.

README mô tả luồng tạo thử nghiệm, giao nhiệm vụ, chỉnh nhãn, chốt và xem điểm; bổ sung hướng dẫn dùng hai script dữ liệu và nêu giới hạn hiện tại. ARCHITECTURE mô tả các model mới, giao dịch revision, editor và timer. DATA_CONTRACT ghi ràng buộc polygon, API Assignment, quy tắc raster hóa và giới hạn hình học/bộ nhớ.

ROADMAP bỏ các đầu việc code đã triển khai, giữ công việc còn lại. Việc bỏ khỏi roadmap chỉ phản ánh có implementation, không phải xác nhận đã nghiệm thu. File VALIDATION.md được thay toàn bộ bằng báo cáo này; các liên kết tới file được đổi nhãn cho đúng nội dung.

## Trạng thái bàn giao tại 08:54 ngày 09/10/2026

Đã viết code và đọc/rà soát nguồn; chưa chạy pytest, TypeScript/Vite build, frontend tests, server, Docker, migration, inference hoặc kiểm duyệt giao diện. Không thêm dependency, không sửa lockfile và không cài các thư viện đề xuất trong DOCX. Các kết quả kiểm tra của bộ khung cũ không được dùng làm bằng chứng cho đợt thay đổi này.

Các phần chưa triển khai gồm Alembic; phân quyền ground truth; heartbeat/idle detection cho timer; segmentation nhiều vùng/có lỗ và brush; gizmo cuboid; calibration KITTI và chuyển hệ camera–LiDAR; inference model thật; COCO/KITTI AP; báo cáo chi phí và thống kê chỉnh sửa nâng cao.

Timer hiện cần người dùng pause trước khi đóng trang. Nếu đóng cưỡng bức hoặc crash khi đang chạy, khoảng thời gian phía server có thể tiếp tục tăng. Endpoint editor không trả ground truth nhưng API quản trị vẫn chưa có phân quyền, nên chưa dùng để tổ chức benchmark mù nhiều người.

Chưa tạo commit và chưa push trong đợt làm việc này. Các file mới cần được đưa vào staging cùng các file đã sửa khi người dùng quyết định commit; báo cáo không thay cho kiểm thử hoặc phê duyệt đưa vào sử dụng.

## Mốc ghi nhận 09:13 ngày 09/10/2026 — Viết lại roadmap

File thay đổi: `docs/ROADMAP.md`.

Viết lại danh sách công việc bằng tiếng Việt dễ hiểu, chia thành sáu phần: chạy thử bản hiện tại, chuẩn bị dữ liệu và kiểm tra điểm, nâng cấp editor, kết nối AI, bổ sung báo cáo và hoàn thiện trước khi dùng lâu dài/nhiều người. Mỗi phần ghi rõ việc do người dùng thực hiện hoặc việc cần viết thêm code; giải thích thuật ngữ ngay tại mục liên quan và bổ sung thứ tự ưu tiên.

Giữ các công việc chưa hoàn thành của roadmap trước đó, không đánh dấu thêm chức năng nào là đã xong. Đợt cập nhật này chỉ sửa tài liệu; không sửa code, không chạy test/build, không commit hoặc push.

## Mốc ghi nhận 09:15 ngày 09/10/2026 — Chuẩn bị commit và push

Người dùng yêu cầu đưa các thay đổi lên repository. Đã fetch origin và xác nhận nhánh main cục bộ đồng bộ với origin/main trước khi tạo commit. Phạm vi chuẩn bị commit gồm 23 file code và tài liệu của đợt này; không có dữ liệu thực nghiệm hoặc file DOCX bên ngoài repository.

Tiếp tục giữ yêu cầu không chạy test/build. Mốc này ghi nhận bước chuẩn bị; kết quả commit và push được xác nhận trong lịch sử Git và thông báo bàn giao sau khi lệnh hoàn tất.
