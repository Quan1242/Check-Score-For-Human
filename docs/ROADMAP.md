# Công việc tiếp theo

## Mốc 1 — 2D end-to-end
- [ ] Adapter BDD100K -> schema nội bộ, class mapping và split manifest.
- [ ] Editor SVG/canvas: vẽ, chọn, resize, xóa, zoom/pan, undo/redo, autosave.
- [ ] Transform tọa độ màn hình <-> ảnh gốc; kiểm thử resize/zoom.
- [ ] Assignment: người thực hiện, chế độ, mẫu, phiên bản cuối.
- [ ] Timer có pause/resume và event log phía server.
- [ ] Notebook model 2D: verify bản mới nhất phù hợp, pin checkpoint + package, predict và timing.
- [ ] Ghép khung một–một, precision/recall/F1 ở IoU cố định; AP cho AI có confidence.
- [ ] Thử pilot trước khi khóa benchmark.

## Mốc 2 — Instance segmentation
- [ ] Quyết định polygon đầy đủ hoặc COCO RLE; hỗ trợ holes/multipart.
- [ ] Adapter dataset segmentation đúng phiên bản.
- [ ] Polygon/brush editor và rasterization nhất quán.
- [ ] Notebook segmentation, nhập và sửa masks.
- [ ] Mask IoU/Dice, instance matching, phát hiện thiếu/thừa.

## Mốc 3 — 3D
- [ ] Upload/parse calibration KITTI, ghép ảnh–LiDAR.
- [ ] Viewer point cloud, top/front/side views và cuboid gizmo.
- [ ] Chuyển hệ tọa độ, tâm hộp, chiều kích thước và yaw.
- [ ] Chọn model 3D phù hợp KITTI + GPU Colab; pin phiên bản sau xác minh.
- [ ] Pipeline prediction -> schema lidar.
- [ ] IoU 3D và evaluation phù hợp benchmark, xử lý ignore/difficulty.

## Mốc 4 — Thử nghiệm và báo cáo
- [ ] Phân quyền ground truth, chia nhiệm vụ tránh nhớ đáp án.
- [ ] Dashboard theo task, lớp, người và model; không gộp các loại IoU.
- [ ] Cấu hình đơn giá, chi phí GPU và phân bổ chi phí train.
- [ ] Correction rate có mẫu số rõ ràng; additions báo riêng.
- [ ] Xuất CSV/report, split/config/version để tái lập.
- [ ] ZIP có kiểm tra đường dẫn, upload tiến trình, migrations và backup.
