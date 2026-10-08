# M49 — Đặc tả công thức đánh giá Human vs AI Annotation Benchmark

**Phiên bản:** 2.0 — bản thuần công thức · **Ngày:** 08/10/2026  
**Phạm vi:** Bounding box 2D, instance segmentation, bounding box 3D; so sánh `manual`, `ai`, `assisted`.  
**Không bao gồm:** mã nguồn, pseudocode, cấu hình, lệnh, quy trình cài đặt hoặc chỉ dẫn lập trình.

## 1. Mục tiêu và phạm vi đánh giá

M49 có **hai hệ đánh giá tách biệt**:

1. **Chất lượng bộ nhãn cuối (giao thức M49):** áp dụng nhất quán cho nhãn thủ công, nhãn AI và nhãn AI được người sửa. Báo cáo TP, FP, FN, Precision, Recall, F1, IoU trung bình trên các cặp ghép và tỷ lệ hoàn thành. Không yêu cầu confidence trên nhãn người.
2. **Chất lượng mô hình phát hiện (giao thức benchmark):** COCO-style AP cho bbox/mask và KITTI AP_R40 cho 3D. Đòi hỏi điểm tin cậy, thứ tự xếp hạng và các quy tắc riêng của benchmark. **Không được dùng phép ghép của M49 để thay phép ghép trong COCO/KITTI.**

Chất lượng hình học, khả năng tìm đủ đối tượng, thời gian và chi phí là **các trục đánh giá riêng**. Chỉ tạo điểm tổng hợp khi trọng số đã được xác định trước.

### Ký hiệu dùng chung

| Ký hiệu | Ý nghĩa |
|---|---|
| $G$, $P$ | Tập nhãn chuẩn và tập nhãn dự đoán trên cùng mẫu |
| $c$ | Lớp đối tượng |
| $\tau$ | Ngưỡng IoU để chấp nhận ghép cặp |
| $M$ | Tập cặp ghép một–một hợp lệ |
| $N$ | Số mẫu được giao; $n$ là số mẫu hoàn thành |
| $|A|$ | Số phần tử, diện tích hoặc thể tích của $A$ tùy ngữ cảnh |
| $\mathrm{N/A}$ | Giá trị không xác định/không áp dụng; không tự thay bằng 0 hoặc 1 |

**Điều kiện so sánh:** cùng danh sách lớp, cùng mẫu và ground truth đã khóa, cùng chính sách che khuất/cắt biên/ignore; cùng định nghĩa “hoàn thành”. Dữ liệu nên được chia theo cảnh/video để tránh rò rỉ giữa các tập.

## 2. IoU của bounding box 2D

Với hai hộp $A=(a_{x1},a_{y1},a_{x2},a_{y2})$ và $B=(b_{x1},b_{y1},b_{x2},b_{y2})$, sử dụng tọa độ **liên tục trên ảnh gốc**, $x_1<x_2$, $y_1<y_2$:

$$
w_I=\max\!\left(0,\min(a_{x2},b_{x2})-\max(a_{x1},b_{x1})\right)
$$

$$
h_I=\max\!\left(0,\min(a_{y2},b_{y2})-\max(a_{y1},b_{y1})\right)
$$

$$
I=w_Ih_I,\quad S_A=(a_{x2}-a_{x1})(a_{y2}-a_{y1}),\quad S_B=(b_{x2}-b_{x1})(b_{y2}-b_{y1})
$$

$$
\boxed{\operatorname{IoU}_{2D}(A,B)=\frac{I}{S_A+S_B-I}}
$$

**Đối chiếu:** cùng định nghĩa giao/hợp sử dụng cho bbox IoU; ví dụ $A=[0,0,10,10]$, $B=[5,0,15,10]$ cho $\operatorname{IoU}=50/150=1/3$. Không cộng $1$ vào chiều rộng/chiều cao trong hệ tọa độ liên tục. Hộp có diện tích không dương phải bị loại ở bước kiểm tra hợp lệ. [S1–S2]

## 3. Instance segmentation: Mask IoU và Dice

Với $A$ và $B$ là **tập pixel foreground của hai instance**:

$$
I=|A\cap B|,\qquad U=|A\cup B|=|A|+|B|-I
$$

$$
\boxed{\operatorname{IoU}_{mask}=\frac{I}{U}},\qquad
\boxed{\operatorname{Dice}=\frac{2I}{|A|+|B|}}
$$

Khi mẫu số xác định:

$$
\boxed{\operatorname{Dice}=\frac{2\operatorname{IoU}_{mask}}{1+\operatorname{IoU}_{mask}}}
$$

**Đối chiếu số học:** $|A|=100$, $|B|=120$, $I=80$ dẫn tới $\operatorname{IoU}=80/140\approx0{,}571429$ và $\operatorname{Dice}=160/220\approx0{,}727273$.

Không thay mask IoU bằng IoU của hộp bao. Nếu cả hai mask rỗng, biểu thức có mẫu số bằng 0 và không được gán giá trị 1 để tăng điểm. Instance mask rỗng là lỗi dữ liệu; trường hợp hai ảnh không có instance phải được xử lý ở mức tập đối tượng. Khi so sánh mask, chuẩn hóa kích thước và quy tắc raster hóa trước. [S1], [S3]

## 4. Bounding box 3D có yaw quanh trục đứng

**Quy ước M49:** hộp $B=(c_x,c_y,c_z,l,w,h,\theta)$, tâm là tâm hình học, trục $z$ hướng lên, $l,w,h>0$ đo bằng mét, yaw $\theta$ tính bằng radian; hộp không có pitch/roll.

Bốn góc đáy cục bộ thuộc tập:

$$
\mathcal{V}=\{(-l/2,-w/2),(l/2,-w/2),(l/2,w/2),(-l/2,w/2)\}.
$$

Phép quay–tịnh tiến sang mặt phẳng thế giới:

$$
\begin{bmatrix}x\\y\end{bmatrix}
=\begin{bmatrix}c_x\\c_y\end{bmatrix}
+\begin{bmatrix}\cos\theta&-\sin\theta\\\sin\theta&\cos\theta\end{bmatrix}
\begin{bmatrix}u\\v\end{bmatrix},\quad (u,v)\in\mathcal{V}.
$$

Gọi $S_{A\cap B}$ là diện tích giao của **hai đa giác đáy xoay**. Chiều cao giao:

$$
h_I=\max\!\left(0,\min(c_{z,A}+h_A/2,c_{z,B}+h_B/2)-\max(c_{z,A}-h_A/2,c_{z,B}-h_B/2)\right).
$$

$$
V_I=S_{A\cap B}h_I,\qquad V_A=l_Aw_Ah_A,\quad V_B=l_Bw_Bh_B
$$

$$
\boxed{\operatorname{IoU}_{3D}=\frac{V_I}{V_A+V_B-V_I}},\qquad
\boxed{\operatorname{IoU}_{BEV}=\frac{S_{A\cap B}}{l_Aw_A+l_Bw_B-S_{A\cap B}}}
$$

**Đối chiếu số học:** hai hộp cùng tâm, cùng $l=4,w=2,h=2$, xoay nhau $90^\circ$: diện tích giao đáy $4$, thể tích giao $8$, mỗi thể tích $16$, nên $\operatorname{IoU}_{3D}=8/(16+16-8)=1/3$.

**Giới hạn:** biểu thức trên chính xác cho hai hộp cùng trục đứng chỉ xoay yaw; hộp có pitch/roll đòi hỏi thuật toán giao khối đa diện tổng quát. KITTI dùng quy ước camera khác LiDAR về tọa độ/trục/tâm; không được đổi tên trường rồi áp dụng công thức. **BEV IoU không phải 3D IoU.** [S5–S7]

### Sai số hình học 3D bổ sung

Với cặp ghép $(p,g)$:

$$
e_{center}=\sqrt{(c_{x,p}-c_{x,g})^2+(c_{y,p}-c_{y,g})^2+(c_{z,p}-c_{z,g})^2}
$$

$$
e_l=\frac{|l_p-l_g|}{l_g},\quad e_w=\frac{|w_p-w_g|}{w_g},\quad e_h=\frac{|h_p-h_g|}{h_g}
$$

$$
\boxed{e_\theta=\left|\operatorname{atan2}\!\left(\sin(\theta_p-\theta_g),\cos(\theta_p-\theta_g)\right)\right|},\qquad
e_{\theta,deg}=e_\theta\frac{180}{\pi}.
$$

Sai số góc được chuẩn hóa vào $[0,\pi]$; nếu bài toán phân biệt đầu/đuôi xe, yaw phải báo riêng vì quay $180^\circ$ có thể giữ nguyên IoU hình học.

## 5. Ghép một–một của bộ nhãn cuối (quy tắc M49, không phải COCO/KITTI)

Trong **mỗi mẫu và mỗi lớp**, đặt ma trận chất lượng $Q_{ij}=\operatorname{IoU}(p_i,g_j)$ theo loại hình học đang xét. Chỉ cho phép cặp có $Q_{ij}\ge\tau$.

$$
\mathcal{E}_\tau=\{(i,j):Q_{ij}\ge\tau\}
$$

Mỗi nhãn dự đoán và nhãn chuẩn chỉ xuất hiện nhiều nhất một lần. Chọn nghiệm theo thứ tự ưu tiên từ trái sang phải:

$$
\boxed{M^*=\underset{M\subseteq\mathcal E_\tau\,;\,M\text{ một–một}}{\operatorname{lexmax}}\left(|M|,\sum_{(i,j)\in M}Q_{ij}\right)}.
$$

Nghĩa là **(1) tối đa số cặp hợp lệ, (2) trong các nghiệm đó tối đa tổng IoU**. Không tối đa tổng IoU trước rồi mới loại cặp dưới ngưỡng.

**Phản ví dụ kiểm tra:** tại $\tau=0{,}5$ và $Q=\begin{bmatrix}1&0{,}5\\0{,}5&0{,}49\end{bmatrix}$, ghép chéo cho **2** cặp hợp lệ, ghép theo đường chéo chỉ cho **1** cặp hợp lệ. M49 phải chọn ghép chéo.

**Quy ước:** nghiệm đồng hạng có thể khác ID cặp; số cặp và tổng IoU tối ưu phải giống nhau. Với ảnh/miền có ignore hoặc crowd cần giao thức bổ sung, không được áp dụng phép ghép này rồi tự coi tương đương benchmark gốc. [S4]

## 6. TP, FP, FN và Precision/Recall/F1 của nhãn cuối

Sau matching trên từng mẫu/lớp:

$$
TP=|M^*|,\qquad FP=|P|-TP,\qquad FN=|G|-TP.
$$

$$
\boxed{Precision=\frac{TP}{TP+FP}},\quad
\boxed{Recall=\frac{TP}{TP+FN}},\quad
\boxed{F1=\frac{2TP}{2TP+FP+FN}}.
$$

**Ví dụ kiểm tra:** $|G|=120$, $|P|=100$, $TP=80$, suy ra $FP=20$, $FN=40$, $Precision=80\%$, $Recall\approx66{,}67\%$, $F1\approx72{,}73\%$.

### Quy tắc mẫu số bằng 0 (quy ước M49)

| Tình huống | Precision | Recall | F1 |
|---|---:|---:|---:|
| Có GT, không có dự đoán | N/A | 0 | 0 |
| Không có GT, có dự đoán | 0 | N/A | 0 |
| Không có GT, không có dự đoán | N/A | N/A | N/A |
| Mọi mẫu số xác định | Theo công thức | Theo công thức | Theo công thức |

Ở cấp toàn bộ dataset, **cộng TP/FP/FN trước rồi tính tỷ số**, không tính trung bình F1 từng ảnh. Lớp sai tạo FP cho lớp được dự đoán và FN cho lớp đúng (nếu không có cặp ghép khác).

### Micro-F1, macro-F1 và trung bình IoU

$$
TP_\Sigma=\sum_c TP_c,\quad FP_\Sigma=\sum_c FP_c,\quad FN_\Sigma=\sum_c FN_c.
$$

$$
\boxed{F1_{micro}=\frac{2TP_\Sigma}{2TP_\Sigma+FP_\Sigma+FN_\Sigma}},\qquad
\boxed{F1_{macro}=\frac{1}{|\mathcal C'|}\sum_{c\in\mathcal C'}F1_c}.
$$

$\mathcal C'$ phải được công bố trước (khuyến nghị: các lớp có GT trong benchmark). Vẫn hiển thị các lớp không có GT nhưng xuất hiện FP và tính FP đó vào micro.

$$
\boxed{\overline{IoU}_{matched}=\frac{1}{|M^*|}\sum_{(i,j)\in M^*}Q_{ij}},\quad |M^*|>0.
$$

Nếu không có cặp ghép, $\overline{IoU}_{matched}=\mathrm{N/A}$. Đây là IoU **có điều kiện trên cặp ghép**; không được so sánh riêng mà bỏ qua recall.

## 7. COCO-style AP cho bbox/mask: công thức tham chiếu, không thay evaluator

Cho từng lớp $c$ và ngưỡng IoU $t$, sắp xếp phát hiện theo confidence giảm dần. Sau khi thực hiện phép ghép và ignore/crowd **đúng giao thức COCO**:

$$
P_k=\frac{TP_k}{TP_k+FP_k},\qquad R_k=\frac{TP_k}{N_{GT,c}}.
$$

Đường precision nội suy:

$$
p_{int}(r;c,t)=\max_{k:R_k\ge r}P_k,
$$

với giá trị bằng 0 nếu không có điểm $k$ đáp ứng và lớp có GT hợp lệ. Với 101 mốc $\mathcal R=\{0,0{,}01,\ldots,1\}$:

$$
\boxed{AP(c,t)=\frac{1}{101}\sum_{r\in\mathcal R}p_{int}(r;c,t)}.
$$

$$
\boxed{AP_{50}=\operatorname{mean}_{c\in\mathcal C_{valid}}AP(c,0{,}50)},\qquad
\boxed{AP_{75}=\operatorname{mean}_{c\in\mathcal C_{valid}}AP(c,0{,}75)}
$$

$$
\boxed{AP_{50:95}=\operatorname{mean}_{c\in\mathcal C_{valid},\ t\in\{0{,}50,0{,}55,\ldots,0{,}95\}}AP(c,t)}.
$$

**Đối chiếu giao thức:** COCOeval mặc định dùng 10 ngưỡng IoU từ 0,50 đến 0,95 (bước 0,05), 101 mức recall và các thiết lập area/max detections riêng. Các công thức trên chỉ diễn đạt phần tổng hợp; **không đủ để tái tạo chính xác COCO AP** nếu không tuân theo score tie, crowd/ignore, giới hạn detections và area ranges của COCOeval. Mặc định thường dùng max detections 1/10/100 và chỉ số AP báo cáo sử dụng giới hạn 100, trừ khi công bố cấu hình khác. [S1–S2]

**Kiểm tra sự khác biệt với F1:** một GT và hai dự đoán trùng hộp, TP xếp trước FP: AP có thể bằng 1, nhưng nhãn cuối có $TP=1$, $FP=1$, $FN=0$, nên $F1=2/3$. Không dùng AP thay F1 để chấm chất lượng bộ nhãn cuối. Không tạo confidence giả cho nhãn người.

## 8. KITTI 3D AP_R40: công thức tham chiếu, không thay evaluator

KITTI đánh giá Car/Pedestrian/Cyclist theo difficulty **Easy / Moderate / Hard** và ngưỡng overlap được công bố cho 3D: **Car 0,70; Pedestrian và Cyclist 0,50**. Không mặc định các ngưỡng này là “KITTI official” cho Bus/Truck ngoài giao thức chính. [S7–S8]

Biểu diễn khái niệm của AP theo 40 vị trí recall:

$$
\boxed{AP_{R40}=\frac{1}{40}\sum_{j=1}^{40}p_{int}\!\left(\frac{j}{40}\right)}.
$$

**Đối chiếu:** KITTI dùng 40 vị trí recall (không tính mốc 0) thay cho giao thức AP_11 cũ. Tuy nhiên nội suy, chọn score threshold, matching, difficulty, loại đối tượng được bỏ qua và tiêu chí overlap phải tuân thủ đầy đủ evaluator KITTI tương thích; **không thể lấy thuật toán COCO rồi đổi 101 thành 40**. Công thức là mô tả khái niệm, không phải đặc tả hoàn chỉnh của official KITTI score. [S7–S8]

## 9. Mức hoàn thành và dữ liệu thiếu

$$
\boxed{Completion\ rate=\frac{n}{N}},\qquad N>0.
$$

Một ảnh **đã hoàn thành và không có đối tượng** khác với ảnh **chưa được thực hiện / lỗi xử lý**. Không âm thầm bỏ ảnh khó khỏi mẫu số; công bố coverage, các lỗi và chính sách xử lý dữ liệu thiếu. Không biến dữ liệu thiếu thành dự đoán rỗng nếu chưa quy định trước.

## 10. Đo thời gian

Với các phiên làm việc hợp lệ không chồng lấn $[t_{s,k},t_{e,k}]$:

$$
\boxed{T_{active}=\sum_k(t_{e,k}-t_{s,k})}.
$$

Nếu khoảng chồng nhau, $T_{active}$ phải bằng **độ dài hợp các khoảng thời gian làm việc**, không phải tổng cộng trùng. Phân biệt $T_{active}$ với $T_{elapsed}$ tính theo mốc bắt đầu–hoàn tất gồm chờ/nghỉ.

$$
\boxed{Throughput=\frac{N_{processed}}{T_{job}}},\qquad
\boxed{t_{amortized}=\frac{T_{job}}{N_{processed}}}.
$$

$t_{amortized}$ không mặc nhiên là latency từng request. Thời gian AI phải xác định phạm vi đo (nạp mô hình, warm-up, xử lý trước, suy luận, hậu xử lý, truyền dữ liệu); thời gian huấn luyện tính riêng. So sánh latency phải cùng phần cứng, batch size, ảnh và phạm vi đo.

### Tiết kiệm thời gian nhân công và thời gian tuần tự

$$
\boxed{Saving_{labor}=1-\frac{T_{assisted,labor}}{T_{manual,labor}}}.
$$

Nếu AI chạy trước, sau đó con người sửa tuần tự, và cùng tính trên một khối lượng mẫu:

$$
T_{assisted,seq}=T_{AI}+T_{assisted,labor},\qquad
\boxed{Saving_{seq}=1-\frac{T_{assisted,seq}}{T_{manual,labor}}}.
$$

Công thức thứ hai **không áp dụng trực tiếp khi các công việc chạy chồng thời gian**; khi đó phải đo thời gian hoàn tất thực. Mẫu số 0 → N/A. Tiết kiệm âm phải giữ giá trị âm.

## 11. Mức độ chỉnh sửa nhãn AI

Với cùng tập nhãn AI gốc đã được khóa:

$$
\boxed{Edit\ rate=\frac{N_{AI\ objects\ edited\ or\ deleted\ (unique)}}{N_{AI\ objects\ presented}}}
$$

$$
\boxed{Accept\ rate=\frac{N_{AI\ objects\ unchanged}}{N_{AI\ objects\ presented}}},\qquad
\boxed{Additions/image=\frac{N_{new\ objects}}{N_{completed\ images}}}.
$$

Nếu đối tượng AI ban đầu được phân loại duy nhất thành **giữ nguyên** hoặc **chỉnh sửa/xóa**, thì $Accept\ rate+Edit\ rate=1$. Đối tượng mới thêm **không thuộc** mẫu số nhãn AI gốc. Số lần thao tác thực khác số đối tượng đã thay đổi; chỉ đo thao tác thực khi có lịch sử sự kiện. Mẫu số 0 → N/A.

## 12. Chi phí và điều kiện quyết định

Đặt $r_h$ là đơn giá nhân công/giờ, $r_g$ là chi phí tính toán/giờ và các thành phần phí khác tính cùng đơn vị tiền:

$$
\boxed{C_{manual}=H_{manual}r_h+C_{manual,other}}
$$

$$
\boxed{C_{AI}=H_{GPU}r_g+C_{API}+C_{storage/transfer}}
$$

$$
\boxed{C_{assisted}=H_{assisted}r_h+C_{AI}+C_{assisted,other}}
$$

$$
\boxed{Saving_{cost}=1-\frac{C_{assisted}}{C_{manual}}},\qquad
\boxed{Cost/completed\ sample=\frac{C_{total}}{N_{completed}}}.
$$

Nếu phân bổ chi phí huấn luyện $C_{train}$ trên $N_{deployment}$ mẫu đã xác định trước:

$$
\boxed{C_{train,allocated\ per\ sample}=\frac{C_{train}}{N_{deployment}}}.
$$

Không đồng thời cộng đầy đủ $C_{train}$ và phần phân bổ của chính nó (tránh tính trùng). Mẫu số bằng 0 → N/A. Chỉ xét phương án chi phí thấp hơn là **đạt yêu cầu** khi chất lượng và completion vượt các ngưỡng đã chốt trước:

$$
\boxed{F1_{micro}\ge F1_{min},\qquad Recall\ge R_{min},\qquad Completion\ rate\ge C_{min}.}
$$

Các ngưỡng $F1_{min},R_{min},C_{min}$ là mục tiêu dự án, **không phải ngưỡng chính thức COCO/KITTI**.

## 13. Tổng hợp kết quả và kiểm tra độ tin cậy

**Bảng bắt buộc trên cùng benchmark:** theo phương pháp, theo lớp và theo loại hình học: số mẫu được giao/hoàn thành, TP/FP/FN, Precision, Recall, micro-F1, matched mean IoU và số cặp ghép. Báo thời gian lao động, thời gian AI, tổng chi phí, tỷ lệ chỉnh sửa/thêm/xóa. AP theo COCO/KITTI được ghi **ở bảng detector riêng**.

Nếu cần khoảng tin cậy cho chênh lệch chất lượng hoặc tiết kiệm: lấy mẫu lặp theo **đơn vị độc lập phù hợp** (ảnh hoặc cụm cảnh/video); với thiết kế paired, giữ nguyên cặp kết quả của các phương pháp khi tái lấy mẫu. Nêu rõ cách lấy mẫu và số lần lặp. Không suy rộng từ dữ liệu quá nhỏ hoặc thiếu đa dạng.

### Các phép tự kiểm tra số học cần đạt

| Phép kiểm tra | Kết quả kỳ vọng |
|---|---|
| IoU 2D hai hộp trùng nhau | $1$ |
| IoU 2D hai hộp rời nhau/chỉ chạm biên | $0$ |
| IoU đối xứng | $IoU(A,B)=IoU(B,A)$ |
| IoU 2D ví dụ ở mục 2 | $1/3$ |
| Mask IoU và Dice ví dụ ở mục 3 | $4/7$ và $8/11$ |
| IoU 3D ví dụ xoay $90^\circ$ ở mục 4 | $1/3$ |
| Matching phản ví dụ mục 5 | $2$ TP, không phải $1$ |
| TP=80, FP=20, FN=40 | $F1=8/11\approx0{,}727273$ |
| Cả GT và prediction đều rỗng | F1 và IoU cặp ghép = N/A, không tự gán $1$ |
| Tiết kiệm chi phí khi assisted đắt hơn manual | Số âm |

## 14. Kết quả đối chiếu và giới hạn xác minh

| Nội dung | Kết luận của bản tài liệu này | Mức bằng chứng |
|---|---|---|
| IoU 2D, mask IoU, Dice, IoU 3D yaw-only | Công thức đúng với định nghĩa và ví dụ số học, trong các điều kiện đã nêu | Rà soát toán học và đối chiếu tài liệu thư viện hình học |
| Matching ưu tiên số cặp rồi tổng IoU | Mục tiêu hợp lệ của giao thức **M49 riêng**; phản ví dụ khẳng định không được tối ưu tổng IoU trước | Rà soát logic toán học; không nhận là COCO/KITTI matching |
| TP/FP/FN, P/R/F1, micro/macro | Đúng theo định nghĩa chuẩn và quy tắc mẫu số của M49 | Rà soát đại số và ví dụ số |
| COCO AP_50:95, 101 recall points | Phù hợp định nghĩa tổng hợp COCO, nhưng công thức rút gọn không đủ tái hiện toàn bộ evaluator | Đối chiếu COCO API; **không chạy parity benchmark** |
| KITTI AP_R40 | 40 mốc recall và ngưỡng Car/Pedestrian/Cyclist phù hợp tài liệu KITTI; biểu thức chỉ là tóm tắt | Đối chiếu tài liệu KITTI/OpenPCDet; **không chạy parity evaluator** |
| Tiết kiệm lao động, tổng chi phí, tỷ lệ sửa nhãn | Là **định nghĩa metric vận hành của M49**, không phải chuẩn benchmark hình học | Kiểm tra định nghĩa/mẫu số, **chưa xác minh bằng log thực tế** |

**Lưu ý bằng chứng:** bản gốc nói đến 19 nhóm kiểm thử tổng hợp, 1.000 cặp bbox và 300 ma trận matching, nhưng không cung cấp kèm bộ fixture, log, kết quả chạy hay môi trường được pin để tái kiểm chứng. Tài liệu này **không tuyên bố đã chạy lại** các kiểm thử đó; cũng không tuyên bố website đã tích hợp thành công bộ chấm, đã chạy KITTI AP_R40 end-to-end hoặc có số liệu chi phí thực.

## 15. Tài liệu dùng để đối chiếu công thức

- **[S1] COCO API:** https://github.com/cocodataset/cocoapi
- **[S2] COCO evaluation protocol (`COCOeval`):** https://github.com/cocodataset/cocoapi/blob/master/PythonAPI/pycocotools/cocoeval.py
- **[S3] COCO mask representation / IoU:** https://github.com/cocodataset/cocoapi/blob/master/PythonAPI/pycocotools/mask.py
- **[S4] SciPy — Linear sum assignment (đối chiếu bản chất bài toán gán, không định nghĩa giao thức M49):** https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.linear_sum_assignment.html
- **[S5] Shapely — Geometry intersection:** https://shapely.readthedocs.io/en/stable/reference/shapely.intersection.html
- **[S6] PyTorch3D — 3D box overlap (hộp định hướng tổng quát):** https://pytorch3d.readthedocs.io/en/latest/modules/ops.html
- **[S7] KITTI 3D benchmark:** https://www.cvlibs.net/datasets/kitti/eval_object.php?obj_benchmark=3d
- **[S8] OpenPCDet — KITTI evaluator tham khảo:** https://github.com/open-mmlab/OpenPCDet/tree/master/pcdet/datasets/kitti/kitti_object_eval_python

---
