# Kế hoạch hackathon: điều khiển robot gắp hàng bằng cử chỉ

## 1. Mục tiêu và phạm vi

Trong 120 phút, nhóm 4 người xây dựng demo trên laptop gồm ba thành phần: môi trường mô phỏng 3D có một dây chuyền hàng hóa, một cánh tay robot và một giỏ; chương trình nhận diện cánh tay từ vai đến ngón tay bằng webcam; chương trình điều khiển robot từ keypoints thu được. Người dùng điều khiển vị trí ngang của đầu gắp, chụm ngón để gắp hộp, di chuyển sang giỏ và mở ngón để thả.

Ngữ cảnh sản phẩm: người vận hành trạm chuyển kiện trong kho/nhà máy VinFast hoặc giải pháp Vin Robotics. Demo chứng minh tương tác điều khiển và luồng chuyển kiện trong mô phỏng. Khả năng nâng hàng nặng và cải thiện năng suất thực tế chưa được chứng minh.

### Bắt buộc hoàn thành

- Một người, một cánh tay điều khiển; nhận diện và hiển thị vai, khuỷu, cổ tay cùng 21 mốc bàn tay/ngón tay bằng Pose Lite + Hand Landmarker. Đây là yêu cầu bắt buộc.
- Một robot có sẵn trong PyBullet, một trạm gắp dạng băng chuyền dừng, ba hộp có ID/màu khác nhau và một giỏ.
- Vị trí tay trên ảnh điều khiển X–Y trên mặt bàn; hướng đầu gắp cố định xuống dưới.
- Chụm ngón cái–trỏ để gắp, mở ngón để thả; hệ thống tự nâng/hạ.
- Chỉ gắp khi đầu gắp thực sự đủ gần hộp hợp lệ; hiển thị hộp đang được nhắm tới.
- Gắp đơn giản hóa bằng liên kết cố định tạm thời; tháo liên kết khi thả.
- Giới hạn vùng điều khiển và tốc độ; mất tracking thì tạm dừng, không tự thả hộp.
- Có reset, log đánh giá, ít nhất một ca lỗi và video dự phòng.

### Bổ sung khi luồng chính đã ổn định

Theo thứ tự: thống kê độ trễ xử lý; replay lệnh; băng chuyền chạy chậm và dừng tại trạm gắp. Cảnh 3D luôn phải có dây chuyền; chuyển động của dây chuyền là phần bổ sung, bản MVP cho dây chuyền dừng khi gắp.

Không đưa vào MVP: sao chép từng góc khớp người, điều khiển độ sâu tuyệt đối từ webcam, vật lý lực kẹp/ma sát chính xác, tránh vật cản tự động, huấn luyện model, robot thật, dashboard web.

## 2. Phân công 4 thành viên

Thay TV1–TV4 bằng tên thật khi bắt đầu. TV1 nên là người quen tích hợp Python nhất; TV3 nên là người quen robotics/mô phỏng nhất.

| Thành viên | Trách nhiệm chính | File sở hữu | Đầu ra bàn giao |
|---|---|---|---|
| TV1 — Tích hợp và điều khiển | Chốt giao diện module, ánh xạ tay → robot, làm mượt, máy trạng thái, chạy chương trình chính | `main.py`, `contracts.py`, `config.py`, `control.py`, `dev/run_control.py` | Điều khiển chạy độc lập bằng mẫu tay và phản hồi robot giả lập; sau đó ghép module thật |
| TV2 — Computer vision | Webcam, Pose Lite + Hand Landmarker, ghép đúng cánh tay và bàn tay, xuất keypoints từ vai đến ngón tay, overlay | `vision.py`, `models/`, `dev/run_vision.py` | Webcam + overlay toàn bộ cánh tay chạy độc lập và xuất `HandSample` chứa keypoints đúng hợp đồng |
| TV3 — Robot và mô phỏng | Cảnh, robot, IK, motor, gắn/thả hộp, giỏ, reset | `simulation.py`, `assets/` nếu cần, `dev/run_simulation.py` | Simulator chạy độc lập bằng bàn phím hoặc chuỗi lệnh cố định |
| TV4 — Công cụ kiểm chứng và demo | Bộ dữ liệu mẫu, robot giả lập cho tích hợp, log/CSV, tổng hợp kết quả, môi trường máy demo, video | `dev/fakes.py`, `dev/run_metrics.py`, `requirements.txt`, `metrics.py`, `README_DEMO.md`, `results/`, `DEMO_SCRIPT.md` | Bộ chạy kiểm chứng độc lập, logger và báo cáo chạy ngay trên dữ liệu mẫu; sau đó dùng dữ liệu thật |

TV4 cũng kiểm thử trải nghiệm điều khiển bằng người dùng thứ hai, không chỉ quan sát người viết code.

### Cách bảo đảm làm việc song song

**Mỗi người có một module chạy được mà không cần đợi module của người khác.** Chuỗi phụ thuộc của sản phẩm không trở thành chuỗi chờ khi phát triển.

| Thành viên | Đầu vào thay thế khi module khác chưa có | Chạy độc lập bằng lệnh dự kiến | Việc bắt đầu ngay |
|---|---|---|---|
| TV1 | Vài `HandSample` và `SimStatus` tạo trực tiếp trong runner; dùng `dev/fakes.py` khi TV4 bàn giao | `python -m dev.run_control` | Mapping, giới hạn tốc độ, chuyển trạng thái; không import MediaPipe/PyBullet |
| TV2 | Webcam trên máy của mình; không cần robot | `python -m dev.run_vision` | Nhận vai–khuỷu–cổ tay và bàn tay, vẽ landmark, xuất keypoints |
| TV3 | Điểm đích cố định hoặc phím điều khiển; không cần webcam | `python -m dev.run_simulation` | Dựng cảnh, IK, kiểm tra gắp/thả tại các điểm đã biết |
| TV4 | Sự kiện/lượt thử tổng hợp có kết quả kỳ vọng; không cần webcam hoặc simulator | `python -m dev.run_metrics` | Logger, xuất CSV, báo cáo, trường hợp thành công/thất bại/reset |

Các lệnh trên là yêu cầu triển khai, chưa tồn tại trong repo ở bước lập kế hoạch này. Mỗi người tự viết runner nhỏ cho module mình; không chờ TV4 viết xong toàn bộ bộ công cụ.

- Phút 0–5: TV1 đưa hợp đồng tối thiểu vào code; TV2 thử webcam/model, TV3 thử robot/GUI, TV4 kiểm tra dependency máy demo và tạo mẫu kết quả. Cả bốn bắt đầu đồng thời.
- Phút 5: chốt tên trường, đơn vị, chữ ký hàm và cấu hình mặc định. Sau đó từng người làm độc lập; trao đổi ngắn ngay khi phát hiện thiếu giao diện.
- Phút 15: TV4 bàn giao fake tối thiểu. Fake chỉ cần trả các trạng thái theo kịch bản, không xây một simulator thứ hai. Nếu fake chậm, TV1 vẫn dùng mẫu cục bộ.
- Các module chỉ import kiểu dữ liệu từ `contracts.py`; file này chỉ dùng thư viện chuẩn Python. `control.py` không phụ thuộc thư viện camera hoặc robot.
- Mỗi người tự cài môi trường cần cho module mình. TV4 phụ trách môi trường tích hợp trên máy demo; cả nhóm không chờ TV4 cài xong mới viết code.
- Giả định mỗi thành viên có máy phát triển hoặc phiên làm việc riêng. Máy demo dành các khung tích hợp cho TV1/TV4; TV2 và TV3 tiếp tục trên máy mình. Nếu chỉ có một máy, không thể chạy đồng thời nhiều phiên chiếm cùng webcam; phải chia lượt chạy phần cứng, còn code và kiểm tra với mẫu vẫn thực hiện độc lập.

### Tiêu chuẩn bàn giao module

Mỗi lần bàn giao gồm: commit hoặc file hoàn chỉnh trong phạm vi sở hữu, lệnh chạy độc lập, một đầu vào mẫu và đầu ra quan sát được, dependency mới nếu có, cùng lỗi còn biết. TV1 lấy phiên bản đã bàn giao để tích hợp; người sở hữu tiếp tục sửa module của mình và gửi bản tiếp theo.

Không sửa đồng thời cùng một file. Nếu cần đổi giao diện, thống nhất với TV1 trước; ưu tiên sửa cách triển khai bên trong module để giữ hợp đồng đã chốt.

### Quy tắc phối hợp

- Chỉ TV1 sửa `contracts.py` và `config.py`. TV2 đề xuất ngưỡng camera/cử chỉ; TV3 đề xuất workspace, vị trí hộp/giỏ và độ cao. TV1 cập nhật các giá trị thống nhất, các thành viên tiếp tục dùng mặc định trong lúc chờ.
- Các thành viên tự chạy module với đầu vào giả lập để phát triển; bản demo cuối phải nhận lệnh từ webcam thật.
- Nếu dùng nhiều laptop: mỗi người một branch, commit nhỏ theo mốc; TV1 tích hợp vào branch demo. Nếu dùng chung workspace: tuân thủ quyền sở hữu file ở bảng trên.
- Chốt dependency trên máy demo rồi chia sẻ cùng phiên bản; không tự nâng phiên bản giữa buổi.
- Đồng bộ tối đa 2 phút ở phút 15, 35, 60, 85 và 105, tính trong ngân sách 120 phút. Mỗi lần báo: đã chạy gì, đang vướng gì, đầu ra tiếp theo. Không để cả nhóm đứng xem một người sửa lỗi.

## 3. Kiến trúc và hợp đồng tích hợp

```text
Webcam → vision.py → HandSample → control.py → RobotCommand
                                                 ↓
                                            simulation.py
                                                 ↓
                                             SimStatus
                                                 ↓
                              main.py + overlay + metrics.py
```

`main.py` là nơi điều phối. Mọi thao tác PyBullet GUI và bước mô phỏng do một luồng sở hữu. Callback vision chỉ cập nhật mẫu mới nhất; không gọi simulator trong callback. Không xếp hàng nhiều frame hoặc lệnh cũ.

### Hợp đồng dữ liệu — chốt bản tối thiểu ở phút 5

| Kiểu | Trường tối thiểu | Quy ước |
|---|---|---|
| `HandSample` | `frame_id`, `captured_at`, `processed_at`, `valid`, `arm_side`, `arm_keypoints`, `hand_keypoints`, `pose_valid`, `hand_valid` | Tên kiểu giữ nguyên nhưng chứa toàn bộ cánh tay: `arm_keypoints` có shoulder/elbow/wrist; `hand_keypoints` có 21 mốc theo thứ tự MediaPipe. Tọa độ ảnh chuẩn hóa trên cùng ảnh lật gương; timestamp monotonic, giây |
| `RobotCommand` | `target_xyz`, `gripper_closed` | Mét trong hệ tọa độ simulator; tư thế hướng xuống cố định trong cấu hình |
| `SimStatus` | `ee_xyz`, `target_reached`, `candidate_box_id`, `held_box_id`, `placed_box_ids` | Phản hồi từ trạng thái thực trong mô phỏng, không suy ra chỉ từ lệnh đã gửi |
| `TrialRecord` | `trial_id`, `operator`, `requested_box_id`, `picked_box_id`, `placed_in_bin`, `duration_s`, `failure_reason` | Hợp đồng cho TV4; ghi tất cả lượt thử, kể cả thất bại |

`config.py` chứa workspace X–Y, vị trí các hộp/giỏ, độ cao vận chuyển/gắp/thả và ngưỡng cho phép gắn vật. TV1 và TV3 dùng cùng dữ liệu này để tránh tự giả định hai cảnh khác nhau. TV3 kiểm chứng giá trị thực tế và gửi cập nhật trước mốc phút 35.

TV2 xuất keypoints thô cùng kích thước ảnh (`image_width`, `image_height`) và chất lượng/visibility ở những trường model cung cấp. TV1 tính `u,v` của tâm lòng bàn tay và `pinch_ratio` từ keypoints trong `control.py`. `pinch_ratio` = khoảng cách đầu ngón cái–trỏ / kích thước lòng bàn tay tham chiếu. Tính khoảng cách trong cùng hệ tọa độ pixel hoặc đã sửa tỉ lệ ảnh. Mẫu thiếu tay hoặc kích thước tham chiếu quá nhỏ không được dùng để phát lệnh.

Pose và hand xử lý cùng frame trong bản đầu tiên. Ghép bàn tay với cổ tay cùng bên trên ảnh; chọn một bên cố định và kiểm tra khoảng cách hai vị trí cổ tay để tránh ghép nhầm. `valid` chỉ đúng khi cả pose, hand và phép ghép hợp lệ; thiếu vai/khuỷu hoặc bàn tay phải thể hiện trên overlay và tạm dừng điều khiển. Nếu sau này chạy pose thưa hơn hand, phải thêm timestamp riêng, kiểm tra tuổi từng kết quả và không coi kết quả cũ là cùng frame mới. Không ghép trực tiếp tọa độ world của hai model vì khác gốc tọa độ.

Không coi điểm phân loại tay trái/phải là độ tin cậy của toàn bộ landmark. Kết hợp kết quả phát hiện, kiểm tra dữ liệu và tuổi của mẫu để quyết định có dùng được hay không.

### API tối thiểu

- Vision: `start()`, `latest_sample()`, `close()`; ảnh overlay do TV2 cung cấp cho phần hiển thị.
- Điều khiển: `update(sample, sim_status, now) -> RobotCommand`, `reset()`.
- Mô phỏng: `initialize()`, `step(command, dt) -> SimStatus`, `try_attach(box_id) -> bool`, `release()`, `reset()`, `close()`.
- Log: `record_event(event)` và `save_trial(trial)`.

`RobotCommand` bổ sung `action` (`NONE`, `ATTACH`, `RELEASE`) và `box_id` tùy chọn. `control.update()` trả hành động cần thực hiện; `main.py` gửi lệnh chuyển động và gọi `try_attach`/`release` tương ứng. TV3 kiểm tra lại khoảng cách thực và tình trạng hộp; TV1 xác nhận kết quả qua `held_box_id` ở lần cập nhật kế tiếp. Không chuyển sang mang hàng chỉ vì đã phát lệnh ATTACH; các lệnh lặp không được tạo thêm liên kết hoặc đếm lại hộp. Trong runner độc lập, fake simulator cung cấp cùng phản hồi này.

TV2 cung cấp keypoints và trạng thái tracking; TV1 sở hữu duy nhất việc trích vị trí tay/cử chỉ từ keypoints, xác nhận chụm/mở theo thời gian và chuyển trạng thái. Keypoints bàn tay điều khiển vị trí đầu gắp và gắp/thả; vai–khuỷu–cổ tay dùng để hiển thị, ghép đúng tay và kiểm tra tính hợp lệ. Không yêu cầu mỗi khớp người điều khiển một khớp robot. TV3 sở hữu duy nhất liên kết vật lý và xác nhận hộp trong giỏ. TV4 nhận các sự kiện có `timestamp`, `event_type`, `trial_id`, `box_id`, `controller_state`, `reason` (trường không áp dụng có thể rỗng) và `TrialRecord`; không đọc biến nội bộ của các module.

### Quy tắc ánh xạ

- Vẽ hình chữ nhật điều khiển trên ảnh. Vị trí tay bên trong được ánh xạ tuyến tính vào một vùng X–Y đã kiểm chứng robot với tới được.
- Trái–phải của tay theo ảnh gương → X; lên–xuống của tay → Y. Hiển thị con trỏ để người dùng nhìn thấy đích.
- Z do chu trình nâng/hạ quyết định; không dùng độ sâu landmark làm khoảng cách camera tuyệt đối.
- Chọn một tư thế robot ban đầu ổn định; kiểm tra trước vị trí gắp, giỏ và đường di chuyển ở độ cao vận chuyển.
- Làm mượt nhẹ và giới hạn vận tốc; các ngưỡng đặt trong `config.py`, không rải trong nhiều file.
- Hai ngưỡng chụm/mở khác nhau, xác nhận theo thời gian và chỉ phát lệnh khi trạng thái cử chỉ thay đổi. Khởi động hoặc phục hồi tracking phải thấy tay mở ổn định trước khi nhận lệnh gắp mới.

### Máy trạng thái

```text
READY → LOWERING_PICK → LIFTING → CARRYING → LOWERING_PLACE → RELEASING → READY
                     ↘ gắp thất bại → quay về độ cao an toàn → READY

Bất kỳ trạng thái nào → PAUSED khi mất tracking hoặc nhấn phím dừng
```

- `READY`: đầu gắp ở độ cao vận chuyển, tay điều khiển X–Y; chụm hợp lệ chỉ bắt đầu gắp nếu có hộp được tô sáng.
- `LOWERING_PICK`: khóa X–Y tại hộp được chọn, hạ đầu gắp; attach chỉ khi đạt khoảng cách cho phép.
- `LIFTING`: nâng đến độ cao vận chuyển rồi mới cho tay điều khiển ngang.
- `CARRYING`: mang hộp theo tay; mở ngón chỉ bắt đầu đặt khi mục tiêu ở vùng hợp lệ của giỏ.
- `LOWERING_PLACE`: khóa X–Y, hạ hộp đến độ cao thả đã cấu hình.
- `RELEASING`: tháo liên kết; xác nhận hộp trong giỏ sau khi ổn định rồi tăng bộ đếm, nâng đầu gắp trở lại.
- `PAUSED`: giữ mục tiêu tại vị trí hiện tại, giữ nguyên trạng thái đang kẹp; không tiếp tục mục tiêu cũ. Chỉ tiếp tục sau khi tracking ổn định và người dùng xác nhận; reset luôn khả dụng.

Mở tay ngoài giỏ không làm rơi hộp trong MVP; hiển thị yêu cầu đưa hộp đến giỏ. Đây là hỗ trợ thao tác và phải được giải thích khi demo.

## 4. Lịch làm việc 120 phút

| Mốc | TV1 | TV2 | TV3 | TV4 | Điều kiện hoàn thành mốc |
|---|---|---|---|---|---|
| 0–15 | Chốt contracts/config ở phút 5; mapping chạy với mẫu keypoints cục bộ | Webcam + Pose Lite + Hand Landmarker, runner riêng | Mở PyBullet, robot mẫu, runner điều khiển điểm đích | Môi trường máy demo, fake keypoints toàn cánh tay, mẫu TrialRecord | Bốn nhánh công việc khởi động độc lập; có contract và fake tối thiểu |
| 15–35 | Trích vị trí/cử chỉ từ keypoints, lọc, máy trạng thái với fake | Ghép pose/hand, HandSample thật, overlay vai đến ngón; bàn giao bản 1 | Cảnh, IK, workspace đã kiểm chứng; bàn giao bản 1 | CSV/báo cáo từ dữ liệu mẫu; kiểm tra đủ keypoints và hợp đồng | Mỗi người có kết quả chạy riêng; đủ bản 1 để ghép |
| 35–60 | Ghép bản 1 camera → điều khiển → robot; pause/reset | Tự kiểm tra mất tay/nghiêng tay, sửa lỗi vision được báo | Làm attach/release bằng runner lệnh cố định, tô sáng hộp | Phút 35–40 kiểm tra bản ghép với TV1; sau đó hoàn thiện log và kịch bản đánh giá | Đầu gắp theo tay thật; gắp/thả chạy riêng trong simulator |
| 60–85 | Ghép toàn bộ chu trình từ các module đã có | Chỉnh độ nhạy, giữ tay đã chọn, overlay trạng thái | Hoàn thiện xác nhận hộp trong giỏ, reset, sửa lỗi vật lý | Phút 60–65 kiểm tra bản ghép với TV1; ghép logger, chạy lượt thử đầu | Một chu trình thật hoàn chỉnh, có log |
| 85–105 | Đóng băng bản ứng viên; chỉ sửa lỗi chặn demo trên bản làm việc riêng | Vận hành 5 lượt thử trên bản ứng viên, ghi ca lỗi; sau đó soạn phần giải thích vision | Kiểm tra reset/giới hạn bằng runner riêng; chuẩn bị giải thích IK | Vận hành 5 lượt còn lại, tổng hợp cả 10 lượt và ca lỗi | Có kết quả trên một phiên bản xác định; mỗi người vẫn có đầu việc riêng |
| 105–120 | Kiểm tra khởi động bản cuối, chốt kiến trúc và lời mở đầu | Diễn thao tác để quay video, chuẩn bị trả lời vision | Chuẩn bị cảnh/reset và phần robotics, hỗ trợ ca lỗi | Ghi video, chốt bảng đo và tài liệu chạy; điều phối tập demo | Có video và bằng chứng; cả nhóm tập chung một lượt cuối |

### Tích hợp có giới hạn thời gian, không dừng cả nhóm

- Phút 35–40: TV1/TV4 thử thay từng fake bằng module thật. TV2/TV3 tiếp tục đầu việc của mình, chỉ nhận lỗi thuộc module mình.
- Phút 60–65: tích hợp attach/release và log theo cùng cách. Bản module ổn định gần nhất được giữ để quay lại khi có lỗi.
- Nếu một module chưa sẵn sàng: giữ fake cho phần đó trong môi trường phát triển và tiếp tục kiểm tra các phần còn lại. Fake không được dùng để công bố đã đạt mốc webcam điều khiển robot hoặc tính thành công của demo.
- Nếu lỗi giao diện mất hơn 5 phút: chủ module sửa trong file của mình; TV1 tiếp tục phần tích hợp khác. Không để TV1 nhận sửa toàn bộ các module.
- Khi đo 10 lượt, giữ nguyên một phiên bản. Các sửa đổi đồng thời nằm trên branch/bản làm việc riêng; nếu thay bản đo thì ghi phiên bản mới và đo lại những lượt chịu ảnh hưởng. Dữ liệu mẫu luôn tách khỏi `results/` dùng cho báo cáo thật.

Theo đề bài, 120 phút build nằm sau 15 phút chọn hướng và trước 15 phút chuẩn bị demo. Kế hoạch vẫn dành 15 phút cuối build cho dự phòng để không phụ thuộc vào thời gian ngoài giờ code.

## 5. Các mốc cắt giảm phạm vi

- Phút 15: nếu cài đặt lỗi, TV4 và chủ module giải quyết ngay. Ưu tiên phiên bản Python có gói cài sẵn tương thích; tránh biên dịch thư viện trong giờ thi. Không được trì hoãn kiểm tra môi trường đến lúc tích hợp.
- Phút 35: nếu IK chưa đến được cả trạm gắp và giỏ, giảm workspace hoặc đổi vị trí cảnh; chưa làm camera đẹp hay thêm băng chuyền động.
- Phút 60: nếu điều khiển chậm, giảm độ phân giải đầu vào/tần suất xử lý và giữ frame mới nhất; vẫn phải có cả Pose Lite và Hand Landmarker. Chỉ dùng bàn tay có thể giúp chẩn đoán lỗi tạm thời nhưng không đạt yêu cầu nghiệm thu từ vai đến ngón tay.
- Phút 85: nếu chưa hoàn tất gắp–thả, giảm còn một hộp, giữ băng chuyền dừng và dùng các điểm nâng/hạ cố định. Không cố tinh chỉnh ma sát.
- Phút 105: không thêm tính năng. Chỉ sửa lỗi chặn demo, đo lại phần chịu ảnh hưởng và quay video.
- Nếu demo trực tiếp hỏng: chuyển sang video đã quay và công bố rõ đó là video dự phòng.

## 6. Kiểm chứng và điều kiện nghiệm thu

### Kiểm tra tích hợp bắt buộc

1. Khởi động và reset cảnh được trên đúng máy demo.
2. Tay di chuyển đúng chiều theo overlay; vị trí đích nằm trong workspace.
3. Chụm xa hộp không làm hộp nhảy vào đầu gắp.
4. Gắp được hộp được chỉ định; không tự chọn hộp khác khi người dùng đang chụm.
5. Hộp chỉ được tính thành công khi đã thả và nằm trong giỏ; không đếm hai lần.
6. Che tay trong lúc di chuyển hoặc đang giữ hộp: robot tạm dừng, hộp không tự rơi; có cách phục hồi rõ ràng.
7. Reset từ giữa chu trình xóa liên kết, trạng thái cử chỉ và bộ đếm cũ.
8. Webcam hiển thị liên tục vai–khuỷu–cổ tay cùng các mốc ngón tay của đúng một bên; keypoints được truyền thật sang chương trình điều khiển. Che vai/khuỷu và che bàn tay là hai tình huống cần kiểm tra riêng.
9. Cửa sổ 3D có đủ dây chuyền hàng hóa, một cánh tay robot, các hộp và một giỏ. Nói rõ dây chuyền đang dừng tại trạm gắp trong MVP.

### Bảng đo 10 lượt

Chuẩn bị trước thứ tự ID hộp cần chọn, có ít nhất hai người thao tác. Reset cảnh giữa các lượt. Ghi cả lượt thất bại, không thay bằng lượt đẹp hơn.

CSV tối thiểu: `trial_id, operator, requested_box_id, picked_box_id, placed_in_bin, duration_s, failure_reason`.

- Thành công = chọn đúng hộp yêu cầu và thả vào giỏ trong thời hạn 30 giây tính từ tín hiệu bắt đầu.
- Báo cáo: số lượt thành công/10, số lượt gắp nhầm, thời gian trung vị của các lượt thành công và số lượt dùng để tính trung vị.
- Mục tiêu nội bộ ban đầu: ít nhất 8/10 lượt thành công. Đây là tiêu chí mong muốn, không phải kết quả đã đạt.
- Nếu ghi độ trễ, tách rõ thời gian xử lý từ lúc đọc frame đến phát lệnh và thời gian robot đến đích. Không gọi thời gian xử lý nội bộ là độ trễ camera-to-display đầy đủ.

### Ca lỗi bắt buộc

Xoay nghiêng hoặc che bàn tay khiến landmark/cử chỉ không ổn định. Cho thấy tác động thực, trạng thái PAUSED khi tracking mất, và cách phục hồi. Nếu có cảnh báo sai cử chỉ dù tracking còn tồn tại, ghi rõ giới hạn này; không khẳng định pause giải quyết mọi lỗi.

## 7. Kịch bản trình bày 10 phút

| Thời lượng | Người dẫn | Nội dung |
|---|---|---|
| 0:00–1:00 | TV1 | Người dùng, thao tác chuyển kiện, giá trị giảm thao tác nâng trực tiếp |
| 1:00–3:00 | TV2 | Webcam, mốc tay, điều khiển trực tiếp; chỉ ra hộp được chọn |
| 3:00–5:00 | TV3 | Gắp–chuyển–thả; mời giám khảo chỉ định hộp hoặc thử điều khiển |
| 5:00–7:00 | TV4, TV1 hỗ trợ | Bảng đo, ca lỗi, kiến thức áp dụng và giới hạn của demo |
| 7:00–10:00 | Cả nhóm | Hỏi đáp; mỗi người trả lời phần mình và hiểu toàn bộ luồng |

Trụ cột cần giải thích: Hình học (mapping và IK), Biểu diễn (landmark và trạng thái), Thời gian (lọc và độ trễ), Bất định (tracking mất), Bằng chứng (10 lượt thử và ca lỗi).

Ước lượng tác động dùng công thức có giả định công khai, ví dụ: số lượt nâng thủ công có thể chuyển sang robot mỗi ca = số kiện thuộc phạm vi xử lý × tỷ lệ thao tác được robot thực hiện. Không chuyển số liệu mô phỏng thành tuyên bố đã giảm chấn thương hoặc đáp ứng tải trọng công nghiệp.

## 8. Bàn giao cuối buổi

- Mã nguồn và hướng dẫn chạy một lệnh trong `README_DEMO.md`.
- Phiên bản dependency đã chạy được và hướng dẫn lấy model đúng tên.
- Cấu hình workspace, ngưỡng cử chỉ và cách reset/pause.
- File kết quả 10 lượt, mô tả ca lỗi, video dự phòng có webcam và simulator.
- `DEMO_SCRIPT.md` ghi lời dẫn, phân vai và những giới hạn phải nói rõ.

## 9. Tài liệu kỹ thuật tham khảo

- MediaPipe Hand Landmarker: https://developers.google.com/edge/mediapipe/solutions/vision/hand_landmarker/python
- MediaPipe Pose Landmarker: https://developers.google.com/edge/mediapipe/solutions/vision/pose_landmarker
- PyBullet Quickstart: https://github.com/bulletphysics/bullet3/blob/master/docs/pybullet_quickstart_guide/PyBulletQuickstartGuide.md.html
- Ví dụ IK: https://github.com/bulletphysics/bullet3/blob/master/examples/pybullet/examples/inverse_kinematics.py

Kế hoạch dựa trên đề bài trong `index.html` và phạm vi MVP đã thống nhất. Chưa cài thư viện, triển khai ứng dụng hoặc đo hiệu năng trong bước lập kế hoạch này.
